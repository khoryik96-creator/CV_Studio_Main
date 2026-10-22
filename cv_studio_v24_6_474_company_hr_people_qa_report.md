# Historical — v24.6.474 Job Leads company HR people

The current release identity is always the root `VERSION` file. This document
records this milestone only.

## Scope and baseline

Owner requested a Phase 2 column for saved/shortlisted job ads: company-associated
LinkedIn HR people, optional country filtering, HR/hiring keywords and profile
links. Branch `codex/v24.6.474-job-leads-company-hr` starts from merged master
`15b89cff5612c511e227d52564bf75ddbd0f5d3a` (v24.6.473). No PR/merge was requested.

Active saved ads have an HR people button and a companion-backed column beside
Preview. Any country is default; an exact country name is optional. Search
options expose the requested keyword family, 1–15 pages (default 3) and an
optional company page override. Successful scans save names, visible titles,
locations, observed public profile URLs, matched terms, source/country/keywords
and scan time. A limited scan remains labelled when reopened. No hiring-authority
or independently verified employment claim is made.

The exact ad's company link is captured only when needed. Its company People
heading must match the saved ad company. A scoped, observed employee-search link
supplies the single Current company ID. Country selection uses the native visible
location control and one exact suggestion, then verifies the settled URL and
checked labels. IDs are never guessed. Searches stop on unknown layouts,
restrictions, source/filter/document changes, elapsed/page limits or failure.

## Preserved contracts

- Existing 120 routes and sealed hash
  `ee8d33baeb48b961a2f50723faacbeb7fed86b55454b3518ab4a07bcd1e90033`, five ordered
  guards and 80 MiB application request boundary remain.
- Job Leads adds one action on the existing guarded route; it remains non-paid.
  Its database stays schema 2, main SQLite schema 10 and journal schema 1.
  Bounded passive JSON evidence requires no schema migration.
- Atomic revision checks prevent late results overwriting a changed/deleted ad.
  Ordinary edits retain current HR evidence; changing the company/job clears it.
  Notes, manual contact, status, folder and creation date remain. Trash, folder
  moves and JSON backup/import retain evidence. Existing duplicate Add semantics
  remain; no automatic contact assignment is introduced.
- HR and existing Jobs/profile/capture runs cannot overlap. Worker suspension
  retains run limits and exact document/source authority in session memory,
  excluding profile content. Mutations are marked before clicks/navigation and
  cannot replay after ambiguity. Search source tabs are retained, existing user
  tabs are not navigated, and owned-tab cleanup rules remain.
- Four companion files, existing host permissions and protected-key boundaries
  remain. No provider request, outreach, LinkedIn write, login bypass, private
  API, new background worker or automatic startup recovery is added.

## Verification

- Failing-before/passing-after store coverage for absent HR persistence, then
  round-trip, ordinary edits, company changes, stale revisions, Trash/folder and
  backup retention, deduplication, hostile/bounded inputs and capacity rollback.
- Real guarded-route coverage proves cross-site rejection, structured stale
  conflicts, no-store responses and no paid-provider call. An initial new test
  required correction to accept the existing `no-store, max-age=0` header;
  production cache behavior was not changed.
- New reader fixtures exercise observed/scoped company identity, native exact
  country suggestions/checked state, title-only keyword matches, TA/data word
  boundaries, missing/empty results, pagination, duplicates and restrictions.
- Fresh-worker fixtures exercise binding, source/filter identity before/after
  injection, Any country without native location clicks, selected country,
  bounded pages across suspension/repeated Begin, interrupted mutation non-replay,
  busy-run isolation and retained sources.
- Actual-controller fixtures cover saved evidence, countries, pagination,
  deduplication, stale-save errors, text escaping, draft retention, Stop, old/busy
  companions, refreshed evidence and Trash. A final review found that temporary
  full-ad capture hid the saved HR panel; a reproducer failed before correction
  and passes now. HR uses the saved identity and locks saved-ad filters while
  scanning, preventing cross-ad display during progress.
- Final isolated Windows full Python: **1,765 passed, 4 skipped, 8,392 subtests**
  (179.79 seconds). All **45 JavaScript suites passed** after final UI changes.
- Syntax inventory, Git whitespace, repository consistency, owner-source
  validation/preflight and **24 live local source smoke assertions passed**.
  Native Windows Antiword was trusted/functional; Tesseract English was
  functional. No protected compilation/package or macOS native run was made.
- Browser QA used isolated temporary state at port 5084, fictional ads/people
  and a simulated companion. Worldwide scan saved three results; Singapore saved
  one. Reload retained evidence/country; switching ads separated their lists.
  Reading a full ad retained the HR column. The screenshot is an isolated demo,
  not real sourcing output.

## Limits and handover

Current live LinkedIn company headers, employee links, modern People cards and
native location suggestions/application were inspected read-only to ground the
selectors. No installed extension was replaced/armed and no end-to-end real HR
scan, account/credential change, paid call, outreach, owner-record mutation or
owner-receipt/installation change was performed. A live owner check is still
needed for their browser/account and any LinkedIn layout/language differences.

Reload the updated companion files, refresh LinkedIn and CV Studio and reconnect
the app tab before using this capability. The Codex preview demonstrates local
UI with simulated transport; actual LinkedIn scans require Chrome/Brave with the
connected companion. Results are bounded observations, not an exhaustive list.
