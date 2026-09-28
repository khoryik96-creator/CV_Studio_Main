"""CV parse fidelity validation for CV Studio.

Observational post-parse stage: it compares the final reconciled/normalized CV
against its source text and reports where structure may have been lost --
dropped employers or a large bullet shortfall -- WITHOUT mutating the parsed
data.

This is the audit seam that would have surfaced the dropped-bullet regression:
a reconciliation step that silently deletes bullets shows up here as a
bullet-retention shortfall, and a dropped employer shows up as a missing
source employer. Because the stage never changes ``parsed``, wiring it into the
``/parse`` flow cannot alter output -- at worst it attaches a ``fidelity``
report and, when material loss is detected, sets the existing degraded/warning
fields.

Pure functions of their inputs (parsed dict + source text) -- no Flask, no
globals, no network, no AI call. This module never imports ``app``. It reuses
the deterministic source extractors that already live in cvstudio_cv_reconcile
so "source truth" is defined in exactly one place.
"""

import re

from cvstudio_cv_normalize import (
    _cv_match_key,
    _cv_token_overlap_score,
)
from cvstudio_cv_reconcile import (
    _extract_authoritative_work_rows,
    _flatten_parsed_work_roles,
    _role_plain_bullets,
)

# A source employer counts as "present" in the parsed output when a parsed
# company shares its match key or a strong token overlap. Mirrors the identity
# test the reconciler uses so the two stages agree on what an employer is.
_EMPLOYER_MATCH_OVERLAP = 0.67

# Bullet retention: only a *material* shortfall on a CV that actually carried a
# meaningful number of source bullets is worth flagging. This avoids firing on
# short CVs or on imperfect PDF bullet extraction.
_BULLET_MIN_SOURCE = 6
_BULLET_SHORTFALL_RATIO = 0.6

# Lines that look like CV bullets in the raw source text. Deliberately narrow:
# a leading bullet glyph or dash/asterisk followed by whitespace and content.
_SOURCE_BULLET_RE = re.compile(
    r"^\s*(?:[•●▪◦‣⁃∙·‧]|[-*])\s+\S"
)

# Experience-section delimiters, mirrored from cvstudio_cv_reconcile so the two
# stages agree on where the work history begins and ends. Bullet counting is
# confined to this span: parsed bullets only come from work experience, so a
# whole-document bullet count would be inflated by bulleted skills / profile /
# education sections and fire false shortfall warnings.
_EXPERIENCE_HEADING_RE = re.compile(
    r"^(?:EMPLOYMENT|WORK|CAREER|PROFESSIONAL)\s+(?:HISTORY|EXPERIENCES?)\b"
    r"|^(?:HISTORY|EXPERIENCES?)\s*:?\s*$",
    re.I,
)
_SECTION_STOP_HEADING_RE = re.compile(
    r"^(?:EDUCATION|ACADEMIC|CERTIFICATION|CERTIFICATIONS|REFERENCE|REFERENCES|"
    r"SKILLS|TECHNICAL SKILLS|ADDITIONAL INFORMATION|LANGUAGES?|PROJECTS?|"
    r"INTERESTS?|HOBBIES|PROFILE|SUMMARY|AWARDS?)\b",
    re.I,
)


# A CV that writes its employers as labelled cells -- "Company: Acme Sdn Bhd" --
# has no Dates/Organization/Role columns for the authoritative-row reader to find,
# so that reader returns nothing and a shortfall goes unnoticed. The label itself
# is high-confidence evidence: a line that says "Company:" is naming an employer.
_LABELLED_COMPANY_RE = re.compile(
    r"^[ \t]*compan(?:y|ies)[ \t]*[:\-\u2013\u2014][ \t]*(.+)$",
    re.I | re.M,
)

# The extractor joins a table row's cells with " | ", so an Industry cell rides
# along on the same line as the company it sits beside.
_LABELLED_COMPANY_TRAILER_RE = re.compile(
    r"\s*\|.*$|\s*\bindustry\b\s*[:\-].*$", re.I
)


def _source_labelled_companies(cv_text):
    """Employer names the source labels outright with a "Company:" prefix."""
    names = []
    for raw in _LABELLED_COMPANY_RE.findall(str(cv_text or "")):
        name = _LABELLED_COMPANY_TRAILER_RE.sub("", str(raw or ""))
        name = re.sub(r"\s+", " ", name).strip(" .,;:|-")
        # A label with nothing after it, or a whole paragraph, is not a name.
        if name and 2 <= len(name) <= 120:
            names.append(name)
    return names


def _source_employers(cv_text, parsed=None):
    """Distinct high-confidence employers extracted from the source text."""
    employers = []
    seen = set()
    candidates = [
        str(row.get("company") or "").strip()
        for row in _extract_authoritative_work_rows(cv_text, parsed)
    ]
    # Read the labels from the work-history section only. A referees block or a
    # cover note can also say "Company:", and an employer expected from outside
    # the work history would be reported missing on a perfectly good parse.
    # Read the labels from the work-history section only, and only when that
    # section could actually be located. A referees block or a cover note can also
    # say "Company:", and an employer expected from outside the work history would
    # be reported missing on a perfectly good parse. No section, no claim.
    scoped = _experience_section_text(cv_text)
    if scoped is not None:
        candidates.extend(_source_labelled_companies(scoped))
    for company in candidates:
        key = _cv_match_key(company)
        if not key or key in seen:
            continue
        seen.add(key)
        employers.append(company)
    return employers


