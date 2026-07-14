#!/usr/bin/env python3
import argparse
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from ai_scenario_utils import (
    count_simple_paths,
    OPENAI_SYSTEM_PROMPT,
    build_validation_gate_report,
    default_topology_name,
)
from openai_live_utils import (
    create_provider_client,
    list_accessible_models,
    redact_data,
    redact_text,
    request_structured_scenario,
    resolve_openai_model,
    resolve_provider_model,
    sanitize_provider_host,
)
from topology_utils import build_graph_adjacency, shortest_path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_ROOT = PROJECT_ROOT / ".local-evidence"
RUNS_ROOT = PROJECT_ROOT / "runs"
SIMULATOR_SCRIPT = PROJECT_ROOT / "scripts" / "simulator_topology.py"
PREPARE_SCRIPT = PROJECT_ROOT / "scripts" / "prepare_wsl_docker.py"
IS_WINDOWS = os.name == "nt"
WSL_PYTHON = "/mnt/d/home/fanys23/project_70/.venv-wsl311/bin/python"
PROMPT = (
    "Create a connected six-node routed network topology with one client,\n"
    "one server, four routers, two alternative paths, 20 Mbps bandwidth,\n"
    "10 ms one-way delay, 0 percent packet loss, and one TCP traffic flow\n"
    "from the client to the server."
)
MAX_REQUEST_ATTEMPTS = 3


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["openai", "openai_compatible"], default="openai_compatible")
    parser.add_argument("--prompt", default=PROMPT)
    parser.add_argument("--max-attempts", type=int, default=MAX_REQUEST_ATTEMPTS)
    parser.add_argument("--api-key-stdin", action="store_true")
    parser.add_argument("--model", default="")
    parser.add_argument(
        "--endpoint-order",
        nargs="+",
        choices=["responses_json_schema", "chat_json_schema", "chat_json_object", "chat_plain_json"],
        default=None,
    )
    parser.add_argument("--skip-model-list", action="store_true")
    return parser.parse_args()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(redact_data(payload), indent=2) + "\n", encoding="utf-8")


