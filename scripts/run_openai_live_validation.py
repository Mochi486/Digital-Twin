#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from ai_scenario_utils import OPENAI_SYSTEM_PROMPT, build_validation_gate_report, default_topology_name
from openai_live_utils import (
    choose_fallback_model,
    create_openai_client,
    is_model_access_error,
    list_accessible_models,
    redact_data,
    redact_text,
    request_structured_scenario,
    resolve_openai_model,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_ROOT = PROJECT_ROOT / ".local-evidence"
RUNS_ROOT = PROJECT_ROOT / "runs"
SIMULATOR_SCRIPT = PROJECT_ROOT / "scripts" / "simulator_topology.py"
PREPARE_SCRIPT = PROJECT_ROOT / "scripts" / "prepare_wsl_docker.py"
PROMPT = (
    "Create a connected six-node routed network topology with one client,\n"
    "one server, four routers, two alternative paths, 20 Mbps bandwidth,\n"
    "10 ms one-way delay, 0 percent packet loss, and one TCP traffic flow\n"
    "from the client to the server."
)
MAX_REQUEST_ATTEMPTS = 3


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default=PROMPT)
    parser.add_argument("--max-attempts", type=int, default=MAX_REQUEST_ATTEMPTS)
    parser.add_argument("--api-key-stdin", action="store_true")
    return parser.parse_args()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_command(cmd: list[str], cwd: Path = PROJECT_ROOT, stdout_path: Path | None = None):
    if stdout_path is None:
        return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    with stdout_path.open("w", encoding="utf-8") as log_file:
        return subprocess.run(cmd, cwd=cwd, text=True, stdout=log_file, stderr=subprocess.STDOUT)


def verify_docker_available(evidence_dir: Path) -> dict:
    docker_version_log = evidence_dir / "docker-version.txt"
    docker_info_log = evidence_dir / "docker-info.txt"
    version_result = run_command(["docker", "version"], stdout_path=docker_version_log)
    info_result = run_command(["docker", "info"], stdout_path=docker_info_log)
    return {
        "status": "ok" if version_result.returncode == 0 and info_result.returncode == 0 else "error",
        "docker_version_exit_code": version_result.returncode,
        "docker_info_exit_code": info_result.returncode,
        "docker_version_log": str(docker_version_log),
        "docker_info_log": str(docker_info_log),
    }


def run_simulator_dry_run(scenario_path: Path, evidence_dir: Path) -> dict:
    output_path = evidence_dir / "openai-live-dry-run.json"
    plot_path = evidence_dir / "openai-live-dry-run.svg"
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


def run_real_validation(scenario_path: Path, evidence_dir: Path, tracked_run_dir: Path) -> dict:
    tracked_run_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = tracked_run_dir / "metrics.json"
    plot_path = tracked_run_dir / "topology.svg"
    prepare_log = evidence_dir / "openai-live-prepare.log"
    simulator_log = evidence_dir / "openai-live-simulator.log"

    prepare_proc = subprocess.Popen(
        [
            sys.executable,
            str(PREPARE_SCRIPT),
            "--scenario",
            str(scenario_path),
            "--ignore-existing",
            "--evidence",
            str(prepare_log),
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        text=True,
    )
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
        ],
        stdout_path=simulator_log,
    )
    prepare_rc = prepare_proc.wait()
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
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        selected_path = []
        if metrics.get("static_routes"):
            selected_path = metrics["static_routes"][0].get("path", [])
        record["metrics"] = metrics
        record["selected_path"] = selected_path
        record["hop_count"] = len(selected_path) - 1 if selected_path else None
    return record


def cleanup_and_check_residuals(scenario_path: Path, evidence_dir: Path) -> dict:
    cleanup_metrics = evidence_dir / "cleanup-metrics.json"
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
    for pattern in ("sk-", "OPENAI_API_KEY="):
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
            hits.extend(redact_text(line) for line in result.stdout.splitlines() if line.strip())
    return {"status": "clean" if not hits else "findings", "hits": hits}


def build_attempt_record(attempt_number: int, model: str, provider_result: dict, validation: dict | None) -> dict:
    record = {
        "attempt": attempt_number,
        "provider": "openai",
        "model": model,
        "request_timestamp": provider_result.get("request_timestamp"),
        "response_id": provider_result.get("response_id"),
        "usage": provider_result.get("usage"),
        "status": provider_result.get("status"),
        "raw_structured_json_response": provider_result.get("structured_output"),
        "validation": None,
    }
    if validation is not None:
        record["validation"] = {
            "valid": validation["valid"],
            "gates": validation["gates"],
            "schema_validation": validation["schema_validation"],
            "semantic_validation": validation["semantic_validation"],
            "projection_validation": validation["projection_validation"],
        }
    if provider_result.get("status") != "ok":
        record["error_type"] = provider_result.get("error_type")
        record["status_code"] = provider_result.get("status_code")
        record["error_message"] = provider_result.get("error_message")
        record["error_payload"] = provider_result.get("error_payload")
    return redact_data(record)


