# Historical QA record — v24.6.441 batch JobAdder pre-write recovery

Tested on 2026-10-13. Use root `VERSION` and `HANDOFF.md` for current state.
Continues PR #227 / `codex/v24.6.439-batch-jobadder-link` from `385607d` / v440.
Owner authorized merging the corrective. The initial v440 hosted run passed
all three gates (unfiltered Windows: 1,587 passed, four skipped, 7,121 subtests),
but automatic review found a safe-recovery gap, corrected before merge.

## Finding and bounded correction

The manual action cleared its held payload before reading the original file or
looking up a candidate. A local file-read or read-only lookup failure therefore
removed the only upload action even though no JobAdder write had started. The
finished file still existed, but the user had no retry through that row.

The batch orchestration now retains an explicit retry after local original-file
read/blob construction failure. The shared batch upload helper marks only an
exception from the initial read-only candidate lookup as pre-write. Neither
candidate create/update nor attachment-upload failures receive that marker.
The row keeps its visible failure and exact finished file/data, and offers
**Retry upload** only for proven pre-write failures. A user click is required;
no failed operation is automatically replayed. Ambiguous writes expose no retry.

This retains the shared JobAdder upload-helper signature, response/error details,
candidate URL construction, paid formatting boundaries and transport policies.
The source/review warning and busy-state controls still govern the held action.
Manual email entry uses the same orchestration and recovery instead of a
duplicated upload block. The explicitly entered email remains authoritative
through a failed attempt and its retry, even if parsed email data differs.

## Grounded verification

The new regression failed before the correction because the held payload was
lost after a synthetic file-read failure. The final frontend fixture loads the
real batch upload helper and orchestration with synthetic boundary responses.

- File-read and candidate-lookup failures perform zero writes, retain the exact
  finished blob/data, display failure and keep the explicit retry action.
- A subsequent explicit retry performs one write, preserves the profile link
  and does not repeat parsing, generation or paid formatting calls.
- Ambiguous candidate-create and attachment-upload failures perform one attempt,
  retain no retry action, and cannot be replayed by calling the row action again.
- Manual email entry has the same lookup/ambiguous-write controls; its grounded
  pre-write regression also failed before the duplicated handler was replaced.
- Prior actual OAuth completion, pending/rejected login, unchanged refreshes,
  auto-upload-off, warning holds, Apply/Undo, duplicate filenames, manual email
  and candidate/dashboard link controls remain in the same passing fixture.

All 29 frontend suites passed. Tracked-language syntax, repository consistency,
owner-source preflight and the 24-assertion source smoke passed. Full isolated
Python regression: **1,584 passed, four skipped, three deselected, 7,121 subtests**
in 154.31 seconds. Only the same three documented updater-environment fixtures
were excluded. Final frontend, version, changed-JavaScript syntax and repository
consistency checks are repeated after the manual-email controls.

## Boundaries

No live JobAdder/provider requests, credentials or paid calls were used. App
tests and smoke isolate receipts and all durable/credential state. No owner
installation/receipt update, protected build or release ZIP. No source-reading
heuristic, route/schema or formatted CV content/layout changed. The final head
must pass all three hosted gates before squash merge; issue #35 records exact
final tested/merge identities and results. No real-account upload or native
Word visual verification is claimed.

Source preview on loopback5071 retains its existing isolated temporary state;
HTTP200, v24.6.441 and the exact development runner/root were verified.
