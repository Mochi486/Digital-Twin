# Germany50 subset forwarding failure root cause and fix

The pre-fix subset failures were preserved under
`runs/final-evaluation/germany50-subset-*`. Diagnosis found that the scoped WSL
forwarding planner omitted access-edge bridge rules when a controller switched
between alternatives through multi-interface endpoints. The fix adds only
actual topology-edge and access-edge rules for runtime-selected paths; it does
not restore an 88×87 or any other full-mesh forwarding plan.

The corrected evidence is in `runs/final-evaluation/germany50-subset-fixed/`:
10-node shortest/median/longest each have three successful runs (9/9), and the
same is true for 20 nodes (9/9). Each retained run has scenario, route/qdisc
verification, ping, iperf3 metrics, and cleanup evidence. The 30-node connected
subset is dry-run validated only. These are Germany50 subset experiments, not
full all-pairs Germany50 traffic tests.
