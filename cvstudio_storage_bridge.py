"""Behavior-preserving HTTP orchestration for CV Studio durable-storage routes.

Flask route registration intentionally remains in ``app.py``.  This module has
no application import and receives request/response adapters plus repository
providers explicitly, preserving initialization order and compatibility tests
that temporarily rebind the app-level repositories.
"""

from __future__ import annotations

import re
from typing import Any, Callable


PHASE2A_USAGE_MAX_RECORDS = 250000
PHASE2A_USAGE_SECRET_FIELDS = {
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
PHASE2A_USAGE_SECRET_SUFFIXES = {
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
    "secret",
}
PHASE2A_USAGE_DROP = object()


def phase2a_usage_secret_field(
    key: Any,
    *,
    secret_fields: set[str] | frozenset[str] = PHASE2A_USAGE_SECRET_FIELDS,
    secret_suffixes: set[str] | frozenset[str] = PHASE2A_USAGE_SECRET_SUFFIXES,
) -> bool:
    key_text = str(key or "").strip().lower()
    if key_text in secret_fields:
        return True
    compact = re.sub(r"[^a-z0-9]", "", key_text)
    return compact.startswith("authorization") or any(
        compact.endswith(suffix) for suffix in secret_suffixes
    )


def phase2a_usage_safe_value(
    value: Any,
    depth: int = 0,
    *,
    drop: Any = PHASE2A_USAGE_DROP,
    secret_field: Callable[[Any], bool] = phase2a_usage_secret_field,
) -> Any:
    if depth > 24:
        return drop
    if isinstance(value, dict):
        clean = {}
        for key, nested in value.items():
            key_text = str(key or "")[:120]
            if secret_field(key_text):
                continue
            safe_nested = phase2a_usage_safe_value(
                nested,
                depth + 1,
                drop=drop,
                secret_field=secret_field,
            )
            if safe_nested is not drop:
                clean[key_text] = safe_nested
        return clean
    if isinstance(value, list):
        clean = []
        for nested in value:
            safe_nested = phase2a_usage_safe_value(
                nested,
                depth + 1,
                drop=drop,
                secret_field=secret_field,
            )
            if safe_nested is not drop:
                clean.append(safe_nested)
        return clean
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return drop


def phase2a_usage_records(
    payload: Any,
    *,
    maximum: int = PHASE2A_USAGE_MAX_RECORDS,
    safe_value: Callable[[Any], Any] = phase2a_usage_safe_value,
) -> list[dict[str, Any]] | None:
    if not isinstance(payload, list):
        return None
    if len(payload) > maximum:
        return None
    records = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        clean = safe_value(item)
        records.append(clean if isinstance(clean, dict) else {})
    return records


def phase2a_ppc_metadata(payload: Any) -> dict[str, dict[str, str]] | None:
    if not isinstance(payload, dict) or len(payload) > 250000:
        return None
    clean = {}
    for placement_id, raw in payload.items():
        placement_id = str(placement_id or "").strip()[:500]
        if not placement_id or not isinstance(raw, dict):
            continue
        payment = str(raw.get("payment") or "")
        guarantee = str(raw.get("guaranteeMonths") or "")
        clean[placement_id] = {
            "payment": payment if payment in ("Paid", "Unpaid", "Invoiced") else "",
            "guaranteeMonths": (
                guarantee
                if re.fullmatch(r"(?:[1-6]|9|12|resigned_backout)", guarantee)
                else ""
            ),
            "updatedAt": str(raw.get("updatedAt") or "")[:80],
        }
    return clean


def phase2b_record_array(
    payload: Any,
    maximum: int,
    normalizer: Callable[[list[dict[str, Any]]], list[dict[str, Any]] | None],
) -> list[dict[str, Any]] | None:
    if (
        not isinstance(payload, list)
        or len(payload) > maximum
        or any(not isinstance(item, dict) for item in payload)
    ):
        return None
    return normalizer(payload)


def phase2b_browser_settings(
    payload: Any,
    browser_setting_keys: set[str] | frozenset[str],
    browser_setting_normalizer: Callable[[str, Any], str | None],
) -> dict[str, str] | None:
    if not isinstance(payload, dict) or len(payload) > len(browser_setting_keys):
        return None
    clean = {}
    for raw_key, value in payload.items():
        key = str(raw_key or "")
        normalized = browser_setting_normalizer(key, value)
        if normalized is None:
            return None
        clean[key] = normalized
    return clean


def phase2b_browser_setting_keys(
    payload: Any,
    browser_setting_keys: set[str] | frozenset[str],
) -> list[str] | None:
    if not isinstance(payload, list) or len(payload) > len(browser_setting_keys):
        return None
    keys = []
    seen = set()
    for raw_key in payload:
        key = str(raw_key or "")
        if key not in browser_setting_keys:
            return None
        if key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


class StorageBridge:
    """Explicitly wired handlers behind the established app-level endpoints."""

    def __init__(
        self,
        *,
        request_json: Callable[[], Any],
        jsonify: Callable[[Any], Any],
        error_payload: Callable[..., Any],
        request_id: Callable[[], str],
        usage_repository: Callable[[], Any],
        ppc_repository: Callable[[], Any],
        transfer_repository: Callable[[], Any],
        link_repository: Callable[[], Any],
        browser_settings_repository: Callable[[], Any],
        usage_records: Callable[[Any], list[dict[str, Any]] | None],
        ppc_metadata: Callable[[Any], dict[str, dict[str, str]] | None],
        record_array: Callable[
            [Any, int, Callable[[list[dict[str, Any]]], Any]], Any
        ],
        browser_settings: Callable[[Any], dict[str, str] | None],
        browser_setting_keys: Callable[[Any], list[str] | None],
    ):
        self._request_json = request_json
        self._jsonify = jsonify
        self._error_payload = error_payload
        self._request_id = request_id
        self._usage_repository = usage_repository
        self._ppc_repository = ppc_repository
        self._transfer_repository = transfer_repository
        self._link_repository = link_repository
        self._browser_settings_repository = browser_settings_repository
        self._usage_records = usage_records
        self._ppc_metadata = ppc_metadata
        self._record_array = record_array
        self._browser_settings = browser_settings
        self._browser_setting_keys = browser_setting_keys

    def _body(self) -> Any:
        return self._request_json() or {}

    def usage_history_read(self):
        return self._jsonify(
            {
                "ok": True,
                "records": self._usage_repository().list(),
                "request_id": self._request_id(),
                "legacy_preserved": True,
            }
        )

    def usage_history_import(self):
        body = self._body()
        records = self._usage_records(body.get("records"))
        if records is None:
            return self._error_payload(
                "STORAGE_PAYLOAD_INVALID",
                "Usage history payload is invalid or too large",
                400,
            )
        repository = self._usage_repository()
        imported = repository.import_legacy(records)
        return self._jsonify(
            {
                "ok": True,
                "imported": imported,
                "records": repository.list(),
                "request_id": self._request_id(),
                "legacy_preserved": True,
            }
        )

    def usage_history_upsert(self):
        body = self._body()
        records = self._usage_records(body.get("records"))
        if records is None:
            return self._error_payload(
                "STORAGE_PAYLOAD_INVALID",
                "Usage history payload is invalid or too large",
                400,
            )
        written = self._usage_repository().upsert(records)
        return self._jsonify(
            {
                "ok": True,
                "written": written,
                "request_id": self._request_id(),
                "legacy_preserved": True,
            }
        )

    def usage_history_clear(self):
        self._usage_repository().clear()
        return self._jsonify(
            {
                "ok": True,
                "request_id": self._request_id(),
                "legacy_preserved": True,
            }
        )

    def ppc_metadata_read(self):
        return self._jsonify(
            {
                "ok": True,
                "metadata": self._ppc_repository().load(),
                "request_id": self._request_id(),
                "legacy_preserved": True,
            }
        )

    def ppc_metadata_import(self):
        body = self._body()
        metadata = self._ppc_metadata(body.get("metadata"))
        if metadata is None:
            return self._error_payload(
                "STORAGE_PAYLOAD_INVALID",
                "PPC metadata payload is invalid or too large",
                400,
            )
        repository = self._ppc_repository()
        imported = repository.import_legacy(metadata)
        return self._jsonify(
            {
                "ok": True,
                "imported": imported,
                "metadata": repository.load(),
                "request_id": self._request_id(),
                "legacy_preserved": True,
            }
        )

    def ppc_metadata_upsert(self):
        body = self._body()
        metadata = self._ppc_metadata(body.get("metadata"))
        if metadata is None:
            return self._error_payload(
                "STORAGE_PAYLOAD_INVALID",
                "PPC metadata payload is invalid or too large",
                400,
            )
        written = self._ppc_repository().upsert(metadata)
        return self._jsonify(
            {
                "ok": True,
                "written": written,
                "request_id": self._request_id(),
                "legacy_preserved": True,
            }
        )

    def ppc_metadata_clear(self):
        self._ppc_repository().clear()
        return self._jsonify(
            {
                "ok": True,
                "request_id": self._request_id(),
                "legacy_preserved": True,
            }
        )

    def onenote_transfer_read(self):
        return self._jsonify(
            {
                "ok": True,
                "records": self._transfer_repository().list(),
                "request_id": self._request_id(),
                "legacy_preserved": True,
            }
        )

    def onenote_transfer_import(self):
        body = self._body()
        repository = self._transfer_repository()
        records = self._record_array(
            body.get("records"), 200, repository.normalize_records
        )
        if records is None:
            return self._error_payload(
                "STORAGE_PAYLOAD_INVALID",
                "OneNote transfer record payload is invalid or too large",
                400,
            )
        imported = repository.import_legacy(records)
        return self._jsonify(
            {
                "ok": True,
                "imported": imported,
                "records": repository.list(),
                "request_id": self._request_id(),
                "legacy_preserved": True,
            }
        )

    def onenote_transfer_replace(self):
        body = self._body()
        repository = self._transfer_repository()
        records = self._record_array(
            body.get("records"), 200, repository.normalize_records
        )
        if records is None:
            return self._error_payload(
                "STORAGE_PAYLOAD_INVALID",
                "OneNote transfer record payload is invalid or too large",
                400,
            )
        written = repository.replace(records)
        return self._jsonify(
            {
                "ok": True,
                "written": written,
                "request_id": self._request_id(),
                "legacy_preserved": True,
            }
        )

    def onenote_transfer_clear(self):
        self._transfer_repository().clear()
        return self._jsonify(
            {
                "ok": True,
                "request_id": self._request_id(),
                "legacy_preserved": True,
            }
        )

    def onenote_links_read(self):
        return self._jsonify(
            {
                "ok": True,
                "links": self._link_repository().list(),
                "request_id": self._request_id(),
                "legacy_preserved": True,
            }
        )

    def onenote_links_import(self):
        body = self._body()
        repository = self._link_repository()
        links = self._record_array(
            body.get("links"), 100, repository.normalize_records
        )
        if links is None:
            return self._error_payload(
                "STORAGE_PAYLOAD_INVALID",
                "Saved OneNote link payload is invalid or too large",
                400,
            )
        imported = repository.import_legacy(links)
        return self._jsonify(
            {
                "ok": True,
                "imported": imported,
                "links": repository.list(),
                "request_id": self._request_id(),
                "legacy_preserved": True,
            }
        )

    def onenote_links_replace(self):
        body = self._body()
        repository = self._link_repository()
        links = self._record_array(
            body.get("links"), 100, repository.normalize_records
        )
        if links is None:
            return self._error_payload(
                "STORAGE_PAYLOAD_INVALID",
                "Saved OneNote link payload is invalid or too large",
                400,
            )
        written = repository.replace(links)
        return self._jsonify(
            {
                "ok": True,
                "written": written,
                "request_id": self._request_id(),
                "legacy_preserved": True,
            }
        )

    def browser_settings_read(self):
        return self._jsonify(
            {
                "ok": True,
                "settings": self._browser_settings_repository().load(),
                "request_id": self._request_id(),
                "legacy_preserved": True,
            }
        )

    def browser_settings_import(self):
        body = self._body()
        settings = self._browser_settings(body.get("settings"))
        if settings is None:
            return self._error_payload(
                "STORAGE_PAYLOAD_INVALID",
                "Browser setting payload contains an unsupported key or value",
                400,
            )
        repository = self._browser_settings_repository()
        imported = repository.import_legacy(settings)
        return self._jsonify(
            {
                "ok": True,
                "imported": imported,
                "settings": repository.load(),
                "request_id": self._request_id(),
                "legacy_preserved": True,
            }
        )

    def browser_settings_upsert(self):
        body = self._body()
        settings = self._browser_settings(body.get("settings"))
        if settings is None:
            return self._error_payload(
                "STORAGE_PAYLOAD_INVALID",
                "Browser setting payload contains an unsupported key or value",
                400,
            )
        written = self._browser_settings_repository().upsert(settings)
        return self._jsonify(
            {
                "ok": True,
                "written": written,
                "request_id": self._request_id(),
                "legacy_preserved": True,
            }
        )

    def browser_settings_delete(self):
        body = self._body()
        keys = self._browser_setting_keys(body.get("keys"))
        if keys is None:
            return self._error_payload(
                "STORAGE_PAYLOAD_INVALID",
                "Browser setting delete payload contains an unsupported key",
                400,
            )
        deleted = self._browser_settings_repository().delete(keys)
        return self._jsonify(
            {
                "ok": True,
                "deleted": deleted,
                "request_id": self._request_id(),
                "legacy_preserved": True,
            }
        )
