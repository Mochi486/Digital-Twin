# Reproducibility guide

Use the repository virtual environment and run the lightweight checks without
rerunning official experiments:

```bash
.venv-wsl311/bin/python -m unittest discover -s tests -v
.venv-wsl311/bin/python scripts/audit_pre_dissertation_evidence.py
git bundle verify pre-dissertation-rl-docker-v1.bundle
```

Germany50 `--route-mode full --dry-run` validates the 4,224-entry plan;
`--route-mode selected` is the already-recorded real traffic mode for three
paths on the complete topology with batched per-container routes. The final
dashboard is started with `python dashboard/static_server.py`, not Streamlit.
The audit inventory lists retained evidence and the raw-bandwidth limitation.
