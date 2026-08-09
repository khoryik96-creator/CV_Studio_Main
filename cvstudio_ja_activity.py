"""JobAdder candidate-activity diagnostic helpers and read/create probes.

Behaviour-preserving extraction of the JobAdder activity-diagnostic flow from
the legacy web shell:

* pure helpers - response-header redaction, network-error labelling, the
  conservative read-diagnostic summary, and the activity-id parsers for list
  and post results;
* ``JaActivityDiagnosticService`` - the read-only OAuth GET probe and the
  single controlled OAuth POST probe. These perform network I/O, so their
  JobAdder dependencies (access token, token refresh, API-URL builder, and the
  shared raw-request client) are supplied through explicit injection rather
  than imported. The Flask routes that drive them stay in ``app.py``.

The pure functions take only their inputs; the service touches the network
solely through its injected callables. Depends only on the redacted
external-service error type already defined in ``cvstudio_clients``. This module
never imports ``app``.
"""

import json
import re
import urllib.error
from datetime import datetime, timezone

from cvstudio_clients import ExternalServiceError


def _ja_activity_diagnostic_response_headers(headers):
    """Keep useful response metadata while excluding cookie/authentication headers."""
    blocked = {"set-cookie", "set-cookie2", "authorization", "proxy-authorization"}
    try:
        return {str(k): str(v) for k, v in headers.items() if str(k).lower() not in blocked}
    except Exception:
        return {}


def _ja_activity_diagnostic_network_error(error):
    """Preserve the legacy diagnostic field with shared-client redaction."""
    if isinstance(error, ExternalServiceError):
        return str(getattr(error, "safe_detail", "") or error)
    return str(getattr(error, "reason", error))


def _ja_activity_diagnostic_summary(request_results):
    """Return a conservative summary without guessing undocumented API behavior."""
    statuses = [r.get("status") for r in (request_results or [])]
    numeric_statuses = [s for s in statuses if isinstance(s, int)]
    if any(200 <= s < 300 for s in numeric_statuses):
        return "At least one OAuth activity GET succeeded. Review the complete response body for the saved Screening Call and Presentability answer model."
    if len(numeric_statuses) == 2 and all(s in (404, 405) for s in numeric_statuses):
        return "Both OAuth activity GET routes returned 404/405. This is evidence that these read routes are unavailable, but the exact POST response must still be reviewed separately before making a final endpoint conclusion."
    if any(s in (401, 403) for s in numeric_statuses):
        return "JobAdder rejected at least one read request as unauthorised. Reconnect JobAdder OAuth before interpreting endpoint availability."
    return "The read requests did not expose a successful activity model. Review each full status and response body before deciding the next controlled test."


def _ja_activity_ids_from_list_result(result):
    parsed = (result or {}).get("response_json")
    if not isinstance(parsed, dict):
        return []
    items = parsed.get("items")
    if not isinstance(items, list):
        return []
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        value = item.get("activityId")
        if value is None:
            value = item.get("activityID")
        try:
            out.append(int(value))
        except Exception:
            pass
    return out


def _ja_activity_id_from_post_result(result):
    parsed = (result or {}).get("response_json")
    if isinstance(parsed, dict):
        for key in ("activityId", "activityID"):
            value = parsed.get(key)
            try:
                return int(value)
            except Exception:
                pass
        for container_key in ("activity", "item", "result", "data"):
            child = parsed.get(container_key)
            if isinstance(child, dict):
                for key in ("activityId", "activityID"):
                    value = child.get(key)
                    try:
                        return int(value)
                    except Exception:
                        pass
    headers = (result or {}).get("response_headers") or {}
    for key, value in headers.items():
        if str(key).lower() == "location":
            m = re.search(r"/activities/(\d+)(?:$|[/?#])", str(value))
            if m:
                return int(m.group(1))
    return None


