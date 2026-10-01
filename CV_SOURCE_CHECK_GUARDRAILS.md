# CV source-reading guardrails

This is the rulebook for the parts of CV Studio that read a CV's own tables and
labels to check or correct the AI's reading of it. Every rule here was settled by
a real CV or a review finding. **Read it before changing any of these files:**

- `cvstudio_cv_reconcile.py`: `_extract_authoritative_work_rows` (the work-row
  reader) and the education, separator and heading rules above it
- `cvstudio_cv_fidelity.py`: the source check (missing and unnamed employers)
- `cvstudio_cv_normalize.py`: `_cv_pretranslate_year_first_month_names` and
  `_recover_education_source_labels`
- `cvstudio_cv_reconcile.py`: `_restore_labelled_company_qualifiers`
- `_cv_strip_pay_from_summary` (`cvstudio_cv_normalize.py`): salary in the
  generated Summary box
- `vendor/cvstudio/cv-format.js`, `batch-format.js`, `create-profile.js`: how
  the warning is shown, and the auto-upload hold

## Why this file exists

These rules guess a CV's structure from plain text. Every CV is laid out
differently, so every rule has two ways to be wrong, and tightening one usually
loosens the other. Between v24.6.411 and v24.6.416, each of five review rounds
found a case the previous fix had broken. Most were cases nobody had written
down yet, not the same bug twice.

So every case is now written down. Each rule below has examples in
`tests/fixtures/cv_guardrail_cases.json`, and `tests/test_cv_guardrail_cases.py`
runs all of them on every test run.

## How to change these rules

Every change, including every fix for a review finding, goes through all six
steps. Skipping one is how earlier rounds broke things.

1. **Add the new case first**, to `cv_guardrail_cases.json`, under an existing
   rule or a new one described here. Watch it fail.
2. Make the change. **Every existing case must still pass.** If one fails, the
   change breaks a behaviour that was chosen on purpose. Change the approach,
   not the case. Only the owner can agree to change or delete a case.
3. Run the whole-suite replay (see the v24.6.416 QA report) and confirm nothing
   outside the new cases changed against master.
4. For P1, `tests/test_cv_summary_salary_generated.py` also runs thousands of
   generated sentences, and a speed limit on hostile input. Add a new way of
   stating pay, a new kind of pay-related work, or a new slow input shape to its
   lists rather than only a single case.
5. **Compare the old and new rule** on every sentence in the repository's code,
   tests and docs. Every difference must be a new case or an intended fix; any
   other difference is a regression to fix first.
6. **Break each fix on purpose** and confirm a test fails. A break that no test
   notices means that part has no case of its own; add one.

## The one principle

**When unsure, do nothing.** Both mistakes have a cost, but they aren't equal:

- If the **work-row reader** is unsure, it should return fewer rows. With fewer
  than two rows, or rows that don't cover the AI's reading, the reconciler
  keeps the AI's reading. A wrong row, like a degree read as a job or "|" read
  as a company, gets printed in the candidate's CV.
- If the **source check** is unsure, it should report nothing. A false warning
  now holds the CV back from JobAdder auto-upload. A missed warning is what
  master always did.

## Work-row reader

### R1
**A separator is never a company; a placeholder is.** A company that is only
"|", ":", "│" or "｜" is refused. That was the reported bug: every employer
printed as "|". A "-", "—", "--", "." or "N/A" in the company column marks a
career break or freelance work. That row is kept exactly as master keeps it,
because dropping it drops the entry from the rebuilt work history. The rule
lives in one pattern, `_CV_SEPARATOR_ONLY_RE`, shared with the source check.

### R2
**An education heading has to be the whole line.** "Education", "Educational
Background", "Academic Qualifications" and "Education & Training" start an
education section. "Education Consultant", "Academic Coordinator" or
"Education Queensland" inside a work history don't.

### R3
**An education section ends at a work heading, not at a part of itself.** It
ends at a work-history heading, any other known section heading, a heading
with a work word in it, a whole heading such as "Positions Held",
"Appointments" or "Academic Appointments", or an unknown heading in capitals.
It does not end at "Leadership Positions", "LEADERSHIP POSITIONS", "Key
Assignments", "Co-curricular Activities", a school's name on its own line, or
notes like "CGPA 3.5".

