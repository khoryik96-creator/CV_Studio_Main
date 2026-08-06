"""Pure CV data-normalization helpers (Phase 7B-6c).

Behaviour-preserving extraction of the stateless CV/candidate data
normalisers from the legacy web shell: smart title/word casing, work-history
date-range normalisation, candidate-language canonicalisation, and CV bullet /
structured-content / output normalisation, together with the lookup tables and
compiled patterns they depend on.

Pure functions and module-level data only - no Flask, no globals mutated at
runtime, no network. This module never imports ``app``.
"""

import re
import json
from datetime import date


_MONTH_ABBR = {
    "jan": "Jan", "january": "Jan",
    "feb": "Feb", "february": "Feb",
    "mar": "Mar", "march": "Mar",
    "apr": "Apr", "april": "Apr",
    "may": "May",
    "jun": "Jun", "june": "Jun",
    "jul": "Jul", "july": "Jul",
    "aug": "Aug", "august": "Aug",
    "sep": "Sep", "sept": "Sep", "september": "Sep",
    "oct": "Oct", "october": "Oct",
    "nov": "Nov", "november": "Nov",
    "dec": "Dec", "december": "Dec",
}


# Number -> house-style month abbreviation, so numeric "MM/YYYY" dates (which
# some parse runs emit instead of "Mon YYYY") are normalised to the same style.
_MONTH_ABBR_BY_NUMBER = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}


def _numeric_month_year_repl(match):
    """Convert a numeric MM/YYYY (or M/YYYY) token to house-style "Mon YYYY".

    A month outside 1-12 is left untouched (it is not a month/year token).
    """
    month = int(match.group(1))
    if 1 <= month <= 12:
        return f"{_MONTH_ABBR_BY_NUMBER[month]} {match.group(2)}"
    return match.group(0)


_COMPANY_TOKEN_MAP = {
    "SDN": "Sdn", "BHD": "Bhd", "PTE": "Pte", "LTD": "Ltd", "LMT": "Lmt",
    "PVT": "Pvt", "INC": "Inc", "LLC": "LLC", "LLP": "LLP", "PLC": "PLC",
    "CORP": "Corp", "CO": "Co", "COMPANY": "Company", "TECH": "Tech",
}


_COMPANY_BRAND_TOKEN_MAP = {
    "IFAST": "iFAST",
    "GRABPAY": "GrabPay",
    "DATAIKU": "Dataiku",
    "YOUTUBE": "YouTube",
}


_ACRONYM_KEEP = {
    "AI", "ML", "BI", "IT", "HR", "QA", "UA", "UX", "UI", "PMO", "PM",
    "AWS", "GCP", "SQL", "ETL", "ELT", "SSIS", "SSRS", "SSAS", "ADF", "DBA",
    "RDS", "EMR", "EC2", "S3", "IAM", "API", "APAC", "SEA", "ERP", "SAP", "FICO",
    "MSBI", "MSC", "IBM", "CGI", "EPAM", "TCS", "HP", "HSBC", "DBS", "OCBC",
    "UOB", "AIA", "IHH", "RHB", "CIMB", "EY", "KPMG", "PWC", "BNM", "AML",
}


_TITLE_TOKEN_MAP = {
    "SR": "Sr", "SR.": "Sr.", "JR": "Jr", "JR.": "Jr.", "VP": "VP", "AVP": "AVP",
}


