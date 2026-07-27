#!/usr/bin/env python3
"""Bounded two-static-path Q-learning experiment (six Docker nodes maximum)."""
import argparse
import csv
import json
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path

from routed_delay_utils import build_combined_qdisc_commands, summarize_numeric
from simulator_topology import (
    cleanup, configure_routes, create_subnets, ping_test, resolve_interface_name,
    run_command, run_iperf, start_nodes, verify_routes,
)
from topology_utils import get_interface, get_node, get_subnet, load_topology_scenario, parse_throughput

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCENARIO_PATH = PROJECT_ROOT / "data" / "minimal-rl-dual-path.json"
PREPARE_HOST_ROUTING = PROJECT_ROOT / "scripts" / "prepare_wsl_docker.py"
PATHS = {"A": ["r1", "r2", "r4"], "B": ["r1", "r3", "r4"]}
PHASES = (
    {"name": "phase-1-a-preferred", "A": (5, 0, 20), "B": (30, 4, 12)},
    {"name": "phase-2-b-preferred", "A": (30, 4, 12), "B": (5, 0, 20)},
)
REWARD_DEFINITION = "throughput_mbps - 0.05 * rtt_ms - 0.50 * packet_loss_percent"


def reward(metrics: dict) -> float:
    return round(metrics["throughput_mbps"] - 0.05 * metrics["rtt_ms"] - 0.50 * metrics["loss_percent"], 3)


def state_from_metrics(metrics: dict, current_path: str) -> tuple[str, str, str, str]:
    """Compact tabular state: RTT bucket, loss bucket, throughput bucket, current path."""
    rtt = "low" if metrics["rtt_ms"] < 45 else "high"
    loss = "none" if metrics["loss_percent"] < 1 else "loss"
    throughput = "high" if metrics["throughput_mbps"] >= 16 else "low"
    return rtt, loss, throughput, current_path


class QLearningAgent:
    def __init__(self, seed: int = 20260722, alpha: float = 0.35, gamma: float = 0.85, epsilon: float = 0.18):
        self.alpha, self.gamma, self.epsilon = alpha, gamma, epsilon
        self.rng = random.Random(seed)
        self.values: dict[tuple[str, str, str, str], dict[str, float]] = {}

    def _row(self, state):
        return self.values.setdefault(state, {"A": 0.0, "B": 0.0})

    def choose(self, state: tuple[str, str, str, str]) -> str:
        row = self._row(state)
        if self.rng.random() < self.epsilon:
            return self.rng.choice(["A", "B"])
        return max(("A", "B"), key=lambda action: (row[action], action == "A"))

    def update(self, state, action: str, observed_reward: float, next_state) -> None:
        row, next_row = self._row(state), self._row(next_state)
        row[action] = round(row[action] + self.alpha * (observed_reward + self.gamma * max(next_row.values()) - row[action]), 6)


def phase_for_episode(episode: int, episodes: int) -> dict:
    return PHASES[0] if episode <= episodes // 2 else PHASES[1]


def synthetic_metrics(path: str, phase: dict, episode: int, seed: int) -> dict:
    delay, loss, bandwidth = phase[path]
    rng = random.Random(seed + episode * 17 + (0 if path == "A" else 1))
    return {
        "rtt_ms": round(14 + 4 * delay + rng.uniform(-0.6, 0.6), 3),
        "loss_percent": float(loss),
        "throughput_mbps": round(bandwidth * (0.93 if loss == 0 else 0.72) + rng.uniform(-0.15, 0.15), 3),
    }


def baseline_results(episodes: int, seed: int) -> dict:
    policies = {"fixed_a": lambda phase: "A", "fixed_b": lambda phase: "B", "threshold_heuristic": lambda phase: min(("A", "B"), key=lambda p: (phase[p][0] + phase[p][1] * 4, p))}
    result = {}
    for name, policy in policies.items():
        rows = []
        for episode in range(1, episodes + 1):
            selected = policy(phase_for_episode(episode, episodes))
            metrics = synthetic_metrics(selected, phase_for_episode(episode, episodes), episode, seed)
            rows.append({"path": selected, "reward": reward(metrics), **metrics})
        result[name] = {"mean_reward": summarize_numeric([row["reward"] for row in rows]), "path_counts": dict(Counter(row["path"] for row in rows)), "rows": rows}
    return result


