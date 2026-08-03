"""Phase 7B-4 characterization of the AI secret-store management domain.

These assertions capture the exact behaviour of the ``/secure-secrets/info``,
``/secure-secrets/save`` and ``/secure-secrets/clear`` endpoints before and
after the logic is moved out of the legacy web shell into a composed
``cvstudio_secrets`` service.  The routes must keep their URLs, endpoint names,
methods and request guards, so the Phase 7A route contract seal is unaffected.

The save/clear endpoints mutate the shared, machine-bound AI secret store and
call the real secure save/delete primitives.  To keep the tests side-effect
free, ``setUp`` swaps the shared ``_ai_secret_store`` for a fresh dict and the
``_cv_secure_save``/``_cv_secure_delete`` primitives for in-memory fakes, then
restores them in ``tearDown`` -- the same global-rebinding pattern the Phase 4
characterization tests use.  Because the service resolves those module globals
through injected callbacks at call time, the identical test exercises the route
logic before and after the extraction.
"""

import os
from pathlib import Path
import tempfile
import unittest

_MODULE_TEMPORARY = tempfile.TemporaryDirectory(
    prefix="cvstudio-phase7b-secrets-"
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


_SECRET_ROUTES = {
    "/secure-secrets/info": ({"GET"}, "secure_secrets_info"),
    "/secure-secrets/save": ({"POST"}, "secure_secrets_save"),
    "/secure-secrets/clear": ({"POST"}, "secure_secrets_clear"),
}


class Phase7BSecretsServiceCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self._original_store = app._ai_secret_store
        self._original_save = app._cv_secure_save
        self._original_delete = app._cv_secure_delete
        self.saved = []
        self.deleted = []

        def fake_save(service, record):
            self.saved.append((service, dict(record)))
            return "test_backend_store"

        def fake_delete(service):
            self.deleted.append(service)
            return None

        app._ai_secret_store = {}
        app._cv_secure_save = fake_save
        app._cv_secure_delete = fake_delete
        self.client = app.app.test_client()

    def tearDown(self):
        app._ai_secret_store = self._original_store
        app._cv_secure_save = self._original_save
        app._cv_secure_delete = self._original_delete

    @staticmethod
    def _headers(request_id):
        return {
            "X-CV-Studio-Request": "1",
            "X-CV-Studio-Request-ID": request_id,
        }

    def test_secret_routes_url_method_endpoint_and_guards_are_exact(self):
        rules = {rule.rule: rule for rule in app.app.url_map.iter_rules()}
        self.assertEqual(len(rules), 116)
        for path, (methods, endpoint) in _SECRET_ROUTES.items():
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

    def test_info_reports_every_slot_unconfigured_by_default(self):
        response = self.client.get(
            "/secure-secrets/info", headers=self._headers("phase7b-secrets-info")
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(set(payload), {"configured", "storage"})
        self.assertEqual(set(payload["configured"]), set(app._AI_SECRET_SLOTS))
        self.assertTrue(all(v is False for v in payload["configured"].values()))
        self.assertEqual(payload["storage"], "backend_secure_store")

    def test_save_persists_known_slot_and_reports_backend(self):
        slot = sorted(app._AI_SECRET_SLOTS)[0]
        response = self.client.post(
            "/secure-secrets/save",
            json={"secrets": {slot: "a-secret-value"}},
            headers=self._headers("phase7b-secrets-save"),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["configured"][slot])
        self.assertEqual(payload["storage"], "test_backend_store")
        self.assertEqual(app._ai_secret_store[slot], "a-secret-value")
        # Exactly one secure_save of the persisted slot map occurred.
        self.assertEqual(len(self.saved), 1)
        self.assertEqual(self.saved[0][0], "ai")
        self.assertEqual(self.saved[0][1], {slot: "a-secret-value"})

    def test_save_ignores_unknown_slots(self):
        response = self.client.post(
            "/secure-secrets/save",
            json={"secrets": {"totally_unknown_slot": "x"}},
            headers=self._headers("phase7b-secrets-save-unknown"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("totally_unknown_slot", response.get_json()["configured"])
        self.assertNotIn("totally_unknown_slot", app._ai_secret_store)

    def test_save_clear_blank_removes_slot(self):
        slot = sorted(app._AI_SECRET_SLOTS)[0]
        app._ai_secret_store[slot] = "existing"
        response = self.client.post(
            "/secure-secrets/save",
            json={"secrets": {slot: ""}, "clear_blank": True},
            headers=self._headers("phase7b-secrets-save-blank"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["configured"][slot])
        self.assertNotIn(slot, app._ai_secret_store)

    def test_clear_removes_requested_slot(self):
        slot = sorted(app._AI_SECRET_SLOTS)[0]
        other = sorted(app._AI_SECRET_SLOTS)[1]
        app._ai_secret_store[slot] = "one"
        app._ai_secret_store[other] = "two"
        response = self.client.post(
            "/secure-secrets/clear",
            json={"slots": [slot]},
            headers=self._headers("phase7b-secrets-clear"),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload["configured"][slot])
        self.assertTrue(payload["configured"][other])
        self.assertNotIn(slot, app._ai_secret_store)
        # A remaining secret means the store is re-persisted, not deleted.
        self.assertEqual(self.deleted, [])
        self.assertTrue(self.saved)

    def test_clear_deletes_backend_when_no_secrets_remain(self):
        slot = sorted(app._AI_SECRET_SLOTS)[0]
        app._ai_secret_store[slot] = "only"
        response = self.client.post(
            "/secure-secrets/clear",
            json={"slots": [slot]},
            headers=self._headers("phase7b-secrets-clear-all"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["configured"][slot])
        self.assertEqual(self.deleted, ["ai"])


if __name__ == "__main__":
    unittest.main()
