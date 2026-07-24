# Experiment matrix

| Family | Status | Primary evidence |
| --- | --- | --- |
| Bandwidth | Partial retained evidence | `runs/current/metrics.json` retains the 20 Mbps measurement; the audit records that raw 50/100 Mbps files are not present. |
| Delay | PASS, 20/20 | `runs/delay_batch_20260713-135915/` |
| Packet loss | PASS, 20/20 | `runs/packet_loss_batch_20260713-153303/` |
| Dual router | PASS, 5/5 | `runs/two_router_batch_20260713-160810/` |
| AI mock / compatible live | PASS | See `runs/final-evaluation/evidence-inventory.json`; official OpenAI remains 429. |
| Germany50 selected paths | PASS | `runs/germany50-selected-paths-final/` |
| Germany50 10/20 subsets | PASS, 9/9 each | `runs/final-evaluation/germany50-subset-fixed/` |
| Germany50 30 subset | Dry-run PASS | `runs/final-evaluation/germany50-subset-30/` |
| Germany50 complete topology | Selected-route PASS | `runs/final-evaluation/germany50-full-fixed/selected-attempt-1/` |
| RL controlled seeds | PASS, five seeds | `runs/final-evaluation/rl-final/` |
| RL real Docker supplement | PASS, 80 valid episodes | `runs/final-evaluation/rl-docker-supplement/` |
| Dashboard | PASS, static fallback smoke | `dashboard/static_server.py` |

`final-results.csv` is retained as the original pre-supplement matrix; the RL
supplement summary is deliberately separate and is not backfilled into that
immutable CSV.
