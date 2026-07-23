"""Zero-dependency fallback dashboard for artifact browsing when Streamlit is unavailable."""
import argparse
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
        germany = load(ROOT / "runs/germany50-selected-paths-final/summary.json") or {}
        rl = load(ROOT / "runs/minimal-rl-path-control-v1/summary.json") or {}
        body = f"""<!doctype html><title>Digital Twin Dashboard</title><h1>Digital Twin Dashboard</h1>
<p>Zero-dependency fallback UI. API keys are not accepted, stored, or displayed.</p>
<h2>Scenario</h2><p>Existing JSON scenarios: data/</p><h2>AI</h2><p>Use guarded mock Generate/Validate/Dry-run via the existing Python API.</p>
<h2>Metrics / Germany50 selected paths</h2><pre>{json.dumps(germany.get('summaries', []), indent=2)}</pre>
<h2>RL and baselines</h2><pre>{json.dumps({k: rl.get(k) for k in ('q_learning','baselines','selected_path_counts')}, indent=2)}</pre>"""
        data = body.encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--port", type=int, default=8765); args = parser.parse_args()
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__": main()
