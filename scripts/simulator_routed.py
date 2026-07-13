import json
import subprocess
from pathlib import Path

from routed_delay_utils import (
    build_bandwidth_qdisc_command,
    get_configured_bandwidth_mbps,
    get_configured_delay_ms,
    get_configured_packet_loss_percent,
    build_netem_qdisc_command,
    parse_ping_output,
    parse_throughput,
    theoretical_round_trip_loss_percent,
    validate_scenario_impairments,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCENARIO_PATH = PROJECT_ROOT / "data" / "scenario_routed.json"
OUTPUT_PATH = PROJECT_ROOT / "runs" / "current" / "metrics.json"

IMAGE_NAME = "my-iperf-tc"

CLIENT = "client1"
ROUTER = "router1"
SERVER = "server1"


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


def load_scenario():
    with open(SCENARIO_PATH, "r", encoding="utf-8") as f:
        scenario = json.load(f)
    validate_scenario_impairments(scenario)
    return scenario


def cleanup():
    print("\n=== Cleaning old containers and networks ===")

    run_command(["docker", "rm", "-f", CLIENT, ROUTER, SERVER])

    scenario = load_scenario()
    for net in scenario["networks"]:
        run_command(["docker", "network", "rm", net["name"]])


def create_networks(scenario):
    print("\n=== Creating Docker networks ===")

    for net in scenario["networks"]:
        run_command(
            [
                "docker",
                "network",
                "create",
                "--subnet",
                net["subnet"],
                net["name"],
            ],
            check=True,
        )


def get_node(scenario, node_id):
    for node in scenario["nodes"]:
        if node["id"] == node_id:
            return node
    raise RuntimeError(f"Node not found: {node_id}")


def start_router(scenario):
    print("\n=== Starting router ===")

    router = get_node(scenario, ROUTER)
    interfaces = router["interfaces"]
    first_if = interfaces[0]

    run_command(
        [
            "docker",
            "run",
            "-d",
            "--name",
            ROUTER,
            "--cap-add=NET_ADMIN",
            "--sysctl",
            "net.ipv4.ip_forward=1",
            "--network",
            first_if["network"],
            "--ip",
            first_if["ip"],
            IMAGE_NAME,
            "sleep",
            "infinity",
        ],
        check=True,
    )

    for iface in interfaces[1:]:
        run_command(
            [
                "docker",
                "network",
                "connect",
                "--ip",
                iface["ip"],
                iface["network"],
                ROUTER,
            ],
            check=True,
        )


def start_server(scenario):
    print("\n=== Starting server ===")

    server = get_node(scenario, SERVER)
    router_server_network = get_router_server_network_name(scenario)

    run_command(
        [
            "docker",
            "run",
            "-d",
            "--name",
            SERVER,
            "--cap-add=NET_ADMIN",
            "--network",
            router_server_network,
            "--ip",
            server["ip"],
            IMAGE_NAME,
            "iperf3",
            "-s",
        ],
        check=True,
    )


def start_client(scenario):
    print("\n=== Starting client ===")

    client = get_node(scenario, CLIENT)
    client_router_network = get_client_router_network_name(scenario)

    run_command(
        [
            "docker",
            "run",
            "-d",
            "--name",
            CLIENT,
            "--cap-add=NET_ADMIN",
            "--network",
            client_router_network,
            "--ip",
            client["ip"],
            IMAGE_NAME,
            "sleep",
            "infinity",
        ],
        check=True,
    )


def get_client_router_network_name(scenario):
    router = get_node(scenario, ROUTER)
    return router["interfaces"][0]["network"]


def get_router_server_network_name(scenario):
    router = get_node(scenario, ROUTER)
    return router["interfaces"][1]["network"]


def configure_routes(scenario):
    print("\n=== Configuring static routes ===")

    router = get_node(scenario, ROUTER)
    client_router_ip = router["interfaces"][0]["ip"]
    router_server_ip = router["interfaces"][1]["ip"]
    client_router_subnet = next(
        net["subnet"] for net in scenario["networks"] if net["name"] == router["interfaces"][0]["network"]
    )
    router_server_subnet = next(
        net["subnet"] for net in scenario["networks"] if net["name"] == router["interfaces"][1]["network"]
    )

    run_command(
        ["docker", "exec", CLIENT, "ip", "route", "add", router_server_subnet, "via", client_router_ip],
        check=True,
    )
    run_command(
        ["docker", "exec", SERVER, "ip", "route", "add", client_router_subnet, "via", router_server_ip],
        check=True,
    )


def ping_test(scenario, destination_ip):
    print("\n=== Running ping test ===")

    traffic = scenario["traffic"]
    ping_count = str(traffic.get("ping_count", 3))
    ping_interval_s = traffic.get("ping_interval_s")
    cmd = ["docker", "exec", CLIENT, "ping", "-c", ping_count]
    if ping_interval_s is not None:
        cmd.extend(["-i", str(ping_interval_s)])
    cmd.append(destination_ip)

    result = run_command(
        cmd,
        check=False,
    )
    parsed = parse_ping_output(result.stdout)
    success = parsed["packets_received"] > 0
    return success, result.stdout, parsed


def resolve_interface_name(container_name, target_ip):
    result = run_command(
        [
            "docker",
            "exec",
            container_name,
            "ip",
            "-o",
            "-4",
            "addr",
            "show",
        ],
        check=True,
    )

    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        interface_name = fields[1]
        ip_with_prefix = fields[3]
        if ip_with_prefix.split("/")[0] == target_ip:
            return interface_name

    raise RuntimeError(f"Could not resolve interface for {container_name} IP {target_ip}")


def clear_root_qdisc(container_name, interface_name):
    run_command(
        ["docker", "exec", container_name, "tc", "qdisc", "del", "dev", interface_name, "root"],
        check=False,
    )


def apply_bandwidth_limit(scenario):
    print("\n=== Applying bandwidth limit ===")

    bandwidth_mbps = get_configured_bandwidth_mbps(scenario)
    if bandwidth_mbps is None:
        print("No bandwidth limit configured.")
        return None

    server = get_node(scenario, SERVER)
    interface_name = resolve_interface_name(SERVER, server["ip"])

    clear_root_qdisc(SERVER, interface_name)
    command = build_bandwidth_qdisc_command(interface_name, bandwidth_mbps)
    run_command(["docker", "exec", SERVER] + command, check=True)
    return interface_name


def apply_router_impairments(scenario):
    print("\n=== Applying router impairments ===")

    delay_ms = get_configured_delay_ms(scenario)
    packet_loss_percent = get_configured_packet_loss_percent(scenario)
    router = get_node(scenario, ROUTER)
    interfaces = []
    qdisc_state = {}

    if delay_ms == 0 and packet_loss_percent == 0:
        print("No router impairments configured.")
        return interfaces, qdisc_state

    for iface in router["interfaces"]:
        interface_name = resolve_interface_name(ROUTER, iface["ip"])
        interfaces.append(
            {
                "container": ROUTER,
                "network": iface["network"],
                "ip": iface["ip"],
                "interface": interface_name,
                "direction": "egress",
            }
        )
        clear_root_qdisc(ROUTER, interface_name)
        command = build_netem_qdisc_command(interface_name, delay_ms, packet_loss_percent)
        run_command(["docker", "exec", ROUTER] + command, check=True)
        qdisc_state[interface_name] = get_qdisc_state(ROUTER, interface_name)

    return interfaces, qdisc_state


def get_qdisc_state(container_name, interface_name):
    result = run_command(
        ["docker", "exec", container_name, "tc", "qdisc", "show", "dev", interface_name],
        check=True,
    )
    return result.stdout.strip()


def run_iperf(scenario):
    print("\n=== Running iperf3 TCP test ===")

    traffic = scenario["traffic"]
    destination_ip = traffic["destination_ip"]
    duration_s = str(traffic.get("duration_s", 5))
    reverse = traffic.get("reverse", True)

    cmd = [
        "docker",
        "exec",
        CLIENT,
        "iperf3",
        "-c",
        destination_ip,
        "-t",
        duration_s,
    ]

    if reverse:
        cmd.insert(-2, "-R")

    result = run_command(cmd, check=True)
    return result.stdout


def save_metrics(
    scenario,
    ping_success,
    ping_metrics,
    throughput_mbps,
    delay_interfaces,
    qdisc_state,
    server_qdisc_state,
):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    metrics = {
        "topology": scenario.get("topology_name"),
        "ping_success": ping_success,
        "configured_bandwidth_mbps": get_configured_bandwidth_mbps(scenario),
        "configured_delay_ms": get_configured_delay_ms(scenario),
        "configured_packet_loss_percent": get_configured_packet_loss_percent(scenario),
        "delay_semantics": (
            "delay_ms is one-way delay applied on router egress for both routed subnets; "
            "ping RTT is measured end-to-end and reported separately."
        ),
        "packet_loss_semantics": (
            "packet_loss_percent is one-way packet loss applied on router egress for both routed subnets; "
            "measured ping packet loss is end-to-end round-trip loss and is reported separately."
        ),
        "delay_interfaces": delay_interfaces,
        "loss_interfaces": delay_interfaces,
        "qdisc_state": qdisc_state,
        "ping_packets_transmitted": ping_metrics["packets_transmitted"],
        "ping_packets_received": ping_metrics["packets_received"],
        "ping_packet_loss_percent": ping_metrics["packet_loss_percent"],
        "ping_rtt_min_ms": ping_metrics["rtt_min_ms"],
        "ping_rtt_avg_ms": ping_metrics["rtt_avg_ms"],
        "ping_rtt_max_ms": ping_metrics["rtt_max_ms"],
        "ping_rtt_mdev_ms": ping_metrics["rtt_mdev_ms"],
        "theoretical_round_trip_loss_percent": theoretical_round_trip_loss_percent(
            get_configured_packet_loss_percent(scenario)
        ),
        "throughput_mbps": throughput_mbps,
        "bandwidth_qdisc_interface": server_qdisc_state["interface"],
        "bandwidth_qdisc_state": server_qdisc_state["qdisc"],
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print("\n=== Metrics saved ===")
    print(metrics)


def main():
    scenario = load_scenario()

    cleanup()
    create_networks(scenario)
    start_router(scenario)
    start_server(scenario)
    start_client(scenario)
    configure_routes(scenario)

    delay_interfaces, delay_qdisc_state = apply_router_impairments(scenario)
    server_bandwidth_interface = apply_bandwidth_limit(scenario)
    server_qdisc_state = {
        "interface": server_bandwidth_interface,
        "qdisc": get_qdisc_state(SERVER, server_bandwidth_interface) if server_bandwidth_interface else "",
    }

    destination_ip = scenario["traffic"]["destination_ip"]
    ping_success, _, ping_metrics = ping_test(scenario, destination_ip)

    if not ping_success:
        raise RuntimeError("Ping test failed. Routed topology is not connected.")

    iperf_output = run_iperf(scenario)
    throughput_mbps = parse_throughput(iperf_output)
    if throughput_mbps is None:
        raise RuntimeError("Could not parse throughput from iperf output.")

    qdisc_state = {
        "router_delay": delay_qdisc_state,
        "server_bandwidth": server_qdisc_state,
    }
    save_metrics(
        scenario,
        ping_success,
        ping_metrics,
        throughput_mbps,
        delay_interfaces,
        qdisc_state,
        server_qdisc_state,
    )

    print("\n=== Routed simulation finished ===")
    print("Throughput:", throughput_mbps, "Mbps")


if __name__ == "__main__":
    main()
