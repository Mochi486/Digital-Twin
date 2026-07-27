# Known limitations

Germany50 real traffic uses selected on-demand static routes; the complete
4,224-entry plan is dry-run validated, not installed for an all-pairs traffic
test. The complete topology was instantiated, but results support only the
three selected end-to-end paths.

Official OpenAI live validation is accurately retained as HTTP 429
`insufficient_quota`; no successful official OpenAI request is claimed. The
final UI is the zero-dependency `dashboard/static_server.py` fallback, not a
successful Streamlit deployment.

The RL real-Docker supplement contains 80 valid episodes. Threshold heuristic
outperformed Q-learning in this low-dimensional, rule-defined setting; this is
a negative result for RL superiority. Raw 50 Mbps and 100 Mbps bandwidth
measurements were not found by the final audit, so only the retained 20 Mbps
raw measurement should be cited until those original artifacts are recovered.
