"""Pure Lead Finder URL, portal and company-guess helpers.

Behavior-preserving extraction from the legacy web shell. These classify job-ad
URLs, label the source portal, and derive a best-effort company name from a URL
or search result. They use only the standard library and are independent of the
Flask application, which re-exports them for its existing call sites.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from datetime import date


def _lead_is_direct_job_url(url):
    """Best-effort classifier for direct job-ad URLs vs portal home/search/listing pages."""
    url = str(url or "").strip()
    if not re.match(r"^https?://", url, re.I):
        return False
    try:
        u = urllib.parse.urlparse(url)
    except Exception:
        return False
    host = (u.netloc or "").lower()
    path = (u.path or "").lower()
    query = (u.query or "").lower()
    if not host or path in ("", "/"):
        return False
    # Common portal direct-ad patterns.
    if "linkedin.com" in host:
        params = urllib.parse.parse_qs(query, keep_blank_values=True)
        has_current_job_id = bool((params.get("currentjobid") or [""])[0])
        return "/jobs/view" in path or ("/jobs/collections/recommended" in path and has_current_job_id)
    if "jobstreet" in host or "jobsdb" in host:
        if _lead_is_non_job_content_url(url):
            return False
        # Known non-job JobStreet sections: login/account/profile pages,
        # company profiles, and saved/applied-jobs lists. These must be
        # rejected before query-string jobId handling because JobStreet
        # redirects can carry the original jobId while the current page is
        # still a sign-in/account/application page, not an openable job ad.
        if re.match(r"^/(companies|my-activity|profile|sign-in|login|register|account|saved-jobs|saved|applied-jobs|applied|applications)(/|$)", path):
            return False
        # JobStreet's split-view job URL shape carries the specific job
        # identifier in the query string (e.g. /jobs?jobId=87401944&type=standard)
        # even though the path itself is the generic "/jobs" listing path.
        # Accept it only after non-job account/sign-in/application paths are
        # excluded above.
        if re.search(r"(^|&)job[_-]?id=\d+", query):
            return True
        # Listing/category pages, including location-suffixed variants like
        # /sap-consultant-jobs/in-Kuala-Lumpur (a real, confirmed JobStreet
        # category-page shape) -- match "-jobs" as a path-segment boundary
        # anywhere in the path, not just anchored at the very end.
        if re.search(r"/(?:jobs|job-search)/", path) or re.search(r"-jobs(?:/|$)", path):
            return False
        leaf = path.rstrip("/").split("/")[-1]
        if re.fullmatch(r"(jobs?|careers?|vacancies|positions|openings|search|listings?|in-[a-z0-9-]+|page-?\d+)", leaf, re.I):
            return False
        # Anything else on a JobStreet/JobsDB domain that isn't one of the
        # known listing/editorial/account shapes above is very likely an
        # individual job ad -- JobStreet's exact permalink shape has varied
        # (slug-only, slug+id, id-only), so this treats "not a known
        # non-ad pattern" as the direct-ad signal rather than requiring an
        # exact '/job/' literal, which was the source of the false negatives.
        return len(path.strip("/")) >= 8
    if "indeed" in host:
        params = urllib.parse.parse_qs(query, keep_blank_values=True)
        has_jk = bool((params.get("jk") or [""])[0])
        # Indeed search/listing pages can carry vjk= or even jk= as split-view
        # context, but they are still listing pages, not stable direct job ads.
        # Accept only direct job-click/detail endpoints.
        if "/viewjob" in path:
            return True
        if path.rstrip("/") in ("/rc/clk", "/pagead/clk") and has_jk:
            return True
        return False
    if "glassdoor" in host:
        return "job-listing" in path or "jl=" in query
    if "hiredly" in host:
        return "/jobs/" in path and len(path.strip("/")) > len("jobs")
    if "mycareersfuture" in host:
        return "/job/" in path
    if "kalibrr" in host:
        return "/jobs/" in path or "/job/" in path
    if "monster" in host or "foundit" in host:
        return "/job/" in path or "jobid" in query
    # ATS/company-career platforms with individual requisition pages.
    ats_hosts = (
        "greenhouse.io", "lever.co", "ashbyhq.com", "workdayjobs.com", "myworkdayjobs.com",
        "smartrecruiters.com", "bamboohr.com", "icims.com", "jobvite.com", "workable.com",
        "successfactors", "recruitee.com", "comeet.co", "oraclecloud.com", "brassring.com",
        "jobadder.com", "pinpointhq.com", "teamtailor.com", "personio.com"
    )
    if any(h in host for h in ats_hosts):
        return len(path.strip("/")) > 8 and not re.search(r"/(jobs|careers|search|openings)/?$", path)
    # Generic company pages: accept only when URL path looks like an individual job, not a listing/search page.
    if re.search(r"/(job|jobs|career|careers|vacancy|vacancies|position|positions|opening|openings|role|roles)/", path):
        parts = [seg for seg in path.strip("/").split("/") if seg]
        leaf = parts[-1] if parts else ""
        if re.fullmatch(r"(jobs?|careers?|vacancies|positions|openings|search|listings?)", leaf):
            return False
        # Some real company career URLs end with a short numeric requisition id,
        # e.g. /job/kuala-lumpur-sap-consultant/123. Earlier builds rejected
        # those because the leaf was shorter than 5 characters, downgrading real
        # SAP/Oracle-style company job pages to Verify Source. Treat a specific
        # path under /job/ or a multi-segment career path as a direct posting,
        # while still keeping bare /jobs or /careers listing pages out.
        tail = ""
        m = re.search(r"/(?:job|jobs|career|careers|vacancy|vacancies|position|positions|opening|openings|role|roles)/(.+)$", path)
        if m:
            tail = m.group(1).strip("/")
        tail_compact = re.sub(r"[^a-z0-9]+", "", tail)
        if tail_compact and (len(tail_compact) >= 5 or len([x for x in tail.split("/") if x]) >= 2 or re.search(r"/(?:job|vacancy|position|opening|role)/[^/]+", path)):
            return True
    if re.search(r"(jobid|job_id|job=|reqid|req_id|requisition|gh_jid|currentjobid)=", query):
        return True
    return False


_LEAD_NON_JOB_CONTENT_PATH_MARKERS = (
    "/career-advice", "/career-guide", "/careers-advice", "/salary-guide", "/salary-guides",
    "/salary-report", "/salary-centre", "/salary-center", "/career-resources", "/resources/",
    "/trends/", "/blog/", "/articles/", "/news/", "/insights/", "/help/", "/faq",
)


def _lead_is_non_job_content_url(url):
    """True for portal editorial/informational pages -- career advice articles,
    salary guides, blog posts, help pages -- that are never job postings or
    hiring leads, no matter what role/company words happen to appear in the
    path (e.g. jobstreet.com/career-advice/role/sap-consultant/salary is an
    article about SAP Consultant salaries in general, not a lead at any
    specific employer, including one literally named SAP).
    """
    try:
        path = (urllib.parse.urlparse(str(url or "")).path or "").lower()
    except Exception:
        return False
    return any(marker in path for marker in _LEAD_NON_JOB_CONTENT_PATH_MARKERS)


def _lead_is_generic_portal_category_url(url, company=""):
    """True for portal 'browse jobs by title' pages with no company-specific
    signal at all (e.g. my.jobstreet.com/senior-data-engineer-jobs). These show
    every employer's ads for that title, not the one specific company/lead
    being claimed, so they are not actually useful as a 'verify this lead' link.

    Direct job-post URLs must never be treated as generic. v21.77 could mark
    LinkedIn /jobs/view/... as generic because the path starts with /jobs/.
    """
    if _lead_is_direct_job_url(url):
        return False
    if _lead_is_non_job_content_url(url):
        # Editorial/career-advice content is not just "generic" -- it's not
        # job content at all. Treating it as generic (rather than falling
        # through to the company-substring check below) ensures it always
        # gets swapped for a real verification search rather than kept as-is
        # just because a role/company word happens to appear in the URL.
        return True
    url = str(url or "")
    try:
        u = urllib.parse.urlparse(url)
    except Exception:
        return False
    host = (u.netloc or "").lower()
    path = (u.path or "").lower()
    query = (u.query or "").lower()
    known_portal = any(p in host for p in (
        "linkedin.com", "jobstreet", "jobsdb", "indeed", "glassdoor", "hiredly",
        "mycareersfuture", "kalibrr", "monster", "foundit"
    ))
    if not known_portal:
        return False
    # JobStreet/JobsDB control pages (sign-in/account/profile/saved/applied jobs
    # and company profile pages) do not verify a specific employer+role lead.
    # Treat them like generic/non-direct source pages so they get replaced by
    # a targeted verification search instead of surviving as a clickable source
    # just because a redirect query contains jobId=.
    if ("jobstreet" in host or "jobsdb" in host) and re.match(r"^/(companies|my-activity|profile|sign-in|login|register|account|saved-jobs|saved|applied-jobs|applied|applications)(/|$)", path):
        return True
    if path in ("", "/"):
        return True
    # Search/listing/category URLs are generic even when the company word appears
    # in the URL. This matters for real recruiter cases such as Oracle DBA or SAP
    # Consultant: a generic JobStreet page like /oracle-dba-jobs contains
    # "oracle", but it still does not verify Oracle is the employer.
    if re.search(r"-jobs(?:/|$)", path) or re.search(r"-jobs\.html$", path) or re.search(r"/(jobs|job-search|search)(/|$)", path):
        return True
    if query and re.search(r"(^|&)(keywords?|q|query|location|where|search|page|fromage|salary)=", query):
        return True
    company_compact = re.sub(r"[^a-z0-9]+", "", str(company or "").lower())
    path_query_compact = re.sub(r"[^a-z0-9]+", "", (path + "?" + query))
    # For non-search/non-category portal URLs, a visible company token can be a
    # useful specificity signal. Direct job-post URLs were already returned False
    # at the top via _lead_is_direct_job_url.
    if company_compact and len(company_compact) >= 3 and company_compact in path_query_compact:
        return False
    return False


def _lead_verification_company_text(company):
    """Return a useful employer string for verification searches.

    Some provider/AI rows use placeholders like "Unknown" or
    "Unknown (Senior Data Engineer — AWS infrastructure...)" in the company
    field when JobStreet snippets do not expose the employer. Quoting those
    placeholders in a Google verification query makes the Verify Source button
    search for the word "Unknown" instead of the actual role. Treat them as
    missing employer evidence.
    """
    text = re.sub(r"\s+", " ", str(company or "")).strip()
    if not text:
        return ""
    compact = re.sub(r"[^a-z0-9]+", "", text.lower())
    if not compact:
        return ""
    bad_exact = {
        "unknown", "unknownemployer", "unknowncompany", "na", "none", "notavailable",
        "notspecified", "notprovided", "notvisible", "employernotvisible",
        "companynotvisible", "confidential", "undisclosed", "tbc", "tbd"
    }
    if compact in bad_exact:
        return ""
    # Handles values like "Unknown (Senior Data Engineer — scalable pipelines role)".
    if re.match(r"^(unknown|n/?a|not\s+(?:specified|provided|visible|available)|employer\s+(?:not\s+)?visible|company\s+(?:not\s+)?visible|confidential|undisclosed)\b", text, re.I):
        return ""
    return text


def _lead_is_generated_verification_search(url):
    """True for Google verification searches generated by CV Studio.

    These are not job-source evidence from Google; they are recruiter review
    helpers used when the selected portal did not expose a direct permalink.
    Do not remove them during selected-source cleanup.
    """
    try:
        u = urllib.parse.urlparse(str(url or ""))
        host = (u.netloc or "").lower()
        path = (u.path or "").lower()
        return "google." in host and path.startswith("/search")
    except Exception:
        return False


def _lead_canonical_direct_job_url(url):
    """Return a cleaner direct job URL when a portal provides a split-view link.

    Keep normal direct URLs unchanged, but turn LinkedIn collection links that
    only expose currentJobId into the stable /jobs/view/<id>/ permalink. This
    prevents the Open Job Ad button from opening a generic LinkedIn collection
    page when the job id is known.
    """
    url = str(url or "").strip()
    if not url:
        return url
    try:
        u = urllib.parse.urlparse(url)
        host = (u.netloc or "").lower()
        path = (u.path or "").lower()
        params = urllib.parse.parse_qs((u.query or "").lower(), keep_blank_values=True)
    except Exception:
        return url
    if "linkedin.com" in host and "/jobs/collections/recommended" in path:
        current_job_id = (params.get("currentjobid") or [""])[0]
        if re.fullmatch(r"\d{5,}", str(current_job_id or "")):
            return f"https://www.linkedin.com/jobs/view/{current_job_id}/"
    return url


def _lead_url_portal(url):
    """Display-friendly source name for a job URL."""
    try:
        host = (urllib.parse.urlparse(str(url or "")).netloc or "").lower()
    except Exception:
        host = str(url or "").lower()
    if "linkedin.com" in host:
        return "LinkedIn Jobs"
    if "jobstreet" in host:
        return "JobStreet"
    if "jobsdb" in host:
        return "JobsDB"
    if "indeed" in host:
        return "Indeed"
    if "glassdoor" in host:
        return "Glassdoor"
    if "hiredly" in host:
        return "Hiredly"
    if "mycareersfuture" in host:
        return "MyCareersFuture"
    if "kalibrr" in host:
        return "Kalibrr"
    if "monster" in host or "foundit" in host:
        return "Monster/Foundit"
    return "Company Careers"


def _lead_guess_portal_from_url(url, provider=""):
    s = (str(url or "") + " " + str(provider or "")).lower()
    if "linkedin.com" in s:
        return "LinkedIn Jobs"
    if "jobstreet" in s:
        return "JobStreet"
    if "indeed" in s:
        return "Indeed"
    if "glassdoor" in s:
        return "Glassdoor"
    if "foundit" in s or "monster" in s:
        return "Monster/Foundit"
    if "hiredly" in s:
        return "Hiredly"
    if "jobsdb" in s:
        return "JobsDB"
    if "mycareersfuture" in s:
        return "MyCareersFuture"
    if "kalibrr" in s:
        return "Kalibrr"
    if any(x in s for x in ["greenhouse", "lever.co", "workday", "smartrecruiters", "workable", "jobvite", "icims", "ashby", "successfactors"]):
        return "Company Careers / ATS"
    try:
        u = urllib.parse.urlparse(str(url or ""))
        if "career" in (u.netloc or "").lower() or re.search(r"/(careers?|jobs?|vacanc)", (u.path or "").lower()):
            return "Company Careers"
    except Exception:
        pass
    return str(provider or "Search Provider").title() if provider else "Search Provider"


def _lead_source_allowed_by_selection(url, portal, job_sources):
    """Respect the user's selected source chips for provider results.

    SerpAPI/Google Jobs can return Indeed/Glassdoor/etc. even when the user only
    selected JobStreet. Earlier builds accepted those cross-source results, which
    made the source filters feel ignored. Unknown/company-career URLs are allowed
    only when Company Careers or Other Portals is selected.
    """
    selected = {str(s or "").strip().lower() for s in (job_sources or []) if str(s or "").strip()}
    if not selected:
        return True
    portal_l = str(portal or "").strip().lower()
    url_l = str(url or "").lower()

    def sel_has(*needles):
        return any(any(n in s for n in needles) for s in selected)

    if "linkedin" in portal_l or "linkedin.com" in url_l:
        return sel_has("linkedin")
    if "jobstreet" in portal_l or "jobstreet" in url_l:
        return sel_has("jobstreet")
    if "jobsdb" in portal_l or "jobsdb" in url_l:
        return sel_has("jobsdb")
    if "indeed" in portal_l or "indeed" in url_l:
        return sel_has("indeed")
    if "glassdoor" in portal_l or "glassdoor" in url_l:
        return sel_has("glassdoor")
    if "hiredly" in portal_l or "hiredly" in url_l:
        return sel_has("hiredly")
    if "mycareersfuture" in portal_l or "mycareersfuture" in url_l:
        return sel_has("mycareersfuture")
    if "kalibrr" in portal_l or "kalibrr" in url_l:
        return sel_has("kalibrr")
    if "monster" in portal_l or "foundit" in portal_l or "monster" in url_l or "foundit" in url_l:
        return sel_has("monster", "foundit")
    if "company career" in portal_l or "ats" in portal_l:
        return sel_has("company", "career")

    known_ats = ("greenhouse.io", "lever.co", "ashbyhq.com", "workdayjobs", "myworkdayjobs", "smartrecruiters.com", "workable.com", "jobvite.com", "icims.com", "successfactors", "oraclecloud.com", "brassring.com")
    if any(h in url_l for h in known_ats):
        return sel_has("company", "career")

    # Unknown public job boards should only pass when the user selected Other
    # Portals. This prevents a JobStreet-only run from showing unrelated boards.
    return sel_has("other public", "other portal")


def _lead_clean_company_guess(raw):
    raw = re.sub(r"\s+", " ", str(raw or "")).strip(" -|,•:")
    raw = re.sub(r"\b(?:is\s+)?hiring\b.*$", "", raw, flags=re.I).strip(" -|,•:")
    raw = re.sub(r"\bis\s*$", "", raw, flags=re.I).strip(" -|,•:")
    raw = re.sub(r"\b(job|jobs|career|careers|vacancy|vacancies|recruitment)\b.*$", "", raw, flags=re.I).strip(" -|,•:")
    raw = re.sub(r"\b(linkedin|jobstreet|indeed|glassdoor|hiredly|foundit|monster|jobsdb|mycareersfuture|kalibrr|serpapi|tavily)\b.*$", "", raw, flags=re.I).strip(" -|,•:")
    words = raw.split()
    if len(words) >= 2 and len(words) % 2 == 0:
        mid = len(words) // 2
        if " ".join(words[:mid]).lower() == " ".join(words[mid:]).lower():
            words = words[:mid]
    if len(words) >= 2 and words[0].lower() == words[1].lower():
        words = words[1:]
    raw = re.sub(r"\s+", " ", " ".join(words)).strip(" -|,•:")
    if len(raw) > 90:
        raw = raw[:90].strip(" -|,•:")
    bad = {"jobs", "job", "careers", "career", "malaysia", "singapore", "remote", "hiring", "linkedin", "jobstreet", "indeed", "search", "source"}
    if raw.lower() in bad or len(raw) < 2:
        return ""
    return raw


def _lead_guess_company_from_url(url):
    try:
        host = urllib.parse.urlparse(str(url or "")).netloc.lower()
    except Exception:
        return ""
    if not host:
        return ""
    portal_bits = ["linkedin", "jobstreet", "indeed", "glassdoor", "foundit", "monster", "hiredly", "jobsdb", "mycareersfuture", "kalibrr", "google"]
    if any(x in host for x in portal_bits):
        return ""
    host = re.sub(r"^www\.", "", host)
    parts = host.split(".")
    if len(parts) >= 2:
        base = parts[-3] if parts[-2] in {"com", "co", "net", "org"} and len(parts) >= 3 else parts[-2]
    else:
        base = parts[0]
    base = re.sub(r"[-_]+", " ", base).strip()
    if not base or base in {"jobs", "careers", "workdayjobs", "myworkdayjobs", "greenhouse", "lever", "ashbyhq", "smartrecruiters"}:
        return ""
    return base.title()


def _lead_clean_csv(value, limit=12):
    if isinstance(value, list):
        parts = value
    else:
        parts = re.split(r"[,;\n]+", str(value or ""))
    out = []
    seen = set()
    for part in parts:
        part = re.sub(r"\s+", " ", str(part or "")).strip()
        if not part:
            continue
        k = part.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(part)
        if len(out) >= limit:
            break
    return out


def _lead_clean_job_filters(raw):
    raw = raw if isinstance(raw, dict) else {}
    out = {
        "must_have": ", ".join(_lead_clean_csv(raw.get("must_have"), 12)),
        "exclude_keywords": ", ".join(_lead_clean_csv(raw.get("exclude_keywords"), 12)),
        "seniority": re.sub(r"\s+", " ", str(raw.get("seniority") or "")).strip(),
        "max_days_open": re.sub(r"[^0-9]", "", str(raw.get("max_days_open") or ""))[:3],
        "work_setup": re.sub(r"\s+", " ", str(raw.get("work_setup") or "")).strip(),
        "employment_type": re.sub(r"\s+", " ", str(raw.get("employment_type") or "")).strip(),
        "company_include": ", ".join(_lead_clean_csv(raw.get("company_include"), 10)),
        "company_exclude": ", ".join(_lead_clean_csv(raw.get("company_exclude"), 10)),
    }
    return {k: v for k, v in out.items() if v}


def _lead_job_filter_instruction(job_filters):
    if not job_filters:
        return "No extra relevance filters supplied. Infer relevance from CV, target role, regions and selected portals."
    lines = []
    if job_filters.get("must_have"):
        lines.append(f"- MUST-HAVE keywords/skills: {job_filters['must_have']}. Prefer and rank higher when these appear, but do not discard otherwise relevant role/title/job leads only because the snippet does not show every stack/skill.")
    if job_filters.get("exclude_keywords"):
        lines.append(f"- EXCLUDE keywords: {job_filters['exclude_keywords']}. Remove leads that clearly match these exclusions.")
    if job_filters.get("seniority"):
        lines.append(f"- SENIORITY target: {job_filters['seniority']}. Rank/title-match around this level, but include adjacent levels as lower-fit review leads when the job is otherwise relevant.")
    if job_filters.get("max_days_open"):
        lines.append(f"- FRESHNESS preference: prioritize jobs posted within {job_filters['max_days_open']} days when date is visible. Do not discard otherwise relevant jobs only because posting date is hidden.")
    if job_filters.get("work_setup"):
        lines.append(f"- WORK SETUP preference: {job_filters['work_setup']}. Use as relevance/ranking signal unless it conflicts with selected-country rules.")
    if job_filters.get("employment_type"):
        lines.append(f"- EMPLOYMENT TYPE preference: {job_filters['employment_type']}. Prefer ads matching this type.")
    if job_filters.get("company_include"):
        lines.append(f"- COMPANY/INDUSTRY INCLUDE: {job_filters['company_include']}. Prefer these sectors/company types, but keep adjacent sectors as lower-fit review leads unless clearly excluded.")
    if job_filters.get("company_exclude"):
        lines.append(f"- COMPANY/INDUSTRY EXCLUDE: {job_filters['company_exclude']}. Remove leads that clearly match these exclusions.")
    return "\n".join(lines)


def _lead_filter_query_terms(job_filters):
    if not job_filters:
        return ""
    parts = []
    for k in ("must_have", "seniority", "work_setup", "employment_type", "company_include"):
        v = job_filters.get(k)
        if v:
            parts.extend(_lead_clean_csv(v, 6) if k in ("must_have", "company_include") else [v])
    return " ".join(parts[:12]).strip()


def _lead_exclude_query_terms(job_filters):
    if not job_filters:
        return ""
    terms = _lead_clean_csv(job_filters.get("exclude_keywords"), 8) + _lead_clean_csv(job_filters.get("company_exclude"), 6)
    return " ".join("-" + re.sub(r"\s+", "-", t.strip()) for t in terms if t.strip())


_LEAD_EMAIL_BLOCKED_PERSONAL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.com.my", "yahoo.com.sg", "ymail.com", "rocketmail.com",
    "hotmail.com", "hotmail.com.my", "hotmail.co.uk", "outlook.com", "outlook.my", "live.com", "live.com.my", "msn.com",
    "icloud.com", "me.com", "mac.com", "proton.me", "protonmail.com", "pm.me",
    "aol.com", "mail.com", "email.com", "gmx.com", "gmx.net", "fastmail.com", "hey.com",
    "tuta.com", "tutanota.com", "zoho.com", "yandex.com", "yandex.ru", "qq.com", "163.com", "126.com",
    "rediffmail.com", "mail.ru", "inbox.com", "hushmail.com", "lavabit.com"
}


_LEAD_EMAIL_BLOCKED_DOMAIN_SUFFIXES = (
    ".gmail.com", ".googlemail.com", ".yahoo.com", ".hotmail.com", ".outlook.com", ".live.com",
    ".icloud.com", ".protonmail.com", ".proton.me", ".mail.com", ".gmx.com", ".yandex.com"
)


_LEAD_EMAIL_RE = re.compile(r"^[A-Z0-9._%+\-']+@([A-Z0-9.\-]+\.[A-Z]{2,})$", re.I)


def _lead_email_domain(email):
    """Return the normalized domain for a syntactically plausible email."""
    email = str(email or "").strip().strip("<>()[]{}.,;:'\" ")
    m = _LEAD_EMAIL_RE.match(email)
    if not m:
        return ""
    domain = m.group(1).lower().strip(".")
    return domain


def _lead_is_company_domain_email(email, company=""):
    """Accept only non-personal, non-free-mail business-domain emails.

    This intentionally does not guess or pattern-match company domains. It only
    removes obvious personal/free-mail domains and malformed addresses, because
    legitimate public business emails can appear on parent-company, agency,
    conference, or directory domains that do not text-match the company name.
    """
    domain = _lead_email_domain(email)
    if not domain:
        return False
    if domain in _LEAD_EMAIL_BLOCKED_PERSONAL_DOMAINS:
        return False
    if any(domain.endswith(suffix) for suffix in _LEAD_EMAIL_BLOCKED_DOMAIN_SUFFIXES):
        return False
    # Common placeholders/test domains should never be treated as real contacts.
    if domain in {"example.com", "example.org", "example.net", "test.com", "localhost"}:
        return False
    return True


def _lead_sanitize_public_business_emails(people):
    """Clear personal/free-mail or malformed emails before returning/caching.

    The Lead Finder email step is for public business/company-domain review only.
    LinkedIn/profile URLs can be identity context; email values themselves must
    come from a non-personal business domain.
    """
    if not isinstance(people, list):
        return []
    cleaned = []
    for p in people:
        if not isinstance(p, dict):
            continue
        item = dict(p)
        email = str(item.get("email") or "").strip()
        if email and not _lead_is_company_domain_email(email, item.get("company") or ""):
            item["email"] = ""
            item["email_confidence"] = ""
            item["email_source"] = ""
            item["verification_status"] = "Not found"
            note = str(item.get("notes") or "").strip()
            block_note = "Removed personal/free-mail or invalid email; public business-domain email required."
            item["notes"] = (note + " " + block_note).strip() if note and block_note not in note else (note or block_note)
        elif not email and not str(item.get("verification_status") or "").strip():
            item["verification_status"] = "Not found"
        cleaned.append(item)
    return cleaned


def _lead_normalize_linkedin_url(url):
    """Strip scheme/www/tracking-param/fragment differences so the same profile
    always yields the same cache key, regardless of how the URL happened to be
    written (http vs https, with/without www, with/without trailing slash, with
    tracking query params attached).
    """
    url = str(url or "").strip()
    if not url:
        return ""
    if re.match(r"^(?:www\.)?linkedin\.com/", url, flags=re.I):
        url = "https://" + url
    try:
        u = urllib.parse.urlparse(url)
        host = (u.netloc or "").lower()
        if "linkedin.com" not in host:
            return ""
        host = re.sub(r"^www\.", "", host)
        path = u.path.rstrip("/")
        return f"https://{host}{path}".lower()
    except Exception:
        return ""


def _lead_has_any(text, terms):
    """Role-family keyword match with word-boundaries for short tokens.

    Prevents false triggers like HR from words such as "through" or AP from
    "Spark", which caused unrelated title families to be searched.
    """
    text = str(text or "").lower()
    for term in terms or []:
        t = str(term or "").strip().lower()
        if not t:
            continue
        if len(t) <= 3 or re.fullmatch(r"[a-z]&[a-z]", t):
            if re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", text):
                return True
        else:
            if t in text:
                return True
    return False


_LEAD_FAMILY_PATTERNS = {
    "hr": [
        r"\bhr\s+(executive|assistant|manager|specialist|generalist|officer|administrator|admin|business partner|bp|partner|operations|shared services|shared service)\b",
        r"\b(human resources|people\s*&\s*culture|talent acquisition|recruiter|recruitment consultant|payroll specialist|employee relations|compensation and benefits|c&b|learning and development|l&d|organizational development|organisation development)\b",
    ],
    "data": [
        r"\b(data engineer|data engineering|senior data engineer|lead data engineer|data platform|data architect|etl|elt|data warehouse|data lake|lakehouse|databricks|snowflake|spark|pyspark|airflow|dbt|analytics engineer|bi developer|business intelligence|data analyst|data scientist|machine learning|mlops|ai engineer|data governance)\b",
    ],
    "software_tech": [
        r"\b(software engineer|software developer|backend developer|front[- ]?end developer|full[- ]?stack developer|mobile developer|qa engineer|test engineer|solution architect|technical architect|cloud engineer|devops|sre|site reliability|platform engineer|infrastructure engineer|cybersecurity|security engineer|application support|production support|systems engineer|network engineer|euc|desktop support|end user computing|it support)\b",
    ],
    "finance": [
        r"\b(finance executive|finance analyst|finance manager|head of finance|chief financial officer|cfo|accountant|accounting|accounts payable|accounts receivable|accounts executive|ap analyst|ar analyst|r2r|record to report|otc|order to cash|p2p|procure to pay|fp&a|financial analyst|financial controller|treasury|tax executive|tax manager|audit executive|internal auditor|shared services analyst|finance operations|payroll executive|payroll specialist|payroll manager|credit control|credit controller|billing executive|billing specialist|collections executive|bookkeeper|cost accountant|general ledger accountant|gl accountant)\b",
    ],
    "operations": [
        r"\b(operations executive|operations specialist|operations analyst|operations manager|head of operations|business operations|process improvement|continuous improvement|supply chain|logistics|warehouse|fulfillment|procurement|purchasing|production supervisor|production manager|manufacturing|plant manager|quality executive|qa executive|qc executive|customer service|contact centre|call center)\b",
    ],
    "marketing": [
        r"\b(marketing executive|marketing specialist|marketing manager|brand executive|brand manager|digital marketing|performance marketing|growth marketer|growth marketing|seo specialist|sem specialist|content marketing|social media|communications executive|communications manager|pr executive|crm executive|campaign manager|ecommerce|e-commerce|trade marketing|market research|events executive)\b",
    ],
    "sales": [
        r"\b(sales executive|sales representative|sales consultant|sales manager|business development|bd manager|account executive|account manager|key account|commercial executive|commercial manager|partnerships manager|channel sales|retail sales|customer success|client success|revenue operations|pre[- ]?sales)\b",
    ],
    "legal_risk": [
        r"\b(legal executive|legal counsel|general counsel|legal advisor|legal manager|contracts specialist|contracts manager|contract manager|company secretary|corporate secretarial|compliance executive|compliance analyst|compliance manager|compliance officer|chief compliance officer|chief risk officer|regulatory compliance|risk analyst|risk manager|operational risk|governance specialist|aml analyst|kyc analyst|data protection officer|privacy specialist)\b",
    ],
    "admin": [
        r"\b(admin executive|administrative assistant|administration manager|office manager|business support|executive assistant|personal assistant|secretary|receptionist|facilities executive|facilities manager|corporate services)\b",
    ],
    "product_design": [
        r"\b(product executive|product analyst|product manager|senior product manager|product owner|product lead|ux designer|ui designer|product designer|ux researcher|service designer|customer experience|cx manager)\b",
    ],
    "oil_gas": [
        r"\b(oil and gas|o&g|petroleum|upstream|downstream|offshore|marine engineer|epc|hse|ehs|process engineer|rotating equipment|static equipment|maintenance engineer|turnaround planner|reliability engineer|energy analyst)\b",
    ],
    "consulting_project": [
        r"\b(management consultant|strategy consultant|business consultant|advisory consultant|transformation consultant|change management|business analyst|senior business analyst|pmo analyst|pmo consultant|project consultant|implementation consultant|project manager|programme manager|program manager|delivery manager)\b",
    ],
    "sap_erp": [
        r"\b(sap fico|sap basis|sap consultant|sap functional|sap solution architect|sap finance|sap mm|sap sd|sap abap|s/4hana|s4hana|erp consultant|erp business analyst|enterprise applications|oracle consultant|workday consultant|microsoft dynamics)\b",
    ],
    "database_dba": [
        r"\b(database administrator|dba|oracle dba|oracle rac|exadata|mysql dba|sql server dba|postgresql dba|postgres dba|mongodb dba|db2 dba|database engineer|database architect|database administration|rman|data guard|golden gate|asm administrator|database reliability engineer|dre)\b",
    ],
}


_LEAD_TERMINAL_ROLE_TOKENS = {
    "manager", "head", "director", "vp", "svp", "chief", "lead", "executive", "specialist", "analyst",
    "engineer", "developer", "consultant", "assistant", "associate", "officer", "accountant", "recruiter",
    "designer", "scientist", "administrator", "dba", "controller", "auditor", "secretary", "counsel",
    "marketer", "representative", "technician", "coordinator", "planner", "supervisor", "architect",
    "partner", "clerk", "principal",
}


_LEAD_SENIORITY_TOKENS = {
    "senior", "lead", "principal", "head", "director", "vp", "svp", "chief",
    "junior", "intern", "trainee", "fresh", "assistant", "associate",
}


def _lead_contains_any_token(text, tokens):
    text = str(text or "")
    return any(re.search(r"(?<![a-z0-9])" + re.escape(tok) + r"(?![a-z0-9])", text) for tok in tokens)


_LEAD_FAMILY_DEFAULT_TITLE = {
    "hr": "HR Executive",
    "data": "Data Engineer",
    "software_tech": "Software Engineer",
    "finance": "Finance Executive",
    "operations": "Operations Executive",
    "marketing": "Marketing Executive",
    "sales": "Sales Executive",
    "legal_risk": "Compliance Executive",
    "admin": "Admin Executive",
    "product_design": "Product Manager",
    "oil_gas": "Oil and Gas Engineer",
    "consulting_project": "Business Analyst",
    "sap_erp": "SAP Consultant",
    "database_dba": "Database Administrator",
}


def _lead_family_scores(text):
    text = re.sub(r"\s+", " ", str(text or "").lower())
    scores = {}
    for family, patterns in _LEAD_FAMILY_PATTERNS.items():
        score = 0
        for pat in patterns:
            matches = re.findall(pat, text, flags=re.I)
            if matches:
                score += len(matches) * 3
        # Extra controlled single-token signals. Do not use these for HR because
        # HR is too easy to contaminate via company names/stakeholder mentions.
        if family == "data":
            for tok in ("python", "sql", "spark", "pyspark", "databricks", "snowflake", "airflow", "dbt"):
                if re.search(r"(?<![a-z0-9])" + re.escape(tok) + r"(?![a-z0-9])", text):
                    score += 1
        elif family == "finance":
            for tok in ("ifrs", "audit", "tax", "treasury", "fp&a"):
                if re.search(r"(?<![a-z0-9])" + re.escape(tok) + r"(?![a-z0-9])", text):
                    score += 1
        elif family == "software_tech":
            for tok in ("java", "javascript", "react", "node", ".net", "kubernetes", "aws", "azure", "gcp"):
                if re.search(r"(?<![a-z0-9])" + re.escape(tok) + r"(?![a-z0-9])", text):
                    score += 1
        elif family == "database_dba":
            # These are distinctive enough (unlike generic "sql") to weight more
            # heavily; a CV listing 2-3 of these is almost certainly a DBA profile
            # even if it never literally says "database administrator".
            for tok in ("rac", "exadata", "rman", "asm", "data guard", "dataguard", "goldengate", "golden gate",
                        "pl/sql", "plsql", "t-sql", "tsql", "asm administrator", "tablespace", "oem", "toad"):
                if re.search(r"(?<![a-z0-9])" + re.escape(tok) + r"(?![a-z0-9])", text):
                    score += 2
        if score:
            scores[family] = score
    return scores


def _lead_families_from_text(text, max_families=3):
    scores = _lead_family_scores(text)
    if not scores:
        return []
    best = max(scores.values())
    # Keep only strong/near-best families. This prevents a random HR mention in a
    # Data Engineer CV from generating HR title angles.
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [fam for fam, score in ranked if score >= max(3, best * 0.65)][:max_families]


def _lead_primary_role_families(target_role="", cv_text="", candidate_context="", industries=""):
    target_role = str(target_role or "").strip()
    target_families = _lead_families_from_text(target_role, max_families=2)
    if target_role and target_families:
        return target_families
    # Only use high-signal CV areas for inference. Full CV text can include many
    # stakeholder/project words that are not the candidate's own function.
    cv_focus = str(cv_text or "")[:3500]
    ctx_focus = str(candidate_context or "")[:1200]
    ind_focus = str(industries or "")[:500]
    return _lead_families_from_text(" ".join([cv_focus, ctx_focus, ind_focus]), max_families=2)


def _lead_resolve_search_target_role(target_role="", cv_text="", candidate_context="", industries=""):
    """Protect against stale/manual target-role fields contaminating searches.

    If the target role says HR but the uploaded CV is clearly Data/Finance/etc.,
    Lead Finder should not search HR jobs. The CV's own strong role family wins,
    but a warning is returned so the user can see why the search was anchored.
    """
    raw_target = re.sub(r"\s+", " ", str(target_role or "")).strip()
    cv_fams = _lead_primary_role_families("", cv_text, candidate_context, industries)
    target_fams = _lead_families_from_text(raw_target, max_families=2)
    if raw_target and target_fams and cv_fams and not set(target_fams).intersection(cv_fams):
        replacement = _LEAD_FAMILY_DEFAULT_TITLE.get(cv_fams[0], "Relevant open role")
        return replacement, f'Target role "{raw_target}" looked inconsistent with the uploaded CV role family; Lead Finder anchored job search to "{replacement}" to avoid unrelated job leads.'
    if raw_target:
        return raw_target, ""
    if cv_fams:
        return _LEAD_FAMILY_DEFAULT_TITLE.get(cv_fams[0], "Relevant open role"), ""
    return "", ""


def _lead_job_title_angles(target_role, cv_text="", candidate_context="", industries=""):
    """Generate recruiter job-title angles anchored to the candidate's role family.

    Earlier broad versions added title banks for every keyword seen in the CV,
    which caused failures such as Data Engineer uploads producing HR Executive
    searches because the CV mentioned HR stakeholders. This version chooses the
    primary role family first, then expands only within that family.
    """
    titles = []

    def add(*items):
        existing = {t.lower() for t in titles}
        for item in items:
            item = re.sub(r"\s+", " ", str(item or "")).strip()
            if item and item.lower() not in existing:
                titles.append(item)
                existing.add(item.lower())

    cleaned_target = re.sub(r"\s+", " ", str(target_role or "")).strip()
    if cleaned_target:
        add(cleaned_target)
        tl = cleaned_target.lower()
        has_seniority = _lead_contains_any_token(tl, _LEAD_SENIORITY_TOKENS)
        has_terminal = _lead_contains_any_token(tl, _LEAD_TERMINAL_ROLE_TOKENS)
        if not _lead_contains_any_token(tl, ("senior", "lead", "principal", "head", "director", "vp", "svp", "chief")):
            add(f"Senior {cleaned_target}")
        if not _lead_contains_any_token(tl, ("senior", "lead", "head", "director", "vp", "svp", "chief")):
            add(f"Lead {cleaned_target}")
        if not has_terminal:
            add(f"{cleaned_target} Manager")
        if not has_seniority:
            add(f"Assistant {cleaned_target}", f"Junior {cleaned_target}")
        if not has_terminal:
            add(f"{cleaned_target} Executive", f"{cleaned_target} Specialist", f"{cleaned_target} Consultant", f"{cleaned_target} Analyst")

    families = _lead_primary_role_families(cleaned_target, cv_text, candidate_context, industries)

    family_titles = {
        "hr": [
            "HR Executive", "Human Resources Executive", "HR Specialist", "HR Generalist", "HR Manager",
            "Senior HR Manager", "HR Business Partner", "People Partner", "People & Culture Manager",
            "Talent Acquisition Specialist", "Talent Acquisition Partner", "Talent Acquisition Manager", "Recruiter",
            "Employee Relations Specialist", "Compensation and Benefits Specialist", "Learning and Development Specialist",
            "HR Operations Specialist", "Payroll Specialist", "HR Shared Services Specialist"
        ],
        "operations": [
            "Operations Executive", "Operations Specialist", "Operations Analyst", "Operations Manager", "Head of Operations",
            "Business Operations Manager", "Process Improvement Specialist", "Supply Chain Executive", "Supply Chain Analyst",
            "Supply Chain Manager", "Logistics Executive", "Logistics Manager", "Warehouse Manager", "Procurement Executive",
            "Procurement Specialist", "Production Supervisor", "Production Manager", "Manufacturing Engineer", "Plant Manager",
            "Quality Executive", "QA Executive", "QC Executive", "Customer Service Executive", "Customer Service Manager"
        ],
        "finance": [
            "Finance Executive", "Finance Analyst", "Finance Manager", "Head of Finance", "Accountant", "Senior Accountant",
            "Accounting Manager", "Accounts Executive", "Accounts Payable Specialist", "Accounts Receivable Specialist",
            "Record to Report Analyst", "Order to Cash Analyst", "Procure to Pay Analyst", "FP&A Analyst", "FP&A Manager",
            "Financial Analyst", "Financial Controller", "Treasury Analyst", "Treasury Manager", "Tax Executive", "Tax Manager",
            "Audit Executive", "Internal Auditor", "Shared Services Analyst", "Finance Operations Specialist"
        ],
        "marketing": [
            "Marketing Executive", "Marketing Specialist", "Marketing Manager", "Brand Executive", "Brand Manager",
            "Digital Marketing Executive", "Digital Marketing Specialist", "Digital Marketing Manager", "Performance Marketing Specialist",
            "Performance Marketing Manager", "Growth Marketer", "Growth Manager", "SEO Specialist", "SEM Specialist",
            "Content Marketing Specialist", "Social Media Executive", "Social Media Manager", "Communications Executive",
            "Communications Manager", "PR Executive", "CRM Executive", "Campaign Manager", "Ecommerce Executive", "Trade Marketing Executive"
        ],
        "sales": [
            "Sales Executive", "Sales Representative", "Sales Consultant", "Sales Manager", "Business Development Executive",
            "Business Development Manager", "Account Executive", "Account Manager", "Key Account Executive", "Key Account Manager",
            "Commercial Executive", "Commercial Manager", "Partnerships Manager", "Channel Sales Manager", "Customer Success Executive",
            "Customer Success Manager", "Pre-Sales Consultant"
        ],
        "legal_risk": [
            "Legal Executive", "Legal Counsel", "Legal Manager", "Contracts Specialist", "Compliance Executive", "Compliance Analyst",
            "Compliance Manager", "Regulatory Compliance Specialist", "Risk Analyst", "Risk Manager", "Governance Specialist",
            "AML Analyst", "KYC Analyst", "Data Protection Officer", "Privacy Specialist"
        ],
        "admin": [
            "Admin Executive", "Administrative Assistant", "Administration Manager", "Office Manager", "Business Support Executive",
            "Business Support Manager", "Executive Assistant", "Personal Assistant", "Secretary", "Receptionist", "Facilities Executive"
        ],
        "product_design": [
            "Product Executive", "Product Analyst", "Product Manager", "Senior Product Manager", "Product Owner", "Product Lead",
            "Business Analyst", "UX Designer", "UI Designer", "Product Designer", "UX Researcher", "Service Designer",
            "Customer Experience Executive", "Customer Experience Manager", "CX Manager"
        ],
        "oil_gas": [
            "Oil and Gas Engineer", "Process Engineer", "Project Engineer", "Maintenance Engineer", "Mechanical Engineer",
            "Electrical Engineer", "Instrumentation Engineer", "HSE Executive", "HSE Manager", "Offshore Engineer", "Marine Engineer",
            "EPC Project Manager", "Turnaround Planner", "Reliability Engineer", "Rotating Equipment Engineer", "Static Equipment Engineer"
        ],
        "consulting_project": [
            "Consultant", "Senior Consultant", "Management Consultant", "Strategy Consultant", "Business Consultant",
            "Advisory Consultant", "Transformation Consultant", "Change Management Consultant", "Business Analyst", "Senior Business Analyst",
            "PMO Analyst", "PMO Consultant", "Project Consultant", "Implementation Consultant", "Project Manager", "Programme Manager"
        ],
        "sap_erp": [
            "SAP FICO Consultant", "SAP Consultant", "SAP Functional Consultant", "SAP Solution Architect", "SAP Finance Lead",
            "SAP MM Consultant", "SAP SD Consultant", "SAP ABAP Developer", "S/4HANA Consultant", "ERP Consultant",
            "ERP Business Analyst", "Enterprise Applications Consultant", "Business Applications Analyst", "Oracle Consultant", "Workday Consultant"
        ],
        "data": [
            "Data Engineer", "Senior Data Engineer", "Lead Data Engineer", "Data Platform Engineer", "Data Architect",
            "ETL Developer", "Data Warehouse Engineer", "Analytics Engineer", "Data Analyst", "Senior Data Analyst",
            "Business Intelligence Analyst", "BI Developer", "Data Scientist", "Machine Learning Engineer", "MLOps Engineer", "AI Engineer",
            "Data Governance Analyst"
        ],
        "software_tech": [
            "Software Engineer", "Software Developer", "Backend Developer", "Frontend Developer", "Full Stack Developer", "Mobile Developer",
            "QA Engineer", "Test Engineer", "Solution Architect", "Technical Architect", "Cloud Engineer", "DevOps Engineer",
            "SRE Engineer", "Platform Engineer", "Infrastructure Engineer", "Cybersecurity Analyst", "Application Support Analyst",
            "Production Support Analyst", "IT Project Manager", "Technical Project Manager", "EUC Engineer", "Desktop Support Engineer"
        ],
        "database_dba": [
            "Database Administrator", "Senior Database Administrator", "Oracle DBA", "Oracle RAC DBA", "Exadata DBA",
            "MySQL DBA", "SQL Server DBA", "PostgreSQL DBA", "MongoDB DBA", "DB2 DBA", "Database Engineer",
            "Database Architect", "Database Reliability Engineer", "Lead Database Administrator", "Database Team Lead",
            "Database Consultant", "Data Guard Administrator", "Database Operations Engineer"
        ],
    }
    for fam in families:
        add(*family_titles.get(fam, []))

    # Fresh-grad signals are level modifiers, not a separate function. Add only a
    # few safe variants after the primary family has been established.
    cv_blob = " ".join([str(target_role or ""), str(candidate_context or ""), str(cv_text or "")[:2500]]).lower()
    if _lead_has_any(cv_blob, ["fresh graduate", "graduate trainee", "management trainee", "entry level", "internship"]):
        add("Graduate Trainee", "Management Trainee", "Junior Executive", "Junior Specialist", "Entry Level")

    # Last-resort fallback if the role family is genuinely unknown.
    if not titles:
        add("Executive", "Senior Executive", "Specialist", "Analyst", "Associate", "Consultant", "Manager")
    return titles[:40]


_LEAD_FAMILY_BOOST_TOKENS = {
    "data": ("python", "sql", "spark", "pyspark", "databricks", "snowflake", "airflow", "dbt"),
    "finance": ("ifrs", "audit", "tax", "treasury", "fp&a"),
    "software_tech": ("java", "javascript", "react", "node", ".net", "kubernetes", "aws", "azure", "gcp"),
    "database_dba": ("rac", "exadata", "rman", "asm", "data guard", "dataguard", "goldengate", "golden gate",
                      "pl/sql", "plsql", "t-sql", "tsql", "tablespace", "oem", "toad"),
}


def _lead_cv_evidence_tokens(family, text):
    """Extract the literal phrases/tokens that justify `family` for this text.

    This is deliberately based on the CV's actual described work (tools,
    technologies, functional evidence phrases) rather than any job title
    string, so the cache groups candidates by what they actually do.
    """
    text_l = re.sub(r"\s+", " ", str(text or "").lower())
    tokens = set()
    for pat in _LEAD_FAMILY_PATTERNS.get(family, []):
        for m in re.finditer(pat, text_l, flags=re.I):
            tokens.add(m.group(0).strip())
    for tok in _LEAD_FAMILY_BOOST_TOKENS.get(family, ()):
        if re.search(r"(?<![a-z0-9])" + re.escape(tok) + r"(?![a-z0-9])", text_l):
            tokens.add(tok)
    return tokens


def _lead_cv_content_signature(target_role, cv_text, candidate_context, industries):
    """Build a (family, evidence_tokens) signature from actual CV content.

    Intentionally NOT based on the typed target_role text alone or the CV's
    job-title line — a 'System Analyst' whose CV describes Spark/Airflow/ETL
    work should get the same signature as a candidate titled 'Data Engineer'
    doing the same work, and a different signature from a 'System Analyst'
    doing helpdesk/support work. Returns None when no family/evidence is
    confidently detected (novel/niche roles fall through to a fresh AI call
    every time rather than risk a bad cache match).
    """
    families = _lead_primary_role_families(target_role, cv_text, candidate_context, industries)
    if not families:
        return None
    family = families[0]
    blob = " ".join([
        str(target_role or ""), str(candidate_context or "")[:1200],
        str(cv_text or "")[:6000], str(industries or ""),
    ])
    evidence = _lead_cv_evidence_tokens(family, blob)
    if not evidence:
        return None
    return family, evidence


def _lead_role_specific_title_bank(target_role, role_terms, cv_text=""):
    """Generate deterministic role-specific hiring-manager title angles.

    The generic HR title bank is useful, but functional hiring managers vary by
    role. This helper gives the people-search prompt more role-specific search
    angles without guessing actual people.
    """
    blob = " ".join([str(target_role or ""), " ".join(str(x or "") for x in (role_terms or [])), str(cv_text or "")[:3000]]).lower()
    titles = []

    def add(*items):
        for item in items:
            item = str(item or "").strip()
            if item and item.lower() not in {t.lower() for t in titles}:
                titles.append(item)

    # Always useful functional owner patterns. Keep this cross-functional because
    # Hyppies recruits for tech, HR, finance, ops, marketing, commercial and
    # general corporate roles.
    add(
        "Hiring Manager", "Line Manager", "Reporting Manager", "Team Lead", "Functional Lead",
        "Senior Manager", "Associate Director", "Director", "Department Head", "Head of", "VP", "General Manager"
    )

    if _lead_has_any(blob, ["sap", "fico", "s/4", "s4hana", "hana", "erp", "abap", "successfactors", "ariba", "mm", "sd"]):
        add(
            "Head of SAP", "SAP Manager", "SAP FICO Manager", "SAP Finance Lead", "SAP Functional Lead",
            "SAP Solution Architect", "SAP Architect", "ERP Manager", "ERP Applications Manager",
            "Enterprise Applications Manager", "Business Applications Manager", "IT Applications Manager",
            "Finance Systems Manager", "S/4HANA Programme Manager", "SAP Delivery Manager", "SAP Practice Lead"
        )
    if _lead_has_any(blob, ["data engineer", "data engineering", "etl", "elt", "spark", "databricks", "snowflake", "bigquery", "redshift", "data platform", "lakehouse", "airflow"]):
        add(
            "Head of Data", "Head of Data Engineering", "Data Engineering Manager", "Data Platform Manager",
            "Director of Data Engineering", "Director of Data Analytics", "Analytics Engineering Manager",
            "Data Architect", "Data Platform Lead", "BI Manager", "Data Warehouse Manager",
            "Chief Data Officer", "VP Data", "Data & Analytics Lead"
        )
    if _lead_has_any(blob, ["machine learning", "ml engineer", "mlops", "ai", "genai", "llm", "rag", "computer vision", "nlp", "data scientist"]):
        add(
            "Head of AI", "Head of Machine Learning", "AI/ML Manager", "MLOps Lead", "Data Science Manager",
            "Director of AI", "AI Engineering Manager", "Machine Learning Engineering Manager", "Chief AI Officer",
            "Applied AI Lead", "GenAI Lead", "Analytics Director"
        )
    if _lead_has_any(blob, ["software engineer", "developer", "java", ".net", "frontend", "backend", "full stack", "mobile", "react", "node", "spring"]):
        add(
            "Engineering Manager", "Software Engineering Manager", "Development Manager", "Head of Engineering",
            "Application Development Manager", "Technical Architect", "Solution Architect", "Delivery Manager",
            "CTO", "VP Engineering", "Software Development Lead"
        )
    if _lead_has_any(blob, ["cloud", "devops", "sre", "site reliability", "platform", "kubernetes", "terraform", "aws", "azure", "gcp", "infrastructure"]):
        add(
            "Head of Cloud", "Cloud Engineering Manager", "Platform Engineering Manager", "DevOps Manager",
            "SRE Manager", "Infrastructure Manager", "Head of Infrastructure", "Cloud Architect",
            "Platform Lead", "Technology Operations Manager", "IT Operations Manager"
        )
    if _lead_has_any(blob, ["database administrator", "dba", "oracle dba", "oracle rac", "exadata", "mysql dba", "sql server dba", "postgresql dba", "postgres dba", "mongodb dba", "db2 dba", "database engineer", "database architect", "data guard", "golden gate"]):
        add(
            "Head of Database", "Database Manager", "Database Team Lead", "Head of Infrastructure",
            "Infrastructure Manager", "Head of DBA", "Database Operations Manager", "IT Infrastructure Manager",
            "Head of IT Operations", "Database Architect", "Technology Operations Manager", "Head of Systems"
        )
    if _lead_has_any(blob, ["application support", "production support", "l2", "l3", "incident", "service delivery", "control-m", "geneos", "itil", "trading support"]):
        add(
            "Application Support Manager", "Production Support Manager", "Support Lead", "Service Delivery Manager",
            "Incident Manager", "Technology Operations Manager", "IT Operations Manager", "Run The Bank Lead",
            "Trading Support Manager", "Operations Lead", "Application Manager"
        )
    if _lead_has_any(blob, ["project manager", "programme", "program manager", "pmo", "transformation", "business analyst", "ba", "product owner", "scrum"]):
        add(
            "Programme Manager", "Program Director", "Project Director", "PMO Lead", "Head of Transformation",
            "Transformation Lead", "Delivery Director", "Business Change Manager", "Product Lead",
            "Product Owner Lead", "Agile Delivery Lead", "Business Analysis Manager"
        )
    if _lead_has_any(blob, ["payments", "swift", "rentas", "iso20022", "core banking", "banking", "cards", "fintech", "rpp", "fpx"]):
        add(
            "Head of Payments", "Payments Technology Lead", "Core Banking Lead", "Banking Applications Manager",
            "Payments Product Manager", "Transaction Banking Technology Manager", "Digital Banking Lead",
            "Financial Services Technology Director", "Banking Transformation Lead"
        )
    if _lead_has_any(blob, ["risk", "compliance", "audit", "governance", "credit risk", "basel", "ifrs9", "aml", "privacy", "pdpa", "security"]):
        add(
            "Head of Risk", "Risk Manager", "Credit Risk Manager", "Compliance Manager", "Head of Compliance",
            "Audit Manager", "Governance Manager", "Information Security Manager", "CISO", "Data Protection Officer",
            "Privacy Manager", "Operational Risk Manager"
        )
    if _lead_has_any(blob, ["finance", "accounting", "fp&a", "controller", "treasury", "tax", "audit", "shared service", "ssc"]):
        add(
            "Finance Manager", "Finance Controller", "Head of Finance", "FP&A Manager", "Treasury Manager",
            "Shared Services Manager", "Finance Transformation Lead", "Record-to-Report Manager", "Order-to-Cash Manager"
        )
    if _lead_has_any(blob, ["sales", "business development", "account manager", "customer success", "marketing", "growth", "commercial"]):
        add(
            "Sales Manager", "Business Development Manager", "Commercial Director", "Head of Sales",
            "Customer Success Manager", "Marketing Manager", "Growth Lead", "Revenue Operations Manager"
        )
    if _lead_has_any(blob, ["hr", "human resources", "talent", "recruiter", "people"]):
        add(
            "Head of HR", "HR Manager", "Talent Acquisition Manager", "People Partner", "HR Business Partner",
            "Head of People", "Recruitment Lead", "Talent Lead"
        )

    if _lead_has_any(blob, ["operations", "operation manager", "ops", "supply chain", "logistics", "warehouse", "fulfillment", "procurement", "purchasing", "production", "manufacturing", "plant", "factory", "quality", "qa", "qc", "continuous improvement", "lean", "six sigma", "customer service", "contact centre", "call center"]):
        add(
            "Head of Operations", "Operations Manager", "Senior Operations Manager", "Operations Director", "COO",
            "General Manager Operations", "Site Manager", "Plant Manager", "Manufacturing Manager", "Production Manager",
            "Supply Chain Manager", "Head of Supply Chain", "Logistics Manager", "Warehouse Manager", "Fulfillment Manager",
            "Procurement Manager", "Purchasing Manager", "Quality Manager", "Continuous Improvement Manager",
            "Customer Service Manager", "Contact Centre Manager"
        )
    if _lead_has_any(blob, ["marketing", "brand", "digital marketing", "performance marketing", "growth", "seo", "sem", "content", "social media", "communications", "pr", "crm", "campaign", "ecommerce", "e-commerce", "trade marketing", "market research"]):
        add(
            "Marketing Manager", "Senior Marketing Manager", "Head of Marketing", "Marketing Director", "CMO",
            "Brand Manager", "Senior Brand Manager", "Digital Marketing Manager", "Performance Marketing Manager",
            "Growth Manager", "Growth Lead", "Content Marketing Manager", "Social Media Manager", "Communications Manager",
            "PR Manager", "CRM Manager", "Campaign Manager", "Ecommerce Manager", "Trade Marketing Manager",
            "Market Research Manager"
        )
    if _lead_has_any(blob, ["sales", "business development", "bd", "account manager", "key account", "commercial", "partnership", "channel", "retail", "customer success", "client success", "revenue", "presales", "pre-sales"]):
        add(
            "Sales Manager", "Senior Sales Manager", "Head of Sales", "Sales Director", "Commercial Manager",
            "Commercial Director", "Business Development Manager", "Head of Business Development", "Key Account Manager",
            "Strategic Account Manager", "Partnerships Manager", "Channel Manager", "Retail Manager", "Country Manager",
            "Customer Success Manager", "Head of Customer Success", "Revenue Operations Manager", "Pre-Sales Manager"
        )
    if _lead_has_any(blob, ["hr", "human resources", "people", "talent", "employee relations", "compensation", "benefits", "c&b", "learning", "l&d", "organizational development", "od", "hr operations", "payroll", "recruitment", "talent acquisition"]):
        add(
            "Head of HR", "HR Director", "HR Manager", "Senior HR Manager", "HR Business Partner", "Senior HR Business Partner",
            "People Partner", "People & Culture Manager", "Head of People", "Talent Acquisition Manager", "Head of Talent Acquisition",
            "Recruitment Lead", "Talent Lead", "Employee Relations Manager", "Compensation and Benefits Manager", "C&B Manager",
            "Learning and Development Manager", "L&D Manager", "Organizational Development Manager", "HR Operations Manager",
            "Payroll Manager"
        )
    if _lead_has_any(blob, ["finance", "accounting", "accounts", "fp&a", "financial planning", "controller", "treasury", "tax", "ap", "ar", "r2r", "record to report", "order to cash", "otc", "procure to pay", "p2p", "shared service", "ssc", "audit"]):
        add(
            "Finance Manager", "Senior Finance Manager", "Head of Finance", "Finance Director", "CFO", "Financial Controller",
            "Group Financial Controller", "FP&A Manager", "Financial Planning and Analysis Manager", "Treasury Manager",
            "Tax Manager", "Accounting Manager", "Accounts Payable Manager", "Accounts Receivable Manager",
            "Record-to-Report Manager", "Order-to-Cash Manager", "Procure-to-Pay Manager", "Shared Services Manager",
            "Finance Operations Manager", "Finance Transformation Lead", "Audit Manager"
        )
    if _lead_has_any(blob, ["legal", "lawyer", "counsel", "contract", "corporate secretarial", "company secretary", "compliance", "regulatory", "privacy", "pdpa", "risk", "governance", "aml", "kyc"]):
        add(
            "Head of Legal", "Legal Director", "Legal Manager", "Legal Counsel", "Senior Legal Counsel", "General Counsel",
            "Contracts Manager", "Company Secretary", "Corporate Secretarial Manager", "Compliance Manager", "Head of Compliance",
            "Regulatory Compliance Manager", "Risk Manager", "Operational Risk Manager", "Governance Manager", "AML Manager", "KYC Manager",
            "Data Protection Officer", "Privacy Manager"
        )
    if _lead_has_any(blob, ["admin", "administration", "office manager", "secretary", "personal assistant", "pa", "executive assistant", "ea", "business support", "reception", "facilities"]):
        add(
            "Administration Manager", "Admin Manager", "Office Manager", "Business Support Manager", "Facilities Manager",
            "Executive Assistant Manager", "Corporate Services Manager", "Head of Administration", "Office Operations Manager"
        )
    if _lead_has_any(blob, ["product", "product manager", "product owner", "ux", "ui", "designer", "researcher", "service design", "customer experience", "cx"]):
        add(
            "Product Manager", "Senior Product Manager", "Group Product Manager", "Head of Product", "Product Director",
            "Product Owner Lead", "UX Manager", "Design Manager", "Head of Design", "UX Research Manager",
            "Customer Experience Manager", "CX Manager", "Service Design Lead"
        )

    return titles[:60]


def _lead_filter_by_regions(parsed, regions):
    """Post-filter model output so selected regions are treated as hard filters."""
    if not isinstance(parsed, dict) or _lead_has_apac(regions):
        return parsed, ""
    companies = parsed.get("companies") if isinstance(parsed.get("companies"), list) else []
    people = parsed.get("people") if isinstance(parsed.get("people"), list) else []
    kept_companies = [c for c in companies if _lead_location_allowed(c, regions)]
    kept_names = {str(c.get("company") or "").strip().lower() for c in kept_companies if isinstance(c, dict) and c.get("company")}
    kept_people = []
    for p in people:
        if not isinstance(p, dict):
            continue
        pc = str(p.get("company") or "").strip().lower()
        company_ok = (not kept_names) or (pc in kept_names)
        if not company_ok:
            continue
        # People are derived from the already-filtered job leads. Keep people
        # with explicit matching location, and also keep company-matched people
        # when no separate person-level location was available. Drop them only
        # when person-level evidence clearly points outside the selected region.
        person_location_blob = " ".join(str(p.get(k) or "") for k in ("country", "region", "location")).strip()
        if _lead_location_allowed(p, regions) or (pc in kept_names and not person_location_blob):
            kept_people.append(p)
    removed_companies = max(0, len(companies) - len(kept_companies))
    removed_people = max(0, len(people) - len(kept_people))
    parsed["companies"] = kept_companies
    parsed["people"] = kept_people
    if removed_companies or removed_people:
        regions_txt = ", ".join(str(r) for r in regions)
        return parsed, f"Location filter applied: removed {removed_companies} job lead(s) and {removed_people} people lead(s) outside selected region(s): {regions_txt}. Remote leads are kept only when they clearly accept candidates based in the selected country/region."
    return parsed, ""


def _lead_filter_people_by_input_companies(people, companies):
    """People discovery is downstream of already location-filtered job leads.

    Do not apply person-level country filtering here: a regional recruiter or
    hiring manager may sit in Singapore/Hong Kong/etc. while owning a Malaysia
    or APAC role. Instead, keep people tied to the selected input companies and
    drop only obvious off-company/no-name noise.
    """
    if not isinstance(people, list):
        return [], ""
    companies = companies if isinstance(companies, list) else []
    company_names = [str(c.get("company") or "").strip() for c in companies if isinstance(c, dict) and str(c.get("company") or "").strip()]
    kept = []
    for p in people:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "").strip()
        title = str(p.get("title") or "").strip()
        pc = str(p.get("company") or "").strip()
        if not name or not title:
            continue
        if company_names and pc:
            if not any(_lead_company_names_match(pc, c) for c in company_names):
                continue
        elif company_names and not pc:
            # Keep only if public evidence/notes mention one of the target companies.
            blob = " ".join(str(p.get(k) or "") for k in ("profile_url", "source_url", "notes", "title")).lower()
            if not any(_lead_norm_company_name(c) and _lead_norm_company_name(c) in _lead_norm_company_name(blob) for c in company_names):
                continue
        kept.append(p)
    removed = max(0, len(people) - len(kept))
    if removed:
        return kept, f"People filter applied: removed {removed} off-company/low-evidence contact(s). Person location was not used as a filter because regional HR/hiring managers can own selected-country roles."
    return kept, ""


def _lead_int_0_100(value, default=0):
    try:
        n = int(round(float(str(value).replace('%', '').strip())))
    except Exception:
        n = default
    if n < 0:
        n = 0
    if n > 100:
        n = 100
    return n


def _lead_parse_posted_date(value, today=None):
    """Best-effort parse of portal date/relative freshness text.

    Returns (date_posted_iso, days_open) where values may be empty/None.
    This keeps Lead Finder useful even when portals return relative strings such as
    "3 days ago" or "Posted today" instead of a fixed date.
    """
    today = today or date.today()
    raw = str(value or '').strip()
    if not raw:
        return '', None
    s = raw.lower()
    if s in {'unknown', 'n/a', 'na', 'not available', 'not visible', 'not shown', 'unspecified', 'none', '-'}:
        return '', None
    # ISO or common yyyy/mm/dd / yyyy.mm.dd
    m = re.search(r'(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})', s)
    if m:
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return d.isoformat(), max(0, (today - d).days)
        except Exception:
            pass
    # dd/mm/yyyy, dd-mm-yyyy, dd.mm.yyyy. Ambiguous but common in job portals.
    m = re.search(r'\b(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})\b', s)
    if m:
        try:
            d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            return d.isoformat(), max(0, (today - d).days)
        except Exception:
            pass
    if any(x in s for x in ['today', 'just posted', 'few hours', 'hour ago', 'hours ago', 'moments ago']) or re.search(r'\bnew\b', s):
        return today.isoformat(), 0
    if 'yesterday' in s:
        d = today - timedelta(days=1)
        return d.isoformat(), 1
    m = re.search(r'(\d+)\s*(day|days|d)\s*ago', s)
    if m:
        days = int(m.group(1))
        d = today - timedelta(days=days)
        return d.isoformat(), days
    m = re.search(r'(\d+)\s*(week|weeks|w)\s*ago', s)
    if m:
        days = int(m.group(1)) * 7
        d = today - timedelta(days=days)
        return d.isoformat(), days
    m = re.search(r'(\d+)\s*(month|months|mo)\s*ago', s)
    if m:
        days = int(m.group(1)) * 30
        d = today - timedelta(days=days)
        return d.isoformat(), days
    return raw, None


def _lead_freshness_label(days_open):
    try:
        d = int(days_open)
    except Exception:
        return 'Unknown'
    if d <= 0:
        return 'Today'
    if d <= 7:
        return f'{d} day(s) open'
    if d <= 14:
        return '8-14 days open'
    if d <= 30:
        return '15-30 days open'
    return '30+ days open'


def _lead_best_verification_url(original_job, company, role):
    """Given a non-direct job URL, return the most useful link for a recruiter
    to manually verify the lead. A generic portal category page gets swapped
    for a constructed search combining the employer + role + site, since the
    original page cannot confirm that employer is actually hiring for that role.
    """
    original_job = str(original_job or "").strip()
    if not original_job:
        return "", ""
    if not _lead_is_generic_portal_category_url(original_job, company):
        return original_job, ""
    try:
        host = urllib.parse.urlparse(original_job).netloc
    except Exception:
        host = ""
    company = _lead_verification_company_text(company)
    role = re.sub(r"\s+", " ", str(role or "")).strip()
    q_parts = [f'"{company}"'] if company else []
    q_parts += [f'"{role}"'] if role else []
    q_parts += [f"site:{host}"] if host else []
    if not q_parts:
        return original_job, ""
    search_url = "https://www.google.com/search?q=" + urllib.parse.quote(" ".join(q_parts))
    note = "The portal only returned a generic title-search page (not specific to this employer); replaced with a targeted search combining the employer, role, and portal so it can actually be verified."
    return search_url, note


def _lead_normalize_company_urls(c):
    """Prefer direct job-ad links. Move portal/search/list pages into source_url so the UI doesn't label them as Open Job."""
    if not isinstance(c, dict):
        return c
    candidates = [c.get("job_url"), c.get("source_url"), c.get("company_url")]
    direct = ""
    original_job = str(c.get("job_url") or "").strip()
    original_source = str(c.get("source_url") or "").strip()
    quality_raw = str(c.get("job_url_quality") or "").strip()
    if quality_raw == "needs_verification":
        # If the source itself is only a generic portal category page, replace it
        # with a targeted employer+role verification search. Do not keep raw
        # JobStreet/LinkedIn title-category URLs as if they verify the lead.
        verify_input = original_job or original_source
        if verify_input:
            best_url, gen_note = _lead_best_verification_url(verify_input, c.get("company"), c.get("matched_role") or c.get("title"))
            if best_url:
                c["source_url"] = best_url
            if gen_note:
                existing_note = str(c.get("source_note") or "").strip()
                c["source_note"] = (existing_note + " " + gen_note).strip() if existing_note and gen_note not in existing_note else (existing_note or gen_note)
        c["job_url"] = ""
        c["job_url_quality"] = "needs_verification"
        return c
    structured_ok = quality_raw == "structured_google_job" and re.match(r"^https?://", original_job, re.I) and not _lead_is_generic_portal_category_url(original_job, c.get("company"))
    if structured_ok:
        c["job_url"] = original_job
        c["job_url_quality"] = "structured_google_job"
        return c
    if quality_raw == "structured_google_job" and original_job and _lead_is_generic_portal_category_url(original_job, c.get("company")):
        best_url, gen_note = _lead_best_verification_url(original_job, c.get("company"), c.get("matched_role") or c.get("title"))
        c["source_url"] = best_url or original_job
        c["job_url"] = ""
        c["job_url_quality"] = "needs_verification"
        note = str(c.get("source_note") or "").strip()
        msg = "Structured Google Jobs returned only a generic/search URL, not a direct job-post permalink; verify before outreach."
        if gen_note:
            msg += " " + gen_note
        c["source_note"] = (note + " " + msg).strip() if note and msg not in note else (note or msg)
        return c
    for u in candidates:
        if _lead_is_direct_job_url(u):
            direct = str(u).strip()
            break
    if direct:
        c["job_url"] = _lead_canonical_direct_job_url(direct)
        c["job_url_quality"] = "direct_job_ad"
    else:
        # No usable direct job-ad URL was found. Do not keep known JobStreet/JobsDB
        # non-job control/editorial URLs (sign-in/account/applied/saved/company
        # profile/career-advice pages) as the clickable source just because they
        # carry a redirected jobId query parameter. Replace those with the same
        # targeted employer+role+portal verification search used for generic
        # title-category pages. Preserve non-generic source URLs when they are
        # genuinely useful source pages.
        replacement_input = ""
        if original_source and _lead_is_generic_portal_category_url(original_source, c.get("company")):
            replacement_input = original_source
        elif original_job and _lead_is_generic_portal_category_url(original_job, c.get("company")):
            replacement_input = original_job
        elif original_job and not original_source:
            replacement_input = original_job

        if replacement_input:
            best_url, gen_note = _lead_best_verification_url(replacement_input, c.get("company"), c.get("matched_role") or c.get("title"))
            if best_url:
                c["source_url"] = best_url
            if gen_note:
                existing_note = str(c.get("source_note") or "").strip()
                c["source_note"] = (existing_note + " " + gen_note).strip() if existing_note and gen_note not in existing_note else (existing_note or gen_note)
        c["job_url"] = ""
        c["job_url_quality"] = "source_or_search_result_only"
        if original_job:
            note = str(c.get("source_note") or "").strip()
            msg = "Direct job-ad URL was not available; kept the portal/search/company source separately."
            c["source_note"] = (note + " " + msg).strip() if note and msg not in note else (note or msg)
    return c


