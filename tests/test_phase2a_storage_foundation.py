import sqlite3
import tempfile
import unittest
from pathlib import Path

from cvstudio_storage import (
    BUSY_TIMEOUT_MS,
    CVStudioStorage,
    MIGRATIONS,
    SCHEMA_VERSION,
    StorageBusyError,
    StorageCorruptionError,
    StorageMigrationError,
)


class Phase2AStorageFoundationTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory(prefix="cvstudio-phase2a-")
        self.root = Path(self._temporary.name)
        self.database = self.root / "state" / "cv_studio.sqlite3"

    def tearDown(self):
        self._temporary.cleanup()

    def _backup_files(self):
        directory = self.database.parent / "migration_backups"
        return sorted(directory.glob("*.sqlite3")) if directory.is_dir() else []

    def test_initialization_enforces_pragmas_and_records_verified_migrations(self):
        storage = CVStudioStorage(self.database)
        storage.initialize()

        health = storage.health()
        self.assertTrue(health["healthy"])
        self.assertEqual(health["schema_version"], SCHEMA_VERSION)
        self.assertEqual(health["journal_mode"], "wal")
        self.assertTrue(health["foreign_keys"])
        self.assertEqual(health["busy_timeout_ms"], BUSY_TIMEOUT_MS)
        self.assertEqual(health["integrity_check"], "ok")

        history = storage.migration_history()
        self.assertEqual(
            [(item["version"], item["name"]) for item in history],
            [(migration.version, migration.name) for migration in MIGRATIONS],
        )
        self.assertTrue(all(len(item["checksum"]) == 64 for item in history))

        backups = self._backup_files()
        self.assertEqual(len(backups), len(MIGRATIONS))
        self.assertEqual(
            {item["backup_name"] for item in history},
            {path.name for path in backups},
        )
        for backup in backups:
            connection = sqlite3.connect(str(backup))
            try:
                result = connection.execute("PRAGMA integrity_check").fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(result, "ok")

        with storage.connection() as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(
                connection.execute("PRAGMA busy_timeout").fetchone()[0],
                BUSY_TIMEOUT_MS,
            )
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)

    def test_second_initialization_is_idempotent_and_creates_no_extra_backup(self):
        first = CVStudioStorage(self.database)
        first.initialize()
        backup_names = [path.name for path in self._backup_files()]
        history = first.migration_history()

        second = CVStudioStorage(self.database)
        second.initialize()

        self.assertEqual(second.migration_history(), history)
        self.assertEqual([path.name for path in self._backup_files()], backup_names)
        with second.connection() as connection:
            duplicate_versions = connection.execute(
                """
                SELECT version, COUNT(*) FROM schema_migrations
                GROUP BY version HAVING COUNT(*) > 1
                """
            ).fetchall()
        self.assertEqual(duplicate_versions, [])

    def test_interrupted_migration_rolls_back_and_restart_completes(self):
        def interrupt(version, stage):
            if version == 4 and stage == "after_schema":
                raise RuntimeError("simulated interruption")

        interrupted = CVStudioStorage(self.database, migration_hook=interrupt)
        with self.assertRaises(StorageMigrationError):
            interrupted.initialize()

        connection = sqlite3.connect(str(self.database))
        try:
            user_version = connection.execute("PRAGMA user_version").fetchone()[0]
            table = connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name = 'lead_contact_cache'
                """
            ).fetchone()
            applied = connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            connection.close()

        self.assertEqual(user_version, 3)
        self.assertIsNone(table)
        self.assertEqual([row[0] for row in applied], [1, 2, 3])
        self.assertEqual(integrity, "ok")

        resumed = CVStudioStorage(self.database)
        resumed.initialize()
        self.assertEqual(
            [item["version"] for item in resumed.migration_history()],
            list(range(1, SCHEMA_VERSION + 1)),
        )
        self.assertEqual(resumed.recheck_integrity(), "ok")

    def test_corrupt_database_returns_safe_error_and_preserves_legacy_bytes(self):
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.database.write_bytes(b"not-a-sqlite-database")
        legacy = self.root / "legacy_cache.json"
        original = b'{"entries":[{"family":"fixture","evidence":["term"]}]}'
        legacy.write_bytes(original)

        storage = CVStudioStorage(self.database)
        with self.assertRaises(StorageCorruptionError) as raised:
            storage.initialize()

        self.assertNotIn(str(self.root), str(raised.exception))
        self.assertEqual(legacy.read_bytes(), original)
        health = storage.health()
        self.assertFalse(health["healthy"])
        self.assertEqual(health["code"], "STORAGE_CORRUPT")
        self.assertEqual(health["action"], "restore_storage_backup")
        self.assertNotIn(str(self.root), health["message"])

    def test_database_lock_is_retryable_and_not_reported_as_corruption(self):
        CVStudioStorage(self.database, busy_timeout_ms=1000).initialize()
        blocker = sqlite3.connect(str(self.database), isolation_level=None)
        try:
            blocker.execute("PRAGMA journal_mode = WAL")
            blocker.execute("BEGIN EXCLUSIVE")
            blocker.execute(
                "UPDATE schema_meta SET value = value WHERE key = 'schema_version'"
            )

            storage = CVStudioStorage(self.database, busy_timeout_ms=1000)
            with self.assertRaises(StorageBusyError) as raised:
                storage.initialize()
            self.assertEqual(raised.exception.code, "STORAGE_BUSY")
            self.assertTrue(raised.exception.retryable)
            self.assertEqual(raised.exception.recovery_action, "retry")
            self.assertNotIn("corrupt", str(raised.exception).lower())
        finally:
            blocker.rollback()
            blocker.close()

        storage.initialize()
        self.assertTrue(storage.health()["healthy"])


if __name__ == "__main__":
    unittest.main()
