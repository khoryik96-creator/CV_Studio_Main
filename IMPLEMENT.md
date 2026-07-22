# Phase Execution Runbook

## Current gate

Phases 1, 2A, 2B and 3 are complete in private owner/source release v24.6.224.
There is no active implementation target. Do not make further production
changes or begin Phase 4 unless the owner explicitly starts it.

## Before a future Phase 4 implementation

1. Read `AGENTS.md`, `ROADMAP.md`, `PHASE_STATUS.md` and `BACKBURNER_ROADMAP.md`.
2. Read `CV_STUDIO_V24_6_224_PHASE_4_HANDOVER.md`.
3. Read `cv_studio_v24_6_224_phase3_corrective_review_qa_report.md`, the
   v24.6.223 Phase 3 QA report, the
   Phase 2B QA reports and the historical Phase 2A QA reports.
4. Verify the v24.6.224 source/package checksum against its adjacent SHA-256 and
   verification sidecars.
5. Verify Git and create a clean v24.6.224 baseline commit if the extracted
   folder is not already a repository.
6. Re-run the Phase 1/2 storage suites, Phase 3 client characterization, both
   frontend fixtures, live source smoke and tracked-language static validation
   before changing code.
7. Preserve schema versions 1–10, all verified-backup/recovery guarantees,
   every JSON/localStorage mirror, all 107 route URLs and every legacy response
   field.
8. Limit an authorized Phase 4 to gradual behavior-preserving backend
   modularisation as described in the handover. Move one bounded module at a
   time with characterization fixtures.
9. Keep credential migration, persistent background jobs, frontend
   modularisation, lazy loading, new workflows and roadmap items 4/7/8 out of
   scope unless separately authorized.
10. Work milestone by milestone, test and checkpoint each stable change, then
    stop at the end of the authorized phase.
