"""Characterization tests for DeepSeek provider hardening.

Covers three behaviour-preserving robustness fixes:

1. The AI-provider error classifier distinguishes 402 (insufficient balance)
   and 422 (invalid model/parameter) from the generic request-failed code.
2. Retired/misspelled DeepSeek model names are migrated at the transport
   boundary, idempotently, without touching unrecognised (possibly newer)
   model names or other providers.
3. The ``/test`` route probes the *selected* model (not a hardcoded one) and
   reports strict-JSON compatibility, so a stale model or a structured-output
   failure is caught by the test instead of by every real feature call.
"""

import os
from pathlib import Path
import tempfile
import unittest

from owner_build_tools.build_protected import write_test_receipt


ROOT = Path(__file__).resolve().parents[1]

_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-deepseek-hardening-")
_ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["CVSTUDIO_DB_PATH"] = str(
    Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3"
)
write_test_receipt(ROOT)
try:
    import app
finally:
    if _ORIGINAL_DATABASE_OVERRIDE is None:
        os.environ.pop("CVSTUDIO_DB_PATH", None)
    else:
        os.environ["CVSTUDIO_DB_PATH"] = _ORIGINAL_DATABASE_OVERRIDE


class ErrorClassifierTests(unittest.TestCase):
    def test_402_maps_to_insufficient_balance(self):
        code, retryable, action = app._cvstudio_classify_error(
            402, "DeepSeek API error", path="/parse"
        )
        self.assertEqual(code, "AI_PROVIDER_INSUFFICIENT_BALANCE")
        self.assertFalse(retryable)
        self.assertEqual(action, "top_up_ai_balance")

    def test_insufficient_balance_message_without_status(self):
        code, _, action = app._cvstudio_classify_error(
            400, "deepseek: Insufficient Balance"
        )
        self.assertEqual(code, "AI_PROVIDER_INSUFFICIENT_BALANCE")
        self.assertEqual(action, "top_up_ai_balance")

    def test_422_maps_to_invalid_model(self):
        code, retryable, action = app._cvstudio_classify_error(
            422, "deepseek invalid model", path="/parse"
        )
        self.assertEqual(code, "AI_PROVIDER_INVALID_MODEL")
        self.assertFalse(retryable)
        self.assertEqual(action, "reset_ai_model")

    def test_model_not_found_message_maps_to_invalid_model(self):
        code, _, _ = app._cvstudio_classify_error(
            400, "openai: model not found"
        )
        self.assertEqual(code, "AI_PROVIDER_INVALID_MODEL")

    def test_auth_still_takes_priority(self):
        code, _, action = app._cvstudio_classify_error(
            401, "deepseek api key invalid"
        )
        self.assertEqual(code, "AI_PROVIDER_AUTH_REQUIRED")
        self.assertEqual(action, "open_ai_settings")

    def test_generic_provider_failure_preserved(self):
        code, retryable, action = app._cvstudio_classify_error(
            500, "deepseek server error"
        )
        self.assertEqual(code, "AI_PROVIDER_REQUEST_FAILED")
        self.assertTrue(retryable)

    def test_non_provider_402_is_not_hijacked(self):
        # 402 without any provider marker must not become an AI provider code.
        code, _, _ = app._cvstudio_classify_error(402, "some storage failure")
        self.assertNotEqual(code, "AI_PROVIDER_INSUFFICIENT_BALANCE")


class ModelMigrationTests(unittest.TestCase):
    def test_retired_names_migrate_to_flash(self):
        self.assertEqual(app._migrate_deepseek_model("deepseek-chat"), "deepseek-v4-flash")
        self.assertEqual(
            app._migrate_deepseek_model("deepseek-reasoner"), "deepseek-v4-flash"
        )

    def test_common_typo_migrates(self):
        self.assertEqual(
            app._migrate_deepseek_model("deepseek-v4-flahs"), "deepseek-v4-flash"
        )

    def test_case_and_whitespace_insensitive(self):
        self.assertEqual(
            app._migrate_deepseek_model("  DeepSeek-Chat  "), "deepseek-v4-flash"
        )

    def test_current_models_untouched(self):
        self.assertEqual(
            app._migrate_deepseek_model("deepseek-v4-flash"), "deepseek-v4-flash"
        )
        self.assertEqual(
            app._migrate_deepseek_model("deepseek-v4-pro"), "deepseek-v4-pro"
        )

    def test_unknown_future_model_preserved(self):
        # A genuinely new model we don't know about must pass through unchanged.
        self.assertEqual(
            app._migrate_deepseek_model("deepseek-v5-turbo"), "deepseek-v5-turbo"
        )

    def test_idempotent(self):
        once = app._migrate_deepseek_model("deepseek-chat")
        twice = app._migrate_deepseek_model(once)
        self.assertEqual(once, twice)

    def test_empty_is_safe(self):
        self.assertEqual(app._migrate_deepseek_model(""), "")
        self.assertEqual(app._migrate_deepseek_model(None), "")


