"""Deterministic CV parse post-processing for CV Studio.

Behaviour-preserving extraction from the app shell: the structure corrections
applied to a provider-parsed CV before formatting -- authoritative work-row
extraction and reconciliation, same-company role ordering, explicit project
heading restoration, incomplete early-career collapsing, and redaction-aware
language cleanup. Pure functions of their inputs (parsed dict + source text) --
no Flask, no globals, no network, no AI call. This module never imports ``app``.
"""

import re
import unicodedata

from cvstudio_cv_normalize import (
    _CV_REDACTED_LANGUAGE_RE,
    _CV_SOURCE_SECTION_BOUNDARY_KEYS,
    _WORK_TABLE_DATE_RE,
    _cv_combine_date_ranges,
    _cv_company_span_from_roles,
    _cv_date_parts,
    _cv_date_sort_point,
    _cv_match_key,
    _cv_project_group_sort_key,
    _cv_source_boundary_key,
    _cv_text_similarity,
    _cv_token_overlap_score,
    _normalize_cv_date_range,
    _smart_title_text,
)


_EARLIER_CAREER_RE = re.compile(r"earlier\s+career\b", re.I)
# An undated entry carrying at least this many descriptive bullets is a real job.
_DESCRIBED_ROLE_BULLETS = 2


def _role_plain_bullets(role):
    bullets = []
    for item in (role or {}).get("bullets") or []:
        if isinstance(item, str) and item.strip():
            bullets.append(item.strip())
        elif isinstance(item, dict):
            heading = str(item.get("heading") or "").strip()
            for sub in item.get("bullets") or []:
                if isinstance(sub, str) and sub.strip():
                    bullets.append((f"{heading}: " if heading else "") + sub.strip())
    return bullets


# Characters that mark a company name as part of a "Job Title - Company" listing line
# rather than a heading of its own.
_LISTING_LEAD_CHARS = "-\u2010\u2011\u2012\u2013\u2014\u2015\u2022\u00b7*:,/|;"


def _entry_is_dated(exp):
    if not isinstance(exp, dict):
        return False
    if str(exp.get("date_range") or "").strip():
        return True
    for role in exp.get("roles") or []:
        if isinstance(role, dict) and str(role.get("date_range") or "").strip():
            return True
    return False


def _role_bullet_items(role):
    """Return a role's bullets with any {heading, bullets} sub-group left intact."""
    items = []
    for item in (role or {}).get("bullets") or []:
        if isinstance(item, str) and item.strip():
            items.append(item.strip())
        elif isinstance(item, dict) and (item.get("heading") or item.get("bullets")):
            items.append(item)
    return items


def _flatten_source(text):
    """Collapse whitespace, and record which characters opened a line.

    Offsets stay valid for the returned string, so matching uses re.IGNORECASE rather
    than casefold: casefold can change a string's length (ss, ligatures) and would shift
    every offset computed from it.
    """
    chars = []
    line_start = []
    opening = True
    spaced = False
    for character in str(text or ""):
        if character in "\r\n":
            opening = True
            spaced = True
            continue
        if character.isspace():
            spaced = True
            continue
        if spaced and chars:
            chars.append(" ")
            line_start.append(False)
        spaced = False
        chars.append(character)
        line_start.append(opening)
        opening = False
    return "".join(chars), line_start


def _company_source_pattern(name):
    """Match a company name across punctuation drift: "Sdn. Bhd." vs "SDN BHD"."""
    tokens = [token for token in re.split(r"[\s.]+", str(name or "").strip()) if token]
    if not tokens or len("".join(tokens)) < 3:
        return None
    return re.compile(r"[\s.]*".join(re.escape(token) for token in tokens), re.I)


def _reads_as_heading(flat, line_start, offset):
    """Report whether a match at ``offset`` starts a block rather than continuing text.

    A name inside a profile paragraph ("experienced leader at KGB Holdings") is a
    mention, not a heading, and must not decide where a sub-brand belongs. Extracted PDF
    text loses many line breaks and glues a heading to the sentence before it
    ("...new business concept.KGB HOLDINGS SDN BHD"), so the end of the previous
    sentence counts as a boundary too. A name after a dash or a bullet is one entry of a
    "Job Title - Company" listing and never a heading.
    """
    if offset < len(line_start) and line_start[offset]:
        return True
    lead = flat[:offset].rstrip()
    if not lead:
        return True
    return lead[-1] in ".!?:;"


def _starts_a_listing_entry(flat, offset):
    """Report whether a match continues a "Job Title - Company" listing line."""
    lead = flat[:offset].rstrip()
    return bool(lead) and lead[-1] in _LISTING_LEAD_CHARS


def _heading_offsets(flat, line_start, name):
    """Offsets where a company name reads as a heading rather than a mention."""
    pattern = _company_source_pattern(name)
    if pattern is None:
        return []
    return [
        match.start()
        for match in pattern.finditer(flat)
        if _reads_as_heading(flat, line_start, match.start())
    ]


# Role nouns. Text to the right of an employer heading is the block's own title
# when it carries one of these, and a two-column sidebar fragment when it does not
# ("Management", "Development", "Compliance" are sidebar wrap, not titles).
_JOB_TITLE_NOUNS = frozenset({
    "manager", "director", "executive", "officer", "head", "chief", "chef",
    "engineer", "analyst", "consultant", "supervisor", "lead", "leader",
    "president", "partner", "specialist", "coordinator", "assistant", "associate",
    "administrator", "technician", "architect", "designer", "developer",
    "accountant", "auditor", "advisor", "adviser", "principal", "founder",
    "owner", "intern", "trainee", "apprentice", "clerk", "secretary", "cashier",
    "operator", "agent", "representative", "rep", "commis", "sous", "chefs",
    "managers", "directors", "executives", "officers", "engineers", "analysts",
})


# A role heading often carries a place or a qualifier after a separator:
# "Analyst - Kuala Lumpur", "Manager (Operations)", "Director | Group". That is the
# same role, so it must not stop the heading being found -- a role the source prints
# this way used to be unlocatable, and the project then went to the newest promotion
# instead of the one that ran it.
_ROLE_HEADING_QUALIFIER_RE = re.compile(
    r"^[\-\u2010-\u2015,|/(\[]\s*[^•▪◦*]{0,60}$"
)


def _role_heading_tail_is_incidental(tail):
    """Whether text after a role heading leaves it still reading as that heading."""
    tail = str(tail or "").strip()
    if not tail:
        return True
    if re.match(r"^[•▪◦*]", tail):
        return True
    if _WORK_TABLE_DATE_RE.fullmatch(tail.strip(" ()|:")):
        return True
    return bool(_ROLE_HEADING_QUALIFIER_RE.match(tail))


def _reads_as_job_title(text):
    """Whether a fragment names a role rather than reading as sidebar wrap."""
    words = re.findall(r"[A-Za-z]+", str(text or "").lower())
    return any(word in _JOB_TITLE_NOUNS for word in words)


def _source_line_end(flat, line_start, offset):
    return next((i for i in range(offset + 1, len(flat)) if line_start[i]), len(flat))


def _source_block_span(flat, offset, boundaries):
    """The source text from a sub-brand heading up to the next employer heading.

    pdfplumber interleaves a two-column layout, so a block's own duties arrive on
    non-adjacent lines with sidebar fragments wedged between them:

        POS & HRIS) PM BRANDS SDN BHD (HALO DIM SUM)
        • Cost Optimisation, Pricing & Margin
        • Developed the business proposal and rollout plan for the Halo Dim Sum
        Management
        kiosk concept.

    Corroborating a mid-line heading therefore has to look across that whole span.
    The span stops at the next dated employer heading, so a block can never borrow
    a later employer's duties as its evidence.
    """
    end = next((point for point in boundaries if point > offset), len(flat))
    return flat[offset:end]


def _reads_as_referees_heading_line(line):
    """Whether one source line is a referees section heading.

    The line goes to ``_reads_as_reference_heading`` with nothing screening it
    first: that predicate folds accents and possessives, so a heading reading
    "RÉFÉRENCES" or "Referee's Details" has to reach it. A word match in front of it
    would drop exactly those.
    """
    tokens = _reference_heading_tokens(line)
    return bool(
        tokens
        and len(tokens) <= _REFERENCE_HEADING_MAX_TOKENS
        and not _REFERENCE_ON_REQUEST_RE.fullmatch(" ".join(tokens))
        and _reads_as_reference_heading(line)
    )


