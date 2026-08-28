"""Blind CV/JD organisation-masking helpers (Phase 7B-6f).

Behaviour-preserving extraction of the stateless organisation-masking logic
from the legacy web shell: collecting employer/organisation mask terms,
recursively walking parsed CV structures, and replacing or post-processing
company mentions so a blinded CV/JD hides identifying employer names while
keeping a curated technology allowlist.

Pure functions and module-level data only - no Flask, no globals, no network.
This module never imports ``app``.
"""

import copy
import re


_BLIND_ORG_TECH_ALLOWLIST = {
    "aws", "amazon web services", "azure", "microsoft azure", "gcp", "google cloud",
    "python", "pyspark", "spark", "apache spark", "airflow", "apache airflow",
    "sql", "mysql", "postgresql", "oracle sql", "redshift", "aws redshift",
    "lambda", "aws lambda", "s3", "ec2", "emr", "rds", "glue", "aws glue",
    "tableau", "power bi", "ssis", "ssrs", "ssas", "jenkins", "git", "github",
    "kafka", "databricks", "snowflake", "talend", "dbeaver", "athena",
    "salesforce", "sap", "oracle", "linux", "windows", "excel", "csv", "json",
    # Ambiguous technology vendor/platform names: do not sweep these from free-text
    # bullets because they are often tools rather than client identities. Employer
    # fields are still handled by the AI prompt/company-field masking.
    "microsoft", "amazon", "google", "apple", "adobe", "cisco", "huawei",
    "workday", "servicenow", "ibm", "youtube", "dataiku",
}


_BLIND_CURATED_ORG_NAMES = {
    "Maxis", "Celcom", "Digi", "CelcomDigi", "U Mobile", "Telekom Malaysia", "TM",
    "Axiata", "Time dotCom", "YTL", "Yes", "Astro", "Unifi",
    "Maybank", "CIMB", "RHB", "Hong Leong Bank", "Public Bank", "AmBank",
    "Bank Islam", "Bank Muamalat", "Affin Bank", "Alliance Bank", "OCBC", "UOB",
    "DBS", "Bank of Singapore", "HSBC", "Standard Chartered", "Citibank", "Citi", "JP Morgan",
    "JPMorgan", "Goldman Sachs", "Morgan Stanley", "Credit Suisse", "UBS",
    "IHH", "IHH Healthcare", "AIA", "Prudential", "Great Eastern", "Allianz",
    "Etiqa", "Zurich", "FWD", "Tune Protect", "Sunway", "Sime Darby",
    "Petronas", "Shell", "ExxonMobil", "BHP", "MISC", "Tenaga Nasional", "TNB",
    "AirAsia", "Malaysia Airlines", "Batik Air", "Grab", "GrabPay", "Shopee",
    "Lazada", "Zalora", "Foodpanda", "Touch 'n Go", "TNG", "Boost", "BigPay",
    "Setel", "Carsome", "iFAST", "CTOS", "Experian", "Bursa Malaysia",
    "PayNet", "DuitNow", "MyClear", "MDEC", "EPF", "KWSP", "SOCSO", "PERKESO",
    "Accenture", "Deloitte", "PwC", "EY", "KPMG", "Capgemini", "Cognizant",
    "TCS", "Infosys", "Wipro", "HCLTech", "IBM", "DXC", "NTT", "NTT DATA",
    "Fujitsu", "Atos", "EPAM", "Avanade", "Dataiku", "YouTube", "Google",
    "Meta", "Facebook", "Apple", "Amazon", "Netflix", "Microsoft", "SAP", "Oracle",
    "Salesforce", "Workday", "ServiceNow", "Adobe", "Cisco", "Huawei", "Tencent",
    "Alibaba", "ByteDance", "TikTok", "Genting", "Genting Group", "Resorts World",
}


_BLIND_ORG_SUFFIX_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9&.'’\-]*(?:\s+[A-Za-z0-9&.'’\-]+){0,8}\s+"
    r"(?i:Sdn\.?\s*Bhd\.?|Bhd\.?|Berhad|Pte\.?\s*Ltd\.?|Pvt\.?\s*Ltd\.?|Ltd\.?|Limited|Inc\.?|LLC|LLP|PLC|Corp\.?|Corporation|Company|Co\.?|Group|Holdings|Bank|Insurance|Assurance|Telecommunications|Telekom|Technologies|Technology|Solutions|Services|Consulting))\b"
)


