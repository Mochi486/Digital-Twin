import json
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RUNS_DIR = PROJECT_ROOT / "runs"
CURRENT_DIR = RUNS_DIR / "current"

SCENARIO_PATH = DATA_DIR / "scenario.json"
CURRENT_METRICS_PATH = CURRENT_DIR / "metrics.json"

# 现在测试不同带宽限制
scenarios = [
    {
        "nodes": [
            {"id": "client1", "type": "client"},
            {"id": "server1", "type": "server"}
        ],
        "links": [
            {"source": "server1", "target": "client1", "bandwidth_mbps": 20, "delay_ms": 0}
        ],
        "traffic": {
            "protocol": "tcp",
            "duration_s": 5,
            "reverse": True
        }
    },
    {
        "nodes": [
            {"id": "client1", "type": "client"},
            {"id": "server1", "type": "server"}
        ],
        "links": [
            {"source": "server1", "target": "client1", "bandwidth_mbps": 50, "delay_ms": 0}
        ],
        "traffic": {
            "protocol": "tcp",
            "duration_s": 5,
            "reverse": True
        }
    },
    {
        "nodes": [
            {"id": "client1", "type": "client"},
            {"id": "server1", "type": "server"}
        ],
        "links": [
            {"source": "server1", "target": "client1", "bandwidth_mbps": 100, "delay_ms": 0}
        ],
        "traffic": {
            "protocol": "tcp",
            "duration_s": 5,
            "reverse": True
        }
    }
]
for i, scenario in enumerate(scenarios, start=1):
    run_name = f"run_{i:03d}"
    run_dir = RUNS_DIR / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== Running {run_name} ===")
    print("Scenario:", scenario)

    # 1. 写入当前 scenario.json
    with open(SCENARIO_PATH, "w", encoding="utf-8") as f:
        json.dump(scenario, f, indent=2)

    # 2. 调用真实 simulator
    result = subprocess.run(
        ["python", "scripts/simulator_real.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True
    )

    print(result.stdout)
    if result.returncode != 0:
        print("ERROR:", result.stderr)
        continue

    # 3. 保存本轮 scenario 和 metrics
    shutil.copy(SCENARIO_PATH, run_dir / "scenario.json")
    shutil.copy(CURRENT_METRICS_PATH, run_dir / "metrics.json")

print("\nAll batch runs completed.")