def _reference_block_spans(flat, line_start):
    """``(start, end)`` of each referees section in the flattened source.

    A referees list names employers and job titles, so a company matched inside one
    is a contact detail rather than the section the CV filed that company under.

    A section ENDS at the next recognised section heading. Some CVs put referees
    part-way through -- after the profile, or between two halves of the work history
    -- and treating the first referees heading as a cut to the end of the document
    made every employer below it unreachable.
    """
    spans = []
    open_start = None
    offset = 0
    while offset < len(flat):
        end = _source_line_end(flat, line_start, offset)
        line = flat[offset:end].strip()
        if _reads_as_referees_heading_line(line):
            if open_start is None:
                open_start = offset
            offset = end
            continue
        if open_start is not None and line and (
            _cv_source_boundary_key(line) in _CV_SOURCE_SECTION_BOUNDARY_KEYS
        ):
            spans.append((open_start, offset))
            open_start = None
        offset = end
    if open_start is not None:
        spans.append((open_start, len(flat)))
    return spans


def _block_offsets(flat, line_start, name, role, boundaries=()):
    """Offsets where a sub-brand block's own name can begin.

    A two-column CV extracted with pdfplumber interleaves the sidebar into the
    main column, so the block's heading
    routinely lands mid-line behind unrelated text
    ("... (ERP, POS & HRIS) PM BRANDS SDN BHD"). Requiring a line or sentence boundary
    there rejects the real document. The parent side stays strict, and a name that
    continues a listing line is still refused, so the pairing remains anchored.
    """
    pattern = _company_source_pattern(name)
    if pattern is None:
        return []
    referees_spans = _reference_block_spans(flat, line_start)
    strong, column = [], []
    for match in pattern.finditer(flat):
        if _starts_a_listing_entry(flat, match.start()) and not line_start[match.start()]:
            continue
        if _offset_in_spans(match.start(), referees_spans):
            continue
        end = _source_line_end(flat, line_start, match.start())
        tail = flat[match.end():end].strip().lstrip(".:").strip()
        # A heading can carry sidebar text to its right. A bullet glyph settles it:
        # the tail is a sidebar item, and what it happens to say does not matter --
        # a competency list is full of "• Executive Leadership" and "• Chef
        # Training". Only an unglyphed tail has to be read, because then it is
        # either a wrapped sidebar word ("... (HALO DIM SUM) Management") or the
        # block's own metadata: prose carrying on the same sentence ("Project Delta
        # on supplier onboarding"), a date, or a job title printed beside the
        # employer ("BETA SYSTEMS SDN BHD Senior Manager"). A model that dropped
        # that title leaves the entry looking untitled, and absorbing it would
        # delete a whole job.
        if tail and not re.match(r"^[•▪◦*]", tail) and (
            tail[:1].islower()
            or _WORK_TABLE_DATE_RE.search(tail)
            or _reads_as_job_title(tail)
        ):
            continue
        following_end = _source_line_end(flat, line_start, end) if end < len(flat) else end
        following = flat[end:following_end].strip()
        if not following:
            continue
        # Before any duties, an unexplained line may be a title/date the model
        # missed. Do not erase that standalone job by treating it as a project.
        first_items = _role_plain_bullets(role)
        is_duty = bool(re.match(r"^[-•▪◦*]\s*\S", following))
        if not is_duty and first_items:
            source_key = _cv_match_key(following)
            duty_key = _cv_match_key(first_items[0])
            is_duty = bool(source_key and duty_key and (
                source_key == duty_key or
                (len(source_key) >= 24 and duty_key.startswith(source_key))
            ))
        if not is_duty:
            continue
        heading = _reads_as_heading(flat, line_start, match.start())
        if not heading:
            # For a mid-line two-column match, a list marker alone is not evidence:
            # the duty has to belong to this block. Look for it across the block's
            # whole span, because the extractor splits it over interleaved lines --
            # checking only the next line rejects every real two-column CV.
            duty_words = re.findall(r"\w+", first_items[0].lower()) if first_items else []
            span = _source_block_span(flat, match.end(), boundaries)
            source_words = re.findall(r"\w+", span.lower())
            if len(duty_words) < 3 or not set(duty_words).issubset(set(source_words)):
                continue
        target = strong if heading else column
        target.append(match.start())
    # A real heading wins over a sidebar-like mention. Multiple possible blocks
    # remain untouched rather than letting their model order decide ownership.
    candidates = strong or column
    return candidates if len(candidates) == 1 else []


