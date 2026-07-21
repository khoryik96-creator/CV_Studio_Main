# Current Phase Status

## Release state

- Approved baseline: v24.6.217
- Completed release: v24.6.219
- Baseline Git commit: `c8eeb34c275d374170a5931d69ed95ea213c791a`
- Working branch: `codex/phase-2a-sqlite`
- Active phase: none
- Status: Phase 2A corrective review patch complete
- Current milestone: complete; stop at the Phase 2A boundary

## v24.6.219 corrective plan

- Keep SQLite usage rows authoritative when a stale legacy browser mirror has the same record ID.
- Reject stale PPC metadata conflicts using the existing `updatedAt` contract.
- Report usage-history clear failures and restore the local compatibility mirror instead of claiming success.
- Distinguish transient/operational SQLite failures from genuine database corruption.
- Recursively exclude credential-like fields from usage-history payloads before SQLite or backup persistence.
- Add focused regressions for every finding, then rerun the complete Phase 2A and release validation set.
- Advance release surfaces and owner/source evidence to v24.6.219 only after all tests pass; stop without starting Phase 2B.

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
- [x] Implement repository interfaces.
- [x] Migrate usage history.
- [x] Migrate lead-title cache.
- [x] Migrate lead-contact cache.
- [x] Migrate salary-component cache.
- [x] Migrate PPC metadata.
- [x] Implement non-sensitive diagnostic state.
- [x] Prove SQLite-first reads, legacy fallback/import and one-release dual writes.
- [x] Prove migration idempotency.
- [x] Test corrupt and interrupted migration handling.
- [x] Run complete regression and static validation.
- [x] Create and byte-verify private owner/source ZIP.
- [x] Produce QA report, SHA-256 and Phase 2B handover.

## Decisions and limitations

- A dedicated Phase 2A storage module is permitted only as the requested repository/foundation boundary; no unrelated backend route or client modularisation will be performed.
- Browser notes/settings are not being migrated. Usage history and PPC metadata are the two explicitly named Phase 2A browser-origin stores and will retain legacy localStorage mirrors.
- Legacy backend cache files remain byte-present throughout migration and continue to receive compatible writes for the transition release.
- The runtime PID JSON is deliberately not moved because current Windows stop/launcher scripts require it and changing that contract would exceed Phase 2A.
- Schema changes are ordered as seven migrations so each store receives its own verified pre-change backup and restart-safe checkpoint.
- Migration tests found and eliminated two Windows file-handle leaks before any existing store was connected to SQLite.
- No protected colleague package will be produced without matching native compilation and smoke testing.
- Genuine native Windows/macOS installation testing is not part of the current local source run and will not be claimed.
- The archive checksum is recorded in an adjacent sidecar generated after the archive; the ZIP cannot reliably contain its own authoritative hash.

## Blockers

None.

## Test results

### v24.6.219 corrective review patch

- Focused Python suites: 16 tests passed across storage foundation, repositories and real Flask integration.
- Frontend storage fixture: passed.
- Stale usage imports with an existing ID are insert-only; SQLite retains newer URL/audit fields.
- Usage hydration keeps SQLite authoritative except for the specific records mutated in the active page while hydration was in flight.
- PPC stale or timestamp-free conflicts cannot replace newer SQLite metadata; a genuinely newer `updatedAt` value still wins.
- A failed usage clear restores the compatibility mirror, reports an error and does not emit a false success notification.
- A real SQLite writer lock returns retryable `STORAGE_BUSY` with `retry`, then initialises normally after the lock is released.
- Recursive credential-key exclusion drops top-level, nested, camel-case and hyphenated credential fields while preserving safe usage audit fields such as `input_tokens` and `output_tokens`.
- Python compilation, inline frontend syntax and diff whitespace validation passed for the corrective checkpoint.

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
- Repository targeted suite: 4 additional tests passed; 8 Phase 2A tests pass in combination.
  - Usage imports are fingerprinted/idempotent and legacy cost-only rows retain missing detailed fields.
  - Lead-title signatures deduplicate deterministically without duplicate rows.
  - Lead-contact and salary cache documents round-trip and clear correctly.
  - PPC metadata imports/upserts idempotently; diagnostic state drops fields outside the non-sensitive allowlist.
- Python syntax: storage module plus both Phase 2A test modules passed `py_compile`.
- Backend cache integration suite: 4 additional tests passed.
  - Lead-title, lead-contact and salary legacy JSON imported without deletion and repeated reads produced no duplicates.
  - SQLite remained authoritative when a previously imported legacy file became malformed.
  - Cache updates wrote SQLite first and retained the exact v24.6.217 JSON shapes as compatibility mirrors.
  - Corrupt storage returned a structured `STORAGE_CORRUPT` response with the caller request ID and recovery action; legacy bytes were unchanged.
- Runtime diagnostics expose path-free durable-storage health only.
- Usage/PPC backend route coverage: import, upsert, read and explicit clear passed with request IDs and legacy-preserved flags.
- Frontend storage fixture: passed.
  - Both inline `index.html` scripts compile in Node.
  - Usage and PPC hydrate from SQLite while synchronously retaining their v24.6.217 localStorage keys.
  - Writes are serialized; usage clear is protected from an in-flight import restoring deleted history.
  - Legacy usage rows without IDs use stable sorted-key identity, avoiding duplicates when JSON property order changes.
  - PPC mirror conflicts use `updatedAt`; browser mutations are re-upserted if they race hydration.
