import subprocess
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "runs" / "current"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

NETWORK_NAME = "mynet"
SERVER_NAME = "iperf_server"
CLIENT_NAME = "iperf_client"
IMAGE_NAME = "networkstatic/iperf3"


def run_command(cmd):
    """运行命令并返回 CompletedProcess"""
    print(f"\n>>> Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result


def ensure_network():
    """如果网络不存在，就创建"""
    result = run_command(["docker", "network", "ls", "--format", "{{.Name}}"])
    networks = result.stdout.splitlines()

    if NETWORK_NAME not in networks:
        print(f"Network '{NETWORK_NAME}' not found. Creating...")
        create_result = run_command(["docker", "network", "create", NETWORK_NAME])
        if create_result.returncode != 0:
            raise RuntimeError("Failed to create Docker network.")
    else:
        print(f"Network '{NETWORK_NAME}' already exists.")


def remove_container_if_exists(name):
    """如果容器已存在，就删除"""
    result = run_command(["docker", "ps", "-a", "--format", "{{.Names}}"])
    containers = result.stdout.splitlines()

    if name in containers:
        print(f"Removing existing container: {name}")
        rm_result = run_command(["docker", "rm", "-f", name])
        if rm_result.returncode != 0:
            raise RuntimeError(f"Failed to remove container {name}.")


def start_server():
    """启动 iperf3 server"""
    remove_container_if_exists(SERVER_NAME)

    result = run_command([
        "docker", "run", "-d",
        "--name", SERVER_NAME,
        "--network", NETWORK_NAME,
        IMAGE_NAME,
        "-s"
    ])

    if result.returncode != 0:
        raise RuntimeError("Failed to start iperf3 server container.")


def run_client():
    """运行 iperf3 client，并返回输出"""
    remove_container_if_exists(CLIENT_NAME)

    result = run_command([
        "docker", "run", "--rm",
        "--name", CLIENT_NAME,
        "--network", NETWORK_NAME,
        IMAGE_NAME,
        "-c", SERVER_NAME,
        "-t", "5"
    ])

    if result.returncode != 0:
        raise RuntimeError("Failed to run iperf3 client container.")

    return result.stdout


def parse_throughput(output_text):
    """
    从 iperf3 文本输出中提取 receiver 那一行的吞吐量
    例如：
    [  5]   0.00-5.00   sec  29.7 GBytes  51.1 Gbits/sec  receiver
    """
    lines = output_text.splitlines()

    for line in reversed(lines):
        if "receiver" in line:
            match = re.search(r"([\d.]+)\s+([KMG])bits/sec", line)
            if match:
                value = float(match.group(1))
                unit = match.group(2)

                factor = {"K": 1e-3, "M": 1, "G": 1e3}
                mbps = value * factor[unit]
                return round(mbps, 2)

    return None


def save_metrics(throughput_mbps):
    metrics = {
        "throughput_mbps": throughput_mbps
    }

    output_path = OUTPUT_DIR / "metrics.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print(f"Saved metrics to: {output_path}")
    print("Metrics:", metrics)


def cleanup():
    """清理 server 容器（client 用 --rm 会自动删）"""
    remove_container_if_exists(SERVER_NAME)


def main():
    print("=== Docker iperf test starting ===")

    ensure_network()
    start_server()
    output = run_client()

    throughput_mbps = parse_throughput(output)
    if throughput_mbps is None:
        raise RuntimeError("Could not parse throughput from iperf3 output.")

    save_metrics(throughput_mbps)

    cleanup()

    print("=== Docker iperf test finished ===")


if __name__ == "__main__":
    main()