import argparse
import csv
import json
import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from germany50_selected_paths import PATHS, write_selected_path_scenarios
from topology_utils import load_topology_scenario


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_SCENARIO = PROJECT_ROOT / "data" / "scenario_germany50.json"
SCENARIO_DIR = PROJECT_ROOT / "data" / "germany50-selected-paths"
RUNS_ROOT = PROJECT_ROOT / "runs"
EVIDENCE_ROOT = PROJECT_ROOT / ".local-evidence"
SIMULATOR = PROJECT_ROOT / "scripts" / "simulator_topology.py"
PREPARE = PROJECT_ROOT / "scripts" / "prepare_wsl_docker.py"


def run_process(command: list[str], output_path: Path) -> int:
    with output_path.open("w", encoding="utf-8") as output:
        return subprocess.run(command, cwd=PROJECT_ROOT, stdout=output, stderr=subprocess.STDOUT, text=True).returncode


def run_one(path_name: str, scenario_path: Path, run_index: int, run_root: Path, evidence_root: Path) -> dict:
    run_name = f"{path_name}-run-{run_index:02d}"
    run_dir = run_root / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    dry_run_path = run_dir / "dry-run.json"
    metrics_path = run_dir / "metrics.json"
    plot_path = run_dir / "topology.svg"
    dry_rc = run_process(
        [sys.executable, str(SIMULATOR), "--scenario", str(scenario_path), "--output", str(dry_run_path), "--plot", str(plot_path), "--dry-run"],
        evidence_root / f"{run_name}-dry-run.log",
    )
    real_rc = run_process(
        [sys.executable, str(SIMULATOR), "--scenario", str(scenario_path), "--output", str(metrics_path), "--plot", str(plot_path), "--prepare-host-routing-log", str(evidence_root / f"{run_name}-prepare.log")],
        evidence_root / f"{run_name}-real.log",
    )
    prepare_rc = 0
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    route_verified = bool(metrics.get("route_verification")) and all(item["matched"] for item in metrics.get("route_verification", []))
    qdisc_verified = bool(metrics.get("delay_loss_applications")) and all(
        "netem" in item.get("qdisc", "") for item in metrics.get("delay_loss_applications", [])
    )
    return {
        "path_class": path_name,
        "run_index": run_index,
        "success": dry_rc == 0 and real_rc == 0 and prepare_rc == 0 and bool(metrics),
        "dry_run_exit_code": dry_rc,
        "simulator_exit_code": real_rc,
        "prepare_exit_code": prepare_rc,
        "metrics_file": str(metrics_path),
        "dry_run_file": str(dry_run_path),
        "backbone_hop_count": metrics.get("resource_estimate", {}).get("node_count", 2) - 4,
        "rtt_avg_ms": metrics.get("ping_rtt_avg_ms"),
        "throughput_mbps": metrics.get("throughput_mbps"),
        "route_verified": route_verified,
        "qdisc_verified": qdisc_verified,
        "cleanup_time_s": metrics.get("cleanup_time_s"),
    }


def stats(values: list[float]) -> dict:
    return {"mean": statistics.fmean(values), "std": statistics.pstdev(values), "min": min(values), "max": max(values)}


def write_svg_chart(path: Path, title: str, rows: list[dict], metric: str, units: str) -> None:
    width, height, margin = 720, 420, 70
    maximum = max(row[metric]["mean"] for row in rows) * 1.15
    points = []
    for index, row in enumerate(rows):
        x = margin + index * ((width - 2 * margin) / max(1, len(rows) - 1))
        y = height - margin - (row[metric]["mean"] / maximum) * (height - 2 * margin)
        points.append((x, y, row))
    labels = "".join(f'<text x="{x:.1f}" y="{height - 38}" text-anchor="middle" font-size="12">{row["path_class"]} ({row["backbone_hop_count"]})</text>' for x, _, row in points)
    circles = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#2563eb"/>' for x, y, _ in points)
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in points)
    path.write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
