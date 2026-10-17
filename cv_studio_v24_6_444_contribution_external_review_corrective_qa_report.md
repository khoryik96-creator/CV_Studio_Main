# Contribution external-review corrective verification

Current source version: repository-root `VERSION`. Owned branch:
`codex/v24.6.442-contribution-grouping`. Exact main base:
`fcaedaeb633c19efb9dfa55bd7f35afa0c7d5c08`; pre-correction checkpoint:
`acf541c` (v24.6.443). Local Windows verification: 2026-10-17.

## Confirmed findings and behavior

The supplied report described v24.6.442. Its seven substantive counterexamples
also reproduce against v24.6.443. Four other listed cases produce the deliberate
fail-closed legacy bullet output, so those fallback rules were preserved.

| Confirmed behavior | Bounded correction |
| --- | --- |
| A year following an unmatched employer inherits the preceding employer | End ownership at that unknown source label. Preserve wrapped duties only when joined marked source text exactly matches a complete existing item; no prose is rewritten. |
| Later training or Awards & Recognition sections affect contribution labels | Stop at those section boundaries, including strong numbered/uppercase/colon headings; ordinary marked achievements remain items. |
| Contribution-only preview loses its section title | Display Additional Information in the existing preview section style. |
| Blind CV echoes an unblinded hint while visible items were anonymized | Discard provider `item_headings`, then rebuild only from returned visible items with matching category/count and unchanged year/non-heading anchors. Changed order, missing/rewritten items and duplicate anonymized labels fall back safely. |
| Balanced Markdown heading emphasis prints literally | Render the already-bold heading text without its emphasis delimiters, in both outputs. |
| Ampersand/category punctuation disagrees with Python | Use the same normalized category key in preview and Word. |
| Carriage returns or other recognized line separators produce inconsistent lists | Align additional-item splitting with Python `splitlines`, preserving words and the array/string representation; string list separators become ordinary newlines. |

Existing organization/candidate identity sweeps remain in place after Blind
structure repair. The new hint values never copy wording from the original CV.
The privacy counterexample is demonstrated with mocked provider output; no live
provider behavior or paid anonymization was tested.

## Regression evidence

- All 947 previous registry cases are preserved exactly. Twenty-nine appended
  cases cover source ownership, ordinary/strong section boundaries, wrapped
  duties, separators, category/emphasis handling and blinded heading metadata
  (976 total). The reported counterexamples failed before their fixes.
- Real `/parse`, `/blind` and `/generate-docx` tests replace provider transport
  only. They verify no stale source label in the returned blinded JSON or Word
  output, valid headings/bullets, emphasis rendering and category/separator parity.
- Generated controls retain the existing 200 single-group and 100 split-group
  examples, add 100 blinded-label cases and exercise all supported separators.
  Existing bounded-source and 4,000-entry tests pass. Wrapped-source matching is
  capped at 64 checks, 4,096 distinct keys and an 8,192-character source fragment.
- The original reported source/output pair was checked read-only outside Git:
  all six correct company/year headings and every achievement word still match.
  No personal document content or private paths enter the fixtures or this report.
- Final isolated full suite: **1,596 passed, four skipped, three known local
  environment fixtures deselected; 7,177 subtests passed**.
- All **29 frontend suites** pass, including full preview section-title checks.
- Full-suite capture/replay covers **324 distinct inputs** across normalization
  and blinded structure repair. Against exact main, 150 intended layout deltas;
  against `acf541c`, 125. After removing only heading metadata and normalizing
  additional-item list separators/markers, every other content field is equal.
- Comparison across 11,989 tracked text paragraphs found no unrelated differences.
- Eleven deliberate Python mutations and seven renderer mutations were caught.
  These independently break employer ownership, verified wrapping, new/strong
  section boundaries, marked achievements, line splitting, blinded hints/anchors/
  categories/collisions, section titles and Word/preview rendering.
- Tracked-language syntax, repository byte consistency, owner-source preflight
  and the 24-assertion source smoke pass. No protected package was compiled.

The unchanged local exclusions are
`test_python_runtime_resolver_returns_the_exact_validated_interpreter`,
`test_real_update_preflight_uses_launcher_path_python_before_stale_fixed_install`,
and `test_downloaded_preflight_is_self_contained_for_v357_upgrade_transition`.
No new hosted-check or native Mac result is claimed.

Routes, five guards, 80 MiB limit, SQLite schema 10, journal schema 1, protected
credentials and paid-call/retry/non-replay boundaries are unchanged. Test state
is isolated. No owner installation/receipt or document edit, live JobAdder or
provider call, protected build, PR or merge occurred.