def _lead_guess_title_company_from_context(context, url, job_title_angles=None):
    """Best-effort extraction for non-JSON AI output.

    This is intentionally conservative: it only runs after the model already
    spent a live-search call but failed JSON formatting. Earlier Lead Finder
    versions often returned useful job URLs in prose/markdown, so this recovers
    those direct job-post URLs instead of throwing paid output away as 0 leads.
    """
    context = re.sub(r"\s+", " ", str(context or " ")).strip()
    portal_words = r"(?:LinkedIn|JobStreet|JobsDB|Indeed|Glassdoor|Hiredly|Foundit|Monster|Google Jobs|Careers?|Jobs?)"
    clean = re.sub(r"https?://\S+", " ", context)
    clean = re.sub(r"^(?:\s*(?:[-*•]|\d+[.)])\s*)+", "", clean)
    clean = re.sub(r"^(?:here are|useful leads?|job leads?|lead list)[^:]{0,60}:", "", clean, flags=re.I)
    clean = re.sub(r"\b(?:Apply|View|Open|Source|URL|Job URL|job_url|source_url)\b[:\-]*", " ", clean, flags=re.I)
    clean = re.sub(r"\s+", " ", clean).strip(" -|•*;,.\t")

    title = ""
    company = ""
    # Prefer common job-title separators.
    pieces = [x.strip(" -|•*;,.\t") for x in re.split(r"\s+(?:at|@)\s+|\s+[–—-]\s+|\s+\|\s+", clean, maxsplit=2, flags=re.I) if x.strip()]
    role_terms = job_title_angles or []
    def looks_role(x):
        x_l = x.lower()
        if any(str(t or "").lower() in x_l or x_l in str(t or "").lower() for t in role_terms):
            return True
        return bool(re.search(r"\b(engineer|developer|analyst|manager|executive|specialist|consultant|architect|lead|head|director|associate|officer|administrator|designer|accountant|recruiter|partner|scientist|technician|coordinator|planner|controller)\b", x_l))

    if len(pieces) >= 2:
        a, b = pieces[0], pieces[1]
        if looks_role(a) and not re.search(portal_words, b, re.I):
            title, company = a, b
        elif looks_role(b) and not re.search(portal_words, a, re.I):
            title, company = b, a
    if not title:
        # Try to find a role angle directly in the surrounding text.
        for angle in role_terms or []:
            a = str(angle or "").strip()
            if a and re.search(r"\b" + re.escape(a) + r"\b", clean, re.I):
                title = a
                break
    if not title:
        # Last resort: take the leading phrase before portal/company clutter.
        m = re.search(r"\b((?:Senior|Lead|Principal|Junior|Associate|Assistant|Head of|Director of|VP of|Vice President of)?\s*[A-Z][A-Za-z0-9/&+ .]{3,80}?(?:Engineer|Developer|Analyst|Manager|Executive|Specialist|Consultant|Architect|Lead|Director|Officer|Accountant|Recruiter|Scientist|Coordinator|Administrator))\b", clean)
        if m:
            title = m.group(1).strip()
    if not company:
        # Company is frequently after title separators; otherwise infer from host.
        host = urllib.parse.urlparse(str(url or "")).netloc.lower()
        host_company = re.sub(r"^(www\.|careers\.|jobs\.|apply\.)", "", host).split(".")[0]
        if host_company and host_company not in {"linkedin", "jobstreet", "jobsdb", "indeed", "glassdoor", "hiredly", "mycareersfuture", "kalibrr", "foundit", "monster"}:
            company = host_company.replace("-", " ").title()
    if not company:
        company = "Company not shown"
    if not title:
        title = (role_terms[0] if role_terms else "Relevant open role")
    title = re.sub(portal_words + r"$", "", str(title), flags=re.I).strip(" -|•*;,.\t") or (role_terms[0] if role_terms else "Relevant open role")
    company = re.sub(portal_words + r"$", "", str(company), flags=re.I).strip(" -|•*;,.\t") or "Company not shown"
    return title[:120], company[:120]


