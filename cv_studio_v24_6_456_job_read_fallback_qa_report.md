# CV Studio v24.6.456 — automatic job-read fallback

Owner report: LinkedIn ad details sometimes load and sometimes fail. One live,
unauthenticated diagnostic request returned LinkedIn HTTP 429. This confirms a
temporary public-read limit as one failure cause; without the exact real ad URL,
it does not establish the cause of every reported failure.

Branch `codex/v24.6.456-job-read-fallback` continues the unmerged v455 checkpoint
`3e4f802`. The v455 job search/content/folder changes remain included.

## Correction

Previously Fill from link stopped at every public-read error and required the
owner to trigger the existing Chrome read separately, even with a connected
companion. It now preserves the structured error code and, only after
`JOB_AD_UNAVAILABLE` or `JOB_AD_RATE_LIMITED`, checks the bound companion once.

The read-only `jobStatus` command returns connected/capability/busy flags behind
the existing exact app-tab/document validation. It does not arm a connection or
perform any LinkedIn page action. A one-second response bound avoids the normal
35-second capture wait when the companion is absent. Active profile sourcing,
Jobs discovery or another ad capture is left alone.

An available, idle companion performs one existing canonical `jobFromLink`
capture. The public request and browser capture are never automatically
repeated. Browser failure retains the request correlation and expands setup;
absence/busy also expands setup. Existing source identity checks, source-switch
confirmation, manual corrections, optional contact/status/follow-up, chosen
folder, rich content and nonempty refresh protections remain.

This improves handling of public-read failures; it does not make public access
always available or bypass LinkedIn login, checks or access limits. It requires
the v456 companion files, Reload and reconnecting the app tab in Chrome. An
older companion remains usable through its existing explicit read controls.

## Verification

Performed on Windows x64 on 20 October 2026 with isolated receipts/state and
synthetic fixtures. No live paid/provider request, owner saved-record mutation
or installed app/receipt update was performed.

- Full unfiltered Python regression: **1,732 passed, four skipped, 7,599
  subtests passed**, 177.83 seconds.
- **All 38 JavaScript suites passed.** New actual-controller tests cover public
  success without a probe, both eligible error codes, one public request/one
  capture, short disconnected timeout, active-run isolation, failed/mismatched
  captures, manual corrections, changed-source success/failure, noneligible
  security/storage errors and empty content refresh preservation.
- The existing link-capture worker suite verifies status rejects an unbound
  sender and reports in-flight capture/profile runs as busy. All prior worker
  lifecycle, job search, profile modes and Job Leads tests continue to pass.
- Syntax, repository consistency, whitespace, owner-source preflight and 24
  source smoke assertions pass. Actual bundled Windows Antiword/Tesseract
  functional preflights pass. No native macOS/protected compilation claim.
- Actual in-app browser using an isolated synthetic public-reader/companion:
  public HTTP 429 transitions automatically to a populated company/role/location,
  posting date and rich description; the manual note and folder survive and
  nothing is saved automatically. A second disconnected test returns promptly,
  expands companion setup and retains its manual note and empty source fields.
  Screenshot proof is retained in ignored runtime.
- Persistent preview 5074 runs v24.6.456. Read-only SQL value hashes before and
  after restart confirm both saved lead rows are exactly unchanged. Earlier
  draft tabs are preserved. The installed port-5000 app is untouched. Synthetic
  UI tabs/server are closed after verification.

## Boundaries

The 120-route seal/digest, five ordered guards, 80 MiB request limit, main SQLite
schema 10, dedicated Job Leads schema 2 and journal schema 1 remain unchanged.
No new route, storage migration, cache, extension permission, key handling,
provider request, external mutation or automatic worker is added. Companion
packaging remains four assets; VERSION/generated surfaces are 24.6.456.

Live installed-Chrome execution and real LinkedIn layouts were not verified by
the synthetic browser tests. Public-read availability remains controlled by
LinkedIn. No push, PR or merge was requested or performed.