def _blind_walk_strings(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _blind_walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _blind_walk_strings(v)
    elif isinstance(obj, str):
        yield obj


def _blind_add_mask_term(terms, value):
    if not value:
        return
    text = re.sub(r"\s+", " ", str(value)).strip().strip(" .,:;|-/")
    if not text or len(text) < 3:
        return
    low = text.lower().strip()
    # Reject sentence-spanning regex overcaptures such as
    # "Integrated Maybank2u ... Worked with Bank".
    if re.search(r"[.!?]", text) and not re.search(r"\b(?:sdn|bhd|ltd|inc|corp|co)\.", low):
        return
    if low in _BLIND_ORG_TECH_ALLOWLIST:
        return
    # Do not collect generic descriptors already produced by the blind prompt.
    generic_bits = ("leading ", "prominent ", "major ", "global ", "top-", "fortune ", "one of ", "government", "public sector")
    if low.startswith(generic_bits) or low in {"candidate", "company", "client", "project", "organization", "organisation"}:
        return
    # Avoid over-masking common CV words/sections.
    if low in {"summary", "technical skills", "work experience", "project experience", "education", "certification", "banking", "insurance", "telecommunications"}:
        return
    terms.add(text)


def _blind_collect_org_mask_terms(original_cv):
    terms = set()
    if not isinstance(original_cv, dict):
        return []

    cand = original_cv.get("candidate") if isinstance(original_cv.get("candidate"), dict) else {}
    _blind_add_mask_term(terms, cand.get("current_company"))

    for exp in original_cv.get("work_experiences") or []:
        if not isinstance(exp, dict):
            continue
        _blind_add_mask_term(terms, exp.get("company"))

    # Exact curated org names found anywhere in the original CV, including
    # bullets/project descriptions. This catches cases like "built for Maxis".
    all_text = "\n".join(_blind_walk_strings(original_cv))
    compact_text = re.sub(r"\s+", " ", all_text)
    for name in sorted(_BLIND_CURATED_ORG_NAMES, key=len, reverse=True):
        if not name or name.lower() in _BLIND_ORG_TECH_ALLOWLIST:
            continue
        exact_pat = re.compile(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])", re.I)
        prefix_pat = re.compile(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?=[A-Z0-9][A-Za-z0-9]{1,30})", re.I)
        if exact_pat.search(compact_text) or prefix_pat.search(compact_text):
            _blind_add_mask_term(terms, name)

    # Legal-suffix/company-pattern extraction from all text.
    for m in _BLIND_ORG_SUFFIX_RE.finditer(compact_text):
        candidate = m.group(1)
        # Trim common field labels accidentally captured before the name.
        candidate = re.sub(r"^(?:Organization|Organisation|Company|Client|Employer|Project|Project Name|Current Company)\s*[:\-]\s*", "", candidate, flags=re.I).strip()
        _blind_add_mask_term(terms, candidate)

    # Prefer longer phrases first so "Hong Leong Bank" is masked before "Bank"-ish fragments.
    clean = sorted(terms, key=lambda x: (-len(x), x.lower()))
    return clean[:250]


