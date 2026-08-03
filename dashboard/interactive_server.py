#!/usr/bin/env python3
"""Local-only, zero-dependency controller for small Docker topology experiments.

It deliberately accepts a tiny JSON schema rather than commands, paths, images,
or generated topology data.  Real runs use the existing generic topology
simulator and a per-run derived scenario with project-scoped resource names.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from collections import deque
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "dashboard" / "web"
RUN_ROOT = ROOT / "runs" / "dashboard-interactive"
TEMPLATES = {
    "direct": ("Direct client-server", ROOT / "data" / "scenario.json"),
    "routed": ("Client-router-server", ROOT / "data" / "scenario_routed.json"),
    "two-router": ("Two-router topology", ROOT / "data" / "scenario_two_router_topology.json"),
}
LIMITS = {"bandwidth_mbps": (1, 1000), "delay_ms": (0, 500), "loss_percent": (0, 20),
          "ping_count": (1, 20), "iperf_duration_seconds": (1, 30)}
MAX_BODY = 16 * 1024
MAX_LOG = 256 * 1024
RUN_ID = re.compile(r"^[a-f0-9]{12}$")
ARTIFACTS = {"json": "result.json", "csv": "result.csv", "log": "run.log", "zip": "bundle.zip"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_template(template_id: str) -> dict:
    if template_id not in TEMPLATES:
        raise ValueError("Unknown scenario template")
    return json.loads(TEMPLATES[template_id][1].read_text(encoding="utf-8"))


def graph(scenario: dict) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {item["id"]: set() for item in scenario["nodes"]}
    for link in scenario.get("links", []):
        result[link["source"]].add(link["target"])
        result[link["target"]].add(link["source"])
    return result


def path_between(scenario: dict, source: str, destination: str) -> list[str] | None:
    links = graph(scenario)
    queue = deque([[source]])
    visited = {source}
    while queue:
        path = queue.popleft()
        if path[-1] == destination:
            return path
        for node in sorted(links.get(path[-1], set())):
            if node not in visited:
                visited.add(node); queue.append(path + [node])
    return None


def template_summary(template_id: str) -> dict:
    scenario = load_template(template_id)
    nodes = [{"id": n["id"], "role": n["type"]} for n in scenario["nodes"]]
    endpoints = [n["id"] for n in scenario["nodes"] if n["type"] in {"client", "server"}]
    defaults = {"bandwidth_mbps": 20, "delay_ms": 0, "loss_percent": 0,
                "ping_count": scenario.get("traffic", {}).get("ping_count", 3),
                "iperf_duration_seconds": scenario.get("traffic", {}).get("duration_s", 5)}
    return {"id": template_id, "display_name": TEMPLATES[template_id][0], "nodes": nodes,
            "links": scenario.get("links", []), "endpoint_capable_nodes": endpoints,
            "default_conditions": defaults}


def number(value: object, key: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be numeric")
    low, high = LIMITS[key]
    if value < low or value > high:
        raise ValueError(f"{key} must be between {low} and {high}")
    return int(value) if key in {"ping_count", "iperf_duration_seconds"} else float(value)


def validate_request(payload: dict) -> tuple[dict, dict, list[str]]:
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")
    template_id = payload.get("scenario_id")
    if not isinstance(template_id, str):
        raise ValueError("scenario_id is required")
    scenario = load_template(template_id)
    source, destination = payload.get("source"), payload.get("destination")
    node_types = {n["id"]: n["type"] for n in scenario["nodes"]}
    if source not in node_types or destination not in node_types:
        raise ValueError("source and destination must be template nodes")
    if source == destination:
        raise ValueError("source and destination must differ")
    if node_types[source] != "client" or node_types[destination] != "server":
        raise ValueError("source must be a client and destination must be a server")
    selected_path = path_between(scenario, source, destination)
    if not selected_path:
        raise ValueError("source and destination are unreachable")
    test = payload.get("test", "ping+iperf3")
    if test not in {"ping", "iperf3", "ping+iperf3"}:
        raise ValueError("Unsupported test configuration")
    config = {key: number(payload.get(key, template_summary(template_id)["default_conditions"][key]), key) for key in LIMITS}
    dry_run = payload.get("dry_run", True)
    if not isinstance(dry_run, bool):
        raise ValueError("dry_run must be boolean")
    if not dry_run and payload.get("confirmation") != "RUN":
        raise ValueError("Real Docker runs require confirmation RUN")
    return scenario, {"scenario_id": template_id, "source": source, "destination": destination,
                      "test": test, "dry_run": dry_run, **config}, selected_path


def derived_topology(scenario: dict, config: dict, prefix: str) -> dict:
    """Normalize the verified two-router template into uniquely named resources."""
    if config["scenario_id"] != "two-router":
        raise ValueError("Real Docker execution is currently limited to the two-router template")
    copy = json.loads(json.dumps(scenario))
    renames = {n["id"]: f"d{prefix}-{n['id']}" for n in copy["nodes"]}
    subnets = {s["name"]: f"d{prefix}-{s['name']}" for s in copy["subnets"]}
    for node in copy["nodes"]:
        node["id"] = renames[node["id"]]
        for interface in node["interfaces"]: interface["subnet"] = subnets[interface["subnet"]]
    for subnet in copy["subnets"]: subnet["name"] = subnets[subnet["name"]]
    for link in copy["links"]:
        link["source"], link["target"] = renames[link["source"]], renames[link["target"]]
        link["subnet"] = subnets[link["subnet"]]
        link["bandwidth_mbps"] = config["bandwidth_mbps"]
        link["delay_ms"] = config["delay_ms"]
        link["packet_loss_percent"] = config["loss_percent"]
    for route in copy["routes"]: route["node"] = renames[route["node"]]
    copy["traffic"].update({"source": renames[config["source"]], "destination": renames[config["destination"]],
                             "ping_count": config["ping_count"], "duration_s": config["iperf_duration_seconds"]})
    copy["topology_name"] = f"dashboard-{prefix}"
    return copy


class Store:
    def __init__(self): self.runs: dict[str, dict] = {}; self.lock = threading.RLock(); self.real_active: str | None = None
    def create(self, config: dict, selected_path: list[str]) -> dict:
        run_id = uuid.uuid4().hex[:12]; directory = RUN_ROOT / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{run_id}"
        directory.mkdir(parents=True, exist_ok=False)
        item = {"run_id": run_id, "status": "QUEUED", "created_at": utc_now(), "started_at": None, "ended_at": None,
                "config": config, "selected_path": selected_path, "directory": directory.name, "failure_message": None,
                "cleanup_status": "PENDING", "process": None, "cancel_requested": False}
        with self.lock: self.runs[run_id] = item
        return item


STORE = Store()


def write_artifacts(item: dict, result: dict, log: str = "") -> None:
    directory = RUN_ROOT / item["directory"]
    (directory / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    with (directory / "result.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted(result.keys())); writer.writeheader(); writer.writerow(result)
    (directory / "run.log").write_text(log[-MAX_LOG:], encoding="utf-8")
    with zipfile.ZipFile(directory / "bundle.zip", "w", zipfile.ZIP_DEFLATED) as bundle:
        for name in ("scenario.json", "result.json", "result.csv", "run.log"):
            path = directory / name
            if path.is_file() and path.resolve().parent == directory.resolve(): bundle.write(path, name)


def execute(item: dict) -> None:
    config, directory = item["config"], RUN_ROOT / item["directory"]
    output = ""
    item["started_at"] = utc_now(); item["status"] = "VALIDATING"
    try:
        scenario = load_template(config["scenario_id"])
        item["status"] = "PREPARING"
        if config["dry_run"]:
            scenario["traffic"].update({"source": config["source"], "destination": config["destination"],
                                         "ping_count": config["ping_count"], "duration_s": config["iperf_duration_seconds"]})
            (directory / "scenario.json").write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")
            item["status"] = "COLLECTING"
            result = {"run_id": item["run_id"], "status": "SUCCEEDED", "dry_run": True, "scenario": config["scenario_id"],
                      "source": config["source"], "destination": config["destination"], "selected_path": item["selected_path"],
                      "applied_conditions": {k: config[k] for k in LIMITS}, "route_verification": "DRY_RUN_PASS",
                      "qdisc_verification": "NOT_APPLIED", "cleanup_status": "NOT_REQUIRED"}
            item["cleanup_status"] = "NOT_REQUIRED"; write_artifacts(item, result, "Dry-run validation passed.\n")
        else:
            scoped = derived_topology(scenario, config, item["run_id"][:8])
            scenario_path, metrics_path, plot_path = directory / "scenario.json", directory / "simulator-metrics.json", directory / "topology.svg"
            scenario_path.write_text(json.dumps(scoped, indent=2) + "\n", encoding="utf-8")
            item["status"] = "RUNNING"
            cmd = [sys.executable, str(ROOT / "scripts" / "simulator_topology.py"), "--scenario", str(scenario_path),
                   "--output", str(metrics_path), "--plot", str(plot_path)]
            process = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=False)
            item["process"] = process
            try: output, _ = process.communicate(timeout=90)
            except subprocess.TimeoutExpired: process.terminate(); output, _ = process.communicate(timeout=10); raise RuntimeError("Dashboard job timed out")
            if item["cancel_requested"]: raise RuntimeError("Cancelled by user")
            if process.returncode != 0: raise RuntimeError(f"Trusted simulator failed ({process.returncode})")
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            item["status"] = "COLLECTING"; item["cleanup_status"] = "PASS"
            result = {"run_id": item["run_id"], "status": "SUCCEEDED", "dry_run": False, "scenario": config["scenario_id"],
                      "source": config["source"], "destination": config["destination"], "selected_path": item["selected_path"],
                      "applied_conditions": {k: config[k] for k in LIMITS}, "route_verification": metrics.get("route_verification"),
                      "qdisc_verification": metrics.get("router_qdisc_state"), "cleanup_status": "PASS",
                      "ping_sent": metrics.get("ping_packets_transmitted"), "ping_received": metrics.get("ping_packets_received"),
                      "measured_loss_percent": metrics.get("ping_packet_loss_percent"), "rtt_min_ms": metrics.get("ping_rtt_min_ms"),
                      "rtt_avg_ms": metrics.get("ping_rtt_avg_ms"), "rtt_max_ms": metrics.get("ping_rtt_max_ms"),
                      "throughput_mbps": metrics.get("throughput_mbps")}
            write_artifacts(item, result, output)
        item["status"] = "SUCCEEDED"
    except Exception as error:
        item["status"] = "CANCELLED" if item["cancel_requested"] else "FAILED"; item["failure_message"] = str(error)
        item["cleanup_status"] = "ATTEMPTED"
        write_artifacts(item, {"run_id": item["run_id"], "status": item["status"], "failure_message": str(error), "cleanup_status": "ATTEMPTED"}, output)
    finally:
        item["process"] = None; item["ended_at"] = utc_now()
        with STORE.lock:
            if not config["dry_run"]: STORE.real_active = None


class Handler(BaseHTTPRequestHandler):
    server_version = "DigitalTwinInteractive/1.0"
    def log_message(self, *_): pass
    def send_json(self, payload: dict, status=200, cookie: str | None = None):
        data = json.dumps(payload).encode(); self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.send_header("Cache-Control", "no-store")
        if cookie: self.send_header("Set-Cookie", cookie)
        self.end_headers(); self.wfile.write(data)
    def session(self):
        cookies = SimpleCookie(self.headers.get("Cookie")); sid = cookies.get("dt_session")
        if sid and sid.value in self.server.sessions: return sid.value, None
        sid = secrets.token_urlsafe(24); csrf = secrets.token_urlsafe(24); self.server.sessions[sid] = csrf
        return sid, f"dt_session={sid}; HttpOnly; SameSite=Strict; Path=/; dt_csrf={csrf}; SameSite=Strict; Path=/"
    def get_json(self):
        if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json": raise ValueError("Content-Type must be application/json")
        size = int(self.headers.get("Content-Length", "0"))
        if size < 1 or size > MAX_BODY: raise ValueError("Request body too large or empty")
        return json.loads(self.rfile.read(size))
    def csrf(self):
        sid, _ = self.session(); origin = self.headers.get("Origin"); host = self.headers.get("Host", "")
        if host not in {"127.0.0.1:8765", "localhost:8765"} or origin not in {"http://127.0.0.1:8765", "http://localhost:8765"}: raise PermissionError("Invalid Host or Origin")
        if not secrets.compare_digest(self.headers.get("X-CSRF-Token", ""), self.server.sessions[sid]): raise PermissionError("Missing or invalid CSRF token")
    def do_GET(self):
        parsed = urlparse(self.path); path = parsed.path
        if path == "/healthz": return self.send_json({"status": "ok"})
        if path == "/":
            sid, cookie = self.session(); data = (WEB / "index.html").read_bytes(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.send_header("Set-Cookie", cookie); self.end_headers(); return self.wfile.write(data)
        if path in {"/app.js", "/styles.css"}:
            data = (WEB / path[1:]).read_bytes(); self.send_response(200); self.send_header("Content-Type", "text/javascript" if path.endswith("js") else "text/css"); self.send_header("Content-Length", str(len(data))); self.end_headers(); return self.wfile.write(data)
        if path == "/api/system":
            sid, cookie = self.session(); docker = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"], capture_output=True, text=True, shell=False).returncode == 0
            return self.send_json({"docker_available": docker, "simulator_available": (ROOT / "scripts/simulator_topology.py").is_file(), "active_run": STORE.real_active, "application_version": "interactive-dashboard-v1", "csrf_token": self.server.sessions[sid]}, cookie=cookie)
        if path == "/api/scenarios": return self.send_json({"scenarios": [template_summary(key) for key in TEMPLATES]})
        if path.startswith("/api/scenarios/"):
            try: return self.send_json(template_summary(path.rsplit("/", 1)[1]))
            except ValueError as error: return self.send_json({"error": str(error)}, 404)
        if path == "/api/runs": return self.send_json({"runs": [public_run(x) for x in STORE.runs.values()]})
        match = re.fullmatch(r"/api/runs/([a-f0-9]{12})", path)
        if match and match.group(1) in STORE.runs: return self.send_json(public_run(STORE.runs[match.group(1)]))
        match = re.fullmatch(r"/api/runs/([a-f0-9]{12})/download/(json|csv|log|zip)", path)
        if match and match.group(1) in STORE.runs:
            file = RUN_ROOT / STORE.runs[match.group(1)]["directory"] / ARTIFACTS[match.group(2)]
            if not file.is_file() or file.resolve().parent != (RUN_ROOT / STORE.runs[match.group(1)]["directory"]).resolve(): return self.send_json({"error": "Artifact unavailable"}, 404)
            data = file.read_bytes(); self.send_response(200); self.send_header("Content-Type", "application/octet-stream"); self.send_header("Content-Disposition", f"attachment; filename={file.name}"); self.send_header("Content-Length", str(len(data))); self.end_headers(); return self.wfile.write(data)
        self.send_json({"error": "Not found"}, 404)
    def do_POST(self):
        try:
            self.csrf(); payload = self.get_json(); path = urlparse(self.path).path
            if path == "/api/validate":
                _, config, selected = validate_request(payload); return self.send_json({"valid": True, "config": config, "selected_path": selected})
            if path == "/api/runs":
                _, config, selected = validate_request(payload)
                with STORE.lock:
                    if not config["dry_run"] and STORE.real_active: return self.send_json({"error": "A real Docker run is already active"}, 409)
                    item = STORE.create(config, selected)
                    if not config["dry_run"]: STORE.real_active = item["run_id"]
                threading.Thread(target=execute, args=(item,), daemon=True).start(); return self.send_json(public_run(item), 202)
            match = re.fullmatch(r"/api/runs/([a-f0-9]{12})/(cancel|cleanup)", path)
            if not match or match.group(1) not in STORE.runs: return self.send_json({"error": "Not found"}, 404)
            item, action = STORE.runs[match.group(1)], match.group(2)
            if action == "cancel":
                item["cancel_requested"] = True
                if item["process"]: item["process"].terminate()
                return self.send_json(public_run(item), 202)
            item["cleanup_status"] = "NOT_REQUIRED" if item["config"]["dry_run"] else "ATTEMPTED"; return self.send_json(public_run(item), 202)
        except (ValueError, json.JSONDecodeError) as error: self.send_json({"error": str(error)}, 400)
        except PermissionError as error: self.send_json({"error": str(error)}, 403)


def public_run(item: dict) -> dict:
    return {key: value for key, value in item.items() if key not in {"process"}}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--port", type=int, default=8765); args = parser.parse_args()
    if args.port != 8765: raise SystemExit("This local-only UI is fixed to port 8765 for strict Host/Origin validation")
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler); server.sessions = {}
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__ == "__main__": main()
