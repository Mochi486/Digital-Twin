# Dashboard user acceptance

## Launch and access

The final dashboard is the zero-dependency `dashboard/static_server.py`
fallback, not Streamlit. Start it from the repository root:

```bash
python3 dashboard/static_server.py --port 8765
```

It binds only to `127.0.0.1`. In a Windows browser, open
`http://localhost:8765/`; WSL localhost forwarding makes this local address
available without exposing the service publicly. The health endpoint is
`http://localhost:8765/healthz`.

## Verified page content

The dashboard is a **visualization-only** acceptance view. Its in-page
navigation anchors are:

- `/#scenario`: explains that existing scenarios are retained artifacts.
- `/#ai`: shows the compatible-provider result and the official OpenAI HTTP
  429 `insufficient_quota` result; it does not submit prompts.
- `/#metrics`: shows the extracted Germany50 1/4/9-hop metrics.
- `/#germany50`: shows the 50-node/88-link topology, 4,224-entry dry-run plan,
  and selected-route traffic scope.
- `/#rl`: shows the final real-Docker policy summary: 20 valid episodes per
  policy (80 total), including the negative result for Q-learning.

The acceptance request returned HTTP 200 for `/` and `/healthz`; all five
navigation anchors, the Germany50 scope statement, the OpenAI 429 evidence,
the Qwen result, and the 80-episode RL summary rendered in the returned HTML.
The page has no JavaScript, no external CSS/image/CSV/JSON resource requests,
and no input or password fields, so there were no browser-console JavaScript
errors or asset 404s to observe. Browser automation was not available in this
environment; the actual rendered document and HTTP responses were inspected.

## Supported and unsupported interaction

Supported interaction is limited to clicking the five navigation anchors and
reading the sealed results. The dashboard does **not** select nodes or
endpoints, configure bandwidth/delay/loss, generate topologies, execute Docker,
run ping/iperf3/Germany50/RL, display live progress, retain a history, or offer
CSV/JSON downloads. It does not accept, display, store, or persist API keys.

## Manual acceptance steps

1. Open `http://localhost:8765/` in a Windows browser.
2. Click Scenario, AI, Metrics, Germany50, and RL in the top navigation.
3. Confirm the AI section reports official OpenAI HTTP 429 rather than success.
4. Confirm the Germany50 section says 50 nodes, 88 links, a 4,224-route
   dry-run plan, and selected-route—not all-pairs—traffic.
5. Confirm the RL section reports 80 valid real-Docker episodes and says the
   threshold heuristic outperformed Q-learning.
6. Confirm there are no forms, run buttons, API-key fields, or download buttons.

The dashboard acceptance passes when all sections render these statements and
the health endpoint returns `ok`. Stop the service with `Ctrl+C` in the
terminal that started it. If that terminal is unavailable, identify the local
listener with `ss -ltnp | grep :8765` and stop only that Python PID.
