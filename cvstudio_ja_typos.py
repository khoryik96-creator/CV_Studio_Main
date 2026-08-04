"""JobAdder recruitment and salary typo-correction helpers.

Behaviour-preserving extraction of the pure fuzzy typo-correction logic from the
legacy web shell (Phase 7B): bounded edit distance, casing preservation, the
recruitment/salary typo alias and fuzzy-term tables, and the field-level
corrections applied to screening notes, notice-period text and salary strings.

Pure functions of their inputs - no Flask, no globals beyond the tables defined
here, no network, no JobAdder or provider access. This module never imports
``app``.
"""

import re


_JA_SALARY_TYPO_RULES = [
    (
        "ordinal_month",
        re.compile(
            r"(?<![a-z0-9])(\d+(?:\.\d+)?(?:th|st|nd|rd))\s*"
            r"(?:monnth|monnths|monht|monhth|moth|mnth|mth|mthh|mnt)(s?)(?![a-z])",
            re.I,
        ),
        lambda m: m.group(1) + " month" + ("s" if m.group(2) else ""),
    ),
    (
        "allowance",
        re.compile(
            r"(?<![a-z])(?:allowance|allowence|allowanse|alowance|alowence|alowanse|"
            r"allwance|allwan(?:ce)?|alwance|alwan(?:ce)?|allowan(?:ce)?|allownce|"
            r"alowanc(?:e)?|alwanc(?:e)?|allowanc(?:e)?|alwnce|alwn|sllowance)(?![a-z])",
            re.I,
        ),
        "allowance",
    ),
    (
        "month",
        re.compile(
            r"(?<![a-z])(?:month|monnth|monnths|monht|monhth|moth|mnth|mth|mthh|mnt)(s?)(?![a-z])",
            re.I,
        ),
        lambda m: "month" + ("s" if m.group(1) else ""),
    ),
    (
        "bonus",
        re.compile(r"(?<![a-z])(?:bonus|bonous|bouns|bonos|bonnus|bnus)(?![a-z])", re.I),
        "bonus",
    ),
    (
        "epf",
        re.compile(r"(?<![a-z])(?:epf|efp|epff)(?![a-z])", re.I),
        "EPF",
    ),
    (
        "percent",
        re.compile(r"(?<![a-z])(?:percent|precent|persent|percet|percnt)(?![a-z])", re.I),
        "percent",
    ),
    (
        "myr_currency",
        re.compile(
            r"(?<![a-z])(?:ringgit|rngint|rnggit|ringit|ringgt|ringgitt|ringet|"
            r"renggit|rengit|ringint|ringgint|rngit|rngt)(?![a-z])",
            re.I,
        ),
        "MYR",
    ),
]


def _ja_salary_normalize_recruiter_typos(raw, with_changes=False):
    """Normalize conservative salary-only typo aliases deterministically.

    This is intentionally scoped to Current Salary Breakdown / Expected Salary
    parser calls.  It does not inspect Summary, RFL, Looking For, Remarks or any
    other Screening Call section.
    """
    text = str(raw or "")
    changes = []
    for rule_name, pattern, replacement in _JA_SALARY_TYPO_RULES:
        def repl(match, _replacement=replacement, _name=rule_name):
            value = _replacement(match) if callable(_replacement) else _replacement
            original = match.group(0)
            if original.casefold() != str(value).casefold():
                changes.append({"type": _name, "from": original, "to": value})
            return value
        text = pattern.sub(repl, text)
    return (text, changes) if with_changes else text



def _ja_edit_distance_limited(a, b, max_distance):
    a, b = str(a or ""), str(b or "")
    if abs(len(a) - len(b)) > max_distance:
        return max_distance + 1
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        row_min = i
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            value = min(current[j - 1] + 1, previous[j] + 1, previous[j - 1] + cost)
            if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                value = min(value, previous[j - 2] + 1)
            current.append(value)
            row_min = min(row_min, value)
        if row_min > max_distance:
            return max_distance + 1
        previous = current
    return previous[-1]


