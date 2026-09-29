# v24.6.419 – v24.6.423 Salary never reaches the Summary box

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

## v24.6.421 — ten further review findings

**Missed pay, now removed**
- **Markdown bold.** The summary is told to bold key phrases, and "**Salary:** RM
  17,000 per month." or "salary of **RM 17,000**" got through. Matching now runs on
  a copy without emphasis markers. The kept text is unchanged.
- **Other ways of writing a period.** "RM 15k/month", "/mo", "/mth" and "/yr" were
  missed, and so was "earning approx. RM 8,000 per month", where the full stop in
  "approx." ended the search. The text is already one sentence or clause, so a
  full stop inside it is an abbreviation.

**Work that was wrongly removed, now kept**
- **Years.** "Led compensation from 2018 to 2022", "between 2019 and 2021" and
  "compensation - 2019 redesign project" were removed.
  - A plain figure after a pay term now counts only when it ends the sentence, or
    is followed by a pay period, a currency or a pay word such as "net" or
    "excluding".
  - A year-like figure is held to that strictly. Any other plain figure may also
    be followed by a comma or "and".
  - "Salary 2000." is still removed.
- **Other people's pay.** "Advised on salary expectations of new hires" and
  "Salary expectations were benchmarked for 40 roles" were removed. Pay talk with
  no amount is now someone else's, and kept, when:
  - it is followed by "of", "for", "across", "among" or "from";
  - it is followed by a reporting verb ("were benchmarked");
  - it is followed by a work noun ("data", "dashboards");
  - it follows other people's possessive or a work verb.

  "Candidate's salary expectations are negotiable" (Blind wording) is still
  removed.
- **The organisation's money.** Examples: "RM 5M salary and benefits budget", "RM
  2M in salary and overtime costs", "2k salary records", "total package of 1,500
  SKUs". The budget and cost check now looks up to three words ahead, and knows
  records, slips, runs, claims and similar words.

**No silent loss, no lost cost**
- **Format and Batch.** A pay-only automatic summary no longer aborts the run and
  throws away the paid parse. The run carries on with an empty Summary box, a
  warning explains why, and the summary's cost is counted with the run.
- **Summary tab.** A pay-only answer's cost is recorded as a summary before the
  message is shown.
- **An intro line left over.** "Here is the summary:" followed by a single pay
  bullet no longer becomes the summary. If every bullet line was pay, the server
  returns empty text.
- **The preview.** `/parse` filters the summary as well, so the preview matches
  the Word file.
- **`/generate-docx` (JSON).** A summary that was all pay is now refused with the
  same message as the uploaded-DOCX path, instead of an empty box.

**Tidy-ups**
- Each clause is evaluated once, not twice.
- `/generate-ai` shares one helper for joining and replacing the provider's text,
  used by both the anonymised summary and the pay filter.

**Regression evidence**
- **Cases.** 35 new P1 cases, one for every example in the review, including
  three text-level cases. The case file only gained lines: no existing case was
  changed.
- **Old rule against new rule** on every sentence in the repository's code, tests,
  fixtures and docs (29,705 strings). 27 differ, and every one is a review
  example.
- **Whole-suite recording.** The filter ran 142 times and changed nothing outside
  the two salary test files.
- **Mutations.** Eleven were made, one per fix (markup, periods, year guard,
  after/before context, budget look-ahead, plain-figure tail, intro-only, abbreviation
  stop, `/parse` hook, JSON refusal). All eleven were caught.
- **Full suite:** 1438 passed, 23 skipped, plus the two known environment-only
  test groups. **Node:** 27/27.

## v24.6.422: twenty findings from two more reviews

Most of the findings came from one cause. The rule removed any sentence with a
pay word and an amount, but a summary also describes the candidate's work, and
much of that work is about pay (HR, payroll, recruitment, sales). The rule was
rebuilt around one question: is there a clear sign that this is the
candidate's **own** pay?

**The rule**
- **Always removed:** "my" or "candidate's", or current / expected / asking /
  last-drawn / previous, before a pay word and an amount.
- **Removed unless the sentence describes work:** a pay word and an amount, and
  the other ways of stating pay. A sentence describes work when:
  - it opens with a work verb from an explicit list, so "Managed", "Placed" or
    "Oversaw" count but "Seasoned" and "Earned" don't;
  - it names the organisation's money ("budget", "AUM", "procurement");
  - it names the people the money is for ("for 300 staff", "to the sales team",
    "for the group", "across APAC").
