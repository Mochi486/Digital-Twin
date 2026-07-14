import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from openai_live_utils import choose_fallback_model, redact_data, redact_text, resolve_openai_model


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


if __name__ == "__main__":
    unittest.main()
