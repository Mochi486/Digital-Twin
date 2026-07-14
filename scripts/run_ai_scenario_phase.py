#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from ai_scenario_utils import validate_and_project_generated_scenario


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_ROOT = PROJECT_ROOT / ".local-evidence"
RUNS_ROOT = PROJECT_ROOT / "runs"
GENERATOR_SCRIPT = PROJECT_ROOT / "scripts" / "generate_scenario_ai.py"
SIMULATOR_SCRIPT = PROJECT_ROOT / "scripts" / "simulator_topology.py"
ROUTED_SIMULATOR_SCRIPT = PROJECT_ROOT / "scripts" / "simulator_routed.py"
PREPARE_SCRIPT = PROJECT_ROOT / "scripts" / "prepare_wsl_docker.py"
IMAGE_NAME = "my-iperf-tc"

MOCK_SCENARIO_SPECS = [
    {
        "name": "linear-5",
        "prompt": "Create a five-node linear routed topology with 20 Mbps bandwidth and 10 ms delay",
        "provider": "mock",
        "real_runs": 2,
    },
    {
        "name": "redundant-6",
        "prompt": "Create a six-node redundant routed topology with two candidate paths and 20 Mbps bandwidth",
        "provider": "mock",
        "real_runs": 1,
    },
    {
        "name": "lossy-8",
        "prompt": "Create an eight-node routed topology with 20 Mbps bandwidth and 1% packet loss",
        "provider": "mock",
        "real_runs": 1,
    },
]
OPENAI_SCENARIO_SPEC = {
    "name": "openai-live-6",
    "prompt": "Create a six-node redundant routed topology with two candidate paths, 25 Mbps bandwidth, and 8 ms delay",
    "provider": "openai",
    "real_runs": 1,
}


def run_command(cmd: list[str], cwd: Path = PROJECT_ROOT, check: bool = False, stdout_path: Path | None = None):
    if stdout_path is None:
        result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    else:
        with stdout_path.open("w", encoding="utf-8") as log_file:
            result = subprocess.run(cmd, cwd=cwd, text=True, stdout=log_file, stderr=subprocess.STDOUT)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}")
    return result


def ensure_root():
    if os.geteuid() != 0:
        raise RuntimeError("run_ai_scenario_phase.py must run as root inside WSL.")


def ensure_experiment_image(evidence_dir: Path) -> dict:
    inspect = run_command(["docker", "image", "inspect", IMAGE_NAME])
    build_log = evidence_dir / "docker-build.log"
    if inspect.returncode == 0:
        return {"status": "existing", "build_log": None}
    build_result = run_command(
        ["docker", "build", "-f", "Dockerfile.iperf", "-t", IMAGE_NAME, "."],
        check=False,
        stdout_path=build_log,
    )
    return {
        "status": "built" if build_result.returncode == 0 else "build_failed",
        "build_log": str(build_log),
        "exit_code": build_result.returncode,
    }


def verify_wsl_docker(evidence_dir: Path) -> dict:
    version_log = evidence_dir / "docker-version.txt"
    info_log = evidence_dir / "docker-info.txt"
    hello_log = evidence_dir / "docker-hello-world.txt"
    version_result = run_command(["docker", "version"], stdout_path=version_log)
    info_result = run_command(["docker", "info"], stdout_path=info_log)
    hello_result = run_command(["docker", "run", "--rm", "hello-world"], stdout_path=hello_log)
    image_status = ensure_experiment_image(evidence_dir)
    return {
        "docker_version_exit_code": version_result.returncode,
        "docker_info_exit_code": info_result.returncode,
        "hello_world_exit_code": hello_result.returncode,
        "docker_version_log": str(version_log),
        "docker_info_log": str(info_log),
        "hello_world_log": str(hello_log),
        "image_status": image_status,
        "ok": version_result.returncode == 0 and info_result.returncode == 0 and hello_result.returncode == 0,
    }


