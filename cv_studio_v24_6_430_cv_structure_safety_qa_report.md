# v24.6.430 — CV structure safety corrective

## Result in plain language

All three findings from the review of Claude's R7/F4 changes are fixed:

- An uncertain employer cannot make reconciliation delete a correctly parsed
  job or its duties while another entry needs correcting. In this situation,
  CV Studio keeps the entire AI reading instead of trusting a partial skeleton.
- Reporting/working phrases with intervening adverbs cannot replace a job
  title. Genuine titles such as Managing Director remain supported.
- A graduation year on a combined education line belongs only to the uniquely
  identified qualification segment. A master's year does not date a bachelor.

The branch includes the previously unmerged v24.6.429 fixes. Nothing is merged.

## Identity and boundaries

- Master audited: `cb0bcaee5e4c92bbf0bb92758744446965119156`, v24.6.428.
- This follow-up starts at `9974868`, the verified unmerged v24.6.429 branch.
- Branch: `codex/pr220-v24.6.430-cv-structure-safety`; PR220 is provisional.
- Root VERSION: `24.6.430`, generated with `bump_version.py`.
- Production changes: two bounded CV helper modules; other code changes are
  generated version stamps. No routes, schemas, credentials, dependencies,
  provider calls, DOCX layout or crawler behavior changed.
- The protected builder already includes both helper modules. Protected-source,
  version and native dependency checks pass. No protected ZIP was compiled,
  no expensive CI build was started, and no macOS execution is claimed.

## Guardrail evidence

1. New registry cases and parse-to-DOCX tests were added before production
   changes. The initial run reproduced all three findings: 16 failing cases
   and end-to-end checks, with the older cases still passing.
2. All **839 existing registry cases are unchanged**. Direct old/new comparison
   also confirms their work-reader/education outputs are identical. **23 new
   cases** cover prose, incomplete histories, same-line education, single-degree
   field separators, repeated qualifications and institution-name false positives.
3. Full-suite differential across the reader, reconciler, education restoration
   and output normalization: **665 distinct inputs**, **22 intended differences**,
   **zero unexpected differences**, compared with v24.6.429.
4. The salary filter is unchanged; its generated/hostile-input tests still run
   in the complete regression gate.
5. Repository-wide code/test/document corpus: **193,498 line/string/sentence
   fragments**, **15 differences**. Every difference is new reproduction text
   in the added fixtures or route tests; none occurs in the baseline text.
6. **10 deliberate mutations were caught**: adverbs, uncertainty collection,
   incomplete-history fallback, qualification splitting, institution match,
   degree match, unique selection, whole-line year ambiguity, first qualification
   field handling, and protecting institutions containing Master.

The first implementation failed two old F4 cases. It was corrected without
changing their expectations: institution-first pipe fields remain one
qualification, and two different years on one physical line remain ambiguous.

## Verification

- Full isolated Windows gate: **1,491 passed, 4 skipped, 3 deselected,
  6,792 subtests passed**, about 120 seconds.
- All **26 frontend suites passed**.
- Real `/parse` and `/generate-docx` regressions verify retained job/duty text,
  correct titles and qualification-specific years. A complete work history
  still corrects provider drift; an unrelated uncertain Education line does
  not disable it.
- Syntax: **160 Python files, 77 JavaScript files, 9 PowerShell files passed**.
- Repository byte/dependency consistency and Windows protected-source preflight
  passed. Genuine bundled Windows-x64 Antiword and installed Tesseract functional
  checks passed; Tesseract reports `5.5.0.20241111`.
- Live isolated source smoke: **24 assertions passed**.
- Preview: HTTP 200 and `/instance` reports `v24.6.430` at loopback port 5065.
  Its existing owned temporary state was reused; the installed owner's state,
  credentials and authorization receipt were not modified.

## Existing environment limits

These three Windows updater fixture failures were already reproduced on the
baseline and remain unchanged. A separate v24.6.430 rerun confirms all three
still fail with exit code 8 because their fixture Python does not meet exact
runtime-package validation:

- `test_python_runtime_resolver_returns_the_exact_validated_interpreter`
- `test_real_update_preflight_uses_launcher_path_python_before_stale_fixed_install`
- `test_downloaded_preflight_is_self_contained_for_v357_upgrade_transition`

They are the only exclusions in the full gate. This is not an all-green
unfiltered-suite claim. Existing dependency alerts are separate; no dependency
upgrade, updater repair or native protected build is included in this task.
