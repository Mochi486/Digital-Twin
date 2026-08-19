# Reproducibility guide

From a fresh WSL clone, use the reviewer scripts without rerunning official
experiments:

```bash
bash scripts/reviewer_setup.sh
bash scripts/reviewer_dashboard.sh
```

The setup script creates `.venv-wsl311`, installs the Python requirements,
builds `my-iperf-tc`, and runs the standard-library unit tests. The Dashboard
start command executed by the second script is:

```bash
.venv-wsl311/bin/python dashboard/interactive_server.py --port 8765
```

For an already activated environment, the equivalent reviewer-facing command
is `python3 dashboard/interactive_server.py --port 8765`. The older
`dashboard/static_server.py` and Streamlit implementation are retained only as
legacy/optional references and are not the primary reviewer entry point.

Germany50 `--route-mode full --dry-run` validates the 4,224-entry plan;
`--route-mode selected` is the already-recorded real traffic mode for three
paths on the complete topology with batched per-container routes. The
Dashboard is a supporting interface, not a frontend for those formal runs.
The audit inventory and bandwidth supplement list the retained evidence,
including the later 50 Mbps and 100 Mbps direct real-Docker runs.