class CallLlmMigrationTests(unittest.TestCase):
    def setUp(self):
        self._orig = app._call_deepseek

    def tearDown(self):
        app._call_deepseek = self._orig

    def test_call_llm_migrates_stale_deepseek_model(self):
        captured = {}

        def fake(api_key, payload_dict, timeout_seconds=180):
            captured["model"] = payload_dict.get("model")
            return {"content": [{"type": "text", "text": "ok"}], "usage": {}}

        app._call_deepseek = fake
        app.call_llm(
            "deepseek",
            "key",
            {"model": "deepseek-chat", "messages": [], "max_tokens": 5},
        )
        self.assertEqual(captured["model"], "deepseek-v4-flash")

    def test_call_llm_leaves_current_model(self):
        captured = {}

        def fake(api_key, payload_dict, timeout_seconds=180):
            captured["model"] = payload_dict.get("model")
            return {"content": [{"type": "text", "text": "ok"}], "usage": {}}

        app._call_deepseek = fake
        app.call_llm(
            "deepseek",
            "key",
            {"model": "deepseek-v4-pro", "messages": [], "max_tokens": 5},
        )
        self.assertEqual(captured["model"], "deepseek-v4-pro")


class TestRouteTests(unittest.TestCase):
    def setUp(self):
        self._orig = app.call_llm
        app.app.config["TESTING"] = True
        self.client = app.app.test_client()
        # Satisfy the AI-spend browser-session guard that fronts /test.
        self.client.set_cookie(
            app._AI_SPEND_SESSION_COOKIE, app._AI_SPEND_SESSION_TOKEN
        )

    def tearDown(self):
        app.call_llm = self._orig

    def test_test_route_uses_selected_model_and_reports_json_ok(self):
        captured = {}

        def fake(provider, api_key, payload):
            captured["provider"] = provider
            captured["model"] = payload.get("model")
            return {"content": [{"type": "text", "text": '{"ok": true}'}], "usage": {}}

        app.call_llm = fake
        resp = self.client.post(
            "/test",
            json={"provider": "deepseek", "api_key": "sk-test", "model": "deepseek-v4-pro"},
            headers={"X-CV-Studio-Request": "1"},
        )
        data = resp.get_json()
        self.assertTrue(data.get("ok"))
        self.assertTrue(data.get("json_ok"))
        self.assertEqual(data.get("model"), "deepseek-v4-pro")
        self.assertEqual(captured["model"], "deepseek-v4-pro")

    def test_test_route_migrates_stale_model(self):
        captured = {}

        def fake(provider, api_key, payload):
            captured["model"] = payload.get("model")
            return {"content": [{"type": "text", "text": '{"ok": true}'}], "usage": {}}

        app.call_llm = fake
        resp = self.client.post(
            "/test",
            json={"provider": "deepseek", "api_key": "sk-test", "model": "deepseek-chat"},
            headers={"X-CV-Studio-Request": "1"},
        )
        data = resp.get_json()
        self.assertEqual(data.get("model"), "deepseek-v4-flash")
        self.assertEqual(captured["model"], "deepseek-v4-flash")

    def test_test_route_json_ok_false_on_non_json(self):
        def fake(provider, api_key, payload):
            return {"content": [{"type": "text", "text": "hello there"}], "usage": {}}

        app.call_llm = fake
        resp = self.client.post(
            "/test",
            json={"provider": "deepseek", "api_key": "sk-test"},
            headers={"X-CV-Studio-Request": "1"},
        )
        data = resp.get_json()
        self.assertTrue(data.get("ok"))
        self.assertFalse(data.get("json_ok"))


if __name__ == "__main__":
    unittest.main()
