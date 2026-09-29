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
    _CV_SOURCE_SECTION_BOUNDARY_KEYS,
    _cv_match_key,
    _cv_source_boundary_key,
    _cv_token_overlap_score,
)
from cvstudio_cv_reconcile import (
    _CV_SEPARATOR_ONLY_RE,
    _WORK_HISTORY_HEADING_RE,
    _WORK_HISTORY_STOP_WORDS,
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
# None means "no work-history section found", so it cannot double as "not
# supplied". This sentinel keeps the two apart.
_UNSET = object()


# One definition, owned by the reconciler, so the two stages cannot drift apart.
_EXPERIENCE_HEADING_RE = _WORK_HISTORY_HEADING_RE

# The bullet count's stops: the reconciler's shared work-history stop words, plus
# trailing sections that carry bullets of their own. The reconciler's readers end
# at those sections too, but as whole headings, through its section-boundary
# list. The bullet count needs them as prefixes, so a bulleted "Interests &
# Hobbies" after the work history is not counted as duties; the reconciler must
# not, because a line such as "Summary of role:" inside a job would then end its
# work history and drop the rows after it. So these extra words live here only.
_AUDIT_TRAILING_STOP_WORDS = ("INTERESTS?", "HOBBIES", "PROFILE", "SUMMARY", "AWARDS?")
_SECTION_STOP_HEADING_RE = re.compile(
    r"^(?:" + "|".join(_WORK_HISTORY_STOP_WORDS + _AUDIT_TRAILING_STOP_WORDS) + r")\b",
    re.I,
)

# Where the labelled-employer scan starts: the shared work-history heading, or a
# line that is one of the other names CVs give it -- "Working Experience",
# "Employment Record", "Relevant Experience". Only the label scan starts here; the
# bullet count keeps the shared heading alone, so its scope does not change.
#
# "Professional Background" and "Career Background" are profile headings as often
# as work headings. A profile carries no "Company:" labels, and every span is
# read (see _label_scan_section), so starting there costs nothing and a CV whose
# only work heading is one of them is still checked.
_LABEL_SCAN_START_RE = re.compile(
    r"^\s*(?:(?:WORK(?:ING)?|EMPLOYMENT|CAREER|PROFESSIONAL|RELEVANT|PREVIOUS|PAST|JOB|INDUSTRY)"
    r"\s+(?:EXPERIENCES?|HISTORY|RECORDS?)"
    r"|(?:PROFESSIONAL|CAREER|EMPLOYMENT)\s+BACKGROUND|EMPLOYMENT\s+DETAILS"
    r"|(?:PREVIOUS|PAST)\s+EMPLOYMENTS?|EMPLOYMENT|POSITIONS\s+HELD)"
    r"\s*(?:\([^)]*\))?\s*:?\s*$",
    re.I,
)

# Where the labelled-employer scan stops. The bullet check above ends at any line
# that merely STARTS with a section word, which is right for counting bullets but
# wrong here: a label-style CV carries "Project: Core banking migration" or
# "Summary of duties:" inside a job, and ending the scan there left every later
# "Company:" label unread, so a dropped employer was never reported. A stop is
# therefore a heading line -- see _label_scan_stops -- and this pattern is one of
# its forms: the heading, an optional qualifier, an optional parenthesis, an
# optional colon, and nothing else.
_LABEL_SECTION_STOP_RE = re.compile(
    r"^\s*(?:EDUCATION(?:AL)?|ACADEMIC|CERTIFICATIONS?|REFERENCES?|REFEREES?|"
    r"(?:TECHNICAL|KEY|CORE)\s+SKILLS|SKILLS|ADDITIONAL\s+INFORMATION|LANGUAGES?|"
    r"PROJECTS?|INTERESTS?|HOBBIES|PROFILE|SUMMARY|AWARDS?)"
    r"(?:\s*(?:&|AND|/)\s*[A-Z]+|\s+(?:BACKGROUND|QUALIFICATIONS?|DETAILS|HISTORY|"
    r"INFORMATION|TRAINING|ACHIEVEMENTS?))?"
    r"\s*(?:\([^)]*\))?\s*:?\s*$",
    re.I,
)

# A referees block names other people's employers, and the parse leaves it out,
# so reading on into it reports a referee's "Company:" as a missing employer.
# These headings come in more shapes than the pattern above holds -- "REFERENCE
# CONTACTS", "Professional References", "Referee: Mr Tan" -- so any line that
# opens with the word, optionally after one qualifier, ends the scan -- except a
# labelled reference NUMBER inside a job ("Reference No: 4411", "Reference
# Number: A-12"), which is part of that job. The label needs its colon: a
# numbered referee heading such as "Referee #1" or "Reference No. 1" has none,
# and still ends the scan.
_LABEL_SCAN_REFERENCE_RE = re.compile(
    r"^\s*(?:(?:PROFESSIONAL|CHARACTER|PERSONAL|EMPLOYMENT|EMPLOYER|WORK|BUSINESS|CAREER|"
    r"ACADEMIC|FORMER|PREVIOUS|KEY)\s+)?(?:REFERENCES?|REFEREES?)\b"
    r"(?!\s*(?:no\b\.?|nos\b\.?|number|num\b\.?|code|id\b|#)[^:\uff1a\r\n]*[:\uff1a])",
    re.I,
)
_LABEL_SCAN_PERSONAL_RE = re.compile(
    r"^\s*PERSONAL\s+(?:DETAILS|PARTICULARS|INFORMATION|INFO|DATA|PROFILE|BACKGROUND)"
    r"\s*:?\s*$",
    re.I,
)

# The reconciler's own section list also ends the scan, less its work-history
# headings -- the reported CV repeats "Experience" above every employer -- and
# "achievements", which is also a sub-heading inside a job.
_LABEL_SCAN_BOUNDARY_KEYS = frozenset(
    key for key in _CV_SOURCE_SECTION_BOUNDARY_KEYS
    if key not in {
        "work experience", "working experience", "professional experience",
        "employment history", "career history", "achievements",
    }
)


def _label_scan_starts(line):
    return bool(_EXPERIENCE_HEADING_RE.match(line) or _LABEL_SCAN_START_RE.match(line))


def _label_scan_restarts(line):
    """A later work-history heading that opens another span.

    Stricter than the first start: the shared heading pattern matches a PREFIX,
    so prose inside a referees block -- "Work experience with the candidate: 3
    years" -- would reopen the scan into the referees' own "Company:" lines. A
    restart has to be a heading: no value after a colon, and a few words at most.
    """
    text = str(line or "").strip()
    if _LABEL_SCAN_START_RE.match(text):
        return True
    return (
        bool(_EXPERIENCE_HEADING_RE.match(text))
        and not re.search(r"[:\uff1a]\s*\S", text)
        and len(text.split()) <= 4
    )


def _label_scan_ends(line):
    """A referees or personal-details heading: nothing after it is work history."""
    text = str(line or "").strip()
    return bool(_LABEL_SCAN_REFERENCE_RE.match(text) or _LABEL_SCAN_PERSONAL_RE.match(text))


def _label_scan_stops(line):
    """Whether a line is a heading that ends the labelled-employer scan.

    Stopping early can only leave a label unread, which is what happened before
    this scan existed; reading past a heading can report someone else's employer
    as missing. So every heading form stops it, and only a heading does: a line
    with a value after its colon, such as "Project: Core banking migration", is
    part of the job. Referee and personal-details headings are not tested here:
    _label_scan_ends catches them first and ends the whole walk.
    """
    text = str(line or "").strip()
    if not text:
        return False
    if _LABEL_SECTION_STOP_RE.match(text):
        return True
    # The section list is compared on letters alone, so a line carrying a value
    # -- "Training: 2019", "Languages: 3" -- would read as the bare heading. A
    # heading has nothing after its colon. Figures alone do not rule a heading
    # out: "AWARDS 2021" still ends the scan, because reading on into another
    # section is what reports a false missing employer.
    if re.search(r"[:\uff1a]\s*\S", text):
        return False
    return _cv_source_boundary_key(text) in _LABEL_SCAN_BOUNDARY_KEYS


# A CV that writes its employers as labelled cells -- "Company: Acme Sdn Bhd" --
# has no Dates/Organization/Role columns for the authoritative-row reader to find,
# so that reader returns nothing and a shortfall goes unnoticed. The label itself
# is high-confidence evidence: a line that says "Company:" is naming an employer.
# The label may open the line or a pipe-delimited cell within it, because the
# extractor joins a table row's cells with " | " and the company is not always the
# first column.
#
# The value may sit in the label's own cell ("Company: Acme") or, in a two-column
# label table, in the next one ("Company: | Acme", "Company | Acme"). Without the
# colon the label has to be the whole cell, so prose cannot read as a label.
#
# In the same cell a colon is required. An earlier draft also accepted a bare
# hyphen, which turned a wrapped sentence beginning "Company-wide rollout of the
# new platform" into the employer candidate "wide rollout of the new platform".
#
# The two forms are captured separately. Only a value in the NEXT cell can be a
# column header ("Company | Position Held | Duration"); a value in the label's own
# cell is always the name.
_LABELLED_COMPANY_RE = re.compile(
    r"(?:^|\|)[ \t]*compan(?:y|ies)(?:[ \t]+name)?[ \t]*"
    r"(?:(?:[:\uff1a][ \t]*)?\|[ \t]*([^|\r\n]+)|[:\uff1a][ \t]*([^|\r\n]+))",
    re.I | re.M,
)

# An Industry, Position or Duration cell riding along on the same row. The label
# has to be followed by a colon or a spaced dash; a bare hyphen is part of a name,
# as in "Role-Play Studios" or "Sector-X Consulting".
_LABELLED_COMPANY_TRAILER_RE = re.compile(
    r"\s*\b(?:industry|industries|position|duration|period|role|title|sector)\b"
    r"(?:\s*[:\uff1a]|\s+[-\u2013\u2014]\s).*$",
    re.I,
)

# The next column's header, read as a value when the row is a table's header row
# ("Company | Position Held | Duration", "Company Name | Period of Employment").
# A next-cell value made up entirely of header words names no employer. Every
# word has to be one, so an employer that merely contains one -- "Department of
# Statistics", "Position Partners Sdn Bhd", "Title Insurance Co" -- is still read.
# A value in the label's own cell ("Company: Total") is never tested against this
# list, so real names made of header words are still read there.
_LABEL_TABLE_HEADER_WORDS = frozenset({
    "industry", "industries", "sector", "position", "positions", "held", "title", "titles",
    "job", "jobs", "designation", "designations", "role", "roles", "rank", "grade", "level",
    "post", "period", "duration", "tenure", "date", "dates", "from", "to", "start",
    "started", "end", "ended", "year", "years", "month", "months", "since", "until",
    "employment", "employed", "department", "division", "location", "country", "city",
    "state", "address", "salary", "pay", "remuneration", "compensation", "package",
    "description", "duties", "duty", "responsibilities", "responsibility", "reason",
    "reasons", "leaving", "left", "name", "company", "companies", "employer", "employers",
    "organisation", "organization", "organisations", "organizations", "type", "nature",
    "business", "status", "supervisor", "superior", "reporting", "report", "reports",
    "manager", "achievements", "remarks", "remark", "notes", "contact", "number",
    "details", "detail", "information", "info", "total", "experience", "current", "last",
    "previous", "drawn", "basic", "monthly", "annual", "expected", "notice", "currency",
})
_LABEL_HEADER_FILLER_WORDS = frozenset({"of", "and", "the", "for", "in", "at", "no"})


def _looks_like_column_header(name):
    words = [
        word for word in re.findall(r"[a-z]+", str(name or "").lower())
        if word not in _LABEL_HEADER_FILLER_WORDS
    ]
    return bool(words) and all(word in _LABEL_TABLE_HEADER_WORDS for word in words)


def _source_labelled_companies(cv_text):
    """Employer names the source labels outright with a "Company:" prefix."""
    names = []
    for next_cell, own_cell in _LABELLED_COMPANY_RE.findall(str(cv_text or "")):
        name = _LABELLED_COMPANY_TRAILER_RE.sub("", str(next_cell or own_cell or ""))
        name = re.sub(r"\s+", " ", name).strip(" .,;:|-")
        if next_cell and _looks_like_column_header(name):
            continue
        # A label with nothing after it, or a whole paragraph, is not a name.
        if name and 2 <= len(name) <= 120:
            names.append(name)
    return names


# A labelled name often carries more than the employer: a parenthesised brand, a
# branch location, a trailing department. The parse keeps the employer alone, and
# the token-overlap score then falls below the match threshold and reports a
# present employer as missing. These are the shorter readings to also try.
def _employer_name_readings(company):
    """(own readings, bracketed readings) of a labelled employer name.

    The own readings are the name and its head before a parenthesis, comma or
    dash. The bracketed readings are what sits inside a parenthesis -- a brand,
    or the client an agency placed the candidate with. Those are weaker evidence
    and the caller only accepts them when no other source employer owns the
    same parsed name.
    """
    text = re.sub(r"\s+", " ", str(company or "")).strip()
    own = [text] if text else []
    for pattern in (r"\s*\(", r"\s*,", r"\s*\u2013", r"\s*\u2014", r"\s+-\s+"):
        head = re.split(pattern, text, maxsplit=1)[0].strip(" .,;:-")
        if head and head != text and len(head) >= 2 and head not in own:
            own.append(head)
    bracketed = []
    for part in re.findall(r"\(([^)]{2,80})\)", text):
        part = part.strip(" .,;:-")
        if part and part not in own and part not in bracketed:
            bracketed.append(part)
    return own, bracketed


def _employer_name_matches(variant, candidate):
    key = _cv_match_key(variant)
    if key and _cv_match_key(candidate) == key:
        return True
    return _cv_token_overlap_score(variant, candidate) >= _EMPLOYER_MATCH_OVERLAP


def _source_employers(cv_text, parsed=None, section=_UNSET):
    """Distinct high-confidence employers extracted from the source text.

    ``section`` is the already-split work-history text when the caller has it;
    splitting the whole document again per check buys nothing on a long CV.
    """
    employers = []
    seen = set()
    candidates = [
        str(row.get("company") or "").strip()
        for row in _extract_authoritative_work_rows(cv_text, parsed)
    ]
    # Read the labels from the work-history section only, and only when that
    # section could actually be located. A referees block or a cover note can also
    # say "Company:", and an employer expected from outside the work history would
    # be reported missing on a perfectly good parse. No section, no claim.
    scoped = _label_scan_section(cv_text) if section is _UNSET else section
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


def _own_name_hits(company, parsed_employers):
    """Parsed employers that match this labelled name, or its head, directly."""
    own = _employer_name_readings(company)[0] or [company]
    return {
        candidate for candidate in parsed_employers
        if any(_employer_name_matches(variant, candidate) for variant in own)
    }


def _missing_source_employers(source_emps, parsed_emps):
    """Source employers the parse did not keep under any reasonable name.

    A bracketed reading -- a brand, or the client an agency placed the candidate
    with -- is weaker evidence than the name itself. It may only match a parsed
    employer that no source employer claims under its own name: "Hays Recruitment
    (Petronas)" is not present merely because the parse kept the candidate's
    separate Petronas job.
    """
    own_hits = [_own_name_hits(company, parsed_emps) for company in source_emps]
    # Only consulted for an employer with no own hits, so every name in here was
    # claimed by some other source employer.
    claimed = set().union(*own_hits)
    missing = []
    for company, hits in zip(source_emps, own_hits):
        if hits:
            continue
        bracketed = _employer_name_readings(company)[1]
        if any(
            _employer_name_matches(variant, candidate)
            for variant in bracketed
            for candidate in parsed_emps
            if candidate not in claimed
        ):
            continue
        missing.append(company)
    return missing


def _count_parsed_bullets(parsed):
    total = 0
    for exp in (parsed or {}).get("work_experiences") or []:
        if not isinstance(exp, dict):
            continue
        for role in exp.get("roles") or []:
            if isinstance(role, dict):
                total += len(_role_plain_bullets(role))
    return total


def _section_spans(cv_text, starts, stops, restarts=None, ends=None):
    """Spans of lines from a start heading to the next stop, as lists of lines.

    The one walker for both the bullet count and the labelled-employer scan. The
    heading line itself is not part of a span. With no ``restarts`` only the first
    span is returned. With ``restarts`` a later heading opens another span, and an
    ``ends`` line closes the current one and stops the walk for good.
    """
    spans = []
    current = None
    for line in str(cv_text or "").splitlines():
        text = line.strip()
        if current is None:
            opens = restarts if (spans and restarts) else starts
            if not spans or restarts:
                if opens(text):
                    current = []
            continue
        if ends and ends(text):
            spans.append(current)
            return spans
        if stops(text):
            spans.append(current)
            current = None
            if not restarts:
                return spans
            continue
        current.append(line)
    if current is not None:
        spans.append(current)
    return spans


def _experience_section_text(cv_text):
    """Text between the experience heading and the next section, or None.

    None means no experience heading was found and the section could not be
    scoped -- the caller then skips the bullet check rather than risk a false
    positive from bullets elsewhere in the document.
    """
    spans = _section_spans(cv_text, _EXPERIENCE_HEADING_RE.match, _SECTION_STOP_HEADING_RE.match)
    return "\n".join(spans[0]) if spans else None


def _label_scan_section(cv_text):
    """The work-history text the labelled-employer scan reads, or None.

    Every work-history span is read, not only the first: a heading earlier in the
    CV that also reads as a work-history start must not leave the real work
    history unread. A referees or personal-details heading ends the walk.
    """
    spans = _section_spans(
        cv_text, _label_scan_starts, _label_scan_stops,
        restarts=_label_scan_restarts, ends=_label_scan_ends,
    )
    if not spans:
        return None
    return "\n".join("\n".join(span) for span in spans)


def _count_source_bullets(cv_text, section=_UNSET):
    """Count source bullet lines within the experience section.

    Returns None when the section can't be located (bullet check disabled).
    """
    section = _experience_section_text(cv_text) if section is _UNSET else section
    if section is None:
        return None
    return sum(1 for line in section.splitlines() if _SOURCE_BULLET_RE.match(line))


# A parsed company that is nothing but a cell separator. One definition, shared
# with the table reader; see _CV_SEPARATOR_ONLY_RE.
_SEPARATOR_ONLY_COMPANY_RE = _CV_SEPARATOR_ONLY_RE


def evaluate_cv_fidelity(parsed, cv_text):
    """Compare a reconciled/normalized CV against its source text.

    Returns a plain report dict and never mutates ``parsed``. ``ok`` is True
    when no material structural loss was detected.
    """
    # The bullet count and the label scan bound the work history differently; see
    # _label_scan_starts and _label_scan_stops.
    section = _experience_section_text(cv_text)
    label_section = _label_scan_section(cv_text)
    source_emps = _source_employers(cv_text, parsed, section=label_section)
    parsed_emps = _parsed_employers(parsed)
    missing = _missing_source_employers(source_emps, parsed_emps)

    # A parsed company that is only a separator -- "|", ":" and their wide forms --
    # is the cell separator the model picked up instead of the name beside it. The
    # finished CV shows an empty employer, which looks like a layout fault rather
    # than a dropped field, so it is named here. A "-" or "N/A" is NOT reported: a
    # CV writes those on purpose for a career break, and reporting them held a
    # correct CV's auto-upload.
    #
    # Walked per work experience, not per flattened role: one employer with three
    # roles lost one company field, and counting the roles said "3 work entries".
    # The date range is read from the experience itself, which is where that key
    # lives -- the flattened rows carry exp_date/role_date instead, so an earlier
    # draft always fell through to the separator and located nothing.
    unnamed = []
    for exp in (parsed or {}).get("work_experiences") or []:
        if not isinstance(exp, dict):
            continue
        company = str(exp.get("company") or "")
        if not _SEPARATOR_ONLY_COMPANY_RE.match(company):
            continue
        label = str(exp.get("date_range") or "").strip()
        if not label:
            roles = exp.get("roles") if isinstance(exp.get("roles"), list) else []
            for role in roles:
                if isinstance(role, dict):
                    label = str(role.get("date_range") or role.get("title") or "").strip()
                    if label:
                        break
        unnamed.append(label or company.strip())

    source_bullets = _count_source_bullets(cv_text, section=section)
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
            "{} employer{} came back with no name -- the separator was read instead "
            "of the company ({}).".format(
                len(unnamed),
                "" if len(unnamed) == 1 else "s",
                ", ".join(unnamed[:4]),
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
