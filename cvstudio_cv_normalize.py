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
import unicodedata
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


# Shared month-word alternation (longest first so "January" wins over "Jan").
_CV_MONTH_WORD = (
    r"(?:January|February|March|April|September|October|November|December|"
    r"June|July|August|Sept|May|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
)


# A year followed by a month name is the same year-first hazard as "2020-06",
# just spelled out: "2025 june - current", "2022 march - 2024 august". Providers
# mis-read it the same way, and this form is common in hand-written table CVs.
#
# The year has to come first in the token for this to fire, so "Apr 2019" and
# "Sept 2024" are untouched. A newline between the two is not crossed, because a
# year ending one line and a month opening the next are two different dates.
# Horizontal spaces Word and PDF use between a month and its year. The same set
# the ISO helper and the field normaliser already treat as ordinary date
# separators, so a figure space or thin space cannot hide a date from this pass.
_CV_HSPACE = r"[ \t\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]"
_CV_YEAR_TOKEN = r"(?:19|20)\d{2}"
_CV_RANGE_SEP = (
    r"(?:[-\u2010-\u2015\u2212]|to|until|till|through)"
)
# The right-hand side of an open range. Every spelling _normalize_cv_date_range
# reads as Present is listed, including the "till date" / "till now" / "until
# present" forms that are common on the CVs this pass was written for; the
# separator alternation above only covers "till" standing in for the dash.
_CV_OPEN_END = (
    r"(?:(?:till|until|up[ \t]?to|to)[ \t]?(?:date|now|present|current)"
    r"|todate|current(?:ly)?|present(?:ly)?|now|ongoing|date)"
)
# "2025 june", "2025 June.", "2025 Jun,"
_CV_YEAR_FIRST_TOKEN = (
    _CV_YEAR_TOKEN + _CV_HSPACE + r"+" + _CV_MONTH_WORD + r"\.?,?"
)
# "Jun 2015", "Jun. 2015", "June, 2015", "Jun2015"
_CV_MONTH_FIRST_TOKEN = (
    _CV_MONTH_WORD + r"\.?,?" + _CV_HSPACE + r"*" + _CV_YEAR_TOKEN
)
_CV_EITHER_DATE_TOKEN = (
    r"(?:" + _CV_YEAR_FIRST_TOKEN + r"|" + _CV_MONTH_FIRST_TOKEN + r")"
)

# A cell that is NOTHING BUT a date or a date range. The right-hand side of a
# range may also be a bare year ("2015 June - 2017"): the left-hand side still has
# to be a full date token, so a range of two bare years never reaches the swap.
#
# Anchoring to a whole cell is the point of this pass, not a shortcut. An
# earlier draft rewrote "YYYY Month" anywhere it appeared and did real damage:
# "figures for 2023 may be revised" became "figures for may 2023 be revised",
# "Won the 2024 March tender" was reworded, and a line of several month-first
# dates had its years and months interleaved, because "may", "march" and
# "august" are ordinary English words and a year can close one date while a
# month opens the next. Restricting the rewrite to a line that holds only a date
# removes every one of those, at the cost of leaving a year-first date that is
# embedded in a longer cell alone. A line with no " | " separator is one cell.
_CV_YEAR_FIRST_DATE_LINE_RE = re.compile(
    r"^" + _CV_HSPACE + r"*"
    + _CV_EITHER_DATE_TOKEN
    + r"(?:" + _CV_HSPACE + r"*" + _CV_RANGE_SEP + _CV_HSPACE + r"*"
    + r"(?:" + _CV_EITHER_DATE_TOKEN + r"|" + _CV_OPEN_END + r"|"
    + _CV_YEAR_TOKEN + r"(?![ \t]*" + _CV_MONTH_WORD + r"))" + r")?"
    + _CV_HSPACE + r"*[.,;]?" + _CV_HSPACE + r"*$",
    re.I,
)

# Within such a line, the year-first halves to turn around. At most two date
# tokens can reach here, so the left-to-right scan cannot take a year from one
# date and a month from the next. A full stop or comma after the month travels
# with it -- "2025 Jun." becomes "Jun. 2025", never "Jun 2025." -- which is a
# month-first form the line pattern above already accepts.
_CV_YEAR_FIRST_SWAP_RE = re.compile(
    r"\b(" + _CV_YEAR_TOKEN + r")" + _CV_HSPACE + r"+(" + _CV_MONTH_WORD + r"\b\.?,?)",
    re.I,
)


def _cv_line_is_year_first_date(line):
    """Whether a cell is entirely a date range with at least one year-first half."""
    if not _CV_YEAR_FIRST_DATE_LINE_RE.match(line):
        return False
    # "Jun 2015 - august 2017" is already month-first throughout; there is
    # nothing to turn around and the line must come back byte-identical.
    return bool(_CV_YEAR_FIRST_SWAP_RE.search(line))


def _cv_year_first_month_repl(match):
    """Swap "2025 june" to "june 2025", keeping the source spelling of the month."""
    return "{} {}".format(match.group(2), match.group(1))


def _cv_pretranslate_year_first_month_names(text):
    """Rewrite "YYYY Month" to "Month YYYY" in table cells that are only a date.

    Applied to the whole CV document only, alongside ``_cv_pretranslate_iso_dates``
    and never inside ``_normalize_cv_date_range``: that field normaliser is
    mirrored in two JavaScript copies, and a rule added on one side only would
    break their shared contract.

    Mirrors ``_cv_pretranslate_iso_dates`` for the spelled-out form. A CV that
    writes its most recent roles year-first and its older ones month-first gets
    read inconsistently, and the year-first rows are the ones that come back
    wrong or go missing entirely.

    Only a table cell -- or a line, which is a cell with no separator -- holding
    nothing but a date or date range is touched, and only when part of it is
    year-first. Prose is never reworded, a cell carrying several dates is never
    reordered, and the month keeps the source spelling.

    The anchor is the cell, not the line. v24.6.412 required the whole LINE to
    be a date, but the upload route joins a table row's cells with " | ", so a
    date cell never sat alone on its line and that version changed nothing on the
    CV it was written for. Widening the anchor back to the whole document is not
    the fix: that is the v24.6.411 version, which reworded prose.
    """
    text = str(text or "")
    if not text:
        return text
    out = []
    for line in text.splitlines(True):
        stripped = line.rstrip("\r\n")
        ending = line[len(stripped):]
        out.append(_cv_rewrite_year_first_cells(stripped) + ending)
    return "".join(out)


# The upload route flattens each table row into one line, joining its cells with
# " | ". A date cell therefore does not arrive on a line of its own: it arrives as
# "2025 june- current | Senior Data Engineer". The rewrite is anchored to a whole
# CELL for that reason. A line with no separator is a single cell, so a date that
# does sit alone on its line is handled exactly as before.
_CV_CELL_SEPARATOR_RE = re.compile(r"(" + _CV_HSPACE + r"*\|" + _CV_HSPACE + r"*)")


def _cv_rewrite_year_first_cells(line):
    """Turn round each cell of a line that is entirely a year-first date."""
    if "|" not in line:
        if _cv_line_is_year_first_date(line):
            return _CV_YEAR_FIRST_SWAP_RE.sub(_cv_year_first_month_repl, line)
        return line
    # Splitting on a captured separator keeps every separator in the list, so the
    # line reassembles byte-for-byte apart from the cells that were rewritten.
    parts = _CV_CELL_SEPARATOR_RE.split(line)
    for index in range(0, len(parts), 2):
        if _cv_line_is_year_first_date(parts[index]):
            parts[index] = _CV_YEAR_FIRST_SWAP_RE.sub(
                _cv_year_first_month_repl, parts[index]
            )
    return "".join(parts)


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
    # A "YYYY-NN" directly followed by a month name is NOT an ISO year-month:
    # the dash is a range separator and NN is a day, as in
    # "Apr 2022-11 Jul 2026". Reading that as November 2022 corrupted the range.
    # The guard allows horizontal Unicode spaces but deliberately not newlines: this helper
    # also runs over whole CV documents, where a real ISO date can sit at the end
    # of a line whose next line happens to start with a month name.
    text = re.sub(
        r"\b((?:19|20)\d{2})-(0[1-9]|1[0-2])\b(?![ \t\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]*" + _CV_MONTH_WORD + r"\b)",
        _iso_year_month_repl,
        text,
        flags=re.I,
    )
    return text


# A number beside a month may be a two-digit year. Require a complete date,
# or an entire day-bearing range with an explicit shared year, before removal.
# Keep this logic mirrored in both JavaScript date normalizers.
_CV_DAY_WORD = r"(?:0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?"
_CV_DAY_BEFORE_MONTH_RE = re.compile(
    r"\b" + _CV_DAY_WORD + r"[ \t]+(" + _CV_MONTH_WORD + r")\.?,?\s+(\d{4})\b", re.I,
)
_CV_DAY_AFTER_MONTH_RE = re.compile(
    r"\b(" + _CV_MONTH_WORD + r")\.?[ \t]+" + _CV_DAY_WORD + r",?\s+(\d{4})\b", re.I,
)
_CV_SHARED_DAY_RANGE_RES = (
    re.compile(
        r"(" + _CV_MONTH_WORD + r")\.?\s+" + _CV_DAY_WORD + r"\s*(?:-|to)\s*("
        + _CV_MONTH_WORD + r")\.?\s+" + _CV_DAY_WORD + r",?\s+(\d{4})", re.I,
    ),
    re.compile(
        _CV_DAY_WORD + r"\s+(" + _CV_MONTH_WORD + r")\.?\s*(?:-|to)\s*"
        + _CV_DAY_WORD + r"\s+(" + _CV_MONTH_WORD + r")\.?,?\s+(\d{4})", re.I,
    ),
)


