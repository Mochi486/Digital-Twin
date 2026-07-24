# Pre-dissertation repository and evidence audit

This audit is read-only with respect to measured data; it parses retained artifacts and records only evidence completeness.

| Experiment or feature | Status | Raw evidence | Summary | Figure | Documentation | Consistency | Missing items |
| --- | --- | --- | --- | --- | --- | --- | --- |
| delay matrix | PASS | runs/delay_batch_20260713-135915/ | runs/final-evaluation/evidence-inventory.json | docs/final/figures/delay-vs-rtt.svg | docs/final/pre-dissertation-evidence-audit.md | 20 rows; means={'0': 0.105, '10': 27.008, '30': 80.303, '50': 133.686} | summary/figure are generated audit derivatives |
| packet-loss matrix | PASS | runs/packet_loss_batch_20260713-153303/ | runs/final-evaluation/evidence-inventory.json | docs/final/figures/loss-vs-measured-ping-loss.svg | docs/final/pre-dissertation-evidence-audit.md | 20 rows; measured means={'0': 0.0, '1': 3.0, '3': 6.0, '5': 10.0} | summary/figure are generated audit derivatives |
| dual-router | PASS | runs/two_router_batch_20260713-160810/ | runs/final-evaluation/evidence-inventory.json | runs/two_router_batch_20260713-160810/ | docs/final/pre-dissertation-evidence-audit.md | 5 rows; throughput mean=19.22 |  |
| bandwidth | PARTIAL | runs/current/metrics.json | README.md |  | docs/final/pre-dissertation-evidence-audit.md | 20 Mbps evidence=19.2 Mbps | No preserved raw 50/100 Mbps measurement files discovered |
| AI mock topology generation | PASS | .local-evidence/ai-scenario-phase-20260714-093638/{linear-5,redundant-6,lossy-8}-scenario.json | runs/final-evaluation/evidence-inventory.json | .local-evidence/ai-scenario-phase-20260714-093638/*-simulator-dry-run.svg | docs/progress/core-platform-v1-seal.md | three validated generated scenarios; only non-sensitive scenario/dry-run artifacts are tracked |  |
| AI compatible-provider live | PASS | runs/openai-compatible-live-validation-20260714-064525/metrics.json | runs/final-evaluation/ai-qwen-live-summary.json | runs/openai-compatible-live-validation-20260714-064525/topology.svg | docs/final/pre-dissertation-evidence-audit.md | 82.194 ms, 18.3 Mbps, 0% loss | sanitized provider summary required for repository retention |
| AI official OpenAI | PASS | .local-evidence/openai-live-validation-20260714-030746/openai-live-summary.json | runs/final-evaluation/ai-openai-429-evidence.json |  | docs/final/pre-dissertation-evidence-audit.md | HTTP 429 insufficient_quota preserved in sanitized summary | original local evidence intentionally contains environment metadata and is not tracked |
| Germany50 selected-route full topology | PASS | runs/final-evaluation/germany50-full-fixed/selected-attempt-1/ | runs/final-evaluation/germany50-full-fixed/selected-attempt-1/summary.json | runs/final-evaluation/germany50-full-fixed/ | docs/progress/germany50-full-results.md | 50 containers, 88 networks, selected routes only |  |
| Germany50 10/20-node subsets and 30-node dry-run | PASS | runs/final-evaluation/germany50-subset-fixed/ | runs/final-evaluation/germany50-subset-fixed/summary.json | runs/final-evaluation/germany50-subset-fixed/ | docs/progress/germany50-subset-failure-root-cause-and-fix.md | corrected run summaries={'10': 9, '20': 9}; 30 dry-run |  |
| RL real Docker supplement | PASS | runs/final-evaluation/rl-docker-supplement/checkpoint.json | runs/final-evaluation/rl-docker-supplement/summary.json | runs/final-evaluation/rl-docker-supplement/figures/ | docs/final/rl-real-docker-supplement.md | policy counts={'q_learning': 20, 'heuristic': 20, 'fixed_a': 20, 'fixed_b': 20} |  |
| fallback dashboard | PASS | dashboard/static_server.py | runs/final-evaluation/pre-dissertation-checkpoint.json |  | docs/final/known-limitations.md | static Python fallback; not Streamlit |  |

## Cross-checks

- JSON/CSV parse errors: 0
- Delay mean RTTs (ms): {'0': 0.105, '10': 27.008, '30': 80.303, '50': 133.686}
- Packet-loss mean measurements (%): {'0': 0.0, '1': 3.0, '3': 6.0, '5': 10.0}
- RL valid episodes: {'q_learning': 20, 'heuristic': 20, 'fixed_a': 20, 'fixed_b': 20}
- Germany50 wording: full topology was instantiated; selected on-demand routes, not all 4,224 routes, carried real traffic.
- OpenAI official result remains HTTP 429 `insufficient_quota`; the compatible-provider six-node run is separate.