def _lead_recover_job_leads_from_text(raw_text, regions, job_sources, job_title_angles, max_n=6):
    """Recover direct job-post leads from a non-JSON model answer.

    This prevents paid AI-web-search output from being wasted just because the
    model returned bullets/prose instead of strict JSON. It never creates leads
    from generic portal/search pages; direct job-post URL rules still apply.
    """
    raw_text = str(raw_text or "")
    if not raw_text.strip():
        return {"summary": {}, "companies": [], "people": []}, ""
    urls = []
    for m in re.finditer(r"https?://[^\s<>)\]\}\"']+", raw_text):
        u = m.group(0).rstrip(".,;:!?)]}")
        if _lead_is_direct_job_url(u):
            urls.append((u, m.start(), m.end()))
    seen = set()
    companies = []
    for u, start, end in urls:
        key = u.lower()
        if key in seen:
            continue
        seen.add(key)
        line_start = raw_text.rfind("\n", 0, start)
        line_start = 0 if line_start < 0 else line_start + 1
        line_end = raw_text.find("\n", end)
        line_end = len(raw_text) if line_end < 0 else line_end
        current_line = raw_text[line_start:line_end].strip()
        # If the URL is on a separate line from the title/company, include one
        # previous line; otherwise keep context to the current line so a lead
        # above does not contaminate title/company parsing for the next URL.
        context = current_line
        if len(re.sub(r"https?://\S+", "", current_line).strip()) < 8:
            prev_end = max(0, line_start - 1)
            prev_start = raw_text.rfind("\n", 0, prev_end)
            prev_start = 0 if prev_start < 0 else prev_start + 1
            prev_line = raw_text[prev_start:prev_end].strip()
            if prev_line and not re.search(r"https?://", prev_line):
                context = (prev_line + " " + current_line).strip()
        title, company = _lead_guess_title_company_from_context(context, u, job_title_angles)
        portal = _lead_url_portal(u)
        companies.append({
            "id": f"co_{len(companies)+1}",
            "company": company,
            "country": (regions or [""])[0] if regions else "",
            "region": "",
            "industry": "",
            "job_portal": portal if portal in (job_sources or []) or portal else portal,
            "matched_role": title,
            "hiring_signal": "Recovered direct job-post URL from AI live-search output.",
            "date_posted": "",
            "days_open": "",
            "job_freshness": "Unknown",
            "job_url": u,
            "job_url_quality": "direct_job_ad",
            "company_url": "",
            "job_fit_percent": 65,
            "match_score": 65,
            "why_matched": "Direct job-post URL recovered from the paid live-search response; review fit manually.",
            "source_url": u,
            "source_note": "Recovered from non-JSON AI output after live search returned usable direct job URL.",
            "date_found": date.today().isoformat(),
            "lead_kind": "extracted_job_lead",
        })
        if len(companies) >= int(max_n or 6):
            break
    out = {
        "summary": {
            "candidate_title": (job_title_angles or [""])[0] if job_title_angles else "",
            "target_roles": job_title_angles or [],
            "target_job_title_angles": job_title_angles or [],
            "regions": regions or [],
            "job_sources_used": job_sources or [],
            "source_strategy": "Recovered direct job-post URLs from non-JSON AI web-search output.",
            "job_fit_method": "Recovered leads are shown for recruiter review; fit score is conservative when snippet detail is limited.",
            "compliance_note": "Only public direct job-post URLs were recovered; generic portal/search links remain hidden."
        },
        "companies": companies,
        "people": []
    }
    if companies:
        return out, f"Recovered {len(companies)} direct job lead(s) from non-JSON AI output instead of returning 0."
    return out, ""