- **Dates:** a year after "from" or "since" is a date ("Head of Compensation
  from 2019").
- **Words that no longer count as pay:** "Paid" and "making" count only at the
  start and right before the amount, so "paid social spend" and
  "decision-making" are work. "Package requirements" is no longer pay talk.
  "Drawing up" is not drawing pay.
- **Newly caught:**
  - "Last drawn RM 9,000", "Asking RM 9,000", "Expected: RM 9,000";
  - "RM 9,000 expected", "RM 9,000 / month";
  - "Salary: negotiable", "Salary - negotiable", "Salary: 5,500 ringgit";
  - "Current salary (basic): RM 6,500", "Expected salary for this role: RM 9k";
  - "Salary cut to RM 5k", "Current salary approx. RM 9,000". The last one was
    missed before because of a word-boundary quirk after the full stop.

**Sentences and formatting**
- **Sentence ends** are now found:
  - after closing bold ("**Expected salary RM 9k.** Available");
  - after a figure ("a team of 8.", "by 5.5%.", "GPA of 3.8.");
  - after "Sdn Bhd.", "Ltd.", "etc." and "p.a.".

  The sentence before the pay sentence is no longer lost with it.
- A "**" left without its partner by a removal is dropped.
- A summary item that isn't text is returned untouched, instead of as a piece
  of its Python form.
- **Numbered provider lists** ("1.", "2)") are list lines. An intro line left
  after every numbered item was pay no longer becomes the summary.

**Nothing silent, nothing blocked**
- **Every removal is shown.** `/parse` and `/blind` return
  `summary_pay_removed`, and `/generate-docx` sends `X-CV-Summary-Pay-Removed`.
  - In Format and Batch, the note joins the source-check warning: above the
    preview, on the batch row, and holding JobAdder auto-upload.
  - The Summary tab shows it under the summary.
  - The same applies to a pay-only automatic summary, which previously showed
    only a toast that was replaced at once.
- **`/generate-docx` (JSON)** no longer refuses the whole CV over a summary that
  was only pay.

**Regression evidence**
- **Guardrail cases:** rule P1 has 344 cases. The case file only gained lines;
  no existing case was changed.
- **New test file** `tests/test_cv_summary_salary_generated.py`:
  - 15,488 generated ways of stating one's own pay are all removed;
  - 6,400 generated pieces of pay-related work are all kept;
  - over every case plus 2,000 random combinations with bold and semicolons,
    running the filter again changes nothing, the provider-text and bullet paths
    agree, and no lone "**" is left.
- **Old rule vs new rule** on every sentence in the repository (29,993 strings):
  16 differ, and every one is a review example or an intended fix.
- **Whole-suite recording:** all three filter entry points were watched (697
  calls), and nothing changed outside the salary test files.
- **Deliberate breaks:** 37 in total, covering every rule part, the splitter,
  the numbered lines, the bold balance, the non-text items, the route reports,
  the header, and the page's warning, hold and cost handling. All were caught.
  Six needed a new isolating case first, and one exposed a real bug: "for
  the next role" never counted as the candidate's own. That is fixed.
- **Existing page tests** are unchanged. The new warning code only runs when
  pay was actually removed, so every existing flow behaves exactly as before.
- **Full suite:** 1442 passed, 23 skipped, plus the known environment-only
  tests. **Node:** 27/27.

**What this can't promise.** No text rule can be perfect. A new phrasing may
still be misread. The design limits the damage: a removal is always visible and
holds auto-upload, so a mistake is seen before the CV is sent, and the export
is never blocked. Every new phrasing found goes into the generated lists.

## v24.6.423: ten findings from one more review

**Pay that still got through**
- **Clauses:** a clause next to a pay clause went through on its own ("Current:
  RM 9,000; Expected: RM 11,000", "…; RM 1,500 allowances", "…; plus 2 months
  bonus"). In a sentence that states pay, a clause carrying an amount or
  continuing the pay now goes with it, unless it describes work. "Current: RM
  9,000" is also caught by itself now.
- **Look-alike work phrases:** "across base, bonus and allowances", "for the
  team lead role" and "for 12 LPA" were read as work. They are pay.
- **New ways of stating pay:**
  - "The candidate / he / she is paid RM 9,000", "They are paid RM 9,000";
  - "Receives / Makes / Gets RM 9,000 monthly";
  - "Seeking RM 12k", "Asking for RM 10k";
  - "On a package of RM 150k".
- **Non-text summary items** skipped the filter, but the Word file writes them
  as text. One that states pay is now dropped whole. It is never edited.

**Real content that was removed**
- **Short sentences before pay:** "Proficient in Python and C.", "Based in the
  U.S." and "Worked at Acme Co." were lost with the pay sentence after them. A
  single letter, a dotted token, "Co." or a month now ends a sentence when the
  next sentence states pay on its own. "Sr.", "Dr.", "Sdn." and a leading list
  number never do.
- **Currency inside words:** "PHP 8" and "Form 16" were read as money. A letter
  code must now be a word of its own, followed by three or more figures or a
  unit.
- **"their salary":** "negotiated their salary of RM 15k for placed engineers"
  was removed. "his", "her" and "their" alone no longer prove it's the
  candidate's own pay, and someone else's pay the candidate worked on is work.
  "His salary is RM 14k" is still removed.

**Warnings**
- **Uploaded-DOCX path:** it now sends the same removal header, and the page
  warns after the saved message. It still says so when nothing is left, since
  filling the Summary is its only job. The formatted CV is never refused.
- **Stale parse note:** the parse's note no longer shows, or pauses
  auto-upload, when that summary was replaced by a linked or automatic one.
- **Count:** it is now of sentences, not clauses.

**Regression evidence**
- **Cases:** 55 new P1 cases, including every review example, for 399 in all.
  One existing case changed on purpose. The non-text item that stated pay used
  to be kept as it was; it is now dropped whole, which is what the review
  asked for. Its note records this, and no other case changed.
- **Generated test:** new families for own-pay verbs, pay continuations,
  currency look-alikes, and facts before a pay sentence (11 facts x 3 pay
  sentences).
- **Old rule vs new rule** on every non-test sentence in the repository (29,670
  strings): 7 differ, and all are this review's examples.
- **Whole-suite recording:** the filter changed nothing outside the salary tests.
- **Deliberate breaks:** 22 of 22 caught, after adding two word-boundary cases
  and correcting two break scripts.
- **Full suite:** 1446 passed, 23 skipped, plus the known environment-only
  tests. **Node:** 27/27.

