# CV Studio v24.6.222 → Phase 3 Handover

Source release: private owner/source v24.6.222

Completed phase: Phase 2B — browser-backed durable records and settings,
including both corrective review closures

Phase 2B source baseline: v24.6.219 at
`a43dbb84dcc44c773527f49d0332b2eb15a37cc1`

## Activation gate

Phase 3 is not active. Start it only after an explicit owner instruction. Read
the v24.6.222 second corrective QA report, the v24.6.221/v24.6.220 Phase 2B QA
reports and verify the v24.6.222 archive against its adjacent SHA-256 sidecar
before changing production code.

## Preserve the storage foundation

The local database remains:

- Windows: `%LOCALAPPDATA%\TheGuoLab\CVStudio\cv_studio.sqlite3`
- macOS/Linux source: `~/.guo_lab_cv_studio/cv_studio.sqlite3`
- verified migration backups: `migration_backups` under the same state folder

Schema version 10 contains the Phase 2A foundation plus OneNote transfer
records, saved OneNote links and allowlisted non-secret browser settings.
Preserve WAL mode, foreign keys, busy timeout, integrity checks,
`PRAGMA user_version`, migration history and repository interfaces. Any future
schema change must create and independently verify a unique timestamped backup,
run transactionally and remain restart-safe and idempotent.

## Preserve the corrected Phase 2B contracts

- Fully normalize every record array before import or replacement. Never permit
  a record that cannot be stored safely to reach a tombstoning transaction.
- Invalid or oversized record arrays use the structured request-ID
  `STORAGE_PAYLOAD_INVALID` contract and preserve existing authoritative rows.
- Normalize every browser-setting value with the repository's canonical size,
  secret and JSON-sanitization rules before a route reports success. Rejected
  values must use the structured invalid-payload contract and preserve the
  previous authoritative value.
- Schema-1 restore must confirm every requested durable write. A false helper
  result or rejected promise must reject restore, avoid a success notification
  and avoid automatic reload; counts include only confirmed writes.
- Independent store writes remain separately transactional rather than one
  cross-store transaction. A failed restore remains visible and retryable from
  the unchanged external backup.
- SQLite-authoritative browser-setting hydration must synchronize existing UI
  controls, not only the backing `localStorage` mirror.
- Hydrated preview-memory settings must update active cache limits; Auto mode
  must obtain diagnostics without duplicate startup scheduling.
- `cv_studio_onenote_transfer_records_v1` and
  `cvstudio_onenote_saved_desktop_links_v1` remain transition mirrors.
- Stale imports never overwrite an existing row or tombstone; same-page races
  retain only records or keys actually mutated after hydration began.
- Durable clear/delete failures remain visible and restore their browser mirror.
- Schema-1 local-data exports retain the legacy `settings` object and optional
  additive record collections.
- Recursive credential-like fields never enter SQLite, backups, diagnostics or
  local-data exports. Legacy files are never deleted by migration.

## Candidate Phase 3 scope

If explicitly authorized, Phase 3 is limited to shared external-service client
foundations described in `ROADMAP.md`:

- `JobAdderClient`;
- `MicrosoftGraphClient`;
- `AIProviderClient`;
- centralized retry, pagination, token refresh, timeout, redaction and
  structured error handling behind existing route contracts.

Inventory existing call sites and response shapes first. Extract one client at
a time with characterization fixtures and preserve every route URL and legacy
response field.

## Still out of scope

- credentials or protected-secret migration;
- persistent background jobs;
- backend/frontend modularisation beyond a narrowly authorized client boundary;
- lazy loading or unrelated user-facing workflows;
- Flask server replacement;
- saved/versioned AI Crawler scoring profiles;
- candidate Shortlist/Maybe/Reject/Reviewed workflow.

## Required Phase 3 entry checks

1. Verify the v24.6.222 owner ZIP and fresh extraction against the adjacent
   SHA-256 and verification sidecars.
2. Verify Git is clean and based on the completed v24.6.222 release commit.
3. Read `AGENTS.md`, `ROADMAP.md`, `PHASE_STATUS.md`, `IMPLEMENT.md`, this
   handover, the v24.6.222/v24.6.221/v24.6.220 QA reports and historical Phase
   2A reports.
4. Run the full Python suite, both frontend fixtures and live source smoke.
5. Re-prove migration idempotency, interruption rollback/restart, corruption
   recovery, tombstones, rejected-replacement preservation, strict setting
   validation, restore failure visibility and legacy bytes.
6. Run Python, JavaScript, Bash and PowerShell syntax validation, owner-source
   validation/preflight and repository consistency.
7. Inventory external-service call sites, route contracts, retries, credentials
   and paid-call risks before implementation.
8. Record the authorized Phase 3 plan and checkpoint each stable milestone.

## Native-test caveat

v24.6.222 has genuine Windows source execution and controlled local fixtures,
but no new protected native compilation, protected-binary smoke certification
or physical installer/restore test. Do not create a protected colleague package
without matching native evidence.

## Stop boundary

Stop after Phase 2B. Phase 3 or any later phase requires a new explicit owner
instruction.
