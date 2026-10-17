# Contribution duplicate-label review corrective

Source version: repository-root `VERSION`. Owned branch:
`codex/v24.6.442-contribution-grouping`. Exact main base:
`fcaedaeb633c19efb9dfa55bd7f35afa0c7d5c08`; pre-correction checkpoint:
`3b22979`. Local Windows verification: 2026-10-17.

## Finding and correction

The independent reviewer reproduced one P2 defect: label counts reset inside
each contribution entry, so two entries containing the same source employer
could both receive heading metadata. C1 requires ambiguous duplicates to keep
their existing bullet treatment.

The repair prepares the existing item keys once, counts them across every
matching contribution entry, then assigns headings using that shared count.
Unrelated skills categories are excluded. A source-backed re-check replaces
heading metadata and removes it if every label became ambiguous; source-free
export still retains already-confirmed metadata. Item values, order, category
and array/newline representation are preserved. Preview and Word renderers
require no production changes.

## Verification

- All 939 previous registry cases are unchanged; eight cases appended (947
  total). Five targeted cases failed before the repair, including split entry,
  newline/case, repeated-year, marker-normalization and stale-metadata paths.
- Positive controls retain disjoint valid groups, ignore matching labels in
  unrelated skills, and preserve source-free export metadata.
- One hundred generated split-entry cases check text preservation, normalized
  duplicate identity, valid year headings and idempotence. A 4,000-entry test
  checks duplicate handling within the timing bound. Existing single-group
  generated and hostile-source tests also pass.
- Real `/parse` and `/generate-docx` tests mock provider transport only. Both
  duplicate employer paragraphs retain real Word numbering; unique years remain
  bold, unnumbered headings. A preview fixture covers the same corrected shape.
- Focused backend run: 97 passed, 991 subtests. All 29 frontend suites passed.
- Restoring the old per-entry implementation makes five new cases fail;
  retaining stale annotations makes a dedicated case fail. The seven earlier
  source-rule mutations are still caught (nine backend mutations in total).
- Exact-master corpus comparison: 11,969 tracked text paragraphs; zero
  unrelated normalization differences.
- Final isolated full suite: **1,591 passed, four skipped, three known local
  environment fixtures deselected; 7,144 subtests passed**.
- Full-suite normalization replay covers 170 distinct inputs. Against exact
  main there are 16 intended heading-metadata deltas; against pre-correction
  `3b22979` there are six. Removing only heading metadata from both results
  makes every result equal: no item/category/order or other data differences.
  All 939 pre-correction registry cases are preserved exactly.
- Tracked-language syntax, repository byte consistency, owner-source preflight
  and the 24-assertion source smoke passed. No protected package was compiled.

The local full suite excludes only the three previously documented updater
environment fixtures, without editing them:
`test_python_runtime_resolver_returns_the_exact_validated_interpreter`,
`test_real_update_preflight_uses_launcher_path_python_before_stale_fixed_install`,
and `test_downloaded_preflight_is_self_contained_for_v357_upgrade_transition`.
No new hosted-check result is claimed.

Routes, five guards, 80 MiB request limit, SQLite schema 10, journal schema 1,
provider gates/retries/non-replay and credentials are unchanged. Tests isolate
application state. No owner installation/receipt or document edit, live/paid
provider or JobAdder call, protected build, PR or merge was performed.