def _smart_word_case(token, *, company=False, title=False):
    if token is None:
        return ""
    raw = str(token)
    if not raw:
        return raw
    stripped = re.sub(r"[^A-Za-z0-9&.+#]", "", raw)
    upper = stripped.upper()
    if not stripped:
        return raw
    if company and upper in _COMPANY_BRAND_TOKEN_MAP:
        replacement = _COMPANY_BRAND_TOKEN_MAP[upper]
    elif company and stripped.isalpha() and any(ch.islower() for ch in stripped) and any(ch.isupper() for ch in stripped) and not (stripped[:1].isupper() and stripped[1:].islower()):
        # Preserve brand-like mixed-case tokens such as iFAST, GrabPay,
        # YouTube, Dataiku, McKinsey. These should not become Ifast/Grabpay.
        replacement = stripped
    elif company and upper in _COMPANY_TOKEN_MAP:
        replacement = _COMPANY_TOKEN_MAP[upper]
    elif title and upper in _TITLE_TOKEN_MAP:
        replacement = _TITLE_TOKEN_MAP[upper]
    elif upper in _ACRONYM_KEEP or (len(upper) <= 3 and upper == stripped and stripped.isalpha()):
        replacement = upper
    else:
        # Preserve internal separators by title-casing alphabetic chunks only.
        def repl(m):
            w = m.group(0)
            return w[:1].upper() + w[1:].lower()
        replacement = re.sub(r"[A-Za-z]+", repl, raw.lower())
        return replacement
    # Put any punctuation around the token back in place.
    start = raw.find(stripped)
    if start >= 0:
        return raw[:start] + replacement + raw[start + len(stripped):]
    return replacement


def _smart_title_text(value, *, company=False, title=False):
    text = str(value or "").strip()
    if not text:
        return ""
    # Only normalize aggressively when the source is mostly uppercase. Mixed-case
    # names like "McKinsey", "iFAST", "GrabPay", or "Dataiku" are kept intact.
    letters = re.findall(r"[A-Za-z]", text)
    uppercase_ratio = (sum(1 for ch in letters if ch.isupper()) / len(letters)) if letters else 0
    if uppercase_ratio < 0.72:
        # Mixed-case company names should mostly stay intact, but corporate suffixes
        # often arrive as ALL CAPS from source tables (e.g. "MSC SDN BHD"). Normalize
        # only known tokens/acronyms so "Virtual Calibre MSC SDN BHD" becomes
        # "Virtual Calibre MSC Sdn Bhd" without disturbing names like iFAST/Dataiku.
        if company:
            parts = re.split(r"(\s+|/|\||,|;|\(|\)|\[|\])", text)
            def fix_company_part(part):
                if not part or part.isspace() or re.fullmatch(r"/|\||,|;|\(|\)|\[|\]", part):
                    return part
                stripped = re.sub(r"[^A-Za-z0-9&.+#]", "", part)
                upper = stripped.upper()
                if upper in _COMPANY_BRAND_TOKEN_MAP or upper in _COMPANY_TOKEN_MAP or upper in _ACRONYM_KEEP:
                    return _smart_word_case(part, company=True)
                # Source tables often mix Title Case with stray lowercase company
                # words (e.g. "Balrath outsourcing Service"). Normalize fully
                # lowercase words, but keep brand-like mixed-case tokens such as
                # iFAST, GrabPay, Dataiku, YouTube, etc. intact.
                if stripped.isalpha() and stripped == stripped.lower() and len(stripped) > 2:
                    return _smart_word_case(part, company=True)
                return part
            return "".join(fix_company_part(part) for part in parts).strip()
        if title:
            # Still fix common all-caps title tokens embedded in otherwise mixed text.
            text = re.sub(r"\bSR\.?\b", "Sr.", text)
            text = re.sub(r"\bJR\.?\b", "Jr.", text)
        return text
    parts = re.split(r"(\s+|/|\||,|;|\(|\)|\[|\])", text)
    return "".join(_smart_word_case(part, company=company, title=title) if part and not part.isspace() and not re.fullmatch(r"/|\||,|;|\(|\)|\[|\]", part) else part for part in parts).strip()


def _normalize_month_token(m):
    return _MONTH_ABBR.get(str(m or "").strip().lower().rstrip('.'), str(m or "").strip())


