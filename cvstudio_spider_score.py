"""Spider (AI Crawler) JD-scoring and candidate-fit helpers.

Behaviour-preserving extraction of the pure JD parsing and candidate scoring
logic from the legacy web shell (Phase 7B): job-description heading/section
parsing and relevance-term extraction, discovery/context fit-term handling,
weighted term coverage, the candidate fit-percentage and overall item score,
and JobAdder option-payload flattening.

Pure functions of their inputs - no Flask, no globals, no network, no JobAdder
or provider access. Depends only on the stateless field helpers already
extracted into ``cvstudio_spider_boolean``. This module never imports ``app``.
"""

import re

from cvstudio_spider_boolean import (
    _SPIDER_COUNTRY_DEFINITIONS,
    _spider_boolean_positive_terms,
    _spider_candidate_blob,
    _spider_country_match,
    _spider_discovery_keyword_match,
    _spider_hit_terms,
    _spider_residential_classes,
    _spider_residential_status_text,
    _spider_status_target,
    _spider_term_coverage,
    _spider_terms,
    _spider_visible_years,
    _spider_years_bounds,
)


_SPIDER_JD_HEADING_PREFIX_RE = re.compile(
    r"^\s*(?:"
    r"\d{1,3}(?:\.\d{1,3})+|"        # 2.1 / 2.4.3
    r"\d{1,3}[.)]|"                   # 2. / 2)
    r"[A-Za-z][.)]|"                   # A. / b)
    r"[IVXLCDM]{1,8}[.)]"              # I. / IV)
    r")\s*",
    re.I,
)


def _spider_strip_jd_heading_prefix(value):
    """Remove common corporate outline numbering without touching content years."""
    return _SPIDER_JD_HEADING_PREFIX_RE.sub("", str(value or "")).strip()


def _spider_jd_heading_section(raw_line):
    """Classify a JD heading and return ``(section, remainder)``.

    ``section`` is one of ``core``, ``nice`` or ``noise``.  Corporate numbering
    such as ``2.2 Primary Responsibilities`` is removed before matching, while
    ordinary sentences remain untouched.  Exact heading matching prevents a
    sentence such as "experience with AWS" from changing the active section.
    """
    line = re.sub(r"^[\s#>*•\-–—]+", "", str(raw_line or "")).strip()
    line = _spider_strip_jd_heading_prefix(line)
    if not line:
        return None, ""

    def normalise(value):
        value = str(value or "").casefold().replace("&", " and ")
        value = value.replace("’", "'").replace("‘", "'").replace("`", "'")
        value = value.replace("'", "")
        value = re.sub(r"[^a-z0-9+]+", " ", value)
        return re.sub(r"\s+", " ", value).strip()

    core_headings = {
        "job purpose", "role purpose", "position purpose", "purpose of the role",
        "your role", "the role", "role summary", "job summary", "position summary",
        "your mission", "role mission", "the position", "position description",
        "what you will do", "what youll do", "what you do", "your responsibilities",
        "what you will be doing", "what youll be doing", "what you would do",
        "what you will be responsible for", "what youll be responsible for",
        "key responsibilities", "primary responsibilities", "main responsibilities",
        "responsibilities", "role responsibilities", "job responsibilities", "duties",
        "responsibilities and duties", "responsibilities and accountabilities",
        "responsibilities duties", "key responsibilities and duties",
        "key responsibilities and deliverables", "responsibilities and deliverables",
        "key duties", "job duties", "accountabilities", "key accountabilities",
        "scope of work", "job scope", "role scope", "day to day", "your impact", "key deliverables",
        "key tasks", "what you need to succeed", "what you need", "what we need",
        "what we are looking for", "what were looking for", "requirements",
        "job requirements", "role requirements", "candidate requirements",
        "key requirements", "core requirements", "minimum requirements",
        "must have", "must haves", "essential requirements", "essential skills",
        "essential criteria", "selection criteria", "required criteria",
        "required skills", "required experience", "skills and experience",
        "skills required", "experience required", "required qualifications",
        "minimum qualifications", "knowledge skills and abilities", "candidate specification",
        "person specification", "technical skills", "functional skills",
        "key skills and experience", "qualifications and skills", "qualifications skills",
        "experience and skills", "candidate profile", "who you are", "about you",
        "qualifications", "capabilities", "competencies", "core competencies",
        "details regarding the types of experience required", "types of experience required",
        "education certification and designation requirements",
        "technical requirements", "functional requirements",
        "tech stack", "technology stack", "tech stack tools", "technology stack tools",
        "tools", "technologies", "platforms", "systems", "tools and technologies",
        "technology and tools", "technical stack",
    }
    nice_headings = {
        "nice to have", "nice to haves", "good to have", "good to haves",
        "preferred", "preferred skills", "preferred experience", "preferred qualifications",
        "preferred qualifications and experience", "preferred experience and skills",
        "preferred desirable", "preferred and desirable", "desirable", "desirable skills",
        "desirable criteria", "desired skills", "desired qualifications", "desired experience",
        "bonus", "bonus points", "added advantage", "an advantage", "advantage", "advantageous", "additional skills",
        "nice if you have", "it would be a plus", "a plus", "plus",
        "optional", "optional requirements",
    }
    noise_headings = {
        "rbc job mandate", "job mandate", "mandate template", "job details", "reports to details",
        "job information", "job information for use by position evaluation team only",
        "time allocation", "time allocation percent", "level of responsibility and decision",
        "managerial scope", "financial impact", "key relationships", "key contact and purpose of relationship",
        "required in canada only for pay equity purposes", "working conditions", "physical effort", "mental effort",
        "about our client", "about the client", "about the company", "company overview",
        "about us", "who we are", "our client", "client overview", "company profile", "company background",
        "about the organisation", "about the organization", "about the role",
        "role overview", "job overview", "overview", "purpose", "mandate template",
        "location", "work arrangement", "working arrangement", "work mode", "work setup",
        "salary", "salary and benefits", "compensation", "remuneration", "benefits",
        "perks", "why join us", "why join", "what we offer", "culture", "our culture",
        "alternative job titles", "alternative titles", "equal opportunity",
        "diversity and inclusion", "how to apply", "application process", "contact",
        "company information", "confidential", "for candidate use only",
    }

    prefix = line
    remainder = ""
    m = re.match(r"^(.{1,100}?)(?:\s*[:：]\s*|\s+[\-–—]\s+)(.+)$", line)
    if m:
        prefix, remainder = m.group(1).strip(), m.group(2).strip()
    key = normalise(prefix)
    if key in core_headings:
        return "core", remainder
    if key in nice_headings:
        return "nice", remainder
    if key in noise_headings or re.fullmatch(r"page\s+\d+\s+of\s+\d+", key or ""):
        return "noise", ""

    key = normalise(line.rstrip(":：-–— "))
    if key in core_headings:
        return "core", ""
    if key in nice_headings:
        return "nice", ""
    if key in noise_headings or re.fullmatch(r"page\s+\d+\s+of\s+\d+", key or ""):
        return "noise", ""
    return None, line