def scenario_route_data(scenario: dict, path: str) -> tuple[str, str, str, str]:
    """Return destination subnet and next hops for r1 forward / r4 reverse selection."""
    forward_dest = get_subnet(scenario, "net_006_r4_rl-server")["cidr"]
    reverse_dest = get_subnet(scenario, "net_001_rl-client_r1")["cidr"]
    via_r1 = get_interface(get_node(scenario, "r2" if path == "A" else "r3"), f"net_00{2 if path == 'A' else 4}_r1_r{'2' if path == 'A' else '3'}")["ip"]
    via_r4 = get_interface(get_node(scenario, "r2" if path == "A" else "r3"), f"net_00{3 if path == 'A' else 5}_r{'2' if path == 'A' else '3'}_r4")["ip"]
    return forward_dest, reverse_dest, via_r1, via_r4


class DockerDualPathBackend:
    def __init__(self, scenario: dict, runtime_dir: Path):
        self.scenario = scenario
        self.runtime_scenario_path = runtime_dir / "docker-scenario.normalized.json"
        self.route_switches = []

    def start(self) -> None:
        # The controller can switch between paths A and B without rebuilding
        # the topology.  Tell the scoped WSL helper to protect topology edges
        # for both endpoint directions; it still creates O(E), not N×N, rules.
        self.scenario.setdefault("traffic", {})["runtime_path_selection"] = True
        cleanup(self.scenario)
        create_subnets(self.scenario)
        self.runtime_scenario_path.write_text(json.dumps(self.scenario, indent=2) + "\n", encoding="utf-8")
        run_command(
            [sys.executable, str(PREPARE_HOST_ROUTING), "--scenario", str(self.runtime_scenario_path)],
            check=True,
        )
        start_nodes(self.scenario)
        configure_routes(self.scenario)
        verify_routes(self.scenario)

    def _apply_stage(self, phase: dict) -> None:
        for link in self.scenario["links"]:
            path = "A" if link["source"] in {"r1", "r2"} and link["target"] in {"r2", "r4"} else "B" if link["source"] in {"r1", "r3"} and link["target"] in {"r3", "r4"} else None
            delay, loss, bandwidth = phase[path] if path else (2, 0, 20)
            for node_id in (link["source"], link["target"]):
                node = get_node(self.scenario, node_id)
                if node["type"] != "router":
                    continue
                iface = resolve_interface_name(node_id, get_interface(node, link["subnet"])["ip"])
                for command in build_combined_qdisc_commands(iface, bandwidth, delay, loss):
                    run_command(["docker", "exec", node_id] + command, check=True)

    def select_and_measure(self, path: str, phase: dict) -> dict:
        self._apply_stage(phase)
        forward_dest, reverse_dest, via_r1, via_r4 = scenario_route_data(self.scenario, path)
        for node, destination, via in (("r1", forward_dest, via_r1), ("r4", reverse_dest, via_r4)):
            run_command(["docker", "exec", node, "ip", "route", "replace", destination, "via", via], check=True)
        checks = []
        for node, destination, via in (("r1", forward_dest, via_r1), ("r4", reverse_dest, via_r4)):
            output = run_command(["docker", "exec", node, "ip", "route", "show", destination], check=True).stdout.strip()
            checks.append({"node": node, "destination": destination, "via": via, "matched": f"via {via}" in output})
        if not all(item["matched"] for item in checks):
            raise RuntimeError("In-place route selection verification failed.")
        # Keep the real Docker evaluation bounded: two real ICMP probes per
        # episode are sufficient for route/RTT verification while iperf3
        # remains a real per-episode throughput measurement.
        ok, ping, _ = ping_test(self.scenario, True)
        if not ok:
            raise RuntimeError("RL path ping failed.")
        throughput = parse_throughput(run_iperf(self.scenario, False))
        if throughput is None:
            raise RuntimeError("RL iperf3 parsing failed.")
        self.route_switches.append({"path": path, "checks": checks})
        return {"rtt_ms": ping["rtt_avg_ms"], "loss_percent": ping["packet_loss_percent"], "throughput_mbps": throughput, "route_checks": checks}

    def close(self) -> float:
        try:
            return cleanup(self.scenario)
        finally:
            run_command([sys.executable, str(PREPARE_HOST_ROUTING), "--cleanup"], check=False)


