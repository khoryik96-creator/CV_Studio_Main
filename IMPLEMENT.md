> **Version source of truth.** The current release is whatever the repository-root [`VERSION`](VERSION) file says — it is generated into every code surface by `bump_version.py` and enforced by `tests/test_version_single_source.py`. Any version number written *below* is historical context from when this document was authored; do **not** treat it as the current baseline. See `HANDOFF.md` for live project state.

# Phase Execution Runbook

## Current gate

Phases 1, 2A, 2B, 3, 4, 5A, 5B and 6A–6C are complete. The separately authorized
mandatory Windows-x64 Antiword milestone completed in v24.6.240, and its
verification-to-execution TOCTOU race is corrected in private owner/source
release v24.6.241. The bounded JobAdder account-management and settings
milestone is complete in private owner/source release v24.6.242. Phase 6A
frontend modularisation and the bounded Phase 6B local-jsPDF lazy loading
change are complete on their source branches without changing the v24.6.243
installed identity. The corrected v24.6.245 long-CV/access source is merged at
`4c1e9a420830f62b68889518945d889260a3f616`. The v24.6.246 candidate
added mandatory architecture-pinned Antiword for Intel and Apple Silicon
macOS, made functional Tesseract plus English data a setup requirement on
Windows and macOS, and restored native Mac CI/protected-build gates. That
source is merged at `a6b35d2e0cad977e737622ed7d10e451ed5f7de3`.

Phase 7A is now explicitly authorized on
`agent/v24.6.247-modular-monolith-foundation`. Keep the v24.6.246 installed
identity and the Python/Flask plus JavaScript stack. Introduce only the
composition root, explicit current module inventory and exact application
contract sealing needed for later one-domain-at-a-time extraction. Stop after
tests, focused review and commit, before release, merge or Phase 7B.

## v24.6.247 Phase 7A implementation decision

Construct the existing Flask application through `cvstudio_architecture.py`
without moving route decorators or changing initialization order. Record each
current app-independent module exactly once in an acyclic dependency registry;
retain `app.py` as the temporary legacy web shell and sole composition caller.

After all existing decorators and error handlers are registered, seal the app
against the known 108-route URL/method/endpoint digest, five ordered global
request guards and 80 MiB request limit. Any drift must fail visibly at startup
and in focused tests. Protected-source validation must require and compile the
new architecture module. No route, endpoint name, schema, response, security
gate, feature, dependency behavior or platform claim may change.

## v24.6.246 native dependency implementation decision

Bundle the current official content-addressed R-universe Antiword 1.3.5 archives
and exact 37-file runtimes separately for Windows x64, Intel macOS and Apple
Silicon macOS. macOS verifies and runs only its matching architecture from a
private immutable snapshot; Windows retains its deny-replacement handle model.
Every installation and protected smoke must prove genuine `.doc` extraction.

Treat Tesseract as mandatory on every supported platform. Setup may acquire it
through the platform package manager, but completion requires an executable
version check and English language data. Runtime diagnostics and all OCR callers
share the same functional resolver. GitHub's native Windows, Intel Mac and Apple
Silicon Mac runners are the release gates; no Mac artifact or support claim may
be made from static inspection alone.

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
