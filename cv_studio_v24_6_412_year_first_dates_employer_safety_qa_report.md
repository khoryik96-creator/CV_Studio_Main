# v24.6.411 / v24.6.412 Year-first dates, and a shortfall that should not ship

Branch: `claude/cv-year-first-dates-employer-safety`.
Base: master `960a0866b357db702e9cc0fdbabdfcc2e60f12ae`, v24.6.410.

Raised from a real formatted CV whose output was missing the candidate's three
most recent employers, including his current job.

## What the reported CV did

The source lists **nine** employers. The formatted CV carried **six**. The three
missing were the newest: a 2025-to-current data engineering role at a bank, a
2024–2025 role, and a 2022–2024 role. The CV read as though the candidate's
career stopped in 2022.

Two education rows were also rendered at the top of Work Experience, formatted as
jobs and duplicating the Education section below. Every surviving job header read
`Apr 2019 to Mar 2022 | |` — the employer name replaced by the cell separator.

## Where the fault was, and was not

**Extraction was perfect.** `_extract_docx_text_preserve_tables` pulled all nine
employers out of the source's four tables in order, with company, industry, dates,
title, salary and every duty line intact.

**The generator was correct.** The AI's output was reconstructed from the symptoms
and fed to the real `generate.js`, which reproduced the reported document line for
line, including the `| |`. Nothing downstream is misbehaving; it rendered a wrong
structure faithfully.

**The fault is the model's structured output.** It dropped three employers,
promoted two education rows into `work_experiences`, and took the `|` separator as
the company name.

## The trigger

The three lost employers are the only three whose dates are written year-first:

```
2025 june- current          <- lost
2024 sept -2025 April       <- lost
2022 march - 2024 august    <- lost
Apr 2019 - Mar 2022         <- kept
Sep 2017 - Apr 2019         <- kept
Jun 2015 - august  2017     <- kept
```

Every year-first row lost, every month-first row kept. That is not a coincidence,
and the codebase already knew this hazard: `_cv_pretranslate_iso_dates` exists
precisely because "providers read that format unreliably — they mis-tag the month
or year, or turn a real end date into Present". It only covered the numeric form
(`2020-06`). The same hazard spelled out with a month name went through untouched.

## Change 1 — normalise the spelled-out year-first form

`_cv_pretranslate_year_first_month_names` rewrites `YYYY Month` to `Month YYYY`
across the CV document before the provider reads it, mirroring what the numeric
helper already did. The month keeps the source's own spelling, so the CV is
reordered rather than edited.

**Deliberately not added to `_normalize_cv_date_range`.** That per-field
normaliser is mirrored in two JavaScript copies under one shared contract, and a
rule added on the Python side alone would break it. The first draft did chain it
there and `tests/test_cv_date_parity.py` caught it immediately — see below.

Guarded so a year that already *closes* a month-first date is left alone: in
`Jun 2020 Jun 2021` the 2020 belongs to the first date and the `Jun` after it
opens the second. The optional leading month is captured rather than skipped, so
that case is recognised and returned untouched.

## Change 2 — see the shortfall instead of shipping it

A fidelity audit already runs on every parse and can mark a result degraded. It
found **zero** source employers in this CV, so it reported `ok: true` while three
were missing: it locates employers only through `_extract_authoritative_work_rows`,
which wants a Dates/Organization/Role table. This CV labels them instead —
`Company: TNG Digital Sdn Bhd | Industry: Finance`.

The audit now also reads those labels. On the reported CV it finds eight of the
nine employers and reports the shortfall. Two guards keep it conservative:

- **Work-history section only, and only when that section can be located.** A
  referees block or a cover note can also say "Company:", and an employer expected
  from outside the work history would warn on a perfectly good parse. No section
  found, no claim made.
- **The Industry cell is stripped**, because the extractor joins a row's cells with
  `" | "` and the industry rides along on the same line.

A parsed company that is punctuation only — `|`, `-`, `:` — is also named now. In
the finished CV it shows as an empty employer, which reads as a layout fault
rather than as the dropped field it is.

The audit remains observational. It never mutates the parse; it tells the user to
check before continuing.

## What this does and does not fix

It removes the trigger and it stops the same failure shipping silently. It does
**not** guarantee the model reads this CV correctly — that cannot be verified here,
because the parse step needs a live paid provider call. The honest claim is: the
known bad input class is normalised away, and if a shortfall still happens the app
says so instead of handing over a CV without the candidate's current job.

Neither change touches the education/work misclassification. The audit will now
flag the resulting shortfall, which is the safety net working, but the
misclassification itself is a model-output problem left for a verified fix.

## Tests

`tests/test_cv_year_first_dates_employer_safety.py` — 21 tests, 41 subtests: each
verbatim date cell from the reported CV, the six month-first cells that must not
move, the source spelling preserved, year-only education ranges untouched, salary
figures / phone numbers / CGPA / `MSSQL 2014` / `FY2024 Sept` untouched, no
crossing a line break, idempotence, and the field normaliser proven unchanged.
Then the audit: labelled employers seen without a table, the industry cell not
read as part of the name, a missing employer reported, a complete parse silent, a
separator-only company named, real names never called separators, a label outside
the work history making no claim.

Six mutations were introduced and each was caught: removing the swap, removing the
month-first guard, not reading labels, not flagging a separator company, reading
the industry cell into the name, and widening the label scan to the whole document.

**One regression was found and fixed during this work.** Chaining the new swap
into `_cv_pretranslate_iso_dates` put it inside `_normalize_cv_date_range`, which
turned `Jun 2020 Jun 2021` into `Jun Jun 2020 2021`. The existing date-parity
suite failed on five separate line-ending variants. That is the JS-mirrored
contract doing its job, and it is why the swap is document-scoped.

