# Supervisor handoff

Core baseline: `core-platform-v1`; pre-dissertation baseline:
`pre-dissertation-v1`; latest RL supplement tag:
`pre-dissertation-rl-docker-v1`.

Germany50 full selected-route result: 50 containers, 88 networks, a dry-run
4,224-route plan, and 20 selected installed routes. All three selected-path
traffic groups succeeded; this is not an all-pairs claim. The RL supplement
has 20 valid real-Docker episodes per policy (80 total) and reports the
negative result that the threshold heuristic outperformed Q-learning. The final
UI is `dashboard/static_server.py`; the official OpenAI live result is the
retained 429 `insufficient_quota` outcome.

Use `runs/final-evaluation/evidence-inventory.json` and
`docs/final/pre-dissertation-evidence-audit.md` as evidence-map entry points.
