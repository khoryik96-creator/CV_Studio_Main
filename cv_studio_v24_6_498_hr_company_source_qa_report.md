# v24.6.498 — source-confirmed HR company identity

Unmerged branch `codex/v24.6.498-hr-company-source`, from merged v497 `ff722b3`.

## Confirmed cause

The failed saved lead says `cbs`; the exact same live job header's native
employer link says `cbs Corporate Business Solutions`. The old controller
required lowercased names to be equal and failed before opening the company
page. This is earlier than the grouped-company filter stage corrected in v497.
Read-only UI inspection confirmed the mismatch without editing the lead,
rerunning its HR scan or reading private profiles/messages. Fixtures use only
fictional employer names and IDs.

## Correction and related triggers

- Keep the saved ad company/role/contact/notes unchanged. Use the single native
  employer link observed on that exact canonical job URL as the scan identity.
  Two consecutive employer URL/name/title observations must agree. The worker
  retains a bounded, document-scoped observation for two minutes and checks it
  at `hrBegin`; a browser-app flag alone cannot authorize a different name.
- Only that source-confirmed path may derive the current native filter label
  from the heading of the exact linked company page. Manual company pages keep
  their strict name check. Other jobs, employer URLs, app documents, stale
  observations and conflicting native company links cannot reuse the proof.
- Optional bounded `hr.company_name` stores the verified LinkedIn label for
  display/repeated scans and backup/restore. `hr.company` still equals the
  saved ad label; old records remain readable without a migration or schema
  version change. Invalid evidence writes fail atomically.
- Metadata-only reads accept the identity-confirmed header before About loads,
  extract employer links without adjacent Follow controls, and treat multiple
  observed labels on one company URL as one identity. Conflicting/foreign
  employer links remain unconfirmed.
- The existing sixteen-poll passive-read bound now waits through unchanged-job
  loading, reinjects into the current document and waits for employer links
  rather than prematurely returning incomplete metadata. It never re-navigates
  a user tab or retries paid/network mutations. Missing employer evidence has
  specific guidance. A new capability refuses older companions before HR.

## Validation

- A new short/full-name controller assertion failed on v497 before the fix.
  Tests now cover preserved ad labels, exact job identity, missing/hostile
  employer links, verified name persistence and subsequent scans.
- Source-binding worker tests cover two agreeing observations, a stale first
  employer, same-ad reload/reinjection, worker restoration, expiry, different
  jobs/URLs/names, missing links and strict manual-page behavior.
- Reader fixtures cover header-only metadata, unchanged full-content readiness,
  Follow controls, multiple labels on the same URL and hostile/conflicting
  employers. Store tests cover optional-name validation, atomic failure,
  unchanged ad data and backup/restore round trips.
- Native Chromium executes the real reader/worker against intercepted fictional
  pages: a pre-opened exact ad without About supplies its full employer label;
  the linked company supplies a different canonical heading and grouped IDs.
  Native exact-company selection, Any country/Malaysia, all eleven HR terms in
  three queries, six pages per case, six joining reads and twelve controlled
  source-loading races pass. The fixture with merged v497 cannot read this
  header-only metadata, reproducing the earlier readiness dependency.
- Actual isolated-app browser checks preserve a short saved label, show/save
  the canonical LinkedIn name and successfully scan the same ad again. Bulk
  progress, remembered settings, Stop, earlier saves and unsaved-draft behavior
  also pass. Screenshots use fictional intercepted data only.
- Final isolated full regression: **1,894 passed, 4 skipped; 8,416 subtests**.
  All **64 JavaScript fixture files pass**, including after the final worker
  reinjection correction. Native companion scenarios pass on that final code.
- Source/native preflight, tracked-language checks, repository consistency and
  **24 live source-smoke assertions pass**. Windows x64 Antiword and Tesseract
  were functionally checked. No protected colleague build was produced.

## Boundaries and delivery

The 122 routes, ordered guards, 80 MiB limit, database/journal versions,
provider consent and non-replay, scan budgets, native country/company authority,
revisioned saves and orange lifecycle remain. No new extension permission,
provider/API call, outreach or hosting. Apollo activation remains deferred.
Owner source/server on port 5000, installation receipt, saved records and
active companion were not changed. Preview 5093 uses isolated state.

The live diagnosis establishes the CBS mismatch; synthetic browser coverage
does not claim an installed-extension live CBS rescan or compatibility with
every future LinkedIn layout. This is a local unmerged checkpoint. Apply the
companion update and refresh CV Studio/LinkedIn when using the new preview.
