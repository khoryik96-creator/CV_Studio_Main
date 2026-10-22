# CV Studio v24.6.470 — Fresh People search and reader readiness

Historical QA record; root `VERSION` is authoritative.

The owner showed `Cannot read properties of null (reading 'empty')` after the
planning call, then requested a new LinkedIn People search on every Start. The
controller dereferenced an unvalidated search snapshot. The browser adapter's
`!value?.loading` condition treated null as a completed read, and the worker
forwarded absent script results without distinguishing failure from readiness.
The original LinkedIn/transport event producing that null is not proven by the
screenshot. These missing-result paths are reproduced with controlled responses.

Fresh People search is now the normal default. The connected companion opens a
new inactive People source before paid work and the plan supplies its keywords.
Existing tabs are never repurposed or closed. Search options retains explicit
existing-search/filter review, manual tab selection, Recruiter Lite and Recruiter.
The narrow opening action uses the existing exact-document and browser-work gates;
it accepts no arbitrary URL. Initial pending People navigation is handled as loading.
Stop during opening prevents API start/plan. No provider request is automatically
repeated; the explicit DeepSeek confirmation and all existing budgets remain.

Missing search/profile script results receive at most 30 readiness reads through
the existing browser poll, followed by useful refresh/update guidance. Missing
results from search submissions or pagination are failures rather than retries.
The worker serializes fixed reader/access failures instead of losing script
exceptions. No arbitrary exception text is returned. The controller independently
rejects malformed snapshots before empty/result handling or paid screening.

Focused tests cover:

- Starting twice creates distinct new People sources, including with no initial
  LinkedIn tab; initial discovery and missing consent never open a tab.
- Existing-search/manual selection, filters, all three 15-page modes, observed
  profile links, owned-tab cleanup, suspension recovery and budgets are retained.
- Old/disconnected companions start no paid work; Stop during opening/detection
  preserves the prior list. Pending source URLs cannot grant authority off LinkedIn.
- A transient null read recovers without repeating plan; persistent absence stops
  after 30 reads with no screen request and performs run cleanup. Malformed data
  fails clearly. Actual injected-function exceptions produce fixed sign-in/reader
  guidance without exposing exception content.

The new fresh-source regression failed against merged v469 before implementation.
An independent replay of the merged v469 controller with a null read reproduced
the exact `Cannot read properties of null (reading 'empty')` error. The corrected
controller rejects the same input with useful reader guidance.

All **42 JavaScript suites passed**. Full isolated Windows Python regression:
**1,750 passed, four skipped, 8,392 subtests**, 143.90 seconds. Receipt, SQLite,
journal, salary and credential paths were isolated before collection. The final
additional ambiguous-search/next-page non-replay cases also passed.

Tracked Python/JavaScript/PowerShell/shell syntax, whitespace and repository
consistency checks passed. Windows owner-source native preflight verified
Antiword and Tesseract/English; **24 live source smoke assertions passed**.
No protected compilation or local native macOS test occurred.

Actual browser UI verification used an isolated Flask app, synthetic candidate,
simulated companion and mocked provider. The first run recovered from a null
search read and reached a complete profile result. A second Start created another
distinct simulated source and finished. The visible counter reached two fresh
sources; each run retained its normal three-call accounting (plan/screen/detail).
Screenshot and fixture remain ignored under `runtime/`. No real LinkedIn layout,
installed extension or paid DeepSeek call is implied. Existing installations need
the updated app and companion, refreshed/reconnected in Chrome before live use.

No owner records, credentials, installation receipt or installed app is changed.
No route/schema, extension permission, protected build or release artifact changes.
This task authorizes a local source checkpoint and preview; no PR/merge requested.
