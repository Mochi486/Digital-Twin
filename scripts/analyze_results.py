import json
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = PROJECT_ROOT / "runs"

records = []

for run_dir in sorted(RUNS_DIR.glob("run_*")):
    scenario_file = run_dir / "scenario.json"
    metrics_file = run_dir / "metrics.json"

    if not scenario_file.exists() or not metrics_file.exists():
        continue

    with open(scenario_file, "r", encoding="utf-8") as f:
        scenario = json.load(f)

    with open(metrics_file, "r", encoding="utf-8") as f:
        metrics = json.load(f)

    links = scenario.get("links", [])
    traffic = scenario.get("traffic", {})

    link = links[0] if links else {}

    record = {
        "run": run_dir.name,
        "bandwidth_mbps": link.get("bandwidth_mbps"),
        "delay_ms": link.get("delay_ms"),
        "duration_s": traffic.get("duration_s"),
        "throughput_mbps": metrics.get("throughput_mbps")
    }

    records.append(record)

df = pd.DataFrame(records)

if df.empty:
    print("No valid run data found.")
    exit()

df = df.sort_values(by="bandwidth_mbps")

print(df)

plt.figure()
plt.plot(df["bandwidth_mbps"], df["throughput_mbps"], marker="o")

for _, row in df.iterrows():
    plt.annotate(
        row["run"],
        (row["bandwidth_mbps"], row["throughput_mbps"]),
        textcoords="offset points",
        xytext=(6, 6),
        ha="left",
        fontsize=9
    )

plt.xlabel("Configured Bandwidth Limit (Mbps)")
plt.ylabel("Measured Throughput (Mbps)")
plt.title("Throughput vs Bandwidth Limit")
plt.savefig(PROJECT_ROOT / "throughput_plot.png")

print("Plot saved.")