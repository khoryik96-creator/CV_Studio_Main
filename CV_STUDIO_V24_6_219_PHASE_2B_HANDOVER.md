# CV Studio v24.6.219 → Phase 2B Handover

Source release: private owner/source v24.6.219

Phase 2A implementation: v24.6.218

Phase 2A corrective review closure: v24.6.219

## Activation gate

Phase 2B is not active. Start it only after an explicit owner instruction. The
v24.6.218 QA report remains the foundation record; the v24.6.219 corrective QA
report is the current release entry record.

## Preserve the Phase 2A foundation

The local database remains:

- Windows: `%LOCALAPPDATA%\TheGuoLab\CVStudio\cv_studio.sqlite3`
- macOS/Linux source: `~/.guo_lab_cv_studio/cv_studio.sqlite3`
- verified migration backups: `migration_backups` under the same state folder

Preserve WAL mode, foreign keys, the bounded busy timeout, integrity checks,
`PRAGMA user_version`, migration history and the repository interfaces. Any
future schema change must create and independently integrity-verify a unique
timestamped backup first, run transactionally, and remain restart-safe and
idempotent.

Also preserve the v24.6.219 corrected contracts:

- stale usage/PPC compatibility mirrors cannot replace newer SQLite rows;
- current-page hydration races may retain only the records actually mutated;
- durable clear failures are visible and restore the compatibility mirror;
- busy/locked SQLite is retryable and distinct from corruption;
- recursive credential-like usage fields never enter SQLite or its backups.

## Existing compatibility contracts

- `lead_title_cache.json`, `lead_contact_cache.json` and
  `runtime/salary_ai_component_cache.json` remain importable and receive
  transition writes;
- `guo_lab_stats` remains the usage-history browser mirror;
- `cvstudio_ppc_meta_v1` remains the PPC browser mirror;
- legacy usage rows before v24.6.215 keep cost only;
- legacy files are never deleted by migration.

Reassess transition mirrors explicitly; do not silently remove them. Preserve
unknown fields and export/backward-readability behavior until the owner accepts
a compatibility change.

## Recommended Phase 2B scope

Inventory first, then migrate only owner-approved durable browser records such
as saved OneNote links/parser records and selected persistent settings that
need backup/restore. Keep temporary UI state in localStorage where appropriate
and define explicit import/export compatibility for every selected record.

## Still out of scope

- credentials, API keys, OAuth tokens and protected secrets;
- shared JobAdder, Microsoft or AI-provider clients;
- background jobs;
- backend or frontend modularisation;
- lazy loading;
- Flask server replacement;
- saved/versioned AI Crawler scoring profiles;
- candidate Shortlist/Maybe/Reject/Reviewed workflow;
- unrelated new user-facing features.

## Required entry checks

1. Verify the v24.6.219 owner ZIP against its adjacent SHA-256 sidecar and
   freshly extract it.
2. Verify Git and create a clean v24.6.219 baseline commit if needed.
3. Read `AGENTS.md`, `ROADMAP.md`, `PHASE_STATUS.md`, `IMPLEMENT.md`, both Phase
   2A QA reports and this handover.
4. Run the complete Python suite, frontend fixture, source smoke, owner-source
   validation and repository consistency check.
5. Re-prove double migration/import, interruption rollback, corrupt-database
   recovery and byte-exact legacy preservation.
6. Inventory the chosen browser stores and every read/write/export call site
   before changing production code.
7. Record an implementation plan in `PHASE_STATUS.md` and checkpoint each stable
   milestone.

## Phase 2A test entry points

- `python -m unittest discover -s tests -p test_*.py -v`
- `node tests/test_phase2a_frontend_storage.js`
- `python tests/run_phase2a_source_smoke.py`
- `python owner_build_tools/repo_consistency.py --root .`

## Native-test caveat

The owner/source release was validated locally at source level. It does not
claim a native protected Windows/macOS build or physical installer/restore run.
Do not create a protected colleague package without the matching native
compilation and smoke testing.

## Stop boundary

Complete only the phase the owner explicitly activates. Phase 2B must stop
before Phase 3 and must not absorb any backburner or later-phase work.
