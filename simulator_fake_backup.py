import json
import random

print("Simulation starting...")

# 假装读取一个场景
scenario = {
    "nodes": 10,
    "traffic": "medium"
}

# 假装生成网络指标
metrics = {
    "latency": random.randint(10, 100),
    "packet_loss": random.uniform(0, 0.1),
    "throughput": random.randint(50, 200)
}

print("Simulation finished.")
print("Metrics:", metrics)

# 保存结果
with open("metrics.json", "w") as f:
    json.dump(metrics, f)