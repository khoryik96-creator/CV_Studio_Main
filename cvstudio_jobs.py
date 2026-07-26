"""Bounded persistent lifecycle state for existing CV Studio background work.

The primary application database deliberately remains at schema version 10.
This module owns a separate atomic JSON journal containing opaque job metadata
only. It never stores credentials, candidate identifiers, document content or
task results.
"""

from __future__ import annotations

from collections import OrderedDict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import threading
import time


JOB_STATE_SCHEMA = 1
JOB_STATES = frozenset(
    {
        "queued",
        "running",
        "succeeded",
        "failed",
        "cancel_requested",
        "cancelled",
        "interrupted",
        "needs_attention",
    }
)
ACTIVE_JOB_STATES = frozenset({"queued", "running", "cancel_requested"})
TERMINAL_JOB_STATES = frozenset(
    {"succeeded", "failed", "cancelled", "needs_attention"}
)
_PRUNABLE_JOB_STATES = frozenset({"succeeded", "failed", "cancelled"})
SAFE_JOB_CLASSES = frozenset({"safe_idempotent_read", "local_idempotent"})
JOB_SAFETY_CLASSES = frozenset(
    {
        "safe_idempotent_read",
        "local_idempotent",
        "paid",
        "external_mutation",
    }
)

_MAX_COUNTER = 1000000
_MAX_TIMESTAMP = 1000000000000.0
_OPAQUE_ID_RE = re.compile(r"^[a-f0-9]{64}$")
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,79}$")
_CODE_RE = re.compile(r"^[A-Z0-9_]{1,80}$")
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{0,80}$")
_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_WINDOWS_PATH_RE = re.compile(r"(?i)\b[A-Z]:\\(?:[^\\\r\n]+\\)*[^\\\r\n]*")
_POSIX_PRIVATE_PATH_RE = re.compile(
    r"(?i)(?:/Users/|/home/)[^\s\"']+"
)
_BEARER_VALUE_RE = re.compile(
    r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;}]+"
)
_SECRET_VALUE_RE = re.compile(
    r"""(?ix)(
        ["']?(?:(?:access|refresh|id)?[_-]?token|client[_-]?secret|
        api[_-]?key|password|device[_-]?code|authorization|credential|
        cookie|set[_-]?cookie|secret)["']?\s*[:=]\s*
    )(?:"(?:\\.|[^"\\\r\n])*"|'(?:\\.|[^'\\\r\n])*'|[^\s,;}]+)"""
)
_CANDIDATE_ID_RE = re.compile(
    r"""(?ix)(
        ["']?candidate(?:[_ -]?id)?["']?\s*[:=]\s*
    )(?:"(?:\\.|[^"\\\r\n])*"|'(?:\\.|[^'\\\r\n])*'|[A-Za-z0-9_.:-]+)"""
)
_JOURNAL_FIELDS = frozenset({"schema", "updated_at", "jobs"})
_RECORD_FIELDS = frozenset(
    {
        "id",
        "kind",
        "safety",
        "state",
        "stage",
        "progress_current",
        "progress_total",
        "attempts",
        "recoveries",
        "created_at",
        "started_at",
        "updated_at",
        "finished_at",
        "request_id",
        "retryable",
        "recovery_action",
        "error_code",
        "error_summary",
    }
)


class PersistentJobError(RuntimeError):
    code = "JOB_STATE_UNAVAILABLE"
    public_message = "Persistent background task state is unavailable."
    retryable = True
    recovery_action = "retry"
    http_status = 503

    def __init__(self, detail=""):
        super().__init__(self.public_message)
        self.detail = sanitize_job_text(detail)


class PersistentJobStateCorruptError(PersistentJobError):
    code = "JOB_STATE_CORRUPT"
    public_message = (
        "Persistent background task state is unreadable. Existing task state "
        "was left unchanged."
    )
    retryable = False
    recovery_action = "review_job_state"


class PersistentJobStateUnavailableError(PersistentJobError):
    pass