def _normalize_cv_date_range(value):
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    text = re.sub(r"\b(till\s*date|till\s*now|to\s*date|current|presently|now)\b", "Present", text, flags=re.I)
    text = re.sub(r"\bpresent\b", "Present", text, flags=re.I)
    # Convert source separators to the house style "to".
    text = re.sub(r"\s*-\s*", " to ", text)
    text = re.sub(r"\s+to\s+", " to ", text, flags=re.I)
    # Normalize month words/abbreviations only inside date fields.
    def month_repl(m):
        return _normalize_month_token(m.group(0))
    text = re.sub(r"\b(January|February|March|April|June|July|August|September|Sept|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\b", month_repl, text, flags=re.I)
    # Numeric MM/YYYY -> "Mon YYYY" so date format is consistent regardless of
    # whether a given parse run emitted "06/2024" or "Jun 2024".
    text = re.sub(r"\b(\d{1,2})/(\d{4})\b", _numeric_month_year_repl, text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


_CV_REDACTED_LANGUAGE_RE = re.compile(
    r"(?:\bredacted\b|\bmasked\b|\bwithheld\b|\bhidden\b|\bconfidential\b|\bnot\s+disclosed\b|\bundisclosed\b|\bremoved\b|\[\s*(?:redacted|masked|withheld|hidden|confidential|removed)\s*\]|\*{3,}|x{3,}|█{2,}|#{3,})",
    re.I,
)


_CV_LANGUAGE_STANDARD_ORDER = ["English", "Bahasa Malaysia", "Chinese"]


_CV_LANGUAGE_ALIASES = {
    "English": ["english", "eng"],
    "Bahasa Malaysia": ["bahasa malaysia", "bahasa melayu", "malay language", "malay", "bm"],
    "Chinese": [
        "chinese", "mandarin", "putonghua", "hua yu", "huayu", "cantonese", "yue",
        "hokkien", "hakka", "teochew", "teo chew", "foochow", "fuzhou",
        "hainanese", "shanghainese", "min nan", "minnan", "taiwanese hokkien"
    ],
    "Tamil": ["tamil"],
    "Hindi": ["hindi"],
    "Japanese": ["japanese", "nihongo"],
    "Korean": ["korean"],
    "Thai": ["thai"],
    "Vietnamese": ["vietnamese"],
    "Indonesian": ["bahasa indonesia", "indonesian"],
    "Filipino": ["filipino", "tagalog"],
    "Arabic": ["arabic"],
    "French": ["french"],
    "German": ["german"],
    "Spanish": ["spanish"],
    "Portuguese": ["portuguese"],
    "Italian": ["italian"],
    "Dutch": ["dutch"],
    "Russian": ["russian"],
    "Kurdish": ["kurdish"],
    "Bengali": ["bengali", "bangla"],
    "Punjabi": ["punjabi"],
    "Urdu": ["urdu"],
    "Nepali": ["nepali"],
    "Burmese": ["burmese", "myanmar"],
    "Khmer": ["khmer", "cambodian"],
    "Lao": ["lao", "laotian"],
}


_CV_LANGUAGE_ALIAS_TO_STANDARD = {}


def _cv_lang_alias_re(alias):
    alias = str(alias or "").strip()
    if not alias:
        return None
    return re.compile(r"(?<![A-Za-z])" + re.escape(alias).replace(r"\ ", r"\s+") + r"(?![A-Za-z])", re.I)


def _split_candidate_language_names(value):
    """Return candidate language tokens stripped of proficiency wording.

    Providers often return values with proficiency levels, slashes, semicolons,
    bullets, or explanations. Keep only candidate-stated language tokens.
    """
    text = str(value or "").strip()
    if not text:
        return []
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"\b(?:native|fluent|professional|business|conversational|basic|intermediate|advanced|written|spoken|read|write|speaking|reading|writing|mother tongue|proficient|bilingual|trilingual|multilingual|language|languages)\b", "", text, flags=re.I)
    # Split on separators and common connector words. This intentionally splits
    # Mandarin/Cantonese into two tokens; both collapse back to Chinese.
    parts = re.split(r"[,;|/\n]+|\s+(?:and|or|plus|&)\s+", text, flags=re.I)
    out = []
    for part in parts:
        name = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ\s\-]", " ", part).strip()
        name = re.sub(r"\s+", " ", name)
        if name:
            out.append(name)
    return out


