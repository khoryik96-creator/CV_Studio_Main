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

1. **Add the new case first**, to `cv_guardrail_cases.json`, under an existing
   rule or a new one described here. Watch it fail.
2. Make the change. **Every existing case must still pass.** If one fails, the
   change breaks a behaviour that was chosen on purpose. Change the approach,
   not the case. Only the owner can agree to change or delete a case.
3. Run the whole-suite replay (see the v24.6.416 QA report) and confirm nothing
   outside the new cases changed against master.

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
  `strip_candidate_pay: true`. The browser only ever receives filtered text, so
  the preview, the Summary tab and copied text match the Word file.
- `/blind`, on a source About / Summary section promoted into the box, before
  the provider sees it.
- `/generate-docx`, on both of its paths, as a last net.

There is no browser copy.

Only a statement of the candidate's **own** pay is removed:
- a pay term followed by an amount: "Salary: RM 17,000", "Salary 2000", "CTC of
  12 LPA", "total compensation of $180k";
- an amount followed by a pay term: "RM16,000 expected salary";
- pay talk with no amount: "expected salary", "salary expectations", "salary is
  negotiable", "open to discuss remuneration";
- an amount in lakhs per annum, or earnings, bonus, commission or allowance per
  period.

A pay word on its own is the candidate's work and is kept, for example
"negotiated compensation packages for 40 hires", "salary range benchmarking",
"payroll salary processing", "minimum wage compliance", "saved RM 2M in salary
costs", "managed allowances for 3,000 expatriates". A plain figure directly
after a pay term counts only with three or more digits, and never when it
counts people.

Removal is by sentence, and by semicolon clause within a sentence.
Abbreviations such as "Sr." or "B.Sc." don't end a sentence, so no fragment is
left. A bullet left empty is dropped. When every line was pay, the page says so
("only described the candidate's pay"). It isn't recorded as a failed paid
call, and the uploaded-DOCX route says the same rather than "No CV Summary
bullets".

Matching runs on an NFKC-normalised copy, so full-width digits count as
ordinary digits. Digits in other scripts count too, and a neighbouring
non-Latin character doesn't hide an amount.

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
