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


def _iso_year_month_repl(match):
    """Convert an ISO YYYY-MM (day already stripped) token to "Mon YYYY"."""
    month = int(match.group(2))
    if 1 <= month <= 12:
        return f"{_MONTH_ABBR_BY_NUMBER[month]} {match.group(1)}"
    return match.group(0)


def _cv_pretranslate_iso_dates(text):
    """Rewrite ISO-style YYYY-MM and YYYY-MM-DD dates to house-style "Mon YYYY".

    Some CVs write experience dates year-first, e.g. "2020-06" or "2020-06-15".
    Providers read that format unreliably -- they mis-tag the month or year, or
    turn a real end date into "Present" -- whereas they read "Jun 2020"
    correctly, so converting the source up front removes the ambiguity. Only
    a 19xx/20xx year with a 01-12 month is touched, which does not match phone
    numbers, percentages, version strings, or amounts. The day is dropped.
    """
    text = str(text or "")
    # YYYY-MM-DD first (drop the day), then the bare YYYY-MM.
    text = re.sub(r"\b((?:19|20)\d{2})-(0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])\b", _iso_year_month_repl, text)
    text = re.sub(r"\b((?:19|20)\d{2})-(0[1-9]|1[0-2])\b", _iso_year_month_repl, text)
    return text


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


_CV_EMPTY_EDUCATION_DEGREE_RE = re.compile(
    r"^(?:no\s+degree|degree\s+(?:not\s+)?(?:specified|stated)|"
    r"not\s+(?:specified|stated)|n\s*/?\s*a|none|unknown)$",
    re.I,
)


_CV_NO_DEGREE_PREFIX_RE = re.compile(
    r"^no\s+degree\s*(?::|[-\u2013\u2014])\s*(.+?)\s*$",
    re.I,
)


_CV_RECRUITMENT_TRACKING_METADATA_RE = re.compile(
    r"(?im)(?:^[ \t]*|[ \t]*\|[ \t]*)position\s*:\s*retrieved\s+resumes\s*"
    r"\(\s*siva\s+folder\s*:[^)\r\n]*\)\s*;\s*"
    r"date\s+applied\s*:[^\r\n]*(?=\r?\n|$)",
)


_CV_BRACKETED_SOURCE_SECTION_RE = re.compile(
    r"^\s*\[\s*([^\]]{2,100})\s*\]\s*:?\s*$",
    re.I,
)


_CV_RECOVERABLE_SOURCE_SECTIONS = {
    "project involvement history": "Project Involvement History",
    "participated training programme": "Participated Training Programme",
    "participated training program": "Participated Training Programme",
    "participation training programme": "Participated Training Programme",
    "participation in training programme": "Participated Training Programme",
}


_CV_SOURCE_SECTION_BOUNDARY_KEYS = {
    "profile",
    "personal profile",
    "professional profile",
    "summary",
    "professional summary",
    "career summary",
    "career objective",
    "objective",
    "work experience",
    "working experience",
    "professional experience",
    "employment history",
    "career history",
    "education",
    "education background",
    "academic background",
    "qualifications",
    "certification",
    "certifications",
    "licenses",
    "training",
    "skills",
    "technical skills",
    "soft skills",
    "core expertise",
    "competencies",
    "languages",
    "language proficiency",
    "achievements",
    "awards",
    "publications",
    "references",
    "referees",
    "personal details",
    "personal particulars",
    "additional information",
    "other information",
    "hobbies",
    "interests",
}


_CV_GITHUB_LINK_RE = re.compile(
    r"(?:\bgithub\b\s*:?\s*)?(?:https?://)?(?:www\.)?github\.com/"
    r"([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*)/?",
    re.I,
)


