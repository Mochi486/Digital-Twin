# Repository Contents

## Included Source Code

- `Dockerfile.iperf`
  - experiment image for `iperf3`, `ping`, and `tc`
- `scripts/simulator_real.py`
  - direct client-server bandwidth simulator
- `scripts/simulator_routed.py`
  - single-router routed simulator
- `scripts/simulator_topology.py`
  - generic multi-hop topology simulator
- `scripts/topology_utils.py`
  - deterministic normalization, addressing, routing, and topology helpers
- `scripts/routed_delay_utils.py`
  - delay/loss/bandwidth helpers and parsers
- `scripts/generate_scenario_ai.py`
  - AI scenario generator entry point
- `scripts/openai_live_utils.py`
  - provider creation, endpoint fallback, redaction, and structured request helpers
- `scripts/run_openai_live_validation.py`
  - bounded live validation runner
- `scripts/prepare_wsl_docker.py`
  - WSL host bridge routing helper
- `scripts/run_demo.py`
  - unified small demo entry point
- `scripts/run_two_router_batch.py`
  - two-router acceptance and regression batch
- `scripts/run_delay_batch.py`
  - delay matrix batch
- `scripts/run_packet_loss_batch.py`
  - packet-loss matrix batch

## Included Tests

- `tests/test_ai_scenario_utils.py`
- `tests/test_openai_live_utils.py`
- `tests/test_prepare_wsl_docker.py`
- `tests/test_routed_delay_utils.py`
- `tests/test_topology_utils.py`

These cover schema validation, semantic validation, provider parsing, secret redaction, deterministic routing, qdisc helper behavior, and WSL cleanup rule matching.

## Included Scenarios And Input Data

- `data/scenario.json`
  - direct bandwidth prototype scenario
- `data/scenario_routed.json`
  - single-router routed scenario
- `data/scenario_two_router_topology.json`
  - generic multi-hop example with two routers
- `data/external/`
  - imported source data used for larger deferred topology work

## Included Documentation

- `README.md`
  - project overview and usage
- `docs/QUICKSTART.md`
  - exact validated commands
- `docs/REPOSITORY_CONTENTS.md`
  - included and excluded content map
- `docs/progress/*.md`
  - dated implementation, experiment, and validation reports

## Included Representative Outputs

- `runs/run_001/`, `runs/run_002/`, `runs/run_003/`
  - representative direct bandwidth metrics
- `runs/ai-scenario-phase-20260714-093638/`
  - representative AI scenario outputs and SVGs
- `runs/openai-live-regressions-20260714-110941/`
  - representative bounded routed smoke outputs

These tracked outputs are intentionally small and publication-friendly:

- metrics JSON
- scenario JSON
- summary JSON or CSV where already present
- SVG topology or plot files

## Excluded Local Evidence

- `.local-evidence/`
  - full local evidence, logs, live payload archives, and intermediate diagnostics
- `.venv-win311/`
- `.venv-wsl311/`
- `__pycache__/`
- `.pytest_cache/`
- `.env`
- `*.bundle`
- ad hoc `runs/openai-compatible-live-validation-*`
- ad hoc `runs/openai-live-regressions-*` reruns beyond the selected representative set

These are excluded because they are machine-local, large, secret-adjacent, or not needed for supervisor review of the repository artifact.
