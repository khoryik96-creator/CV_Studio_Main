"""Spider (AI Crawler) boolean, keyword, and candidate field-parsing helpers.

Behaviour-preserving extraction of the stateless candidate-matching logic from
the legacy web shell: boolean rule tokenisation, positive/negative term
extraction, boolean expression evaluation, discovery-keyword and term-coverage
matching, preview text cleaning, and (Phase 7B) candidate field parsing —
experience-years bounds, employment-month parsing, residency/status and
work-setup alias resolution, candidate text/id extraction, candidate search-key
deduplication, candidate-items payload parsing, and plain-keyword candidate
marking.

Pure functions of their inputs - no Flask, no globals, no network, no JobAdder
or provider access. This module never imports ``app``.
"""

import hashlib
import json
import re
import time
from datetime import date


def _spider_terms(value, max_terms=18):
    """Split recruiter filter text into safe, compact terms for candidate filtering."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_parts = []
        for v in value:
            raw_parts.extend(_spider_terms(v, max_terms=max_terms))
        out, seen = [], set()
        for t in raw_parts:
            k = t.lower()
            if k not in seen:
                seen.add(k)
                out.append(t)
        return out[:max_terms]
    text = str(value or "")
    # Split before stripping control chars so newline-separated must-haves stay separate terms.
    parts = re.split(r"[,;\n\r]+", text)
    out, seen = [], set()
    for part in parts:
        part = re.sub(r"[\x00-\x1f\x7f]", " ", part)
        part = re.sub(r"^[\s\-•*]+", "", part).strip().strip('"\'')
        part = re.sub(r"\s+", " ", part)
        if len(part) < 2 or len(part) > 80:
            continue
        k = part.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(part)
        if len(out) >= max_terms:
            break
    return out


def _spider_boolean_not_terms(value, max_terms=18):
    """Extract simple NOT terms from recruiter Boolean keyword rules."""
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(value or ""))
    out, seen = [], set()
    pat = re.compile(r"\bNOT\s+(?:\"([^\"]+)\"|'([^']+)'|\(([^)]+)\)|([^\s(),;]+))", re.I)
    for m in pat.finditer(text):
        raw = next((g for g in m.groups() if g), "")
        for term in re.split(r"\bAND\b|\bOR\b|[,;/]+", raw, flags=re.I):
            term = re.sub(r"^[\s\-•*]+", "", term).strip().strip('"\'()')
            term = re.sub(r"\s+", " ", term)
            if len(term) < 2 or len(term) > 80:
                continue
            k = term.lower()
            if k in seen:
                continue
            seen.add(k)
            out.append(term)
            if len(out) >= max_terms:
                return out
    return out


def _spider_boolean_positive_terms(value, max_terms=24):
    """Extract positive match terms from simple Boolean rules without treating AND/OR as terms."""
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(value or ""))
    if not text.strip():
        return []
    text = re.sub(r"\bNOT\s+(?:\"[^\"]+\"|'[^']+'|\([^)]+\)|[^\s(),;]+)", " ", text, flags=re.I)
    text = text.replace("（", "(").replace("）", ")")
    parts = []
    for q in re.findall(r"\"([^\"]+)\"|'([^']+)'", text):
        parts.append(q[0] or q[1])
    text = re.sub(r"\"[^\"]+\"|'[^']+'", " ", text)
    parts.extend(re.split(r"\bAND\b|\bOR\b|[,;\n\r()/|]+", text, flags=re.I))
    out, seen = [], set()
    for part in parts:
        term = re.sub(r"^[\s\-•*]+", "", str(part or "")).strip().strip('"\'()')
        term = re.sub(r"\s+", " ", term)
        if not term or term.lower() in {"and", "or", "not"}:
            continue
        if len(term) < 2 or len(term) > 80:
            continue
        k = term.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(term)
        if len(out) >= max_terms:
            break
    return out


def _spider_terms_for_fit(value, max_terms=24):
    text = str(value or "")
    if re.search(r"\b(AND|OR|NOT)\b|[()\"]", text):
        return _spider_boolean_positive_terms(text, max_terms)
    return _spider_terms(text, max_terms)


def _spider_term_matches(text, term):
    """Boundary-aware term/phrase matching for recruiter filters.

    Short acronyms must be complete tokens: BI does not match mobile, SAP does
    not match sapphire, and HR does not match three. Phrases retain whitespace
    matching while punctuation-heavy skills such as C++ remain usable.
    """
    source = re.sub(r"\s+", " ", str(text or ""))
    needle = re.sub(r"\s+", " ", str(term or "")).strip()
    if not source or not needle:
        return False
    left = r"(?<!\w)" if needle[0].isalnum() or needle[0] == "_" else ""
    right = r"(?!\w)" if needle[-1].isalnum() or needle[-1] == "_" else ""
    return re.search(left + re.escape(needle) + right, source, re.I | re.UNICODE) is not None


def _spider_normalized_record_label(item):
    if not isinstance(item, dict):
        return ""
    for key in ("name", "label", "fieldName", "customFieldName", "displayName", "title"):
        value = str(item.get(key) or "").strip().casefold()
        if value:
            return re.sub(r"[^a-z0-9]+", "", value)
    return ""


def _spider_hit_terms(blob_low, terms):
    hits = []
    for term in terms or []:
        if _spider_term_matches(blob_low, term):
            hits.append(term)
    return hits


def _spider_boolean_tokens(rule_text):
    """Tokenize recruiter Boolean syntax for both text and JobAdder set evaluation."""
    raw = str(rule_text or "").replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    raw = re.sub(r"[,;\n\r|]+", " OR ", raw)
    token_re = re.compile(r'"([^\"]+)"|\'([^\']+)\'|(\()|(\))|\b(AND|OR|NOT)\b|([^\s()]+)', re.I)
    tokens = []
    for m in token_re.finditer(raw):
        quoted_double, quoted_single, lp, rp, op, bare = m.groups()
        if quoted_double is not None or quoted_single is not None:
            term = (quoted_double if quoted_double is not None else quoted_single).strip()
            if term:
                tokens.append(("TERM", term))
        elif lp:
            tokens.append(("LP", lp))
        elif rp:
            tokens.append(("RP", rp))
        elif op:
            tokens.append((op.upper(), op.upper()))
        elif bare:
            term = bare.strip().strip('"\'')
            if term:
                tokens.append(("TERM", term))
    if not tokens:
        return []

    # Adjacent atoms keep the earlier recall-oriented OR behaviour.
    expanded = []
    prev_type = None
    for tok in tokens:
        typ = tok[0]
        if prev_type in {"TERM", "RP"} and typ in {"TERM", "LP", "NOT"}:
            expanded.append(("OR", "OR"))
        expanded.append(tok)
        prev_type = typ
    return expanded


def _spider_boolean_terms(rule_text, max_terms=16):
    """Return unique Boolean atoms in recruiter order, excluding operators."""
    out, seen = [], set()
    for typ, val in _spider_boolean_tokens(rule_text):
        if typ != "TERM":
            continue
        term = re.sub(r"\s+", " ", str(val or "")).strip()
        if len(term) < 2 or len(term) > 100:
            continue
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(term)
        if len(out) >= max_terms:
            break
    return out


def _spider_boolean_expression_match(blob_low, rule_text, proven_terms=None):
    """Evaluate recruiter Boolean syntax against profile text plus JobAdder-proven terms.

    ``proven_terms`` are terms JobAdder itself confirmed through separate latest-resume
    keyword searches. This is essential because the candidate detail endpoint often does
    not expose the full resume text that the Keywords endpoint searched.
    """
    tokens = _spider_boolean_tokens(rule_text)
    if not tokens:
        return True, [], []

    proven = {re.sub(r"\s+", " ", str(x or "")).strip().lower() for x in (proven_terms or []) if str(x or "").strip()}
    precedence = {"OR": 1, "AND": 2, "NOT": 3}
    output = []
    ops = []
    for tok in tokens:
        typ = tok[0]
        if typ == "TERM":
            output.append(tok)
        elif typ in precedence:
            while ops and ops[-1][0] in precedence and (
                precedence[ops[-1][0]] > precedence[typ]
                or (typ != "NOT" and precedence[ops[-1][0]] == precedence[typ])
            ):
                output.append(ops.pop())
            ops.append(tok)
        elif typ == "LP":
            ops.append(tok)
        elif typ == "RP":
            while ops and ops[-1][0] != "LP":
                output.append(ops.pop())
            if ops and ops[-1][0] == "LP":
                ops.pop()
    while ops:
        op = ops.pop()
        if op[0] not in {"LP", "RP"}:
            output.append(op)

    stack = []
    hits = []
    missing = []
    for typ, val in output:
        if typ == "TERM":
            key = re.sub(r"\s+", " ", str(val or "")).strip().lower()
            found = key in proven or bool(_spider_hit_terms(blob_low, [val]))
            stack.append(found)
            if found:
                hits.append(val)
            else:
                missing.append(val)
        elif typ == "NOT":
            stack.append(not stack.pop() if stack else True)
        elif typ in {"AND", "OR"}:
            right = stack.pop() if stack else False
            left = stack.pop() if stack else False
            stack.append((left and right) if typ == "AND" else (left or right))
    return (bool(stack[-1]) if stack else False), hits, missing


def _spider_discovery_keyword_match(blob_low, rule_text, strict=False, proven_terms=None):
    """Return (matched, evidence, missing) for keyword discovery.

    JobAdder performs latest-resume keyword discovery. CV Studio verifies recruiter
    Boolean logic using both visible candidate/profile text and the exact atomic terms
    proven by the JobAdder Keywords searches.
    """
    raw = str(rule_text or "").strip()
    if not raw:
        return True, [], []
    proven_terms = list(proven_terms or [])
    negatives = _spider_boolean_not_terms(raw, 18)
    negative_hits = _spider_hit_terms(blob_low, negatives)
    proven_low = {re.sub(r"\s+", " ", str(x or "")).strip().lower() for x in proven_terms}
    negative_hits.extend([t for t in negatives if str(t).strip().lower() in proven_low and t not in negative_hits])
    if negative_hits:
        return False, [], ["excluded keyword: " + ", ".join(negative_hits[:5])]

    has_boolean = re.search(r"\b(AND|OR|NOT)\b|[()\"']", raw, re.I) is not None
    if has_boolean:
        matched, hits, missing = _spider_boolean_expression_match(blob_low, raw, proven_terms=proven_terms)
        if not matched:
            return False, hits, ["Boolean rule not satisfied" + ((": " + ", ".join(missing[:6])) if missing else "")]
        return True, hits, []

    positives = _spider_terms(raw, 36)
    hits = _spider_hit_terms(blob_low, positives)
    for t in positives:
        if str(t).strip().lower() in proven_low and t not in hits:
            hits.append(t)
    if not positives:
        return True, [], []
    if strict:
        missing = [t for t in positives if t not in hits]
        if missing:
            return False, hits, ["missing keyword: " + ", ".join(missing[:6])]
    elif not hits:
        return False, [], ["no Boolean/keyword evidence visible"]
    return True, hits, []


def _spider_term_coverage(blob_low, term):
    """Return 0..1 evidence coverage for one phrase without substring noise."""
    if _spider_term_matches(blob_low, term):
        return 1.0
    words = [w for w in re.findall(r"[A-Za-z0-9+#.]+", str(term or "")) if len(w) > 1]
    if len(words) < 2:
        return 0.0
    matched = 0
    for word in words:
        variants = [word]
        if len(word) > 4 and word.lower().endswith("s"):
            variants.append(word[:-1])
        if any(_spider_term_matches(blob_low, v) for v in variants):
            matched += 1
    coverage = matched / float(len(words))
    # A failed two-word phrase must never receive credit from one generic token
    # (for example AWS alone must not satisfy "AWS RDS"). If both words are
    # visible but non-adjacent, retain conservative partial credit.
    if len(words) == 2:
        return 0.75 if matched == 2 else 0.0
    # One generic token from a longer phrase is too weak to count as evidence.
    if matched < 2:
        return 0.0
    return coverage if coverage >= 0.5 else 0.0


def _spider_clean_doc_text_for_preview(text):
    text = str(text or '')
    text = text.replace('\r', '\n').replace('\x07', ' | ')
    text = re.sub(r'[\x00-\x06\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]+', ' ', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r' *\| *\| *', ' | ', text)
    text = re.sub(r'\n[ \t]+', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _spider_boolean_fallback_atoms(rule_text, max_positive=8, max_negative=24):
    """Return ordered positive and NOT-scoped atoms from recruiter Boolean text.

    The lightweight recursive walk understands NOT applied to one atom or a
    parenthesized group. Quoted phrases (single or double) and unquoted Unicode
    terms are preserved. It intentionally does not attempt local Boolean result
    validation; it only creates a safe zero-result discovery fallback.
    """
    raw = re.sub(r"[\x00-\x1f\x7f]", " ", str(rule_text or ""))
    token_re = re.compile(
        r"""\s*(?:
            (?P<dq>"(?:\\.|[^"\\])*")|
            (?P<sq>'(?:\\.|[^'\\])*')|
            (?P<lp>\()|(?P<rp>\))|
            (?P<op>\bAND\b|\bOR\b|\bNOT\b)|
            (?P<word>[^\s()]+)
        )""",
        re.I | re.X | re.UNICODE,
    )
    tokens = []
    for match in token_re.finditer(raw):
        kind = match.lastgroup
        value = match.group(kind) if kind else ""
        if kind in ("dq", "sq"):
            value = value[1:-1]
            value = re.sub(r"\\([\\\"'])", r"\1", value)
            tokens.append(("atom", value))
        elif kind == "op":
            tokens.append((value.upper(), value.upper()))
        elif kind == "lp":
            tokens.append(("(", value))
        elif kind == "rp":
            tokens.append((")", value))
        elif kind == "word":
            value = value.strip(" \t\r\n,;:")
            if value:
                tokens.append(("atom", value))

    positives, negatives = [], []

    def walk(index, inherited_negative=False):
        pending_not = False
        while index < len(tokens):
            kind, value = tokens[index]
            if kind == ")":
                return index + 1
            if kind == "NOT":
                pending_not = not pending_not
                index += 1
                continue
            if kind in ("AND", "OR"):
                pending_not = False
                index += 1
                continue
            effective_negative = bool(inherited_negative) ^ bool(pending_not)
            pending_not = False
            if kind == "(":
                index = walk(index + 1, effective_negative)
                continue
            if kind == "atom":
                term = re.sub(r"\s+", " ", str(value or "")).strip(" \t\r\n,;:")[:100]
                if term and term.upper() not in {"AND", "OR", "NOT"}:
                    (negatives if effective_negative else positives).append(term)
            index += 1
        return index

    walk(0, False)

    def dedupe(values, limit):
        out, seen = [], set()
        for value in values:
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(value)
            if len(out) >= max(1, int(limit or 1)):
                break
        return out

    return dedupe(positives, max_positive), dedupe(negatives, max_negative)


def _spider_boolean_fallback_terms(rule_text, max_terms=8):
    positives, _negatives = _spider_boolean_fallback_atoms(rule_text, max_terms, 24)
    return positives


def _spider_min_years_value(value):
    try:
        n = int(float(str(value or "0").strip() or 0))
    except Exception:
        n = 0
    return max(0, min(40, n))


def _spider_max_years_value(value):
    """Return an inclusive upper experience bound, or ``None`` for no maximum.

    The UI uses 40 as its LinkedIn-style open-ended right edge (40+), so a
    selected value of 40 intentionally means no upper cap rather than excluding
    a candidate with more than forty years of visible experience.
    """
    if value is None or str(value).strip() == "":
        return None
    try:
        n = int(float(str(value).strip()))
    except Exception:
        return None
    n = max(0, min(40, n))
    return None if n >= 40 else n


def _spider_years_bounds(filters):
    filters = filters if isinstance(filters, dict) else {}
    minimum = _spider_min_years_value(
        filters.get("years_min")
        if filters.get("years_min") is not None
        else (filters.get("years") or filters.get("experience_years"))
    )
    maximum = _spider_max_years_value(
        filters.get("years_max")
        if filters.get("years_max") is not None
        else filters.get("experience_years_max")
    )
    if maximum is not None and maximum < minimum:
        maximum = minimum
    return minimum, maximum


def _spider_parse_employment_month(value, is_end=False):
    raw = re.sub(r"\s+", " ", str(value or "")).strip()
    if not raw:
        return None
    if re.search(r"\b(?:present|current|now|ongoing|to date)\b", raw, re.I):
        today = date.today()
        return today.year * 12 + (today.month - 1)
    m = re.search(r"(?<!\d)((?:19|20)\d{2})(?:[-/.](1[0-2]|0?[1-9]))?(?!\d)", raw)
    if not m:
        month_names = {
            "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
            "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
            "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
            "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
        }
        m2 = re.search(
            r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
            r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
            r"[\s,./-]+((?:19|20)\d{2})\b",
            raw,
            re.I,
        )
        if not m2:
            return None
        month = month_names.get(m2.group(1).lower()[:3])
        year = int(m2.group(2))
    else:
        year = int(m.group(1))
        month = int(m.group(2)) if m.group(2) else (12 if is_end else 1)
    if year < 1950 or year > date.today().year + 1 or not month:
        return None
    return year * 12 + (month - 1)


def _spider_structured_employment_years(candidate):
    """Calculate non-overlapping career duration from JobAdder employment history."""
    roots = []
    if isinstance(candidate, dict):
        roots.append(candidate)
        detail = candidate.get("_spiderDetail")
        if isinstance(detail, dict):
            roots.append(detail)
    intervals = []
    seen_records = set()
    for root in roots:
        employment = root.get("employment") if isinstance(root.get("employment"), dict) else {}
        histories = []
        for key in ("history", "employmentHistory", "workHistory", "positions"):
            value = employment.get(key)
            if isinstance(value, list):
                histories.extend(value)
        for key in ("employmentHistory", "workHistory", "positions"):
            value = root.get(key)
            if isinstance(value, list):
                histories.extend(value)
        for record in histories[:200]:
            if not isinstance(record, dict):
                continue
            signature = repr(sorted((str(k), str(v)) for k, v in record.items() if k in {
                "start", "startDate", "from", "dateFrom", "end", "endDate", "to", "dateTo", "employer", "position"
            }))
            if signature in seen_records:
                continue
            seen_records.add(signature)
            start_raw = next((record.get(k) for k in ("start", "startDate", "from", "dateFrom", "dateStarted") if record.get(k)), None)
            end_raw = next((record.get(k) for k in ("end", "endDate", "to", "dateTo", "dateFinished") if record.get(k)), None)
            start_month = _spider_parse_employment_month(start_raw, is_end=False)
            end_month = _spider_parse_employment_month(end_raw or "Present", is_end=True)
            if start_month is None or end_month is None or end_month < start_month:
                continue
            intervals.append((start_month, end_month + 1))
    if not intervals:
        return None
    intervals.sort()
    merged = []
    for start_month, end_month in intervals:
        if not merged or start_month > merged[-1][1]:
            merged.append([start_month, end_month])
        else:
            merged[-1][1] = max(merged[-1][1], end_month)
    total_months = sum(max(0, end_month - start_month) for start_month, end_month in merged)
    return round(total_months / 12.0, 2) if total_months > 0 else None


def _spider_visible_years(candidate):
    """Return explicit or structured career experience without age/location guesses.

    Structured JobAdder employment history remains authoritative. Text fallback
    accepts common recruiter wording (``3 yrs exp``, ``18 months experience``,
    ``10 years overall experience``) but still requires an explicit experience
    marker in the same phrase. Generic elapsed time such as ``20 years in
    Malaysia`` or ``graduated 12 years ago`` therefore remains unknown.
    """
    structured = _spider_structured_employment_years(candidate)
    if structured is not None:
        return structured

    text = _spider_pick_field_text(
        candidate,
        ["totalexperience", "experienceyears", "yearsexperience", "experience", "profile", "summary"],
    )
    if not text:
        text = _spider_candidate_blob(candidate)
    text = re.sub(r"\s+", " ", str(text or ""))
    vals = []
    qualifier = (
        r"(?:overall\s+|total\s+|relevant\s+|professional\s+|hands[- ]on\s+|"
        r"industry\s+|working\s+|commercial\s+|technical\s+|practical\s+|"
        r"[A-Za-z][A-Za-z0-9+#./-]{1,24}\s+){0,3}"
    )
    year_patterns = [
        # 3 years overall experience / 3+ yrs AWS experience / 3 yrs exp
        rf"(?<!\d)(\d{{1,2}}(?:\.\d+)?)(?:\+)?\s*(?:years?|yrs?)\s+(?:of\s+)?{qualifier}(?:experience|exp)\b",
        # overall experience: 3 years / AWS experience of 3 yrs
        rf"\b{qualifier}(?:experience|exp)\s*(?:of\s*)?[:=-]?\s*(\d{{1,2}}(?:\.\d+)?)(?:\+)?\s*(?:years?|yrs?)\b",
        # over/nearly 3 years of relevant experience
        rf"\b(?:over|more\s+than|around|approximately|approx\.?|nearly)\s+(\d{{1,2}}(?:\.\d+)?)\s*(?:years?|yrs?)\s+(?:of\s+)?{qualifier}(?:experience|exp)\b",
    ]
    month_patterns = [
        rf"(?<!\d)(\d{{1,3}}(?:\.\d+)?)(?:\+)?\s*(?:months?|mths?|mos?)\s+(?:of\s+)?{qualifier}(?:experience|exp)\b",
        rf"\b{qualifier}(?:experience|exp)\s*(?:of\s*)?[:=-]?\s*(\d{{1,3}}(?:\.\d+)?)(?:\+)?\s*(?:months?|mths?|mos?)\b",
    ]
    for pattern in year_patterns:
        for m in re.finditer(pattern, text, re.I):
            try:
                value = float(m.group(1))
            except Exception:
                continue
            if 0 <= value <= 60:
                vals.append(value)
    for pattern in month_patterns:
        for m in re.finditer(pattern, text, re.I):
            try:
                months = float(m.group(1))
            except Exception:
                continue
            if 0 <= months <= 720:
                vals.append(round(months / 12.0, 2))
    return max(vals) if vals else None


def _spider_flatten(value, depth=0):
    if depth > 5 or value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, list):
        out = []
        for x in value[:80]:
            out.extend(_spider_flatten(x, depth + 1))
        return out
    if isinstance(value, dict):
        out = []
        for k, v in list(value.items())[:120]:
            # Internal discovery/scoring metadata must never become candidate evidence.
            if str(k).startswith("_spider"):
                continue
            out.append(str(k))
            out.extend(_spider_flatten(v, depth + 1))
        return out
    return [str(value)]


def _spider_candidate_blob(candidate):
    """Build candidate evidence with the latest resume first.

    Candidate detail objects can be large.  Resume text used to be appended after
    the detail JSON and then lost to the 20,000-character evidence ceiling, which
    could leave every result on the same 10% discovery floor.  Reserve the front of
    the blob for the latest extracted CV and fill the remaining space with profile
    fields, excluding the duplicate ``resumeText`` key from the second pass.
    """
    resume_text = ""
    profile_value = candidate
    if isinstance(candidate, dict):
        resume_text = re.sub(r"\s+", " ", str(candidate.get("resumeText") or "")).strip()[:14000]
        if "resumeText" in candidate:
            profile_value = {k: v for k, v in candidate.items() if k != "resumeText"}
    profile_text = re.sub(r"\s+", " ", " ".join(_spider_flatten(profile_value))).strip()
    if resume_text:
        remaining = max(0, 20000 - len(resume_text) - 1)
        return (resume_text + " " + profile_text[:remaining]).strip()
    return profile_text[:20000]


def _spider_pick_field_text(candidate, key_patterns):
    """Extract text from likely matching fields without assuming one JobAdder schema."""
    pats = [p.lower() for p in key_patterns]
    found = []

    def walk(obj, depth=0):
        if depth > 5 or obj is None:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                lk = str(k).lower()
                if any(p in lk for p in pats):
                    found.extend(_spider_flatten(v, depth + 1))
                walk(v, depth + 1)
        elif isinstance(obj, list):
            for x in obj[:80]:
                walk(x, depth + 1)

    walk(candidate)
    return re.sub(r"\s+", " ", " ".join(found)).strip()[:6000]


def _spider_has_any(text, terms):
    return any(_spider_term_matches(text, term) for term in (terms or []))


def _spider_status_aliases(status):
    target = _spider_status_target(status)
    return {
        "citizen": ["citizen", "citizenship", "local citizen", "malaysian citizen", "singapore citizen"],
        "permanent_resident": ["permanent resident", "permanent residency", "pr status", "pr holder"],
        "no_visa_required": ["no visa required", "no sponsorship required", "unrestricted work rights", "full working rights", "right to work without sponsorship"],
        "work_visa": ["work visa", "employment pass", "s pass", "work permit", "sponsorship required", "requires sponsorship", "visa required"],
    }.get(target, [str(status or "").strip()] if str(status or "").strip() else [])


def _spider_status_target(status):
    s = re.sub(r"\s+", " ", str(status or "")).strip().lower()
    if not s or s == "any":
        return ""
    if "citizen" in s:
        return "citizen"
    if "permanent" in s or s == "pr":
        return "permanent_resident"
    if "no visa" in s or "no sponsorship" in s:
        return "no_visa_required"
    if "work visa" in s or "visa required" in s or "employment pass" in s:
        return "work_visa"
    return s


def _spider_residential_status_text(candidate):
    """Read only fields that are actually labelled as residency/work-rights data."""
    found = []
    direct_markers = (
        "residentialstatus", "residencystatus", "residencestatus", "residency", "visastatus", "righttowork", "workright",
        "workrights", "citizenship", "immigrationstatus", "workauthorization", "workauthorisation",
    )
    label_markers = (
        "residential status", "residence status", "residency", "visa status", "right to work", "work right",
        "work rights", "citizenship", "immigration status", "work authorization", "work authorisation",
    )
    label_keys = {"label", "name", "title", "fieldname", "customfieldname", "question", "displayname"}
    value_keys = {"value", "values", "text", "option", "options", "selected", "selectedvalue", "answer"}

    def add(value, depth):
        for part in _spider_flatten(value, depth + 1):
            part = re.sub(r"\s+", " ", str(part or "")).strip()
            if part:
                found.append(part)

    def walk(obj, depth=0):
        if obj is None or depth > 7:
            return
        if isinstance(obj, dict):
            normalized = {re.sub(r"[^a-z0-9]", "", str(k).lower()): (k, v) for k, v in obj.items()}
            for norm, (key, value) in normalized.items():
                if any(marker in norm for marker in direct_markers):
                    add(value, depth)
            label_text = " ".join(
                str(v or "") for norm, (k, v) in normalized.items()
                if norm in label_keys and not isinstance(v, (dict, list))
            ).lower()
            if label_text and any(marker in label_text for marker in label_markers):
                for norm, (key, value) in normalized.items():
                    if norm in value_keys:
                        add(value, depth)
            for value in obj.values():
                walk(value, depth + 1)
        elif isinstance(obj, list):
            for value in obj[:100]:
                walk(value, depth + 1)

    walk(candidate)
    # Stable de-duplication keeps diagnostics short.
    seen, unique = set(), []
    for part in found:
        key = part.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(part)
    return " | ".join(unique)[:4000]


def _spider_residential_classes(text):
    source = re.sub(r"\s+", " ", str(text or "")).strip()
    low = source.lower()
    classes = set()
    exact_values = {re.sub(r"[^a-z0-9]+", " ", x).strip() for x in re.split(r"[|,;/\n\r]+", low) if x.strip()}
    if _spider_has_any(source, ["local citizen", "malaysian citizen", "singapore citizen", "citizenship", "citizen"]):
        classes.add("citizen")
    if _spider_has_any(source, ["permanent resident", "permanent residency", "pr status", "pr holder"]) or "pr" in exact_values:
        classes.add("permanent_resident")
    if _spider_has_any(source, ["no visa required", "no sponsorship required", "unrestricted work rights", "full working rights", "right to work without sponsorship"]):
        classes.add("no_visa_required")
    if _spider_has_any(source, ["work visa", "employment pass", "s pass", "work permit", "sponsorship required", "requires sponsorship", "visa required"]) or exact_values.intersection({"ep", "sp", "s pass", "employment pass"}):
        classes.add("work_visa")
    return classes


def _spider_work_setup_aliases(work_setup):
    s = str(work_setup or "").strip().lower()
    if not s or s == "any":
        return []
    if "remote" in s:
        return ["remote", "work from home", "wfh"]
    if "hybrid" in s:
        return ["hybrid"]
    if "site" in s or "office" in s:
        return ["on-site", "onsite", "office based", "office-based"]
    return [s]


def _spider_candidate_id(candidate):
    if not isinstance(candidate, dict):
        return ""
    for key in ["candidateId", "candidateID", "candidate_id", "id", "candidate", "entityId"]:
        val = candidate.get(key)
        if isinstance(val, dict):
            for sub in ["candidateId", "id", "value"]:
                if val.get(sub):
                    return str(val.get(sub))
        elif val:
            return str(val)
    return ""


_SPIDER_COUNTRY_DEFINITIONS = {
    "malaysia": {
        "names": ["malaysia"], "codes": ["MY", "MYS"],
        "places": [
            "kuala lumpur", "labuan", "putrajaya", "johor", "kedah", "kelantan", "melaka", "malacca",
            "negeri sembilan", "pahang", "penang", "pulau pinang", "perak", "perlis", "sabah", "sarawak",
            "selangor", "terengganu", "johor bahru", "iskandar puteri", "alor setar", "sungai petani",
            "kota bharu", "seremban", "nilai", "kuantan", "george town", "georgetown", "butterworth",
            "bayan lepas", "ipoh", "kangar", "kota kinabalu", "sandakan", "tawau", "kuching", "miri",
            "sibu", "bintulu", "shah alam", "petaling jaya", "subang jaya", "klang", "cyberjaya",
            "kajang", "bangi", "kuala terengganu",
        ],
    },
    "singapore": {"names": ["singapore"], "codes": ["SG", "SGP"], "places": ["singapore"]},
    "indonesia": {
        "names": ["indonesia"], "codes": ["ID", "IDN"],
        "places": ["jakarta", "bandung", "surabaya", "medan", "semarang", "yogyakarta", "jogjakarta", "bali", "denpasar", "bekasi", "tangerang"],
    },
    "philippines": {
        "names": ["philippines", "the philippines"], "codes": ["PH", "PHL"],
        "places": ["manila", "metro manila", "makati", "taguig", "quezon city", "pasig", "cebu", "davao", "calabarzon"],
    },
    "brunei": {"names": ["brunei", "brunei darussalam"], "codes": ["BN", "BRN"], "places": ["bandar seri begawan", "kuala belait", "seria"]},
    "india": {
        "names": ["india"], "codes": ["IN", "IND"],
        "places": ["bengaluru", "bangalore", "mumbai", "new delhi", "delhi", "hyderabad", "pune", "chennai", "kolkata", "gurugram", "gurgaon", "noida"],
    },
    "thailand": {"names": ["thailand"], "codes": ["TH", "THA"], "places": ["bangkok", "chiang mai", "phuket", "chonburi"]},
    "vietnam": {"names": ["vietnam", "viet nam"], "codes": ["VN", "VNM"], "places": ["ho chi minh city", "saigon", "hanoi", "da nang"]},
    "cambodia": {"names": ["cambodia"], "codes": ["KH", "KHM"], "places": ["phnom penh", "siem reap"]},
    "laos": {"names": ["laos", "lao pdr"], "codes": ["LA", "LAO"], "places": ["vientiane"]},
    "myanmar": {"names": ["myanmar", "burma"], "codes": ["MM", "MMR"], "places": ["yangon", "mandalay"]},
    "china": {"names": ["china", "mainland china"], "codes": ["CN", "CHN"], "places": ["beijing", "shanghai", "shenzhen", "guangzhou", "hangzhou"]},
    "hong kong": {"names": ["hong kong", "hong kong sar"], "codes": ["HK", "HKG"], "places": ["hong kong"]},
    "taiwan": {"names": ["taiwan"], "codes": ["TW", "TWN"], "places": ["taipei", "kaohsiung", "taichung"]},
    "japan": {"names": ["japan"], "codes": ["JP", "JPN"], "places": ["tokyo", "osaka", "yokohama", "nagoya"]},
    "south korea": {"names": ["south korea", "korea, republic of", "republic of korea"], "codes": ["KR", "KOR"], "places": ["seoul", "busan", "incheon"]},
    "australia": {"names": ["australia"], "codes": ["AU", "AUS"], "places": ["sydney", "melbourne", "brisbane", "perth", "adelaide", "canberra"]},
    "new zealand": {"names": ["new zealand"], "codes": ["NZ", "NZL"], "places": ["auckland", "wellington", "christchurch"]},
    "united arab emirates": {"names": ["united arab emirates", "uae"], "codes": ["AE", "ARE"], "places": ["dubai", "abu dhabi", "sharjah"]},
    "united kingdom": {"names": ["united kingdom", "uk", "great britain"], "codes": ["GB", "GBR"], "places": ["london", "manchester", "birmingham", "edinburgh"]},
    "united states": {"names": ["united states", "united states of america", "usa", "u.s.a."], "codes": ["US", "USA"], "places": ["new york", "san francisco", "los angeles", "seattle", "chicago", "boston"]},
}

_SPIDER_COUNTRY_NAME_LOOKUP = {}
_SPIDER_COUNTRY_CODE_LOOKUP = {}
for _spider_country_key, _spider_country_def in _SPIDER_COUNTRY_DEFINITIONS.items():
    _SPIDER_COUNTRY_NAME_LOOKUP[_spider_country_key] = _spider_country_key
    for _spider_country_name in _spider_country_def.get("names", []):
        _SPIDER_COUNTRY_NAME_LOOKUP[str(_spider_country_name).strip().lower()] = _spider_country_key
    for _spider_country_code in _spider_country_def.get("codes", []):
        _SPIDER_COUNTRY_CODE_LOOKUP[str(_spider_country_code).strip().upper()] = _spider_country_key






def _spider_country_profile(country):
    raw = re.sub(r"\s+", " ", str(country or "")).strip()
    low = raw.lower()
    if not low or low == "any":
        return None
    canonical = _SPIDER_COUNTRY_NAME_LOOKUP.get(low) or _SPIDER_COUNTRY_CODE_LOOKUP.get(raw.upper())
    if canonical:
        data = _SPIDER_COUNTRY_DEFINITIONS[canonical]
        return {
            "canonical": canonical,
            "names": list(data.get("names") or [canonical]),
            "codes": {str(x).upper() for x in data.get("codes", [])},
            "places": list(data.get("places") or []),
        }
    return {"canonical": low, "names": [raw], "codes": set(), "places": []}


def _spider_country_aliases(country):
    profile = _spider_country_profile(country)
    if not profile:
        return []
    return list(profile.get("names") or []) + list(profile.get("places") or [])


def _spider_location_identity(candidate):
    """Return explicit country codes/names and broader city/state/address text."""
    codes, country_values, location_values = set(), [], []
    code_keys = {"countrycode", "countryiso", "countryiso2", "countryiso3", "isocountrycode", "countryidcode"}
    country_keys = {"country", "countryname"}
    location_keys = {"location", "address", "city", "state", "province", "suburb", "region", "town"}

    def add_text(bucket, value, depth):
        for part in _spider_flatten(value, depth + 1):
            part = re.sub(r"\s+", " ", str(part or "")).strip()
            if part:
                bucket.append(part)

    def add_codes(value, depth):
        for part in _spider_flatten(value, depth + 1):
            for token in re.findall(r"(?<![A-Za-z])([A-Za-z]{2,3})(?![A-Za-z])", str(part or "")):
                up = token.upper()
                if up in _SPIDER_COUNTRY_CODE_LOOKUP:
                    codes.add(up)

    def walk(obj, depth=0):
        if obj is None or depth > 6:
            return
        if isinstance(obj, dict):
            for key, value in list(obj.items())[:160]:
                norm = re.sub(r"[^a-z0-9]", "", str(key).lower())
                if norm in code_keys:
                    add_codes(value, depth)
                if norm in country_keys:
                    add_text(country_values, value, depth)
                    add_codes(value, depth)
                if norm in location_keys:
                    add_text(location_values, value, depth)
                walk(value, depth + 1)
        elif isinstance(obj, list):
            for value in obj[:100]:
                walk(value, depth + 1)

    walk(candidate)
    return codes, re.sub(r"\s+", " ", " ".join(country_values)).strip()[:3000], re.sub(r"\s+", " ", " ".join(location_values)).strip()[:6000]


def _spider_country_match(candidate, country):
    """Return (match|mismatch|unknown, evidence) using codes before place inference."""
    target = _spider_country_profile(country)
    if not target:
        return "match", ""
    codes, explicit_country, location_text = _spider_location_identity(candidate)
    target_codes = set(target.get("codes") or set())
    if codes and target_codes.intersection(codes):
        return "match", "country code " + sorted(target_codes.intersection(codes))[0]
    recognized_code_countries = {_SPIDER_COUNTRY_CODE_LOOKUP[c] for c in codes if c in _SPIDER_COUNTRY_CODE_LOOKUP}
    if recognized_code_countries and target.get("canonical") not in recognized_code_countries:
        return "mismatch", "country code " + ", ".join(sorted(codes))

    # Explicit country names outrank city/state inference.
    if _spider_has_any(explicit_country, target.get("names")):
        return "match", explicit_country[:120]
    for canonical, definition in _SPIDER_COUNTRY_DEFINITIONS.items():
        if canonical == target.get("canonical"):
            continue
        if _spider_has_any(explicit_country, definition.get("names")):
            return "mismatch", explicit_country[:120]

    if _spider_has_any(location_text, target.get("names")):
        return "match", location_text[:120]
    for canonical, definition in _SPIDER_COUNTRY_DEFINITIONS.items():
        if canonical == target.get("canonical"):
            continue
        if _spider_has_any(location_text, definition.get("names")):
            return "mismatch", location_text[:120]

    if _spider_has_any(location_text, target.get("places")):
        return "match", location_text[:120]
    for canonical, definition in _SPIDER_COUNTRY_DEFINITIONS.items():
        if canonical == target.get("canonical"):
            continue
        if _spider_has_any(location_text, definition.get("places")):
            return "mismatch", location_text[:120]
    return "unknown", (explicit_country or location_text)[:120]


# ---------------------------------------------------------------------------
# Candidate search key, payload parsing, and keyword marking
# ---------------------------------------------------------------------------

def _spider_candidate_search_key(candidate):
    """Stable key for set algebra and de-duplication across JobAdder keyword probes."""
    cid = _spider_candidate_id(candidate)
    if cid:
        return "id:" + str(cid)
    if isinstance(candidate, dict):
        email = str(candidate.get("email") or candidate.get("emailAddress") or "").strip().lower()
        if email:
            return "email:" + email
        name = str(candidate.get("name") or candidate.get("fullName") or "").strip().lower()
        if name:
            return "name:" + name
    return "raw:" + hashlib.sha1(json.dumps(candidate, sort_keys=True, default=str).encode("utf-8", errors="ignore")).hexdigest()


def _spider_parse_candidate_items(payload):
    if isinstance(payload, dict):
        data_obj = payload.get("data")
        items = payload.get("items") or payload.get("candidates") or (data_obj.get("items") if isinstance(data_obj, dict) else None) or []
        total = None
        # Preserve an explicit totalCount=0 instead of losing it through truthiness.
        for key in ("totalCount", "total", "count"):
            if key in payload and payload.get(key) is not None:
                total = payload.get(key)
                break
        if total is None and isinstance(data_obj, dict):
            for key in ("totalCount", "total", "count"):
                if key in data_obj and data_obj.get(key) is not None:
                    total = data_obj.get(key)
                    break
    elif isinstance(payload, list):
        items, total = payload, len(payload)
    else:
        items, total = [], 0
    return (items if isinstance(items, list) else []), total


def _spider_mark_plain_keyword_candidates(items, query_text, fallback_rule="", fallback_negative_terms=None):
    query_terms = _spider_terms_for_fit(query_text, 24)
    negative_terms = list(fallback_negative_terms or [])
    marked = []
    for item in items or []:
        out = dict(item) if isinstance(item, dict) else {"value": item}
        out["_spiderSearchTerms"] = list(query_terms)
        if fallback_rule:
            out["_spiderBooleanFallback"] = True
            out["_spiderOriginalBooleanRule"] = str(fallback_rule)[:1500]
            out["_spiderBooleanNegativeTerms"] = negative_terms[:24]
        marked.append(out)
    return marked, query_terms
