# Historical — v24.6.478 HR unload cleanup

Current release identity is root `VERSION`. The owner resumed fix-all-and-merge
for PR #238 after all three v477 CI checks passed. Automated review identified
one outstanding P2: HR profile tabs could be orphaned when the app unloaded
before the controller's finally block sent End.

## Correction and safety

The pagehide handler now stops HR as well as Jobs discovery and sends End for
each exact active run. A late response cannot reach save_hr. Because unload
messages are best-effort, the worker also cleans HR-owned tabs when the app
document navigates, its tab is removed, or exact-document session restoration
fails. Cleanup does not resume scans or external/provider operations.

The existing close helper accepts an exact matching expected pending load as
well as the committed profile URL, retaining inactive/ownership and pending-URL
checks. This covers initially uncommitted profile tabs and a tab created after
the app already disappeared. Active/taken-over, redirected and differently
pending tabs remain untouched; the company search is retained for the user.
Other run families retain their established disconnect policy.

No route, schema, extension permission, paid call, outreach, owner records,
installed receipt or application installation is changed. No protected package
or live installed-companion cleanup run is claimed.

## Regression evidence

The new frontend pagehide assertion failed on v477. Worker tests replayed against
v477 failed at navigate/owned cleanup. Both pass after the correction. The
worker matrix covers navigation, removal, failed missing-app restoration and
replaced-document restoration against unchanged, pending, taken-over,
redirected and differently pending profiles. A deferred-create test covers app
navigation while Chrome is still returning the newly opened tab. Source tabs,
user ownership and persisted authority are checked. Existing Sourcer, Jobs,
folder, HR and formatting suites remain required.

Full isolated Windows Python: **1,776 passed, four skipped, 8,392 subtests
passed** (143.96 seconds). All **46 JavaScript suites passed** after the final
deferred-create fixture was added. Source/static/repository/owner-source
preflight and all 24 source-smoke assertions passed with isolated state/receipts.
Windows Antiword was trusted/functional and Tesseract English was functional.
Exact-head CI/re-review are required before the owner-authorized merge. PR #238 and
coordination issue #35 retain the final CI/review/merge evidence.
