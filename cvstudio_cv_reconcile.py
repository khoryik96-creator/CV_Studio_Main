"""Deterministic CV parse post-processing for CV Studio.

Behaviour-preserving extraction from the app shell: the structure corrections
applied to a provider-parsed CV before formatting -- authoritative work-row
extraction and reconciliation, same-company role ordering, explicit project
heading restoration, incomplete early-career collapsing, and redaction-aware
language cleanup. Pure functions of their inputs (parsed dict + source text) --
no Flask, no globals, no network, no AI call. This module never imports ``app``.
"""

import re

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

    start = len(exps)
    while start > 0 and is_undated(exps[start - 1]):
        start -= 1
    block = exps[start:]
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
        roles = exp.get("roles") if isinstance(exp.get("roles"), list) else []
        if not roles:
            if company:
                bullets.append(company)
            continue
        for role in roles:
            if not isinstance(role, dict):
                continue
            title = _smart_title_text(role.get("title") or "", title=True)
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

    parsed["work_experiences"] = exps[:start] + [{
        "date_range": "",
        "company": "Earlier Career",
        "roles": [{
            "title": first_title or "Earlier Career",
            "date_range": "",
            "reason_for_leaving": "",
            "bullets": bullets,
        }]
    }]
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
