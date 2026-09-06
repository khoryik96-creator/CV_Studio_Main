# v24.6.382 — async-handler audit corrective

Base: master `a5fa125` (v24.6.381). Branch:
`codex/pr194-v24.6.382-async-handler-safety` (PR number provisional).

## Confirmed and corrected

- OneNote section loading and Outlook connection testing now contain unexpected
  rejected promises at their existing UI entry points. A failed child section
  request cannot become the parent picker's successful-load notification.
  The PR-review corrective also replaces the parent's loading indicator with
  a visible failure message on both rejected and non-OK fallback responses.
- OneNote upload failures escaping the existing per-item guard now mark only
  the still-present originating row as unconfirmed; replaced rows are untouched.
  Temporary Create Profile skip flags are released even if the run rejects.
- Single-CV download and batch Open Folder receive defensive entry guards.
  Their existing destination, filename and mixed-output behavior is unchanged.
- Outlook Save and Connect stop if disconnect fails. Known account state and
  settings are retained until the backend confirms disconnection.
- Outlook login rejection is visible. Test-draft network, JSON and incomplete
  success-response failures close the reserved blank tab and report uncertainty.
  The user must check Outlook Drafts before retrying; no automatic replay occurs.

## Audit qualifications

The original upload network operations already had per-item catches, and the
shared Open Folder helper already caught ordinary network failures. The new
outer guards are defense in depth, not replacements for those protections.
The global fetch timeout remains intact. No npm installation was required and
no package lock was generated; HANDOFF now uses the existing CI no-lock recipe.
The four unused Python definitions are on a separate independent cleanup branch.

## Validation

- Full isolated Windows regression: **1117 passed, 4 skipped, 128 subtests**.
- All **23 frontend fixture groups** passed, including new actual mocked
  workflows for network/HTTP/JSON rejection, success, unchanged state, no replay,
  parent failure propagation and queue cleanup.
- Live source smoke: **24 assertions** passed.
- Protected-source preflight passed: verified Antiword 1.3.5, Tesseract 5.5 with
  English data, adm-zip 0.6.0 and all required frontend/source files.
- Tracked Python/JavaScript/PowerShell syntax, repository byte consistency,
  version anchors and Git whitespace checks passed.

No CV text, formatting rules, route/schema, dependencies, credentials or paid-call
boundaries changed. No live JobAdder/Microsoft write or paid AI call was used.
Native protected compilation was not run; the expensive build stays manual.
No PR or merge is authorized by this handover-fix request.