def _parsed_employers(parsed):
    """Distinct employers named in the parsed work history."""
    employers = []
    seen = set()
    for item in _flatten_parsed_work_roles(parsed):
        company = str(item.get("company") or "").strip()
        key = _cv_match_key(company)
        if not key or key in seen:
            continue
        seen.add(key)
        employers.append(company)
    return employers


def _employer_is_present(company, parsed_employers):
    key = _cv_match_key(company)
    for candidate in parsed_employers:
        if key and _cv_match_key(candidate) == key:
            return True
        if _cv_token_overlap_score(company, candidate) >= _EMPLOYER_MATCH_OVERLAP:
            return True
    return False


def _count_parsed_bullets(parsed):
    total = 0
    for exp in (parsed or {}).get("work_experiences") or []:
        if not isinstance(exp, dict):
            continue
        for role in exp.get("roles") or []:
            if isinstance(role, dict):
                total += len(_role_plain_bullets(role))
    return total


def _experience_section_text(cv_text):
    """Text between the experience heading and the next section, or None.

    None means no experience heading was found and the section could not be
    scoped -- the caller then skips the bullet check rather than risk a false
    positive from bullets elsewhere in the document.
    """
    lines = str(cv_text or "").splitlines()
    start = None
    for i, line in enumerate(lines):
        if _EXPERIENCE_HEADING_RE.match(line.strip()):
            start = i + 1
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start, len(lines)):
        if _SECTION_STOP_HEADING_RE.match(lines[j].strip()):
            end = j
            break
    return "\n".join(lines[start:end])


def _count_source_bullets(cv_text):
    """Count source bullet lines within the experience section.

    Returns None when the section can't be located (bullet check disabled).
    """
    section = _experience_section_text(cv_text)
    if section is None:
        return None
    return sum(1 for line in section.splitlines() if _SOURCE_BULLET_RE.match(line))


def evaluate_cv_fidelity(parsed, cv_text):
    """Compare a reconciled/normalized CV against its source text.

    Returns a plain report dict and never mutates ``parsed``. ``ok`` is True
    when no material structural loss was detected.
    """
    source_emps = _source_employers(cv_text, parsed)
    parsed_emps = _parsed_employers(parsed)
    missing = [c for c in source_emps if not _employer_is_present(c, parsed_emps)]

    # A parsed company that is punctuation only -- "|", "-", ":" -- is the cell
    # separator the model picked up instead of the name beside it. The finished CV
    # shows an empty employer, which looks like a layout fault rather than a
    # dropped field, so it is named here.
    unnamed = [
        str(item.get("date_range") or item.get("company") or "").strip()
        for item in _flatten_parsed_work_roles(parsed)
        if str(item.get("company") or "").strip()
        and not re.search(r"[^\W_]", str(item.get("company") or ""), re.UNICODE)
    ]

    source_bullets = _count_source_bullets(cv_text)
    parsed_bullets = _count_parsed_bullets(parsed)
    bullet_scoped = source_bullets is not None
    bullet_shortfall = (
        bullet_scoped
        and source_bullets >= _BULLET_MIN_SOURCE
        and parsed_bullets < source_bullets * _BULLET_SHORTFALL_RATIO
    )

    warnings = []
    if missing:
        warnings.append(
            "Employer(s) present in the CV but missing from the parsed result: "
            + ", ".join(missing)
        )
    if unnamed:
        warnings.append(
            "{} work entr{} came back with no employer name -- the separator was "
            "read instead of the company.".format(
                len(unnamed), "y" if len(unnamed) == 1 else "ies"
            )
        )
    if bullet_shortfall:
        warnings.append(
            "Only {parsed} bullet point(s) were kept out of about {source} found "
            "in the CV -- some detail may have been dropped.".format(
                parsed=parsed_bullets, source=source_bullets
            )
        )

    return {
        "ok": not warnings,
        "employers": {
            "source": len(source_emps),
            "parsed": len(parsed_emps),
            "missing": missing,
            "unnamed": unnamed,
        },
        "bullets": {
            "source_estimate": source_bullets,
            "parsed": parsed_bullets,
            "shortfall": bullet_shortfall,
            "scoped": bullet_scoped,
        },
        "warnings": warnings,
    }


def summarize_fidelity_warning(report):
    """A single user-facing warning string for a fidelity report, or None.

    Shaped to match the wording style of the existing truncated-parse warning
    so the ``/parse`` route can reuse the same degraded/warning fields.
    """
    if not report or report.get("ok"):
        return None
    warnings = report.get("warnings") or []
    if not warnings:
        return None
    return (
        "Some information in this CV may not have been captured correctly -- "
        "please check the parsed result against the original before continuing. "
        + " ".join(warnings)
    )
