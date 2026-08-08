> **Historical — do not use as the current release reference.** This document is a point-in-time record. The authoritative current version is the repository-root `VERSION` file; see `HANDOFF.md` for current state.

# CV Studio v24.6.245 Long-CV Output and Access Corrective QA

## Scope and provenance

- Exact base version: merged Phase 6C source v24.6.244.
- Exact base commit: `c75aa20c5a99ea5e9af84204a19703c90e0c2d36`.
- Candidate branch: `agent/v24.6.245-long-cv-access-corrective`.
- The corrected source commit is the final PR head. A new commit-bound source
  sidecar is required because the pre-review archive is intentionally immutable
  and superseded.
- No paid/live AI request, provider login, JobAdder write or credential-bearing
  operation was used.

## Diagnosis confirmed

The supplied 17-page PDF contains 22,493 extracted characters and 34 standalone
responsibility/achievement markers. The supplied faulty 11-page DOCX contains
two literal serialized JSON bullet groups and an inferred Manulife title. The
old browser callers timed out independently at 120/180 seconds, while the
provider could continue longer. Neither backend output normalization nor the
DOCX generator decoded structured objects serialized inside strings, and the
generator deliberately stringified remaining objects.

## Corrections

- Added one deterministic long-CV policy: 180/300-second backend provider
  timeouts with 210/330-second browser margins. All three `/parse` callers use
  the shared browser helper and display `long CV` when selected.
- Strengthened the parser contract: titles must be explicit source facts and
  structured bullet groups must be JSON objects, not serialized strings.
- Added idempotent backend, preview and DOCX normalization for valid JSON-looking
  bullet groups, canonical responsibility/achievement headings, narrowly
  bounded inferred-title annotations, malformed-text preservation and empty
  certification/skill filtering.
- Corrected both findings from the single independent review: top-level plain
  responsibility/achievement labels become real heading objects in all three
  normalizers, and bounded `assumed`, `guessed` and `likely` title commentary is
  removed only when tied to duties, responsibilities, content or context.
- DOCX output renders every structured group as a bold heading plus bullets,
  omits empty role-title/section paragraphs, keeps headings with following
  content where practical and never substitutes a company for a missing title.
- Moved CV Scoring to the final feature position and added version-scoped casual
  access code `1996`.
- Removed the AI Crawler password prompt, stored unlock dependency and password
  payload; the retained backend compatibility hook allows local use.

## Files modified

- `.github/workflows/ci.yml` — include the corrective frontend fixture.
- `AGENTS.md`, `IMPLEMENT.md`, `PHASE_STATUS.md`, `ROADMAP.md` — current scope,
  base, decisions, boundaries and validation record.
- `app.py` — version identity, prompt, timeout policy, backend normalizer,
  generator boundary and unlocked AI Crawler compatibility hook.
- `index.html` — version identity, shared timeout use, preview defense, tab order,
  CV Scoring lock and AI Crawler unlock.
- `generate.js` — independent normalization and safe DOCX rendering.
- `INSTALL_CORE.ps1`, `INSTALL_RECEIPT.ps1`, `START_HIDDEN.vbs`, `WATCHDOG.vbs`
  — v24.6.245 installation/runtime identity.
- `owner_build_tools/build_protected.py`,
  `owner_build_tools/BUILD_PROTECTED_WINDOWS.bat`,
  `owner_build_tools/repo_consistency.py` — consistent next-version build and
  repository checks; no protected artifact was produced.
- `tests/test_phase2a_app_cache_integration.py` — expected installed identity.
- `tests/test_long_cv_output_corrective.py` — backend, prompt, timeout, DOCX XML
  and AI Crawler access regressions.
- `tests/test_long_cv_output_corrective.js` — browser timeout, preview, tab and
  access regressions.

## Validation

- Complete Python discovery after the final production correction: **162 passed**
  in 26.829 seconds.
- Frontend: **10/10 fixtures passed**.
- Corrective focused Python: **7/7 passed**.
- Live source smoke: **24/24 assertions passed**.
- Tracked Python compilation: passed.
- Tracked JavaScript plus protected inline-script syntax: passed.
- PowerShell parser and POSIX shell syntax validation: passed.
- Repository consistency and whitespace: passed.
- Owner/source Windows-x64 preflight: passed with bundled, trusted, functional
  Antiword 1.3.5 and vetted `adm-zip` 0.5.17.
- Route/schema behavior was not intentionally changed; the complete regression
  suite preserved the existing 108-route architectural characterization.

## Manual Sai CV verification

The source PDF, faulty DOCX and screenshots were inspected. A real corrective
DOCX reproducing the supplied serialized `Business Set up` and `Manpower` groups
was generated, exported through Microsoft Word and rendered with Poppler. The
render contains proper bold headings and ordinary bullets, a blank unstated
position, one generic `Skills:` heading, no inferred-title annotation, no valid
serialized JSON object and no empty Education section. Branding, margins,
footer and alignment remain intact.

## Honest limitations

- The complete 17-page CV was not sent to a live AI provider, so no paid
  end-to-end provider latency or fresh full-CV semantic parse is claimed.
- The deterministic long-CV selection and all parse transport boundaries are
  covered locally; the old browser abort can no longer occur at 180 seconds for
  this source class.
- No protected colleague ZIP was built. No macOS artifact or Intel/Apple Silicon
  validation/support claim was produced.
- The pre-review owner/source ZIP remains immutable at source commit
  `956eb4d8faf96980a7c4c12739f00a985b6ca2ef`; it is superseded and is not a
  final artifact for the corrected PR head.