_CV_GITHUB_PLACEHOLDER_PATHS = {"unknown"}


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
    elif upper in _ACRONYM_KEEP or (len(upper) <= 3 and upper == stripped and stripped.isalpha()) or (
        upper == stripped and stripped.isalpha() and len(stripped) >= 2 and not any(ch in "AEIOU" for ch in upper)
    ):
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
    # Drop a leading dash/bullet the source baked in front of the date (e.g.
    # "- 2001" from a DOCX list). A date never starts with a minus sign, so this
    # is safe; internal range separators like "2020 - 2023" are left untouched.
    text = re.sub(r"^[\s]*[-‐-―−•·▪◦*]+[\s]*", "", text)
    if not text:
        return ""
    # Some provider runs preserve only the end of a source range and emit a
    # dangling separator (for example "to 2001"). A lone graduation year is
    # not a range, so keep only the year. A separator with no date is empty.
    lone_end_year = re.fullmatch(r"to\s+(\d{4})", text, flags=re.I)
    if lone_end_year:
        text = lone_end_year.group(1)
    elif re.fullmatch(r"to", text, flags=re.I):
        return ""
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    text = re.sub(r"\b(till\s*date|till\s*now|to\s*date|current|presently|now)\b", "Present", text, flags=re.I)
    text = re.sub(r"\bpresent\b", "Present", text, flags=re.I)
    # Convert ISO YYYY-MM(-DD) to "Mon YYYY" BEFORE turning "-" into "to", so an
    # ISO range like "2020-06 to 2025-07" is not shredded into "2020 to 06 ...".
    text = _cv_pretranslate_iso_dates(text)
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
    # A parenthesised proficiency descriptor marks a language declaration line on
    # its own, e.g. "Malay (Professional Working):". This matters for two-column
    # CV layouts where PDF extraction interleaves the LANGUAGES sidebar with other
    # sections, pushing later languages beyond the heading's line window.
    paren_proficiency = re.compile(
        r"\([^)]*\b(?:professional|working|native|conversational|fluen\w+|proficien\w+|"
        r"elementary|limited|intermediate|advanced|basic|mother\s*tongue|bilingual)\b[^)]*\)",
        re.I,
    )
    for i, line in enumerate(lines):
        if re.search(r"\blanguages?\b|\blinguistic\b|\bspoken\b|\bfluent\b|\bproficient\b|\bbilingual\b|\btrilingual\b|\bmultilingual\b|\bmother tongue\b", line, re.I):
            chunks.extend(lines[i:i+4])
        elif paren_proficiency.search(line):
            chunks.append(line)
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


# Address / contact markers that mean a value is a location or contact line, not
# a person's name. Kept broad enough to catch English street types and the
# South-East-Asian address vocabulary these CVs use.
_CV_LOCATION_MARKER_RE = re.compile(
    r"\b(?:avenue|ave|street|st|road|rd|lane|ln|drive|dr|boulevard|blvd|highway|"
    r"jalan|jln|lorong|lrg|taman|kampung|kampong|kg|bandar|persiaran|lebuh|lebuhraya|"
    r"block|blok|suite|unit|floor|tingkat|apartment|apt|residency|residence|condominium|"
    r"postcode|poskod|malaysia|singapore|indonesia|brunei|thailand|vietnam|philippines|"
    r"selangor|kuala\s+lumpur|putrajaya|cyberjaya|petaling|subang|shah\s+alam|klang|"
    r"johor|penang|perak|kedah|kelantan|terengganu|pahang|melaka|negeri\s+sembilan|"
    r"sarawak|sabah|labuan|bangi|cheras|ampang|kajang|seremban)\b",
    re.I,
)

_CV_NAME_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'.\-/]*")


def _name_is_location_like(value):
    """True when a candidate.name value is really a location/contact line.

    Person names do not carry an email, a phone/street number, or address
    vocabulary; a value that does was mis-tagged (e.g. the address landed in the
    name field on a CV whose header uses icon glyphs).
    """
    s = str(value or "").strip()
    if not s:
        return False
    if "@" in s:
        return True
    if re.search(r"\d", s):  # names do not contain digits; addresses/phones do
        return True
    return bool(_CV_LOCATION_MARKER_RE.search(s))


def _looks_like_person_name(value):
    """Conservative check that a line is a plausible person name."""
    s = str(value or "").strip().strip(",").strip()
    if not s or "@" in s or re.search(r"\d", s):
        return False
    if "," in s or _CV_LOCATION_MARKER_RE.search(s):
        return False
    words = s.split()
    if not (1 < len(words) <= 6):
        return False
    return all(_CV_NAME_WORD_RE.fullmatch(w) for w in words)


