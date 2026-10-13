# Historical QA record — v24.6.440 batch JobAdder OAuth review corrective

Tested on 2026-10-13. Use root `VERSION` and `HANDOFF.md` for current state.
Continues owned unmerged branch `codex/v24.6.439-batch-jobadder-link` from
`de8bef3af26fddf0f5d1ab2d0706a3d4e2b1edf3` / v439. Merged master remains
`a40bf63d8c879db0ef1d7b6cf6c3cb455fb32736` / v438.

## Finding and minimal correction

The v439 read-only reviewer found that the actual OAuth success callback set
`window._jaToken=true` before calling `updateJAConnectedUI()`. The shared renderer
therefore missed the disconnected-to-connected transition and did not refresh
completed batch rows. The earlier fixture invoked the renderer directly and
missed that preceding assignment.

One production statement is removed: the callback no longer preassigns the
connection marker. The established renderer still sets it from the successful
backend payload, now observing the prior disconnected state and refreshing the
rows. Existing token/session transport, preference handling, warning holds and
candidate upload/URL functions remain unchanged. No forced periodic rerender
is added, preserving in-progress email inputs on unchanged status refreshes.

## Grounded regression and controls

The expanded fixture executes the real `jobAdderLogin()` polling callback and
`updateJAConnectedUI()` with synthetic server responses. Before the production
change, it failed because successful login performed zero batch rerenders.
After the change, success refreshes completed rows exactly once. Tests cover:

- Pending and rejected login do not expose upload controls or upload files.
- Successful login reveals clean-row manual upload or warning-row Upload anyway.
- Auto-upload remains disabled; connecting never replays a held upload.
- Existing blobs, parsed data and held-upload objects retain their identity.
- Repeated connected diagnostics do not rerender rows and reset input controls.
- A subsequent disconnect hides upload actions without sending anything.
- Prior automatic/manual uploads, candidate links, duplicate filenames,
  manual email, Apply/Undo, warning holds, stale work and busy controls remain.

All 29 frontend suites passed, including the expanded callback fixture and
rejected-login control. Full isolated Python regression: **1,584 passed, four
skipped, three deselected, 7,121 subtests**, in 216.28 seconds. The same three
documented local updater environment fixtures are excluded; see the v439 QA
record for their exact names. Version-source checks (five tests), tracked-language
syntax, repository consistency, owner-source preflight and the 24-assertion
source smoke passed. HTTP200, v24.6.440 and the exact isolated preview runner/root
were verified on loopback5071 with its existing temporary state.

## Boundaries

No live credentials, JobAdder requests or paid provider calls were used.
App tests and source smoke isolate receipts and all durable/credential state.
No owner installation/receipt update, protected build, release ZIP, PR or merge.
No source-reading heuristic, route/schema, formatted content/layout, upload
transport or candidate URL construction changed. No real-account or native
Word visual verification is claimed.
