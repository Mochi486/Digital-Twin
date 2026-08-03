"""Create an isolated, fully preserved replication of the original bandwidth sweep.

The original ``run_batch.py`` used ``simulator_real.py`` with a two-node,
five-second reverse TCP iperf3 flow.  This runner preserves that experimental
method while retaining the command evidence that the original batch did not.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "runs" / "bandwidth-evidence-supplement"
IMAGE = "my-iperf-tc"
NETWORK = "bandwidth_evidence_supplement_net"
SERVER = "bandwidth_evidence_supplement_server"
CLIENT = "bandwidth_evidence_supplement_client"
T_CRITICAL_95_N5 = 2.7764451051977987


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def command_record(command: list[str]) -> dict:
    result = subprocess.run(command, capture_output=True, text=True)
    return {"command": command, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def remove_container(name: str, records: list[dict]) -> None:
    records.append(command_record(["docker", "rm", "-f", name]))


def run_one(output: Path, bandwidth: int, index: int, commit: str, environment: dict) -> dict:
    run_id = f"{bandwidth}mbps-run-{index:02d}"
    run_dir = output / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    scenario = {
        "nodes": [{"id": "client1", "type": "client"}, {"id": "server1", "type": "server"}],
        "links": [{"source": "server1", "target": "client1", "bandwidth_mbps": bandwidth, "delay_ms": 0}],
        "traffic": {"protocol": "tcp", "duration_s": 5, "reverse": True},
    }
    started = utc_now()
    records: list[dict] = []
    cleanup_records: list[dict] = []
    write_json(run_dir / "configuration.json", {"scenario": scenario, "source_method": "simulator_real.py-compatible direct iperf3 reverse TCP flow", "commit": commit, "image": IMAGE, "network": NETWORK, "started_at": started})
    status = "failure"
    throughput = None
    error = ""
    try:
        records.append(command_record(["docker", "network", "inspect", NETWORK]))
        if records[-1]["returncode"] != 0:
            records.append(command_record(["docker", "network", "create", NETWORK]))
            if records[-1]["returncode"] != 0:
                raise RuntimeError(records[-1]["stderr"] or "unable to create Docker network")
        remove_container(SERVER, records)
        records.append(command_record(["docker", "run", "-d", "--name", SERVER, "--network", NETWORK, "--cap-add=NET_ADMIN", IMAGE, "iperf3", "-s"]))
        if records[-1]["returncode"] != 0:
            raise RuntimeError(records[-1]["stderr"] or "unable to start server")
        records.append(command_record(["docker", "exec", SERVER, "tc", "qdisc", "replace", "dev", "eth0", "root", "tbf", "rate", f"{bandwidth}mbit", "burst", "32kbit", "latency", "400ms"]))
        if records[-1]["returncode"] != 0:
            raise RuntimeError(records[-1]["stderr"] or "unable to apply tbf qdisc")
        client = command_record(["docker", "run", "--rm", "--name", CLIENT, "--network", NETWORK, IMAGE, "iperf3", "-c", SERVER, "-R", "-t", "5"])
        records.append(client)
        (run_dir / "raw-iperf3-output.txt").write_text(client["stdout"], encoding="utf-8")
        if client["returncode"] != 0:
            raise RuntimeError(client["stderr"] or "iperf3 client failed")
        for line in reversed(client["stdout"].splitlines()):
            if "receiver" in line:
                fields = line.split()
                for position, value in enumerate(fields):
                    if value.endswith("bits/sec") and position:
                        number, unit = fields[position - 1], value[0]
                        throughput = float(number) * {"K": 1e-3, "M": 1, "G": 1e3}[unit]
                        break
            if throughput is not None:
                break
        if throughput is None:
            raise RuntimeError("could not parse receiver throughput from iperf3 output")
        status = "success"
    except Exception as exc:  # Persist all failures as experimental evidence.
        error = str(exc)
    finally:
        remove_container(CLIENT, cleanup_records)
        remove_container(SERVER, cleanup_records)
    ended = utc_now()
    cleanup_success = all(record["returncode"] == 0 or "No such container" in record["stderr"] for record in cleanup_records)
    (run_dir / "stdout-stderr.json").write_text(json.dumps({"commands": records, "cleanup_commands": cleanup_records}, indent=2) + "\n", encoding="utf-8")
    metrics = {"run_id": run_id, "status": status, "configured_bandwidth_mbps": bandwidth, "throughput_mbps": throughput, "ratio_to_configured": throughput / bandwidth if throughput is not None else None, "started_at": started, "ended_at": ended, "commit": commit, "environment_file": "../environment.json", "cleanup_status": "success" if cleanup_success else "failure", "error": error}
    write_json(run_dir / "metrics.json", metrics)
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--bandwidth", type=int, action="append", choices=(50, 100), help="Repeat to run more than one configured bandwidth.")
    parser.add_argument("--retry", action="store_true", help="Permit a single replacement run after a preserved failure.")
    parser.add_argument("--start-index", type=int, default=1)
    args = parser.parse_args()
    if args.runs != 5 and not (args.retry and args.runs == 1):
        raise ValueError("This evidence protocol requires exactly five runs per configuration")
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing evidence directory: {output}")
    output.mkdir(parents=True)
    bandwidths = args.bandwidth or [50, 100]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True).strip()
    environment = {"captured_at": utc_now(), "commit": commit, "python": sys.version, "docker_version": command_record(["docker", "version", "--format", "{{.Server.Version}}"]), "image": command_record(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}} {{.Created}}"])}
    write_json(output / "environment.json", environment)
    write_json(output / "batch-manifest.json", {"evidence_mode": "SUPPLEMENTARY_REPLICATION", "source_baseline_commit": "f18e13ea28415c22425ca738c2ce967438277cf8", "execution_commit": commit, "protocol": "two-node direct simulator_real.py-compatible reverse TCP iperf3, 5 seconds, TBF on server eth0", "planned_runs": {str(bandwidth): args.runs for bandwidth in bandwidths}, "retry": args.retry, "started_at": utc_now()})
    rows = [run_one(output, bandwidth, index, commit, environment) for bandwidth in bandwidths for index in range(args.start_index, args.start_index + args.runs)]
    with (output / "per-run-results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["run_id", "status", "configured_bandwidth_mbps", "throughput_mbps", "ratio_to_configured", "started_at", "ended_at", "commit", "environment_file", "cleanup_status", "error"])
        writer.writeheader()
        writer.writerows(rows)
    groups = {}
    for bandwidth in bandwidths:
        values = [row["throughput_mbps"] for row in rows if row["configured_bandwidth_mbps"] == bandwidth and row["status"] == "success"]
        mean = statistics.mean(values) if values else None
        standard_deviation = statistics.stdev(values) if len(values) >= 2 else None
        ci95 = T_CRITICAL_95_N5 * standard_deviation / math.sqrt(len(values)) if len(values) == 5 else None
        groups[str(bandwidth)] = {"configured_bandwidth_mbps": bandwidth, "valid_runs": len(values), "total_runs": args.runs, "throughput_mean_mbps": mean, "throughput_standard_deviation_mbps": standard_deviation, "throughput_ci95_half_width_mbps": ci95, "throughput_min_mbps": min(values) if values else None, "throughput_max_mbps": max(values) if values else None, "mean_ratio_to_configured": mean / bandwidth if mean is not None else None}
    write_json(output / "summary.json", {"evidence_mode": "SUPPLEMENTARY_REPLICATION", "groups": groups, "failed_runs": [row for row in rows if row["status"] != "success"], "completed_at": utc_now()})
    cleanup = command_record(["docker", "network", "rm", NETWORK])
    write_json(output / "cleanup.json", {"network_cleanup": cleanup, "status": "success" if cleanup["returncode"] == 0 else "failure"})
    return 0 if all(row["status"] == "success" for row in rows) and cleanup["returncode"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