def _attach_untitled_subsidiary_entries(parsed, cv_text=""):
    """Fold a dateless, titleless company block into the role it sits under.

    Some CVs list a sub-brand or special project beneath a dated role, with the company
    on its own line and no dates or job title of its own::

        A&W MALAYSIA SDN BHD
        Head of Operations, Special Projects
        (February 2025 - August 2025)
          * ...
        PM BRANDS SDN BHD (HALO DIM SUM)
          * Developed the business proposal ...

    The parent is read from the source CV, never from the model's ordering. The model
    moves such a block freely - in the case this was written for it emitted the block
    last - so "whatever entry precedes it in the list" is not evidence, and trusting it
    filed a 2025 special project under a 2017 employer.

    Headings and corroborated two-column blocks count: an employer named in a
    profile paragraph is a mention, not the section the block sits in. When every
    dated employer cannot be located as a heading, the ordering cannot be trusted
    and nothing is attached.
    """
    if not isinstance(parsed, dict):
        return parsed
    exps = parsed.get("work_experiences")
    if not isinstance(exps, list) or len(exps) < 2:
        return parsed
    flat, line_start = _flatten_source(cv_text)
    if not flat:
        return parsed

    def is_subsidiary(exp):
        if not isinstance(exp, dict):
            return False
        if _entry_is_dated(exp):
            return False
        if str(exp.get("section_heading") or "").strip():
            return False
        company = str(exp.get("company") or "").strip()
        if not company or _EARLIER_CAREER_RE.match(company):
            return False
        roles = exp.get("roles") if isinstance(exp.get("roles"), list) else []
        if len(roles) != 1 or not isinstance(roles[0], dict):
            return False
        if str(roles[0].get("title") or "").strip():
            return False
        return bool(_role_bullet_items(roles[0]))

    def source_role_index(exp, parent_start, parent_end, child_offset):
        """The role whose source heading most recently precedes the block, or None.

        A project belongs to the role that was running when it happened, not to
        whichever promotion the model listed first. ``None`` means the source could
        not say, and the caller falls back rather than dropping the block.
        """
        roles = (exp or {}).get("roles")
        if not isinstance(roles, list) or len(roles) < 2:
            return None
        anchors = []
        seen = set()
        for role_index, role in enumerate(roles):
            if not isinstance(role, dict) or not str(role.get("title") or "").strip():
                return None
            pattern = _company_source_pattern(role["title"])
            if pattern is None:
                return None
            offsets = []
            for match in pattern.finditer(flat, parent_start, parent_end):
                if not _reads_as_heading(flat, line_start, match.start()):
                    continue
                line_end = _source_line_end(flat, line_start, match.start())
                tail = flat[match.end():min(line_end, parent_end)].strip(" .:")
                if _role_heading_tail_is_incidental(tail):
                    offsets.append(match.start())
            if len(offsets) != 1 or offsets[0] in seen:
                return None
            seen.add(offsets[0])
            if offsets[0] < child_offset:
                anchors.append((offsets[0], role_index))
        return max(anchors)[1] if anchors else None

    def host_role_index(exp, parent_start, parent_end, child_offset):
        """Which role of the parent receives the block.

        The source decides when it can. When it cannot -- an untitled promotion, a
        title the source never prints as a heading, two roles sharing one heading --
        the newest role takes it. That keeps the block under the right employer,
        which is the whole point of the pass; declining instead puts the sub-brand
        back on its own dateless row, the defect this exists to remove.
        """
        roles = (exp or {}).get("roles")
        if not isinstance(roles, list) or not roles or not isinstance(roles[0], dict):
            return None
        located = source_role_index(exp, parent_start, parent_end, child_offset)
        return 0 if located is None else located

    dated_indexes = [index for index, exp in enumerate(exps) if _entry_is_dated(exp)]
    if not dated_indexes:
        return parsed
    dated_headings = {}
    for index in dated_indexes:
        offsets = _heading_offsets(flat, line_start, exps[index].get("company"))
        if not offsets:
            # One employer we cannot place means "nearest preceding" is guesswork.
            return parsed
        dated_headings[index] = offsets

    # Every employer heading in source order. A block's evidence span stops at the
    # next one, so it can never corroborate itself with a later employer's duties.
    heading_boundaries = sorted(
        point for points in dated_headings.values() for point in points
    )

    def owning_employer(offset):
        """``(entry index, role index)`` the source puts this offset under, or None."""
        parents = []
        for parent_index, heading_offsets in dated_headings.items():
            earlier = [item for item in heading_offsets if item < offset]
            if earlier:
                parents.append((max(earlier), parent_index))
        if not parents:
            return None
        parent_start, parent_index = max(parents)
        if sum(point == parent_start for point, _ in parents) != 1:
            return None
        parent_end = next(
            (point for point in heading_boundaries if point > parent_start), len(flat)
        )
        role_index = host_role_index(exps[parent_index], parent_start, parent_end, offset)
        if role_index is None:
            return None
        return parent_index, role_index

    attachments = {}
    absorbed = set()
    for index, exp in enumerate(exps):
        if not is_subsidiary(exp):
            continue
        offsets = _block_offsets(
            flat, line_start, exp.get("company"), exp["roles"][0], heading_boundaries
        )
        if not offsets:
            continue
        offset = offsets[0]
        owner = owning_employer(offset)
        if owner is None:
            # Nothing to attach to. Leaving the block in place keeps its content in the
            # CV; dropping it would delete a company and its bullets outright.
            continue
        parent_index, role_index = owner
        attachments.setdefault(parent_index, {}).setdefault(role_index, []).append((offset, index))
        absorbed.add(index)

    # A model that already nested the block has the same ownership question to get
    # wrong, and gets no correction from the loop above because the block never
    # appears as an entry of its own. Re-read those groups from the source too, on
    # the same evidence: a single located heading, under a different employer than
    # the one holding it. Anything the source cannot place stays where it is.
    moves = []
    for index, exp in enumerate(exps):
        if index in absorbed:
            continue
        for role in (exp.get("roles") or []):
            if not isinstance(role, dict) or not isinstance(role.get("bullets"), list):
                continue
            for item in role["bullets"]:
                if not isinstance(item, dict):
                    continue
                heading = str(item.get("heading") or "").strip()
                items = [line for line in (item.get("bullets") or []) if str(line).strip()]
                if not heading or not items:
                    continue
                offsets = _block_offsets(
                    flat, line_start, heading, {"bullets": items}, heading_boundaries
                )
                if not offsets:
                    continue
                owner = owning_employer(offsets[0])
                if owner is None or owner[0] == index:
                    continue
                moves.append((offsets[0], index, role, item, owner))
    for offset, _, role, item, owner in moves:
        role["bullets"] = [entry for entry in role["bullets"] if entry is not item]
        parent_index, role_index = owner
        attachments.setdefault(parent_index, {}).setdefault(role_index, []).append(
            (offset, item)
        )

    if not attachments:
        return parsed

    kept = []
    for index, exp in enumerate(exps):
        if index in absorbed:
            continue
        if index in attachments:
            for role_index, children in attachments[index].items():
                host = exp["roles"][role_index]
                bullets = host.get("bullets")
                if isinstance(bullets, str):
                    bullets = [bullets] if bullets.strip() else []
                elif not isinstance(bullets, list):
                    bullets = []
                host["bullets"] = bullets
                for _, child in sorted(children, key=lambda pair: pair[0]):
                    if isinstance(child, dict):
                        # A group the model had already nested, moved whole.
                        bullets.append(child)
                        continue
                    block = exps[child]
                    bullets.append({
                        "heading": _smart_title_text(block.get("company") or "", company=True),
                        "bullets": _role_bullet_items(block["roles"][0]),
                    })
        kept.append(exp)
    parsed["work_experiences"] = kept
    return parsed


def _collapse_incomplete_earlier_career(parsed):
    """Avoid ugly provider drift like bare '| Company' rows for undated early roles.

    When multiple trailing work entries have no date ranges, they are usually an
    old/early-career list rather than fully described jobs. Group them into one
    Earlier Career block so DeepSeek follows the cleaner Claude-style output.
    Date-bearing roles are never touched.
    """
    if not isinstance(parsed, dict):
        return parsed
    exps = parsed.get("work_experiences")
    if not isinstance(exps, list) or len(exps) < 2:
        return parsed

    def is_earlier_career_block(exp):
        """Report whether the model already emitted its own Earlier Career grouping."""
        return _EARLIER_CAREER_RE.match(
            str((exp or {}).get("company") or "").strip()
        ) is not None

    def is_described_role(exp):
        """Report whether an undated entry is a real job rather than a listing.

        An early-career listing is a bare "Title - Company" line. A described role
        carries its own account of the work, and belongs where the source put it even
        when the source gave it no dates - a 2025 role must not be filed beside 2015
        ones just because its dates are missing.
        """
        if is_earlier_career_block(exp):
            return False
        described = 0
        for role in (exp or {}).get("roles") or []:
            if isinstance(role, dict):
                described += len(_role_plain_bullets(role))
        return described >= _DESCRIBED_ROLE_BULLETS

    def is_undated(exp):
        if not isinstance(exp, dict):
            return False
        if str(exp.get("date_range") or "").strip():
            return False
        roles = exp.get("roles") if isinstance(exp.get("roles"), list) else []
        if not roles:
            return bool(str(exp.get("company") or "").strip())
        for role in roles:
            if isinstance(role, dict) and str(role.get("date_range") or "").strip():
                return False
        return bool(str(exp.get("company") or "").strip())

    # Scan the whole trailing run of dateless entries. A described role inside that run
    # keeps its own row, but must not halt the scan, or the bare "| Company" rows above
    # it stop being collapsed and the drift this function exists to remove comes back.
    start = len(exps)
    while start > 0 and is_undated(exps[start - 1]):
        start -= 1
    tail = exps[start:]
    block = [exp for exp in tail if not is_described_role(exp)]
    described = [exp for exp in tail if is_described_role(exp)]
    # Do not collapse an all-undated work history. Some source CVs omit all
    # dates; turning the entire career into "Earlier Career" would be worse
    # than the original provider output. Only collapse trailing undated roles
    # when at least one dated/structured role exists above them.
    if start == 0 or len(block) < 2:
        return parsed

    bullets = []
    first_title = ""
    for exp in block:
        company = _smart_title_text(exp.get("company") or "", company=True)
        already_grouped = is_earlier_career_block(exp)
        if already_grouped:
            # Already an Earlier Career grouping: take its bullets, not its name or its
            # title, or the heading is nested inside itself and printed again as a
            # bullet and as the role title.
            company = ""
        roles = exp.get("roles") if isinstance(exp.get("roles"), list) else []
        if not roles:
            if company:
                bullets.append(company)
            continue
        for role in roles:
            if not isinstance(role, dict):
                continue
            title = "" if already_grouped else _smart_title_text(role.get("title") or "", title=True)
            if title and not first_title:
                first_title = title
            if title and company:
                line = f"{title} – {company}"
            else:
                line = title or company
            if line and line not in bullets:
                bullets.append(line)
            for extra in _role_plain_bullets(role):
                if extra and extra not in bullets:
                    bullets.append(extra)

    if len(bullets) < 2:
        return parsed

    parsed["work_experiences"] = exps[:start] + described + [{
        "date_range": "",
        "company": "Earlier Career",
        "roles": [{
            # No title: the company row already reads "Earlier Career", and repeating it
            # here prints the heading twice.
            "title": first_title,
            "date_range": "",
            "reason_for_leaving": "",
            "bullets": bullets,
        }]
    }]
    return parsed


