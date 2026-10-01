# v24.6.431 — qualification and summary-pay corrective

## Result

All three findings from the v24.6.430 review are corrected:

- A degree heading above the university identifies that qualification's major
  and grade label. The following degree heading cannot identify the previous
  university block. University-first and degree-below-school controls remain.
- University-first qualifications sharing a physical line retain their own
  institution prefix, with either semicolons or pipes. The master's stated
  graduation year is restored without assigning it to the bachelor's degree.
- Employee/worker job-title phrases cannot masquerade as payroll recipients.
  Hyphenated/possessive titles and unprefixed LPA amounts are covered; real
  employee recipients and their relative/action clauses remain work.

The source scan retains its preceding nonblank line in one pass. A first
implementation repeatedly copied the prefix of a large source; a new hostile
education test exposed that slowdown before it was committed. The corrected
scan passes the two-second test on 20,000 repeated qualifications.

## Identity and scope

- Merged master: `cb0bcaee5e4c92bbf0bb92758744446965119156`, v24.6.428.
- Immediate baseline: `a85035c453fb92f1788d2879b4f55e56e7d7b277`, unmerged v430.
- Branch: `codex/pr220-v24.6.431-qualification-pay-guards`.
- PR220 is provisional. No PR, merge or release is created by this work.
- Root VERSION `24.6.431` was generated with `bump_version.py`.
- The branch includes the prior unmerged v429/v430 corrections. New production
  behavior changes only in `cvstudio_cv_normalize.py`; other executable changes
  are generated version stamps. No renderer, DOCX layout, crawler, dependency,
  credential, paid-provider or external-write behavior is changed.
- Routes, guards, request limit, SQLite schema10 and job schema1 remain sealed by
  their existing tests. The protected builder includes the changed helper.
  Protected compilation remains manual; no protected ZIP or expensive CI build
  was produced. Native dependency checks below are Windows x64, not macOS tests.

## Six-step guardrail evidence

1. New cases were added before production edits. The red run reported 19
   failing fixture/end-to-end/generated checks, reproducing all three findings.
   The first correction also exposed unprefixed LPA job-role pay in the generated
   sweep; that was corrected and given explicit registry controls.
2. All **862 v430 cases remain byte-for-byte unchanged**. **29 cases** were
   appended (891 total). Direct output comparison finds no changes in those
   original cases. The 805 merged-master cases are likewise unchanged.
3. Full-suite replay records **24,674 distinct inputs** across work reading,
   reconciliation, education recovery, output normalization and counted summary
   filtering. Against v430: **310 intended differences, zero unexpected**.
   Against merged master: **679 intended differences, zero unexpected** after
   individually checking one new hostile payroll control. Its 80,052-character
   employee-recipient sentence correctly remains work; master removed it.
4. Generated salary tests sweep job titles and genuine recipients across verbs
   and amounts, alongside all previous generated cases. New long role/recipient
   shapes and the repetitive education source pass the existing/new speed gates.
5. Own-code/test/document corpus comparison: **194,053 fragments / 27 differences**
   against v430; **194,071 / 73 differences** against master after adding the
   education speed test. Every difference is new reproduction/control text or
   the intentionally added guardrail documentation. Baseline archive membership
   checks confirm **zero existing-text changes** for either baseline.
6. **14 deliberate mutations were caught**: degree-above-school evidence, next
   degree boundary, label-specific blocks, semicolon/pipe institution prefixes,
   recipient-role exclusion, unprefixed role pay, relative-clause protection,
   institution/degree/uniqueness/year-ambiguity guards, Master-institution
   protection, and the quadratic preceding-line scan. No mutation was applied
   to the production working tree.

## Validation

- Final isolated Windows full suite: **1,496 passed, 4 skipped, 3 deselected,
  6,838 subtests passed**, 187 seconds. The earlier v430 replay run, before
  adding the education speed test, was 1,495 passed / 6,838 subtests.
- All **26 frontend suites** pass.
- Real `/parse` to `/generate-docx` tests confirm the correct major/grade/year,
  removal warning and retained payroll achievement in actual generated Word XML.
- Additional no-network route checks verify ordinary and anonymized Summary,
  uploaded-DOCX summary insertion and promoted Blind source summary. Unrelated
  `/generate-ai` callers remain unchanged. All provider calls are synthetic.
- Syntax: **160 Python, 77 JavaScript, 9 PowerShell files** pass.
- Repository consistency, whitespace and Windows protected-source preflight
  pass. Genuine bundled Antiword1.3.5 functional/trust checks, installed
  Tesseract5.5.0.20241111 English and adm-zip0.6.0 checks pass.
- Live isolated source smoke: **24 assertions** pass.
- Preview: HTTP200 and `/instance` reports v24.6.431 at loopback port5066.
  Background start/restart commands were blocked by this session's execution
  policy, so a foreground managed preview was used with fresh isolated temporary
  state. The older preview and owner's installed state/credentials are untouched;
  credentials are not copied into this separate preview. Preview availability is
  tied to its managed process; no always-on-service claim is made.

## Existing limitations

The same three baseline updater fixtures are excluded, not fixed or concealed:

- `test_python_runtime_resolver_returns_the_exact_validated_interpreter`
- `test_real_update_preflight_uses_launcher_path_python_before_stale_fixed_install`
- `test_downloaded_preflight_is_self_contained_for_v357_upgrade_transition`

They previously failed on master/v430 because fixture interpreters do not meet
exact installed-package validation (exit8). This is not an all-green unfiltered
suite or a newly compiled protected-runtime claim. No live AI/JobAdder test was
performed, and arbitrary unseen CV layouts cannot be guaranteed by these checks.
