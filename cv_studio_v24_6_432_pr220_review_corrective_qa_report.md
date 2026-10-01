# v24.6.432 — PR220 review corrective

## Result and scope

Both PR220 review findings are corrected:

- An independent candidate-pay subject is checked before the work exception.
  Personal receipts and earnings cannot hide behind a work-opening sentence.
  Business receipts, company earnings, genuine employee recipients and a
  possessive used as a work verb's object remain work. The business exception
  also survives the optional final dot in an abbreviated annual period.
- All five affected app-import fixtures pass an explicit temporary receipt
  environment. The builder cannot inherit the owner's HOME on non-Windows.
  The safety gate checks the non-Windows selector before any write and verifies
  all seven pure/application modules independently. Resolved paths accommodate
  macOS temporary-path aliases without changing real HOME or os.name.

Merged baseline: `cb0bcaee5e4c92bbf0bb92758744446965119156`, v24.6.428.
Immediate baseline: `37f4be226d5c9f19a71067a1b0b9c097d83822ee`, v24.6.431.
Branch: `codex/pr220-v24.6.431-qualification-pay-guards`, retained as PR220's
existing head; VERSION is now `24.6.432`, generated with `bump_version.py`.
PR: https://github.com/khoryik96-creator/CV_Studio_Main/pull/220 . The owner
authorized fixes and merge after gates; GitHub records the final merge status.

The existing Mac dependency jobs now also run the receipt-isolation gate.
No new CI job or protected build is enabled. Other PRs are untouched. This
corrective changes only the summary-pay normalizer, test safety/coverage and
generated version surfaces. No DOCX renderer/layout, bullet wording, routes,
schemas, credentials, crawler, dependencies or provider-call behavior changes.

## Six-step guardrail evidence

1. New fixture/generated/isolation checks were added first. The red run caught
   both salary reproductions, all five unsafe receipt setups and the generated
   personal-pay sweep. An incorrect pure-module call-count assumption in the
   new safety test was corrected; pure tests still write no receipt.
2. All **891 immediate-baseline cases** are unchanged, as are the **805 master
   cases**. **Six cases** were appended, for **897 total**. Direct comparison
   confirms no old fixture-output changes against either baseline.
3. Whole-suite replay records **34,763 distinct inputs** across work reading,
   reconciliation, education recovery, output normalization and counted summary
   filtering. Against v431: **8,067 intended differences, zero unexpected**.
   Against master: **8,746 intended differences, zero unexpected**. The new
   mixed-clause sweeps account for most added inputs/differences.
4. Generated coverage adds **10,080 mixed-clause combinations** across subjects,
   verbs, conjunctions, amounts and periods, including business/other-party
   controls. Repeated receipt/earnings prefixes join the hostile-input checks.
   Real provider-summary and generated Word XML checks verify the same removal
   count and preserved company-earnings text, with synthetic provider calls.
5. Own-source corpus comparison: **194,455 fragments / eight differences**
   against v431; **194,457 / 84 differences** against master. Baseline archive
   membership checks confirm **zero existing-text changes** for both baselines.
   Differences are new reproduction/control text and guardrail documentation.
6. **22 deliberate mutations were caught**: four new personal-pay guards, 13
   carry-forward formatting guards and removal of each of the five explicit
   receipt environments. Receipt mutations fail before any write. No mutation
   was applied to tracked production files. Earlier education-performance
   mutation evidence is retained in the v431 QA report.

## Validation and limitations

- Isolated full Windows suite: **1,499 passed, four skipped, three deselected,
  6,852 subtests passed**, 284 seconds. The three local updater-environment
  deselections are listed below; this is not an unfiltered local-green claim.
- The second, master-comparison run had **1,498 passed and one timing failure**:
  the unchanged repeated-education reader took 2.10 seconds against its
  two-second limit while the corpus audit overlapped. Its isolated pytest
  rerun passed in 0.95 seconds. AST comparison confirms that reader is unchanged
  from v431; four direct alternating old/new measurements all passed at
  0.603–0.655 seconds. The replay/corpus results remain complete and unchanged;
  the original failed-run status is retained in local audit evidence. No test
  limit was relaxed and no unrelated performance code was altered.
- The receipt safety gate was rerun after resolved-path comparison was added:
  **one test / seven subtests pass**. All five receipt mutations still fail.
- All **26 frontend suites**, **24 live source-smoke assertions**, tracked
  syntax (**160 Python, 77 JavaScript, nine PowerShell, five POSIX shell files**),
  version-source checks, repository consistency and whitespace checks pass.
- Windows protected-source preflight passes, including genuine bundled
  Antiword1.3.5 trust/function, Tesseract5.5.0.20241111 English and adm-zip0.6.0.
  No compiled protected artifact, live AI/JobAdder call or credential copying.
  Hosted Windows regression and Mac dependency/isolation jobs must pass on the
  final PR head before merge; their live status is on PR220. Local non-Windows
  selector simulation is not represented as genuine native Mac execution.
- Preview: HTTP200 and `/instance` reports v24.6.432 at loopback port5067.
  It uses separate temporary state; installed settings/credentials are untouched.
  Availability depends on its managed process, not an always-on-service promise.

Unchanged local updater fixtures excluded from the full local run:

- `test_python_runtime_resolver_returns_the_exact_validated_interpreter`
- `test_real_update_preflight_uses_launcher_path_python_before_stale_fixed_install`
- `test_downloaded_preflight_is_self_contained_for_v357_upgrade_transition`

These were already confirmed against master as exact installed-package fixture
validation failures in the local Python3.14 environment. Hosted CI runs the
complete suite without these exclusions. Arbitrary unseen CV layouts are not
guaranteed by the existing and newly added synthetic regression coverage.