def generate_scenario(spec: dict, evidence_dir: Path) -> dict:
    scenario_path = evidence_dir / f"{spec['name']}-scenario.json"
    report_path = evidence_dir / f"{spec['name']}-report.json"
    dry_run_path = evidence_dir / f"{spec['name']}-generator-dry-run.json"
    plot_path = evidence_dir / f"{spec['name']}-generator.svg"
    result = run_command(
        [
            sys.executable,
            str(GENERATOR_SCRIPT),
            "--provider",
            spec["provider"],
            "--prompt",
            spec["prompt"],
            "--output-scenario",
            str(scenario_path),
            "--report",
            str(report_path),
            "--dry-run-output",
            str(dry_run_path),
            "--plot",
            str(plot_path),
        ]
    )
    record = {
        "name": spec["name"],
        "provider": spec["provider"],
        "prompt": spec["prompt"],
        "generator_exit_code": result.returncode,
        "generator_stdout": result.stdout,
        "generator_stderr": result.stderr,
        "scenario_file": str(scenario_path),
        "report_file": str(report_path),
        "generator_dry_run_file": str(dry_run_path),
        "generator_plot_file": str(plot_path),
    }
    if report_path.exists():
        record["report"] = json.loads(report_path.read_text(encoding="utf-8"))
    return record


def simulator_dry_run(name: str, scenario_path: Path, evidence_dir: Path) -> dict:
    metrics_path = evidence_dir / f"{name}-simulator-dry-run.json"
    plot_path = evidence_dir / f"{name}-simulator-dry-run.svg"
    result = run_command(
        [
            sys.executable,
            str(SIMULATOR_SCRIPT),
            "--scenario",
            str(scenario_path),
            "--output",
            str(metrics_path),
            "--plot",
            str(plot_path),
            "--dry-run",
        ]
    )
    record = {
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "metrics_file": str(metrics_path),
        "plot_file": str(plot_path),
    }
    if metrics_path.exists():
        record["metrics"] = json.loads(metrics_path.read_text(encoding="utf-8"))
    return record


def run_prepare_and_simulator(name: str, scenario_path: Path, evidence_dir: Path, smoke: bool = False) -> dict:
    run_dir = RUNS_ROOT / evidence_dir.name / name
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = run_dir / "metrics.json"
    plot_path = run_dir / "topology.svg"
    simulator_log = evidence_dir / f"{name}-simulator.log"
    prepare_log = evidence_dir / f"{name}-prepare.log"

    cmd = [
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
    ]
    if smoke:
        cmd.append("--smoke")
    sim_result = run_command(cmd, stdout_path=simulator_log)
    prepare_rc = 0 if prepare_log.exists() else 1

    record = {
        "success": sim_result.returncode == 0 and prepare_rc == 0 and metrics_path.exists(),
        "simulator_exit_code": sim_result.returncode,
        "prepare_exit_code": prepare_rc,
        "metrics_file": str(metrics_path),
        "plot_file": str(plot_path),
        "simulator_log": str(simulator_log),
        "prepare_log": str(prepare_log),
    }
    if metrics_path.exists():
        record["metrics"] = json.loads(metrics_path.read_text(encoding="utf-8"))
    return record


