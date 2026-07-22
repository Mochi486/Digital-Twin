import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from topology_utils import (
    build_route_command,
    build_topology_svg,
    choose_path_length_samples,
    get_bandwidth_plan,
    get_link_impairment_plan,
    import_topology_zoo_gml,
    import_sndlib_native,
    select_connected_subset,
    shortest_path,
    validate_topology_scenario,
)
from germany50_selected_paths import PATHS, build_selected_path_scenario


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
        self.assertEqual(plan[0]["node"], "router2")
        self.assertEqual(plan[0]["bandwidth_mbps"], 20.0)
        self.assertEqual(plan[0]["direction"], "egress")

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

    def test_compact_scenario_auto_addressing_and_routes(self):
        scenario = {
            "topology_name": "compact-three-hop",
            "nodes": [
                {"id": "a"},
                {"id": "b"},
                {"id": "c"},
            ],
            "links": [
                {"source": "a", "target": "b", "delay_ms": 0, "packet_loss_percent": 0},
                {"source": "b", "target": "c", "delay_ms": 10, "packet_loss_percent": 0},
            ],
            "traffic": {"source": "a", "destination": "c", "protocol": "tcp", "duration_s": 2},
        }
        normalized = validate_topology_scenario(scenario)
        self.assertEqual(len(normalized["subnets"]), 2)
        self.assertEqual(len(normalized["routes"]), 2)
        self.assertEqual(normalized["nodes"][1]["type"], "router")
        self.assertEqual(normalized["resource_estimate"]["network_count"], 2)

    def test_duplicate_link_rejected(self):
        scenario = {
            "topology_name": "dup",
            "nodes": [{"id": "a"}, {"id": "b"}],
            "links": [
                {"source": "a", "target": "b"},
                {"source": "b", "target": "a"},
            ],
            "traffic": {"source": "a", "destination": "b", "protocol": "tcp", "duration_s": 1},
        }
        with self.assertRaises(ValueError):
            validate_topology_scenario(scenario)

    def test_disconnected_topology_rejected(self):
        scenario = {
            "topology_name": "disc",
            "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
            "links": [{"source": "a", "target": "b"}],
            "traffic": {"source": "a", "destination": "b", "protocol": "tcp", "duration_s": 1},
        }
        with self.assertRaises(ValueError):
            validate_topology_scenario(scenario)

    def test_shortest_path_and_path_samples(self):
        scenario = validate_topology_scenario(
            {
                "topology_name": "path-samples",
                "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}],
                "links": [
                    {"source": "a", "target": "b"},
                    {"source": "b", "target": "c"},
                    {"source": "c", "target": "d"},
                ],
                "traffic": {"source": "a", "destination": "d", "protocol": "tcp", "duration_s": 1},
            }
        )
        samples = choose_path_length_samples(scenario)
        self.assertEqual(shortest_path({"a": {"b"}, "b": {"a", "c"}, "c": {"b", "d"}, "d": {"c"}}, "a", "d"), ["a", "b", "c", "d"])
        self.assertEqual(samples["longest"]["hop_count"], 3)

    def test_select_connected_subset(self):
        scenario = validate_topology_scenario(
            {
                "topology_name": "subset",
                "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}, {"id": "e"}],
                "links": [
                    {"source": "a", "target": "b"},
                    {"source": "b", "target": "c"},
                    {"source": "c", "target": "d"},
                    {"source": "d", "target": "e"},
                ],
                "traffic": {"source": "a", "destination": "e", "protocol": "tcp", "duration_s": 1},
            }
        )
        subset = select_connected_subset(scenario, 3)
        self.assertEqual(len(subset["nodes"]), 3)
        self.assertEqual(len(subset["links"]), 2)

    def test_import_topology_zoo_gml(self):
        gml_text = """graph [
  label "Mini"
  GeoLocation "Germany"
  node [
    id 0
    label "A"
  ]
  node [
    id 1
    label "B"
  ]
  edge [
    source 0
    target 1
  ]
]"""
        with tempfile.TemporaryDirectory() as temp_dir:
            gml_path = Path(temp_dir) / "mini.gml"
            gml_path.write_text(gml_text, encoding="utf-8")
            scenario = import_topology_zoo_gml(
                gml_path,
                topology_name="mini-germany",
                source_url="https://example.test/mini.gml",
            )
            self.assertEqual(len(scenario["nodes"]), 2)
            self.assertEqual(len(scenario["links"]), 1)
            self.assertEqual(scenario["source_metadata"]["geo_location"], "Germany")

    def test_import_sndlib_native_allocates_routes_for_real_format(self):
        native_text = """?SNDlib native format; type: network; version: 1.0
# NODE SECTION
NODES (
  Alpha ( 1.0 2.0 )
  Beta ( 2.0 3.0 )
  Gamma ( 3.0 4.0 )
)
# LINK SECTION
LINKS (
  L1 ( Alpha Beta ) 0.00 0.00 0.00 0.00 ( 40.00 1.00 )
  L2 ( Beta Gamma ) 0.00 0.00 0.00 0.00 ( 40.00 1.00 )
)
# DEMAND SECTION
DEMANDS (
)
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            native_path = Path(temp_dir) / "mini.txt"
            native_path.write_text(native_text, encoding="utf-8")
            scenario = import_sndlib_native(
                native_path,
                topology_name="mini-sndlib",
                source_url="https://example.test/mini.txt",
                license_name="Example License",
                license_url="https://example.test/license",
            )
        self.assertEqual(len(scenario["nodes"]), 3)
        self.assertEqual(len(scenario["links"]), 2)
        self.assertEqual(len(scenario["subnets"]), 2)
        self.assertEqual(scenario["source_metadata"]["format"], "SNDlib native network 1.0")

    def test_selected_germany50_path_scenarios_are_bounded_and_deterministic(self):
        base = json.loads((Path(__file__).resolve().parent.parent / "data" / "scenario_germany50.json").read_text())
        scenario = build_selected_path_scenario(base, "longest")
        self.assertEqual(scenario["experiment_metadata"]["backbone_path"], PATHS["longest"])
        self.assertEqual(scenario["experiment_metadata"]["backbone_hop_count"], 9)
        self.assertEqual(len(scenario["nodes"]), 12)
        self.assertEqual(len(scenario["links"]), 11)
        self.assertEqual(scenario["traffic"]["ping_count"], 100)


if __name__ == "__main__":
    unittest.main()
