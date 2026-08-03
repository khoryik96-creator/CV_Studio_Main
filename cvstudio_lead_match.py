"""Lead location and company-matching helpers (Phase 7B-6d).

Behaviour-preserving extraction of the stateless Lead Finder geography and
company-matching helpers from the legacy web shell: country/region alias
resolution, APAC/remote detection, location-allowed checks, and company-name
normalisation and matching, with the lookup tables they depend on.

Pure functions and module-level data only - no Flask, no globals mutated at
runtime, no network. This module never imports ``app``.
"""

import re


_LEAD_COUNTRY_ALIASES = {
    "Malaysia": ["malaysia", "my", "kuala lumpur", "kl", "selangor", "penang", "johor", "cyberjaya", "putrajaya", "petaling jaya", "shah alam"],
    "Singapore": ["singapore", "sg"],
    "Indonesia": ["indonesia", "id", "jakarta", "surabaya", "bandung"],
    "Philippines": ["philippines", "ph", "manila", "makati", "taguig", "cebu"],
    "Brunei": ["brunei", "bn", "bandar seri begawan"],
    "Thailand": ["thailand", "thai", "bangkok", "th"],
    "Vietnam": ["vietnam", "viet nam", "ho chi minh", "hanoi", "vn"],
    "Poland": ["poland", "pl", "warsaw", "krakow", "wroclaw", "poznan", "gdansk"],
    "Nigeria": ["nigeria", "ng", "lagos", "abuja", "ikeja"],
    "Austria": ["austria", "at", "vienna", "wien", "graz", "linz", "salzburg"],
}


_LEAD_REMOTE_TERMS = ("remote", "work from home", "wfh", "work-from-home", "hybrid")


_LEAD_APAC_TERMS = ("apac", "asia pacific", "southeast asia", "south east asia", "sea", "asean", "regional")


_LEAD_APAC_REMOTE_REGION_NAMES = {
    "malaysia", "singapore", "indonesia", "philippines", "brunei", "thailand", "vietnam",
    "apac", "asia pacific", "southeast asia", "south east asia", "sea", "asean"
}


def _lead_region_aliases(regions):
    aliases = []
    for r in regions or []:
        r = str(r or "").strip()
        if not r:
            continue
        aliases.append(r.lower())
        aliases.extend(_LEAD_COUNTRY_ALIASES.get(r, []))
    # Keep order while deduping.
    seen = set()
    out = []
    for a in aliases:
        a = str(a or "").strip().lower()
        if a and a not in seen:
            seen.add(a)
            out.append(a)
    return out


def _lead_has_apac(regions):
    return any(str(r or "").strip().lower() in ("apac", "asia pacific", "southeast asia", "south east asia", "sea", "asean") for r in (regions or []))


def _lead_regions_allow_apac_remote(regions):
    return any(str(r or "").strip().lower() in _LEAD_APAC_REMOTE_REGION_NAMES for r in (regions or []))


def _lead_blob_has_alias(blob, alias):
    alias = str(alias or "").strip().lower()
    if not alias:
        return False
    # Short country codes like MY/SG/ID are useful, but dangerous as raw
    # substrings ("my" appears in company/MyCareersFuture). Match them as
    # standalone tokens only.
    if len(alias) <= 3 and re.fullmatch(r"[a-z0-9]+", alias):
        return re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", blob) is not None
    return alias in blob


def _lead_text_blob(item):
    if not isinstance(item, dict):
        return ""
    keys = (
        "country", "region", "location", "matched_role", "hiring_signal", "job_url",
        "company_url", "why_matched", "source_url", "source_note", "notes",
        "job_portal", "title", "contact_type"
    )
    return " ".join(str(item.get(k) or "") for k in keys).lower()


def _lead_location_allowed(item, regions):
    """Allow only selected-country leads plus remote roles clearly open to that country.

    APAC remains broad because the user explicitly selected a regional search. For a
    specific country like Malaysia, a generic 'Remote' role is not enough; the lead
    must also mention Malaysia/MY/KL/etc. or an APAC/SEA remote scope.
    """
    if _lead_has_apac(regions):
        return True
    aliases = _lead_region_aliases(regions)
    if not aliases:
        return True
    blob = _lead_text_blob(item)
    if not blob.strip():
        return False
    if any(_lead_blob_has_alias(blob, a) for a in aliases):
        return True
    is_remote = any(t in blob for t in _LEAD_REMOTE_TERMS)
    if is_remote and _lead_regions_allow_apac_remote(regions) and any(t in blob for t in _LEAD_APAC_TERMS):
        return True
    return False


