# Current Phase Status

## Release state

- Approved baseline: v24.6.217
- Baseline Git commit: `c8eeb34c275d374170a5931d69ed95ea213c791a`
- Working branch: `codex/phase-2a-sqlite`
- Active phase: Phase 2A only
- Status: SQLite safety foundation complete; repository implementation is next
- Current milestone: repository interfaces and backend JSON-cache migration

## Verified baseline

- Git 2.55.0.windows.3 is available.
- The opened folder was already a clean Git worktree, so no repository initialisation was required.
- `HEAD` is the existing clean commit `CV Studio v24.6.217 baseline`.
- Backend, frontend, installer, protected-build workflow and owner-tool version surfaces all identify v24.6.217.
- The supplied baseline records all identify the approved owner ZIP SHA-256 as `c499ea8043f274bf47a4981c84794759f38fc7c761b98ba3939626114a898a59`.

## Phase 2A storage inventory

### In-scope durable stores and call sites

1. **Usage history** — browser `localStorage` key `guo_lab_stats`.
   - Read/write boundary: `statsLoad`, `statsSave`, `statsRecord`, `statsAttachJobAdderUrl`, `clearStats`, stats rendering and CSV export in `index.html`.
   - Producers cover format/blind/create, CV scoring, Owl/Owl chat, AI Crawler, summary, OneNote salary/activity, provider tests, paid-AI failures, company and Lead Finder runs.
   - Legacy rows predating v24.6.215 may contain cost only. Their missing detailed token/call/cache fields must remain missing; they must not be reconstructed.
2. **Lead-title cache** — `lead_title_cache.json` beside `app.py`.
   - Read/write boundary: `_lead_title_cache_load`, `_lead_title_cache_save`, find/store/touch helpers, stats/clear routes and the Lead Finder search route.
   - `merge_title_cache.py` remains a supported legacy JSON producer during the transition release.
3. **Lead-contact cache** — `lead_contact_cache.json` beside `app.py`.
   - Read/write boundary: `_lead_contact_cache_load`, `_lead_contact_cache_save`, find/store/touch helpers, enrichment routes and stats/clear routes.
4. **Salary-component cache** — `runtime/salary_ai_component_cache.json`.
   - Read/write boundary: `_ja_salary_ai_cache_load`, `_ja_salary_ai_cache_get`, `_ja_salary_ai_cache_put` and salary AI extraction.
5. **PPC metadata** — browser `localStorage` key `cvstudio_ppc_meta_v1`.
   - Read/write boundary: `ppcMetaLoad`, `ppcMetaSave`, `ppcUpdateMeta`, `ppcMetaFor`, PPC filtering/KPI/rendering.
   - The browser IndexedDB/fallback placement-query cache, PPC UI preferences, invoice recipient, Outlook draft links and client settings are separate and remain unchanged.
6. **Diagnostic state** — v24.6.217 has no durable user-data diagnostic JSON to import.
   - Recent browser API errors are bounded in memory only; runtime diagnostics are generated on demand.
   - Phase 2A will persist only non-sensitive storage health/migration state. It will not store request content, paths, emails, candidate identifiers, tokens or keys.

### Explicitly inventoried but out of scope

- `install_receipt.json`, `update_state.json` and `install_health_report.json` remain owned by the Phase 1 installation/rollback contract.
- `cvstudio.<instance>.pid.json` and the legacy PID file remain the Windows launcher/stop-process compatibility contract; they are not user data and will not be reinterpreted.
- JobAdder, Outlook/Microsoft and AI secret/token JSON stores remain in their existing protected mechanisms.
- Browser OneNote records/links, notes, saved settings, UI state, invoice settings and credential-like settings remain for Phase 2B or later as already scoped.
- In-memory AI Crawler preview/resume caches and the in-memory PPC detail cache remain ephemeral.

## Concrete implementation plan

### Milestone 1 — SQLite safety foundation

- Add a narrowly scoped storage module using Python's built-in `sqlite3`.
- Store the database in the existing per-user CV Studio state directory, with an environment-only test override.
- Enforce WAL, foreign keys, a bounded busy timeout and integrity checks on every managed connection/initialisation.
- Add ordered schema migrations, `PRAGMA user_version`, schema metadata and durable migration history.
- Before every schema-changing migration, create a unique timestamped SQLite backup with the SQLite backup API and verify the backup with `PRAGMA integrity_check`.
- Run each migration transactionally and support deterministic failure injection in tests to prove rollback/restart safety.

### Milestone 2 — repositories and backend JSON caches

- Add repositories for usage history, lead-title cache, lead-contact cache, salary-component cache, PPC metadata and non-sensitive diagnostic state.
- Import legacy data by deterministic keys/fingerprints inside transactions; record import fingerprints; never rename or delete legacy files.
- Convert lead-title, lead-contact and salary reads to SQLite first with safe JSON import/fallback.
- Dual-write those three legacy JSON formats for one-release backward readability, including clear/touch paths and compatibility with `merge_title_cache.py`.

