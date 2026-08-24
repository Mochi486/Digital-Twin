# Figure and Table Plan - Supervisor Draft V1

## Body assets

| Asset | RQ / claim | Evidence source | Planned body position | Readiness | Appendix recommendation | Evidence limitation |
|---|---|---|---|---|---|---|
| Figure 1 - Overall system architecture | RQ0, C1, C3 | Repository architecture, scenario validators, topology/routing/impairment runners, evidence inventory | Section 3, after objectives and scope | PUBLICATION_READY; PDF/PNG/SVG plus editable Python source | No | Conceptual architecture; it does not claim synchronization with a production network. AI/RL/Dashboard are supporting extensions. |
| Figure 2 - Main impairment results | RQ1, C2 | `runs/bandwidth-evidence-supplement/{summary.json,per-run-results.csv}`; retained delay/loss raw metrics; cross-check against `docs/final/figures/{delay-vs-rtt.svg,loss-vs-measured-ping-loss.svg}` | Section 5.1 | PUBLICATION_READY; vector PDF plus PNG/SVG | Per-run data only | `DISSERTATION_REGENERATED_FROM_REAL_DATA`. The project audit SVGs were inspected but not reused because they omit the replicated bandwidth cohorts and the uncertainty/provenance in the dissertation composite. Direct 20 Mbps is a single record. |
| Figure 3 - Topology scaling/Germany50 | RQ2, C2 | `data/scenario_germany50.json`; selected-path definitions; full-topology selected-route and route-plan summaries | Section 5.2 | PUBLICATION_READY; vector PDF plus PNG/SVG | Detailed path table | 4,224 entries are dry-run route-plan evidence. Real traffic covers only shortest/median/longest representative paths. |
| Figure 4 - RL comparison | RQ3, C3 | `runs/final-evaluation/rl-docker-supplement/per-episode-results.csv` and `runs/final-evaluation/rl-docker-supplement/summary.json` | Section 5.3 | PUBLICATION_READY; vector PDF plus PNG/SVG | Four-policy table and settings | Figure displays 40 episodes for heuristic/Q-learning; the retained aggregate has 80 valid episodes across four policies. The heuristic achieved a higher mean reward than Q-learning under the evaluated setup. |
| Table 1 - Experimental matrix | RQ1-RQ3 | `notes/experiment_inventory.md`; `experiment_summary.csv` | Section 4 | PUBLICATION_READY | Detailed evidence paths | Mixes repeated cohorts, single records, and documented-only evidence; run/valid counts remain explicit. |
| Table 2 - Main quantitative results | RQ1, C2 | `experiment_summary.csv` | Section 5.1 | PUBLICATION_READY | Full precision/per-run data | RR and AC provenance are explicitly distinguished. Direct 20 Mbps is marked as a single record. |
| Table 3 - Extended validation summary | RQ2, RQ3, C2, C3 | Germany50, AI, RL, Dashboard summaries and inventory | Section 5.3 | PUBLICATION_READY | Full evidence index | Germany50 dry-run/traffic, provider identity, RL outcome, and Dashboard missing-log boundaries are mandatory. |

## Source and output files

- Editable generation source: `analysis/figure_generation/generate_phase_e_figures.py`.
- Figure 1: `figures/architecture/overall_system_architecture.{pdf,png,svg}`.
- Figure 2: `figures/bandwidth/main_impairment_results.{pdf,png,svg}`.
- Figure 3: `figures/germany50/topology_scaling_germany50.{pdf,png,svg}`.
- Figure 4: `figures/rl/rl_heuristic_vs_qlearning.{pdf,png,svg}`.
- Tables: `tables/table_1_experimental_matrix.tex`, `table_2_quantitative_results.tex`, and `table_3_extended_validation.tex`.

## Page-discipline rule

Only these four figures and three tables belong in the body. Detailed configurations, evidence paths, the four-policy RL summary, and Germany50 path detail remain in the Appendix. If body length exceeds 12 pages, first shorten repeated prose and captions; do not shrink TMLR fonts or remove central evidence.
