#!/usr/bin/env python3
"""Create aggregate, non-destructive statistics for the RL Docker supplement."""
import csv
import json
import math
import statistics
from pathlib import Path


POLICIES = ("q_learning", "heuristic", "fixed_a", "fixed_b")
METRICS = ("reward", "rtt_ms", "loss_percent", "throughput_mbps")


def mean_std_ci(values):
    mean = statistics.fmean(values)
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    ci95 = 1.96 * std / math.sqrt(len(values)) if len(values) > 1 else 0.0
    return {"mean": round(mean, 6), "std": round(std, 6), "ci95": round(ci95, 6)}


def write_svg(path: Path, title: str, series: dict[str, list[float]]):
    width, height = 900, 360
    values = [value for rows in series.values() for value in rows] or [0.0]
    lo, hi = min(values), max(values)
    span = max(hi - lo, 1.0)
    colors = ("#2563eb", "#dc2626", "#16a34a", "#9333ea")
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             f'<text x="40" y="28" font-family="sans-serif" font-size="18">{title}</text>',
             f'<text x="40" y="348" font-family="sans-serif" font-size="12">min={lo:.3f}, max={hi:.3f}</text>']
    for color, (name, rows) in zip(colors, series.items()):
        points = []
        for index, value in enumerate(rows):
            x = 55 + index * 800 / max(1, len(rows) - 1)
            y = 315 - (value - lo) * 255 / span
            points.append(f"{x:.1f},{y:.1f}")
        parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{" ".join(points)}"/>')
        parts.append(f'<text x="{55 + 150 * list(series).index(name)}" y="50" fill="{color}" font-family="sans-serif" font-size="12">{name}</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main(root: Path):
    checkpoint_path = root / "checkpoint.json"
    state = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    rows = []
    for policy in POLICIES:
        rows.extend({**row, "policy": policy} for row in state["policy_progress"][policy])
    rows.sort(key=lambda row: (POLICIES.index(row["policy"]), row["episode"]))
    if any(len(state["policy_progress"][policy]) != 20 for policy in POLICIES):
        raise SystemExit("All four policies require exactly 20 valid episodes before summary generation.")
    with (root / "per-episode-results.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["policy", "episode", "phase", "path", "reward", "rtt_ms", "loss_percent", "throughput_mbps", "elapsed_s"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows({field: row.get(field, "") for field in fields} for row in rows)
    summaries = {}
    for policy in POLICIES:
        policy_rows = state["policy_progress"][policy]
        paths = [row["path"] for row in policy_rows]
        summaries[policy] = {
            "valid_episodes": len(policy_rows),
            "failed_or_retried": len(state.get("attempts", {}).get(policy, [])),
            "switch_count": sum(left != right for left, right in zip(paths, paths[1:])),
            "path_selection_counts": {"A": paths.count("A"), "B": paths.count("B")},
            "metrics": {metric: mean_std_ci([float(row[metric]) for row in policy_rows]) for metric in METRICS},
        }
    with (root / "policy-summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle); writer.writerow(["policy", "valid_episodes", "switch_count", "path_a", "path_b", *[f"{m}_{s}" for m in METRICS for s in ("mean", "std", "ci95")]])
        for policy in POLICIES:
            item = summaries[policy]; row = [policy, item["valid_episodes"], item["switch_count"], item["path_selection_counts"]["A"], item["path_selection_counts"]["B"]]
            row += [item["metrics"][metric][stat] for metric in METRICS for stat in ("mean", "std", "ci95")]; writer.writerow(row)
    figures = root / "figures"; figures.mkdir(exist_ok=True)
    for metric, label in (("reward", "Reward by episode"), ("rtt_ms", "RTT by episode (ms)"), ("throughput_mbps", "Throughput by episode (Mbps)"), ("loss_percent", "Loss by episode (%)")):
        write_svg(figures / f"{metric}-by-episode.svg", label, {policy: [float(row[metric]) for row in state["policy_progress"][policy]] for policy in POLICIES})
    write_svg(figures / "path-selection-timeline.svg", "Path selection timeline (A=0, B=1)", {policy: [0.0 if row["path"] == "A" else 1.0 for row in state["policy_progress"][policy]] for policy in POLICIES})
    write_svg(figures / "policy-mean-comparison.svg", "Policy mean reward comparison", {policy: [summaries[policy]["metrics"]["reward"]["mean"]] for policy in POLICIES})
    summary = {"experiment": "real-docker-rl-policy-supplement", "policies": summaries, "rows": len(rows), "checkpoint": str(checkpoint_path), "figures": [str(path) for path in sorted(figures.glob("*.svg"))]}
    (root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    state["current_stage"] = "summary_complete"; state["completed_stages"] = sorted(set(state.get("completed_stages", []) + ["policy_execution", "summary"])); state["artifacts"] = {"summary": str(root / "summary.json"), "per_episode_csv": str(root / "per-episode-results.csv"), "policy_summary_csv": str(root / "policy-summary.csv")}
    checkpoint_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument("--root", type=Path, default=Path("runs/final-evaluation/rl-docker-supplement")); args = parser.parse_args(); main(args.root)
