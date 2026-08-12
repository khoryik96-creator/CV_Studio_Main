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


SCHEMA_VERSION = 10
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
    SchemaMigration(
        8,
        "onenote_transfer_record_repository",
        (
            """
            CREATE TABLE onenote_transfer_records (
                record_key TEXT PRIMARY KEY,
                recorded_at TEXT NOT NULL DEFAULT '',
                sort_position INTEGER NOT NULL DEFAULT 0,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted INTEGER NOT NULL DEFAULT 0 CHECK (deleted IN (0, 1))
            )
            """,
            """
            CREATE INDEX onenote_transfer_records_active_idx
            ON onenote_transfer_records(deleted, recorded_at, sort_position)
            """,
        ),
    ),
    SchemaMigration(
        9,
        "onenote_saved_link_repository",
        (
            """
            CREATE TABLE onenote_saved_links (
                link_id TEXT PRIMARY KEY,
                sort_position INTEGER NOT NULL DEFAULT 0,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted INTEGER NOT NULL DEFAULT 0 CHECK (deleted IN (0, 1))
            )
            """,
            """
            CREATE INDEX onenote_saved_links_active_idx
            ON onenote_saved_links(deleted, sort_position)
            """,
        ),
    ),
    SchemaMigration(
        10,
        "browser_settings_repository",
        (
            """
            CREATE TABLE browser_settings (
                setting_key TEXT PRIMARY KEY,
                value_text TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                deleted INTEGER NOT NULL DEFAULT 0 CHECK (deleted IN (0, 1))
            )
            """,
            """
            CREATE INDEX browser_settings_active_idx
            ON browser_settings(deleted, setting_key)
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


_PRIVATE_RECORD_MAX_BYTES = 512 * 1024
_BROWSER_SETTING_MAX_BYTES = 2 * 1024 * 1024
_PRIVATE_JSON_DROP = object()
_PRIVATE_SECRET_FIELDS = {
    "access_token",
    "refresh_token",
    "client_secret",
    "api_key",
    "authorization",
    "authorization_code",
    "password",
    "credential",
    "credentials",
    "token",
}
_PRIVATE_SECRET_SUFFIXES = {
    "accesstoken",
    "refreshtoken",
    "clientsecret",
    "apikey",
    "authorizationcode",
    "password",
    "credential",
    "credentials",
    "bearertoken",
    "oauthtoken",
    "oauth2token",
    "authtoken",
    "idtoken",
    "sessiontoken",
    "csrftoken",
    "devicecode",
    "secret",
}
_SUSPICIOUS_SECRET_TEXT = re.compile(
    r"(?i)(?:\bBearer\s+[A-Za-z0-9._~-]{12,}|\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{12,}|"
    r"\b(?:api[_-]?key|client[_-]?secret|access[_-]?token|refresh[_-]?token)\s*[:=])"
)


def _private_secret_field(key) -> bool:
    key_text = str(key or "").strip().lower()
    if key_text in _PRIVATE_SECRET_FIELDS:
        return True
    compact = re.sub(r"[^a-z0-9]", "", key_text)
    return compact.startswith("authorization") or any(
        compact.endswith(suffix) for suffix in _PRIVATE_SECRET_SUFFIXES
    )


def _sanitize_private_json(value, depth=0):
    """Recursively preserve private feature data while excluding credentials."""

    if depth > 24:
        return _PRIVATE_JSON_DROP
    if isinstance(value, dict):
        clean = {}
        for index, (key, nested) in enumerate(value.items()):
            if index >= 10_000:
                break
            key_text = str(key or "")[:160]
            if _private_secret_field(key_text):
                continue
            safe_nested = _sanitize_private_json(nested, depth + 1)
            if safe_nested is not _PRIVATE_JSON_DROP:
                clean[key_text] = safe_nested
        return clean
    if isinstance(value, list):
        clean = []
        for nested in value[:10_000]:
            safe_nested = _sanitize_private_json(nested, depth + 1)
            if safe_nested is not _PRIVATE_JSON_DROP:
                clean.append(safe_nested)
        return clean
    if isinstance(value, str):
        return value[:262_144]
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return _PRIVATE_JSON_DROP


def _clean_private_record(record):
    if not isinstance(record, dict):
        return None
    clean = _sanitize_private_json(record)
    if not isinstance(clean, dict):
        return None
    encoded = _canonical_json(clean).encode("utf-8")
    return clean if len(encoded) <= _PRIVATE_RECORD_MAX_BYTES else None


_AI_ROUTE_FEATURES = (
    "cv_single",
    "summary",
    "appraiser",
    "the_owl",
    "the_spider",
    "cv_batch",
    "ja_create",
    "onenote_salary",
    "jd_anonymizer",
    "company_profile",
    "lead_search",
    "lead_people",
    "lead_email",
)
_AI_PROVIDERS = ("anthropic", "deepseek", "openai")
BROWSER_SETTING_KEYS = frozenset(
    {
        "cvstudio_ppc_ui_state_v1",
        "cvstudio_ppc_kpi_visibility_v1",
        "cvstudio_ppc_column_visibility_v1",
        "cvstudio_ppc_invoice_email_v1",
        "cvstudio_ppc_outlook_ms_client_v1",
        "cvstudio_ppc_outlook_drafts_v1",
        "cvstudio_onenote_spelling_correction_v1",
        "cv_studio_onenote_salary_ai_enabled_v1",
        "onenote_source_mode",
        "onenote_ms_client_id",
        "onenote_ms_tenant",
        "cvstudio_cv_text_alignment_v1",
        "cvstudio_summary_box_autofit_v1",
        "cvstudio_page_nav_pinned_v1",
        "cvstudio_spider_preview_memory_mode_v1",
        "ja_auto_upload",
        "hy_provider",
        "hy_model",
        "hy_lead_provider",
        "hy_lead_model",
        "hy_search_provider",
        "hy_enrichment_provider",
    }
    | {"hy_model_{}".format(provider) for provider in _AI_PROVIDERS}
    | {"hy_lead_model_{}".format(provider) for provider in _AI_PROVIDERS}
    | {"hy_ai_route_{}".format(feature) for feature in _AI_ROUTE_FEATURES}
    | {"hy_ai_route_model_{}".format(feature) for feature in _AI_ROUTE_FEATURES}
)


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

    def get(self, cache_key: str):
        """Fetch a single cached entry without materialising the whole map."""
        cache_key = _safe_text(cache_key, 500)
        if not cache_key:
            return None
        with self.storage.connection() as connection:
            row = connection.execute(
                "SELECT payload_json FROM salary_component_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row["payload_json"])
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def put(self, cache_key: str, entry: dict, cap: int = 0) -> bool:
        """Upsert one row and trim to the newest ``cap`` in a single transaction.

        Replaces the load-modify-save-whole-map path.  On conflict the existing
        row keeps its rowid (insertion order), so trimming the lowest rowids over
        the cap drops the oldest entries — matching the previous newest-N policy.
        """
        with self.storage.connection(write=True) as connection:
            if not self._write_entry(connection, cache_key, entry):
                return False
            if cap and cap > 0:
                connection.execute(
                    """
                    DELETE FROM salary_component_cache
                    WHERE rowid IN (
                        SELECT rowid FROM salary_component_cache
                        ORDER BY rowid DESC
                        LIMIT -1 OFFSET ?
                    )
                    """,
                    (int(cap),),
                )
        return True

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


class OneNoteTransferRepository:
    store_name = "onenote_transfer_records"
    max_records = 200

    def __init__(self, storage: CVStudioStorage):
        self.storage = storage

    @staticmethod
    def _record_key(record: dict) -> str:
        supplied = _safe_text(record.get("id"), 240)
        if supplied:
            return "id:" + supplied
        return "legacy:" + _payload_fingerprint(record)

    @classmethod
    def normalize_records(cls, records) -> list[dict] | None:
        if not isinstance(records, list) or len(records) > cls.max_records:
            return None
        clean_records = []
        for raw in records:
            clean = _clean_private_record(raw)
            if clean is None:
                return None
            clean_records.append(clean)
        return clean_records

    @classmethod
    def _prepare(cls, records) -> list[tuple[str, dict]]:
        if not isinstance(records, list):
            return []
        clean_records = []
        seen = set()
        for raw in records[: cls.max_records]:
            clean = _clean_private_record(raw)
            if clean is None:
                continue
            record_key = cls._record_key(clean)
            if record_key in seen:
                continue
            seen.add(record_key)
            clean_records.append((record_key, clean))
        return clean_records

    @staticmethod
    def _write_record(
        connection,
        record_key: str,
        record: dict,
        position: int,
        *,
        overwrite: bool,
    ) -> bool:
        conflict_clause = (
            """
            ON CONFLICT(record_key) DO UPDATE SET
                recorded_at = excluded.recorded_at,
                sort_position = excluded.sort_position,
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at,
                deleted = 0
            """
            if overwrite
            else "ON CONFLICT(record_key) DO NOTHING"
        )
        cursor = connection.execute(
            """
            INSERT INTO onenote_transfer_records(
                record_key, recorded_at, sort_position, payload_json, updated_at, deleted
            ) VALUES (?, ?, ?, ?, ?, 0)
            """ + conflict_clause,
            (
                record_key,
                _safe_text(record.get("ts"), 80),
                max(0, int(position)),
                _canonical_json(record),
                _utc_now(),
            ),
        )
        return cursor.rowcount > 0

    def import_legacy(self, records, fingerprint: str | None = None) -> int:
        records = self.normalize_records(records)
        if records is None:
            raise ValueError("OneNote transfer records are invalid or too large")
        prepared = self._prepare(records)
        fingerprint = fingerprint or _payload_fingerprint(
            [record for _, record in prepared]
        )
        with self.storage.connection(write=True) as connection:
            if self.storage.legacy_import_seen(connection, self.store_name, fingerprint):
                return 0
            count = sum(
                1
                for position, (record_key, record) in enumerate(prepared)
                if self._write_record(
                    connection,
                    record_key,
                    record,
                    position,
                    overwrite=False,
                )
            )
            self.storage.record_legacy_import(
                connection, self.store_name, fingerprint, count
            )
        return count

    def replace(self, records) -> int:
        records = self.normalize_records(records)
        if records is None:
            raise ValueError("OneNote transfer records are invalid or too large")
        prepared = self._prepare(records)
        updated_at = _utc_now()
        with self.storage.connection(write=True) as connection:
            connection.execute(
                "UPDATE onenote_transfer_records SET deleted = 1, updated_at = ? WHERE deleted = 0",
                (updated_at,),
            )
            for position, (record_key, record) in enumerate(prepared):
                self._write_record(
                    connection,
                    record_key,
                    record,
                    position,
                    overwrite=True,
                )
        return len(prepared)

    def list(self) -> list[dict]:
        with self.storage.connection() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM onenote_transfer_records
                WHERE deleted = 0
                ORDER BY CASE WHEN recorded_at = '' THEN 0 ELSE 1 END DESC,
                         recorded_at DESC, sort_position, rowid
                LIMIT ?
                """,
                (self.max_records,),
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
            connection.execute(
                "UPDATE onenote_transfer_records SET deleted = 1, updated_at = ? WHERE deleted = 0",
                (_utc_now(),),
            )


class OneNoteSavedLinkRepository:
    store_name = "onenote_saved_links"
    max_records = 100

    def __init__(self, storage: CVStudioStorage):
        self.storage = storage

    @staticmethod
    def _normalize(raw) -> dict | None:
        clean = _clean_private_record(raw)
        if clean is None:
            return None
        name = _safe_text(clean.get("name"), 80)
        link = _safe_text(clean.get("link"), 4096)
        if not name or not link:
            return None
        kind = _safe_text(clean.get("kind") or clean.get("type"), 20).lower()
        clean["kind"] = kind if kind in {"notebook", "section", "page"} else "notebook"
        clean["name"] = name
        clean["link"] = link
        link_id = _safe_text(clean.get("id"), 240)
        if not link_id:
            link_id = "legacy-" + _payload_fingerprint({"name": name, "link": link})[:32]
        clean["id"] = link_id
        clean["createdAt"] = _safe_text(clean.get("createdAt"), 80)
        clean["updatedAt"] = _safe_text(clean.get("updatedAt"), 80)
        return clean

    @classmethod
    def normalize_records(cls, records) -> list[dict] | None:
        if not isinstance(records, list) or len(records) > cls.max_records:
            return None
        clean_records = []
        for raw in records:
            clean = cls._normalize(raw)
            if clean is None:
                return None
            clean_records.append(clean)
        return clean_records

    @classmethod
    def _prepare(cls, records) -> list[dict]:
        if not isinstance(records, list):
            return []
        clean_records = []
        seen = set()
        for raw in records[: cls.max_records]:
            clean = cls._normalize(raw)
            if clean is None or clean["id"] in seen:
                continue
            seen.add(clean["id"])
            clean_records.append(clean)
        return clean_records

    @staticmethod
    def _write_link(connection, record: dict, position: int, *, overwrite: bool) -> bool:
        conflict_clause = (
            """
            ON CONFLICT(link_id) DO UPDATE SET
                sort_position = excluded.sort_position,
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at,
                deleted = 0
            """
            if overwrite
            else "ON CONFLICT(link_id) DO NOTHING"
        )
        cursor = connection.execute(
            """
            INSERT INTO onenote_saved_links(
                link_id, sort_position, payload_json, updated_at, deleted
            ) VALUES (?, ?, ?, ?, 0)
            """ + conflict_clause,
            (
                record["id"],
                max(0, int(position)),
                _canonical_json(record),
                _safe_text(record.get("updatedAt"), 80) or _utc_now(),
            ),
        )
        return cursor.rowcount > 0

    def import_legacy(self, records, fingerprint: str | None = None) -> int:
        records = self.normalize_records(records)
        if records is None:
            raise ValueError("Saved OneNote links are invalid or too large")
        prepared = self._prepare(records)
        fingerprint = fingerprint or _payload_fingerprint(prepared)
        with self.storage.connection(write=True) as connection:
            if self.storage.legacy_import_seen(connection, self.store_name, fingerprint):
                return 0
            count = sum(
                1
                for position, record in enumerate(prepared)
                if self._write_link(connection, record, position, overwrite=False)
            )
            self.storage.record_legacy_import(
                connection, self.store_name, fingerprint, count
            )
        return count

    def replace(self, records) -> int:
        records = self.normalize_records(records)
        if records is None:
            raise ValueError("Saved OneNote links are invalid or too large")
        prepared = self._prepare(records)
        with self.storage.connection(write=True) as connection:
            connection.execute(
                "UPDATE onenote_saved_links SET deleted = 1, updated_at = ? WHERE deleted = 0",
                (_utc_now(),),
            )
            for position, record in enumerate(prepared):
                self._write_link(connection, record, position, overwrite=True)
        return len(prepared)

    def list(self) -> list[dict]:
        with self.storage.connection() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM onenote_saved_links
                WHERE deleted = 0
                ORDER BY sort_position, rowid
                LIMIT ?
                """,
                (self.max_records,),
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
        self.replace([])


class BrowserSettingsRepository:
    store_name = "browser_settings"

    def __init__(self, storage: CVStudioStorage):
        self.storage = storage

    @staticmethod
    def normalize_value(setting_key: str, value) -> str | None:
        if setting_key not in BROWSER_SETTING_KEYS or not isinstance(value, str):
            return None
        if len(value.encode("utf-8")) > _BROWSER_SETTING_MAX_BYTES:
            return None
        if _SUSPICIOUS_SECRET_TEXT.search(value):
            return None
        try:
            parsed = json.loads(value)
        except Exception:
            return value
        if not isinstance(parsed, (dict, list)):
            return value
        clean = _sanitize_private_json(parsed)
        if clean is _PRIVATE_JSON_DROP:
            return None
        encoded = _canonical_json(clean)
        if len(encoded.encode("utf-8")) > _BROWSER_SETTING_MAX_BYTES:
            return None
        return encoded

    @classmethod
    def _prepare(cls, settings) -> dict[str, str]:
        if not isinstance(settings, dict):
            return {}
        clean = {}
        for key, value in settings.items():
            setting_key = str(key or "")
            normalized = cls.normalize_value(setting_key, value)
            if normalized is not None:
                clean[setting_key] = normalized
        return clean

    @staticmethod
    def _write_setting(connection, setting_key: str, value: str, *, overwrite: bool) -> bool:
        conflict_clause = (
            """
            ON CONFLICT(setting_key) DO UPDATE SET
                value_text = excluded.value_text,
                updated_at = excluded.updated_at,
                deleted = 0
            """
            if overwrite
            else "ON CONFLICT(setting_key) DO NOTHING"
        )
        cursor = connection.execute(
            """
            INSERT INTO browser_settings(setting_key, value_text, updated_at, deleted)
            VALUES (?, ?, ?, 0)
            """ + conflict_clause,
            (setting_key, value, _utc_now()),
        )
        return cursor.rowcount > 0

    def import_legacy(self, settings, fingerprint: str | None = None) -> int:
        prepared = self._prepare(settings)
        fingerprint = fingerprint or _payload_fingerprint(prepared)
        with self.storage.connection(write=True) as connection:
            if self.storage.legacy_import_seen(connection, self.store_name, fingerprint):
                return 0
            count = sum(
                1
                for key, value in prepared.items()
                if self._write_setting(connection, key, value, overwrite=False)
            )
            self.storage.record_legacy_import(
                connection, self.store_name, fingerprint, count
            )
        return count

    def upsert(self, settings) -> int:
        prepared = self._prepare(settings)
        with self.storage.connection(write=True) as connection:
            for key, value in prepared.items():
                self._write_setting(connection, key, value, overwrite=True)
        return len(prepared)

    def delete(self, setting_keys) -> int:
        keys = []
        seen = set()
        if isinstance(setting_keys, list):
            for raw_key in setting_keys:
                key = str(raw_key or "")
                if key in BROWSER_SETTING_KEYS and key not in seen:
                    seen.add(key)
                    keys.append(key)
        with self.storage.connection(write=True) as connection:
            for key in keys:
                connection.execute(
                    """
                    INSERT INTO browser_settings(setting_key, value_text, updated_at, deleted)
                    VALUES (?, '', ?, 1)
                    ON CONFLICT(setting_key) DO UPDATE SET
                        value_text = '',
                        updated_at = excluded.updated_at,
                        deleted = 1
                    """,
                    (key, _utc_now()),
                )
        return len(keys)

    def load(self) -> dict[str, str]:
        with self.storage.connection() as connection:
            rows = connection.execute(
                """
                SELECT setting_key, value_text FROM browser_settings
                WHERE deleted = 0 ORDER BY setting_key
                """
            ).fetchall()
        return {str(row["setting_key"]): str(row["value_text"]) for row in rows}


__all__ = [
    "BROWSER_SETTING_KEYS",
    "BUSY_TIMEOUT_MS",
    "BrowserSettingsRepository",
    "CVStudioStorage",
    "LeadContactCacheRepository",
    "LeadTitleCacheRepository",
    "MIGRATIONS",
    "OneNoteSavedLinkRepository",
    "OneNoteTransferRepository",
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
