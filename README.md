# Digital Twin

Docker-based network digital twin with configurable bandwidth, latency, packet loss, multi-router topologies, automated metrics, and AI-generated network scenarios.

## Project Overview

This repository implements a bounded MSc project artifact for repeatable network emulation on Docker and WSL. It covers direct and routed topologies, deterministic JSON-driven multi-hop scenarios, automated metrics capture, and guarded AI-assisted scenario generation.

The validated scope is intentionally bounded:

- no Germany50 full experiment execution
- no DFN full-topology execution
- no topologies above 10 nodes
- only a bounded six-node, two-static-path RL control demonstration

## Architecture

The platform is split into five layers:

1. Container runtime:
   Docker networks and Linux traffic control on WSL Docker Engine.
2. Scenario description:
   JSON scenarios for direct, routed, and generic multi-hop topologies.
3. Topology execution:
   `simulator_real.py`, `simulator_routed.py`, and `simulator_topology.py`.
4. Experiment orchestration:
   batch runners, dry-run helpers, and bounded live validation scripts.
5. AI generation and validation:
   `generate_scenario_ai.py`, `openai_live_utils.py`, schema gates, semantic gates, forbidden-content rejection, deterministic subnet/IP allocation, and static-route generation.

## Implemented Capabilities

- direct client-server bandwidth experiments
- single-router routed experiments
- generic multi-router topology simulation
- per-link bandwidth, delay, and packet-loss control
- deterministic subnet allocation for compact AI scenarios
- deterministic static-route generation
- route verification and qdisc capture
- dry-run topology validation
- delay batch runner
- packet-loss batch runner
- two-router acceptance runner
- AI scenario generation with `mock`, `openai`, and `openai_compatible` providers
- OpenAI-compatible live validation with endpoint fallback
- WSL Docker compatibility helper for host bridge routing rules

## Repository Structure

- `Dockerfile.iperf`: experiment container image
- `dockerfile`: older legacy prototype file kept for reference
- `data/`: base scenarios and imported topology sources
- `scripts/`: simulators, batch runners, AI generator, live validator, and helpers
- `tests/`: unit tests for validation, topology utilities, and secret handling
- `docs/progress/`: dated progress and validation reports
- `runs/`: representative tracked metrics, scenarios, and SVG outputs
- `.local-evidence/`: local-only evidence and large logs, excluded from Git

## WSL Docker Prerequisites

Validated execution was performed on WSL with Docker Engine available inside WSL.

Required tools:

- WSL Ubuntu or equivalent Linux environment
- Docker CLI and Docker Engine access from WSL
- Python 3.11
- `sudo` access for full phase orchestration if you use `run_ai_scenario_phase.py`

Validated environment checks:

```bash
docker version
docker info
docker run --rm hello-world
```

