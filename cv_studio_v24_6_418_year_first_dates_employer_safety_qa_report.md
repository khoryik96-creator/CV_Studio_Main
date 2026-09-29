# v24.6.411 – v24.6.418 Year-first dates, and a shortfall that should not ship

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
`Company: QRS Digital Sdn Bhd | Industry: Finance`.

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
  reported CV's own first employer — `company: Orbix IT outsourcing sdn bhd(lumen
  bank sdn bhd)` against a parsed `Orbix IT Outsourcing Sdn Bhd` — scored 0.6
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


---

# v24.6.413 The real cause, and a warning that stays on screen

The owner re-ran the reported CV on v24.6.412. The output was unchanged — three
newest employers missing, education rows shown as jobs, every employer shown as
`|` — and no warning appeared. Both earlier versions had been tested against the
wrong input, and the diagnosis above was wrong about where the fault was.

## v24.6.411 and v24.6.412 changed nothing on the real path

The date tests fed `_extract_docx_text_preserve_tables`. The upload route
(`/extract-text`) does not use that helper for this document: it joins each table
row's cells into one line with `" | "`. The date cell therefore reaches the
rewrite as `2025 june- current | Senior Data Engineer`, which is not a line that is
entirely a date, so the line-anchored rewrite left all three untouched. The model
received exactly what it received on master.

**Fixed by anchoring to the cell instead of the line.** A joined row is split on
its `|` separators and each cell that is entirely a date is rewritten; the other
cells and the separators are returned byte-for-byte. A line with no `|` behaves
exactly as in v24.6.412. Driven through the real `/extract-text` and `/parse`
routes on a synthetic document with the same table shape, the model now receives
`june 2025- current | Senior Data Engineer`, and exactly 3 of 176 lines differ
from what the route sent before.

## The AI was not the cause — the app's own reconciliation step was

A perfect, hand-written parse of the reported CV was fed through `/parse` on
master code. **It came out exactly as broken as the owner's output.** The fault
was never the model's structured output.

After the model answers, `_reconcile_work_experience_with_authoritative_table`
rebuilds the work history from the source's own table when it finds one, and
replaces the model's list with it. On this CV the table it found was wrong in
three ways, all in `_extract_authoritative_work_rows`:

- **Education rows were read as jobs.** The pipe-table path had no notion of
  section, so `2014 - 2017 | Diploma …` inside Education became a work row.
- **The company was the separator.** A row shaped `date | title` has no company
  cell, and the borderless-table path took the leading `|` as the company.
- **The year-first rows were dropped** because their dates did not parse, so the
  rebuilt list simply had no entry for the three newest employers.

That rebuilt list — 9 wrong rows — replaced a correct parse.

Fixed, each narrowly:

- A company cell with no letter or digit in it is rejected, so a row is never
  kept with `|` as its employer.
- Rows under an Education / Educational / Academic heading are skipped, until a
  work-history heading or another known section heading ends that section. A
  work table after the education table is still read. An employer named
  "Ministry of Education" inside the work history is still kept.
- The borderless path strips the separator from both ends of the company before
  matching the title.

When the reader cannot produce a trustworthy table it now returns nothing, and the
reconciler steps aside and keeps the model's parse — its established behaviour for
a CV with no table at all. On the reported CV the reader now returns 0 rows
instead of 9 wrong ones.

## The warning was shown for a fraction of a second

The fidelity audit did flag the result. The browser showed it as a toast, and the
very next line showed "Parsed! Generating DOCX…" in the same single toast element,
so the warning was replaced before it could be read.

It is now also written into a banner at the top of the preview, which stays until
the next CV is formatted, and the final toast says "Done — but read the warning
above the preview before sending this CV" instead of "Done!". Batch rows that
finished with a warning carry the same message under the row. The banner is set
with `textContent` and the batch row with `esc()`, so the message cannot inject
markup. Create Profile is deliberately unchanged: it uses the parse only for name,
email and phone and uploads the original file.

## Regression evidence

- **The new reconciler test fails on master's reconciler** and passes on this one
  (`tests/test_cv_label_table_reconciliation.py`, 14 tests, synthetic document
  only — no candidate data).
- **Whole-suite reconciler differential.** Every call the existing suite makes
  into the reconciler was recorded and replayed against master and this branch:
  90 distinct calls, identical inputs, **0 outputs changed**. The only behaviour
  change is on shapes no existing test covered.
- **Whole-suite date-rewrite differential.** The only inputs the cell-anchored
  rewrite changes across the entire suite come from this work's own two test
  files.
- **Real documents.** Of the documents available here, only the reported CV's
  reconciliation changed (9 wrong rows to 0).
- **Mutations.** Twelve mutations across the three fixes, each verified to have
  actually changed the file; all twelve fail the suite. One earlier mutation
  survived because the code it removed was redundant; that code was deleted.
- One regression was caught and fixed during the work: a shared helper added to
  `runtime-core.js` broke the batch lifecycle fixture, which loads
  `batch-format.js` on its own. The helper was removed and the warning is read
  inline.

Full suite: **1359 passed, 23 skipped**, plus the two environment-only tests this
container has always had to skip (antiword binary absent, Windows registry
unavailable). Node fixtures: **25/25**. Launcher line endings match `origin/master`
exactly.

## Not changed, recommended as a follow-up

- If JobAdder auto-upload is enabled, a CV that finished with a warning is still
  uploaded automatically. Pausing auto-upload when a warning is present would be a
  small separate change; it was left alone here so this fix does not alter any
  upload behaviour.
- The reconciler does not reconstruct companies from label-style rows
  (`Company: … | Industry: …`); it steps aside so the model's parse is kept. The
  audit still reads those labels and reports a shortfall.
- The model's parse of the reported CV itself cannot be verified here, because it
  needs a live paid provider call. It has to be confirmed by re-running the CV.


---

# v24.6.414 Review corrections

Ten findings across two reviews of v24.6.413. Nine are fixed in code. The tenth,
real candidate data in the branch's earlier commits, can only be fully fixed by a
history rewrite or a squash merge, and is left for the owner (see the end).

## The table reader (`_extract_authoritative_work_rows`)

- **An education heading was any short line starting with "education" or
  "academic".** "Education Consultant", "Academic Coordinator" and "Education
  Queensland" all switched it on and hid every work row after them. The line now
  has to BE an education heading: "Education", "Educational Background",
  "Academic Qualifications", "Education & Training" and similar.
- **A work table after Education was dropped if its heading was on no list**
  ("POSITIONS HELD", "APPOINTMENTS", "PROFESSIONAL BACKGROUND") — a regression from
  master. Two guards now: a short capitalised heading that is not an education
  line also ends the section, and inside the section only a row that reads as a
  qualification (university, college, diploma, degree, SPM, CGPA…) is set aside.
  A title-case "Positions Held" followed by ordinary work rows is read either way.
- **A company sharing the date cell kept the separator** ("Acme Corp |"), and the
  generic-title fallback split across it ("Beta Holdings | Data" / "Analyst"). The
  company is now stripped of separators whichever way the row arrives, and when
  cells remain the title is the whole last cell. A row with no separator is split
  exactly as before. The two duplicated title loops are now one helper.
- **Three copies of the work-history heading pattern** are now one,
  `_WORK_HISTORY_HEADING_RE`, which the audit imports. The borderless reader's stop
  list gained REFEREE/REFEREES to match the audit. Unused parameters removed.

## The date rewrite

- **"Till Date", "Till Now", "Presently", "until present" and a bare-year end**
  ("2015 June – 2017") were not recognised, so those cells stayed year-first —
  the same current-job case the change exists for. All are now handled. A range
  of two bare years, and a bare year closing a month-first date, are untouched.
- **The docstring contradicted the code** about whole-line versus per-cell
  anchoring. It now states the anchor is the cell, why the line anchor failed, and
  that widening back to the document is the v24.6.411 version that reworded prose.

## The source check (fidelity audit)

- **The label scan stopped at duty lines** such as "Project: Core banking
  migration" or "Summary of duties:", because the stop pattern matched any line
  STARTING with a section word. Labels after the first job were never read and a
  dropped employer went unreported. The label scan now stops only at a line that
  is a heading and nothing else. The bullet count keeps its original scope, so
  its behaviour is unchanged.
- **A bracketed client could stand in for a missing employer.** "Hays Recruitment
  (Petronas)" counted as present because the parse kept the candidate's separate
  Petronas job. A bracketed reading may no longer borrow a parsed employer that
  another source employer already matches under its own name. A bracketed brand
  with no rival still counts.
- **A label and its value in separate cells** ("Company: | Acme", "Company |
  Acme") were not read. They are now; a table header row ("Company | Position |
  Duration") is recognised and names no employer.
- **Hyphenated names were erased.** "Role-Play Studios", "Sector-X Consulting" and
  "Title-Pro Pty" were stripped to nothing because a bare hyphen after "role",
  "sector" or "title" was taken as a trailing label. A trailing label now needs a
  colon or a spaced dash.

## The screen

- **Auto-upload no longer sends a flagged CV.** In the single-CV flow it pauses
  and says so beside the JobAdder box; the Upload button still sends it once it
  has been checked. In a batch the row shows "Not uploaded — check the warning"
  with an "Upload anyway" button, which sends it once. A clean CV auto-uploads
  exactly as before.
- **Blind mode no longer shows employer names.** The source check's warning lists
  the real company names the blind step hides; in Blind mode the banner, the
  batch row and the toast now say the CV was flagged without naming anyone.
  Other warnings, such as a truncated parse, are shown unchanged.
- **Create Profile** now keeps its warning on the file's row, cleared on a re-run.
  The profile is not held: only name, email and phone come from this parse and
  the original file is what gets uploaded.
- **Batch warnings** use role="note" instead of role="alert", so a screen reader
  does not re-announce them every time another file's progress re-renders the
  list.

## Regression evidence

- **Whole-suite replay.** Every distinct input the full test suite feeds the table
  reader, the reconciler, the date rewrite and the source check was captured (300
  inputs) and replayed through master, v24.6.413 and this version, each loaded
  on its own. Against v24.6.413: **0 changed outside this work's own tests.**
  Against master: the reader, reconciler and date rewrite are identical outside
  this work's own tests, and every source-check report is identical apart from
  the empty `unnamed` field added in v24.6.411.
- **Real documents.** Only the reported CV changes (9 wrong rows to 0), as in
  v24.6.413. Through the real upload and parse routes a correct parse of it keeps
  all nine employers with no warning.
- **The new tests fail on v24.6.413** (29 failures) and pass here.
- **Mutations.** 13 back-end and 8 screen mutations, one per fix, each confirmed
  to have changed the file: all 21 fail the tests. Three initially survived
  because another guard covered the same test; a test was added for each so
  every guard is proven on its own.
- Full suite: **1379 passed, 23 skipped**, plus the two environment-only tests.
  Node fixtures: **25/25**. Launcher line endings match `origin/master`.

## Real candidate data in history — owner decision

The current files contain no detail from the reported CV: employer names were
replaced in v24.6.413, and the remaining university name in a comment and a test
is replaced here. The branch's earlier commits (v24.6.411–413) still contain four
real employer names and the university. A history rewrite was prepared but not
run: it rewrites published commits, so it is the owner's call. The simplest safe
path is to merge this PR with **Squash and merge**, which puts only the final,
clean files on master.


---

# v24.6.415 Review corrections

Ten findings on v24.6.414. All ten are fixed. Because v24.6.414 made a flagged CV
hold JobAdder auto-upload, a false warning now has a real cost, so the rule for
this round was: **when the source check is unsure, it claims nothing.** A missed
claim is exactly what master did; a false one holds a correct CV.

## False warnings on correct CVs

- **Referee and personal-details headings.** The label scan read past "REFERENCE
  CONTACTS", "Professional References", "Character Referees", "Referee: Mr Tan"
  and "Personal Details", so a referee's "Company:" was reported missing. The
  parse always leaves referees out, so this warned on every such CV. The scan now
  stops at any line opening with REFERENCE(S)/REFEREE(S), optionally after one
  qualifier, at a personal-details heading, and at any heading in the
  reconciler's own section list (less its work-history headings and
  "achievements", a sub-heading inside a job). A line with a value after its
  colon -- "Project: Core banking migration", "Skills used: Python" -- still does
  not stop it.
- **Column headers read as employers.** "Company | Position Held | Duration" gave
  "Position Held"; "Company Name | Period of Employment" gave "Period of
  Employment". A value made up entirely of column-header words is now ignored.
  Every word has to be one, so "Department of Statistics", "Position Partners Sdn
  Bhd" and "Title Insurance Co" are still read.
- **Placeholder companies reported as unnamed.** A "-" or em dash for a career
  break or freelance work was reported as a separator read instead of a name.
  Only a real separator -- the table pipe in its ASCII, full-width and
  box-drawing forms, or the label colon -- is reported now.

## Missed or dropped employers

- **"Working Experience" and similar headings.** The label scan only started at
  the shared heading pattern, so a CV headed "WORKING EXPERIENCE", "Employment
  Record", "Relevant Experience", "Previous Employment" or "Positions Held" was
  never scanned. The label scan now starts at those too. The bullet count keeps
  the shared heading alone, so its scope is unchanged, and the reconciler's own
  start is untouched -- widening it would let the reconciler rebuild the work
  history of CVs it currently leaves alone.
- **Work rows dropped inside an education section.** Inside Education, any row
  containing "school", "academy", "foundation", "institute", "certificate" or a
  bare "BA"/"MA" was set aside, so "Acme Foundation | Program Manager" after an
  unlisted heading vanished. Only a row that names a qualification is set aside
  now: bachelor, master's, diploma, degree, PhD, SPM, CGPA, MBA, "foundation in",
  "certificate in" and the like. Institution words only stop a line such as
  "NORTHWIND UNIVERSITY" from being taken as the next section's heading.
  "Positions", "appointments" and "assignments" now also end the section.
- **Placeholder rows dropped by the reconciler (found in this round's own
  checks).** v24.6.413 made the table reader refuse any company cell with no
  letter or digit. That covered "-" too, and because the reconciler replaces the
  work history with the rows it reads, a "Jan 2020 - Dec 2021 | - | Engineer" row
  -- a career break -- disappeared from the output where master kept it. The
  check is removed. It is no longer needed for the reported bug: every reader
  now strips the "|" separator, and an empty company is refused as it always was.
  Rows with "-", an em dash or "N/A" now come out exactly as on master.

## Other

- **Dates:** "2025 Jun. - current" became "Jun 2025. - current". The month's full
  stop or comma now travels with it: "Jun. 2025 - current".
- **One warning helper:** batch mode now uses the single-CV helper
  `cvParseWarningText` instead of a copy, so the Blind-mode wording cannot drift
  between the two. It is only called when there is a warning, so a batch run
  without one needs nothing from `cv-format.js`.
- **Simpler employer matching:** each source employer's direct matches are
  computed once; the old version recomputed them per employer (quadratic).
- **Dead code removed:** `_employer_name_variants`, and `_employer_is_present`,
  which nothing used after the simplification.
- **One stop list:** the reconciler's work-history stop words are one shared tuple.
  The bullet count builds its list from it plus its own trailing sections, and
  the resulting pattern matches exactly the same lines as before (a test pins
  that). The project-block reader keeps its own list on purpose -- it has to stop
  at the work-history headings that follow a projects block and must never stop
  at a PROJECT line -- and says so where it is defined.

## Regression evidence

- **Whole-suite replay:** every distinct input the full suite feeds the table
  reader, the reconciler, the date rewrite and the source check was captured (404
  inputs) and replayed through master, v24.6.414 and this version, each loaded on
  its own. **Against v24.6.414: 0 changed outside this work's own tests. Against
  master: 0 changed outside this work's own tests** -- the source-check reports
  are identical apart from the empty `unnamed` field v24.6.411 added.
- **Real documents:** unchanged from v24.6.414. The reported CV's wrong table rows
  stay at 0 (master: 9), the source check still finds the same 8 labelled
  employers, and a correct parse through the real upload and parse routes keeps
  all 9 employers with no warning.
- **Mutations:** 16 new ones, one per fix, each confirmed to have changed the
  file -- all fail the tests. The earlier rounds' mutations were re-run: all
  still fail the tests. Two earlier guards had lost their own test because this
  round's narrower education check now covered the same cases; a test was added
  for each so both are proven independently again. The only earlier mutation
  that no longer applies is the batch copy of the warning helper, which was
  removed on purpose.
- Each new education test first proves the row IS read outside an education
  section, so its empty result inside one is the guard, not the date format.
- Full suite **1396 passed, 23 skipped**, plus the two environment-only tests.
  Node fixtures **25/25**, the existing batch lifecycle test unchanged. Launcher
  line endings match `origin/master`.


---

# v24.6.416 Review corrections

Ten findings on v24.6.415. All ten are fixed. Four were regressions against
v24.6.414 introduced by v24.6.415's own narrowing; those are corrected without
bringing back the problems v24.6.415 fixed.

## Table reader

- **Education rows read as jobs (regression).** v24.6.415 set aside only rows
  naming a listed qualification, so "Anna University | B.Tech", "University of
  Malaya | B.A Economics", "Delhi University | LLB" and "Sekolah Menengah … |
  Kuala Lumpur" under Education became work rows. Now a row is set aside if it
  names a qualification (B.Tech, M.Tech, B.Com, BBA, LLB, LLM, B.Ed, MBBS and
  "B.A" without the trailing dot added), or names an institution without naming
  a job. "Contoso Academy | Trainer" and "Acme Foundation | Program Manager" are
  still kept; "Fabrikam College | BA" under Education is now read as a degree.
- **Separator-only companies accepted (regression).** Removing the guard in
  v24.6.415 let ":", "│" and "｜" through, because only the ASCII "|" is stripped
  from a cell. `add_row` now refuses a company that is only separator characters,
  using one pattern shared with the source check. A "-", em dash or "N/A"
  career-break row is still kept exactly as master keeps it. The comment that
  claimed separators never reached `add_row` is gone.
- **"Leadership Positions" inside Education ended it (regression).**
  "Positions", "appointments" and "assignments" now end an education section only
  as the whole heading ("Positions Held", "Appointments").

## Source check

- **An early "Professional Background" heading hid the work history
  (regression).** The label scan started at the first matching heading, often
  the profile near the top, and stopped at the next section. It now reads every
  span from a work-history heading to the next stop, and "Professional
  Background" / "Career Background" no longer start a scan; with no work-history
  heading at all it still claims nothing.
- **Value lines ended the scan.** "Training: 2019", "Languages: 3" and "Reference
  No: 4411" matched a heading once letters alone were compared. A line with a
  value after its colon no longer matches the section list, and "Reference
  No/Number/Code/ID" is excluded from the referee rule. Figures alone do not
  rule a heading out: "AWARDS 2021" still ends the scan, because reading on into
  another section is what reports a false missing employer.
- **Real employer names read as column headers.** A value is now treated as a
  header only when it sits in the next cell ("Company | Position Held"), never in
  the label's own cell ("Company: Department of Information"), and "state",
  "total", "information" and "info" are out of the header words.
- The stale comment that still listed "-" as a reported separator, and a dead
  substitution before the section-key comparison, are removed.

## Screen

- **Batch mode no longer depends on `cv-format.js` being loaded.** It uses the
  single-CV wording when that helper exists; loaded on its own, a warned file
  still finishes (no ReferenceError), is still held from auto-upload, and in
  Blind mode shows a notice that names no one. The Blind-mode rule itself lives
  only in `cvParseWarningText`.

## Regression evidence

- **Whole-suite replay:** 473 distinct inputs the full suite feeds the table
  reader, reconciler, date rewrite and source check, replayed through master,
  v24.6.415 and this version: **0 changed outside this work's own tests against
  either**, the source-check report identical to master apart from the empty
  `unnamed` field.
- **Real documents:** unchanged from v24.6.415 — the reported CV's wrong rows stay
  at 0 (master 9), the source check finds the same 8 employers, and a correct
  parse keeps all 9 with no warning.
- **The new tests fail on v24.6.415** (28 failures) and pass here.
- **Mutations:** every fix this round broken on purpose and confirmed caught,
  including the batch fallback. Three initially survived because another guard
  covered the same test (degree words, the background heading, the value-line
  rule); an isolating test was added for each. A fourth showed the "no figures"
  half of the value-line rule had no test; on review it was also wrong for
  "AWARDS 2021", so it was removed rather than tested. Every earlier round's
  mutations were re-run: none survive.
- Full suite **1408 passed, 23 skipped**, plus the two environment-only tests.
  Node **25/25**. Launcher line endings match `origin/master`.


---

# v24.6.417 Review corrections, and a guardrail registry

Ten findings on v24.6.416, all fixed. Five were cases v24.6.416 broke, and the
owner asked why every round kept producing new ones. This version also adds the
answer: a written rulebook and one test that runs every case from every round.

## Why each round found new bugs

These rules guess a CV's structure from plain text, and every rule has two ways
to be wrong. Tightening one to stop a false warning usually loosens it somewhere
else. Each round was checked against every case written down so far, and all of
them passed. The new findings were almost all cases that had never been written
down: "Academic Appointments" as a heading, "Referee #1", a "Total Experience"
column. Checking against the existing tests could not catch a case nobody had
written.

## The registry

- **`CV_SOURCE_CHECK_GUARDRAILS.md`**: every rule in plain language: what it
  does, why, and the principle behind all of them. When unsure, the table
  reader returns fewer rows (the AI's reading is kept) and the source check
  reports nothing (auto-upload isn't held). It also sets out how to change a
  rule: add the case first, and never edit or delete an existing case without
  the owner's agreement.
- **`tests/fixtures/cv_guardrail_cases.json`**: 208 cases, every scenario from
  all five review rounds plus the reported CV's own shapes, each tied to a rule.
- **`tests/test_cv_guardrail_cases.py`**: runs all of them, and fails if a case
  cites a rule the rulebook doesn't describe, or a described rule has no case.

Run against earlier versions, the registry fails **154 cases on master, 77 on
v24.6.414, 34 on v24.6.415 and 20 on v24.6.416**, and none on this version. Had it
existed from the start, every regression in this series would have failed a
test before review.

## The ten fixes

- **Academic jobs dropped as education.** "Academic Appointments", "Professional
  Appointments", "Research Positions" and similar now end an education section
  as whole headings. Fellow, Postdoctoral, Scholar, Demonstrator, Staff and
  Faculty count as job titles.
- **"Referee #1" and "Reference No. 1" no longer read on.** The exception for a
  reference number inside a job now needs its colon ("Reference No: 4411").
- **No reopening inside referees.** A later span only opens at a real heading (no
  value after a colon, a few words at most), and nothing after a referees or
  personal-details heading is read at all.
- **Header words restored.** "Total Experience", "State" and "Information" are
  column headings again in the next cell. The label's own cell is never tested,
  so "Company: Total" is still a name.
- **"LEADERSHIP POSITIONS" in capitals** no longer ends Education. A capitalised
  line naming part of an education section (positions, activities, thesis,
  societies…) isn't taken as the next heading.
- **"Career / Professional Background" start the scan again.** Since every span
  is read, an early profile under them costs nothing.
- **Institution names carrying job words.** The job word is read from the title
  cell only, so "Institute of Chartered Accountants | Kuala Lumpur" stays
  education. "Associate of Arts", CIMA and ACCA are qualifications.
- **One job-title list.** The borderless reader's title pattern and the education
  rule share one list; the resulting pattern is character-for-character the
  same as before.
- **One section walker.** The bullet count and the label scan use one walker, and
  the bullet count's section is identical to master's.
- **No second copy of the Blind-mode rule.** Batch calls `cvParseWarningText`
  directly, as it already calls other page helpers. The page loads
  `cv-format.js` before `batch-format.js`, and a test pins that order. The batch
  test harness stubs the helper like its other page globals.

## Regression evidence

- **Whole-suite replay:** 586 distinct inputs replayed through master, v24.6.416
  and this version: **0 changed outside this work's own tests against either.**
- **Real documents:** unchanged — the reported CV's wrong rows stay at 0 (master
  9), the same 8 employers are found, a correct parse keeps all 9 with no
  warning.
- **Mutations:** every fix this round broken on purpose and caught. Four
  initially survived because another rule covered the same case; a registry case
  isolating each was added. Re-running earlier rounds' mutations exposed a
  duplicate referee check left dead by this round's walker; it was removed so
  each rule is checked in one place, and removing either remaining check is
  caught.
- Full suite **1415 passed, 23 skipped**, plus the two environment-only tests.
  Node **25/25**. Launcher line endings match `origin/master`.


---

# v24.6.418 Keep the bracketed employer name, the CGPA label and the majors

The owner re-ran the reported CV on v24.6.417. All nine employers, their dates and
their names came out right. Three smaller losses remained, all from the
provider's reading, and the owner asked for all three to be fixed.

## What was lost

1. **The bank in the current employer's name.** The source labels it
   `company: <outsourcer> sdn bhd(<bank> sdn bhd)`; the provider returned only the
   part before the bracket, so the CV no longer said which bank the candidate
   works at.
2. **The CGPA label.** The source says `CGPA 2.0 / 4.0`; the provider returned
   `2.0 / 4.0`, and the Word file prints the field as given.
3. **The majors.** Two qualifications carry a `Major` line in the source.
   Education had no field for it, so it had nowhere to go.

The instructions already told the provider to keep employer names and the CGPA
"exactly as written". It didn't, so instructions alone are not enough. Each
detail is now also restored from the source after the parse, and the
instructions are clarified too.

## The fix

- **`_restore_labelled_company_qualifiers`** (reconciler, run in `/parse` before the
  casing pass): when a parsed employer is exactly the part before a bracket in a
  "Company:"-labelled source name (the same words, ignoring legal forms the
  instructions let the provider drop), the bracket is appended, and to the
  candidate's Current Company if it held the same name. A bracket with figures,
  a different company, a name that already has a bracket, or two different
  brackets for one name are all left alone.
- **`_recover_education_source_labels`** (output normaliser, only when the source
  is available, i.e. in `/parse`): reads the lines under the entry's institution,
  up to the next line with a year or a section heading. A CGPA with no label of
  its own gets the source's label when the source writes it right before the
  same figure. A `Major`, `Major:`, `Major - `, `Majoring in` or `Major | value`
  line fills a new `major` field. Two different labels or majors, or a sentence
  such as "Major in the arts club", change nothing.
- **`major`** is a new education field: in the parse instructions, printed by
  `generate.js` as "Major: …" under the degree, and shown in the preview.
- The label reader (`_source_labelled_companies` and its patterns) moved from the
  fidelity audit into the reconciler, unchanged, so both can use it. The audit
  imports it from there.
- No real candidate data was added: the examples in the instructions, comments
  and tests are synthetic.

## Guardrails

Three new rules, F1–F3, in `CV_SOURCE_CHECK_GUARDRAILS.md`, with 32 new cases
(240 in all).

## Regression evidence

- **Real CV end to end:** the source through `/extract-text`, `/parse` (the
  provider's actual losses reproduced) and `/generate-docx`. The Word file shows
  the outsourcer's name with the bank in brackets as the job heading and Current Company,
  "CGPA 2.0 / 4.0", and "Major: IT and management" and "Major: Science" under their
  qualifications. The restored name is recognised by the source check.
- **Whole suite, recorded:** the two restore steps ran 129 times across the full
  suite. Outside this branch's own tests they changed nothing. The only other
  changes were in this branch's own synthetic CV test, whose CV has a "Major"
  line, and those tests still pass.
- **Replay:** 600 distinct inputs to the table reader, reconciler, date rewrite
  and source check: 0 changes against v24.6.417 in any test (moving the label
  reader changed nothing), and 0 against master outside this work's tests.
- **Mutations:** every guard in the three restores and the Word "Major" line was
  broken on purpose and caught. Three guards first survived because another
  guard covered the same case; a case isolating each was added. One guard was
  also widened: the CGPA label is now added to any value without a label of its
  own ("3.5 out of 4.0"), not only a bare figure.
- Full suite **1424 passed, 23 skipped**, plus the two environment-only tests.
  Node **25/25**.
