# Quick Start

This document lists the current verified commands for the `Digital Twin` repository.

## 1. Build The Experiment Image

WSL:

```bash
cd /mnt/d/home/fanys23/project_70
docker build -f Dockerfile.iperf -t my-iperf-tc .
```

## 2. Install Python Dependency

Windows PowerShell:

```powershell
Set-Location D:\home\fanys23\project_70
python -m venv .venv-win311
.\.venv-win311\Scripts\python.exe -m pip install -r requirements.txt
```

WSL:

```bash
cd /mnt/d/home/fanys23/project_70
python3 -m venv .venv-wsl311
. .venv-wsl311/bin/activate
python -m pip install -r requirements.txt
```

## 3. Run Unit Tests

Windows PowerShell:

```powershell
Set-Location D:\home\fanys23\project_70
.\.venv-win311\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

WSL:

```bash
cd /mnt/d/home/fanys23/project_70
. .venv-wsl311/bin/activate
python -m unittest discover -s tests -p "test_*.py"
```

## 4. Single-Router Baseline

WSL:

```bash
cd /mnt/d/home/fanys23/project_70
. .venv-wsl311/bin/activate
python scripts/run_demo.py baseline
```

Raw command:

```bash
python scripts/simulator_routed.py --scenario data/scenario_routed.json --output runs/current/metrics.json --prepare-host-routing-log .local-evidence/readme-baseline-prepare.log
```

## 5. Two-Router Dry-Run

WSL:

```bash
cd /mnt/d/home/fanys23/project_70
. .venv-wsl311/bin/activate
python scripts/run_demo.py two-router
```

Raw command:

```bash
python scripts/simulator_topology.py --scenario data/scenario_two_router_topology.json --output runs/current/topology_metrics.json --plot runs/current/topology_two_router.svg --dry-run
```

## 6. Delay Smoke

WSL:

```bash
cd /mnt/d/home/fanys23/project_70
. .venv-wsl311/bin/activate
python scripts/run_demo.py delay-smoke
```

## 7. Packet-Loss Smoke

WSL:

```bash
cd /mnt/d/home/fanys23/project_70
. .venv-wsl311/bin/activate
python scripts/run_demo.py loss-smoke
```

## 8. AI Mock Dry-Run

WSL:

```bash
cd /mnt/d/home/fanys23/project_70
. .venv-wsl311/bin/activate
python scripts/run_demo.py ai-mock
```

Raw command:

```bash
python scripts/generate_scenario_ai.py --provider mock --prompt "Create a six-node redundant routed topology with two candidate paths and 20 Mbps bandwidth" --output-scenario runs/current/ai_scenario.json --report runs/current/ai_scenario_report.json --dry-run-output runs/current/ai_scenario_dry_run.json --plot runs/current/ai_scenario.svg
```

## 9. Compatible-Provider Live Validation

Windows PowerShell:

```powershell
Set-Location D:\home\fanys23\project_70
$env:COMPAT_API_KEY="<set-in-session>"
$env:COMPAT_BASE_URL="https://ws-1s2sexxqtqluyr11.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
$env:COMPAT_MODEL="qwen3.7-plus"
.\.venv-win311\Scripts\python.exe scripts\run_demo.py ai-live
```

Raw command:

```powershell
.\.venv-win311\Scripts\python.exe scripts\run_openai_live_validation.py --provider openai_compatible --skip-model-list --model qwen3.7-plus --endpoint-order chat_json_schema chat_json_object chat_plain_json
```

## 10. Batch Runners

WSL:

```bash
cd /mnt/d/home/fanys23/project_70
. .venv-wsl311/bin/activate
python scripts/run_two_router_batch.py
python scripts/run_delay_batch.py
python scripts/run_packet_loss_batch.py
```
