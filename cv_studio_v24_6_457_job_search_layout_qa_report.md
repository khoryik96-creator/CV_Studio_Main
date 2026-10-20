# CV Studio v24.6.457 — current LinkedIn job layout and search readiness

Owner report: Job Leads search did not work. The owner confirmed trying only
the Codex in-app preview. Its visible status was the companion-response timeout,
not a LinkedIn results response. The companion runs in a connected Chrome tab;
it cannot service requests from the in-app preview.

Branch `codex/v24.6.457-job-search-layout` continues unmerged v456 `8340c63`.

## Confirmed layout issue

Read-only inspection of the owner's already-open signed-in LinkedIn Jobs page
in Brave also found a real compatibility defect. The current page is
`/jobs/search-results/`; its rendered SearchResultsMainContent region contains
25 job-card buttons with numeric job IDs in `job-card-component-ref-<ID>`
component keys and ordered title/company/location paragraphs. There are zero
ordinary job-view anchors in that result region. The old path allowlist and
anchor-only reader therefore could not capture it even after connecting.

The new reader supports both this observed layout and the established linked
cards. It uses visible DOM and rendered component identities, with no hidden
React state, tracking-payload parsing, cookies, network interception or login
bypass. It excludes malformed/mixed identities and missing title/company,
deduplicates canonical URLs and keeps the existing 40-row snapshot limit.
Modern Next must be in the result region and share a parent with numbered Page
buttons. Existing scroll/page/deadline/session-memory bounds remain.

The two search paths canonicalize to one source identity. Selected job,
navigation and tracking fields including eBP do not change that identity;
actual filters remain pinned. Backend, frontend and companion canonicalizers
also accept a single selected job on the modern path, rejecting absent or
duplicate selected IDs as before.

Modern ad capture requires the same-job visible title link, exactly one company
and the matching JobDetails_AboutTheJob_<ID> region. Loading-only headings,
stale titles, mismatched descriptions and ambiguous companies are rejected.
Descriptions keep passive source markup and explicit truncation information;
relative posting ages are never converted to guessed dates.

## Search readiness correction

Before clearing results or opening a browser search, the controller now checks
the bound companion with a one-second response bound. Disconnected, old or busy
companions produce distinct guidance and preserve previous results/selections.
No unrelated End is sent if a run was never started, including Stop during
readiness. The job_search capability flag requires the updated companion.
The initial panel guidance clearly separates browser search from saved-ad and
public-link reads available in the Codex preview.

## Verification

Performed on Windows x64 on 20 October 2026 with isolated receipts/state.

- Full unfiltered Python suite: **1,737 passed, four skipped, 7,599 subtests
  passed**, 182.15 seconds. The five additional selected-link tests cover valid
  modern aliases and missing/duplicate job IDs. Focused Job Leads: 49 passed.
- **All 39 JavaScript suites passed.** The new modern DOM fixture covers keyed
  identity, field ordering, missing-title safety, deduplication/40-row bounds,
  unrelated Next rejection, scoped scrolling/paging, same-job description,
  loading-only headings, stale/ambiguous content and hostile hosts. Existing
  legacy, date, profile, lifecycle, fallback and batch suites remain passing.
- Controller tests verify disconnected/old/busy readiness opens no source and
  sends no End, leaves prior results intact and unlocks controls. Worker tests
  verify path aliases/selected-card tracking across suspension while changed
  real filters still reject reads. Existing source/run/budget safeguards remain.
- Live read-only DOM checks verified 25 readable unique modern cards, zero
  normal job links, a recognized pagination control and a scrollable results
  region. Only aggregate structural evidence is retained in ignored runtime;
  no unrelated page content enters fixtures or source evidence.
- Actual in-app preview confirms the new fast disconnected message and
  restored controls. The owner saved rows remain untouched. This test does not
  simulate a successful connection inside the unsupported in-app browser.
- Syntax/repository/whitespace checks, owner-source preflight and 24 source
  smoke assertions pass, including genuine bundled Windows Antiword/Tesseract
  functional checks. No protected compilation or native macOS claim.
- Persistent source preview 5074 is v24.6.457. Read-only before/after SQL value
  hashes verify both saved rows exactly preserved. Earlier draft tabs are kept;
  the installed port-5000 app and its authorization are untouched.

## Limits and preserved boundaries

The live checks verify rendered selectors, not a complete installed-companion
search/import session. A separate fresh navigation check could not be completed
through the available browser controls. No live pagination, login, extension
installation, account/permission change, application or message was performed.
The owner must update/reload the companion and connect the CV Studio tab in
Chrome. Using an already-open filtered Jobs search provides the observed source
layout directly. If LinkedIn changes real filters or presents an access check,
the run still stops; it does not weaken identity checks to keep searching.

All 120 routes/digest, five guards, 80 MiB limit, main SQLite schema 10, dedicated
Job Leads schema 2, journal schema 1 and extension permissions remain. Existing
save/draft/Trash/folder/provider contracts are preserved. No paid call, external
write, owner saved-data mutation, new route/migration, push, PR or merge.
