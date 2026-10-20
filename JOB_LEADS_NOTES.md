# Job Leads module

Current version is the repository-root `VERSION`. This owner-requested module
tracks LinkedIn job ads for business development, separately from the candidate
sourcer and the locked historical Lead Finder.

## Workflow

- Open **Job Leads** and paste a LinkedIn job link. Public company, role,
  location and description load directly, including in the in-app browser.
  **Fill from link** retries the read. Existing manual entries are preserved.
  Review the details before saving; manual entry remains available.
  Replacing an unsaved draft's job link asks before clearing its job-specific
  fields. The folder is retained; a cancelled or failed read keeps the old URL
  and details. Same-job manual corrections remain. Save independently rejects
  a different URL that has not been loaded into this draft; saved leads require
  New lead before switching to another job.
- Optional fields: contact person, location, posting date, notes, status,
  follow-up date and retained job-description text. Contact is always manual and optional;
  status starts as New and follow-up dates are never inferred from the ad.
  Follow-ups due are shown in the module;
  this is not a scheduled notification or outreach service.
- **Create folder** creates a saved folder even before it contains an ad.
  Choose a named folder in the Folder menu to enable **Delete folder**.
  Deleting it moves its ads to Unfiled without deleting them; trashed ads stay
  in Trash. The confirmation includes every ad in that folder, and concurrent
  changes reject the operation atomically. **Save to folder** still accepts an
  existing or new name when saving an individual ad.
- Tick **Select** on saved cards (or **Select ads on this page**), choose
  **Move to folder**, then **Move selected**. This files ads after reviewing
  them; it does not change their notes, content, status or creation date.
  Search/folder/status changes clear selections. Trash must be restored before
  it can be selected. Unsaved edits on a selected ad require discard confirmation.
- **Date created** shows the original local save timestamp on each card and in
  the edit form. It is separate from LinkedIn's posting date, remains stable
  through edits/Trash/restore, and is retained when restoring a current backup.
  Legacy backups without a creation timestamp use the time they are imported.
- For login-only ads, the optional Chrome fallback can fill a draft. Install/reload the latest bundled companion,
  arm it from the CV Studio toolbar icon, open a job ad and use **Refresh job
  tabs → Read job ad**. Review the fields before saving. Manual entry works
  without the companion. Public reads need no extension; neither path uses AI
  or incurs provider charges.
- **Date posted** fills only when the same job supplies valid exact date
  metadata. Source calendar dates are preserved across time zones; relative
  ages are not converted into guessed dates. It can also be entered manually.
  Older leads and ads without exact metadata show **Posted: Not available**.
- Expand **View more — job ad content** on a saved lead to read its captured
  description without reopening LinkedIn or making a network call. The draft
  has the same expandable section with editable text. Captured excerpts are
  labelled, and missing descriptions explain how to add one. Headings, paragraphs,
  bold/italic text and lists are retained as a bounded semantic tree, with no
  source attributes, styles, media, scripts or executable HTML. Plain text is
  retained for editing/CSV and remains bounded to 20,000 characters.
  **Edit or paste job content** accepts formatted clipboard content into an empty
  or fully selected field; ordinary text edits replace its rich formatting.
  For older plain-text captures, use **Refresh ad content**, review and save.
  Failed or empty refreshes preserve the existing draft. The LinkedIn link stays available.
- Search saved leads, filter by status or due date, and edit/view details.
  Re-saving the same LinkedIn job preserves the existing record and notes.
  **Delete**, **Clear shown ads** and **Clear all ads** move records into
  recoverable Trash. Clear shown ads affects the current folder/search/status
  selection across all its pages; Clear all ads affects every active folder.
  Bulk actions confirm the count. Select Trash and **Restore** to return a lead
  to its original folder. There is no permanent purge; Trash still counts toward
  storage limits and is retained in JSON backups. Stale selections fail atomically.
- **More options** keeps CSV export, backup/import and bulk clearing collapsed
  until needed. **Back up saved ads** exports all records as Job Leads JSON.
  **Import backup** validates the entire file before
  adding missing job IDs in one transaction; existing records are never replaced.
  Current version-2 backups include empty folders; version-1 backups remain
  readable. This dedicated backup is separate from Settings' legacy local-data backup.
  Posting dates are included in CSV, and JSON backup/restore also retains the
  description excerpt marker, rich content, folders and Trash state. CSV also
  includes folder and creation date. Existing records retain all their data.
- Job Leads inputs use visible labels without placeholder text, including search.

## Boundaries