def _cv_strip_day_of_month(text):
    """Reduce "11 Jul 2026" or "Jul 11, 2026" to "Jul 2026".

    Preserve ambiguous short years, including mixed "Jan 20 to Dec 2021".
    A shared year is used only for an explicit day-bearing span on both ends.
    """
    text = str(text or "")
    for pattern in _CV_SHARED_DAY_RANGE_RES:
        match = pattern.fullmatch(text)
        if match:
            # Leave the omitted start year for the chronology-checked expansion
            # below. A December-to-January span cannot share its ending year.
            return f"{match.group(1)} to {match.group(2)} {match.group(3)}"
    text = _CV_DAY_BEFORE_MONTH_RE.sub(r"\1 \2", text)
    text = _CV_DAY_AFTER_MONTH_RE.sub(r"\1 \2", text)
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
    "education certification",
    "education certifications",
    "education qualifications",
    "education background",
    "academic background",
    "academic qualifications",
    "qualifications",
    "professional qualifications",
    "certification",
    "certifications",
    "certifications training",
    "courses training",
    "training courses",
    "training development",
    "professional development",
    "licenses",
    "licenses certifications",
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
    "awards achievements",
    "publications",
    "professional affiliations",
    "professional memberships",
    "memberships",
    "references",
    "referees",
    "personal details",
    "personal particulars",
    "additional information",
    "other information",
    "hobbies",
    "interests",
    "volunteer",
    "volunteering",
    "volunteer experience",
    "volunteer community",
    "community involvement",
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
    # Word/PDF horizontal spaces are ordinary date separators, not line breaks.
    text = re.sub(r"[\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]", " ", text)
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
    # House style is month + year, so drop any day-of-month first. This must run
    # before the ISO rewrite: "Apr 2022-11 Jul 2026" would otherwise have its
    # "2022-11" read as November 2022 instead of a range separator plus a day.
    text = _cv_strip_day_of_month(text)
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
    # A source can state a one-year qualification or role as either ``2018``
    # or the redundant range ``2018 to 2018``. Render the compact, truthful
    # single-year form rather than implying a multi-year span.
    same_year = re.fullmatch(r"(\d{4})\s+to\s+\1", text, flags=re.I)
    if same_year:
        return same_year.group(1)
    # Compact earlier-career lines often omit the repeated start year, e.g.
    # ``Jul - Dec 2019``. The shared trailing year applies to both month
    # endpoints only when their month order permits the same year. A reversed
    # month span retains its unstated start year rather than guessing a year.
    same_year_months = re.fullmatch(
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+to\s+"
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})",
        text,
        flags=re.I,
    )
    if same_year_months:
        start_month = _normalize_month_token(same_year_months.group(1))
        end_month = _normalize_month_token(same_year_months.group(2))
        year = same_year_months.group(3)
        if _CV_MONTH_NUMBER[start_month.lower()] > _CV_MONTH_NUMBER[end_month.lower()]:
            return text
        return f"{start_month} {year} to {end_month} {year}"
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
    r"^\s*(?:(?:key\s+)?(?P<key>responsibilit(?:y|ies)|achievements?)|"
    r"(?P<plain>implementation|support|rollout|activities?\s+description))\s*:?\s*$",
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
    key = match.group("key")
    if key:
        return "Key achievements" if key.lower().startswith("achievement") else "Key responsibilities"
    # Generic source subheadings are structural labels, not wording to rewrite.
    return text.rstrip(":").strip()


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


def _strip_cv_additional_bullet_markers(items, always_bulleted=False):
    """Remove baked markers only where Additional Info renders real bullets.

    Certifications always render as list paragraphs. Skill collections render
    as list paragraphs only when they contain multiple items; a single scalar
    item remains ordinary prose and therefore keeps any visible source marker.
    """
    structured = isinstance(items, list)
    values = items if structured else re.split(r"(?:\r?\n)+", str(items or ""))
    nonempty = [value for value in values if str(value or "").strip()]
    if not always_bulleted and len(nonempty) <= 1:
        return items

    cleaned = []
    for value in nonempty:
        text = str(value or "").strip()
        text = _strip_leading_bullet_marker(text).strip()
        if text:
            cleaned.append(text)
    return cleaned if structured else "\n".join(cleaned)


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


def _cv_source_boundary_key(value):
    """Normalize equivalent combined headings such as ``A & B`` / ``A AND B``."""
    key = re.sub(r"\band\b", " ", _cv_source_section_key(value))
    return re.sub(r"\s+", " ", key).strip()


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
        item = _strip_leading_bullet_marker(line).strip()
        has_explicit_item_marker = item != line
        boundary_key = _cv_source_boundary_key(item)
        marker_is_numbered = bool(re.match(r"^\s*(?:\(\d{1,3}\)|\d{1,3}[.)])\s*", line))
        letters = [char for char in item if char.isalpha()]
        marker_is_emphasized = bool(
            has_explicit_item_marker
            and (
                (letters and all(char.isupper() for char in letters))
                or line.rstrip().endswith(":")
            )
        )
        if (
            current
            and boundary_key in _CV_SOURCE_SECTION_BOUNDARY_KEYS
            and (
                not has_explicit_item_marker
                or marker_is_numbered
                or marker_is_emphasized
            )
        ):
            current = ""
            continue
        if not current or not line:
            continue
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
    parsed["certifications"] = _strip_cv_additional_bullet_markers(
        certifications,
        always_bulleted=True,
    )
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
            structured_items = isinstance(raw_items, list)
            raw_item_values = raw_items if structured_items else [raw_items]
            item_lines = []
            for raw_item in raw_item_values:
                lines = [
                    item.strip()
                    for item in re.split(r"(?:\r?\n)+", str(raw_item))
                    if item.strip()
                ]
                # Providers occasionally wrap an entire comma-separated expertise
                # paragraph in a one-element list. Three or more comma-delimited
                # values are strong list evidence; a single comma remains intact
                # to protect phrases such as "Mergers, Acquisitions & Integration".
                split_commas = (
                    not structured_items
                    or (
                        len(raw_item_values) == 1
                        and len(lines) == 1
                        and lines[0].count(",") >= 2
                    )
                )
                for line in lines:
                    values = re.split(r",\s*", line) if split_commas else [line]
                    item_lines.extend(value.strip() for value in values if value.strip())
            if item_lines:
                skill["items"] = item_lines
        skill["items"] = _strip_cv_additional_bullet_markers(
            skill.get("items") or ""
        )
        normalized_skills.append(skill)
    parsed["skills"] = normalized_skills
    return parsed


def _recover_cv_source_skill_item_punctuation(parsed, source_text):
    """Restore source separators for a one-line skill group without rewriting it.

    Providers sometimes replace middle-dot separators with commas even though
    every word is otherwise identical. Use a category-anchored source span only
    when its alphanumeric content exactly matches the parsed items, so this is a
    punctuation/layout repair rather than a prose rewrite.
    """
    if not isinstance(parsed, dict) or not str(source_text or "").strip():
        return parsed
    skills = parsed.get("skills")
    if not isinstance(skills, list) or not skills:
        return parsed

    lines = [
        re.sub(r"\s+", " ", str(line or "").strip())
        for line in str(source_text).splitlines()
        if str(line or "").strip()
    ]
    categories = [
        re.sub(r"\s+", " ", str(skill.get("category") or "").strip())
        for skill in skills
        if isinstance(skill, dict) and str(skill.get("category") or "").strip()
    ]

    def content_key(value):
        return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())

    def starts_category(line, category):
        return re.match(
            r"^" + re.escape(category) + r"\s*:?\s+(.+)$",
            line,
            re.I,
        )

    for skill in skills:
        if not isinstance(skill, dict) or not isinstance(skill.get("items"), str):
            continue
        category = re.sub(r"\s+", " ", str(skill.get("category") or "").strip())
        parsed_items = re.sub(r"\s+", " ", str(skill.get("items") or "").strip())
        parsed_key = content_key(parsed_items)
        if not category or not parsed_key:
            continue
        for index, line in enumerate(lines):
            match = starts_category(line, category)
            if not match:
                continue
            candidate = match.group(1).strip()
            cursor = index + 1
            while content_key(candidate) != parsed_key and cursor < len(lines):
                following = lines[cursor]
                if any(
                    other.lower() != category.lower()
                    and starts_category(following, other)
                    for other in categories
                ):
                    break
                if re.fullmatch(r"[A-Z][A-Z0-9 &/()\-]{3,}", following):
                    break
                candidate_key = content_key(candidate)
                following_key = content_key(following)
                if not parsed_key.startswith(candidate_key + following_key):
                    break
                candidate += " " + following
                cursor += 1
            if content_key(candidate) == parsed_key and re.search(r"[·•]", candidate):
                # Restore punctuation, not stale source casing. Transfer only
                # matched ASCII characters; keep every source separator/symbol
                # and leave ambiguous Unicode mappings in their original form.
                source_chars = re.findall(r"[A-Za-z0-9]", candidate)
                parsed_chars = re.findall(r"[A-Za-z0-9]", parsed_items)
                if "".join(source_chars).lower() == "".join(parsed_chars).lower():
                    corrected_chars = iter(parsed_chars)
                    candidate = re.sub(
                        r"[A-Za-z0-9]", lambda match: next(corrected_chars), candidate
                    )
                skill["items"] = candidate
                break
    return parsed


def _normalize_cv_data_for_output(
    parsed, source_text="", *, preserve_work_order=False
):
    """Normalize structured CV data for preview and DOCX export."""
    if not isinstance(parsed, dict):
        return parsed
    experiences = parsed.get("work_experiences") or []
    # The private marker controls this first post-reconciliation pass. A retained
    # subsection heading carries the same source-order intent into the separate
    # /generate-docx request without exposing internal reconciliation metadata.
    authoritative_work_order = bool(
        preserve_work_order
        or parsed.pop("_work_experience_order_authoritative", False)
        or any(
            isinstance(exp, dict) and str(exp.get("section_heading") or "").strip()
            for exp in experiences
        )
    )
    parsed = _normalize_cv_structured_content(parsed)
    parsed = _recover_cv_source_additional_sections(parsed, source_text)
    parsed = _recover_cv_source_skill_item_punctuation(parsed, source_text)
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
    parsed["work_experiences"] = (
        normalized_experiences
        if authoritative_work_order
        else _sort_work_experiences_reverse_chronological(normalized_experiences)
    )
    for edu in parsed.get("education") or []:
        if not isinstance(edu, dict):
            continue
        _recover_education_source_labels(edu, source_text)
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


_CV_MONTH_PRECISION_RE = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\b",
    re.I,
)


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


_CV_BROAD_LOCATION_SUFFIX_KEYS = {
    _cv_match_key(value)
    for value in (
        "APAC", "Asia", "Australia", "China", "Europe", "Global",
        "Hong Kong", "India", "Indonesia", "Japan", "Malaysia",
        "New Zealand", "Philippines", "Singapore", "South Korea",
        "Taiwan", "Thailand", "UAE", "UK", "United Arab Emirates",
        "United Kingdom", "US", "USA", "United States", "Vietnam",
    )
}


def _cv_company_base_key(value):
    """Return a conservative base key for a location-suffixed employer name."""
    text = re.sub(r"\s+", " ", str(value or "").strip())
    parts = re.split(r"\s+(?:[-\u2013\u2014]|\|)\s+", text, maxsplit=1)
    if len(parts) != 2:
        return _cv_match_key(text)
    base, suffix = parts
    # Only a known broad geographic suffix is a harmless spelling variant.
    # Short business-unit names such as "Consulting" remain part of the company.
    if _cv_match_key(suffix) not in _CV_BROAD_LOCATION_SUFFIX_KEYS:
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


def _cv_experience_has_month_precision(exp):
    """Return whether every bounded endpoint has explicit month precision."""
    if not isinstance(exp, dict):
        return False
    date_range = _normalize_cv_date_range(exp.get("date_range") or "")
    if not date_range:
        date_range = _cv_company_span_from_roles(exp.get("roles") or [])
    start_text, end_text = _cv_date_parts(date_range)
    if not start_text or not _CV_MONTH_PRECISION_RE.search(start_text):
        return False
    if not end_text:
        return True
    return bool(
        _CV_MONTH_PRECISION_RE.search(end_text)
        or re.search(r"\b(?:present|current|now|till\s*date|to\s*date)\b", end_text, re.I)
    )


