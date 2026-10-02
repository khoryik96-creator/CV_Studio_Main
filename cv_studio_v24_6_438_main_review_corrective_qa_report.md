# Historical QA record — v24.6.438 main-review corrective

Tested on 2026-10-02. Root `VERSION` and `HANDOFF.md` provide current state.
Owner requested fixing all three findings from the read-only review of merged
v437 main. Branch `codex/v24.6.438-main-review-corrections` starts at exact
master `f55a0499b4136974e49470c4ec7bfb530492dd33` / v24.6.437. Issue #35 received
the shared-file claim before editing. No new PR or merge was requested.

## Corrections

- **Normalized repeated-header identity (D2):** the established reader returns
  `Sr. Engineer` for `SR Engineer`; comparing that to the raw pair previously
  missed a second stint and overwrote 2020–2024 with 2011–2015. Both sides of
  the ambiguity guard now use the same existing company/title house style.
  Primary date matching remains exact; only the refusal guard uses this style.
- **Later work sections (D2):** the existing table reader stops at its first
  section boundary. Ambiguity collection now separately reads each later
  explicit work section until every eligible pair is already ambiguous. These
  extra rows never become the authoritative reconstruction skeleton. The
  reader and its existing output contracts remain unchanged.
- **Added-job current-header conflicts (D4):** an already-present first-job
  suggestion no longer becomes a clean review when the current employer or
  position contradicts the rendered job. It remains a manual warning, retaining
  the existing issue/upload-hold behavior. The comparison uses actual rendered
  company/title style and latest role order. Absent/consistent headers, older
  jobs and qualifications retain their existing resolved filtering. Candidate
  fields are never changed by this check.

## Regression and safety evidence

Eight registry cases and focused synthetic regressions were added before code
changes. The grounded pre-fix run failed **72 cases/subtests**, reproducing all
three findings. All **915** previous registry case objects and expectations are
unchanged. New controls cover SR/JR casing, employer style, later work sections,
current employer/position conflicts and consistent headers. Generated repeated
stints cover forty years; a 20,000-section hostile input remains under the
three-second limit. Existing 20,000-header and other performance cases pass.

Positive controls preserve unique abbreviated-title date recovery, distinct
titles/employers, unrelated/non-work sections, missing headers, consistent
rendered casing, latest-role ordering, older-job and qualification suggestions.
They also verify that a proposed older-role subset checks the actual latest
job header. Review validation does not mutate input data.

Validation on final production code:

- Focused pure helper/review/OCR/registry gate: **63 passed, 1,164 subtests**.
- Complete isolated suite: **1,581 passed, four skipped, 7,120 subtests** in
  151.44 seconds. Only the same three previously reproduced local updater
  environment fixtures were deselected:
  `test_python_runtime_resolver_returns_the_exact_validated_interpreter`,
  `test_real_update_preflight_uses_launcher_path_python_before_stale_fixed_install`,
  `test_downloaded_preflight_is_self_contained_for_v357_upgrade_transition`.
  These passed in v437's unfiltered hosted gate.
- All **29** frontend suites passed, including single/batch issue upload holds.
- **29** deliberate behavioral mutations in temporary source copies were
  caught. New mutations remove normalized identity, later-section collection,
  added-job employer/title conflicts, rendered header style and latest-role
  checks. No tracked source was mutated.
- Syntax inventory: 165 Python, 80 JavaScript, nine PowerShell, three shell and
  two command files. Syntax, version-source, repository consistency,
  owner-source preflight and **24-assertion** live source smoke passed.
- Whole-suite capture recorded **1,160** distinct serializable source inputs.
  The final replay includes tracked/new repository code, tests and documents
  against exact v437 master. Every difference must prevent an ambiguous date
  overwrite or preserve a manual conflicting-header warning. Existing reader
  outputs and OCR behavior must be identical. Final replay figures follow.

## Preserved boundaries

Routes, schemas, credential stores, provider calls/retries, cost accounting,
paid confirmations, Apply/Undo, file/export options and Word layout remain.
The 118-route contract, five ordered guards, 80 MiB limit, SQLite schema 10 and
journal schema 1 are unchanged. App tests and smoke used isolated temporary
receipt/data/credential roots. No owner installation/receipt update, live/paid
provider call, JobAdder write, protected build, release artifact, PR or merge
occurred. No native Word visual or genuine macOS testing is claimed for v438.

The separate loopback5071 source preview uses its existing isolated temporary
state. Restart/version verification is recorded with the final evidence below.

Final corpus comparison: **3,336 inputs**, including **1,088** potential
date/pipe source fragments replayed with and without a work heading. All 915
existing registry expectations are unchanged. There are **60** prevented date
overwrites (each corrected result equals the exact original parsed input) and
**12** restored manual header-conflict warnings. Existing reader and OCR
outputs are identical; **zero unexpected differences**.

The source preview was restarted with its existing temporary state. HTTP 200,
v24.6.438 and the listener's exact preview runner/root were verified on
loopback5071. The installed owner app and receipt were left untouched.
