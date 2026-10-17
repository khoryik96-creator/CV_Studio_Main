# Contribution grouping corrective verification

Source version: repository-root `VERSION`. Baseline: exact merged master
`fcaedaeb633c19efb9dfa55bd7f35afa0c7d5c08`. Development branch:
`codex/v24.6.442-contribution-grouping`. Verified locally on Windows, 2026-10-17.

## Problem and correction

The provider placed contribution employer labels, year labels and achievements
in a single Additional Information skills group. Both existing renderers put a
bullet on every string in a multi-item group, losing the source hierarchy.

The bounded source check now adds optional `item_headings` only for labels
confirmed within a unique Contribution towards Projects / Taskforce source
section. Employers must match work history; plain employer/year lines must be
followed by marked achievements. Repeated source labels or repeated parsed
items remain ambiguous and keep their original treatment. The repair preserves
category/items, their representation, text and order. It does not add omitted
achievements or change ordinary skills, dates, role bullets or work history.

Preview and Word render the confirmed labels as bold headings with achievement
bullets below. A contribution-only section has no redundant Skills wrapper.
Legacy/source-free data without heading metadata keeps its existing output.

## Evidence

- Preserved all 924 original registry cases exactly; appended 15 synthetic C1
  cases (939 total). Reported-case regressions failed before their corresponding fixes.
- The actual source and supplied output were checked outside the repository:
  all six employer/year labels were identified without changing achievement
  wording. No candidate content or personal document paths enter this report
  or the fixtures.
- Real `/parse` and `/generate-docx` route tests replace only provider transport
  and verify that labels have bold text without numbering, achievements retain
  real Word numbering, and metadata survives source-free export.
- Preview controls cover headings, duplicate items and ordinary year lists.
  All 29 frontend fixture suites passed.
- Two hundred generated employer/year combinations preserve items and are
  idempotent. Hostile source sizes fail closed within the timing limit.
- Seven deliberate backend mutations were caught by the registry, including
  removing the repair, accepting marked/unknown employers, crossing a section
  end, ignoring source/parsed duplicates, and losing joined award-count markers.
  Separate deliberate Word/preview renderer mutations were also caught.
- Exact-master corpus comparison: 11,954 text paragraphs; no unrelated
  normalization differences.
- Final isolated full suite: **1,588 passed, four skipped, three known local
  environment fixtures deselected; 7,136 subtests passed**.
- Exact-master full-suite replay: 160 distinct normalization inputs; eight
  intended heading-metadata deltas and no other differences. All original
  source registry cases remain byte-for-byte/semantically unchanged.
- Tracked-language syntax, repository byte consistency, owner-source preflight
  and the 24-assertion source smoke passed. No protected package was compiled.

The three previously documented local updater-environment fixtures are excluded
from the local full-suite command, without changing their tests:
`test_python_runtime_resolver_returns_the_exact_validated_interpreter`,
`test_real_update_preflight_uses_launcher_path_python_before_stale_fixed_install`,
and `test_downloaded_preflight_is_self_contained_for_v357_upgrade_transition`.
No hosted checks for this new branch are claimed.

## Owner document and boundaries

A separate corrected Word copy changes contribution paragraph formatting only,
removes the redundant Skills label, and keeps the Additional Information heading
with the group. Original substantive text and every other ZIP part were
verified unchanged. All five pages were rendered and inspected; changed final
pages were rendered again after the heading pagination correction. The bundled
LibreOffice renderer is unavailable on this host, so the diagnosed fallback was
an isolated, invisible installed Word instance exporting read-only to PDF, then
bundled Poppler rendering. The original supplied file remains intact.

Application routes, five guards, 80 MiB limit, SQLite schema 10, journal schema 1,
credentials, provider retries/non-replay and paid-call gates are unchanged.
Tests use isolated temporary state; no owner installation/receipt update, live
provider or JobAdder call, paid action, protected build, PR or merge occurred.