def validate_invalid_cases(evidence_dir: Path) -> dict:
    cases = {
        "disconnected_topology": {
            "nodes": [{"id": "node-1", "role": "client"}, {"id": "node-2", "role": "router"}, {"id": "node-3", "role": "server"}],
            "links": [{"source": "node-1", "target": "node-2"}],
            "traffic": {"source": "node-1", "destination": "node-3", "protocol": "tcp", "duration_s": 2, "ping_count": 4, "reverse": True},
        },
        "duplicate_link": {
            "nodes": [{"id": "node-1", "role": "client"}, {"id": "node-2", "role": "server"}],
            "links": [{"source": "node-1", "target": "node-2"}, {"source": "node-2", "target": "node-1"}],
            "traffic": {"source": "node-1", "destination": "node-2", "protocol": "tcp", "duration_s": 2, "ping_count": 4, "reverse": True},
        },
        "illegal_node_role": {
            "nodes": [{"id": "node-1", "role": "client"}, {"id": "node-2", "role": "switch"}],
            "links": [{"source": "node-1", "target": "node-2"}],
            "traffic": {"source": "node-1", "destination": "node-2", "protocol": "tcp", "duration_s": 2, "ping_count": 4, "reverse": True},
        },
        "over_node_limit": {
            "nodes": [{"id": f"node-{index}", "role": "router"} for index in range(1, 12)],
            "links": [{"source": f"node-{index}", "target": f"node-{index + 1}"} for index in range(1, 11)],
            "traffic": {"source": "node-1", "destination": "node-11", "protocol": "tcp", "duration_s": 2, "ping_count": 4, "reverse": True},
        },
        "invalid_impairment_ranges": {
            "nodes": [{"id": "node-1", "role": "client"}, {"id": "node-2", "role": "server"}],
            "links": [{"source": "node-1", "target": "node-2", "bandwidth_mbps": -1, "delay_ms": 999, "packet_loss_percent": 55}],
            "traffic": {"source": "node-1", "destination": "node-2", "protocol": "tcp", "duration_s": 2, "ping_count": 4, "reverse": True},
        },
        "forbidden_command_content": {
            "nodes": [{"id": "docker-run", "role": "client"}, {"id": "node-2", "role": "server"}],
            "links": [{"source": "docker-run", "target": "node-2", "packet_loss_percent": 0}],
            "traffic": {
                "source": "docker-run",
                "destination": "node-2",
                "protocol": "tcp",
                "duration_s": 2,
                "ping_count": 4,
                "reverse": True,
            },
        },
        "schema_mismatch": ["this", "is", "not", "an", "object"],
    }
    cases["over_node_limit"]["nodes"][0]["role"] = "client"
    cases["over_node_limit"]["nodes"][-1]["role"] = "server"

    results = {}
    for name, candidate in cases.items():
        results[name] = validate_and_project_generated_scenario(candidate, f"invalid-{name}")
    output_path = evidence_dir / "invalid-scenario-validation.json"
    output_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return {"results": results, "output_file": str(output_path)}


def run_single_router_dry_run(evidence_dir: Path) -> dict:
    metrics_path = evidence_dir / "single-router-dry-run.json"
    plot_path = evidence_dir / "single-router-dry-run.svg"
    scenario_path = PROJECT_ROOT / "data" / "scenario_two_router_topology.json"
    compact = {
        "topology_name": "single-router-compact",
        "nodes": [{"id": "client1"}, {"id": "router1"}, {"id": "server1"}],
        "links": [
            {"source": "client1", "target": "router1", "delay_ms": 0, "packet_loss_percent": 0},
            {"source": "router1", "target": "server1", "bandwidth_mbps": 20, "delay_ms": 0, "packet_loss_percent": 0},
        ],
        "traffic": {"source": "client1", "destination": "server1", "protocol": "tcp", "duration_s": 2, "ping_count": 3, "reverse": True},
    }
    scenario_path = evidence_dir / "single-router-scenario.json"
    scenario_path.write_text(json.dumps(compact, indent=2) + "\n", encoding="utf-8")
    result = run_command([sys.executable, str(SIMULATOR_SCRIPT), "--scenario", str(scenario_path), "--output", str(metrics_path), "--plot", str(plot_path), "--dry-run"])
    return {
        "exit_code": result.returncode,
        "scenario_file": str(scenario_path),
        "metrics_file": str(metrics_path),
        "plot_file": str(plot_path),
    }


def run_two_router_dry_run(evidence_dir: Path) -> dict:
    metrics_path = evidence_dir / "two-router-dry-run.json"
    plot_path = evidence_dir / "two-router-dry-run.svg"
    scenario_path = PROJECT_ROOT / "data" / "scenario_two_router_topology.json"
    result = run_command([sys.executable, str(SIMULATOR_SCRIPT), "--scenario", str(scenario_path), "--output", str(metrics_path), "--plot", str(plot_path), "--dry-run"])
    return {
        "exit_code": result.returncode,
        "metrics_file": str(metrics_path),
        "plot_file": str(plot_path),
    }


