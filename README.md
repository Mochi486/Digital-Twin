# Digital Twin Network Emulation Platform

## Project overview

This UCL Internet Engineering MSc project is a Docker/WSL network digital twin.
JSON scenarios drive small direct and routed topologies, Linux `tc`/`netem`
impairments, ping/iperf3 measurement, static-route verification, and guarded
AI-assisted topology generation. The repository preserves its final evidence;
new local Dashboard experiments are isolated from it.

## Current final scope

The complete 50-node and 88-link Germany50 topology was instantiated. Real
traffic evaluation used selected on-demand routes for three representative
end-to-end paths. The complete 4,224-entry route plan was validated in dry-run
mode and was not installed for all-pairs testing.

The real-Docker supplement contains 80 valid episodes. The threshold heuristic
materially outperformed Q-learning. The result demonstrates a functioning
learnable closed-loop implementation but does not support RL superiority.

## Architecture

1. Docker networks and Linux traffic control on WSL.
2. JSON scenario descriptions under `data/`.
3. Direct, routed, and generic-topology simulators in `scripts/`.
4. Batch orchestration and reproducible evidence capture.
5. AI schema/semantic validation, plus a local interactive Dashboard.

## Core digital-twin capabilities

- Direct client/server and multi-router Docker emulation.
- Bandwidth, one-way delay, and packet-loss controls with qdisc capture.
- Deterministic subnets, static routes, route verification, topology SVGs, and
  ping/iperf3 metrics.
- Guarded mock, OpenAI, and OpenAI-compatible scenario-generation workflows.

## Bandwidth, delay, and loss results

The retained final matrix contains 20/20 delay and 20/20 packet-loss raw
measurements. Audit-derived delay RTT means are 0.105, 27.008, 80.303, and
133.686 ms for configured 0, 10, 30, and 50 ms one-way delay. Measured loss
was reported for configured 0, 1, 3, and 5% one-way loss. The retained raw
bandwidth evidence supports 20 Mbps; original raw 50 Mbps and 100 Mbps files
were not found and must not be reconstructed or cited as retained evidence.

## AI-assisted topology generation

AI output is schema- and semantically validated before projection to an
executable scenario. Forbidden operational content is rejected. The compatible
provider path was validated; the official OpenAI path is accurately retained as
HTTP 429 `insufficient_quota`, not a successful request.

## Germany50 scope and limitation

Germany50 is not an all-pairs traffic result. The complete topology was
instantiated, but real traffic was limited to shortest, median, and longest
representative paths. The 4,224-entry full route plan was dry-run validated
only. See [the final evaluation](docs/final/final-evaluation-report.md).

## RL 80-episode evaluation

The real-Docker supplement compares Q-learning, threshold heuristic, fixed A,
and fixed B over 20 valid episodes each. The threshold heuristic outperformed
Q-learning; this is a negative result for RL superiority, not a claim of it.
See [the RL supplement](docs/final/rl-real-docker-supplement.md).

## Interactive Dashboard

`dashboard/static_server.py` remains the read-only fallback for sealed
results. `dashboard/interactive_server.py` adds a local-only small-topology
experiment console: it supports allowlisted direct, routed, and two-router
templates, dry runs, and an explicitly confirmed two-router Docker path.
Germany50 and formal RL results remain read-only. New runs are written only to
`runs/dashboard-interactive/<timestamp>-<run-id>/`.

## Installation

```bash
cd /mnt/d/home/fanys23/project_70
python3 -m venv .venv-wsl311
. .venv-wsl311/bin/activate
python -m pip install -r requirements.txt
docker build -f Dockerfile.iperf -t my-iperf-tc .
```

## CLI quick start

```bash
.venv-wsl311/bin/python -m unittest discover -s tests -v
.venv-wsl311/bin/python scripts/run_demo.py two-router
.venv-wsl311/bin/python scripts/run_demo.py ai-mock
```

Do not rerun formal matrices, Germany50 selected-path evidence, or the RL
supplement to reproduce this README.

## Dashboard quick start

```bash
python3 dashboard/interactive_server.py --port 8765
```

Open `http://localhost:8765/` from a Windows browser. Start with Dry-run. A
real Docker run requires selecting the two-router template, clearing Dry-run,
and typing `RUN`. See the [interactive Dashboard guide](docs/final/interactive-dashboard-user-guide.md).

## Repository structure

- `data/` — immutable base scenarios and topology sources.
- `scripts/` — simulators, validation, orchestration, and analysis helpers.
- `dashboard/` — read-only fallback and zero-dependency interactive server.
- `runs/final-evaluation/`, `runs/germany50-selected-paths-final/` — sealed
  formal results.
- `runs/dashboard-interactive/` — new local Dashboard artifacts.
- `docs/final/` — final reports, evidence index, limitations, and guides.

## Reproducibility

Use the [reproducibility guide](docs/final/reproducibility-guide.md), evidence
inventory, and standard-library unit tests. The complete Germany50 route plan
may be dry-run validated; it must not be represented as all-pairs testing.

## Known limitations

Docker execution requires a WSL Docker Engine. Dashboard real execution is
intentionally limited to the small two-router template, one job at a time, and
local loopback. It accepts no credentials, commands, images, or file paths.
Raw 50/100 Mbps evidence remains missing. Official OpenAI remains HTTP 429.

## Dissertation status

Final formal results and tags are preserved. The Dashboard is an additive,
local experiment interface and does not alter formal bandwidth/delay/loss,
Germany50, AI, or RL conclusions. See the
[supervisor handoff](docs/final/supervisor-handoff-summary.md).
