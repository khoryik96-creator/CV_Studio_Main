import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cvstudio_storage as storage_module
from cvstudio_storage import (
    BrowserSettingsRepository,
    CVStudioStorage,
    MIGRATIONS,
    OneNoteSavedLinkRepository,
    OneNoteTransferRepository,
    SCHEMA_VERSION,
    StorageMigrationError,
    UsageHistoryRepository,
)


class Phase2BSchemaMigrationTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory(prefix="cvstudio-phase2b-schema-")
        self.root = Path(self._temporary.name)
        self.database = self.root / "state" / "cv_studio.sqlite3"

    def tearDown(self):
        self._temporary.cleanup()

    def _create_v7_database(self):
        with patch.object(storage_module, "MIGRATIONS", MIGRATIONS[:7]), patch.object(
            storage_module, "SCHEMA_VERSION", 7
        ):
            storage = storage_module.CVStudioStorage(self.database)
            storage.initialize()
            UsageHistoryRepository(storage).upsert(
                [
                    {
                        "id": "phase2a-preserved",
                        "ts": "2026-07-20T00:00:00Z",
                        "name": "Phase 2A preserved fixture",
                        "mode": "format",
                    }
                ]
            )

    def _backup_names(self):
        directory = self.database.parent / "migration_backups"
        return sorted(path.name for path in directory.glob("*.sqlite3"))

    def test_v7_upgrade_creates_three_verified_backups_and_preserves_phase2a_data(self):
        self._create_v7_database()
        v7_backups = self._backup_names()
        self.assertEqual(len(v7_backups), 7)

        storage = CVStudioStorage(self.database)
        storage.initialize()

        self.assertEqual(SCHEMA_VERSION, 10)
        self.assertEqual(
            [(row["version"], row["name"]) for row in storage.migration_history()],
            [(migration.version, migration.name) for migration in MIGRATIONS],
        )
        self.assertEqual(len(self._backup_names()), 10)
        self.assertEqual(
            UsageHistoryRepository(storage).list()[0]["id"],
            "phase2a-preserved",
        )
        with storage.connection() as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
        self.assertTrue(
            {"onenote_transfer_records", "onenote_saved_links", "browser_settings"}
            <= tables
        )

        upgraded_backups = self._backup_names()
        restarted = CVStudioStorage(self.database)
        restarted.initialize()
        self.assertEqual(self._backup_names(), upgraded_backups)
        self.assertEqual(restarted.recheck_integrity(), "ok")

    def test_interrupted_phase2b_migration_rolls_back_and_restarts(self):
        self._create_v7_database()

        def interrupt(version, stage):
            if version == 9 and stage == "after_schema":
                raise RuntimeError("simulated Phase 2B interruption")

        interrupted = CVStudioStorage(self.database, migration_hook=interrupt)
        with self.assertRaises(StorageMigrationError):
            interrupted.initialize()

        connection = sqlite3.connect(str(self.database))
        try:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 8)
            self.assertIsNotNone(
                connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='onenote_transfer_records'"
                ).fetchone()
            )
            self.assertIsNone(
                connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='onenote_saved_links'"
                ).fetchone()
            )
            applied = connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
            self.assertEqual([row[0] for row in applied], list(range(1, 9)))
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        finally:
            connection.close()

        resumed = CVStudioStorage(self.database)
        resumed.initialize()
        self.assertEqual(
            [row["version"] for row in resumed.migration_history()],
            list(range(1, SCHEMA_VERSION + 1)),
        )
        self.assertEqual(UsageHistoryRepository(resumed).list()[0]["id"], "phase2a-preserved")