def _lead_reviewable_job_lead(c):
    """Return True for paid-search leads that are useful enough to show even when a direct permalink is missing.

    This intentionally does NOT resurrect generic fallback search links. It only
    keeps rows that contain a real-looking employer + role + public source URL,
    so a paid AI/provider call does not become literal 0 just because the portal
    exposed a listing/search URL rather than a direct job permalink.
    """
    if not isinstance(c, dict):
        return False
    if str(c.get("lead_kind") or "").lower() == "fallback_search_link":
        return False
    url = str(c.get("source_url") or c.get("company_url") or c.get("job_url") or "").strip()
    if not re.match(r"^https?://", url, re.I):
        return False
    if _lead_is_non_job_content_url(url):
        return False
    company = re.sub(r"\s+", " ", str(c.get("company") or "")).strip()
    role = re.sub(r"\s+", " ", str(c.get("matched_role") or c.get("title") or "")).strip()
    company_l = company.lower()
    role_l = role.lower()
    bad_companies = {
        "", "unknown", "unknown company", "company", "company not shown", "n/a", "na",
        "jobstreet", "jobstreet search", "linkedin", "linkedin jobs", "linkedin jobs public search results",
        "indeed", "indeed search", "glassdoor", "glassdoor search", "hiredly", "jobsdb", "monster", "foundit"
    }
    bad_roles = {"", "matched role", "relevant open role", "open role", "job", "jobs", "source/search", "search result"}
    if company_l in bad_companies or role_l in bad_roles:
        return False
    company_norm = re.sub(r"[^a-z0-9]+", " ", company_l).strip()
    role_norm = re.sub(r"[^a-z0-9]+", " ", role_l).strip()
    if company_norm in {"company not visible in search result", "company not visible", "not visible"}:
        return False
    # Reject cases where the guessed company is actually just the job title/listing
    # title, e.g. company='Senior Data Engineer' from
    # my.jobstreet.com/senior-data-engineer-jobs.
    if company_norm and role_norm and _lead_company_is_actually_role_text(company_norm, role_norm):
        return False
    # Reject obvious portal/search pseudo-companies.
    if re.search(r"\b(search|jobs? found|job listings?|public search results|jobs in|vacancies)\b", company_l):
        return False
    # Require at least one role-ish word so company news/source pages are not shown as job leads.
    if not re.search(r"\b(engineer|developer|analyst|manager|executive|specialist|consultant|architect|lead|head|director|associate|officer|administrator|designer|accountant|recruiter|partner|scientist|technician|coordinator|planner|controller|assistant|intern|trainee|operator|supervisor|representative|sales|marketing|finance|data|hr|human resources|operations|project|product|support)\b", role_l):
        return False
    return True


