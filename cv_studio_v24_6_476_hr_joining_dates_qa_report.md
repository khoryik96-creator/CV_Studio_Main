# v24.6.476 — HR company joining dates

Owner request: show when people on the Job Leads HR cards joined the company.
Continues unmerged `codex/v24.6.474-job-leads-company-hr` from v475 `a2e57b0`.
The v474 HR feature and v475 rich-description corrective remain included.

## Behavior and evidence

- HR cards show `Joined company: Jun 2020`, a year alone when that is all the
  source provides, or `Not available`. No duration subtraction or guessed month.
- The companion reads only matched public profile URLs observed on the current
  company/country results page. Visible Experience items must link to the exact
  observed company ID or verified company-page slug and contain current
  employment date metadata. About/activity/education/free-form descriptions
  are excluded. Fully visible continuous promotions retain the earlier start;
  old separate stints, collapsed groups, uncertain continuity and ambiguous
  simultaneous stints cannot supply a confident joining date.
- One temporary inactive profile at a time; 100 lookup attempts maximum within
  the existing ten-minute HR run. Creation intent is persisted before opening,
  with no replay of ambiguous creation. Suspension can poll a known owned tab;
  activation/redirect relinquishes ownership. Source filters and profile URL
  are checked around reader injection. Stop/error retains previous saved HR
  results; a slow/missing Experience section only leaves its date unavailable.
  Fresh-page inspection confirmed lazy Experience loading after scrolling.
  At most four scroll attempts, persisted before each action, target the
  Experience container (or advance the profile viewport while it hydrates).
  Empty Experience skeletons are polled; user-opened tabs cannot be scrolled.
- The optional bounded canonical date survives local storage/backup through
  existing `save_hr`. Old evidence loads with an empty optional date. Revisions,
  notes, folders, contact, status, creation date, duplicate handling and Trash
  remain. No new route, schema migration, extension permission or packaged file.

## Verification

New reader and storage regressions failed before implementation (missing reader
method and discarded optional field / accepted invalid dates). Focused checks
now pass for company/profile identity, metadata scoping, promotions/rejoining,
year-only/unknown/collapsed/ambiguous dates, canonical validation, atomic failure
and backup round trips. Worker/UI tests cover restart and creation ambiguity,
attempt ceiling, source drift, profile takeover/redirect, null-result polling,
bounded optional lookups, deduplication, draft preservation, Stop and old records.

Browser QA at `http://127.0.0.1:5086/?module=jobleads&preview=v24.6.476` used
fictional ads/people and simulated companion responses through the actual
controller/service/store. All three display states saved and survived reload.
Screenshot: ignored `runtime/hr_joined_476.jpg`. Current LinkedIn Experience
markup was inspected read-only; no real installed-companion end-to-end HR scan
is claimed. No paid call, outreach, owner record/receipt/install change,
protected build, push, PR or merge was performed.

Full isolated Windows regression: **1,776 Python tests passed, four skipped,
8,392 subtests passed** (268.45 seconds). **All 46 JavaScript suites passed**.
Tracked/untracked syntax, repository consistency, source validation and
owner-source preflight passed. Windows x64 Antiword was trusted/functionally
verified; Tesseract and English language passed. All **24 source-smoke
assertions passed** with isolated state/receipts. Final JavaScript/static checks
were repeated after the bounded lazy-loading refinement.
