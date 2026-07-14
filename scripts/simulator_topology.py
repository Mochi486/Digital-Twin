import argparse
import json
import subprocess
import time
from pathlib import Path

from topology_utils import (
    build_bandwidth_qdisc_command,
    build_netem_qdisc_command,
    build_resource_estimate,
    build_route_command,
    build_topology_svg,
    get_bandwidth_plan,
    get_destination_ip,
    get_link_impairment_plan,
    get_router_nodes,
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


def count_running_resources():
    containers = run_command(["docker", "ps", "-q"], check=True).stdout.splitlines()
    networks = run_command(["docker", "network", "ls", "-q"], check=True).stdout.splitlines()
    return {
        "running_container_count": len([item for item in containers if item.strip()]),
        "running_network_count": len([item for item in networks if item.strip()]),
    }


def cleanup(scenario):
    start = time.perf_counter()
    print("\n=== Cleaning containers and subnets ===")
    for node in scenario["nodes"]:
        run_command(["docker", "rm", "-f", node["id"]], check=False)
    for subnet in scenario["subnets"]:
        run_command(["docker", "network", "rm", subnet["name"]], check=False)
    return round(time.perf_counter() - start, 3)


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
    if node["type"] == "router" or len(node["interfaces"]) > 1:
        cmd.extend(
            [
                "--sysctl",
                "net.ipv4.conf.all.rp_filter=0",
                "--sysctl",
                "net.ipv4.conf.default.rp_filter=0",
            ]
        )
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


def collect_all_node_routes(scenario):
    route_state = {}
    for node in scenario["nodes"]:
        result = run_command(["docker", "exec", node["id"], "ip", "route", "show"], check=True)
        route_state[node["id"]] = result.stdout.strip()
    return route_state


def verify_routes(scenario):
    verification = []
    for route in scenario["routes"]:
        result = run_command(["docker", "exec", route["node"], "ip", "route", "show", route["destination"]], check=True)
        route_output = result.stdout.strip()
        expected_fragment = f"{route['destination']} via {route['via']}"
        matched = expected_fragment in route_output
        verification.append(
            {
                "node": route["node"],
                "destination": route["destination"],
                "via": route["via"],
                "matched": matched,
                "route_output": route_output,
            }
        )
        if not matched:
            raise RuntimeError(
                f"Route verification failed for {route['node']} destination {route['destination']}: {route_output}"
            )
    return verification


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
        traffic["duration_s"] = min(int(traffic.get("duration_s", 5)), 1)
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
    destination_node = next(node for node in scenario["nodes"] if node["id"] == traffic["destination"])
    if destination_node["type"] != "server":
        run_command(
            [
                "docker",
                "exec",
                "-d",
                traffic["destination"],
                "sh",
                "-lc",
                "pkill iperf3 >/dev/null 2>&1 || true; iperf3 -s -1",
            ],
            check=True,
        )
        time.sleep(1)
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


def setup_topology(scenario):
    timings = {}
    start = time.perf_counter()
    create_subnets(scenario)
    timings["create_subnets_s"] = round(time.perf_counter() - start, 3)

    start = time.perf_counter()
    start_nodes(scenario)
    timings["start_nodes_s"] = round(time.perf_counter() - start, 3)

    start = time.perf_counter()
    configure_routes(scenario)
    timings["configure_routes_s"] = round(time.perf_counter() - start, 3)

    start = time.perf_counter()
    route_verification = verify_routes(scenario)
    timings["verify_routes_s"] = round(time.perf_counter() - start, 3)

    start = time.perf_counter()
    applied_impairments = apply_link_impairments(scenario)
    timings["apply_impairments_s"] = round(time.perf_counter() - start, 3)

    start = time.perf_counter()
    bandwidth_controls = apply_bandwidth_limits(scenario)
    timings["apply_bandwidth_s"] = round(time.perf_counter() - start, 3)

    timings["setup_total_s"] = round(sum(timings.values()), 3)
    return applied_impairments, bandwidth_controls, route_verification, timings


def exercise_topology(scenario, smoke_mode):
    timings = {}
    start = time.perf_counter()
    ping_success, ping_metrics, _ = ping_test(scenario, smoke_mode)
    timings["ping_s"] = round(time.perf_counter() - start, 3)
    if not ping_success:
        raise RuntimeError("Ping test failed for generic topology.")

    start = time.perf_counter()
    throughput_mbps = parse_throughput(run_iperf(scenario, smoke_mode))
    timings["iperf_s"] = round(time.perf_counter() - start, 3)
    if throughput_mbps is None:
        raise RuntimeError("Could not parse throughput from iperf output.")
    return ping_metrics, throughput_mbps, timings


def save_metrics(
    scenario,
    output_path,
    smoke_mode,
    ping_success,
    ping_metrics,
    throughput_mbps,
    applied_impairments,
    bandwidth_controls,
    route_verification,
    stage_timings,
    cleanup_time_s,
):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    resource_usage = count_running_resources()
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
        "route_verification": route_verification,
        "delay_loss_applications": applied_impairments,
        "bandwidth_controls": bandwidth_controls,
        "all_node_route_tables": collect_all_node_routes(scenario),
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
        "resource_estimate": build_resource_estimate(scenario),
        "resource_usage": resource_usage,
        "stage_timings_s": stage_timings,
        "cleanup_time_s": cleanup_time_s,
    }
    output_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(f"\n=== Metrics saved to {output_path} ===")
    return metrics


def write_dry_run(output_path: Path, scenario: dict, plot_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dry_run = {
        "topology": scenario["topology_name"],
        "resource_estimate": build_resource_estimate(scenario),
        "node_count": len(scenario["nodes"]),
        "link_count": len(scenario["links"]),
        "route_count": len(scenario["routes"]),
        "subnet_count": len(scenario["subnets"]),
        "plot_file": str(plot_path),
    }
    output_path.write_text(json.dumps(dry_run, indent=2) + "\n", encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--plot", type=Path, default=DEFAULT_PLOT_PATH)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cleanup-only", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    scenario = load_topology_scenario(args.scenario)
    build_topology_svg(scenario, args.plot)

    if args.cleanup_only:
        cleanup_time_s = cleanup(scenario)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"cleanup_time_s": cleanup_time_s}, indent=2) + "\n", encoding="utf-8")
        return

    if args.dry_run:
        write_dry_run(args.output, scenario, args.plot)
        return

    initial_cleanup_time_s = cleanup(scenario)
    try:
        applied_impairments, bandwidth_controls, route_verification, setup_timings = setup_topology(scenario)
        ping_metrics, throughput_mbps, run_timings = exercise_topology(scenario, args.smoke)
        stage_timings = {
            "initial_cleanup_s": initial_cleanup_time_s,
            **setup_timings,
            **run_timings,
        }
        save_metrics(
            scenario,
            args.output,
            args.smoke,
            True,
            ping_metrics,
            throughput_mbps,
            applied_impairments,
            bandwidth_controls,
            route_verification,
            stage_timings,
            cleanup_time_s=0.0,
        )
    finally:
        final_cleanup_time_s = cleanup(scenario)
        if args.output.exists():
            metrics = json.loads(args.output.read_text(encoding="utf-8"))
            metrics["cleanup_time_s"] = final_cleanup_time_s
            args.output.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