def _lead_keep_only_direct_job_leads(parsed):
    """Keep direct job leads, and downgrade useful non-direct leads to Needs Verification.

    Earlier v21.6x builds deleted every paid AI/provider lead whose URL was not a
    strict direct-job permalink. That was too harsh for JobStreet/LinkedIn/Google
    search because they often expose listing/source URLs while the paid response
    still contains employer + role evidence. We now keep those as reviewable job
    leads instead of silently returning 0, while still hiding generic fallback
    search links and source-only portal pages.
    """
    if not isinstance(parsed, dict):
        return parsed, ""
    companies = parsed.get("companies") or []
    if not isinstance(companies, list):
        parsed["companies"] = []
        return parsed, ""
    kept = []
    direct_count = 0
    review_count = 0
    removed = 0
    seen = set()
    for c in companies:
        if not isinstance(c, dict):
            removed += 1
            continue
        c = _lead_normalize_company_urls(c)
        structured_ok = str(c.get("job_url_quality") or "") == "structured_google_job" and re.match(r"^https?://", str(c.get("job_url") or ""), re.I) and not _lead_is_generic_portal_category_url(c.get("job_url"), c.get("company"))
        if _lead_is_direct_job_url(c.get("job_url")) or structured_ok:
            c["lead_kind"] = "extracted_job_lead"
            direct_count += 1
        elif _lead_reviewable_job_lead(c):
            c["lead_kind"] = "job_lead_needs_verification"
            c["job_url"] = ""
            c["job_url_quality"] = "needs_verification"
            note = str(c.get("source_note") or "").strip()
            msg = "Needs verification: no direct job-ad permalink was available, but the paid search output contained employer + role evidence. Review the source before people search/outreach."
            c["source_note"] = (note + " " + msg).strip() if note and msg not in note else (note or msg)
            review_count += 1
        else:
            removed += 1
            continue
        key = "|".join(str(c.get(k) or "").strip().lower() for k in ("company", "matched_role", "job_portal", "job_url", "source_url"))
        if key in seen:
            continue
        seen.add(key)
        kept.append(c)
    parsed["companies"] = kept
    notes = []
    if review_count:
        notes.append(f"Kept {review_count} paid-search job lead(s) as Needs Verification instead of discarding them for missing direct job permalinks.")
    if removed:
        notes.append(f"Hidden {removed} unusable generic/source-only result(s).")
    if notes:
        return parsed, " ".join(notes)
    return parsed, ""