def _cv_experience_intervals_touch(left, right):
    if not (
        _cv_experience_has_month_precision(left)
        and _cv_experience_has_month_precision(right)
    ):
        return False
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
            # A source subsection heading starts a new semantic group even when
            # the employer and dates happen to touch the preceding entry.
            and not str(exp.get("section_heading") or "").strip()
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


def _sort_cv_dated_items_in_place(items):
    """Sort dated items into dated slots without moving undated source entries."""
    decorated = [
        (index, item, _cv_experience_interval(item))
        for index, item in enumerate(items or [])
    ]
    dated_items = [row for row in decorated if row[2] is not None]
    dated_items.sort(key=lambda row: (-row[2][1], -row[2][0], row[0]))
    dated_iterator = iter(row[1] for row in dated_items)
    return [
        next(dated_iterator) if interval is not None else item
        for _, item, interval in decorated
    ]


def _sort_work_experiences_reverse_chronological(experiences):
    """Sort dated employers newest-first without moving undated employers."""
    return _sort_cv_dated_items_in_place(experiences)


def _sort_cv_roles_reverse_chronological(roles):
    """Sort dated roles newest-first without moving undated roles."""
    return _sort_cv_dated_items_in_place(roles)


# A grade label written before the figure: "CGPA 2.0 / 4.0", "GPA: 3.8/4.0".
_CV_EDU_GRADE_LABEL = r"(?:C?GPA|CWA|WAM|Grade\s+Point\s+Average)"
# A major or specialisation stated on its own line or cell under a qualification:
# "Major: Finance", "Major<tab>Finance", "Major - Finance", "Majoring in Finance".
# A bare space after "Major" is not a label -- "Major in the arts club" is prose.
_CV_EDU_MAJOR_RE = re.compile(
    r"^\s*(?:(?:majors?|speciali[sz]ation)\s*(?:[:\uff1a]|\t|\s[-\u2013]\s)"
    r"|(?:majoring|majored|speciali[sz]ed)\s+in\s)"
    r"\s*(?P<value>[^|\r\n]*[^\W\d_][^|\r\n]*?)\s*$",
    re.I,
)
# The label alone in its cell, with the value in the next one: "Major | Finance".
_CV_EDU_MAJOR_LABEL_CELL_RE = re.compile(r"^\s*(?:majors?|speciali[sz]ation)\s*[:\uff1a]?\s*$", re.I)
_CV_EDU_BLOCK_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
# A new qualification after a field separator starts its own graduation span.
# Ordinary fields (institution, grade, Graduation: ...) remain with the degree.
_CV_EDU_QUALIFICATION_RE = re.compile(
    r"\b(?:(?:bachelor(?:s|['’]s)?|master(?:s|['’]s)?|doctor(?:ate)?|diploma|certificate)"
    r"(?=\s+(?:of|in|degree|science|arts|business|engineering|management|commerce|law)\b"
    r"|\s*[-–—:]|$)|associate\s+of|[BM]\.?(?:Sc|Eng|Tech|BA|Com)\.?|MBA|Ph\.?D\.?)\b",
    re.I,
)
# "graduated 2007", "graduated in June 2007", "Graduation: 2007", "Class of 2007".
# The year has to follow the word directly: "graduated students ... in 2019" is not
# a graduation date.
_CV_EDU_GRADUATED_RE = re.compile(
    r"\b(?:graduated|graduation(?:\s+(?:year|date))?|class\s+of)\b\s*(?:[:：\-–]\s*)?(?:in\s+|on\s+)?"
    r"(?P<when>(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+)?(?:19|20)\d{2})\b",
    re.I,
)


def _education_source_blocks(education, source_text, *, for_labels=False):
    """The source lines under each place this qualification's institution appears.

    A block starts at the line naming the institution and runs to the next line
    carrying a year (the next qualification), a section heading, or six lines,
    whichever comes first.
    """
    needle = re.sub(r"\s+", " ", str(education.get("institution") or "")).strip().lower()
    if len(needle) < 3:
        return []
    lines = str(source_text or "").splitlines()
    blocks = []
    previous = ""
    for index, line in enumerate(lines):
        preceding = previous
        if line.strip():
            previous = line.strip()
        if needle not in re.sub(r"\s+", " ", line).lower():
            continue
        block = [line]
        has_degree = bool(_CV_EDU_QUALIFICATION_RE.search(line))
        if for_labels:
            # A degree can precede its school. Keep the institution at block[0]
            # for date matching, but include the immediately preceding heading
            # as identity evidence, never another school's line or ordinary prose.
            if (needle not in re.sub(r"\s+", " ", preceding).lower()
                    and _CV_EDU_QUALIFICATION_RE.match(_strip_leading_bullet_marker(preceding))):
                block.append(preceding)
                has_degree = True
        for following in lines[index + 1:index + 7]:
            text = following.strip()
            if not text:
                continue
            if _CV_EDU_BLOCK_YEAR_RE.search(text):
                break
            if _cv_source_boundary_key(re.sub(r"[\s:]+$", "", text)) in _CV_SOURCE_SECTION_BOUNDARY_KEYS:
                break
            if for_labels and _CV_EDU_QUALIFICATION_RE.match(_strip_leading_bullet_marker(text)):
                # The first degree below a school belongs to it; once identified,
                # the next degree heading starts a different qualification.
                if has_degree:
                    break
                has_degree = True
            block.append(text)
        blocks.append(block)
    return blocks


def _education_qualification_spans(line):
    """Keep a university-first prefix with its own degree across field separators."""
    segments = []
    for part in re.split(r"\s*;\s*", line):
        if (segments and _CV_EDU_QUALIFICATION_RE.search(part)
                and _CV_EDU_QUALIFICATION_RE.search(segments[-1])):
            segments.append(part)
        elif segments:
            segments[-1] += " | " + part
        else:
            segments.append(part)
    spans = []
    for segment in segments:
        cells = re.split(r"\s*\|\s*", segment)
        institution_first = (len(cells) > 1 and not _CV_EDU_QUALIFICATION_RE.search(cells[0])
                             and bool(_CV_EDU_QUALIFICATION_RE.search(cells[1])))
        groups = [[cells[0]]]
        for cell in cells[1:]:
            if (_CV_EDU_QUALIFICATION_RE.search(cell)
                    and _CV_EDU_QUALIFICATION_RE.search(" | ".join(groups[-1]))):
                prefix = []
                previous = groups[-1][-1]
                if (institution_first and len(groups[-1]) > 1
                        and not _CV_EDU_QUALIFICATION_RE.search(previous)
                        and not _CV_EDU_BLOCK_YEAR_RE.search(previous)
                        and not re.search(r"[:：=]|\b(?:graduated|graduation|class|major|" + _CV_EDU_GRADE_LABEL + r")\b", previous, re.I)
                        and re.search(r"[^\W\d_]", previous)):
                    prefix.append(groups[-1].pop())
                groups.append(prefix + [cell])
            else:
                groups[-1].append(cell)
        spans.extend(" | ".join(group) for group in groups)
    return spans


def _recover_education_source_labels(education, source_text):
    """Put back the CGPA label and the major a provider dropped from an entry.

    A provider asked to copy the CGPA "exactly as written" can still return only
    the figure -- "2.0 / 4.0" from "CGPA 2.0 / 4.0" -- and a "Major" line under a
    qualification has no field of its own unless one is given. Both are read only
    from the lines under this entry's institution in the source. Repeated
    institutions need a uniquely identified qualification block; conflicting
    or missing evidence leaves the labels unchanged.
    """
    if not isinstance(education, dict) or not str(source_text or "").strip():
        return education
    blocks = _education_source_blocks(education, source_text)
    if not blocks:
        return education

    # A repeated school is not a shared qualification. Use a unique block
    # grounded in this entry's degree/date for its labels; never copy a master's
    # major or grade label onto a bachelor's degree at the same university.
    # A single school block retains the established restoration behaviour.
    label_blocks = blocks
    if len(blocks) > 1:
        label_blocks = _education_source_blocks(education, source_text, for_labels=True)
        degree_tokens = _cv_token_set(education.get("degree"))
        years = set(_CV_EDU_BLOCK_YEAR_RE.findall(str(education.get("date_range") or "")))
        matches = [block for block in label_blocks
                   if (degree_tokens or years)
                   and (not degree_tokens or degree_tokens <= _cv_token_set("\n".join(block)))
                   and (not years or years <= set(_CV_EDU_BLOCK_YEAR_RE.findall(block[0])))]
        label_blocks = matches if len(matches) == 1 else []

    cgpa = str(education.get("cgpa") or "").strip()
    # Only a value with no grade label of its own: "2.0 / 4.0", "3.5 out of 4.0".
    if cgpa and not re.search(r"\b" + _CV_EDU_GRADE_LABEL + r"\b", cgpa, re.I):
        figure = r"\s*".join(re.escape(part) for part in cgpa.split())
        labels = set()
        for block in label_blocks:
            for line in block:
                match = re.search(
                    r"\b(?P<label>" + _CV_EDU_GRADE_LABEL + r")\b\s*[:\uff1a=\-]?\s*" + figure + r"(?![\d.])",
                    line,
                    re.I,
                )
                if match:
                    label = re.sub(r"\s+", " ", match.group("label"))
                    labels.add(label.upper() if " " not in label else label)
        if len(labels) == 1:
            education["cgpa"] = "{} {}".format(labels.pop(), cgpa)

    if not str(education.get("major") or "").strip():
        majors = set()
        for block in label_blocks:
            for line in block:
                cells = line.split("|")
                for position, cell in enumerate(cells):
                    match = _CV_EDU_MAJOR_RE.match(cell)
                    if match:
                        majors.add(re.sub(r"\s+", " ", match.group("value")).strip())
                    elif (
                        _CV_EDU_MAJOR_LABEL_CELL_RE.match(cell)
                        and position + 1 < len(cells)
                        and re.search(r"[^\W\d_]", cells[position + 1])
                    ):
                        majors.add(re.sub(r"\s+", " ", cells[position + 1]).strip())
        # Kept even when the qualification's name already hints at it ("SPM in
        # Sciences" with "Major: science"): the source states both.
        if len(majors) == 1:
            major = majors.pop()
            education["major"] = major[:1].upper() + major[1:]

    if not str(education.get("date_range") or "").strip():
        # "Master of Management – Northwind Business School, graduated 2007." Only
        # the institution's own line is read, and when the entry has a degree, only
        # a line naming it: a school's line for another qualification carries that
        # qualification's year.
        degree_tokens = _cv_token_set(education.get("degree"))
        institution = re.sub(r"\s+", " ", str(education.get("institution") or "")).strip().lower()
        own_lines = []
        for block in blocks:
            line = block[0]
            # Retain the established whole-line ambiguity guard, even when its
            # two years occur in different qualification segments.
            if len(set(_CV_EDU_BLOCK_YEAR_RE.findall(line))) > 1:
                continue
            groups = _education_qualification_spans(line)
            if len(groups) == 1:
                own_lines.append(line)
                continue
            # A year in the master's segment cannot date the bachelor's entry,
            # even when PDF extraction placed both schools on one physical line.
            matches = [group for group in groups
                       if institution in re.sub(r"\s+", " ", group).lower()
                       and (not degree_tokens or degree_tokens <= _cv_token_set(group))]
            if len(matches) == 1:
                own_lines.append(matches[0])
        if degree_tokens:
            own_lines = [line for line in own_lines if degree_tokens <= _cv_token_set(line)]
        years = set()
        unsure = False
        for line in own_lines:
            found = [re.sub(r"\s+", " ", m.group("when")).strip() for m in _CV_EDU_GRADUATED_RE.finditer(line)]
            years.update(found)
            # Another year on the line may be this qualification's: unsure.
            if found and set(_CV_EDU_BLOCK_YEAR_RE.findall(line)) != {when[-4:] for when in found}:
                unsure = True
        if len(years) == 1 and not unsure:
            education["date_range"] = years.pop()
    return education


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


