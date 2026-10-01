# v24.6.433 — conservative plural-subject follow-up for PR220

## Result

A final adversarial check, before merge, exposed an overbroad v432 pay-clause
override: plural subjects in work sentences can refer to employee receipts or
company earnings. The new unconditional override no longer takes those plural
subjects. The established context-aware matchers still handle them, including
standalone candidate-pay statements. Explicit candidate and singular personal
subjects still remove the two original PR220 salary reproductions.

Two new registry cases failed first. No existing fixture expectation was changed.
The v432 generated mixed-clause sweep's ambiguous plural personal-pay template
was replaced with an explicit candidate subject; generated payroll/company
plural controls were added. This is a deliberate narrowing of the unmerged
v432 override, not a change to the pre-existing context rules.

## Identity and boundaries

- VERSION: `24.6.433`, generated with `bump_version.py`.
- Immediate baseline: `36482c816f9a98b4dcca95f1226e9fae8e45a4bf`, unmerged v432.
- Merged baseline: `cb0bcaee5e4c92bbf0bb92758744446965119156`, v428.
- Existing branch: `codex/pr220-v24.6.431-qualification-pay-guards`, PR #220.
  The branch name is retained for PR continuity; its latest version is v433.
- Only the newly added salary-subject pattern is narrowed. No work-reader,
  education, renderer, DOCX layout, bullet wording, route/schema, dependency,
  credential, crawler or provider boundary changes.
- All prior v429–v432 corrections remain in the stack, including explicit
  temporary receipt environments and the gate in the existing Mac CI jobs.
  No additional job or expensive protected build is enabled.

## Guardrail evidence

- **897 prior registry cases unchanged; two appended; 899 total.** All 805
  master cases remain unchanged. Direct old/new comparison finds no prior
  registry-output changes against either baseline.
- Immediate-baseline full replay: **35,436 distinct inputs, 673 intended
  differences, zero unexpected**. These are the newly protected payroll/company
  controls and their generated combinations.
- Master full replay: **35,436 inputs, 8,746 intended differences, zero
  unexpected**. Its full suite also passes: **1,499 passed, four skipped,
  three deselected, 6,856 subtests**, 284.02 seconds.
- Immediate-baseline own-source comparison: **194,646 fragments / eight
  differences**. The changed fragments are the two new registry controls.
- Master own-source comparison: **194,646 fragments / 84 differences**.
  Archive-membership checks confirm **zero existing-text changes** against both
  baselines. The final QA document was checked separately against both helper
  versions after the full corpus pass; it adds no behavioral differences.
- Generated coverage includes explicit candidate/singular subjects and
  payroll/company plural controls across work verbs, amounts and periods.
- **24 mutations caught**: 19 formatting guards (two new plural protections,
  four v432 personal-pay guards and 13 carry-forward guards) plus removal of
  each of the five explicit receipt environments. No mutation writes into
  pretend owner state or modifies tracked production files.
- The complete v432 evidence, including its one retained load-sensitive timing
  result, remains in the v432 QA report. Neither final v433 full run has a timing
  failure; no limit was relaxed.

## Validation

- Full isolated Windows gate: **1,499 passed, four skipped, three deselected,
  6,856 subtests passed**, 222.57 seconds. No timing failure in this run.
- Focused generated/registry gate: **30 passed, 3,502 subtests passed**.
- All 26 frontend suites, 24 live source-smoke assertions, version checks,
  tracked-language syntax, repository consistency and whitespace checks pass.
- Windows protected-source preflight and native Antiword1.3.5,
  Tesseract5.5.0.20241111 English and adm-zip0.6.0 checks pass. No protected ZIP,
  live provider/JobAdder call, paid operation or credential copying.
- v432 hosted Windows regression and both real Mac dependency/receipt-isolation
  gates passed. The v433 final head must pass hosted gates before merging;
  consult PR220 for the live final result. No compiled Mac runtime claim.
- Preview: HTTP200 and `/instance` confirms v24.6.433 on loopback5068, with
  separate temporary state. Installed settings and credentials are untouched.

The same three previously confirmed local updater-environment fixtures remain
the only full-suite exclusions (see the v432 report for names/evidence). Hosted
CI runs the full suite without exclusions. Synthetic regression coverage cannot
guarantee every unseen CV layout or resolve every ambiguous pronoun reference.
