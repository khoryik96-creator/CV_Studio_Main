# CV Studio v24.6.220 → Phase 3 Handover

Source release: private owner/source v24.6.220

Completed phase: Phase 2B — browser-backed durable records and settings

Phase 2B source baseline: v24.6.219 at
`a43dbb84dcc44c773527f49d0332b2eb15a37cc1`

## Activation gate

Phase 3 is not active. Start it only after an explicit owner instruction. Read
the v24.6.220 Phase 2B QA report and verify the release archive against its
adjacent SHA-256 sidecar before changing production code.

## Preserve the storage foundation

The local database remains:

- Windows: `%LOCALAPPDATA%\TheGuoLab\CVStudio\cv_studio.sqlite3`
- macOS/Linux source: `~/.guo_lab_cv_studio/cv_studio.sqlite3`
- verified migration backups: `migration_backups` under the same state folder

Schema version 10 contains:

1. schema metadata, migration history and legacy-import fingerprints;
2. usage history;
3. lead-title cache;
4. lead-contact cache;
5. salary-component cache;
6. PPC metadata;
7. non-sensitive diagnostic state;
8. OneNote transfer records;
9. saved OneNote links;
10. allowlisted non-secret browser settings.

Preserve WAL mode, foreign keys, the bounded busy timeout, integrity checks,
`PRAGMA user_version`, migration history and repository interfaces. Any future
schema change must create and independently integrity-verify a unique
timestamped backup first, run transactionally, and remain restart-safe and
idempotent.

## Preserve the Phase 2A and Phase 2B compatibility contracts

- `lead_title_cache.json`, `lead_contact_cache.json` and
  `runtime/salary_ai_component_cache.json` remain importable and receive their
  transition writes;
- `guo_lab_stats` and `cvstudio_ppc_meta_v1` remain Phase 2A browser mirrors;
- `cv_studio_onenote_transfer_records_v1` and
  `cvstudio_onenote_saved_desktop_links_v1` remain Phase 2B browser mirrors;
- selected browser settings retain their exact localStorage keys and string
  values while SQLite remains authoritative;
- stale imports never overwrite an existing row or tombstone;
- current-page hydration races retain only records/keys genuinely mutated after
  hydration began;
- durable clear/delete failures remain visible and restore their browser mirror;
- schema-1 local-data exports keep the legacy `settings` object and optional
  additive record collections;
- legacy usage rows before v24.6.215 keep cost-only history;
- recursive credential-like fields never enter SQLite, migration backups,
  diagnostics or local-data exports;
- legacy files are never deleted by migration.

Do not remove a transition mirror or shorten backward readability without an
explicit owner compatibility decision and dedicated migration/export evidence.

## Candidate Phase 3 scope

If explicitly authorized, Phase 3 is limited to shared external-service client
foundations described in `ROADMAP.md`:

- `JobAdderClient`;
- `MicrosoftGraphClient`;
- `AIProviderClient`;
- centralized retry, pagination, token refresh, timeout, redaction and structured
  error handling behind existing route contracts.

Inventory existing call sites and response shapes first. Extract one client at
a time with characterization fixtures, preserve every route URL and legacy
response field, and avoid coupling client extraction to a new workflow.

## Still out of scope

- credentials or protected-secret migration;
- persistent background jobs or AI cost guardrails beyond existing behavior;
- backend or frontend modularisation beyond the narrowly authorized client
  boundary;
- lazy loading;
- unrelated new user-facing workflows;
- Flask server replacement;
- saved/versioned AI Crawler scoring profiles;
- candidate Shortlist/Maybe/Reject/Reviewed workflow.

## Required Phase 3 entry checks

1. Verify the v24.6.220 owner ZIP against its adjacent SHA-256 sidecar and
   freshly extract it.
2. Verify Git is clean and based on the completed v24.6.220 release commit.
3. Read `AGENTS.md`, `ROADMAP.md`, `PHASE_STATUS.md`, `IMPLEMENT.md`, this
   handover, the v24.6.220 QA report and the historical Phase 2A QA reports.
4. Run the complete Python suite and both frontend storage fixtures.
5. Run the real loopback source smoke and owner-source validation/preflight.
6. Re-prove migration idempotency, interrupted migration rollback/restart,
   corruption recovery, tombstones and legacy-byte preservation.
7. Run Python, JavaScript, Bash and PowerShell syntax validation plus repository
   consistency.
8. Inventory external-service call sites, route contracts, retry behavior,
   credential boundaries and paid-call risks before implementation.
9. Record the authorized milestone plan in `PHASE_STATUS.md` and checkpoint each
   stable milestone.

## Current test entry points

- `python -m unittest discover -s tests -p test_*.py`
- `node tests/test_phase2a_frontend_storage.js`
- `node tests/test_phase2b_frontend_storage.js`
- `python tests/run_phase2a_source_smoke.py`
- `python owner_build_tools/repo_consistency.py --root .`

Owner-source validation remains available through `validate_source` and
`preflight_source` in `owner_build_tools/build_protected.py`.

## Native-test caveat

v24.6.220 has genuine Windows source execution and controlled local fixtures,
but no new native protected Windows/macOS compilation or physical
installer/restore certification. Do not distribute a protected colleague
package until matching native compilation and smoke evidence exists.

## Stop boundary

Complete only the phase the owner explicitly activates. A future Phase 3 must
stop before Phase 4 and must not absorb background jobs, modularisation,
backburner items or other later-phase work.
