import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dashboard"))
import interactive_server as dashboard


def request(**overrides):
    payload = {"scenario_id": "two-router", "source": "client1", "destination": "server1",
               "bandwidth_mbps": 20, "delay_ms": 0, "loss_percent": 0, "ping_count": 3,
               "iperf_duration_seconds": 3, "test": "ping+iperf3", "dry_run": True}
    payload.update(overrides)
    return payload


class DashboardValidationTests(unittest.TestCase):
    def test_allowlisted_templates(self):
        self.assertEqual(set(dashboard.TEMPLATES), {"direct", "routed", "two-router"})
        self.assertTrue(dashboard.template_summary("direct")["real_run_allowed"])
        self.assertFalse(dashboard.template_summary("routed")["real_run_allowed"])
        self.assertFalse(dashboard.template_summary("two-router")["real_run_allowed"])

    def test_direct_role_aliases_resolve_to_repository_nodes(self):
        _, config, selected = dashboard.validate_request(request(scenario_id="direct", source="client", destination="server"))
        self.assertEqual((config["source"], config["destination"]), ("client1", "server1"))
        self.assertEqual(selected, ["client1", "server1"])

    def test_unknown_scenario_rejected(self):
        with self.assertRaises(ValueError): dashboard.validate_request(request(scenario_id="../../etc/passwd"))

    def test_unknown_node_rejected(self):
        with self.assertRaises(ValueError): dashboard.validate_request(request(source="client1;id"))

    def test_same_endpoint_rejected(self):
        with self.assertRaises(ValueError): dashboard.validate_request(request(destination="client1"))

    def test_non_endpoint_direction_rejected(self):
        with self.assertRaises(ValueError): dashboard.validate_request(request(source="router1"))

    def test_ranges_rejected(self):
        for key, value in [("bandwidth_mbps", 0), ("bandwidth_mbps", 1001), ("delay_ms", -1),
                           ("delay_ms", 501), ("loss_percent", -1), ("loss_percent", 21),
                           ("ping_count", 21), ("iperf_duration_seconds", 31)]:
            with self.subTest(key=key, value=value):
                with self.assertRaises(ValueError): dashboard.validate_request(request(**{key: value}))

    def test_real_confirmation_required(self):
        with self.assertRaisesRegex(ValueError, "confirmation RUN"):
            dashboard.validate_request(request(scenario_id="direct", source="client", destination="server", dry_run=False))
        _, config, _ = dashboard.validate_request(request(scenario_id="direct", source="client", destination="server", dry_run=False, confirmation="RUN"))
        self.assertFalse(config["dry_run"])

    def test_malformed_types_and_command_strings_rejected(self):
        for value in ["$(id)", "1; docker ps", True]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError): dashboard.validate_request(request(bandwidth_mbps=value))

    def test_path_is_found(self):
        scenario, _, selected = dashboard.validate_request(request())
        self.assertEqual(selected, ["client1", "router1", "router2", "server1"])
        self.assertIsNone(dashboard.path_between({"nodes": [{"id": "a"}, {"id": "b"}], "links": []}, "a", "b"))

    def test_dry_run_supports_every_allowlisted_template(self):
        endpoints = {
            "direct": ("client", "server"),
            "routed": ("client1", "server1"),
            "two-router": ("client1", "server1"),
        }
        for scenario_id, (source, destination) in endpoints.items():
            with self.subTest(scenario_id=scenario_id):
                _, config, selected = dashboard.validate_request(
                    request(scenario_id=scenario_id, source=source, destination=destination)
                )
                self.assertTrue(config["dry_run"])
                self.assertGreaterEqual(len(selected), 2)

    def test_routed_and_two_router_real_runs_are_rejected(self):
        for scenario_id in ("routed", "two-router"):
            with self.subTest(scenario_id=scenario_id):
                with self.assertRaisesRegex(ValueError, "limited to the direct template"):
                    dashboard.validate_request(request(scenario_id=scenario_id, dry_run=False, confirmation="RUN"))

    def test_artifacts_are_current_run_only(self):
        old_root = dashboard.RUN_ROOT
        with tempfile.TemporaryDirectory() as temp:
            dashboard.RUN_ROOT = Path(temp)
            item = {"run_id": "abc123def456", "directory": "one", "config": {}}
            (dashboard.RUN_ROOT / "one").mkdir()
            dashboard.write_artifacts(item, {"run_id": item["run_id"], "status": "SUCCEEDED"})
            with __import__("zipfile").ZipFile(dashboard.RUN_ROOT / "one" / "bundle.zip") as bundle:
                self.assertEqual(set(bundle.namelist()), {"result.json", "result.csv", "run.log"})
        dashboard.RUN_ROOT = old_root

    def test_run_ids_match_download_allowlist(self):
        self.assertTrue(dashboard.RUN_ID.fullmatch("abc123def456"))
        self.assertFalse(dashboard.RUN_ID.fullmatch("../../etc/passwd"))

    def test_documentation_claims_are_accurate(self):
        text = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
        self.assertIn("4,224-entry", text)
        self.assertIn("threshold heuristic", text)
        self.assertIn("HTTP 429", text)
        self.assertNotIn("Streamlit remains an optional", text)


if __name__ == "__main__": unittest.main()