def write_svg(path: Path, title: str, rows: list[dict], key: str) -> None:
    width, height = 800, 300
    values = [float(row[key]) for row in rows] or [0.0]
    lo, hi = min(values), max(values)
    span = max(hi - lo, 1.0)
    points = []
    for index, value in enumerate(values, start=1):
        x = 55 + (index - 1) * 700 / max(1, len(values) - 1)
        y = 250 - (value - lo) * 190 / span
        points.append(f"{x:.1f},{y:.1f}")
    path.write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><rect width="100%" height="100%" fill="white"/><text x="400" y="24" text-anchor="middle">{title}</text><line x1="55" y1="250" x2="755" y2="250" stroke="black"/><line x1="55" y1="50" x2="55" y2="250" stroke="black"/><polyline fill="none" stroke="#2563eb" stroke-width="2" points="{' '.join(points)}"/><text x="60" y="45">max {hi:.3f}</text><text x="60" y="270">min {lo:.3f}</text></svg>\n''', encoding="utf-8")


def run_experiment(episodes: int, output_dir: Path, seed: int = 20260722, docker: bool = False) -> dict:
    if episodes < 20:
        raise ValueError("At least 20 episodes are required.")
    output_dir.mkdir(parents=True, exist_ok=True)
    scenario = load_topology_scenario(SCENARIO_PATH)
    agent, current_path = QLearningAgent(seed), "A"
    current_metrics = synthetic_metrics("A", PHASES[0], 0, seed)
    backend = DockerDualPathBackend(scenario, output_dir) if docker else None
    rows, cleanup_time_s = [], 0.0
    if backend:
        backend.start()
    try:
        for episode in range(1, episodes + 1):
            phase = phase_for_episode(episode, episodes)
            state = state_from_metrics(current_metrics, current_path)
            action = agent.choose(state)
            metrics = backend.select_and_measure(action, phase) if backend else synthetic_metrics(action, phase, episode, seed)
            observed_reward = reward(metrics)
            next_state = state_from_metrics(metrics, action)
            agent.update(state, action, observed_reward, next_state)
            rows.append({"episode": episode, "phase": phase["name"], "path": action, "reward": observed_reward, **metrics})
            # A foreground execution window can interrupt a real Docker run;
            # preserve every completed episode atomically for resume evidence.
            progress = output_dir / "episodes-progress.json"
            temporary = progress.with_suffix(".tmp")
            temporary.write_text(json.dumps({"seed": seed, "docker": docker, "completed_episodes": len(rows), "rows": rows}, indent=2) + "\n", encoding="utf-8")
            temporary.replace(progress)
            current_path, current_metrics = action, metrics
    finally:
        if backend:
            cleanup_time_s = backend.close()
        if docker and rows:
            (output_dir / "docker-terminal-evidence.json").write_text(json.dumps({"completed_episodes": len(rows), "cleanup_time_s": cleanup_time_s}, indent=2) + "\n", encoding="utf-8")
    for field, filename, title in (("reward", "reward.svg", "Episode reward"), ("rtt_ms", "rtt.svg", "Episode RTT (ms)"), ("throughput_mbps", "throughput.svg", "Episode throughput (Mbps)")):
        write_svg(output_dir / filename, title, rows, field)
    write_svg(output_dir / "path-selection.svg", "Path selection (A=1, B=2)", [{**row, "path_number": 1 if row["path"] == "A" else 2} for row in rows], "path_number")
    baselines = baseline_results(episodes, seed)
    summary = {
        "scope": "Minimal six-node dual-static-path experiment; not Germany50 or DFN full topology.",
        "seed": seed, "episodes": episodes, "reward_definition": REWARD_DEFINITION,
        "docker_real_run": docker, "topology_node_count": len(scenario["nodes"]), "path_definitions": PATHS,
        "selected_path_counts": dict(Counter(row["path"] for row in rows)),
        "q_learning": {"mean_reward": summarize_numeric([row["reward"] for row in rows]), "mean_rtt_ms": summarize_numeric([row["rtt_ms"] for row in rows]), "mean_throughput_mbps": summarize_numeric([row["throughput_mbps"] for row in rows])},
        "baselines": {name: {key: value for key, value in data.items() if key != "rows"} for name, data in baselines.items()},
        "route_switch_verification": all(all(check["matched"] for check in row.get("route_checks", [])) for row in rows) if docker else "mock-not-applicable",
        "cleanup_time_s": cleanup_time_s, "q_table": {"|".join(state): values for state, values in agent.values.items()},
    }
    (output_dir / "episodes.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    with (output_dir / "episodes.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["episode", "phase", "path", "reward", "rtt_ms", "loss_percent", "throughput_mbps"])
        writer.writeheader(); writer.writerows([{key: row[key] for key in writer.fieldnames} for row in rows])
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260722)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "runs" / "minimal-rl-path-control")
    parser.add_argument("--docker", action="store_true", help="Run one persistent six-node Docker topology.")
    args = parser.parse_args()
    print(json.dumps(run_experiment(args.episodes, args.output_dir, args.seed, args.docker), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