def main() -> int:
    args = parse_args()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    evidence_dir = EVIDENCE_ROOT / f"openai-live-validation-{timestamp}"
    tracked_run_dir = RUNS_ROOT / f"openai-live-validation-{timestamp}"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    api_key_override = None
    stdin_key_length = 0
    if args.api_key_stdin:
        api_key_override = sys.stdin.read().strip()
        stdin_key_length = len(api_key_override)
    env_key_length = len(os.environ.get("OPENAI_API_KEY", ""))

    summary = {
        "status": "started",
        "prompt": args.prompt,
        "provider": "openai",
        "api_key_present": bool(api_key_override or os.environ.get("OPENAI_API_KEY")),
        "api_key_debug": {
            "stdin_key_length": stdin_key_length,
            "env_key_length": env_key_length,
        },
        "sdk_status": None,
        "docker_status": None,
        "model_resolution": None,
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

    client, sdk_status = create_openai_client(api_key_override=api_key_override)
    summary["sdk_status"] = sdk_status
    if client is None:
        summary["status"] = "blocked"
        summary["error"] = {
            "type": sdk_status.get("error_type"),
            "message": sdk_status.get("error_message"),
        }
        write_json(evidence_dir / "openai-live-summary.json", summary)
        return 1

    docker_status = verify_docker_available(evidence_dir)
    summary["docker_status"] = docker_status
    if docker_status["status"] != "ok":
        summary["status"] = "blocked"
        summary["error"] = {"type": "docker_unavailable", "message": "WSL Docker Engine is unavailable."}
        write_json(evidence_dir / "openai-live-summary.json", summary)
        return 1

    requested_model = resolve_openai_model("")
    final_model = requested_model
    model_resolution = {"requested_model": requested_model, "final_model": None, "accessible_models": None}

    for attempt_number in range(1, args.max_attempts + 1):
        provider_result = request_structured_scenario(client, args.prompt, final_model, OPENAI_SYSTEM_PROMPT)
        validation = None
        if provider_result["status"] == "ok":
            validation = build_validation_gate_report(
                provider_result["structured_output"],
                args.prompt,
                topology_name=default_topology_name(args.prompt),
            )
        attempt_record = build_attempt_record(attempt_number, final_model, provider_result, validation)
        attempt_path = evidence_dir / f"openai-attempt-{attempt_number:02d}.json"
        write_json(attempt_path, attempt_record)
        summary["attempts"].append({**attempt_record, "attempt_file": str(attempt_path)})

        if provider_result["status"] != "ok":
            if is_model_access_error(
                provider_result.get("error_type"),
                provider_result.get("status_code"),
                provider_result.get("error_message"),
            ):
                accessible_record = list_accessible_models(client)
                model_resolution["accessible_models"] = accessible_record
                fallback_model = choose_fallback_model(accessible_record.get("model_ids", []))
                if fallback_model and fallback_model != final_model:
                    final_model = fallback_model
                    continue
            summary["status"] = "blocked"
            summary["error"] = {
                "type": provider_result.get("error_type"),
                "status_code": provider_result.get("status_code"),
                "message": provider_result.get("error_message"),
            }
            break

        if validation and validation["valid"]:
            summary["selected_attempt"] = attempt_number
            model_resolution["final_model"] = final_model
            scenario_path = tracked_run_dir / "scenario.json"
            write_json(scenario_path, validation["projected_scenario"])
            summary["final_scenario_file"] = str(scenario_path)
            dry_run = run_simulator_dry_run(scenario_path, evidence_dir)
            summary["dry_run"] = dry_run
            if dry_run["status"] != "ok":
                summary["status"] = "blocked"
                summary["error"] = {"type": "dry_run_failed", "message": "Simulator dry-run failed."}
                break
            real_run = run_real_validation(scenario_path, evidence_dir, tracked_run_dir)
            summary["real_run"] = real_run
            cleanup = cleanup_and_check_residuals(scenario_path, evidence_dir)
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

    model_resolution["final_model"] = model_resolution["final_model"] or final_model
    summary["model_resolution"] = model_resolution
    summary["secret_scan"] = run_secret_scan(PROJECT_ROOT)
    write_json(evidence_dir / "openai-live-summary.json", redact_data(summary))
    return 0 if summary["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
