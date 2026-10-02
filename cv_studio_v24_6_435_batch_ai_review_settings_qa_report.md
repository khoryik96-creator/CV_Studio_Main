# Historical QA record — v24.6.435 batch AI review and Settings

This record describes this source checkpoint. Use root `VERSION` and
`HANDOFF.md` for the live release/work state.

## Scope and baseline

Owner requested extending the optional AI formatting review to Batch Format
and moving its toggle to Settings. Branch `codex/v24.6.435-batch-format-review`
starts at pushed, unmerged v434 `c86b2f7cd9dc03092bf146a0367b640316aea852`.
Its master base is `efe42f21c3c4ab82c725f799f74e360296b511e3` / v433, rechecked
on 2026-10-02. Issue #35 claim was posted before changes. Existing dependency
PRs213–215 are untouched. No PR, merge, protected compilation, release, live
provider call or JobAdder write was requested or performed.

One off-by-default saved preference now lives in Settings → General Settings.
Normal single and batch formatting each add one source-content review per CV
when enabled; Blind is excluded. The batch setting is captured once per run.
Each workflow uses its own selected provider (`cv_single` / `cv_batch`). The
non-secret `cvstudio_formatting_review_v1` key is added to existing durable
setting and backup allowlists, with strict true-only opt-in, hydration, restart
and tombstone behavior. No schema migration is introduced. Failed writes warn
that the choice applies only to the current page.

## Behavior and failure checks

- Per-file source quotes and Apply fix / Undo / Check again use the existing
  signed source/data-bound backend review and Word-export proof. The shared
  review renderer creates text nodes for untrusted quotes/messages.
- Apply changes only the intended row's CV data, individual/Download All blob
  registry and held-upload data/blob. Duplicate input/output filenames are
  exercised. Original alignment, summary-box and bullet-level options survive
  later Settings changes. Undo restores the exact previous Word blob/pair.
- Findings, unavailable checks and stale initial answers hold automatic upload.
  Clean reviews preserve existing auto-upload. Apply/Undo/recheck never upload.
  Failed review keeps the finished file and continues later rows without replay.
- Completed paid costs/usage are retained before review-envelope validation.
  Explicit recheck and detached late completions receive separate history entries.
- Row/file/source/data/blob ownership and unique row/output IDs prevent cross-file
  and stale changes. Active uploads lock review actions. Busy fixes block stale
  individual/all downloads, held uploads, manual-email upload and overlapping
  checks. Removed rows and late corrected exports cannot repopulate output.
- Export failure or missing approval header retains all prior output pairs.
  A render failure after publication rolls back the row/download/held-upload pair.
  Final batch rendering enables manual buttons after processing completes.

New regression cases were added before implementation and failed on the old
flow. Later failing cases exposed stale-initial-review upload, duplicate-ID,
rejected-setting-save and disabled-after-batch action issues; each was corrected
without changing old expected formatting behavior.
Final shared-renderer review also caught disabled single-CV Undo/recheck buttons;
a failing case restored the existing single-CV action behavior while keeping
batch controls locked during its in-flight work.

## Verification on Windows, 2026-10-02

- Focused isolated Python gate: 33 passed, seven subtests (review validator,
  version, existing setting repositories and two new durable setting tests).
- Unfiltered complete Python suite: **1,522 passed, four skipped, 6,864 subtests
  passed; three failures** in Windows updater runtime environment fixtures.
  Exact failed tests: `test_python_runtime_resolver_returns_the_exact_validated_interpreter`,
  `test_real_update_preflight_uses_launcher_path_python_before_stale_fixed_install`,
  `test_downloaded_preflight_is_self_contained_for_v357_upgrade_transition`.
- The exact three updater failures reproduced unchanged on the v434 checkout in
  the same environment. Three opt-in native OLE fixtures reported as failing in
  the older v434 QA now pass on both checkouts without a code change. This report
  preserves that distinction rather than claiming the whole suite is green.
- Final complete gate with only those exact three updater fixtures deselected:
  **1,522 passed, four skipped, three deselected, 6,864 subtests passed**.
- All **29 frontend suites passed**, including real module orchestration with
  synthetic paid/provider/export/upload responses and Settings persistence.
- **22 deliberate temporary-copy mutations caught**, covering strict opt-in,
  persistence/hydration/save failure, review activation/Blind/provider routing,
  cost/stale accounting, upload holds, completed controls, unique identity/source,
  active uploads, corrected downloads/held uploads, proof/export options, Undo,
  render rollback and manual-email busy guard. Live checkout was never mutated.
- Tracked-language validation including new tests: 162 Python, 80 JavaScript,
  nine PowerShell and five POSIX shell files passed. Repository consistency and
  diff whitespace checks passed. Owner-source validation/preflight passed, with
  functional trusted Antiword 1.3.5 Windows x64, Tesseract 5.5.0.20241111 English
  and exact adm-zip 0.6.0. No protected build was run.
- Live loopback source smoke: **24 assertions passed**, with temporary receipt,
  database/journal/salary/credential locations. An initial smoke harness receipt
  was placed in the wrong temporary subdirectory, preventing server startup;
  the harness was corrected to pass the smoke's active temporary path explicitly.
  Owner receipt/state were untouched.
- Existing deterministic normalize/reconcile/fidelity, review backend, Word
  renderer/template and 899-case registry are unchanged from v434. Full suite
  exercises the existing generated/hostile and registry checks. No fresh corpus
  replay is claimed for unchanged helpers; v434's replay evidence stays historical.
- Preserved 118-route contract hash
  `42768445b8fe97e48688238c02bebf5abce0251befc3d212c2d2b029911f7862`, five ordered
  guards, 80 MiB limit, SQLite10, journal1, provider paid/non-replay and credential
  boundaries. Version surfaces generated by `bump_version.py` from `VERSION`.

## Preview and practical limits

Source preview `http://127.0.0.1:5070/?preview=v24.6.435` returned HTTP200;
`/instance` reported v24.6.435 and the new checkout/port/listening process.
Browser checks verified Settings placement, default Off, saved On after reload,
normal-batch cost notice and its exclusion in Blind. Preference restored to Off;
Settings was left visible. Browser console showed no warnings/errors. Screenshot
retained outside the repository. Existing v434 preview on5069 remains available.
All preview state is temporary and no owner credentials were copied.

This is structured source-content checking, not visual Word-layout inspection.
Manual review remains necessary; uncertain corrections stay manual. No real paid
provider behavior, live upload or fresh native macOS/protected-package testing is
claimed. Runtime/test helpers, logs, node_modules junction and screenshot are not
tracked source or release artifacts.
