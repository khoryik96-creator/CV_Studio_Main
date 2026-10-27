# v24.6.496 — grouped-company HR scan correction

Branch `codex/v24.6.496-hr-company-identity`, stacked on the tested local Apollo
checkpoint `5c3fa52` (v495). Both are unmerged; last merged master is `a323ad5`.
Apollo setup remains inactive and its public service address remains blank.

## Root cause and correction

The owner's batch screenshot had three loading/company-control failures and
one saved result. Read-only inspection of the three still-open company pages
confirmed the same pattern on every failure: a header employee-search link
contains several related company IDs, while an HTTP-valued header connection
link identifies the exact company. The old reader required a singleton HTTPS
link and therefore found no ID. It stayed on the company page until the bounded
controller wait expired. The error wording incorrectly suggested search filters
might have changed even though no People search had opened.

The reader now recognizes that exact-company evidence only within the matching
company header. HTTP singleton IDs require the expected native connections
query and membership in every recognized HTTPS employee group. The link is read
as evidence only; no HTTP request/navigation occurs. Multiple conflicting IDs,
missing corroboration, foreign/credentialed URLs, duplicate query values and
unrelated recommendations stay unconfirmed. Existing HTTPS single-ID behavior
remains characterized. No arbitrary first member of a group is selected.

The worker advertises `hr_company_identity_revision:1`; Job Leads checks it
before opening a scan. Old companions receive explicit update guidance rather
than another series of loading failures. Existing company/country authority,
result binding, pagination, joining dates, Stop, save revision and cleanup
boundaries are unchanged. No route/schema/permission/provider change is added.

## Evidence

- New `test_company_hr_http_identity.js` failed against the old reader on the
  diagnosed layout before implementation. It now covers grouped IDs, a primary
  ID that is not first, legacy HTTPS, hostile URLs/queries, contradictory IDs,
  absent corroboration and header scope. No real company/profile IDs in fixtures.
- Native Chromium with the actual companion worker/reader and intercepted
  fictional pages navigates from a grouped header to the exact company search,
  reviews three keyword groups/all 11 terms over six result pages, for both
  Any country and Malaysia. All six joining-date lookups and twelve controlled
  source-loading races pass; country/company and unchecked-filter gates remain.
- The same native fixture against unmodified `origin/master` fails before its
  first search navigation (zero updates). This reproduces the company's loading
  stall independently of Apollo and confirms the correction reaches that stage.
- All **59 JavaScript fixture files pass**, including bulk HR, old-companion
  refusal, scoped reader, pagination, joining dates, and Apollo boundaries.
- Actual isolated-app browser QA confirms remembered Malaysia/10 settings,
  per-ad progress, Stop retaining a completed save and draft, no third scan after
  Stop, Any-country/3 persistence and subsequent serial three-ad completion.
  Screenshots `bulk496_settings.png`, `bulk496_progress.png`, `bulk496_done.png`
  contain fictional intercepted data and are not live owner scan results.
- Source/native preflight and 24 live source-smoke assertions pass. Final
  isolated full regression: **1,888 passed, 4 skipped; 8,416 subtests**.

## Delivery limits

No owner saved ad, HR record, installed source/receipt or active companion was
modified. Company tabs were only read; no live scan reran or private profiles/
messages were inspected. Preview 5093 is isolated from installed port 5000.
No paid call, outreach, hosting deployment, protected package, PR or merge.
After publication, normal Update & Restart plus Apply companion update and a
refresh of CV Studio/LinkedIn are required to use the new reader/capability.