def _spider_jd_scoring_lines(jd_text):
    """Return section-aware JD lines for fit scoring.

    When a JD contains recognised responsibility/requirement/tech-stack or
    nice-to-have headings, only those sections are scored.  Company marketing,
    location/work-mode metadata, benefits, culture, legal text and footers are
    ignored.  Unstructured JDs retain a conservative fallback so keyword-only
    or plain-paragraph job descriptions continue to work.
    """
    text = re.sub(r"[\x00-\x09\x0b\x0c\x0e-\x1f\x7f]", " ", str(jd_text or ""))
    core, nice, fallback = [], [], []
    current = None
    target_heading_seen = False
    metadata_line_re = re.compile(
        r"^(?:job\s+title|evaluated\s+position\s+level|position\s+level|platform|city\s*,?\s*country|transit|incumbent\s+name|signature|date|job\s+id|mandate\s+effective\s+date|location|work(?:ing)?\s*(?:mode|arrangement|setup)?|city|state|country|salary|compensation)\s*[:|=-]",
        re.I,
    )
    footer_re = re.compile(
        r"^(?:rbc\s+canada\s+only(?:\s+\w+\s+\d{4})?|hyppies\s*\||confidential(?:\s*\||$)|for candidate use only|page\s+\d+\s+of\s+\d+|\d{1,2}/\d{1,2}/\d{4})",
        re.I,
    )
    def looks_like_unknown_heading(value):
        value = re.sub(r"\s+", " ", str(value or "")).strip().rstrip(":：-–— ")
        if not value or len(value) > 90 or len(value.split()) > 10:
            return False
        letters = [ch for ch in value if ch.isalpha()]
        if not letters:
            return False
        upper_ratio = sum(ch.isupper() for ch in letters) / float(len(letters))
        titleish = value == value.title()
        return upper_ratio >= 0.75 or titleish

    for original in re.split(r"[\r\n]+", text):
        raw = re.sub(r"^[\s•*]+", "", original).strip()
        raw = _spider_strip_jd_heading_prefix(raw)
        if not raw:
            continue
        section, remainder = _spider_jd_heading_section(raw)
        if section is not None:
            current = section
            if section in {"core", "nice"}:
                target_heading_seen = True
                if remainder:
                    (core if section == "core" else nice).append(remainder)
            continue
        # A short unknown corporate heading must end an earlier About/Benefits
        # block. Otherwise a valid section such as "YOUR ROLE" remains trapped
        # inside noise and the entire unstructured fallback can disappear.
        if current == "noise" and looks_like_unknown_heading(raw):
            current = None
            continue
        if metadata_line_re.match(raw) or footer_re.match(raw):
            continue
        # Header strips such as "Kuala Lumpur | On-site | Fintech" are context,
        # not capability evidence.  Keep only fragments that are not pure
        # location/work-arrangement context for the unstructured fallback.
        fallback_line = raw
        if "|" in fallback_line:
            pieces = [part.strip() for part in fallback_line.split("|") if part.strip()]
            pieces = [part for part in pieces if not _spider_context_only_fit_term(part, {})]
            fallback_line = " | ".join(pieces).strip()
        if fallback_line and current != "noise":
            fallback.append(fallback_line)
        if current == "core":
            core.append(raw)
        elif current == "nice":
            nice.append(raw)
        # Content inside an explicitly noisy section is deliberately ignored.

    def dedupe(lines):
        seen, out = set(), []
        for line in lines:
            line = re.sub(r"\s+", " ", str(line or "")).strip()
            key = line.casefold()
            if line and key not in seen:
                seen.add(key)
                out.append(line)
        return out

    if target_heading_seen:
        return {"sectioned": True, "core": dedupe(core), "nice": dedupe(nice), "fallback": []}
    return {"sectioned": False, "core": dedupe(fallback), "nice": [], "fallback": dedupe(fallback)}


