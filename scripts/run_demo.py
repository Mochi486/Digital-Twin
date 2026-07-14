#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from run_ai_scenario_phase import run_routed_regression, run_single_router_dry_run, run_two_router_dry_run


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_ROOT = PROJECT_ROOT / ".local-evidence"
GENERATOR_SCRIPT = PROJECT_ROOT / "scripts" / "generate_scenario_ai.py"
LIVE_VALIDATION_SCRIPT = PROJECT_ROOT / "scripts" / "run_openai_live_validation.py"
PROMPT_AI_MOCK = "Create a six-node redundant routed topology with two candidate paths and 20 Mbps bandwidth"


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def run_command(cmd: list[str], cwd: Path = PROJECT_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def evidence_dir_for(name: str) -> Path:
    path = EVIDENCE_ROOT / f"demo-{name}-{stamp()}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_baseline() -> int:
    evidence_dir = evidence_dir_for("baseline")
    result = run_routed_regression("baseline", evidence_dir, delay_ms=0, packet_loss_percent=0)
    summary_path = evidence_dir / "demo-summary.json"
    write_json(summary_path, result)
    print(json.dumps({"command": "baseline", "evidence_dir": str(evidence_dir), "summary_file": str(summary_path), "result": result}, indent=2))
    return 0 if result["success"] else 1


def run_two_router() -> int:
    evidence_dir = evidence_dir_for("two-router")
    result = run_two_router_dry_run(evidence_dir)
    summary_path = evidence_dir / "demo-summary.json"
    write_json(summary_path, result)
    print(json.dumps({"command": "two-router", "evidence_dir": str(evidence_dir), "summary_file": str(summary_path), "result": result}, indent=2))
    return 0 if result["exit_code"] == 0 else 1


def run_delay_smoke() -> int:
    evidence_dir = evidence_dir_for("delay-smoke")
    result = run_routed_regression("delay-smoke", evidence_dir, delay_ms=30, packet_loss_percent=0)
    summary_path = evidence_dir / "demo-summary.json"
    write_json(summary_path, result)
    print(json.dumps({"command": "delay-smoke", "evidence_dir": str(evidence_dir), "summary_file": str(summary_path), "result": result}, indent=2))
    return 0 if result["success"] else 1


def run_loss_smoke() -> int:
    evidence_dir = evidence_dir_for("loss-smoke")
    result = run_routed_regression(
        "packet-loss-smoke",
        evidence_dir,
        delay_ms=0,
        packet_loss_percent=3,
        ping_count=50,
        ping_interval_s=0.05,
    )
    summary_path = evidence_dir / "demo-summary.json"
    write_json(summary_path, result)
    print(json.dumps({"command": "loss-smoke", "evidence_dir": str(evidence_dir), "summary_file": str(summary_path), "result": result}, indent=2))
    return 0 if result["success"] else 1


def run_ai_mock() -> int:
    evidence_dir = evidence_dir_for("ai-mock")
    scenario_path = evidence_dir / "ai-mock-scenario.json"
    report_path = evidence_dir / "ai-mock-report.json"
    dry_run_path = evidence_dir / "ai-mock-dry-run.json"
    plot_path = evidence_dir / "ai-mock-topology.svg"
    cmd = [
        sys.executable,
        str(GENERATOR_SCRIPT),
        "--provider",
        "mock",
        "--prompt",
        PROMPT_AI_MOCK,
        "--output-scenario",
        str(scenario_path),
        "--report",
        str(report_path),
        "--dry-run-output",
        str(dry_run_path),
        "--plot",
        str(plot_path),
    ]
    result = run_command(cmd)
    payload = {
        "command": "ai-mock",
        "evidence_dir": str(evidence_dir),
        "scenario_file": str(scenario_path),
        "report_file": str(report_path),
        "dry_run_file": str(dry_run_path),
        "plot_file": str(plot_path),
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    summary_path = evidence_dir / "demo-summary.json"
    write_json(summary_path, payload)
    print(json.dumps({"command": "ai-mock", "evidence_dir": str(evidence_dir), "summary_file": str(summary_path), "exit_code": result.returncode}, indent=2))
    return result.returncode


def run_ai_live() -> int:
    cmd = [sys.executable, str(LIVE_VALIDATION_SCRIPT), "--provider", "openai_compatible"]
    compat_model = os.environ.get("COMPAT_MODEL", "").strip()
    if compat_model:
        cmd.extend(["--model", compat_model])
    result = run_command(cmd)
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    return result.returncode


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run validated Digital Twin demos. "
            "baseline=single-router real run, two-router=generic topology dry-run, "
            "delay-smoke/loss-smoke=small routed regressions, ai-mock=mock AI dry-run, "
            "ai-live=compatible-provider live validation."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [
        ("baseline", "Run the single-router routed baseline real experiment."),
        ("two-router", "Run the generic two-router topology dry-run."),
        ("delay-smoke", "Run the bounded 30 ms routed delay smoke experiment."),
        ("loss-smoke", "Run the bounded 3 percent routed packet-loss smoke experiment."),
        ("ai-mock", "Generate and dry-run a mock AI topology."),
        ("ai-live", "Run the compatible-provider live validation flow."),
    ]:
        subparsers.add_parser(name, help=help_text)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "baseline":
        return run_baseline()
    if args.command == "two-router":
        return run_two_router()
    if args.command == "delay-smoke":
        return run_delay_smoke()
    if args.command == "loss-smoke":
        return run_loss_smoke()
    if args.command == "ai-mock":
        return run_ai_mock()
    if args.command == "ai-live":
        return run_ai_live()
    raise RuntimeError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
