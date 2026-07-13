import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from topology_utils import (
    build_route_command,
    build_topology_svg,
    get_bandwidth_plan,
    get_link_impairment_plan,
    validate_topology_scenario,
)


def make_scenario():
    return {
        "topology_name": "client-router1-router2-server",
        "nodes": [
            {"id": "client1", "type": "client", "interfaces": [{"subnet": "net_a", "ip": "10.0.1.2"}]},
            {
                "id": "router1",
                "type": "router",
                "interfaces": [
                    {"subnet": "net_a", "ip": "10.0.1.254"},
                    {"subnet": "net_b", "ip": "10.0.2.254"},
                ],
            },
            {
                "id": "router2",
                "type": "router",
                "interfaces": [
                    {"subnet": "net_b", "ip": "10.0.2.253"},
                    {"subnet": "net_c", "ip": "10.0.3.254"},
                ],
            },
            {"id": "server1", "type": "server", "interfaces": [{"subnet": "net_c", "ip": "10.0.3.2"}]},
        ],
        "subnets": [
            {"name": "net_a", "cidr": "10.0.1.0/24"},
            {"name": "net_b", "cidr": "10.0.2.0/24"},
            {"name": "net_c", "cidr": "10.0.3.0/24"},
        ],
        "links": [
            {"source": "client1", "target": "router1", "subnet": "net_a", "delay_ms": 0, "packet_loss_percent": 0},
            {"source": "router1", "target": "router2", "subnet": "net_b", "delay_ms": 30, "packet_loss_percent": 3},
            {
                "source": "router2",
                "target": "server1",
                "subnet": "net_c",
                "bandwidth_mbps": 20,
                "delay_ms": 10,
                "packet_loss_percent": 1,
            },
        ],
        "routes": [{"node": "client1", "destination": "10.0.3.0/24", "via": "10.0.1.254"}],
        "traffic": {"source": "client1", "destination": "server1", "protocol": "tcp", "duration_s": 5},
    }


class TopologyUtilsTests(unittest.TestCase):
    def test_validate_topology_scenario(self):
        scenario = make_scenario()
        validate_topology_scenario(scenario)
        scenario["links"][1]["packet_loss_percent"] = 101
        with self.assertRaises(ValueError):
            validate_topology_scenario(scenario)

    def test_link_impairment_plan_applies_to_router_egress_only(self):
        plan = get_link_impairment_plan(make_scenario())
        self.assertEqual(len(plan), 3)
        self.assertEqual([entry["node"] for entry in plan].count("router1"), 1)
        self.assertEqual([entry["node"] for entry in plan].count("router2"), 2)
        self.assertTrue(all(entry["node"] != "client1" for entry in plan))
        self.assertTrue(all(entry["node"] != "server1" for entry in plan))

    def test_bandwidth_plan_targets_link_target_interface(self):
        plan = get_bandwidth_plan(make_scenario())
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["node"], "server1")
        self.assertEqual(plan[0]["bandwidth_mbps"], 20.0)

    def test_route_command(self):
        self.assertEqual(
            build_route_command({"destination": "10.0.3.0/24", "via": "10.0.1.254"}),
            ["ip", "route", "add", "10.0.3.0/24", "via", "10.0.1.254"],
        )

    def test_topology_svg_generation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "topology.svg"
            build_topology_svg(make_scenario(), output_path)
            self.assertTrue(output_path.exists())
            self.assertIn("client-router1-router2-server", output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