def _recover_candidate_name_from_text(cv_text):
    """Recover the candidate name from the top of the CV.

    Scans the first few non-empty lines (stripping leading "(cid:NNNN)" icon-font
    glyphs that PDF extraction leaves before contact lines) and returns the first
    that reads as a person name. Returns "" when none qualifies.
    """
    seen = 0
    for raw in str(cv_text or "").splitlines():
        line = re.sub(r"^(?:\(cid:\d+\)\s*)+", "", str(raw).strip()).strip()
        if not line:
            continue
        seen += 1
        if _looks_like_person_name(line):
            return line
        if seen >= 5:
            break
    return ""


def _correct_mistagged_candidate_name(parsed, cv_text=""):
    """Repair a candidate.name that was populated with a location/contact line.

    Only acts when the name is missing or clearly not a person name, and only
    replaces it when a plausible name can be recovered from the CV header, so a
    correct (if unusual) name is never discarded.
    """
    if not isinstance(parsed, dict):
        return parsed
    cand = parsed.get("candidate")
    if not isinstance(cand, dict):
        return parsed
    name = str(cand.get("name") or "").strip()
    if name and not _name_is_location_like(name):
        return parsed
    recovered = _recover_candidate_name_from_text(cv_text)
    if recovered:
        cand["name"] = recovered
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


_CV_LEADING_BULLET_MARKER_RE = re.compile(
    r"^\s*(?:"
    r"[•●▪◦‣∙·▶►➤⁃∙»›]"  # glyph bullets: always markers
    r"|\((?:[ivxlcdm]{1,7}|[a-z]|\d{1,3})\)"  # parenthesised enumerator: (i) (a) (12)
    r"|\d{1,3}[.)](?=\s|[^\W\d_])"  # numeric enumerator "1." / "1)" (protects "3.5")
    r"|\d{1,3}-(?=\s)"  # source enumerator "1- " (protects "5-star")
    r"|(?-i:(?:[a-z]|[ivxlcdm]{2,7})[.)-])(?=\s)"  # bare lower-case a. / ii. / a-
    r"|[*‐-―-](?=\s|[^\W\d_])"  # dash/asterisk: only before whitespace or a letter (protects "-5%")
    r")\s*",
    re.I,
)


def _strip_leading_bullet_marker(text):
    """Drop a list marker the source bullet carried in its own text.

    DOCX/plain-text CVs sometimes deliver bullets with the visible marker baked
    into the string (e.g. ``-Received calls`` or ``• Provide support``). The
    formatter renders its own bullet, so the literal marker must be removed or it
    shows up as ``- Received calls`` in the output. Glyph bullets are always
    markers; a leading dash/asterisk is stripped only when followed by whitespace
    or a letter, so figures like ``-5% variance`` are left intact.
    """
    value = str(text or "")
    for _ in range(5):  # tolerate a short run like "• - "
        stripped = _CV_LEADING_BULLET_MARKER_RE.sub("", value, count=1)
        if stripped == value:
            break
        value = stripped
    return value


def _absorb_orphan_section_labels(items):
    """Attach loose bullets to an empty section label that introduces them.

    When a provider emits a sub-section label such as ``Key responsibilities``
    as a flat bullet string instead of nesting the duties under it, the label
    becomes an empty ``{"heading": ..., "bullets": [], "kind": "section"}`` group
    followed by the real bullets as loose siblings -- which renders as a lone
    label with nothing beneath it. Re-attach the following plain bullets to the
    label so it introduces its duties as intended, and drop the label outright
    when nothing follows it (a bare label carries no information).
    """
    result = []
    index = 0
    count = len(items)
    while index < count:
        item = items[index]
        if (
            isinstance(item, dict)
            and item.get("kind") == "section"
            and not item.get("bullets")
            and str(item.get("heading") or "").strip()
        ):
            collected = []
            nxt = index + 1
            while nxt < count and isinstance(items[nxt], str):
                collected.append(items[nxt])
                nxt += 1
            if collected:
                merged = dict(item)
                merged["bullets"] = collected
                result.append(merged)
            index = nxt
            continue
        result.append(item)
        index += 1
    return result