# ── References / referees ─────────────────────────────────────────────────────
# A referees block is contact data for third parties, so it never belongs in the
# formatted CV. The parse prompt asks the model to drop it, but the catch-all
# "any other section" rule used to sweep it into a skills category, and already
# parsed data can still carry one, so the removal is deterministic here too.
#
# Matching is on the CATEGORY LABEL only, and only when every word in it is part
# of a referees heading. That keeps genuine skills such as "Reference Data
# Management" or "Reference Architecture" -- which name a discipline, not a
# referee -- untouched.
_REFERENCE_HEADING_WORDS = frozenset({"reference", "references", "referee", "referees"})
_REFERENCE_HEADING_FILLER = frozenset({
    "and", "or", "details", "detail", "contacts", "contact", "contactdetails",
    "information", "info", "personal", "professional", "character", "work",
    "employment", "academic", "business", "available", "upon", "on", "request",
    "furnished", "provided", "list", "section",
})
# "References available upon request" carries no information. It is dropped as a
# whole line even inside a category that is kept for its other content.
_REFERENCE_ON_REQUEST_RE = re.compile(
    r"^(?:references?|referees?)"
    r"(?:\s+(?:are|is|can\s+be|will\s+be|shall\s+be))?"
    r"\s+(?:available|furnished|provided|supplied)"
    r"(?:\s+(?:up)?on\s+request)?[.!]?$",
    re.I,
)


# An accented heading ("RÉFÉRENCES", "Références") and a possessive one
# ("Referee's Details") both have to tokenize to the same words as the plain
# form, or the allowlist below never sees a reference word and the whole block
# renders. Accents are folded away and the possessive "'s" dropped; the
# apostrophe can arrive as ASCII or as either curly form.
# The apostrophe and backtick are written as escapes, not literals, so the
# brace matcher in tests/test_long_cv_output_corrective.js can lift the browser
# mirror of this function out of its source without entering quote mode.
_REFERENCE_POSSESSIVE_RE = re.compile(r"[\u0027\u2018\u2019\u02bc\u00b4\u0060]s\b", re.I)


def _reference_heading_tokens(label):
    # Possessives go first: NFKD turns an acute accent used as an apostrophe into
    # a combining mark, so folding before stripping would leave a bare "s" token.
    text = _REFERENCE_POSSESSIVE_RE.sub("", str(label or ""))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return [token for token in re.split(r"[^A-Za-z]+", text) if token]


def _reads_as_reference_heading(label):
    """True when a skills-category label is purely a references/referees heading."""
    tokens = [token.lower() for token in _reference_heading_tokens(label)]
    if not tokens:
        return False
    if not any(token in _REFERENCE_HEADING_WORDS for token in tokens):
        return False
    return all(
        token in _REFERENCE_HEADING_WORDS or token in _REFERENCE_HEADING_FILLER
        for token in tokens
    )


def _strip_reference_on_request_items(items):
    """Drop "references available upon request" lines, keeping the items' shape."""
    if isinstance(items, list):
        kept = [
            item for item in items
            if not (isinstance(item, str) and _REFERENCE_ON_REQUEST_RE.match(item.strip()))
        ]
        return kept, len(kept) != len(items)
    if isinstance(items, str):
        lines = items.split("\n")
        kept = [line for line in lines if not _REFERENCE_ON_REQUEST_RE.match(line.strip())]
        if len(kept) == len(lines):
            return items, False
        return "\n".join(kept), True
    return items, False


# A referees block is the one place in a CV where a phone number and an email
# address belong to somebody else. The raw-text contact fallbacks in /parse take
# the FIRST match in the document, so a candidate who lists no contact details of
# their own would otherwise be given their referee's -- and the app searches and
# uploads to JobAdder on that email. These spans let the fallbacks skip it.
#
# A span only opens on a line short enough to read as a heading. A sentence such
# as "Provided references and contact details on request" is built entirely from
# allowlisted words, so length is what separates it from a real heading.
_REFERENCE_HEADING_MAX_TOKENS = 5


def _reference_section_spans(cv_text):
    """``(start, end)`` offsets of each referees section in the source text."""
    text = str(cv_text or "")
    if not text:
        return []
    lines = []
    offset = 0
    for line in text.split("\n"):
        lines.append((offset, line))
        offset += len(line) + 1
    spans = []
    open_start = None
    for start, line in lines:
        stripped = line.strip()
        is_heading = (
            bool(stripped)
            and not _REFERENCE_ON_REQUEST_RE.fullmatch(
                " ".join(_reference_heading_tokens(stripped))
            )
            and len(_reference_heading_tokens(stripped)) <= _REFERENCE_HEADING_MAX_TOKENS
            and _reads_as_reference_heading(stripped)
        )
        if is_heading:
            if open_start is None:
                open_start = start
            continue
        if open_start is None:
            continue
        # Any other known section heading closes the block.
        if stripped and _cv_source_boundary_key(stripped) in _CV_SOURCE_SECTION_BOUNDARY_KEYS:
            spans.append((open_start, start))
            open_start = None
    if open_start is not None:
        spans.append((open_start, len(text)))
    return spans


def _offset_in_spans(offset, spans):
    return any(start <= offset < end for start, end in spans)


def _search_outside_reference_sections(pattern, cv_text, spans=None):
    """First match of ``pattern`` in ``cv_text`` that is not inside a referees block."""
    text = str(cv_text or "")
    if not text:
        return None
    if spans is None:
        spans = _reference_section_spans(text)
    for match in re.finditer(pattern, text):
        if not _offset_in_spans(match.start(), spans):
            return match
    return None


def _cv_skill_has_printable_item(items):
    if isinstance(items, list):
        return any(isinstance(item, str) and item.strip() for item in items)
    return bool(str(items or "").strip())


def _drop_reference_sections(parsed):
    """Remove referees/references content from the parsed CV.

    A whole skills category goes when its label reads as a referees heading; a
    kept category only loses an "available upon request" line. Categories left
    with nothing printable are removed, matching the renderer's own filter.
    """
    if not isinstance(parsed, dict):
        return parsed
    skills = parsed.get("skills")
    if not isinstance(skills, list):
        return parsed
    kept = []
    changed = False
    for entry in skills:
        if not isinstance(entry, dict):
            kept.append(entry)
            continue
        if _reads_as_reference_heading(entry.get("category")):
            changed = True
            continue
        items, stripped = _strip_reference_on_request_items(entry.get("items"))
        if not stripped:
            kept.append(entry)
            continue
        changed = True
        # The label survived the heading test, so an emptied category was a
        # referees block under another name. Drop it rather than print a heading
        # over nothing.
        if not _cv_skill_has_printable_item(items):
            continue
        entry = dict(entry)
        entry["items"] = items
        kept.append(entry)
    if changed:
        parsed["skills"] = kept
    return parsed


def _source_has_redacted_language_block(cv_text):
    """Return True only when a Languages block is explicitly redacted/masked.

    This intentionally avoids broad "template/filler" assumptions. A common
    language set such as English/French/German/Spanish can be real, so it should
    be preserved unless the source or parsed value explicitly says it was
    redacted/masked/withheld.
    """
    text = str(cv_text or "")
    if not text:
        return False
    if "language" not in text.lower():
        return False
    for m in re.finditer(r"\blanguages?\b", text, flags=re.I):
        start = max(0, m.start() - 250)
        end = min(len(text), m.end() + 450)
        if _CV_REDACTED_LANGUAGE_RE.search(text[start:end]):
            return True
    return False


def _clean_candidate_languages_from_redaction(parsed, cv_text):
    """Clear languages only when the language evidence is explicitly redacted.

    Do not clear normal language names due to template/filler heuristics. This is
    deliberately narrow per user preference: if something is redacted, ignore it;
    otherwise preserve the parser/AI result.
    """
    if not isinstance(parsed, dict):
        return parsed
    cand = parsed.get("candidate") or {}
    if not isinstance(cand, dict):
        return parsed
    raw_lang = str(cand.get("languages") or "").strip()
    if not raw_lang:
        return parsed
    if _CV_REDACTED_LANGUAGE_RE.search(raw_lang) or _source_has_redacted_language_block(cv_text):
        cand["languages"] = ""
        parsed["candidate"] = cand
    return parsed


