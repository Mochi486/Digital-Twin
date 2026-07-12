# Docker Network Digital Twin

This repository contains a Docker-based network digital twin prototype for controlled bandwidth experiments. The current implementation includes both a direct client-server prototype and a routed client-router-server topology using Docker networks, static routing, ping validation, and iperf3 TCP traffic generation.

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
- `scripts/run_batch.py`: automated bandwidth sweep for 20, 50, and 100 Mbps
- `scripts/analyze_results.py`: analysis and throughput plotting
- `data/scenario.json`: direct topology scenario
- `data/scenario_routed.json`: routed topology scenario
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

## Planned Next Work

- delay and latency experiments
- packet-loss experiments
- repeated runs with summary statistics
- larger and multi-hop topologies
- AI scenario generation
- optional reinforcement learning for adaptive control

## Notes

- No remote has been configured automatically for this repository.
- The unrelated `iot-agent-system` remote must not be reused for this project.
