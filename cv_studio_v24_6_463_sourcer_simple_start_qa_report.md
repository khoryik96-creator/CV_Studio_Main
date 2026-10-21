# CV Studio v24.6.463 — simpler LinkedIn Sourcer startup

Historical QA record; root `VERSION` remains the release reference.

The owner confirmed using Chrome/Brave with the companion connected. The first
message required the existing DeepSeek checkbox. Their later screenshot showed
screened candidate cards and two reported AI attempts followed by a generic
browser-action error, so it establishes a failure after startup rather than a
disconnected or never-started search. It does not establish the exact failing
profile action. No user profile data was copied into fixtures or logs.

## Behavior

The primary form now contains the brief, detected-source status, explicit DeepSeek
balance/data-sharing permission and Start search. Search options retains manual
People/Recruiter Lite/Recruiter mode, source selection, keyword-vs-existing-search,
pages and API-attempt limits. Defaults remain 10 pages / 35 attempts; the current
limits remain visible beside consent. The current LinkedIn filters are kept by
default, with a clear explanation that the brief ranks those results and does not
change their location filters.

Tab discovery runs on initialization and Start. It preserves a compatible manual
selection or chooses the most recently used compatible search, rejects Jobs and
profile tabs, and detects the search type. Startup validates readiness before any
paid work. Missing/disconnected sources and backend-rejected starts preserve the
previous candidate list. Stop during detection sends no new paid request. No
permission is checked or persisted automatically.

A concrete ownership bug was reproduced: the companion discarded a background
profile tab when LinkedIn added one trailing slash to its exact observed URL.
The new regression failed against the previous code. A bounded same-page comparison
now permits that one suffix through update events, reads, suspension recovery,
navigation and conservative cleanup. Query/hash changes, another profile/path,
activation, inconsistent pending navigation, document binding and before/after
injection checks still stop commands. This corrects a possible cause of the
screenshot's browser error; no live reproduction proves it was the precise cause.

## Verification

- Full isolated Windows Python suite: **1,737 passed, four skipped, 7,599 subtests
  passed**, 173.49 seconds. **All 42 JavaScript suites passed.**
- New UI tests use the real controller/core with simulated transport: automatic
  tab/type detection, explicit consent, existing filters, preserved manual source,
  missing/disconnected readiness, old results, rejected starts, invalid limits and
  Stop before paid work. No provider/network call is required by these fixtures.
- Ownership regression verifies the slash change through worker suspension,
  reading, navigation and cleanup. Negative cases prove query/hash/identity changes
  remain unread and unclosed; all existing lifecycle/takeover/limits cases passed.
- Browser UI with actual backend/controller and simulated companion/DeepSeek
  detected the open People search without opening options. Start without consent
  focused the visible permission; consent plus Start completed planning, screen
  and full-detail review of one fictional candidate. The page showed Profile detail
  read and completion. Advanced settings remained available, and a disconnected
  fixture opened explicit connection help automatically. No real paid call.
- Source syntax, repository consistency, whitespace and native-dependency
  preflight passed, including bundled Windows Antiword and Tesseract/English
  functional checks. All **24 source smoke assertions passed**. No protected build
  or Mac native-test claim is made.

All browser screenshots and fixture launchers remain ignored local artifacts.
No route/schema/permission/provider-boundary change, owner record/receipt mutation,
LinkedIn write, live installed-companion verification, push, PR or merge belongs
to this local checkpoint. The companion needs its updated files, Reload, refreshed
pages and reconnection for the profile URL correction.

Four-file v463 companion ZIP is byte-verified against current source, SHA-256
`31d99522dac7db28f99959564953b63e77e82d175cfb5883dd221a383e3262ef`.
The fresh source preview on 5078 uses a read-only backup of the prior isolated
preview's Job Leads database, checked table-by-table and by integrity check. The
old preview, owner installation and original database were left untouched. The
new screen loaded with its proper disconnected guidance in Codex; live browser
discovery requires Chrome/Brave with the reconnected companion. Disposable fixture
tabs were closed and its server stopped.
