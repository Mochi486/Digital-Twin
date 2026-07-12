import json
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RUNS_DIR = PROJECT_ROOT / "runs"
CURRENT_DIR = RUNS_DIR / "current"

N_RUNS = 3  # 想跑几轮改这里

for i in range(1, N_RUNS + 1):
    run_name = f"run_{i:03d}"
    run_dir = RUNS_DIR / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== Running {run_name} ===")

    # 1) 运行 AI 生成脚本（它会写 data/scenario.json）
    gen = subprocess.run(
        ["python", "scripts/generate_scenario_ai.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True
    )
    print(gen.stdout)
    if gen.returncode != 0:
        print("AI generator ERROR:", gen.stderr)
        continue

    # 2) 读取刚生成的 scenario.json（可选，但强烈建议用于打印/归档）
    scenario_path = DATA_DIR / "scenario.json"
    with open(scenario_path, "r", encoding="utf-8") as f:
        scenario = json.load(f)
    print("Scenario:", scenario)

    # 3) 调用 docker compose 运行仿真
    result = subprocess.run(
        ["docker", "compose", "up", "--build"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True
    )

    print(result.stdout)
    if result.returncode != 0:
        print("ERROR:", result.stderr)
        continue

    # 4) 保存本次 scenario 和 metrics
    shutil.copy(scenario_path, run_dir / "scenario.json")
    shutil.copy(CURRENT_DIR / "metrics.json", run_dir / "metrics.json")

    # 5) 清理 compose
    subprocess.run(["docker", "compose", "down"], cwd=PROJECT_ROOT)

print("\nAll batch runs completed.")