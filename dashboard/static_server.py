"""Zero-dependency fallback dashboard for artifact browsing when Streamlit is unavailable."""
import argparse
import html
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in {"/health", "/healthz"}:
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok\n"); return
        extracted = load(ROOT / "runs/germany50-selected-paths-final/summary.json") or {}
        germany = load(ROOT / "runs/final-evaluation/germany50-full-fixed/selected-attempt-1/summary.json") or {}
        rl = load(ROOT / "runs/final-evaluation/rl-docker-supplement/summary.json") or {}
        qwen = load(ROOT / "runs/final-evaluation/ai-qwen-live-summary.json") or {}
        openai = load(ROOT / "runs/final-evaluation/ai-openai-429-evidence.json") or {}
        rl_policies = rl.get("policies", {})
        rl_total = sum(policy.get("valid_episodes", 0) for policy in rl_policies.values())
        def pretty(value):
            return html.escape(json.dumps(value, indent=2))
        body = f"""<!doctype html><title>Digital Twin Dashboard</title>
<h1>Digital Twin Dashboard</h1>
<p>Zero-dependency fallback UI. API keys are not accepted, stored, or displayed.</p>
<nav><a href="#scenario">Scenario</a> | <a href="#ai">AI</a> | <a href="#metrics">Metrics</a> | <a href="#germany50">Germany50</a> | <a href="#rl">RL</a></nav>
<h2 id="scenario">Scenario</h2><p>Read-only browser for existing JSON scenarios and sealed experiment artifacts under <code>data/</code> and <code>runs/</code>.</p>
<h2 id="ai">AI</h2><p>Guarded mock Generate/Validate/Dry-run remains a Python API workflow; this dashboard does not submit prompts or execute providers.</p><pre>{pretty({"compatible_provider": qwen, "official_openai": openai})}</pre>
<h2 id="metrics">Metrics</h2><p>Germany50 extracted-path metrics retained from the 1/4/9-hop experiment.</p><pre>{pretty(extracted.get("summaries", []))}</pre>
<h2 id="germany50">Germany50</h2><p>The complete 50-node and 88-link topology was instantiated. Real traffic used selected on-demand static routes for three paths; the 4,224-entry full plan was dry-run validated, not installed or tested all-pairs.</p><pre>{pretty(germany)}</pre>
<h2 id="rl">RL and baselines</h2><p>Real Docker supplement: {rl_total} valid episodes ({", ".join(f"{name}: {value.get('valid_episodes', 0)}" for name, value in rl_policies.items())}). Threshold heuristic outperformed Q-learning in this retained result.</p><pre>{pretty(rl_policies)}</pre>"""
        data = body.encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--port", type=int, default=8765); args = parser.parse_args()
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__": main()
