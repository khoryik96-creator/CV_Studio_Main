"""Low-level JobAdder request layer: API-URL normalization + JSON wrappers.

Behaviour-preserving extraction from the legacy web shell:

* ``_ja_normalize_api_base`` - a pure function that pins a request to a safe,
  JobAdder-owned HTTPS API base without guessing a tenant region.
* ``_ja_get_json`` / ``_ja_post_json`` / ``_ja_put_json`` - thin convenience
  wrappers around the shared JobAdder client's ``request_json``. The client is
  supplied through ``bind_jobadder_request_client`` rather than imported, so the
  module never imports ``app`` and never reaches for connection state directly.

The URL helper is pure; the JSON wrappers touch the network only through the
injected client callable. This module never imports ``app``.
"""

import json
import urllib.parse


# The shared JobAdder client's ``request_json`` bound method, injected by app.py
# once ``_JOBADDER_CLIENT`` exists. The wrappers below are only ever called at
# request time, well after binding.
_request_json = None


def bind_jobadder_request_client(request_json):
    """Inject the shared JobAdder client's ``request_json`` callable."""
    global _request_json
    _request_json = request_json


def _ja_normalize_api_base(value):
    """Return a safe JobAdder API base without guessing a tenant region.

    OAuth token responses normally provide the tenant-specific API URL. Keep
    that exact JobAdder-owned HTTPS host when present; otherwise use JobAdder's
    generic documented endpoint. Never silently force AU3, which breaks EU/US
    tenants, and never allow a migrated browser value to redirect bearer tokens
    to a non-JobAdder host.
    """
    raw = str(value or "").strip().rstrip("/") or "https://api.jobadder.com/v2"
    try:
        parsed = urllib.parse.urlsplit(raw)
        host = str(parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme.lower() != "https" or not (host == "jobadder.com" or host.endswith(".jobadder.com")):
            return "https://api.jobadder.com/v2"
        path = (parsed.path or "").rstrip("/")
        if not path:
            path = "/v2"
        return "https://{}{}".format(host, path)
    except Exception:
        return "https://api.jobadder.com/v2"


def _ja_post_json(path, payload, timeout=15):
    """POST JSON to a JobAdder API path using the current server-side token."""
    return _request_json(
        path,
        method="POST",
        body=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=timeout,
        raw_fallback=True,
        safe_to_retry=False,
        retries=0,
    )


def _ja_get_json(path, timeout=15):
    """GET JSON from a JobAdder API path using the current server-side token."""
    return _request_json(
        path,
        method="GET",
        headers={"Accept": "application/json"},
        timeout=timeout,
        raw_fallback=True,
    )


def _ja_put_json(path, payload, timeout=20):
    """PUT JSON to a JobAdder API path using the current server-side token."""
    return _request_json(
        path,
        method="PUT",
        body=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=timeout,
        raw_fallback=True,
        safe_to_retry=False,
        retries=0,
    )
