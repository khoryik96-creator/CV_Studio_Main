# Job Leads explicit folders and read diagnosis — v24.6.454

Owner request: Create folder/Delete folder buttons, filing shortlisted saved
ads afterward, and diagnosis of job ads that read yesterday but fail today.
Branch `codex/v24.6.454-job-leads-folder-controls` from local v453 `e472cb8`.

## Behavior

- Create folder persists an empty named folder. Saving to a typed new folder
  remains supported. New folders prefill an otherwise untouched new-ad form.
- Delete folder is enabled when a named folder is selected. Confirmation gives
  the affected count. Ads move to Unfiled; no ads are deleted, and trashed ads
  remain trashed. The entire operation rejects a stale folder membership or
  record revision, retaining current data.
- Individual Select checkboxes and Select ads on this page allow already-saved
  ads to be moved together. The destination controls appear only while selected.
  Filter changes clear selection; moves preserve content, notes, dates and status.
  A selected ad with unsaved edits requires discard confirmation; failed moves
  retain its draft. Existing row/bulk Trash and Restore behavior stays intact.
- All new fields have visible labels and no placeholders. Backup/import and
  bulk clear controls stay collapsed under More options.

## Persistence and compatibility

The dedicated Job Leads database moves from schema 1 to 2 with one additive
folder table. An integrity-verified database backup is created before initial
creation or migration. Folder names are imported from existing rows without
rewriting lead data, IDs, revisions or timestamps. Migration is transactional,
restart-safe and idempotent. A failure rolls back to the original schema.

Folders have bounded names/count/bytes. Moves and deletion use transactions
and revision-checked selections. Backup format 2 retains empty folders; format-1
backups remain readable, and imports still leave existing ad records unchanged.
Older app versions reject schema 2 instead of silently ignoring folder metadata.
Core schema 10, journal 1, the 120-route digest, five request guards and 80 MiB
global request limit remain unchanged. All actions use the existing guarded route.

## Read failure diagnosis

The owner-visible job URL reproduced the old generic unavailable response. A
bounded read through the production public-reader transport observed **HTTP
429** directly from LinkedIn. This is public-request limiting, not a parser
failure demonstrated by this incident. No public availability recovery is claimed.

The reader now returns `JOB_AD_RATE_LIMITED` with status 429 and a clear message:
try later or use the connected Chrome companion for an ad visible in Chrome.
The companion timeout also explains its Chrome requirement. Existing saved
content is local and remains accessible. No automatic retry, alternate-identity
request, login/rate-limit bypass, credential forwarding or paid call was added.
No raw ad content or owner contact/notes entered this report or tracked fixtures.

## Verification

- New folder/migration and rate-limit cases reproduced **14 failures before
  implementation**, then passed. Tests cover empty-folder reopen/backup,
  legacy migration/exact rows, verified backup, migration rollback/retry, stale
  atomic moves/deletion, active versus trashed state, bounds and legacy imports.
- **126 focused Python tests passed.**
- **All 35 JavaScript suites passed**, including added actual-controller folder
  scenarios for selection, moving, cancellation, failed/stale moves, dirty drafts,
  deleting empty/nonempty folders and preserving notes/creation timestamps.
- **Full unfiltered isolated Windows regression: 1,731 passed, four skipped,
  7,599 subtests, no failures or deselections, 218.88 seconds.** Uses the ignored
  exact dependency directory established for v452 and isolated receipt/app paths.
- Syntax/byte/source inventories, repository consistency, owner-source preflight,
  native Antiword/Tesseract/adm-zip checks and **24 smoke assertions passed**.
  A final wording-only companion-timeout adjustment was followed by another
  JavaScript syntax check and Job Leads frontend pass.
- Actual separate synthetic browser preview: created an empty folder, selected
  two saved ads, moved both into it, deleted it through confirmation, and verified
  both ads remained Unfiled with their original creation dates. A synthetic 429
  verified the new message and preserved draft. No live request in these UI cases.
- Persistent source preview 5074 was restarted after confirming no active
  sourcing run. Before/after hashes confirmed its two saved lead rows remained
  byte-for-byte identical through migration, with a verified backup retained.
  Earlier drafts were kept open. Synthetic test server was stopped afterward.

No saved owner ad was edited, moved or deleted during verification. The isolated
source-preview schema upgrade was verified; the installed owner app on port 5000
and its receipt remain untouched. No protected package, push, PR or merge occurred.
