"""Shared external-service client foundations for CV Studio Phase 3.

This module deliberately contains transport/client boundaries only. Flask
routes, credential persistence, feature orchestration and user-facing response
shapes remain in app.py so Phase 3 does not become the Phase 4 backend split.
"""

from __future__ import annotations

from dataclasses import dataclass
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request


_SENSITIVE_HEADER_NAMES = {
    "authorization",
    "proxy-authorization",
    "x-api-key",
    "api-key",
    "cookie",
    "set-cookie",
    "set-cookie2",
}
_TRANSIENT_HTTP_STATUSES = {408, 425, 429, 500, 502, 503, 504, 529}


class _CaseInsensitiveHeaders(dict):
    """Small read-compatible mapping that preserves HTTP header semantics."""

    def __init__(self, headers=None):
        super().__init__()
        self._header_names = {}
        try:
            items = headers.items()
        except Exception:
            items = []
        for key, value in items:
            self[key] = value

    def __setitem__(self, key, value):
        name = str(key)
        folded = name.lower()
        stored_name = self._header_names.get(folded)
        if stored_name is None:
            self._header_names[folded] = name
            stored_name = name
        super().__setitem__(stored_name, value)

    def __getitem__(self, key):
        stored_name = self._header_names.get(str(key).lower(), key)
        return super().__getitem__(stored_name)

    def __contains__(self, key):
        return str(key).lower() in self._header_names

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


def bounded_timeout(value, default=20, minimum=1, maximum=180):
    """Return a finite timeout within the client-specific safety bounds."""
    try:
        parsed = float(value)
    except Exception:
        parsed = float(default)
    if parsed != parsed or parsed in (float("inf"), float("-inf")):
        parsed = float(default)
    return max(float(minimum), min(float(maximum), parsed))


