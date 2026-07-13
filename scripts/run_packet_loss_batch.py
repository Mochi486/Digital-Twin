import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from routed_delay_utils import (
    get_routed_link,
    summarize_numeric,
    theoretical_round_trip_loss_percent,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCENARIO_PATH = PROJECT_ROOT / "data" / "scenario_routed.json"
RUNS_ROOT = PROJECT_ROOT / "runs"
EVIDENCE_ROOT = PROJECT_ROOT / ".local-evidence"
METRICS_PATH = PROJECT_ROOT / "runs" / "current" / "metrics.json"
PREPARE_SCRIPT = PROJECT_ROOT / "scripts" / "prepare_wsl_docker.py"
SIMULATOR_SCRIPT = PROJECT_ROOT / "scripts" / "simulator_routed.py"

LOSS_VALUES = [0, 1, 3, 5]
RUNS_PER_LOSS = 5
PING_PACKETS_PER_RUN = 100
PING_INTERVAL_S = 0.05


def ensure_root():
    result = subprocess.run(["id", "-u"], capture_output=True, text=True, check=True)
    if result.stdout.strip() != "0":
        raise RuntimeError("run_packet_loss_batch.py must run as root for prepare_wsl_docker.py.")


def make_svg_plot(points, output_path: Path, title: str, x_label: str, y_label: str, value_key: str):
    width = 720
    height = 420
    margin_left = 70
    margin_bottom = 50
    margin_top = 30
    margin_right = 30

    xs = [point["packet_loss_percent"] for point in points]
    ys = [point[value_key] for point in points]
    x_min, x_max = min(xs), max(xs)
    y_min = 0
    y_max = max(ys) if ys else 1
    if y_max == y_min:
        y_max += 1

    def x_pos(value):
        usable = width - margin_left - margin_right
        if x_max == x_min:
            return margin_left + usable / 2
        return margin_left + usable * ((value - x_min) / (x_max - x_min))

    def y_pos(value):
        usable = height - margin_top - margin_bottom
        return height - margin_bottom - usable * ((value - y_min) / (y_max - y_min))

    point_elements = []
    polyline_points = []
    for point in points:
        x = x_pos(point["packet_loss_percent"])
        y = y_pos(point[value_key])
        polyline_points.append(f"{x},{y}")
        point_elements.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="#1f77b4" />'
            f'<text x="{x + 6:.2f}" y="{y - 6:.2f}" font-size="12">{point[value_key]:.2f}</text>'
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
  <rect width="100%" height="100%" fill="white"/>
  <line x1="{margin_left}" y1="{height - margin_bottom}" x2="{width - margin_right}" y2="{height - margin_bottom}" stroke="black"/>
  <line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{height - margin_bottom}" stroke="black"/>
  <text x="{width / 2:.2f}" y="18" text-anchor="middle" font-size="18">{title}</text>
  <text x="{width / 2:.2f}" y="{height - 10}" text-anchor="middle" font-size="14">{x_label}</text>
  <text x="18" y="{height / 2:.2f}" transform="rotate(-90 18,{height / 2:.2f})" text-anchor="middle" font-size="14">{y_label}</text>
  <polyline fill="none" stroke="#1f77b4" stroke-width="2" points="{' '.join(polyline_points)}"/>
  {''.join(point_elements)}
</svg>
"""
    output_path.write_text(svg, encoding="utf-8")


def main():
    ensure_root()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    evidence_dir = EVIDENCE_ROOT / f"packet-loss-experiments-{stamp}"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    batch_runs_dir = RUNS_ROOT / f"packet_loss_batch_{stamp}"
    batch_runs_dir.mkdir(parents=True, exist_ok=True)

    original_scenario = SCENARIO_PATH.read_text(encoding="utf-8")
    results = []

    try:
        for packet_loss_percent in LOSS_VALUES:
            for run_index in range(1, RUNS_PER_LOSS + 1):
                run_name = f"loss_{packet_loss_percent:03d}_run_{run_index:02d}"
                run_dir = batch_runs_dir / run_name
                run_dir.mkdir(parents=True, exist_ok=True)

                scenario = json.loads(original_scenario)
                routed_link = get_routed_link(scenario)
                routed_link["delay_ms"] = 0
                routed_link["packet_loss_percent"] = packet_loss_percent
                scenario["traffic"]["ping_count"] = PING_PACKETS_PER_RUN
                scenario["traffic"]["ping_interval_s"] = PING_INTERVAL_S
                SCENARIO_PATH.write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")

                prepare_log = evidence_dir / f"{run_name}-prepare.log"
                simulator_log = evidence_dir / f"{run_name}-simulator.log"

                prepare_proc = subprocess.Popen(
                    [
                        sys.executable,
                        str(PREPARE_SCRIPT),
                        "--ignore-existing",
                        "--evidence",
                        str(prepare_log),
                    ],
                    cwd=PROJECT_ROOT,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.STDOUT,
                    text=True,
                )

                with simulator_log.open("w", encoding="utf-8") as log_file:
                    result = subprocess.run(
                        [sys.executable, str(SIMULATOR_SCRIPT)],
                        cwd=PROJECT_ROOT,
                        text=True,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                    )
                prepare_rc = prepare_proc.wait()

                run_record = {
                    "run_name": run_name,
                    "packet_loss_percent": packet_loss_percent,
                    "run_index": run_index,
                    "success": result.returncode == 0 and prepare_rc == 0 and METRICS_PATH.exists(),
                    "simulator_exit_code": result.returncode,
                    "prepare_exit_code": prepare_rc,
                    "theoretical_round_trip_loss_percent": theoretical_round_trip_loss_percent(packet_loss_percent),
                }

                (run_dir / "scenario.json").write_text(
                    json.dumps(scenario, indent=2) + "\n",
                    encoding="utf-8",
                )

                if METRICS_PATH.exists():
                    metrics_copy = run_dir / "metrics.json"
                    metrics_copy.write_text(METRICS_PATH.read_text(encoding="utf-8"), encoding="utf-8")

                if run_record["success"]:
                    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
                    run_record.update(
                        {
                            "throughput_mbps": metrics["throughput_mbps"],
                            "ping_packet_loss_percent": metrics["ping_packet_loss_percent"],
                            "ping_packets_transmitted": metrics["ping_packets_transmitted"],
                            "ping_packets_received": metrics["ping_packets_received"],
                            "ping_success": metrics["ping_success"],
                        }
                    )

                results.append(run_record)
    finally:
        SCENARIO_PATH.write_text(original_scenario, encoding="utf-8")

    summary_rows = []
    for packet_loss_percent in LOSS_VALUES:
        successful = [row for row in results if row["packet_loss_percent"] == packet_loss_percent and row["success"]]
        if not successful:
            summary_rows.append(
                {
                    "packet_loss_percent": packet_loss_percent,
                    "successful_runs": 0,
                    "failed_runs": RUNS_PER_LOSS,
                }
            )
            continue

        measured_loss_values = [row["ping_packet_loss_percent"] for row in successful]
        throughput_values = [row["throughput_mbps"] for row in successful]
        loss_stats = summarize_numeric(measured_loss_values)
        throughput_stats = summarize_numeric(throughput_values)

        summary_rows.append(
            {
                "packet_loss_percent": packet_loss_percent,
                "successful_runs": len(successful),
                "failed_runs": RUNS_PER_LOSS - len(successful),
                "theoretical_round_trip_loss_percent": theoretical_round_trip_loss_percent(packet_loss_percent),
                "measured_loss_mean_percent": loss_stats["mean"],
                "measured_loss_sample_std_percent": loss_stats["sample_std"],
                "measured_loss_min_percent": loss_stats["min"],
                "measured_loss_max_percent": loss_stats["max"],
                "throughput_mean_mbps": throughput_stats["mean"],
                "throughput_sample_std_mbps": throughput_stats["sample_std"],
                "throughput_min_mbps": throughput_stats["min"],
                "throughput_max_mbps": throughput_stats["max"],
            }
        )

    summary = {
        "loss_values_tested": LOSS_VALUES,
        "runs_per_loss": RUNS_PER_LOSS,
        "ping_packets_per_run": PING_PACKETS_PER_RUN,
        "total_runs": len(results),
        "successful_runs": sum(1 for row in results if row["success"]),
        "failed_runs": sum(1 for row in results if not row["success"]),
        "results": results,
        "summary_rows": summary_rows,
    }

    summary_json = evidence_dir / "packet-loss-summary.json"
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    summary_csv = evidence_dir / "packet-loss-summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "packet_loss_percent",
                "successful_runs",
                "failed_runs",
                "theoretical_round_trip_loss_percent",
                "measured_loss_mean_percent",
                "measured_loss_sample_std_percent",
                "measured_loss_min_percent",
                "measured_loss_max_percent",
                "throughput_mean_mbps",
                "throughput_sample_std_mbps",
                "throughput_min_mbps",
                "throughput_max_mbps",
            ],
        )
        writer.writeheader()
        for row in summary_rows:
            writer.writerow(row)

    plottable_rows = [row for row in summary_rows if row.get("successful_runs")]
    loss_plot_file = evidence_dir / "loss-vs-measured-ping-loss.svg"
    make_svg_plot(
        plottable_rows,
        loss_plot_file,
        "Configured One-Way Loss vs Measured Ping Loss",
        "Configured one-way packet loss (%)",
        "Measured ping packet loss (%)",
        "measured_loss_mean_percent",
    )
    throughput_plot_file = evidence_dir / "loss-vs-throughput.svg"
    make_svg_plot(
        plottable_rows,
        throughput_plot_file,
        "Configured One-Way Loss vs Throughput",
        "Configured one-way packet loss (%)",
        "Measured throughput (Mbps)",
        "throughput_mean_mbps",
    )

    print(
        json.dumps(
            {
                "evidence_dir": str(evidence_dir),
                "summary_json": str(summary_json),
                "summary_csv": str(summary_csv),
                "loss_plot_file": str(loss_plot_file),
                "throughput_plot_file": str(throughput_plot_file),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
