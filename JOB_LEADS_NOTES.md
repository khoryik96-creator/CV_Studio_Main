# Job Leads module

Current version is the repository-root `VERSION`. This owner-requested module
tracks LinkedIn job ads for business development, separately from the candidate
sourcer and the locked historical Lead Finder.

## Workflow

- Open **Job Leads** and paste a LinkedIn job link. Public company, role,
  location and description load directly, including in the in-app browser.
  **Fill from link** starts a new read. On a recognized public-unavailable or
  public-rate-limit failure, a connected, idle Chrome companion is tried once
  automatically (v24.6.456). A short read-only bound-status probe avoids a long
  capture timeout when disconnected; an active profile/Jobs/capture run is left
  alone. No public request or browser capture is automatically repeated.
  Setup expands when the companion is unavailable or a capture fails.
  Existing manual entries are preserved.
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

## LinkedIn job discovery and content (v24.6.455)

Job Leads has a collapsed **Find job ads on LinkedIn** panel. The connected
Chrome companion opens a keyword/location Jobs search, or reads an explicitly
chosen already-open Jobs search while retaining its filters. It reads visible
cards, scrolls the recognized results list and uses recognized job pagination.
Limits are 1–15 pages, eight scrolls per page, ten minutes and 600 unique ads.
No AI provider or public per-link lookup is used for discovery. Search summaries
are explicitly labelled; Read full ad optionally captures the selected ad.
Selecting results and Add selected to list uses the established save route.
Existing duplicates, including Trash, are never overwritten. A partial storage
failure leaves the remaining selections available; existing manual drafts are
not replaced. Stop prevents further reads/paging and retains collected results.
New search tabs remain open for the user; existing tabs are not repurposed.

Job searches have their own companion run kind and source/filter identity,
with the existing binding, document revalidation, session-memory persistence
and fail-closed storage behavior. Page/scroll budgets survive worker suspension
and repeated Begin. Search filters/host changes, challenges and access limits
stop the run; no bypass, application, message, cookie access, provider call or
remote save is added. No new routes, schemas or extension permissions.

Single-ad capture now polls the same loaded DOM for up to 16 reads separated
by 350 ms when recognized detail fields are still loading. URL/pending URL and
binding are rechecked each time; this is not a network or navigation retry.
Missing description gets a shorter readiness allowance before metadata returns.

Rich formatting unwraps nested layout divs into proper sibling paragraphs,
headings and lists, retaining only the bounded passive semantic tree. Existing
nested paragraph captures flatten at display time, and explicit plain-text
bullet markers render as lists. Saved description text is not rewritten.
The manually selected Save to folder default is retained in origin-local browser
UI storage. New leads/captures use that choice; editing an existing ad uses its
own folder. Explicit Unfiled is remembered, deletion clears the matching default,
and reload discards a preference for a folder that no longer exists.

`test_linkedin_job_search.js`, `test_job_search_reader.js` and
`test_job_search_frontend.js` cover authority/budgets, scoped extraction and
the actual controller with synthetic companion messages. The existing Job Leads
and link-capture suites cover sticky folders, legacy/plain formatting, delayed
DOM readiness and fixed timeout behavior. Refresh/reload the downloaded v455
companion and reconnect the CV Studio Chrome tab to use the new actions.

The v456 `jobStatus` probe is behind the same exact app tab/document check and
returns only connected/capability/busy flags. It never arms the companion or
opens, reads, navigates or closes a LinkedIn tab. Automatic link fallback is
limited to `JOB_AD_UNAVAILABLE`/`JOB_AD_RATE_LIMITED`; storage, security, busy
and unrelated failures do not trigger it. The existing canonical URL checks,
single-capture lock, source-switch confirmation, optional manual contact/status,
rich formatting and empty-refresh protection apply to fallback results too.
`test_job_read_fallback_frontend.js` covers these flows and preservation on a
missing, busy, timed-out, failing or mismatched companion. Existing installations
need the v456 companion's updated files, Reload and app-tab reconnection.

## Current LinkedIn search layout (v24.6.457)

The current signed-in page inspected in Brave uses `/jobs/search-results/`
and a rendered `[componentkey="SearchResultsMainContent"]` result region.
Its job cards are buttons with `job-card-component-ref-<numeric job ID>`
component keys and ordered title/company/location paragraphs, with no job-view
anchors. The reader accepts this DOM layout alongside the existing linked-card
layout. It never reads hidden React state, tracking payloads, cookies or network
responses. Wrong/mixed card identities, missing title/company, duplicate cards
and oversized snapshots remain rejected/bounded. Modern Next is confined to
the results region and a parent containing numbered Page buttons.

`/jobs/search/` and `/jobs/search-results/` share one source identity; selected
job/paging/tracking fields (including `eBP`) are excluded, while actual search
filters remain pinned. Selected modern search links also canonicalize to the
same job-view ID in the backend, controller and worker. Modern ad capture uses
the same-job title link and exact `JobDetails_AboutTheJob_<ID>` region, requires
one company and substantive description, and rejects stale/ambiguous panels.
It retains passive source formatting and labels collapsed/truncated content.
Relative posting ages remain unconverted.

