"""JobAdder candidate-write service for CV Studio.

The application keeps ownership of the JobAdder OAuth token lifecycle, the
critical-write concurrency guard (the ``_ja_critical_write_route`` decorator
stays on the delegating routes) and the ``JobAdderClient`` transport.  This
module holds only the JSON candidate-write handlers behind
``/jobadder/create_candidate`` and ``/jobadder/update_candidate``.  It reaches
the token refresh, request body and transport through injected callbacks and
never imports the application.  Both writes stay non-retryable
(``safe_to_retry=False``); the logic is a verbatim move of the legacy web-shell
handlers.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
from typing import Any, Callable


_JOBADDER_EMAIL_RE = re.compile(
    r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,63}", re.IGNORECASE
)
_JOBADDER_PHONE_RE = re.compile(r"\+?\d[\d\s().\-]{6,22}\d")
_JOBADDER_PHONE_LABEL_RE = re.compile(
    r"^(?:phone|mobile|contact|tel|telephone|handphone)\s*[:\-]?\s*",
    re.IGNORECASE,
)


def _jobadder_email_value(value: Any) -> str:
    """Return one valid JobAdder email from common AI/API field shapes."""
    if isinstance(value, list):
        value = value[0] if value else ""
    if isinstance(value, dict):
        value = value.get("address") or value.get("email") or ""
    match = _JOBADDER_EMAIL_RE.search(str(value or "").strip())
    if not match:
        return ""
    email = match.group(0).lower()
    return email if len(email) <= 254 else ""


def _jobadder_phone_value(value: Any) -> str:
    """Keep one plausible optional phone and discard AI-concatenated prose."""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    if isinstance(value, dict):
        value = value.get("number") or value.get("value") or ""
    raw = " ".join(str(value or "").split()).strip()
    candidates = [raw] + _JOBADDER_PHONE_RE.findall(raw)
    for candidate in candidates:
        cleaned = _JOBADDER_PHONE_LABEL_RE.sub("", candidate).strip()
        if not re.fullmatch(r"\+?[\d().\-\s]+", cleaned):
            continue
        digits = re.sub(r"\D", "", cleaned)
        if not 8 <= len(digits) <= 15:
            continue
        if re.fullmatch(r"(?:19|20)\d{6,}", digits):
            continue
        if len(cleaned) <= 50:
            return cleaned
    return ""


def _jobadder_error_summary(raw_detail: Any) -> str:
    """Extract JobAdder's readable validation reasons from an HTTP body."""
    detail = str(raw_detail or "").strip()
    if not detail:
        return "JobAdder rejected the candidate data without an explanation."
    try:
        payload = json.loads(detail)
    except (TypeError, ValueError):
        return detail[:1200]
    messages = []
    if isinstance(payload, dict):
        for key in ("message", "error", "detail", "title"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                messages.append(value.strip())
        errors = payload.get("errors")
        if isinstance(errors, list):
            for item in errors:
                if isinstance(item, dict):
                    message = str(item.get("message") or "").strip()
                    fields = item.get("fields")
                    if message and isinstance(fields, list) and fields:
                        message += " ({}).".format(", ".join(map(str, fields)))
                    if message:
                        messages.append(message)
                elif str(item or "").strip():
                    messages.append(str(item).strip())
        elif isinstance(errors, dict):
            for value in errors.values():
                if isinstance(value, list):
                    messages.extend(str(item).strip() for item in value if str(item).strip())
                elif str(value or "").strip():
                    messages.append(str(value).strip())
    if not messages:
        return detail[:1200]
    return " ".join(dict.fromkeys(messages))[:1200]


def _sanitize_jobadder_candidate_contacts(data: dict[str, Any]):
    """Normalize contacts before a create/update can reach JobAdder."""
    if "email" in data:
        email = _jobadder_email_value(data.get("email"))
        if not email and str(data.get("email") or "").strip():
            return "Email is not in a valid format. Enter one email address."
        data["email"] = email
    for key in ("phone", "mobile"):
        if key in data:
            phone = _jobadder_phone_value(data.get(key))
            if phone:
                data[key] = phone
            else:
                data.pop(key, None)
    return ""


class JobAdderWriteService:
    """Explicitly wired handlers behind the JSON candidate-write endpoints."""

    def __init__(
        self,
        *,
        jsonify: Callable[[Any], Any],
        request_json: Callable[[], Any],
        refresh_token: Callable[..., Any],
        client: Callable[[], Any],
    ):
        self._jsonify = jsonify
        self._request_json = request_json
        self._refresh_token = refresh_token
        self._client = client

    def create_candidate(self):
        """Server-side proxy: create a new candidate."""
        token = self._refresh_token(force=False)
        if not token:
            return self._jsonify({"error": "Not authenticated"}), 401
        data = self._request_json() or {}
        if not data:
            return self._jsonify({"error": "Invalid or empty JSON body"}), 400
        contact_error = _sanitize_jobadder_candidate_contacts(data)
        if contact_error:
            return self._jsonify({"error": contact_error}), 400
        try:
            # Build payload — keep non-empty values (dicts/lists are kept if non-empty)
            payload = {}
            for k, v in data.items():
                if v is None or v == "" or v == [] or v == {}: continue
                # For nested dicts, also strip if all values are empty
                if isinstance(v, dict) and all(not vv for vv in v.values()): continue
                payload[k] = v
            body = json.dumps(payload).encode()
            print(f"[JA Create] payload keys: {list(payload.keys())}", file=sys.stderr)
            _status, result = self._client().request_json(
                "candidates",
                method="POST",
                body=body,
                headers={"Content-Type": "application/json"},
                token=token,
                timeout=15,
                fallback={},
                safe_to_retry=False,
                retries=0,
            )
            return self._jsonify(result)
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            return self._jsonify({
                "error": f"JobAdder error: {e.code}",
                "detail": body,
                "jobadder_message": _jobadder_error_summary(body),
            }), e.code
        except Exception as e:
            return self._jsonify({"error": str(e)}), 500

    def update_candidate(self):
        """Update existing candidate profile fields via PUT /candidates/{id}."""
        token = self._refresh_token(force=False)
        if not token:
            return self._jsonify({"error": "Not authenticated"}), 401
        data = self._request_json() or {}
        if not data:
            return self._jsonify({"error": "Invalid or empty JSON body"}), 400
        candidate_id = data.pop("candidateId", "")
        if not candidate_id:
            return self._jsonify({"error": "Missing candidateId"}), 400
        contact_error = _sanitize_jobadder_candidate_contacts(data)
        if contact_error:
            return self._jsonify({"error": contact_error}), 400
        try:
            payload = {k: v for k, v in data.items() if v not in (None, "", [], {})}
            body = json.dumps(payload).encode()
            _status, result = self._client().request_json(
                "candidates/{}".format(candidate_id),
                method="PUT",
                body=body,
                headers={"Content-Type": "application/json"},
                token=token,
                timeout=15,
                fallback={},
                safe_to_retry=False,
                retries=0,
            )
            return self._jsonify(result)
        except urllib.error.HTTPError as e:
            body_err = e.read().decode()
            return self._jsonify({
                "error": "JobAdder error: {}".format(e.code),
                "detail": body_err,
                "jobadder_message": _jobadder_error_summary(body_err),
            }), e.code
        except Exception as e:
            return self._jsonify({"error": str(e)}), 500
