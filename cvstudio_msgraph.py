"""Microsoft Graph / Outlook pure helpers (Phase 7B).

First slice of the OneNote + Outlook / MS-Graph domain extraction: the
stateless helpers that touch neither Flask, the application, the credential
stores, nor the network — tenant sanitisation, account projection, the
device-login/draft error-payload translator, and Outlook draft-input
validation. These are a verbatim move of the legacy web-shell helpers.

The stateful service handlers (token lifecycle, credential storage, Graph
calls, the OneNote/Outlook route bodies) stay in ``app.py`` for now and move in
later slices as an explicitly wired service class. This module never imports
``app``.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets as _secrets
import subprocess
import sys
import threading
import time
import urllib.error
from datetime import datetime

from cvstudio_outlook_crypto import (
    keystream as _ms_outlook_keystream,
    dpapi_transform as _ms_outlook_dpapi_transform,
    store_key as _outlook_crypto_store_key,
    protect_record as _outlook_crypto_protect_record,
    unprotect_record as _outlook_crypto_unprotect_record,
)


def _safe_json_object(text):
    """Parse a JSON string, returning ``{}`` on empty or invalid input.

    Mirrors the web shell's ``safe_json(text, {})`` for the already-decoded
    string inputs this module passes it, without depending on ``app``.
    """
    if not text or not str(text).strip():
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


def _ms_safe_tenant(value):
    tenant = re.sub(r"[^A-Za-z0-9_.-]", "", str(value or "common").strip())
    return tenant or "common"


def _ms_outlook_account_normalize(raw):
    raw = raw if isinstance(raw, dict) else {}
    return {
        "id": str(raw.get("id") or ""),
        "displayName": str(raw.get("displayName") or "").strip(),
        "email": str(raw.get("mail") or raw.get("userPrincipalName") or raw.get("email") or "").strip(),
    }


def _ms_outlook_error_payload(raw_body, status=0, context="Microsoft Outlook"):
    text = raw_body.decode(errors="replace") if isinstance(raw_body, bytes) else str(raw_body or "")
    data = _safe_json_object(text)
    err = data.get("error") if isinstance(data, dict) else None
    code = ""
    description = ""
    if isinstance(err, dict):
        code = str(err.get("code") or "")
        description = str(err.get("message") or "")
        inner = err.get("innerError") if isinstance(err.get("innerError"), dict) else {}
        if not code:
            code = str(inner.get("code") or "")
    elif isinstance(err, str):
        code = err
        description = str(data.get("error_description") or data.get("error_uri") or "")
    if not code and isinstance(data, dict):
        code = str(data.get("code") or "")
    combined = (code + " " + description + " " + text).lower()
    friendly = "{} request failed".format(context)
    action = "Review Technical details and try again."
    pending = False
    if "authorization_pending" in combined:
        friendly = "Microsoft Outlook login is still waiting for approval."
        action = "Finish the Microsoft device login, then click Finish Outlook Login again."
        pending = True
    elif "slow_down" in combined:
        friendly = "Microsoft asked CV Studio to slow down the login check."
        action = "Wait a few seconds, then click Finish Outlook Login again."
        pending = True
    elif "unauthorized_client" in combined or "aadsts700016" in combined or "invalid_client" in combined:
        friendly = "The Microsoft Outlook app Client ID is invalid or not enabled for this tenant."
        action = "Check the Client ID and tenant, then enable public-client/device-code authentication in the Microsoft app registration."
    elif "consent_required" in combined or "interaction_required" in combined:
        friendly = "Microsoft needs the Outlook permissions to be approved again."
        action = "Reconnect Outlook and approve User.Read and Mail.ReadWrite. An administrator may need to grant consent."
    elif "insufficient" in combined or "erroraccessdenied" in combined or "authorization_requestdenied" in combined:
        friendly = "The connected Microsoft account does not have permission to create Outlook drafts."
        action = "Add delegated Mail.ReadWrite to the app registration, grant consent, then reconnect Outlook."
    elif "access_denied" in combined or "authorization_declined" in combined:
        friendly = "Microsoft Outlook login was cancelled or denied."
        action = "Start the Outlook connection again and approve the requested permissions."
    elif "expired_token" in combined or "code_expired" in combined:
        friendly = "The Microsoft Outlook login code expired."
        action = "Start Outlook login again to get a fresh device code."
    elif "invalid_grant" in combined:
        friendly = "The Microsoft Outlook session expired or was revoked."
        action = "Disconnect and reconnect Outlook."
    elif status == 401:
        friendly = "The Microsoft Outlook connection expired."
        action = "Reconnect Outlook."
    elif status == 403:
        friendly = "Microsoft refused permission to create the Outlook draft."
        action = "Confirm delegated Mail.ReadWrite is granted, then reconnect Outlook."
    return {
        "error": friendly,
        "error_code": code or ("HTTP_{}".format(status) if status else "MICROSOFT_ERROR"),
        "action": action,
        "pending": pending,
        "technical_details": text[:2400],
        "status": int(status or 0),
    }


def _ms_outlook_validate_draft_input(data):
    recipient = str(data.get("to") or "").strip()
    subject = re.sub(r"[\r\n\t]+", " ", str(data.get("subject") or "")).strip()
    html_body = str(data.get("html") or "").strip()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", recipient):
        raise ValueError("Invalid Outlook draft recipient")
    if not subject:
        raise ValueError("Missing Outlook draft subject")
    if not html_body:
        raise ValueError("Missing Outlook draft HTML body")
    if len(subject) > 998 or len(html_body) > 250000:
        raise OverflowError("Outlook draft content is too large")
    return recipient, subject, html_body


class OutlookService:
    """PPC rich-Outlook-draft integration as an explicitly wired service.

    Owns the Outlook token store, device-login sessions and draft idempotency
    cache, and holds the eight ``/ppc/outlook/*`` handler bodies. The web shell
    keeps the Flask routes and calls these methods. Every application-level
    dependency (Flask ``jsonify``/request JSON, the MS token endpoint, the graph
    client factory, and the install-receipt path/machine-hash/signing-key) is
    injected at construction, so this module never imports ``app``.

    Tokens use the operating-system secret store when available (Windows DPAPI,
    macOS Keychain) and the authenticated machine-bound file only as a fallback.
    The browser never receives an access or refresh token. Draft messages are
    created only; no Microsoft Graph send endpoint is ever called. This is a
    verbatim move of the legacy web-shell helpers.
    """

    _SCOPE = "offline_access User.Read Mail.ReadWrite"
    _STORE_SCHEMA = 2
    _KEYCHAIN_SERVICE = "TheGuoLab.CVStudio.Outlook"

    def __init__(
        self,
        *,
        jsonify,
        request_json,
        token_response,
        graph_client_factory,
        receipt_path,
        machine_hash,
        signing_key,
    ):
        self._jsonify = jsonify
        self._request_json = request_json
        self._token_response = token_response
        self._receipt_path = receipt_path
        self._machine_hash = machine_hash
        self._signing_key = signing_key
        self._store_lock = threading.RLock()
        self._refresh_lock = threading.Lock()
        self._device_lock = threading.RLock()
        self._draft_lock = threading.RLock()
        self._device_store = {}
        self._draft_cache = {}
        self._store = self._load_store()
        # Migrate the v24.6.180 fallback file into the OS vault when possible.
        if self._store and self._store.get("_storage") == "legacy_machine_bound_file":
            try:
                self._save_store()
            except Exception:
                pass
        self._graph_client = graph_client_factory(
            token_provider=lambda force=False: (
                self._refresh_access_token(force=True) if force else self._token()
            ),
            reconnect_handler=self._mark_reconnect_required,
        )

    # ── storage paths ──────────────────────────────────────────────────────
    def _legacy_store_path(self):
        return os.path.join(os.path.dirname(self._receipt_path()), "outlook_token_store_v1.json")

    def _fallback_store_path(self):
        return os.path.join(os.path.dirname(self._receipt_path()), "outlook_token_store_v2.json")

    def _dpapi_store_path(self):
        return os.path.join(os.path.dirname(self._receipt_path()), "outlook_token_store_v2.dpapi")

    # ── record cryptography (delegates to cvstudio_outlook_crypto) ─────────
    def _store_key(self, schema=None):
        return _outlook_crypto_store_key(schema, self._machine_hash(), self._signing_key())

    def _protect_record(self, record, schema=None):
        return _outlook_crypto_protect_record(record, self._machine_hash(), self._signing_key(), schema=schema)

    def _unprotect_record(self, payload):
        return _outlook_crypto_unprotect_record(payload, self._machine_hash(), self._signing_key())

    # ── OS vault (DPAPI / Keychain / machine-bound file) ───────────────────
    def _keychain_account(self):
        return "cvstudio-" + self._machine_hash()[:24]

    def _keychain_available(self):
        if sys.platform != "darwin":
            return False
        try:
            proc = subprocess.run(["security", "help"], capture_output=True, timeout=5, check=False)
            return proc.returncode in (0, 1)
        except Exception:
            return False

    def _primary_storage_kind(self):
        if os.name == "nt":
            return "windows_dpapi"
        if self._keychain_available():
            return "macos_keychain"
        return "machine_bound_file"

    def _vault_read_primary(self):
        kind = self._primary_storage_kind()
        if kind == "windows_dpapi":
            path = self._dpapi_store_path()
            with open(path, "rb") as handle:
                plain = _ms_outlook_dpapi_transform(handle.read(), protect=False)
            data = json.loads(plain.decode("utf-8"))
            return (data if isinstance(data, dict) else {}), kind
        if kind == "macos_keychain":
            proc = subprocess.run(
                ["security", "find-generic-password", "-a", self._keychain_account(), "-s", self._KEYCHAIN_SERVICE, "-w"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if proc.returncode != 0:
                raise FileNotFoundError("Outlook Keychain item is unavailable")
            data = json.loads((proc.stdout or "").strip())
            return (data if isinstance(data, dict) else {}), kind
        raise FileNotFoundError("No dedicated operating-system vault")

    def _vault_write_primary(self, record):
        kind = self._primary_storage_kind()
        text = json.dumps(record, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        if kind == "windows_dpapi":
            path = self._dpapi_store_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            protected = _ms_outlook_dpapi_transform(text.encode("utf-8"), protect=True)
            temp_path = path + ".tmp"
            with open(temp_path, "wb") as handle:
                handle.write(protected)
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except Exception:
                    pass
            os.replace(temp_path, path)
            return kind
        if kind == "macos_keychain":
            proc = subprocess.run(
                ["security", "add-generic-password", "-U", "-a", self._keychain_account(), "-s", self._KEYCHAIN_SERVICE, "-w", text],
                capture_output=True, text=True, timeout=15, check=False,
            )
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or proc.stdout or "Could not save Outlook token in macOS Keychain")[:500])
            return kind
        raise RuntimeError("No dedicated operating-system vault")

    def _vault_delete_primary(self):
        kind = self._primary_storage_kind()
        try:
            if kind == "windows_dpapi":
                os.remove(self._dpapi_store_path())
            elif kind == "macos_keychain":
                subprocess.run(
                    ["security", "delete-generic-password", "-a", self._keychain_account(), "-s", self._KEYCHAIN_SERVICE],
                    capture_output=True, timeout=10, check=False,
                )
        except FileNotFoundError:
            pass
        except Exception:
            pass

    def _fallback_read(self, path=None):
        path = path or self._fallback_store_path()
        with open(path, "r", encoding="utf-8") as handle:
            return self._unprotect_record(json.load(handle))

    def _fallback_write(self, record):
        path = self._fallback_store_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        protected = self._protect_record(record)
        temp_path = path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(protected, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except Exception:
                pass
        try:
            os.chmod(temp_path, 0o600)
        except Exception:
            pass
        os.replace(temp_path, path)
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass
        return "machine_bound_file"

    # ── store lifecycle ────────────────────────────────────────────────────
    def _record_for_storage(self, store):
        account = store.get("account") if isinstance(store.get("account"), dict) else {}
        return {
            "schema": self._STORE_SCHEMA,
            "access_token": str(store.get("access_token") or ""),
            "refresh_token": str(store.get("refresh_token") or ""),
            "client_id": str(store.get("client_id") or ""),
            "tenant": _ms_safe_tenant(store.get("tenant") or "common"),
            "expires_at": int(store.get("expires_at") or 0),
            "account": {
                "id": str(account.get("id") or ""),
                "displayName": str(account.get("displayName") or ""),
                "email": str(account.get("email") or ""),
            },
        }

    def _load_store(self):
        # Primary OS vault first.
        try:
            data, kind = self._vault_read_primary()
            if data:
                data["_storage"] = kind
                return data
        except Exception:
            pass
        # Authenticated file fallback.
        try:
            data = self._fallback_read()
            if data:
                data["_storage"] = "machine_bound_file"
                return data
        except Exception:
            pass
        # One-time migration from v24.6.180's legacy protected file.
        try:
            data = self._fallback_read(self._legacy_store_path())
            if data:
                data["_storage"] = "legacy_machine_bound_file"
                return data
        except Exception:
            pass
        return {}

    def _save_store(self):
        with self._store_lock:
            record = self._record_for_storage(self._store)
            if not record["access_token"] and not record["refresh_token"]:
                self._delete_all_secret_stores()
                return
            kind = ""
            try:
                kind = self._vault_write_primary(record)
                try:
                    os.remove(self._fallback_store_path())
                except FileNotFoundError:
                    pass
            except Exception:
                kind = self._fallback_write(record)
            self._store["_storage"] = kind
            try:
                os.remove(self._legacy_store_path())
            except FileNotFoundError:
                pass
            except Exception:
                pass

    def _delete_all_secret_stores(self):
        self._vault_delete_primary()
        for path in (self._fallback_store_path(), self._legacy_store_path(), self._dpapi_store_path()):
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            except Exception:
                pass

    def _clear_store(self):
        with self._store_lock:
            self._store.clear()
            self._delete_all_secret_stores()

    # ── token lifecycle ────────────────────────────────────────────────────
    def _refresh_access_token(self, force=False):
        with self._refresh_lock:
            with self._store_lock:
                token = str(self._store.get("access_token") or "").strip()
                expires_at = int(self._store.get("expires_at") or 0)
                if token and not force and (not expires_at or time.time() < expires_at - 120):
                    return token
                refresh = str(self._store.get("refresh_token") or "").strip()
                client_id = str(self._store.get("client_id") or "").strip()
                tenant = _ms_safe_tenant(self._store.get("tenant") or "common")
            if not refresh or not client_id:
                raise PermissionError("Microsoft Outlook drafts are not connected")
            try:
                tok = self._token_response({
                    "client_id": client_id,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                    "scope": self._SCOPE,
                }, tenant=tenant)
            except Exception as exc:
                with self._store_lock:
                    self._store.pop("access_token", None)
                    self._store["expires_at"] = 0
                    self._save_store()
                raise PermissionError("Microsoft Outlook connection expired; reconnect Outlook") from exc
            access_token = str(tok.get("access_token") or "").strip()
            if not access_token:
                raise PermissionError("Microsoft returned no Outlook access token; reconnect Outlook")
            with self._store_lock:
                self._store.update({
                    "access_token": access_token,
                    "refresh_token": str(tok.get("refresh_token") or refresh),
                    "client_id": client_id,
                    "tenant": tenant,
                    "expires_at": int(time.time() + int(tok.get("expires_in") or 3300)),
                })
                self._save_store()
            return access_token

    def _token(self):
        with self._store_lock:
            token = str(self._store.get("access_token") or "").strip()
            expires_at = int(self._store.get("expires_at") or 0)
        if token and (not expires_at or time.time() < expires_at - 120):
            return token
        return self._refresh_access_token()

    def _mark_reconnect_required(self):
        with self._store_lock:
            self._store.pop("access_token", None)
            self._store["expires_at"] = 0
            try:
                self._save_store()
            except Exception:
                pass

    # ── graph calls ────────────────────────────────────────────────────────
    def graph_json(self, path, body=None, method="GET", timeout=25):
        safe_method = str(method or "GET").upper()
        return self._graph_client.request_json(
            path,
            body=body,
            method=safe_method,
            timeout=timeout,
            safe_to_retry=safe_method in ("GET", "HEAD", "OPTIONS"),
            retries=1 if safe_method in ("GET", "HEAD", "OPTIONS") else 0,
        )

    def _graph_post_json(self, path, body=None, timeout=25):
        return self.graph_json(path, body=body or {}, method="POST", timeout=timeout)

    def refresh_account(self):
        profile = self.graph_json("me?$select=id,displayName,mail,userPrincipalName", timeout=20)
        account = _ms_outlook_account_normalize(profile)
        with self._store_lock:
            self._store["account"] = account
            self._save_store()
        return account

    def public_info(self):
        with self._store_lock:
            has_access = bool(str(self._store.get("access_token") or "").strip())
            has_refresh = bool(str(self._store.get("refresh_token") or "").strip())
            account = self._store.get("account") if isinstance(self._store.get("account"), dict) else {}
            return {
                "connected": bool(has_access or has_refresh),
                "client_id": str(self._store.get("client_id") or ""),
                "tenant": self._store.get("tenant", "common"),
                "expires_at": self._store.get("expires_at", 0),
                "storage": str(self._store.get("_storage") or self._primary_storage_kind()),
                "account": {
                    "id": str(account.get("id") or ""),
                    "displayName": str(account.get("displayName") or ""),
                    "email": str(account.get("email") or ""),
                },
            }

    # ── device sessions & draft idempotency cache ─────────────────────────
    def _cleanup_device_sessions(self):
        now = time.time()
        with self._device_lock:
            for key in list(self._device_store):
                if float((self._device_store.get(key) or {}).get("expires_at") or 0) <= now:
                    self._device_store.pop(key, None)

    def _cleanup_draft_cache(self):
        now = time.time()
        cutoff = now - 1800
        abandoned_cutoff = now - 120
        with self._draft_lock:
            for key in list(self._draft_cache):
                entry = self._draft_cache.get(key) or {}
                in_progress = bool(entry.get("in_progress"))
                stamp = float(entry.get("cached_at") or entry.get("started_at") or 0)
                if (not in_progress and stamp < cutoff) or (in_progress and stamp < abandoned_cutoff):
                    removed = self._draft_cache.pop(key, None) or {}
                    event = removed.get("event")
                    if event:
                        try:
                            event.set()
                        except Exception:
                            pass

    def _draft_request_fail(self, request_id):
        if not request_id:
            return
        with self._draft_lock:
            entry = self._draft_cache.pop(request_id, None) or {}
            event = entry.get("event")
            if event:
                try:
                    event.set()
                except Exception:
                    pass

    def _draft_request_complete(self, request_id, payload_hash, result):
        if not request_id:
            return
        with self._draft_lock:
            entry = self._draft_cache.get(request_id) or {}
            event = entry.get("event")
            self._draft_cache[request_id] = {
                "payload_hash": payload_hash,
                "result": dict(result or {}),
                "cached_at": time.time(),
                "in_progress": False,
                "event": event,
            }
            if event:
                try:
                    event.set()
                except Exception:
                    pass

    def _create_draft_payload(self, recipient, subject, html_body):
        payload = {
            "subject": subject,
            "body": {"contentType": "HTML", "content": html_body},
            "toRecipients": [{"emailAddress": {"address": recipient}}],
        }
        draft = self._graph_post_json("me/messages", payload, timeout=30)
        web_link = str(draft.get("webLink") or "").strip()
        if not draft.get("id") or not web_link:
            raise RuntimeError("Microsoft created no usable Outlook draft link")
        if "ispopout=" not in web_link.lower():
            web_link += ("&" if "?" in web_link else "?") + "ispopout=1"
        return {
            "ok": True,
            "draft_id": draft.get("id"),
            "webLink": web_link,
            "isDraft": True,
            "mayRequireEditClick": True,
            "created_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }

    # ── route handler bodies (routes stay in the web shell) ────────────────
    def api_info(self):
        return self._jsonify(self.public_info())

    def test_connection(self):
        try:
            account = self.refresh_account()
            result = self.public_info()
            result.update({"ok": True, "account": account})
            return self._jsonify(result)
        except PermissionError as exc:
            return self._jsonify({"error": str(exc), "action": "Reconnect Outlook.", "needs_reconnect": True}), 401
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            payload = _ms_outlook_error_payload(body, exc.code, "Microsoft Outlook connection test")
            payload["needs_reconnect"] = exc.code in (400, 401, 403)
            return self._jsonify(payload), exc.code
        except Exception as exc:
            return self._jsonify({"error": "Could not test the Microsoft Outlook connection", "action": "Check the internet connection and try again.", "technical_details": str(exc)[:1200]}), 500

    def refresh_token(self):
        try:
            self._refresh_access_token()
            result = self.public_info()
            result.update({"ok": True, "connected": True})
            return self._jsonify(result)
        except PermissionError as exc:
            return self._jsonify({"error": str(exc), "action": "Reconnect Outlook.", "needs_reconnect": True}), 401
        except Exception as exc:
            return self._jsonify({"error": "Could not refresh Microsoft Outlook", "action": "Reconnect Outlook.", "technical_details": str(exc)[:1200], "needs_reconnect": True}), 500

    def disconnect(self):
        self._clear_store()
        with self._device_lock:
            self._device_store.clear()
        with self._draft_lock:
            self._draft_cache.clear()
        return self._jsonify({"ok": True, "connected": False, "storage": self._primary_storage_kind()})

    def device_start(self):
        data = self._request_json()
        client_id = str(data.get("client_id") or "").strip()
        tenant = _ms_safe_tenant(data.get("tenant") or "common")
        if not re.fullmatch(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}", client_id):
            return self._jsonify({"error": "Enter a valid Microsoft Outlook app Client ID", "action": "Copy the Application (client) ID from the Microsoft app registration."}), 400
        try:
            d = self._graph_client.token_request(
                {"client_id": client_id, "scope": self._SCOPE},
                tenant=tenant,
                endpoint="devicecode",
                timeout=20,
            )
            if not d.get("device_code"):
                return self._jsonify({"error": "Microsoft did not return an Outlook device code", "action": "Check the app registration and try again.", "technical_details": json.dumps(d)[:1200]}), 502
            session_id = _secrets.token_urlsafe(24)
            expires_in = max(60, int(d.get("expires_in") or 900))
            with self._device_lock:
                self._cleanup_device_sessions()
                self._device_store[session_id] = {
                    "device_code": str(d.get("device_code") or ""),
                    "client_id": client_id,
                    "tenant": tenant,
                    "expires_at": time.time() + expires_in,
                }
            return self._jsonify({
                "ok": True,
                "login_session_id": session_id,
                "user_code": d.get("user_code") or "",
                "verification_uri": d.get("verification_uri") or d.get("verification_url") or "https://microsoft.com/devicelogin",
                "expires_in": expires_in,
                "interval": int(d.get("interval") or 5),
                "message": d.get("message") or "",
            })
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            return self._jsonify(_ms_outlook_error_payload(body, exc.code, "Microsoft Outlook login")), exc.code
        except Exception as exc:
            return self._jsonify({"error": "Could not start Microsoft Outlook login", "action": "Check the internet connection and try again.", "technical_details": str(exc)[:1200]}), 500

    def device_poll(self):
        data = self._request_json()
        session_id = str(data.get("login_session_id") or "").strip()
        self._cleanup_device_sessions()
        with self._device_lock:
            current_session = self._device_store.get(session_id) or {}
            if current_session.get("_polling"):
                return self._jsonify({"error": "This Outlook login is already being checked. Wait a moment and try again."}), 409
            if current_session:
                current_session["_polling"] = True
                self._device_store[session_id] = current_session
            session = dict(current_session)
        if not session_id or not session:
            return self._jsonify({"error": "The Outlook login session expired or does not exist", "action": "Start Outlook login again."}), 400
        client_id = str(session.get("client_id") or "").strip()
        tenant = _ms_safe_tenant(session.get("tenant") or "common")
        device_code = str(session.get("device_code") or "").strip()
        try:
            tok = self._token_response({
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": client_id,
                "device_code": device_code,
            }, tenant=tenant)
            access_token = str(tok.get("access_token") or "").strip()
            if not access_token:
                return self._jsonify({"error": "Microsoft returned no Outlook access token", "action": "Restart the Outlook connection.", "technical_details": json.dumps(tok)[:1200]}), 502
            with self._store_lock:
                self._store.clear()
                self._store.update({
                    "access_token": access_token,
                    "refresh_token": str(tok.get("refresh_token") or ""),
                    "client_id": client_id,
                    "tenant": tenant,
                    "expires_at": int(time.time() + int(tok.get("expires_in") or 3300)),
                    "account": {},
                })
                self._save_store()
            try:
                account = self.refresh_account()
            except Exception:
                account = {}
            with self._device_lock:
                self._device_store.pop(session_id, None)
            result = self.public_info()
            result.update({"ok": True, "connected": True, "account": account or result.get("account")})
            return self._jsonify(result)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            payload = _ms_outlook_error_payload(body, exc.code, "Microsoft Outlook login")
            if payload.get("pending"):
                return self._jsonify(payload), 202
            if "expired" in str(payload.get("error_code") or "").lower() or exc.code in (400, 401):
                if "authorization_pending" not in body and "slow_down" not in body:
                    with self._device_lock:
                        self._device_store.pop(session_id, None)
            return self._jsonify(payload), exc.code
        except Exception as exc:
            return self._jsonify({"error": "Could not finish Microsoft Outlook login", "action": "Try again or restart the Outlook connection.", "technical_details": str(exc)[:1200]}), 500
        finally:
            with self._device_lock:
                current_session = self._device_store.get(session_id)
                if current_session:
                    current_session.pop("_polling", None)
                    self._device_store[session_id] = current_session

    def create_draft(self):
        data = self._request_json()
        request_id = str(data.get("request_id") or "").strip()
        if request_id and not re.fullmatch(r"[A-Za-z0-9_.:-]{8,180}", request_id):
            return self._jsonify({"error": "Invalid Outlook draft request ID"}), 400
        try:
            recipient, subject, html_body = _ms_outlook_validate_draft_input(data)
        except ValueError as exc:
            return self._jsonify({"error": str(exc)}), 400
        except OverflowError as exc:
            return self._jsonify({"error": str(exc)}), 413
        payload_hash = hashlib.sha256((recipient + "\n" + subject + "\n" + html_body).encode("utf-8")).hexdigest()
        self._cleanup_draft_cache()

        # Reserve this idempotency key before Graph is called. A concurrent retry
        # with the same request ID and payload waits for the first request instead
        # of creating a second draft. Different content with the same ID is rejected.
        wait_event = None
        creator = True
        if request_id:
            with self._draft_lock:
                cached = self._draft_cache.get(request_id)
                if cached:
                    if cached.get("payload_hash") != payload_hash:
                        return self._jsonify({"error": "This draft request ID was already used for different content"}), 409
                    if cached.get("result"):
                        result = dict(cached.get("result") or {})
                        result["reused"] = True
                        return self._jsonify(result)
                    wait_event = cached.get("event")
                    creator = False
                else:
                    wait_event = threading.Event()
                    self._draft_cache[request_id] = {
                        "payload_hash": payload_hash,
                        "started_at": time.time(),
                        "cached_at": time.time(),
                        "in_progress": True,
                        "event": wait_event,
                    }

        if request_id and not creator:
            if wait_event and wait_event.wait(timeout=40):
                with self._draft_lock:
                    cached = self._draft_cache.get(request_id) or {}
                    result = dict(cached.get("result") or {})
                if result:
                    result["reused"] = True
                    return self._jsonify(result)
            return self._jsonify({
                "error": "The matching Outlook draft request is still being processed",
                "action": "Wait a moment and use Open last draft or retry the same request.",
                "retry_same_request": True,
            }), 409

        try:
            result = self._create_draft_payload(recipient, subject, html_body)
            self._draft_request_complete(request_id, payload_hash, result)
            return self._jsonify(result)
        except PermissionError as exc:
            self._draft_request_fail(request_id)
            return self._jsonify({"error": str(exc), "action": "Reconnect Outlook.", "needs_reconnect": True}), 401
        except urllib.error.HTTPError as exc:
            self._draft_request_fail(request_id)
            body = exc.read().decode(errors="replace")
            payload = _ms_outlook_error_payload(body, exc.code, "Microsoft Outlook draft creation")
            payload["needs_reconnect"] = exc.code in (400, 401, 403)
            return self._jsonify(payload), exc.code
        except Exception as exc:
            self._draft_request_fail(request_id)
            return self._jsonify({"error": "Could not create the Microsoft Outlook draft", "action": "Use Copy formatted, then review Technical details.", "technical_details": str(exc)[:1200]}), 500

    def create_test_draft(self):
        try:
            account = self.refresh_account()
            recipient = str(account.get("email") or "").strip()
            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", recipient):
                return self._jsonify({"error": "The connected Microsoft account has no usable email address", "action": "Reconnect with a mailbox-enabled Microsoft account."}), 400
            body = '<div style="font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#000000;"><p>CV Studio Outlook connection test.</p><p>This is a draft only. Nothing was sent.</p></div>'
            result = self._create_draft_payload(recipient, "CV Studio Outlook draft test", body)
            result["account"] = account
            return self._jsonify(result)
        except PermissionError as exc:
            return self._jsonify({"error": str(exc), "action": "Reconnect Outlook.", "needs_reconnect": True}), 401
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            payload = _ms_outlook_error_payload(body, exc.code, "Microsoft Outlook test draft")
            payload["needs_reconnect"] = exc.code in (400, 401, 403)
            return self._jsonify(payload), exc.code
        except Exception as exc:
            return self._jsonify({"error": "Could not create the Microsoft Outlook test draft", "action": "Review Technical details and try again.", "technical_details": str(exc)[:1200]}), 500


class OneNoteGraphService:
    """OneNote Microsoft Graph connection layer as an explicitly wired service.

    Owns the OneNote token store (backend secure store), the delegated-token
    lifecycle, the shared Graph client and its JSON/bytes call helpers, the
    device-login sessions, and the six connection route handler bodies
    (api_info, store_token, refresh_token, disconnect, device_start,
    device_poll). The OneNote *content* handlers (notebooks/sections/pages/
    import) and the desktop-COM cluster stay in the web shell for now and call
    the shared Graph helpers through app-level aliases; they move in later
    slices.

    Every application dependency (Flask jsonify/request JSON, the MS token
    endpoint, the secure-store save/load/delete, and the Graph client factory)
    is injected, so this module never imports ``app``. Verbatim move of the
    legacy web-shell ``_ms_graph_*`` helpers.
    """

    _DEFAULT_SCOPE = "offline_access User.Read Notes.Read"
    _BASE = "https://graph.microsoft.com/v1.0"

    def __init__(
        self,
        *,
        jsonify,
        request_json,
        token_response,
        secure_save,
        secure_load,
        secure_delete,
        graph_client_factory,
    ):
        self._jsonify = jsonify
        self._request_json = request_json
        self._token_response = token_response
        self._secure_save = secure_save
        self._secure_delete = secure_delete
        self._store_lock = threading.RLock()
        self._device_lock = threading.RLock()
        self._refresh_lock = threading.Lock()
        self._store = {}
        self._device_store = {}
        loaded = secure_load("onenote")
        if isinstance(loaded, dict):
            self._store.update(loaded)
        self._graph_client = graph_client_factory(
            token_provider=lambda force=False: (
                self._refresh_access_token(force=True) if force else self._token()
            ),
            reconnect_handler=self._mark_reconnect_required,
        )

    # ── store / token lifecycle ────────────────────────────────────────────
    def _save_store(self):
        record = {k: self._store.get(k) for k in ("access_token", "refresh_token", "client_id", "tenant", "expires_at", "account_email", "account_name") if self._store.get(k) not in (None, "")}
        if record:
            self._store["_storage"] = self._secure_save("onenote", record)
        else:
            self._secure_delete("onenote")

    def _fetch_account(self, access_token):
        token = str(access_token or "").strip()
        if not token:
            return {}
        try:
            data = self._graph_client.request_json(
                "me?$select=displayName,mail,userPrincipalName",
                timeout=15,
                access_token=token,
            )
            return {
                "account_name": str(data.get("displayName") or "").strip(),
                "account_email": str(data.get("mail") or data.get("userPrincipalName") or "").strip(),
            }
        except Exception:
            return {}

    def _refresh_access_token(self, force=False):
        with self._refresh_lock:
            token = str(self._store.get("access_token") or "").strip()
            expires_at = int(self._store.get("expires_at") or 0)
            if token and not force and (not expires_at or expires_at > time.time() + 120):
                return token
            refresh = str(self._store.get("refresh_token") or "").strip()
            client_id = str(self._store.get("client_id") or "").strip()
            tenant = _ms_safe_tenant(self._store.get("tenant") or "common")
            if not refresh or not client_id:
                return token
            tok = self._token_response({"client_id": client_id, "grant_type": "refresh_token", "refresh_token": refresh, "scope": self._DEFAULT_SCOPE}, tenant=tenant)
            if not tok.get("access_token"):
                raise PermissionError("Microsoft OneNote refresh returned no access token")
            with self._store_lock:
                previous = dict(self._store)
                try:
                    self._store.update({
                        "access_token": tok.get("access_token", ""),
                        "refresh_token": tok.get("refresh_token", refresh),
                        "client_id": client_id,
                        "tenant": tenant,
                        "expires_at": int(time.time() + int(tok.get("expires_in") or 3300)),
                    })
                    self._store.update(self._fetch_account(self._store.get("access_token")))
                    self._save_store()
                except Exception:
                    self._store.clear(); self._store.update(previous)
                    raise
                return str(self._store.get("access_token") or "")

    def _token(self):
        return self._refresh_access_token(force=False)

    def _mark_reconnect_required(self):
        with self._store_lock:
            self._store.pop("access_token", None)
            self._store["expires_at"] = 0
            try:
                self._save_store()
            except Exception:
                pass

    # ── graph calls (shared with the content handlers via app aliases) ─────
    def graph_json(self, path, params=None, timeout=20):
        top = None
        if isinstance(params, dict):
            try:
                top = int(params.get("$top")) if params.get("$top") not in (None, "") else None
            except Exception:
                top = None
        return self._graph_client.request_json(
            path,
            params=params,
            timeout=timeout,
            paginate=bool(top and top > 0),
            max_items=max(1, min(5000, top or 100)),
        )

    def graph_post_json(self, path, body=None, params=None, timeout=25):
        return self._graph_client.request_json(
            path,
            body=body or {},
            method="POST",
            params=params,
            timeout=timeout,
            safe_to_retry=False,
            retries=0,
        )

    def graph_bytes(self, path, params=None, timeout=25):
        return self._graph_client.request_bytes(path, params=params, timeout=timeout)

    def _cleanup_device_sessions(self):
        now = time.time()
        with self._device_lock:
            for sid in list(self._device_store):
                if float((self._device_store.get(sid) or {}).get("expires_at") or 0) <= now:
                    self._device_store.pop(sid, None)

    # ── route handler bodies (routes stay in the web shell) ────────────────
    def api_info(self):
        try:
            if self._store.get("refresh_token"):
                self._refresh_access_token(force=False)
        except Exception:
            pass
        return self._jsonify({
            "connected": bool(self._store.get("access_token")),
            "client_id": self._store.get("client_id", ""),
            "tenant": self._store.get("tenant", "common"),
            "expires_at": self._store.get("expires_at", 0),
            "account_email": self._store.get("account_email", ""),
            "account_name": self._store.get("account_name", ""),
            "storage": self._store.get("_storage", "backend_secure_store"),
        })

    def store_token(self):
        """One-time migration from legacy browser token storage."""
        data = self._request_json()
        token = str(data.get("access_token") or "").strip()
        if not token:
            return self._jsonify({"ok": True, "connected": bool(self._store.get("access_token"))})
        with self._store_lock:
            previous = dict(self._store)
            try:
                self._store["access_token"] = token
                for key in ("refresh_token", "client_id"):
                    if data.get(key): self._store[key] = str(data.get(key))
                if data.get("tenant"): self._store["tenant"] = _ms_safe_tenant(data.get("tenant"))
                try: self._store["expires_at"] = int(data.get("expires_at") or time.time() + int(data.get("expires_in") or 3300))
                except Exception: self._store["expires_at"] = int(time.time() + 3300)
                self._save_store()
            except Exception:
                self._store.clear(); self._store.update(previous)
                raise
        return self._jsonify({"ok": True, "connected": True})

    def refresh_token(self):
        try:
            self._refresh_access_token(force=True)
            return self._jsonify({"ok": True, "connected": True, "expires_at": self._store.get("expires_at", 0)})
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            return self._jsonify({"error": "Microsoft token refresh failed", "status": exc.code, "detail": body[:800]}), exc.code
        except Exception as exc:
            return self._jsonify({"error": str(exc)}), 500

    def disconnect(self):
        with self._store_lock:
            self._store.clear()
            self._secure_delete("onenote")
        with self._device_lock:
            self._device_store.clear()
        return self._jsonify({"ok": True, "connected": False})

    def device_start(self):
        data = self._request_json()
        client_id = str(data.get("client_id") or "").strip()
        tenant = _ms_safe_tenant(data.get("tenant") or "common")
        if not client_id:
            return self._jsonify({"error": "Missing Microsoft app client ID"}), 400
        try:
            result = self._graph_client.token_request(
                {"client_id": client_id, "scope": self._DEFAULT_SCOPE},
                tenant=tenant,
                endpoint="devicecode",
                timeout=20,
            )
            if not result.get("device_code"):
                return self._jsonify({"error": "Microsoft did not return a device code", "detail": result}), 502
            self._cleanup_device_sessions()
            session_id = _secrets.token_urlsafe(24)
            expires_in = int(result.get("expires_in") or 900)
            with self._device_lock:
                self._device_store[session_id] = {"device_code": result.get("device_code"), "client_id": client_id, "tenant": tenant, "expires_at": time.time() + expires_in}
            public = {k: v for k, v in result.items() if k != "device_code"}
            public["login_session_id"] = session_id
            return self._jsonify(public)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            return self._jsonify({"error": "Microsoft device login failed", "status": exc.code, "detail": body[:800]}), exc.code
        except Exception as exc:
            return self._jsonify({"error": str(exc)}), 500

    def device_poll(self):
        data = self._request_json()
        session_id = str(data.get("login_session_id") or "").strip()
        if not session_id:
            return self._jsonify({"error": "Start Microsoft login first"}), 400
        self._cleanup_device_sessions()
        with self._device_lock:
            current_session = self._device_store.get(session_id) or {}
            if current_session.get("_polling"):
                return self._jsonify({"error": "This Microsoft login is already being checked. Wait a moment and try again."}), 409
            if current_session:
                current_session["_polling"] = True
                self._device_store[session_id] = current_session
            session = dict(current_session)
        if not session:
            return self._jsonify({"error": "Microsoft login session expired"}), 404
        try:
            tok = self._token_response({"grant_type": "urn:ietf:params:oauth:grant-type:device_code", "client_id": session["client_id"], "device_code": session["device_code"]}, tenant=session["tenant"])
            if not tok.get("access_token"):
                return self._jsonify({"error": "Microsoft returned no access token", "detail": tok}), 502
            with self._store_lock:
                previous = dict(self._store)
                try:
                    self._store.update({
                        "access_token": tok.get("access_token", ""),
                        "refresh_token": tok.get("refresh_token", ""),
                        "client_id": session["client_id"],
                        "tenant": session["tenant"],
                        "expires_at": int(time.time() + int(tok.get("expires_in") or 3300)),
                    })
                    self._store.update(self._fetch_account(self._store.get("access_token")))
                    self._save_store()
                except Exception:
                    self._store.clear(); self._store.update(previous)
                    raise
            with self._device_lock:
                self._device_store.pop(session_id, None)
            return self._jsonify({"ok": True, "connected": True, "client_id": session["client_id"], "tenant": session["tenant"], "expires_at": self._store["expires_at"]})
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            return self._jsonify({"error": "Microsoft login not complete", "status": exc.code, "detail": body[:800]}), exc.code
        except Exception as exc:
            return self._jsonify({"error": str(exc)}), 500
        finally:
            with self._device_lock:
                current_session = self._device_store.get(session_id)
                if current_session:
                    current_session.pop("_polling", None)
                    self._device_store[session_id] = current_session
