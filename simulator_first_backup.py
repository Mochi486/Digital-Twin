import json
import random
from pathlib import Path

print("Simulation starting...")

# 读取场景文件（从挂载目录读）
scenario_path = Path("/app/data/scenario.json")
if not scenario_path.exists():
    raise FileNotFoundError("scenario.json not found in /app/data. Did you mount the volume correctly?")

with open(scenario_path, "r", encoding="utf-8") as f:
    scenario = json.load(f)

print("Loaded scenario:", scenario)

# 根据 scenario 生成一些“仿真指标”（先用简单规则模拟）
nodes = int(scenario.get("nodes", 10))
traffic = scenario.get("traffic", "medium")

base_latency = 20 + nodes  # 节点越多延迟越高（简单规则）
traffic_factor = {"low": 0.8, "medium": 1.0, "high": 1.3}.get(traffic, 1.0)

metrics = {
    "latency_ms": round(base_latency * traffic_factor + random.randint(0, 10), 2),
    "packet_loss_rate": round(random.uniform(0, 0.05) * traffic_factor, 5),
    "throughput_mbps": round(random.randint(50, 200) / traffic_factor, 2)
}

# 输出到挂载目录
output_path = Path("/app/data/metrics.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(metrics, f, indent=2)

print("Simulation finished.")
print("Saved metrics to:", output_path)
print("Metrics:", metrics)