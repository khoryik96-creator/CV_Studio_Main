# CV Studio v24.6.462 — Job Leads preview and companion controls

Historical QA record; root `VERSION` remains the version reference.

The owner requested better folder/dropdown/New folder styling and reported the
preview empty for both direct LinkedIn additions and in-app search. Inspection
found that the preview only resolved temporary discovery results: saved records
and direct additions could not populate it, and reloading lost its entire source.
Normal search selection already worked in the isolated baseline fixture. No live
installed-companion search failure was reproduced or attributed to a new cause.

Preview now resolves saved ads and discovery results, defaults to an active saved
ad after reload, and selects direct LinkedIn additions or a saved card's new
Preview action. Search still selects its first result and allows explicit
switching. Search-only counts and bulk selection are unchanged. Saved ads in
Trash cannot be duplicated through the preview. Empty previews hide unavailable
actions and give clear next steps.

Full reads of saved ads populate only a temporary preview. No saved content,
tracking fields or unsaved draft is replaced. A refreshed saved list restores
authoritative content. Existing edit/refresh/save remains the explicit path to
persist changed content. No routes, schemas or capture protocol changed.

Companion folder selectors, New folder, name input and Create share consistent
height, spacing, rounded borders and teal accents. Added retains its reversible
action in its accessible label and title. Native text-column mounting, inline-size
containment and text wrapping are preserved. No new asset or permission exists.

## Verification

- Full isolated Windows Python suite: **1,737 passed, four skipped, 7,599
  subtests passed**, 180.70 seconds. **All 41 JavaScript suites passed.**
- Focused frontend coverage verifies saved previews after reload, empty state,
  saved-card Preview, full reads without durable writes or draft replacement,
  temporary-preview invalidation on refresh, direct-add selection, Trash state,
  multi-page discovery, first-result preview, switching, rich content, selected
  imports, partial failures, Stop, 15-page bounds and readiness preservation.
- Actual controller/backend fixture with fictional data and simulated companion
  transport showed a saved Finance Manager ad before searching, automatically
  previewed the first search result, switched to FP&A Manager and rendered full
  headings, bold text and bullets. Direct Add switched the preview to SAP Finance
  Lead immediately while retaining the unsaved note. All writes were confined
  to the fixture's temporary database.
- Actual companion content-script layout fixture verified folder creation and
  selection, Added state and a long error. Wide (450 px), narrow (280 px) and grid
  (350 px) cards retained text widths of **330.3125, 196 and 266 px** before and
  after actions. No horizontal overflow occurred. Screenshots remain ignored
  local QA artifacts, with fictional data.
- Source syntax, repository consistency, whitespace and native-dependency
  preflight passed, including genuine bundled Windows Antiword and
  Tesseract/English functional checks. All **24 source smoke assertions passed**.
  No protected compilation or native Mac claim.

Four-file ZIP verified byte-for-byte against current source, manifest 24.6.462:
`6bc400738207bfd6fbdf4c77ef38117c425e1d60962d2f349c24fcf18a475052`.
The source preview on 5077 uses a read-only SQLite backup of the previous isolated
preview, verified table-by-table and with `PRAGMA integrity_check`. Its original
database, installed owner app, installation receipt and owner leads are unchanged.
The source preview visibly displayed its saved Wipro SAP MM Lead Consultant ad
without rerunning search. Disposable fixture tabs were closed and both fixture
servers stopped; only the source preview remains available.

Normal Chrome/Brave was unavailable to browser tooling. Browser QA therefore uses
simulated transport and cannot establish current live LinkedIn compatibility or
successful installation of the new companion. No paid call, LinkedIn write,
schema change, push, PR, merge or installed-app update belongs to this checkpoint.
