# CV Studio v24.6.469 — Folder-selection preview synchronization

Historical QA record; root `VERSION` is authoritative.

The v468 review found that Create folder selected its folder programmatically
after loading records, then refreshed only the saved list. The preview's new
filter synchronization ran only for manual input/change events. An empty folder
could therefore show zero leads while keeping the prior ad, its old count and
an enabled Trash action.

`applySavedFilters()` now owns the existing list/preview synchronization. Both
manual filter changes and the successful Create folder path call it after
selecting the folder. It retains the existing saved/search preview distinction
and dismissal flag. Only an out-of-filter saved preview is reset; matching
records are selected normally. Search selections, closed previews, notes and
drafts are preserved. Folder selection issues no ad update/removal request.

New actual-controller checks fail on v468 before correction and pass afterward:

- A new empty folder clears the previous preview, count and Trash action,
  disables ad navigation and preserves every saved record and unsaved note.
- Selecting an existing populated folder through Create folder previews its
  first matching ad and navigates within that folder with the correct count.
- A dismissed preview stays dismissed through folder creation.
- Folder creation during search review preserves the search preview and picked
  results. Existing manual-filter, navigation, Trash/restore, failure/discard,
  direct-companion and document-formatting coverage remains unchanged.

All **42 JavaScript suites passed**. Full isolated Windows Python regression:
**1,750 passed, four skipped, 8,392 subtests**, 175.74 seconds. Receipt, SQLite,
job journal, salary and credential state were isolated before collection.
The in-app browser was available for this
corrective: the actual controller and local store, with three fictional ads,
showed a saved preview before Create folder and an empty preview/zero matching
leads afterward. The total remained three saved records; the previous count,
content and management buttons were cleared. Evidence remains ignored locally.

- Tracked Python/JavaScript/PowerShell/shell syntax, whitespace and repository
  consistency checks passed. Windows owner-source native preflight verified
  Antiword and Tesseract/English; **24 live source smoke assertions passed**.
  No protected compilation or local native macOS test occurred.

PR CI and merge identity are recorded separately
in the coordination log. The owner authorized fixing the findings and merging
both v468 and this corrective. No owner records/receipt/installation change,
live LinkedIn/provider call, route/schema change or protected build is involved.
