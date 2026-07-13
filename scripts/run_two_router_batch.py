import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from topology_utils import build_topology_svg, load_topology_scenario, summarize_numeric

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCENARIO_PATH = PROJECT_ROOT / "data" / "scenario_two_router_topology.json"
RUNS_ROOT = PROJECT_ROOT / "runs"
EVIDENCE_ROOT = PROJECT_ROOT / ".local-evidence"
PREPARE_SCRIPT = PROJECT_ROOT / "scripts" / "prepare_wsl_docker.py"
SIMULATOR_SCRIPT = PROJECT_ROOT / "scripts" / "simulator_topology.py"

BASELINE_RUNS = 5
BASELINE_DELAY_MS = 0
BASELINE_PACKET_LOSS_PERCENT = 0
DELAY_REGRESSION_MS = 30
LOSS_REGRESSION_PERCENT = 3


def ensure_root():
    result = subprocess.run(["id", "-u"], capture_output=True, text=True, check=True)
    if result.stdout.strip() != "0":
        raise RuntimeError("run_two_router_batch.py must run as root for prepare_wsl_docker.py.")


def select_edge_links(scenario):
    edge_links = []
    node_by_id = {node["id"]: node for node in scenario["nodes"]}
    for link in scenario["links"]:
        source_type = node_by_id[link["source"]]["type"]
        target_type = node_by_id[link["target"]]["type"]
        if "router" in (source_type, target_type) and source_type != target_type:
            edge_links.append(link)
    return edge_links


def configure_impairments(scenario, delay_ms, packet_loss_percent):
    for link in scenario["links"]:
        link["delay_ms"] = 0
        link["packet_loss_percent"] = 0
    for link in select_edge_links(scenario):
        link["delay_ms"] = delay_ms
        link["packet_loss_percent"] = packet_loss_percent


def run_once(scenario_text, run_name, evidence_dir, run_dir, smoke_mode=False):
    scenario = json.loads(scenario_text)
    run_dir.mkdir(parents=True, exist_ok=True)
    scenario_path = run_dir / "scenario.json"
    metrics_path = run_dir / "metrics.json"
    plot_path = run_dir / "topology.svg"
    simulator_log = evidence_dir / f"{run_name}-simulator.log"
    prepare_log = evidence_dir / f"{run_name}-prepare.log"

    scenario_path.write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")

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

    cmd = [
        sys.executable,
        str(SIMULATOR_SCRIPT),
        "--scenario",
        str(scenario_path),
        "--output",
        str(metrics_path),
        "--plot",
        str(plot_path),
    ]
    if smoke_mode:
        cmd.append("--smoke")

    with simulator_log.open("w", encoding="utf-8") as log_file:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            text=True,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
    prepare_rc = prepare_proc.wait()

    record = {
        "run_name": run_name,
        "success": result.returncode == 0 and prepare_rc == 0 and metrics_path.exists(),
        "simulator_exit_code": result.returncode,
        "prepare_exit_code": prepare_rc,
        "metrics_file": str(metrics_path),
        "plot_file": str(plot_path),
    }
    if record["success"]:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        record.update(
            {
                "throughput_mbps": metrics["throughput_mbps"],
                "ping_success": metrics["ping_success"],
                "ping_packet_loss_percent": metrics["ping_packet_loss_percent"],
                "ping_rtt_avg_ms": metrics["ping_rtt_avg_ms"],
            }
        )
    return record


def main():
    ensure_root()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    evidence_dir = EVIDENCE_ROOT / f"two-router-phase-{stamp}"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = RUNS_ROOT / f"two_router_batch_{stamp}"
    runs_dir.mkdir(parents=True, exist_ok=True)

    base_scenario = load_topology_scenario(SCENARIO_PATH)
    build_topology_svg(base_scenario, evidence_dir / "two-router-topology.svg")
    scenario_text = SCENARIO_PATH.read_text(encoding="utf-8")
    results = {"baseline": [], "delay_regression": None, "loss_regression": None}

    baseline_scenario = json.loads(scenario_text)
    configure_impairments(baseline_scenario, BASELINE_DELAY_MS, BASELINE_PACKET_LOSS_PERCENT)
    baseline_text = json.dumps(baseline_scenario, indent=2) + "\n"
    for run_index in range(1, BASELINE_RUNS + 1):
        run_name = f"baseline_run_{run_index:02d}"
        results["baseline"].append(
            run_once(
                baseline_text,
                run_name,
                evidence_dir,
                runs_dir / run_name,
            )
        )

    delay_scenario = json.loads(scenario_text)
    configure_impairments(delay_scenario, DELAY_REGRESSION_MS, BASELINE_PACKET_LOSS_PERCENT)
    results["delay_regression"] = run_once(
        json.dumps(delay_scenario, indent=2) + "\n",
        "delay_regression_30ms",
        evidence_dir,
        runs_dir / "delay_regression_30ms",
    )

    loss_scenario = json.loads(scenario_text)
    configure_impairments(loss_scenario, BASELINE_DELAY_MS, LOSS_REGRESSION_PERCENT)
    loss_scenario["traffic"]["ping_count"] = 100
    loss_scenario["traffic"]["ping_interval_s"] = 0.05
    results["loss_regression"] = run_once(
        json.dumps(loss_scenario, indent=2) + "\n",
        "loss_regression_3pct",
        evidence_dir,
        runs_dir / "loss_regression_3pct",
    )

    successful_baselines = [run for run in results["baseline"] if run["success"]]
    throughput_mean = (
        summarize_numeric([run["throughput_mbps"] for run in successful_baselines])["mean"]
        if successful_baselines
        else None
    )

    summary = {
        "baseline_runs": BASELINE_RUNS,
        "successful_baseline_runs": len(successful_baselines),
        "throughput_mean_mbps": throughput_mean,
        "results": results,
        "topology_plot": str(evidence_dir / "two-router-topology.svg"),
    }
    summary_path = evidence_dir / "two-router-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_dir": str(evidence_dir), "summary_file": str(summary_path)}, indent=2))


if __name__ == "__main__":
    main()
