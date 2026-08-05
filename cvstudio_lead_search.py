"""Lead Finder search-provider HTTP primitives (Phase 7B).

Behaviour-preserving extraction of the low-level search-provider fetch cluster
from the legacy web shell: the certifi-aware SSL context, the JSON-over-HTTP
fetch helper, and the Tavily / SerpAPI query functions. These are pure network
primitives -- they take an API key and query as arguments and return normalised
result dicts, touching no application state (no secret store, no ``call_llm``,
no request context). This is a verbatim move; the web shell re-imports the
names so existing ``app._lead_*`` call sites and ``mock.patch.object`` seams are
unaffected.

The higher-level orchestration that reads the AI secret store and drives the
LLM (``_lead_search_provider_config``, ``_lead_collect_search_provider_results``,
``_lead_extract_from_search_provider_results``, ``_lead_quick_job_search``,
``_lead_call_with_optional_web``) stays in the web shell -- it is service-module
shaped and depends on app-owned globals.
"""

from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

try:
    import certifi
except Exception:  # pragma: no cover - certifi is optional
    certifi = None

from cvstudio_lead_enrich import (
    _lead_google_jobs_query,
    _lead_is_direct_job_url,
)


def _lead_ssl_context():
    """Use certifi's CA bundle when available.

    Some Windows/Python installs carry an outdated certificate store. That can
    cause SerpAPI/Tavily tests to fail with SSL: CERTIFICATE_VERIFY_FAILED even
    when the API key is valid. certifi keeps an updated Mozilla CA bundle and is
    safe to use for HTTPS verification; this does not disable SSL verification.
    """
    if certifi:
        try:
            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            return None
    return None


def _lead_fetch_json_url(url, method="GET", data=None, headers=None, timeout=18):
    encoded = None
    if data is not None:
        encoded = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=encoded, headers=headers or {}, method=method)
    context = _lead_ssl_context()
    try:
        if context is not None:
            resp_cm = urllib.request.urlopen(req, timeout=timeout, context=context)
        else:
            resp_cm = urllib.request.urlopen(req, timeout=timeout)
        with resp_cm as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        msg = str(reason)
        if "CERTIFICATE_VERIFY_FAILED" in msg or "certificate verify failed" in msg.lower() or "certificate has expired" in msg.lower():
            raise urllib.error.URLError(
                "SSL certificate verification failed while contacting the search provider. "
                "This usually means the local Python certificate bundle is outdated. "
                "CV Studio now uses certifi when installed; run INSTALL.bat/install.sh once, "
                "or run: pip install --upgrade certifi. Original error: " + msg
            )
        raise


def _lead_search_tavily(api_key, query, max_results=6, timeout=18):
    payload = {
        "query": query,
        "search_depth": "basic",
        "max_results": max(1, min(int(max_results or 6), 10)),
        "include_answer": False,
        "include_raw_content": False
    }
    # Tavily's current Search API uses Bearer authentication in the
    # Authorization header. Older examples sometimes placed api_key in the
    # JSON body; using the header avoids 401s on current accounts.
    data = _lead_fetch_json_url(
        "https://api.tavily.com/search",
        method="POST",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + str(api_key or "").strip()},
        timeout=timeout
    )
    out = []
    for r in data.get("results") or []:
        if not isinstance(r, dict):
            continue
        out.append({
            "title": str(r.get("title") or "").strip(),
            "url": str(r.get("url") or "").strip(),
            "snippet": str(r.get("content") or r.get("snippet") or "").strip(),
            "published_date": str(r.get("published_date") or "").strip(),
            "provider": "tavily",
            "query": query
        })
    return out