def to_wsl_path(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    remainder = resolved.as_posix().split(":", 1)[1].lstrip("/")
    return f"/mnt/{drive}/{remainder}"


def run_command(cmd: list[str], cwd: Path = PROJECT_ROOT, stdout_path: Path | None = None):
    if stdout_path is None:
        return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    with stdout_path.open("w", encoding="utf-8") as log_file:
        return subprocess.run(cmd, cwd=cwd, text=True, stdout=log_file, stderr=subprocess.STDOUT)


def run_wsl_bash(command: str, stdout_path: Path | None = None):
    return run_command(["wsl", "bash", "-lc", command], cwd=PROJECT_ROOT, stdout_path=stdout_path)


def build_wsl_python_command(script_path: Path, *args: str) -> str:
    parts = [shlex.quote(WSL_PYTHON), shlex.quote(to_wsl_path(script_path))]
    parts.extend(shlex.quote(arg) for arg in args)
    return " ".join(parts)


def verify_docker_available(evidence_dir: Path) -> dict:
    docker_version_log = evidence_dir / "docker-version.txt"
    docker_info_log = evidence_dir / "docker-info.txt"
    if IS_WINDOWS:
        version_result = run_wsl_bash("docker version", stdout_path=docker_version_log)
        info_result = run_wsl_bash("docker info", stdout_path=docker_info_log)
    else:
        version_result = run_command(["docker", "version"], stdout_path=docker_version_log)
        info_result = run_command(["docker", "info"], stdout_path=docker_info_log)
    return {
        "status": "ok" if version_result.returncode == 0 and info_result.returncode == 0 else "error",
        "docker_version_exit_code": version_result.returncode,
        "docker_info_exit_code": info_result.returncode,
        "docker_version_log": str(docker_version_log),
        "docker_info_log": str(docker_info_log),
    }


def run_simulator_dry_run(scenario_path: Path, evidence_dir: Path, prefix: str) -> dict:
    output_path = evidence_dir / f"{prefix}-dry-run.json"
    plot_path = evidence_dir / f"{prefix}-dry-run.svg"
    if IS_WINDOWS:
        result = run_wsl_bash(
            build_wsl_python_command(
                SIMULATOR_SCRIPT,
                "--scenario",
                to_wsl_path(scenario_path),
                "--output",
                to_wsl_path(output_path),
                "--plot",
                to_wsl_path(plot_path),
                "--dry-run",
            )
        )
    else:
        result = run_command(
            [
                sys.executable,
                str(SIMULATOR_SCRIPT),
                "--scenario",
                str(scenario_path),
                "--output",
                str(output_path),
                "--plot",
                str(plot_path),
                "--dry-run",
            ]
        )
    record = {
        "status": "ok" if result.returncode == 0 and output_path.exists() else "error",
        "exit_code": result.returncode,
        "stdout": redact_text(result.stdout),
        "stderr": redact_text(result.stderr),
        "metrics_file": str(output_path),
        "plot_file": str(plot_path),
    }
    if output_path.exists():
        record["metrics"] = json.loads(output_path.read_text(encoding="utf-8"))
    return record


def _select_client_server_path(metrics: dict) -> list[str]:
    for route in metrics.get("static_routes", []):
        path = route.get("path", [])
        if path and path[0] == "node-1" and path[-1] == "node-5":
            return path
    for route in metrics.get("static_routes", []):
        path = route.get("path", [])
        if path and path[0] == "node-1" and path[-1] == "node-6":
            return path
    for route in metrics.get("static_routes", []):
        path = route.get("path", [])
        if path and path[0] == "node-1":
            return path
    return []


def _build_source_destination_path(scenario: dict) -> tuple[list[str], int]:
    traffic = scenario["traffic"]
    adjacency = build_graph_adjacency([node["id"] for node in scenario["nodes"]], scenario["links"])
    path = shortest_path(adjacency, traffic["source"], traffic["destination"])
    alternative_path_count = count_simple_paths(adjacency, traffic["source"], traffic["destination"], limit=32)
    return path, alternative_path_count


def run_real_validation(scenario_path: Path, evidence_dir: Path, tracked_run_dir: Path, prefix: str) -> dict:
    tracked_run_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = tracked_run_dir / "metrics.json"
    plot_path = tracked_run_dir / "topology.svg"
    prepare_log = evidence_dir / f"{prefix}-prepare.log"
    simulator_log = evidence_dir / f"{prefix}-simulator.log"

    if IS_WINDOWS:
        sim_result = run_wsl_bash(
            build_wsl_python_command(
                SIMULATOR_SCRIPT,
                "--scenario",
                to_wsl_path(scenario_path),
                "--output",
                to_wsl_path(metrics_path),
                "--plot",
                to_wsl_path(plot_path),
                "--prepare-host-routing-log",
                to_wsl_path(prepare_log),
            ),
            stdout_path=simulator_log,
        )
        prepare_rc = 0 if prepare_log.exists() else 1
    else:
        sim_result = run_command(
            [
                sys.executable,
                str(SIMULATOR_SCRIPT),
                "--scenario",
                str(scenario_path),
                "--output",
                str(metrics_path),
                "--plot",
                str(plot_path),
                "--prepare-host-routing-log",
                str(prepare_log),
            ],
            stdout_path=simulator_log,
        )
        prepare_rc = 0 if prepare_log.exists() else 1
    record = {
        "status": "ok" if sim_result.returncode == 0 and prepare_rc == 0 and metrics_path.exists() else "error",
        "simulator_exit_code": sim_result.returncode,
        "prepare_exit_code": prepare_rc,
        "metrics_file": str(metrics_path),
        "plot_file": str(plot_path),
        "prepare_log": str(prepare_log),
        "simulator_log": str(simulator_log),
    }
    if metrics_path.exists():
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        selected_path, alternative_path_count = _build_source_destination_path(scenario)
        route_verification = metrics.get("route_verification", [])
        record["metrics"] = metrics
        record["container_count"] = metrics.get("resource_estimate", {}).get("node_count")
        record["network_count"] = metrics.get("resource_estimate", {}).get("network_count")
        record["selected_path"] = selected_path
        record["hop_count"] = len(selected_path) - 1 if selected_path else None
        record["route_verification_status"] = "passed" if route_verification and all(item.get("matched") for item in route_verification) else "failed"
        record["alternative_path_count"] = alternative_path_count
        record["qdisc_verification_status"] = "passed" if metrics.get("router_qdisc_state") else "failed"
    return record


def cleanup_and_check_residuals(scenario_path: Path, evidence_dir: Path, prefix: str) -> dict:
    cleanup_metrics = evidence_dir / f"{prefix}-cleanup-metrics.json"
    if IS_WINDOWS:
        result = run_wsl_bash(
            build_wsl_python_command(
                SIMULATOR_SCRIPT,
                "--scenario",
                to_wsl_path(scenario_path),
                "--output",
                to_wsl_path(cleanup_metrics),
                "--cleanup-only",
            )
        )
        containers = run_wsl_bash("docker ps -a --format '{{.Names}}'")
        networks = run_wsl_bash("docker network ls --format '{{.Name}}'")
    else:
        result = run_command(
            [
                sys.executable,
                str(SIMULATOR_SCRIPT),
                "--scenario",
                str(scenario_path),
                "--output",
                str(cleanup_metrics),
                "--cleanup-only",
            ]
        )
        containers = run_command(["docker", "ps", "-a", "--format", "{{.Names}}"])
        networks = run_command(["docker", "network", "ls", "--format", "{{.Name}}"])
    residual_containers = [
        line.strip()
        for line in containers.stdout.splitlines()
        if line.strip().startswith(("node-", "client", "router", "server"))
    ]
    residual_networks = [
        line.strip()
        for line in networks.stdout.splitlines()
        if line.strip().startswith("net_")
    ]
    return {
        "status": "ok" if result.returncode == 0 and not residual_containers and not residual_networks else "error",
        "cleanup_exit_code": result.returncode,
        "cleanup_metrics_file": str(cleanup_metrics),
        "residual_containers": residual_containers,
        "residual_networks": residual_networks,
    }


def run_secret_scan(project_root: Path) -> dict:
    hits = []
    excluded = {
        "scripts/openai_live_utils.py",
        "scripts/run_openai_live_validation.py",
        "tests/test_openai_live_utils.py",
    }
    for pattern in ("sk-", "OPENAI_API_KEY=", "COMPAT_API_KEY="):
        result = run_command(
            [
                "git",
                "grep",
                "-n",
                pattern,
                "--",
                "README.md",
                "docs",
                "scripts",
                "tests",
                "data",
                "runs",
                ".gitignore",
            ],
            cwd=project_root,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                normalized = line.replace("\\", "/")
                if any(normalized.startswith(prefix + ":") for prefix in excluded):
                    continue
                hits.append(redact_text(line))
    return {"status": "clean" if not hits else "findings", "hits": hits}


def capability_matrix_filename(provider: str) -> str:
    return f"{provider.replace('_', '-')}-capability-matrix.json"


def build_probe_matrix(provider: str, client, model_list_record: dict, selected_model: str, endpoint_order: list[str]) -> tuple[list[dict], dict | None]:
    matrix = []
    selected = None
    accessible_models = model_list_record.get("model_ids", []) if model_list_record.get("status") == "ok" else []
    if accessible_models and selected_model not in accessible_models:
        matrix.append(
            {
                "model": selected_model,
                "model_exists": False,
                "endpoint_type": None,
                "json_schema_support": False,
                "json_object_support": False,
                "request_status": "model_missing",
                "status_code": None,
                "error_type": "model_missing",
                "error_message": "Model not present in provider model list.",
                "latency_seconds": None,
                "selected": False,
            }
        )
        return matrix, None
    for endpoint_type in endpoint_order:
        result = request_structured_scenario(
            client,
            PROMPT,
            selected_model,
            OPENAI_SYSTEM_PROMPT,
            endpoint_type,
        )
        row = {
            "model": selected_model,
            "model_exists": True,
            "endpoint_type": endpoint_type,
            "json_schema_support": endpoint_type == "chat_json_schema" and result["status"] == "ok",
            "json_object_support": endpoint_type == "chat_json_object" and result["status"] == "ok",
            "request_status": result.get("status"),
            "status_code": result.get("status_code"),
            "error_type": result.get("error_type"),
            "error_message": result.get("error_message"),
            "latency_seconds": result.get("latency_seconds"),
            "response_id": result.get("response_id"),
            "usage": result.get("usage"),
            "selected": False,
            "probe_result": redact_data(result),
        }
        matrix.append(row)
        if result["status"] == "ok":
            row["selected"] = True
            selected = row
            break
    return matrix, selected


def build_attempt_record(attempt_number: int, provider: str, model: str, endpoint_type: str, provider_result: dict, validation: dict | None) -> dict:
    record = {
        "attempt": attempt_number,
        "provider": provider,
        "model": model,
        "endpoint_type": endpoint_type,
        "request_timestamp": provider_result.get("request_timestamp"),
        "response_id": provider_result.get("response_id"),
        "usage": provider_result.get("usage"),
        "latency_seconds": provider_result.get("latency_seconds"),
        "status": provider_result.get("status"),
        "raw_structured_json_response": provider_result.get("structured_output"),
        "raw_response": provider_result.get("raw_response"),
        "validation": None,
    }
    if validation is not None:
        record["validation"] = {
            "valid": validation["valid"],
            "gates": validation["gates"],
            "schema_validation": validation["schema_validation"],
            "semantic_validation": validation["semantic_validation"],
            "prompt_constraint_validation": validation["prompt_constraint_validation"],
            "projection_validation": validation["projection_validation"],
        }
        record["normalization"] = {
            "before": provider_result.get("structured_output"),
            "after": validation.get("projected_scenario"),
            "reasons": [
                "deterministic subnet allocation from base_cidr 10.64.0.0/16",
                "deterministic endpoint IP assignment per point-to-point subnet",
                "deterministic shortest-path static route generation",
            ],
        }
    if provider_result.get("status") != "ok":
        record["error_type"] = provider_result.get("error_type")
        record["status_code"] = provider_result.get("status_code")
        record["error_message"] = provider_result.get("error_message")
        record["error_payload"] = provider_result.get("error_payload")
    return redact_data(record)


def summary_filename(provider: str) -> str:
    return f"{provider.replace('_', '-')}-live-summary.json"


def main() -> int:
    args = parse_args()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    provider_slug = args.provider.replace("_", "-")
    evidence_dir = EVIDENCE_ROOT / f"{provider_slug}-live-validation-{timestamp}"
    tracked_run_dir = RUNS_ROOT / f"{provider_slug}-live-validation-{timestamp}"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    api_key_override = None
    stdin_key_length = 0
    if args.api_key_stdin:
        api_key_override = sys.stdin.read().strip()
        stdin_key_length = len(api_key_override)

    api_key_env = "OPENAI_API_KEY" if args.provider == "openai" else "COMPAT_API_KEY"
    base_url_env = "COMPAT_BASE_URL" if args.provider == "openai_compatible" else ""
    env_key_length = len(os.environ.get(api_key_env, ""))
    base_url = os.environ.get(base_url_env, "") if base_url_env else ""
    selected_model = resolve_provider_model(args.provider, args.model or os.environ.get("COMPAT_MODEL", ""))
    endpoint_order = args.endpoint_order
    if endpoint_order is None:
        endpoint_order = (
            ["chat_json_schema", "chat_json_object", "chat_plain_json"]
            if args.provider == "openai_compatible"
            else ["responses_json_schema"]
        )

    summary = {
        "status": "started",
        "prompt": args.prompt,
        "provider": args.provider,
        "api_key_present": bool(api_key_override or os.environ.get(api_key_env)),
        "api_key_debug": {
            "stdin_key_length": stdin_key_length,
            "env_key_length": env_key_length,
        },
        "sanitized_provider_host": sanitize_provider_host(base_url),
        "sdk_status": None,
        "docker_status": None,
        "selected_model": selected_model,
        "endpoint_order": endpoint_order,
        "model_list": None,
        "capability_matrix_file": None,
        "capability_matrix": [],
        "selected_probe": None,
        "attempts": [],
        "selected_attempt": None,
        "final_scenario_file": None,
        "dry_run": None,
        "real_run": None,
        "cleanup": None,
        "secret_scan": None,
        "tracked_run_dir": str(tracked_run_dir),
        "evidence_dir": str(evidence_dir),
        "error": None,
    }

    client, sdk_status = create_provider_client(args.provider, api_key_override=api_key_override)
    summary["sdk_status"] = sdk_status
    if client is None:
        summary["status"] = "blocked"
        summary["error"] = {
            "type": sdk_status.get("error_type"),
            "message": sdk_status.get("error_message"),
        }
        write_json(evidence_dir / summary_filename(args.provider), summary)
        return 1

    model_list_record = None
    if not args.skip_model_list:
        model_list_record = list_accessible_models(client)
        summary["model_list"] = model_list_record
        if model_list_record["status"] != "ok":
            summary["status"] = "blocked"
            summary["error"] = {
                "type": model_list_record.get("error_type"),
                "status_code": model_list_record.get("status_code"),
                "message": model_list_record.get("error_message"),
            }
            write_json(evidence_dir / summary_filename(args.provider), summary)
            return 1
    else:
        summary["model_list"] = {"status": "skipped_by_request"}

    capability_matrix, selected_probe = build_probe_matrix(
        args.provider,
        client,
        model_list_record or {"status": "skipped_by_request", "model_ids": []},
        selected_model,
        endpoint_order,
    )
    matrix_path = evidence_dir / capability_matrix_filename(args.provider)
    write_json(matrix_path, capability_matrix)
    summary["capability_matrix_file"] = str(matrix_path)
    summary["capability_matrix"] = capability_matrix
    summary["selected_probe"] = selected_probe
    if selected_probe is None:
        summary["status"] = "blocked"
        summary["error"] = {
            "type": "no_supported_model",
            "message": "All candidate models failed capability probing or were unavailable.",
        }
        write_json(evidence_dir / summary_filename(args.provider), summary)
        return 1

    docker_status = verify_docker_available(evidence_dir)
    summary["docker_status"] = docker_status
    if docker_status["status"] != "ok":
        summary["status"] = "blocked"
        summary["error"] = {"type": "docker_unavailable", "message": "WSL Docker Engine is unavailable."}
        write_json(evidence_dir / summary_filename(args.provider), summary)
        return 1

    selected_endpoint = selected_probe["endpoint_type"]
    selected_probe_result = selected_probe.get("probe_result", {})
    first_success_consumed = bool(selected_probe_result)
    for attempt_number in range(1, args.max_attempts + 1):
        if first_success_consumed and attempt_number == 1:
            provider_result = selected_probe_result
        else:
            provider_result = request_structured_scenario(
                client,
                args.prompt,
                selected_model,
                OPENAI_SYSTEM_PROMPT,
                selected_endpoint,
            )
        validation = None
        if provider_result["status"] == "ok":
            validation = build_validation_gate_report(
                provider_result["structured_output"],
                args.prompt,
                topology_name=default_topology_name(args.prompt),
            )
        attempt_record = build_attempt_record(
            attempt_number,
            args.provider,
            selected_model,
            selected_endpoint,
            provider_result,
            validation,
        )
        attempt_path = evidence_dir / f"{provider_slug}-attempt-{attempt_number:02d}.json"
        write_json(attempt_path, attempt_record)
        summary["attempts"].append({**attempt_record, "attempt_file": str(attempt_path)})

        if provider_result["status"] != "ok":
            if attempt_number == args.max_attempts:
                summary["status"] = "blocked"
                summary["error"] = {
                    "type": provider_result.get("error_type"),
                    "status_code": provider_result.get("status_code"),
                    "message": provider_result.get("error_message"),
                }
            continue

        if validation and validation["valid"]:
            summary["selected_attempt"] = attempt_number
            scenario_path = tracked_run_dir / "scenario.json"
            write_json(scenario_path, validation["projected_scenario"])
            summary["final_scenario_file"] = str(scenario_path)
            raw_json_path = evidence_dir / f"{provider_slug}-raw-response.json"
            validation_path = evidence_dir / f"{provider_slug}-validation-report.json"
            write_json(raw_json_path, provider_result["structured_output"])
            write_json(validation_path, validation)
            dry_run = run_simulator_dry_run(scenario_path, evidence_dir, provider_slug)
            summary["dry_run"] = dry_run
            if dry_run["status"] != "ok":
                summary["status"] = "blocked"
                summary["error"] = {"type": "dry_run_failed", "message": "Simulator dry-run failed."}
                break
            real_run = run_real_validation(scenario_path, evidence_dir, tracked_run_dir, provider_slug)
            summary["real_run"] = real_run
            cleanup = cleanup_and_check_residuals(scenario_path, evidence_dir, provider_slug)
            summary["cleanup"] = cleanup
            summary["status"] = "completed" if real_run["status"] == "ok" and cleanup["status"] == "ok" else "blocked"
            if summary["status"] != "completed":
                summary["error"] = {"type": "real_run_failed", "message": "Real Docker validation failed."}
            break

        if attempt_number == args.max_attempts:
            summary["status"] = "blocked"
            summary["error"] = {
                "type": "validation_failed",
                "message": "Structured output validation failed after the maximum allowed attempts.",
            }

    if summary["status"] == "started":
        summary["status"] = "blocked"
        summary["error"] = {"type": "validation_failed", "message": "No valid live scenario was produced."}
    summary["secret_scan"] = run_secret_scan(PROJECT_ROOT)
    write_json(evidence_dir / summary_filename(args.provider), summary)
    return 0 if summary["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
