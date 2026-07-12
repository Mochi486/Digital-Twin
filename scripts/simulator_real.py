import subprocess
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCENARIO_PATH = PROJECT_ROOT / "data" / "scenario.json"
OUTPUT_PATH = PROJECT_ROOT / "runs" / "current" / "metrics.json"

NETWORK_NAME = "mynet"
SERVER_NAME = "iperf_server"
CLIENT_NAME = "iperf_client"
IMAGE_NAME = "my-iperf-tc"


def run_command(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result


def load_scenario():
    with open(SCENARIO_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_network():
    result = run_command(["docker", "network", "ls", "--format", "{{.Name}}"])
    networks = result.stdout.splitlines()
    if NETWORK_NAME not in networks:
        run_command(["docker", "network", "create", NETWORK_NAME])


def remove_container_if_exists(name):
    result = run_command(["docker", "ps", "-a", "--format", "{{.Names}}"])
    containers = result.stdout.splitlines()
    if name in containers:
        run_command(["docker", "rm", "-f", name])


def start_server():
    remove_container_if_exists(SERVER_NAME)
    result = run_command([
        "docker", "run", "-d",
        "--name", SERVER_NAME,
        "--network", NETWORK_NAME,
        "--cap-add=NET_ADMIN",
        IMAGE_NAME,
        "iperf3", "-s"
    ])
    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError("Failed to start server")


def run_client(duration_s):
    remove_container_if_exists(CLIENT_NAME)
    result = run_command([
    "docker", "run", "--rm",
    "--name", CLIENT_NAME,
    "--network", NETWORK_NAME,
    IMAGE_NAME,
    "iperf3", "-c", SERVER_NAME,
    "-R",
    "-t", str(duration_s)
    ])
    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError("Failed to run client")
    return result.stdout


def apply_network_control(bandwidth_mbps=None, delay_ms=0):
    """
    在 server 容器的 eth0 上应用网络控制：
    - bandwidth limit
    - optional delay
    """
    # 删除旧规则，避免重复添加失败
    run_command([
        "docker", "exec", SERVER_NAME,
        "tc", "qdisc", "del", "dev", "eth0", "root"
    ])

    if bandwidth_mbps is not None and delay_ms and delay_ms > 0:
        # 同时加 delay + rate
        result = run_command([
            "docker", "exec", SERVER_NAME,
            "tc", "qdisc", "add", "dev", "eth0", "root",
            "netem",
            "delay", f"{delay_ms}ms",
            "rate", f"{bandwidth_mbps}mbit"
        ])

    elif bandwidth_mbps is not None:
        # 只做 bandwidth limit
        result = run_command([
            "docker", "exec", SERVER_NAME,
            "tc", "qdisc", "add", "dev", "eth0", "root", "tbf",
            "rate", f"{bandwidth_mbps}mbit",
            "burst", "32kbit",
            "latency", "400ms"
        ])

    elif delay_ms and delay_ms > 0:
        # 只做 delay
        result = run_command([
            "docker", "exec", SERVER_NAME,
            "tc", "qdisc", "add", "dev", "eth0", "root",
            "netem",
            "delay", f"{delay_ms}ms"
        ])

    else:
        return

    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError("Failed to apply network control.")

def parse_throughput(output_text):
    lines = output_text.splitlines()
    for line in reversed(lines):
        if "receiver" in line:
            match = re.search(r"([\d.]+)\s+([KMG])bits/sec", line)
            if match:
                value = float(match.group(1))
                unit = match.group(2)
                factor = {"K": 1e-3, "M": 1, "G": 1e3}
                return round(value * factor[unit], 2)
    return None


def save_metrics(throughput_mbps):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    metrics = {
        "throughput_mbps": throughput_mbps
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)


def cleanup():
    remove_container_if_exists(SERVER_NAME)


def main():
    scenario = load_scenario()

    traffic = scenario.get("traffic", {})
    links = scenario.get("links", [])

    duration_s = traffic.get("duration_s", 5)

    if not links:
        raise RuntimeError("No links found in scenario.json")

    main_link = links[0]
    bandwidth_mbps = main_link.get("bandwidth_mbps", None)
    delay_ms = main_link.get("delay_ms", 0)

    ensure_network()
    start_server()

    if bandwidth_mbps is not None:
        apply_network_control(bandwidth_mbps, delay_ms)

    output = run_client(duration_s)

    throughput_mbps = parse_throughput(output)
    if throughput_mbps is None:
        raise RuntimeError("Could not parse throughput")

    save_metrics(throughput_mbps)
    cleanup()

    print("Simulation finished.")
    print("Throughput:", throughput_mbps, "Mbps")


if __name__ == "__main__":
    main()