def _canonical_language_name(name):
    raw = re.sub(r"\s+", " ", str(name or "").strip())
    if not raw:
        return ""
    low = raw.lower().replace("_", "-")
    low = re.sub(r"\s+", " ", low).strip(" -")

    # First match exact aliases, then phrase aliases (for values like Mandarin Chinese).
    if low in _CV_LANGUAGE_ALIAS_TO_STANDARD:
        return _CV_LANGUAGE_ALIAS_TO_STANDARD[low]
    for alias, standard in sorted(_CV_LANGUAGE_ALIAS_TO_STANDARD.items(), key=lambda kv: len(kv[0]), reverse=True):
        rx = _cv_lang_alias_re(alias)
        if rx and rx.search(low):
            return standard

    # Conservative title-case fallback for less common languages that are already
    # named by the candidate/AI.
    return " ".join(w[:1].upper() + w[1:].lower() for w in low.split())


def _language_evidence_text(cv_text):
    text = str(cv_text or "")
    if not text.strip():
        return ""
    chunks = []
    lines = [ln.strip() for ln in re.split(r"\r?\n", text) if ln.strip()]
    for i, line in enumerate(lines):
        if re.search(r"\blanguages?\b|\blinguistic\b|\bspoken\b|\bfluent\b|\bproficient\b|\bbilingual\b|\btrilingual\b|\bmultilingual\b|\bmother tongue\b", line, re.I):
            chunks.extend(lines[i:i+4])
        elif re.search(r"\b(?:speak|speaks|speaking|read|reads|reading|write|writes|writing|communicat(?:e|es|ing)|correspond(?:ence|s|ing))\b", line, re.I):
            chunks.append(line)
    # Also catch compact resume sections like "Languages: English, Malay" within paragraphs.
    for m in re.finditer(r"\blanguages?\s*[:\-]", text, flags=re.I):
        chunks.append(text[m.start():m.start()+500])
    return "\n".join(chunks)


def _language_has_source_evidence(standard, cv_text):
    # If no source text is available (e.g. export of already parsed data), normalize
    # names but do not delete. Parse routes pass source text and are strict.
    if not str(cv_text or "").strip():
        return True
    evidence = _language_evidence_text(cv_text)
    if not evidence.strip():
        return False
    aliases = _CV_LANGUAGE_ALIASES.get(standard, [standard])
    return any((_cv_lang_alias_re(alias) and _cv_lang_alias_re(alias).search(evidence)) for alias in aliases)


def _normalize_candidate_language_value(value, cv_text=""):
    if _CV_REDACTED_LANGUAGE_RE.search(str(value or "")):
        return ""
    standards = []
    for token in _split_candidate_language_names(value):
        std = _canonical_language_name(token)
        if not std:
            continue
        if not _language_has_source_evidence(std, cv_text):
            continue
        if std not in standards:
            standards.append(std)
    if not standards:
        return ""

    def sort_key(lang):
        try:
            return (_CV_LANGUAGE_STANDARD_ORDER.index(lang), lang)
        except ValueError:
            return (len(_CV_LANGUAGE_STANDARD_ORDER), lang.lower())

    return ", ".join(sorted(standards, key=sort_key))


def _normalize_candidate_languages(parsed, cv_text=""):
    if not isinstance(parsed, dict):
        return parsed
    cand = parsed.get("candidate") or {}
    if not isinstance(cand, dict):
        return parsed
    raw = cand.get("languages")
    if raw:
        cand["languages"] = _normalize_candidate_language_value(raw, cv_text)
        parsed["candidate"] = cand
    return parsed


_CV_SECTION_HEADING_RE = re.compile(
    r"^\s*(?:key\s+)?(responsibilit(?:y|ies)|achievements?)\s*:?\s*$",
    re.I,
)


