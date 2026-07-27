# RL real-Docker supplement

This supplement preserves the pre-dissertation v1 results and adds a balanced
real-Docker policy comparison. It uses the existing minimal two-path topology,
identical 20-episode phase schedule, route/qdisc verification, ICMP, iperf3,
and project-scoped cleanup for every policy. It does not modify Germany50,
bandwidth, delay/loss, AI, or dashboard measurements.

## Samples and evidence

The four valid Q-learning episodes already recorded in
`runs/final-evaluation/rl-final/docker-evaluation/episodes-progress.json` were
verified for state/action, matched route checks, ping, iperf3, RTT, loss,
throughput, reward, and cleanup evidence. They were retained unchanged and
were supplemented to 20 valid Q-learning episodes. Threshold heuristic, fixed
A, and fixed B each have 20 new real-Docker episodes under the same ordered
network phases. The aggregate therefore contains 80 valid measured episodes.

| Policy | n | Reward mean ± std | RTT mean ms | Loss mean % | Throughput mean Mbps | switches | A/B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Q-learning | 20 | 4.143 ± 15.045 | 89.225 | 2.500 | 9.855 | 0 | 20/0 |
| Threshold heuristic | 20 | 17.116 ± 0.325 | 30.189 | 0.000 | 18.625 | 1 | 10/10 |
| Fixed A | 20 | -1.419 ± 21.126 | 99.609 | 12.500 | 9.812 | 0 | 20/0 |
| Fixed B | 20 | 0.257 ± 19.665 | 91.027 | 10.000 | 9.808 | 0 | 0/20 |

The 95% reward confidence intervals are ±6.594, ±0.142, ±9.259, and ±8.619
respectively. Full per-episode rows, including all low-reward outcomes, are in
`runs/final-evaluation/rl-docker-supplement/per-episode-results.csv`; aggregate
statistics and confidence intervals are in `summary.json` and
`policy-summary.csv`. The figures directory contains reward, RTT, loss,
throughput, path-selection timeline, and policy-comparison SVGs.

Two failed trials were retained as `FAILED_RETRIED` checkpoint attempts rather
than silently discarded: heuristic episode 11 exposed the now-fixed
runtime-path forwarding omission, and fixed-A episode 14 had a transient
zero-reply ping under the impaired phase. Only their corresponding episode
indices were retried; all 80 completed rows remain in the statistics.

## Conclusion

The threshold heuristic outperformed Q-learning in this low-dimensional,
rule-defined environment. This is a negative result for the claim that the
current Q-learning configuration is superior to the heuristic; no episodes
were selected or removed to change that outcome. The implementation still
demonstrates a real-Docker learnable control loop with runtime route selection,
route verification, state observation, measured reward, checkpoint recovery,
and cleanup. More complex state, non-stationary conditions, and longer
training remain future work rather than claims supported by this experiment.

The original controlled five-seed simulation evaluation remains separately
preserved under `runs/final-evaluation/rl-final/`; this document reports only
the balanced real-Docker four-policy supplement.
