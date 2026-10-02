# Historical QA record — v24.6.436 resolved review and scan-date corrections

This records the source checkpoint tested on 2026-10-02. Root `VERSION` and
`HANDOFF.md` are the live release/work references.

## Scope and diagnosis

Owner requested that AI review omit mistakes already corrected in the formatted
CV and that the reported date error be traced and fixed. Branch
`codex/v24.6.436-review-date-corrections` starts at exact merged master
`cf48a558940b026a7713b3d31d33c9645fe48fe8` / v435. Scope and its OCR extension were
claimed in issue #35 before their respective shared-file edits.

The existing review validator retained duplicate/already-satisfied operations as
manual warnings. The review now checks the final formatted data, omits only
source-verified supported operations whose proposed details already exist, and
instructs the provider to ignore house style. Normalized date spelling, case and
bullet markers do not create content errors. Entry identity alone cannot hide a
missing duty/result field; duties must exist at the same role. Current/last
header conflicts, unsupported operations and unverified evidence stay manual.
Signed issue IDs, stale checks, cost accounting, Apply/Undo and upload holds keep
their existing contracts; retained issue IDs remain usable after filtering.

Offline inspection of the supplied scanned PDF showed a correct start year
2011, while the formatted Word document showed 2017, producing the backwards
range Aug 2017 to May 2015. The real production PDF/OCR helper reproduced the
220-DPI misreading. Independently rendered 150/160-DPI scans both read 2011.
Scanned two-line `Title / Employer | Dates` headers now get at most two alternate
reads on at most two suspect pages. Both must agree on the unique employer/title,
start month, end date and a one-digit start-year correction into chronological
order. Only that digit changes in the primary OCR text; alternative duties or
other page text are never substituted. Pixel limits, semaphore and the original
180-second document deadline remain; alternate render/OCR timeouts are ten
seconds each. Optional failure retains primary text, primary failure remains
visible, and near-deadline documents skip the optional reads.

The original work-row reader also did not recognize this two-line layout. A
separate date-only pass now uses one exact existing employer/title pair and one
unique source header to restore dates, preserving every job/duty/header/order.
Single-role dates remain on the company; multi-role dates attach only to the
matched role. Repeated stints, unrelated sections, reversed source ranges,
trailing prose and conflicting single-role date fields remain unchanged.
It does not turn an incomplete history into a replacement skeleton.

Supplied documents and rendered/OCR analysis stayed outside tracked source,
fixtures, QA evidence and coordination comments. This report records no contact
details, candidate identifiers or private document paths.

## Verification

- New source-date and review cases failed before implementation; the optional
  OCR tests also reproduced three failures before the OCR change.
- Initial focused integration gate: **103 passed, 2,598 subtests**. Includes the
  registry, review routes, date parity, real DOCX text, OCR budgets and page-aware
  PDF extraction. Corrected dates reach the actual Word renderer with duties
  retained; an already-fixed final date produces a clean review.
- Complete isolated local regression gate: **1,559 passed, four skipped, three
  deselected, 6,975 subtests**, 207.25 seconds. The only exclusions are the exact
  three existing updater-environment fixtures listed below. An earlier run
  exposed the broad-exception ratchet; the two intentional optional cleanup/
  best-effort handlers are explicitly documented, without loosening its baseline.
- Final focused follow-up: **28 passed, 84 subtests**, 1.12 seconds, including one
  additional test proving that even agreeing alternate scans cannot rewrite
  multiple year digits. No production code changed after the passing full gate.
- All **29 frontend suites** passed. Python/JavaScript/PowerShell/shell syntax,
  version single-source checks, repository consistency and Windows owner-source
  validation/preflight passed. Inventory: 165 Python, 80 JavaScript, nine
  PowerShell, three shell and two command files. Isolated live source smoke:
  **24 assertions**. Windows Antiword was trusted/functional; Tesseract 5.5.0
  with English data was functional. No protected compilation.
- **19 temporary-copy mutations caught**: resolved-filter/evidence checks,
  entry-content and duty ownership, candidate header conflicts, exact/unique
  date evidence, chronology/referee/conflicting-date guards, OCR consensus,
  single-digit/endpoints/uniqueness, page cap, near-deadline and pixel limits.
- Whole-suite capture plus final follow-up recorded **772 distinct source
  inputs**. Replayed against exact master together with relevant code/test/doc
  fragments: **2,744 inputs, zero unexpected differences**. Intended differences
  were 19 already-satisfied reviews, 50 source-date cases (including generated
  years), and three consensus OCR corrections. The row reader itself had no
  differences. All **899 existing registry expectations remain unchanged**;
  six D2/D3 cases were added. Corpus scan inspected 114,146 fragments, with 986
  potentially relevant date/pipe fragments replayed both with and without a work
  heading. The final QA document was also included in the closing corpus pass.
- The real supplied PDF passed through the production page-render/OCR helper
  at 220/150/160 DPI and recovered Aug 2011 to May 2015 in 6.58 seconds. A separate
  private full-history replay retained all four jobs and changed only the wrong
  year. No provider/paid call was made. Word correctness here is verified by
  generated document XML, with no visual Word-layout claim.
- Source-only preview serves HTTP 200 / v24.6.436 on loopback 5071 with isolated
  temporary receipt/data/credential state. Browser inspection was denied by the
  browser security policy; no alternate browser access was attempted. The new
  preview was smoke-tested independently by HTTP. Owner installation remains v435.

Known local updater exclusions, already reproduced on the baseline:

1. `test_python_runtime_resolver_returns_the_exact_validated_interpreter`
2. `test_real_update_preflight_uses_launcher_path_python_before_stale_fixed_install`
3. `test_downloaded_preflight_is_self_contained_for_v357_upgrade_transition`

## Boundaries and limits

118 routes and the sealed digest, five guards, 80 MiB request limit, SQLite10,
journal1, protected credentials, provider paid/non-replay boundaries and Word
layout remain. Review applies to ordinary single/batch CVs through the existing
shared route; its default-off setting and Blind exclusion remain. OCR rechecks
are local and add no AI charge. They can add processing time on suspect scans,
and ambiguous or unsupported dates remain unchanged for review.

No owner receipt/data change, live AI, JobAdder write, new dependency, schema
migration, release package, protected build, PR or merge was performed. No fresh
macOS native or hosted CI result is claimed. The tested owned branch is ready
to push; PR creation/merge remains a separate owner action.