def _order_same_company_roles_newest_first(parsed):
    """Deterministically keep promoted roles newest-first inside one employer.

    Providers occasionally return same-company promotions oldest-first even though
    the CV Studio layout requires current/latest role first. Unknown-date roles are
    kept after dated roles in their original relative order.
    """
    if not isinstance(parsed, dict):
        return parsed
    exps = parsed.get("work_experiences") or []
    if not isinstance(exps, list):
        return parsed

    for exp in exps:
        if not isinstance(exp, dict):
            continue
        roles = exp.get("roles") or []
        if not isinstance(roles, list) or len(roles) < 2:
            continue
        decorated = []
        dated_count = 0
        for original_index, role in enumerate(roles):
            if not isinstance(role, dict):
                decorated.append((None, None, original_index, role))
                continue
            date_range = _normalize_cv_date_range(role.get("date_range") or "")
            start_text, end_text = _cv_date_parts(date_range)
            end_point = _cv_date_sort_point(end_text or date_range, end=True)
            start_point = _cv_date_sort_point(start_text or date_range, end=False)
            if end_point or start_point:
                dated_count += 1
            decorated.append((end_point, start_point, original_index, role))
        if dated_count < 2:
            continue

        # Stable newest-first ordering. Unknown dates remain after dated roles.
        decorated.sort(key=lambda item: (
            1 if item[0] is not None or item[1] is not None else 0,
            item[0] or (-1, -1),
            item[1] or (-1, -1),
            -item[2],
        ), reverse=True)
        exp["roles"] = [item[3] for item in decorated]

    # Recompute each employer's header date range from its roles' ranges so the
    # company span can never be backwards or truncated relative to the roles
    # shown under it. Only overrides when the roles actually carry dates.
    for exp in exps:
        if not isinstance(exp, dict):
            continue
        span = _cv_company_span_from_roles(exp.get("roles") or [])
        if span:
            exp["date_range"] = span

    # Keep the header's current position aligned with the first/current role, and
    # derive employment status: the candidate is "current" only when the latest
    # role is open-ended (Present). A concrete end date means they have left, so
    # the header must read LAST POSITION, not CURRENT POSITION.
    cand = parsed.get("candidate") or {}
    if isinstance(cand, dict) and exps:
        top_exp = exps[0] if isinstance(exps[0], dict) else {}
        top_roles = top_exp.get("roles") or []
        if top_roles and isinstance(top_roles[0], dict):
            top_date = _normalize_cv_date_range(top_roles[0].get("date_range") or top_exp.get("date_range") or "")
            _, top_end = _cv_date_parts(top_date)
            end_blob = top_end or top_date
            if re.search(r"\bPresent\b", end_blob, re.I):
                cand["current_position"] = top_roles[0].get("title") or cand.get("current_position") or ""
                cand["current_company"] = top_exp.get("company") or cand.get("current_company") or ""
                cand["is_employed"] = True
            elif re.search(r"\d{4}", end_blob):
                # Concrete end year with no "Present" -> the latest engagement has
                # a stated end, so the candidate has left.
                cand["is_employed"] = False
        parsed["candidate"] = cand
    return parsed


def _extract_explicit_project_blocks(cv_text):
    """Extract conservative project/client blocks from a dedicated project section.

    Besides the visible heading and bullets, retain Duration/source order so the
    formatter can place project groups under the correct promoted role and order
    them chronologically within that role.
    """
    lines = [re.sub(r"\s+", " ", str(line or "").strip()) for line in str(cv_text or "").splitlines()]
    blocks = []
    current = None
    current_bullet = None
    in_projects = False

    def finish_current():
        nonlocal current, current_bullet
        if current_bullet and current is not None:
            current.setdefault("bullets", []).append(current_bullet.strip())
        current_bullet = None
        if current and current.get("title") and current.get("bullets"):
            title = re.sub(r"\s*\|\s*Duration\s*:.*$", "", current.get("title") or "", flags=re.I).strip()
            client = (current.get("client") or "").strip()
            # Replace generic module suffixes with the named client in the visible heading.
            if client:
                title = re.sub(r"\s+[\-–—]\s+(?:[A-Za-z0-9/+& ]+\s+)?Module\s*$", "", title, flags=re.I).strip()
                if _cv_match_key(client) not in _cv_match_key(title):
                    title = f"{title} – {client}"
            current["heading"] = title
            current["source_index"] = len(blocks)
            blocks.append(current)
        current = None

    stop_heading = re.compile(r"^(?:CERTIFICATION|CERTIFICATIONS|EMPLOYMENT HISTORY|WORK HISTORY|CAREER HISTORY|EDUCATION(?: BACKGROUND)?|ACADEMIC|REFERENCE|REFERENCES|SKILLS|TECHNICAL SKILLS|ADDITIONAL INFORMATION)\b", re.I)
    project_section = re.compile(r"\bPROJECT\s+EXPERIENCES?\b", re.I)
    project_marker = re.compile(r"^[✓✔☑]\s*(.+)$")
    bullet_marker = re.compile(r"^[•●▪◦]\s*(.*)$")

    for line in lines:
        if not line:
            continue
        if project_section.search(line):
            in_projects = True
            continue
        if in_projects and stop_heading.match(line):
            finish_current()
            break
        if not in_projects:
            continue

        pm = project_marker.match(line)
        if pm:
            finish_current()
            raw_title = pm.group(1).strip()
            duration = ""
            dm = re.search(r"\|\s*Duration\s*:\s*(.+)$", raw_title, re.I)
            if dm:
                duration = dm.group(1).strip()
                raw_title = raw_title[:dm.start()].strip()
            current = {"title": raw_title, "client": "", "duration": duration, "bullets": []}
            continue
        if current is None:
            continue

        bm = bullet_marker.match(line)
        if bm:
            if current_bullet:
                current.setdefault("bullets", []).append(current_bullet.strip())
            current_bullet = bm.group(1).strip()
            continue
        if current_bullet:
            # Metadata starts a new non-bullet line; wrapped bullet text does not.
            if re.match(r"^(?:Client|Employer|Role|Duration|Technologies?)\s*:", line, re.I):
                current.setdefault("bullets", []).append(current_bullet.strip())
                current_bullet = None
            else:
                current_bullet += " " + line
                continue

        cm = re.search(r"\bClient\s*:\s*([^|]+)", line, re.I)
        if cm:
            current["client"] = cm.group(1).strip()
        dm = re.search(r"\bDuration\s*:\s*([^|]+(?:\s+(?:Present|Current))?)", line, re.I)
        if dm:
            current["duration"] = dm.group(1).strip()

    if in_projects:
        finish_current()
    return blocks


def _restore_explicit_project_headings(parsed, cv_text):
    """Rebuild project groups beneath the correct promoted role.

    The source project section supplies only structure/order. Bullet wording comes
    from the parsed role wherever possible. A common provider drift splits a source
    bullet like ``Strategic Team Leadership: Direct and mentor...`` into two list
    items; when the source confirms that relationship, this joins the pair back into
    one bullet instead of leaving stray pseudo-headings.
    """
    if not isinstance(parsed, dict):
        return parsed
    blocks = _extract_explicit_project_blocks(cv_text)
    if not blocks:
        return parsed

    roles = []
    for exp in parsed.get("work_experiences") or []:
        if not isinstance(exp, dict):
            continue
        for role in exp.get("roles") or []:
            if isinstance(role, dict):
                roles.append(role)

    def role_plain_items(role):
        return [(i, item) for i, item in enumerate(role.get("bullets") or []) if isinstance(item, str)]

    def match_block_to_role(block, role):
        entries = role_plain_items(role)
        if not entries:
            return []
        by_index = {i: text for i, text in entries}
        entry_indices = [i for i, _ in entries]
        used = set()
        matches = []

        for source_i, source_bullet in enumerate(block.get("bullets") or []):
            best = None
            source_text = str(source_bullet or "").strip()
            # First try the frequent split-label shape: short label + following text.
            if ':' in source_text:
                label, remainder = source_text.split(':', 1)
                label = label.strip()
                remainder = remainder.strip()
                if label and remainder and len(label.split()) <= 8:
                    for pos in range(len(entry_indices) - 1):
                        i1, i2 = entry_indices[pos], entry_indices[pos + 1]
                        if i1 in used or i2 in used or i2 != i1 + 1:
                            continue
                        s1 = _cv_text_similarity(by_index[i1], label)
                        s2 = _cv_text_similarity(by_index[i2], remainder)
                        score = (s1 + s2) / 2.0
                        if s1 >= 0.82 and s2 >= 0.50 and (best is None or score > best[0]):
                            combined = by_index[i1].rstrip(':').strip() + ': ' + by_index[i2].strip()
                            best = (score, [i1, i2], combined)

            # Otherwise match one parsed bullet to the complete source bullet.
            for item_i, item_text in entries:
                if item_i in used:
                    continue
                score = _cv_text_similarity(item_text, source_text)
                if score >= 0.56 and (best is None or score > best[0]):
                    best = (score, [item_i], item_text)

            if best is not None:
                score, consumed, output_text = best
                used.update(consumed)
                matches.append({
                    "source_index": source_i,
                    "item_indices": consumed,
                    "text": output_text,
                    "score": score,
                })
        return matches

    # Decide the single best role for each project block. This prevents the same
    # project heading being duplicated across promotions when generic wording overlaps.
    assignments = {id(role): [] for role in roles}
    for block in blocks:
        best_role = None
        best_matches = []
        best_rank = (-1, -1.0)
        for role in roles:
            matches = match_block_to_role(block, role)
            rank = (len(matches), sum(m.get("score", 0.0) for m in matches))
            if rank > best_rank:
                best_rank = rank
                best_role = role
                best_matches = matches
        if best_role is not None and best_matches:
            assignments[id(best_role)].append((block, best_matches))

    for role in roles:
        assigned = assignments.get(id(role)) or []
        if not assigned:
            continue
        original = role.get("bullets") or []
        consumed = set()
        groups = []
        for block, matches in assigned:
            matches = sorted(matches, key=lambda m: m.get("source_index", 0))
            bullets = []
            for match in matches:
                consumed.update(match.get("item_indices") or [])
                text = str(match.get("text") or "").strip()
                if text and text not in bullets:
                    bullets.append(text)
            if bullets:
                groups.append({
                    "heading": block.get("heading") or block.get("title") or "Project",
                    "bullets": bullets,
                    "kind": "project",
                    "_project_block": block,
                })

        groups.sort(key=lambda g: _cv_project_group_sort_key(g.get("_project_block") or {}))
        for group in groups:
            group.pop("_project_block", None)

        # Keep any genuinely unmatched provider content after the structured projects.
        leftovers = [item for i, item in enumerate(original) if i not in consumed]
        role["bullets"] = groups + leftovers
    return parsed


