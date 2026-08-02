"""Phase 7B-3 characterization of the static web-asset domain.

These assertions capture the exact behaviour of the ``/vendor/<path:filename>``,
``/cv_studio_logo.png``, ``/cv_studio.ico`` and ``/favicon.ico`` endpoints
before and after the logic is moved out of the legacy web shell into a composed
``cvstudio_web_assets`` service.  The routes must keep their URLs, endpoint
names, methods and request guards, so the Phase 7A route contract seal is
unaffected by the extraction.  The vendor route's path-traversal rejection is
security-sensitive and is characterized here so the move stays verbatim.
"""

import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

_MODULE_TEMPORARY = tempfile.TemporaryDirectory(
    prefix="cvstudio-phase7b-web-assets-"
)
_ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["CVSTUDIO_DB_PATH"] = str(
    Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3"
)
from owner_build_tools.build_protected import write_test_receipt

write_test_receipt(ROOT)
try:
    import app
finally:
    if _ORIGINAL_DATABASE_OVERRIDE is None:
        os.environ.pop("CVSTUDIO_DB_PATH", None)
    else:
        os.environ["CVSTUDIO_DB_PATH"] = _ORIGINAL_DATABASE_OVERRIDE


_WEB_ASSET_ROUTES = {
    "/vendor/<path:filename>": ({"GET"}, "vendor_asset"),
    "/cv_studio_logo.png": ({"GET"}, "app_logo_png"),
    "/cv_studio.ico": ({"GET"}, "app_icon_ico"),
    "/favicon.ico": ({"GET"}, "favicon"),
}


class Phase7BWebAssetsCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    @staticmethod
    def _headers(request_id):
        return {
            "X-CV-Studio-Request": "1",
            "X-CV-Studio-Request-ID": request_id,
        }

    def test_web_asset_routes_url_method_endpoint_and_guards_are_exact(self):
        rules = {rule.rule: rule for rule in app.app.url_map.iter_rules()}
        self.assertEqual(len(rules), 108)
        for path, (methods, endpoint) in _WEB_ASSET_ROUTES.items():
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

    def test_vendor_serves_bundled_asset_bytes(self):
        response = self.client.get(
            "/vendor/cvstudio/api-transport.js",
            headers=self._headers("phase7b-web-vendor"),
        )
        self.assertEqual(response.status_code, 200)
        expected = (ROOT / "vendor" / "cvstudio" / "api-transport.js").read_bytes()
        self.assertEqual(response.get_data(), expected)

    def _assert_not_found(self, response):
        # The route returns ``{"error": "Not found"}``; the shared error
        # post-processor enriches it into the standard NOT_FOUND envelope. Both
        # layers must survive the extraction.
        self.assertEqual(response.status_code, 404)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "Not found")
        self.assertEqual(payload["message"], "Not found")
        self.assertEqual(payload["code"], "NOT_FOUND")
        self.assertIsInstance(payload["request_id"], str)
        self.assertTrue(payload["request_id"])

    def test_vendor_rejects_invalid_characters(self):
        self._assert_not_found(
            self.client.get(
                "/vendor/nope$$$.js",
                headers=self._headers("phase7b-web-vendor-bad"),
            )
        )

    def test_vendor_rejects_missing_asset(self):
        self._assert_not_found(
            self.client.get(
                "/vendor/cvstudio/does-not-exist.js",
                headers=self._headers("phase7b-web-vendor-missing"),
            )
        )

    def test_logo_and_icon_serve_exact_bytes(self):
        logo = self.client.get(
            "/cv_studio_logo.png", headers=self._headers("phase7b-web-logo")
        )
        self.assertEqual(logo.status_code, 200)
        self.assertEqual(
            logo.get_data(), (ROOT / "cv_studio_logo.png").read_bytes()
        )

        icon = self.client.get(
            "/cv_studio.ico", headers=self._headers("phase7b-web-icon")
        )
        self.assertEqual(icon.status_code, 200)
        self.assertEqual(icon.get_data(), (ROOT / "cv_studio.ico").read_bytes())

    def test_favicon_serves_the_icon_when_present(self):
        response = self.client.get(
            "/favicon.ico", headers=self._headers("phase7b-web-favicon")
        )
        self.assertEqual(response.status_code, 200)
        # cv_studio.ico exists in the source tree, so favicon serves it directly.
        self.assertEqual(
            response.get_data(), (ROOT / "cv_studio.ico").read_bytes()
        )


if __name__ == "__main__":
    unittest.main()
