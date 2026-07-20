import json
import os
from pathlib import Path
import tempfile
import unittest


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
        app._CVSTUDIO_LEAD_TITLE_REPOSITORY.clear()
        app._CVSTUDIO_LEAD_CONTACT_REPOSITORY.clear()
        app._CVSTUDIO_SALARY_REPOSITORY.clear()
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


if __name__ == "__main__":
    unittest.main()
