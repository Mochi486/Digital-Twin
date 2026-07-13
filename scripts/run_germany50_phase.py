import json
import subprocess
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from topology_utils import (
    build_resource_estimate,
    build_topology_svg,
    choose_path_length_samples,
    load_topology_scenario,
    select_connected_subset,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS_ROOT = PROJECT_ROOT / "runs"
EVIDENCE_ROOT = PROJECT_ROOT / ".local-evidence"
PREPARE_SCRIPT = PROJECT_ROOT / "scripts" / "prepare_wsl_docker.py"
SIMULATOR_SCRIPT = PROJECT_ROOT / "scripts" / "simulator_topology.py"
IMPORT_SCRIPT = PROJECT_ROOT / "scripts" / "import_germany50.py"
RAW_GML_PATH = PROJECT_ROOT / "data" / "external" / "germany50" / "gml" / "Dfn.gml"
SCENARIO_PATH = PROJECT_ROOT / "data" / "scenario_germany50.json"
METADATA_PATH = PROJECT_ROOT / "data" / "external" / "germany50" / "source-metadata.json"
SOURCE_URL = "https://adelaide.figshare.com/articles/dataset/Internet_Topology_Zoo_Data_Set_/30153949"


def ensure_root():
    result = subprocess.run(["id", "-u"], capture_output=True, text=True, check=True)
    if result.stdout.strip() != "0":
        raise RuntimeError("run_germany50_phase.py must run as root for prepare_wsl_docker.py.")


def run_command(cmd, cwd=PROJECT_ROOT):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def import_source():
    result = subprocess.run(
        [
            sys.executable,
            str(IMPORT_SCRIPT),
            "--source-gml",
            str(RAW_GML_PATH),
            "--output-scenario",
            str(SCENARIO_PATH),
            "--metadata-output",
            str(METADATA_PATH),
            "--source-url",
            SOURCE_URL,
            "--topology-name",
            "germany50-dfn",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout


def write_scenario(path: Path, scenario: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")


def assign_traffic_endpoint_roles(scenario: dict):
    source = scenario["traffic"]["source"]
    destination = scenario["traffic"]["destination"]
    for node in scenario["nodes"]:
        if node["id"] == source:
            node["type"] = "client"
        elif node["id"] == destination:
            node["type"] = "server"
        else:
            node["type"] = "router"


def run_prepare_and_simulator(name: str, scenario_path: Path, evidence_dir: Path, smoke=False, dry_run=False):
    run_dir = RUNS_ROOT / evidence_dir.name / name
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = run_dir / ("dry-run.json" if dry_run else "metrics.json")
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
    ]
    if smoke:
        cmd.append("--smoke")
    if dry_run:
        cmd.append("--dry-run")

    prepare_rc = 0
    if not dry_run:
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
    else:
        prepare_proc = None

    with simulator_log.open("w", encoding="utf-8") as log_file:
        sim_result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            text=True,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

    if prepare_proc is not None:
        prepare_rc = prepare_proc.wait()

    record = {
        "name": name,
        "success": sim_result.returncode == 0 and prepare_rc == 0 and metrics_path.exists(),
        "simulator_exit_code": sim_result.returncode,
        "prepare_exit_code": prepare_rc,
        "metrics_file": str(metrics_path),
        "plot_file": str(plot_path),
    }
    if metrics_path.exists():
        record["metrics"] = json.loads(metrics_path.read_text(encoding="utf-8"))
    return record


def configure_pair_scenario(base_scenario: dict, pair: tuple[str, str], hop_count: int):
    scenario = {
        "topology_name": base_scenario["topology_name"],
        "source_metadata": base_scenario.get("source_metadata", {}),
        "addressing": base_scenario.get("addressing", {}),
        "route_generation_mode": "traffic_endpoint_subnets",
        "nodes": [
            {
                key: value
                for key, value in node.items()
                if key in {"id", "type", "original_id", "original_label", "country", "latitude", "longitude"}
            }
            for node in base_scenario["nodes"]
        ],
        "links": [
            {
                key: value
                for key, value in link.items()
                if key in {"source", "target", "delay_ms", "packet_loss_percent", "bandwidth_mbps"}
            }
            for link in base_scenario["links"]
        ],
        "traffic": {},
    }
    scenario["traffic"]["source"] = pair[0]
    scenario["traffic"]["destination"] = pair[1]
    scenario["traffic"]["duration_s"] = 2
    scenario["traffic"]["ping_count"] = 5
    scenario["traffic"].pop("destination_ip", None)
    scenario["traffic"]["reverse"] = True
    scenario["experiment_metadata"] = {"pair": pair, "hop_count": hop_count}
    assign_traffic_endpoint_roles(scenario)
    return scenario


def main():
    ensure_root()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    evidence_dir = EVIDENCE_ROOT / f"germany50-phase-{stamp}"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    import_source()
    scenario = load_topology_scenario(SCENARIO_PATH)
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    build_topology_svg(scenario, evidence_dir / "germany50-topology.svg")

    subset5 = select_connected_subset(scenario, 5)
    subset10 = select_connected_subset(scenario, 10)
    assign_traffic_endpoint_roles(subset5)
    assign_traffic_endpoint_roles(subset10)
    subset5_path = evidence_dir / "scenario-germany50-subset-5.json"
    subset10_path = evidence_dir / "scenario-germany50-subset-10.json"
    write_scenario(subset5_path, subset5)
    write_scenario(subset10_path, subset10)

    dry_run_result = run_prepare_and_simulator("germany50-dry-run", SCENARIO_PATH, evidence_dir, dry_run=True)
    smoke5_result = run_prepare_and_simulator("germany50-subset-5-smoke", subset5_path, evidence_dir, smoke=True)
    smoke10_result = run_prepare_and_simulator("germany50-subset-10-smoke", subset10_path, evidence_dir, smoke=True)

    path_samples = choose_path_length_samples(scenario)
    full_start_results = {}
    resource_estimate = build_resource_estimate(scenario)
    can_attempt_full = resource_estimate["node_count"] <= 60 and resource_estimate["network_count"] <= 90

    if can_attempt_full:
        for key, sample in path_samples.items():
            pair_scenario = configure_pair_scenario(scenario, sample["pair"], sample["hop_count"])
            pair_path = evidence_dir / f"scenario-{key}.json"
            write_scenario(pair_path, pair_scenario)
            full_start_results[key] = run_prepare_and_simulator(
                f"germany50-{key}-path",
                pair_path,
                evidence_dir,
                smoke=False,
            )
            full_start_results[key]["pair"] = sample["pair"]
            full_start_results[key]["path"] = sample["path"]
            full_start_results[key]["hop_count"] = sample["hop_count"]

    summary = {
        "source": metadata,
        "resource_estimate": resource_estimate,
        "dry_run": dry_run_result,
        "subset_5_smoke": smoke5_result,
        "subset_10_smoke": smoke10_result,
        "path_samples": path_samples,
        "full_start_attempted": can_attempt_full,
        "full_start_results": full_start_results,
        "topology_plot": str(evidence_dir / "germany50-topology.svg"),
    }
    summary_path = evidence_dir / "germany50-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_dir": str(evidence_dir), "summary_file": str(summary_path)}, indent=2))


if __name__ == "__main__":
    main()
