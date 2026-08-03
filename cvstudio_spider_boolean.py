"""Spider (AI Crawler) boolean and keyword matching helpers (Phase 7B-6e).

Behaviour-preserving extraction of the stateless candidate-matching logic from
the legacy web shell: boolean rule tokenisation, positive/negative term
extraction, boolean expression evaluation, discovery-keyword and term-coverage
matching, and preview text cleaning.

Pure functions of their inputs - no Flask, no globals, no network, no JobAdder
or provider access. This module never imports ``app``.
"""

import re


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
