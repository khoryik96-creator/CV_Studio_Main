# v24.6.427 A job title above an "Employer | Place | Dates" row

Branch: `claude/pr157-chatgpt-fix-zke4cy`, from merged master `bb3b606` (v24.6.425).
v24.6.426 is taken by the unmerged PR #214 crawler branch.

## The reported CV

A real CV wrote each job like this (names here are synthetic):

```
PROFESSIONAL EXPERIENCE
General Manager – Head of Consumer Electronics
Acme Holdings | Kuala Lumpur, Malaysia | Apr 2019 – Dec 2024
• ...
Product Marketing Manager – Audio and Imaging
Acme Holdings | Kuala Lumpur, Malaysia | Apr 2014 – Mar 2019
...
Marketing Manager
Contoso Media – Northwind Books| Kuala Lumpur, Malaysia | Aug 2002 – Apr 2007
EDUCATION
• Master of Management – Northwind Business School, graduated 2007.
```

The formatted CV came back with one employer, "Kuala Lumpur, Malaysia", holding the
candidate's self-employment and three roles titled with the employer's name. Each
next job's title was glued onto the last bullet of the one before. The current
company was "Kuala Lumpur, Malaysia". "Contoso Media – Northwind Books" was split at
the dash, and the education years were missing.

Replaying the real extraction with a **perfect** provider parse gave the same
result, which shows the break was deterministic. The work-row reader split the row
on its first separator: the employer became the title and the place became the
company. It also treated the title line as a wrapped bullet. The reconciler then
rebuilt the work history from those rows. The education years were missing because
the AI left them out and nothing put a stated year back.

## The fix

**Rule R7 (work-row reader), `cvstudio_cv_reconcile.py`:**

1. **A place cell is recognised.** When the last cell before the dates is a
   place, the employer is the cell before it, taken whole ("Contoso Media –
   Northwind Books"). Places are listed countries, states and cities, "City,
   Country" or "Remote" (`_cv_cell_is_place`). A cell with an organisation word
   is an employer: "Singapore Airlines", "Acme Sdn Bhd, Malaysia".
2. **The title is the line directly above.** It must be short, start with a
   capital and name a job. It must not be a bullet, a date, a heading, a
   sub-heading ("EXECUTIVE EXPERIENCE", "Consultant Roles"), a line with cells or
   a sentence. That line starts the next job, so it is never glued onto a bullet.
3. **Same-line titles still work.** "Engineer – Acme | Singapore | dates" and
   "Engineer | Acme | Singapore | dates" drop the place and read as before.
4. **When unsure, no row.** No title above, a job title where the employer should
   be, or cells with no clear title all produce no row. Any reader also refuses a
   company that is only a known place. With fewer rows the reconciler keeps the
   AI's reading.

**Rule F4 (education), `cvstudio_cv_normalize.py`:** when the AI leaves an
entry's date empty, a year stated on the institution's own line fills it. The
forms read are "graduated 2007", "graduated in June 2007", "Graduation: 2007"
and "Class of 2007". If the same school appears for two qualifications, only
the line naming this degree counts. A date the AI gave is never replaced. Two
different years, "graduates of …", or a year that doesn't follow the word
directly all change nothing.

## The six steps

1. **Cases first.** 47 new cases in `tests/fixtures/cv_guardrail_cases.json`: 35
   for R7 and 12 for F4. The rows test now also checks titles and bullets when a
   case gives them. On master, 37 of the 47 fail. The other 10 pin behaviour
   that must not change: a row without a place, an employer with a country after
   it (in both readers), and the seven F4 cases where nothing is restored. The new
   `tests/test_cv_title_above_place_rows.py` sends a synthetic CV of the reported
   layout through `/parse` and `/generate-docx`. All 5 of its tests fail on master
   and pass now.
2. **Existing cases.** All earlier cases pass unchanged.
3. **Whole-suite replay.** Every call during the full suite was recorded on the
   old and new code: 361 reader calls, 26 reconciler calls, 79 education
   restores and 107 final normalize calls. 45 outputs differ. 37 are new cases
   and 8 are the new end-to-end test. None of the 107 normalize outputs shared
   with master changed.
4. (P1 only; not affected.)
5. **Old vs new on the repository.** The reader ran on 2,320 windows of 50 lines
   taken from every tracked text file. The education restore ran on every
   repository line that mentions graduating. Every difference (28 windows, 11
   lines) comes from the new cases, or from the new code comment that quotes a
   case.
6. **Deliberate breaks.** 26 breaks were tried, one for each guard. The first
   round let 7 through. For each of those a case of its own was added, and one
   gap was fixed: a sub-heading such as "EXECUTIVE EXPERIENCE" had been read as
   a title. After that, 25 of the 26 are caught. The remaining one reads the
   whole education block instead of the institution's line. It cannot change
   the result, because a block ends at the first line with a year, so the later
   lines never hold one.

## Reported CV, locally

The real extraction replayed with the corrected code gives the following. It was
run locally only; no real data is in the repository.

- Self-employed (Independent Marketing Consultant).
- The electronics employer with three roles, each with all of its bullets and no
  glued titles.
- The dash-joined book employer.
- The dash-joined film school.
- Both education years restored.
- Current company "Self-employed" and no warning.

## Full regression

- Python: 1458 passed, 23 skipped (the usual deselections), 6648 subtests.
- Node: all 27 `tests/*.js` pass.
- Launcher CRLF counts match master (242 / 89 / 37).

No release or native protected build is produced by this work.