class Phase2BRepositoryTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory(prefix="cvstudio-phase2b-repositories-")
        root = Path(self._temporary.name)
        self.storage = CVStudioStorage(root / "state" / "cv_studio.sqlite3")
        self.storage.initialize()

    def tearDown(self):
        self._temporary.cleanup()

    def test_transfer_records_are_bounded_filtered_replaceable_and_tombstoned(self):
        repository = OneNoteTransferRepository(self.storage)
        legacy = [
            {
                "id": "transfer-a",
                "ts": "2026-07-20T02:00:00Z",
                "name": "Transfer fixture A",
                "status": "Transferred",
                "input_tokens": 12,
                "clientSecret": "redacted-fixture-value",
                "nested": {"access-token": "redacted-fixture-value", "safe": True},
            },
            {
                "id": "transfer-b",
                "ts": "2026-07-20T01:00:00Z",
                "name": "Transfer fixture B",
                "status": "Transferred",
            },
        ]

        self.assertEqual(repository.import_legacy(legacy), 2)
        self.assertEqual(repository.import_legacy(legacy), 0)
        loaded = repository.list()
        self.assertEqual([row["id"] for row in loaded], ["transfer-a", "transfer-b"])
        self.assertEqual(loaded[0]["input_tokens"], 12)
        self.assertNotIn("clientSecret", loaded[0])
        self.assertEqual(loaded[0]["nested"], {"safe": True})

        replacement = [
            dict(loaded[0], status="Transferred and reviewed"),
            {
                "id": "transfer-c",
                "ts": "2026-07-21T01:00:00Z",
                "name": "Transfer fixture C",
                "status": "Transferred",
            },
        ]
        self.assertEqual(repository.replace(replacement), 2)
        self.assertEqual(
            [row["id"] for row in repository.list()],
            ["transfer-c", "transfer-a"],
        )

        oversized = dict(
            replacement[0],
            field_a="a" * (300 * 1024),
            field_b="b" * (300 * 1024),
        )
        with self.assertRaisesRegex(ValueError, "invalid or too large"):
            repository.replace([oversized])
        self.assertEqual(
            [row["id"] for row in repository.list()],
            ["transfer-c", "transfer-a"],
        )

        stale_deleted = dict(legacy[1], status="Stale browser mirror")
        self.assertEqual(repository.import_legacy([stale_deleted]), 0)
        self.assertNotIn("transfer-b", [row["id"] for row in repository.list()])

        repository.clear()
        self.assertEqual(repository.list(), [])
        self.assertEqual(repository.import_legacy([dict(replacement[0], status="Stale")]), 0)
        self.assertEqual(repository.list(), [])

    def test_saved_links_preserve_unknown_safe_fields_and_tombstones(self):
        repository = OneNoteSavedLinkRepository(self.storage)
        legacy = [
            {
                "id": "link-a",
                "name": "Notebook fixture",
                "kind": "notebook",
                "link": "opaque-onenote-link-a",
                "createdAt": "2026-07-20T00:00:00Z",
                "futureField": {"safe": "kept", "api_key": "redacted-fixture-value"},
            },
            {
                "id": "link-b",
                "name": "Section fixture",
                "kind": "section",
                "link": "opaque-onenote-link-b",
            },
        ]

        self.assertEqual(repository.import_legacy(legacy), 2)
        self.assertEqual(repository.import_legacy(legacy), 0)
        loaded = repository.list()
        self.assertEqual(loaded[0]["futureField"], {"safe": "kept"})

        self.assertEqual(repository.replace([dict(loaded[0], name="Renamed fixture")]), 1)
        self.assertEqual(repository.list()[0]["name"], "Renamed fixture")
        oversized = dict(
            loaded[0],
            field_a="a" * (300 * 1024),
            field_b="b" * (300 * 1024),
        )
        with self.assertRaisesRegex(ValueError, "invalid or too large"):
            repository.replace([oversized])
        self.assertEqual(repository.list()[0]["name"], "Renamed fixture")
        self.assertEqual(
            repository.import_legacy([dict(legacy[1], futureField="stale")]),
            0,
        )
        self.assertEqual([row["id"] for row in repository.list()], ["link-a"])

    def test_browser_settings_are_allowlisted_filtered_and_tombstoned(self):
        self.assertIn(
            "cvstudio_summary_box_autofit_v1",
            storage_module.BROWSER_SETTING_KEYS,
        )
        repository = BrowserSettingsRepository(self.storage)
        legacy = {
            "hy_provider": "openai",
            "hy_model_openai": "gpt-fixture",
            "cvstudio_ppc_ui_state_v1": json.dumps(
                {
                    "page": 2,
                    "clientSecret": "redacted-fixture-value",
                    "nested": {"safe": True, "api-key": "redacted-fixture-value"},
                }
            ),
            "hy_key_openai": "redacted-fixture-value",
            "hy_lead_model_openai": "api_key=redacted-fixture-value",
        }

        self.assertEqual(repository.import_legacy(legacy), 3)
        self.assertEqual(repository.import_legacy(legacy), 0)
        loaded = repository.load()
        self.assertEqual(loaded["hy_provider"], "openai")
        self.assertEqual(loaded["hy_model_openai"], "gpt-fixture")
        self.assertNotIn("hy_key_openai", loaded)
        self.assertNotIn("hy_lead_model_openai", loaded)
        self.assertEqual(
            json.loads(loaded["cvstudio_ppc_ui_state_v1"]),
            {"nested": {"safe": True}, "page": 2},
        )

        self.assertEqual(repository.upsert({"hy_provider": "deepseek"}), 1)
        self.assertEqual(repository.delete(["hy_model_openai", "hy_key_openai"]), 1)
        self.assertEqual(repository.load()["hy_provider"], "deepseek")
        self.assertNotIn("hy_model_openai", repository.load())

        stale = {
            "hy_provider": "anthropic",
            "hy_model_openai": "gpt-stale-fixture",
        }
        self.assertEqual(repository.import_legacy(stale), 0)
        self.assertEqual(repository.load()["hy_provider"], "deepseek")
        self.assertNotIn("hy_model_openai", repository.load())


if __name__ == "__main__":
    unittest.main()