def _extract_authoritative_work_rows(cv_text, parsed=None):
    """Extract authoritative employment rows from pipe or whitespace tables.

    PDF extraction frequently removes visible table borders. The earlier parser only
    accepted `Date | Company | Role`, so rows such as
    `Oct 2022 - Present EY Technology Solutions Sdn Bhd Manager` were missed.
    This extension is deliberately confined to an explicit Employment/Work History
    section and uses parsed role titles as safe split anchors.
    """
    rows = []
    seen = set()
    lines = [re.sub(r"\s+", " ", str(raw_line or "").strip()) for raw_line in str(cv_text or "").splitlines()]

    def add_row(date_cell, company_cell, role_cell):
        if not date_cell or not company_cell or not role_cell:
            return None
        if len(company_cell) > 120 or len(role_cell) > 160:
            return None
        date_norm = _normalize_cv_date_range(date_cell)
        company_norm = _smart_title_text(company_cell, company=True)
        title_norm = _smart_title_text(role_cell, title=True)
        key = (_cv_match_key(date_norm), _cv_match_key(company_norm), _cv_match_key(title_norm))
        if key in seen:
            return next(
                (
                    row for row in rows
                    if (
                        _cv_match_key(row.get("date_range")),
                        _cv_match_key(row.get("company")),
                        _cv_match_key(row.get("title")),
                    ) == key
                ),
                None,
            )
        seen.add(key)
        row = {"date_range": date_norm, "company": company_norm, "title": title_norm}
        rows.append(row)
        return row

    # Existing explicit pipe-delimited layout.
    for line in lines:
        if not line or "|" not in line:
            continue
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c]
        if len(cells) < 3:
            continue
        date_cell, company_cell, role_cell = cells[0], cells[1], " | ".join(cells[2:]).strip()
        low = " ".join(cells[:3]).lower()
        if any(h in low for h in ("dates organization role", "date organization role", "dates | organization | role")):
            continue
        if not _WORK_TABLE_DATE_RE.search(date_cell):
            continue
        if not re.search(r"\b(?:-|to|till|present|current|now|date|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b", date_cell, re.I):
            continue
        add_row(date_cell, company_cell, role_cell)

    # Borderless/whitespace table layout from PDF extraction.
    parsed_work_roles = _flatten_parsed_work_roles(parsed or {})
    known_titles = []
    known_work_pairs = set()
    for item in parsed_work_roles:
        title = re.sub(r"\s+", " ", str(item.get("title") or "").strip())
        if title and title.lower() not in {t.lower() for t in known_titles}:
            known_titles.append(title)
        company_key = _cv_match_key(item.get("company"))
        title_key = _cv_match_key(title)
        if company_key and title_key:
            known_work_pairs.add((company_key, title_key))
    known_titles.sort(key=len, reverse=True)

    in_history = False
    history_heading = re.compile(
        r"^(?:EMPLOYMENT|WORK|CAREER|PROFESSIONAL)\s+(?:HISTORY|EXPERIENCES?)\b"
        r"|^(?:HISTORY|EXPERIENCES?)\s*:?\s*$",
        re.I,
    )
    stop_heading = re.compile(r"^(?:EDUCATION|ACADEMIC|CERTIFICATION|CERTIFICATIONS|REFERENCE|REFERENCES|SKILLS|TECHNICAL SKILLS|ADDITIONAL INFORMATION|LANGUAGES?|PROJECTS?)\b", re.I)
    _mon_sub = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
    # Title-first header lines: "<Title> — <Company> <DateRange>" with the date
    # trailing (e.g. "Dispatcher Technical Support — PT. Foo (Bar) Mar 2011 to Feb 2013").
    # The date is captured at the end first, then the remaining head is split into
    # title/company on the em/en dash or pipe separator.
    title_first_date_at_end = re.compile(
        r"\s+[—–\-]?\s*((?:" + _mon_sub + r"\s+)?\d{4}\s*(?:to|[-–—])\s*(?:(?:" + _mon_sub + r"\s+)?\d{4}|Present|Current|Till\s*Date|To\s*Date))\s*$",
        re.I,
    )
    title_first_single_year_at_end = re.compile(r"\s+(\d{4})\s*$")
    title_first_split = re.compile(r"^(?P<title>[A-Za-z][^—–|]{1,90}?)\s*[—–|]\s*(?P<company>.+)$")
    date_prefix = re.compile(
        r"^((?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+)?\d{4}\s*(?:-|–|—|to)\s*(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+)?(?:\d{4}|Present|Current|Till\s*Date|To\s*Date))\s+(.+)$",
        re.I,
    )
    generic_title = re.compile(
        r"\b((?:(?:Senior|Sr\.?|Junior|Jr\.?|Lead|Principal|Assistant|Associate|Deputy|Group|Regional|Country|General|Chief|Vice|Executive)\s+)*(?:Manager|Director|Head|Associate|Consultant|Analyst|Engineer|Developer|Architect|Specialist|Executive|Officer|Administrator|Coordinator|Supervisor|Partner|President|Intern|Trainee|Accountant|Recruiter|Designer|Scientist|Technician|Controller|Planner|Support)(?:\s+[A-Za-z0-9/&+.-]+){0,4})$",
        re.I,
    )

    def _dash_side_is_role_title(text):
        """Does this side of a "X — Y" header read as the role TITLE (vs employer)?

        The dash split is ambiguous: some CVs write "<Title> — <Company>" and
        others "<Company> — <Title>". Prefer the provider-parsed titles
        (known_titles) as ground truth, then fall back to the generic job-title
        shape. Used to decide orientation so the employer and title are not swapped.
        """
        cleaned = str(text or "").strip()
        if not cleaned:
            return False
        key = _cv_match_key(cleaned)
        for kt in known_titles:
            if key and key == _cv_match_key(kt):
                return True
            if _cv_token_overlap_score(cleaned, kt) >= 0.67:
                return True
        return bool(generic_title.search(cleaned))

    def _title_first_row_parts(
        line, *, allow_single_year=False, allow_unmatched_single_year=False
    ):
        tail = title_first_date_at_end.search(line)
        single_year = False
        if tail is None and allow_single_year:
            tail = title_first_single_year_at_end.search(line)
            single_year = tail is not None
        if tail is None:
            return None
        head = line[:tail.start()].strip()
        split = title_first_split.match(head)
        if not split:
            return None
        side_left = split.group("title").strip().strip("|").strip()
        side_right = split.group("company").strip().strip("|").strip()
        left_is_title = _dash_side_is_role_title(side_left)
        right_is_title = _dash_side_is_role_title(side_right)
        # A trailing bare year is common prose, so only accept the compact
        # header when one side independently looks like a role title.
        if single_year and not (left_is_title or right_is_title):
            return None
        if right_is_title and not left_is_title:
            company, title = side_left, side_right
        else:
            company, title = side_right, side_left
        # Outside a recognized source work subsection, a bare-year row must
        # agree with an employer/title pair the provider already found. This
        # blocks prose such as "Manager — Leadership Programme 2023" from
        # becoming an invented employer while still retaining genuine parsed
        # one-year jobs. A subsection permits deterministic recovery of a role
        # the provider omitted, as in Lee Lin Yuan's MySteel entry.
        if (
            single_year
            and not allow_unmatched_single_year
            and (_cv_match_key(company), _cv_match_key(title)) not in known_work_pairs
        ):
            return None
        return tail.group(1).strip(), company, title

    def _role_local_work_heading(line):
        text = str(line or "").strip()
        key = _cv_source_boundary_key(text.rstrip(":"))
        return key in {"achievements", "responsibilities"} and (
            text.endswith(":") or text.lower().startswith("key ")
        )

    def _is_cv_section_boundary(line):
        text = str(line or "").strip()
        if not text:
            return False
        text = re.sub(r"^\[\s*|\s*\]\s*:?$", "", text).strip().rstrip(":")
        text = re.sub(r"[\s_\-–—=]+$", "", text).strip()
        key = _cv_source_boundary_key(text)
        if key in _CV_SOURCE_SECTION_BOUNDARY_KEYS:
            return True
        # Template headings are sometimes letter-spaced and may share a line
        # with their first value: ``A W A R D S ____`` or
        # ``L A N G U A G E S English``. Collapse only the leading run of
        # single alphabetic tokens, then compare it with the central boundary
        # allowlist; ordinary prose is unaffected.
        letters = []
        for token in text.split():
            token = token.strip(".:;|[]()")
            if not re.fullmatch(r"[A-Za-z]", token):
                break
            letters.append(token)
        compact = "".join(letters).lower()
        if len(compact) < 4:
            return False
        return any(
            compact == re.sub(r"[^a-z]", "", boundary)
            for boundary in _CV_SOURCE_SECTION_BOUNDARY_KEYS
        )

    def _rejected_single_year_header_shape(line):
        tail = title_first_single_year_at_end.search(str(line or ""))
        if tail is None:
            return False
        return bool(title_first_split.match(str(line)[:tail.start()].strip()))

    # ``ACHIEVEMENTS:`` is role-local only when employment clearly continues
    # with another dated job header. At the end of Work Experience it is a
    # top-level CV section and must not be absorbed into the last role.
    role_local_heading_indices = set()
    for heading_index, heading_line in enumerate(lines):
        if not _role_local_work_heading(heading_line):
            continue
        for following_line in lines[heading_index + 1:]:
            if stop_heading.match(following_line) or _is_cv_section_boundary(following_line):
                break
            if date_prefix.match(following_line) or _title_first_row_parts(following_line):
                role_local_heading_indices.add(heading_index)
                break

    for line_index, line in enumerate(lines):
        if not line:
            continue
        if history_heading.match(line):
            in_history = True
            continue
        if in_history and (
            stop_heading.match(line)
            or (
                _is_cv_section_boundary(line)
                and line_index not in role_local_heading_indices
            )
        ):
            break
        if not in_history or re.match(r"^(?:Year|Date|Dates)\s+Company\s+Role$", line, re.I):
            continue
        dm = date_prefix.match(line)
        if dm:
            date_cell, rest = dm.group(1).strip(), dm.group(2).strip()
            title_cell = ""
            company_cell = ""
            for known_title in known_titles:
                tm = re.search(r"(?:^|\s)" + re.escape(known_title) + r"\s*$", rest, re.I)
                if tm:
                    title_cell = known_title
                    company_cell = rest[:tm.start()].strip()
                    break
            if not title_cell:
                gm = generic_title.search(rest)
                if gm:
                    title_cell = gm.group(1).strip()
                    company_cell = rest[:gm.start()].strip()
            add_row(date_cell, company_cell, title_cell)
            continue

        # Dash header with trailing date: "<Title> — <Company> <DateRange>" OR
        # the reverse "<Company> — <Title> | <DateRange>". Disambiguate which side
        # is the role title so the employer and title are not swapped (which would
        # also blank the matched bullets during reconciliation). Strip any stray
        # pipe the trailing-date capture leaves behind.
        parts = _title_first_row_parts(line)
        if parts:
            add_row(*parts)

    # Enrich the authoritative headers with source bullets and semantic work
    # sub-section headings. This pass is deliberately limited to explicit
    # bullet glyphs inside the work-history section; wrapped continuation lines
    # are joined, but ordinary prose is never promoted into a duty.
    source_bullet_marker = re.compile(r"^[•●▪◦‣∙·▶►➤⁃»›]\s*(.*)$")
    work_group_heading = re.compile(
        r"^(?:(?:INDEPENDENT|FREELANCE)(?:\s*/\s*(?:INDEPENDENT|FREELANCE))?"
        r"\s+(?:CONSULTING|PROJECTS?)(?:\s*(?:&|AND|/)\s*(?:DELIVERY|PROJECTS?))?"
        r"|EARLIER\s+(?:EXPERIENCE|CAREER))$",
        re.I,
    )
    compact_earlier_role = re.compile(
        r"^(?P<title>[^,•]{2,100}),\s*(?P<company>[^()•]{2,140}?)\s*"
        r"\((?P<date>" + _mon_sub + r"\s*[-–—]\s*" + _mon_sub + r"\s+\d{4})\)$",
        re.I,
    )
    active_row = None
    active_bullet = ""
    pending_section_heading = ""

    def flush_source_bullet():
        nonlocal active_bullet
        text = re.sub(r"\s+", " ", active_bullet).strip()
        if active_row is not None and text:
            source_bullets = active_row.setdefault("source_bullets", [])
            if text not in source_bullets:
                source_bullets.append(text)
        active_bullet = ""

    in_history = False
    for line_index, line in enumerate(lines):
        if not line:
            continue
        if history_heading.match(line):
            in_history = True
            continue
        if in_history and (
            stop_heading.match(line)
            or (
                _is_cv_section_boundary(line)
                and line_index not in role_local_heading_indices
            )
        ):
            flush_source_bullet()
            break
        if not in_history:
            continue
        if active_row is not None and line_index in role_local_heading_indices:
            flush_source_bullet()
            continue
        if work_group_heading.fullmatch(line):
            flush_source_bullet()
            active_row = None
            pending_section_heading = _smart_title_text(line, title=True)
            continue

        # Compact early-career summaries can carry two or more entries on one
        # line, separated by a visible bullet, with a shared year inside each
        # parenthesized date range.
        compact_matches = []
        for segment in re.split(r"\s+[•●]\s+", line):
            match = compact_earlier_role.fullmatch(segment.strip())
            if match:
                compact_matches.append(match)
        if compact_matches and len(compact_matches) == len(re.split(r"\s+[•●]\s+", line)):
            flush_source_bullet()
            for match in compact_matches:
                row = add_row(
                    match.group("date"),
                    match.group("company"),
                    match.group("title"),
                )
                if row is not None and pending_section_heading:
                    row["section_heading"] = pending_section_heading
                    pending_section_heading = ""
                active_row = row
            continue

        parts = _title_first_row_parts(
            line,
            allow_single_year=True,
            allow_unmatched_single_year="|" in line,
        )
        if parts:
            flush_source_bullet()
            active_row = add_row(*parts)
            if active_row is not None and pending_section_heading:
                active_row["section_heading"] = pending_section_heading
                pending_section_heading = ""
            continue

        # A line that structurally resembles a one-year job header but failed
        # the grounding rules is neither a job nor a wrapped continuation of
        # the preceding duty. Flush the real duty and discard the unsafe line.
        if _rejected_single_year_header_shape(line):
            flush_source_bullet()
            continue

        bullet_match = source_bullet_marker.match(line)
        if bullet_match and active_row is not None:
            flush_source_bullet()
            active_bullet = bullet_match.group(1).strip()
            continue
        if active_bullet and active_row is not None:
            if active_bullet.endswith("-") and re.match(r"^[a-z]", line):
                active_bullet += line
            else:
                active_bullet += " " + line

    flush_source_bullet()

    return rows


