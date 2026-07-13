import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from prepare_wsl_docker import RULE_COMMENT, load_networks
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


if __name__ == "__main__":
    unittest.main()
