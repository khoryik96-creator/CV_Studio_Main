# CV Studio v24.6.473 — Idempotent companion Add

Historical QA record; root `VERSION` is authoritative.

PR #237 re-review identified a P2 timing gap in v472: another CV Studio window
could save an ad after its metadata preflight reported unsaved. The final capture
handler could then treat the selected new-ad destination as a requested move of
that existing record. No actual owner records were changed during diagnosis.

The Add handler now returns an existing active record as a duplicate before
entering the destination validation/move branch. It performs no save, removal,
folder move or field update for that duplicate. A record appearing later, during
the final save, is protected by the existing `BEGIN IMMEDIATE` and URL duplicate
check in `JobLeadsStore.save`; its unchanged record/folder is returned and no move
follows. No new schema, route, lock, token, revision or worker contract is needed.

New actual-controller regressions reproduce both timing windows. The first reads
unsaved metadata, inserts a synthetic record in Keep original, then requests Add
into SAP; it requires the original folder, notes, contact and revision to remain
identical with zero write requests. This failed on v472 (folder became SAP), then
passed. The second inserts a duplicate during the mocked atomic save and proves
the unchanged record is returned without a folder-move request. Store transaction
and cross-connection duplicate behavior retain the existing Python coverage.

Existing explicit Move to folder, Trash restoration into a chosen folder,
partial restore/move failure, unsaved/editing draft guards, new-ad destinations,
source binding, version and provider boundaries remain covered. The v472
preflight still avoids an unnecessary write for an already-known active record;
this final guard covers the time between that read and the Add handler/save.

All **42 JavaScript suites passed**. Full isolated Windows Python:
**1,750 passed, four skipped, 8,392 subtests**, 137.10 seconds. Static/syntax,
repository consistency and Windows source/native preflight passed, including
trusted functional Antiword, Tesseract/English and **24 source smoke assertions**.
Exact-head PR CI/review results are recorded in issue #35 before merge.
No live LinkedIn/provider call,
owner records/installation/receipt/credentials, protected build or local native
macOS test is involved. This correction is within the owner's authorized merge.
