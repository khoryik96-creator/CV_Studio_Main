# v24.6.411 Year-first dates, and a shortfall that should not ship

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
