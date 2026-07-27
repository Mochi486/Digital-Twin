# Post-core Extension Plan

**Development branch:** `feature/post-core-extensions`  
**Baseline:** `core-platform-v1` (`a8675fe`)

## 1. SNDlib Germany50

Phase 1 is complete: import the official SNDlib native topology; retain source, license, checksum, and raw input; validate the 50-node/88-link graph; reuse the generic simulator for schema, connectivity, automatic addressing, static routes, route-conflict detection, resource estimates, and dry-runs. Create connected 5-node and 10-node dry-run subsets and select shortest, median, and longest endpoint paths. Do not start full 50-node Docker traffic.

The next safe subphase is selected-path real testing only, beginning with the 5-node subset and using tracked local evidence. It must not mutate the baseline tag or branch.

## 2. Minimal RL path selection

Define a narrow, simulator-independent interface: topology graph and link-state input; candidate-path action set; reward/constraint result; serializable policy decision. Begin only after the selected Germany50 path tests provide bounded, reproducible inputs. No training infrastructure or uncontrolled full-topology execution is in scope initially.

## 3. Lightweight Streamlit dashboard

Expose read-only scenario, dry-run, and selected-path result views through a small adapter layer. Keep it separate from simulator execution and do not embed credentials or Docker control in the UI.

## 4. Final integration and evaluation

Run bounded integration cases, compare static routing and the minimal RL policy on the same selected paths, document resources/limits, rerun the full test suite, and package reproducible evidence.