def run_routed_regression(name: str, evidence_dir: Path, delay_ms: int, packet_loss_percent: int, ping_count: int = 5, ping_interval_s: float | None = None) -> dict:
    scenario = json.loads((PROJECT_ROOT / "data" / "scenario_routed.json").read_text(encoding="utf-8"))
    scenario["links"][1]["delay_ms"] = delay_ms
    scenario["links"][1]["packet_loss_percent"] = packet_loss_percent
    scenario["traffic"]["ping_count"] = ping_count
    if ping_interval_s is not None:
        scenario["traffic"]["ping_interval_s"] = ping_interval_s
    elif "ping_interval_s" in scenario["traffic"]:
        scenario["traffic"].pop("ping_interval_s")

    run_dir = RUNS_ROOT / evidence_dir.name / name
    run_dir.mkdir(parents=True, exist_ok=True)
    scenario_path = run_dir / "scenario.json"
    scenario_path.write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")
    metrics_path = run_dir / "metrics.json"
    prepare_log = evidence_dir / f"{name}-prepare.log"
    simulator_log = evidence_dir / f"{name}-simulator.log"

    sim_result = run_command(
        [
            sys.executable,
            str(ROUTED_SIMULATOR_SCRIPT),
            "--scenario",
            str(scenario_path),
            "--output",
            str(metrics_path),
            "--prepare-host-routing-log",
            str(prepare_log),
        ],
        stdout_path=simulator_log,
    )
    prepare_rc = 0 if prepare_log.exists() else 1
    record = {
        "success": sim_result.returncode == 0 and prepare_rc == 0 and metrics_path.exists(),
        "simulator_exit_code": sim_result.returncode,
        "prepare_exit_code": prepare_rc,
        "metrics_file": str(metrics_path),
        "prepare_log": str(prepare_log),
        "simulator_log": str(simulator_log),
    }
    if metrics_path.exists():
        record["metrics"] = json.loads(metrics_path.read_text(encoding="utf-8"))
    return record


def main() -> int:
    ensure_root()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    evidence_dir = EVIDENCE_ROOT / f"ai-scenario-phase-{stamp}"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "evidence_dir": str(evidence_dir),
        "docker_verification": verify_wsl_docker(evidence_dir),
        "openai_api_key_present": bool(os.environ.get("OPENAI_API_KEY")),
        "invalid_scenario_validation": validate_invalid_cases(evidence_dir),
        "mock_scenarios": [],
        "openai_scenario": None,
        "regressions": {},
    }

    for spec in MOCK_SCENARIO_SPECS:
        generated = generate_scenario(spec, evidence_dir)
        scenario_path = Path(generated["scenario_file"])
        generated["simulator_dry_run"] = simulator_dry_run(spec["name"], scenario_path, evidence_dir)
        generated["real_runs"] = []
        for run_index in range(1, spec["real_runs"] + 1):
            generated["real_runs"].append(run_prepare_and_simulator(f"{spec['name']}-real-run-{run_index:02d}", scenario_path, evidence_dir))
        summary["mock_scenarios"].append(generated)

    if summary["openai_api_key_present"]:
        generated = generate_scenario(OPENAI_SCENARIO_SPEC, evidence_dir)
        report = generated.get("report", {})
        if generated["generator_exit_code"] == 0 and report.get("provider_result", {}).get("status") == "ok":
            scenario_path = Path(generated["scenario_file"])
            generated["simulator_dry_run"] = simulator_dry_run(OPENAI_SCENARIO_SPEC["name"], scenario_path, evidence_dir)
            generated["real_runs"] = [run_prepare_and_simulator(f"{OPENAI_SCENARIO_SPEC['name']}-real-run-01", scenario_path, evidence_dir)]
        else:
            generated["simulator_dry_run"] = None
            generated["real_runs"] = []
        summary["openai_scenario"] = generated

    summary["regressions"]["single_router_dry_run"] = run_single_router_dry_run(evidence_dir)
    summary["regressions"]["two_router_dry_run"] = run_two_router_dry_run(evidence_dir)
    summary["regressions"]["delay_smoke"] = run_routed_regression("delay-smoke", evidence_dir, delay_ms=30, packet_loss_percent=0)
    summary["regressions"]["packet_loss_smoke"] = run_routed_regression(
        "packet-loss-smoke",
        evidence_dir,
        delay_ms=0,
        packet_loss_percent=3,
        ping_count=50,
        ping_interval_s=0.05,
    )

    summary_path = evidence_dir / "ai-scenario-phase-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_dir": str(evidence_dir), "summary_file": str(summary_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
