"""Pure Lead Finder URL, portal and company-guess helpers.

Behavior-preserving extraction from the legacy web shell. These classify job-ad
URLs, label the source portal, and derive a best-effort company name from a URL
or search result. They use only the standard library and are independent of the
Flask application, which re-exports them for its existing call sites.
"""

from __future__ import annotations

import re
import urllib.parse


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
