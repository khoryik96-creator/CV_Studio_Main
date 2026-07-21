import os
from pathlib import Path
import tempfile
import unittest


_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-phase2b-app-import-")
_ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["CVSTUDIO_DB_PATH"] = str(
    Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3"
)
try:
    import app
finally:
    if _ORIGINAL_DATABASE_OVERRIDE is None:
        os.environ.pop("CVSTUDIO_DB_PATH", None)
    else:
        os.environ["CVSTUDIO_DB_PATH"] = _ORIGINAL_DATABASE_OVERRIDE

from cvstudio_storage import (
    BrowserSettingsRepository,
    CVStudioStorage,
    OneNoteSavedLinkRepository,
    OneNoteTransferRepository,
)


class Phase2BAppStorageIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory(prefix="cvstudio-phase2b-app-")
        self.storage = CVStudioStorage(
            Path(self._temporary.name) / "state" / "cv_studio.sqlite3"
        )
        self.storage.initialize()
        self.originals = (
            app._CVSTUDIO_STORAGE,
            app._CVSTUDIO_ONENOTE_TRANSFER_REPOSITORY,
            app._CVSTUDIO_ONENOTE_LINK_REPOSITORY,
            app._CVSTUDIO_BROWSER_SETTINGS_REPOSITORY,
        )
        app._CVSTUDIO_STORAGE = self.storage
        app._CVSTUDIO_ONENOTE_TRANSFER_REPOSITORY = OneNoteTransferRepository(
            self.storage
        )
        app._CVSTUDIO_ONENOTE_LINK_REPOSITORY = OneNoteSavedLinkRepository(
            self.storage
        )
        app._CVSTUDIO_BROWSER_SETTINGS_REPOSITORY = BrowserSettingsRepository(
            self.storage
        )
        self.client = app.app.test_client()

    def tearDown(self):
        (
            app._CVSTUDIO_STORAGE,
            app._CVSTUDIO_ONENOTE_TRANSFER_REPOSITORY,
            app._CVSTUDIO_ONENOTE_LINK_REPOSITORY,
            app._CVSTUDIO_BROWSER_SETTINGS_REPOSITORY,
        ) = self.originals
        self._temporary.cleanup()

    @staticmethod
    def _headers(request_id):
        return {
            "X-CV-Studio-Request": "1",
            "X-CV-Studio-Request-ID": request_id,
        }

    def test_transfer_routes_import_replace_clear_and_preserve_request_ids(self):
        legacy = [
            {
                "id": "transfer-route-a",
                "ts": "2026-07-20T01:00:00Z",
                "name": "Transfer route fixture",
                "status": "Transferred",
                "nested": {
                    "client-secret": "redacted-fixture-value",
                    "safe": True,
                },
            }
        ]
        response = self.client.post(
            "/storage/onenote-transfer-records/import",
            json={"records": legacy},
            headers=self._headers("phase2b-transfer-import"),
        )
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["request_id"], "phase2b-transfer-import")
        self.assertEqual(payload["imported"], 1)
        self.assertEqual(payload["records"][0]["nested"], {"safe": True})
        self.assertTrue(payload["legacy_preserved"])

        replacement = [
            {
                "id": "transfer-route-b",
                "ts": "2026-07-21T01:00:00Z",
                "name": "Replacement route fixture",
                "status": "Transferred",
            }
        ]
        response = self.client.post(
            "/storage/onenote-transfer-records/replace",
            json={"records": replacement},
            headers=self._headers("phase2b-transfer-replace"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["written"], 1)
        read = self.client.get(
            "/storage/onenote-transfer-records",
            headers={"X-CV-Studio-Request-ID": "phase2b-transfer-read"},
        ).get_json()
        self.assertEqual([row["id"] for row in read["records"]], ["transfer-route-b"])

        response = self.client.post(
            "/storage/onenote-transfer-records/clear",
            json={},
            headers=self._headers("phase2b-transfer-clear"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.get("/storage/onenote-transfer-records").get_json()["records"],
            [],
        )

    def test_saved_link_routes_replace_and_reject_oversized_record_sets(self):
        links = [
            {
                "id": "link-route-a",
                "name": "Saved link route fixture",
                "kind": "section",
                "link": "opaque-onenote-link-route",
                "future": {"safe": "kept", "api_key": "redacted-fixture-value"},
            }
        ]
        response = self.client.post(
            "/storage/onenote-saved-links/import",
            json={"links": links},
            headers=self._headers("phase2b-links-import"),
        )
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["links"][0]["future"], {"safe": "kept"})

        changed = [dict(payload["links"][0], name="Renamed route fixture")]
        response = self.client.post(
            "/storage/onenote-saved-links/replace",
            json={"links": changed},
            headers=self._headers("phase2b-links-replace"),
        )
        self.assertEqual(response.status_code, 200)
        read = self.client.get("/storage/onenote-saved-links").get_json()
        self.assertEqual(read["links"][0]["name"], "Renamed route fixture")

        response = self.client.post(
            "/storage/onenote-saved-links/import",
            json={"links": [{} for _ in range(101)]},
            headers=self._headers("phase2b-links-invalid"),
        )
        payload = response.get_json()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(payload["code"], "STORAGE_PAYLOAD_INVALID")
        self.assertEqual(payload["request_id"], "phase2b-links-invalid")

    def test_browser_setting_routes_enforce_allowlist_and_tombstones(self):
        response = self.client.post(
            "/storage/browser-settings/import",
            json={
                "settings": {
                    "hy_provider": "openai",
                    "hy_model_openai": "gpt-route-fixture",
                }
            },
            headers=self._headers("phase2b-settings-import"),
        )
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["settings"]["hy_provider"], "openai")

        response = self.client.post(
            "/storage/browser-settings/upsert",
            json={"settings": {"hy_provider": "deepseek"}},
            headers=self._headers("phase2b-settings-upsert"),
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            "/storage/browser-settings/delete",
            json={"keys": ["hy_model_openai"]},
            headers=self._headers("phase2b-settings-delete"),
        )
        self.assertEqual(response.status_code, 200)
        read = self.client.get("/storage/browser-settings").get_json()["settings"]
        self.assertEqual(read["hy_provider"], "deepseek")
        self.assertNotIn("hy_model_openai", read)

        response = self.client.post(
            "/storage/browser-settings/upsert",
            json={"settings": {"hy_key_openai": "redacted-fixture-value"}},
            headers=self._headers("phase2b-settings-invalid"),
        )
        payload = response.get_json()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(payload["code"], "STORAGE_PAYLOAD_INVALID")
        self.assertEqual(payload["request_id"], "phase2b-settings-invalid")
        self.assertNotIn("hy_key_openai", self.client.get("/storage/browser-settings").get_json()["settings"])

    def test_storage_corruption_uses_existing_structured_recovery_contract(self):
        corrupt_database = Path(self._temporary.name) / "corrupt" / "cv_studio.sqlite3"
        corrupt_database.parent.mkdir(parents=True, exist_ok=True)
        corrupt_database.write_bytes(b"not-a-sqlite-database")
        app._CVSTUDIO_ONENOTE_TRANSFER_REPOSITORY = OneNoteTransferRepository(
            CVStudioStorage(corrupt_database)
        )

        response = self.client.get(
            "/storage/onenote-transfer-records",
            headers={"X-CV-Studio-Request-ID": "phase2b-corrupt-route"},
        )
        payload = response.get_json()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(payload["code"], "STORAGE_CORRUPT")
        self.assertEqual(payload["request_id"], "phase2b-corrupt-route")
        self.assertEqual(payload["action"], "restore_storage_backup")
        self.assertNotIn(str(self._temporary.name), str(payload))


if __name__ == "__main__":
    unittest.main()