_JA_RECRUITMENT_TYPO_ALIASES = {
    "allwan":"allowance", "alwan":"allowance", "alwance":"allowance", "alowance":"allowance", "allowence":"allowance",
    "allownce":"allowance", "allownace":"allowance", "allowanec":"allowance", "allwance":"allowance", "sllowance":"allowance",
    "contrcat":"contract", "contrct":"contract", "conttract":"contract", "contrat":"contract", "conract":"contract", "cotract":"contract",
    "contrctual":"contractual", "contractaul":"contractual", "contractural":"contractual",
    "permenant":"permanent", "permanant":"permanent", "permament":"permanent", "permenent":"permanent", "permnent":"permanent",
    "permanet":"permanent", "permanenet":"permanent", "premanent":"permanent",
    "expatrite":"expatriate", "expatraite":"expatriate", "expatriat":"expatriate", "expartriate":"expatriate",
    "expatirate":"expatriate", "expatriete":"expatriate",
    "loacl":"local", "lcoal":"local", "locla":"local",
    "nationalty":"nationality", "nationallity":"nationality", "natinality":"nationality", "nationlity":"nationality",
    "sponsosrhip":"sponsorship", "sponorship":"sponsorship", "sponsorsip":"sponsorship", "sponserhip":"sponsorship",
    "sponsership":"sponsorship", "sponsrship":"sponsorship", "sponshorship":"sponsorship", "sponsorhip":"sponsorship",
    "citizneship":"citizenship", "citizenhip":"citizenship", "citizanship":"citizenship", "citiznship":"citizenship",
    "relocaiton":"relocation", "relcoation":"relocation", "relocaton":"relocation",
    "employement":"employment", "emplyoment":"employment", "employmnt":"employment",
    "salry":"salary", "sallary":"salary", "bonous":"bonus", "bouns":"bonus",
    "guaranted":"guaranteed", "garanteed":"guaranteed", "guaranteeed":"guaranteed",
    "negotiabe":"negotiable", "negotible":"negotiable", "negtiable":"negotiable",
    "availablity":"availability", "availibility":"availability", "avalability":"availability",
    "enviroment":"environment", "environement":"environment", "experiance":"experience", "experince":"experience",
    "communcation":"communication", "comunication":"communication", "communicaiton":"communication",
    "presntability":"presentability", "presentabilty":"presentability", "candiadte":"candidate", "candiate":"candidate",
    "residental":"residential", "residnetial":"residential", "viza":"visa", "vissa":"visa", "pemrit":"permit",
    "permmit":"permit", "stauts":"status", "reomte":"remote", "hybird":"hybrid", "oniste":"onsite",
}
_JA_RECRUITMENT_FUZZY_TERMS = (
    "allowance", "contract", "contractual", "permanent", "expatriate", "nationality", "sponsorship", "citizenship",
    "relocation", "employment", "guaranteed", "negotiable", "availability", "environment", "experience",
    "communication", "presentability", "candidate", "residential",
)
_JA_RECRUITMENT_PROTECTED_WORDS = {
    "allowance", "allowances", "contract", "contracts", "contracted", "contracting", "contractor", "contractors",
    "contractual", "contractually", "permanent", "permanently", "expatriate", "expatriates", "local", "locals",
    "nationality", "nationalities", "sponsorship", "sponsorships", "sponsor", "sponsored", "sponsoring",
    "citizenship", "citizenships", "citizen", "citizens", "relocation", "relocate", "relocated", "relocating",
    "employment", "employed", "employer", "employers", "employee", "employees", "salary", "salaries", "bonus", "bonuses",
    "guaranteed", "guarantee", "guarantees", "negotiable", "availability", "available", "environment", "environments",
    "experience", "experienced", "experiences", "communication", "communications", "presentability", "candidate", "candidates",
    "residential", "residence", "visa", "visas", "permit", "permits", "status", "remote", "hybrid", "onsite",
}

def _ja_case_like(original, corrected):
    original = str(original or "")
    corrected = str(corrected or "")
    if original and original == original.upper():
        return corrected.upper()
    if re.fullmatch(r"[A-Z][a-z]+", original):
        return corrected[:1].upper() + corrected[1:]
    return corrected

def _ja_recruitment_typo_target(token, allow_fuzzy=True):
    lower = str(token or "").lower()
    if not lower or lower in _JA_RECRUITMENT_PROTECTED_WORDS:
        return ""
    explicit = _JA_RECRUITMENT_TYPO_ALIASES.get(lower)
    if explicit:
        return explicit
    if not allow_fuzzy or len(lower) < 8:
        return ""
    best = None
    for target in _JA_RECRUITMENT_FUZZY_TERMS:
        if lower[0] != target[0] or lower[-1] != target[-1] or abs(len(lower) - len(target)) > 2:
            continue
        allowed = 2 if max(len(lower), len(target)) >= 11 else 1
        distance = _ja_edit_distance_limited(lower, target, allowed)
        if distance <= allowed and distance / max(len(lower), len(target)) <= 0.20:
            if best is None or distance < best[1]:
                best = (target, distance)
    return best[0] if best else ""

