# CV Studio v24.6.464 — Sourcer tab compatibility correction

Historical QA record; root `VERSION` remains the release reference.

PR #234's automatic review identified one P2 compatibility gap in v463: the
companion supports Chrome 116 onward, but `Tab.lastAccessed` is documented as
Chrome 121+ in the [official Tabs API reference](https://developer.chrome.com/docs/extensions/reference/api/tabs#type-Tab).
Without that field, all tabs received zero recency and source selection followed
query order, potentially selecting an older search.

The companion now includes the existing active-tab flag. The controller uses it
as a tie-breaker when recency is missing/equal. Manual source choices remain
authoritative, newer recency timestamps still take priority, and a remaining tie
keeps stable browser order. The chosen source is visibly identified as before.
This adds no permission, persistence, route, schema or external operation and
retains Chrome 116 support. All original v463 source/ZIP/QA artifacts stay intact.

New controller and real-worker VM assertions failed before the correction, then
passed. Coverage checks unavailable timestamps, an active second search defeating
query order, modern recency remaining authoritative and existing manual-source
retention. All **42 JavaScript suites passed**. Full isolated Windows Python:
**1,737 passed, four skipped, 7,599 subtests passed**, 178.69 seconds. Source
syntax, repository consistency, whitespace and owner-source native-dependency
preflight passed, including bundled Windows Antiword and Tesseract/English
functional checks. All **24 source smoke assertions passed**. No protected
compilation or native Mac testing was performed locally.

The v463 simpler flow and bounded same-profile slash fix are retained. Its
sample-data browser verification remains applicable; no visual/control layout
changed here. No live installed-Chrome 116–120 test, paid call, LinkedIn write or
owner installation/records/receipt mutation is claimed.

Four-file companion ZIP v24.6.464 is byte-verified against current source:
`48166f98559cfdb514538992e7ff26225a750033f70a9bb51be5676e38f9ceb1`.
