"""Phase 2A SQLite foundation for CV Studio.

This module is deliberately limited to local durable storage.  It does not
own Flask routes, provider clients, credentials, background jobs or UI state.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import uuid


SCHEMA_VERSION = 7
BUSY_TIMEOUT_MS = 5_000
_INTEGRITY_OK = "ok"
_SAFE_STATE_KEYS = {
    "storage_health",
    "last_migration",
    "last_legacy_import",
}


class StorageError(RuntimeError):
    """Base class carrying only user-safe recovery information."""

    code = "STORAGE_UNAVAILABLE"
    retryable = True
    recovery_action = "check_storage_access"
    public_message = (
        "Local storage is unavailable. Preserve the legacy JSON files, close "
        "other CV Studio windows, check local disk space and access, then retry."
    )

    def __init__(self, message: str | None = None):
        super().__init__(message or self.public_message)


class StorageCorruptionError(StorageError):
    code = "STORAGE_CORRUPT"
    retryable = False
    recovery_action = "restore_storage_backup"
    public_message = (
        "The local storage database is corrupt. Close CV Studio, preserve the "
        "legacy JSON files, and restore the latest verified migration backup "
        "before retrying."
    )


class StorageMigrationError(StorageError):
    code = "STORAGE_MIGRATION_FAILED"
    retryable = False
    recovery_action = "restore_storage_backup"
    public_message = (
        "The local storage migration could not be completed safely. Close CV "
        "Studio, preserve the legacy JSON files, and retry after checking the "
        "latest verified migration backup."
    )


class StorageVersionError(StorageError):
    code = "STORAGE_VERSION_UNSUPPORTED"
    retryable = False
    recovery_action = "restore_storage_backup"
    public_message = (
        "The local storage database was created by a newer CV Studio release. "
        "Use that release or restore a compatible verified migration backup."
    )


class StorageBusyError(StorageError):
    code = "STORAGE_BUSY"
    retryable = True
    recovery_action = "retry"
    public_message = (
        "Local storage is busy. Wait for the current CV Studio operation to "
        "finish, close duplicate CV Studio windows if necessary, and retry."
    )


_SQLITE_CORRUPTION_CODES = {
    int(getattr(sqlite3, "SQLITE_CORRUPT", 11)),
    int(getattr(sqlite3, "SQLITE_FORMAT", 24)),
    int(getattr(sqlite3, "SQLITE_NOTADB", 26)),
}
_SQLITE_BUSY_CODES = {
    int(getattr(sqlite3, "SQLITE_BUSY", 5)),
    int(getattr(sqlite3, "SQLITE_LOCKED", 6)),
}


def _sqlite_storage_error(error: sqlite3.Error) -> StorageError:
    """Classify SQLite failures without treating ordinary lock/I/O errors as corruption."""

    raw_code = getattr(error, "sqlite_errorcode", None)
    primary_code = (int(raw_code) & 0xFF) if isinstance(raw_code, int) else None
    message = str(error or "").strip().lower()
    if primary_code in _SQLITE_CORRUPTION_CODES or any(
        fragment in message
        for fragment in (
            "database disk image is malformed",
            "file is not a database",
            "malformed database schema",
            "database corruption",
        )
    ):
        return StorageCorruptionError()
    if primary_code in _SQLITE_BUSY_CODES or "database is locked" in message or "database table is locked" in message:
        return StorageBusyError()
    return StorageError()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _payload_fingerprint(value) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def default_state_directory() -> Path:
    """Return the existing per-user CV Studio state directory."""

    override = str(os.environ.get("CVSTUDIO_STATE_DIR") or "").strip()
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "TheGuoLab" / "CVStudio"
        return Path.home() / "AppData" / "Local" / "TheGuoLab" / "CVStudio"
    return Path.home() / ".guo_lab_cv_studio"


def default_database_path() -> Path:
    override = str(os.environ.get("CVSTUDIO_DB_PATH") or "").strip()
    if override:
        return Path(override).expanduser()
    return default_state_directory() / "cv_studio.sqlite3"


@dataclass(frozen=True)
class SchemaMigration:
    version: int
    name: str
    statements: tuple[str, ...]

    @property
    def checksum(self) -> str:
        material = "\n-- statement --\n".join(self.statements)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


MIGRATIONS = (
    SchemaMigration(
        1,
        "storage_foundation",
        (
            """
            CREATE TABLE schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL,
                backup_name TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE legacy_imports (
                store_name TEXT NOT NULL,
                source_fingerprint TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                record_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (store_name, source_fingerprint)
            )
            """,
        ),
    ),
    SchemaMigration(
        2,
        "usage_history_repository",
        (
            """
            CREATE TABLE usage_history (
                record_id TEXT PRIMARY KEY,
                recorded_at TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'sqlite',
                updated_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX usage_history_recorded_at_idx ON usage_history(recorded_at)",
        ),
    ),
    SchemaMigration(
        3,
        "lead_title_cache_repository",
        (
            """
            CREATE TABLE lead_title_cache (
                entry_key TEXT PRIMARY KEY,
                family TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT '',
                hits INTEGER NOT NULL DEFAULT 0,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX lead_title_cache_family_idx ON lead_title_cache(family)",
        ),
    ),
    SchemaMigration(
        4,
        "lead_contact_cache_repository",
        (
            """
            CREATE TABLE lead_contact_cache (
                cache_key TEXT PRIMARY KEY,
                cached_at TEXT NOT NULL DEFAULT '',
                hits INTEGER NOT NULL DEFAULT 0,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
        ),
    ),
    SchemaMigration(
        5,
        "salary_component_cache_repository",
        (
            """
            CREATE TABLE salary_component_cache (
                cache_key TEXT PRIMARY KEY,
                saved_at TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
        ),
    ),
    SchemaMigration(
        6,
        "ppc_metadata_repository",
        (
            """
            CREATE TABLE ppc_metadata (
                placement_id TEXT PRIMARY KEY,
                metadata_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT ''
            )
            """,
        ),
    ),
    SchemaMigration(
        7,
        "diagnostic_state_repository",
        (
            """
            CREATE TABLE diagnostic_state (
                state_key TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
        ),
    ),
)


class CVStudioStorage:
    """Connection lifecycle, migrations, backups and repository entry point."""

    def __init__(
        self,
        database_path: str | os.PathLike | None = None,
        *,
        busy_timeout_ms: int = BUSY_TIMEOUT_MS,
        migration_hook=None,
    ):
        self.database_path = Path(database_path) if database_path else default_database_path()
        self.backup_directory = self.database_path.parent / "migration_backups"
        self.busy_timeout_ms = max(1_000, min(int(busy_timeout_ms), 60_000))
        self._migration_hook = migration_hook
        self._lock = threading.RLock()
        self._initialized = False
        self._last_error: StorageError | None = None
        self._last_integrity_check = ""
        self._journal_mode = ""

    def _connect_raw(self) -> sqlite3.Connection:
        connection = None
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(
                str(self.database_path),
                timeout=self.busy_timeout_ms / 1000.0,
                isolation_level=None,
                check_same_thread=False,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = {}".format(self.busy_timeout_ms))
            journal_row = connection.execute("PRAGMA journal_mode = WAL").fetchone()
            self._journal_mode = str(journal_row[0] if journal_row else "").lower()
            connection.execute("PRAGMA synchronous = NORMAL")
            return connection
        except sqlite3.Error as exc:
            if connection is not None:
                connection.close()
            raise _sqlite_storage_error(exc) from exc
        except OSError as exc:
            if connection is not None:
                connection.close()
            raise StorageError() from exc

    @staticmethod
    def _integrity_result(connection: sqlite3.Connection) -> str:
        try:
            rows = connection.execute("PRAGMA integrity_check").fetchall()
        except sqlite3.Error as exc:
            raise _sqlite_storage_error(exc) from exc
        values = [str(row[0] if row else "") for row in rows]
        if values != [_INTEGRITY_OK]:
            raise StorageCorruptionError()
        return _INTEGRITY_OK

    def _verified_backup(self, connection: sqlite3.Connection, migration: SchemaMigration) -> Path:
        """Create and integrity-check a transactionally consistent backup."""

        self.backup_directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        safe_stem = re.sub(r"[^A-Za-z0-9_.-]", "_", self.database_path.stem)[:80] or "cv_studio"
        name = "{}.pre_v{:03d}.{}.{}.sqlite3".format(
            safe_stem,
            migration.version,
            timestamp,
            uuid.uuid4().hex[:10],
        )
        destination_path = self.backup_directory / name
        destination = None
        try:
            destination = sqlite3.connect(str(destination_path), isolation_level=None)
            connection.backup(destination)
            destination.close()
            destination = None
            verify = sqlite3.connect("file:{}?mode=ro".format(destination_path.as_posix()), uri=True)
            try:
                self._integrity_result(verify)
            finally:
                verify.close()
            if not destination_path.is_file() or destination_path.stat().st_size <= 0:
                raise StorageMigrationError()
            return destination_path
        except StorageError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise StorageMigrationError() from exc
        finally:
            if destination is not None:
                try:
                    destination.close()
                except Exception:
                    pass

    @staticmethod
    def _current_version(connection: sqlite3.Connection) -> int:
        row = connection.execute("PRAGMA user_version").fetchone()
        return int(row[0] if row else 0)

    def _apply_migration(self, connection: sqlite3.Connection, migration: SchemaMigration) -> None:
        backup = self._verified_backup(connection, migration)
        try:
            connection.execute("BEGIN IMMEDIATE")
            for statement in migration.statements:
                connection.execute(statement)
            if self._migration_hook is not None:
                self._migration_hook(migration.version, "after_schema")
            applied_at = _utc_now()
            connection.execute(
                """
                INSERT INTO schema_migrations(version, name, checksum, applied_at, backup_name)
                VALUES (?, ?, ?, ?, ?)
                """,
                (migration.version, migration.name, migration.checksum, applied_at, backup.name),
            )
            connection.execute(
                """
                INSERT INTO schema_meta(key, value) VALUES ('schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (str(migration.version),),
            )
            connection.execute("PRAGMA user_version = {}".format(migration.version))
            if self._migration_hook is not None:
                self._migration_hook(migration.version, "before_commit")
            connection.commit()
        except Exception as exc:
            try:
                connection.rollback()
            except Exception:
                pass
            if isinstance(exc, StorageError):
                raise
            if isinstance(exc, sqlite3.Error):
                classified = _sqlite_storage_error(exc)
                if isinstance(classified, (StorageBusyError, StorageCorruptionError)):
                    raise classified from exc
            raise StorageMigrationError() from exc

    def initialize(self) -> None:
        with self._lock:
            if self._initialized:
                return
            connection = None
            try:
                connection = self._connect_raw()
                self._last_integrity_check = self._integrity_result(connection)
                current = self._current_version(connection)
                if current > SCHEMA_VERSION:
                    raise StorageVersionError()
                for migration in MIGRATIONS:
                    if migration.version > current:
                        self._apply_migration(connection, migration)
                        current = migration.version
                        self._last_integrity_check = self._integrity_result(connection)
                if current != SCHEMA_VERSION:
                    raise StorageMigrationError()
                self._validate_history(connection)
                self._initialized = True
                self._last_error = None
                self._write_storage_health(connection)
            except StorageError as exc:
                self._initialized = False
                self._last_error = exc
                raise
            except sqlite3.Error as exc:
                self._initialized = False
                self._last_error = _sqlite_storage_error(exc)
                raise self._last_error from exc
            except Exception as exc:
                self._initialized = False
                self._last_error = StorageMigrationError()
                raise self._last_error from exc
            finally:
                if connection is not None:
                    connection.close()

    def _validate_history(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
        ).fetchall()
        expected = [(m.version, m.name, m.checksum) for m in MIGRATIONS]
        actual = [(int(row["version"]), str(row["name"]), str(row["checksum"])) for row in rows]
        if actual != expected:
            raise StorageMigrationError()
        meta = connection.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()
        if not meta or int(meta["value"]) != SCHEMA_VERSION:
            raise StorageMigrationError()

    def _write_storage_health(self, connection: sqlite3.Connection) -> None:
        payload = {
            "status": "ok",
            "schema_version": SCHEMA_VERSION,
            "journal_mode": self._journal_mode,
            "foreign_keys": True,
            "busy_timeout_ms": self.busy_timeout_ms,
            "integrity_check": self._last_integrity_check,
            "checked_at": _utc_now(),
        }
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(
                """
                INSERT INTO diagnostic_state(state_key, payload_json, updated_at)
                VALUES ('storage_health', ?, ?)
                ON CONFLICT(state_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (_canonical_json(payload), payload["checked_at"]),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    @contextmanager
    def connection(self, *, write: bool = False):
        self.initialize()
        connection = self._connect_raw()
        try:
            if write:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            if write:
                connection.commit()
        except sqlite3.Error as exc:
            if write:
                try:
                    connection.rollback()
                except Exception:
                    pass
            error = _sqlite_storage_error(exc)
            if isinstance(error, StorageCorruptionError):
                self._initialized = False
                self._last_error = error
            raise error from exc
        except Exception:
            if write:
                try:
                    connection.rollback()
                except Exception:
                    pass
            raise
        finally:
            connection.close()

    def recheck_integrity(self) -> str:
        self.initialize()
        connection = self._connect_raw()
        try:
            result = self._integrity_result(connection)
        finally:
            connection.close()
        self._last_integrity_check = result
        return result

    def health(self) -> dict:
        """Return path-free, credential-free storage diagnostics."""

        try:
            self.initialize()
        except StorageError:
            pass
        backup_count = 0
        try:
            backup_count = sum(1 for item in self.backup_directory.iterdir() if item.is_file())
        except Exception:
            backup_count = 0
        if self._last_error:
            return {
                "status": "error",
                "healthy": False,
                "code": self._last_error.code,
                "retryable": bool(self._last_error.retryable),
                "action": self._last_error.recovery_action,
                "message": self._last_error.public_message,
                "schema_version": None,
                "backup_count": backup_count,
            }
        return {
            "status": "ok",
            "healthy": True,
            "schema_version": SCHEMA_VERSION,
            "journal_mode": self._journal_mode,
            "foreign_keys": True,
            "busy_timeout_ms": self.busy_timeout_ms,
            "integrity_check": self._last_integrity_check,
            "backup_count": backup_count,
        }

    def migration_history(self) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT version, name, checksum, applied_at, backup_name
                FROM schema_migrations ORDER BY version
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def legacy_import_seen(self, connection, store_name: str, fingerprint: str) -> bool:
        row = connection.execute(
            """
            SELECT 1 FROM legacy_imports
            WHERE store_name = ? AND source_fingerprint = ?
            """,
            (store_name, fingerprint),
        ).fetchone()
        return row is not None

    def record_legacy_import(
        self,
        connection,
        store_name: str,
        fingerprint: str,
        record_count: int,
    ) -> None:
        imported_at = _utc_now()
        connection.execute(
            """
            INSERT OR IGNORE INTO legacy_imports(
                store_name, source_fingerprint, imported_at, record_count
            ) VALUES (?, ?, ?, ?)
            """,
            (store_name, fingerprint, imported_at, max(0, int(record_count))),
        )
        connection.execute(
            """
            DELETE FROM legacy_imports
            WHERE store_name = ? AND source_fingerprint NOT IN (
                SELECT source_fingerprint FROM legacy_imports
                WHERE store_name = ?
                ORDER BY imported_at DESC, source_fingerprint DESC
                LIMIT 25
            )
            """,
            (store_name, store_name),
        )
        diagnostic = {
            "store": store_name,
            "record_count": max(0, int(record_count)),
            "imported_at": imported_at,
        }
        connection.execute(
            """
            INSERT INTO diagnostic_state(state_key, payload_json, updated_at)
            VALUES ('last_legacy_import', ?, ?)
            ON CONFLICT(state_key) DO UPDATE SET
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at
            """,
            (_canonical_json(diagnostic), imported_at),
        )

    def diagnostic_state_set(self, state_key: str, payload: dict) -> None:
        if state_key not in _SAFE_STATE_KEYS or not isinstance(payload, dict):
            raise ValueError("Unsupported diagnostic state")
        safe_payload = {
            str(key)[:80]: value
            for key, value in payload.items()
            if str(key) in {
                "status",
                "schema_version",
                "journal_mode",
                "foreign_keys",
                "busy_timeout_ms",
                "integrity_check",
                "checked_at",
                "version",
                "name",
                "applied_at",
                "store",
                "record_count",
                "imported_at",
            }
            and isinstance(value, (str, int, float, bool, type(None)))
        }
        updated_at = _utc_now()
        with self.connection(write=True) as connection:
            connection.execute(
                """
                INSERT INTO diagnostic_state(state_key, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(state_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (state_key, _canonical_json(safe_payload), updated_at),
            )

    def diagnostic_state_get(self, state_key: str) -> dict | None:
        if state_key not in _SAFE_STATE_KEYS:
            return None
        with self.connection() as connection:
            row = connection.execute(
                "SELECT payload_json FROM diagnostic_state WHERE state_key = ?",
                (state_key,),
            ).fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row["payload_json"])
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None


def _safe_text(value, maximum: int = 500) -> str:
    return str(value or "").strip()[:maximum]


def _safe_integer(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


class UsageHistoryRepository:
    store_name = "usage_history"

    def __init__(self, storage: CVStudioStorage):
        self.storage = storage

    @staticmethod
    def _record_key(record: dict) -> str:
        supplied = _safe_text(record.get("id"), 240)
        if supplied:
            return "id:" + supplied
        return "legacy:" + _payload_fingerprint(record)

    @staticmethod
    def _write_record(connection, record: dict, source: str, *, overwrite: bool = True) -> bool:
        payload = dict(record)
        record_id = UsageHistoryRepository._record_key(payload)
        recorded_at = _safe_text(payload.get("ts"), 80)
        updated_at = _utc_now()
        conflict_clause = (
            """
            ON CONFLICT(record_id) DO UPDATE SET
                recorded_at = excluded.recorded_at,
                payload_json = excluded.payload_json,
                source = excluded.source,
                updated_at = excluded.updated_at
            """
            if overwrite
            else "ON CONFLICT(record_id) DO NOTHING"
        )
        cursor = connection.execute(
            """
            INSERT INTO usage_history(
                record_id, recorded_at, payload_json, source, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """ + conflict_clause,
            (
                record_id,
                recorded_at,
                _canonical_json(payload),
                _safe_text(source, 40) or "sqlite",
                updated_at,
            ),
        )
        return cursor.rowcount > 0

    def import_legacy(self, records, fingerprint: str | None = None) -> int:
        if not isinstance(records, list):
            return 0
        clean = [dict(record) for record in records if isinstance(record, dict)]
        fingerprint = fingerprint or _payload_fingerprint(clean)
        with self.storage.connection(write=True) as connection:
            if self.storage.legacy_import_seen(connection, self.store_name, fingerprint):
                return 0
            count = sum(
                1 for record in clean
                if self._write_record(connection, record, "legacy", overwrite=False)
            )
            self.storage.record_legacy_import(
                connection, self.store_name, fingerprint, count
            )
        return count

    def upsert(self, records, source: str = "browser") -> int:
        if not isinstance(records, list):
            return 0
        clean = [dict(record) for record in records if isinstance(record, dict)]
        with self.storage.connection(write=True) as connection:
            for record in clean:
                self._write_record(connection, record, source, overwrite=True)
        return len(clean)

    def list(self) -> list[dict]:
        with self.storage.connection() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM usage_history
                ORDER BY CASE WHEN recorded_at = '' THEN 0 ELSE 1 END,
                         recorded_at, rowid
                """
            ).fetchall()
        result = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
            except Exception:
                continue
            if isinstance(payload, dict):
                result.append(payload)
        return result

    def clear(self) -> None:
        with self.storage.connection(write=True) as connection:
            connection.execute("DELETE FROM usage_history")


class LeadTitleCacheRepository:
    store_name = "lead_title_cache"

    def __init__(self, storage: CVStudioStorage):
        self.storage = storage

    @staticmethod
    def _entry_key(entry: dict) -> str:
        signature = {
            "family": _safe_text(entry.get("family"), 240),
            "evidence": sorted(
                _safe_text(item, 500)
                for item in (entry.get("evidence") or [])
                if _safe_text(item, 500)
            ),
        }
        return _payload_fingerprint(signature)

    @classmethod
    def _write_entry(cls, connection, entry: dict) -> bool:
        if not isinstance(entry, dict):
            return False
        family = _safe_text(entry.get("family"), 240)
        evidence = entry.get("evidence")
        if not family or not isinstance(evidence, list) or not evidence:
            return False
        payload = dict(entry)
        connection.execute(
            """
            INSERT INTO lead_title_cache(
                entry_key, family, created_at, hits, payload_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(entry_key) DO UPDATE SET
                family = excluded.family,
                created_at = excluded.created_at,
                hits = excluded.hits,
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at
            """,
            (
                cls._entry_key(payload),
                family,
                _safe_text(payload.get("created_at"), 80),
                max(0, _safe_integer(payload.get("hits"))),
                _canonical_json(payload),
                _utc_now(),
            ),
        )
        return True

    def import_legacy(self, data, fingerprint: str | None = None) -> int:
        if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
            return 0
        entries = [dict(entry) for entry in data["entries"] if isinstance(entry, dict)]
        fingerprint = fingerprint or _payload_fingerprint(data)
        with self.storage.connection(write=True) as connection:
            if self.storage.legacy_import_seen(connection, self.store_name, fingerprint):
                return 0
            count = sum(1 for entry in entries if self._write_entry(connection, entry))
            self.storage.record_legacy_import(
                connection, self.store_name, fingerprint, count
            )
        return count

    def save(self, data) -> int:
        entries = (
            [dict(entry) for entry in data.get("entries", []) if isinstance(entry, dict)]
            if isinstance(data, dict)
            else []
        )
        with self.storage.connection(write=True) as connection:
            connection.execute("DELETE FROM lead_title_cache")
            count = sum(1 for entry in entries if self._write_entry(connection, entry))
        return count

    def load(self) -> dict:
        with self.storage.connection() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM lead_title_cache
                ORDER BY created_at, rowid
                """
            ).fetchall()
        entries = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
            except Exception:
                continue
            if isinstance(payload, dict):
                entries.append(payload)
        return {"entries": entries}

    def clear(self) -> None:
        self.save({"entries": []})


class LeadContactCacheRepository:
    store_name = "lead_contact_cache"

    def __init__(self, storage: CVStudioStorage):
        self.storage = storage

    @staticmethod
    def _write_entry(connection, cache_key: str, entry: dict) -> bool:
        cache_key = _safe_text(cache_key, 800)
        if not cache_key or not isinstance(entry, dict):
            return False
        payload = dict(entry)
        connection.execute(
            """
            INSERT INTO lead_contact_cache(
                cache_key, cached_at, hits, payload_json, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                cached_at = excluded.cached_at,
                hits = excluded.hits,
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at
            """,
            (
                cache_key,
                _safe_text(payload.get("cached_at"), 80),
                max(0, _safe_integer(payload.get("hits"))),
                _canonical_json(payload),
                _utc_now(),
            ),
        )
        return True

    def import_legacy(self, data, fingerprint: str | None = None) -> int:
        if not isinstance(data, dict) or not isinstance(data.get("entries"), dict):
            return 0
        entries = data["entries"]
        fingerprint = fingerprint or _payload_fingerprint(data)
        with self.storage.connection(write=True) as connection:
            if self.storage.legacy_import_seen(connection, self.store_name, fingerprint):
                return 0
            count = sum(
                1
                for key, entry in entries.items()
                if self._write_entry(connection, key, entry)
            )
            self.storage.record_legacy_import(
                connection, self.store_name, fingerprint, count
            )
        return count

    def save(self, data) -> int:
        entries = data.get("entries", {}) if isinstance(data, dict) else {}
        if not isinstance(entries, dict):
            entries = {}
        with self.storage.connection(write=True) as connection:
            connection.execute("DELETE FROM lead_contact_cache")
            count = sum(
                1
                for key, entry in entries.items()
                if self._write_entry(connection, key, entry)
            )
        return count

    def load(self) -> dict:
        with self.storage.connection() as connection:
            rows = connection.execute(
                "SELECT cache_key, payload_json FROM lead_contact_cache ORDER BY cache_key"
            ).fetchall()
        entries = {}
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
            except Exception:
                continue
            if isinstance(payload, dict):
                entries[str(row["cache_key"])] = payload
        return {"entries": entries}

    def clear(self) -> None:
        self.save({"entries": {}})


class SalaryComponentCacheRepository:
    store_name = "salary_component_cache"

    def __init__(self, storage: CVStudioStorage):
        self.storage = storage

    @staticmethod
    def _write_entry(connection, cache_key: str, entry: dict) -> bool:
        cache_key = _safe_text(cache_key, 500)
        if not cache_key or not isinstance(entry, dict):
            return False
        payload = dict(entry)
        connection.execute(
            """
            INSERT INTO salary_component_cache(
                cache_key, saved_at, payload_json, updated_at
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                saved_at = excluded.saved_at,
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at
            """,
            (
                cache_key,
                _safe_text(payload.get("savedAt"), 80),
                _canonical_json(payload),
                _utc_now(),
            ),
        )
        return True

    def import_legacy(self, data, fingerprint: str | None = None) -> int:
        if not isinstance(data, dict):
            return 0
        fingerprint = fingerprint or _payload_fingerprint(data)
        with self.storage.connection(write=True) as connection:
            if self.storage.legacy_import_seen(connection, self.store_name, fingerprint):
                return 0
            count = sum(
                1
                for key, entry in data.items()
                if self._write_entry(connection, key, entry)
            )
            self.storage.record_legacy_import(
                connection, self.store_name, fingerprint, count
            )
        return count

    def save(self, data) -> int:
        entries = data if isinstance(data, dict) else {}
        with self.storage.connection(write=True) as connection:
            connection.execute("DELETE FROM salary_component_cache")
            count = sum(
                1
                for key, entry in entries.items()
                if self._write_entry(connection, key, entry)
            )
        return count

    def load(self) -> dict:
        with self.storage.connection() as connection:
            rows = connection.execute(
                "SELECT cache_key, payload_json FROM salary_component_cache ORDER BY rowid"
            ).fetchall()
        result = {}
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
            except Exception:
                continue
            if isinstance(payload, dict):
                result[str(row["cache_key"])] = payload
        return result

    def clear(self) -> None:
        self.save({})


class PPCMetadataRepository:
    store_name = "ppc_metadata"

    def __init__(self, storage: CVStudioStorage):
        self.storage = storage

    @staticmethod
    def _write_entry(connection, placement_id: str, metadata: dict) -> bool:
        placement_id = _safe_text(placement_id, 500)
        if not placement_id or not isinstance(metadata, dict):
            return False
        payload = dict(metadata)
        updated_at = _safe_text(payload.get("updatedAt"), 80)
        cursor = connection.execute(
            """
            INSERT INTO ppc_metadata(placement_id, metadata_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(placement_id) DO UPDATE SET
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            WHERE excluded.updated_at <> ''
              AND (ppc_metadata.updated_at = '' OR excluded.updated_at >= ppc_metadata.updated_at)
            """,
            (
                placement_id,
                _canonical_json(payload),
                updated_at,
            ),
        )
        return cursor.rowcount > 0

    def import_legacy(self, data, fingerprint: str | None = None) -> int:
        if not isinstance(data, dict):
            return 0
        fingerprint = fingerprint or _payload_fingerprint(data)
        with self.storage.connection(write=True) as connection:
            if self.storage.legacy_import_seen(connection, self.store_name, fingerprint):
                return 0
            count = sum(
                1
                for key, metadata in data.items()
                if self._write_entry(connection, key, metadata)
            )
            self.storage.record_legacy_import(
                connection, self.store_name, fingerprint, count
            )
        return count

    def upsert(self, data) -> int:
        if not isinstance(data, dict):
            return 0
        with self.storage.connection(write=True) as connection:
            count = sum(
                1
                for key, metadata in data.items()
                if self._write_entry(connection, key, metadata)
            )
        return count

    def load(self) -> dict:
        with self.storage.connection() as connection:
            rows = connection.execute(
                "SELECT placement_id, metadata_json FROM ppc_metadata ORDER BY placement_id"
            ).fetchall()
        result = {}
        for row in rows:
            try:
                payload = json.loads(row["metadata_json"])
            except Exception:
                continue
            if isinstance(payload, dict):
                result[str(row["placement_id"])] = payload
        return result

    def clear(self) -> None:
        with self.storage.connection(write=True) as connection:
            connection.execute("DELETE FROM ppc_metadata")


__all__ = [
    "BUSY_TIMEOUT_MS",
    "CVStudioStorage",
    "LeadContactCacheRepository",
    "LeadTitleCacheRepository",
    "MIGRATIONS",
    "PPCMetadataRepository",
    "SCHEMA_VERSION",
    "SalaryComponentCacheRepository",
    "StorageCorruptionError",
    "StorageBusyError",
    "StorageError",
    "StorageMigrationError",
    "StorageVersionError",
    "UsageHistoryRepository",
    "default_database_path",
    "default_state_directory",
    "_canonical_json",
    "_payload_fingerprint",
    "_utc_now",
]