def redact_external_text(value, maximum=4000):
    """Remove credential material from diagnostics and structured errors."""
    text = str(value or "")
    text = re.sub(
        r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;\"']+",
        r"\1[redacted]",
        text,
    )
    text = re.sub(
        r"(?i)([?&](?:access[-_]?token|refresh[-_]?token|client[-_]?secret|api[-_]?key|x-api-key|code|password|device[-_]?code)=)[^&\s]+",
        r"\1[redacted]",
        text,
    )
    text = re.sub(
        r"(?i)([\"']?(?:access[-_]?token|refresh[-_]?token|client[-_]?secret|api[-_]?key|x-api-key|password|device[-_]?code|candidate[-_]?id)[\"']?\s*[:=]\s*[\"']?)[^\s,;}\"']+",
        r"\1[redacted]",
        text,
    )
    text = re.sub(r"(?i)\b(sk-ant-|sk-proj-|sk-)[A-Za-z0-9_.-]{8,}", "[redacted]", text)
    text = re.sub(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[redacted-email]", text)
    return text[: max(0, int(maximum or 0))]


def redact_external_headers(headers):
    """Return response/request headers without authentication or cookie data."""
    out = {}
    try:
        items = headers.items()
    except Exception:
        items = []
    for key, value in items:
        name = str(key)
        out[name] = "[redacted]" if name.lower() in _SENSITIVE_HEADER_NAMES else redact_external_text(value, 1000)
    return out


def _redact_error_body(body):
    raw = bytes(body or b"")
    if not raw:
        return b""
    text = raw.decode("utf-8", errors="replace")
    return redact_external_text(text, max(4000, min(len(text) + 256, 65536))).encode("utf-8")


def _host_allowed(url, allowed_hosts):
    try:
        parsed = urllib.parse.urlsplit(str(url or ""))
        host = str(parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme.lower() != "https" or not host:
            return False
        for allowed in allowed_hosts or ():
            suffix = str(allowed or "").lower().lstrip(".").rstrip(".")
            if suffix and (host == suffix or host.endswith("." + suffix)):
                return True
    except Exception:
        return False
    return False


def _url_origin(url):
    """Return the normalized origin used for redirect credential decisions."""
    try:
        parsed = urllib.parse.urlsplit(str(url or ""))
        scheme = parsed.scheme.lower()
        host = str(parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
        if port is None:
            port = 443 if scheme == "https" else 80 if scheme == "http" else None
        return scheme, host, port
    except Exception:
        return "", "", None


class _AllowlistedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject foreign redirect targets and never forward secrets cross-origin."""

    def __init__(self, service, allowed_hosts):
        super().__init__()
        self._service = str(service or "external_service")
        self._allowed_hosts = tuple(allowed_hosts or ())

    def redirect_request(self, request_object, fp, code, message, headers, new_url):
        resolved_url = urllib.parse.urljoin(request_object.full_url, str(new_url or ""))
        if self._allowed_hosts and not _host_allowed(resolved_url, self._allowed_hosts):
            try:
                fp.close()
            except Exception:
                pass
            raise ExternalServiceError(
                self._service,
                "{} redirect target is not allowed".format(
                    self._service.replace("_", " ").title()
                ),
                detail="Blocked redirect to non-service HTTPS host",
            )
        redirected = super().redirect_request(
            request_object,
            fp,
            code,
            message,
            headers,
            resolved_url,
        )
        if redirected is not None and _url_origin(request_object.full_url) != _url_origin(resolved_url):
            for name, _value in list(redirected.header_items()):
                if str(name).lower() in _SENSITIVE_HEADER_NAMES:
                    redirected.remove_header(name)
        return redirected


def _service_defaults(service, status=0):
    service = str(service or "external_service").strip().lower()
    status = int(status or 0)
    if service == "jobadder":
        code = "JOBADDER_RECONNECT_REQUIRED" if status in (401, 403) else "JOBADDER_REQUEST_FAILED"
        action = "open_jobadder_settings" if status in (401, 403) else ("retry" if status in _TRANSIENT_HTTP_STATUSES else "")
    elif service in ("microsoft", "microsoft_graph"):
        code = "MICROSOFT_RECONNECT_REQUIRED" if status in (401, 403) else "MICROSOFT_GRAPH_REQUEST_FAILED"
        action = "reconnect_microsoft" if status in (401, 403) else ("retry" if status in _TRANSIENT_HTTP_STATUSES else "")
    elif service in ("ai", "ai_provider"):
        code = "AI_PROVIDER_AUTH_REQUIRED" if status in (401, 403) else "AI_PROVIDER_REQUEST_FAILED"
        action = "open_ai_settings" if status in (401, 403) else ("retry_or_switch_provider" if status in _TRANSIENT_HTTP_STATUSES else "open_ai_settings")
    else:
        code = "EXTERNAL_SERVICE_REQUEST_FAILED"
        action = "retry" if status in _TRANSIENT_HTTP_STATUSES else ""
    return code, action


class ExternalServiceError(RuntimeError):
    """A redacted machine-readable external-service failure."""

    def __init__(self, service, message, *, status=0, retryable=False, action="", detail=""):
        self.service = str(service or "external_service")
        self.status = int(status or 0)
        self.retryable = bool(retryable)
        inferred_code, inferred_action = _service_defaults(self.service, self.status)
        self.service_code = inferred_code
        self.action = str(action or inferred_action)
        self.safe_detail = redact_external_text(detail or message)
        super().__init__(redact_external_text(message))

    def structured(self):
        return {
            "service": self.service,
            "code": self.service_code,
            "status": self.status,
            "retryable": self.retryable,
            "action": self.action,
            "detail": self.safe_detail,
        }


class ExternalServiceHTTPError(urllib.error.HTTPError):
    """HTTPError-compatible failure carrying redacted structured metadata."""

    def __init__(self, service, url, status, reason, headers, body):
        safe_body = _redact_error_body(body)
        safe_reason = redact_external_text(reason, 500)
        super().__init__(url, int(status), safe_reason, headers or {}, io.BytesIO(safe_body))
        self.service = str(service or "external_service")
        self.retryable = int(status or 0) in _TRANSIENT_HTTP_STATUSES
        self.service_code, self.action = _service_defaults(self.service, status)
        self.safe_detail = safe_body.decode("utf-8", errors="replace")[:4000]
        self.redacted_headers = redact_external_headers(headers or {})

    def read(self, amt=-1):
        data = self.fp.read(amt)
        if amt is None or int(amt) < 0:
            self.close()
        return data

    def structured(self):
        return {
            "service": self.service,
            "code": self.service_code,
            "status": int(self.code or 0),
            "retryable": self.retryable,
            "action": self.action,
            "detail": self.safe_detail,
        }


@dataclass(frozen=True)
class ExternalResponse:
    status: int
    headers: dict
    body: bytes
    url: str

    def json(self, fallback=None):
        fallback = {} if fallback is None else fallback
        if not self.body:
            return fallback
        try:
            parsed = json.loads(self.body.decode("utf-8", errors="strict"))
        except Exception:
            return fallback
        return parsed


class ExternalServiceTransport:
    """Bounded urllib transport with safe retry and redacted failure handling."""

    def __init__(self, opener=None, sleeper=None):
        self._opener = opener
        self._sleeper = sleeper or time.sleep

    def _open(self, request_object, *, service="", allowed_hosts=(), **kwargs):
        if self._opener is not None:
            return self._opener(request_object, **kwargs)
        context = kwargs.pop("context", None)
        handlers = [_AllowlistedRedirectHandler(service, allowed_hosts)]
        if context is not None:
            handlers.append(urllib.request.HTTPSHandler(context=context))
        opener = urllib.request.build_opener(*handlers)
        return opener.open(request_object, **kwargs)

    @staticmethod
    def _retry_delay(headers, attempt):
        retry_after = ""
        try:
            retry_after = headers.get("Retry-After") or ""
        except Exception:
            retry_after = ""
        try:
            return float(max(1, min(5, int(retry_after))))
        except Exception:
            return min(1.0, 0.25 * (2 ** max(0, int(attempt or 0))))

    def request(
        self,
        service,
        url,
        *,
        method="GET",
        body=None,
        headers=None,
        timeout=20,
        context=None,
        allowed_hosts=(),
        safe_to_retry=None,
        retries=1,
        timeout_maximum=180,
    ):
        method = str(method or "GET").upper()
        if allowed_hosts and not _host_allowed(url, allowed_hosts):
            raise ExternalServiceError(
                service,
                "{} request target is not allowed".format(str(service or "External service")),
                detail="Blocked non-service HTTPS host",
            )
        timeout_value = bounded_timeout(timeout, 20, 1, timeout_maximum)
        retry_safe = method in ("GET", "HEAD", "OPTIONS") if safe_to_retry is None else bool(safe_to_retry)
        retry_limit = max(0, min(2, int(retries or 0))) if retry_safe else 0
        attempt = 0
        while True:
            request_object = urllib.request.Request(
                str(url),
                data=body,
                headers=dict(headers or {}),
                method=method,
            )
            kwargs = {"timeout": timeout_value}
            if context is not None:
                kwargs["context"] = context
            try:
                with self._open(
                    request_object,
                    service=service,
                    allowed_hosts=allowed_hosts,
                    **kwargs,
                ) as response:
                    return ExternalResponse(
                        int(getattr(response, "status", 200) or 200),
                        _CaseInsensitiveHeaders(getattr(response, "headers", {}) or {}),
                        response.read(),
                        str(getattr(response, "url", "") or url),
                    )
            except urllib.error.HTTPError as error:
                try:
                    error_body = error.read()
                except Exception:
                    error_body = b""
                error_headers = getattr(error, "headers", {}) or {}
                status = int(getattr(error, "code", 0) or 0)
                reason = str(getattr(error, "reason", "") or "HTTP error")
                try:
                    error.close()
                except Exception:
                    pass
                if status in _TRANSIENT_HTTP_STATUSES and attempt < retry_limit:
                    self._sleeper(self._retry_delay(error_headers, attempt))
                    attempt += 1
                    continue
                raise ExternalServiceHTTPError(service, url, status, reason, error_headers, error_body)
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                retryable = retry_safe and attempt < retry_limit
                if retryable:
                    self._sleeper(min(1.0, 0.25 * (2 ** attempt)))
                    attempt += 1
                    continue
                raise ExternalServiceError(
                    service,
                    "{} request failed".format(str(service or "External service").replace("_", " ").title()),
                    retryable=bool(retry_safe),
                    action="retry" if retry_safe else "",
                    detail=str(error),
                ) from error


class JobAdderClient:
    """Shared JobAdder OAuth/API client behind the established Flask routes."""

    TOKEN_URL = "https://id.jobadder.com/connect/token"
    ALLOWED_HOSTS = ("jobadder.com",)

    def __init__(self, api_base_provider, token_provider, reconnect_handler=None, transport=None):
        self._api_base_provider = api_base_provider
        self._token_provider = token_provider
        self._reconnect_handler = reconnect_handler
        self.transport = transport or ExternalServiceTransport()

    def _api_url(self, path):
        raw = str(path or "")
        if raw.lower().startswith("https://"):
            url = raw
        else:
            base = str(self._api_base_provider() or "https://api.jobadder.com/v2").rstrip("/")
            url = base + "/" + raw.lstrip("/")
        if not _host_allowed(url, self.ALLOWED_HOSTS):
            raise ExternalServiceError("jobadder", "JobAdder request target is not allowed")
        return url

    @staticmethod
    def _with_params(url, params):
        if not params:
            return url
        query = urllib.parse.urlencode(params, doseq=True)
        return url + (("&" if "?" in url else "?") + query if query else "")

    def exchange_token(self, params, timeout=20):
        response = self.transport.request(
            "jobadder",
            self.TOKEN_URL,
            method="POST",
            body=urllib.parse.urlencode(dict(params or {})).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=timeout,
            timeout_maximum=60,
            allowed_hosts=self.ALLOWED_HOSTS,
            safe_to_retry=False,
            retries=0,
        )
        token = response.json({})
        if not isinstance(token, dict) or not token.get("access_token"):
            raise ExternalServiceError("jobadder", "JobAdder returned no access token")
        return token

    def _token(self, force=False, fallback=""):
        token = ""
        try:
            token = str(self._token_provider(bool(force)) or "").strip()
        except Exception:
            if force:
                raise
        return token or str(fallback or "").strip()

    def _mark_reconnect(self):
        if callable(self._reconnect_handler):
            try:
                self._reconnect_handler()
            except Exception:
                pass

    def request_raw(
        self,
        path,
        *,
        method="GET",
        body=None,
        headers=None,
        params=None,
        timeout=20,
        token="",
        refresh_on_401=True,
        safe_to_retry=None,
        retries=None,
    ):
        method = str(method or "GET").upper()
        active_token = self._token(False, token)
        if not active_token:
            raise PermissionError("Not authenticated")
        url = self._with_params(self._api_url(path), params)
        base_headers = {"Authorization": "Bearer " + active_token}
        for key, value in dict(headers or {}).items():
            if str(key).lower() != "authorization":
                base_headers[str(key)] = str(value)
        retry_safe = method in ("GET", "HEAD", "OPTIONS") if safe_to_retry is None else bool(safe_to_retry)
        retry_count = (1 if retry_safe else 0) if retries is None else int(retries or 0)

        def perform(access_token):
            request_headers = dict(base_headers)
            request_headers["Authorization"] = "Bearer " + access_token
            return self.transport.request(
                "jobadder",
                url,
                method=method,
                body=body,
                headers=request_headers,
                timeout=timeout,
                timeout_maximum=60,
                allowed_hosts=self.ALLOWED_HOSTS,
                safe_to_retry=retry_safe,
                retries=retry_count,
            )

        try:
            return perform(active_token)
        except ExternalServiceHTTPError as error:
            if int(error.code or 0) != 401 or not refresh_on_401:
                raise
            try:
                refreshed = self._token(True)
            except Exception as refresh_error:
                # A temporary token-endpoint/network failure is not evidence
                # that OAuth was revoked. Keep the protected connection so a
                # later safe read can retry; permanent refresh rejection is
                # translated by the token provider into an empty token/state.
                if not bool(getattr(refresh_error, "retryable", False)):
                    self._mark_reconnect()
                raise
            if not refreshed:
                self._mark_reconnect()
                raise
            error.close()
            try:
                return perform(refreshed)
            except ExternalServiceHTTPError as retry_error:
                if int(retry_error.code or 0) == 401:
                    self._mark_reconnect()
                raise

    def request_json(self, path, *, fallback=None, raw_fallback=False, **kwargs):
        request_headers = dict(kwargs.pop("headers", {}) or {})
        if not any(str(key).lower() == "accept" for key in request_headers):
            request_headers["Accept"] = "application/json"
        response = self.request_raw(path, headers=request_headers, **kwargs)
        if raw_fallback:
            fallback = {"raw": response.body.decode("utf-8", errors="replace") if response.body else ""}
        if fallback is None:
            fallback = {}
        parsed = response.json(fallback)
        return response.status, parsed

    def paginate_offset(
        self,
        path,
        *,
        params=None,
        token="",
        max_items=1000,
        page_size=100,
        timeout=25,
        parse_page,
        item_key=None,
        page_signature=None,
        initial_total=None,
        total_mode="replace",
        deduplicate=True,
        retry_empty=False,
        empty_retry_delay=0.35,
        on_http_error=None,
        fetch_page=None,
    ):
        """Fetch defensive Offset/Limit pages and return items plus state codes.

        Feature adapters retain their existing human-readable warnings while
        this client owns offset advancement, caps, duplicate/no-progress stops,
        bounded empty-page retry and total tracking.
        """
        max_items = max(0, int(max_items or 0))
        page_size = max(1, int(page_size or 1))
        base_params = list(params.items()) if isinstance(params, dict) else list(params or [])
        base_params = [(k, v) for k, v in base_params if str(k).lower() not in ("offset", "limit")]
        output = []
        seen = set()
        signatures = set()
        offset = 0
        pages = 0
        reported_total = None if initial_total is None else max(0, int(initial_total or 0))
        codes = []
        active_params = list(base_params)

        while offset < max_items:
            if reported_total is not None and offset >= min(reported_total, max_items):
                break
            take = min(page_size, max_items - offset)
            page_params = list(active_params) + [("Offset", offset), ("Limit", take)]
            try:
                if callable(fetch_page):
                    payload = fetch_page(page_params)
                else:
                    _status, payload = self.request_json(
                        path,
                        params=page_params,
                        token=token,
                        timeout=timeout,
                        fallback={"items": []},
                    )
            except urllib.error.HTTPError as error:
                replacement = on_http_error(error, list(active_params), offset, pages) if callable(on_http_error) else None
                if replacement is None:
                    raise
                error.close()
                active_params = list(replacement.items()) if isinstance(replacement, dict) else list(replacement)
                active_params = [(k, v) for k, v in active_params if str(k).lower() not in ("offset", "limit")]
                continue

            items, total = parse_page(payload)
            items = items if isinstance(items, list) else []
            if total not in (None, ""):
                try:
                    parsed_total = max(0, int(total))
                    if reported_total is None or total_mode == "replace":
                        reported_total = parsed_total
                    else:
                        reported_total = max(reported_total, parsed_total)
                except Exception:
                    pass

            if not items and retry_empty and reported_total is not None and offset < min(reported_total, max_items):
                self.transport._sleeper(max(0.0, min(2.0, float(empty_retry_delay or 0))))
                if callable(fetch_page):
                    payload = fetch_page(page_params)
                else:
                    _status, payload = self.request_json(
                        path,
                        params=page_params,
                        token=token,
                        timeout=timeout,
                        fallback={"items": []},
                    )
                items, total = parse_page(payload)
                items = items if isinstance(items, list) else []
                if total not in (None, ""):
                    try:
                        parsed_total = max(0, int(total))
                        reported_total = parsed_total if reported_total is None or total_mode == "replace" else max(reported_total, parsed_total)
                    except Exception:
                        pass

            pages += 1
            keys = []
            for index, item in enumerate(items):
                if callable(item_key):
                    try:
                        key = str(item_key(item))
                    except Exception:
                        key = ""
                else:
                    try:
                        key = json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)
                    except Exception:
                        key = "{}:{}".format(offset, index)
                keys.append(key)
            if callable(page_signature):
                signature = str(page_signature(items, keys))
            else:
                signature = json.dumps(sorted(set(keys)), ensure_ascii=False)
            if items and signature in signatures:
                codes.append("repeated_page")
                break
            signatures.add(signature)

            new_unique = 0
            for item, key in zip(items, keys):
                if deduplicate and key in seen:
                    continue
                seen.add(key)
                output.append(item)
                new_unique += 1
            if items and deduplicate and new_unique == 0:
                codes.append("no_new_unique")
                break
            returned_count = len(items)
            if returned_count <= 0:
                if reported_total is not None and offset < min(reported_total, max_items):
                    codes.append("empty_before_total")
                break
            previous_offset = offset
            offset += returned_count
            if offset <= previous_offset:
                codes.append("no_progress")
                break
            if reported_total is None and returned_count < take:
                break

        effective_total = reported_total if reported_total is not None else len(output)
        if reported_total is not None and offset >= min(reported_total, max_items) and len(output) < min(reported_total, max_items):
            codes.append("missing_at_total")
        truncated = bool(effective_total > len(output))
        if reported_total is not None and reported_total > max_items:
            codes.append("cap_reached")
        return output[:max_items], {
            "offset": offset,
            "pages": pages,
            "reported_total": effective_total,
            "truncated": truncated,
            "incomplete": bool(codes and any(code != "cap_reached" for code in codes)),
            "codes": codes,
            "active_params": active_params,
        }


class MicrosoftGraphClient:
    """Shared Microsoft Graph/OAuth client for separate OneNote/Outlook stores."""

    GRAPH_BASE = "https://graph.microsoft.com/v1.0"
    GRAPH_HOSTS = ("graph.microsoft.com",)
    LOGIN_HOSTS = ("login.microsoftonline.com",)

    def __init__(
        self,
        token_provider,
        *,
        not_connected_message="Microsoft Graph is not connected",
        reconnect_handler=None,
        context_provider=None,
        transport=None,
    ):
        self._token_provider = token_provider
        self._not_connected_message = str(not_connected_message or "Microsoft Graph is not connected")
        self._reconnect_handler = reconnect_handler
        self._context_provider = context_provider
        self.transport = transport or ExternalServiceTransport()

    def _context(self):
        return self._context_provider() if callable(self._context_provider) else None

    def _token(self, force=False):
        try:
            return str(self._token_provider(bool(force)) or "").strip()
        except TypeError:
            return str(self._token_provider() or "").strip()

    def _mark_reconnect(self):
        if callable(self._reconnect_handler):
            try:
                self._reconnect_handler()
            except Exception:
                pass

    def _graph_url(self, path):
        raw = str(path or "")
        url = raw if raw.lower().startswith("https://") else self.GRAPH_BASE + "/" + raw.lstrip("/")
        if not _host_allowed(url, self.GRAPH_HOSTS):
            raise ExternalServiceError("microsoft_graph", "Microsoft Graph request target is not allowed")
        return url

    @staticmethod
    def _with_params(url, params):
        if not params:
            return url
        query = urllib.parse.urlencode(params, doseq=True)
        return url + (("&" if "?" in url else "?") + query if query else "")

    def token_request(self, request_data, *, tenant="common", endpoint="token", timeout=20):
        safe_tenant = re.sub(r"[^A-Za-z0-9_.-]", "", str(tenant or "common").strip()) or "common"
        endpoint_name = "devicecode" if str(endpoint or "token").lower() == "devicecode" else "token"
        form_data = dict(request_data or {})
        retryable_refresh = (
            endpoint_name == "token"
            and str(form_data.get("grant_type") or "").strip().lower() == "refresh_token"
        )
        url = "https://login.microsoftonline.com/{}/oauth2/v2.0/{}".format(safe_tenant, endpoint_name)
        response = self.transport.request(
            "microsoft_graph",
            url,
            method="POST",
            body=urllib.parse.urlencode(form_data).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=timeout,
            timeout_maximum=60,
            context=self._context(),
            allowed_hosts=self.LOGIN_HOSTS,
            safe_to_retry=retryable_refresh,
            retries=1 if retryable_refresh else 0,
        )
        return response.json({})

    def request_raw(
        self,
        path,
        *,
        method="GET",
        body=None,
        headers=None,
        params=None,
        timeout=25,
        refresh_on_401=True,
        safe_to_retry=None,
        retries=None,
        access_token=None,
    ):
        method = str(method or "GET").upper()
        supplied_token = str(access_token or "").strip()
        token = supplied_token or self._token(False)
        if not token:
            raise PermissionError(self._not_connected_message)
        url = self._with_params(self._graph_url(path), params)
        base_headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
        for key, value in dict(headers or {}).items():
            if str(key).lower() != "authorization":
                base_headers[str(key)] = str(value)
        retry_safe = method in ("GET", "HEAD", "OPTIONS") if safe_to_retry is None else bool(safe_to_retry)
        retry_count = (1 if retry_safe else 0) if retries is None else int(retries or 0)

        def perform(access_token):
            request_headers = dict(base_headers)
            request_headers["Authorization"] = "Bearer " + access_token
            return self.transport.request(
                "microsoft_graph",
                url,
                method=method,
                body=body,
                headers=request_headers,
                timeout=timeout,
                timeout_maximum=60,
                context=self._context(),
                allowed_hosts=self.GRAPH_HOSTS,
                safe_to_retry=retry_safe,
                retries=retry_count,
            )

        try:
            return perform(token)
        except ExternalServiceHTTPError as error:
            if int(error.code or 0) != 401 or not refresh_on_401 or supplied_token:
                raise
            try:
                refreshed = self._token(True)
            except Exception:
                self._mark_reconnect()
                raise
            if not refreshed:
                self._mark_reconnect()
                raise
            error.close()
            try:
                return perform(refreshed)
            except ExternalServiceHTTPError as retry_error:
                if int(retry_error.code or 0) == 401:
                    self._mark_reconnect()
                raise

    def _request_json_once(
        self,
        path,
        *,
        body=None,
        method="GET",
        params=None,
        timeout=25,
        headers=None,
        safe_to_retry=None,
        retries=None,
        access_token=None,
    ):
        payload = None if body is None else json.dumps(body).encode("utf-8")
        request_headers = dict(headers or {})
        if payload is not None:
            request_headers.setdefault("Content-Type", "application/json")
        response = self.request_raw(
            path,
            method=method,
            body=payload,
            headers=request_headers,
            params=params,
            timeout=timeout,
            safe_to_retry=safe_to_retry,
            retries=retries,
            access_token=access_token,
        )
        return response.json({})

    def request_json(
        self,
        path,
        *,
        body=None,
        method="GET",
        params=None,
        timeout=25,
        headers=None,
        safe_to_retry=None,
        retries=None,
        paginate=False,
        max_items=100,
        max_pages=20,
        access_token=None,
    ):
        if paginate:
            if access_token:
                raise ExternalServiceError(
                    "microsoft_graph",
                    "Explicit-token Microsoft Graph requests cannot paginate",
                )
            return self.get_collection(
                path,
                params=params,
                timeout=timeout,
                max_items=max_items,
                max_pages=max_pages,
                headers=headers,
            )
        return self._request_json_once(
            path,
            body=body,
            method=method,
            params=params,
            timeout=timeout,
            headers=headers,
            safe_to_retry=safe_to_retry,
            retries=retries,
            access_token=access_token,
        )

    def request_bytes(self, path, *, params=None, timeout=25, headers=None):
        response = self.request_raw(
            path,
            method="GET",
            params=params,
            timeout=timeout,
            headers=headers or {"Accept": "text/html,application/json;q=0.9,*/*;q=0.8"},
        )
        return response.body, response.headers.get("Content-Type", "")

    def get_collection(self, path, *, params=None, timeout=25, max_items=100, max_pages=20, headers=None):
        """Follow Graph @odata.nextLink within bounded item/page limits."""
        item_cap = max(1, min(5000, int(max_items or 100)))
        page_cap = max(1, min(100, int(max_pages or 20)))
        first = self._request_json_once(
            path,
            params=params,
            timeout=timeout,
            headers=headers,
            safe_to_retry=True,
            retries=1,
        )
        if not isinstance(first, dict) or not isinstance(first.get("value"), list):
            return first
        output = list(first.get("value") or [])[:item_cap]
        next_link = str(first.get("@odata.nextLink") or "").strip()
        seen_links = set()
        pages = 1
        while next_link and len(output) < item_cap and pages < page_cap:
            if next_link in seen_links:
                break
            seen_links.add(next_link)
            page = self._request_json_once(
                next_link,
                timeout=timeout,
                headers=headers,
                safe_to_retry=True,
                retries=1,
            )
            pages += 1
            if not isinstance(page, dict):
                break
            values = page.get("value") if isinstance(page.get("value"), list) else []
            remaining = item_cap - len(output)
            output.extend(values[:remaining])
            candidate = str(page.get("@odata.nextLink") or "").strip()
            if not values and candidate == next_link:
                break
            next_link = candidate
        result = dict(first)
        result["value"] = output
        result.pop("@odata.nextLink", None)
        return result


class AIProviderClient:
    """Provider-aware, non-replaying transport for chargeable AI requests."""

    _PROVIDERS = {
        "anthropic": {
            "url": "https://api.anthropic.com/v1/messages",
            "hosts": ("api.anthropic.com",),
            "api_key_header": "x-api-key",
            "headers": {"anthropic-version": "2023-06-01"},
        },
        "deepseek": {
            "url": "https://api.deepseek.com/anthropic/v1/messages",
            "hosts": ("api.deepseek.com",),
            "api_key_header": "x-api-key",
            "headers": {"anthropic-version": "2023-06-01"},
        },
        "openai": {
            "url": "https://api.openai.com/v1/responses",
            "hosts": ("api.openai.com",),
            "api_key_header": "Authorization",
            "headers": {},
        },
    }

    def __init__(self, transport=None):
        self.transport = transport or ExternalServiceTransport()

    @staticmethod
    def _provider_name(provider):
        name = str(provider or "anthropic").strip().lower()
        if name in ("", "claude"):
            return "anthropic"
        if name == "gpt":
            return "openai"
        return name

    def request(self, provider, api_key, payload, *, timeout=180):
        """Send one AI POST without retrying an ambiguous chargeable call."""
        provider_name = self._provider_name(provider)
        config = self._PROVIDERS.get(provider_name)
        if not config:
            raise ExternalServiceError(
                "ai_provider",
                "Unsupported AI provider",
                action="open_ai_settings",
            )
        headers = {"Content-Type": "application/json"}
        headers.update(config["headers"])
        key = str(api_key or "")
        if config["api_key_header"].lower() == "authorization":
            headers[config["api_key_header"]] = "Bearer " + key
        else:
            headers[config["api_key_header"]] = key
        response = self.transport.request(
            "ai_provider",
            config["url"],
            method="POST",
            body=json.dumps(payload or {}).encode("utf-8"),
            headers=headers,
            timeout=bounded_timeout(timeout, 180, 15, 300),
            timeout_maximum=300,
            allowed_hosts=config["hosts"],
            safe_to_retry=False,
            retries=0,
        )
        return json.loads(response.body.decode("utf-8", errors="strict"))