_CV_INFERRED_TITLE_SUFFIX_RE = re.compile(
    r"\s*[\[(]\s*(?:inferred|implied|assumed|guessed|likely)\s+(?:from|based\s+on)\s+"
    r"(?:responsibilit(?:y|ies)|duties|job\s+content|role\s+content|context)\s*[\])]\s*$",
    re.I,
)


def _strip_cv_inferred_title(value):
    text = str(value or "").strip()
    return "" if _CV_INFERRED_TITLE_SUFFIX_RE.search(text) else text


def _canonical_cv_section_heading(value):
    text = str(value or "").strip()
    match = _CV_SECTION_HEADING_RE.fullmatch(text)
    if not match:
        return text
    return "Key achievements" if match.group(1).lower().startswith("achievement") else "Key responsibilities"


def _normalize_cv_bullet_items(items, allow_standalone_sections=True):
    """Repair valid JSON-looking bullet strings without changing plain prose."""
    source = items if isinstance(items, list) else ([] if items in (None, "") else [items])
    normalized = []

    def add(item):
        if isinstance(item, str):
            candidate = item.strip()
            section_heading = _canonical_cv_section_heading(candidate)
            if allow_standalone_sections and candidate and _CV_SECTION_HEADING_RE.fullmatch(candidate):
                normalized.append({"heading": section_heading, "bullets": [], "kind": "section"})
                return
            if candidate and candidate[0] in "[{" and candidate[-1] in "]}":
                try:
                    decoded = json.loads(candidate)
                except (TypeError, ValueError, json.JSONDecodeError):
                    decoded = None
                if isinstance(decoded, (dict, list)):
                    before = len(normalized)
                    add(decoded)
                    if len(normalized) == before:
                        normalized.append(item)
                    return
            if candidate:
                normalized.append(item)
            return
        if isinstance(item, list):
            for child in item:
                add(child)
            return
        if not isinstance(item, dict):
            if item is not None and str(item).strip():
                normalized.append(str(item))
            return

        heading = _canonical_cv_section_heading(item.get("heading") or item.get("title") or "")
        bullets = _normalize_cv_bullet_items(
            item.get("bullets") or item.get("items") or [],
            allow_standalone_sections=False,
        )
        if heading:
            group = {"heading": heading, "bullets": bullets}
            kind = str(item.get("kind") or "").strip()
            if kind:
                group["kind"] = kind
            elif _CV_SECTION_HEADING_RE.fullmatch(str(item.get("heading") or item.get("title") or "")):
                group["kind"] = "section"
            normalized.append(group)
            return
        for bullet in bullets:
            add(bullet)

    for value in source:
        add(value)
    return normalized


def _normalize_cv_structured_content(parsed):
    """Idempotently repair role bullets, inferred-title annotations and blanks."""
    if not isinstance(parsed, dict):
        return parsed
    candidate = parsed.get("candidate")
    if isinstance(candidate, dict):
        candidate["current_position"] = _strip_cv_inferred_title(candidate.get("current_position"))
    for exp in parsed.get("work_experiences") or []:
        if not isinstance(exp, dict):
            continue
        for role in exp.get("roles") or []:
            if not isinstance(role, dict):
                continue
            role["title"] = _strip_cv_inferred_title(role.get("title"))
            role["bullets"] = _normalize_cv_bullet_items(role.get("bullets"))
    certifications = parsed.get("certifications") or []
    if not isinstance(certifications, list):
        certifications = [certifications]
    parsed["certifications"] = [
        value for value in certifications
        if str(value or "").strip()
    ]
    skills = parsed.get("skills") or []
    if not isinstance(skills, list):
        skills = []
    parsed["skills"] = [
        value for value in skills
        if isinstance(value, dict)
        and (str(value.get("category") or "").strip() or str(value.get("items") or "").strip())
    ]
    return parsed


