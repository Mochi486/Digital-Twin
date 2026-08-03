# Interactive Dashboard validation

Branch and commit are recorded by the local validation command before handoff.
The implementation uses standard-library HTTP, local HTML/CSS/JavaScript, and
the existing generic topology simulator. Unit tests cover request validation,
security boundaries, dry-run lifecycle, and restricted downloads; the existing
test suite remains the regression baseline.

HTTP validation checks `/healthz`, `/api/system`, and `/api/scenarios` on
loopback. A minimal real Docker smoke, when Docker is available, is sent to
`POST /api/runs` through the same API with the two-router template, ping count
3, iperf duration 3 seconds, and confirmation `RUN`. Its artifacts are under
`runs/dashboard-interactive/`, never formal-result directories. The trusted
simulator performs its project-scoped container/network cleanup; a failed or
cancelled process is marked as cleanup attempted.

Known limits: real Dashboard runs are limited to the two-router template and
one active job. The Dashboard does not make Germany50/RL mutable or claim
all-pairs Germany50 traffic, RL superiority, Streamlit deployment, or official
OpenAI success.

On 2026-08-03 the HTTP dry-run integration path passed. The single requested
real Docker UI-path smoke was accepted but the trusted simulator exited with
status 1. Its scoped containers and networks were absent after cleanup; it is
recorded as a failed smoke, not a successful experiment. No retry was made.