# ── Salary never reaches the Summary box ─────────────────────────────────────
# A generated summary is written by a provider from the whole CV, and a CV can
# state the candidate's current and expected salary. The summary instructions
# forbid it, but instructions are not a guarantee, so a statement of the
# candidate's pay is removed from the summary before it is shown or written:
# by /generate-ai for the two summary callers, by /parse and the Blind summary
# preparation, and by /generate-docx as a last net. This is the only
# implementation; the browser receives already-filtered text, and every removal
# is reported so the page can say so. Rule P1 in CV_SOURCE_CHECK_GUARDRAILS.md.
#
# A summary is also the candidate's work, and much of that work is about pay
# (HR, payroll, recruitment, sales), so a sentence is removed only on a clear sign
# that it states the candidate's OWN pay:
#   * "my"/"candidate's" or expected/asking/last-drawn before a pay word and an
#     amount -- "Expected salary RM16,000", "Expected wage RM 3,000" -- "on a
#     package of RM 150k", or "the candidate is paid RM 9,000". Nothing overrides
#     this; "his/her/their" alone does not count, as a recruiter "negotiated their
#     salary". Current/present/previous counts the same way unless the clause
#     opens with a work verb and names the organisation's money or people;
#   * otherwise a pay word and an amount, in either order ("Salary: RM 17,000",
#     "RM16,000 salary"), earnings or a bonus per period, lakhs per annum, or
#     "Last drawn RM 9,000" -- unless the words AROUND THE AMOUNT describe work
#     (_cv_pay_is_work_around): its comma part opens with a work verb ("Managed
#     total compensation of $12M"), or it names the organisation's money or
#     people ("budget", "for 300 staff", "across APAC",
#     "Head of Compensation from 2019"), it is someone else's pay the candidate
#     worked on ("negotiated their salary of RM 15k"), or a recruiter describes
#     the roles they fill ("placements with salaries up to RM 30k");
#   * pay talk with no amount -- "salary expectations are negotiable",
#     "Salary: negotiable" -- unless it is someone else's ("advised clients on
#     expected salary ranges", "salary expectations of new hires").
#
# Matching runs on an NFKC-normalised copy without Markdown emphasis, so
# "**Salary:** RM 17,000" reads as "Salary: RM 17,000" and full-width digits read
# as ordinary digits; digits in other scripts count as digits too. A letter
# currency code must not follow a Latin letter ("Form 16" holds no "RM 16"), but a
# neighbouring character such as "月薪" does not hide "RM8000". The kept text is
# the original.
_CV_PAY_TERM = (
    r"(?:salar(?:y|ies)|remuneration|total\s+compensation|compensation|ctc|"
    r"take[\s-]?home(?:\s+pay)?|epf(?:\s+contributions?)?|kwsp(?:\s+contributions?)?|"
    r"(?:monthly|annual|basic|base|gross|net|current|expected|last[\s-]+drawn|total)\s+(?:pay|package|income|wages?)|"
    r"(?:salary|pay|remuneration)\s+package|wages?|(?:monthly|annual|yearly)\s+(?:gross|nett?|basic))"
)
# Letter codes are words: "Form 16" holds no "RM 16" and "PHP 8" is a language.
_CV_PAY_CURRENCY_CODE = r"(?:rm|myr|sgd|usd|inr|rs\.?|aud|hkd|idr|rp|php|thb|cny|rmb|jpy|eur|gbp)"
_CV_PAY_CURRENCY_SYMBOL = r"(?:s\$|us\$|a\$|hk\$|\$|€|£|₹|₱|฿|¥)"
_CV_PAY_CURRENCY = r"(?:" + _CV_PAY_CURRENCY_CODE + r"|" + _CV_PAY_CURRENCY_SYMBOL + r")"
_CV_PAY_CURRENCY_WORD = (
    r"(?:ringgit|dollars?|rupees?|pesos?|baht|yuan|yen|euros?|pounds?|dirhams?|riyals?|rupiah)"
)
_CV_PAY_UNIT = r"(?:k|mil|million|m|lakhs?|lpa|crores?)"
_CV_PAY_PERIOD = (
    r"(?:per\s+(?:month|mth|annum|year|hour)|a\s+(?:month|year)|monthly|annually|yearly|"
    r"p\.?\s?a\b\.?|p\.?\s?m\b\.?|/\s?(?:month|mth|mo|m|annum|year|yr|y|a|hour|hr|h)\b)"
)
# An amount with a currency or a unit.
# A figure never starts inside another one: "2016" holds no "016".
# A letter code needs a word boundary before it -- a neighbouring non-Latin
# character such as "月薪" still counts as one -- and an amount with three or more
# figures or a unit after it ("RM 9,000", "RM9k"), so "PHP 8" is not money.
_CV_PAY_AMOUNT_MARKED = (
    r"(?:(?:(?<![a-z])" + _CV_PAY_CURRENCY_CODE
    + r"(?=\s?(?:\d[\d,.]{2,}|\d{1,3}(?:[ \u00a0]\d{3})+\b|\d[\d,.]*\s?" + _CV_PAY_UNIT + r"\b))"
    r"|" + _CV_PAY_CURRENCY_SYMBOL + r")\s?(?:\d{1,3}(?:[ \u00a0]\d{3})+\b|\d[\d,.]*(?:\s?" + _CV_PAY_UNIT + r")?\b)"
    r"|(?<![\d.,])\d[\d,.]*\s?" + _CV_PAY_UNIT + r"\b"
    r"|(?<![\d.,])\d[\d,.]*\s?" + _CV_PAY_CURRENCY + r"(?![a-z])"
    r"|(?<![\d.,])\d[\d,.]*\s?" + _CV_PAY_CURRENCY_WORD + r"\b)"
)
# A figure counting people or things is not money.
_CV_PAY_NOT_MONEY = (
    r"(?!\s*\+?\s*(?:employees|staff|headcounts?|workers|people|users|clients|customers|"
    r"candidates|members|records|transactions|accounts|students|executives|hires|"
    r"expatriates|plants|sites|branches|stores|units|countries|projects)\b)"
)
# What may follow a plain figure (no currency, no unit) for it to read as pay:
# the end of the clause, a pay period, a currency, or a pay qualifier. "Salary
# 2000" and "Salary of 5,000 per month" qualify; "total package of 1,500 SKUs" does
# not.
_CV_PAY_PLAIN_TAIL = (
    r"(?:[.!?)\]\"'*]*\s*$|\s*" + _CV_PAY_PERIOD + r"|\s*" + _CV_PAY_CURRENCY + r"(?![a-z])"
    r"|\s*" + _CV_PAY_UNIT + r"\b|\s*\+|\s+(?:net|nett|gross|only|negotiable|basic|plus|"
    r"excluding|including|inclusive|exclusive|before|after)\b)"
)
# A plain figure that looks like a year ("compensation from 2018 to 2022") is an
# amount only where the tail says so; any other plain figure also before a comma,
# a semicolon or "and".
_CV_PAY_AMOUNT_PLAIN = (
    r"(?:(?:19|20)\d{2}\b(?=" + _CV_PAY_PLAIN_TAIL + r")"
    r"|(?!(?:19|20)\d{2}\b)(?:\d{1,3}(?:,\d{3})+|\d{3,}(?:\.\d+)?)\b"
    r"(?=" + _CV_PAY_PLAIN_TAIL + r"|\s*[,;]|\s+(?:and|with)\b))"
)
_CV_PAY_AMOUNT = r"(?:" + _CV_PAY_AMOUNT_MARKED + _CV_PAY_NOT_MONEY + r"|" + _CV_PAY_AMOUNT_PLAIN + r")"
# "for the next role", said of the candidate's own move.
_CV_PAY_OWN_ROLE = (
    r"for\s+(?:this|the|a|an|my|any|new|next|future)\s+(?:[a-z]+\s+){0,2}"
    r"(?:role|position|job|opportunity|move)"
)
_CV_PAY_CONNECTOR = (
    r"(?:\s*[:=\-\u2013~]\s*|\s*\([^()]{1,20}\)\s*|\s+" + _CV_PAY_OWN_ROLE + r"\b\s*"
    r"|\s+(?:(?:was\s+|were\s+)?(?:cut|raised|increased|revised|adjusted|reduced|rose)\s+to"
    r"|per\s+(?:month|mth|annum|year)|in\s+(?:19|20)\d{2}|stands?\s+at|stood\s+at|drawn|history|worth"
    r"|of|is|was|at|around|about|approx(?:imately)?|circa|"
    r"currently|now|expected|expectations?|requirements?|above|below|over|under|up\s+to|"
    r"at\s+least|min(?:imum)?|max(?:imum)?|between|from|range|in\s+the\s+range\s+of)\b\.?\s*)"
)
_CV_PAY_WORD = (
    r"(?:salar(?:y|ies)|pay|package|remuneration|ctc|compensation|wages?|income|earnings|base|basic|"
    r"take[\s-]?home(?:\s+pay)?)"
)
# The organisation's money, not the candidate's pay: "RM 5M salary and benefits
# budget", "RM 2M in salary and overtime costs", "2k salary records".
_CV_PAY_ORG_MONEY = (
    r"(?!(?:\s+[a-z&]+){0,3}?\s+(?:costs?|budgets?|expenses?|spend(?:ing)?|bills?|savings?|"
    r"payments?|processing|disbursements?|increments?|reviews?|structures?|bands?|surveys?|"
    r"data|framework|administration|records?|slips?|runs?|liabilit(?:y|ies)|accruals?|"
    r"provisions?|claims?|funds?|pools?|forecasts?|reports?|audits?)\b)"
)
# Clearly the candidate's own: "my" / "candidate's", or current, expected, asking or
# last-drawn, before a pay word and an amount. Nothing around it overrides this.
_CV_PAY_OWN_RE = re.compile(
    r"\b(?:(?:my|(?:the\s+)?candidate['\u2019]s)\s+"
    r"(?:(?:current|present|expected|asking|desired|last[\s-]+drawn|previous)\s+)?"
    r"|(?:expected|expecting|asking|desired|last[\s-]+drawn)\s+)"
    r"(?:(?:monthly|annual|basic|base|gross|net|total|take[\s-]?home)\s+)?"
    + _CV_PAY_WORD + r"\b(?:" + _CV_PAY_CONNECTOR + r"){0,4}\s*" + _CV_PAY_AMOUNT
    # "On a package of RM 150k".
    + r"|\bon\s+an?\s+(?:(?:annual|monthly|total|base|basic|gross|current)\s+)?"
      r"(?:salary|package|pay|ctc)\s+of\s+" + _CV_PAY_AMOUNT_MARKED
    # "The candidate is paid RM 9,000 monthly".
    + r"|\b(?:(?:the\s+)?candidate|he|she|i)\s+(?:is|am|was|gets|got)\s+(?:currently\s+)?paid\b"
      r"[^;]{0,20}?" + _CV_PAY_AMOUNT_MARKED,
    re.I,
)
# "Current / present / previous salary RM 9,000": the candidate's own, unless the
# clause opens with a work verb AND names the organisation's money or people --
# "Restructured current compensation of RM 12M for 300 staff".
_CV_PAY_OWN_CURRENT_RE = re.compile(
    r"\b(?:current|present|previous)\s+"
    r"(?:(?:monthly|annual|basic|base|gross|net|total|take[\s-]?home)\s+)?"
    + _CV_PAY_WORD + r"\b(?:" + _CV_PAY_CONNECTOR + r"){0,4}\s*" + _CV_PAY_AMOUNT,
    re.I,
)
# A pay word and an amount, and the other ways of stating pay, which a sentence
# about work overrides (_CV_PAY_WORK_RE, _cv_pay_opens_with_work_verb).
_CV_PAY_AMOUNT_RE = re.compile(
    # A pay term, then an amount.
    r"\b" + _CV_PAY_TERM + r"\b(?:" + _CV_PAY_CONNECTOR + r"){0,4}\s*" + _CV_PAY_AMOUNT
    # An amount, then a pay term -- but not the organisation's money.
    + r"|" + _CV_PAY_AMOUNT_MARKED + r"\s+(?:[a-z]+\s+){0,2}?" + _CV_PAY_TERM + r"\b" + _CV_PAY_ORG_MONEY
    # "Last drawn RM 9,000", "Expected: RM 9,000", "Asking for RM 10k",
    # "Current: RM 9,000".
    + r"|\b(?:expected|expecting|asking(?:\s+for)?|desired|last[\s-]+drawn|current|"
      r"present|previous)\b(?:" + _CV_PAY_CONNECTOR + r"){0,3}\s*" + _CV_PAY_AMOUNT_MARKED
    # "Seeking RM 12k", "Looking for RM 12,000", "Seeking a senior role with RM
    # 12k monthly".
    + r"|\b(?:seeking|looking\s+for|targeting)\b[^;]{0,40}?" + _CV_PAY_AMOUNT_MARKED
    # "Package: RM 150,000", "Pay: RM 9k", "Income - RM 9,000".
    + r"|^\W*(?:package|pay|wages?|income|earnings|ctc)\s*[:=\-\u2013]\s*" + _CV_PAY_AMOUNT_MARKED
    # "Basic RM 7,000 + allowance RM 1,000", "Gross salary: RM 9,000".
    + r"|^\W*(?:basic|base|gross|nett?)(?:\s+(?:salary|pay))?\s*[:=\-\u2013]?\s*" + _CV_PAY_AMOUNT_MARKED
    # "Candidate's current role pays RM 9k".
    + r"|\b(?:role|job|position|employer)\s+pays\s+(?:about\s+|around\s+|approx(?:imately|\.)?\s*)?"
      + _CV_PAY_AMOUNT_MARKED
    # "RM 9,000 expected", "RM 9,000 negotiable".
    + r"|" + _CV_PAY_AMOUNT_MARKED + r"\s+(?:expected|asking|last[\s-]+drawn|negotiable)\b"
    # A clause that is only an amount per period: "RM 9,000 / month", "Gross RM
    # 9,000/month".
    + r"|^\W*(?:(?:gross|nett?|basic|base|total|approx(?:imately)?\.?|about|around|currently|now|at|"
      r"on|only)\s+)*" + _CV_PAY_AMOUNT_MARKED + r"\s*" + _CV_PAY_PERIOD
      + r"(?:\s*\(?(?:nett?|gross|basic|negotiable|only)\)?)?[\W_]*$"
    # Lakhs per annum.
    + r"|(?<![\d.,])\b\d[\d.,]*\s?(?:lpa|lakhs?\s+(?:per\s+annum|p\.?\s?a\b))"
    # Earnings per period. The text is already one sentence or clause, so a full
    # stop inside it ("approx.") is an abbreviation, not an end. "Drawing up" is
    # not drawing pay.
    + r"|\b(?:earn(?:s|ed|ing)?|draw(?:s|ing)?|drew|takes?\s+home|taking\s+home|took\s+home)\b(?!\s+up\b)"
      r"[^;]{0,40}?(?:" + _CV_PAY_AMOUNT_MARKED + r"|(?<![\d.,])\d{1,3}(?:,\d{3})+\b|(?<![\d.,])(?!(?:19|20)\d{2}\b)\d{3,}\b)\s*"
      r"(?:(?:in|of)\s+(?:commissions?|bonus(?:es)?|incentives?|salary|pay)\s+)?" + _CV_PAY_PERIOD
    # "Earning RM 9k.", "Currently earning 9K.": earnings opening the clause.
    + r"|^\W*(?:(?:currently|now)\s+)?(?:earning|earns|drawing|draws|taking\s+home|takes\s+home)\s+"
      r"(?:about\s+|around\s+|approx(?:imately|\.)?\s*)?" + _CV_PAY_AMOUNT_MARKED
    # "Paid RM 7k/mo.", "Making RM 9k a month": only opening the clause and right
    # before the amount, so "paid social spend" and "decision-making" are work.
    + r"|^\W*(?:(?:currently|now)\s+)?(?:paid|making|makes|receiv(?:es|ed|ing)|gets|getting)\s+"
      r"(?:about\s+|around\s+|approx(?:imately|\.)?\s*)?"
      r"(?:" + _CV_PAY_AMOUNT_MARKED + r"|(?<![\d.,])\d{1,3}(?:,\d{3})+\b|(?<![\d.,])(?!(?:19|20)\d{2}\b)\d{3,}\b)\s*" + _CV_PAY_PERIOD
    # "They are paid RM 9,000 a month" (a gender-neutral summary).
    + r"|\bthey\s+(?:are|were)\s+(?:currently\s+)?paid\b[^;]{0,20}?" + _CV_PAY_AMOUNT_MARKED
    # A bonus, commission or allowance per period.
    + r"|\b(?:bonus(?:es)?|commissions?|allowances?)\s*(?:of|:)?\s*" + _CV_PAY_AMOUNT_MARKED
      + r"\s*" + _CV_PAY_PERIOD,
    re.I,
)
# These additional formats get one pass, not another alternative in the
# overlapping amount-search loop: many pay phrases on a pasted line stay fast.
_CV_PAY_ADDITIONAL_AMOUNT_RE = re.compile(
    r"\b(?:(?:monthly|annual|yearly|gross|net|total)\s+)?earnings\s+(?:of|are|is)\s+"
    + _CV_PAY_AMOUNT_MARKED
    + r"|\b(?:(?:the\s+)?candidate|he|she|i|they)\s+(?:receiv(?:es|e|ed)|makes?|gets?|getting)\s+"
    r"(?:about\s+|around\s+|approx(?:imately|\.)?\s*)?" + _CV_PAY_AMOUNT_MARKED + r"\s*" + _CV_PAY_PERIOD
    + r"(?!\s+(?:in|for)\s+(?:client\s+)?(?:fees|revenue|billings?|funding|grants?|investments?)\b)",
    re.I,
)
# An independent personal-pay clause is not a work achievement just because
# the sentence opens with "Led". Require its own subject at a clause opening;
# "Analysed her earnings ... for the client" remains a work-verb object.
_CV_PAY_SUBJECT_CLAUSE_RE = re.compile(
    r"(?:^\W*|\b(?:and|but|while|whereas)\s+)(?:"
    # "They/their" can refer to employees or companies in a work sentence;
    # leave those ambiguous subjects to the established contextual matchers.
    r"(?:(?:the\s+)?candidate|he|she|i)\s+(?:receiv(?:es|e|ed)|makes?|gets?|getting)\s+"
    r"(?:about\s+|around\s+|approx(?:imately|\.)?\s*)?" + _CV_PAY_AMOUNT_MARKED + r"\s*" + _CV_PAY_PERIOD
    # A period abbreviation can backtrack before its final dot ("p.a.").
    # Business qualifiers must still apply to that complete period.
    + r"(?!\.?\s+(?:in|for)\s+(?:client\s+)?(?:fees|revenue|billings?|funding|grants?|investments?)\b)"
    + r"|(?:my|his|her|(?:the\s+)?candidate['\u2019]s)\s+"
      r"(?:(?:monthly|annual|yearly|gross|net|total)\s+)?earnings\s+(?:of|are|is)\s+"
      + _CV_PAY_AMOUNT_MARKED + r")",
    re.I,
)
_CV_PAY_ORG_EARNINGS_RE = re.compile(
    r"\b(?:company|business|corporate|group|firm|bank|client|portfolio)\s+"
    r"(?:(?:monthly|annual|yearly|gross|net|total)\s+)?earnings\b", re.I,
)
# Money or people that are the organisation's, or a job title or date, in the same
# sentence: the figure describes work, not the candidate's pay.
_CV_PAY_WORK_RE = re.compile(
    r"\b(?:budgets?|costs?|spend(?:ing)?|expenses?|revenue|turnover|profits?|margins?|"
    r"savings?|portfolio|aum|premiums?|procurement|billings?|fees|funding|grants?|investments?|"
    r"across(?!\s+(?:(?:the|all|his|her|their|my)\s+)?(?:base|basic|bonus(?:es)?|allowances?|salary|"
    r"pay|fixed|variable|cash|benefits?|components?|stipends?|commissions?)\b)|"
    r"for\s+(?:the\s+|our\s+|a\s+)?(?:firm|company|group|bank|business|"
    r"organi[sz]ation|clients?|region|department|division|unit)|"
    r"(?:in|of)\s+new\s+business|in\s+(?:revenue|fees|billings?)|"
    r"for\s+\d[\d,.]*\+?\s*(?:k\s+)?(?!(?:months?|years?|yrs?|weeks?|days?|hours?|lpa|lakhs?|crores?|"
    r"mil|million|k|m)\b)[a-z]+|"
    r"(?:to|for|across)\s+(?:the\s+|all\s+|our\s+)?(?:[a-z]+\s+|\d[\d,.]*\+?\s+){0,2}"
    r"(?:teams?|staff|employees|agents|workers|members|people|drivers|vendors|suppliers)"
    r"(?!\s+(?:lead|leader|manager|head|role|position|job|member)\b))\b",
    re.I,
)
# A recruiter describing the pay of the roles they fill: "placing C-suite leaders
# with compensation above USD 500k". Not when the clause says it is the
# candidate's own ("Recruiter earning RM 9k monthly").
_CV_PAY_RECRUITER_RE = re.compile(
    r"\b(?:recruit(?:er|ers|ing|ment)|headhunt\w*|executive\s+search|search\s+consultant|"
    r"talent\s+acquisition|placing|placements?|mandates?|vacanc(?:y|ies)|requisitions?|"
    r"for\s+(?:the\s+)?roles|roles\s+(?:with|paying|offering))\b",
    re.I,
)
_CV_PAY_OWN_VERB_RE = re.compile(
    r"\b(?:earn\w*|draw(?:s|ing)?|drew|receiv\w*|paid|making|makes|gets|getting|seeking|"
    r"looking\s+for|asking|expect\w*|my)\b",
    re.I,
)
# Someone else's pay the candidate worked on: "negotiated their salary of RM 15k".
_CV_PAY_OTHERS_PAY_RE = re.compile(
    r"\b(?:negotiat|benchmark|review|align|increas|rais|adjust|approv|determin|structur|manag|"
    r"handl|process|secur|set)\w*\s+(?:their|his|her|the|its)\s+(?:[a-z]+\s+)?"
    r"(?:salar(?:y|ies)|pay|compensation|packages?|remuneration)\b",
    re.I,
)
# A clause that opens with a work verb describes work: "Managed total
# compensation of $12M", "Placed 40 executives averaging $180k". The verbs a
# candidate states their own pay with (earned, drew, made, paid, received) are not
# on the list, and neither are the adjectives a summary opens with ("Seasoned",
# "Experienced").
_CV_PAY_WORK_VERB_FORMS = (
    ("manage", "managed"), ("lead", "led"), ("oversee", "oversaw"), ("administer", "administered"),
    ("process", "processed"), ("place", "placed"), ("negotiate", "negotiated"), ("reduce", "reduced"),
    ("generate", "generated"), ("own", "owned"), ("advise", "advised"), ("deliver", "delivered"),
    ("design", "designed"), ("develop", "developed"), ("build", "built"), ("implement", "implemented"),
    ("run", "ran"), ("drive", "drove"), ("grow", "grew"), ("handle", "handled"),
    ("supervise", "supervised"), ("coordinate", "coordinated"), ("direct", "directed"),
    ("execute", "executed"), ("establish", "established"), ("launch", "launched"),
    ("create", "created"), ("spearhead", "spearheaded"), ("streamline", "streamlined"),
    ("optimise", "optimised"), ("optimize", "optimized"), ("improve", "improved"),
    ("increase", "increased"), ("decrease", "decreased"), ("close", "closed"), ("sell", "sold"),
    ("recruit", "recruited"), ("hire", "hired"), ("train", "trained"), ("mentor", "mentored"),
    ("audit", "audited"), ("analyse", "analysed"), ("analyze", "analyzed"), ("prepare", "prepared"),
    ("review", "reviewed"), ("restructure", "restructured"), ("redesign", "redesigned"),
    ("benchmark", "benchmarked"), ("budget", "budgeted"), ("forecast", "forecasted"),
    ("allocate", "allocated"), ("control", "controlled"), ("monitor", "monitored"),
    ("track", "tracked"), ("calculate", "calculated"), ("compute", "computed"),
    ("reconcile", "reconciled"), ("disburse", "disbursed"), ("save", "saved"), ("cut", "cut"),
    ("lower", "lowered"), ("raise", "raised"), ("define", "defined"),
    ("write", "wrote"), ("set", "set"), ("plan", "planned"), ("model", "modelled"),
    ("report", "reported"), ("structure", "structured"), ("revamp", "revamped"),
    ("overhaul", "overhauled"), ("introduce", "introduced"), ("standardise", "standardised"),
    ("standardize", "standardized"), ("automate", "automated"), ("align", "aligned"),
    ("assess", "assessed"), ("evaluate", "evaluated"), ("conduct", "conducted"),
    ("organise", "organised"), ("organize", "organized"), ("operate", "operated"),
    ("maintain", "maintained"), ("ensure", "ensured"), ("achieve", "achieved"), ("win", "won"),
    ("bring", "brought"), ("spend", "spent"), ("teach", "taught"), ("consult", "consulted"),
    ("support", "supported"), ("collaborate", "collaborated"), ("boost", "boosted"),
    ("expand", "expanded"), ("scale", "scaled"), ("source", "sourced"), ("screen", "screened"),
    ("interview", "interviewed"), ("onboard", "onboarded"), ("fill", "filled"),
    ("chair", "chaired"), ("resolve", "resolved"), ("investigate", "investigated"),
    ("approve", "approved"), ("validate", "validated"), ("verify", "verified"),
    ("research", "researched"), ("survey", "surveyed"), ("collect", "collected"),
    ("gather", "gathered"), ("capture", "captured"), ("compile", "compiled"),
    ("facilitate", "facilitated"), ("guide", "guided"),
    ("coach", "coached"), ("deploy", "deployed"), ("migrate", "migrated"),
    ("integrate", "integrated"), ("configure", "configured"), ("test", "tested"),
    ("architect", "architected"), ("engineer", "engineered"), ("price", "priced"),
    ("pitch", "pitched"),
)


