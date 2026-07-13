#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_ROOT = PROJECT_ROOT / ".local-evidence"
RUNS_ROOT = PROJECT_ROOT / "runs"
GENERATOR_SCRIPT = PROJECT_ROOT / "scripts" / "generate_scenario_ai.py"
SIMULATOR_SCRIPT = PROJECT_ROOT / "scripts" / "simulator_topology.py"

SCENARIO_SPECS = [
    {
        "name": "linear-5",
        "prompt": "Create a five-node linear routed topology with 20 Mbps bandwidth and 10 ms delay",
        "attempt_real_run": True,
    },
    {
        "name": "redundant-6",
        "prompt": "Create a six-node redundant routed topology with two candidate paths and 20 Mbps bandwidth",
        "attempt_real_run": False,
    },
    {
        "name": "lossy-8",
        "prompt": "Create an eight-node routed topology with 20 Mbps bandwidth and 1% packet loss",
        "attempt_real_run": True,
    },
]
OPENAI_PROBE_PROMPT = "Create a five-node linear routed topology with 20 Mbps bandwidth and 10 ms delay"

REGRESSION_SCENARIOS = [
    "data/scenario_routed.json",
    "data/scenario_two_router_topology.json",
]


def run_command(cmd: list[str], cwd: Path = PROJECT_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def docker_available() -> bool:
    result = run_command(["where.exe", "docker"])
    return result.returncode == 0


def generate_scenario(spec: dict, evidence_dir: Path) -> dict:
    scenario_path = evidence_dir / f"{spec['name']}-scenario.json"
    report_path = evidence_dir / f"{spec['name']}-report.json"
    dry_run_path = evidence_dir / f"{spec['name']}-dry-run.json"
    plot_path = evidence_dir / f"{spec['name']}-plot.svg"
    result = run_command(
        [
            sys.executable,
            str(GENERATOR_SCRIPT),
            "--provider",
            "mock",
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
        "prompt": spec["prompt"],
        "generator_exit_code": result.returncode,
        "generator_stdout": result.stdout,
        "generator_stderr": result.stderr,
        "scenario_file": str(scenario_path),
        "report_file": str(report_path),
        "dry_run_file": str(dry_run_path),
        "plot_file": str(plot_path),
    }
    if report_path.exists():
        record["report"] = json.loads(report_path.read_text(encoding="utf-8"))
    return record


def run_openai_probe(evidence_dir: Path) -> dict:
    report_path = evidence_dir / "openai-provider-report.json"
    scenario_path = evidence_dir / "openai-provider-scenario.json"
    dry_run_path = evidence_dir / "openai-provider-dry-run.json"
    plot_path = evidence_dir / "openai-provider-plot.svg"
    result = run_command(
        [
            sys.executable,
            str(GENERATOR_SCRIPT),
            "--provider",
            "openai",
            "--prompt",
            OPENAI_PROBE_PROMPT,
            "--report",
            str(report_path),
            "--output-scenario",
            str(scenario_path),
            "--dry-run-output",
            str(dry_run_path),
            "--plot",
            str(plot_path),
        ]
    )
    record = {
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "report_file": str(report_path),
    }
    if report_path.exists():
        record["report"] = json.loads(report_path.read_text(encoding="utf-8"))
    return record


def simulator_dry_run(spec: dict, evidence_dir: Path, scenario_path: Path) -> dict:
    metrics_path = evidence_dir / f"{spec['name']}-simulator-dry-run.json"
    plot_path = evidence_dir / f"{spec['name']}-simulator-topology.svg"
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


def simulator_real_run(spec: dict, evidence_dir: Path, scenario_path: Path) -> dict:
    metrics_path = evidence_dir / f"{spec['name']}-metrics.json"
    plot_path = evidence_dir / f"{spec['name']}-real-topology.svg"
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
            "--smoke",
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


def regression_dry_run(path: str, evidence_dir: Path) -> dict:
    scenario_path = PROJECT_ROOT / path
    output_name = scenario_path.stem + "-regression-dry-run.json"
    plot_name = scenario_path.stem + "-regression.svg"
    result = run_command(
        [
            sys.executable,
            str(SIMULATOR_SCRIPT),
            "--scenario",
            str(scenario_path),
            "--output",
            str(evidence_dir / output_name),
            "--plot",
            str(evidence_dir / plot_name),
            "--dry-run",
        ]
    )
    return {
        "scenario": path,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    evidence_dir = EVIDENCE_ROOT / f"ai-scenario-phase-{stamp}"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    live_api_status = "not_run_missing_api_key"
    if os.environ.get("OPENAI_API_KEY"):
        live_api_status = "not_run_key_present"

    summary = {
        "evidence_dir": str(evidence_dir),
        "docker_available": docker_available(),
        "live_api_status": live_api_status,
        "openai_probe": run_openai_probe(evidence_dir),
        "generated_scenarios": [],
        "regressions": [],
    }

    for spec in SCENARIO_SPECS:
        generated = generate_scenario(spec, evidence_dir)
        scenario_path = Path(generated["scenario_file"])
        generated["simulator_dry_run"] = simulator_dry_run(spec, evidence_dir, scenario_path)
        if spec["attempt_real_run"] and summary["docker_available"]:
            generated["simulator_real_run"] = simulator_real_run(spec, evidence_dir, scenario_path)
        else:
            generated["simulator_real_run"] = {
                "skipped": True,
                "reason": "docker_unavailable" if not summary["docker_available"] else "not_selected",
            }
        summary["generated_scenarios"].append(generated)

    for path in REGRESSION_SCENARIOS:
        summary["regressions"].append(regression_dry_run(path, evidence_dir))

    summary_path = evidence_dir / "ai-scenario-phase-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_dir": str(evidence_dir), "summary_file": str(summary_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