def _ja_correct_recruitment_typos(raw_text, enabled=True, allow_fuzzy=True, with_changes=False):
    text = str(raw_text or "")
    if not text or not enabled:
        return (text, []) if with_changes else text
    changes = []
    def replace_token(match):
        token = match.group(0)
        target = _ja_recruitment_typo_target(token, allow_fuzzy=allow_fuzzy)
        if not target or target.lower() == token.lower():
            return token
        replacement = _ja_case_like(token, target)
        if len(changes) < 12:
            changes.append("{} -> {}".format(token, replacement))
        return replacement
    corrected = re.sub(r"[A-Za-z]+", replace_token, text)
    return (corrected, changes) if with_changes else corrected

def _ja_correct_screening_field_typos(fields, enabled=True):
    fields = dict(fields or {})
    if not enabled:
        return fields
    field_rules = {
        "brief_overview": False,
        "reason_leaving": True,
        "looking_for": True,
        "current_salary_breakdown": True,
        "expected_salary": True,
        "notice_period": True,
        "leads": True,
        "remarks": True,
        "role": True,
        "location": True,
        "red_flags": True,
        "next_steps": True,
        "raw_presentability": True,
    }
    for key, allow_fuzzy in field_rules.items():
        fields[key] = _ja_correct_recruitment_typos(fields.get(key, ""), enabled=True, allow_fuzzy=allow_fuzzy)
    return fields

def _ja_correct_notice_typos(raw_text, enabled=True):
    text = str(raw_text or "").strip()
    if not text or not enabled:
        return text
    if re.search(r"\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}\b", text) or re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]20\d{2}\b", text):
        return text
    immediate_aliases = {
        "imm", "immed", "imdt", "immdiate", "immedaite", "imediate", "immediatey",
        "immediatly", "immediatley", "immediatelly", "immidiately", "immidiate",
    }
    month_aliases = {
        "monht": "month", "monhts": "months", "monhth": "month", "monhths": "months",
        "moth": "month", "moths": "months", "mothn": "month", "mothns": "months",
        "monnth": "month", "monnths": "months", "monthh": "month", "monthhs": "months",
    }
    week_aliases = {"wek": "week", "weks": "weeks", "weeek": "week", "weeeks": "weeks"}
    day_aliases = {"daay": "day", "daays": "days", "dayz": "days"}
    found_immediate = False

    def fix_token(match):
        nonlocal found_immediate
        token = match.group(0).lower()
        if token in ("immediate", "immediately") or token in immediate_aliases:
            found_immediate = True
            return "immediate"
        if 7 <= len(token) <= 12 and (
            _ja_edit_distance_limited(token, "immediate", 2) <= 2
            or _ja_edit_distance_limited(token, "immediately", 2) <= 2
        ):
            found_immediate = True
            return "immediate"
        if token in month_aliases:
            return month_aliases[token]
        if token in week_aliases:
            return week_aliases[token]
        if token in day_aliases:
            return day_aliases[token]
        return match.group(0)

    corrected = re.sub(r"[A-Za-z]+", fix_token, text)
    corrected = re.sub(r"\s+", " ", corrected).strip()
    if found_immediate or re.search(r"\b(?:available|availble|avalable)\s+now\b", corrected, re.I):
        return "Immediate"
    if re.fullmatch(r"(?:0|none|nil|n/a)", corrected, re.I):
        return "Immediate"
    word_numbers = {"one": 1, "a": 1, "an": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
    m = re.fullmatch(r"(one|a|an|two|three|four|five|six)\s*(day|days|week|weeks|month|months)", corrected, re.I)
    if m:
        corrected = "{} {}".format(word_numbers[m.group(1).lower()], m.group(2).lower())
    m = re.fullmatch(r"(\d+)\s*(day|days|week|weeks|month|months)", corrected, re.I)
    if m:
        number = int(m.group(1))
        unit = m.group(2).lower()
        singular = "month" if unit.startswith("month") else "week" if unit.startswith("week") else "day"
        return "{} {}{}".format(number, singular, "" if number == 1 else "s")
    if re.fullmatch(r"\d+", corrected):
        number = int(corrected)
        if number == 0:
            return "Immediate"
        if 1 <= number <= 12:
            return "{} month{}".format(number, "" if number == 1 else "s")
    return corrected
