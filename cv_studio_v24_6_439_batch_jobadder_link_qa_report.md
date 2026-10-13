# Historical QA record — v24.6.439 batch JobAdder status/link corrective

Tested on 2026-10-13. Use root `VERSION` and `HANDOFF.md` for current state.
Branch `codex/v24.6.439-batch-jobadder-link` starts at exact merged master
`a40bf63d8c879db0ef1d7b6cf6c3cb455fb32736` / v24.6.438.

## Report and cause

The owner reported no JobAdder status or candidate link after batch formatting,
while single formatting retained its JobAdder controls. The main-branch batch
flow populated a status only inside the connected/auto-upload-enabled branch.
When automatic upload was disabled or the connection was unavailable, it left
the status hidden and offered no manual upload for that completed row.

Both skipped-upload paths reproduce the blank UI with synthetic inputs. The
owner's live account/preferences were not inspected, so this record does not
claim which of those conditions was active in their browser. Successful uploads
already generated profile links; those existing paths remain unchanged.

## Correction and coverage

Completed rows retain their exact file/data upload payload whenever uploading is
skipped. The row explains whether JobAdder needs connecting, auto-upload is off,
or a source/review warning needs checking. Connected clean rows offer **Upload
to JobAdder**; warning rows retain **Upload anyway**. No skipped operation is
automatically replayed when the connection changes. Reconnection refreshes the
rows and enables the explicit upload action without reformatting.

The new regression failed before the fix. Real batch orchestration, row
rendering, manual-upload actions and the shared connection renderer run in the
frontend fixture with synthetic provider/upload responses. Coverage includes:

- Auto-upload off and disconnected completion, with zero automatic writes.
- Connecting after formatting, without a new format run or automatic upload.
- Per-row manual uploads, retained output blobs, and persistent profile links.
- Identical filenames with different candidate links and exact dashboard IDs.
- Repeated clicks after completion do not replay the upload.
- Missing email prompts for input; entering it retains the normal upload/link.
- Connected, enabled automatic uploads still produce links for both rows.
- Existing source/review holds, Apply/Undo, stale work and busy-state tests pass.

All 29 frontend suites passed. Tracked-language syntax, repository consistency,
version stamping, owner-source preflight and the 24-assertion source smoke passed.
The full isolated Python suite uses the same three documented local updater
environment exclusions as v438: `test_python_runtime_resolver_returns_the_exact_validated_interpreter`,
`test_real_update_preflight_uses_launcher_path_python_before_stale_fixed_install`,
and `test_downloaded_preflight_is_self_contained_for_v357_upgrade_transition`.
These passed in the unfiltered hosted v438 gate. Final isolated local results:
**1,584 passed, four skipped, three deselected, 7,121 subtests**, in 194.62
seconds. The final version-source test passed again (five tests).

## Boundaries

No source-reading heuristic, formatted CV content/layout, provider call, route,
schema, upload transport or candidate URL construction changed. The 118 routes,
five guards, 80 MiB request limit, SQLite schema 10 and journal schema 1 remain.
App tests and source smoke isolate receipt, credentials and all durable data in
temporary state. No live JobAdder read/write or paid AI call was made. The owner
installation and receipt remain untouched; no protected build, release ZIP,
PR or merge was requested or performed.

Source preview: loopback5071, existing isolated temporary state. HTTP200,
v24.6.439 and the exact development runner/root were verified. This is not a
claim of real-account upload or native Word visual verification.
