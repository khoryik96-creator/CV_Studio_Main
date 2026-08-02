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
import sys
import urllib.error
from typing import Any, Callable


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
        try:
            # Ensure email is flat string not array (JobAdder API requirement)
            if "email" in data and isinstance(data["email"], list):
                data["email"] = data["email"][0].get("address", "") if data["email"] else ""
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
            return self._jsonify({"error": f"JobAdder error: {e.code}", "detail": body}), e.code
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
            return self._jsonify({"error": "JobAdder error: {}".format(e.code), "detail": body_err}), e.code
        except Exception as e:
            return self._jsonify({"error": str(e)}), 500
