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
_BLIND_SUMMARY_EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}(?![A-Za-z0-9._%+\-])",
    re.I,
)
_BLIND_SUMMARY_URL_RE = re.compile(
    r"(?<![A-Za-z0-9@])(?:"
    r"(?:https?://|www\.)[^\s<>()]+|"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}[A-Za-z0-9])?\.)+"
    r"(?:com|net|org|io|dev|me|co|info|biz|ai|app|tech|site|online|xyz|"
    r"cloud|digital|website|my|sg|uk)(?:/[^\s<>()]*)?"
    r")",
    re.I,
)
_BLIND_SUMMARY_BARE_DOMAIN_RE = re.compile(
    r"(?<![A-Za-z0-9@])"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}(?:/[^\s<>()]*)?",
    re.I,
)
_BLIND_SUMMARY_NON_DOMAIN_SUFFIXES = {
    "css", "csv", "doc", "docx", "html", "ini", "java", "js", "json",
    "log", "md", "pdf", "php", "ppt", "pptx", "py", "sql", "svg",
    "ts", "txt", "xls", "xlsx", "xml", "yaml", "yml",
}
_BLIND_SUMMARY_DOTTED_DEGREE_RE = re.compile(
    r"(?:[BM]\.(?:Arch|Com|Ed|Eng|Pharm|Sc|Tech)|D\.Phil)"
)
_BLIND_SUMMARY_PHONE_CANDIDATE_RE = re.compile(
    r"(?<![A-Za-z0-9])\+?\d[\d\s().\-]{6,}\d(?![A-Za-z0-9])"
)
_BLIND_SUMMARY_PHONE_CONTEXT_RE = re.compile(
    r"(?:\b(?:call|contact(?:\s+(?:number|no\.?))?|mobile(?:\s+(?:number|no\.?))?|"
    r"phone(?:\s+(?:number|no\.?))?|tel(?:ephone)?|whatsapp)"
    r"\s*(?:(?:number|no\.?)\s*)?(?::|#|-|is|at)?|"
    r"(?<![A-Za-z0-9])(?:m|t)\s*[:#-])\s*$",
    re.I,
)
_BLIND_SUMMARY_ADDRESS_LINE_RE = re.compile(
    r"^(?:(?:home|residential|mailing|current|permanent)\s+)?address\s*[:|\-]\s*(.+)$",
    re.I,
)
_BLIND_SUMMARY_INLINE_ADDRESS_RE = re.compile(
    r"\b(?:(?:home|residential|mailing|current|permanent)\s+)?address\s*[:\-]\s*[^;|\n]+",
    re.I,
)
_BLIND_SUMMARY_STREET_MARKER_RE = re.compile(
    r"\b(?:jalan|jln|lorong|lrg|persiaran|lebuh|lebuhraya|street|st|road|rd|"
    r"avenue|ave|lane|ln|drive|dr|boulevard|blvd|highway|suite|unit|block|blok|level|"
    r"floor|tingkat|apartment|apt|residensi|residency|residence|condominium|"
    r"menara|plaza)\b",
    re.I,
)
_BLIND_SUMMARY_UNLABELED_ADDRESS_RE = re.compile(
    r"^(?:(?:no\.?|unit|suite|block|blok|lot|floor|tingkat|level)\s*)?"
    r"(?:[A-Za-z]{0,3}[-/]?)?\d+[A-Za-z]?(?:[-/]\d+[A-Za-z]?){0,3}"
    r"(?:\s*,?\s*|\s+).+",
    re.I,
)
_BLIND_SUMMARY_DATE_RANGE_RE = re.compile(
    r"\b(?:(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\.?\s+)?(?:19|20)\d{2}\b\s*(?:[-–—]|to)\s*"
    r"(?:(?:(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\.?\s+)?\b(?:19|20)\d{2}\b|present\b|current\b|now\b)",
    re.I,
)
_BLIND_SUMMARY_SINGLE_YEAR_RE = re.compile(
    r"(?:\(\s*)?\b(?:19|20)\d{2}\b(?:\s*\))?",
    re.I,
)
_BLIND_SUMMARY_CATEGORY_RE = re.compile(
    r"^(?:summary|professional summary|executive summary|profile|professional profile|career profile|objective|career objective|overview|about(?:\s+him(?:\s*/\s*her)?|\s+her|\s+the\s+candidate)?)$",
    re.I,
)
_BLIND_SUMMARY_MARKER_RE = re.compile(
    r"^\s*(?:(?:[-*•●▪◦‣⁃∙·‧])+\s+|(?:\(?\d{1,3}[.)])\s+)"
)
_BLIND_SUMMARY_CONTEXT_NAME_RE = re.compile(
    r"\b(?i:client|customer|employer|company|organization|organisation|university|school|college|institution)"
    r"(?:[ \t]+(?i:named|called))?[ \t]*[:\-]?[ \t]+(?:(?i:the)[ \t]+)?"
    r"([A-Z][A-Za-z0-9&.'’\-]*(?:[ \t]+[A-Z][A-Za-z0-9&.'’\-]*){0,5})",
)
_BLIND_SUMMARY_BRAND_CONTEXT_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9&.'’\-]*(?:[ \t]+[A-Z][A-Za-z0-9&.'’\-]*){0,4})[ \t]+"
    r"(?:product|platform|solution|system|rollout|implementation|application|programme|program|project)\b",
)
_BLIND_SUMMARY_BRAND_TOKEN_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9]{3,})\b"
)
_BLIND_INSTITUTION_SUFFIX_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9&.'’\-]*(?:\s+[A-Za-z0-9&.'’\-]+){0,8}\s+"
    r"(?i:University|College|School|Institute|Polytechnic|Academy))\b"
)
_BLIND_INSTITUTION_PREFIX_RE = re.compile(
    r"\b((?i:University|College|School|Institute|Polytechnic|Academy)[ \t]+"
    r"(?:of[ \t]+)?[A-Z][A-Za-z0-9&.'’\-]*(?:[ \t]+[A-Za-z0-9&.'’\-]+){0,7})\b"
)
_BLIND_SUMMARY_ROLE_DESCRIPTOR_RE = re.compile(
    r"\b(?:manager|engineer|consultant|director|analyst|officer|developer|architect|"
    r"specialist|lead|head|executive|administrator|president|partner|coordinator|"
    r"supervisor|designer|accountant|recruiter|intern|associate|owner)\b",
    re.I,
)
_BLIND_SUMMARY_DEGREE_DESCRIPTOR_RE = re.compile(
    r"\b(?:bachelor|master|doctorate|doctoral|phd|diploma|degree|certificate|"
    r"foundation|a[- ]levels?|spm|stpm|mba|bsc|ba|msc|ma)\b",
    re.I,
)
_BLIND_INLINE_MARKDOWN_MARKERS = frozenset("*_`")


