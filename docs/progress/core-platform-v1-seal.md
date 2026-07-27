# Core Platform v1 Seal

**Baseline commit:** `a8675fe42a3fea7530946d67ce404719ed955dc8`  
**Annotated tag:** `core-platform-v1`  
**Preserved branch:** `baseline/core-platform-v1`  
**Date:** 2026-07-22

## Included platform

The sealed core contains the Docker/`tc` simulation foundation, routed and generic topology simulators, deterministic automatic addressing and static-route generation, topology validation, bounded AI scenario validation, and the WSL host-routing helper. Obsolete tracked run artifacts, duplicate backups, plots, and superseded progress reports were removed as part of the seal cleanup. Shared AI configuration and logging support were also consolidated.

## Verification at seal

`python -m unittest discover -s tests -v` completed successfully: **43 tests passed**.

The already-tracked core evidence includes bounded real Docker experiments for baseline routing, delay, packet loss, two-router topologies, and selected 5/6/8-node AI-generated topologies. The validation suite is intentionally Docker-free and tests parsers, traffic-control command construction, graph/connectivity checks, addressing, routing, scenario validation, and provider fallbacks.

## Known limits

- Docker/`tc` real experiments require WSL Docker Engine and the host-routing prerequisites.
- Full DFN/Germany50 traffic execution was not a core-platform validation target.
- AI live execution depends on external credentials and provider quota; offline tests use fakes.
- RL and a dashboard are not part of this sealed baseline.

All Germany50, RL, and frontend work must start from `feature/post-core-extensions`; the `core-platform-v1` tag is immutable.
