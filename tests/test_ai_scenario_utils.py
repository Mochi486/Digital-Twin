import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from ai_scenario_utils import (
    build_validation_gate_report,
    build_openai_text_format,
    count_simple_paths,
    find_forbidden_content,
    infer_prompt_constraints,
    mock_generate_abstract_scenario,
    validate_prompt_constraints,
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

    def test_disconnected_topology_rejected_before_execution(self):
        prompt = "invalid topology"
        invalid = {
            "nodes": [{"id": "node-1", "role": "client"}, {"id": "node-2", "role": "router"}, {"id": "node-3", "role": "server"}],
            "links": [{"source": "node-1", "target": "node-2"}],
            "traffic": {"source": "node-1", "destination": "node-3", "protocol": "tcp", "duration_s": 2, "ping_count": 4, "reverse": True},
        }
        validation = validate_and_project_generated_scenario(invalid, prompt)
        self.assertFalse(validation["valid"])
        self.assertIn("Topology is disconnected", validation["projection_validation"]["errors"][0])

    def test_illegal_role_rejected(self):
        invalid = {
            "nodes": [{"id": "node-1", "role": "client"}, {"id": "node-2", "role": "switch"}],
            "links": [{"source": "node-1", "target": "node-2"}],
            "traffic": {"source": "node-1", "destination": "node-2", "protocol": "tcp", "duration_s": 2, "ping_count": 4, "reverse": True},
        }
        validation = validate_and_project_generated_scenario(invalid, "invalid")
        self.assertFalse(validation["valid"])
        self.assertIn("role must be one of", validation["schema_validation"]["errors"][0])

    def test_over_node_limit_rejected(self):
        invalid = {
            "nodes": [{"id": f"node-{index}", "role": "router"} for index in range(1, 12)],
            "links": [{"source": f"node-{index}", "target": f"node-{index + 1}"} for index in range(1, 11)],
            "traffic": {"source": "node-1", "destination": "node-11", "protocol": "tcp", "duration_s": 2, "ping_count": 4, "reverse": True},
        }
        invalid["nodes"][0]["role"] = "client"
        invalid["nodes"][-1]["role"] = "server"
        validation = validate_and_project_generated_scenario(invalid, "invalid")
        self.assertFalse(validation["valid"])
        self.assertIn("nodes count must be between", validation["semantic_validation"]["errors"][0])

    def test_invalid_impairment_ranges_rejected(self):
        invalid = {
            "nodes": [{"id": "node-1", "role": "client"}, {"id": "node-2", "role": "server"}],
            "links": [{"source": "node-1", "target": "node-2", "bandwidth_mbps": -5, "delay_ms": 999, "packet_loss_percent": 40}],
            "traffic": {"source": "node-1", "destination": "node-2", "protocol": "tcp", "duration_s": 2, "ping_count": 4, "reverse": True},
        }
        validation = validate_and_project_generated_scenario(invalid, "invalid")
        self.assertFalse(validation["valid"])
        self.assertTrue(validation["schema_validation"]["errors"] or validation["semantic_validation"]["errors"])

    def test_forbidden_command_content_rejected(self):
        invalid = {
            "nodes": [{"id": "docker-run", "role": "client"}, {"id": "node-2", "role": "server"}],
            "links": [{"source": "docker-run", "target": "node-2"}],
            "traffic": {
                "source": "docker-run",
                "destination": "node-2",
                "protocol": "tcp",
                "duration_s": 2,
                "ping_count": 4,
                "reverse": True,
            },
        }
        validation = validate_and_project_generated_scenario(invalid, "invalid")
        self.assertFalse(validation["valid"])
        findings = find_forbidden_content(invalid)
        self.assertTrue(findings)

    def test_schema_mismatch_rejected(self):
        invalid = ["not", "an", "object"]
        validation = validate_and_project_generated_scenario(invalid, "invalid")
        self.assertFalse(validation["valid"])
        self.assertEqual(validation["schema_validation"]["errors"][0], "Scenario must be a JSON object.")

    def test_validation_gate_report_marks_duplicate_link_failure(self):
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
        report = build_validation_gate_report(invalid, "invalid")
        self.assertEqual(report["gates"]["duplicate_link_validation"], "failed")
        self.assertEqual(report["gates"]["deterministic_addressing"], "failed")

    def test_prompt_constraint_validation_enforces_alternative_paths(self):
        candidate = {
            "nodes": [
                {"id": "node-1", "role": "client"},
                {"id": "node-2", "role": "router"},
                {"id": "node-3", "role": "router"},
                {"id": "node-4", "role": "router"},
                {"id": "node-5", "role": "router"},
                {"id": "node-6", "role": "server"},
            ],
            "links": [
                {"source": "node-1", "target": "node-2", "bandwidth_mbps": 20, "delay_ms": 10, "packet_loss_percent": 0},
                {"source": "node-2", "target": "node-3", "bandwidth_mbps": 20, "delay_ms": 10, "packet_loss_percent": 0},
                {"source": "node-3", "target": "node-4", "bandwidth_mbps": 20, "delay_ms": 10, "packet_loss_percent": 0},
                {"source": "node-4", "target": "node-5", "bandwidth_mbps": 20, "delay_ms": 10, "packet_loss_percent": 0},
                {"source": "node-5", "target": "node-6", "bandwidth_mbps": 20, "delay_ms": 10, "packet_loss_percent": 0},
            ],
            "traffic": {"source": "node-1", "destination": "node-6", "protocol": "tcp", "duration_s": 2, "ping_count": 4, "reverse": True},
        }
        prompt = (
            "Create a connected six-node routed network topology with one client, "
            "one server, four routers, two alternative paths, 20 Mbps bandwidth, "
            "10 ms one-way delay, 0 percent packet loss, and one TCP traffic flow "
            "from the client to the server."
        )
        validation = validate_prompt_constraints(candidate, prompt)
        self.assertFalse(validation["valid"])
        self.assertIn("alternative client-to-server paths", validation["errors"][0])

    def test_count_simple_paths_finds_two_paths(self):
        adjacency = {
            "node-1": {"node-2", "node-3"},
            "node-2": {"node-1", "node-4"},
            "node-3": {"node-1", "node-4"},
            "node-4": {"node-2", "node-3"},
        }
        self.assertEqual(count_simple_paths(adjacency, "node-1", "node-4", limit=2), 2)


if __name__ == "__main__":
    unittest.main()
