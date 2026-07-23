# Phase Execution Runbook

## Current gate

Phases 1, 2A, 2B, 3 and 4 are complete in private owner/source release
v24.6.231. There is no active implementation target. Do not make further
production changes or begin Phase 5 unless the owner explicitly starts it.

## Before a future Phase 5 implementation

1. Read `AGENTS.md`, `ROADMAP.md`, `PHASE_STATUS.md` and `BACKBURNER_ROADMAP.md`.
2. Read `CV_STUDIO_V24_6_231_PHASE_5_HANDOVER.md`.
3. Read
   `cv_studio_v24_6_231_phase4_backend_modularisation_qa_report.md`,
   `cv_studio_v24_6_230_phase3_content_negotiation_corrective_qa_report.md`,
   the v24.6.224 corrective QA report, the
   v24.6.223 Phase 3 QA report, the
   Phase 2B QA reports and the historical Phase 2A QA reports.
4. Verify the v24.6.231 source/package checksum against its adjacent SHA-256 and
   verification sidecars.
5. Verify Git and create a clean v24.6.231 baseline commit if the extracted
   folder is not already a repository.
6. Re-run the Phase 1/2 storage suites, Phase 3 client characterization, Phase 4
   module characterization, both frontend fixtures, live source smoke and
   tracked-language static validation before changing code.
7. Preserve schema versions 1–10, all verified-backup/recovery guarantees,
   every JSON/localStorage mirror, all 107 route URLs and every legacy response
   field.
8. Limit an authorized Phase 5 to the exact owner-approved background-job and/or
   central AI cost-guardrail scope described in the handover. Do not combine
   unrelated work.
9. Keep credential migration, frontend modularisation, lazy loading, unrelated
   workflows and roadmap items 4/7/8 out of scope unless separately authorized.
10. Work milestone by milestone, test and checkpoint each stable change, then
    stop at the end of the authorized phase.
