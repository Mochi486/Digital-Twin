# Minimal RL dual-path control results

## Scope

This is a bounded six-node Docker experiment, not a full Germany50 or DFN run.
It consists of one client, one server, and four routers.  Two precomputed static
paths are selected by replacing only the relevant `r1` and `r4` routes while the
topology stays running:

- Path A: `r1 -> r2 -> r4`
- Path B: `r1 -> r3 -> r4`

No dynamic routing protocol was used.  The controller state is binned observed
RTT, packet loss, throughput, and current path.  Actions are `A` and `B`; the
fixed-seed tabular Q-learning reward is:

`throughput_mbps - 0.05 * rtt_ms - 0.50 * packet_loss_percent`.

## Real Docker evaluation

The WSL Docker run used seed `20260722`, a single persistent six-node topology,
and 20 short episodes.  Phase 1 made A preferable (5 ms / 0% / 20 Mbps versus
30 ms / 4% / 12 Mbps for B); Phase 2 reverses those path conditions.  Every
episode replaced and verified the selected forward and reverse static routes;
qdisc policies were reapplied on the already-running routers.  The route switch
verification result is `true` and cleanup completed in 3.103 seconds.

| Controller | Result |
| --- | --- |
| Q-learning | selected A 13 times and B 7 times; mean reward 5.852; mean RTT 61.499 ms; mean throughput 12.428 Mbps |
| Fixed A | mean reward 8.425 (deterministic same-phase comparison) |
| Fixed B | mean reward 8.439 (deterministic same-phase comparison) |
| Threshold heuristic | mean reward 16.918; selected A/B 10/10 |

The policy is intentionally minimal and exploratory, so its short-run reward is
below the oracle-like threshold heuristic.  It nevertheless demonstrates
state/action/reward learning, reproducible seed handling, and in-place route
control under a real phase change rather than claiming optimal RL performance.

## Artifacts and reproducibility

- `runs/minimal-rl-path-control-v1/episodes.json`
- `runs/minimal-rl-path-control-v1/episodes.csv`
- `runs/minimal-rl-path-control-v1/summary.json`
- `runs/minimal-rl-path-control-v1/reward.svg`
- `runs/minimal-rl-path-control-v1/path-selection.svg`
- `runs/minimal-rl-path-control-v1/rtt.svg`
- `runs/minimal-rl-path-control-v1/throughput.svg`

The offline mock test fixes the same seed and verifies repeatable path counts and
Q-learning aggregates.  Local Docker/host-routing logs remain in ignored
`.local-evidence/`; final cleanup leaves no project containers or networks.
