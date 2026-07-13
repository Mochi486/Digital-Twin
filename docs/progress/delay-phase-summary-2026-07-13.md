# Delay Phase Summary - 2026-07-13

## Status

- Delay phase completed on branch `feature/delay-loss-metrics`.
- Routed baseline had already been recovered on WSL Docker Engine with project-scoped host routing preparation.
- Delay experiments ran successfully for `0`, `10`, `30`, and `50` ms.
- Each delay value was executed `5` times, for `20/20` successful runs.

## Evidence

- Delay experiment evidence root: `D:\home\fanys23\project_70\.local-evidence\delay-experiments-20260713-135915`
- Summary JSON: `D:\home\fanys23\project_70\.local-evidence\delay-experiments-20260713-135915\delay-summary.json`
- Summary CSV: `D:\home\fanys23\project_70\.local-evidence\delay-experiments-20260713-135915\delay-summary.csv`
- RTT plot: `D:\home\fanys23\project_70\.local-evidence\delay-experiments-20260713-135915\delay-vs-rtt.svg`

## Measured Results

| Configured one-way delay (ms) | Mean RTT (ms) | Mean throughput (Mbps) |
| --- | ---: | ---: |
| 0 | 0.105 | 19.2 |
| 10 | 27.008 | 19.1 |
| 30 | 80.303 | 18.6 |
| 50 | 133.686 | 17.9 |

## RTT Scaling Review

The simulator saved the effective qdisc state in per-run metrics. For delayed runs, the saved state shows:

- `netem delay <N>ms` on router egress `eth0`
- `netem delay <N>ms` on router egress `eth1`
- `tbf rate 20Mbit ...` on server egress `eth0`

The delay semantics used by the simulator are one-way router egress delay on both routed subnets. A simple expectation would therefore be that ping RTT rises by about `2 × delay_ms`. The measured data are consistently higher than that simple baseline:

- `10 ms` configured produced `27.008 ms` mean RTT, about `7.008 ms` above `20 ms`
- `30 ms` configured produced `80.303 ms` mean RTT, about `20.303 ms` above `60 ms`
- `50 ms` configured produced `133.686 ms` mean RTT, about `33.686 ms` above `100 ms`

This report does not attribute that gap to any unverified mechanism. What can be stated directly from the saved qdisc state and measurements is:

- The path is not just the two router `netem` delays; it also includes the active server-side `tbf` qdisc.
- The measured RTT tracks the configured delay monotonically and almost linearly, but not as an exact `2 × delay_ms` mapping.
- The environment therefore contributes additional latency beyond the nominal router `netem` value, and the experiment must report measured RTT rather than infer RTT from configuration.

## Notes

- Delay evidence paths now consistently live under `project_70\.local-evidence`.
- The routed baseline and delay phase remain reproducible through the WSL host preparation helper `scripts/prepare_wsl_docker.py`.
