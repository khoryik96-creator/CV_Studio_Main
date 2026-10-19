# Job Leads module — source QA, 2026-10-19

Historical release evidence; root `VERSION` is the live release identity.

## Scope

Owner requested a dedicated LinkedIn job-ad tracker and selected company, role,
contact person, notes, status and follow-up date. Source v24.6.447 on local branch
`codex/v24.6.447-job-leads` follows unpushed v446 checkpoint `cfa18bc`, based on
merged main `480678d`. No push, PR, merge or installation update was requested.

New module includes manual URL entry, read-only Chrome-companion job capture
into a reviewable draft, persistent records, conflict/duplicate protection,
search/status/due filters, editing, CSV, and insert-only JSON backup restore.
Local follow-up dates are visible when the module is opened; no scheduled
notifications or external outreach are implemented.

One GET/POST `/job-leads` endpoint brings the seal to 120 routes with digest
`ee8d33baeb48b961a2f50723faacbeb7fed86b55454b3518ab4a07bcd1e90033`.
Dedicated tests independently verify that removal of this route restores the
exact old 119-route digest, and removal of both modules restores the main
118-route digest. Five ordered guards, the existing schema-10 database, journal
schema 1, CV formatting and paid-provider behavior remain unchanged. New leads
have a separate lazily opened schema-1 SQLite store and verified pre-migration
backup; no existing database is migrated or reinterpreted.

## Results

- Baseline before implementation: 17 focused Sourcer/architecture tests passed.
- Focused final domain/routes/inventories/version/sign-out checks: 73 passed,
  six subtests. Job Leads adds 33 Python cases, all using temporary state.
- Follow-up targeted checks after corruption recovery and UTF-8 backup handling:
  55 passed. Corruption is non-retryable with an explicit restore action; backup
  encoding retains bounded non-English text without ASCII escape expansion.
- Full isolated local suite: **1,640 passed, four skipped, three deselected,
  7,599 subtests**, 167.47 seconds; repeat 161.59 seconds. The same three documented local updater
  environment exclusions were retained; unfiltered hosted checks have not run.
- All **31** root frontend suites passed, including new Job Leads checks and
  unchanged three-mode 15-page Sourcer/controller tests.
- Native Chrome with synthetic intercepted LinkedIn pages passed recognized
  standalone/search job extraction, stale selected-job mismatch, unknown layout
  and login-check stopping. Actual module UI passed manual save, contact/notes
  edit, browser reload persistence, due filter, search, capture-as-draft,
  dedicated backup/insert-only restore and switching between app modules.
- Real Chrome source Sourcer smoke with mocked companion/provider passed again
  alongside Job Leads. No real LinkedIn or provider request was made.
- Tracked/new Python and JavaScript syntax, PowerShell/POSIX parsing,
  repository byte consistency, whitespace, source inventories, native Windows
  Antiword/Tesseract/admission preflight and 24-assertion live source smoke passed.
- Desktop and narrow Chrome screenshots were inspected; Job Leads styles are
  scoped and use the established app theme.

The main preview on 5074 uses isolated persistent preview state and an in-memory,
read-only copy of the existing saved DeepSeek key for the previously authorized
Sourcer. Job Leads makes no paid calls. The installed owner app/server/receipt,
source documents and JobAdder state were not modified. Fixture server 5075 was
used only for synthetic checks and is stopped after final verification.

Actual extension installation and live LinkedIn layouts remain owner-driven;
synthetic reader/companion tests do not establish live layout compatibility.
No Mac native result, protected compilation, release package or hosted CI result
is claimed. See `JOB_LEADS_NOTES.md` for workflow and storage/recovery details.
