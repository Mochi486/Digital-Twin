import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from prepare_wsl_docker import RULE_COMMENT, build_rule_plan, load_networks
from routed_delay_utils import is_tagged_project70_rule


class PrepareWslDockerTests(unittest.TestCase):
    def test_only_tagged_rules_match_cleanup_filter(self):
        tagged_rule = (
            f'-A PREROUTING -d 10.0.2.0/24 -i br-123456789abc '
            f'-m comment --comment "{RULE_COMMENT}" -j ACCEPT'
        )
        untagged_rule = "-A PREROUTING -d 10.0.2.0/24 -i br-123456789abc -j ACCEPT"

        self.assertTrue(is_tagged_project70_rule(tagged_rule, RULE_COMMENT))
        self.assertFalse(is_tagged_project70_rule(untagged_rule, RULE_COMMENT))

    def test_load_networks_accepts_subnets_schema(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            scenario_path = Path(temp_dir) / "scenario.json"
            scenario_path.write_text(
                '{"subnets":[{"name":"net_a","cidr":"10.0.1.0/24"}]}',
                encoding="utf-8",
            )
            self.assertEqual(
                load_networks(scenario_path),
                [{"name": "net_a", "subnet": "10.0.1.0/24"}],
            )

    def test_rule_plan_is_router_adjacent_not_full_mesh(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "scenario.json"
            path.write_text('{"subnets":[{"name":"a","cidr":"10.0.0.0/29"},{"name":"b","cidr":"10.0.0.8/29"},{"name":"c","cidr":"10.0.0.16/29"}],"nodes":[{"id":"r","type":"router"}],"links":[{"source":"r","target":"x","subnet":"a"},{"source":"r","target":"y","subnet":"b"},{"source":"r","target":"z","subnet":"c"}]}')
            self.assertEqual(len(build_rule_plan(path, load_networks(path))), 6)

    def test_rule_plan_includes_multi_interface_endpoint_access(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "scenario.json"
            path.write_text('{"subnets":[{"name":"access","cidr":"10.0.0.0/29"},{"name":"primary","cidr":"10.0.0.8/29"}],"nodes":[{"id":"client","type":"client"}],"links":[{"source":"client","target":"x","subnet":"access"},{"source":"client","target":"y","subnet":"primary"}]}')
            self.assertEqual(len(build_rule_plan(path, load_networks(path))), 2)

    def test_traffic_plan_targets_source_egress_subnet_on_reverse_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "scenario.json"
            path.write_text(
                '{"networks":[{"name":"primary","subnet":"10.0.0.0/29"},'
                '{"name":"access","subnet":"10.0.0.8/29"},'
                '{"name":"destination","subnet":"10.0.0.16/29"}],'
                '"traffic":{"source":"client","destination":"server"},'
                '"nodes":[{"id":"client","interfaces":[{"subnet":"primary"},{"subnet":"access"}]},'
                '{"id":"router","interfaces":[{"subnet":"access"},{"subnet":"destination"}]},'
                '{"id":"server","interfaces":[{"subnet":"destination"}]}],'
                '"links":[{"source":"client","target":"router","subnet":"access"},'
                '{"source":"router","target":"server","subnet":"destination"}]}'
            )
            self.assertEqual(
                build_rule_plan(path, load_networks(path)),
                [("access", "10.0.0.16/29"), ("access", "10.0.0.8/29"),
                 ("destination", "10.0.0.16/29"), ("destination", "10.0.0.8/29")],
            )


if __name__ == "__main__":
    unittest.main()
