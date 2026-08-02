"""Read-only JobAdder proxy service for CV Studio.

The application keeps ownership of the JobAdder OAuth token lifecycle, the
shared credentials store and the ``JobAdderClient`` transport.  This module
holds only the read-only proxy handlers behind ``/jobadder/api_info``,
``/jobadder/search_candidate``, ``/jobadder/lists``, ``/jobadder/get_candidate``
and ``/jobadder/debug_endpoints``.  It reaches the token refresh, transport,
public-info projection, credentials store and API-path helper through injected
callbacks resolved at call time, and never imports the application or performs a
write.  The logic is a verbatim move of the legacy web-shell handlers.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
from typing import Any, Callable


class JobAdderReadService:
    """Explicitly wired handlers behind the read-only JobAdder proxy endpoints."""

    def __init__(
        self,
        *,
        jsonify: Callable[[Any], Any],
        query_arg: Callable[..., str],
        refresh_token: Callable[..., Any],
        client: Callable[[], Any],
        public_info: Callable[[], dict],
        creds_store: Callable[[], dict],
        ja_api: Callable[[str], str],
    ):
        self._jsonify = jsonify
        self._query_arg = query_arg
        self._refresh_token = refresh_token
        self._client = client
        self._public_info = public_info
        self._creds_store = creds_store
        self._ja_api = ja_api

    def api_info(self):
        try:
            if self._creds_store().get("refresh_token"):
                self._refresh_token(force=False)
        except Exception:
            pass
        return self._jsonify(self._public_info())

    def search_candidate(self):
        """Server-side proxy: search candidate by email."""
        email = self._query_arg("email", "")
        token = self._refresh_token(force=False)
        if not token:
            return self._jsonify({"error": "Not authenticated"}), 401
        try:
            _status, payload = self._client().request_json(
                "candidates?email=" + urllib.parse.quote(email),
                token=token,
                timeout=15,
                fallback={"items": []},
            )
            return self._jsonify(payload)
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            return self._jsonify({"error": f"JobAdder error: {e.code}", "detail": body}), e.code
        except Exception as e:
            return self._jsonify({"error": str(e)}), 500

    def lists(self):
        """Fetch JobAdder list values (worktype, currency etc.) for UI."""
        token = self._refresh_token(force=False)
        if not token:
            return self._jsonify({"error": "Not authenticated"}), 401
        list_name = str(self._query_arg("name", "worktype") or "worktype").strip().lower()
        if not re.fullmatch(r"[a-z0-9_-]+", list_name):
            return self._jsonify({"error": "Invalid JobAdder list name"}), 400
        # JobAdder exposes work types as /v2/worktypes, not /v2/lists/worktype.
        endpoint = "worktypes" if list_name in {"worktype", "worktypes"} else "lists/" + list_name
        try:
            _status, payload = self._client().request_json(
                endpoint,
                token=token,
                timeout=10,
                fallback={},
            )
            return self._jsonify(payload)
        except urllib.error.HTTPError as e:
            return self._jsonify({"error": "JobAdder error: {}".format(e.code), "detail": e.read().decode()}), e.code
        except Exception as e:
            return self._jsonify({"error": str(e)}), 500

    def get_candidate(self):
        """Fetch full candidate record to inspect field structure."""
        token = self._refresh_token(force=False)
        candidate_id = self._query_arg("candidate_id", "")
        if not token or not candidate_id:
            return self._jsonify({"error": "Need token and candidate_id"}), 400
        try:
            _status, payload = self._client().request_json(
                "candidates/{}".format(candidate_id),
                token=token,
                timeout=10,
                fallback={},
            )
            return self._jsonify(payload)
        except urllib.error.HTTPError as e:
            return self._jsonify({"error": e.code, "detail": e.read().decode()}), e.code
        except Exception as e:
            return self._jsonify({"error": str(e)}), 500

    def debug_endpoints(self):
        """Test which candidate endpoints are available — returns OPTIONS/HEAD info."""
        token = self._refresh_token(force=False)
        candidate_id = self._query_arg("candidate_id", "")
        if not token or not candidate_id:
            return self._jsonify({"error": "Need token and candidate_id param"}), 400
        results = {}
        endpoints = [
            (self._ja_api("candidates/{}".format(candidate_id)), True),
            (self._ja_api("candidates/{}/resume".format(candidate_id)), False),
            (self._ja_api("candidates/{}/attachments".format(candidate_id)), True),
            (self._ja_api("candidates/{}/documents".format(candidate_id)), True),
        ]
        for url, accept_json in endpoints:
            try:
                response = self._client().request_raw(
                    url,
                    token=token,
                    timeout=10,
                    headers={"Accept": "application/json"} if accept_json else None,
                )
                results[url] = {"status": response.status, "ok": True}
            except urllib.error.HTTPError as e:
                results[url] = {"status": e.code, "ok": False, "detail": e.read().decode()[:200]}
            except Exception as e:
                results[url] = {"error": str(e)}
        return self._jsonify(results)