def _cv_pay_work_verb_words():
    words = set()
    for base, past in _CV_PAY_WORK_VERB_FORMS:
        third = base + ("es" if re.search(r"(?:s|sh|ch|x|z|o)$", base) else "s")
        stem = base[:-1] if base.endswith("e") and not base.endswith("ee") else base
        if re.search(r"[^aeiou][aeiou][bdgmnprt]$", base) and base not in {"audit", "budget", "benchmark",
                                                                           "develop", "market", "model"}:
            stem = base + base[-1]
        words.update({base, past, third, stem + "ing"})
    return frozenset(words)


_CV_PAY_WORK_VERBS = _cv_pay_work_verb_words()
_CV_PAY_FIRST_WORD_RE = re.compile(
    r"^\W*(?:(?:successfully|effectively|personally|jointly|also|then)\s+)?([a-z]+)", re.I
)


# Pay talk with no amount that can be about anyone's pay -- "expected salary",
# "salary expectations" -- is the candidate's own only when nothing around it says
# it is someone else's: see _cv_pay_talk_is_candidates.
_CV_PAY_TALK_RE = re.compile(
    r"\b(?:expected|expecting|asking|desired|last[\s-]+drawn)\s+"
    r"(?:monthly\s+|annual\s+|basic\s+|take[\s-]?home\s+)?"
    r"(?:salar(?:y|ies)|remuneration|ctc|pay|package|compensation)\b"
    r"|\b(?:salar(?:y|ies)|remuneration|ctc|compensation|pay)\s+(?:expectations?|requirements?)\b",
    re.I,
)
# Pay talk only a candidate says of their own pay: "salary is negotiable",
# "Salary: negotiable", "open to discuss remuneration".
_CV_PAY_OWN_TALK_RE = re.compile(
    r"\b(?:salar(?:y|ies)|remuneration|ctc|compensation|pay|package)\s+(?:is\s+|are\s+)?negotiable\b"
    r"|\b(?:salar(?:y|ies)|remuneration|ctc|compensation|pay|package)\s*[:\-\u2013]\s*"
    r"(?:negotiable|nego\b|flexible|confidential|open\b|tbc\b|tbd\b|to\s+be\s+(?:discussed|negotiated)|"
    r"on\s+request|market\s+rate|as\s+per\s+company)"
    r"|\bnegotiable\s+(?:salar(?:y|ies)|remuneration|ctc|pay|package)\b"
    r"|\b(?:open|willing)\s+to\s+(?:discuss|negotiate)\s+(?:the\s+|my\s+|his\s+|her\s+|their\s+)?"
    r"(?:salar(?:y|ies)|remuneration|ctc|pay|package|compensation)\b",
    re.I,
)
# After the pay talk: "... of new hires", "... were benchmarked", "... data" --
# but "for the next role" is the candidate's own move.
_CV_PAY_TALK_OTHERS_AFTER_RE = re.compile(
    r"\s+(?:of|(?!" + _CV_PAY_OWN_ROLE + r"\b)for|across|among|from|under|"
    r"(?:were|was|are|is|been|being)\s+[a-z]+ed|increments?|increases?|adjustments?|movements?|"
    r"reviews?|structures?|planning|plans?|negotiations?|negotiating|exceed\w*|var(?:y|ies|ied)|gaps?|"
    r"mismatch\w*|conversations?|discussions?|queries|questions|alignment|guidance|advice|advisory|"
    r"counsel\w*|coaching|insights?|"
    r"benchmark\w*|surveys?|data|analysis|analytics|framework|polic(?:y|ies)|guidelines?|"
    r"trends?|modell?ing|models?|costs?|budgets?|management|process(?:es|ing)?|dashboards?|"
    r"reports?|tools?|templates?|matri(?:x|ces)|ranges?|bands?|scales?|grades?)\b",
    re.I,
)
# Before it: whose expectations, or the work done on them -- "candidates' salary
# expectations", "Advised on salary expectations".
_CV_PAY_TALK_OTHERS_BEFORE_RE = re.compile(
    r"(?:\b(?:candidates|applicants|hires|employees|staff|talent|clients|teams?|workers|"
    r"members|people|executives|expatriates|new\s+joiners)['\u2019]?"
    r"|\b(?:manag(?:e|ed|es|ing)|advis(?:e|ed|es|ing)(?:\s+on)?|handl(?:e|ed|es|ing)|"
    r"align(?:ed|s|ing)?|negotiat(?:e|ed|es|ing)|benchmark(?:ed|s|ing)?|assess(?:ed|es|ing)?|"
    r"gather(?:ed|s|ing)?|captur(?:e|ed|es|ing)|collect(?:ed|s|ing)?|understand(?:s|ing)?|"
    r"understood|discuss(?:ed|es|ing)?|balanc(?:e|ed|es|ing)|match(?:ed|es|ing)?|"
    r"clarif(?:y|ied|ies|ying)|review(?:ed|s|ing)?|evaluat(?:e|ed|es|ing)|analy[sz](?:e|ed|es|ing)|"
    r"survey(?:ed|s|ing)?|track(?:ed|s|ing)?)(?:\s+on)?(?:\s+(?:the|their|all|market))?)\s+$",
    re.I,
)


