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


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def load_networks(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        scenario = json.load(f)
    return scenario["networks"]


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
    result = run(["iptables", "-t", "raw", "-S", "PREROUTING"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def delete_tagged_rules(log) -> None:
    for rule in current_raw_rules():
        if not is_tagged_project70_rule(rule, RULE_COMMENT):
            continue
        rule_args = rule.split()[2:]
        delete_args = ["iptables", "-t", "raw", "-D", "PREROUTING"] + rule_args
        run(delete_args)
        print(f"Deleted tagged rule: {' '.join(delete_args)}", file=log, flush=True)


def ensure_accept_rule(bridge_name: str, subnet: str, log) -> None:
    check_cmd = [
        "iptables", "-t", "raw", "-C", "PREROUTING",
        "-i", bridge_name, "-d", subnet,
        "-m", "comment", "--comment", RULE_COMMENT,
        "-j", "ACCEPT",
    ]
    exists = run(check_cmd, check=False)
    if exists.returncode == 0:
        print(f"Rule already present for {bridge_name} -> {subnet}", file=log, flush=True)
        return

    add_cmd = [
        "iptables", "-t", "raw", "-I", "PREROUTING", "1",
        "-i", bridge_name, "-d", subnet,
        "-m", "comment", "--comment", RULE_COMMENT,
        "-j", "ACCEPT",
    ]
    run(add_cmd)
    print(f"Added rule: {' '.join(add_cmd)}", file=log, flush=True)


def wait_and_prepare(
    networks: list[dict],
    timeout_s: float,
    poll_s: float,
    log,
    ignore_existing: bool,
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
            delete_tagged_rules(log)
            for source_net in networks:
                for destination_net in networks:
                    if source_net["name"] == destination_net["name"]:
                        continue
                    ensure_accept_rule(
                        bridge_map[source_net["name"]],
                        destination_net["subnet"],
                        log,
                    )
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
    args = parser.parse_args()

    if run(["id", "-u"]).stdout.strip() != "0":
        print("prepare_wsl_docker.py must run as root to manage iptables.", file=sys.stderr)
        return 1

    scenario_path = Path(args.scenario)
    networks = load_networks(scenario_path)

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
        bridge_map = wait_and_prepare(
            networks,
            args.timeout,
            args.poll_interval,
            log,
            args.ignore_existing,
        )
        print(json.dumps(bridge_map, indent=2), file=log, flush=True)
    finally:
        if log is not sys.stdout:
            log.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