def _flatten_parsed_work_roles(parsed):
    flat = []
    for exp_i, exp in enumerate((parsed or {}).get("work_experiences") or []):
        if not isinstance(exp, dict):
            continue
        company = exp.get("company") or ""
        exp_date = exp.get("date_range") or ""
        roles = exp.get("roles") if isinstance(exp.get("roles"), list) else []
        if not roles:
            roles = [{"title": "", "date_range": "", "bullets": []}]
        for role_i, role in enumerate(roles):
            if not isinstance(role, dict):
                continue
            flat.append({
                "exp_i": exp_i,
                "role_i": role_i,
                "company": company,
                "exp_date": exp_date,
                "title": role.get("title") or "",
                "role_date": role.get("date_range") or exp_date,
                "role": role,
            })
    return flat


def _score_authoritative_row_match(row, item):
    score = 0.0
    row_company_key = _cv_match_key(row.get("company"))
    item_company_key = _cv_match_key(item.get("company"))
    row_title_key = _cv_match_key(row.get("title"))
    item_title_key = _cv_match_key(item.get("title"))
    row_date = _normalize_cv_date_range(row.get("date_range"))
    item_date = _normalize_cv_date_range(item.get("role_date") or item.get("exp_date"))

    if row_company_key and row_company_key == item_company_key:
        score += 5.0
    else:
        comp_overlap = _cv_token_overlap_score(row.get("company"), item.get("company"))
        if comp_overlap >= 0.67:
            score += 3.0
        elif comp_overlap >= 0.34:
            score += 1.5

    if row_title_key and row_title_key == item_title_key:
        score += 3.0
    else:
        title_overlap = _cv_token_overlap_score(row.get("title"), item.get("title"))
        if title_overlap >= 0.67:
            score += 2.0
        elif title_overlap >= 0.34:
            score += 1.0

    if row_date and item_date and row_date.lower() == item_date.lower():
        score += 2.5
    else:
        rs, re_ = _cv_date_parts(row_date)
        is_, ie = _cv_date_parts(item_date)
        if rs and is_ and rs.lower() == is_.lower():
            score += 1.0
        if re_ and ie and re_.lower() == ie.lower():
            score += 1.0

    return score


