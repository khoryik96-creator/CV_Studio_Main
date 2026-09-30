# v24.6.429 — bounded review fixes and regression evidence

Verified on native Windows x64, 2026-09-30. Baseline:
`cb0bcaee5e4c92bbf0bb92758744446965119156` / master v24.6.428 (#219).
Branch: `codex/pr220-v24.6.429-guardrail-review-fixes` (PR number provisional).
This branch is not merged; no release or protected ZIP was produced.

## Fixed

1. **Tests could overwrite the installed authorization.** Two pure CV test
   modules no longer create receipts. Five app-import test modules put receipts,
   database, journal, credential paths and salary data in temporary state and
   restore overrides after import. A fresh-interpreter test for each of the
   seven modules protects an owner's sentinel receipt and data paths. Test
   isolation only: no production authorization logic changed.
2. **A major could attach to the wrong degree at the same university.** Major
   and grade-label recovery now require a uniquely identified degree/date
   block when the school appears more than once. Missing or conflicting
   evidence leaves the entry unchanged. Existing majors and graduation-year
   restoration are preserved.
3. **Payroll achievements could disappear.** Explicit recipients immediately
   following the exact salary amount, such as "for each employee" and "per
   employee", preserve payroll work. A different amount, another sentence or
   comma part, and a job-role description cannot shelter personal pay.
4. **Explicit earnings could leak into the Summary box.** Earnings labels and
   candidate-subject receipt-per-period statements are filtered. Company
   earnings and explicit business receipts remain. The shared server filter
   still serves Format, Batch, Summary, Blind and both DOCX paths.

The pay matcher also avoids redundant scans of clear work and abbreviation
fragments. Direct amount matches may skip their already-checked span; reverse
matches still examine embedded pay phrases. This preserves the existing
two-second hostile-input gate without raising its threshold.

## Guardrail evidence

- All **805 baseline fixture cases remain unchanged**. **34 cases added**.
- Reproducing tests failed before the fixes, including seven independent
  receipt-overwrite checks and real parse-to-DOCX tests.
- **12 deliberate mutations caught**: education pooling, degree/date evidence,
  uniqueness, earnings/receipt detection, business exceptions, employee
  recipients, amount boundaries, overlapping-match handling and fast rejection.
  The amount-boundary mutation initially survived; a no-thousands-comma case
  was added, then it failed as required.
- Whole-suite replay recorded **23,536 unique inputs** to the two changed
  public helper boundaries. **394 intended differences**, all in the added
  fixture/generated/route-test inputs; **zero unexpected differences**.
- Compared **110,096 distinct sentence/string fragments** from own tracked
  Python/JavaScript/HTML/JSON code, fixtures and Markdown documentation
  (including Python literal values; third-party vendor bundles excluded).
  **19 differences**, all examples added for these fixes. No older repository
  examples changed.

## Gates

- Unfiltered full run: **1,486 passed, 4 skipped, 6,767 subtests passed**;
  **3 existing Windows updater fixture failures** listed below.
- Full rerun excluding only those three: **1,486 passed, 4 skipped,
  3 deselected, 6,767 subtests passed**, about 209 seconds.
- All **26 frontend suites passed**.
- Final focused rerun: **164 passed, 3,726 subtests passed**, including the
  independent receipt checks, all guardrail/generated cases, real DOCX routes
  and version single-source checks.
- Syntax: **160 Python files, 77 JavaScript files, 9 PowerShell files**
  passed. Version-single-source, sealed route/security/schema contracts,
  repository byte/line-ending consistency and protected-source preflight pass.
- Verified bundled Antiword **1.3.5** is trusted and functional on Windows x64.
  Installed Tesseract **5.5.0.20241111** passes its functional check.
- Live isolated preview responds HTTP 200 with v24.6.429 on loopback port 5065.
  Its settings/credentials are separate from the owner's installed copy.

Remaining baseline-only failures, also reproduced before these fixes:

- `tests/test_update_launcher.py::test_python_runtime_resolver_returns_the_exact_validated_interpreter`
- `tests/test_update_launcher.py::test_real_update_preflight_uses_launcher_path_python_before_stale_fixed_install`
- `tests/test_update_launcher.py::test_downloaded_preflight_is_self_contained_for_v357_upgrade_transition`

These local Windows fixture/resolver mismatches are not silently treated as
passing. Launcher runtime selection and exact-package security checks were not
weakened to satisfy them.

## Boundaries and limits

No work-row/reconciliation algorithm, DOCX layout/bullet renderer, route,
schema, credential store, OAuth, crawler or dependency changed. Generated
version stamps are the only changes in production files outside the normalizer.
The existing normalizer is already part of protected packaging, so rebuilding
from this branch carries these fixes. Native protected compilation/package
smoke testing remains the owner's separate manual build; source preflight is
not a claim that a new protected binary was tested. No macOS native test, live
credentialed external call or paid-provider call was performed.

This evidence found no regression within the exercised cases; it cannot prove
every possible CV or provider response is safe. Ambiguous education recovery
continues to prefer no change over guessing.
