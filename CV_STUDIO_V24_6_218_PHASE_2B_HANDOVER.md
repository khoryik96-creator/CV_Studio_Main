# CV Studio v24.6.218 → Phase 2B Handover

**Current private owner/source release:** v24.6.218  
**Completed phase:** Phase 2A — SQLite foundation and lower-risk durable-data migration  
**Phase 2A migration base:** v24.6.217

## Activation gate

Do not begin Phase 2B automatically. This handover defines the next candidate
scope only. The owner must explicitly start Phase 2B.

## Preserve the Phase 2A foundation

Database locations:

- Windows: %LOCALAPPDATA%\TheGuoLab\CVStudio\cv_studio.sqlite3
- macOS/Linux source: ~/.guo_lab_cv_studio/cv_studio.sqlite3
- verified migration backups: migration_backups under the same state folder

Schema version 7 contains:

1. schema metadata, migration history and legacy-import fingerprints;
2. usage history;
3. lead-title cache;
4. lead-contact cache;
5. salary-component cache;
6. PPC metadata;
7. non-sensitive diagnostic state.

Every future schema change must:

- create and integrity-verify a unique timestamped backup first;
- run transactionally;
- be restart-safe and idempotent;
- retain structured request-ID corruption/migration errors;
- avoid logging or bundling private values/paths;
- leave credentials outside plain SQLite.

## Existing Phase 2A compatibility contracts

- lead_title_cache.json remains importable and receives transition writes;
- lead_contact_cache.json remains importable and receives transition writes;
- runtime/salary_ai_component_cache.json remains importable and receives
  transition writes;
- guo_lab_stats remains the usage-history browser mirror;
- cvstudio_ppc_meta_v1 remains the PPC browser mirror;
- legacy usage rows before v24.6.215 keep cost only;
- legacy files are never deleted by migration.

Do not remove these mirrors in Phase 2B without an explicit compatibility
decision and migration/export evidence.

## Recommended Phase 2B scope

Inventory and migrate selected durable browser records/settings only:

- saved OneNote links and parser records where they are genuinely durable;
- selected persistent user settings that need backup/restore;
- other owner-approved browser records that should survive browser-profile
  loss;
- explicit import/export compatibility for the selected records.

Keep temporary display/filter state in localStorage where appropriate. Migrate
one store at a time with fixtures, SQLite-first reads and a documented
transition policy.

## Still out of scope

- credentials, API keys, OAuth tokens and protected secrets;
- shared JobAdder, Microsoft or AI provider clients;
- background jobs;
- backend or frontend modularisation;
- lazy loading;
- Flask server replacement;
- saved/versioned AI Crawler scoring profiles;
- candidate Shortlist/Maybe/Reject/Reviewed workflow;
- unrelated new user-facing features.

## Required Phase 2B entry checks

1. Verify the v24.6.218 archive against its adjacent SHA-256 sidecar.
2. Read the v24.6.218 Phase 2A QA report.
3. Run all Python discovery tests.
4. Run the frontend storage fixture.
5. Run the live loopback source smoke.
6. Run owner-source validation/preflight.
7. Re-run Python, JavaScript, Bash and PowerShell syntax validation.
8. Verify repository consistency.
9. Confirm no legacy store or credential path changed before implementation.

## Phase 2A test entry points

- python -m unittest discover -s tests -p test_*.py -v
- node tests/test_phase2a_frontend_storage.js
- python tests/run_phase2a_source_smoke.py
- python owner_build_tools/repo_consistency.py --root .

Owner-source preflight remains available through validate_source and
preflight_source in owner_build_tools/build_protected.py.

## Native-test caveat

v24.6.218 has Windows source execution and controlled local fixtures, but no
new Windows-native protected compilation or physical Windows/macOS
installer/restore certification. Do not distribute a protected colleague
package until matching native compilation and smoke evidence exists.

## Stop boundary

Phase 2B must stop before Phase 3 shared-client work.
