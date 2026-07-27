import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from minimal_rl_path_control import (  # noqa: E402
    PATHS,
    QLearningAgent,
    REWARD_DEFINITION,
    run_experiment,
    state_from_metrics,
)


class MinimalRlPathControlTests(unittest.TestCase):
    def test_state_includes_all_observations_and_current_path(self):
        state = state_from_metrics({"rtt_ms": 22, "loss_percent": 0, "throughput_mbps": 19}, "A")
        self.assertEqual(state, ("low", "none", "high", "A"))

    def test_q_learning_updates_selected_action(self):
        agent = QLearningAgent(seed=1, epsilon=0)
        state = ("low", "none", "high", "A")
        agent.update(state, "B", 10, state)
        self.assertGreater(agent.values[state]["B"], 0)

    def test_mock_experiment_is_repeatable_and_changes_phase(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            a = run_experiment(20, Path(first), seed=99, docker=False)
            b = run_experiment(20, Path(second), seed=99, docker=False)
            self.assertEqual(a["selected_path_counts"], b["selected_path_counts"])
            self.assertEqual(a["q_learning"], b["q_learning"])
            self.assertEqual(a["topology_node_count"], 6)
            self.assertEqual(PATHS["A"], ["r1", "r2", "r4"])
            self.assertIn("throughput_mbps", REWARD_DEFINITION)
            rows = json.loads((Path(first) / "episodes.json").read_text(encoding="utf-8"))
            self.assertEqual({row["phase"] for row in rows}, {"phase-1-a-preferred", "phase-2-b-preferred"})
            self.assertEqual(len(rows), 20)


if __name__ == "__main__":
    unittest.main()