class JaActivityDiagnosticService:
    """Read-only OAuth activity GET and the single controlled OAuth POST probe.

    The JobAdder dependencies are injected so the module never imports ``app`` or
    touches request state directly:

    * ``access_token_provider()`` returns the current access token for the
      read-only GET (no refresh);
    * ``refresh_access_token(force=False)`` returns a fresh token for the POST;
    * ``api_url(path)`` builds the absolute JobAdder URL for the report;
    * ``request_raw(path, ...)`` performs the raw OAuth request (the shared
      ``_JOBADDER_CLIENT.request_raw``).

    The returned reports deliberately exclude the OAuth token and Authorization
    header; response bodies are preserved in full for model-binding review.
    """

    def __init__(self, *, access_token_provider, refresh_access_token, api_url, request_raw):
        self._access_token_provider = access_token_provider
        self._refresh_access_token = refresh_access_token
        self._api_url = api_url
        self._request_raw = request_raw

    def get(self, path, timeout=25):
        """Perform one exact read-only JobAdder OAuth GET and preserve the raw response.

        The returned report deliberately excludes the OAuth token and request
        Authorization header. Response bodies are not shortened so the user can
        provide the complete model-binding evidence for review.
        """
        token = self._access_token_provider()
        if not token:
            raise PermissionError("Not authenticated")
        url = self._api_url(path)
        started = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        try:
            response = self._request_raw(
                path,
                method="GET",
                token=token,
                timeout=timeout,
                headers={"Accept": "application/json, text/plain, */*"},
            )
            raw_text = response.body.decode("utf-8", errors="replace")
            headers = _ja_activity_diagnostic_response_headers(response.headers)
            parsed = None
            if raw_text.strip():
                try:
                    parsed = json.loads(raw_text)
                except Exception:
                    parsed = None
            return {
                "method": "GET",
                "path": path,
                "url": url,
                "started_utc": started,
                "ok": True,
                "status": int(response.status or 200),
                "response_headers": headers,
                "response_body": raw_text,
                "response_json": parsed,
            }
        except urllib.error.HTTPError as e:
            raw_bytes = e.read()
            raw_text = raw_bytes.decode("utf-8", errors="replace")
            headers = _ja_activity_diagnostic_response_headers(e.headers)
            parsed = None
            if raw_text.strip():
                try:
                    parsed = json.loads(raw_text)
                except Exception:
                    parsed = None
            return {
                "method": "GET",
                "path": path,
                "url": url,
                "started_utc": started,
                "ok": False,
                "status": int(e.code),
                "reason": str(getattr(e, "reason", "") or ""),
                "response_headers": headers,
                "response_body": raw_text,
                "response_json": parsed,
            }
        except (urllib.error.URLError, ExternalServiceError) as e:
            return {
                "method": "GET",
                "path": path,
                "url": url,
                "started_utc": started,
                "ok": False,
                "status": None,
                "network_error": _ja_activity_diagnostic_network_error(e),
                "response_headers": {},
                "response_body": "",
                "response_json": None,
            }

    def post(self, path, payload, timeout=25):
        """Send one OAuth POST and preserve the complete response for diagnostics.

        Authentication/cookie headers are never copied into the returned report.
        """
        token = self._refresh_access_token(force=False)
        if not token:
            raise PermissionError("JobAdder is not connected")
        url = self._api_url(path)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        started = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        base = {
            "method": "POST",
            "path": path,
            "url": url,
            "started_utc": started,
            "request_payload": payload,
        }
        try:
            response = self._request_raw(
                path,
                method="POST",
                body=body,
                token=token,
                timeout=timeout,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Content-Type": "application/json; charset=utf-8",
                },
                safe_to_retry=False,
                retries=0,
            )
            raw_text = response.body.decode("utf-8", errors="replace")
            parsed = None
            if raw_text.strip():
                try:
                    parsed = json.loads(raw_text)
                except Exception:
                    parsed = None
            base.update({
                "ok": True,
                "status": int(response.status or 200),
                "response_headers": _ja_activity_diagnostic_response_headers(response.headers),
                "response_body": raw_text,
                "response_json": parsed,
            })
            return base
        except urllib.error.HTTPError as e:
            raw_bytes = e.read()
            raw_text = raw_bytes.decode("utf-8", errors="replace")
            parsed = None
            if raw_text.strip():
                try:
                    parsed = json.loads(raw_text)
                except Exception:
                    parsed = None
            base.update({
                "ok": False,
                "status": int(e.code),
                "reason": str(getattr(e, "reason", "") or ""),
                "response_headers": _ja_activity_diagnostic_response_headers(e.headers),
                "response_body": raw_text,
                "response_json": parsed,
            })
            return base
        except (urllib.error.URLError, ExternalServiceError) as e:
            base.update({
                "ok": False,
                "status": None,
                "network_error": _ja_activity_diagnostic_network_error(e),
                "response_headers": {},
                "response_body": "",
                "response_json": None,
            })
            return base