def _spider_jd_relevance_terms(jd_text, max_terms=34):
    """Extract balanced, section-focused JD terms for fit scoring.

    Terms are collected per responsibility/requirement line and selected in a
    balanced pass, so the first long bullet cannot consume the whole budget.
    Explicit tools, regulatory frameworks and professional certifications rank
    above generic noun phrases.  Language, degree and corporate-template noise
    remain excluded by policy.
    """
    groups = _spider_jd_scoring_lines(jd_text)
    if not groups.get("core") and not groups.get("nice"):
        return []

    language_line_re = re.compile(
        r"\b(language|languages|linguistic|fluent|fluency|spoken|written|bilingual|multilingual|"
        r"english|mandarin|chinese|cantonese|hokkien|hakka|teochew|malay|bahasa|japanese|korean|thai|"
        r"vietnamese|tagalog|filipino|indonesian)\b",
        re.I,
    )
    education_line_re = re.compile(
        r"\b(degree|diploma|bachelor|master|phd|doctorate|university|college|education|academic|"
        r"cgpa|gpa|spm|stpm)\b",
        re.I,
    )
    certification_re = re.compile(r"\b(?:ACA|CIMA|ACCA|CFA|CPA|FRM|PMP|CISSP|CISM|CISA)\b", re.I)
    ignored_exact = {
        "rbc", "gg", "tbd", "id", "it", "job id", "position level", "evaluated position level",
        "incumbent name", "signature date", "required", "preferred", "other", "details",
    }
    generic = {
        "responsibilities", "requirements", "experience", "years experience", "candidate", "role", "skills",
        "good communication", "strong communication", "team player", "stakeholders", "fast paced",
        "ability to", "responsible for", "knowledge of", "familiar with", "hands on", "hands-on",
        "finance qualification", "required", "preferred",
    }
    stop_tokens = {
        "and", "or", "the", "for", "with", "from", "into", "this", "that", "will", "must", "have", "has",
        "able", "work", "working", "team", "teams", "role", "candidate", "experience", "years", "year", "strong",
        "good", "excellent", "skills", "knowledge", "understanding", "responsible", "required", "requirement",
        "to", "of", "in", "via", "through", "as", "a", "an", "on", "such", "including", "includes",
        "provide", "provides", "provided", "using", "use", "used", "similar", "other", "applications", "rbc",
    }
    action_noise = {
        "architect", "implement", "sustain", "manage", "ensure", "enforce", "optimise", "optimize",
        "act", "offer", "offering", "partner", "align", "support", "supporting", "drive", "deliver",
        "maintain", "develop", "perform", "oversee", "lead", "collaborate", "coordinate", "conduct",
        "review", "validate", "prepare", "assign", "monitor", "supervise", "identify", "escalate",
        "proven", "solid", "regular", "internal", "cross-functional", "organisational", "organizational",
    }
    domain_cues = {
        "database", "databases", "security", "query", "performance", "cloud", "backup", "snapshot", "snapshots",
        "recovery", "access", "cost", "storage", "networking", "availability", "monitoring", "migration", "migrations",
        "architecture", "integration", "development", "implementation", "reporting", "regulatory", "risk", "compliance",
        "testing", "troubleshooting", "governance", "automation", "data", "analytics", "leadership", "stakeholder",
        "project", "product", "sales", "marketing", "finance", "financial", "accounting", "audit", "payroll",
        "recruitment", "operations", "strategy", "controls", "patching", "rightsizing", "encryption", "relational",
        "process", "processes", "standards", "administration", "tuning", "capital", "leverage", "exposures",
        "securities", "derivatives", "treasury", "reconciliation", "documentation", "workload", "coaching", "mentoring",
    }
    recognised_singletons = {
        "sap", "oracle", "netsuite", "salesforce", "python", "java", "sql", "azure", "aws", "gcp", "kubernetes",
        "docker", "linux", "powerbi", "tableau", "etl", "airflow", "spark", "hadoop", "workday", "servicenow",
        "jira", "swift", "iso20022", "reconciliation", "payroll", "treasury", "abap", "fico", "bpc", "bw", "hana",
        "devops", "recruitment", "collections", "mysql", "postgresql", "rds", "vpc", "subnets", "ec2", "encryption",
        "patching", "backup", "snapshots", "monitoring", "axiom", "ifr", "sft", "derivatives", "airb", "firb",
        "ifrs9", "rentas", "excel", "powerpoint", "word",
    }
    canonical_patterns = [
        (r"\bhighly\s+available\b|\bhigh\s+availability\b", "high availability"),
        (r"\bquery\s+tuning\b", "query tuning"),
        (r"\bperformance\s+tuning\b", "performance tuning"),
        (r"\bdatabase\s+security\b", "database security"),
        (r"\baccess\s+controls?\b", "access controls"),
        (r"\bcloud\s+monitoring\b", "cloud monitoring"),
        (r"\bbackup(?:\s*/\s*|\s+and\s+)snapshot(?:s)?(?:\s+management)?\b", "backup and snapshot management"),
        (r"\bsnapshot(?:s)?\s+management\b", "snapshot management"),
        (r"\bautomated\s+recovery\b", "automated recovery"),
        (r"\bdisaster\s+recovery\b", "disaster recovery"),
        (r"\bcloud\s+networking\b", "cloud networking"),
        (r"\bsecurity\s+groups?\b", "security groups"),
        (r"\bstorage\s+management\b", "storage management"),
        (r"\bright[- ]?sizing(?:\s+instances?)?\b", "rightsizing instances"),
        (r"\bcost[- ]saving\b|\bcost\s+optim(?:isation|ization)\b|\boptim(?:ise|ize)\s+cloud\s+expenditure\b", "cloud cost optimization"),
        (r"\brelational\s+databases?\b", "relational databases"),
        (r"\bdatabase\s+administration\b", "database administration"),
        (r"\bdatabase\s+guidance\b", "database guidance"),
        (r"\bdatabase\s+processes?\b", "database processes"),
        (r"\bec2\s*(?:-|to)\s*rds\s+migrations?\b", "EC2-to-RDS migration"),
        (r"\bp2v\s+migrations?\b", "P2V migration"),
        (r"\bregulatory\s+report(?:ing|s)\b", "regulatory reporting"),
        (r"\bcapital\s+markets?\b", "capital markets"),
        (r"\bfinancial\s+services?\b", "financial services"),
        (r"\blarge\s+exposures?\b", "large exposures"),
        (r"\bconcentration\s+risk\b", "concentration risk"),
        (r"\bcapital\s+and\s+leverage\b|\bcapital,?\s+leverage\b", "capital and leverage monitoring"),
        (r"\bcontrols?\s+and\s+procedures?\b", "controls and procedures"),
        (r"\baudit\s+documentation\b", "audit documentation"),
        (r"\bcoaching\s+and\s+mentoring\b", "coaching and mentoring"),
        (r"\bworkload\s+allocation\b", "workload allocation"),
        (r"\bmanagement\s+analytical\s+packages?\b", "management analytical packages"),
        (r"\bperformance\s+evaluations?\b", "performance evaluations"),
        (r"\baxiom\b", "Axiom"),
        (r"\bbasel\s+iii\b", "Basel III"),
        (r"\bcrd\s+v(?:\s*(?:and|&|/)\s*vi)?\b|\bcrd\s+vi\b", "CRD V/VI"),
        (r"\bsecurities\b", "securities"),
        (r"\bsft(?:['’]s|s)?\b", "SFT"),
        (r"\bderivatives?\b", "derivatives"),
        (r"\bmicrosoft\s+office\b", "Microsoft Office"),
        (r"\brisk\s+mitigation\b", "risk mitigation"),
        (r"\bprocess\s+improvement\b", "process improvement"),
        (r"\banalytical\s+thinking\b", "analytical thinking"),
    ]

    def clean_term(term):
        term = re.sub(r"^[\s\-•*:/]+", "", str(term or ""))
        term = re.sub(r"\s+", " ", term).strip().strip(".,:;()[]{}'\"")
        low = term.casefold()
        if len(term) < 2 or len(term) > 70 or low in generic or low in ignored_exact:
            return ""
        if re.fullmatch(r"gg\d{1,3}", low) or re.fullmatch(r"[ivxlcdm]+", low):
            return ""
        if _spider_ignored_fit_term(term):
            return ""
        return term

    def line_candidates(raw):
        raw = re.sub(r"^[\s\-•*]+", "", str(raw or "")).strip()
        raw = _spider_strip_jd_heading_prefix(raw)
        if not raw:
            return []
        found = []
        seen = set()

        def add(term, priority):
            term = clean_term(term)
            key = term.casefold() if term else ""
            if not term or key in seen:
                return
            seen.add(key)
            found.append((int(priority), len(found), term))

        # Mixed education/certification rows keep professional designations only.
        # Academic subjects (Finance, Accounting, Computer Science, etc.) are
        # not job-fit evidence merely because they share a row with ACCA/CFA.
        certs = certification_re.findall(raw)
        if education_line_re.search(raw):
            for cert in certs:
                add(cert.upper(), 100)
            # Corporate table extraction can place an education clause and a
            # separate technical requirement on one physical line. Remove the
            # education-bearing clauses but retain distinct semicolon, pipe or
            # sentence-delimited technical clauses instead of dropping the
            # whole row.
            clauses = [part.strip() for part in re.split(r"[;|]|(?<=[.!?])\s+", raw) if part.strip()]
            technical_clauses = [part for part in clauses if not education_line_re.search(part)]
            if not technical_clauses:
                return sorted(found, key=lambda x: (-x[0], x[1]))
            raw = " ".join(technical_clauses)
            certs = certification_re.findall(raw)
            for cert in certs:
                add(cert.upper(), 100)
        if language_line_re.search(raw):
            for cert in certs:
                add(cert.upper(), 100)
            stripped = language_line_re.sub(" ", raw)
            stripped = re.sub(
                r"\b(?:speak|speaks|spoken|written|fluent|fluency|in|and|or|with)\b", " ", stripped, flags=re.I,
            )
            raw = re.sub(r"\s+", " ", stripped).strip()
            if not raw:
                return sorted(found, key=lambda x: (-x[0], x[1]))
        else:
            for cert in certs:
                add(cert.upper(), 100)

        low_raw = raw.casefold()
        for pattern, canonical in canonical_patterns:
            if re.search(pattern, low_raw, re.I):
                add(canonical, 110)

        parts = re.split(r"[,;/|()]|\s+-\s+", raw)
        for part in parts:
            part = re.sub(r"\b(?:minimum|min\.?|at least|more than|less than)\b", "", part, flags=re.I)
            part = re.sub(r"\b\d+\+?\s*(?:years?|yrs?)\b", "", part, flags=re.I)
            words = re.findall(r"[A-Za-z][A-Za-z0-9+#.:-]*", part)
            meaningful = [
                word for word in words
                if word.casefold() not in stop_tokens and word.casefold() not in action_noise
            ]
            if not meaningful:
                continue

            for word in meaningful:
                low = word.casefold().replace(" ", "")
                if low in recognised_singletons:
                    add(word, 90)

            for size in (3, 2):
                for i in range(len(meaningful) - size + 1):
                    window = meaningful[i:i + size]
                    lows = {word.casefold() for word in window}
                    if lows & domain_cues:
                        add(" ".join(window), 60 + size)

            if 2 <= len(meaningful) <= 5 and any(
                word.casefold() in domain_cues or word.casefold().replace(" ", "") in recognised_singletons
                for word in meaningful
            ):
                add(" ".join(meaningful), 55)

        return sorted(found, key=lambda x: (-x[0], x[1]))[:8]

    def balanced_select(lines, limit):
        per_line = [line_candidates(line) for line in lines]
        per_line = [items for items in per_line if items]
        selected = []
        selected_keys = set()

        def take(term):
            key = term.casefold()
            if key not in selected_keys and len(selected) < limit:
                selected_keys.add(key)
                selected.append(term)

        # First retain one best concept from every meaningful line.
        for items in per_line:
            if len(selected) >= limit:
                break
            take(items[0][2])

        # Then fill remaining capacity by evidence priority across all lines.
        rest = []
        for line_index, items in enumerate(per_line):
            for item_index, (priority, _order, term) in enumerate(items[1:], start=1):
                rest.append((-priority, line_index, item_index, term))
        for _neg_priority, _line_index, _item_index, term in sorted(rest):
            if len(selected) >= limit:
                break
            take(term)
        return selected

    max_terms = max(1, int(max_terms or 1))
    nice_budget = min(8, max(2, max_terms // 7)) if groups.get("nice") else 0
    core_limit = max_terms - nice_budget
    output = balanced_select(groups.get("core") or [], core_limit)
    if groups.get("nice") and len(output) < max_terms:
        nice_terms = balanced_select(groups.get("nice") or [], min(nice_budget, max_terms - len(output)))
        seen = {term.casefold() for term in output}
        for term in nice_terms:
            if term.casefold() not in seen and len(output) < max_terms:
                seen.add(term.casefold())
                output.append(term)
    return output[:max_terms]

def _spider_ignored_fit_term(term):
    """True for language/education criteria that must never affect match-fit %."""
    text = str(term or "").strip().lower()
    if not text:
        return True
    return re.search(
        r"\b(language|languages|linguistic|fluent|fluency|spoken|written|bilingual|multilingual|"
        r"english|mandarin|chinese|cantonese|hokkien|hakka|teochew|malay|bahasa|japanese|korean|thai|"
        r"vietnamese|tagalog|filipino|indonesian|degree|diploma|bachelor|master|masters|phd|doctorate|"
        r"university|college|education|academic|cgpa|gpa|spm|stpm)\b",
        text,
        re.I,
    ) is not None


def _spider_strip_context_fit_term(term, filters=None):
    """Remove pure location/work-mode metadata without damaging technical phrases.

    Standalone values such as ``Kuala Lumpur`` or ``On-site`` are not fit
    evidence.  Embedded technical concepts such as ``Hybrid Cloud``, ``Remote
    Desktop Services`` and ``remote sensing`` must remain intact.
    """
    text = re.sub(r"\s+", " ", str(term or "")).strip()
    if not text:
        return ""
    filters = filters if isinstance(filters, dict) else {}
    location_terms = set()
    for definition in _SPIDER_COUNTRY_DEFINITIONS.values():
        for value in list(definition.get("names") or []) + list(definition.get("places") or []):
            value = re.sub(r"\s+", " ", str(value or "")).strip().lower()
            if value:
                location_terms.add(value)
    for value in (filters.get("country"), filters.get("city_state"), filters.get("location")):
        value = re.sub(r"\s+", " ", str(value or "")).strip().lower()
        if value and value != "any":
            location_terms.add(value)

    cleaned = text
    cleaned = re.sub(
        r"\b(?:location|located|city|state|country|postcode|postal code)\s*[:=-]?\s*",
        " ", cleaned, flags=re.I,
    )
    cleaned = re.sub(r"\b(?:based|located)\s+in\b", " ", cleaned, flags=re.I)

    # Preserve well-known technical uses of hybrid/remote before stripping work
    # arrangements.  The placeholders contain only ASCII word characters and
    # are restored after location cleanup.
    protected = []
    tech_pattern = re.compile(
        r"\b(?:hybrid\s+(?:cloud|infrastructure|architecture|network|environment|database|systems?|integration|deployment)|"
        r"remote\s+(?:desktop(?:\s+services?)?|sensing|access|monitoring|management|administration|support|operations|backup|database|servers?|systems?))\b",
        re.I,
    )
    def protect(match):
        protected.append(match.group(0))
        return "TECHWORKMODETOKEN{}".format(len(protected) - 1)
    cleaned = tech_pattern.sub(protect, cleaned)
    cleaned = re.sub(
        r"\b(?:on[ -]?site|onsite|office[ -]?based|work(?:ing)? from (?:the )?office|"
        r"remote|work from home|wfh|hybrid|flexible work(?:ing)?|work arrangement|work mode)\b",
        " ", cleaned, flags=re.I,
    )
    for i, original in enumerate(protected):
        cleaned = cleaned.replace("TECHWORKMODETOKEN{}".format(i), original)

    for location in sorted(location_terms, key=len, reverse=True):
        cleaned = re.sub(r"(?<!\w)" + re.escape(location) + r"(?!\w)", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"[|,/;:()\[\]{}]+", " ", cleaned)
    cleaned = re.sub(r"(?:^|\s)[-–—]+(?:\s|$)", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -–—|,;/:")
    if cleaned.lower() in {
        "location", "work", "working", "arrangement", "mode", "setup",
        "on site", "onsite", "remote", "hybrid", "wfh", "office based",
    }:
        return ""
    return cleaned

def _spider_context_only_fit_term(term, filters=None):
    """True when a fit term contains only location/work-arrangement context."""
    return not bool(_spider_strip_context_fit_term(term, filters))













def _spider_weighted_coverage(blob_low, terms):
    """Return weighted coverage, summary hits, clean terms and per-term evidence."""
    clean = []
    seen = set()
    for term in terms or []:
        t = re.sub(r"\s+", " ", str(term or "")).strip()
        if not t or _spider_ignored_fit_term(t):
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        clean.append(t)
    if not clean:
        return None, [], [], []
    hits = []
    details = []
    total = 0.0
    earned = 0.0
    for term in clean:
        words = re.findall(r"[A-Za-z0-9+#.]+", term)
        weight = 2.0 if len(words) >= 2 else (1.6 if re.match(r"^[A-Z0-9+#.]{2,}$", term) else 1.0)
        coverage = _spider_term_coverage(blob_low, term)
        total += weight
        earned += coverage * weight
        status = "exact" if coverage >= 0.999 else ("partial" if coverage >= 0.5 else "missing")
        details.append({
            "term": term,
            "coverage": round(float(coverage), 4),
            "weight": round(float(weight), 2),
            "status": status,
        })
        if coverage >= 0.5:
            hits.append(term if coverage >= 0.999 else term + " (partial)")
    return (earned / total if total else 0.0), hits, clean, details

def _spider_match_fit_percent(candidate, filters, blob_low, discovery_hits):
    """Calculate a normalized 0-100 job-fit percentage with an auditable breakdown."""
    components = []
    evidence = []
    unknown = []

    jd_terms = []
    for term in _spider_jd_relevance_terms(filters.get("jd") or filters.get("job_description"), 56):
        cleaned_term = _spider_strip_context_fit_term(term, filters)
        if cleaned_term:
            jd_terms.append(cleaned_term)
    jd_cov, jd_hits, _jd_clean, jd_details = _spider_weighted_coverage(blob_low, jd_terms)

    must_raw = filters.get("must") or filters.get("boolean") or ""
    must_terms = []
    for term in _spider_boolean_positive_terms(must_raw, 28):
        cleaned_term = _spider_strip_context_fit_term(term, filters)
        if cleaned_term and not _spider_ignored_fit_term(cleaned_term):
            must_terms.append(cleaned_term)
    if not must_terms and must_raw:
        for term in _spider_terms(must_raw, 28):
            cleaned_term = _spider_strip_context_fit_term(term, filters)
            if cleaned_term and not _spider_ignored_fit_term(cleaned_term):
                must_terms.append(cleaned_term)
    must_cov, must_hits, _must_clean, must_details = _spider_weighted_coverage(blob_low, must_terms)
    native_confirmed = bool(candidate.get("_spiderNativeBooleanMatched")) if isinstance(candidate, dict) else False
    must_coverage_before_native_floor = must_cov
    native_floor_applied = False
    if must_cov is not None and native_confirmed and must_cov < 0.60:
        must_cov = 0.60
        native_floor_applied = True

    role_terms = []
    for term in _spider_terms(filters.get("role"), 10):
        cleaned_term = _spider_strip_context_fit_term(term, filters)
        if cleaned_term and not _spider_ignored_fit_term(cleaned_term):
            role_terms.append(cleaned_term)
    role_cov, role_hits, _role_clean, role_details = _spider_weighted_coverage(blob_low, role_terms)

    nice_terms = []
    for term in _spider_terms(filters.get("nice"), 18):
        cleaned_term = _spider_strip_context_fit_term(term, filters)
        if cleaned_term and not _spider_ignored_fit_term(cleaned_term):
            nice_terms.append(cleaned_term)
    nice_cov, nice_hits, _nice_clean, nice_details = _spider_weighted_coverage(blob_low, nice_terms)

    def add_component(key, label, coverage, base_weight, hits, term_details, missing_message):
        if coverage is None:
            return
        components.append({
            "key": key,
            "label": label,
            "coverage": float(coverage),
            "base_weight": float(base_weight),
            "hits": list(hits or []),
            "terms": list(term_details or []),
        })
        if hits:
            evidence_label = {
                "jd": "Job scope/requirements",
                "must": "Must-have/Boolean",
                "role": "Role alignment",
                "nice": "Additional requirements",
            }.get(key, label)
            evidence.append(evidence_label + ": " + ", ".join(list(hits)[:8]))
        elif key == "must" and native_confirmed:
            evidence.append("JobAdder confirmed the recruiter Boolean against the latest resume")
        else:
            unknown.append(missing_message)

    add_component("jd", "JD requirements", jd_cov, 55.0, jd_hits, jd_details, "JD scope/requirements not visible")
    add_component("must", "Boolean / must-have", must_cov, 25.0 if jd_cov is not None else 50.0, must_hits, must_details, "must-have evidence not visible")
    add_component("role", "Target-role alignment", role_cov, 10.0 if jd_cov is not None else 30.0, role_hits, role_details, "target role not visible")
    add_component("nice", "Nice-to-have", nice_cov, 10.0 if jd_cov is not None else 20.0, nice_hits, nice_details, "additional requirements not visible")

    total_weight = sum(item["base_weight"] for item in components)
    raw_percent = int(round(sum(item["coverage"] * item["base_weight"] for item in components) / total_weight * 100.0)) if total_weight else 0
    percent = raw_percent
    discovery_floor_applied = False
    if components:
        if discovery_hits and percent < 10:
            percent = 10
            discovery_floor_applied = True
            evidence.append("Keyword discovery: " + ", ".join(discovery_hits[:8]))
            unknown.append("JobAdder confirmed discovery, but visible job-fit evidence is limited")
    elif discovery_hits:
        percent = 10
        discovery_floor_applied = True
        evidence.append("Keyword discovery: " + ", ".join(discovery_hits[:8]))
        unknown.append("No JD/role/must-have scope supplied; showing minimum discovery fit")
    else:
        percent = 0
        unknown.append("No usable job-scope criteria supplied")

    component_rows = []
    for item in components:
        max_points = (item["base_weight"] / total_weight * 100.0) if total_weight else 0.0
        points = item["coverage"] * max_points
        terms = item.get("terms") or []
        component_rows.append({
            "key": item["key"],
            "label": item["label"],
            "coverage_percent": int(round(item["coverage"] * 100.0)),
            "points": round(points, 1),
            "max_points": round(max_points, 1),
            "matched": [x.get("term") for x in terms if x.get("status") == "exact"][:12],
            "partial": [x.get("term") for x in terms if x.get("status") == "partial"][:12],
            "missing": [x.get("term") for x in terms if x.get("status") == "missing"][:12],
            "native_boolean_floor": bool(item["key"] == "must" and native_floor_applied),
            "coverage_before_adjustment_percent": int(round(must_coverage_before_native_floor * 100.0)) if item["key"] == "must" and native_floor_applied and must_coverage_before_native_floor is not None else int(round(item["coverage"] * 100.0)),
            "points_before_adjustment": round((must_coverage_before_native_floor if item["key"] == "must" and native_floor_applied and must_coverage_before_native_floor is not None else item["coverage"]) * max_points, 1),
            "evidence_status": "unavailable" if not item.get("hits") else "visible",
        })

    breakdown = {
        "method": "normalized_weighted_coverage_v2",
        "components": component_rows,
        "raw_percent": max(0, min(100, raw_percent)),
        "final_percent": max(0, min(100, percent)),
        "discovery_floor_applied": discovery_floor_applied,
        "native_boolean_floor_applied": native_floor_applied,
        "excluded_from_score": ["location", "work arrangement", "language", "education", "salary", "industry", "target companies"],
    }
    return max(0, min(100, percent)), evidence[:10], unknown[:8], breakdown

def _spider_item_score(candidate, filters, enriched=False):
    """Return (keep, fit_percent, fit evidence, unknown, excluded, hard_passed, discovery evidence).

    Stage 1 discovers candidates by Boolean Rules / Keywords (when supplied),
    plus explicit hard filters. The JD is not used to decide discovery eligibility.
    Stage 2 scores the remaining candidate 0-100 against job scope/requirements,
    omitting language and education, and keeps candidates from 10% upward.
    """
    filters = filters if isinstance(filters, dict) else {}
    blob = _spider_candidate_blob(candidate)
    blob_low = blob.lower()
    unknown, excluded, hard_passed = [], [], []

    # Only the separate Exclude/Avoid field is rechecked locally.
    # Native JobAdder Boolean rules (including NOT) are trusted as returned and are
    # never re-evaluated against the incomplete candidate-detail JSON.
    exclude_terms = _spider_terms(filters.get("exclude") or filters.get("avoid"), 24)
    hit_excludes = _spider_hit_terms(blob_low, exclude_terms)
    if hit_excludes:
        return False, 0, [], unknown, ["exclude: " + ", ".join(hit_excludes[:5])], hard_passed, []

    # A Boolean fallback searches positive atoms only. If a NOT operand is visibly
    # present in the available profile data, exclude it conservatively; absence is
    # kept as unknown because JobAdder detail JSON may omit resume text.
    fallback_negative_terms = list(candidate.get("_spiderBooleanNegativeTerms") or []) if isinstance(candidate, dict) else []
    if candidate.get("_spiderBooleanFallback") if isinstance(candidate, dict) else False:
        fallback_negative_hits = _spider_hit_terms(blob_low, fallback_negative_terms)
        if fallback_negative_hits:
            return False, 0, [], unknown, ["Boolean NOT match: " + ", ".join(fallback_negative_hits[:5])], hard_passed, []
        if fallback_negative_terms:
            unknown.append("Boolean NOT terms not fully visible in available profile data")

    def hard_filter_terms(label, value, max_terms=24, require_all=False):
        terms = _spider_terms(value, max_terms)
        if not terms:
            return []
        hits = _spider_hit_terms(blob_low, terms)
        missing = [t for t in terms if t not in hits]
        if require_all and missing:
            raise ValueError("missing hard filter {}: {}".format(label, ", ".join(missing[:5])))
        if not hits:
            if not enriched and not bool(filters.get("strict")):
                unknown.append("{} not visible in list result".format(label))
                return []
            raise ValueError("missing hard filter {}".format(label))
        hard_passed.append(label + ": " + ", ".join(hits[:5]))
        return hits

    # Existing explicit hard filters remain eligibility gates, not fit-score points.
    try:
        hard_filter_terms("IT skills", filters.get("it_skills") or filters.get("skills"), 24, bool(filters.get("strict")))
        hard_filter_terms("qualifications", filters.get("qualifications"), 18, False)
    except ValueError as e:
        return False, 0, [], unknown, [str(e)], hard_passed, []

    country = str(filters.get("country") or "").strip()
    if country and country.lower() != "any":
        country_result, country_evidence = _spider_country_match(candidate, country)
        if country_result == "match":
            hard_passed.append("country: " + country)
        elif country_result == "mismatch":
            return False, 0, [], unknown, ["country mismatch: " + (country_evidence or country)[:100]], hard_passed, []
        elif not enriched and not bool(filters.get("strict")):
            unknown.append("country not visible in list result")
        else:
            return False, 0, [], unknown, ["country not visible"], hard_passed, []

    residential = str(filters.get("residential") or "Any").strip()
    if residential and residential.lower() != "any":
        res_text = _spider_residential_status_text(candidate)
        target_status = _spider_status_target(residential)
        visible_statuses = _spider_residential_classes(res_text)
        if target_status and target_status in visible_statuses:
            hard_passed.append("residential: " + residential)
        elif visible_statuses:
            return False, 0, [], unknown, ["residential mismatch: " + res_text[:100]], hard_passed, []
        elif not enriched and not bool(filters.get("strict")):
            unknown.append("residential status not visible in list result")
        else:
            return False, 0, [], unknown, ["residential status not visible"], hard_passed, []

    min_years, max_years = _spider_years_bounds(filters)
    if min_years > 0 or max_years is not None:
        visible_years = _spider_visible_years(candidate)
        if visible_years is None:
            unknown.append("years experience not visible")
        else:
            visible_label = ("{:.1f}".format(float(visible_years))).rstrip("0").rstrip(".")
            if float(visible_years) < float(min_years):
                return False, 0, [], unknown, ["years experience below minimum {}: {}".format(min_years, visible_label)], hard_passed, []
            if max_years is not None and float(visible_years) > float(max_years):
                return False, 0, [], unknown, ["years experience above maximum {}: {}".format(max_years, visible_label)], hard_passed, []
            if max_years is None:
                hard_passed.append("experience: {} years visible (minimum {}+)".format(visible_label, min_years))
            elif min_years > 0:
                hard_passed.append("experience: {} years visible (range {}-{})".format(visible_label, min_years, max_years))
            else:
                hard_passed.append("experience: {} years visible (maximum {})".format(visible_label, max_years))

    native_boolean_match = bool(candidate.get("_spiderNativeBooleanMatched")) if isinstance(candidate, dict) else False
    plain_fallback_match = bool(candidate.get("_spiderBooleanFallback")) if isinstance(candidate, dict) else False
    native_boolean_rule = str(candidate.get("_spiderBooleanRule") or filters.get("must") or filters.get("boolean") or "").strip() if isinstance(candidate, dict) else str(filters.get("must") or filters.get("boolean") or "").strip()
    if native_boolean_match:
        # JobAdder's candidate Keywords search is the discovery authority. The detail
        # endpoint may omit the latest-resume text, so do not re-test the rule locally.
        discovery_ok = True
        discovery_hits = [native_boolean_rule] if native_boolean_rule else ["JobAdder native Boolean match"]
        discovery_missing = []
    elif plain_fallback_match:
        # The original Boolean returned zero rows. These rows came from the explicit,
        # labelled plain-keyword fallback, so do not re-evaluate the Boolean (especially
        # NOT terms) against incomplete candidate JSON or synthetic proven-term lists.
        discovery_ok = True
        discovery_hits = list(candidate.get("_spiderSearchTerms") or []) if isinstance(candidate, dict) else []
        if not discovery_hits:
            discovery_hits = ["JobAdder plain-keyword fallback match"]
        discovery_missing = []
    else:
        proven_terms = candidate.get("_spiderSearchTerms", []) if isinstance(candidate, dict) else []
        discovery_ok, discovery_hits, discovery_missing = _spider_discovery_keyword_match(
            blob_low,
            filters.get("must") or filters.get("boolean") or "",
            bool(filters.get("strict")),
            proven_terms=proven_terms,
        )
    if not discovery_ok:
        return False, 0, [], unknown, discovery_missing, hard_passed, discovery_hits

    fit_percent, fit_evidence, fit_unknown, fit_breakdown = _spider_match_fit_percent(candidate, filters, blob_low, discovery_hits)
    unknown.extend(fit_unknown)
    if filters.get("salary"):
        unknown.append("salary not used in fit score")
    if filters.get("industry"):
        unknown.append("industry not used in fit score")
    if filters.get("targets"):
        unknown.append("target companies not used in fit score")

    if fit_percent < 10:
        return False, fit_percent, fit_evidence, unknown[:8], ["match fit below 10%"], hard_passed[:8], discovery_hits[:10], fit_breakdown
    return True, fit_percent, fit_evidence[:10], unknown[:8], excluded, hard_passed[:8], discovery_hits[:10], fit_breakdown

def _spider_option_fallbacks(name):
    key = str(name or "").strip().lower()
    if key in {"industry", "industries"}:
        return ["Banking", "Financial Services", "Fintech", "Shared Services", "Technology", "Telecommunications", "Manufacturing", "FMCG", "Healthcare", "Retail", "E-commerce", "Consulting"]
    if key in {"it_skills", "it skills", "skill", "skills", "technical_skills"}:
        return ["SAP", "SAP ABAP", "SAP FICO", "SAP BW", "SAP BPC", "Oracle", "NetSuite", "Salesforce", "Python", "Java", "AWS", "Azure", "GCP", "Kubernetes", "Docker", "SQL", "Power BI", "Tableau"]
    if key in {"qualifications", "qualification", "certifications"}:
        return ["ACCA", "CPA", "CIMA", "MIA", "ICAEW", "CFA", "CIA", "PMP", "PRINCE2", "ITIL", "CKA", "AWS Certified", "Azure Certified", "SAP Certified"]
    return []


def _spider_extract_option_values(payload):
    values = []
    seen = set()
    def add(v):
        if isinstance(v, dict):
            for k in ["name", "label", "value", "title", "text", "displayName"]:
                if v.get(k):
                    return add(v.get(k))
            return
        txt = re.sub(r"\s+", " ", str(v or "")).strip()
        if not txt or len(txt) > 120:
            return
        k = txt.lower()
        if k not in seen:
            seen.add(k); values.append(txt)
    def walk(x, depth=0):
        if depth > 4 or x is None:
            return
        if isinstance(x, list):
            for item in x[:300]:
                walk(item, depth+1)
        elif isinstance(x, dict):
            for key in ["items", "values", "valueList", "data", "list", "records", "options"]:
                if isinstance(x.get(key), list):
                    walk(x.get(key), depth+1)
            if any(k in x for k in ["name", "label", "value", "title", "text", "displayName"]):
                add(x)
        else:
            add(x)
    walk(payload)
    return values[:250]