def _normalize_cv_data_for_output(parsed, source_text=""):
    """Normalize structured CV data for preview and DOCX export."""
    if not isinstance(parsed, dict):
        return parsed
    parsed = _normalize_cv_structured_content(parsed)
    cand = parsed.get("candidate") or {}
    if isinstance(cand, dict):
        if cand.get("current_company"):
            cand["current_company"] = _smart_title_text(cand.get("current_company"), company=True)
        if cand.get("current_position"):
            cand["current_position"] = _smart_title_text(cand.get("current_position"), title=True)
        if cand.get("languages"):
            cand["languages"] = _normalize_candidate_language_value(cand.get("languages"), source_text)
        parsed["candidate"] = cand
    for exp in parsed.get("work_experiences") or []:
        if not isinstance(exp, dict):
            continue
        if exp.get("date_range"):
            exp["date_range"] = _normalize_cv_date_range(exp.get("date_range"))
        if exp.get("company"):
            exp["company"] = _smart_title_text(exp.get("company"), company=True)
        roles = exp.get("roles") or []
        if isinstance(roles, list):
            for role in roles:
                if not isinstance(role, dict):
                    continue
                if role.get("date_range"):
                    role["date_range"] = _normalize_cv_date_range(role.get("date_range"))
                if role.get("title"):
                    role["title"] = _smart_title_text(role.get("title"), title=True)
    for edu in parsed.get("education") or []:
        if isinstance(edu, dict) and edu.get("date_range"):
            edu["date_range"] = _normalize_cv_date_range(edu.get("date_range"))
    return parsed


_WORK_TABLE_DATE_RE = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{4}\b|\b\d{4}\b",
    re.I,
)


_CV_ROLE_DENSE_MARKER_RE = re.compile(
    r"^\s*(?:[ivxlcdm]+[.)]\s*)?(?:key\s+)?(?:responsibilit(?:y|ies)|achievements?)\s*:?\s*$",
    re.I | re.M,
)


def _cv_parse_backend_timeout_seconds(cv_text):
    """Return the bounded provider timeout for one CV parse request."""
    text = str(cv_text or "")
    is_long = len(text) >= 18000 or len(_CV_ROLE_DENSE_MARKER_RE.findall(text)) >= 8
    return 300 if is_long else 180


