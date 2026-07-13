import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from routed_delay_utils import get_routed_link, summarize_numeric

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCENARIO_PATH = PROJECT_ROOT / "data" / "scenario_routed.json"
RUNS_ROOT = PROJECT_ROOT / "runs"
EVIDENCE_ROOT = PROJECT_ROOT / ".local-evidence"
METRICS_PATH = PROJECT_ROOT / "runs" / "current" / "metrics.json"
PREPARE_SCRIPT = PROJECT_ROOT / "scripts" / "prepare_wsl_docker.py"
SIMULATOR_SCRIPT = PROJECT_ROOT / "scripts" / "simulator_routed.py"

DELAY_VALUES = [0, 10, 30, 50]
RUNS_PER_DELAY = 5


def run(cmd, check=True, stdout_path=None):
    with stdout_path.open("w", encoding="utf-8") if stdout_path else subprocess.DEVNULL as sink:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            text=True,
            stdout=sink if stdout_path else subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}")
    return result


def ensure_root():
    result = subprocess.run(["id", "-u"], capture_output=True, text=True, check=True)
    if result.stdout.strip() != "0":
        raise RuntimeError("run_delay_batch.py must run as root for prepare_wsl_docker.py.")


def make_svg_plot(points, output_path: Path):
    width = 720
    height = 420
    margin_left = 70
    margin_bottom = 50
    margin_top = 30
    margin_right = 30

    delays = [point["delay_ms"] for point in points]
    rtts = [point["rtt_mean_ms"] for point in points]
    x_min, x_max = min(delays), max(delays)
    y_min = 0
    y_max = max(rtts) if rtts else 1
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
        x = x_pos(point["delay_ms"])
        y = y_pos(point["rtt_mean_ms"])
        polyline_points.append(f"{x},{y}")
        point_elements.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="#1f77b4" />'
            f'<text x="{x + 6:.2f}" y="{y - 6:.2f}" font-size="12">{point["rtt_mean_ms"]:.2f}</text>'
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
  <rect width="100%" height="100%" fill="white"/>
  <line x1="{margin_left}" y1="{height - margin_bottom}" x2="{width - margin_right}" y2="{height - margin_bottom}" stroke="black"/>
  <line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{height - margin_bottom}" stroke="black"/>
  <text x="{width / 2:.2f}" y="18" text-anchor="middle" font-size="18">Configured Delay vs Measured Average RTT</text>
  <text x="{width / 2:.2f}" y="{height - 10}" text-anchor="middle" font-size="14">Configured one-way delay (ms)</text>
  <text x="18" y="{height / 2:.2f}" transform="rotate(-90 18,{height / 2:.2f})" text-anchor="middle" font-size="14">Measured average RTT (ms)</text>
  <polyline fill="none" stroke="#1f77b4" stroke-width="2" points="{' '.join(polyline_points)}"/>
  {''.join(point_elements)}
</svg>
"""
    output_path.write_text(svg, encoding="utf-8")


def main():
    ensure_root()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    evidence_dir = EVIDENCE_ROOT / f"delay-experiments-{stamp}"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    batch_runs_dir = RUNS_ROOT / f"delay_batch_{stamp}"
    batch_runs_dir.mkdir(parents=True, exist_ok=True)

    original_scenario = SCENARIO_PATH.read_text(encoding="utf-8")
    base_scenario = json.loads(original_scenario)

    results = []

    try:
        for delay_ms in DELAY_VALUES:
            for run_index in range(1, RUNS_PER_DELAY + 1):
                run_name = f"delay_{delay_ms:03d}_run_{run_index:02d}"
                run_dir = batch_runs_dir / run_name
                run_dir.mkdir(parents=True, exist_ok=True)

                scenario = json.loads(original_scenario)
                get_routed_link(scenario)["delay_ms"] = delay_ms
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

                result = subprocess.run(
                    [sys.executable, str(SIMULATOR_SCRIPT)],
                    cwd=PROJECT_ROOT,
                    text=True,
                    stdout=simulator_log.open("w", encoding="utf-8"),
                    stderr=subprocess.STDOUT,
                )
                prepare_rc = prepare_proc.wait()

                run_record = {
                    "run_name": run_name,
                    "delay_ms": delay_ms,
                    "run_index": run_index,
                    "success": result.returncode == 0 and prepare_rc == 0 and METRICS_PATH.exists(),
                    "simulator_exit_code": result.returncode,
                    "prepare_exit_code": prepare_rc,
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
                            "ping_rtt_avg_ms": metrics["ping_rtt_avg_ms"],
                            "ping_success": metrics["ping_success"],
                        }
                    )

                results.append(run_record)

    finally:
        SCENARIO_PATH.write_text(original_scenario, encoding="utf-8")

    summary_rows = []
    for delay_ms in DELAY_VALUES:
        successful = [row for row in results if row["delay_ms"] == delay_ms and row["success"]]
        if not successful:
            summary_rows.append(
                {
                    "delay_ms": delay_ms,
                    "successful_runs": 0,
                    "failed_runs": RUNS_PER_DELAY,
                }
            )
            continue

        rtt_values = [row["ping_rtt_avg_ms"] for row in successful]
        throughput_values = [row["throughput_mbps"] for row in successful]
        rtt_stats = summarize_numeric(rtt_values)
        throughput_stats = summarize_numeric(throughput_values)

        summary_rows.append(
            {
                "delay_ms": delay_ms,
                "successful_runs": len(successful),
                "failed_runs": RUNS_PER_DELAY - len(successful),
                "rtt_mean_ms": rtt_stats["mean"],
                "rtt_sample_std_ms": rtt_stats["sample_std"],
                "rtt_min_ms": rtt_stats["min"],
                "rtt_max_ms": rtt_stats["max"],
                "throughput_mean_mbps": throughput_stats["mean"],
                "throughput_sample_std_mbps": throughput_stats["sample_std"],
                "throughput_min_mbps": throughput_stats["min"],
                "throughput_max_mbps": throughput_stats["max"],
            }
        )

    summary = {
        "delay_values_tested": DELAY_VALUES,
        "runs_per_delay": RUNS_PER_DELAY,
        "total_runs": len(results),
        "successful_runs": sum(1 for row in results if row["success"]),
        "failed_runs": sum(1 for row in results if not row["success"]),
        "results": results,
        "summary_rows": summary_rows,
    }

    summary_json = evidence_dir / "delay-summary.json"
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    summary_csv = evidence_dir / "delay-summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "delay_ms",
                "successful_runs",
                "failed_runs",
                "rtt_mean_ms",
                "rtt_sample_std_ms",
                "rtt_min_ms",
                "rtt_max_ms",
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
    plot_file = evidence_dir / "delay-vs-rtt.svg"
    make_svg_plot(plottable_rows, plot_file)

    print(json.dumps(
        {
            "evidence_dir": str(evidence_dir),
            "summary_json": str(summary_json),
            "summary_csv": str(summary_csv),
            "plot_file": str(plot_file),
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()