def _cv_pay_opens_with_work_verb(text):
    """Whether a clause opens with a verb describing work rather than pay."""
    match = _CV_PAY_FIRST_WORD_RE.match(text)
    return bool(match) and match.group(1).lower() in _CV_PAY_WORK_VERBS


def _cv_pay_talk_is_candidates(text, match):
    """Whether pay talk with no amount is about the candidate's own pay."""
    if _CV_PAY_TALK_OTHERS_AFTER_RE.match(text, match.end()):
        return False
    begin, finish = _cv_pay_segment(text, match.start())
    if _cv_pay_opens_with_work_verb(text[begin:finish]):
        return False
    return not _CV_PAY_TALK_OTHERS_BEFORE_RE.search(text[begin:match.start()])


# Abbreviations whose full stop does not end a sentence: they come before a name
# or a figure ("Sr. Manager", "Sept. 2024", "Rs. 50,000", "Sdn. Bhd."). Ones a
# sentence can end with -- "Sdn Bhd.", "Ltd.", "etc." -- are not listed, so
# "Worked at Acme Sdn Bhd. Expected salary RM 9k." loses only its second sentence.
_CV_ABBREVIATIONS = frozenset({
    "mr", "mrs", "ms", "dr", "sr", "jr", "st", "no", "nos", "vs", "sdn", "approx", "est",
    "prof", "rs", "fig", "vol",
})
# A stop that may or may not end a sentence -- after "Co.", a month, a single
# letter ("Python and C.") or a dotted token ("the U.S.") -- ends one only when
# the next sentence states the candidate's pay on its own, so a fact before a pay
# sentence is never lost with it.
_CV_AMBIGUOUS_ABBREVIATIONS = frozenset({
    "co", "corp", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct",
    "nov", "dec",
})
# Dotted abbreviations that end a pay sentence: "RM 9k p.a. Built pipelines."
_CV_SENTENCE_ENDING_DOTTED = frozenset({"p.a", "p.m"})
# A sentence ends at . ! or ?, after any closing quote, bracket or Markdown
# emphasis ("**Expected salary RM 9k.** Available"), before the next sentence; or
# at a stop with no space before a capitalised word ("RM 9,000.Led"). A run of
# stops is looked at once, from its start, so a long run of dots cannot slow it.
# Before a lowercase word the stop is "weak": it ends a sentence only when the
# next one states pay ("Head of Payroll. salary RM 15k.").
_CV_SENTENCE_END_RE = re.compile(
    r"(?<![.!?])[.!?]+[\"')\]*_]*\s+(?=(?P<upper>[\"'(*_A-Z0-9])|(?P<lower>[a-z]))"
    r"|(?<=[a-z0-9]{2})[.!?](?=[A-Z][a-z]{2,})"
)
_CV_NUMBER_TOKEN_RE = re.compile(r"[\d.,%]+")


