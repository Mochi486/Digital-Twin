import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from routed_delay_utils import (
    build_bandwidth_qdisc_command,
    build_netem_qdisc_command,
    get_configured_packet_loss_percent,
    parse_ping_output,
    parse_throughput,
    summarize_numeric,
    theoretical_round_trip_loss_percent,
    validate_scenario_impairments,
    validate_scenario_packet_loss,
    validate_scenario_delay,
)


class RoutedDelayUtilsTests(unittest.TestCase):
    def test_validate_non_negative_delay(self):
        scenario = {
            "links": [
                {
                    "network": "net_router_server",
                    "bandwidth_mbps": 20,
                    "delay_ms": 10,
                    "packet_loss_percent": 3,
                }
            ]
        }
        self.assertEqual(validate_scenario_delay(scenario), 10)
        self.assertEqual(validate_scenario_packet_loss(scenario), 3)
        self.assertEqual(validate_scenario_impairments(scenario), (10, 3))
        self.assertEqual(get_configured_packet_loss_percent(scenario), 3)

        scenario["links"][0]["delay_ms"] = -1
        with self.assertRaises(ValueError):
            validate_scenario_delay(scenario)
        scenario["links"][0]["delay_ms"] = 10
        scenario["links"][0]["packet_loss_percent"] = 101
        with self.assertRaises(ValueError):
            validate_scenario_packet_loss(scenario)

    def test_parse_ping_output(self):
        output = """
3 packets transmitted, 3 received, 0% packet loss, time 2239ms
rtt min/avg/max/mdev = 0.058/0.090/0.108/0.022 ms
"""
        parsed = parse_ping_output(output)
        self.assertEqual(parsed["packets_transmitted"], 3)
        self.assertEqual(parsed["packets_received"], 3)
        self.assertEqual(parsed["packet_loss_percent"], 0.0)
        self.assertEqual(parsed["rtt_avg_ms"], 0.09)

    def test_parse_ping_output_with_loss(self):
        output = """
100 packets transmitted, 96 received, 4% packet loss, time 6034ms
rtt min/avg/max/mdev = 0.044/0.093/0.183/0.029 ms
"""
        parsed = parse_ping_output(output)
        self.assertEqual(parsed["packets_transmitted"], 100)
        self.assertEqual(parsed["packets_received"], 96)
        self.assertEqual(parsed["packet_loss_percent"], 4.0)
        self.assertEqual(parsed["rtt_max_ms"], 0.183)

    def test_statistics(self):
        summary = summarize_numeric([1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertEqual(summary["mean"], 3.0)
        self.assertEqual(summary["sample_std"], 1.581)
        self.assertEqual(summary["min"], 1.0)
        self.assertEqual(summary["max"], 5.0)

    def test_qdisc_command_generation(self):
        self.assertEqual(
            build_netem_qdisc_command("eth1", 30, 5),
            [
                "tc",
                "qdisc",
                "replace",
                "dev",
                "eth1",
                "root",
                "netem",
                "delay",
                "30ms",
                "loss",
                "5%",
            ],
        )
        self.assertEqual(
            build_netem_qdisc_command("eth1", 0, 3),
            ["tc", "qdisc", "replace", "dev", "eth1", "root", "netem", "loss", "3%"],
        )
        self.assertEqual(
            build_bandwidth_qdisc_command("eth0", 20),
            [
                "tc",
                "qdisc",
                "replace",
                "dev",
                "eth0",
                "root",
                "tbf",
                "rate",
                "20mbit",
                "burst",
                "32kbit",
                "latency",
                "400ms",
            ],
        )

    def test_parse_throughput(self):
        output = """
[  5]   0.00-5.02   sec  11.5 MBytes  19.2 Mbits/sec                  receiver
"""
        self.assertEqual(parse_throughput(output), 19.2)

    def test_theoretical_round_trip_loss(self):
        self.assertEqual(theoretical_round_trip_loss_percent(0), 0.0)
        self.assertEqual(theoretical_round_trip_loss_percent(1), 1.99)
        self.assertEqual(theoretical_round_trip_loss_percent(5), 9.75)


if __name__ == "__main__":
    unittest.main()
