import json
import re
import subprocess
from pathlib import Path

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
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")

    return result


def load_scenario():
    with open(SCENARIO_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def cleanup():
    print("\n=== Cleaning old containers and networks ===")

    run_command(["docker", "rm", "-f", CLIENT, ROUTER, SERVER])

    scenario = load_scenario()
    for net in scenario["networks"]:
        run_command(["docker", "network", "rm", net["name"]])


def create_networks(scenario):
    print("\n=== Creating Docker networks ===")

    for net in scenario["networks"]:
        run_command([
            "docker", "network", "create",
            "--subnet", net["subnet"],
            net["name"]
        ], check=True)


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

    run_command([
        "docker", "run", "-d",
        "--name", ROUTER,
        "--cap-add=NET_ADMIN",
        "--network", first_if["network"],
        "--ip", first_if["ip"],
        IMAGE_NAME,
        "sleep", "infinity"
    ], check=True)

    for iface in interfaces[1:]:
        run_command([
            "docker", "network", "connect",
            "--ip", iface["ip"],
            iface["network"],
            ROUTER
        ], check=True)

    run_command([
        "docker", "exec", ROUTER,
        "sysctl", "-w", "net.ipv4.ip_forward=1"
    ], check=True)


def start_server(scenario):
    print("\n=== Starting server ===")

    server = get_node(scenario, SERVER)

    run_command([
        "docker", "run", "-d",
        "--name", SERVER,
        "--cap-add=NET_ADMIN",
        "--network", "net_router_server",
        "--ip", server["ip"],
        IMAGE_NAME,
        "iperf3", "-s"
    ], check=True)


def start_client(scenario):
    print("\n=== Starting client ===")

    client = get_node(scenario, CLIENT)

    run_command([
        "docker", "run", "-d",
        "--name", CLIENT,
        "--cap-add=NET_ADMIN",
        "--network", "net_client_router",
        "--ip", client["ip"],
        IMAGE_NAME,
        "sleep", "infinity"
    ], check=True)


def configure_routes():
    print("\n=== Configuring static routes ===")

    run_command([
        "docker", "exec", CLIENT,
        "ip", "route", "add", "10.0.2.0/24",
        "via", "10.0.1.254"
    ], check=True)

    run_command([
        "docker", "exec", SERVER,
        "ip", "route", "add", "10.0.1.0/24",
        "via", "10.0.2.254"
    ], check=True)


def ping_test(destination_ip):
    print("\n=== Running ping test ===")

    result = run_command([
        "docker", "exec", CLIENT,
        "ping", "-c", "3", destination_ip
    ])

    success = "0% packet loss" in result.stdout
    return success, result.stdout


def get_bandwidth_from_scenario(scenario):
    for link in scenario["links"]:
        if "bandwidth_mbps" in link:
            return link["bandwidth_mbps"]
    return None


def apply_bandwidth_limit(bandwidth_mbps):
    print("\n=== Applying bandwidth limit ===")

    if bandwidth_mbps is None:
        print("No bandwidth limit configured.")
        return

    # 删除旧规则，避免重复添加时报错
    run_command([
        "docker", "exec", SERVER,
        "tc", "qdisc", "del", "dev", "eth0", "root"
    ])

    run_command([
        "docker", "exec", SERVER,
        "tc", "qdisc", "add", "dev", "eth0", "root", "tbf",
        "rate", f"{bandwidth_mbps}mbit",
        "burst", "32kbit",
        "latency", "400ms"
    ], check=True)


def run_iperf(scenario):
    print("\n=== Running iperf3 TCP test ===")

    traffic = scenario["traffic"]
    destination_ip = traffic["destination_ip"]
    duration_s = str(traffic.get("duration_s", 5))
    reverse = traffic.get("reverse", True)

    cmd = [
        "docker", "exec", CLIENT,
        "iperf3", "-c", destination_ip,
        "-t", duration_s
    ]

    if reverse:
        cmd.insert(-2, "-R")

    result = run_command(cmd, check=True)
    return result.stdout


def parse_throughput(output_text):
    lines = output_text.splitlines()

    for line in reversed(lines):
        if "receiver" in line:
            match = re.search(r"([\d.]+)\s+([KMG])bits/sec", line)
            if match:
                value = float(match.group(1))
                unit = match.group(2)

                factor = {
                    "K": 1e-3,
                    "M": 1,
                    "G": 1e3
                }

                return round(value * factor[unit], 2)

    return None


def save_metrics(scenario, ping_success, throughput_mbps):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    bandwidth_mbps = get_bandwidth_from_scenario(scenario)

    metrics = {
        "topology": scenario.get("topology_name"),
        "ping_success": ping_success,
        "configured_bandwidth_mbps": bandwidth_mbps,
        "throughput_mbps": throughput_mbps
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
    configure_routes()

    destination_ip = scenario["traffic"]["destination_ip"]

    ping_success, _ = ping_test(destination_ip)

    if not ping_success:
        raise RuntimeError("Ping test failed. Routed topology is not connected.")

    bandwidth_mbps = get_bandwidth_from_scenario(scenario)
    apply_bandwidth_limit(bandwidth_mbps)

    iperf_output = run_iperf(scenario)
    throughput_mbps = parse_throughput(iperf_output)

    if throughput_mbps is None:
        raise RuntimeError("Could not parse throughput from iperf output.")

    save_metrics(scenario, ping_success, throughput_mbps)

    print("\n=== Routed simulation finished ===")
    print("Throughput:", throughput_mbps, "Mbps")


if __name__ == "__main__":
    main()