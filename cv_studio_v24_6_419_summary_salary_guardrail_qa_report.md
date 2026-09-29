# v24.6.419 Salary never reaches the Summary box

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
