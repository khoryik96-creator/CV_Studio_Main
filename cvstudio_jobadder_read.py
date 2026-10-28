"""Read-only JobAdder proxy service for CV Studio.

The application keeps ownership of the JobAdder OAuth token lifecycle, the
shared credentials store and the ``JobAdderClient`` transport.  This module
holds only the read-only proxy handlers behind ``/jobadder/api_info``,
``/jobadder/search_candidate``, ``/jobadder/lists``, ``/jobadder/get_candidate``,
``/jobadder/debug_endpoints`` and ``/jobadder/client_contacts``.  It reaches the
token refresh, transport, public-info projection, credentials store and API-path
helper through injected callbacks resolved at call time, and never imports the
application or performs a write.  The first five handlers are a verbatim move of
the legacy web-shell handlers.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
from typing import Any, Callable


CLIENT_CONTACTS_MAX_OFFSET = 1_000_000
CLIENT_CONTACTS_MAX_LIMIT = 100


def _bounded_text(value, limit):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit] if isinstance(value, (str, int, float)) else ""


def _client_contact_summary(item):
    """The few fields the email scan shows, or None for an unusable record.

    Only what the dashboard needs leaves this process: the contact's id (for the
    JobAdder link), name, company, primary email and whether JobAdder marks the
    contact as no longer with the company. Status, phone numbers, owners, notes
    and custom fields are left behind.
    """
    if not isinstance(item, dict):
        return None
    contact_id = item.get("contactId")
    if isinstance(contact_id, bool) or not isinstance(contact_id, int) or contact_id <= 0:
        return None
    company = item.get("company") if isinstance(item.get("company"), dict) else {}
    name = " ".join(
        part for part in (_bounded_text(item.get("firstName"), 100), _bounded_text(item.get("lastName"), 100)) if part
    )
    return {
        "contact_id": contact_id,
        "name": name,
        "company": _bounded_text(company.get("name"), 200),
        "email": _bounded_text(item.get("email"), 320),
        "inactive": item.get("inactive") is True,
    }


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

    def client_contacts(self):
        """One page of client contacts for the Email Verifier's JobAdder scan.

        Read-only: the scan reports invalid emails with a link to each contact
        and never changes anything in JobAdder. The browser walks the pages with
        ``offset``; this handler fetches exactly one page so every request stays
        bounded and a scan can be stopped between pages.
        """
        try:
            offset = int(str(self._query_arg("offset", "0") or "0").strip())
            limit = int(str(self._query_arg("limit", str(CLIENT_CONTACTS_MAX_LIMIT)) or "0").strip())
        except (TypeError, ValueError):
            return self._jsonify({"error": "Offset and limit must be whole numbers."}), 400
        if not 0 <= offset <= CLIENT_CONTACTS_MAX_OFFSET or not 1 <= limit <= CLIENT_CONTACTS_MAX_LIMIT:
            return self._jsonify({"error": "Offset or limit is out of range."}), 400
        try:
            token = self._refresh_token(force=False)
        except Exception:
            # A failed refresh (for example no network) does not mean the
            # account is disconnected: report a temporary error, not "connect".
            return self._jsonify({"error": "JobAdder could not be reached to refresh the sign-in. Check the internet connection."}), 503
        if not token:
            return self._jsonify({"error": "Connect JobAdder first, then scan again."}), 401
        try:
            _status, payload = self._client().request_json(
                "contacts",
                params=[("Offset", offset), ("Limit", limit)],
                token=token,
                timeout=25,
                # No stand-in list: a page that is not JSON must not look like an
                # empty last page and end the scan early.
                fallback={},
            )
        except PermissionError:
            return self._jsonify({"error": "Connect JobAdder first, then scan again."}), 401
        except urllib.error.HTTPError as e:
            code = int(getattr(e, "code", 0) or 0)
            try:
                e.close()
            except Exception:
                pass  # cleanup-only: a close failure must not hide the JobAdder status.
            if code in (401, 403):
                return self._jsonify({"error": "JobAdder did not allow reading client contacts. Reconnect JobAdder and try again."}), code
            if code == 429:
                return self._jsonify({"error": "JobAdder is limiting requests. Wait a moment and continue."}), 429
            return self._jsonify({"error": "JobAdder could not list client contacts (HTTP {}). Try again later.".format(code or "error")}), 502
        except Exception:
            return self._jsonify({"error": "JobAdder could not be reached. Check the connection and try again."}), 502
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            return self._jsonify({"error": "JobAdder returned an unexpected contact list."}), 502
        items = payload["items"]
        total = payload.get("totalCount")
        total = total if isinstance(total, int) and not isinstance(total, bool) and total >= 0 else None
        contacts = [summary for summary in (_client_contact_summary(item) for item in items) if summary]
        returned = len(items)
        more = returned > 0 and (offset + returned < total if total is not None else returned >= limit)
        next_offset = offset + returned if more and offset + returned <= CLIENT_CONTACTS_MAX_OFFSET else None
        return self._jsonify({
            "contacts": contacts,
            "offset": offset,
            "returned": returned,
            "total": total,
            "next_offset": next_offset,
        })