### R4
**Inside Education, qualifications and schools are set aside; jobs are not.**
A row naming a qualification is always set aside: degree, diploma, B.Tech,
LLB, "B.A", "Associate of Arts", CIMA, SPM, CGPA, "Foundation in", and so on.
A row naming a school or university is set aside too, unless its title cell
names a job. "Contoso Academy | Trainer", "University | Postdoctoral Fellow"
and "Acme Foundation | Program Manager" are jobs. Only the title cell is read
for the job word, because institution names carry them too: "Institute of
Management Accountants".

### R5
**Borderless rows split on cells, never across them.** Separators are stripped
from the company. When cells remain, the title is the whole last cell. A row
with no separators is split exactly as before. A "date | title" row with no
company is left out rather than guessed. A referees heading ends the work
section.

### R6
**An employer named after education is still an employer.** "Ministry of
Education" and a university as an employer inside the work history are kept. A
three-column table with no heading at all is read exactly as it always was.

### R7
**A place is never a company; the line above names the job.** In "Acme
Holdings | Kuala Lumpur, Malaysia | Apr 2019 – Dec 2024" the last cell before
the dates is a place, so the employer is the cell before it, whole, dash and
all ("Contoso Media – Northwind Books"). The job title is the short line
directly above: it starts with a capital, names a job, and is not a bullet, a
date, a heading, a sub-heading ending in "Experience", "Roles" or "Positions",
a sentence ending in a full stop, or a wrapped duty such as "Reporting to
General Manager" (a verb form followed by a linking word, including intervening
adverbs such as "Reporting directly to" and "Working very closely with"; "Managing Director"
and "Marketing and Communications Manager" are still titles). Job words include
the shared title words plus founder, owner, lead, chairman, counsel,
representative, buyer and similar, and CEO, CFO, VP, GM, MD and other
officer acronyms. That line starts the next
job, so it is never glued onto the previous job's last bullet. With the title
on the same line ("Engineer – Acme | Singapore", "Engineer | Acme | Singapore")
the place is dropped and the rest is read as before.

A place is a country, state or large city on the list in
`_CV_PLACE_KEYS`, "City, Country" (any capitalised city name, accents and joining words
included: "São Paulo, Brazil", "Rio de Janeiro, Brazil") or "Remote". A cell with an organisation
word is an employer: "Singapore Airlines", "Acme Sdn Bhd, Malaysia".

When unsure, no row: no title above, a job title where the employer should
be, or a title above as well as a job word inside a dash-joined cell
("Contoso – Executive Search"). An unsure row is left out, never glued onto
the bullet above it, and the bullets after it never join the previous job.
If a title-shaped line was glued onto that job's last bullet just before the
unsure row, that job's source bullets are unsure too and the AI's are kept. A company that is only a known place, from any reader, is
refused. Words that are also an employer's whole name ("Sea", "Global") are not
on the list. A cell that is only loosely a place (an unlisted name before a
country, such as "Contoso, Kuala Lumpur") after a job title, or with no clear
title, is read exactly as before.

A refused place header makes the history incomplete. Reconciliation keeps the
entire provider history instead of rebuilding from just the remaining rows,
even when another provider entry needs correcting. A four-job history must not
become three jobs because one employer such as "Contoso - Executive Search" is
uncertain. Complete source histories still correct provider drift normally;
uncertain lines outside Work Experience do not disable that correction.

## Source check (missing and unnamed employers)

### A1
**Referee and personal-details headings end the scan, in any form.** This
covers "REFERENCE CONTACTS", "Professional References", "Referee: Mr Tan",
"Referee #1", "Reference No. 1" and "Personal Details". The AI always leaves
referees out, so reading on would report a referee's company as a missing
employer. Nothing after these headings is treated as work history.

### A2
**A line with a value after its colon is part of the job.** "Project: Core
banking migration", "Training: 2019", "Languages: 3", "Reference No: 4411",
"Courses: Training". These don't end the scan.

### A3
**A bare heading does end it.** "Training", "Languages:", "Awards", "Hobbies &
Interests" and "AWARDS 2021" end the scan. Figures alone don't make a line
part of a job.

### A4
**Many headings start the scan.** "Working Experience", "Employment Record",
"Relevant Experience", "Employment", "Previous Employment", "Positions Held",
"Career Background" and the shared work-history headings all start it.

