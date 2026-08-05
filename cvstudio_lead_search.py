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
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

try:
    import certifi
except Exception:  # pragma: no cover - certifi is optional
    certifi = None

from cvstudio_lead_enrich import (
    _lead_apply_basic_job_filters,
    _lead_extract_json,
    _lead_fake_anthropic_response,
    _lead_filter_by_regions,
    _lead_google_jobs_query,
    _lead_is_direct_job_url,
    _lead_job_filter_instruction,
    _lead_normalize_company_fit_freshness,
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
        call_llm,
        provider_info,
        call_with_optional_web,
    ):
        self._secret_store = secret_store
        self._search_provider_config = search_provider_config
        self._search_tavily = search_tavily
        self._search_serpapi = search_serpapi
        self._search_provider_queries = search_provider_queries
        # call_llm and call_with_optional_web are patched at app level by the
        # phase5b tests; provider_info reads the app's _LLM_PROVIDER_INFO. All
        # three are late-binding callables resolving the current app global.
        self._call_llm = call_llm
        self._provider_info = provider_info
        self._call_with_optional_web = call_with_optional_web

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

    def call_with_optional_web(self, api_key, payload, warning_prefix="", graceful_json=None, provider="anthropic"):
        """Call the selected LLM provider with web search; retry without tools, then degrade gracefully.

        The old implementation could spend ~60s on web search, then another ~35s on
        fallback, then still return 504. This version never lets a secondary timeout
        crash Lead Finder when graceful_json is supplied.
        """
        warning = ""
        payload = dict(payload or {})
        primary_timeout = int(payload.pop("_primary_timeout_seconds", payload.get("_timeout_seconds", 75)))
        fallback_timeout = int(payload.pop("_fallback_timeout_seconds", 25))
        skip_no_web_fallback = bool(payload.pop("_skip_no_web_fallback", False))
        provider = str(provider or "anthropic").strip().lower()

        def graceful(msg):
            if graceful_json is None:
                raise TimeoutError(msg)
            return _lead_fake_anthropic_response(graceful_json), (warning_prefix or msg)

        # DeepSeek cannot browse the web at all -- if this call needs live search,
        # fail gracefully upfront with a clear, actionable message instead of
        # sending the tool anyway (it would just be silently dropped) or raising
        # an opaque exception mid-request.
        if payload.get("tools") and not self._provider_info().get(provider, {}).get("supports_web_search", True):
            msg = (
                "DeepSeek cannot browse the web itself for this search. Configure a Job Search "
                "Provider (Tavily or SerpAPI) so results can be fetched first and DeepSeek can "
                "classify them, or switch this search back to Claude/GPT."
            )
            if skip_no_web_fallback:
                return graceful(msg)
            fallback = dict(payload)
            fallback.pop("tools", None)
            fallback["_timeout_seconds"] = fallback_timeout
            try:
                data = self._call_llm(provider, api_key, fallback)
                warning = warning_prefix or msg
                return data, warning
            except (TimeoutError, socket.timeout, urllib.error.URLError):
                return graceful(msg)

        try:
            call_payload = dict(payload)
            call_payload["_timeout_seconds"] = primary_timeout
            data = self._call_llm(provider, api_key, call_payload)
            return data, warning
        except urllib.error.HTTPError as e:
            # HTTPError is a subclass of URLError, so keep this block before
            # the generic timeout/network handler below.
            err_body = e.read()
            try:
                err = json.loads(err_body)
                msg = err.get("error", {}).get("message", "API error")
            except Exception:
                msg = err_body.decode("utf-8", errors="replace")[:500]
            if payload.get("tools") and re.search(r"web[_\s-]?search|tool|permission|not enabled|not authorized|unsupported", msg, re.I):
                if skip_no_web_fallback:
                    return graceful("Live web search is unavailable for this API key/workspace; no fallback search links were shown.")
                fallback = dict(payload)
                fallback.pop("tools", None)
                fallback["_timeout_seconds"] = fallback_timeout
                try:
                    data = self._call_llm(provider, api_key, fallback)
                    warning = (warning_prefix or "Web search unavailable for this API key/workspace; continued without live crawling. Results may be less current.")
                    return data, warning
                except (TimeoutError, socket.timeout, urllib.error.URLError):
                    return graceful("Web search was unavailable and the no-web fallback also timed out; returned partial results instead of failing.")
            raise
        except (TimeoutError, socket.timeout, urllib.error.URLError):
            # Web search can occasionally hang for longer than the browser timeout.
            # Retry once without tools so the local app returns a usable response.
            if payload.get("tools"):
                if skip_no_web_fallback:
                    return graceful("Live web search timed out; no fallback search links were shown and no no-web retry was run.")
                fallback = dict(payload)
                fallback.pop("tools", None)
                fallback["_timeout_seconds"] = fallback_timeout
                try:
                    data = self._call_llm(provider, api_key, fallback)
                    warning = (warning_prefix or "Live web search timed out; continued with fast AI-only matching. Results are a starting point and should be reviewed against live job/company sources.")
                    return data, warning
                except (TimeoutError, socket.timeout, urllib.error.URLError):
                    return graceful("Live web search and no-web fallback both timed out; returned partial results instead of failing.")
            return graceful("Lead Finder API request timed out; returned partial results instead of failing.")

    def extract_from_search_provider_results(self, api_key, model, search_provider, provider_results, regions, job_sources, title_angles, target_role, industries, candidate_context, cv_excerpt, company_n=12, job_filters=None, llm_provider="anthropic"):
        """Classify search-provider URL/snippet results into job leads.

        This is intentionally no-web-search: the search provider has already done the
        retrieval. Claude only cleans/classifies snippets, which is faster and more
        reliable than asking it to browse job portals itself.
        """
        if not provider_results:
            return {"summary": {}, "companies": [], "people": []}, "", {}
        provider_name = self._search_provider_config(search_provider).get("provider") or "search_provider"
        compact_results = []
        for i, r in enumerate(provider_results[:70], 1):
            if not isinstance(r, dict):
                continue
            compact_results.append({
                "n": i,
                "title": str(r.get("title") or "")[:240],
                "url": str(r.get("url") or "")[:500],
                "snippet": str(r.get("snippet") or "")[:700],
                "published_date": str(r.get("published_date") or "")[:80],
                "provider": str(r.get("provider") or provider_name),
                "query": str(r.get("query") or "")[:240]
            })
        filter_instruction = _lead_job_filter_instruction(job_filters or {})
        prompt = f"""
You are cleaning job-search API results into recruiter job leads.

IMPORTANT
- The search provider already returned URLs/snippets. Do NOT browse further.
- Extract actual job leads only when the title/snippet/URL gives enough public evidence.
- If a result is only a generic portal search page, do not pretend it is a real job lead; set lead_kind='fallback_search_link'.
- If the URL is a direct job ad, set job_url to that URL and job_url_quality='direct_job_ad'.
- If it is only a search/listing/source page, leave job_url empty and put the URL in source_url with job_url_quality='source_or_search_result_only'.
- Keep selected-country/remote rules and relevance filters.
- Broad recruiter review mode: include adjacent, partial-fit, or lower tech-stack-fit job leads when the role/company/location is relevant. Do not discard just because the full tech stack is not visible or not perfect; reflect weaker fit in job_fit_percent and why_matched.

REGIONS
{json.dumps(regions, ensure_ascii=False)}

SELECTED JOB SOURCES
{json.dumps(job_sources, ensure_ascii=False)}

ROLE/TITLE ANGLES
{json.dumps(title_angles[:14], ensure_ascii=False)}

RELEVANCE FILTERS
{filter_instruction}

TARGET ROLE
{target_role or 'Infer from CV/context'}

INDUSTRY FOCUS
{industries or 'Infer from CV/context'}

RECRUITER CONTEXT
{candidate_context[:900] or 'No extra context provided.'}

CANDIDATE CV EXCERPT
{cv_excerpt[:3000]}

SEARCH PROVIDER RESULTS
{json.dumps(compact_results, ensure_ascii=False)}

RETURN ONLY VALID JSON. No markdown. Shape exactly:
{{
  "summary": {{
    "candidate_title": "best-fit candidate title",
    "seniority": "junior/mid/senior/lead/head/etc",
    "core_skills": ["skill"],
    "target_roles": ["role"],
    "target_job_title_angles": ["role/title angle searched"],
    "job_filters_used": {{}},
    "regions": ["region"],
    "location_filter": "selected countries are hard filters; include selected-country jobs and remote roles only when eligibility is evident",
    "job_sources_used": ["portal/source"],
    "source_strategy": "Search provider API results classified into job leads",
    "job_fit_method": "Job Fit % estimates role/skill/seniority/location alignment, but lower-fit leads are still shown for recruiter review unless explicitly excluded.",
    "freshness_method": "date_posted and days_open are taken from search result snippet/provider data where available; otherwise Unknown",
    "compliance_note": "public search/job/business sources only"
  }},
  "companies": [
    {{
      "id": "co_1",
      "company": "Company name or empty for fallback link",
      "country": "Country",
      "region": "City/region if known",
      "industry": "Industry",
      "job_portal": "portal/source",
      "matched_role": "Relevant open role title",
      "hiring_signal": "public job ad/search result signal",
      "date_posted": "YYYY-MM-DD, relative text, provider date, or empty string",
      "days_open": "",
      "job_freshness": "Today / 1-7 days open / 8-14 days open / 15-30 days open / 30+ days open / Unknown",
      "job_url": "DIRECT job-ad URL only or empty string",
      "job_url_quality": "direct_job_ad / needs_verification / source_or_search_result_only",
      "company_url": "URL or empty string",
      "job_fit_percent": 0,
      "match_score": 0,
      "why_matched": "short reason based on CV and result evidence",
      "source_url": "best evidence URL or empty string",
      "source_note": "source/provider/snippet evidence summary",
      "date_found": "{date.today().isoformat()}",
      "lead_kind": "extracted_job_lead / fallback_search_link"
    }}
  ],
  "people": []
}}

TARGET COUNT
- Return up to {int(company_n)} good leads.
- Prefer extracted_job_lead with company + role evidence.
- Do not invent companies from weak snippets.
""".strip()
        payload = {
            "model": model,
            "max_tokens": min(5200, max(2800, int(company_n) * 260)),
            "messages": [{"role": "user", "content": prompt}],
            "_timeout_seconds": 65,
        }
        data = self._call_llm(llm_provider, api_key, payload)
        raw_text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text" or "text" in b)
        try:
            parsed = _lead_extract_json(raw_text)
        except Exception:
            parsed = {"summary": {}, "companies": [], "people": []}
            return parsed, "Search provider returned results, but AI classification produced malformed output.", data.get("usage", {}) or {}
        parsed["people"] = []
        parsed = _lead_normalize_company_fit_freshness(parsed)
        parsed, location_warning = _lead_filter_by_regions(parsed, regions)
        parsed = _lead_normalize_company_fit_freshness(parsed)
        parsed, filter_warning = _lead_apply_basic_job_filters(parsed, job_filters or {})
        parsed.setdefault("summary", {})
        if isinstance(parsed.get("summary"), dict):
            parsed["summary"].setdefault("target_job_title_angles", title_angles)
            parsed["summary"].setdefault("job_filters_used", job_filters or {})
            parsed["summary"].setdefault("regions", regions)
            parsed["summary"].setdefault("job_sources_used", job_sources)
            parsed["summary"]["source_strategy"] = f"{provider_name} search API results classified into job leads"
            parsed["summary"]["search_provider_used"] = provider_name
            parsed["summary"]["search_provider_results_seen"] = len(provider_results)
        warning = ""
        if location_warning:
            warning = location_warning
        if filter_warning:
            warning = (warning + " " + filter_warning).strip() if warning else filter_warning
        return parsed, warning, data.get("usage", {}) or {}

    def quick_job_search(self, api_key, model, regions, job_sources, title_angles, target_role, industries, candidate_context, cv_excerpt, company_n=6, job_filters=None, llm_provider="anthropic"):
        """Smaller emergency live-search call when the full job-lead prompt times out.

        It asks for fewer fields and fewer leads, then the existing normalizer fills
        defaults. This gives the app a second chance to return real job leads before
        falling back to search links.
        """
        quick_titles = [t for t in (title_angles or []) if str(t).strip()][:8]
        quick_sources = [s for s in (job_sources or []) if str(s).strip()][:4]
        job_filters = job_filters or {}
        filter_instruction = _lead_job_filter_instruction(job_filters)
        prompt = f"""
Find live public job ads for a recruiter. Return ONLY valid JSON.

Rules:
- Use public web/job portal results only. No people, no emails.
- Selected locations are hard filters: {json.dumps(regions, ensure_ascii=False)}.
- Search selected portals only: {json.dumps(quick_sources, ensure_ascii=False)}.
- Use these role/title angles: {json.dumps(quick_titles, ensure_ascii=False)}.
- Apply these relevance filters: {filter_instruction}
- Do not invent companies. If only a search/listing URL is available, put it in source_url and leave job_url empty.
- job_url must be a direct job-ad URL only.

Target role: {target_role or 'infer from CV'}
Industries: {industries or 'infer'}
Recruiter context: {(candidate_context or '')[:900]}
CV excerpt: {(cv_excerpt or '')[:1800]}

JSON shape:
{{"summary":{{"candidate_title":"","target_job_title_angles":{json.dumps(quick_titles, ensure_ascii=False)},"job_filters_used":{json.dumps(job_filters, ensure_ascii=False)},"regions":{json.dumps(regions, ensure_ascii=False)},"job_sources_used":{json.dumps(quick_sources, ensure_ascii=False)},"source_strategy":"quick live job search fallback"}},"companies":[{{"company":"","country":"","region":"","industry":"","job_portal":"","matched_role":"","hiring_signal":"","date_posted":"","days_open":"","job_freshness":"Unknown","job_url":"","job_url_quality":"","company_url":"","job_fit_percent":0,"match_score":0,"why_matched":"","source_url":"","source_note":"","date_found":"{date.today().isoformat()}"}}],"people":[]}}
Target: up to {int(company_n)} real job leads.
""".strip()
        graceful = {"summary": {"target_job_title_angles": quick_titles, "job_filters_used": job_filters, "regions": regions, "job_sources_used": quick_sources, "source_strategy": "quick live job search fallback timed out"}, "companies": [], "people": []}
        payload = {
            "model": model,
            "max_tokens": 3200,
            "messages": [{"role": "user", "content": prompt}],
            "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 2}],
            "_primary_timeout_seconds": 58,
            "_fallback_timeout_seconds": 3,
            "_skip_no_web_fallback": True,
        }
        data, warning = self._call_with_optional_web(api_key, payload, warning_prefix="Quick job-search fallback did not complete.", graceful_json=graceful, provider=llm_provider)
        raw_text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text" or "text" in b)
        try:
            parsed = _lead_extract_json(raw_text)
        except Exception:
            parsed = graceful
            warning = (warning + " API returned malformed quick-search output.").strip()
        parsed["people"] = []
        parsed = _lead_normalize_company_fit_freshness(parsed)
        parsed, loc_warning = _lead_filter_by_regions(parsed, regions)
        parsed, filter_warning = _lead_apply_basic_job_filters(parsed, job_filters)
        if filter_warning:
            warning = (warning + " " + filter_warning).strip()
        if loc_warning:
            warning = (warning + " " + loc_warning).strip()
        return parsed, warning, data.get("usage", {})