def _lead_normalize_company_fit_freshness(parsed):
    if not isinstance(parsed, dict):
        return parsed
    companies = parsed.get('companies') or []
    if not isinstance(companies, list):
        parsed['companies'] = []
        return parsed
    today = date.today()
    for c in companies:
        if not isinstance(c, dict):
            continue
        _lead_normalize_company_urls(c)
        fit_raw = c.get('job_fit_percent', None)
        if fit_raw in (None, ''):
            fit_raw = c.get('match_score', None)
        if fit_raw in (None, ''):
            fit_raw = c.get('score', None)
        if fit_raw in (None, ''):
            q = str(c.get('job_url_quality') or '').lower()
            lk = str(c.get('lead_kind') or '').lower()
            fit_raw = 78 if q in {'direct_job_ad', 'structured_google_job'} or lk == 'extracted_job_lead' else 68
        fit = _lead_int_0_100(fit_raw)
        c['job_fit_percent'] = fit
        c['match_score'] = fit  # backwards-compatible alias used by existing UI/KPI
        posted_raw = c.get('date_posted') or c.get('posted_date') or c.get('posted') or c.get('job_posted') or ''
        iso, days = _lead_parse_posted_date(posted_raw, today=today)
        raw_days = None
        try:
            raw_days = int(c.get('days_open'))
        except Exception:
            raw_days = None
        if days is None and raw_days is not None:
            days = raw_days
        posted_clean = str(posted_raw or '').strip().lower()
        posted_is_unknown = posted_clean in {'unknown', 'n/a', 'na', 'not available', 'not visible', 'not shown', 'unspecified', 'none', '-'}
        if iso:
            c['date_posted'] = iso
        elif days is not None:
            c['date_posted'] = (today - timedelta(days=max(0, int(days)))).isoformat()
        elif posted_raw and not posted_is_unknown:
            c['date_posted'] = str(posted_raw).strip()
        else:
            c['date_posted'] = ''
        c['days_open'] = days if days is not None else ''
        freshness_raw = str(c.get('job_freshness') or '').strip()
        if (not freshness_raw) or freshness_raw.lower() == 'unknown':
            c['job_freshness'] = _lead_freshness_label(days)
        else:
            c['job_freshness'] = freshness_raw
    return parsed


