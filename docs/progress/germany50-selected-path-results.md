# Germany50 selected-path real experiment results

## Scope and provenance

This is a **Germany50 path-extracted experiment**, not a full 50-node Germany50
run.  The deterministic scenarios were built from the SNDlib Germany50 import at
source commit `7aba844ef54417831f782be74764d7cb16022909`.  No full-topology
traffic, RL implementation, or frontend work was run or started.

Each scenario adds one client at the first backbone node and one server at the
last backbone node.  Every access and backbone link is configured with 20 Mbps,
10 ms one-way delay, and 0% packet loss.  Each real WSL Docker run executes a
100-packet flood ping and the same reverse TCP iperf3 invocation for 5 seconds.
The largest extracted scenario contains 10 Germany50 backbone nodes plus the two
end hosts; it is not a 50-node deployment.

| Class | Deterministic backbone path | Backbone hops | Real runs |
| --- | --- | ---: | ---: |
| shortest | Aachen -> Koeln | 1 | 3 |
| median | Erfurt -> Wuerzburg -> Augsburg -> Muenchen -> Passau | 4 | 3 |
| longest | Oldenburg -> Bremen -> Hannover -> Braunschweig -> Kassel -> Erfurt -> Wuerzburg -> Augsburg -> Muenchen -> Passau | 9 | 3 |

## Validation and execution

All nine runs completed schema validation, generated deterministic addressing
and static routes, passed route-conflict checks, and completed a full dry-run
before the real Docker execution.  Recorded route verification and netem qdisc
verification passed for every run.  The runner removed experiment containers,
networks, and tagged host-routing state after every run; a final Docker check
found no selected-path experiment resources remaining.

## Measurements

Values below are mean / sample standard deviation / minimum / maximum across
three successful real runs.  RTT is the measured ping round-trip average in ms;
throughput is reverse TCP iperf3 throughput in Mbps.

| Class | RTT (ms) | Throughput (Mbps) |
| --- | --- | --- |
| shortest (1 hop) | 41.196 / 0.211 / 40.999 / 41.489 | 18.8 / 0.0 / 18.8 / 18.8 |
| median (4 hops) | 104.623 / 0.690 / 103.928 / 105.563 | 17.8 / 0.0 / 17.8 / 17.8 |
| longest (9 hops) | 214.425 / 0.360 / 213.992 / 214.873 | 15.7 / 0.0 / 15.7 / 15.7 |

The measured RTT rises with extracted backbone-hop count and the 20 Mbps
configured bottleneck is approached most closely on the shortest path.  These
results characterize the three selected Germany50-derived paths only; they do
not represent a full Germany50-topology evaluation.

## Reproducible artifacts

- Machine-readable summary: `runs/germany50-selected-paths-final/summary.json`
- Tabular summary: `runs/germany50-selected-paths-final/summary.csv`
- RTT chart: `runs/germany50-selected-paths-final/hop-count-vs-rtt.svg`
- Throughput chart: `runs/germany50-selected-paths-final/hop-count-vs-throughput.svg`
- Per-run schema, dry-run, metric, route, and qdisc evidence:
  `runs/germany50-selected-paths-final/<class>-run-0N/`

## Test status and limitations

The complete unit-test suite passed: 45 tests.  Docker/WSL host-routing logs are
kept in the ignored `.local-evidence/` directory and no session, credential, or
machine configuration files are included in the commit.  The remaining next
safe scope is minimal RL path control, not another Germany50 full-topology run.
