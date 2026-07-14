# AI Scenario Phase Summary

Date: 2026-07-13

## Scope

- Complete AI-generated scenario support for bounded routed topologies up to 10 nodes.
- Run real WSL Docker experiments for the three mock AI scenarios.
- Validate all required pre-execution rejection paths.
- Attempt OpenAI live validation only when `OPENAI_API_KEY` is present inside WSL.

## Delivered Changes

- Reworked `scripts/run_ai_scenario_phase.py` into a WSL-root execution path with:
  - Docker environment verification
  - experiment-image verification
  - generator dry-run and simulator dry-run
  - real mock scenario execution
  - routed delay and packet-loss regressions
  - invalid-scenario validation evidence
- Tightened `scripts/ai_scenario_utils.py` to reject command-like content such as `docker`, `iptables`, and route-command strings before Docker execution.
- Extended `scripts/generate_scenario_ai.py` to capture OpenAI response metadata including response id when live generation is used.
- Extended `scripts/simulator_topology.py` to verify installed static routes and persist all-node route tables.
- Parameterized `scripts/simulator_routed.py` with explicit `--scenario` and `--output` arguments for clean regression execution.
- Expanded unit coverage in `tests/test_ai_scenario_utils.py`.

## WSL Docker Verification

- `docker version`: passed
- `docker info`: passed
- `docker run --rm hello-world`: passed
- Experiment image `my-iperf-tc`: already present

Evidence directory:

- `/mnt/d/home/fanys23/project_70/.local-evidence/ai-scenario-phase-20260714-093638`

## Mock AI Scenario Real Runs

### linear-5

- Schema validation: passed
- Semantic validation: passed
- Deterministic addressing and static-route generation: passed
- Simulator dry-run: passed
- Real runs: `2/2` successful
- Throughput: `18.8 Mbps`, `18.7 Mbps`
- Ping loss: `0.0%`, `0.0%`
- Reproducibility check: passed with near-identical throughput and both runs successful

Metrics:

- `/mnt/d/home/fanys23/project_70/runs/ai-scenario-phase-20260714-093638/linear-5-real-run-01/metrics.json`
- `/mnt/d/home/fanys23/project_70/runs/ai-scenario-phase-20260714-093638/linear-5-real-run-02/metrics.json`

### redundant-6

- Schema validation: passed
- Semantic validation: passed
- Deterministic addressing and static-route generation: passed
- Simulator dry-run: passed
- Real runs: `1/1` successful
- Throughput: `19.4 Mbps`
- Ping loss: `0.0%`

Metrics:

- `/mnt/d/home/fanys23/project_70/runs/ai-scenario-phase-20260714-093638/redundant-6-real-run-01/metrics.json`

### lossy-8

- Schema validation: passed
- Semantic validation: passed
- Deterministic addressing and static-route generation: passed
- Simulator dry-run: passed
- Real runs: `1/1` successful
- Throughput: `19.4 Mbps`
- Measured ping loss: `25.0%`
- Configured one-way packet loss: `1.0%`

Metrics:

- `/mnt/d/home/fanys23/project_70/runs/ai-scenario-phase-20260714-093638/lossy-8-real-run-01/metrics.json`

## Invalid Scenario Rejection

The following cases were rejected before Docker execution:

- disconnected topology
- duplicate link
- illegal node role
- over-node-limit topology
- invalid bandwidth / delay / packet-loss ranges
- command-like content inside AI-controlled fields
- non-object schema mismatch

Evidence:

- `/mnt/d/home/fanys23/project_70/.local-evidence/ai-scenario-phase-20260714-093638/invalid-scenario-validation.json`

## Routed Regressions

- single-router dry-run: passed
- two-router dry-run: passed
- delay regression real run: passed
  - configured one-way delay: `30 ms`
  - measured average RTT: `72.26 ms`
  - throughput: `18.6 Mbps`
- packet-loss regression real run: passed
  - configured one-way loss: `3%`
  - measured ping loss: `8.0%`
  - throughput: `14.4 Mbps`

## OpenAI Live Validation

- `OPENAI_API_KEY` was not present inside the WSL runtime used for the phase run.
- No live OpenAI scenario was generated.
- No live OpenAI Docker run was attempted.
- This remains the only item in this phase that requires manual credential injection before rerun.

Rerun command after exporting the key inside WSL:

```bash
cd /mnt/d/home/fanys23/project_70
export OPENAI_API_KEY=...
. .venv-wsl311/bin/activate
python scripts/run_ai_scenario_phase.py
```

## Explicit Non-Goals

- No Germany50 / DFN full-traffic execution
- No topology larger than 10 nodes
- No RL work
