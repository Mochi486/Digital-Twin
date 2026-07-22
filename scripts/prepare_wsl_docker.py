#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from routed_delay_utils import is_tagged_project70_rule


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCENARIO = PROJECT_ROOT / "data" / "scenario_routed.json"
RULE_COMMENT = "project70-wsl-routing"
HOST_ROOT_MOUNT = "/host"
PRIVILEGED_HELPER_IMAGE = "my-iperf-tc"
DEFAULT_RULE_LIMIT = 512


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def run_host_iptables(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    if run(["id", "-u"]).stdout.strip() == "0":
        return run(["iptables"] + args, check=check)

    helper_cmd = [
        "docker",
        "run",
        "--rm",
        "--privileged",
        "--network",
        "host",
        "-v",
        f"/:{HOST_ROOT_MOUNT}",
        PRIVILEGED_HELPER_IMAGE,
        "chroot",
        HOST_ROOT_MOUNT,
        "/usr/sbin/iptables",
    ] + args
    return run(helper_cmd, check=check)


def load_networks(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        scenario = json.load(f)
    if "networks" in scenario:
        return scenario["networks"]
    if "subnets" in scenario:
        return [
            {
                "name": subnet["name"],
                "subnet": subnet["cidr"],
            }
            for subnet in scenario["subnets"]
        ]
    raise KeyError("Scenario must define either 'networks' or 'subnets'.")


def build_rule_plan(path: Path, networks: list[dict]) -> list[tuple[str, str]]:
    """Return only forwarding pairs joined by a router, never an N×N network mesh."""
    scenario = json.loads(path.read_text(encoding="utf-8"))
    if "nodes" not in scenario or "links" not in scenario:
        return [(source["name"], target["subnet"]) for source in networks for target in networks if source != target]
    by_node = {node["id"]: [] for node in scenario["nodes"]}
    for link in scenario["links"]:
        subnet = link.get("subnet")
        if subnet:
            by_node.setdefault(link["source"], []).append(subnet)
            by_node.setdefault(link["target"], []).append(subnet)
    subnet_by_name = {item["name"]: item["subnet"] for item in networks}
    plan = set()
    for node in scenario["nodes"]:
        if node.get("type") != "router":
            continue
        attached = sorted(set(by_node[node["id"]]))
        for source in attached:
            for target in attached:
                if source != target:
                    plan.add((source, subnet_by_name[target]))
    return sorted(plan)


def bridge_name_for_network(network_name: str) -> str | None:
    result = run(
        ["docker", "network", "inspect", network_name, "--format", "{{.Id}}"],
        check=False,
    )
    network_id = result.stdout.strip()
    if result.returncode != 0 or not network_id:
        return None
    return f"br-{network_id[:12]}"


def network_id_for_name(network_name: str) -> str | None:
    result = run(
        ["docker", "network", "inspect", network_name, "--format", "{{.Id}}"],
        check=False,
    )
    network_id = result.stdout.strip()
    if result.returncode != 0 or not network_id:
        return None
    return network_id


def current_raw_rules() -> list[str]:
    result = run_host_iptables(["-t", "raw", "-S", "PREROUTING"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def delete_tagged_rules(log) -> None:
    for rule in current_raw_rules():
        if not is_tagged_project70_rule(rule, RULE_COMMENT):
            continue
        rule_args = rule.split()[2:]
        delete_args = ["-t", "raw", "-D", "PREROUTING"] + rule_args
        run_host_iptables(delete_args)
        print(f"Deleted tagged rule: iptables {' '.join(delete_args)}", file=log, flush=True)


def ensure_accept_rule(bridge_name: str, subnet: str, log) -> None:
    check_cmd = [
        "-t", "raw", "-C", "PREROUTING",
        "-i", bridge_name, "-d", subnet,
        "-m", "comment", "--comment", RULE_COMMENT,
        "-j", "ACCEPT",
    ]
    exists = run_host_iptables(check_cmd, check=False)
    if exists.returncode == 0:
        print(f"Rule already present for {bridge_name} -> {subnet}", file=log, flush=True)
        return

    add_cmd = [
        "-t", "raw", "-I", "PREROUTING", "1",
        "-i", bridge_name, "-d", subnet,
        "-m", "comment", "--comment", RULE_COMMENT,
        "-j", "ACCEPT",
    ]
    run_host_iptables(add_cmd)
    print(f"Added rule: iptables {' '.join(add_cmd)}", file=log, flush=True)


def wait_and_prepare(
    networks: list[dict],
    timeout_s: float,
    poll_s: float,
    log,
    ignore_existing: bool,
    rule_plan: list[tuple[str, str]],
    rule_limit: int,
) -> dict[str, str]:
    deadline = time.time() + timeout_s
    bridge_map: dict[str, str] = {}
    initial_ids = {}

    if ignore_existing:
        for net in networks:
            initial_ids[net["name"]] = network_id_for_name(net["name"])

    while time.time() < deadline:
        bridge_map.clear()
        for net in networks:
            network_id = network_id_for_name(net["name"])
            if not network_id:
                continue
            if ignore_existing and initial_ids.get(net["name"]) == network_id:
                continue
            bridge_name = f"br-{network_id[:12]}"
            if bridge_name:
                bridge_map[net["name"]] = bridge_name

        if len(bridge_map) == len(networks):
            if len(rule_plan) > rule_limit:
                raise ValueError(f"Forwarding rule estimate {len(rule_plan)} exceeds limit {rule_limit}.")
            delete_tagged_rules(log)
            for source_name, destination_subnet in rule_plan:
                ensure_accept_rule(bridge_map[source_name], destination_subnet, log)
            return bridge_map

        time.sleep(poll_s)

    missing = [net["name"] for net in networks if net["name"] not in bridge_map]
    raise TimeoutError(f"Timed out waiting for Docker networks: {', '.join(missing)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default=str(DEFAULT_SCENARIO))
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--poll-interval", type=float, default=0.2)
    parser.add_argument("--evidence", default="")
    parser.add_argument("--ignore-existing", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--rule-limit", type=int, default=DEFAULT_RULE_LIMIT)
    parser.add_argument("--estimate-only", action="store_true")
    args = parser.parse_args()

    scenario_path = Path(args.scenario)
    networks = load_networks(scenario_path)
    rule_plan = build_rule_plan(scenario_path, networks)

    if args.evidence:
        evidence_path = Path(args.evidence)
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        log = evidence_path.open("w", encoding="utf-8")
    else:
        log = sys.stdout

    try:
        print(f"Scenario: {scenario_path}", file=log, flush=True)
        if args.cleanup:
            delete_tagged_rules(log)
            print("Cleanup complete.", file=log, flush=True)
            return 0
        if args.estimate_only:
            print(json.dumps({"network_count": len(networks), "rule_count": len(rule_plan), "rule_limit": args.rule_limit}, indent=2), file=log)
            return 0
        bridge_map = wait_and_prepare(
            networks,
            args.timeout,
            args.poll_interval,
            log,
            args.ignore_existing,
            rule_plan,
            args.rule_limit,
        )
        print(json.dumps(bridge_map, indent=2), file=log, flush=True)
    finally:
        if log is not sys.stdout:
            log.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