def _blind_identifier_pattern(value, *, case_sensitive_single=False):
    exact = str(value or "").strip()
    if not exact:
        return None
    flags = 0 if case_sensitive_single and not re.search(r"\s", exact) else re.I
    return re.compile(
        r"(?<![A-Za-z0-9])" + re.escape(exact) + r"(?![A-Za-z0-9])",
        flags,
    )


def _blind_replace_identifier(
    text, value, replacement, *, case_sensitive_single=False
):
    pattern = _blind_identifier_pattern(
        value, case_sensitive_single=case_sensitive_single
    )
    if pattern is None:
        return text
    out = str(text or "")
    # The Summary prompt deliberately asks providers to use Markdown bold.
    # Match the visible text too, otherwise **Jane** Example or
    # **Acme** Sdn Bhd bypasses exact identifier replacement.
    visible = []
    offsets = []
    for index, character in enumerate(out):
        if character in _BLIND_INLINE_MARKDOWN_MARKERS:
            continue
        visible.append(character)
        offsets.append(index)
    matches = list(pattern.finditer("".join(visible)))
    if not matches:
        # Preserve support for unusual literal identifiers that themselves
        # contain one of the Markdown marker characters.
        return pattern.sub(replacement, out)
    for match in reversed(matches):
        start = offsets[match.start()]
        end = offsets[match.end() - 1] + 1
        while start > 0 and out[start - 1] in _BLIND_INLINE_MARKDOWN_MARKERS:
            start -= 1
        while end < len(out) and out[end] in _BLIND_INLINE_MARKDOWN_MARKERS:
            end += 1
        out = out[:start] + replacement + out[end:]
    return out


def _blind_contains_identifier(text, value, *, case_sensitive_single=False):
    pattern = _blind_identifier_pattern(
        value, case_sensitive_single=case_sensitive_single
    )
    if pattern is None or pattern.search(str(text or "")):
        return pattern is not None
    visible = "".join(
        character
        for character in str(text or "")
        if character not in _BLIND_INLINE_MARKDOWN_MARKERS
    )
    return bool(pattern.search(visible))