def _cv_match_key(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _cv_token_set(value):
    stop = {"the", "and", "of", "a", "an", "company", "technologies", "technology", "solution", "solutions", "sdn", "bhd", "pte", "ltd", "pvt", "inc", "llc", "llp", "corp", "co"}
    return {t for t in re.findall(r"[a-z0-9]+", str(value or "").lower()) if t and t not in stop}


def _cv_token_overlap_score(a, b):
    aa = _cv_token_set(a)
    bb = _cv_token_set(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / max(len(aa), len(bb))


def _cv_date_parts(date_range):
    text = _normalize_cv_date_range(date_range)
    if not text:
        return "", ""
    parts = re.split(r"\s+to\s+", text, maxsplit=1, flags=re.I)
    if len(parts) == 1:
        return parts[0].strip(), ""
    return parts[0].strip(), parts[1].strip()


def _cv_combine_date_ranges(date_ranges):
    """Combine role date ranges from newest-first source rows into one span."""
    cleaned = [_normalize_cv_date_range(d) for d in (date_ranges or []) if str(d or "").strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    newest_start, newest_end = _cv_date_parts(cleaned[0])
    oldest_start, oldest_end = _cv_date_parts(cleaned[-1])
    end = newest_end or newest_start
    start = oldest_start or newest_start
    if not start:
        return cleaned[0]
    if not end:
        end = "Present" if any("present" in d.lower() for d in cleaned) else (newest_end or newest_start)
    return f"{start} to {end}".strip()


def _cv_company_span_from_roles(roles):
    """Recompute an employer's overall date range from its roles' ranges.

    Returns "<earliest start> to <latest end>" derived from the role with the
    earliest start and the role with the latest end, so a company header can
    never be backwards (e.g. "Jan 2020 to Dec 2019") or truncated relative to
    the roles shown beneath it. Returns "" when no role carries a parseable
    date, so callers only override the provided company date when the roles
    actually supply one.
    """
    best_start = None  # (sort_point, display_text)
    best_end = None
    for role in roles or []:
        if not isinstance(role, dict):
            continue
        rng = _normalize_cv_date_range(role.get("date_range") or "")
        if not rng:
            continue
        start_text, end_text = _cv_date_parts(rng)
        start_point = _cv_date_sort_point(start_text or rng, end=False)
        end_blob = end_text or start_text or rng
        end_point = _cv_date_sort_point(end_blob, end=True)
        if start_point is not None and (best_start is None or start_point < best_start[0]):
            best_start = (start_point, start_text or rng)
        if end_point is not None and (best_end is None or end_point > best_end[0]):
            best_end = (end_point, end_blob)
    if best_start is None and best_end is None:
        return ""
    start = best_start[1] if best_start else best_end[1]
    end = best_end[1] if best_end else best_start[1]
    if start == end:
        return start
    return f"{start} to {end}".strip()


_CV_MONTH_NUMBER = {
    "jan": 1, "january": 1, "feb": 2, "february": 2,
    "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5,
    "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def _cv_date_sort_point(value, end=False):
    """Return a sortable (year, month) point from a CV date/range fragment."""
    text = str(value or "").strip()
    if not text:
        return None
    if re.search(r"\b(?:present|current|now|till\s*date|to\s*date)\b", text, re.I):
        return (9999, 12)
    # Numeric MM/YYYY carries the month too; normalise to "Mon YYYY" first so a
    # date like "06/2024" sorts at month granularity, not just its year.
    text = re.sub(r"\b(\d{1,2})/(\d{4})\b", _numeric_month_year_repl, text)
    matches = list(re.finditer(
        r"\b(?:(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+)?(\d{4})\b",
        text,
        re.I,
    ))
    if not matches:
        return None
    match = matches[-1] if end else matches[0]
    month_text = (match.group(1) or "").lower().rstrip(".")
    month = _CV_MONTH_NUMBER.get(month_text, 12 if end else 1)
    return (int(match.group(2)), month)


def _cv_plain_bullet_texts(items):
    out = []
    for item in items or []:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            for sub in item.get("bullets") or []:
                if isinstance(sub, str):
                    out.append(sub)
    return out


def _cv_text_similarity(a, b):
    aa = re.sub(r"[^a-z0-9]+", " ", str(a or "").lower()).strip()
    bb = re.sub(r"[^a-z0-9]+", " ", str(b or "").lower()).strip()
    if not aa or not bb:
        return 0.0
    aset, bset = set(aa.split()), set(bb.split())
    token_score = len(aset & bset) / max(len(aset), len(bset)) if aset and bset else 0.0
    # Prefixes survive PDF line-wrap and punctuation differences particularly well.
    prefix_score = 1.0 if aa[:55] == bb[:55] else 0.0
    return max(token_score, prefix_score)


def _cv_project_group_sort_key(block):
    """Chronological project order inside a role; broad ad-hoc work goes last."""
    heading = str((block or {}).get("heading") or (block or {}).get("title") or "")
    generic = bool(re.search(r"\b(?:ad[ -]?hoc|business proposals?|general support|ongoing support|various projects?)\b", heading, re.I))
    duration = _normalize_cv_date_range((block or {}).get("duration") or "")
    start_text, _ = _cv_date_parts(duration)
    start = _cv_date_sort_point(start_text or duration, end=False)
    # Known dated projects first in ascending order, then undated, then generic/ad-hoc.
    if generic:
        return (2, (9999, 12), int((block or {}).get("source_index") or 0))
    if start:
        return (0, start, int((block or {}).get("source_index") or 0))
    return (1, (9998, 12), int((block or {}).get("source_index") or 0))
