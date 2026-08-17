# Dissertation Handoff

## Current status

- Template: TMLR template
- Page limit: 12-page body limit, excluding References and Appendix
- Experiment audit: 23 experiments audited; 0 insufficient
- Research framing: RQ, core claim, and 3 contributions completed
- References: 15 verified references
- Core artifacts: 4 core figures and 3 core tables
- Build: `supervisor_draft_v1.pdf` compiled successfully
- Length: body = 12 pages; total PDF = 15 pages
- Next step: manually review the complete PDF, revise it, then send it to the supervisor

## Evidence boundaries

- Germany50: 50 nodes / 88 links. The 4,224 routes are dry-run only; real traffic covers only the shortest, median, and longest routes.
- LLM API: Official OpenAI returned HTTP 429; the Qwen-compatible endpoint succeeded.
- RL: 80 valid real-Docker episodes; the heuristic outperformed Q-learning.
- Dashboard: documented-only; raw validation logs were not retained.
- Bandwidth experiments: direct 20 Mbps is a single retained historical record; 50/100 Mbps are supplementary replicated cohorts; the dual-router 20 Mbps 5-run result is an independent experiment.
