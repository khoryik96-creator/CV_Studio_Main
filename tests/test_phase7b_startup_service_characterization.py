"""Phase 7B-1 characterization of the cross-platform startup domain.

These assertions capture the exact behaviour of the ``/startup/*`` endpoints
before and after the domain logic is moved out of the legacy web shell into a
composed ``cvstudio_startup`` service.  The route URLs, endpoint names, methods
and request guards must remain byte-identical, so the Phase 7A route contract
seal is unaffected by the extraction.

The status endpoint is read-only and characterized on every platform.  The
enable/disable endpoints mutate real operating-system state (Windows ``Run``
registry value, macOS LaunchAgent) on their native platforms, so their full
behaviour is only exercised on the graceful "unsupported platform" path, which
is deterministic and side-effect free.  Native Windows/macOS behaviour is left
to a verbatim code move plus the native CI dependency gates, matching how the
rest of the suite treats platform-specific runtime code.
"""

import os
from pathlib import Path
import platform
import tempfile
import unittest

_MODULE_TEMPORARY = tempfile.TemporaryDirectory(
    prefix="cvstudio-phase7b-startup-"
)
_ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["CVSTUDIO_DB_PATH"] = str(
    Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3"
)
from owner_build_tools.build_protected import write_test_receipt

write_test_receipt(Path(__file__).resolve().parents[1])
try:
    import app
finally:
    if _ORIGINAL_DATABASE_OVERRIDE is None:
        os.environ.pop("CVSTUDIO_DB_PATH", None)
    else:
        os.environ["CVSTUDIO_DB_PATH"] = _ORIGINAL_DATABASE_OVERRIDE


_STARTUP_ROUTES = {
    "/startup/status": ({"GET"}, "startup_status"),
    "/startup/enable": ({"POST"}, "startup_enable"),
    "/startup/disable": ({"POST"}, "startup_disable"),
}

_IS_NATIVE_STARTUP_PLATFORM = platform.system() in {"Windows", "Darwin"}


class Phase7BStartupServiceCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    @staticmethod
    def _headers(request_id):
        return {
            "X-CV-Studio-Request": "1",
            "X-CV-Studio-Request-ID": request_id,
        }

    def test_startup_routes_url_method_endpoint_and_guards_are_exact(self):
        rules = {rule.rule: rule for rule in app.app.url_map.iter_rules()}
        self.assertEqual(len(rules), 116)
        for path, (methods, endpoint) in _STARTUP_ROUTES.items():
            self.assertIn(path, rules)
            self.assertEqual(rules[path].methods & {"GET", "POST"}, methods)
            self.assertEqual(rules[path].endpoint, endpoint)
        self.assertEqual(
            [item.__name__ for item in app.app.before_request_funcs.get(None, [])],
            [
                "_assign_cvstudio_request_id",
                "_reject_declared_oversize_request",
                "_reject_non_local_host_header",
                "_require_ai_spend_browser_session",
                "_reject_cross_site_unsafe_request",
            ],
        )

    def test_startup_status_response_shape_is_stable(self):
        response = self.client.get(
            "/startup/status", headers=self._headers("phase7b-startup-status")
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsInstance(payload, dict)
        self.assertIn("enabled", payload)
        self.assertIsInstance(payload["enabled"], bool)

    @unittest.skipIf(
        _IS_NATIVE_STARTUP_PLATFORM,
        "Native Windows/macOS startup mutation is validated by platform CI gates",
    )
    def test_startup_status_reports_unsupported_platform(self):
        payload = self.client.get(
            "/startup/status",
            headers=self._headers("phase7b-startup-status-unsupported"),
        ).get_json()
        self.assertEqual(
            payload, {"enabled": False, "platform": platform.system()}
        )

    @unittest.skipIf(
        _IS_NATIVE_STARTUP_PLATFORM,
        "Native Windows/macOS startup mutation is validated by platform CI gates",
    )
    def test_startup_enable_rejects_unsupported_platform(self):
        response = self.client.post(
            "/startup/enable",
            headers=self._headers("phase7b-startup-enable-unsupported"),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        # The route returns ``{"ok": False, "error": "Unsupported platform"}``;
        # the shared error post-processor enriches that into the standard
        # CV Studio envelope. Both layers must survive the extraction.
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "Unsupported platform")
        self.assertEqual(payload["message"], "Unsupported platform")
        self.assertEqual(payload["code"], "CVSTUDIO_ERROR")
        self.assertEqual(payload["severity"], "warning")
        self.assertFalse(payload["retryable"])
        self.assertIsInstance(payload["request_id"], str)
        self.assertTrue(payload["request_id"])

    @unittest.skipIf(
        _IS_NATIVE_STARTUP_PLATFORM,
        "Native Windows/macOS startup mutation is validated by platform CI gates",
    )
    def test_startup_disable_is_a_noop_on_unsupported_platform(self):
        response = self.client.post(
            "/startup/disable",
            headers=self._headers("phase7b-startup-disable-unsupported"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True})


if __name__ == "__main__":
    unittest.main()
