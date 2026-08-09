"""JobAdder candidate-activity diagnostic and result-parsing helpers.

Behaviour-preserving extraction of the pure, stateless helpers from the legacy
web shell's JobAdder activity-diagnostic flow: response-header redaction,
network-error labelling, the conservative read-diagnostic summary, and the
activity-id parsers for list and post results.

This is the first (pure-helper) slice of the ``_ja_activity`` domain. The
network-performing pieces (the OAuth GET/POST probes) and their Flask routes
stay in the shell; they need the shared JobAdder client and request state and
belong to a later service slice.

Pure functions of their inputs - no Flask, no globals, no network, no JobAdder
client access. Depends only on the redacted external-service error type already
defined in ``cvstudio_clients``. This module never imports ``app``.
"""

import re

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
