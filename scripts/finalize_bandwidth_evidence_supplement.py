"""Assemble the immutable supplement index from preserved replication attempts."""

from __future__ import annotations

import csv
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "runs" / "bandwidth-evidence-supplement"
T_CRITICAL_95_N5 = 2.7764451051977987


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: object):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    selected = []
    for path in sorted(OUT.rglob("metrics.json")):
        row = read_json(path)
        relative = str(path.relative_to(OUT))
        row["evidence_path"] = relative
        row["cohort"] = "preflight_docker_permission_failure" if "/" not in relative else "additional_recorded_attempt"
        if relative.startswith("replication-attempt-02/50mbps-") or relative.startswith("replication-attempt-02/100mbps-") or relative.startswith("replication-attempt-04-100mbps-retry/"):
            row["cohort"] = "primary_replication_with_preserved_retry"
        selected.append(row)
    groups = {}
    for bandwidth in (50, 100):
        rows = [row for row in selected if row["configured_bandwidth_mbps"] == bandwidth and row["cohort"] == "primary_replication_with_preserved_retry"]
        values = [row["throughput_mbps"] for row in rows if row["status"] == "success"]
        mean = statistics.mean(values)
        deviation = statistics.stdev(values)
        groups[str(bandwidth)] = {
            "configured_bandwidth_mbps": bandwidth,
            "valid_runs": len(values),
            "attempted_runs": len(rows),
            "failed_runs": len(rows) - len(values),
            "throughput_mean_mbps": mean,
            "throughput_standard_deviation_mbps": deviation,
            "throughput_ci95_half_width_mbps": T_CRITICAL_95_N5 * deviation / math.sqrt(len(values)),
            "throughput_min_mbps": min(values),
            "throughput_max_mbps": max(values),
            "mean_ratio_to_configured": mean / bandwidth,
        }
    write_json(OUT / "summary.json", {
        "evidence_mode": "SUPPLEMENTARY_REPLICATION",
        "selection_rule": "The primary cohort is the five-run 50 Mbps batch from replication-attempt-02 and its 100 Mbps batch plus the explicitly preserved run-06 retry after run-05 failed. This yields five valid 100 Mbps measurements from six attempted runs. All earlier permission failures and additional 100 Mbps attempts are retained in per-run-results.csv and are not mixed into the planned cohort statistics.",
        "groups": groups,
        "failed_retry_evidence": [row for row in selected if row["status"] != "success"],
        "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    })
    fields = ["run_id", "status", "configured_bandwidth_mbps", "throughput_mbps", "ratio_to_configured", "started_at", "ended_at", "commit", "environment_file", "cleanup_status", "error", "cohort", "evidence_path"]
    with (OUT / "per-run-results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(selected)
    inventory = {
        "evidence_mode": "SUPPLEMENTARY_REPLICATION",
        "original_evidence_search": {
            "status": "RAW_EVIDENCE_NOT_RECOVERED",
            "searched_scopes": ["runs/", "results/", "outputs/", ".local-evidence/", "docs/", "figures/", "Git reachable history"],
            "search_terms": ["50 Mbps", "100 Mbps", "47.9 Mbps", "95.7 Mbps", "iperf3", "batch manifest"],
            "historical_summary_only": [
                {"commit": "11fc2c81f724ecfeb73085cb05f5ec5a63b9fe21", "path": "runs/run_002/metrics.json", "configured_bandwidth_mbps": 50, "throughput_mbps": 47.9},
                {"commit": "11fc2c81f724ecfeb73085cb05f5ec5a63b9fe21", "path": "runs/run_003/metrics.json", "configured_bandwidth_mbps": 100, "throughput_mbps": 95.7},
            ],
            "conclusion": "The historical metrics are single-value summaries only; no parseable raw iperf3 output, per-run logs, or batch manifest was recovered. They are not treated as recovered original evidence.",
        },
        "supplementary_replication": {"preserved_records": len(selected), "raw_evidence_directory": "runs/bandwidth-evidence-supplement", "primary_cohort": "replication-attempt-02 plus replication-attempt-04 run-06 retry", "attempt_directories": ["replication-attempt-02", "replication-attempt-03-100mbps", "replication-attempt-04-100mbps-retry"], "failed_initial_sandbox_attempt": "Top-level run directories preserve ten Docker-socket-permission failures before escalated Docker execution. The primary Docker attempt contained one 100 Mbps iperf3 failure; an explicit retry was run. The additional 100 Mbps attempt made during diagnosis is also retained, but not mixed into the planned cohort."},
    }
    write_json(OUT / "evidence-inventory.json", inventory)
    report = ROOT / "docs" / "final" / "bandwidth-50-100-evidence-supplement.md"
    report.write_text("""# 50 Mbps and 100 Mbps bandwidth evidence supplement

Status: `SUPPLEMENTARY_REPLICATION`.

The pre-dissertation audit found only historical single-value summaries (47.9 Mbps at 50 Mbps and 95.7 Mbps at 100 Mbps) in commit `11fc2c81f724ecfeb73085cb05f5ec5a63b9fe21`; it did not retain raw iperf3 output, per-run records, or a batch manifest. Consequently, these are not reported as `RECOVERED_ORIGINAL_EVIDENCE`.

The retained supplement uses the original direct two-node reverse TCP iperf3 methodology (five seconds, `my-iperf-tc`, server-side TBF) on the stated baseline commit. It is new evidence and does not alter formal results. The 50 Mbps cohort completed five successful runs. The primary 100 Mbps batch contains one preserved iperf3 failure; the explicit run-06 retry supplied the fifth valid measurement.

| configured bandwidth | valid / attempted | mean Mbps | SD Mbps | 95% CI half-width Mbps | min–max Mbps | mean/configured |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
""" + "\n".join(f"| {g['configured_bandwidth_mbps']} | {g['valid_runs']} / {g['attempted_runs']} | {g['throughput_mean_mbps']:.3f} | {g['throughput_standard_deviation_mbps']:.3f} | {g['throughput_ci95_half_width_mbps']:.3f} | {g['throughput_min_mbps']:.3f}–{g['throughput_max_mbps']:.3f} | {g['mean_ratio_to_configured']:.3f} |" for g in groups.values()) + """

All successful and failed records appear in `runs/bandwidth-evidence-supplement/per-run-results.csv`, including ten preliminary Docker-permission failures and an additional 100 Mbps diagnostic attempt. They are retained for provenance but are not mixed into the planned cohort. Raw iperf3 output and command stdout/stderr are retained beneath the cited attempt directories.
""", encoding="utf-8")


if __name__ == "__main__":
    main()
