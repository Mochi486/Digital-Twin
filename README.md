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
- `scripts/generate_scenario_ai.py`: prompt-driven scenario generator with mock and optional OpenAI providers
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

If you are running this project on WSL Ubuntu with Docker Engine instead of Docker Desktop:

```bash
python scripts/prepare_wsl_docker.py --ignore-existing &
python scripts/simulator_routed.py
```

The helper script installs narrowly scoped host `iptables` accept rules for this project's routed Docker bridges only. Use:

```bash
python scripts/prepare_wsl_docker.py --cleanup
```

to remove only rules tagged for this project.

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

## Current Focus

- AI-generated small routed scenarios with schema and semantic validation
- deterministic address allocation and static route generation for generated scenarios
- safe dry-run and small-scale execution only
- larger DFN-derived full-traffic runs paused pending WSL forwarding scalability work

## Notes

- No remote has been configured automatically for this repository.
- The unrelated `iot-agent-system` remote must not be reused for this project.