def _reconcile_work_experience_with_authoritative_table(parsed, cv_text):
    """Use a source work-history table as a deterministic skeleton when present.

    The function preserves matched role bullets/reasons but corrects employer,
    date, title, and order from the source table. It prevents provider drift such
    as grouping old roles under a project/vendor organization.
    """
    if not isinstance(parsed, dict):
        return parsed
    rows = _extract_authoritative_work_rows(cv_text, parsed)
    if len(rows) < 2:
        return parsed
    current_exps = parsed.get("work_experiences") or []
    if not isinstance(current_exps, list) or not current_exps:
        return parsed

    flat = _flatten_parsed_work_roles(parsed)
    used = set()
    rebuilt = []
    # Group only contiguous same-company table rows. Do NOT merge repeated
    # non-contiguous employers separated by other companies; those represent
    # distinct stints and must stay separate.
    last_exp = None
    last_comp_key = None
    matched_count = 0

    for row in rows:
        best_idx = None
        best_score = -1.0
        for idx, item in enumerate(flat):
            if idx in used:
                continue
            sc = _score_authoritative_row_match(row, item)
            if sc > best_score:
                best_idx, best_score = idx, sc
        matched_role = None
        if best_idx is not None and best_score >= 4.0:
            used.add(best_idx)
            matched_count += 1
            matched_role = dict(flat[best_idx].get("role") or {})
        else:
            matched_role = {"reason_for_leaving": "", "bullets": []}

        parsed_bullets = (
            matched_role.get("bullets")
            if isinstance(matched_role.get("bullets"), list)
            else []
        )
        source_bullets = [
            str(value).strip()
            for value in (row.get("source_bullets") or [])
            if str(value or "").strip()
        ]
        # Explicit source glyph bullets are stronger evidence than an incomplete
        # provider list. Replace only when the deterministic source pass found
        # more duties, preserving richer structured provider output otherwise.
        role_bullets = (
            source_bullets
            if len(source_bullets) > len(_role_plain_bullets(matched_role))
            else parsed_bullets
        )

        role_obj = {
            "title": row.get("title") or matched_role.get("title") or "",
            "date_range": row.get("date_range") or matched_role.get("date_range") or "",
            "reason_for_leaving": matched_role.get("reason_for_leaving") or "",
            "bullets": role_bullets,
        }
        comp_key = _cv_match_key(row.get("company"))
        if last_exp is not None and comp_key and comp_key == last_comp_key:
            exp = last_exp
            exp["roles"].append(role_obj)
            exp.setdefault("_source_dates", []).append(row.get("date_range") or "")
        else:
            exp = {"date_range": row.get("date_range") or "", "company": row.get("company") or "", "roles": [role_obj], "_source_dates": [row.get("date_range") or ""]}
            if row.get("section_heading"):
                exp["section_heading"] = row.get("section_heading")
            rebuilt.append(exp)
            last_exp = exp
            last_comp_key = comp_key

    # If every detected table row matched a provider-parsed role AND the provider
    # parse contains MORE roles than the table, the table is an incomplete subset
    # of an already-correct parse -- a role the row regex could not see, such as a
    # multi-line "Title / Client: X / dates / (Vendors)" block or an undated
    # early-career line. There is no drift to correct here, so trust the fuller
    # parse rather than rebuilding a skeleton that silently drops those roles.
    if rows and matched_count == len(rows) and len(flat) > len(rows):
        return parsed

    # Safety valve: do not replace a richly parsed CV with mostly empty skeletons
    # unless the parsed output is obviously suspicious. This protects unusual CVs
    # whose table is a shallow summary and whose detail lives elsewhere.
    suspicious = False
    table_companies = {_cv_match_key(r.get("company")) for r in rows}
    parsed_companies = [_cv_match_key(e.get("company")) for e in current_exps if isinstance(e, dict)]
    if len(set(parsed_companies)) < max(2, len(table_companies) // 2):
        suspicious = True
    for exp in current_exps:
        if not isinstance(exp, dict):
            continue
        if exp.get("date_range"):
            s, e = _cv_date_parts(exp.get("date_range"))
            # Very broad range under a single employer while table shows many employers.
            if ("Present" in (e or "")) and len(table_companies) >= 4 and _cv_match_key(exp.get("company")) not in table_companies:
                suspicious = True
    if matched_count < max(1, len(rows) // 3) and not suspicious:
        return parsed

    # Extra safety valve: some CVs contain a small recent-work summary table
    # while the full history is described later in normal paragraphs. In that
    # case, using the table as a complete skeleton would delete older roles.
    # Only treat the table as incomplete when it covers a minority of the parsed
    # role rows and the parsed output is not already suspicious/drifted. Real
    # full-history tables, such as 7-10 row Dates | Organization | Role tables,
    # still remain authoritative.
    if not suspicious and len(rows) < len(flat) and len(rows) <= max(2, int(len(flat) * 0.60)):
        return parsed

    for exp in rebuilt:
        roles = exp.get("roles") or []
        if len(roles) == 1:
            roles[0]["date_range"] = ""
            exp["date_range"] = exp.get("_source_dates", [exp.get("date_range")])[0]
        else:
            exp["date_range"] = _cv_combine_date_ranges(exp.get("_source_dates") or [r.get("date_range") for r in roles])
        exp.pop("_source_dates", None)

    parsed["work_experiences"] = rebuilt
    # The rows above came directly from the source work-history sequence. Keep
    # that order through final normalization so a concurrent freelance venture
    # cannot jump ahead of the candidate's primary current employment.
    parsed["_work_experience_order_authoritative"] = True
    cand = parsed.get("candidate") or {}
    if isinstance(cand, dict) and rebuilt:
        first_role = (rebuilt[0].get("roles") or [{}])[0]
        cand["current_company"] = rebuilt[0].get("company") or cand.get("current_company") or ""
        cand["current_position"] = first_role.get("title") or cand.get("current_position") or ""
        # If the top source row is Present, trust it for current employment.
        top_date = rebuilt[0].get("date_range") or first_role.get("date_range") or ""
        if re.search(r"\bPresent\b", top_date, re.I):
            cand["is_employed"] = True
        parsed["candidate"] = cand
    return parsed