Search now probes `jobStatus` with a one-second bound before opening a source,
clearing old results or sending End. Disconnected, busy or older companions
leave the previous results intact and receive distinct guidance. Stop during
this readiness check sends no unrelated End. The `job_search` capability flag
identifies a current companion; update/reload/reconnect its v457 files.
The in-app Codex preview has no Chrome companion and cannot execute search.

Live read-only DOM inspection found 25 readable unique cards, zero normal
job-view links, and recognized paging/scrolling on the owner-opened page. This
verifies the observed selectors, not a complete installed-extension run.
Synthetic modern fixtures cover card identities/field order, scoped paging,
loading/stale description panels and bounds. Existing legacy fixtures remain.

## Preview and direct LinkedIn capture (v24.6.459)

Results have a Preview action and an in-app panel. Read full ad fills this
panel using the existing companion read, and Add this ad saves only that ad.
Other checkbox selections remain available for Add selected to list. Plain
summaries, captured content and excerpts stay explicitly labelled; no LinkedIn
iframe or remote HTML execution is used.

The updated companion's existing four-file package also runs its reader/content
scripts on `https://www.linkedin.com/jobs/*`. Existing host permissions are
unchanged. Recognized rendered cards and loaded job-view pages receive an Add
to CV Studio button. It acts only on a trusted user click, reads that visible
job identity again and never presses LinkedIn Save, Apply or messaging controls.
Injected control text is excluded from ad content. DOM updates do not duplicate
controls. It uses Save selected and LinkedIn ads to folder in the connected
Job Leads tab. Keep that tab open; refresh both pages after extension updates.

Direct captures require a top-frame LinkedIn sender, the same source document,
canonical observed job identity and an idle companion. They are forwarded to
the exact previously connected app document, correlated through its initialized
Job Leads channel and saved using the existing same-origin guarded API.
Busy/replaced/disconnected pages reject visibly; no ambiguous write is replayed.
Duplicate saves retain existing data, including Trash, and manual draft fields
are untouched. No new route, schema, provider call or remote LinkedIn write.

Live diagnosis of the v458 owner page found that LinkedIn removed `location`
from the opened search URL while its rendered location button still said
Malaysia. Exact URL comparison stopped discovery before results arrived. A
new-search-only initial handshake now checks unchanged keyword/filter identity,
reads the recognized location control and pins the resolved search identity.
Missing location UI waits within existing limits; a different location or
changed keywords rejects with readable guidance. Open-search mode and all
later reads retain strict filter identity, counters, deadlines and guards.

The v460 review corrective identifies the modern location control through its
visible Location accessibility label (on the control or its child). Other
expandable header filters and the promoted-jobs/AI-search help controls are
excluded. Read-only live inspection confirmed the nested label and both help
controls. Multiple conflicting recognized locations still reject; unrecognized
location UI remains loading within the existing budget.

## Verification (existing contracts)

### LinkedIn controls (v24.6.461)

The owner confirmed that updating/reloading the wrong companion version resolved
the missing-results report. Readiness now reports the manifest version and an
explicit current-search revision; older companions stop before results are cleared
or a source tab opens. Known reader-start/read failures return fixed guidance,
without exposing raw browser errors or document information.

LinkedIn cards place controls in an existing vertical text column. They never
add a competing flex-row column or change native card styles; unrecognized
horizontal/grid containers receive no inline controls. Summary extraction excludes
the injected controls even when a native footer follows them.

Added is a reversible toggle: removal calls the established revision-guarded
Trash operation, and explicit Add restores the same stored lead. Contact, notes,
status and follow-up details remain. A selected destination can move the restored
lead afterward through the existing guarded operation. If restore succeeds but a
subsequent move fails, the result stays Added in its actual folder with a visible
warning; no write is replayed. A lead currently open for editing in CV Studio
cannot be removed/moved through the companion, preserving that draft.

The LinkedIn folder selector loads from the exact connected Job Leads tab.
New folder creates a folder without saving an ad and selects it for subsequent
adds. Chosen folders carry across the page's controls. All operations still require
an explicit trusted interaction, a visible canonical ad, exact source/destination
documents and an idle companion. Folder names are rendered as text. No new route,
schema, permission, LinkedIn write or provider call exists.

Both the v461 app and companion are needed for folders/removal. An older local
page rejects management commands visibly rather than treating them as legacy
adds. Existing ordinary direct-add messages remain compatible. Replace/reload
the companion files, refresh both pages and reconnect the intended app tab.

The v458 review corrective makes the numeric empty-result check match only a
standalone zero count. A header such as `10 jobs`, `100 jobs` or `1,000 jobs`
can appear before its cards; that remains a loading snapshot rather than ending
discovery with no ads. Both legacy and modern DOM fixtures cover positive
counts before cards, real zero/no-result messages and delayed card readiness.

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
