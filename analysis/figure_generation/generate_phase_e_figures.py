"""Generate Phase E dissertation figures from retained evidence only.

This script never runs experiments and never writes to the evidence repository.
It reads the Phase B inventory CSV plus retained Germany50 and RL artifacts.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from matplotlib.lines import Line2D


DISSERTATION_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = Path(r"D:\projects_70")
INVENTORY_CSV = (
    DISSERTATION_ROOT
    / "derived"
    / "audit_computed_statistics"
    / "experiment_summary.csv"
)
RL_CSV = (
    EVIDENCE_ROOT
    / "runs"
    / "final-evaluation"
    / "rl-docker-supplement"
    / "per-episode-results.csv"
)
RL_SUMMARY = (
    EVIDENCE_ROOT
    / "runs"
    / "final-evaluation"
    / "rl-docker-supplement"
    / "summary.json"
)
GERMANY50 = EVIDENCE_ROOT / "data" / "scenario_germany50.json"


plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 8.0,
        "axes.labelsize": 8.0,
        "axes.titlesize": 9.0,
        "xtick.labelsize": 7.5,
        "ytick.labelsize": 7.5,
        "legend.fontsize": 7.0,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.linewidth": 0.8,
    }
)


def save_figure(fig: plt.Figure, directory: Path, stem: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    fig.savefig(directory / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(directory / f"{stem}.png", dpi=300, bbox_inches="tight")
    fig.savefig(directory / f"{stem}.svg", bbox_inches="tight")
    plt.close(fig)


def read_inventory() -> dict[str, dict[str, str]]:
    with INVENTORY_CSV.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return {row["Experiment"]: row for row in rows}


def numeric(value: str) -> float:
    cleaned = value.strip().replace("±", "")
    return float(cleaned)


def styled_axis(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="0.88", linewidth=0.6, zorder=0)


def draw_box(ax: plt.Axes, xy: tuple[float, float], width: float, height: float,
             title: str, detail: str, face: str = "0.96", linestyle: str = "-",
             title_size: float = 6.8, detail_size: float = 5.9) -> None:
    x, y = xy
    patch = FancyBboxPatch(
        (x, y), width, height,
        boxstyle="round,pad=0.015,rounding_size=0.018",
        linewidth=1.0,
        edgecolor="0.15",
        facecolor=face,
        linestyle=linestyle,
    )
    ax.add_patch(patch)
    ax.text(
        x + width / 2, y + height * 0.62, title,
        ha="center", va="center", weight="bold", fontsize=title_size,
    )
    ax.text(x + width / 2, y + height * 0.30, detail, ha="center", va="center", fontsize=detail_size)


def arrow(ax: plt.Axes, start: tuple[float, float], end: tuple[float, float],
          linestyle: str = "-") -> None:
    ax.add_patch(
        FancyArrowPatch(
            start, end, arrowstyle="-|>", mutation_scale=10,
            linewidth=1.0, color="0.15", linestyle=linestyle,
            shrinkA=2, shrinkB=2,
        )
    )


def figure_architecture() -> None:
    fig, ax = plt.subplots(figsize=(7.2, 3.05))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    xs = [0.02, 0.18, 0.34, 0.50, 0.66, 0.82]
    labels = [
        ("Scenario /\nconfig", "validated JSON\nscenario"),
        ("Validation", "schema / semantic\n/ security"),
        ("Docker\ntopology", "containers / links\n/ namespaces"),
        ("Routing", "forwarding\n/ routes"),
        ("Impairment", "tc/netem / TBF\nbandwidth / delay\n/ loss"),
        ("Measurement", "ping / iperf3\ncontrolled\ntraffic"),
    ]
    width, height, y = 0.14, 0.23, 0.38
    for x, (title, detail) in zip(xs, labels):
        draw_box(ax, (x, y), width, height, title, detail, title_size=6.8, detail_size=5.7)
    for left, right in zip(xs, xs[1:]):
        arrow(ax, (left + width, y + height / 2), (right, y + height / 2))

    evidence_x = 0.78
    draw_box(
        ax, (evidence_x, 0.07), 0.18, 0.19,
        "Retained evidence", "JSON + CSV + logs\nstatistics + plots",
        face="0.88", title_size=6.4, detail_size=5.6,
    )
    arrow(ax, (0.89, y), (0.87, 0.26))

    extensions = [
        (0.08, "AI assistance", "validated scenario\ngeneration"),
        (0.40, "RL control", "closed-loop policy\nselection"),
        (0.72, "Dashboard", "bounded interactive\nsmall-topology UI"),
    ]
    for x, title, detail in extensions:
        draw_box(
            ax, (x, 0.78), 0.20, 0.15, title, detail,
            face="1.0", linestyle="--", title_size=6.8, detail_size=5.9,
        )
    arrow(ax, (0.18, 0.78), (0.25, y + height), linestyle="--")
    arrow(ax, (0.50, 0.78), (0.57, y + height), linestyle="--")
    arrow(ax, (0.82, 0.78), (0.89, y + height), linestyle="--")

    ax.text(0.50, 0.69, "Validated execution and evidence pipeline", ha="center",
            va="center", fontsize=7.4, color="0.35")
    save_figure(fig, DISSERTATION_ROOT / "figures" / "architecture", "overall_system_architecture")


def figure_impairments(inventory: dict[str, dict[str, str]]) -> None:
    # Dissertation-side composite regenerated from retained evidence. The
    # project audit SVGs for delay and loss were inspected, but they omit the
    # replicated bandwidth cohorts and uncertainty/provenance shown here.
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.65))

    ax = axes[0]
    bw_cfg = [20, 50, 100]
    bw_rows = [
        inventory["Bandwidth 20 Mbps historical baseline"],
        inventory["Bandwidth 50 Mbps"],
        inventory["Bandwidth 100 Mbps"],
    ]
    bw_mean = [numeric(row["Mean"]) for row in bw_rows]
    ax.plot([0, 105], [0, 105], linestyle="--", linewidth=0.8, color="0.55", label="Configured = measured")
    ax.scatter([20], [bw_mean[0]], marker="x", s=48, linewidth=1.4, color="0.05", zorder=4)
    ax.errorbar(
        bw_cfg[1:], bw_mean[1:],
        yerr=[numeric(bw_rows[1]["95% CI"]), numeric(bw_rows[2]["95% CI"])],
        fmt="o", color="0.15", markerfacecolor="white", markeredgewidth=1.0,
        capsize=3, linewidth=1.0, zorder=3, label="Repeated cohorts",
    )
    ax.set(xlabel="Configured bandwidth (Mbps)", ylabel="Measured throughput (Mbps)", title="(a) Bandwidth")
    ax.set_xlim(0, 108)
    ax.set_ylim(0, 108)
    ax.set_xticks(bw_cfg)
    styled_axis(ax)
    ax.legend(loc="upper left", frameon=False, fontsize=6.2)

    ax = axes[1]
    lat_cfg = [0, 10, 30, 50]
    lat_rows = [inventory[f"Latency {value} ms"] for value in lat_cfg]
    lat_mean = [numeric(row["Mean"]) for row in lat_rows]
    lat_ci = [numeric(row["95% CI"]) for row in lat_rows]
    ax.errorbar(
        lat_cfg, lat_mean, yerr=lat_ci, fmt="s-", color="0.15",
        markerfacecolor="white", markeredgewidth=1.0, capsize=3, linewidth=1.0,
    )
    ax.set(
        xlabel="Configured one-way delay (ms)",
        ylabel="Measured ping RTT (ms)",
        title="(b) Latency",
    )
    ax.set_xticks(lat_cfg)
    styled_axis(ax)

    ax = axes[2]
    loss_cfg = [0, 1, 3, 5]
    loss_rows = [inventory[f"Packet loss {value}%"] for value in loss_cfg]
    loss_mean = [numeric(row["Mean"]) for row in loss_rows]
    loss_ci = [numeric(row["95% CI"]) for row in loss_rows]
    ax.errorbar(
        loss_cfg, loss_mean, yerr=loss_ci, fmt="D-", color="0.15",
        markerfacecolor="white", markeredgewidth=1.0, capsize=3, linewidth=1.0,
    )
    ax.set(
        xlabel="Configured one-way loss (%)",
        ylabel="Measured end-to-end ping loss (%)",
        title="(c) Packet loss",
    )
    ax.set_xticks(loss_cfg)
    styled_axis(ax)

    fig.subplots_adjust(wspace=0.40, bottom=0.22)
    save_figure(fig, DISSERTATION_ROOT / "figures" / "bandwidth", "main_impairment_results")


def path_edges(nodes: list[str]) -> set[frozenset[str]]:
    return {frozenset((a, b)) for a, b in zip(nodes, nodes[1:])}


def figure_topology_scaling() -> None:
    data = json.loads(GERMANY50.read_text(encoding="utf-8"))
    positions = {node["id"]: (node["longitude"], node["latitude"]) for node in data["nodes"]}
    links = [(link["source"], link["target"]) for link in data["links"]]
    selected = {
        "shortest (1 hop)": ["aachen", "koeln"],
        "median (4 hops)": ["erfurt", "wuerzburg", "augsburg", "muenchen", "passau"],
        "longest (9 hops)": [
            "oldenburg", "bremen", "hannover", "braunschweig", "kassel", "erfurt",
            "wuerzburg", "augsburg", "muenchen", "passau",
        ],
    }

    fig = plt.figure(figsize=(7.2, 3.05))
    grid = fig.add_gridspec(1, 3, width_ratios=[0.72, 0.98, 3.75], wspace=0.12)
    ax_direct = fig.add_subplot(grid[0, 0])
    ax_dual = fig.add_subplot(grid[0, 1])
    ax_map = fig.add_subplot(grid[0, 2])

    for ax in (ax_direct, ax_dual):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
    ax_direct.plot([0.2, 0.8], [0.55, 0.55], color="0.25", linewidth=1.3)
    ax_direct.scatter([0.2, 0.8], [0.55, 0.55], s=[85, 85], marker="s", facecolors="white", edgecolors="0.1", zorder=3)
    ax_direct.text(0.2, 0.38, "client", ha="center", fontsize=7)
    ax_direct.text(0.8, 0.38, "server", ha="center", fontsize=7)
    ax_direct.set_title("Direct", pad=3)

    xs = [0.08, 0.36, 0.64, 0.92]
    ax_dual.plot(xs, [0.55] * 4, color="0.25", linewidth=1.3)
    markers = ["s", "o", "o", "s"]
    for x, marker in zip(xs, markers):
        ax_dual.scatter([x], [0.55], s=72, marker=marker, facecolors="white", edgecolors="0.1", zorder=3)
    for x, label in zip(xs, ["client", "r1", "r2", "server"]):
        ax_dual.text(x, 0.38, label, ha="center", fontsize=6.7)
    ax_dual.set_title("Dual-router", pad=3)

    for source, target in links:
        x1, y1 = positions[source]
        x2, y2 = positions[target]
        ax_map.plot([x1, x2], [y1, y2], color="0.72", linewidth=0.65, zorder=1)
    for label, nodes in selected.items():
        styles = {
            "shortest (1 hop)": ("#0072B2", "-", 2.8),
            "median (4 hops)": ("#D55E00", "--", 2.5),
            "longest (9 hops)": ("#009E73", ":", 2.8),
        }
        color, linestyle, linewidth = styles[label]
        edges = path_edges(nodes)
        for source, target in links:
            if frozenset((source, target)) in edges:
                x1, y1 = positions[source]
                x2, y2 = positions[target]
                ax_map.plot([x1, x2], [y1, y2], color=color, linestyle=linestyle, linewidth=linewidth, zorder=3)
        endpoint_xy = [positions[nodes[0]], positions[nodes[-1]]]
        ax_map.scatter(
            [point[0] for point in endpoint_xy], [point[1] for point in endpoint_xy],
            s=30, marker="s", facecolors="white", edgecolors=color, linewidths=1.3, zorder=4,
        )
    ax_map.scatter(
        [value[0] for value in positions.values()], [value[1] for value in positions.values()],
        s=10, facecolors="white", edgecolors="0.18", linewidths=0.55, zorder=2,
    )
    label_offsets = {
        "aachen": (-11, 9, "right"),
        "koeln": (8, 12, "left"),
        "oldenburg": (-10, 11, "right"),
        "erfurt": (8, 9, "left"),
        "passau": (8, 9, "left"),
    }
    for node in {item for nodes in selected.values() for item in (nodes[0], nodes[-1])}:
        x, y = positions[node]
        dx, dy, alignment = label_offsets[node]
        ax_map.annotate(
            node.title(), (x, y), xytext=(dx, dy), textcoords="offset points",
            ha=alignment, fontsize=6.2,
            bbox=dict(boxstyle="round,pad=0.13", facecolor="white",
                      edgecolor="none", alpha=0.90),
        )
    ax_map.set_aspect("equal", adjustable="datalim")
    ax_map.axis("off")
    ax_map.set_title("Germany50: 50 nodes, 88 links", pad=3)
    legend = [
        Line2D([0], [0], color="#0072B2", linestyle="-", linewidth=2.8, label="shortest (1 hop)"),
        Line2D([0], [0], color="#D55E00", linestyle="--", linewidth=2.5, label="median (4 hops)"),
        Line2D([0], [0], color="#009E73", linestyle=":", linewidth=2.8, label="longest (9 hops)"),
    ]
    fig.legend(handles=legend, loc="lower center", frameon=False, ncol=3,
               bbox_to_anchor=(0.72, 0.015), fontsize=6.3,
               handlelength=2.8, columnspacing=1.2)

    fig.text(0.12, 0.055, "validated execution", ha="center", fontsize=6.8)
    fig.text(0.29, 0.055, "5-run 20-Mbps benchmark", ha="center", fontsize=6.8)
    fig.subplots_adjust(bottom=0.17)
    save_figure(fig, DISSERTATION_ROOT / "figures" / "germany50", "topology_scaling_germany50")


def figure_rl() -> None:
    with RL_CSV.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    summary = json.loads(RL_SUMMARY.read_text(encoding="utf-8"))["policies"]
    policies = ["heuristic", "q_learning"]
    labels = ["Threshold heuristic", "Q-learning"]
    rewards = [[float(row["reward"]) for row in rows if row["policy"] == policy] for policy in policies]

    fig, (ax_dist, ax_episode) = plt.subplots(1, 2, figsize=(7.2, 2.8), gridspec_kw={"width_ratios": [0.9, 1.6]})
    parts = ax_dist.violinplot(rewards, positions=[1, 2], showmeans=False, showmedians=True, widths=0.7)
    for body, hatch in zip(parts["bodies"], ["///", "..."]):
        body.set_facecolor("0.88")
        body.set_edgecolor("0.2")
        body.set_alpha(1.0)
        body.set_hatch(hatch)
    for key in ("cbars", "cmins", "cmaxes", "cmedians"):
        parts[key].set_color("0.2")
        parts[key].set_linewidth(0.8)
    offsets = [-0.08 + 0.008 * (index % 5) for index in range(20)]
    for position, values, marker in zip([1, 2], rewards, ["o", "s"]):
        ax_dist.scatter([position + value for value in offsets], values, s=10, marker=marker, facecolors="white", edgecolors="0.2", linewidths=0.55, zorder=3)
    for position, policy in zip([1, 2], policies):
        mean = summary[policy]["metrics"]["reward"]["mean"]
        ci = summary[policy]["metrics"]["reward"]["ci95"]
        ax_dist.errorbar(position, mean, yerr=ci, fmt="D", color="0.02", capsize=4, markersize=4, zorder=4)
        ax_dist.text(position, mean + ci + 2.0, f"{mean:.2f}", ha="center", fontsize=6.8)
    ax_dist.axhline(0, color="0.55", linewidth=0.7, linestyle="--")
    ax_dist.set_xticks([1, 2], labels, rotation=12, ha="right")
    ax_dist.set_ylabel("Episode reward")
    ax_dist.set_title("Distribution and mean + 95% CI")
    styled_axis(ax_dist)

    for values, label, marker, linestyle, color in zip(
        rewards, labels, ["o", "s"], ["-", "--"], ["0.10", "0.45"]
    ):
        ax_episode.plot(
            range(1, 21), values, marker=marker, markersize=3.0,
            linewidth=0.9, linestyle=linestyle, color=color, label=label,
        )
    ax_episode.axvline(10.5, color="0.55", linewidth=0.8, linestyle=":")
    phase_label = dict(ha="center", va="center", fontsize=6.5,
                       bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=1.2))
    ax_episode.text(5.5, 10.0, "phase 1", **phase_label)
    ax_episode.text(15.5, 10.0, "phase 2", **phase_label)
    ax_episode.axhline(0, color="0.65", linewidth=0.7)
    ax_episode.set(xlabel="Episode", ylabel="Episode reward", title="Real-Docker episode sequence")
    ax_episode.set_xticks([1, 5, 10, 15, 20])
    styled_axis(ax_episode)
    ax_episode.legend(frameon=False, loc="lower left")

    fig.subplots_adjust(wspace=0.35, bottom=0.24)
    save_figure(fig, DISSERTATION_ROOT / "figures" / "rl", "rl_heuristic_vs_qlearning")


def main() -> None:
    inventory = read_inventory()
    figure_architecture()
    figure_impairments(inventory)
    figure_topology_scaling()
    figure_rl()
    print("Generated 4 figures in PDF, PNG, and SVG formats.")


if __name__ == "__main__":
    main()
