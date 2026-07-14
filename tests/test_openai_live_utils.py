import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from openai_live_utils import (
    choose_fallback_model,
    parse_compatible_model_candidates,
    probe_model_capabilities,
    redact_data,
    redact_text,
    request_structured_scenario,
    resolve_openai_model,
    sanitize_provider_host,
)


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self):
        return self._payload


class FakeClient:
    def __init__(self):
        self.responses = self
        self.chat = type("ChatNamespace", (), {"completions": self})()

    def create(self, **kwargs):
        if "text" in kwargs:
            return FakeResponse(
                {
                    "id": "resp_123",
                    "created_at": "2026-07-14T00:00:00Z",
                    "usage": {"input_tokens": 10, "output_tokens": 20},
                    "output_text": '{"nodes":[{"id":"node-1","role":"client"},{"id":"node-2","role":"server"}],"links":[{"source":"node-1","target":"node-2","bandwidth_mbps":20,"delay_ms":0,"packet_loss_percent":0}],"traffic":{"source":"node-1","destination":"node-2","protocol":"tcp","duration_s":2,"ping_count":2,"reverse":true}}',
                }
            )
        raise RuntimeError("chat_json_schema unsupported in fake client")


class FallbackClient:
    def __init__(self):
        self.responses = self
        self.chat = type("ChatNamespace", (), {"completions": self})()

    def create(self, **kwargs):
        if "text" in kwargs:
            raise RuntimeError("responses unsupported")
        response_format = kwargs.get("response_format")
        if response_format == {"type": "json_object"}:
            return FakeResponse(
                {
                    "id": "chat_456",
                    "created_at": "2026-07-14T00:00:00Z",
                    "usage": {"prompt_tokens": 11, "completion_tokens": 21},
                    "choices": [
                        {
                            "message": {
                                "content": '{"nodes":[{"id":"node-1","role":"client"},{"id":"node-2","role":"server"}],"links":[{"source":"node-1","target":"node-2","bandwidth_mbps":20,"delay_ms":0,"packet_loss_percent":0}],"traffic":{"source":"node-1","destination":"node-2","protocol":"tcp","duration_s":2,"ping_count":2,"reverse":true}}'
                            }
                        }
                    ],
                }
            )
        raise RuntimeError("unsupported endpoint")


class OpenAiLiveUtilsTests(unittest.TestCase):
    def test_redact_text_masks_key_like_values(self):
        value = "Authorization: Bearer sk-secret-token"
        redacted = redact_text(value)
        self.assertNotIn("sk-secret-token", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_redact_data_masks_nested_key_assignments(self):
        payload = {"error": {"message": "OPENAI_API_KEY=sk-secret"}}
        redacted = redact_data(payload)
        self.assertNotIn("sk-secret", redacted["error"]["message"])
        self.assertIn("[REDACTED]", redacted["error"]["message"])

    def test_choose_fallback_model_prefers_supported_order(self):
        model = choose_fallback_model(["gpt-4o", "gpt-5"])
        self.assertEqual(model, "gpt-5")

    def test_resolve_openai_model_prefers_cli_when_env_missing(self):
        self.assertEqual(resolve_openai_model("gpt-4.1"), "gpt-4.1")

    def test_parse_compatible_candidates_preserves_priority(self):
        candidates = parse_compatible_model_candidates("qwen3.7-plus deepseek-v4-pro")
        self.assertEqual(candidates[0], "qwen3.7-max-2026-06-08")
        self.assertIn("qwen3.7-plus", candidates)

    def test_sanitize_provider_host_strips_path(self):
        self.assertEqual(sanitize_provider_host("https://example.test/v1/chat/completions"), "example.test")

    def test_request_structured_scenario_supports_responses_json_schema(self):
        result = request_structured_scenario(
            FakeClient(),
            "prompt",
            "qwen3.7-max",
            "system",
            "responses_json_schema",
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["structured_output"]["nodes"][0]["id"], "node-1")

    def test_probe_model_capabilities_stops_after_first_success(self):
        matrix = probe_model_capabilities(FakeClient(), "qwen3.7-max", "system")
        self.assertEqual(len(matrix), 1)
        self.assertEqual(matrix[0]["endpoint_type"], "responses_json_schema")
        self.assertEqual(matrix[0]["request_status"], "ok")

    def test_probe_model_capabilities_falls_back_to_json_object(self):
        matrix = probe_model_capabilities(FallbackClient(), "qwen3.7-max", "system")
        self.assertEqual(matrix[-1]["endpoint_type"], "chat_json_object")
        self.assertEqual(matrix[-1]["request_status"], "ok")


if __name__ == "__main__":
    unittest.main()