def _lead_search_serpapi(api_key, query, max_results=8, timeout=18):
    """Search SerpAPI for job results.

    Prefer SerpAPI's Google Jobs engine because organic Google search often
    returns generic JobStreet/LinkedIn listing pages. Google Jobs results carry
    structured title/company/location fields and apply_options links, which are
    much more likely to become usable Job Leads.
    """
    out = []
    # 1) Structured Google Jobs results first.
    try:
        google_jobs_query = _lead_google_jobs_query(query)
        params_jobs = urllib.parse.urlencode({
            "engine": "google_jobs",
            "q": google_jobs_query,
            "api_key": api_key,
            "hl": "en",
            "num": max(1, min(int(max_results or 8), 10))
        })
        data_jobs = _lead_fetch_json_url(
            "https://serpapi.com/search.json?" + params_jobs,
            method="GET",
            headers={"Accept": "application/json"},
            timeout=timeout
        )
        for r in data_jobs.get("jobs_results") or []:
            if not isinstance(r, dict):
                continue
            apply_url = ""
            structured_apply_source = ""
            # Prefer apply links from an actual employer/ATS/job-board page, not
            # Google search/listing pages. Google Jobs apply_options are already
            # job-specific enough to become reviewable Job Leads when title and
            # company are structured.
            for opt in r.get("apply_options") or []:
                if not isinstance(opt, dict):
                    continue
                link = str(opt.get("link") or "").strip()
                if not re.match(r"^https?://", link, re.I):
                    continue
                host = urllib.parse.urlparse(link).netloc.lower()
                if "google." in host or "serpapi" in host:
                    continue
                if _lead_is_direct_job_url(link):
                    apply_url = link
                    structured_apply_source = str(opt.get("title") or "").strip()
                    break
                if not apply_url:
                    apply_url = link
                    structured_apply_source = str(opt.get("title") or "").strip()
            related_url = ""
            for opt in r.get("related_links") or []:
                if isinstance(opt, dict) and re.match(r"^https?://", str(opt.get("link") or ""), re.I):
                    related_url = str(opt.get("link") or "").strip()
                    break
            detected = r.get("detected_extensions") or {}
            posted_at = ""
            if isinstance(detected, dict):
                posted_at = str(detected.get("posted_at") or detected.get("posted_at_text") or "").strip()
            out.append({
                "title": str(r.get("title") or "").strip(),
                "url": apply_url or related_url,
                "snippet": str(r.get("description") or "").strip(),
                "published_date": posted_at or str(r.get("posted_at") or "").strip(),
                "provider": "serpapi_google_jobs",
                "query": google_jobs_query,
                "original_query": query,
                "company_name": str(r.get("company_name") or "").strip(),
                "location": str(r.get("location") or "").strip(),
                "via": str(r.get("via") or "").strip(),
                "apply_source": structured_apply_source,
                "structured_job_result": bool(str(r.get("title") or "").strip() and str(r.get("company_name") or "").strip() and apply_url),
                "apply_options": r.get("apply_options") or []
            })
        if out:
            return out
    except Exception:
        # Fall back to organic below. The caller captures provider warnings per query.
        pass

    # 2) Organic fallback. This is less reliable and may return listing pages;
    # downstream direct-job filtering will remove those.
    params = urllib.parse.urlencode({
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": max(1, min(int(max_results or 8), 10))
    })
    data = _lead_fetch_json_url(
        "https://serpapi.com/search.json?" + params,
        method="GET",
        headers={"Accept": "application/json"},
        timeout=timeout
    )
    for r in data.get("organic_results") or []:
        if not isinstance(r, dict):
            continue
        out.append({
            "title": str(r.get("title") or "").strip(),
            "url": str(r.get("link") or r.get("url") or "").strip(),
            "snippet": str(r.get("snippet") or "").strip(),
            "published_date": str(r.get("date") or "").strip(),
            "provider": "serpapi",
            "query": query
        })
    return out


class LeadSearchOrchestrator:
    """Search-provider gathering as an explicitly wired service (Phase 7B).

    Owns the provider-config resolution (which reads the AI secret store for a
    backend-stored Tavily/SerpAPI key) and the multi-query collection loop. The
    web shell keeps the Flask routes and the ``_lead_*`` names; it constructs
    this with its app-level dependencies injected as callables so the module
    never imports ``app``.

    The cross-called helpers (``search_provider_config``, ``search_tavily``,
    ``search_serpapi``, ``search_provider_queries``) are injected as callables
    that resolve the *current* app-level name on each call, not bound once at
    construction. The phase5b characterization tests patch
    ``app._lead_search_provider_config`` / ``app._lead_search_tavily`` / ... and
    expect the collection loop to honour the patch; the late-binding callables
    preserve that seam exactly. ``secret_store`` is likewise a zero-arg callable
    because the store global can be reassigned by tests.
    """

    def __init__(
        self,
        *,
        secret_store,
        search_provider_config,
        search_tavily,
        search_serpapi,
        search_provider_queries,
    ):
        self._secret_store = secret_store
        self._search_provider_config = search_provider_config
        self._search_tavily = search_tavily
        self._search_serpapi = search_serpapi
        self._search_provider_queries = search_provider_queries

    def search_provider_config(self, raw):
        raw = raw if isinstance(raw, dict) else {}
        provider = str(raw.get("provider") or raw.get("type") or "none").strip().lower()
        if provider in {"", "off", "disabled", "none"}:
            provider = "none"
        # Keep provider names intentionally small and explicit for safety.
        if provider not in {"none", "tavily", "serpapi"}:
            provider = "none"
        key = str(raw.get("api_key") or raw.get("key") or "").strip()
        if (not key or key == "__BACKEND_SECURE__") and provider in {"tavily", "serpapi"}:
            key = str(self._secret_store().get("search_" + provider) or "").strip()
        return {"provider": provider, "api_key": key, "enabled": provider != "none" and bool(key)}

    def collect_search_provider_results(self, search_provider, job_sources, title_angles, regions, target_role="", job_filters=None, depth="standard"):
        cfg = self._search_provider_config(search_provider)
        if not cfg.get("enabled"):
            return [], []
        max_queries = {"light": 5, "standard": 8, "deep": 12}.get(str(depth or "standard").lower(), 8)
        per_query = {"light": 5, "standard": 7, "deep": 8}.get(str(depth or "standard").lower(), 7)
        queries = self._search_provider_queries(job_sources, title_angles, regions, target_role, job_filters, max_queries=max_queries)
        results = []
        warnings = []
        seen = set()
        for q in queries:
            try:
                if cfg["provider"] == "tavily":
                    batch = self._search_tavily(cfg["api_key"], q, max_results=per_query, timeout=16)
                elif cfg["provider"] == "serpapi":
                    batch = self._search_serpapi(cfg["api_key"], q, max_results=per_query, timeout=16)
                else:
                    batch = []
                for item in batch:
                    url = str(item.get("url") or "").strip()
                    title = str(item.get("title") or "").strip()
                    key = (url or title).lower().rstrip("/")
                    if not key or key in seen:
                        continue
                    seen.add(key)
                    results.append(item)
            except Exception as e:
                warnings.append(f"{cfg['provider']} query failed: {str(e)[:160]}")
            if len(results) >= {"light": 24, "standard": 40, "deep": 60}.get(str(depth or "standard").lower(), 40):
                break
        return results, warnings
