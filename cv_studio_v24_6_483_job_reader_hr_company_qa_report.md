# Historical QA record — CV Studio v24.6.483

Root `VERSION` remains the release source of truth. Local corrective branch:
`codex/v24.6.483-companion-job-reader`, from merged master `e316bfe` (PR #239).
No follow-up PR, merge, owner installation update or protected package is included.

## Report and diagnosis

The owner reported a normal-Brave companion timeout during company HR lookup.
The normal installation's app and bundled companion files were already v482.
Read-only browser diagnostics showed invalidated content-script errors after
extension reload. Refreshing that app document restored status/update replies.
An HR attempt still failed during the job-read stage; no HR results were saved.

The live standalone ad used a plain title, company link and location paragraph.
Its job-type buttons also linked to the ad, and v482's link-title heuristic chose
`Hybrid`. The About section initially showed only its heading, before loading
its body. HR unnecessarily depended on that complete body just to find a company
link. A separate synthetic reproduction also confirmed that a new tab's initial
URL-metadata gap was rejected before its expected job could finish loading.

## Correction

- Recognize the visible standalone company/title/location header, retaining
  existing linked-title layouts and exact job-ID About-section confirmation.
  Incomplete or ambiguous recognized headers cannot fall back to metadata links.
- HR requests only confirmed company metadata with literal `company_only: true`.
  Its reader skips description collection/readiness; existing full ad imports
  and previews retain their original content requirements. HR still verifies
  the canonical job URL and saved company before using the observed company URL.
  No saved description is replaced by a company-only result.
- Wait within the existing load-poll bound only for an extension-created tab's
  initial blank/loading URL gap. Another committed/pending identity is rejected.
- Map job access, layout, injection and loading failures to fixed, redacted
  recovery guidance. Timeout guidance asks for page refresh after companion
  reload and correctly names Chrome and Brave.

No route/guard, request limit, pairing gate, extension permission, main/journal/
Job Leads schema, paid-call boundary, HR record validation or saved-ad rewrite
changes. Existing run/capture isolation and conservative tab cleanup remain.

## Validation

- New synthetic plain-title and initial-tab-gap cases failed against v482 before
  production fixes. New company-only unloaded-body and HR-call tests likewise
  failed before that correction. Existing assertions were preserved.
- Windows Python: **1,779 passed, four skipped, 8,392 subtests**, 168.75s. This
  includes app/version/contracts and the unchanged Python backend; final JS-only
  refinements were followed by all JS suites and source smoke again.
- All **47 JavaScript suites** pass on final code, including pairing, lifecycle,
  full/metadata-only reads, existing job imports, HR, joining dates, cancellation,
  folders and rich-content checks.
- Tracked/untracked language syntax, repository consistency, whitespace,
  owner-source preflight and all **24 source smoke assertions** pass. Genuine
  local Windows Antiword/Tesseract checks pass; no protected compilation ran.
- Real isolated Chromium with synthetic job pages reproduced v482's `Hybrid`
  title error using the base reader, then read correct role/company/location,
  company URL and rich lists with final code for both linked and plain titles.
- The real worker/reader company-only path succeeded with an unloaded ad body;
  the ordinary full-read path still waited and returned specific page guidance.
  Final native tests used a dead outbound proxy plus local fixture interception
  so new page requests could not escape to live LinkedIn. A preliminary native
  interception attempt encountered unauthenticated public LinkedIn loading and
  was excluded from successful offline evidence. No credentials/provider requests
  were involved in those disposable profiles.

Live Brave diagnosis was limited to the reported UI/read-only ad lookup; no
completed live HR scan, outreach or paid call occurred. Owner browser profiles,
installed source, installation receipt and saved leads were not edited. No
native macOS application testing is claimed. Saved leads remained 28 throughout
the observed live diagnosis. Other user activity in their app was left alone.

Ignored local evidence: `runtime/pytest_483_full.log`, `runtime/js483_*.log`,
`runtime/preflight_483.log`, `runtime/job483_baseline.log`,
`runtime/job483_final.log`. An isolated empty-data source preview is served at
port 5089; permanent companion setup must use the normal installation after a
future merge/update, not this preview checkout.
