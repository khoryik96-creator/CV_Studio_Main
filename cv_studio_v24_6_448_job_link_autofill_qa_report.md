# Job-link autofill — source QA, 2026-10-19

Historical release evidence; root `VERSION` is the live release identity.

## Scope

Owner clarified that Job Leads should fill details from a pasted **LinkedIn job
link**. Source v24.6.448 on local `codex/v24.6.448-job-link-autofill` follows
unmerged v447 checkpoint `1223ed8`; merged main remains `480678d` / v445.

Paste or URL change initiates a narrow browser-companion request. An existing
matching job tab is reused, otherwise only the explicitly supplied canonical
job URL opens in a temporary inactive tab. It waits for loading within a bound,
then runs the existing visible job reader. Unknown layouts, changed IDs, login
checks, lost app authority, timeouts and concurrent browser runs fail closed.
Only an unchanged inactive tab created by that read is cleaned up. Existing
user tabs are never navigated or closed. Source/profile navigation constraints
and all three Sourcer modes remain intact.

Only empty company, role, location and description fields are filled. Contact
person remains manual and optional. New status remains New; dates and BD status
are never inferred from job text. Manual company corrections, contact, notes,
status and date survive repeated fill and failed reads. A different ad cannot
silently replace an existing lead in edit mode. No result saves automatically.
The latest companion must be installed/reloaded and connected in Chrome.

## Verification

- Baseline: all 33 Job Leads Python tests and its frontend suite passed before
  implementation.
- Full isolated local suite: **1,640 passed, four skipped, three deselected,
  7,599 subtests**, 165.33 seconds. The same three documented local updater
  environment exclusions were retained; unfiltered hosted checks have not run.
- All 32 root frontend suites passed, including new canonical-link capture
  authority, existing-tab reuse, temporary-tab ownership/cleanup, load timeout,
  challenges, concurrent capture, reload and Sourcer isolation checks. Expanded
  UI tests exercise paste-triggered fill, retries, manual/optional fields,
  invalid URL rejection and failed-read draft retention.
- Native Chrome exercised the actual app with simulated companion responses:
  clipboard link paste, removal of tracking parameters, company/role/location
  fill, blank-contact save and reload, New default, blank follow-up date,
  repeated fill preserving manual corrections/contact/notes/status/date,
  different-job edit protection and read failures preserving a usable draft.
  The actual Sourcer mocked plan/screen/detail flow passed again.
- Desktop and narrow screenshots inspected. Python/JS/PowerShell/POSIX syntax,
  byte consistency, source inventories, native Windows dependency preflight,
  whitespace and 24-assertion live source smoke passed.

The exact 120-route seal, five ordered guards, schema-10 application database,
separate schema-1 Job Leads store, existing journal, provider/paid boundaries,
companion permissions, no-key browser boundary and CV formatting are unchanged.
Version surfaces and the companion manifest were generated using bump_version.

Preview 5074 uses the previous isolated persistent preview state. Synthetic
fixture 5075 is stopped after checks. Installed owner app/server/receipt are
untouched. No live LinkedIn account/extension install, paid call, JobAdder write,
protected build, package, hosted CI, push, PR, merge or native Mac result is
claimed. Actual live LinkedIn layout verification remains owner-driven.