class PersistentJobConflictError(PersistentJobError):
    code = "JOB_ALREADY_RUNNING"
    public_message = "The matching background task is already running."
    retryable = True
    recovery_action = "retry_same_request"
    http_status = 409


class PersistentJobNeedsAttentionError(PersistentJobError):
    code = "JOB_NEEDS_ATTENTION"
    public_message = (
        "The matching background task needs review before it can run again."
    )
    retryable = False
    recovery_action = "review_before_retry"
    http_status = 409


class PersistentJobTransitionError(PersistentJobError):
    code = "JOB_STATE_CONFLICT"
    public_message = "The background task lifecycle state changed."
    retryable = True
    recovery_action = "retry_same_request"
    http_status = 409


def sanitize_job_text(value, limit=240):
    text = str(value or "").encode(
        "utf-8", errors="replace"
    ).decode("utf-8")
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", text).strip()
    text = _BEARER_VALUE_RE.sub(
        lambda match: match.group(1) + "[redacted]", text
    )
    text = _SECRET_VALUE_RE.sub(lambda match: match.group(1) + "[redacted]", text)
    text = _EMAIL_RE.sub("[email redacted]", text)
    text = _CANDIDATE_ID_RE.sub(
        lambda match: match.group(1) + "[candidate redacted]", text
    )
    text = _WINDOWS_PATH_RE.sub("[private path]", text)
    text = _POSIX_PRIVATE_PATH_RE.sub("[private path]", text)
    return text[: max(0, int(limit or 0))]


def deterministic_job_id(kind, *identity_parts):
    clean_kind = _validated_name(kind, "job kind")
    material = "\x1f".join(
        [clean_kind]
        + [str(part or "") for part in identity_parts]
    )
    return hashlib.sha256(
        material.encode("utf-8", errors="surrogatepass")
    ).hexdigest()


def default_job_state_path():
    override = str(os.environ.get("CVSTUDIO_JOB_STATE_PATH") or "").strip()
    if override:
        return Path(override).expanduser()
    database_override = str(os.environ.get("CVSTUDIO_DB_PATH") or "").strip()
    if database_override:
        return Path(database_override).expanduser().parent / "cv_studio_jobs.json"
    state_override = str(os.environ.get("CVSTUDIO_STATE_DIR") or "").strip()
    if state_override:
        return Path(state_override).expanduser() / "cv_studio_jobs.json"
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return (
                Path(base)
                / "TheGuoLab"
                / "CVStudio"
                / "cv_studio_jobs.json"
            )
        return (
            Path.home()
            / "AppData"
            / "Local"
            / "TheGuoLab"
            / "CVStudio"
            / "cv_studio_jobs.json"
        )
    return Path.home() / ".guo_lab_cv_studio" / "cv_studio_jobs.json"


def _validated_name(value, label):
    value = str(value or "").strip().lower()
    if not _NAME_RE.fullmatch(value):
        raise ValueError("Invalid {}".format(label))
    return value


def _validated_job_id(value):
    value = str(value or "").strip().lower()
    if not _OPAQUE_ID_RE.fullmatch(value):
        raise ValueError("Job ID must be an opaque SHA-256 value")
    return value


def _validated_request_id(value):
    value = str(value or "").strip()
    if not _REQUEST_ID_RE.fullmatch(value):
        return ""
    return value


def _request_id_digest(value):
    value = _validated_request_id(value)
    if not value:
        return value
    return hashlib.sha256(
        value.encode("utf-8", errors="surrogatepass")
    ).hexdigest()


def _validated_persisted_request_id(value):
    if not isinstance(value, str):
        raise ValueError("persisted request ID must be a string")
    if value and not _OPAQUE_ID_RE.fullmatch(value):
        raise ValueError("persisted request ID must be an opaque SHA-256 value")
    return value


def _validated_code(value):
    value = str(value or "").strip().upper()
    return value if _CODE_RE.fullmatch(value) else ""