def _blind_redact_phone_candidates(text):
    def replace(match):
        value = match.group(0)
        digits = re.sub(r"\D", "", value)
        # Preserve ordinary date ranges such as 2020 - 2023. Phone-like text
        # must carry a prefix, formatting, a recognised local shape, or nearby
        # contact wording. A long uninterrupted achievement metric is not a
        # phone number merely because it contains nine or more digits.
        if re.fullmatch(
            r"\s*(?:19|20)\d{2}\s*[-–—]\s*(?:19|20)\d{2}\s*",
            value,
        ):
            return value
        nearby = match.string[max(0, match.start() - 48):match.start()]
        if _BLIND_SUMMARY_PHONE_CONTEXT_RE.search(nearby):
            return "[Phone Redacted]"
        if not 8 <= len(digits) <= 15:
            return value
        if value.lstrip().startswith("+"):
            return "[Phone Redacted]"
        if (
            (digits.startswith("0") and 9 <= len(digits) <= 11)
            or (digits.startswith("60") and 10 <= len(digits) <= 12)
        ):
            return "[Phone Redacted]"
        grouped_metric = bool(
            re.fullmatch(r"\d{1,3}(?:(?:\s|\.)\d{3}){2,}", value.strip())
        )
        if grouped_metric:
            return value
        if re.search(r"[\s().-]", value):
            return "[Phone Redacted]"
        return value

    return _BLIND_SUMMARY_PHONE_CANDIDATE_RE.sub(replace, text)


def _blind_summary_plausible_identifier(value):
    text = re.sub(r"\s+", " ", str(value or "")).strip(" .,:;|-/")
    if not text or len(text) < 3:
        return ""
    low = text.casefold()
    if low in _BLIND_ORG_TECH_ALLOWLIST:
        return ""
    if low in {
        "candidate", "company", "client", "customer", "project", "programme",
        "program", "platform", "system", "solution", "university", "college",
        "school", "institution", "implementation", "current company",
    }:
        return ""
    tokens = re.findall(r"[A-Za-z0-9]+", text)
    safe_parts = {
        *(_BLIND_ORG_TECH_ALLOWLIST),
        "project", "system", "solution", "implementation", "application",
        "program", "programme", "management", "accounting", "finance",
        "controlling", "technology", "technologies", "engineering",
    }
    if tokens and all(token.casefold() in safe_parts for token in tokens):
        return ""
    if tokens and all(token.isupper() and len(token) <= 5 for token in tokens):
        return ""
    return text


def _blind_trim_org_match(value):
    """Remove sentence lead-ins accidentally consumed by the suffix regex."""
    clean = re.sub(r"\s+", " ", str(value or "")).strip(" .,:;|-/")
    clean = re.sub(
        r"^(?:Organization|Organisation|Company|Client|Employer|Project|Project Name|Current Company)\s*[:\-]\s*",
        "",
        clean,
        flags=re.I,
    ).strip()
    # The legal-suffix matcher intentionally accepts lower-case words inside a
    # company name, but that also lets it start at "Worked" or "Delivered".
    # Keep only the phrase following the final prose preposition.
    clean = re.sub(
        r"^.*\b(?:at|for|with|by|from)\s+(?=[A-Z0-9])",
        "",
        clean,
        flags=re.I,
    ).strip()
    return clean


def _blind_summary_context_replacements(text):
    replacements = []
    seen = set()

    def add(value, replacement="[Company]"):
        clean = _blind_summary_plausible_identifier(value)
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            replacements.append((clean, replacement, False))

    source = str(text or "")
    for match in _BLIND_SUMMARY_CONTEXT_NAME_RE.finditer(source):
        add(match.group(1))
    for match in _BLIND_SUMMARY_BRAND_CONTEXT_RE.finditer(source):
        add(match.group(1), "[Product]")
    for match in _BLIND_SUMMARY_BRAND_TOKEN_RE.finditer(source):
        token = match.group(1)
        low = token.casefold()
        has_brand_suffix = any(
            low.endswith(suffix) and len(low) - len(suffix) >= 3
            for suffix in (
                "tech", "core", "soft", "pay", "bank", "labs",
                "systems", "solutions", "digital", "global", "group",
            )
        )
        # Internal capitals alone are not a company signal: PowerBI,
        # JavaScript and NodeJS are ordinary technologies. Unknown brands are
        # still recovered from labels, dated employment lines, legal suffixes,
        # product contexts and the conservative brand suffixes below.
        if has_brand_suffix:
            add(token, "[Company]")
    for match in _BLIND_INSTITUTION_SUFFIX_RE.finditer(source):
        add(match.group(1), "[Institution]")
    for match in _BLIND_INSTITUTION_PREFIX_RE.finditer(source):
        add(match.group(1), "[Institution]")
    return replacements


