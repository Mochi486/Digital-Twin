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

    with open(scenario_file) as f:
        scenario = json.load(f)

    with open(metrics_file) as f:
        metrics = json.load(f)

    record = {
        "run": run_dir.name,
        "nodes": scenario["nodes"],
        "traffic": scenario["traffic"],
        "latency": metrics["latency_ms"],
        "loss": metrics["packet_loss_rate"],
        "throughput": metrics["throughput_mbps"]
    }

    records.append(record)

df = pd.DataFrame(records)

if df.empty:
    print("No valid run data found.")
    exit()

# 排序
df = df.sort_values(by="nodes")

print(df)

# 画图
# --- Latency ---
plt.figure()
plt.plot(df["nodes"], df["latency"], marker="o")
for _, row in df.iterrows():
    label = f'{row["run"]} ({row["traffic"]})'
    plt.annotate(
        label,                       # 标注内容
        (row["nodes"], row["latency"]),   # 点的位置
        textcoords="offset points",
        xytext=(6, 6),                    # 文字偏移，避免盖住点
        ha="left",
        fontsize=9
    )
plt.xlabel("Nodes")
plt.ylabel("Latency (ms)")
plt.title("Latency vs Nodes")
plt.savefig(PROJECT_ROOT / "latency_plot.png")

# --- Throughput ---
plt.figure()
plt.plot(df["nodes"], df["throughput"], marker="o")
for _, row in df.iterrows():
    label = f'{row["run"]} ({row["traffic"]})'
    plt.annotate(
        row["run"],
        (row["nodes"], row["throughput"]),
        textcoords="offset points",
        xytext=(6, 6),
        ha="left",
        fontsize=9
    )
plt.xlabel("Nodes")
plt.ylabel("Throughput (Mbps)")
plt.title("Throughput vs Nodes")
plt.savefig(PROJECT_ROOT / "throughput_plot.png")

print("Plots saved.")