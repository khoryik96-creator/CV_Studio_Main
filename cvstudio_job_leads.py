"""Local business-development leads, isolated from the existing schema-10 DB.

No Flask, browser, AI or network dependencies. Writes are transactional and
revision-checked; duplicate LinkedIn job IDs never overwrite existing notes.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import parse_qs, urlsplit
import uuid

STATUSES = {"new": "New", "to_contact": "To contact", "contacted": "Contacted",
            "follow_up": "Following up", "won": "Won", "closed": "Closed"}
FIELDS = {"url": 2048, "company": 200, "role": 240, "contact": 400,
          "location": 240, "notes": 10000, "description": 20000,
          "status": 20, "follow_up": 10}
MAX_RECORDS = 5000
MAX_BYTES = 8 * 1024 * 1024
APPLICATION_ID = 0x43564A4C


class JobLeadsError(ValueError):
    def __init__(self, message, status=400, code="JOB_LEADS_INVALID"):
        super().__init__(message)
        self.status, self.code = status, code
        self.retryable = status == 503 and code == "JOB_LEADS_STORAGE"


def job_url(value):
    """Canonical identity for a job view link or the selected job in search."""
    if not isinstance(value, str) or len(value) > 2048:
        return ""
    try:
        u = urlsplit(value.strip())
        if (u.scheme != "https" or u.hostname not in {"linkedin.com", "www.linkedin.com", "my.linkedin.com", "sg.linkedin.com"}
                or u.username or u.password or u.port or "\\" in value):
            return ""
        match = re.fullmatch(r"/jobs/view/(?:[^/]*-)?([0-9]{1,24})/?", u.path)
        if match:
            identity = match.group(1)
        elif re.fullmatch(r"/jobs(?:/search|/collections/[^/]+)?/?", u.path):
            values = parse_qs(u.query).get("currentJobId", [])
            identity = values[0] if len(values) == 1 else ""
        else:
            return ""
        return "https://www.linkedin.com/jobs/view/" + identity if re.fullmatch(r"[0-9]{1,24}", identity) else ""
    except ValueError:
        return ""


def clean_record(raw):
    if not isinstance(raw, dict):
        raise JobLeadsError("Enter the job details first.")
    result = {}
    for key, limit in FIELDS.items():
        value = raw.get(key, "new" if key == "status" else "")
        if not isinstance(value, str) or len(value) > limit or "\x00" in value:
            raise JobLeadsError("A job field is too long or has an invalid value.")
        result[key] = value.strip()
    result["url"] = job_url(result["url"])
    if not result["url"]:
        raise JobLeadsError("Paste a LinkedIn job ad link, such as https://www.linkedin.com/jobs/view/1234567890.")
    if not result["company"] or not result["role"]:
        raise JobLeadsError("Enter both the company and role before saving.")
    if result["status"] not in STATUSES:
        raise JobLeadsError("Choose a valid lead status.")
    if result["follow_up"]:
        try:
            if date.fromisoformat(result["follow_up"]).isoformat() != result["follow_up"]:
                raise ValueError()
        except ValueError:
            raise JobLeadsError("Choose a valid follow-up date.") from None
    return result


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class JobLeadsStore:
    def __init__(self, path):
        self.path = Path(path)

    @staticmethod
    def _verify(connection):
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise JobLeadsError("Job Leads storage needs repair. Preserve its files and restore a verified database backup before retrying.", 503, "JOB_LEADS_CORRUPT")

    def _initialize(self, connection):
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            # Consistent, integrity-verified backup BEFORE the first schema change.
            backup_dir = self.path.parent / "job_leads_backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / ("before-v1-" + uuid.uuid4().hex + ".sqlite3")
            with sqlite3.connect(str(backup)) as destination:
                connection.backup(destination)
                self._verify(destination)
            # Re-check under a cross-process lock: another request may have
            # completed initialization while the backup was being created.
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("PRAGMA user_version").fetchone()[0] == 0:
                tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                if tables:
                    raise JobLeadsError("This Job Leads database has an unrecognized format. Preserve it and use a compatible backup.", 503, "JOB_LEADS_INCOMPATIBLE")
                connection.execute("CREATE TABLE leads (id TEXT PRIMARY KEY, url TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("PRAGMA application_id=" + str(APPLICATION_ID))
                connection.execute("PRAGMA user_version=1")
            connection.commit()
        if (connection.execute("PRAGMA user_version").fetchone()[0] != 1 or
                connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID):
            raise JobLeadsError("This Job Leads database requires a compatible CV Studio version. Preserve it before restoring a backup.", 503, "JOB_LEADS_INCOMPATIBLE")
        self._verify(connection)

    @contextmanager
    def _connection(self):
        connection = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(str(self.path), timeout=5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout=5000")
            self._initialize(connection)
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection
        except (sqlite3.Error, OSError) as error:
            code = getattr(error, "sqlite_errorcode", None)
            if isinstance(code, int) and (code & 0xFF) in {sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB, sqlite3.SQLITE_FORMAT}:
                raise JobLeadsError("Job Leads storage is corrupt. Close CV Studio, preserve its database files, and restore a verified database backup before retrying.", 503, "JOB_LEADS_CORRUPT") from None
            raise JobLeadsError("Job Leads could not read or save local data. Check disk space and folder access, close duplicate windows, then retry. Your existing records were preserved.", 503, "JOB_LEADS_STORAGE") from None
        finally:
            if connection is not None:
                if connection.in_transaction:
                    try:
                        connection.rollback()
                    except sqlite3.Error:
                        pass
                connection.close()

    @staticmethod
    def _record(row):
        if row is None:
            raise JobLeadsError("This lead no longer exists. Refresh your list.", 404)
        try:
            return {**clean_record(json.loads(row["payload"])), "id": row["id"], "revision": row["revision"],
                    "created_at": row["created_at"], "updated_at": row["updated_at"]}
        except (ValueError, TypeError):
            raise JobLeadsError("A saved Job Leads record needs repair. Preserve the database and restore a verified database backup.", 503, "JOB_LEADS_CORRUPT") from None

    @staticmethod
    def _check_capacity(connection):
        count, size = connection.execute("SELECT COUNT(*), COALESCE(SUM(LENGTH(CAST(payload AS BLOB))),0) FROM leads").fetchone()
        if count > MAX_RECORDS or size > MAX_BYTES:
            raise JobLeadsError("Job Leads storage is full (5,000 leads or 8 MB). Export a backup before making further changes.")

    def list(self):
        with self._connection() as connection:
            return [self._record(row) for row in connection.execute("SELECT * FROM leads ORDER BY updated_at DESC, id")]

    def save(self, raw):
        data = clean_record(raw)
        identity, revision = raw.get("id", ""), raw.get("revision")
        if identity and (not isinstance(identity, str) or not re.fullmatch(r"[a-f0-9]{32}", identity)):
            raise JobLeadsError("Invalid saved lead. Refresh the list.")
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            duplicate = connection.execute("SELECT * FROM leads WHERE url=?", (data["url"],)).fetchone()
            if duplicate and duplicate["id"] != identity:
                return {"record": self._record(duplicate), "duplicate": True}
            now = _now()
            if identity:
                current = connection.execute("SELECT * FROM leads WHERE id=?", (identity,)).fetchone()
                if current is None:
                    raise JobLeadsError("This lead no longer exists. Refresh your list.", 404)
                if type(revision) is not int or revision != current["revision"]:
                    raise JobLeadsError("This lead changed in another window. Refresh and reopen it before saving. Your draft is still here.", 409, "JOB_LEADS_CONFLICT")
                connection.execute("UPDATE leads SET url=?,payload=?,revision=revision+1,updated_at=? WHERE id=?", (data["url"], json.dumps(data, ensure_ascii=False), now, identity))
            else:
                identity = uuid.uuid4().hex
                connection.execute("INSERT INTO leads VALUES (?,?,?,?,?,?)", (identity, data["url"], json.dumps(data, ensure_ascii=False), 1, now, now))
            self._check_capacity(connection)
            result = self._record(connection.execute("SELECT * FROM leads WHERE id=?", (identity,)).fetchone())
            connection.commit()
            return {"record": result, "duplicate": False}

    def restore(self, payload):
        if (not isinstance(payload, dict) or payload.get("format") != "cvstudio-job-leads" or
                payload.get("version") != 1 or not isinstance(payload.get("records"), list) or len(payload["records"]) > MAX_RECORDS):
            raise JobLeadsError("Choose a valid Job Leads backup file.")
        rows = [clean_record(raw) for raw in payload["records"]]
        added = skipped = 0
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for data in rows:
                if connection.execute("SELECT 1 FROM leads WHERE url=?", (data["url"],)).fetchone():
                    skipped += 1
                    continue
                now = _now()
                connection.execute("INSERT INTO leads VALUES (?,?,?,?,?,?)", (uuid.uuid4().hex, data["url"], json.dumps(data, ensure_ascii=False), 1, now, now))
                added += 1
            self._check_capacity(connection)
            connection.commit()
        return {"added": added, "skipped": skipped}

    def backup(self):
        return {"format": "cvstudio-job-leads", "version": 1, "records": self.list()}