def _lead_norm_company_name(value):
    s = str(value or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\b(sdn bhd|berhad|bhd|pte ltd|pte|ltd|limited|inc|corp|corporation|company|co)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _lead_company_names_match(a, b):
    na = _lead_norm_company_name(a)
    nb = _lead_norm_company_name(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # Accept common shortened company names, but avoid tiny accidental matches.
    return (len(na) >= 4 and na in nb) or (len(nb) >= 4 and nb in na)


_LEAD_GENERIC_ROLE_WORDS = {
    "senior", "junior", "lead", "principal", "staff", "chief", "head", "director", "manager",
    "executive", "specialist", "consultant", "analyst", "engineer", "developer", "administrator",
    "officer", "accountant", "recruiter", "designer", "scientist", "coordinator", "planner",
    "supervisor", "architect", "partner", "associate", "assistant", "representative", "technician",
    "controller", "auditor", "secretary", "counsel", "marketer", "dba", "vp", "svp",
}


def _lead_company_is_actually_role_text(company_norm, role_norm):
    """True only when the guessed 'company' is clearly the job title/listing text
    misread as an employer name — an exact match, or every word in it being a
    generic role/seniority word (no proper noun at all).

    Deliberately NOT a substring check: 'Oracle' is a substring of 'Oracle DBA',
    and 'SAP' is a substring of 'SAP Consultant', but both are real employer
    names a recruiter would legitimately encounter (especially in SAP/ERP and
    Oracle DBA searches) and must not be silently dropped.
    """
    if not company_norm or not role_norm:
        return False
    if company_norm == role_norm:
        return True
    company_words = set(company_norm.split())
    if company_words and company_words.issubset(_LEAD_GENERIC_ROLE_WORDS):
        return True
    return False


def _lead_location_instruction(regions):
    if _lead_has_apac(regions):
        return "APAC selected: include APAC/SEA/regional roles and remote APAC roles. Still record the exact country/region wherever known."
    parts = []
    for r in regions or []:
        r = str(r or "").strip()
        if not r:
            continue
        aliases = _LEAD_COUNTRY_ALIASES.get(r, [])
        sample = ", ".join(aliases[:6]) if aliases else r
        parts.append(f"{r}: on-site/hybrid roles based in {r}, plus remote roles that explicitly accept {r}-based candidates ({sample}, remote {r}, {r} remote).")
    return " Hard filter selected locations only. ".join(parts) or "Use selected regions as hard filters."


def _lead_company_matches_title_angles(company, title_angles):
    """Return True when a job lead is in the same role family as the generated title angles.

    This is not a tech-stack filter. It only blocks obviously unrelated role
    families such as HR jobs for a Data Engineer CV. Leads with weak stack/skill
    overlap remain visible if the job title family is relevant.
    """
    if not isinstance(company, dict):
        return False
    angles = [str(t or '').strip().lower() for t in (title_angles or []) if str(t or '').strip()]
    if not angles:
        return True
    # If angles are only generic fallback terms, don't role-filter.
    generic = {'executive','senior executive','specialist','senior specialist','analyst','senior analyst','associate','consultant','manager','senior manager','assistant manager','lead'}
    non_generic = [a for a in angles if a not in generic]
    if not non_generic:
        return True
    hay = ' '.join(str(company.get(k) or '') for k in ['matched_role','hiring_signal','why_matched','source_note','industry']).lower()
    # Strong phrase match on any generated title angle.
    for a in non_generic[:24]:
        if len(a) >= 4 and a in hay:
            return True
    # Token-family match: require at least one meaningful domain token from the
    # generated angles in the job title/signal text.
    stop = {'senior','junior','lead','manager','head','director','executive','specialist','analyst','consultant','engineer','developer','officer','assistant','associate','principal','staff','job','jobs'}
    tokens = set()
    for a in non_generic[:24]:
        for tok in re.findall(r'[a-z][a-z0-9+#.]{2,}', a):
            if tok not in stop:
                tokens.add(tok)
    if not tokens:
        return True
    return any(re.search(r'(?<![a-z0-9])' + re.escape(tok) + r'(?![a-z0-9])', hay) for tok in tokens)
