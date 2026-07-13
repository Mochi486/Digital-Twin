# Two-Router Phase Summary - 2026-07-13

## Status

- Two-router topology acceptance work completed on branch `feature/two-router-topology`.
- The existing single-router routed simulator remained intact.
- A new generic JSON-driven topology simulator was added for multi-hop routed experiments.
- The first acceptance scenario was `client1 -> router1 -> router2 -> server1`.

## Delivered Changes

- Added `scripts/simulator_topology.py` for generic routed topology execution.
- Added `scripts/topology_utils.py` for topology validation, route planning helpers, SVG generation, and impairment planning.
- Added `scripts/run_two_router_batch.py` for repeated baseline and regression runs.
- Added `data/scenario_two_router_topology.json` as the first generic multi-hop scenario.
- Extended `scripts/prepare_wsl_docker.py` so WSL host forwarding preparation can read both legacy `networks/subnet` and generic `subnets/cidr` scenario schemas.
- Added unit coverage in `tests/test_topology_utils.py` and extended `tests/test_prepare_wsl_docker.py`.
- Updated `README.md` with WSL and generic topology usage notes.

## Evidence

- Main two-router evidence directory:
  `D:\home\fanys23\project_70\.local-evidence\two-router-phase-20260713-160810`
- Summary JSON:
  `D:\home\fanys23\project_70\.local-evidence\two-router-phase-20260713-160810\two-router-summary.json`
- Topology SVG:
  `D:\home\fanys23\project_70\.local-evidence\two-router-phase-20260713-160810\two-router-topology.svg`

## Measured Results

- Two-router baseline runs: `5/5` successful
- Baseline configured bandwidth: `20 Mbps`
- Baseline mean measured throughput: `19.22 Mbps`
- Delay regression: `30 ms` completed successfully
- Delay regression measured average RTT: `72.55 ms`
- Delay regression throughput: `18.6 Mbps`
- Packet-loss regression: configured one-way `3%` completed successfully
- Packet-loss regression measured ping loss: `11.0%`
- Packet-loss regression throughput: `14.7 Mbps`

## Interpretation

- The generic simulator correctly created three separate Docker subnets and two router containers.
- Static routes from scenario JSON were sufficient to carry ping and iperf3 traffic end-to-end.
- The same routed impairment model used in earlier delay and packet-loss work carried over to the generic topology path.
- WSL host forwarding preparation remained necessary; the main compatibility fix in this phase was extending the preparation script to follow the generic subnet schema.

## Validation

- Full unit test suite passed with `14` tests after the two-router changes.
- Real Docker execution passed for:
  - one smoke run of the two-router topology
  - five baseline runs
  - one delay regression run
  - one packet-loss regression run

## Notes

- Raw per-run simulator logs remain under `.local-evidence` and are intentionally not tracked.
- Temporary experiment run directories are excluded locally through `.git/info/exclude`.
- The next phase is to generalize the simulator further for scalable imported topologies, beginning with Germany50.