## Installation

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
docker build -f Dockerfile.iperf -t my-iperf-tc .
```

## Exact Quick-Start Commands

These commands are the current verified entry points:

WSL:

```bash
cd /mnt/d/home/fanys23/project_70
. .venv-wsl311/bin/activate
python scripts/run_demo.py baseline
python scripts/run_demo.py two-router
python scripts/run_demo.py delay-smoke
python scripts/run_demo.py loss-smoke
python scripts/run_demo.py ai-mock
```

Windows PowerShell for compatible live validation:

```powershell
Set-Location D:\home\fanys23\project_70
$env:COMPAT_API_KEY="<set-in-session>"
$env:COMPAT_BASE_URL="https://ws-1s2sexxqtqluyr11.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
$env:COMPAT_MODEL="qwen3.7-plus"
.\.venv-win311\Scripts\python.exe scripts\run_demo.py ai-live
```

## Single-Router Example

Direct routed baseline:

```bash
cd /mnt/d/home/fanys23/project_70
. .venv-wsl311/bin/activate
python scripts/simulator_routed.py --scenario data/scenario_routed.json --output runs/current/metrics.json --prepare-host-routing-log .local-evidence/readme-baseline-prepare.log
```

Demo wrapper:

```bash
python scripts/run_demo.py baseline
```

## Two-Router Example

Validated dry-run:

```bash
cd /mnt/d/home/fanys23/project_70
. .venv-wsl311/bin/activate
python scripts/simulator_topology.py --scenario data/scenario_two_router_topology.json --output runs/current/topology_metrics.json --plot runs/current/topology_two_router.svg --dry-run
```

Demo wrapper:

```bash
python scripts/run_demo.py two-router
```

## Delay Experiment

Full batch runner:

```bash
cd /mnt/d/home/fanys23/project_70
. .venv-wsl311/bin/activate
python scripts/run_delay_batch.py
```

Bounded smoke:

```bash
python scripts/run_demo.py delay-smoke
```

## Packet-Loss Experiment

Full batch runner:

```bash
cd /mnt/d/home/fanys23/project_70
. .venv-wsl311/bin/activate
python scripts/run_packet_loss_batch.py
```

Bounded smoke:

```bash
python scripts/run_demo.py loss-smoke
```

## JSON Topology Run

Generic topology dry-run:

```bash
cd /mnt/d/home/fanys23/project_70
. .venv-wsl311/bin/activate
python scripts/simulator_topology.py --scenario data/scenario_two_router_topology.json --output runs/current/topology_metrics.json --plot runs/current/topology_two_router.svg --dry-run
```

Generic topology real run:

```bash
python scripts/simulator_topology.py --scenario data/scenario_two_router_topology.json --output runs/current/topology_metrics.json --plot runs/current/topology_two_router.svg --prepare-host-routing-log .local-evidence/readme-two-router-prepare.log
```

## AI Scenario Generation

Mock provider generation with dry-run:

```bash
cd /mnt/d/home/fanys23/project_70
. .venv-wsl311/bin/activate
python scripts/generate_scenario_ai.py --provider mock --prompt "Create a six-node redundant routed topology with two candidate paths and 20 Mbps bandwidth" --output-scenario runs/current/ai_scenario.json --report runs/current/ai_scenario_report.json --dry-run-output runs/current/ai_scenario_dry_run.json --plot runs/current/ai_scenario.svg
```

Demo wrapper:

```bash
python scripts/run_demo.py ai-mock
```

## OpenAI-Compatible Provider Configuration

The repository supports:

- `mock`
- `openai`
- `openai_compatible`

Compatible-provider environment variables:

- `COMPAT_API_KEY`
- `COMPAT_BASE_URL`
- `COMPAT_MODEL_CANDIDATES`

Validated bounded compatible-provider live run on `2026-07-14`:

- provider type: `openai_compatible`
- provider host: `ws-1s2sexxqtqluyr11.cn-beijing.maas.aliyuncs.com`
- model: `qwen3.7-plus`
- endpoint: `chat.completions`
- structured-output mode: `response_format=json_schema`

Bounded live command:

```powershell
Set-Location D:\home\fanys23\project_70
$env:COMPAT_API_KEY="<set-in-session>"
$env:COMPAT_BASE_URL="https://ws-1s2sexxqtqluyr11.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
$env:COMPAT_MODEL="qwen3.7-plus"
.\.venv-win311\Scripts\python.exe scripts\run_openai_live_validation.py --provider openai_compatible --skip-model-list --model qwen3.7-plus --endpoint-order chat_json_schema chat_json_object chat_plain_json
```

The repository never prints or stores API key values. Only sanitized provider host, selected model, request id, token usage, latency, and redacted non-sensitive payloads are persisted.

## Metrics And Output Locations

Tracked representative outputs:

- `runs/run_001/`
- `runs/run_002/`
- `runs/run_003/`
- `runs/ai-scenario-phase-20260714-093638/`
- `runs/openai-live-regressions-20260714-110941/`

Tracked reports:

- `docs/progress/ai-scenario-phase-summary-2026-07-13.md`
- `docs/progress/delay-phase-summary-2026-07-13.md`
- `docs/progress/packet-loss-phase-summary-2026-07-13.md`
- `docs/progress/two-router-phase-summary-2026-07-13.md`
- `docs/progress/openai-live-validation-summary-2026-07-14.md`
- `docs/progress/openai-compatible-live-validation-summary-2026-07-14.md`

Local-only evidence:

- `.local-evidence/`
- ad hoc live-validation run directories under `runs/openai-compatible-live-validation-*`
- ad hoc regression reruns under `runs/openai-live-regressions-*`

## Minimal RL And Dashboard

The bounded RL extension uses one client, one server, and four routers (six nodes
total), with two precomputed static paths. It does not use a dynamic routing
protocol and never runs a Germany50 or DFN full topology. The controller changes
only the two selected static routes while the topology remains running.

```bash
python scripts/minimal_rl_path_control.py --docker --episodes 20 --seed 20260722 \
  --output-dir runs/minimal-rl-path-control-v1
```

The final verified lightweight UI is the zero-dependency fallback server, which
reuses the existing Python validation, dry-run, topology SVG, and simulator
APIs:

```bash
python dashboard/static_server.py
```

It exposes `/healthz` and Scenario, AI, Metrics, Germany50, and RL sections.
It does not accept, save, or display API keys. Streamlit remains an optional
source implementation; its dependency installation was not the final validated
runtime path.

## Representative Results

Tracked representative results include:

- direct bandwidth runs:
  - `20 Mbps` configured -> about `19.2 Mbps`
  - `50 Mbps` configured -> about `47.9 Mbps`
  - `100 Mbps` configured -> about `95.7 Mbps`
- routed delay smoke:
  - configured one-way delay `30 ms`
  - measured RTT average about `72.615 ms`
  - throughput `18.6 Mbps`
- routed packet-loss smoke:
  - configured one-way loss `3%`
  - measured ping loss `10.0%`
  - throughput `13.8 Mbps`
- compatible-provider live six-node run:
  - ping loss `0.0%`
  - RTT average `82.194 ms`
  - throughput `18.3 Mbps`
  - selected path `client-1 -> router-a -> router-b -> router-d -> server-1`

## Current Limitations

- validated large-topology execution is intentionally capped below 10 nodes
- official OpenAI live path is implemented but still blocked by HTTP `429 insufficient_quota` as of `2026-07-14`
- some orchestration paths assume WSL Docker Engine rather than native Windows Docker CLI
- repository-root dependency locking is minimal and currently captured in `requirements.txt`
- local evidence and repeated live reruns are intentionally excluded from Git

## Germany50, DFN, And RL Scope

- Germany50 import and bounded dry-run support exist, but full experiment execution is deferred
- DFN import and bounded dry-run support exist, but full experiment execution is deferred
- a minimal fixed-seed tabular Q-learning, dual-static-path demonstration is
  implemented with six Docker nodes; broader RL workflows remain deferred

See the dated reports in `docs/progress/` for the exact boundary between completed work and deferred work.
