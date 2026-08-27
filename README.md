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
was reported for configured 0, 1, 3, and 5% one-way loss.

The dissertation-primary bandwidth evidence is the balanced supplementary
cohort in
[`runs/bandwidth-balanced-evidence-supplement-20260826/planned-15/`](runs/bandwidth-balanced-evidence-supplement-20260826/planned-15/): 15/15 valid
planned runs, with five runs each at 20, 50, and 100 Mbps. Mean throughputs are
19.20, 47.80, and 94.76 Mbps respectively. The former `bandwidth=PARTIAL`
inventory entry described a pre-supplement historical snapshot and is
superseded for dissertation use by this retained balanced cohort. The earlier
20-Mbps record and 50/100-Mbps supplement remain preserved as separate cohorts
and are not pooled with the balanced cohort.

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

`dashboard/interactive_server.py` is the final reviewer-facing Dashboard. It is
a supporting interface for browsing and bounded checks, not the frontend used
to run every formal experiment. It supports dry-run for allowlisted direct,
routed, and two-router templates; real Docker execution is restricted to an
explicitly confirmed direct run. Germany50 and formal RL results remain
read-only. New runs are written only to
`runs/dashboard-interactive/<timestamp>-<run-id>/`.
The local SVG distinguishes the selected source with a solid green outline and
the selected destination with a dashed red outline.

## Reviewer requirements

- WSL 2 with a Linux distribution and Bash.
- Docker available from WSL, with the Docker daemon running.
- Python 3 with the `venv` module (Python 3.11 is the validated version).

## Fresh-clone reviewer quick start

```bash
git clone https://github.com/Mochi486/Digital-Twin.git
cd Digital-Twin
bash scripts/reviewer_setup.sh
bash scripts/reviewer_dashboard.sh
```

The setup script creates `.venv-wsl311`, installs `requirements.txt`, builds
the allowlisted `my-iperf-tc` image, and runs the non-formal unit-test suite. It
does not execute delay, loss, Germany50, RL, or other formal experiment
matrices. Open `http://localhost:8765/` from the host browser after the start
script reports that the Dashboard is listening. Stop it with `Ctrl+C`.

## CLI quick start

```bash
.venv-wsl311/bin/python -m unittest discover -s tests -v
```

Do not rerun formal matrices, Germany50 selected-path evidence, or the RL
supplement to reproduce this README.

## Dashboard quick start

```bash
.venv-wsl311/bin/python dashboard/interactive_server.py --port 8765
```

Open `http://localhost:8765/` from a Windows browser. Start with Dry-run. A
real Docker run requires selecting the direct template, clearing Dry-run,
and typing `RUN`. See the [interactive Dashboard guide](docs/final/interactive-dashboard-user-guide.md).

## Repository structure

- `data/` — immutable base scenarios and topology sources.
- `scripts/` — simulators, validation, orchestration, and analysis helpers.
- `dashboard/` — final interactive reviewer server plus legacy/optional UI
  implementations retained for reference. `interactive_server.py` is the
  reviewer entry point; `static_server.py` and Streamlit `app.py` are not.
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
intentionally limited to the small direct template, one job at a time, and
local loopback. It accepts no credentials, commands, images, or file paths.
Official OpenAI remains HTTP 429. The legacy Streamlit UI is retained for
reference and has its own optional `dashboard/requirements.txt`; it is not
installed or launched by the reviewer workflow.

## Dissertation status

Final formal results and tags are preserved. The Dashboard is an additive,
local experiment interface and does not alter formal bandwidth/delay/loss,
Germany50, AI, or RL conclusions. See the
[supervisor handoff](docs/final/supervisor-handoff-summary.md).