### A5
**Every work-history section is read**, not only the first. An early
"Professional Background" profile can't hide the real work history below it.

### A6
**No reopening inside referees.** Prose such as "Work experience with the
candidate: 3 years" can't restart the scan, and nothing after a referees
heading restarts it.

### A7
**No work section, no claim.** If no work-history heading is found, the source
check reports no missing employers at all.

### A8
**Column headers are not employers.** A value in the next cell made up
entirely of header words is a table heading, not a name. Examples: "Position
Held", "Period of Employment", "Total Experience", "State".

### A9
**Real names are read.** A value in the label's own cell is always a name,
even "Company: Total" or "Company: Department of State". Hyphenated names are
kept whole. Industry, position and duration labels on the same row are
stripped. "Company-wide rollout" is prose, not a label.

### A10
**A bracketed name is weaker evidence.** "Acme (Lumen Bank)" counts as present
if the AI kept "Lumen Bank" and nothing else claims it. It doesn't count when
"Lumen Bank" is the candidate's own separate job. The head before a comma or
dash also counts.

### A11
**Only a real separator is an unnamed employer.** A parsed company of "|" or
":" is reported. A "-", "—", "." or "N/A" is a deliberate placeholder and is
not.

## Putting back what the AI dropped

The AI is told to keep all of these, and sometimes still doesn't, so each one is
also restored from the original CV after the AI answers. The same principle
applies: only what the source states word for word is restored, and when
unsure, nothing changes.

### F1
**A bracket in an employer's name is kept.** Take "company: Acme outsourcing sdn
bhd(Contoso bank sdn bhd)". If the AI returns "Acme Outsourcing Sdn Bhd", the
bracket is put back, along with the candidate's Current Company. This only
happens when the AI's name is exactly the part before the bracket, ignoring
legal forms such as Sdn Bhd, and only for names the CV labels with "Company:".
A bracket with figures (a date), a different company, a name that already has
a bracket, or two different brackets for the same name are all left alone.
Code: `_restore_labelled_company_qualifiers`.

### F2
**The CGPA label is kept.** If the AI returns "2.0 / 4.0" and the lines under
that institution say "CGPA 2.0 / 4.0", the result is "CGPA 2.0 / 4.0". The
label (CGPA, GPA, CWA, WAM, Grade Point Average) must sit right before the same
figure. A different figure, another word such as "Result", or two different
labels change nothing. Code: `_recover_education_source_labels`.

### F3
**A stated major is kept.** A "Major", "Major:", "Major - ", "Majoring in" or
"Major | value" line under an institution fills the entry's major. The Word
file and preview show it as "Major: …" under the degree. A sentence such as
"Major in the arts club", two different majors, or a line past the next
qualification or section heading changes nothing.

If the institution appears for several qualifications, the major and grade
label must come from the one block uniquely identified by the entry's degree
and/or stated year. Conflicting or missing identifying evidence changes
nothing. A master's major never fills the bachelor's entry just because the
school is the same; an existing major is never overwritten.

A degree heading immediately above its institution identifies that block too.
Once a block has a degree, the next degree heading belongs to the next block,
not to the previous school's major or grade. A degree below its school is still
supported; blank lines do not change the attachment.

### F4
**A stated graduation year is kept.** If the AI leaves an entry's date empty
and the line naming its institution says "graduated 2007", "graduated in June
2007", "Graduation: 2007" or "Class of 2007", that is the date. When the same
school is named for two qualifications, only the line naming this degree
counts; if the entry names a degree and no line names it, nothing is restored.
A date the AI gave is never replaced. A year on a later line, two
different years, another year on the same line, "graduates of …" or a year
that doesn't follow the word directly change nothing. Code: `_recover_education_source_labels`.

When extraction joins qualifications on one line, a semicolon or pipe followed
by a new qualification starts a separate graduation span. Both the institution
and degree must uniquely identify the span. The master's year cannot date the
bachelor's entry. Ordinary degree/institution/Graduation field separators stay
joined, and an institution such as "The Master's University" is not a new degree.
The existing two-different-years-on-one-line ambiguity rule still applies.

