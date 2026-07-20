# Phase Execution Runbook

## Current gate

Phase 2A is complete in private owner/source release v24.6.218. Do not make
further production changes or begin Phase 2B unless the owner explicitly
starts the next phase.

## Before a future Phase 2B implementation

1. Read `AGENTS.md`, `ROADMAP.md`, `PHASE_STATUS.md` and `BACKBURNER_ROADMAP.md`.
2. Read `CV_STUDIO_V24_6_218_PHASE_2B_HANDOVER.md`.
3. Read `cv_studio_v24_6_218_phase2a_sqlite_foundation_qa_report.md`.
4. Verify the v24.6.218 source/package checksum against its adjacent SHA-256 sidecar.
5. Verify Git and create a clean v24.6.218 baseline commit if the extracted folder is not already a repository.
6. Re-run the Phase 2A migration, corruption, interruption, legacy-preservation and source-smoke suites before changing production code.
7. Inventory only the browser records/settings explicitly selected for Phase 2B.
8. Preserve all Phase 2A SQLite, backup, recovery and one-release compatibility guarantees.
9. Keep credentials, roadmap items 4/7/8, shared clients, background jobs, modularisation and new workflows out of scope unless separately authorised.
10. Work milestone by milestone, test and checkpoint each stable change, then stop at the end of the authorised phase.