- Complete Python discovery suite: 16 tests passed.
  - Includes explicit all-store v24.6.217 fixture migration twice, byte-exact legacy preservation and restart without extra backups.
  - Includes preserved Phase 1 request-ID/error normalization, Host/CSRF defense, JobAdder reconnect classification, owner local-health/DOCX checks and support-bundle regression.
- Live threaded source smoke: 18 loopback assertions passed on an ephemeral port with temporary receipt, database and log state.
- Owner-source validation and dependency preflight: passed, including vetted adm-zip 0.5.17 behavior and both inline JavaScript blocks.
- Static validation checkpoint passed: Python (tracked modules), JavaScript (19 files), Bash (5 files through Git Bash) and PowerShell (5 files, zero parser errors).
- Repository consistency: passed; no lock file, exact Git bytes, approved encodings and platform line endings.
- Scope audit: the Phase 2A diff adds no Flask server replacement, scoring-profile workflow, candidate-decision workflow, shared API client, background job, lazy loading or credential persistence.
- Final v24.6.218 rerun: 16 Python tests, frontend fixture and 18-assertion live source smoke all passed after the version bump.
- Final version audit: 8 primary version surfaces agree on v24.6.218.
- Route compatibility audit: all 88 v24.6.217 Flask route URLs remain present; Phase 2A adds 8 local storage routes.
- Final v24.6.219 rerun: 17 Python tests, frontend fixture and 18-assertion live source smoke all passed after the corrective changes and version bump.
- Final version audit: 8 primary version surfaces agree on v24.6.219.
- Corrective scope audit: no prohibited Phase 2B/backburner implementation definitions or shared-client/background-job/lazy-loading symbols were added.
- v24.6.219 clean archive trial: `git archive` produced one `cv_formatter/` root with 82 tracked source files; fresh extraction found 82 files, zero missing files, zero extra files and zero byte mismatches.
- The authoritative v24.6.219 owner/source ZIP is generated from the final clean phase-record commit. Its SHA-256, byte size, source commit and repeated fresh-extraction result are recorded in adjacent sidecars.
- Clean archive trial: `git archive` produced the required single `cv_formatter/` root with 80 tracked source files; fresh extraction found 80 files, zero missing files, zero extra files and zero byte mismatches.
- The authoritative owner/source ZIP is generated from the final clean documentation commit. Its SHA-256, byte size, source commit and repeated fresh-extraction result are recorded in adjacent checksum and verification sidecars because an archive cannot contain its own authoritative digest.

## Files changed

- `PHASE_STATUS.md` — baseline evidence, storage inventory, milestone plan and results.
- `cvstudio_storage.py` — SQLite lifecycle, safety PRAGMAs, integrity checks, ordered schema, migration history, verified backups and redacted diagnostic state.
- `tests/test_phase2a_storage_foundation.py` — foundation, idempotency, corruption and interrupted-migration coverage.
- `tests/test_phase2a_repositories.py` — repository import, round-trip, clear, compatibility-cutoff and diagnostic allowlist coverage.
- `app.py` — storage initialisation, structured storage recovery, SQLite-first backend cache reads/imports, JSON dual writes and redacted health diagnostics.
- `tests/test_phase2a_app_cache_integration.py` — real Flask-module cache and corruption-route integration coverage.
- `index.html` — asynchronous SQLite hydration and ordered mirroring for usage history and PPC metadata, retaining existing synchronous localStorage compatibility.
- `tests/test_phase2a_frontend_storage.js` — inline-JavaScript syntax plus usage/PPC hydration, deduplication, write and clear fixtures.
- `tests/test_phase2a_v217_fixture.py` — complete legacy store fixture, double import, byte preservation and restart evidence.
- `tests/run_phase2a_source_smoke.py` — bounded real-loopback source smoke with temporary local state and 18 assertions.
- Production/installer/launcher/protected-build version surfaces — advanced consistently to v24.6.219.
- `AGENTS.md`, `ROADMAP.md`, `IMPLEMENT.md`, `CODEX_FIRST_PROMPT.txt`, `README_FIRST.txt`, `BACKBURNER_ROADMAP.md` and `KEEP_PRIVATE_PATCH_BASE.txt` — v24.6.219 completion/stop gate and next-phase entry instructions.
- `cv_studio_v24_6_218_phase2a_sqlite_foundation_qa_report.md` — Phase 2A release QA evidence.
- `CV_STUDIO_V24_6_218_PHASE_2B_HANDOVER.md` — owner-gated next-phase handover.
- `cv_studio_v24_6_219_phase2a_corrective_review_qa_report.md` — corrective review and release QA evidence.
- `CV_STUDIO_V24_6_219_PHASE_2B_HANDOVER.md` — updated owner-gated next-phase handover.

## Next action

Stop. Do not begin Phase 2B or any later phase without a new explicit owner instruction.