University-first spans keep the university with the following degree, including
pipe-only combined lines: "Contoso University | Bachelor of Science | Northwind
University | Master of Science | Graduation: 2015" dates only the master's.
Degree-first and single-qualification field layouts retain their existing rules.

## Dates

### D1
**Only a cell that is entirely a year-first date is turned round.** "2025
june- current" becomes "june 2025- current", in its own table cell, and "Till
Date", "Presently" and bare-year ends are included. A month's full stop or
comma moves with it: "Jun. 2025". Prose ("figures for 2023 may be revised"),
month-first dates, bare-year ranges and lines with several dates are never
touched.

## Summary box

### P1
**The generated summary never states the candidate's pay.** The CV Summary
instructions forbid it, and there is one filter, `_cv_strip_pay_from_summary`
in `cvstudio_cv_normalize.py`, run where each summary is made:

- `/generate-ai`, for the two CV Summary callers, which send
  `strip_candidate_pay: true`. The browser only ever receives filtered text.
- `/parse` and `/blind`, so the preview shows what the Word file will carry.
- `/generate-docx`, on both of its paths, as a last net.

There is no browser copy.

Explicit earnings such as "Earnings of RM 18,000 monthly", "Monthly earnings
of RM 18,000" and "Her earnings are RM 18,000 monthly" count as pay. So does
"The candidate receives RM 18,000 per month"; receipts explicitly for business
and company earnings remain work. Payroll achievements with an explicit
recipient such as "salary of RM 12,000 for each employee" or "per employee"
remain intact. That recipient must be in the pay phrase's own comma part, and
cannot be a job-role description or override an explicit own-pay statement.
Short job-title modifiers count too: "for the employee relations manager role"
is a role, not a payroll recipient, including hyphenated and possessive forms.
An unprefixed amount such as "12 LPA" follows the same rule. Relative or action
clauses describing actual recipients ("each employee who works in a support
role", "every worker assigned to a construction job") remain payroll work.

**A summary is also the candidate's work, and much of that work is about pay**
(HR, payroll, recruitment, sales). So a sentence is removed only on a clear
sign that it states the candidate's **own** pay:

1. **Always removed.** This covers:
   - "my" or "candidate's", or expected / asking / last-drawn, before a pay
     word ("salary", "package", "wage", "income"…) and an amount ("Expected
     salary RM16,000", "Expected wage RM 3,000");
   - "On a package of RM 150k";
   - "The candidate / he / she is paid RM 9,000".

   Nothing overrides these. "his", "her" and "their" alone aren't enough,
   because a recruiter "negotiated their salary".

   "Current", "present" or "previous" before a pay word and an amount is also
   removed ("Led a team of 8 on a current salary of RM 12k"). The one exception
   is a clause that opens with a work verb and names the organisation's money
   or people ("Restructured current compensation of RM 12M for 300 staff").
2. **Removed unless the words around the amount describe work.** This covers:
   - a pay word and an amount in either order ("Salary: RM 17,000", "RM16,000
     salary");
   - "Last drawn RM 9,000", "RM 9,000 expected", "Asking for RM 10k", "Seeking
     RM 12k", "Looking for RM 12,000", "Seeking a senior role with RM 12k
     monthly", "Current: RM 9,000";
   - a label and an amount: "Package: RM 150,000", "Pay: RM 9k", "Income - RM
     9,000"; "Monthly income RM 9,000"; "current role pays RM 9k";
   - "Gross / Nett RM 9,000 / month";
   - "Receives / Makes / Gets RM 9,000 monthly", and "They are paid RM 9,000";
   - "Earning RM 9k", "Takes home RM 7,000 monthly", "earning RM 300k in
     commission annually";
   - more connectors: "Salary per month: RM 9,000", "Salary in 2024 was RM
     9,000", "Salary currently stands at RM 9,000", "Salary drawn:", "Salary
     history:", "package worth RM 200k";
   - "Monthly gross RM 9,000", "Current base of USD 120,000", "Basic RM 7,000 +
     allowance RM 1,000", and a space in the figure ("RM 9 000");
   - a clause that is only an amount per period ("RM 9,000 / month");
   - earnings, a bonus, commission or allowance per period;
   - lakhs per annum.

   **Only the words around the amount count.** That means its own comma part,
   no more than 300 characters either side. A work word elsewhere in the
   sentence doesn't hide the pay:
   - "Heads the revenue team, salary RM 20k" keeps only "Heads the revenue
     team".
   - In "Sales manager across APAC with salary of USD 150,000", the part is cut
     at the word that attaches the pay ("with", "earning", "on a"), so it is pay.
   - One pay attached with "with" is the person's own, whatever work the
     sentence opened with ("Leads a budget of RM 5M with salary RM 20k").
   - A range or plural is other people's: "with average salaries of RM 15k",
     "with total compensation up to $250k".

   The words around an amount describe work when:
   - its part opens with a work verb from an explicit list ("Managed total
     compensation of $12M", "Placed 40 executives averaging $180k"). The list
     leaves out "earned", "drew", "paid" and "made", and the adjectives a
     summary opens with ("Seasoned");
   - a work verb comes just before the pay phrase ("Seasoned payroll specialist
     handling salaries of RM 2M monthly");
   - it names the organisation's money ("budget", "costs", "revenue", "AUM");
   - it names who the money is for ("for 300 staff", "to the sales team", "for
     the group", "across APAC");
   - it is someone else's pay the candidate worked on ("negotiated their salary
     of RM 15k");
   - it is a recruiter describing the roles they fill ("placing C-suite leaders
     with compensation above USD 500k", "Tech recruiter for roles with a CTC of
     30 LPA"). This doesn't apply when the clause says it's the candidate's
     own ("Recruiter earning RM 9k monthly").

   Some phrases look like these but are still pay:
   - "across base, bonus and allowances" (the parts of one's own pay);
   - "for the team lead role" (a role, not people);
   - "for 12 LPA" (an amount, not a headcount).

   A year after "from" or "since" is a date, not an amount ("Head of
   Compensation from 2019").
3. **Pay talk with no amount that only a candidate says of their own pay** is
   removed, unless the sentence opens with a work verb. Examples: "Salary:
   negotiable", "salary is negotiable", "open to discuss remuneration".
4. **Pay talk that can be about anyone** ("expected salary", "salary
   expectations") is removed unless something says it's someone else's. That
   means any of:
   - "of", "for" or "across" after it;
   - a reporting verb after it ("were benchmarked");
   - a work noun after it ("ranges", "dashboards");
   - a work verb at the start;
   - another group's possessive before it ("candidates'").

   "For the next role" is the candidate's own move, and is removed.

**Amounts.** An amount has a currency ("RM", "$", "ringgit") or a unit ("k",
"LPA"). A letter code such as "RM" or "PHP" must be a word of its own, followed
by three or more figures or a unit. So "Form 16", "Norm 3000" and "PHP 8" are
not money. A plain figure counts only directly after a pay word, with three or more
digits, and only where it ends the sentence or is followed by a pay period,
currency or pay word. A year-like figure is held to that strictly. A figure
never starts inside another one ("2016" holds no "016").

**Removal** is by sentence, and by semicolon clause within a sentence. Sentence
ends are handled as follows:

- A sentence ends after closing Markdown emphasis ("**Expected salary RM 9k.**
  Available"), and after a figure ("a team of 8.", "by 5.5%.").
- It also ends after "Sdn Bhd.", "Ltd.", "etc." and "p.a.".
- "Sr.", "Dr.", "Sdn." and a list number ("1.") never end one.
- A single letter, a dotted token ("U.S.", "B.Sc."), "Co." or a month ends a
  sentence only when the next sentence states pay on its own. So "Worked at
  Acme Co. Expected salary RM 9k." keeps "Worked at Acme Co.", and "Joined
  Acme Co. Ltd. in 2019." stays whole.
- It also ends at a full stop with no space before a capitalised word
  ("Salary RM 9,000.Led HR team."). Kept sentences keep the spacing they had,
  so "booking.Com" stays whole.
- A stop before a lowercase word ends a sentence only when the next sentence
  states pay ("Head of Payroll. salary RM 15k." keeps "Head of Payroll.").
- **Clauses next to a pay clause.** In a sentence that states pay, the clause
  right after the pay clause goes with it when it:
  - carries an amount;
  - starts with a pay continuation ("plus 2 months bonus", "negotiable");
  - or starts with "with", "and" or "or" and names pay ("with 2 months
    bonus").

  The clause right before goes with it only when it is just an amount ("RM
  9,000; Expected: RM 11,000"). A clause further away, or one that describes
  work, stays: "Expected salary RM 9k; led HR at Acme; and holds a CIPD
  qualification" keeps both facts.
- **Comma parts.** Within a pay clause, a comma-separated part that isn't pay
  stays when it reads as its own phrase, starts with a capital, and holds no
  pay words and no money that isn't work.
  - "Expected salary RM 9k, CIPD-certified HR leader" keeps "CIPD-certified HR
    leader".
  - "Grew revenue to RM 5M, expected salary RM 9k" keeps its revenue.
  - "Current salary RM 9k, managing 10 staff" leaves nothing.

After a removal:

- A "**" left without its partner is dropped.
- A bullet left empty is dropped.
- A bullet that isn't text is never edited. The Word file writes it as text,
  so it is dropped whole when that text states pay.
- The count is of sentences, not clauses.
- In provider text, "-", "*", "•" and numbered ("1.", "2)") lines are list lines.
  If every list line was pay, an intro such as "Here is the summary:" is
  dropped too.

Filtering again changes nothing, and hostile input can't slow it down. Reading
is linear: a run of stops is looked at once, the word before a stop is found by
walking back only as far as needed, and the words around an amount are read
within a fixed window. The Word paths filter only what the file can use (60
bullets of 20,000 characters). Every known slow shape, such as long runs of
digits, dots, abbreviations or pay phrases, stays under 2 seconds in a test. This is checked on 12,728 inputs, including
random combinations with bold and semicolons.

**Every removal is shown.** `/parse` and `/blind` return `summary_pay_removed`,
`/generate-ai` always does when asked, and `/generate-docx` sends
`X-CV-Summary-Pay-Removed`. What the page does with it:

- **Format and Batch:** the note joins the source-check warning. It stays above
  the preview and on the batch row, and holds JobAdder auto-upload the same way
  (S1, S2). The parse's note counts only when that parsed summary is the one
  used, not one replaced by a linked or automatic summary.
- **Summary tab:** the note is shown under the summary.
- **Pay-only summary:**
  - Format and Batch carry on with an empty Summary box, and count the
    summary's cost.
  - The Summary tab says "only described the candidate's pay" and records the
    paid call as a summary, not a failed one.
  - The uploaded-DOCX route says the same. Its only job is filling the
    Summary, so with nothing left it has nothing to write. When it removes
    only part, it sends the same header, and the page warns. The filter runs
    once there, so the header and the file always agree.
  - A pay-only regeneration on the Summary tab also unlinks a summary linked
    earlier for formatting that CV. It says so as a warning: the tab isn't
    marked failed, because the paid call succeeded.
- **`/generate-docx` (JSON), the formatted CV:** it never refuses the whole CV
  over its summary.

Matching runs on an NFKC-normalised copy with Markdown emphasis removed, so
"**Salary:** RM 17,000" is caught. Full-width digits count as ordinary digits,
digits in other scripts count too, and a neighbouring non-Latin character
doesn't hide an amount.

## Test-state safety

Pure source-reading tests need no installation receipt. Tests importing the
application must create any test receipt and local data inside temporary state,
never in the owner's installed folder or per-user receipt location. Restore all
environment overrides after import. `tests/test_cv_test_state_isolation.py`
collects each affected test in its own interpreter and verifies that a pretend
owner receipt and data paths are unchanged. On Windows this also protects the
folder-bound authorization used by INSTALL/UPDATE.

## Screen (checked by `tests/test_cv_parse_warning_persistence_frontend.js`)

These aren't data-driven, but the JavaScript test above pins each one.

- **S1**: The warning stays on screen: as a banner above the preview, under a
  batch row, and on a Create Profile row. The final message never says a
  plain "Done!" over a warning.
- **S2**: JobAdder auto-upload holds a flagged CV. For a single CV the Upload
  button still works. In batch the row offers "Upload anyway", which sends it
  once. A clean CV uploads exactly as before.
- **S3**: In Blind mode the source check's warning never names an employer.
  The rule lives only in `cvParseWarningText`, which batch mode calls too.
  `cv-format.js` loads before `batch-format.js`.
- **S4**: Warnings are inserted as text, never as HTML. Batch warnings use
  role="note", so screen readers don't re-announce them on every refresh.
