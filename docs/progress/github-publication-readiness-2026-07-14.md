# GitHub Publication Readiness

Date: 2026-07-14

## Current Head

- Branch: `feature/ai-scenario-generation`
- Validation-start HEAD: `5235bdf7dbd934ed25257d5d75a5123a819f8648`

## Publication Goal

Prepare the current MSc project artifact for publication into a new independent GitHub repository without changing the existing `origin` remote and without uploading local evidence, virtual environments, secrets, bundles, or unscreened temporary run directories.

## Verified Repository Content

The checked working tree contains the required project components:

- Dockerfiles:
  - `Dockerfile.iperf`
  - `dockerfile`
- `scripts/`
  - single-router simulator
  - generic topology simulator
  - delay and packet-loss batch runners
  - AI scenario generator
  - live provider validation runner
  - WSL Docker compatibility helper
  - unified demo entry point `scripts/run_demo.py`
- `tests/`
- `data/`
- `docs/progress/`
- `README.md`
- representative tracked metrics, scenarios, and SVG outputs under `runs/`

## Tests And Validation

### Unit Tests

- Command:
  - `.\.venv-win311\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`
- Result:
  - `43/43` passed

### Dry-Run And Demo Checks

- `python scripts/run_demo.py --help`
  - passed
- single-router dry-run helper
  - passed
  - evidence: `.local-evidence/publication-check-single-router/`
- two-router dry-run helper
  - passed
  - evidence: `.local-evidence/publication-check-two-router/`
- AI mock dry-run
  - passed
  - evidence: `.local-evidence/demo-ai-mock-20260714-161126/`

### README / QUICKSTART Command Validation

Executed commands:

- `python scripts/run_demo.py baseline`
  - passed
- `python scripts/run_demo.py two-router`
  - passed
- raw single-router command with explicit host-routing preparation
  - passed
- raw mock AI generation command
  - passed

Path validation:

- all `python scripts/*.py` command references found in:
  - `README.md`
  - `docs/QUICKSTART.md`
  - `docs/REPOSITORY_CONTENTS.md`
- result:
  - no missing script paths

## Secret Scan

Literal-value scan result:

- `OPENAI_API_KEY` literal in tracked publication files:
  - not present in current environment, therefore no literal file hit
- current `COMPAT_API_KEY` literal in tracked publication files:
  - no hits
- `.env` file in repository root:
  - not present

Pattern-level review result:

- repository source and docs intentionally contain safe references to environment-variable names and redaction logic
- no actual live key value was found in tracked publication files
- no broken path `project_70.local-evidence` remained in scanned files

## Included Publication Content

Primary content to publish:

- source code under `scripts/`
- tests under `tests/`
- scenario and input data under `data/`
- user-facing documentation:
  - `README.md`
  - `docs/QUICKSTART.md`
  - `docs/REPOSITORY_CONTENTS.md`
  - `docs/progress/*.md`
- representative tracked outputs:
  - `runs/run_001/`
  - `runs/run_002/`
  - `runs/run_003/`
  - `runs/ai-scenario-phase-20260714-093638/`
  - `runs/openai-live-regressions-20260714-110941/`
  - `runs/current/metrics.json`
  - tracked SVG plots

## Excluded Content

Excluded from publication:

- `.venv-win311/`
- `.venv-wsl311/`
- `.local-evidence/`
- `__pycache__/`
- `.pytest_cache/`
- `.env`
- `*.bundle`
- `runs/openai-compatible-live-validation-*`
- `runs/openai-live-regressions-*` local reruns not already tracked
- `runs/demo-*`
- large raw Docker logs
- local backup directories outside the repository workspace

## Known Limitations

- official OpenAI live path remains blocked by HTTP `429 insufficient_quota`
- compatible-provider live validation is complete, but requires user-supplied in-session credentials
- validated real execution remains bounded to topologies of 10 nodes or fewer
- Germany50 and DFN full experiments remain deferred
- RL remains outside project scope

## Publication Readiness Status

Result:

- ready for independent GitHub repository creation
- ready for push to a new remote named `digital-twin`
- existing `origin` can remain unchanged
