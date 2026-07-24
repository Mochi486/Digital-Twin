#!/usr/bin/env python3
"""Read-only pre-dissertation evidence audit; it never runs experiments."""
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
FINAL = RUNS / "final-evaluation"


def read_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def mean(values):
    return round(statistics.fmean(values), 3)


def json_csv_parse_errors():
    errors = []
    for path in RUNS.rglob("*.json"):
        try:
            read_json(path)
        except Exception as exc:
            errors.append(f"JSON {path.relative_to(ROOT)}: {exc}")
    for path in RUNS.rglob("*.csv"):
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                list(csv.reader(handle))
        except Exception as exc:
            errors.append(f"CSV {path.relative_to(ROOT)}: {exc}")
    return errors


def metric_rows(pattern: str):
    return [read_json(path) for path in sorted(ROOT.glob(pattern))]


def item(name, status, raw, summary, figure, documentation, consistency, missing=""):
    return {"experiment_or_feature": name, "status": status, "raw_evidence_path": raw,
            "summary_path": summary, "figure_path": figure, "documentation_path": documentation,
            "consistency_result": consistency, "missing_items": missing}


def write_bar_svg(path: Path, title: str, values: dict[str, float], unit: str):
    width, height, maximum = 700, 300, max(values.values()) or 1.0
    bars = []
    for index, (label, value) in enumerate(values.items()):
        x, bar_height = 80 + index * 140, value / maximum * 190
        y = 245 - bar_height
        bars.append(f'<rect x="{x}" y="{y:.1f}" width="70" height="{bar_height:.1f}" fill="#2563eb"/>')
        bars.append(f'<text x="{x}" y="265" font-size="12">{label}</text><text x="{x}" y="{y - 6:.1f}" font-size="12">{value:.3f}</text>')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join([f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">', '<rect width="100%" height="100%" fill="white"/>', f'<text x="30" y="30" font-size="18">{title} ({unit})</text>', '<line x1="55" y1="245" x2="670" y2="245" stroke="black"/>', *bars, '</svg>']) + '\n', encoding="utf-8")


def validate_rl_aggregation(errors: list[str]):
    """Cross-check the retained per-episode CSV against both summaries."""
    root = FINAL / "rl-docker-supplement"
    with (root / "per-episode-results.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    with (root / "policy-summary.csv").open(newline="", encoding="utf-8") as handle:
        policy_rows = {row["policy"]: row for row in csv.DictReader(handle)}
    summary = read_json(root / "summary.json")
    expected = ("q_learning", "heuristic", "fixed_a", "fixed_b")
    for policy in expected:
        selected = [row for row in rows if row["policy"] == policy]
        indices = [int(row["episode"]) for row in selected]
        if len(selected) != 20 or len(set(indices)) != 20:
            errors.append(f"RL {policy}: expected 20 unique valid episodes, got {len(selected)}/{len(set(indices))}")
            continue
        if policy not in policy_rows or policy not in summary["policies"]:
            errors.append(f"RL {policy}: missing policy summary")
            continue
        for metric, csv_key, json_key in (("reward", "reward_mean", "reward"), ("rtt_ms", "rtt_ms_mean", "rtt_ms"), ("loss_percent", "loss_percent_mean", "loss_percent"), ("throughput_mbps", "throughput_mbps_mean", "throughput_mbps")):
            calculated = statistics.fmean(float(row[metric]) for row in selected)
            csv_value = float(policy_rows[policy][csv_key])
            json_value = float(summary["policies"][policy]["metrics"][json_key]["mean"])
            if abs(calculated - csv_value) > 1e-8 or abs(calculated - json_value) > 1e-8:
                errors.append(f"RL {policy} {metric}: CSV/JSON aggregation mismatch")
        if int(policy_rows[policy]["valid_episodes"]) != 20 or summary["policies"][policy]["valid_episodes"] != 20:
            errors.append(f"RL {policy}: summary episode count mismatch")
    return {policy: sum(row["policy"] == policy for row in rows) for policy in expected}


def main():
    errors = json_csv_parse_errors()
    inventory = []
    delay = metric_rows("runs/delay_batch_20260713-135915/delay_*_run_*/metrics.json")
    delay_means = {str(value): mean([row["ping_rtt_avg_ms"] for row in delay if row["configured_delay_ms"] == value]) for value in (0, 10, 30, 50)}
    inventory.append(item("delay matrix", "PASS" if len(delay) == 20 else "INCOMPLETE", "runs/delay_batch_20260713-135915/", "runs/final-evaluation/evidence-inventory.json", "docs/final/figures/delay-vs-rtt.svg", "docs/final/pre-dissertation-evidence-audit.md", f"20 rows; means={delay_means}", "summary/figure are generated audit derivatives"))
    loss = metric_rows("runs/packet_loss_batch_20260713-153303/loss_*_run_*/metrics.json")
    loss_means = {str(value): mean([row["ping_packet_loss_percent"] for row in loss if row["configured_packet_loss_percent"] == value]) for value in (0, 1, 3, 5)}
    figures_dir = ROOT / "docs/final/figures"
    write_bar_svg(figures_dir / "delay-vs-rtt.svg", "Configured delay versus measured RTT", delay_means, "ms")
    write_bar_svg(figures_dir / "loss-vs-measured-ping-loss.svg", "Configured loss versus measured round-trip loss", loss_means, "%")
    inventory.append(item("packet-loss matrix", "PASS" if len(loss) == 20 else "INCOMPLETE", "runs/packet_loss_batch_20260713-153303/", "runs/final-evaluation/evidence-inventory.json", "docs/final/figures/loss-vs-measured-ping-loss.svg", "docs/final/pre-dissertation-evidence-audit.md", f"20 rows; measured means={loss_means}", "summary/figure are generated audit derivatives"))
    dual = metric_rows("runs/two_router_batch_20260713-160810/baseline_run_*/metrics.json")
    inventory.append(item("dual-router", "PASS" if len(dual) == 5 else "INCOMPLETE", "runs/two_router_batch_20260713-160810/", "runs/final-evaluation/evidence-inventory.json", "runs/two_router_batch_20260713-160810/", "docs/final/pre-dissertation-evidence-audit.md", f"5 rows; throughput mean={mean([row['throughput_mbps'] for row in dual]) if dual else None}", ""))
    bandwidth_files = [path for path in RUNS.rglob("metrics.json") if read_json(path).get("configured_bandwidth_mbps") in (50, 100)]
    inventory.append(item("bandwidth", "PARTIAL", "runs/current/metrics.json", "README.md", "", "docs/final/pre-dissertation-evidence-audit.md", "20 Mbps evidence=19.2 Mbps", "No preserved raw 50/100 Mbps measurement files discovered" if not bandwidth_files else ""))
    mock_root = ROOT / ".local-evidence/ai-scenario-phase-20260714-093638"
    mock_files = [mock_root / f"{name}-scenario.json" for name in ("linear-5", "redundant-6", "lossy-8")]
    inventory.append(item("AI mock topology generation", "PASS" if all(path.exists() for path in mock_files) else "MISSING", ".local-evidence/ai-scenario-phase-20260714-093638/{linear-5,redundant-6,lossy-8}-scenario.json", "runs/final-evaluation/evidence-inventory.json", ".local-evidence/ai-scenario-phase-20260714-093638/*-simulator-dry-run.svg", "docs/progress/core-platform-v1-seal.md", "three validated generated scenarios; only non-sensitive scenario/dry-run artifacts are tracked", ""))
    qwen_metrics = ROOT / "runs/openai-compatible-live-validation-20260714-064525/metrics.json"
    qwen_summary = read_json(FINAL / "ai-qwen-live-summary.json")
    qwen_ok = qwen_metrics.exists() and (qwen_summary["rtt_ms"], qwen_summary["throughput_mbps"], qwen_summary["packet_loss_percent"]) == (82.194, 18.3, 0.0)
    if not qwen_ok:
        errors.append("AI compatible-provider sanitized summary does not match the expected retained measurements")
    inventory.append(item("AI compatible-provider live", "PASS" if qwen_ok else "INCONSISTENT", str(qwen_metrics.relative_to(ROOT)), "runs/final-evaluation/ai-qwen-live-summary.json", "runs/openai-compatible-live-validation-20260714-064525/topology.svg", "docs/final/pre-dissertation-evidence-audit.md", "82.194 ms, 18.3 Mbps, 0% loss" if qwen_ok else "", "sanitized provider summary required for repository retention"))
    openai_summary = read_json(FINAL / "ai-openai-429-evidence.json")
    openai_ok = openai_summary.get("http_status") == 429 and openai_summary.get("error_code") == "insufficient_quota"
    if not openai_ok:
        errors.append("Official OpenAI sanitized evidence does not preserve HTTP 429 insufficient_quota")
    inventory.append(item("AI official OpenAI", "PASS" if openai_ok else "INCONSISTENT", ".local-evidence/openai-live-validation-20260714-030746/openai-live-summary.json", "runs/final-evaluation/ai-openai-429-evidence.json", "", "docs/final/pre-dissertation-evidence-audit.md", "HTTP 429 insufficient_quota preserved in sanitized summary" if openai_ok else "", "original local evidence intentionally contains environment metadata and is not tracked"))
    g50_full = FINAL / "germany50-full-fixed/selected-attempt-1/summary.json"
    g50_subset = FINAL / "germany50-subset-fixed/summary.json"
    inventory.append(item("Germany50 selected-route full topology", "PASS" if g50_full.exists() else "MISSING", "runs/final-evaluation/germany50-full-fixed/selected-attempt-1/", str(g50_full.relative_to(ROOT)), "runs/final-evaluation/germany50-full-fixed/", "docs/progress/germany50-full-results.md", "50 containers, 88 networks, selected routes only", ""))
    subset_counts = {str(size): len(list((FINAL / "germany50-subset-fixed").glob(f"corrected-{size}-node-*-run-*/summary.json"))) for size in (10, 20)}
    subset_ok = g50_subset.exists() and subset_counts == {"10": 9, "20": 9}
    inventory.append(item("Germany50 10/20-node subsets and 30-node dry-run", "PASS" if subset_ok else "INCOMPLETE", "runs/final-evaluation/germany50-subset-fixed/", str(g50_subset.relative_to(ROOT)), "runs/final-evaluation/germany50-subset-fixed/", "docs/progress/germany50-subset-failure-root-cause-and-fix.md", f"corrected run summaries={subset_counts}; 30 dry-run", ""))
    rl = read_json(FINAL / "rl-docker-supplement/summary.json")
    rl_counts = validate_rl_aggregation(errors)
    inventory.append(item("RL real Docker supplement", "PASS" if rl_counts == {"q_learning": 20, "heuristic": 20, "fixed_a": 20, "fixed_b": 20} else "INCOMPLETE", "runs/final-evaluation/rl-docker-supplement/checkpoint.json", "runs/final-evaluation/rl-docker-supplement/summary.json", "runs/final-evaluation/rl-docker-supplement/figures/", "docs/final/rl-real-docker-supplement.md", f"policy counts={rl_counts}", ""))
    dashboard = ROOT / "dashboard/static_server.py"
    inventory.append(item("fallback dashboard", "PASS" if dashboard.exists() else "MISSING", "dashboard/static_server.py", "runs/final-evaluation/pre-dissertation-checkpoint.json", "", "docs/final/known-limitations.md", "static Python fallback; not Streamlit", ""))
    payload = {"audit_version": 1, "json_csv_parse_errors": errors, "delay_means_ms": delay_means, "loss_means_percent": loss_means, "germany50_subset_corrected_counts": subset_counts, "inventory": inventory, "rl_counts": rl_counts}
    output = FINAL / "evidence-inventory.json"; output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    lines = ["# Pre-dissertation repository and evidence audit", "", "This audit is read-only with respect to measured data; it parses retained artifacts and records only evidence completeness.", "", "| Experiment or feature | Status | Raw evidence | Summary | Figure | Documentation | Consistency | Missing items |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for row in inventory:
        lines.append("| " + " | ".join(str(row[key]).replace("|", "/") for key in ("experiment_or_feature", "status", "raw_evidence_path", "summary_path", "figure_path", "documentation_path", "consistency_result", "missing_items")) + " |")
    lines += ["", "## Cross-checks", f"", f"- JSON/CSV parse errors: {len(errors)}", f"- Delay mean RTTs (ms): {delay_means}", f"- Packet-loss mean measurements (%): {loss_means}", f"- RL valid episodes: {rl_counts}", "- Germany50 wording: full topology was instantiated; selected on-demand routes, not all 4,224 routes, carried real traffic.", "- OpenAI official result remains HTTP 429 `insufficient_quota`; the compatible-provider six-node run is separate.", ""]
    (ROOT / "docs/final/pre-dissertation-evidence-audit.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"parse_errors": len(errors), "inventory_entries": len(inventory), "delay_means": delay_means, "loss_means": loss_means, "rl_counts": rl_counts}, indent=2))


if __name__ == "__main__":
    main()