def _lead_filter_by_title_angles(parsed, title_angles):
    if not isinstance(parsed, dict):
        return parsed, ''
    companies = parsed.get('companies') or []
    if not isinstance(companies, list):
        parsed['companies'] = []
        return parsed, ''
    kept, removed = [], 0
    for c in companies:
        if _lead_company_matches_title_angles(c, title_angles):
            kept.append(c)
        else:
            removed += 1
    parsed['companies'] = kept
    if removed:
        return parsed, f'Removed {removed} unrelated role-family lead(s) before display; low stack-fit leads within the right role family are still shown.'
    return parsed, ''


def _lead_apply_basic_job_filters(parsed, job_filters):
    """Apply safe hard filters only. Most relevance filters stay in the crawl prompt
    to avoid over-deleting sparse portal snippets.
    """
    if not job_filters or not isinstance(parsed, dict):
        return parsed, ""
    companies = parsed.get("companies") or []
    if not isinstance(companies, list):
        return parsed, ""
    excl = [x.lower() for x in _lead_clean_csv(job_filters.get("exclude_keywords"), 20)]
    company_excl = [x.lower() for x in _lead_clean_csv(job_filters.get("company_exclude"), 20)]
    max_days = job_filters.get("max_days_open")
    removed = 0
    kept = []
    for c in companies:
        blob = " ".join(str((c or {}).get(k, "")) for k in ("company","industry","matched_role","hiring_signal","why_matched","source_note","job_portal")).lower()
        if excl and any(x and x in blob for x in excl):
            removed += 1
            continue
        if company_excl and any(x and x in blob for x in company_excl):
            removed += 1
            continue
        if max_days and str((c or {}).get("days_open", "")).strip() != "":
            try:
                if float((c or {}).get("days_open")) > float(max_days):
                    removed += 1
                    continue
            except Exception:
                pass
        kept.append(c)
    parsed["companies"] = kept
    msg = f"Applied relevance filters and removed {removed} clear mismatch lead(s)." if removed else ""
    return parsed, msg


def _lead_portal_search_url(source, title, regions, job_filters=None):
    """Build a reviewable public portal search URL for fallback mode.

    These are not direct job ads. They are used only when live web search times
    out/unavailable, so the user still gets useful next-click search links
    instead of a misleading 0-lead result.
    """
    source_raw = str(source or "").strip() or "Public job portal"
    s = source_raw.lower()
    title = str(title or "").strip() or "jobs"
    location = ", ".join(str(r).strip() for r in (regions or []) if str(r).strip()) or ""
    filter_terms = _lead_filter_query_terms(job_filters or {})
    exclude_terms = _lead_exclude_query_terms(job_filters or {})
    query_base = " ".join(x for x in [title, filter_terms, exclude_terms] if x).strip()
    q = urllib.parse.quote_plus(query_base or title)
    loc = urllib.parse.quote_plus(location)
    q_with_loc = urllib.parse.quote_plus((query_base + " " + location).strip())
    first_region = (str((regions or [""])[0]).strip().lower() if regions else "")
    if "linkedin" in s:
        return f"https://www.linkedin.com/jobs/search/?keywords={q}&location={loc}"
    if "jobstreet" in s:
        if "singapore" in first_region or first_region == "sg":
            host = "www.jobstreet.com.sg"
        elif "indonesia" in first_region or first_region == "id":
            host = "id.jobstreet.com"
        elif "philippines" in first_region or first_region == "ph":
            host = "www.jobstreet.com.ph"
        else:
            host = "www.jobstreet.com.my"
        return f"https://{host}/jobs?keywords={q}"
    if "jobsdb" in s:
        return f"https://hk.jobsdb.com/jobs?keywords={q_with_loc}"
    if "indeed" in s:
        return f"https://www.indeed.com/jobs?q={q}&l={loc}"
    if "glassdoor" in s:
        return f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={q}&locT=&locId=&locKeyword={loc}"
    if "hiredly" in s:
        return f"https://my.hiredly.com/jobs?keyword={q}"
    if "mycareersfuture" in s:
        return f"https://www.mycareersfuture.gov.sg/search?search={q}"
    if "kalibrr" in s:
        return f"https://www.kalibrr.com/job-board/te/{q}"
    if "monster" in s or "foundit" in s:
        return f"https://www.foundit.my/srp/results?query={q_with_loc}"
    # Works for company career pages / other public portals without inventing a source-specific URL.
    return "https://www.google.com/search?q=" + urllib.parse.quote_plus(f'{source_raw} {query_base} {location} jobs')


def _lead_make_search_fallback_leads(job_sources, title_angles, regions, target_role="", max_n=8, job_filters=None):
    today = date.today().isoformat()
    sources = [str(s).strip() for s in (job_sources or []) if str(s).strip()] or ["LinkedIn Jobs", "JobStreet", "Company Careers"]
    titles = [str(t).strip() for t in (title_angles or []) if str(t).strip()]
    if not titles and target_role:
        titles = [str(target_role).strip()]
    if not titles:
        titles = ["Relevant role"]
    leads = []
    seen = set()
    for source in sources[:4]:
        for title in titles[:4]:
            key = (source.lower(), title.lower())
            if key in seen:
                continue
            seen.add(key)
            url = _lead_portal_search_url(source, title, regions, job_filters)
            leads.append({
                "id": f"search_{len(leads)+1}",
                "lead_kind": "fallback_search_link",
                "company": f"{source} search",
                "country": ", ".join(str(r) for r in regions or []),
                "region": ", ".join(str(r) for r in regions or []),
                "industry": "",
                "job_portal": source,
                "matched_role": title,
                "hiring_signal": "Fallback search link generated because live job crawling timed out or returned no usable leads.",
                "date_posted": "",
                "days_open": "",
                "job_freshness": "Unknown",
                "job_url": "",
                "job_url_quality": "source_or_search_result_only",
                "company_url": "",
                "job_fit_percent": 65,
                "match_score": 65,
                "why_matched": "Open this source/search link to review live job ads for this title and selected region. This is not a verified job lead yet.",
                "source_url": url,
                "source_note": "Fallback source/search link only — live web search timed out before extracting direct job leads.",
                "date_found": today,
            })
            if len(leads) >= max_n:
                return leads
    return leads


def _lead_portal_domain_hint(source):
    s = str(source or "").lower()
    if "linkedin" in s:
        return "site:linkedin.com/jobs"
    if "jobstreet" in s:
        return "site:jobstreet.com"
    if "indeed" in s:
        return "site:indeed.com"
    if "glassdoor" in s:
        return "site:glassdoor.com"
    if "monster" in s or "foundit" in s:
        return "site:foundit.my OR site:foundit.sg OR site:monster.com"
    if "hiredly" in s:
        return "site:hiredly.com"
    if "jobsdb" in s:
        return "site:jobsdb.com"
    if "mycareersfuture" in s:
        return "site:mycareersfuture.gov.sg"
    if "kalibrr" in s:
        return "site:kalibrr.com"
    if "career" in s or "company" in s:
        return "careers jobs"
    return "jobs"


def _lead_google_jobs_query(query):
    """Clean normal Google/portal query syntax into a Google Jobs-friendly query.

    SerpAPI's google_jobs engine performs better with plain role + location
    terms. Site: operators often produce no structured jobs and pushed users
    back into expensive/empty AI fallback.
    """
    q = str(query or "")
    q = re.sub(r"\bsite:[^\s]+", " ", q, flags=re.I)
    q = re.sub(r"\bOR\b", " ", q, flags=re.I)
    q = re.sub(r"[-–]\s*\w+", " ", q)  # remove simple negative terms for Google Jobs engine
    q = q.replace('"', " ")
    q = re.sub(r"\s+", " ", q).strip()
    if " job" not in q.lower() and " jobs" not in q.lower():
        q += " jobs"
    return q[:220]


def _lead_guess_role_company_from_search_result(title, snippet, title_angles=None):
    """Best-effort extraction of role + company from provider result title/snippet.

    Search providers often return compact titles such as:
    - "Senior Data Engineer - Maybank - LinkedIn"
    - "Data Engineer | Grab"
    - "Axiata is hiring a Data Engineer"
    This function favours title structure first, then snippet patterns.
    """
    title = re.sub(r"\s+", " ", str(title or "")).strip()
    snippet = re.sub(r"\s+", " ", str(snippet or "")).strip()
    role = ""
    company = ""
    title_angles = [str(t or "").strip() for t in (title_angles or []) if str(t or "").strip()]
    role_words = r"(engineer|developer|architect|analyst|manager|executive|specialist|consultant|associate|lead|head|director|partner|recruiter|accountant|controller|officer|advisor|designer|marketer|sales|operations|finance|hr|human resources|data|sap|fico|marketing|legal|compliance|risk|procurement|supply chain)"
    portal_re = re.compile(r"\b(linkedin|jobstreet|indeed|glassdoor|hiredly|foundit|monster|jobsdb|mycareersfuture|kalibrr|serpapi|tavily|jobs?|careers?)\b", re.I)

    def clean_role(x):
        x = re.sub(r"\s+", " ", str(x or "")).strip(" -|,•:")
        x = re.sub(r"\b(job|jobs|vacancy|vacancies|career|careers|hiring|apply now)\b", "", x, flags=re.I).strip(" -|,•:")
        # Provider snippets often say "Company hiring Senior Data Engineer in Malaysia".
        # Keep the role clean instead of storing "Senior Data Engineer in Malaysia".
        x = re.sub(r"\s+\b(?:in|based in|located in)\s+(?:Malaysia|Singapore|Indonesia|Philippines|Brunei|Thailand|Vietnam|APAC|SEA|Kuala Lumpur|Selangor|Penang|Johor|Cyberjaya|Petaling Jaya)\b.*$", "", x, flags=re.I).strip(" -|,•:")
        if len(x) > 90:
            x = x[:90].strip(" -|,•:")
        return x

    def looks_role(x):
        x = str(x or "").strip()
        if not x:
            return False
        if any(t and re.search(re.escape(t), x, re.I) for t in title_angles):
            return True
        return bool(re.search(role_words, x, re.I))

    # Parse snippet by itself first. When combined with the title, a pattern like
    # "Maybank hiring Senior Data Engineer" could otherwise greedily capture the
    # preceding title text as part of the company.
    for pat in [
        r"(?P<role>[^|–—\-]{3,90})\s+(?:at|@)\s+(?P<company>[^|–—\-.,;]{2,90})",
        r"(?P<company>[^|–—\-.,;]{2,90})\s+(?:is\s+)?hiring\s+(?:a|an|for)?\s*(?P<role>[^|–—\-.;,]{3,90})",
    ]:
        for source_text in (snippet, title):
            m = re.search(pat, source_text, flags=re.I)
            if m:
                cand_role = clean_role(m.group("role"))
                cand_company = _lead_clean_company_guess(m.group("company"))
                if cand_role and cand_company:
                    role, company = cand_role, cand_company
                    break
        if role and company:
            break

    hay = " ".join([title, snippet]).strip()
    if not (role and company):
        for pat in [
            r"(?P<role>[^|–—\-]{3,90})\s+(?:at|@)\s+(?P<company>[^|–—\-.,;]{2,90})",
            r"(?P<company>[^|–—\-.,;]{2,90})\s+(?:is\s+)?hiring\s+(?:a|an|for)?\s*(?P<role>[^|–—\-.;,]{3,90})",
        ]:
            m = re.search(pat, hay, flags=re.I)
            if m:
                cand_role = clean_role(m.group("role"))
                cand_company = _lead_clean_company_guess(m.group("company"))
                if cand_role and cand_company:
                    role, company = cand_role, cand_company
                    break

    if not (role and company) and title:
        parts = [p.strip(" -|,•:") for p in re.split(r"\s*(?:\||–|—| - )\s*", title) if p.strip(" -|,•:")]
        parts = [p for p in parts if not portal_re.fullmatch(p)]
        if len(parts) >= 2:
            first, second = parts[0], parts[1]
            if looks_role(first) and not looks_role(second):
                role = clean_role(first)
                company = _lead_clean_company_guess(second)
            elif looks_role(second) and not looks_role(first):
                role = clean_role(second)
                company = _lead_clean_company_guess(first)
            else:
                role = clean_role(first)
                company = _lead_clean_company_guess(second)

    if not company:
        for pat in [
            r"company\s*[:：]\s*([^.;|,]{2,80})",
            r"employer\s*[:：]\s*([^.;|,]{2,80})",
            r"hiring\s+company\s*[:：]\s*([^.;|,]{2,80})",
            r"join\s+([^.;|,]{2,70})\s+as\s+(?:a|an)?\s*",
        ]:
            m = re.search(pat, snippet, flags=re.I)
            if m:
                company = _lead_clean_company_guess(m.group(1))
                if company:
                    break

    if not role:
        for t in title_angles:
            if t and re.search(re.escape(t), hay, flags=re.I):
                role = t
                break
    if not role and title:
        role = clean_role(re.split(r"\s*(?:\||–|—| - )\s*", title)[0])

    return clean_role(role), _lead_clean_company_guess(company)