def _cv_token_before(text, start, stop):
    """(the word right before `stop`, whether another word comes before it).

    Walks back from `stop` only as far as it needs to, so the splitter stays
    linear however many abbreviations a line holds.
    """
    index = stop
    while index > start and not text[index - 1].isspace():
        index -= 1
    token = text[index:stop]
    while index > start and text[index - 1].isspace():
        index -= 1
    return token, index > start


def _cv_split_sentence_spans(text):
    """(start, end) of each sentence, without breaking at "Sr." or "B.Sc."."""
    spans = []
    start = 0
    for match in _CV_SENTENCE_END_RE.finditer(text):
        token, more_before = _cv_token_before(text, start, match.start())
        token = token.strip("(*_\"'")
        # A figure ends a sentence ("a team of 8.", "margin by 5.5%."), unless it
        # is all there is, as in a list number ("1. Built ...").
        is_number = bool(_CV_NUMBER_TOKEN_RE.fullmatch(token)) and more_before
        lowered = token.lower()
        weak = bool(match.group("lower"))
        ambiguous = weak or (
            not (lowered in _CV_SENTENCE_ENDING_DOTTED or is_number)
            and (len(token) <= 1 or "." in token or lowered in _CV_AMBIGUOUS_ABBREVIATIONS)
        )
        if lowered in _CV_ABBREVIATIONS or (not is_number and _CV_NUMBER_TOKEN_RE.fullmatch(token)):
            # "Sr. Manager"; a list number on its own ("1. Built ...").
            continue
        if ambiguous:
            following = _CV_SENTENCE_END_RE.search(text, match.end())
            next_sentence = text[match.end():following.end() if following else len(text)]
            if not _cv_states_candidate_pay(next_sentence.split(";")[0]):
                continue
        spans.append((start, match.end()))
        start = match.end()
    spans.append((start, len(text)))
    trimmed = []
    for begin, finish in spans:
        piece = text[begin:finish]
        if piece.strip():
            lead = len(piece) - len(piece.lstrip())
            trimmed.append((begin + lead, begin + len(piece.rstrip())))
    return trimmed


def _cv_split_sentences(text):
    """Split prose into sentences without breaking at "Sr." or "B.Sc."."""
    return [text[begin:finish] for begin, finish in _cv_split_sentence_spans(text)]


# Markdown emphasis the summary may carry ("**Salary:** RM 17,000"), removed from
# the copy that is matched, never from the text that is kept.
_CV_PAY_MARKUP_RE = re.compile(r"[*`]+|__")


def _cv_pay_matchable(text):
    """The copy of a clause that is matched: NFKC, without Markdown emphasis."""
    return _CV_PAY_MARKUP_RE.sub("", unicodedata.normalize("NFKC", str(text or ""))).strip()


def _cv_pay_part_is_work(matchable):
    """Whether a whole clause or part describes work (the organisation's money or
    people, someone else's pay, or a work verb opening it)."""
    return bool(
        _CV_PAY_WORK_RE.search(matchable)
        or _CV_PAY_OTHERS_PAY_RE.search(matchable)
        or _cv_pay_opens_with_work_verb(matchable)
    )


# Where the words about a pay phrase begin: the start of its comma part, or a word
# that attaches pay to someone ("with", "earning", "on a").
_CV_PAY_ATTACH_RE = re.compile(r"\b(?:with|earning|drawing|while|whilst|on\s+an?|at\s+an?)\b", re.I)
_CV_PAY_WORD_RE = re.compile(r"[A-Za-z]+(?:['\u2019-][A-Za-z]+)*")
# One pay attached to the person: "with salary RM 20k", "with a salary of", "earning"
# -- unlike "with average salaries of RM 15k", "with packages above" or a range
# ("with total compensation up to $250k").
_CV_PAY_OWN_ATTACH_RE = re.compile(
    r"(?:with|on|at)\s+(?:an?\s+|my\s+)?(?:(?:monthly|annual|basic|base|gross|nett?|total|current)\s+)?"
    r"(?:salary|pay|package|ctc|remuneration|compensation|wage|income|earnings)\b(?!\s+(?:of|for)\s+(?:the\s+)?"
    r"(?:\d|team|staff|employees|workers|hires|candidates))"
    # A range is other people's: "with total compensation up to $250k".
    r"(?!\s+(?:up\s+to|above|over|below|under|averaging|ranging|between|from|starting|of\s+up\s+to)\b)"
    r"|earning\b|drawing\b",
    re.I,
)

# Explicit recipients of the amount are payroll work, including one employee.
# Keep this local to the pay phrase, and reject job-title continuations such as
# "for the team leader role". Words in another comma/sentence cannot shelter pay.
_CV_PAY_EMPLOYEE_PHRASE = (
    r"(?:(?:with|on|at)\s+(?:an?\s+)?)?"
    r"(?:salary|pay|package|ctc|remuneration|compensation|wage|income)\b"
    r"(?:" + _CV_PAY_CONNECTOR + r"){0,4}\s*" + _CV_PAY_AMOUNT
    + r"(?:\s*" + _CV_PAY_PERIOD + r")?\s+"
    r"(?:per\s+|for\s+(?:(?:each|every|an?|the)\s+)?)(?:employee|worker)\b"
)
_CV_PAY_EMPLOYEE_JOB_TITLE = (
    # A short nominal title is not a payroll recipient: "employee relations
    # manager role". Relative/action clauses stay work: "employee who works in
    # a support role", "worker assigned to a construction job".
    r"(?:['’]s)?(?:\s+|-)(?:(?!(?:who|that|which|a|an|the|in|on|to|for|with|at)\b)"
    r"[A-Za-z][A-Za-z-]{0,39}\s+){0,5}(?:role|position|job)\b"
)
_CV_PAY_EMPLOYEE_RECIPIENT_RE = re.compile(
    _CV_PAY_EMPLOYEE_PHRASE + r"(?!\s+of\s+the\s+candidate\b)(?!" + _CV_PAY_EMPLOYEE_JOB_TITLE + r")", re.I)
_CV_PAY_EMPLOYEE_ROLE_RE = re.compile(_CV_PAY_EMPLOYEE_PHRASE + _CV_PAY_EMPLOYEE_JOB_TITLE, re.I)


# How far either side of a pay phrase its words are read. A clause is a sentence
# part, so this is far more than real text needs; it keeps the reading of a very
# long pasted line linear however many pay phrases it holds.
_CV_PAY_CONTEXT_CHARS = 300


def _cv_pay_segment(text, position):
    """(start, end) of the comma part of `text` holding `position`, read no
    further than _CV_PAY_CONTEXT_CHARS either side."""
    low = max(0, position - _CV_PAY_CONTEXT_CHARS)
    high = min(len(text), position + _CV_PAY_CONTEXT_CHARS)
    comma = text.rfind(",", low, position)
    after = text.find(",", position, high)
    return (comma + 1 if comma >= 0 else low), (after if after >= 0 else high)


def _cv_pay_is_work_around(text, position):
    """Whether the words around the pay phrase at `position` describe work.

    Only its own comma part counts, so "Heads the revenue team, salary RM 20k"
    is pay. A part opening with a work verb is work ("Placed 120 candidates with
    average salaries of RM 15k"); otherwise the part is cut at the word that
    attaches the pay to someone, so "Sales manager across APAC with salary of USD
    150,000" is pay. A work verb just before the pay phrase is work too
    ("Seasoned payroll specialist handling salaries of RM 2M").
    """
    begin, finish = _cv_pay_segment(text, position)
    segment = text[begin:finish]
    offset = position - begin
    cut = 0
    for attach in _CV_PAY_ATTACH_RE.finditer(segment, 0, offset + 1):
        cut = attach.start()
    local = segment[cut:]
    opens_work = _cv_pay_opens_with_work_verb(segment)
    own_attachment = bool(cut and (_CV_PAY_OWN_ATTACH_RE.match(local)
                                  or _CV_PAY_EMPLOYEE_ROLE_RE.match(local)))
    # This already-unambiguous work case needs no recruiter/context scans.
    if opens_work and not own_attachment:
        return True
    if _CV_PAY_RECRUITER_RE.search(segment) and not _CV_PAY_OWN_VERB_RE.search(segment):
        return True
    # "Leads a budget of RM 5M with salary RM 20k": one pay attached to the person
    # is theirs, whatever work the sentence opened with.
    if own_attachment:
        # Match from the attachment across the exact amount: its thousands
        # comma is not a clause break, but a real comma before "for" still is.
        if opens_work:
            recipient_text = text[begin + cut:begin + cut + _CV_PAY_CONTEXT_CHARS]
            recipient = _CV_PAY_EMPLOYEE_RECIPIENT_RE.match(recipient_text)
            if recipient and position - begin - cut < recipient.end():
                return True
        return False
    if _CV_PAY_OTHERS_PAY_RE.search(segment):
        return True
    if _CV_PAY_WORK_RE.search(local):
        return True
    if "earnings" in local.lower() and _CV_PAY_ORG_EARNINGS_RE.search(local):
        return True
    before = _CV_PAY_WORD_RE.findall(segment[cut:offset])[-3:]
    return any(word.lower() in _CV_PAY_WORK_VERBS for word in before)


