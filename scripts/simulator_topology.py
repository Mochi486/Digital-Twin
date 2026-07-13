import argparse
import json
import subprocess
import time
from pathlib import Path

from topology_utils import (
    build_bandwidth_qdisc_command,
    build_netem_qdisc_command,
    build_route_command,
    build_topology_svg,
    get_bandwidth_plan,
    get_destination_ip,
    get_interface,
    get_link_impairment_plan,
    get_node,
    get_router_nodes,
    get_subnet,
    load_topology_scenario,
    parse_ping_output,
    parse_throughput,
    theoretical_round_trip_loss_percent,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCENARIO_PATH = PROJECT_ROOT / "data" / "scenario_two_router_topology.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "runs" / "current" / "topology_metrics.json"
DEFAULT_PLOT_PATH = PROJECT_ROOT / "runs" / "current" / "topology_two_router.svg"
IMAGE_NAME = "my-iperf-tc"


def run_command(cmd, check=False):
    print(f"\n>>> {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def cleanup(scenario):
    print("\n=== Cleaning containers and subnets ===")
    for node in scenario["nodes"]:
        run_command(["docker", "rm", "-f", node["id"]], check=False)
    for subnet in scenario["subnets"]:
        run_command(["docker", "network", "rm", subnet["name"]], check=False)


def create_subnets(scenario):
    print("\n=== Creating Docker subnets ===")
    for subnet in scenario["subnets"]:
        run_command(
            ["docker", "network", "create", "--subnet", subnet["cidr"], subnet["name"]],
            check=True,
        )


def container_command_for_node(node):
    if "command" in node:
        return node["command"]
    if node["type"] == "server":
        return ["iperf3", "-s"]
    return ["sleep", "infinity"]


def start_node(node):
    first_iface = node["interfaces"][0]
    cmd = [
        "docker",
        "run",
        "-d",
        "--name",
        node["id"],
        "--cap-add=NET_ADMIN",
    ]
    if node["type"] == "router":
        cmd.extend(["--sysctl", "net.ipv4.ip_forward=1"])
    cmd.extend(
        [
            "--network",
            first_iface["subnet"],
            "--ip",
            first_iface["ip"],
            IMAGE_NAME,
        ]
    )
    cmd.extend(container_command_for_node(node))
    run_command(cmd, check=True)

    for iface in node["interfaces"][1:]:
        run_command(
            [
                "docker",
                "network",
                "connect",
                "--ip",
                iface["ip"],
                iface["subnet"],
                node["id"],
            ],
            check=True,
        )


def start_nodes(scenario):
    print("\n=== Starting containers ===")
    for node in scenario["nodes"]:
        start_node(node)
    time.sleep(1)


def configure_routes(scenario):
    print("\n=== Applying static routes ===")
    for route in scenario["routes"]:
        run_command(["docker", "exec", route["node"]] + build_route_command(route), check=True)


def resolve_interface_name(container_name, target_ip):
    result = run_command(
        ["docker", "exec", container_name, "ip", "-o", "-4", "addr", "show"],
        check=True,
    )
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        if fields[3].split("/")[0] == target_ip:
            return fields[1]
    raise RuntimeError(f"Could not resolve interface for {container_name} IP {target_ip}")


def clear_root_qdisc(container_name, interface_name):
    run_command(
        ["docker", "exec", container_name, "tc", "qdisc", "del", "dev", interface_name, "root"],
        check=False,
    )


def get_qdisc_state(container_name, interface_name):
    result = run_command(
        ["docker", "exec", container_name, "tc", "qdisc", "show", "dev", interface_name],
        check=True,
    )
    return result.stdout.strip()


def collect_router_qdisc_state(scenario):
    router_state = {}
    for router in get_router_nodes(scenario):
        router_state[router["id"]] = {}
        for iface in router["interfaces"]:
            interface_name = resolve_interface_name(router["id"], iface["ip"])
            router_state[router["id"]][interface_name] = get_qdisc_state(router["id"], interface_name)
    return router_state


def collect_router_routes(scenario):
    route_state = {}
    for router in get_router_nodes(scenario):
        result = run_command(["docker", "exec", router["id"], "ip", "route", "show"], check=True)
        route_state[router["id"]] = result.stdout.strip()
    return route_state


def apply_link_impairments(scenario):
    print("\n=== Applying router netem impairments ===")
    applied = []
    for record in get_link_impairment_plan(scenario):
        interface_name = resolve_interface_name(record["node"], record["interface_ip"])
        clear_root_qdisc(record["node"], interface_name)
        command = build_netem_qdisc_command(
            interface_name,
            record["delay_ms"],
            record["packet_loss_percent"],
        )
        run_command(["docker", "exec", record["node"]] + command, check=True)
        applied.append(
            {
                **record,
                "interface": interface_name,
                "qdisc": get_qdisc_state(record["node"], interface_name),
            }
        )
    return applied


def apply_bandwidth_limits(scenario):
    print("\n=== Applying bandwidth limits ===")
    applied = []
    for record in get_bandwidth_plan(scenario):
        interface_name = resolve_interface_name(record["node"], record["interface_ip"])
        clear_root_qdisc(record["node"], interface_name)
        command = build_bandwidth_qdisc_command(interface_name, record["bandwidth_mbps"])
        run_command(["docker", "exec", record["node"]] + command, check=True)
        applied.append(
            {
                **record,
                "interface": interface_name,
                "qdisc": get_qdisc_state(record["node"], interface_name),
            }
        )
    return applied


def effective_traffic(scenario, smoke_mode):
    traffic = dict(scenario["traffic"])
    if smoke_mode:
        traffic["duration_s"] = 1
        traffic["ping_count"] = min(int(traffic.get("ping_count", 3)), 2)
        if "ping_interval_s" in traffic:
            traffic["ping_interval_s"] = min(float(traffic["ping_interval_s"]), 0.2)
    return traffic


def ping_test(scenario, smoke_mode):
    traffic = effective_traffic(scenario, smoke_mode)
    destination_ip = get_destination_ip(scenario)
    cmd = ["docker", "exec", traffic["source"], "ping", "-c", str(traffic.get("ping_count", 3))]
    if "ping_interval_s" in traffic:
        cmd.extend(["-i", str(traffic["ping_interval_s"])])
    cmd.append(destination_ip)
    result = run_command(cmd, check=False)
    parsed = parse_ping_output(result.stdout)
    return parsed["packets_received"] > 0, parsed, result.stdout


def run_iperf(scenario, smoke_mode):
    traffic = effective_traffic(scenario, smoke_mode)
    destination_ip = get_destination_ip(scenario)
    cmd = [
        "docker",
        "exec",
        traffic["source"],
        "iperf3",
        "-c",
        destination_ip,
        "-t",
        str(traffic.get("duration_s", 5)),
    ]
    if traffic.get("reverse", True):
        cmd.insert(-2, "-R")
    result = run_command(cmd, check=True)
    return result.stdout


def save_metrics(
    scenario,
    output_path,
    smoke_mode,
    ping_success,
    ping_metrics,
    throughput_mbps,
    applied_impairments,
    bandwidth_controls,
):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metrics = {
        "topology": scenario["topology_name"],
        "smoke_mode": smoke_mode,
        "ping_success": ping_success,
        "configured_bandwidth_mbps": bandwidth_controls[0]["bandwidth_mbps"] if bandwidth_controls else None,
        "configured_delay_ms": max((item["delay_ms"] for item in applied_impairments), default=0),
        "configured_packet_loss_percent": max(
            (item["packet_loss_percent"] for item in applied_impairments),
            default=0,
        ),
        "delay_semantics": (
            "delay_ms is one-way delay applied on router egress interfaces selected by link definitions. "
            "Measured ping RTT is reported separately."
        ),
        "packet_loss_semantics": (
            "packet_loss_percent is one-way packet loss applied on router egress interfaces selected by link definitions. "
            "Measured ping packet loss is reported separately."
        ),
        "subnets": scenario["subnets"],
        "static_routes": scenario["routes"],
        "delay_loss_applications": applied_impairments,
        "bandwidth_controls": bandwidth_controls,
        "router_route_tables": collect_router_routes(scenario),
        "router_qdisc_state": collect_router_qdisc_state(scenario),
        "ping_packets_transmitted": ping_metrics["packets_transmitted"],
        "ping_packets_received": ping_metrics["packets_received"],
        "ping_packet_loss_percent": ping_metrics["packet_loss_percent"],
        "ping_rtt_min_ms": ping_metrics["rtt_min_ms"],
        "ping_rtt_avg_ms": ping_metrics["rtt_avg_ms"],
        "ping_rtt_max_ms": ping_metrics["rtt_max_ms"],
        "ping_rtt_mdev_ms": ping_metrics["rtt_mdev_ms"],
        "throughput_mbps": throughput_mbps,
        "theoretical_round_trip_loss_percent": theoretical_round_trip_loss_percent(
            max((item["packet_loss_percent"] for item in applied_impairments), default=0)
        ),
    }
    output_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(f"\n=== Metrics saved to {output_path} ===")
    return metrics


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--plot", type=Path, default=DEFAULT_PLOT_PATH)
    parser.add_argument("--smoke", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    scenario = load_topology_scenario(args.scenario)
    build_topology_svg(scenario, args.plot)
    cleanup(scenario)
    create_subnets(scenario)
    start_nodes(scenario)
    configure_routes(scenario)
    applied_impairments = apply_link_impairments(scenario)
    bandwidth_controls = apply_bandwidth_limits(scenario)
    ping_success, ping_metrics, _ = ping_test(scenario, args.smoke)
    if not ping_success:
        raise RuntimeError("Ping test failed for generic topology.")
    throughput_mbps = parse_throughput(run_iperf(scenario, args.smoke))
    if throughput_mbps is None:
        raise RuntimeError("Could not parse throughput from iperf output.")
    save_metrics(
        scenario,
        args.output,
        args.smoke,
        ping_success,
        ping_metrics,
        throughput_mbps,
        applied_impairments,
        bandwidth_controls,
    )


if __name__ == "__main__":
    main()
