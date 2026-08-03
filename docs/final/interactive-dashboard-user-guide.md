# Interactive Dashboard user guide

Start the local server with `python3 dashboard/interactive_server.py --port
8765`, then open `http://localhost:8765/` in Windows. It binds only to
`127.0.0.1` and has no external assets or account/API-key fields.

Choose one of the allowlisted direct, client-router-server, or two-router
templates. Source and destination are constrained to the template client and
server. The SVG shows node roles and links; the validation response includes
the selected path. Set bandwidth (1–1000 Mbps), one-way delay (0–500 ms), loss
(0–20%), ping count (1–20), and iperf duration (1–30 seconds).

Dry-run is the default: click **Validate**, then **Run** to create an isolated
artifact directory without Docker. For a real Docker run choose two-router,
clear Dry-run, type exactly `RUN`, and click Run. Status is polled while the
trusted topology simulator runs. The result includes ping, RTT, loss,
throughput, route/qdisc evidence, and cleanup status where available.

Use Cancel for an active job and Cleanup for an explicit cleanup-status check.
After completion, download JSON, CSV, log, or a ZIP containing only the current
run's allowlisted artifacts. Stop the server with `Ctrl+C` in its terminal.

Germany50, formal RL, sealed final results, custom topology upload, arbitrary
commands/images/paths, CORS, and remote access are not supported. The console
does not accept credentials and POST requests require a local session CSRF
token plus matching local Host/Origin.