<rect width="100%" height="100%" fill="white"/><text x="{width / 2}" y="30" text-anchor="middle" font-size="18">{title}</text>
<line x1="{margin}" y1="{height - margin}" x2="{width - margin}" y2="{height - margin}" stroke="#111"/><line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height - margin}" stroke="#111"/>
<text x="14" y="{margin}" font-size="12">{maximum:.2f} {units}</text><text x="14" y="{height - margin}" font-size="12">0</text>
<polyline points="{polyline}" fill="none" stroke="#2563eb" stroke-width="2"/>{circles}{labels}
<text x="{width / 2}" y="{height - 12}" text-anchor="middle" font-size="12">path class (backbone hops)</text></svg>\n''', encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--path", choices=sorted(PATHS))
    parser.add_argument("--start-index", type=int, default=1)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--summarize-only", action="store_true")
    args = parser.parse_args()
    if args.runs < 3 and not args.summarize_only and not args.allow_partial:
        raise ValueError("At least three runs per selected path are required.")
    run_root = args.run_root
    evidence_root = args.evidence_root
    if args.summarize_only:
        if run_root is None:
            raise ValueError("--run-root is required with --summarize-only.")
        records = []
        for metrics_path in sorted(run_root.glob("*-run-*/metrics.json")):
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            path_name = metrics["topology"].removeprefix("sndlib-germany50-selected-")
            run_name = metrics_path.parent.name
            route_verified = bool(metrics.get("route_verification")) and all(item["matched"] for item in metrics["route_verification"])
            qdisc_verified = bool(metrics.get("delay_loss_applications")) and all("netem" in item.get("qdisc", "") for item in metrics["delay_loss_applications"])
            records.append({"path_class": path_name, "run_index": int(run_name.rsplit("-", 1)[1]), "success": True, "metrics_file": str(metrics_path), "backbone_hop_count": len(PATHS[path_name]) - 1, "rtt_avg_ms": metrics["ping_rtt_avg_ms"], "throughput_mbps": metrics["throughput_mbps"], "route_verified": route_verified, "qdisc_verified": qdisc_verified, "cleanup_time_s": metrics.get("cleanup_time_s")})
    else:
        base = load_topology_scenario(BASE_SCENARIO)
        scenario_paths = write_selected_path_scenarios(base, SCENARIO_DIR)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        run_root = run_root or RUNS_ROOT / f"germany50-selected-paths-{stamp}"
        evidence_root = evidence_root or EVIDENCE_ROOT / f"germany50-selected-paths-{stamp}"
        run_root.mkdir(parents=True, exist_ok=True)
        evidence_root.mkdir(parents=True, exist_ok=True)
        names = [args.path] if args.path else list(PATHS)
        records = [run_one(name, scenario_paths[name], index, run_root, evidence_root) for name in names for index in range(args.start_index, args.start_index + args.runs)]
    if not all(record["success"] for record in records):
        raise RuntimeError(f"One or more selected-path experiments failed; evidence: {evidence_root}")
    summaries = []
    for name in sorted({record["path_class"] for record in records}):
        path_nodes = PATHS[name]
        group = [record for record in records if record["path_class"] == name]
        summaries.append({"path_class": name, "backbone_path": path_nodes, "backbone_hop_count": len(path_nodes) - 1, "runs": len(group), "rtt_ms": stats([record["rtt_avg_ms"] for record in group]), "throughput_mbps": stats([record["throughput_mbps"] for record in group]), "route_verification": all(record["route_verified"] for record in group), "qdisc_verification": all(record["qdisc_verified"] for record in group), "cleanup": all(record["cleanup_time_s"] is not None for record in group)})
    summary = {"experiment_scope": "Germany50 path-extracted experiment; not a full 50-node run", "run_root": str(run_root), "records": records, "summaries": summaries}
    summary_path = run_root / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    csv_path = run_root / "summary.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path_class", "backbone_hop_count", "runs", "rtt_mean_ms", "rtt_std_ms", "rtt_min_ms", "rtt_max_ms", "throughput_mean_mbps", "throughput_std_mbps", "throughput_min_mbps", "throughput_max_mbps"])
        writer.writeheader()
        for row in summaries:
            writer.writerow({"path_class": row["path_class"], "backbone_hop_count": row["backbone_hop_count"], "runs": row["runs"], "rtt_mean_ms": row["rtt_ms"]["mean"], "rtt_std_ms": row["rtt_ms"]["std"], "rtt_min_ms": row["rtt_ms"]["min"], "rtt_max_ms": row["rtt_ms"]["max"], "throughput_mean_mbps": row["throughput_mbps"]["mean"], "throughput_std_mbps": row["throughput_mbps"]["std"], "throughput_min_mbps": row["throughput_mbps"]["min"], "throughput_max_mbps": row["throughput_mbps"]["max"]})
    write_svg_chart(run_root / "hop-count-vs-rtt.svg", "Germany50 extracted paths: hop count vs RTT", summaries, "rtt_ms", "ms")
    write_svg_chart(run_root / "hop-count-vs-throughput.svg", "Germany50 extracted paths: hop count vs throughput", summaries, "throughput_mbps", "Mbps")
    print(json.dumps({"run_root": str(run_root), "summary": str(summary_path), "csv": str(csv_path)}, indent=2))


if __name__ == "__main__":
    main()
