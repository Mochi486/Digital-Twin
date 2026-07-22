# SNDlib Germany50 Phase 1

## Source and licensing

- Raw source: `data/external/germany50/native/germany50.txt`
- Upstream: <https://sndlib.put.poznan.pl/download/sndlib-networks-native/germany50.txt>
- SHA256: `a295adf283f42c5cce8cd5f9c2fbd8b3071bd02c011c841726c0ec29c744c1fe`
- License: ZIB Academic License, retained in `data/external/germany50/LICENSE.txt`; upstream at <https://sndlib.put.poznan.pl/LICENSE.txt>

The imported SNDlib native topology has **50 nodes** and **88 undirected links**. This replaces the untracked Topology Zoo `Dfn.gml` draft (58 nodes/87 links), which is not used by Phase 1.

## Validation and dry-runs

- Schema, connected-graph validation, automatic `/29` addressing, static-route generation, and route-conflict checks passed.
- Full dry-run passed with 50 nodes, 88 links/subnets, and 4,224 generated routes.
- Resource estimate: 50 containers/routers, 88 Docker networks, 4,224 routes; no traffic-control policies are configured by the source topology.
- 5-node connected subset dry-run passed (4 links, 12 routes).
- 10-node connected subset dry-run passed (12 links, 96 routes).

No Docker containers, traffic, full 50-node experiment, RL workflow, or frontend were started.

## Selected endpoint paths

| Class | Endpoints | Hops |
| --- | --- | ---: |
| Shortest | Aachen → Koeln | 1 |
| Median | Erfurt → Passau | 4 |
| Longest | Oldenburg → Passau | 9 |

The generated selected-path scenarios are local evidence for the next bounded real-test phase. The next safe action is `GERMANY50_SELECTED_PATH_REAL_TESTS`.