`cvstudio_job_leads.py` owns a dedicated `job_leads.sqlite3` in the existing
per-user state directory. It opens lazily, checks integrity/application/schema
identity, creates and verifies a consistent backup before initial schema creation,
and serializes writes using SQLite transactions. This store has its own schema 2;
the existing application database remains schema 10 and the job journal schema 1.
An integrity-verified database backup precedes initial creation or the additive
v1-to-v2 folder-table migration. Migration imports existing folder names without
rewriting lead rows, is transactional and can retry after failure. Earlier source
versions reject the newer database rather than silently dropping folder metadata.
Initialization is restart-safe, failed writes roll back and errors are visible.
Revisions prevent an older browser draft overwriting a newer saved edit.
Unknown fields are discarded rather than persisted; links retain only canonical
LinkedIn job IDs. No credentials, AI/provider calls,
LinkedIn messages, applications, JobAdder writes or background worker are added.

`cvstudio_job_ads.py` reads public job HTML only, through the existing guarded
`/job-leads` lookup action. The server constructs a canonical LinkedIn URL;
each redirect must remain on an approved LinkedIn job host and the same job ID.
No request cookies, auth headers, .netrc credentials or tracking queries are
forwarded. The reader limits size to 4 MiB, caps redirects/concurrent reads and
uses network/deadline bounds. It performs no automatic retry or login bypass.
JSON-LD JobPosting identities or a canonical public top card supply the fields;
search headers, recommended jobs and ambiguous identity mismatches are rejected.
No public content is stored until the owner clicks Save lead. Request failures
leave manual entries intact and offer the explicit Chrome/manual fallback.
LinkedIn HTTP 429 is reported separately as temporary public-read limiting;
there is no automatic retry or login/rate-limit bypass. The Chrome fallback
requires this CV Studio address and the connected companion in Chrome; it
cannot operate from the in-app browser. Saved job content remains available
locally through Edit / view details and View more.

The store is bounded to 5,000 leads and 8 MiB of field payload. Individual text
fields and a 12 MiB route/import limit are enforced. Backup/import limits cover
the bounded store. Contacts/notes are local user content, excluded from logs,
tests and diagnostic evidence except synthetic fixtures.

`app.py` owns only the guarded GET/POST `/job-leads` adapter and constructs the
store. All five existing guards remain. This non-AI route is deliberately not a
paid route. The new seal is 120 routes:
`ee8d33baeb48b961a2f50723faacbeb7fed86b55454b3518ab4a07bcd1e90033`.
Excluding `job_leads` exactly reproduces the v446 119-route contract; excluding
both new modules still reproduces the merged v445 118-route contract.

The companion supports `jobTabs`, `jobRead` and `jobFromLink` after its bound app
document check. Link fill reuses a matching job tab or opens only the explicitly
pasted canonical LinkedIn job URL in one temporary inactive tab. It never
navigates or closes a pre-existing tab. Cleanup closes only an unchanged inactive
tab created for that read; navigated/activated tabs are retained. One capture runs
at a time and a sourcing run cannot start midway through it.
Job capture requires a matching canonical job ID,
completed loading and a recognized visible detail panel. Search-panel title
links must confirm the selected job ID to reject stale SPA content. It stops
on unknown layouts, access challenges, navigation or an active sourcing run.
Capture performs no LinkedIn click, application, message or remote save;
it only fills an unsaved CV Studio draft. Its four-file packaging,
permissions and provider/key isolation remain unchanged.

## Verification

`tests/test_job_leads.py` covers canonical identities, rejection of unsafe URLs,
durability, duplicate and stale-write protection, cross-process-style concurrent
connections, backup verification, corruption, atomic restore/rollback, route
guards, request IDs and the previous route digest. `test_job_leads_frontend.js`
covers bound job-only capture, source invalidation, sourcing isolation, draft
protection, DOM text safety and spreadsheet-safe CSV output. Native Chrome uses
synthetic intercepted LinkedIn pages and a simulated companion; actual extension
installation and current live LinkedIn layouts still need owner-driven checking.
`test_job_link_autofill_frontend.js` adds link/canonical URL constraints,
existing-tab reuse, owned-tab cleanup, timeout and concurrent-run/reload checks.
`test_job_ads.py` adds no-network public HTML extraction, same-job redirects,
identity/size/type/auth restrictions, timeouts, ambiguity and concurrency checks.
The owner-reported public ad was verified end-to-end in the real in-app browser
after v449; that does not establish all LinkedIn layouts or login-only access.

The source preview on port 5074 uses isolated state kept across its own restarts.
It is separate from the installed owner app on port 5000. The preview state path
is retained only in ignored runtime configuration. No user data was used for QA.
