# Contribution marked-boundary corrective verification

Current source version: repository-root `VERSION`. Branch:
`codex/v24.6.442-contribution-grouping`. Exact main base:
`fcaedaeb633c19efb9dfa55bd7f35afa0c7d5c08`; preceding tested head:
`72af95f0ebf7de6f793f00abe1ab9793624b7283`. Local Windows: 2026-10-17.

PR #228's automatic review identified that an ordinary achievement such as
`- Awards`, `- Training` or `- Education` ended the contribution scan. Later
source-confirmed employer/year headings consequently lost their layout hints.
The existing generic boundaries now use the same marker distinction as the
additional boundaries: ordinary marked achievements continue, while unmarked,
numbered, uppercase or colon-emphasized section headings stop the scan.
Only this condition changes in production, besides the generated version stamps.

## Verification

- Added nine registry cases before changing the rule. Six positive cases failed
  first; three real section controls passed. All 976 previous cases are retained
  exactly, with 985 total. No existing expectations were edited or deleted.
- Generated checks cover all 59 generic section names and seven marker styles
  (413 combinations), preserving item wording/order and later employer/year
  groups. Before the correction, all 177 ordinary marked combinations failed;
  strong/unmarked section controls passed. All combinations now pass.
- Deliberately restoring the faulty unconditional boundary fails six registry
  cases; disabling real generic boundaries fails four. All 13 Python mutations
  are caught, including the 11 previous contribution/Blind CV guards.
- Final isolated local full suite: **1,597 passed, four skipped, three documented
  local environment cases deselected; 7,599 subtests passed**.
- All **29 frontend suites** pass. No renderer behavior changed in this
  corrective. Tracked-language syntax, byte consistency, owner-source preflight
  and the 24-assertion source smoke pass.
- Full-suite replay covers **333 distinct normalization/Blind CV inputs**.
  Against exact main, 159 intended layout deltas; against `72af95f`, six intended
  heading-metadata deltas. Every other content field is equal under the same
  documented comparison used for v444.
- Comparison against `72af95f` over **12,000 tracked text paragraphs** found no
  unrelated differences.

The same local exclusions are
`test_python_runtime_resolver_returns_the_exact_validated_interpreter`,
`test_real_update_preflight_uses_launcher_path_python_before_stale_fixed_install`,
and `test_downloaded_preflight_is_self_contained_for_v357_upgrade_transition`.
Hosted Windows runs these unfiltered. The prior v444 head passed all three
hosted jobs (including 1,599 Python tests and 7,177 subtests); fresh exact-head
v445 hosted results and final merge identities belong in issue #35.

The owner authorized PR/merge. No owner installation/receipt or document edit,
live/paid provider or JobAdder call, route/schema change, protected compilation
or release package occurred. v442–v444 verification reports remain immutable.
