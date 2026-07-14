# Docker Network Digital Twin

This repository contains a Docker-based network digital twin prototype for controlled bandwidth experiments. The current implementation includes both direct and routed topologies using Docker networks, static routing, ping validation, iperf3 TCP traffic generation, JSON-driven multi-hop scenarios, and AI-assisted scenario generation with strict validation gates.

## Implemented Functionality

- Docker client-server prototype in `scripts/simulator_real.py`
- Client-router-server routed topology in `scripts/simulator_routed.py`
- Static route configuration between the client and server subnets
- Ping connectivity verification before throughput testing
- iperf3 TCP traffic generation with reverse mode enabled by default
- Bandwidth control using Linux `tc` inside Docker containers
- Batch automation for repeated configured-bandwidth runs in `scripts/run_batch.py`
- Result analysis and throughput plotting in `scripts/analyze_results.py`
- Scenario files in `data/scenario.json` and `data/scenario_routed.json`
- Metrics output written to `runs/current/metrics.json` and archived under `runs/run_*`

## Important Files

- `dockerfile`: older simulator container stub from an earlier prototype
- `Dockerfile.iperf`: Docker image used for the current iperf3 and routed topology experiments
- `scripts/simulator_real.py`: direct client-server bandwidth test
- `scripts/simulator_routed.py`: routed client-router-server test with static routes
- `scripts/simulator_topology.py`: generic JSON topology simulator for multi-hop routed scenarios
- `scripts/generate_scenario_ai.py`: prompt-driven scenario generator with `mock`, `openai`, and `openai_compatible` providers
- `scripts/run_batch.py`: automated bandwidth sweep for 20, 50, and 100 Mbps
- `scripts/run_two_router_batch.py`: two-router validation batch with baseline, delay, and loss checks
- `scripts/analyze_results.py`: analysis and throughput plotting
- `data/scenario.json`: direct topology scenario
- `data/scenario_routed.json`: routed topology scenario
- `data/scenario_two_router_topology.json`: generic two-router acceptance scenario
- `runs/current/metrics.json`: latest routed metrics example
- `throughput_plot.png`: throughput summary figure
- `latency_plot.png`: existing figure kept with the project

## Build The Experiment Image

Build the Docker image used by the current experiments:

```bash
docker build -f Dockerfile.iperf -t my-iperf-tc .
```

## Run The Routed Simulation

```bash
python scripts/simulator_routed.py
```

The routed workflow does the following:

- creates Docker networks for the two routed subnets
- starts the client, router, and server containers
- enables IPv4 forwarding on the router container
- configures static routes on the client and server
- verifies connectivity with `ping`
- applies the configured bandwidth limit using `tc`
- runs an iperf3 TCP test
- writes metrics to `runs/current/metrics.json`

## Run On WSL Docker Engine

Current validated execution path is WSL Docker Engine. Run Docker commands inside WSL, not with a Windows Docker CLI.

If you are running this project on WSL Ubuntu with Docker Engine:

```bash
python scripts/prepare_wsl_docker.py --ignore-existing &
python scripts/simulator_routed.py
```

The helper script installs narrowly scoped host `iptables` accept rules for this project's routed Docker bridges only. It can run either as root or through the repository's temporary privileged Docker helper fallback. Use:

```bash
python scripts/prepare_wsl_docker.py --cleanup
```

to remove only rules tagged for this project.

Verify the environment with:

```bash
docker version
docker info
docker run --rm hello-world
```

## Run Bandwidth Experiments

```bash
python scripts/run_batch.py
```

This batch script writes each scenario to `data/scenario.json`, runs the direct prototype, and stores outputs under:

- `runs/run_001`
- `runs/run_002`
- `runs/run_003`

Generate the throughput plot with:

```bash
python scripts/analyze_results.py
```

## Run The Generic Two-Router Topology

```bash
python scripts/prepare_wsl_docker.py --scenario data/scenario_two_router_topology.json --ignore-existing &
python scripts/simulator_topology.py --scenario data/scenario_two_router_topology.json
```

This path preserves the existing single-router simulator and adds a JSON-driven multi-hop topology flow with:

- three Docker subnets
- two router containers
- explicit static routes from scenario JSON
- dynamic interface resolution for `tc`
- per-router route table and qdisc capture

