# Phase Execution Runbook

## Current gate

Phases 1, 2A and 2B are complete in private owner/source release v24.6.221.
There is no active implementation target. Do not make further production
changes or begin Phase 3 unless the owner explicitly starts it.

## Before a future Phase 3 implementation

1. Read `AGENTS.md`, `ROADMAP.md`, `PHASE_STATUS.md` and `BACKBURNER_ROADMAP.md`.
2. Read `CV_STUDIO_V24_6_221_PHASE_3_HANDOVER.md`.
3. Read `cv_studio_v24_6_221_phase2b_corrective_review_qa_report.md`, the
   v24.6.220 Phase 2B QA report and the historical Phase 2A QA reports.
4. Verify the v24.6.221 source/package checksum against its adjacent SHA-256 sidecar.
5. Verify Git and create a clean v24.6.221 baseline commit if the extracted folder is not already a repository.
6. Re-run the Phase 2A/2B migration, corruption, interruption,
   legacy-preservation, frontend and source-smoke suites before changing code.
7. Preserve schema versions 1–10, all verified-backup/recovery guarantees and
   every JSON/localStorage compatibility mirror.
8. Limit an authorized Phase 3 to the shared external-service client boundary
   described in the handover; preserve all route URLs and response fields.
9. Keep credentials, background jobs, modularisation, lazy loading, new
   workflows and roadmap items 4/7/8 out of scope unless separately authorized.
10. Work milestone by milestone, test and checkpoint each stable change, then
    stop at the end of the authorized phase.
