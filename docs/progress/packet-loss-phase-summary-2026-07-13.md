# Packet-Loss Phase Summary - 2026-07-13

## Status

- Packet-loss phase completed on branch `feature/delay-loss-metrics`.
- Delay phase remained intact and a `30 ms` delay regression run passed after the loss implementation was added.
- Routed packet-loss experiments ran for one-way `packet_loss_percent` values `0`, `1`, `3`, and `5`.
- Each configured loss value was executed `5` times with `100` ping packets per run.
- Final packet-loss matrix completed with `20/20` successful runs.

## Evidence

- Packet-loss phase working evidence: `D:\home\fanys23\project_70\.local-evidence\packet-loss-phase-20260713-151120`
- Packet-loss experiment evidence root: `D:\home\fanys23\project_70\.local-evidence\packet-loss-experiments-20260713-153303`
- Summary JSON: `D:\home\fanys23\project_70\.local-evidence\packet-loss-experiments-20260713-153303\packet-loss-summary.json`
- Summary CSV: `D:\home\fanys23\project_70\.local-evidence\packet-loss-experiments-20260713-153303\packet-loss-summary.csv`
- Loss plot: `D:\home\fanys23\project_70\.local-evidence\packet-loss-experiments-20260713-153303\loss-vs-measured-ping-loss.svg`
- Throughput plot: `D:\home\fanys23\project_70\.local-evidence\packet-loss-experiments-20260713-153303\loss-vs-throughput.svg`

## Measured Results

| Configured one-way loss (%) | Theoretical RTT loss (%) | Measured ping loss mean (%) | Throughput mean (Mbps) |
| --- | ---: | ---: | ---: |
| 0 | 0.00 | 0.0 | 19.2 |
| 1 | 1.99 | 3.0 | 19.02 |
| 3 | 5.91 | 6.0 | 14.42 |
| 5 | 9.75 | 10.0 | 7.888 |

## Interpretation

- Loss is applied with router-side `netem` on both routed egress directions.
- The simulator records a theoretical round-trip loss percentage derived from the configured one-way loss, but it keeps that value separate from measured ping loss.
- Measured ping loss rises with configured one-way loss and shows noticeable run-to-run spread even with `100` packets.
- Throughput degrades substantially as configured loss increases, while the server-side `tbf` bandwidth cap remains active.

## Regression Checks

- Delay `30 ms` regression passed after packet-loss support was added.
- Unit tests covered:
  - JSON validation
  - ping parser
  - throughput parser
  - theoretical round-trip loss calculation
  - qdisc command generation
  - statistics helpers

## Notes

- Evidence paths are kept under `project_70\.local-evidence`.
- Local WSL host routing preparation and cleanup continue to use the project-scoped tag `project70-wsl-routing`.
