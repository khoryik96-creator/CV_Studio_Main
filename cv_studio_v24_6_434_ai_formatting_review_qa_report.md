# CV Studio v24.6.434 — optional AI formatting review

Owner-approved source work on `codex/v24.6.434-formatting-review`, based on exact
GitHub master `efe42f21c3c4ab82c725f799f74e360296b511e3` / v24.6.433, verified
1 October 2026. PR #220 is merged and its branch is complete. Root `VERSION` was
bumped with `bump_version.py`; no PR, merge, release or protected ZIP was created.

## Result and bounds

Normal single Format CV has an unchecked AI formatting review toggle. Off keeps
the existing flow; on requests one additional check using the selected
single-CV provider, existing protected key resolution and paid-call guards. The
toggle lasts for the current page and returns to off on reload. Blind, batch,
uploaded-DOCX Summary insertion and other tools are unchanged.

The check compares original text with the data prepared by existing export
passes. It shows a plain explanation, original quote, proposed correction and
Apply fix where verification permits. It checks content/structure, not visual
Word layout. Uncertain/unsupported suggestions are manual flags. AI output is
untrusted and rendered as text. There is no candidate evaluation or browsing.

Supported fixes restore a job, qualification or plain duty; move an existing
plain duty; or correct employer/title/qualification/date fields. All inserted
words must occur in the same unique source quote outside referee sections.
Identity, summary, skills, hidden fields and deletion are prohibited. Exact
previous values, input limits (150,000 source characters, 200,000 JSON
characters), bounded nesting and at most eight issues are enforced. Invalid
Unicode or malformed field shapes fail safely.

Apply performs no provider call. A process-bound signature ties the suggestion
to the exact source/data for 30 minutes. Existing normalization/reference/pay
passes still run; ineffective/non-idempotent fixes reject replacement. Signed
approved data and correction words must survive Word generation before the
browser replaces its preview/file. Undo restores the exact prior pair. A new
check is required before applying another suggestion to changed data.

Failures retain the completed CV; stale responses cannot overwrite cleared or
different input. Successful review cost joins the initial format cost. Explicit
Check again is labelled as another AI call and recorded separately. Completed
stale reviews still enter accounting history. Malformed/oversized review
envelopes preserve completed-call usage/cost and are never automatically replayed.
Issues/unavailable checks hold existing JobAdder auto-upload; manual apply,
undo and recheck never schedule an upload.

## Validation

- New tests failed first for the missing toggle/review/apply behavior; later
  reproductions failed for stale paid accounting, malformed field shapes and
  invalid Unicode before their corrections.
- New review suite: 21 tests and seven subtests passed with simulated providers.
  Real Node Word output verifies restored jobs, qualifications, duties, corrected
  titles and exact duty movement under the proper employer. Loss of an approved
  Word correction rejects the file; tampered/stale/expired tickets reject apply.
- All 27 frontend suites passed, including toggle off/Blind, source evidence,
  text escaping, staged Apply/Undo, paid accounting, export failures and late
  responses and preview-render failure rollback. No live provider, paid request
  or JobAdder call was used.
- All 899 existing registry cases and their expectations are unchanged.
  `cvstudio_cv_normalize.py`, `cvstudio_cv_reconcile.py`, `generate.js`,
  `template.docx` and the registry are byte-identical to master. All 17 original
  fidelity functions retain identical ASTs. A replay on 103,785 existing
  code/test/document fragments found zero work-row or summary-pay differences.
- Generated controls cover 90 Unicode/company variants and their invented-fact
  counterexamples, oversized/deep/invalid text and malformed structures.
  Deliberate mutations were caught: 14 Python guards (source/data/signature,
  evidence, allowlist, exact before, referee exclusion, expiry, invalid text,
  field shapes, approved-output proof and Word retention) and eleven frontend guards
  (toggle, source, escaping, proof, staged publish, undo, cost, reset and stale
  accounting/preview rollback). Mutation helpers stayed outside tracked source.
- Complete unfiltered comparison: baseline v433 had six failures, 1,496 passed,
  four skipped, 6,856 subtests. v434 had the same six failures, 1,517 passed,
  four skipped, 6,864 subtests. There were no new failures. The additional
  opt-in OLE failures were also reproduced directly on the original v433 checkout.
  Final follow-up after bounded-envelope accounting correction excluded only
  those exact six baseline fixtures: 1,517 passed, four skipped, six deselected,
  6,864 subtests. Final frontend rollback checks passed afterward.
- Architecture/version/state-isolation gates, 24-assertion live source smoke,
  all frontend syntax, 161 Python files, nine PowerShell scripts, three POSIX
  scripts, repository consistency and Git whitespace passed. Windows source
  preflight functionally verified pinned Antiword 1.3.5, Tesseract 5.5 English
  and adm-zip 0.6.0. No protected/native compilation or new macOS claim.

The six baseline failures retained are:

1. `test_python_runtime_resolver_returns_the_exact_validated_interpreter`
2. `test_real_update_preflight_uses_launcher_path_python_before_stale_fixed_install`
3. `test_downloaded_preflight_is_self_contained_for_v357_upgrade_transition`
4. `NativeDocRecoveryTests.test_recovered_text_passes_the_same_quality_gate`
5. `NativeDocRecoveryTests.test_recovers_clean_text_from_a_legacy_doc`
6. `UnverifiedDocRecoveryHelperTests.test_helper_recovers_when_opted_in_for_a_legacy_doc`

The first three are the previously documented updater-runtime environment
fixtures. The last three concern the existing opt-in native OLE helper in this
local environment; the mandatory verified Antiword path/preflight passed.
They remain outside this formatting-review change. Unfiltered results are
retained, and this report does not claim the complete local suite is green.

## Preview and preserved contracts

Preview: `http://127.0.0.1:5069/?preview=v24.6.434`, HTTP 200 and actual
`/instance` version verified. The live page shows the unchecked toggle and its
extra-call explanation. Preview state is temporary and isolated; owner
credentials/settings were not copied or changed. UI/transport tests use
synthetic content; AI detection quality on a live provider is not claimed.

118 routes and their exact hash, all five ordered guards, 80 MiB limit, SQLite
schema 10, job schema 1, provider non-replay/cost gates and default response
fields remain. Existing dependency PRs #213–#215 are untouched. Source-only work
does not update any installed or protected package.
