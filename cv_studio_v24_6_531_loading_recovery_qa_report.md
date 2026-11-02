# v24.6.531 loading and companion-update recovery

2026-11-02, Asia/Kuala_Lumpur. Local unmerged checkpoint on
`codex/v24.6.531-companion-update-readiness`, base merged530/PR276/
`73061bcc93f7249e67d74e8e192c333c34c99aa6`.

## Evidence and corrections

Owner reports Checking companion stuck and a blank company-status list. Read-only
local setup responded immediately with530. Read-only clients overview returned
two saved signed statuses and two followed clients; status read returned four
choices. The visible browser first showed the backend busy response, later all
four choices and a populated company list. Data was not lost or reset. No private
company/account/profile details, credentials or raw bodies are retained here.

Three new reproductions failed on530 before production changes:
- A stalled saved-ad read prevents the old Promise.all load from requesting or
  displaying company statuses, even after the account overview is ready.
- Setup headers/JSON have no dedicated end-to-end update deadline; the shared
  fetch deadline clears after headers. One Checking message covers all stages.
- Worker manifest headers/JSON can hold the cross-module update reservation
  indefinitely; the UI timeout alone cannot release that reservation.

Client overview/status display is independent of the saved-ad read. Safe client
POST reads have a60-second end-to-end UI bound, GET saved ads15seconds, with
AbortController cancellation and ignored late completion. Choice writes are not
given a new timeout or retry. Failed initial loading leaves explicit recovery
buttons enabled; existing choices are preserved. Ads apply only to the same
account generation. Pull/Add remain blocked until the ad list has loaded once,
so partial startup cannot bypass duplicate-read prerequisites.

Companion UI now distinguishes local setup, connection and apply. Setup8seconds,
connection6seconds, apply12seconds; no automatic retry. The central fetch timeout
is a10-second backstop, longer than the dedicated8-second deadline so it cannot
mask stage guidance. Both buttons share one operation; Start is blocked during
it. The worker bounds manifest headers+JSON8seconds, cancels the read and releases
the existing reservation on failure. Late manifest completion has no reload path.
Trust, exact manifest version, downloaded-copy migration guidance, both scans'
busy gates and paid non-replay remain. App and companion both need updating.

## Verification

- 85 of85 root JavaScript fixtures pass in the final sequential sweep.
- 88 focused Python tests and8 subtests pass: clients, Sourcer route/service,
  source version authority and test-state isolation. The existing standalone
  Windows temporary-log cleanup warning occurs after the successful suite;
  process exit remains0. No owner state path is used by those tests.
- 24 isolated live-source smoke assertions pass.
- Actual isolated Chrome: deliberate ad-list timeout still displays statuses,
  setup timeout and silent companion recover buttons with clear messages,
  no automatic reload occurs, and one explicit subsequent click succeeds.
- Existing native Signed clients Follow/link/readiness/reload/filter/sort,
  no-status Pull guard and390px mobile scenario pass, zero page errors.
- VM cases cover setup headers AND body, late setup/status replies, cross-button
  coalescing, manifest headers AND body, both-session release, then a new scan
  while a late manifest resolves without reload. Old trust/busy/non-replay tests
  remain unchanged. New cases failed on530 and pass with the corrections.
- Source/static validation, Windows Antiword/Tesseract/adm-zip functional
  preflight, repository consistency and diff checks pass.

No Python behavior changed beyond generated release identity; the full2316-test
Python suite passed on the byte-equivalent backend in530, and relevant88 are
rerun for531. No claim of a new full Python sweep or macOS native verification.

Native reproduction: start `tests/browser/signed_clients_server.py`, then run
`tests/browser/loading_recovery.js` with CVSTUDIO_PLAYWRIGHT and optional
CVSTUDIO_CHROMIUM. It verifies the fictional fixture marker and blocks non-local
network. Evidence is ignored under runtime/audit529 (*531 logs) and
runtime/loading531 (fictional screenshots). No real provider/paid request or
JobAdder write, owner data/installation/extension update, publication or hosting.
The exact original live extension stall is not proven; the covered failure
modes are code/fixture-confirmed. HeldPR257 remains excluded.