def _blind_replace_org_terms_in_text(text, terms):
    if not isinstance(text, str) or not text or not terms:
        return text
    out = text
    for term in terms:
        if not term or len(term) < 3:
            continue
        low = term.lower().strip()
        if low in _BLIND_ORG_TECH_ALLOWLIST:
            continue
        # Preserve already-masked descriptors/placeholders.
        pattern = re.compile(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", re.I)
        out = pattern.sub("[Company]", out)
        # Product/brand-prefix form: Maybank2u, GrabFood, MaxisONE, etc.
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9&.'’\- ]{2,40}", term):
            prefix = re.escape(term)
            prod_pat = re.compile(r"(?<![A-Za-z0-9])(" + prefix + r")(?=[A-Z0-9][A-Za-z0-9]{1,30})", re.I)
            out = prod_pat.sub("[Company]", out)
    return out


def _blind_mask_org_terms_recursive(obj, terms):
    if isinstance(obj, dict):
        return {k: _blind_mask_org_terms_recursive(v, terms) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_blind_mask_org_terms_recursive(v, terms) for v in obj]
    if isinstance(obj, str):
        return _blind_replace_org_terms_in_text(obj, terms)
    return obj


def _blind_role_bullet_texts(items):
    """Flatten role bullet/section text without carrying source wording.

    The blind provider is instructed to preserve JSON structure, but can turn a
    valid section object into a run of plain strings.  This helper reads only the
    provider's already-blinded response so repairing the shape cannot reintroduce
    an employer or client name from the original CV.
    """
    out = []
    source = items if isinstance(items, list) else []
    for item in source:
        if isinstance(item, str):
            if item.strip():
                out.append(item)
            continue
        if not isinstance(item, dict):
            continue
        heading = item.get("heading") or item.get("title") or ""
        if str(heading).strip():
            out.append(str(heading))
        out.extend(_blind_role_bullet_texts(item.get("bullets") or item.get("items") or []))
    return out


def _blind_rebuild_role_bullets(template_items, blinded_items):
    """Apply blinded text to the original bullet container shape when exact."""
    if not isinstance(template_items, list) or not isinstance(blinded_items, list):
        return None
    if any(not isinstance(item, (str, dict)) for item in template_items):
        return None
    replacement = _blind_role_bullet_texts(blinded_items)
    template_count = len(_blind_role_bullet_texts(template_items))
    if not replacement or len(replacement) != template_count:
        return None
    cursor = 0

    def rebuild(items):
        nonlocal cursor
        rebuilt = []
        for item in items:
            if isinstance(item, str):
                rebuilt.append(replacement[cursor])
                cursor += 1
                continue
            if not isinstance(item, dict):
                return None
            heading = item.get("heading") or item.get("title") or ""
            children = item.get("bullets") or item.get("items") or []
            if not str(heading).strip() or not isinstance(children, list):
                return None
            # Reconstruct only the documented structural keys.  Never copy an
            # unknown value from the unblinded source object back into output.
            group = {
                "heading": replacement[cursor],
                "bullets": [],
                "kind": "section",
            }
            cursor += 1
            group["bullets"] = rebuild(children)
            if group["bullets"] is None:
                return None
            rebuilt.append(group)
        return rebuilt

    rebuilt = rebuild(template_items)
    return rebuilt if cursor == len(replacement) else None


def _blind_restore_cv_bullet_structure(blinded, original_cv):
    """Restore role section/list containers when the model only flattened them.

    Repair is deliberately bounded to corresponding work-experience/role indexes
    whose flattened text counts match exactly.  A malformed or shortened response
    is left untouched rather than guessing or copying unblinded source wording.
    """
    if not isinstance(blinded, dict) or not isinstance(original_cv, dict):
        return blinded
    # Copy only the provider response.  No source object is ever copied into it.
    repaired = copy.deepcopy(blinded)
    original_experiences = original_cv.get("work_experiences") or []
    blinded_experiences = repaired.get("work_experiences") or []
    if not isinstance(original_experiences, list) or not isinstance(
        blinded_experiences, list
    ):
        return repaired
    for exp_index, original_exp in enumerate(original_experiences):
        if exp_index >= len(blinded_experiences):
            break
        blinded_exp = blinded_experiences[exp_index]
        if not isinstance(original_exp, dict) or not isinstance(blinded_exp, dict):
            continue
        original_roles = original_exp.get("roles") or []
        blinded_roles = blinded_exp.get("roles") or []
        if not isinstance(original_roles, list) or not isinstance(
            blinded_roles, list
        ):
            continue
        for role_index, original_role in enumerate(original_roles):
            if role_index >= len(blinded_roles):
                break
            blinded_role = blinded_roles[role_index]
            if not isinstance(original_role, dict) or not isinstance(blinded_role, dict):
                continue
            identity_mismatch = any(
                str(original_role.get(key) or "").strip()
                and str(blinded_role.get(key) or "").strip()
                and str(original_role.get(key)).strip().casefold()
                != str(blinded_role.get(key)).strip().casefold()
                for key in ("title", "date_range")
            )
            if identity_mismatch:
                continue
            template_items = original_role.get("bullets") or []
            # No section object means there is no container shape to restore.
            if not any(isinstance(item, dict) for item in template_items):
                continue
            rebuilt = _blind_rebuild_role_bullets(
                template_items,
                blinded_role.get("bullets") or [],
            )
            if rebuilt is not None:
                blinded_role["bullets"] = rebuilt
    return repaired


def _blind_postprocess_company_mentions(blinded, original_cv):
    """Final safety sweep for blind CV output.

    The model may correctly mask employer fields but miss company/client names in
    bullets, project descriptions, achievements or highlights.  Use the original
    parsed CV to build a conservative organisation-name mask list, then sweep the
    returned blinded JSON before it reaches preview/export.
    """
    terms = _blind_collect_org_mask_terms(original_cv)
    if not terms:
        return blinded
    return _blind_mask_org_terms_recursive(blinded, terms)
