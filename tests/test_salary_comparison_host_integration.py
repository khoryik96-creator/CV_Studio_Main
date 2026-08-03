"""Host-side integration contract for the Salary Comparison blueprint.

These tests assert that the CV Studio web shell wires the vendored
``salary_comparison`` module to the shared, machine-bound AI secret store so a
provider key is resolved on the server and never sent to (or accepted from) the
browser, and that the paid AI rule-preview endpoint is protected by the same
AI-spend browser-session guard as CV Studio's other paid AI routes.
"""

import os
from pathlib import Path
import tempfile
import unittest

from owner_build_tools.build_protected import write_test_receipt


ROOT = Path(__file__).resolve().parents[1]

_MODULE_TEMPORARY = tempfile.TemporaryDirectory(
    prefix="cvstudio-salary-host-"
)
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


class SalaryComparisonHostIntegrationTests(unittest.TestCase):
    def test_paid_rule_preview_requires_ai_spend_browser_session(self):
        self.assertIn(
            "/salary-comparison/api/rules/preview", app._AI_SPEND_EXACT_PATHS
        )

    def test_hosted_salary_page_hides_key_field_and_flags_host_managed(self):
        client = app.app.test_client()
        response = client.get("/salary-comparison/")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        # Host-managed: the page must not prompt for a provider key and must
        # signal server-side key resolution to its script.
        self.assertIn("window.SALARY_HOST_MANAGED = true", html)
        self.assertIn('id="rule_api_key" type="hidden"', html)
        self.assertNotIn('id="rule_api_key" type="password"', html)

    def test_key_resolver_is_wired_into_the_blueprint(self):
        resolver = app.app.config.get("SALARY_COMPARISON_KEY_RESOLVER")
        self.assertTrue(callable(resolver))

    def test_resolver_returns_the_shared_stored_provider_key(self):
        resolver = app.app.config["SALARY_COMPARISON_KEY_RESOLVER"]
        original = dict(app._ai_secret_store)
        try:
            app._ai_secret_store["main_deepseek"] = "STORED-DEEPSEEK-KEY"
            app._ai_secret_store["main_anthropic"] = "STORED-CLAUDE-KEY"
            self.assertEqual(resolver("deepseek"), "STORED-DEEPSEEK-KEY")
            self.assertEqual(resolver("claude"), "STORED-CLAUDE-KEY")
        finally:
            app._ai_secret_store.clear()
            app._ai_secret_store.update(original)

    def test_resolver_returns_empty_when_no_key_is_stored(self):
        resolver = app.app.config["SALARY_COMPARISON_KEY_RESOLVER"]
        original = dict(app._ai_secret_store)
        try:
            app._ai_secret_store.pop("main_deepseek", None)
            self.assertEqual(resolver("deepseek"), "")
        finally:
            app._ai_secret_store.clear()
            app._ai_secret_store.update(original)


if __name__ == "__main__":
    unittest.main()