def _blind_walk_strings(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _blind_walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _blind_walk_strings(v)
    elif isinstance(obj, str):
        yield obj


def _blind_summary_items(value, *, limit=20):
    values = value if isinstance(value, list) else str(value or "").splitlines()
    out = []
    for item in values:
        if not isinstance(item, str):
            continue
        clean = _BLIND_SUMMARY_MARKER_RE.sub("", item).strip()
        if clean:
            out.append(clean)
    return out if limit is None else out[:limit]


def _blind_prepare_summary_bullets(cv_data):
    """Promote source Summary/About content before the provider blinds it."""
    if not isinstance(cv_data, dict):
        return cv_data
    prepared = copy.deepcopy(cv_data)
    direct = _blind_summary_items(prepared.get("summary_bullets"), limit=None)
    skills = prepared.get("skills") if isinstance(prepared.get("skills"), list) else []
    promoted = []
    remaining = []
    for item in skills:
        if (
            isinstance(item, dict)
            and _BLIND_SUMMARY_CATEGORY_RE.fullmatch(
                str(item.get("category") or "").strip()
            )
        ):
            promoted.extend(_blind_summary_items(item.get("items"), limit=None))
        else:
            remaining.append(item)
    summary = direct or promoted
    if summary:
        prepared["summary_bullets"] = summary
        prepared["skills"] = remaining
    return prepared


def _blind_source_summary_text(original_cv):
    if not isinstance(original_cv, dict):
        return ""
    values = original_cv.get("summary_bullets")
    if not isinstance(values, list):
        return ""
    return "\n".join(value for value in values if isinstance(value, str))


def _blind_collect_summary_identity_replacements(original_cv):
    """Collect exact source identifiers that may not survive in a blind summary."""
    if not isinstance(original_cv, dict):
        return []
    replacements = []
    seen = set()

    def add(value, replacement, case_sensitive_single=False):
        exact = re.sub(r"\s+", " ", str(value or "")).strip(" .,:;|-/")
        key = exact.casefold()
        if len(exact) < 3 or key in seen:
            return
        seen.add(key)
        replacements.append((exact, replacement, case_sensitive_single))

    candidate = (
        original_cv.get("candidate")
        if isinstance(original_cv.get("candidate"), dict)
        else {}
    )
    candidate_name = str(candidate.get("name") or "").strip()
    if candidate_name.casefold() not in {"", "candidate", "the candidate", "[candidate]"}:
        add(candidate_name, "the candidate", True)
    add(candidate.get("email"), "[Email Redacted]")
    add(candidate.get("phone"), "[Phone Redacted]")
    add(candidate.get("linkedin"), "[Link Redacted]")

    for education in original_cv.get("education") or []:
        if isinstance(education, dict):
            add(education.get("institution"), "[Institution]", True)
    for term in _blind_collect_org_mask_terms(original_cv):
        add(term, "[Company]")
    for term, replacement, case_sensitive_single in _blind_summary_context_replacements(
        _blind_source_summary_text(original_cv)
    ):
        add(term, replacement, case_sensitive_single)

    return sorted(replacements, key=lambda item: -len(item[0]))


def _blind_summary_strip_name_honorifics(value):
    clean = re.sub(r"\s+", " ", str(value or "")).strip()
    clean = re.sub(r"^(?:tan\s+sri)\s+", "", clean, flags=re.I)
    honorifics = {
        "mr", "mrs", "ms", "miss", "mx", "dr", "prof", "professor",
        "ir", "ts", "dato", "datuk", "datin",
    }
    words = clean.split()
    while words and re.sub(r"[^\w]+", "", words[0], flags=re.UNICODE).casefold() in honorifics:
        words.pop(0)
    return " ".join(words)


def _blind_summary_name_word(value):
    token = str(value or "").strip()
    token = token.strip(".")
    if not token:
        return False
    if re.fullmatch(r"a/[pl]", token, re.I):
        return True
    parts = re.split(r"['’\-]", token)
    return all(part and part.isalpha() for part in parts)


def _blind_summary_lineage_name_variants(value):
    """Return compact and spaced Malaysian lineage spellings for one name."""
    original = re.sub(r"\s+", " ", str(value or "")).strip()
    if not original:
        return []
    compact = re.sub(
        r"\b([Aa])\s*/\s*([PpLl])\b",
        lambda match: "{}/{}".format(match.group(1), match.group(2)),
        original,
    )
    spaced = re.sub(
        r"\b([Aa])\s*/\s*([PpLl])\b",
        lambda match: "{} / {}".format(match.group(1), match.group(2)),
        original,
    )
    return list(dict.fromkeys((original, compact, spaced)))


def _blind_summary_bare_domain(value):
    """Return a source-derived bare domain while rejecting common file/code names."""
    candidate = str(value or "").rstrip(".,;:!?")
    host = candidate.split("/", 1)[0].rstrip(".")
    suffix = host.rsplit(".", 1)[-1].casefold() if "." in host else ""
    if (
        not suffix
        or suffix in _BLIND_SUMMARY_NON_DOMAIN_SUFFIXES
        or _BLIND_SUMMARY_DOTTED_DEGREE_RE.fullmatch(host)
    ):
        return ""
    return candidate


def _blind_redact_summary_urls(text):
    """Redact links without treating supported dotted degree names as URLs."""
    def replace(match):
        value = match.group(0)
        if re.match(r"(?:https?://|www\.)", value, re.I):
            return "[Link Redacted]"
        return "[Link Redacted]" if _blind_summary_bare_domain(value) else value

    return _BLIND_SUMMARY_URL_RE.sub(replace, str(text or ""))


def _blind_summary_candidate_name_from_text(source_text):
    lines = [
        _BLIND_SUMMARY_MARKER_RE.sub("", re.sub(r"\s+", " ", line)).strip()
        for line in str(source_text or "").splitlines()
        if str(line or "").strip()
    ]
    for line in lines[:30]:
        match = re.match(r"^(?:candidate\s+)?name\s*[:|]\s*(.+)$", line, re.I)
        if match:
            return _blind_summary_strip_name_honorifics(
                match.group(1).split("|", 1)[0]
            )

    excluded = {
        "about him her", "about the candidate", "summary", "professional summary",
        "profile", "professional profile", "curriculum vitae", "resume", "work experience",
        "work experiences", "education", "skills", "technical skills",
    }
    title_words = {
        "manager", "engineer", "consultant", "director", "analyst", "officer",
        "developer", "architect", "specialist", "lead", "head", "executive",
        "administrator", "president", "partner",
    }
    for original_line in lines[:8]:
        # CV headers commonly keep the name and contact fields on one pipe row.
        # Only inspect the first segment so the contact fields do not cause the
        # candidate-name detector to discard the entire header.
        line = _blind_summary_strip_name_honorifics(
            original_line.split("|", 1)[0]
        )
        if len(line) > 80 or any(value in line for value in ("@", "http://", "https://", ":")):
            continue
        validation_line = re.sub(
            r"\b([Aa])\s*/\s*([PpLl])\b",
            lambda match: "{}/{}".format(match.group(1), match.group(2)),
            line,
        )
        words = validation_line.split()
        if not 1 <= len(words) <= 6:
            continue
        if re.sub(r"[^a-z]+", " ", line.casefold()).strip() in excluded:
            continue
        if not all(_blind_summary_name_word(word) for word in words):
            continue
        if any(word.strip(".'’-,").casefold() in title_words for word in words):
            continue
        if len(words) == 1 and line != lines[0]:
            continue
        if all(
            word.isupper()
            or word[:1].isupper()
            or bool(re.fullmatch(r"a/[pl]", word, re.I))
            for word in words
        ):
            return line
    return ""


def _blind_summary_standalone_org_candidate(value):
    """Return a conservative employer candidate from a vertical CV row."""
    raw = re.sub(r"\s+", " ", str(value or "")).strip()
    if _BLIND_SUMMARY_MARKER_RE.match(raw):
        return ""
    line = raw
    if not line or len(line) > 80 or "|" in line or ":" in line:
        return ""
    if any(marker in line.casefold() for marker in ("@", "http://", "https://", "www.")):
        return ""
    if (
        _BLIND_SUMMARY_DATE_RANGE_RE.search(line)
        or _BLIND_SUMMARY_ROLE_DESCRIPTOR_RE.search(line)
        or _BLIND_SUMMARY_DEGREE_DESCRIPTOR_RE.search(line)
        or _BLIND_SUMMARY_STREET_MARKER_RE.search(line)
    ):
        return ""
    if re.search(r"[!?;]", line):
        return ""
    words = re.findall(r"[A-Za-z0-9&.'’\-]+", line)
    if not 1 <= len(words) <= 8 or not re.search(r"[A-Za-z]", line):
        return ""
    section_names = {
        "experience", "work experience", "employment history", "career history",
        "professional experience", "education", "skills", "technical skills",
        "responsibilities", "achievements", "projects", "project experience",
    }
    if line.casefold() in section_names or line.casefold() in _BLIND_ORG_TECH_ALLOWLIST:
        return ""
    connector_words = {"and", "of", "the", "for", "&"}
    if not all(
        word.casefold() in connector_words
        or word.isupper()
        or word[:1].isupper()
        for word in words
    ):
        return ""
    return line.strip(" .,:;|-/")


def _blind_summary_section_replacement(lines, index):
    """Classify a dated vertical row from its nearest preceding section."""
    education_sections = {
        "education", "education history", "academic background",
        "academic qualifications", "educational qualifications",
    }
    work_sections = {
        "experience", "work experience", "work experiences",
        "employment", "employment history", "work history", "career history",
        "professional experience", "career experience",
    }
    neutral_sections = {
        "qualifications", "professional qualifications", "certifications",
        "certificates", "training", "training courses", "courses", "skills",
        "technical skills", "core expertise", "projects", "project experience",
        "awards", "achievements",
    }
    for prior in range(index - 1, -1, -1):
        heading = re.sub(
            r"[^a-z]+",
            " ",
            str(lines[prior] or "").casefold(),
        ).strip()
        if heading in education_sections:
            return "[Institution]"
        if heading in work_sections:
            return "[Company]"
        if heading in neutral_sections:
            return None
    return "[Company]"


def _blind_summary_dated_line_identity(line):
    """Return an organization written on the same line as its employment date."""
    raw = re.sub(r"\s+", " ", str(line or "")).strip()
    has_date_range = bool(_BLIND_SUMMARY_DATE_RANGE_RE.search(raw))
    has_single_year = bool(_BLIND_SUMMARY_SINGLE_YEAR_RE.search(raw))
    if not (has_date_range or has_single_year) or "|" in raw:
        return ""
    without_date = _BLIND_SUMMARY_DATE_RANGE_RE.sub(" ", raw)
    without_date = _BLIND_SUMMARY_SINGLE_YEAR_RE.sub(" ", without_date)
    without_date = re.sub(r"[()\[\]{}]", " ", without_date)
    without_date = without_date.strip(" .,:;|-/–—")
    role_company = re.search(r"\b(?:at|for|with)\s+(.+)$", without_date, re.I)
    if role_company:
        candidate = _blind_summary_standalone_org_candidate(role_company.group(1))
        if candidate:
            return candidate
    without_date = re.sub(r"^(?:at|for|with)\s+", "", without_date, flags=re.I)
    return _blind_summary_standalone_org_candidate(without_date)


def _blind_summary_vertical_identity_replacements(lines):
    """Collect organizations beside dates with section-aware replacements."""
    identities = []
    cleaned = [re.sub(r"\s+", " ", str(line or "")).strip() for line in lines]
    for index, line in enumerate(cleaned):
        if not (
            _BLIND_SUMMARY_DATE_RANGE_RE.search(line)
            or _BLIND_SUMMARY_SINGLE_YEAR_RE.search(line)
        ):
            continue
        section_replacement = _blind_summary_section_replacement(cleaned, index)
        if section_replacement is None:
            continue
        pipe_value, pipe_replacement, _case_sensitive = _blind_summary_pipe_identity(line)
        if pipe_value:
            identities.append((pipe_value, pipe_replacement))
            continue
        same_line = _blind_summary_dated_line_identity(line)
        if same_line:
            identities.append((same_line, section_replacement))
            continue
        neighbor_indexes = (
            list(range(index - 1, max(-1, index - 3), -1))
            + list(range(index + 1, min(len(cleaned), index + 3)))
        )
        for neighbor_index in neighbor_indexes:
            candidate = _blind_summary_standalone_org_candidate(cleaned[neighbor_index])
            if candidate:
                identities.append((candidate, section_replacement))
                break
    return identities


def _blind_summary_vertical_org_identities(lines):
    """Compatibility wrapper returning only dated organization identities."""
    return [
        identity
        for identity, _replacement in _blind_summary_vertical_identity_replacements(lines)
    ]


def _blind_summary_pipe_identity(line):
    """Return the likely organization/institution from a dated pipe row."""
    parts = [part.strip() for part in str(line or "").split("|")]
    if len(parts) < 2:
        return "", "[Company]", False
    date_indexes = [
        index for index, part in enumerate(parts)
        if re.search(r"\b(?:19|20)\d{2}\b", part)
    ]
    if not date_indexes:
        return "", "[Company]", False
    date_index = date_indexes[0]
    if date_index == len(parts) - 1:
        candidate_indexes = list(range(date_index - 1, -1, -1))
    else:
        candidate_indexes = list(range(date_index + 1, len(parts)))
        candidate_indexes.extend(range(date_index - 1, -1, -1))
    value = ""
    for index in candidate_indexes:
        candidate = parts[index]
        if (
            not candidate
            or re.search(r"\b(?:19|20)\d{2}\b", candidate)
            or _BLIND_SUMMARY_ROLE_DESCRIPTOR_RE.search(candidate)
            or _BLIND_SUMMARY_DEGREE_DESCRIPTOR_RE.search(candidate)
        ):
            continue
        value = candidate
        break
    if not value:
        return "", "[Company]", False
    is_institution = bool(
        _BLIND_INSTITUTION_SUFFIX_RE.search(value)
        or _BLIND_INSTITUTION_PREFIX_RE.search(value)
        or any(_BLIND_SUMMARY_DEGREE_DESCRIPTOR_RE.search(part) for part in parts)
    )
    return (
        value,
        "[Institution]" if is_institution else "[Company]",
        is_institution,
    )


def _blind_collect_plain_summary_identity_replacements(source_text):
    """Collect conservative identity terms from an unparsed CV summary source."""
    source = str(source_text or "")
    replacements = []
    seen = set()

    def add(value, replacement="[Company]", case_sensitive_single=False):
        exact = re.sub(r"\s+", " ", str(value or "")).strip(" .,:;|-/")
        key = exact.casefold()
        if len(exact) < 3 or key in seen:
            return
        seen.add(key)
        replacements.append((exact, replacement, case_sensitive_single))

    candidate_name = _blind_summary_candidate_name_from_text(source)
    for name_variant in _blind_summary_lineage_name_variants(candidate_name):
        add(name_variant, "the candidate", True)
    label_pattern = re.compile(
        r"^(current\s+company|company|employer|client|customer|organization|organisation|institution|university|school|college)\s*[:|]\s*(.+)$",
        re.I,
    )
    institution_labels = {"institution", "university", "school", "college"}
    source_lines = source.splitlines()
    for line_index, raw_line in enumerate(source_lines):
        line = re.sub(r"\s+", " ", raw_line).strip()
        address_match = _BLIND_SUMMARY_ADDRESS_LINE_RE.match(line)
        if address_match:
            address_value = address_match.group(1).strip()
            add(address_value, "[Address Redacted]", True)
            street_value = address_value.split(",", 1)[0].strip()
            if re.search(r"\d", street_value) and _BLIND_SUMMARY_STREET_MARKER_RE.search(street_value):
                add(street_value, "[Address Redacted]", True)
        elif (
            _BLIND_SUMMARY_UNLABELED_ADDRESS_RE.match(line)
            and _BLIND_SUMMARY_STREET_MARKER_RE.search(line)
        ):
            add(line, "[Address Redacted]", True)
            add(line.split(",", 1)[0].strip(), "[Address Redacted]", True)
        for phone_match in _BLIND_SUMMARY_PHONE_CANDIDATE_RE.finditer(line):
            phone_value = phone_match.group(0).strip()
            phone_digits = re.sub(r"\D", "", phone_value)
            prefix = line[:phone_match.start()]
            is_labeled = bool(_BLIND_SUMMARY_PHONE_CONTEXT_RE.search(prefix))
            is_early_standalone = (
                line_index < 12
                and phone_match.start() == 0
                and phone_match.end() == len(line)
                and not _BLIND_SUMMARY_DATE_RANGE_RE.fullmatch(line)
            )
            if 8 <= len(phone_digits) <= 15 and (
                is_labeled or is_early_standalone
            ):
                add(phone_value, "[Phone Redacted]", True)
        for domain_match in _BLIND_SUMMARY_BARE_DOMAIN_RE.finditer(line):
            domain_value = _blind_summary_bare_domain(domain_match.group(0))
            if domain_value:
                add(domain_value, "[Link Redacted]")
                domain_host = domain_value.split("/", 1)[0].rstrip(".")
                if domain_host != domain_value:
                    add(domain_host, "[Link Redacted]")
        match = label_pattern.match(line)
        if match:
            label = match.group(1).casefold()
            value = re.split(r"\s+\|\s+", match.group(2), maxsplit=1)[0].strip()
            add(value, "[Institution]" if label in institution_labels else "[Company]", True)
        value, replacement, case_sensitive = _blind_summary_pipe_identity(line)
        add(value, replacement, case_sensitive)
        for suffix_match in _BLIND_ORG_SUFFIX_RE.finditer(line):
            add(_blind_trim_org_match(suffix_match.group(1)), "[Company]")
        for suffix_match in _BLIND_INSTITUTION_SUFFIX_RE.finditer(line):
            add(suffix_match.group(1), "[Institution]", True)
        for prefix_match in _BLIND_INSTITUTION_PREFIX_RE.finditer(line):
            add(prefix_match.group(1), "[Institution]", True)

    for identity, replacement in _blind_summary_vertical_identity_replacements(
        source_lines
    ):
        add(identity, replacement, True)

    compact = re.sub(r"\s+", " ", source)
    for name in _BLIND_CURATED_ORG_NAMES:
        if name.casefold() in _BLIND_ORG_TECH_ALLOWLIST:
            continue
        if _blind_identifier_pattern(name).search(compact):
            add(name, "[Company]")
    for term, replacement, case_sensitive_single in _blind_summary_context_replacements(source):
        add(term, replacement, case_sensitive_single)

    return sorted(replacements, key=lambda item: -len(item[0]))


def _blind_apply_summary_replacements(text, replacements):
    safe = _BLIND_SUMMARY_MARKER_RE.sub("", str(text or "")).strip()
    # Redact explicit links before exact source identifiers so a provider that
    # adds ``https://`` to a source bare domain cannot leave a malformed partial
    # link such as ``https://[Link Redacted]`` for the later pass.
    safe = _BLIND_SUMMARY_EMAIL_RE.sub("[Email Redacted]", safe)
    safe = _blind_redact_summary_urls(safe)
    for source_value, replacement, case_sensitive_single in replacements:
        safe = _blind_replace_identifier(
            safe,
            source_value,
            replacement,
            case_sensitive_single=case_sensitive_single,
        )
    safe = _BLIND_SUMMARY_EMAIL_RE.sub("[Email Redacted]", safe)
    safe = _blind_redact_summary_urls(safe)
    safe = _blind_redact_phone_candidates(safe)
    safe = _BLIND_SUMMARY_INLINE_ADDRESS_RE.sub("[Address Redacted]", safe)
    return safe


def _blind_generated_summary_items(raw_text):
    raw = re.sub(r"```(?:text|markdown|md)?", "", str(raw_text or ""), flags=re.I)
    raw = raw.replace("```", "").strip()
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    marked = [line for line in lines if _BLIND_SUMMARY_MARKER_RE.match(line)]
    return _blind_summary_items(marked or lines)


def _blind_finalize_generated_summary_text(raw_text, source_text):
    """Fail closed and scrub the standalone anonymized-summary response."""
    if not str(source_text or "").strip():
        raise ValueError("Anonymized CV Summary requires the unchanged source CV")
    bullets = _blind_generated_summary_items(raw_text)
    if not bullets:
        raise ValueError("Anonymized CV Summary returned no usable bullets")
    replacements = _blind_collect_plain_summary_identity_replacements(source_text)
    safe_bullets = []
    for bullet in bullets:
        safe = _blind_apply_summary_replacements(bullet, replacements)
        if not safe:
            raise ValueError("Anonymized CV Summary returned an empty bullet")
        for source_value, _replacement, case_sensitive_single in replacements:
            if _blind_contains_identifier(
                safe,
                source_value,
                case_sensitive_single=case_sensitive_single,
            ):
                raise ValueError(
                    "Anonymized CV Summary still contains a source identifier"
                )
        safe_bullets.append(safe)
    return "\n".join("- " + bullet for bullet in safe_bullets)


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
        candidate = _blind_trim_org_match(m.group(1))
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


def _blind_finalize_summary_bullets(blinded, original_cv):
    """Preserve a populated blinded summary and scrub direct candidate PII."""
    if not isinstance(blinded, dict) or not isinstance(original_cv, dict):
        return blinded
    source = original_cv.get("summary_bullets")
    source_bullets = (
        [value.strip() for value in source if isinstance(value, str) and value.strip()]
        if isinstance(source, list)
        else []
    )
    if not source_bullets:
        return blinded
    output = blinded.get("summary_bullets")
    if not isinstance(output, list):
        raise ValueError("Blind CV could not preserve the About Him / Her summary")
    output_bullets = []
    for value in output:
        if not isinstance(value, str):
            raise ValueError("Blind CV returned an invalid About Him / Her summary")
        clean = _BLIND_SUMMARY_MARKER_RE.sub("", value).strip()
        if not clean:
            raise ValueError("Blind CV returned an invalid About Him / Her summary")
        output_bullets.append(clean)
    if len(output_bullets) != len(source_bullets):
        raise ValueError("Blind CV could not preserve every About Him / Her summary bullet")

    direct_replacements = _blind_collect_summary_identity_replacements(original_cv)
    safe_bullets = []
    for bullet in output_bullets:
        safe = _blind_apply_summary_replacements(bullet, direct_replacements)
        for source_value, _replacement, case_sensitive_single in direct_replacements:
            if _blind_contains_identifier(
                safe,
                source_value,
                case_sensitive_single=case_sensitive_single,
            ):
                raise ValueError(
                    "Blind CV About Him / Her summary still contains a source identifier"
                )
        safe_bullets.append(safe)

    repaired = copy.deepcopy(blinded)
    repaired["summary_bullets"] = safe_bullets
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
