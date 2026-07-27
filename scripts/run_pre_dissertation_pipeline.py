#!/usr/bin/env python3
"""Resumable, foreground pre-dissertation pipeline checkpoint manager."""
import argparse, json, os, tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGES = ["cleanup", "unit_tests", "germany50_selected_routes", "rl_evaluation", "dashboard_smoke", "final_matrix", "figures", "final_docs", "verification", "seal"]

def atomic_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".checkpoint-", text=True)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2); handle.write("\n")
    os.replace(name, path)

def main():
    p=argparse.ArgumentParser(); p.add_argument("--resume", action="store_true"); p.add_argument("--checkpoint", type=Path, required=True); a=p.parse_args()
    state=json.loads(a.checkpoint.read_text()) if a.resume and a.checkpoint.exists() else {"current_stage":"","completed_stages":[],"failed_stages":[],"in_progress_stage":None,"last_successful_action":"","next_action":"","artifacts":{},"attempts":{},"updated_at":""}
    state["next_action"]="Implement selected/full batched Germany50 route provisioning in scripts/run_germany50_full_evaluation.py"
    state["updated_at"]=datetime.now(timezone.utc).isoformat()
    atomic_write(a.checkpoint, state)
    print(json.dumps(state, indent=2))
if __name__ == "__main__": main()
