# v24.6.419 – v24.6.420 Salary never reaches the Summary box

Branch: `claude/pr157-chatgpt-fix-zke4cy`, from merged master `56dca18` (v24.6.418).

The owner asked for a guardrail so the generated summary never mentions salary.
CVs often state the candidate's current salary, a salary per job and an expected
salary. The formatted CV is sent to clients, so none of that may appear in its
Summary box.

## What was there before

- The CV Summary instructions (`cvSummaryPrompt`) had no rule about salary at all.
- Nothing checked the summary afterwards. The parse instructions already omit
  salary from the parsed CV, but the summary is generated separately, from the
  whole CV text.

## The guardrail

1. **Instructions.** `cvSummaryPrompt` now says never to mention the candidate's
   salary or pay in any form (current, last drawn, expected or asking salary,
   remuneration, compensation, package, bonus, commission, allowances, EPF, or
   whether pay is negotiable), even when the CV states it.
2. **Browser.** `cvSummaryStripPay` runs inside `summaryBulletLines`, which every
   AI summary passes through, so the preview, the Summary tab and copied text are
   clean.
3. **Server.** `_cv_strip_pay_from_summary` runs again before the box is written,
   on both `/generate-docx` paths: Format CV (JSON) and filling an uploaded DOCX.
   A summary that bypassed the page, or was made before this rule, still can't
   put a salary into a Word file.

**The rule:** a sentence is removed when a pay word sits beside an amount, or
when it speaks of the candidate's own pay, with or without an amount ("expected
salary", "last drawn", "negotiable", "open to discuss remuneration"). Only that
sentence goes. The rest of the bullet stays, and a bullet left empty is dropped.
The candidate's work is not their pay, so "expertise in compensation and
benefits", "gained knowledge of salary calculation", "processed salaries for
1,200 employees", "managed a USD 5 million budget" and "developed payroll modules"
are kept. A year is not an amount.

The two copies are the same patterns. Rule P1 in `CV_SOURCE_CHECK_GUARDRAILS.md`
has 35 cases in `tests/fixtures/cv_guardrail_cases.json`, run against the Python
copy (`tests/test_cv_guardrail_cases.py`) and the browser copy
(`tests/test_cv_summary_salary_parity.js`).

## Regression evidence

- **Both Word-file paths:** `tests/test_cv_summary_salary_docx.py` sends a
  summary that states pay through the real `/generate-docx` routes. No amount or
  pay phrase reaches either document, and the non-pay text in the same bullets
  survives.
- **Whole suite, recorded:** the server filter ran 57 times across the full
  suite. Outside the new tests it changed no summary.
- **One regression caught and fixed:** `tests/test_long_cv_output_corrective.js`
  loads `summaryBulletLines` on its own and failed once it depended on the new
  filter. The filter's patterns now live inside its two functions, those two are
  added to that test's load list, and a pattern with quote characters is written
  with `\x22`/`\x27` so that test's source reader parses it. The same test passes
  unchanged otherwise.
- **Mutations:** each part broken on purpose and caught. That covers both server
  paths; the own-pay, amount, headcount, keyword-needs-amount, sentence-level
  and year rules in both copies; the browser hook; and the instruction. One
  (the year rule) first survived; a case isolating it was added.
- Full suite **1429 passed, 23 skipped**, plus the two environment-only tests.
  Node **26/26**. Launcher line endings match `origin/master`.


---

# v24.6.420 One filter, a narrow rule, and no silent loss

Nine review findings on v24.6.419, all confirmed and all fixed. Most came from
one design mistake: the rule was written twice, in Python and in the browser,
and matched pay *words* rather than statements of the candidate's pay.

## One filter, on the server

The browser copy is gone. The two CV Summary callers send
`strip_candidate_pay: true` to `/generate-ai`, which filters the provider's text
before returning it, keeping each line's bullet marker. The browser only ever
receives filtered text, so its preview, the Summary tab and copied text match
the Word file. That resolves four findings:

- **Safari:** the browser copy used a regex lookbehind, which Safari before 16.4
  rejects while parsing, taking down all of `candidate-summary.js`. No page
  script now uses lookbehind, and a test enforces it.
- **Unicode disagreement** between the two copies: there is one copy.
  Matching runs on an NFKC-normalised copy, so full-width digits count as digits,
  and a currency code needs no word boundary before it.
- **Drift and per-sentence regex building:** one module-level compiled pattern.
- **Blind preview vs Word file:** `/blind` now filters a promoted source
  About / Summary section before the provider sees it, so the blinded preview and
  the Word file carry the same summary. `/generate-docx` keeps its net on both
  paths.

## A narrow rule

Only a statement of the candidate's **own** pay is removed:
- a pay term followed by an amount: "Salary: RM 17,000", "Salary 2000", "CTC of
  12 LPA";
- an amount followed by a pay term: "RM16,000 expected salary";
- pay talk with no amount: "expected salary", "salary is negotiable";
- lakhs per annum, or earnings, bonus, commission or allowance per period.

A pay word on its own is the candidate's work and is kept. Every false positive
from the review is now a keep case, among them "negotiated compensation packages
for 40 executive hires", "minimum wage legislation", "salary range
benchmarking", "the current release package", "ISO 9001 … payroll salary
processing", "10k users", "allowances for 3000 expatriates", "commissions
revenue", and "saved RM 2M in salary costs". A plain figure after a pay term
needs three or more digits and must not count people.

The formats the review found missed are now removed: "CTC of 12 LPA",
"Expecting 18 LPA", "Salary 2000", full-width "RM８０００", and digits in other
scripts.

## No fragments, no false failures

- **Sentence splitting** knows abbreviations ("Sr.", "B.Sc.", "Sept.") and
  removes by semicolon clause within a sentence. "Promoted to Sr. Manager with
  current salary RM12k." is removed whole, not left as "Promoted to Sr.".
- **A summary that was all pay** is not a provider failure. `/generate-ai`
  reports `summary_pay_removed`. The page shows "The CV Summary only described
  the candidate's pay, which is never included", and doesn't record a failed
  paid call. A genuinely empty answer is still recorded as before. The
  uploaded-DOCX route gives the same plain message instead of "No CV Summary
  bullets provided".
- A non-text item such as `0` is no longer dropped.

## Regression evidence

- **Other callers of `/generate-ai`** (Blind JD, Company Profile and the rest)
  don't send the flag, and their text is returned byte for byte. A test pins it,
  including that only `true`, not any truthy value, turns the filter on.
- **Whole suite, recorded:** the filter ran 103 times across the full suite and
  changed nothing outside the new tests. The two existing test files the
  previous version had to edit (`test_long_cv_output_corrective.js`, and the
  batch harness earlier) are back to exactly what is on master.
- **Cases:** rule P1 now has 73 cases, every example from both reviews,
  including text-level cases for line markers.
- **Mutations:** every rule branch, the NFKC step, abbreviation handling, clause
  handling, the three server hooks, the DOCX message, the two request flags and
  the pay-only handling were broken on purpose and caught. Four initially
  survived. Three had no isolating case, and one was a weak mutation. Cases were
  added and the mutation redone. One flag (ASCII-only matching) was removed:
  it only existed to keep the deleted browser copy in step, and it let
  other-script digits through.
- Full suite **1435 passed, 23 skipped**, plus the two environment-only tests.
  Node **26/26**. Launcher line endings match `origin/master`.
