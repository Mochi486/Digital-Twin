# Germany50 full selected-route results

`runs/final-evaluation/germany50-full-fixed/selected-attempt-1/summary.json`
records successful instantiation of 50 containers and 88 Docker networks. The
complete 4,224-entry static-route plan is validated by
`route-plan-dry-run/summary.json`; the real topology instead installed 20
on-demand routes for the three evaluated endpoint pairs (99.53% reduction).

Shortest (Aachen–Koeln), median (Erfurt–Passau), and longest
(Oldenburg–Passau) each have three successful ping and iperf3 measurements,
route verification, qdisc verification, resource timing, and cleanup. This is
not evidence of all-pairs traffic or installation of all 4,224 static routes.