def _validated_integer(value, label, minimum=0, maximum=_MAX_COUNTER):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("{} must be an integer".format(label))
    if value < minimum or value > maximum:
        raise ValueError("{} is outside its bounded range".format(label))
    return value


def _validated_timestamp(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("{} must be numeric".format(label))
    value = float(value)
    if not math.isfinite(value) or value < 0 or value > _MAX_TIMESTAMP:
        raise ValueError("{} is outside its bounded range".format(label))
    return value


def _unique_json_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate persistent job state field")
        value[key] = item
    return value


class PersistentJobStore:
    """Thread-safe atomic job journal with conservative restart recovery."""

    def __init__(
        self,
        path=None,
        *,
        max_jobs=500,
        max_bytes=2 * 1024 * 1024,
        max_recoveries=3,
        clock=None,
        replace=None,
    ):
        self.path = Path(path) if path is not None else default_job_state_path()
        self.max_jobs = max(1, min(5000, int(max_jobs or 500)))
        self.max_bytes = max(4096, min(16 * 1024 * 1024, int(max_bytes or 0)))
        self.max_recoveries = max(1, min(20, int(max_recoveries or 3)))
        self._clock = clock or time.time
        self._replace = replace or os.replace
        self._lock = threading.RLock()
        self._records = OrderedDict()
        self._initialized = False
        self._startup_recovery = {
            "interrupted": 0,
            "cancelled": 0,
            "needs_attention": 0,
            "recovery_limited": 0,
        }

    def initialize(self):
        with self._lock:
            if self._initialized:
                return dict(self._startup_recovery)
            records = self._load_records()
            recovery = {
                "interrupted": 0,
                "cancelled": 0,
                "needs_attention": 0,
                "recovery_limited": 0,
            }
            changed = False
            now = self._now()
            candidate = self._copy_records(records)
            for job_id, record in list(candidate.items()):
                state = record["state"]
                if state not in ACTIVE_JOB_STATES:
                    continue
                updated = dict(record)
                if state == "cancel_requested":
                    updated.update(
                        {
                            "state": "cancelled",
                            "stage": "cancelled",
                            "retryable": False,
                            "recovery_action": "",
                            "finished_at": now,
                            "updated_at": now,
                        }
                    )
                    recovery["cancelled"] += 1
                elif record["safety"] in SAFE_JOB_CLASSES:
                    recoveries = self._increment_counter(
                        record.get("recoveries"), "job recovery count"
                    )
                    updated["recoveries"] = recoveries
                    updated["updated_at"] = now
                    updated["finished_at"] = now
                    if recoveries <= self.max_recoveries:
                        updated.update(
                            {
                                "state": "interrupted",
                                "stage": "interrupted",
                                "retryable": True,
                                "recovery_action": "retry_same_request",
                                "error_code": "JOB_INTERRUPTED",
                                "error_summary": (
                                    "The previous process stopped before the "
                                    "safe task completed."
                                ),
                            }
                        )
                        recovery["interrupted"] += 1
                    else:
                        updated.update(
                            {
                                "state": "failed",
                                "stage": "recovery_limit",
                                "retryable": True,
                                "recovery_action": "retry_manually",
                                "error_code": "JOB_RECOVERY_LIMIT_REACHED",
                                "error_summary": (
                                    "Automatic restart reconciliation reached "
                                    "its bounded recovery limit."
                                ),
                            }
                        )
                        recovery["recovery_limited"] += 1
                else:
                    updated.update(
                        {
                            "state": "needs_attention",
                            "stage": "needs_attention",
                            "retryable": False,
                            "recovery_action": "review_before_retry",
                            "error_code": "JOB_AMBIGUOUS_AFTER_RESTART",
                            "error_summary": (
                                "CV Studio did not replay interrupted paid or "
                                "externally mutating work."
                            ),
                            "recoveries": self._increment_counter(
                                record.get("recoveries"),
                                "job recovery count",
                            ),
                            "finished_at": now,
                            "updated_at": now,
                        }
                    )
                    recovery["needs_attention"] += 1
                candidate[job_id] = updated
                changed = True
            if changed:
                self._write_records(candidate)
            self._records = candidate
            self._startup_recovery = recovery
            self._initialized = True
            return dict(recovery)

    def begin(
        self,
        job_id,
        *,
        kind,
        safety,
        request_id="",
        stage="starting",
    ):
        job_id = _validated_job_id(job_id)
        kind = _validated_name(kind, "job kind")
        safety = _validated_name(safety, "job safety class")
        if safety not in JOB_SAFETY_CLASSES:
            raise ValueError("Unsupported job safety class")
        stage = _validated_name(stage, "job stage")
        request_id = _request_id_digest(request_id)
        with self._lock:
            self._ensure_initialized()
            previous = self._records.get(job_id)
            if previous and previous["state"] in ACTIVE_JOB_STATES:
                raise PersistentJobConflictError()
            if (
                previous
                and previous["safety"] not in SAFE_JOB_CLASSES
                and previous["state"] in {"interrupted", "needs_attention"}
            ):
                raise PersistentJobNeedsAttentionError()
            if previous and (
                previous["kind"] != kind or previous["safety"] != safety
            ):
                raise PersistentJobNeedsAttentionError(
                    "Opaque job identity was reused for another task boundary."
                )
            now = self._now()
            record = {
                "id": job_id,
                "kind": kind,
                "safety": safety,
                "state": "running",
                "stage": stage,
                "progress_current": 0,
                "progress_total": 100,
                "attempts": self._increment_counter(
                    (previous or {}).get("attempts", 0),
                    "job attempt count",
                ),
                "recoveries": int((previous or {}).get("recoveries") or 0),
                "created_at": float((previous or {}).get("created_at") or now),
                "started_at": now,
                "updated_at": now,
                "finished_at": 0.0,
                "request_id": request_id,
                "retryable": False,
                "recovery_action": "",
                "error_code": "",
                "error_summary": "",
            }
            return self._commit_record(record)

    def progress(self, job_id, *, stage, current, total=100):
        job_id = _validated_job_id(job_id)
        stage = _validated_name(stage, "job stage")
        total = max(1, min(1000000, int(total or 100)))
        current = max(0, min(total, int(current or 0)))
        with self._lock:
            self._ensure_initialized()
            record = self._required_record(job_id)
            if record["state"] != "running":
                if record["state"] == "cancel_requested":
                    return dict(record)
                raise PersistentJobConflictError(
                    "Task progress cannot update a non-running job."
                )
            if (
                record["stage"] == stage
                and record["progress_current"] == current
                and record["progress_total"] == total
            ):
                return dict(record)
            updated = dict(record)
            updated.update(
                {
                    "stage": stage,
                    "progress_current": current,
                    "progress_total": total,
                    "updated_at": self._now(),
                }
            )
            return self._commit_record(updated)

    def complete(self, job_id):
        return self._finish(
            job_id,
            state="succeeded",
            stage="complete",
            retryable=False,
            recovery_action="",
            error_code="",
            error_summary="",
            allowed_states={"running", "cancel_requested"},
        )

    def fail(
        self,
        job_id,
        *,
        error_code="JOB_FAILED",
        error_summary="",
        retryable=False,
        recovery_action="",
    ):
        return self._finish(
            job_id,
            state="failed",
            stage="failed",
            retryable=bool(retryable),
            recovery_action=_validated_name(
                recovery_action, "recovery action"
            )
            if recovery_action
            else "",
            error_code=_validated_code(error_code) or "JOB_FAILED",
            error_summary=sanitize_job_text(error_summary),
            allowed_states={"running", "cancel_requested"},
        )

    def request_cancel(self, job_id):
        job_id = _validated_job_id(job_id)
        with self._lock:
            self._ensure_initialized()
            record = self._required_record(job_id)
            now = self._now()
            if record["state"] == "running":
                state = "cancel_requested"
                stage = "cancel_requested"
                finished_at = 0.0
            elif record["state"] in {"queued", "interrupted"}:
                state = "cancelled"
                stage = "cancelled"
                finished_at = now
            else:
                return dict(record)
            updated = dict(record)
            updated.update(
                {
                    "state": state,
                    "stage": stage,
                    "updated_at": now,
                    "finished_at": finished_at,
                    "retryable": False,
                    "recovery_action": "",
                }
            )
            return self._commit_record(updated)

    def request_cancel_kind(self, kind):
        kind = _validated_name(kind, "job kind")
        with self._lock:
            self._ensure_initialized()
            candidate = self._copy_records(self._records)
            now = self._now()
            changed = 0
            for job_id, record in list(candidate.items()):
                if record["kind"] != kind:
                    continue
                if record["state"] == "running":
                    updated = dict(record)
                    updated.update(
                        {
                            "state": "cancel_requested",
                            "stage": "cancel_requested",
                            "updated_at": now,
                        }
                    )
                elif record["state"] in {"queued", "interrupted"}:
                    updated = dict(record)
                    updated.update(
                        {
                            "state": "cancelled",
                            "stage": "cancelled",
                            "updated_at": now,
                            "finished_at": now,
                            "retryable": False,
                            "recovery_action": "",
                        }
                    )
                else:
                    continue
                candidate[job_id] = updated
                changed += 1
            if changed:
                self._write_records(candidate)
                self._records = candidate
            return changed

    def mark_cancelled(self, job_id):
        return self._finish(
            job_id,
            state="cancelled",
            stage="cancelled",
            retryable=False,
            recovery_action="",
            error_code="",
            error_summary="",
            allowed_states={
                "queued",
                "running",
                "cancel_requested",
                "interrupted",
            },
        )

    def get(self, job_id):
        job_id = _validated_job_id(job_id)
        with self._lock:
            self._ensure_initialized()
            record = self._records.get(job_id)
            return dict(record) if record else None

    def summary(self):
        with self._lock:
            self._ensure_initialized()
            counts = {state: 0 for state in sorted(JOB_STATES)}
            for record in self._records.values():
                counts[record["state"]] += 1
            return {
                "schema": JOB_STATE_SCHEMA,
                "jobs": len(self._records),
                "states": counts,
                "startup_recovery": dict(self._startup_recovery),
            }

    def _finish(
        self,
        job_id,
        *,
        state,
        stage,
        retryable,
        recovery_action,
        error_code,
        error_summary,
        allowed_states,
    ):
        job_id = _validated_job_id(job_id)
        with self._lock:
            self._ensure_initialized()
            record = self._required_record(job_id)
            if record["state"] in TERMINAL_JOB_STATES:
                if record["state"] == state:
                    return dict(record)
                raise PersistentJobTransitionError()
            if record["state"] not in allowed_states:
                raise PersistentJobTransitionError()
            if record["state"] == "cancel_requested" and state == "succeeded":
                state = "cancelled"
                stage = "cancelled"
            now = self._now()
            updated = dict(record)
            updated.update(
                {
                    "state": state,
                    "stage": stage,
                    "progress_current": (
                        updated["progress_total"]
                        if state == "succeeded"
                        else updated["progress_current"]
                    ),
                    "updated_at": now,
                    "finished_at": now,
                    "retryable": bool(retryable),
                    "recovery_action": recovery_action,
                    "error_code": error_code,
                    "error_summary": error_summary,
                }
            )
            return self._commit_record(updated)

    def _commit_record(self, record):
        candidate = self._copy_records(self._records)
        candidate[record["id"]] = dict(record)
        candidate = self._pruned_records(candidate)
        self._write_records(candidate)
        self._records = candidate
        return dict(record)

    def _required_record(self, job_id):
        record = self._records.get(job_id)
        if not record:
            raise PersistentJobStateUnavailableError(
                "Persistent job record was not found."
            )
        return record

    def _ensure_initialized(self):
        if not self._initialized:
            self.initialize()

    def _now(self):
        try:
            return _validated_timestamp(self._clock(), "job clock")
        except PersistentJobError:
            raise
        except Exception as exc:
            raise PersistentJobStateUnavailableError(str(exc)) from exc

    @staticmethod
    def _increment_counter(value, label):
        value = _validated_integer(value, label)
        if value >= _MAX_COUNTER:
            raise PersistentJobStateUnavailableError(
                "{} reached its bounded limit.".format(label.capitalize())
            )
        return value + 1

    @staticmethod
    def _copy_records(records):
        return OrderedDict(
            (job_id, dict(record)) for job_id, record in records.items()
        )

    def _pruned_records(self, records):
        candidate = self._copy_records(records)
        while len(candidate) > self.max_jobs:
            removable = [
                (job_id, record)
                for job_id, record in candidate.items()
                if record["state"] in _PRUNABLE_JOB_STATES
            ]
            if not removable:
                raise PersistentJobStateUnavailableError(
                    "Persistent job limit contains only protected lifecycle "
                    "state."
                )
            oldest_id, _ = min(
                removable,
                key=lambda item: (
                    float(item[1].get("updated_at") or 0),
                    item[0],
                ),
            )
            candidate.pop(oldest_id, None)
        return candidate

    def _load_records(self):
        if not self.path.exists():
            return OrderedDict()
        try:
            size = self.path.stat().st_size
            if size <= 0 or size > self.max_bytes:
                raise ValueError("invalid persistent job state size")
            raw = self.path.read_bytes()
            if len(raw) <= 0 or len(raw) > self.max_bytes:
                raise ValueError("invalid persistent job state size")
            payload = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_unique_json_object,
            )
            if not isinstance(payload, dict):
                raise ValueError("persistent job state must be an object")
            if set(payload) != _JOURNAL_FIELDS:
                raise ValueError("persistent job state fields are unsupported")
            if (
                type(payload.get("schema")) is not int
                or payload.get("schema") != JOB_STATE_SCHEMA
            ):
                raise ValueError("unsupported persistent job state schema")
            _validated_timestamp(
                payload.get("updated_at"), "journal update timestamp"
            )
            jobs = payload.get("jobs")
            if not isinstance(jobs, list) or len(jobs) > self.max_jobs:
                raise ValueError("invalid persistent job collection")
            records = OrderedDict()
            for raw_record in jobs:
                record = self._validated_record(raw_record)
                if record["id"] in records:
                    raise ValueError("duplicate persistent job ID")
                records[record["id"]] = record
            return records
        except PersistentJobError:
            raise
        except Exception as exc:
            raise PersistentJobStateCorruptError(str(exc)) from exc

    def _validated_record(self, value):
        if not isinstance(value, dict):
            raise ValueError("persistent job record must be an object")
        if set(value) != _RECORD_FIELDS:
            raise ValueError("persistent job record fields are unsupported")
        if not isinstance(value.get("id"), str):
            raise ValueError("persisted job ID must be a string")
        job_id = _validated_job_id(value.get("id"))
        if value.get("id") != job_id:
            raise ValueError("persisted job ID is not canonical")
        if not isinstance(value.get("kind"), str):
            raise ValueError("persisted job kind must be a string")
        kind = _validated_name(value.get("kind"), "job kind")
        if value.get("kind") != kind:
            raise ValueError("persisted job kind is not canonical")
        if not isinstance(value.get("safety"), str):
            raise ValueError("persisted job safety class must be a string")
        safety = _validated_name(value.get("safety"), "job safety class")
        if value.get("safety") != safety:
            raise ValueError("persisted job safety class is not canonical")
        if safety not in JOB_SAFETY_CLASSES:
            raise ValueError("unsupported persisted job safety class")
        state = value.get("state")
        if not isinstance(state, str):
            raise ValueError("persisted job state must be a string")
        if state not in JOB_STATES:
            raise ValueError("unsupported persisted job state")
        if not isinstance(value.get("stage"), str):
            raise ValueError("persisted job stage must be a string")
        stage = _validated_name(value.get("stage"), "job stage")
        if value.get("stage") != stage:
            raise ValueError("persisted job stage is not canonical")
        total = _validated_integer(
            value.get("progress_total"),
            "job progress total",
            minimum=1,
        )
        current = _validated_integer(
            value.get("progress_current"),
            "job progress current",
            maximum=total,
        )
        attempts = _validated_integer(value.get("attempts"), "job attempts")
        recoveries = _validated_integer(
            value.get("recoveries"), "job recoveries"
        )
        recovery_action = value.get("recovery_action")
        if not isinstance(recovery_action, str):
            raise ValueError("persisted recovery action must be a string")
        if recovery_action:
            canonical_action = _validated_name(
                recovery_action, "recovery action"
            )
            if recovery_action != canonical_action:
                raise ValueError("persisted recovery action is not canonical")
        error_code = value.get("error_code")
        if not isinstance(error_code, str):
            raise ValueError("persisted error code must be a string")
        if error_code and not _CODE_RE.fullmatch(error_code):
            raise ValueError("persisted error code is invalid")
        error_summary = value.get("error_summary")
        if not isinstance(error_summary, str):
            raise ValueError("persisted error summary must be a string")
        if sanitize_job_text(error_summary) != error_summary:
            raise ValueError("persisted error summary is not sanitized")
        retryable = value.get("retryable")
        if not isinstance(retryable, bool):
            raise ValueError("persisted retryable flag must be boolean")
        return {
            "id": job_id,
            "kind": kind,
            "safety": safety,
            "state": state,
            "stage": stage,
            "progress_current": current,
            "progress_total": total,
            "attempts": attempts,
            "recoveries": recoveries,
            "created_at": _validated_timestamp(
                value.get("created_at"), "job creation timestamp"
            ),
            "started_at": _validated_timestamp(
                value.get("started_at"), "job start timestamp"
            ),
            "updated_at": _validated_timestamp(
                value.get("updated_at"), "job update timestamp"
            ),
            "finished_at": _validated_timestamp(
                value.get("finished_at"), "job finish timestamp"
            ),
            "request_id": _validated_persisted_request_id(
                value.get("request_id")
            ),
            "retryable": retryable,
            "recovery_action": recovery_action,
            "error_code": error_code,
            "error_summary": error_summary,
        }

    def _write_records(self, records):
        temp_path = None
        try:
            payload = {
                "schema": JOB_STATE_SCHEMA,
                "updated_at": self._now(),
                "jobs": sorted(
                    (dict(record) for record in records.values()),
                    key=lambda record: (
                        float(record.get("updated_at") or 0),
                        record["id"],
                    ),
                ),
            }
            encoded = json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            if len(encoded) > self.max_bytes:
                raise PersistentJobStateUnavailableError(
                    "Persistent job state exceeds its bounded file size."
                )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, raw_temp_path = tempfile.mkstemp(
                prefix=self.path.name + ".",
                suffix=".tmp",
                dir=str(self.path.parent),
            )
            temp_path = Path(raw_temp_path)
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            self._replace(str(temp_path), str(self.path))
            temp_path = None
        except PersistentJobError:
            raise
        except Exception as exc:
            raise PersistentJobStateUnavailableError(str(exc)) from exc
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except Exception:
                    pass


__all__ = [
    "ACTIVE_JOB_STATES",
    "JOB_SAFETY_CLASSES",
    "JOB_STATE_SCHEMA",
    "JOB_STATES",
    "PersistentJobConflictError",
    "PersistentJobError",
    "PersistentJobNeedsAttentionError",
    "PersistentJobStateCorruptError",
    "PersistentJobStateUnavailableError",
    "PersistentJobStore",
    "PersistentJobTransitionError",
    "SAFE_JOB_CLASSES",
    "TERMINAL_JOB_STATES",
    "default_job_state_path",
    "deterministic_job_id",
    "sanitize_job_text",
]