### Milestone 3 — usage history and PPC metadata bridge

- Add same-origin local storage routes for idempotent import/read/upsert/clear operations.
- Hydrate browser state from SQLite on startup while using the existing local value as the import/failure fallback.
- Continue writing the existing localStorage keys after every mutation so v24.6.217 remains able to read the data.
- Preserve unknown legacy fields and the v24.6.215 DeepSeek detailed-cost cutoff exactly.

### Milestone 4 — structured recovery and diagnostics

- Expose redacted storage health in runtime diagnostics.
- Return structured request-ID errors with explicit recovery guidance for corruption and migration failures.
- Persist only non-sensitive diagnostic state and exclude database paths, legacy paths, tokens, keys, emails and candidate identifiers from responses, logs, tests and support bundles.

### Milestone 5 — acceptance and release evidence

- Test a v24.6.217 fixture, migration twice, duplicate-free import, legacy JSON preservation and SQLite-first read/write behaviour.
- Test corruption and an injected interrupted migration; verify no partial schema/data and successful restart after removing the injected failure.
- Run targeted and full regression checks plus Python, JavaScript, Bash and PowerShell syntax checks and repository consistency.
- Bump the completed private owner/source release surfaces to the next patch only after implementation passes.
- Create the private owner/source ZIP, extract it freshly, compare every included byte, produce the Phase 2A QA report and Phase 2B handover, and record SHA-256.
- Stop after Phase 2A.

## Milestones

- [x] Verify source baseline and repository state.
- [x] Inventory existing backend JSON/cache stores and read/write call sites.
- [x] Design database path, connection policy, migration order and compatibility boundary.
- [x] Implement SQLite connection, integrity and backup foundation.
- [x] Implement schema-version and migration history.
- [ ] Implement repository interfaces.
- [ ] Migrate usage history.
- [ ] Migrate lead-title cache.
- [ ] Migrate lead-contact cache.
- [ ] Migrate salary-component cache.
- [ ] Migrate PPC metadata.
- [ ] Implement non-sensitive diagnostic state.
- [ ] Prove SQLite-first reads, legacy fallback/import and one-release dual writes.
- [ ] Prove migration idempotency.
- [ ] Test corrupt and interrupted migration handling.
- [ ] Run complete regression and static validation.
- [ ] Create and byte-verify private owner/source ZIP.
- [ ] Produce QA report, SHA-256 and Phase 2B handover.

## Decisions and limitations

- A dedicated Phase 2A storage module is permitted only as the requested repository/foundation boundary; no unrelated backend route or client modularisation will be performed.
- Browser notes/settings are not being migrated. Usage history and PPC metadata are the two explicitly named Phase 2A browser-origin stores and will retain legacy localStorage mirrors.
- Legacy backend cache files remain byte-present throughout migration and continue to receive compatible writes for the transition release.
- The runtime PID JSON is deliberately not moved because current Windows stop/launcher scripts require it and changing that contract would exceed Phase 2A.
- Schema changes are ordered as seven migrations so each store receives its own verified pre-change backup and restart-safe checkpoint.
- Migration tests found and eliminated two Windows file-handle leaks before any existing store was connected to SQLite.
- No protected colleague package will be produced without matching native compilation and smoke testing.
- Genuine native Windows/macOS installation testing is not part of the current local source run and will not be claimed.

## Blockers

None.

## Test results

- Baseline Git worktree: clean before Phase 2A edits.
- Baseline/version surface inspection: passed.
- Storage call-site inventory: complete.
- SQLite foundation targeted suite: 4 tests passed.
  - WAL, foreign keys, 5-second busy timeout, integrity check, schema metadata and exact migration history.
  - Seven distinct pre-migration backups created and independently integrity-verified.
  - Second initialisation created no duplicate history and no extra backup.
  - Injected interruption rolled schema and history back to version 3, then a clean restart completed versions 4–7.
  - Corrupt database returned `STORAGE_CORRUPT`, path-free recovery guidance and left legacy fixture bytes unchanged.
- Python syntax: `cvstudio_storage.py` and the foundation test module passed `py_compile`.

## Files changed

- `PHASE_STATUS.md` — baseline evidence, storage inventory, milestone plan and results.
- `cvstudio_storage.py` — SQLite lifecycle, safety PRAGMAs, integrity checks, ordered schema, migration history, verified backups and redacted diagnostic state.
- `tests/test_phase2a_storage_foundation.py` — foundation, idempotency, corruption and interrupted-migration coverage.

## Next action

Implement repository interfaces, prove idempotent legacy imports, then connect the three backend JSON cache boundaries with SQLite-first reads and compatible dual writes.