def _strip_cv_recruitment_tracking_metadata(value):
    """Remove JobStreet/SiVA application-routing metadata from parsed CV data."""
    if isinstance(value, dict):
        for key in list(value):
            value[key] = _strip_cv_recruitment_tracking_metadata(value[key])
        return value
    if isinstance(value, list):
        cleaned = [_strip_cv_recruitment_tracking_metadata(item) for item in value]
        return [item for item in cleaned if not isinstance(item, str) or item.strip()]
    if not isinstance(value, str):
        return value
    cleaned = _CV_RECRUITMENT_TRACKING_METADATA_RE.sub("", value)
    if cleaned == value:
        return value
    return cleaned.strip(" \t\r\n|;")


def _cv_source_section_key(value):
    return re.sub(r"[^a-z]+", " ", str(value or "").lower()).strip()


def _cv_source_item_key(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _cv_github_path_key(value):
    """Normalize a captured GitHub path without swallowing sentence punctuation."""
    return str(value or "").lower().rstrip("/.")


def _extract_recoverable_cv_source_sections(source_text):
    """Extract allowlisted bracketed sections that providers commonly omit."""
    recovered = {
        display: [] for display in set(_CV_RECOVERABLE_SOURCE_SECTIONS.values())
    }
    current = ""
    for raw_line in str(source_text or "").splitlines():
        line = str(raw_line or "").strip()
        heading = _CV_BRACKETED_SOURCE_SECTION_RE.fullmatch(line)
        if heading:
            current = _CV_RECOVERABLE_SOURCE_SECTIONS.get(
                _cv_source_section_key(heading.group(1)),
                "",
            )
            continue
        if current and _cv_source_section_key(line) in _CV_SOURCE_SECTION_BOUNDARY_KEYS:
            current = ""
            continue
        if not current or not line:
            continue
        item = _strip_leading_bullet_marker(line).strip()
        if item and item not in recovered[current]:
            recovered[current].append(item)
    return {category: items for category, items in recovered.items() if items}


def _recover_cv_source_additional_sections(parsed, source_text):
    """Restore exact project/training lists and remove duplicated training certs."""
    recovered = _extract_recoverable_cv_source_sections(source_text)
    if not recovered:
        return parsed
    recovered_keys = {
        _cv_source_section_key(category) for category in recovered
    }
    skills = []
    for skill in parsed.get("skills") or []:
        if not isinstance(skill, dict):
            continue
        if _cv_source_section_key(skill.get("category")) in recovered_keys:
            continue
        skills.append(skill)
    for category in (
        "Project Involvement History",
        "Participated Training Programme",
    ):
        if category in recovered:
            skills.append({"category": category, "items": recovered[category]})
    parsed["skills"] = skills

    training_keys = {
        _cv_source_item_key(item)
        for item in recovered.get("Participated Training Programme", [])
    }
    if training_keys:
        parsed["certifications"] = [
            item for item in parsed.get("certifications") or []
            if _cv_source_item_key(item) not in training_keys
        ]
    return parsed


def _remove_ungrounded_cv_github_links(parsed, source_text):
    """Drop placeholder or source-contradicted GitHub URLs from parsed CV data."""
    has_source = bool(str(source_text or "").strip())
    source_paths = {
        _cv_github_path_key(match.group(1))
        for match in _CV_GITHUB_LINK_RE.finditer(str(source_text))
    }
    cleaned_skills = []
    for skill in parsed.get("skills") or []:
        if not isinstance(skill, dict):
            continue
        cleaned_skill = dict(skill)
        raw_items = cleaned_skill.get("items") or ""
        was_list = isinstance(raw_items, list)
        category_key = _cv_source_section_key(cleaned_skill.get("category"))
        raw_values = raw_items if was_list else [raw_items]
        github_matches = [
            match
            for value in raw_values
            for match in _CV_GITHUB_LINK_RE.finditer(str(value or ""))
        ]
        if not github_matches:
            if raw_items or category_key not in {
                "github",
                "portfolio links",
                "summary",
            }:
                cleaned_skills.append(cleaned_skill)
            continue
        if not has_source and not any(
            _cv_github_path_key(match.group(1)) in _CV_GITHUB_PLACEHOLDER_PATHS
            for match in github_matches
        ):
            cleaned_skills.append(cleaned_skill)
            continue
        values = raw_items if was_list else re.split(
            r"(?:\r?\n)+|\s+\|\s+",
            str(raw_items),
        )
        cleaned_values = []
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue

            def replace_link(match):
                path = _cv_github_path_key(match.group(1))
                if path in _CV_GITHUB_PLACEHOLDER_PATHS:
                    return ""
                if not has_source or path in source_paths:
                    return match.group(0)
                return ""

            text = _CV_GITHUB_LINK_RE.sub(replace_link, text).strip(" \t|,;-")
            if text:
                cleaned_values.append(text)
        cleaned_skill["items"] = cleaned_values if was_list else "\n".join(cleaned_values)
        if cleaned_values or category_key not in {
            "github",
            "portfolio links",
            "summary",
        }:
            cleaned_skills.append(cleaned_skill)
    parsed["skills"] = cleaned_skills
    return parsed


def _normalize_cv_bullet_items(items, allow_standalone_sections=True):
    """Repair valid JSON-looking bullet strings without changing plain prose."""
    source = items if isinstance(items, list) else ([] if items in (None, "") else [items])
    normalized = []

    def add(item):
        if isinstance(item, str):
            candidate = _strip_leading_bullet_marker(item).strip()
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
            # Keep only bullets that carry real content. After marker stripping a
            # residue like "-" or "--" would otherwise render as a lone dash;
            # ``isalnum`` is Unicode-aware, so non-Latin bullets are preserved.
            if candidate and any(ch.isalnum() for ch in candidate):
                normalized.append(candidate)
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
    # Standalone section labels ("Key responsibilities" etc.) are only created at
    # the level where they are allowed; re-attach the loose bullets that follow
    # such an orphaned label so it does not render as an empty heading.
    if allow_standalone_sections:
        normalized = _absorb_orphan_section_labels(normalized)
    return normalized


def _normalize_cv_structured_content(parsed):
    """Idempotently repair role bullets, inferred-title annotations and blanks."""
    if not isinstance(parsed, dict):
        return parsed
    parsed = _strip_cv_recruitment_tracking_metadata(parsed)
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
    normalized_skills = []
    for value in skills:
        if not isinstance(value, dict):
            continue
        if not (
            str(value.get("category") or "").strip()
            or str(value.get("items") or "").strip()
        ):
            continue
        skill = dict(value)
        category_key = re.sub(
            r"[^a-z]+", " ", str(skill.get("category") or "").lower()
        ).strip()
        if category_key == "core expertise":
            raw_items = skill.get("items") or ""
            raw_item_values = raw_items if isinstance(raw_items, list) else [raw_items]
            item_lines = [
                item.strip()
                for raw_item in raw_item_values
                for item in re.split(r"(?:\r?\n)+|,\s*", str(raw_item))
                if item.strip()
            ]
            if item_lines:
                skill["items"] = item_lines
        normalized_skills.append(skill)
    parsed["skills"] = normalized_skills
    return parsed


def _normalize_cv_data_for_output(parsed, source_text=""):
    """Normalize structured CV data for preview and DOCX export."""
    if not isinstance(parsed, dict):
        return parsed
    parsed = _normalize_cv_structured_content(parsed)
    parsed = _recover_cv_source_additional_sections(parsed, source_text)
    parsed = _remove_ungrounded_cv_github_links(parsed, source_text)
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
    normalized_experiences = _merge_adjacent_continuous_company_stints(
        parsed.get("work_experiences") or []
    )
    for exp in normalized_experiences:
        if isinstance(exp, dict):
            exp["roles"] = _sort_cv_roles_reverse_chronological(
                exp.get("roles") or []
            )
    parsed["work_experiences"] = _sort_work_experiences_reverse_chronological(
        normalized_experiences
    )
    for edu in parsed.get("education") or []:
        if not isinstance(edu, dict):
            continue
        recovered_date = _recover_education_date_range(edu, source_text)
        if recovered_date:
            edu["date_range"] = recovered_date
        elif edu.get("date_range"):
            edu["date_range"] = _normalize_cv_date_range(edu.get("date_range"))
        degree = str(edu.get("degree") or "").strip()
        no_degree_prefix = _CV_NO_DEGREE_PREFIX_RE.fullmatch(degree)
        if no_degree_prefix:
            degree = no_degree_prefix.group(1).strip()
        if _CV_EMPTY_EDUCATION_DEGREE_RE.fullmatch(degree):
            edu["degree"] = ""
        elif no_degree_prefix:
            edu["degree"] = degree
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
    # 8000 chars ~= a dense multi-page CV (a real 8-page CV extracts to ~9-10k
    # chars). The old 18000 threshold left such CVs on the 180s budget, so a
    # DeepSeek parse that occasionally ran past 180s was cut off mid-parse. The
    # timeout is a ceiling, not a fixed wait, so granting the 300s budget more
    # readily has no cost for CVs that parse quickly.
    is_long = len(text) >= 8000 or len(_CV_ROLE_DENSE_MARKER_RE.findall(text)) >= 8
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
    # Numeric MM/YYYY and ISO YYYY-MM carry the month too; normalise both to
    # "Mon YYYY" first so e.g. "06/2024" or "2024-06" sort at month granularity.
    text = _cv_pretranslate_iso_dates(text)
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


def _cv_company_base_key(value):
    """Return a conservative base key for a location-suffixed employer name."""
    text = re.sub(r"\s+", " ", str(value or "").strip())
    parts = re.split(r"\s+(?:[-\u2013\u2014]|\|)\s+", text, maxsplit=1)
    if len(parts) != 2:
        return _cv_match_key(text)
    base, suffix = parts
    # A broad one-part country suffix is a harmless spelling variant. Preserve
    # a more specific city/state suffix (normally comma-delimited), because it
    # may identify a genuinely separate assignment in the marked-correct CV.
    if "," in suffix or len(re.findall(r"[A-Za-z0-9]+", suffix)) > 2:
        return _cv_match_key(text)
    return _cv_match_key(base)


def _cv_company_names_groupable(left, right):
    """Match exact names or a neighbouring base/location spelling variant."""
    left_key = _cv_match_key(left)
    right_key = _cv_match_key(right)
    if not left_key or not right_key:
        return False
    if left_key == right_key:
        return True
    return (
        _cv_company_base_key(left) == right_key
        or _cv_company_base_key(right) == left_key
    )


def _cv_experience_interval(exp):
    if not isinstance(exp, dict):
        return None
    date_range = _normalize_cv_date_range(exp.get("date_range") or "")
    if not date_range:
        date_range = _cv_company_span_from_roles(exp.get("roles") or [])
    start_text, end_text = _cv_date_parts(date_range)
    start = _cv_date_sort_point(start_text or date_range, end=False)
    end = _cv_date_sort_point(end_text or start_text or date_range, end=True)
    if start is None or end is None:
        return None
    start_serial = (start[0] * 12) + start[1]
    end_serial = (end[0] * 12) + end[1]
    if end_serial < start_serial:
        start_serial, end_serial = end_serial, start_serial
    return start_serial, end_serial


def _cv_experience_intervals_touch(left, right):
    left_interval = _cv_experience_interval(left)
    right_interval = _cv_experience_interval(right)
    if left_interval is None or right_interval is None:
        return False
    later_start = max(left_interval[0], right_interval[0])
    earlier_end = min(left_interval[1], right_interval[1])
    return later_start <= earlier_end + 1


def _cv_roles_with_effective_dates(exp):
    roles = [
        dict(role)
        for role in (exp.get("roles") or [])
        if isinstance(role, dict)
    ]
    if len(roles) == 1 and not str(roles[0].get("date_range") or "").strip():
        roles[0]["date_range"] = _normalize_cv_date_range(
            exp.get("date_range") or ""
        )
    return roles


def _merge_adjacent_continuous_company_stints(experiences):
    """Group only neighbouring same-employer entries whose dates touch.

    AI output sometimes splits a promotion path into one company block per role,
    especially when one source row appends a location (``Unilever - Malaysia``).
    This restores the template's multi-role employer format without combining a
    later return to the same employer or two stints separated by a real gap.
    """
    merged = []
    for source_exp in experiences or []:
        if not isinstance(source_exp, dict):
            continue
        exp = dict(source_exp)
        exp["roles"] = [
            dict(role)
            for role in (source_exp.get("roles") or [])
            if isinstance(role, dict)
        ]
        previous = merged[-1] if merged else None
        if not (
            previous
            and previous.get("roles")
            and exp.get("roles")
            and _cv_company_names_groupable(
                previous.get("company"), exp.get("company")
            )
            and _cv_experience_intervals_touch(previous, exp)
        ):
            merged.append(exp)
            continue

        previous["roles"] = (
            _cv_roles_with_effective_dates(previous)
            + _cv_roles_with_effective_dates(exp)
        )
        previous_company = str(previous.get("company") or "").strip()
        incoming_company = str(exp.get("company") or "").strip()
        if incoming_company and len(incoming_company) < len(previous_company):
            previous["company"] = incoming_company
        combined_span = _cv_company_span_from_roles(previous["roles"])
        if combined_span:
            previous["date_range"] = combined_span
    return merged


def _sort_work_experiences_reverse_chronological(experiences):
    """Sort dated employers newest-first while keeping unknown dates stable."""
    indexed = list(enumerate(experiences or []))

    def sort_key(item):
        index, exp = item
        interval = _cv_experience_interval(exp)
        if interval is None:
            return (1, 0, 0, index)
        start, end = interval
        return (0, -end, -start, index)

    return [exp for _, exp in sorted(indexed, key=sort_key)]


def _sort_cv_roles_reverse_chronological(roles):
    """Sort dated roles newest-first while keeping unknown dates stable."""
    indexed = list(enumerate(roles or []))

    def sort_key(item):
        index, role = item
        interval = _cv_experience_interval(role)
        if interval is None:
            return (1, 0, 0, index)
        start, end = interval
        return (0, -end, -start, index)

    return [role for _, role in sorted(indexed, key=sort_key)]


def _recover_education_date_range(education, source_text):
    """Restore source month precision when the provider returned years only."""
    if not isinstance(education, dict) or not str(source_text or "").strip():
        return ""
    current = _normalize_cv_date_range(education.get("date_range") or "")
    if not current or re.search(
        r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|"
        r"Dec(?:ember)?)\b|\b\d{1,2}/\d{4}\b",
        current,
        re.I,
    ):
        return ""

    endpoint = (
        r"(?:\d{1,2}/\d{4}|"
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|"
        r"Dec(?:ember)?)\.?\s+\d{4}|\d{4})"
    )
    range_re = re.compile(
        r"(?P<range>" + endpoint + r"\s*(?:to|[-\u2013\u2014])\s*" + endpoint + r")",
        re.I,
    )
    source = str(source_text)
    source_lower = source.lower()
    anchors = []
    for field in (education.get("institution"), education.get("degree")):
        needle = re.sub(r"\s+", " ", str(field or "").strip()).lower()
        if not needle:
            continue
        for match in re.finditer(re.escape(needle), source_lower):
            anchors.append(match.start())
    if not anchors:
        return ""

    current_years = re.findall(r"\b\d{4}\b", current)
    if len(current_years) != 2:
        return ""
    best = None
    for match in range_re.finditer(source):
        distance = min(abs(match.start() - anchor) for anchor in anchors)
        if distance > 500:
            continue
        candidate = _normalize_cv_date_range(match.group("range"))
        candidate_years = re.findall(r"\b\d{4}\b", candidate)
        if (
            len(candidate_years) != 2
            or (current_years[0], current_years[-1])
            != (candidate_years[0], candidate_years[-1])
        ):
            continue
        if not re.search(
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b",
            candidate,
            re.I,
        ):
            continue
        if best is None or distance < best[0]:
            best = (distance, candidate)
    return best[1] if best else ""


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
