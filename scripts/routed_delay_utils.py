import re
import statistics


def get_routed_link(scenario: dict) -> dict:
    for link in scenario.get("links", []):
        if link.get("network") == "net_router_server":
            return link
    raise ValueError("Routed link for net_router_server not found in scenario.")


def get_configured_bandwidth_mbps(scenario: dict) -> int | float | None:
    link = get_routed_link(scenario)
    return link.get("bandwidth_mbps")


def get_configured_delay_ms(scenario: dict) -> int | float:
    link = get_routed_link(scenario)
    return link.get("delay_ms", 0)


def get_configured_packet_loss_percent(scenario: dict) -> int | float:
    link = get_routed_link(scenario)
    return link.get("packet_loss_percent", 0)


def validate_scenario_delay(scenario: dict) -> int | float:
    delay_ms = get_configured_delay_ms(scenario)
    if delay_ms < 0:
        raise ValueError("delay_ms must be non-negative.")
    return delay_ms


def validate_scenario_packet_loss(scenario: dict) -> int | float:
    packet_loss_percent = get_configured_packet_loss_percent(scenario)
    if packet_loss_percent < 0 or packet_loss_percent > 100:
        raise ValueError("packet_loss_percent must be between 0 and 100.")
    return packet_loss_percent


def validate_scenario_impairments(scenario: dict) -> tuple[int | float, int | float]:
    return validate_scenario_delay(scenario), validate_scenario_packet_loss(scenario)


def parse_ping_output(output_text: str) -> dict:
    transmission_match = re.search(
        r"(?P<tx>\d+)\s+packets transmitted,\s+"
        r"(?P<rx>\d+)\s+(?:packets )?received,\s+"
        r"(?P<loss>[\d.]+)% packet loss",
        output_text,
    )
    if not transmission_match:
        raise ValueError("Could not parse ping transmission statistics.")

    rtt_match = re.search(
        r"rtt min/avg/max/(?:mdev|stddev)\s*=\s*"
        r"(?P<min>[\d.]+)/(?P<avg>[\d.]+)/(?P<max>[\d.]+)/(?P<mdev>[\d.]+)\s+ms",
        output_text,
    )

    parsed = {
        "packets_transmitted": int(transmission_match.group("tx")),
        "packets_received": int(transmission_match.group("rx")),
        "packet_loss_percent": float(transmission_match.group("loss")),
        "rtt_min_ms": None,
        "rtt_avg_ms": None,
        "rtt_max_ms": None,
        "rtt_mdev_ms": None,
    }

    if rtt_match:
        parsed.update(
            {
                "rtt_min_ms": float(rtt_match.group("min")),
                "rtt_avg_ms": float(rtt_match.group("avg")),
                "rtt_max_ms": float(rtt_match.group("max")),
                "rtt_mdev_ms": float(rtt_match.group("mdev")),
            }
        )

    return parsed


def parse_throughput(output_text: str) -> float | None:
    lines = output_text.splitlines()
    for line in reversed(lines):
        if "receiver" not in line:
            continue
        match = re.search(r"([\d.]+)\s+([KMG])bits/sec", line)
        if not match:
            continue

        value = float(match.group(1))
        unit = match.group(2)
        factor = {"K": 1e-3, "M": 1, "G": 1e3}
        return round(value * factor[unit], 2)

    return None


def build_netem_qdisc_command(
    interface_name: str,
    delay_ms: int | float,
    packet_loss_percent: int | float,
) -> list[str]:
    command = [
        "tc",
        "qdisc",
        "replace",
        "dev",
        interface_name,
        "root",
        "netem",
    ]
    if delay_ms > 0:
        command.extend(["delay", f"{delay_ms}ms"])
    if packet_loss_percent > 0:
        command.extend(["loss", f"{packet_loss_percent}%"])
    return command


def build_bandwidth_qdisc_command(
    interface_name: str, bandwidth_mbps: int | float
) -> list[str]:
    return [
        "tc",
        "qdisc",
        "replace",
        "dev",
        interface_name,
        "root",
        "tbf",
        "rate",
        f"{bandwidth_mbps}mbit",
        "burst",
        "32kbit",
        "latency",
        "400ms",
    ]


def summarize_numeric(values: list[float]) -> dict:
    if not values:
        raise ValueError("At least one numeric value is required.")

    return {
        "mean": round(statistics.mean(values), 3),
        "sample_std": round(statistics.stdev(values), 3) if len(values) > 1 else 0.0,
        "min": round(min(values), 3),
        "max": round(max(values), 3),
    }


def is_tagged_project70_rule(rule_line: str, comment_tag: str) -> bool:
    return (
        "-j ACCEPT" in rule_line
        and "-m comment" in rule_line
        and (
            f'--comment "{comment_tag}"' in rule_line
            or f"--comment {comment_tag}" in rule_line
        )
    )


def theoretical_round_trip_loss_percent(one_way_loss_percent: int | float) -> float:
    one_way_probability = float(one_way_loss_percent) / 100.0
    success_probability = (1.0 - one_way_probability) ** 2
    return round((1.0 - success_probability) * 100.0, 3)
