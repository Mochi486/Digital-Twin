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
SIMULATOR_SCRIPT = PROJECT_ROOT / "scripts" / "simulator_topology.py"
IMPORT_SCRIPT = PROJECT_ROOT / "scripts" / "import_germany50.py"
RAW_NATIVE_PATH = PROJECT_ROOT / "data" / "external" / "germany50" / "native" / "germany50.txt"
SCENARIO_PATH = PROJECT_ROOT / "data" / "scenario_germany50.json"
METADATA_PATH = PROJECT_ROOT / "data" / "external" / "germany50" / "source-metadata.json"
SOURCE_URL = "https://sndlib.put.poznan.pl/download/sndlib-networks-native/germany50.txt"
LICENSE_NAME = "ZIB Academic License"
LICENSE_URL = "https://sndlib.put.poznan.pl/LICENSE.txt"


def run_command(cmd, cwd=PROJECT_ROOT):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def import_source():
    result = subprocess.run(
        [
            sys.executable,
            str(IMPORT_SCRIPT),
            "--source-native",
            str(RAW_NATIVE_PATH),
            "--output-scenario",
            str(SCENARIO_PATH),
            "--metadata-output",
            str(METADATA_PATH),
            "--source-url",
            SOURCE_URL,
            "--license-name",
            LICENSE_NAME,
            "--license-url",
            LICENSE_URL,
            "--topology-name",
            "sndlib-germany50",
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


def run_dry_run(name: str, scenario_path: Path, evidence_dir: Path):
    run_dir = RUNS_ROOT / evidence_dir.name / name
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = run_dir / "dry-run.json"
    plot_path = run_dir / "topology.svg"
    simulator_log = evidence_dir / f"{name}-simulator.log"
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
    cmd.append("--dry-run")

    with simulator_log.open("w", encoding="utf-8") as log_file:
        sim_result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            text=True,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

    record = {
        "name": name,
        "success": sim_result.returncode == 0 and metrics_path.exists(),
        "simulator_exit_code": sim_result.returncode,
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

    dry_run_result = run_dry_run("germany50-dry-run", SCENARIO_PATH, evidence_dir)
    subset5_result = run_dry_run("germany50-subset-5-dry-run", subset5_path, evidence_dir)
    subset10_result = run_dry_run("germany50-subset-10-dry-run", subset10_path, evidence_dir)

    path_samples = choose_path_length_samples(scenario)
    selected_path_scenarios = {}
    for name, sample in path_samples.items():
        path_scenario = configure_pair_scenario(scenario, sample["pair"], sample["hop_count"])
        path_file = evidence_dir / f"scenario-germany50-{name}-path.json"
        write_scenario(path_file, path_scenario)
        selected_path_scenarios[name] = {
            **sample,
            "scenario_file": str(path_file),
            "route_count": len(load_topology_scenario(path_file)["routes"]),
        }
    resource_estimate = build_resource_estimate(scenario)

    summary = {
        "source": metadata,
        "resource_estimate": resource_estimate,
        "dry_run": dry_run_result,
        "subset_5_dry_run": subset5_result,
        "subset_10_dry_run": subset10_result,
        "path_samples": selected_path_scenarios,
        "full_traffic_not_run": True,
        "topology_plot": str(evidence_dir / "germany50-topology.svg"),
    }
    summary_path = evidence_dir / "germany50-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_dir": str(evidence_dir), "summary_file": str(summary_path)}, indent=2))


if __name__ == "__main__":
    main()
