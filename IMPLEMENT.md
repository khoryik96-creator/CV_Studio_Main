# Phase Execution Runbook

## Current gate

Phases 1, 2A, 2B, 3, 4, 5A, 5B and 6A–6C are complete. The separately authorized
mandatory Windows-x64 Antiword milestone completed in v24.6.240, and its
verification-to-execution TOCTOU race is corrected in private owner/source
release v24.6.241. The bounded JobAdder account-management and settings
milestone is complete in private owner/source release v24.6.242. Phase 6A
frontend modularisation and the bounded Phase 6B local-jsPDF lazy loading
change are complete on their source branches without changing the v24.6.243
installed identity. macOS remains on v24.6.239. The bounded v24.6.245
post-Phase-6 corrective starts from merged source commit
`c75aa20c5a99ea5e9af84204a19703c90e0c2d36`; it is limited to long-CV parse
timeouts, structured-output repair, CV Scoring access code `1996`, and removal
of the AI Crawler password. Stop before merge, protected packaging or Phase 7.

## v24.6.245 corrective implementation decision

Use one deterministic long-CV predicate in backend and browser. Normal requests
retain a 180-second provider timeout with a 210-second browser margin; CVs of at
least 18,000 characters or eight standalone responsibility/achievement markers
receive 300/330 seconds. Every `/parse` caller must use the shared browser helper.

Normalize imperfect AI structure at the backend response boundary, preview
boundary and DOCX boundary. Decode only valid JSON-looking structured groups;
preserve malformed/unknown text, canonicalize section headings, never infer a
missing title, omit empty labels, and keep the transformation idempotent. Do not
truncate or rewrite substantive CV content and do not make paid provider calls.

## Phase 6C implementation decision

Keep adaptive memory and Job Fit scoring in their established inline/backend
boundaries. Auto trusts only internally consistent runtime memory received in the
last five minutes and otherwise uses Standard; manual selections always win. A
resolution change updates budgets and trims immediately, while an unchanged
selection does not clear caches. Present selected/resolved mode, reason, data
freshness/age and active usage/limits in Settings.

Auto must also schedule the exact end of the five-minute trust window. At that
deadline, reapply the resolution and rerender status without requiring Settings
or a diagnostic refresh; a High-to-Standard fallback must update payload, DOM
and prefetch limits and trim existing caches immediately. Keep only one timer,
cancel it for manual selection, and do not clear caches merely because the same
selection/resolution is reapplied.

Do not alter Job Fit arithmetic. Add only explanation provenance for the existing
native-Boolean/discovery floors, unavailable component evidence and whether resume
text actually contributed. Preserve response aliases and source labels. The new
Phase 6C Python/Node fixtures are mandatory alongside every established frontend
fixture; Windows CI remains the protected/native gate.

## Before a future Phase 6 implementation

1. Read `AGENTS.md`, `ROADMAP.md`, `PHASE_STATUS.md` and `BACKBURNER_ROADMAP.md`.
2. Read `CV_STUDIO_V24_6_243_PHASE_6_HANDOVER.md`.
3. Read
   `cv_studio_v24_6_243_jobadder_account_isolation_corrective_qa_report.md`,
   `CV_STUDIO_V24_6_242_PHASE_6_HANDOVER.md`,
   `cv_studio_v24_6_242_jobadder_account_settings_signout_qa_report.md`,
   `CV_STUDIO_V24_6_241_PHASE_6_HANDOVER.md`,
   `cv_studio_v24_6_241_windows_x64_antiword_toctou_corrective_qa_report.md`,
   `CV_STUDIO_V24_6_240_PHASE_6_HANDOVER.md`,
   `cv_studio_v24_6_240_windows_x64_antiword_mandatory_qa_report.md`,
   `CV_STUDIO_V24_6_239_PHASE_6_HANDOVER.md`,
   `cv_studio_v24_6_239_blind_jd_pdf_metadata_overflow_corrective_qa_report.md`,
   `CV_STUDIO_V24_6_238_PHASE_6_HANDOVER.md`,
   `cv_studio_v24_6_238_blind_jd_exp_summary_corrective_qa_report.md`,
   `CV_STUDIO_V24_6_237_PHASE_6_HANDOVER.md`,
   `cv_studio_v24_6_237_jobadder_esc2_corrective_qa_report.md`,
   `CV_STUDIO_V24_6_236_PHASE_6_HANDOVER.md`,
   `cv_studio_v24_6_236_phase5b_ai_cost_guardrails_corrective_qa_report.md`,
   `CV_STUDIO_V24_6_235_PHASE_6_HANDOVER.md`,
   `cv_studio_v24_6_235_phase5b_ai_cost_guardrails_qa_report.md`,
   `CV_STUDIO_V24_6_234_PHASE_5B_HANDOVER.md`,
   `cv_studio_v24_6_234_phase5a_persistent_jobs_corrective_qa_report.md`,
   `cv_studio_v24_6_233_phase5a_persistent_jobs_qa_report.md`,
   `CV_STUDIO_V24_6_232_PHASE_5_HANDOVER.md`,
   `cv_studio_v24_6_232_phase4_compatibility_corrective_qa_report.md`,
   `cv_studio_v24_6_231_phase4_backend_modularisation_qa_report.md`,
   `cv_studio_v24_6_230_phase3_content_negotiation_corrective_qa_report.md`,
   the v24.6.224 corrective QA report, the
   v24.6.223 Phase 3 QA report, the
   Phase 2B QA reports and the historical Phase 2A QA reports.
4. Verify the v24.6.243 source/package checksum against its adjacent SHA-256 and
   verification sidecars.
5. Verify Git and create a clean v24.6.243 baseline commit if the extracted
   folder is not already a repository.
6. Re-run the Phase 1/2 storage suites, Phase 3 client characterization, Phase
   4 module characterization, Phase 5A persistent-job suites, Phase 5B cost
   suites, all five frontend fixtures, live source smoke and tracked-language
   static validation before changing code.
7. Preserve schema versions 1–10, all verified-backup/recovery guarantees,
   every JSON/localStorage mirror, all 108 route URLs and every legacy response
   field.
8. Preserve Phase 5B estimate/authority provenance, opt-in request guardrail,
   explicit missing billing data and every paid-operation non-replay boundary.
9. Limit any authorized Phase 6 to its exact owner-approved frontend scope.
   Keep credential migration, unrelated workflows and roadmap items 4/7/8 out
   of scope unless separately authorized.
10. Work milestone by milestone, test and checkpoint each stable change, then
    stop at the end of the authorized phase.
