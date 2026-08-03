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
