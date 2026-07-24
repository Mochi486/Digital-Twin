# Final evaluation report

The complete 50-node and 88-link Germany50 topology was instantiated. Real
traffic evaluation used on-demand static routing for three selected end-to-end
paths, while the complete 4,224-entry static routing plan was validated in
dry-run mode. The real selected mode installed 20 routes (99.53% fewer than the
theoretical plan) and completed three ping/iperf3 measurements for each of the
shortest, median, and longest paths. It is not an all-pairs Germany50 traffic
evaluation and does not claim that all 4,224 entries were installed.

The corrected subset evidence records 10-node 9/9 and 20-node 9/9 successful
runs; the connected 30-node subset is dry-run validated. Delay and packet-loss
matrices each retain 20 raw measurements. Their audit-derived means are,
respectively, 0.105/27.008/80.303/133.686 ms RTT for configured 0/10/30/50 ms
one-way delay, and 0/3/6/10% measured round-trip loss for configured
0/1/3/5% one-way loss.

The real-Docker RL supplement contains 80 valid episodes: 20 each for
Q-learning, threshold heuristic, fixed A, and fixed B. The heuristic reward is
17.116 ± 0.325 (95% CI ±0.142), versus Q-learning 4.143 ± 15.045 (±6.594).
Threshold heuristic materially outperformed Q-learning. The work demonstrates
a functioning learnable closed-loop control implementation, but does not
support a claim that reinforcement learning is superior to the heuristic.