Full suite: **1335 passed, 23 skipped**, plus the two environment-only failures
this container has always had (antiword binary absent, Windows registry
unavailable). Node fixtures: **24/24**. Launcher line endings match `origin/master`
exactly.

## For the reported candidate, right now

Editing the three date cells in the source Word file to month-first — "June 2025 -
current", "Sept 2024 - April 2025", "March 2022 - August 2024" — and re-running
should bring the three employers back without any code change. That is worth doing
as the confirmation that the trigger is understood correctly.


---

# v24.6.412 Review corrections

Eight findings across two reviews of v24.6.411. All eight were real. **Four were
defects I introduced in v24.6.411, and two of those corrupted correct data** — the
first version of this change was more dangerous than the bug it fixed.

## The date rewrite was rewriting prose

`_cv_pretranslate_year_first_month_names` matched `YYYY Month` anywhere in the
document. "may", "march" and "august" are ordinary English words, so:

```
figures for 2023 may be revised   ->  figures for may 2023 be revised
Since 2021 March, led the migration -> Since March 2021, led the migration
Won the 2024 March tender         ->  Won the March 2024 tender
```

Those edits went to the provider as the CV source and would have come back in the
recruiter-facing output. That is not a date reorder; it is rewriting the
candidate's own sentences.

It also scrambled real dates, because a year can close one date while a month
opens the next, and the guard consumed the trailing month so `re.sub` resumed past
it and was blind from the second date onward:

```
Jan 2018 Dec 2019 Jan 2020 Dec 2021 -> Jan 2018 Dec Jan 2019 Dec 2020 2021
2015 - 2018    Jun 2019 - Present   -> 2015 - Jun 2018 2019 - Present
2003-2006 May 2007 - Dec 2009       -> 2003-May 2006 2007 - Dec 2009
Jun.2020 Jun.2021                   -> Jun.Jun 2020.2021
```

The separator class also omitted the wide Unicode spaces Word and PDF use, which
both sibling helpers already cover, so `2025<figure space>June` was missed while
`Jun<thin space>2020 Jun<thin space>2021` was corrupted.

**Fixed by anchoring to the line.** The rewrite now only touches a line that is
*entirely* a date or a date range, with at least one year-first half — which is
what a table cell becomes once the document is flattened to text. At most two date
tokens can reach the swap, so a year cannot be taken from one date and a month from
the next. The space class now matches the siblings.

On the reported CV this changes **exactly 3 lines out of 173**: the three date
cells, and nothing else. Prose is never touched. The cost is that a year-first date
embedded in a longer line is left alone, which is the right trade.

## The audit warned on correct parses

- **A referees block was scanned for employers.** `_SECTION_STOP_HEADING_RE`
  covered REFERENCE/REFERENCES but not REFEREE/REFEREES, so the work-history span
  swallowed the block and the referee's own "Company:" line was reported missing,
  setting `degraded` on a flawless parse. REFEREE/REFEREES added.
- **A longer labelled name failed to match the employer the parse kept.** The
  reported CV's own first employer — `company: Avows IT outsourcing sdn bhd(boost
  bank sdn bhd)` against a parsed `Avows IT Outsourcing Sdn Bhd` — scored 0.6
  against a 0.67 threshold and was reported missing. `_employer_name_variants` now
  also tries the reading before a parenthesis, comma, dash or en/em dash, and the
  parenthesised brand on its own.
- **A hyphenated prose word was read as a label.** The separator accepted a bare
  hyphen, so a wrapped line beginning "Company-wide rollout of the new payroll
  platform" produced the employer candidate "wide rollout of the new payroll
  platform" and showed it to the user. A colon is now required.

## The unnamed-employer report located nothing

It read `item.get("date_range")` from `_flatten_parsed_work_roles`, which emits
`exp_date`/`role_date` and never `date_range`, so the fallback always won and every
entry was just the separator character. It also counted per flattened role, so one
employer with three roles read as "3 work entries came back with no employer name".

Now walked per work experience, taking the date range from the experience itself.
**The original test passed with the wrong key** because it only asserted
`len(unnamed) == 1` on a single-role fixture; it now asserts the value.

## Also

- Two extra label shapes are now found: the label inside a pipe-delimited cell
  (`Position: … | Company: Acme | Duration: …`) and `Company Name:`. Both were
  silent misses.
- `_experience_section_text` ran twice over the whole document per report and is
  now split once and shared.
- A duplicated explanatory paragraph in `_source_employers` is removed; the first
  copy was the superseded draft of the second and omitted the qualifier the code
  actually implements.

## Known limitation, stated rather than hidden

The labelled-employer reader lives in the audit only, so the reconciler still
cannot see those employers: a shortfall can be **reported but not repaired**.
Teaching the shared extractor in `cvstudio_cv_reconcile` about label-style rows
would fix the parse itself and keep source truth in one place. That is a larger
change to the reconciliation path and is deliberately not attempted here.

## Regression evidence

Eight mutations were introduced, one per fix. Seven fail the suite. The eighth —
removing the "already month-first, nothing to swap" short-circuit — is provably
behaviour-neutral: on a month-first line the swap pattern matches nothing, so the
substitution is a no-op and the check is an optimisation rather than a guard.

One earlier mutation appeared to survive and did not: the shell quoting had
mangled the edit so it never reached the file. Re-applied by line, it fails three
subtests. A mutation that "survives" is checked for having actually applied.

Full suite: **1347 passed, 23 skipped**, plus the two environment-only failures
this container has always had. Node fixtures: **24/24**. `test_cv_date_parity.py`
passes with all 1600+ subtests, confirming the Python/JavaScript date contract is
untouched.
