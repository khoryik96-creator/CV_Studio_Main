import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
import io


_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-app-cache-")
_MODULE_ROOT = Path(_MODULE_TEMPORARY.name)
_ORIGINAL_LOCAL_STATE = os.environ.get("LOCALAPPDATA")
_ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["LOCALAPPDATA"] = str(_MODULE_ROOT / "local-state")
os.environ["CVSTUDIO_DB_PATH"] = str(_MODULE_ROOT / "local-state" / "cv_studio.sqlite3")

from owner_build_tools.build_protected import write_test_receipt

write_test_receipt(Path(__file__).resolve().parents[1])

import app
from cvstudio_storage import (
    CVStudioStorage,
    LeadTitleCacheRepository,
)


class Phase2AAppCacheIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.legacy_root = _MODULE_ROOT / "legacy"
        cls.legacy_root.mkdir(parents=True, exist_ok=True)
        app._LEAD_TITLE_CACHE_PATH = str(cls.legacy_root / "lead_title_cache.json")
        app._LEAD_CONTACT_CACHE_PATH = str(cls.legacy_root / "lead_contact_cache.json")
        app._SALARY_AI_CACHE_PATH = str(cls.legacy_root / "salary_component_cache.json")

    @classmethod
    def tearDownClass(cls):
        if _ORIGINAL_LOCAL_STATE is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = _ORIGINAL_LOCAL_STATE
        if _ORIGINAL_DATABASE_OVERRIDE is None:
            os.environ.pop("CVSTUDIO_DB_PATH", None)
        else:
            os.environ["CVSTUDIO_DB_PATH"] = _ORIGINAL_DATABASE_OVERRIDE
        _MODULE_TEMPORARY.cleanup()

    def setUp(self):
        app._CVSTUDIO_USAGE_REPOSITORY.clear()
        app._CVSTUDIO_LEAD_TITLE_REPOSITORY.clear()
        app._CVSTUDIO_LEAD_CONTACT_REPOSITORY.clear()
        app._CVSTUDIO_SALARY_REPOSITORY.clear()
        app._CVSTUDIO_PPC_REPOSITORY.clear()
        for path in (
            Path(app._LEAD_TITLE_CACHE_PATH),
            Path(app._LEAD_CONTACT_CACHE_PATH),
            Path(app._SALARY_AI_CACHE_PATH),
        ):
            path.unlink(missing_ok=True)

    @staticmethod
    def _write_json(path, payload):
        Path(path).write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    @staticmethod
    def _read_json(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def test_lead_title_cache_imports_once_reads_sqlite_first_and_dual_writes(self):
        legacy = {
            "entries": [
                {
                    "family": "data",
                    "evidence": ["python", "sql"],
                    "titles": ["Data Engineer"],
                    "created_at": "2026-07-01T00:00:00",
                    "hits": 1,
                }
            ]
        }
        self._write_json(app._LEAD_TITLE_CACHE_PATH, legacy)

        self.assertEqual(app._lead_title_cache_load(), legacy)
        self.assertEqual(app._lead_title_cache_load(), legacy)
        Path(app._LEAD_TITLE_CACHE_PATH).write_text("{invalid", encoding="utf-8")
        self.assertEqual(app._lead_title_cache_load(), legacy)

        changed = {
            "entries": [
                {
                    "family": "finance",
                    "evidence": ["audit"],
                    "titles": ["Finance Manager"],
                    "hits": 0,
                }
            ]
        }
        app._lead_title_cache_save(changed)
        self.assertEqual(app._CVSTUDIO_LEAD_TITLE_REPOSITORY.load(), changed)
        self.assertEqual(self._read_json(app._LEAD_TITLE_CACHE_PATH), changed)

    def test_contact_and_salary_caches_import_and_keep_legacy_json_readable(self):
        contacts = {
            "entries": {
                "profile:fixture": {
                    "verification_status": "Verified fixture",
                    "cached_at": "2026-07-01T00:00:00",
                    "hits": 1,
                }
            }
        }
        self._write_json(app._LEAD_CONTACT_CACHE_PATH, contacts)
        self.assertEqual(app._lead_contact_cache_load(), contacts)

        changed_contacts = {
            "entries": {
                "profile:fixture": {
                    "verification_status": "Verified fixture",
                    "cached_at": "2026-07-01T00:00:00",
                    "hits": 2,
                }
            }
        }
        app._lead_contact_cache_save(changed_contacts)
        self.assertEqual(app._CVSTUDIO_LEAD_CONTACT_REPOSITORY.load(), changed_contacts)
        self.assertEqual(self._read_json(app._LEAD_CONTACT_CACHE_PATH), changed_contacts)

        salary = {
            "salary-fixture": {
                "components": {"current": {"baseMonthly": 1}},
                "provider": "fixture",
                "model": "fixture-model",
                "savedAt": "2026-07-01T00:00:00Z",
            }
        }
        self._write_json(app._SALARY_AI_CACHE_PATH, salary)
        self.assertEqual(app._ja_salary_ai_cache_load(), salary)
        app._ja_salary_ai_cache_put(
            "salary-fixture-new",
            {"current": {"baseMonthly": 2}},
            "fixture",
            "fixture-model",
        )
        sqlite_salary = app._CVSTUDIO_SALARY_REPOSITORY.load()
        legacy_salary = self._read_json(app._SALARY_AI_CACHE_PATH)
        self.assertEqual(sqlite_salary, legacy_salary)
        self.assertEqual(len(sqlite_salary), 2)

    def test_corruption_route_returns_structured_recovery_and_preserves_legacy(self):
        legacy = {
            "entries": [
                {
                    "family": "fixture",
                    "evidence": ["term"],
                    "titles": ["Fixture Role"],
                }
            ]
        }
        self._write_json(app._LEAD_TITLE_CACHE_PATH, legacy)
        legacy_bytes = Path(app._LEAD_TITLE_CACHE_PATH).read_bytes()

        corrupt_database = _MODULE_ROOT / "corrupt-state" / "cv_studio.sqlite3"
        corrupt_database.parent.mkdir(parents=True, exist_ok=True)
        corrupt_database.write_bytes(b"not-a-sqlite-database")
        corrupt_storage = CVStudioStorage(corrupt_database)

        original_storage = app._CVSTUDIO_STORAGE
        original_repository = app._CVSTUDIO_LEAD_TITLE_REPOSITORY
        app._CVSTUDIO_STORAGE = corrupt_storage
        app._CVSTUDIO_LEAD_TITLE_REPOSITORY = LeadTitleCacheRepository(corrupt_storage)
        try:
            response = app.app.test_client().get(
                "/lead-finder/title-cache/stats",
                headers={"X-CV-Studio-Request-ID": "phase2a-corrupt-fixture"},
            )
        finally:
            app._CVSTUDIO_STORAGE = original_storage
            app._CVSTUDIO_LEAD_TITLE_REPOSITORY = original_repository

        payload = response.get_json()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(payload["code"], "STORAGE_CORRUPT")
        self.assertEqual(payload["action"], "restore_storage_backup")
        self.assertEqual(payload["request_id"], "phase2a-corrupt-fixture")
        self.assertNotIn(str(_MODULE_ROOT), json.dumps(payload))
        self.assertEqual(Path(app._LEAD_TITLE_CACHE_PATH).read_bytes(), legacy_bytes)

    def test_runtime_diagnostics_expose_only_path_free_storage_health(self):
        payload = app._cvstudio_runtime_diagnostics_payload()
        storage = payload["durable_storage"]
        self.assertTrue(storage["healthy"])
        self.assertEqual(storage["journal_mode"], "wal")
        self.assertNotIn(str(_MODULE_ROOT), json.dumps(storage))
        self.assertNotIn("database_path", storage)

    def test_usage_and_ppc_routes_import_upsert_read_and_clear(self):
        client = app.app.test_client()
        headers = {
            "X-CV-Studio-Request": "1",
            "X-CV-Studio-Request-ID": "phase2a-browser-store",
        }
        legacy_usage = [
            {
                "ts": "2026-07-01T00:00:00Z",
                "name": "Legacy fixture",
                "mode": "format",
                "cost": 0.125,
                "model": "legacy-model",
            }
        ]
        response = client.post(
            "/storage/usage-history/import",
            json={"records": legacy_usage},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["records"], legacy_usage)
        self.assertNotIn("input_tokens", payload["records"][0])
        self.assertTrue(payload["legacy_preserved"])

        current_usage = [
            {
                "id": "stat_fixture",
                "ts": "2026-07-02T00:00:00Z",
                "name": "Current fixture",
                "mode": "lead",
                "cost": 0.25,
                "input_tokens": 4,
                "output_tokens": 2,
                "api_calls": 1,
                "pricing_model_key": "fixture-pricing",
                "apiKey": True,
                "meta": {
                    "safe_label": "retained",
                    "api_key": True,
                    "nested": [{"x-api-key": True, "output_tokens": 2}],
                },
            }
        ]
        response = client.post(
            "/storage/usage-history/upsert",
            json={"records": current_usage},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        response = client.get("/storage/usage-history", headers=headers)
        records = response.get_json()["records"]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[1]["pricing_model_key"], "fixture-pricing")
        self.assertEqual(records[1]["input_tokens"], 4)
        self.assertNotIn("apiKey", records[1])
        self.assertEqual(records[1]["meta"]["safe_label"], "retained")
        self.assertNotIn("api_key", records[1]["meta"])
        self.assertNotIn("x-api-key", records[1]["meta"]["nested"][0])
        self.assertEqual(records[1]["meta"]["nested"][0]["output_tokens"], 2)

        legacy_ppc = {
            "placement-fixture": {
                "payment": "Invoiced",
                "guaranteeMonths": "3",
                "updatedAt": "2026-07-01T00:00:00Z",
            }
        }
        response = client.post(
            "/storage/ppc-metadata/import",
            json={"metadata": legacy_ppc},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["metadata"], legacy_ppc)

        changed_ppc = {
            "placement-fixture": {
                "payment": "Paid",
                "guaranteeMonths": "3",
                "updatedAt": "2026-07-02T00:00:00Z",
            }
        }
        response = client.post(
            "/storage/ppc-metadata/upsert",
            json={"metadata": changed_ppc},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        response = client.get("/storage/ppc-metadata", headers=headers)
        self.assertEqual(response.get_json()["metadata"], changed_ppc)

        self.assertEqual(
            client.post("/storage/usage-history/clear", json={}, headers=headers).status_code,
            200,
        )
        self.assertEqual(
            client.post("/storage/ppc-metadata/clear", json={}, headers=headers).status_code,
            200,
        )
        self.assertEqual(client.get("/storage/usage-history").get_json()["records"], [])
        self.assertEqual(client.get("/storage/ppc-metadata").get_json()["metadata"], {})

    def test_phase1_request_id_error_contract_and_local_security_regression(self):
        client = app.app.test_client()
        request_id = "phase1-contract-regression"
        response = client.get("/status", headers={"X-CV-Studio-Request-ID": request_id})
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["healthy"])
        self.assertEqual(payload["version"], "v24.6.369")
        self.assertEqual(response.headers["X-CV-Studio-Request-ID"], request_id)

        response = client.get("/missing-phase1-fixture", headers={"X-CV-Studio-Request-ID": request_id})
        payload = response.get_json()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(payload["code"], "NOT_FOUND")
        self.assertEqual(payload["request_id"], request_id)
        self.assertIn("error", payload)
        self.assertIn("message", payload)

        response = client.post("/storage/usage-history/clear", json={})
        payload = response.get_json()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(payload["code"], "UNSAFE_LOCAL_REQUEST")
        self.assertTrue(payload["request_id"])

        response = client.get("/status", headers={"Host": "host-fixture.invalid"})
        payload = response.get_json()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(payload["code"], "INVALID_LOCAL_HOST")
        self.assertEqual(payload["action"], "reopen_local_app")

        self.assertEqual(
            app._cvstudio_classify_error(500, "Local storage is busy."),
            ("STORAGE_BUSY", True, "retry"),
        )
        self.assertEqual(
            app._cvstudio_classify_error(500, "Local storage is unavailable."),
            ("STORAGE_UNAVAILABLE", True, "check_storage_access"),
        )

        response = client.get(
            "/jobadder/search_candidate",
            headers={"X-CV-Studio-Request-ID": request_id},
        )
        payload = response.get_json()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(payload["code"], "JOBADDER_RECONNECT_REQUIRED")
        self.assertEqual(payload["action"], "open_jobadder_settings")
        self.assertEqual(payload["request_id"], request_id)

    def test_phase1_owner_local_integration_and_support_bundle_regression(self):
        client = app.app.test_client()
        headers = {
            "X-CV-Studio-Request": "1",
            "X-CV-Studio-Owner-Test": "1",
            "X-CV-Studio-Request-ID": "phase1-owner-regression",
        }
        response = client.get("/owner/integration/status")
        status = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(status["enabled"])
        self.assertTrue(status["owner_source_only"])

        response = client.post(
            "/owner/integration/run",
            json={"tests": ["local_health", "docx_generation"]},
            headers=headers,
        )
        report = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(report["summary"], {"passed": 2, "failed": 0, "skipped": 0, "total": 2})
        self.assertTrue(all(item["status"] == "passed" for item in report["results"]))

        response = client.post(
            "/diagnostics/support_bundle",
            json={
                "browser": {
                    "active_tab": "stats",
                    "recent_api_errors": [
                        {
                            "status": 500,
                            "code": "FIXTURE_FAILURE",
                            "request_id": "phase1-owner-regression",
                            "message": "Non-sensitive regression fixture",
                            "action": "retry",
                        }
                    ],
                }
            },
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            names = set(archive.namelist())
            self.assertTrue({"runtime.json", "browser.json", "README.txt"}.issubset(names))
            runtime = json.loads(archive.read("runtime.json"))
            browser = json.loads(archive.read("browser.json"))
        self.assertTrue(runtime["durable_storage"]["healthy"])
        self.assertEqual(browser["active_tab"], "stats")
        self.assertNotIn(str(_MODULE_ROOT), json.dumps(runtime))
        self.assertNotIn("local_storage_values", browser)


if __name__ == "__main__":
    unittest.main()
