import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from ai_scenario_utils import (
    build_openai_text_format,
    infer_prompt_constraints,
    mock_generate_abstract_scenario,
    validate_and_project_generated_scenario,
)


class AiScenarioUtilsTests(unittest.TestCase):
    def test_mock_linear_prompt_projects_to_valid_scenario(self):
        prompt = "Create a five-node linear routed topology with 20 Mbps bandwidth and 10 ms delay"
        candidate, raw_response = mock_generate_abstract_scenario(prompt)
        self.assertIn('"nodes"', raw_response)
        validation = validate_and_project_generated_scenario(candidate, prompt)
        self.assertTrue(validation["valid"])
        projected = validation["projected_scenario"]
        self.assertEqual(len(projected["nodes"]), 5)
        self.assertEqual(len(projected["subnets"]), 4)

    def test_redundant_prompt_produces_multiple_candidate_paths(self):
        prompt = "Create a six-node redundant routed topology with two candidate paths and 20 Mbps bandwidth"
        candidate, _ = mock_generate_abstract_scenario(prompt)
        validation = validate_and_project_generated_scenario(candidate, prompt)
        self.assertTrue(validation["valid"])
        links = validation["projected_scenario"]["links"]
        pairs = {tuple(sorted((link["source"], link["target"]))) for link in links}
        self.assertIn(("node-1", "node-2"), pairs)
        self.assertIn(("node-1", "node-3"), pairs)

    def test_invalid_generated_scenario_is_rejected_before_execution(self):
        prompt = "invalid topology"
        invalid = {
            "nodes": [{"id": "node-1", "role": "client"}, {"id": "node-2", "role": "server"}],
            "links": [
                {"source": "node-1", "target": "node-2"},
                {"source": "node-2", "target": "node-1"},
            ],
            "traffic": {
                "source": "node-1",
                "destination": "node-2",
                "protocol": "tcp",
                "duration_s": 2,
                "ping_count": 4,
                "reverse": True,
            },
        }
        validation = validate_and_project_generated_scenario(invalid, prompt)
        self.assertFalse(validation["valid"])
        self.assertIn("Duplicate link detected", validation["semantic_validation"]["errors"][0])

    def test_prompt_constraint_parsing_handles_loss(self):
        parsed = infer_prompt_constraints(
            "Create an eight-node routed topology with 20 Mbps bandwidth and 1% packet loss"
        )
        self.assertEqual(parsed["node_count"], 8)
        self.assertEqual(parsed["packet_loss_percent"], 1.0)

    def test_openai_text_format_uses_json_schema(self):
        text_format = build_openai_text_format()
        self.assertEqual(text_format["type"], "json_schema")
        self.assertTrue(text_format["strict"])
        self.assertEqual(text_format["schema"]["type"], "object")


if __name__ == "__main__":
    unittest.main()
