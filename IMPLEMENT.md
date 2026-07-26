# Phase Execution Runbook

## Current gate

Phases 1, 2A, 2B, 3, 4 and 5A are complete in private owner/source release
v24.6.233. There is no active implementation target. Do not make further
production changes or begin Phase 5B or Phase 6 unless the owner explicitly
starts the exact next milestone.

## Before a future Phase 5B implementation

1. Read `AGENTS.md`, `ROADMAP.md`, `PHASE_STATUS.md` and `BACKBURNER_ROADMAP.md`.
2. Read `CV_STUDIO_V24_6_233_PHASE_5B_HANDOVER.md`.
3. Read
   `cv_studio_v24_6_233_phase5a_persistent_jobs_qa_report.md`,
   `CV_STUDIO_V24_6_232_PHASE_5_HANDOVER.md`,
   `cv_studio_v24_6_232_phase4_compatibility_corrective_qa_report.md`,
   `cv_studio_v24_6_231_phase4_backend_modularisation_qa_report.md`,
   `cv_studio_v24_6_230_phase3_content_negotiation_corrective_qa_report.md`,
   the v24.6.224 corrective QA report, the
   v24.6.223 Phase 3 QA report, the
   Phase 2B QA reports and the historical Phase 2A QA reports.
4. Verify the v24.6.233 source/package checksum against its adjacent SHA-256 and
   verification sidecars.
5. Verify Git and create a clean v24.6.233 baseline commit if the extracted
   folder is not already a repository.
6. Re-run the Phase 1/2 storage suites, Phase 3 client characterization, Phase
   4 module characterization, Phase 5A persistent-job suites, both frontend
   fixtures, live source smoke and tracked-language static validation before
   changing code.
7. Preserve schema versions 1–10, all verified-backup/recovery guarantees,
   every JSON/localStorage mirror, all 107 route URLs and every legacy response
   field.
8. Limit an authorized Phase 5B to the exact owner-approved central AI cost-
   guardrail/provider-reconciliation scope described in the handover. Do not
   reinterpret or broaden Phase 5A persistence/recovery semantics.
9. Keep credential migration, frontend modularisation, lazy loading, unrelated
   workflows and roadmap items 4/7/8 out of scope unless separately authorized.
10. Work milestone by milestone, test and checkpoint each stable change, then
    stop at the end of the authorized phase.