Run the acceptance batch with:

```bash
python scripts/run_two_router_batch.py
```

## Run The AI Scenario Phase

The AI scenario phase generates abstract routed scenarios, validates them, deterministically assigns addresses and routes, performs dry-runs, and executes bounded real experiments for scenarios up to 10 nodes.

From WSL root:

```bash
cd /mnt/d/home/fanys23/project_70
. .venv-wsl311/bin/activate
python scripts/run_ai_scenario_phase.py
```

If you want to enable official OpenAI live scenario generation, export `OPENAI_API_KEY` inside the WSL environment before running the phase script. The project never prints or stores the key itself.

If you want to enable a third-party OpenAI-compatible live provider from the current PowerShell session, set:

- `COMPAT_API_KEY`
- `COMPAT_BASE_URL`
- `COMPAT_MODEL_CANDIDATES`

The project only saves sanitized provider host, selected model, request id, usage, latency, and redacted non-sensitive responses.

For the bounded compatible-provider validation completed on `2026-07-14`, the actual live configuration was:

- provider type: `openai_compatible`
- provider host: `ws-1s2sexxqtqluyr11.cn-beijing.maas.aliyuncs.com`
- model: `qwen3.7-plus`
- endpoint: `chat.completions`
- structured-output mode: `response_format=json_schema`

## OpenAI Live Status

- Mock AI generation is complete and validated.
- Official OpenAI live request wiring uses the official Python SDK plus Responses API Structured Outputs.
- The latest official OpenAI live attempt on `2026-07-14` reached OpenAI and failed with HTTP `429` / `insufficient_quota`.
- Therefore no official OpenAI-generated scenario, dry-run, or real Docker run is counted as complete.
- Third-party OpenAI-compatible provider support is implemented with model-list probing and endpoint fallback across Responses API, Chat Completions JSON schema, JSON object, and plain JSON parsing.
- The bounded `2026-07-14` compatible-provider validation completed successfully against an Alibaba Cloud Bailian OpenAI-compatible endpoint using `qwen3.7-plus` and Chat Completions JSON schema mode.
- The latest compatible-provider live evidence is:
  - `D:\home\fanys23\project_70\.local-evidence\openai-compatible-live-validation-20260714-064525`
- See `docs/progress/openai-live-validation-summary-2026-07-14.md` and `docs/progress/openai-compatible-live-validation-summary-2026-07-14.md`.

## Current Results

Archived batch results in `runs/run_*` show:

- 20 Mbps configured -> about 19.2 Mbps measured
- 50 Mbps configured -> about 47.9 Mbps measured
- 100 Mbps configured -> about 95.7 Mbps measured

The latest routed example in `runs/current/metrics.json` currently records:

- `topology`
- `ping_success`
- `configured_bandwidth_mbps`
- `throughput_mbps`

## Current Results

- `linear-5` real runs: `2/2` successful, `18.8 Mbps` and `18.7 Mbps`
- `redundant-6` real runs: `1/1` successful, `19.4 Mbps`
- `lossy-8` real runs: `1/1` successful, measured `25.0%` ping loss, `19.4 Mbps`
- single-router dry-run regression passed
- two-router dry-run regression passed
- routed delay regression passed with `70.414 ms` average RTT at configured `30 ms` one-way delay
- routed packet-loss regression passed with measured `12.0%` ping loss at configured one-way `3%` loss
- official OpenAI live provider path is implemented but blocked by HTTP `429 insufficient_quota` as of `2026-07-14`
- third-party OpenAI-compatible provider live generation, dry-run, and real WSL Docker run completed on `2026-07-14`
- latest compatible-provider live metrics: `0.0%` ping loss, `82.194 ms` average RTT, `18.3 Mbps` throughput, selected path `client-1 -> router-a -> router-b -> router-d -> server-1`
- Germany50 / DFN full topology remains paused beyond dry-run and small-subset smoke validation

## Current Focus

- AI-generated small routed scenarios with schema and semantic validation
- deterministic address allocation and static route generation for generated scenarios
- WSL-backed real execution for scenarios up to 10 nodes
- larger DFN-derived full-traffic runs remain paused

## Notes

- No remote has been configured automatically for this repository.
- The unrelated `iot-agent-system` remote must not be reused for this project.