def _lead_provider_results_to_leads(provider_results, regions, job_sources, title_angles, target_role="", job_filters=None, max_n=12):
    """Deterministically convert search-provider results into provisional job leads.

    This avoids paying an additional AI call when Tavily/SerpAPI already returns
    direct job URLs/snippets. The output is labelled provider_extracted so users
    know to review the source before outreach.
    """
    job_filters = job_filters or {}
    today = date.today().isoformat()
    leads = []
    seen = set()
    for i, r in enumerate(provider_results or [], 1):
        if not isinstance(r, dict):
            continue
        url = str(r.get("url") or "").strip()
        title = str(r.get("title") or "").strip()
        snippet = str(r.get("snippet") or "").strip()
        if not (url or title or snippet):
            continue
        direct = _lead_is_direct_job_url(url)
        structured_job_raw = bool(r.get("structured_job_result") and str(r.get("company_name") or "").strip() and title and re.match(r"^https?://", url, re.I))
        try:
            _parsed_url = urllib.parse.urlparse(url)
            _path_l = (_parsed_url.path or "").lower()
        except Exception:
            _path_l = ""
        _title_l = title.lower()
        role, company = _lead_guess_role_company_from_search_result(title, snippet, title_angles)
        # Structured providers such as SerpAPI Google Jobs return company_name
        # explicitly; prefer it over brittle title parsing.
        structured_company = _lead_clean_company_guess(r.get("company_name") or "")
        if structured_company:
            company = structured_company
        if not role and title:
            role = title
        if not company and direct:
            company = _lead_guess_company_from_url(url)
        # Direct job URLs are best. If a provider/source result is not a direct
        # permalink but still has employer + role evidence, keep it as Needs
        # Verification instead of silently discarding a paid search result. Do not
        # keep raw generic portal category pages unless a real employer name is
        # visible and distinct from the job title.
        role_for_review = role or title or target_role or ""
        if _lead_is_non_job_content_url(url):
            continue
        company_norm = re.sub(r"[^a-z0-9]+", " ", str(company or "").lower()).strip()
        role_norm = re.sub(r"[^a-z0-9]+", " ", str(role_for_review or "").lower()).strip()
        company_looks_like_role = _lead_company_is_actually_role_text(company_norm, role_norm)
        generic_category_url = _lead_is_generic_portal_category_url(url, company)
        structured_job = bool(structured_job_raw and not generic_category_url)
        reviewable_provider = bool((company or "").strip() and str(role_for_review or "").strip() and re.match(r"^https?://", url, re.I) and not company_looks_like_role)
        if generic_category_url and (not reviewable_provider):
            continue
        if not (direct or structured_job or reviewable_provider):
            continue
        key = (url or (company + role)).lower().rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        portal = _lead_guess_portal_from_url(url, r.get("provider") or "")
        if not _lead_source_allowed_by_selection(url, portal, job_sources):
            continue
        date_posted, days_open = _lead_parse_posted_date(r.get("published_date") or snippet)
        provider_location = str(r.get("location") or "").strip()
        country = provider_location or (regions[0] if regions else "")
        fit = 78 if (direct or structured_job) else 68
        hay = (title + " " + snippet).lower()
        if any(str(t or "").lower() in hay for t in (title_angles or []) if str(t or "").strip()):
            fit += 8
        c = {
            "id": f"co_provider_{len(leads)+1}",
            "company": company or "Company not visible in search result",
            "country": country,
            "region": provider_location or country,
            "industry": "",
            "job_portal": portal,
            "matched_role": role or target_role or "Relevant open role",
            "hiring_signal": title or "Search provider job result",
            "date_posted": date_posted if days_open is not None else (r.get("published_date") or ""),
            "days_open": days_open if days_open is not None else "",
            "job_freshness": _lead_freshness_label(days_open) if days_open is not None else "Unknown",
            "job_url": url if (direct or structured_job) else "",
            "job_url_quality": "direct_job_ad" if direct else ("structured_google_job" if structured_job else "needs_verification"),
            "company_url": "",
            "job_fit_percent": max(0, min(100, fit)),
            "match_score": max(0, min(100, fit)),
            "why_matched": "Matched from search-provider result using the candidate role/title angles and selected region. This is broad review mode: even partial/low stack-fit leads can be kept so the recruiter decides. Review the source before outreach.",
            "source_url": url,
            "source_note": (("Structured Google Jobs result. " if structured_job else "") + (snippet[:420] or title[:420] or "Search provider result"))[:520],
            "date_found": today,
            "lead_kind": "extracted_job_lead" if (direct or structured_job) else "job_lead_needs_verification",
            "provider_extracted": True
        }
        if not _lead_company_matches_title_angles(c, title_angles):
            continue
        leads.append(c)
        if len(leads) >= int(max_n or 12):
            break
    parsed = {
        "summary": {
            "candidate_title": target_role or "Candidate",
            "target_roles": [target_role] if target_role else [],
            "target_job_title_angles": title_angles or [],
            "job_filters_used": job_filters,
            "regions": regions,
            "job_sources_used": job_sources,
            "source_strategy": "Search provider API results converted directly into provisional extracted job leads without extra AI classification cost. Review mode is broad: lower stack-fit leads are kept and labelled instead of discarded.",
            "job_fit_method": "Job Fit % is estimated from title/search-result relevance, direct job URL quality, selected region, and candidate role/title angles. Low-fit/borderline leads are kept for recruiter review unless they hit explicit exclude filters.",
            "freshness_method": "Freshness is taken from provider date/snippet when visible; otherwise Unknown.",
            "compliance_note": "Public search/job sources only; review links before outreach."
        },
        "companies": leads,
        "people": []
    }
    parsed = _lead_normalize_company_fit_freshness(parsed)
    parsed, location_warning = _lead_filter_by_regions(parsed, regions)
    parsed = _lead_normalize_company_fit_freshness(parsed)
    parsed, filter_warning = _lead_apply_basic_job_filters(parsed, job_filters or {})
    warning = ""
    if location_warning:
        warning = location_warning
    if filter_warning:
        warning = (warning + " " + filter_warning).strip() if warning else filter_warning
    return parsed, warning


def _lead_extract_json(raw_text):
    """Extract the first JSON object from a model response safely.

    Lead Finder should not return 0 just because the model wrapped JSON in
    prose/code fences or left a harmless trailing comma. This parser still only
    accepts object-like data, but it is more forgiving than strict json.loads.
    """
    raw_text = (raw_text or "").strip().lstrip("﻿")
    raw_text = re.sub(r"[​‌‍]", "", raw_text)
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:].strip()
    if raw_text.startswith("```"):
        raw_text = raw_text[3:].strip()
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3].strip()

    candidates = [raw_text]
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(raw_text[start:end+1])

    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        repaired = re.sub(r",\s*([}\]])", r"\1", candidate)
        for item in (candidate, repaired):
            try:
                obj = json.loads(item)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass
            try:
                obj = ast.literal_eval(item)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass
    raise ValueError("No valid JSON object found in model response")


def _lead_selected_source_site(job_sources, portal_hint=""):
    """Pick the best site: restriction for a selected-source verification search.

    If the model labels a lead as LinkedIn but gives an Indeed source URL, the
    recruiter selected LinkedIn, so Verify Source should search LinkedIn rather
    than opening the unselected Indeed page. Prefer the visible portal hint when
    it is one of the selected chips; otherwise use the first selected portal in a
    stable priority order.
    """
    selected = [str(s or "").strip().lower() for s in (job_sources or []) if str(s or "").strip()]
    hint = str(portal_hint or "").strip().lower()

    def has(*needles):
        return any(any(n in s for n in needles) for s in selected)

    ordered = []
    if "linkedin" in hint and has("linkedin"):
        ordered.append(("LinkedIn Jobs", "www.linkedin.com/jobs"))
    if "jobstreet" in hint and has("jobstreet"):
        ordered.append(("JobStreet", "my.jobstreet.com"))
    if "jobsdb" in hint and has("jobsdb"):
        ordered.append(("JobsDB", "jobsdb.com"))
    if "indeed" in hint and has("indeed"):
        ordered.append(("Indeed", "indeed.com"))
    if "glassdoor" in hint and has("glassdoor"):
        ordered.append(("Glassdoor", "glassdoor.com"))
    if "hiredly" in hint and has("hiredly"):
        ordered.append(("Hiredly", "hiredly.com"))

    priority = [
        ("LinkedIn Jobs", "www.linkedin.com/jobs", ("linkedin",)),
        ("JobStreet", "my.jobstreet.com", ("jobstreet",)),
        ("JobsDB", "jobsdb.com", ("jobsdb",)),
        ("Indeed", "indeed.com", ("indeed",)),
        ("Glassdoor", "glassdoor.com", ("glassdoor",)),
        ("Hiredly", "hiredly.com", ("hiredly",)),
        ("MyCareersFuture", "mycareersfuture.gov.sg", ("mycareersfuture",)),
        ("Kalibrr", "kalibrr.com", ("kalibrr",)),
        ("Foundit", "foundit.my", ("foundit", "monster")),
    ]
    for label, site, needles in priority:
        if has(*needles):
            ordered.append((label, site))

    seen = set()
    for label, site in ordered:
        if site in seen:
            continue
        seen.add(site)
        return label, site
    if has("company", "career"):
        return "Company career pages", ""
    if has("other public", "other portal"):
        return "selected public job portals", ""
    return "selected source", ""


def _lead_best_selected_source_verification_url(company, role, job_sources, portal_hint=""):
    """Build a review URL constrained to the selected source chips.

    This is used when a lead is otherwise useful, but the returned URL belongs to
    an unselected portal (for example a LinkedIn-only run where the model/provider
    returned an Indeed search URL).
    """
    company = _lead_verification_company_text(company)
    role = re.sub(r"\s+", " ", str(role or "")).strip()
    label, site = _lead_selected_source_site(job_sources, portal_hint)
    q_parts = [f'"{company}"'] if company else []
    q_parts += [f'"{role}"'] if role else []
    if site:
        q_parts.append(f"site:{site}")
    else:
        q_parts.append(str(label or "jobs"))
    if not q_parts:
        return "", ""
    search_url = "https://www.google.com/search?q=" + urllib.parse.quote(" ".join(q_parts))
    note = f"Removed a URL from an unselected portal and replaced it with a targeted verification search for {label}."
    return search_url, note


def _lead_cleanup_urls_by_selected_sources(parsed, job_sources):
    """Remove job/source URLs from portals the user did not select.

    Provider filtering already blocks most cross-source provider results, but the
    AI/refine path can still return a row labelled as one selected source while
    placing an Indeed/Glassdoor/etc. URL in source_url. This final safety pass
    prevents a LinkedIn-only run from opening Indeed links, a JobStreet-only run
    from opening LinkedIn links, and so on.
    """
    if not isinstance(parsed, dict):
        return parsed, ""
    selected = [str(s or "").strip() for s in (job_sources or []) if str(s or "").strip()]
    if not selected:
        return parsed, ""
    companies = parsed.get("companies") or []
    if not isinstance(companies, list):
        return parsed, ""
    changed = 0
    for c in companies:
        if not isinstance(c, dict):
            continue
        role = c.get("matched_role") or c.get("title") or c.get("hiring_signal") or ""
        portal_hint = c.get("job_portal") or ""
        bad_urls = []

        job_url = str(c.get("job_url") or "").strip()
        if job_url and not _lead_is_generated_verification_search(job_url):
            portal = _lead_guess_portal_from_url(job_url, portal_hint)
            if not _lead_source_allowed_by_selection(job_url, portal, selected):
                bad_urls.append(job_url)
                c["job_url"] = ""
                c["job_url_quality"] = "needs_verification"
                c["lead_kind"] = "job_lead_needs_verification"

        source_url = str(c.get("source_url") or "").strip()
        if source_url and not _lead_is_generated_verification_search(source_url):
            portal = _lead_guess_portal_from_url(source_url, portal_hint)
            if not _lead_source_allowed_by_selection(source_url, portal, selected):
                bad_urls.append(source_url)
                c["source_url"] = ""

        if bad_urls:
            if not str(c.get("source_url") or "").strip():
                best_url, gen_note = _lead_best_selected_source_verification_url(c.get("company"), role, selected, portal_hint)
                if best_url:
                    c["source_url"] = best_url
                if gen_note:
                    existing_note = str(c.get("source_note") or "").strip()
                    c["source_note"] = (existing_note + " " + gen_note).strip() if existing_note and gen_note not in existing_note else (existing_note or gen_note)
            changed += 1
    if changed:
        return parsed, f"Cleaned {changed} cross-source URL(s) that belonged to unselected job portals."
    return parsed, ""


def _lead_fake_anthropic_response(obj):
    """Build a minimal Anthropic-like response so routes can return partial JSON instead of 504."""
    return {
        "content": [{"type": "text", "text": json.dumps(obj or {}, ensure_ascii=False)}],
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }


def _lead_search_provider_queries(job_sources, title_angles, regions, target_role="", job_filters=None, max_queries=8):
    titles = [str(t).strip() for t in (title_angles or []) if str(t).strip()]
    if target_role and target_role not in titles:
        titles.insert(0, str(target_role).strip())
    titles = titles[:4] or [str(target_role or "job").strip()]
    srcs = [str(s).strip() for s in (job_sources or []) if str(s).strip()][:4] or ["jobs"]
    regs = [str(r).strip() for r in (regions or []) if str(r).strip()][:3] or [""]
    include = _lead_filter_query_terms(job_filters or {})
    exclude = _lead_exclude_query_terms(job_filters or {})
    queries = []
    for src in srcs:
        hint = _lead_portal_domain_hint(src)
        for reg in regs:
            for title in titles:
                q = f'{hint} "{title}" {reg} job {include} {exclude}'.strip()
                q = re.sub(r"\s+", " ", q)
                if q not in queries:
                    queries.append(q)
                if len(queries) >= max_queries:
                    return queries
    return queries[:max_queries]
