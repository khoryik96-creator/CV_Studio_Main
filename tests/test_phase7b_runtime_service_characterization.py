"""Phase 7B-2 characterization of the runtime liveness/identity domain.

These assertions capture the exact behaviour of the read-only ``/status``,
``/instance``, ``/instance-id`` and ``/ping`` endpoints before and after the
logic is moved out of the legacy web shell into a composed ``cvstudio_runtime``
service.  The routes must keep their URLs, endpoint names, methods and request
guards, so the Phase 7A route contract seal is unaffected by the extraction.

Every endpoint here is read-only and deterministic on all platforms, so the
full response contracts are characterized directly.
"""

import os
from pathlib import Path
import tempfile
import unittest

_MODULE_TEMPORARY = tempfile.TemporaryDirectory(
    prefix="cvstudio-phase7b-runtime-"
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


_RUNTIME_ROUTES = {
    "/status": ({"GET"}, "status"),
    "/instance": ({"GET"}, "instance_info"),
    "/instance-id": ({"GET"}, "instance_id_text"),
    "/ping": ({"GET"}, "ping"),
}


class Phase7BRuntimeServiceCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    @staticmethod
    def _headers(request_id):
        return {
            "X-CV-Studio-Request": "1",
            "X-CV-Studio-Request-ID": request_id,
        }

    def test_runtime_routes_url_method_endpoint_and_guards_are_exact(self):
        rules = {rule.rule: rule for rule in app.app.url_map.iter_rules()}
        self.assertEqual(len(rules), 116)
        for path, (methods, endpoint) in _RUNTIME_ROUTES.items():
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

    def test_status_payload_contract_is_stable(self):
        response = self.client.get(
            "/status", headers=self._headers("phase7b-runtime-status")
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(
            set(payload),
            {
                "status",
                "version",
                "healthy",
                "root",
                "root_hash",
                "instance_id",
                "runtime_mode",
                "runtime_process",
                "pythonw_instances",
            },
        )
        self.assertEqual(payload["status"], "running")
        self.assertTrue(payload["healthy"])
        self.assertEqual(payload["version"], app._CVSTUDIO_VERSION)
        self.assertEqual(payload["root"], app._CVSTUDIO_ROOT)
        self.assertEqual(payload["root_hash"], app._CVSTUDIO_ROOT_HASH)
        self.assertEqual(payload["instance_id"], app._CVSTUDIO_INSTANCE_ID)
        self.assertIn(payload["runtime_mode"], {"native", "source"})
        self.assertEqual(payload["pythonw_instances"], 1)

    def test_instance_payload_contract_is_stable(self):
        response = self.client.get(
            "/instance", headers=self._headers("phase7b-runtime-instance")
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(
            set(payload),
            {
                "product",
                "version",
                "root",
                "root_hash",
                "instance_id",
                "pid",
                "port",
            },
        )
        self.assertEqual(payload["product"], "CV Studio")
        self.assertEqual(payload["version"], app._CVSTUDIO_VERSION)
        self.assertEqual(payload["root"], app._CVSTUDIO_ROOT)
        self.assertEqual(payload["root_hash"], app._CVSTUDIO_ROOT_HASH)
        self.assertEqual(payload["instance_id"], app._CVSTUDIO_INSTANCE_ID)
        self.assertEqual(payload["pid"], os.getpid())
        self.assertEqual(payload["port"], app._CVSTUDIO_PORT)

    def test_instance_id_is_plain_text_with_launcher_headers(self):
        response = self.client.get(
            "/instance-id", headers=self._headers("phase7b-runtime-instance-id")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["Content-Type"], "text/plain; charset=utf-8"
        )
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(
            response.get_data(as_text=True),
            "{}|{}|{}".format(
                app._CVSTUDIO_VERSION,
                app._CVSTUDIO_INSTANCE_ID,
                app._CVSTUDIO_ROOT,
            ),
        )

    def test_ping_is_empty_204(self):
        response = self.client.get(
            "/ping", headers=self._headers("phase7b-runtime-ping")
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.get_data(as_text=True), "")


if __name__ == "__main__":
    unittest.main()
