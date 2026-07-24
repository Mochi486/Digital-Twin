import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from summarize_rl_docker_supplement import POLICIES, mean_std_ci


class RlDockerSupplementTests(unittest.TestCase):
    def test_confidence_interval_summary_is_deterministic(self):
        self.assertEqual(mean_std_ci([1.0, 2.0, 3.0])["mean"], 2.0)
        self.assertGreater(mean_std_ci([1.0, 2.0, 3.0])["ci95"], 0.0)

    def test_checkpoint_has_unique_complete_policy_indices(self):
        root = Path(__file__).resolve().parent.parent
        checkpoint = json.loads((root / "runs/final-evaluation/rl-docker-supplement/checkpoint.json").read_text())
        for policy in POLICIES:
            episodes = [row["episode"] for row in checkpoint["policy_progress"][policy]]
            self.assertEqual(episodes, list(range(1, 21)))
            self.assertEqual(len({row["phase"] for row in checkpoint["policy_progress"][policy]}), 2)
            self.assertTrue(all(all(check["matched"] for check in row["route_checks"]) for row in checkpoint["policy_progress"][policy]))


if __name__ == "__main__":
    unittest.main()