# A plain year after "from", "since" and the like is a date, not an amount:
# "Head of Compensation from 2019".
_CV_PAY_DATED_YEAR_RE = re.compile(r"\b(?:from|since|between|until|till|in)\s+(?:19|20)\d{2}\W*$", re.I)
# Every amount form needs a digit; the no-amount forms need a pay word. Avoid
# running all matchers on every short fragment in a long abbreviation chain.
_CV_PAY_POSSIBLE_RE = re.compile(
    r"\d|salar|pay|package|remuneration|ctc|compensation|wage|income|earning|"
    r"base|basic|bonus|commission|allowance", re.I,
)
_CV_PAY_TERM_START_RE = re.compile(_CV_PAY_TERM + r"\b", re.I)


def _cv_states_candidate_pay(text):
    """Whether a sentence or clause states the candidate's pay.

    Whether a pay phrase is work is judged from the words around it, not from
    anywhere in the clause (_cv_pay_is_work_around).
    """
    matchable = _cv_pay_matchable(text)
    if not _CV_PAY_POSSIBLE_RE.search(matchable):
        return False
    if _CV_PAY_OWN_RE.search(matchable) or _CV_PAY_SUBJECT_CLAUSE_RE.search(matchable):
        return True
    for match in _CV_PAY_OWN_CURRENT_RE.finditer(matchable):
        begin, finish = _cv_pay_segment(matchable, match.start())
        segment = matchable[begin:finish]
        if not (_cv_pay_opens_with_work_verb(segment) and _CV_PAY_WORK_RE.search(segment)):
            return True
    lowered = matchable.lower()
    if any(word in lowered for word in ("earnings", "receiv", "make", "get")):
        for match in _CV_PAY_ADDITIONAL_AMOUNT_RE.finditer(matchable):
            if not _cv_pay_is_work_around(matchable, match.start()):
                return True
    # Every place a pay phrase starts is judged, including one inside a longer
    # match: "RM 5M with salary" must not hide "salary RM 20k".
    position = 0
    while True:
        match = _CV_PAY_AMOUNT_RE.search(matchable, position)
        if not match:
            break
        position = match.start() + 1
        if _CV_PAY_DATED_YEAR_RE.search(match.group(0)):
            continue
        if not _cv_pay_is_work_around(matchable, match.start()):
            return True
        # A leading pay term's direct amount has no inner pay phrase to visit.
        # Reverse matches ("RM 5M with salary") still restart one character on,
        # so they cannot hide the embedded "salary RM 20k".
        if _CV_PAY_TERM_START_RE.match(matchable, match.start()):
            position = match.end()
    for match in _CV_PAY_OWN_TALK_RE.finditer(matchable):
        begin, finish = _cv_pay_segment(matchable, match.start())
        if not _cv_pay_opens_with_work_verb(matchable[begin:finish]):
            return True
    return any(
        _cv_pay_talk_is_candidates(matchable, match)
        for match in _CV_PAY_TALK_RE.finditer(matchable)
    )


def _cv_balance_bold(text):
    """Drop a Markdown "**" left without its partner by a removed sentence."""
    if text.count("**") % 2 == 0:
        return text
    at = text.rfind("**")
    return re.sub(r"\s{2,}", " ", (text[:at] + text[at + 2:])).strip()


# In a sentence that states pay, another clause is part of the same statement when
# it carries an amount or continues the pay ("RM 1,500 allowances", "plus 2 months
# bonus"), unless it describes work.
_CV_PAY_CONTINUATION_RE = re.compile(
    r"^\W*(?:plus|excluding|excl\.?|including|incl\.?|exclusive|inclusive|expected|"
    r"current|present|previous|last[\s-]+drawn|asking|negotiable|basic|bonus(?:es)?|allowances?|"
    r"commissions?|epf|kwsp|nett?|gross|ctc|package)\b"
    r"|^\W*(?:with|and|or)\b.*\b(?:bonus(?:es)?|allowances?|commissions?|epf|kwsp|increments?|"
    r"salar(?:y|ies)|pay|package|ctc|benefits)\b|" + _CV_PAY_AMOUNT_MARKED,
    re.I,
)
# Words that make a leftover comma part part of the pay statement ("Earning, on
# average").
_CV_PAY_FRAGMENT_RE = re.compile(
    r"\b(?:salar(?:y|ies)|pay|package|remuneration|compensation|ctc|wages?|income|earn\w*|"
    r"draw\w*|drew|expected|expecting|asking|seeking|looking|receiv\w*|makes|gets|paid)\b",
    re.I,
)


_CV_PAY_AMOUNT_MARKED_RE = re.compile(_CV_PAY_AMOUNT_MARKED, re.I)


def _cv_pay_amount_only(part):
    """Whether a part right before a pay part is just more of it: "RM 9,000"."""
    matchable = _cv_pay_matchable(part)
    return bool(_CV_PAY_AMOUNT_MARKED_RE.search(matchable)) and not _cv_pay_part_is_work(matchable)


def _cv_mark_continuations(parts, flags):
    """Mark the parts next to a pay part that carry on its statement.

    After it: a part with an amount or one that continues the pay ("plus 2 months
    bonus"). Before it: only a part carrying an amount ("RM 9,000; Expected: RM
    11,000"). Anything further away stays.
    """
    flags = list(flags)
    for index in range(1, len(parts)):
        if not flags[index] and flags[index - 1] and _cv_pay_continues(parts[index]):
            flags[index] = True
    for index in range(len(parts) - 2, -1, -1):
        if not flags[index] and flags[index + 1] and _cv_pay_amount_only(parts[index]):
            flags[index] = True
    return flags


def _cv_pay_clause_remainder(clause):
    """What is left of a pay clause once its comma-separated pay parts are gone.

    "Expected salary RM 9k, CIPD-certified HR leader" keeps "CIPD-certified HR
    leader", and "Grew revenue to RM 5M, expected salary RM 9k" keeps its revenue.
    What is left must read as a phrase of its own, starting with a
    capital; "Current salary RM 9k, managing 10 staff" leaves nothing rather than
    "managing 10 staff". When the pay cannot be told apart, or what is left still
    talks about pay, nothing is left.
    """
    parts = [part.strip() for part in re.split(r",\s+", clause) if part.strip()]
    if len(parts) < 2:
        return ""
    flags = [_cv_states_candidate_pay(part) for part in parts]
    if not any(flags):
        return ""
    flags = _cv_mark_continuations(parts, flags)
    kept = [part for part, flag in zip(parts, flags) if not flag]
    # Money left in a part that is not work is still the pay statement: "Expected
    # salary RM 9k, Senior engineer, RM 1,500 allowances" leaves nothing, while
    # "Grew revenue to RM 5M, expected salary RM 9k" keeps its revenue.
    if not kept or any(_CV_PAY_FRAGMENT_RE.search(part) or _cv_pay_amount_only(part) for part in kept):
        return ""
    remainder = ", ".join(kept)
    if not re.match(r"[\W_]*[A-Z0-9]", _CV_PAY_MARKUP_RE.sub("", remainder)):
        return ""
    return remainder


def _cv_pay_continues(clause):
    """Whether a clause next to a pay clause belongs to the same pay statement."""
    matchable = _cv_pay_matchable(clause)
    return bool(_CV_PAY_CONTINUATION_RE.search(matchable)) and not _cv_pay_part_is_work(matchable)


def _cv_strip_pay_from_prose(text):
    """(text without its pay statements, number of sentences that stated pay).

    Sentences are kept or removed whole, and so are the clauses of a sentence
    joined by semicolons, so the rest of a bullet reads as written. A clause that
    carries on the pay statement goes with it.
    """
    removed = 0
    source = str(text or "").strip()
    # Kept sentences are joined with the spacing they had ("booking.Com" stays
    # whole); a space stands in only where a removed sentence was between them.
    result = ""
    previous_end = None
    for begin, finish in _cv_split_sentence_spans(source):
        sentence = source[begin:finish]
        clauses = [c.strip() for c in sentence.split(";") if c.strip()]
        states_pay = [_cv_states_candidate_pay(c) for c in clauses]
        pay = _cv_mark_continuations(clauses, states_pay) if any(states_pay) else states_pay
        kept = []
        for clause, is_pay, own in zip(clauses, pay, states_pay):
            if not is_pay:
                kept.append(clause)
            elif own:
                remainder = _cv_pay_clause_remainder(clause)
                if remainder:
                    kept.append(remainder)
        dropped = any(pay)
        removed += 1 if dropped else 0
        if not dropped:
            piece = sentence
        elif kept:
            piece = "; ".join(kept)
            ending = re.search(r"[.!?][\"')\]]*$", sentence)
            if ending and not re.search(r"[.!?][\"')\]]*$", piece):
                piece += ending.group(0)
        else:
            previous_end = None
            continue
        if result:
            result += source[previous_end:begin] if previous_end is not None else " "
        result += piece
        previous_end = finish
    return (_cv_balance_bold(result) if removed else result), removed


def _cv_strip_pay_from_summary_counted(bullets):
    """(summary bullets with the candidate's pay removed, number of statements removed).

    A bullet left with nothing is dropped; a bullet without pay is returned as it
    was. An item that is not text is never edited: the Word file writes it as text,
    so it is dropped whole when that text states pay, and kept as it was otherwise.
    """
    if not isinstance(bullets, list):
        return bullets, 0
    kept = []
    removed_total = 0
    for bullet in bullets:
        if bullet is None:
            continue
        if not isinstance(bullet, str):
            if _cv_strip_pay_from_prose(str(bullet))[1]:
                removed_total += 1
            else:
                kept.append(bullet)
            continue
        text = bullet.strip()
        if not text:
            continue
        stripped, removed = _cv_strip_pay_from_prose(text)
        removed_total += removed
        if not removed:
            kept.append(bullet)
        elif stripped:
            kept.append(stripped)
    return kept, removed_total


def _cv_strip_pay_from_summary(bullets):
    """Summary bullets with every statement of the candidate's pay removed."""
    return _cv_strip_pay_from_summary_counted(bullets)[0]


# A line's list marker: "-", "*", "\u2022", or a number ("1.", "2)").
_CV_SUMMARY_LINE_RE = re.compile(r"^(\s*(?:(?:[-\u2022*]|\d{1,2}[.)])\s+)?)(.*?)(\s*)$", re.S)


def _cv_strip_pay_from_summary_text(raw):
    """(raw provider summary text with pay statements removed, number removed).

    Works line by line on the provider's own text, keeping each line's list
    marker, so the browser parses the result exactly as it parses any summary.
    When every list line was pay, what is left -- an intro such as "Here is the
    summary:" -- is not a summary, and the browser would read it as one, so the
    result is empty.
    """
    lines = []
    removed_total = 0
    had_items = kept_items = False
    for line in str(raw or "").split("\n"):
        match = _CV_SUMMARY_LINE_RE.match(line)
        marker, body, trailing = match.group(1), match.group(2), match.group(3)
        if not body.strip():
            lines.append(line)
            continue
        is_item = bool(marker.strip())
        had_items = had_items or is_item
        stripped, removed = _cv_strip_pay_from_prose(body)
        removed_total += removed
        if not removed:
            lines.append(line)
            kept_items = kept_items or is_item
        elif stripped:
            lines.append(marker + stripped + trailing)
            kept_items = kept_items or is_item
    if removed_total and had_items and not kept_items:
        return "", removed_total
    return "\n".join(lines), removed_total
