# CV Studio v24.6.468 — Job Leads preview controls

Historical QA record; root `VERSION` is authoritative.

The reported screenshot showed zero temporary search results beside a saved-ad
preview. The existing Previous/Next results buttons only paged search cards;
they could not browse saved previews, and that preview had no dismissal or
record-management controls. Its automatic fallback also reopened a saved ad
when search results were cleared.

The preview now tracks its source, displays its position and has Previous ad,
Next ad and Close preview controls. Saved navigation follows existing filters.
Search ad navigation follows the result across page boundaries, while results
page buttons select their page's first result. Pagination is hidden without
multiple result pages. The empty search column no longer consumes half the
preview's width. Closing or clearing results does not change saved ads, selected
checkboxes or an editing draft, and ordinary redraws do not reopen the preview.

Saved previews offer Move to Trash / Restore ad through the existing guarded
operation, preserving revision checks, discard confirmation and recoverability.
After a successful saved-preview operation, the next matching ad is shown; with
none remaining, the preview clears. Search results retain the selected ad and
reflect its current saved/Trash state. Failures and cancelled discard checks
leave the current preview intact. No route, schema, permanent deletion, paid
call, companion authority or unrelated formatting behavior changed.

Validation:

- The new controller regression failed against v467 before implementation.
  It covers multiple saved ads, both navigation bounds, filtered navigation,
  dismissal across refresh and redraw, stale-write failure, Trash/restore,
  preserved notes, cancelled discard, the last matching ad, 23 search results
  across two result pages, retained selections and no implicit record writes.
- All **42 JavaScript suites passed**, including existing Job Leads, public
  link fallback, companion/direct capture, profile sourcing and formatting tests.
- Full isolated Windows Python: **1,750 passed, four skipped, 8,392 subtests**,
  174.01 seconds. Receipt, SQLite, journal, salary and credential state use
  temporary directories before collection. No owner receipt was replaced.
- Actual in-app browser checks used the real app/controller and local store
  with three fictional records. Next ad changed the visible role; Move to Trash
  advanced to the next ad; selecting Trash enabled Restore ad and restoration
  returned the original record. A simulated 23-result search verified page 2
  selected result 21 and Previous ad selected result 20 on page 1. Clear results
  left an empty preview until an explicit saved-card Preview action. The actual
  screenshot confirms a full-width saved preview with the new controls at the
  browser's ordinary narrow viewport. Evidence stays in ignored runtime files.

- Tracked Python, JavaScript, PowerShell and shell syntax, whitespace and
  repository consistency checks passed. Windows owner-source native preflight
  verified Antiword and Tesseract/English, and **24 live source smoke assertions
  passed**. No protected compilation or local native macOS testing occurred.

No live LinkedIn or AI provider call occurred. The browser QA preview uses a simulated companion;
this does not claim an installed-extension search was performed. Owner records,
installed app, receipts and existing source previews remain unchanged. This
work ends at a local source checkpoint, before a separately requested PR/merge.
