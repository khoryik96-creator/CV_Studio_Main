# Job Leads module

Current version is the repository-root `VERSION`. This owner-requested module
tracks LinkedIn job ads for business development, separately from the candidate
sourcer and the locked historical Lead Finder.

## Workflow

- Open **Job Leads**, paste the LinkedIn job link, company and role, then save.
- Optional fields: contact person, location, notes, status, follow-up date and
  a retained job-description excerpt. Follow-ups due are shown in the module;
  this is not a scheduled notification or outreach service.
- To fill a draft from Chrome, install/reload the latest bundled companion,
  arm it from the CV Studio toolbar icon, open a job ad and use **Refresh job
  tabs → Read job ad**. Review the fields before saving. Manual entry works
  without the companion. Neither path uses AI or incurs provider charges.
- Search saved leads, filter by status or due date, and edit/view details.
  Re-saving the same LinkedIn job preserves the existing record and notes.
  Close a lead with the Closed status; there is no destructive delete action.
- Export the filtered view as CSV. **Download backup** exports all records as
  Job Leads JSON. **Restore missing leads** validates the entire file before
  adding missing job IDs in one transaction; existing records are never replaced.
  This dedicated backup is separate from Settings' legacy local-data backup.

## Boundaries

`cvstudio_job_leads.py` owns a dedicated `job_leads.sqlite3` in the existing
per-user state directory. It opens lazily, checks integrity/application/schema
identity, creates and verifies a consistent backup before initial schema creation,
and serializes writes using SQLite transactions. This store has its own schema 1;
the existing application database remains schema 10 and the job journal schema 1.
Initialization is restart-safe, failed writes roll back and errors are visible.
Revisions prevent an older browser draft overwriting a newer saved edit.
Unknown fields are discarded rather than persisted; links retain only canonical
LinkedIn job IDs. No backend URL fetching, credentials, AI/provider calls,
LinkedIn messages, applications, JobAdder writes or background worker are added.

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

The existing companion adds only `jobTabs` and `jobRead` after its bound app
document check. Job capture requires a selected tab, matching canonical job ID,
completed loading and a recognized visible detail panel. Search-panel title
links must confirm the selected job ID to reject stale SPA content. It stops
on unknown layouts, access challenges, navigation or an active sourcing run.
Capture performs no click, navigation, tab creation, tab closure or save on
LinkedIn; it only fills an unsaved CV Studio draft. Its four-file packaging,
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

The source preview on port 5074 uses isolated state kept across its own restarts.
It is separate from the installed owner app on port 5000. The preview state path
is retained only in ignored runtime configuration. No user data was used for QA.
