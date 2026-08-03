# Interactive Dashboard validation

Branch and commit are recorded by the local validation command before handoff.
The implementation uses standard-library HTTP, local HTML/CSS/JavaScript, and
the existing generic topology simulator. Unit tests cover request validation,
security boundaries, dry-run lifecycle, and restricted downloads; the existing
test suite remains the regression baseline.

HTTP validation checks `/healthz`, `/api/system`, and `/api/scenarios` on
loopback. A minimal real Docker smoke, when Docker is available, is sent to
`POST /api/runs` through the same API with the direct template, ping count
3, iperf duration 3 seconds, and confirmation `RUN`. Its artifacts are under
`runs/dashboard-interactive/`, never formal-result directories. The trusted
simulator performs its project-scoped container/network cleanup; a failed or
cancelled process is marked as cleanup attempted.

Known limits: real Dashboard runs are limited to the direct template and
one active job. The Dashboard does not make Germany50/RL mutable or claim
all-pairs Germany50 traffic, RL superiority, Streamlit deployment, or official
OpenAI success.

On 2026-08-03 the HTTP dry-run integration path passed. The final direct
Docker UI-path smoke (`3cada000bb4d`) used 20 Mbps, zero delay/loss, three
ping packets, and a three-second iperf3 measurement through `POST /api/runs`.
It succeeded with 3/3 ping replies, RTT 0.101/0.118/0.143 ms, and 19.4 Mbps
throughput. JSON, CSV, log, and ZIP downloads each returned HTTP 200. The
run-scoped containers and network were absent after cleanup. The earlier
two-router simulator failure was traced to an incompatible execution path;
the direct template now uses fixed argument-list Docker operations and scoped
resource names, with no arbitrary command, image, or path input.
