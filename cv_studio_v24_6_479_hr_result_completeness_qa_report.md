# Historical — v24.6.479 HR result completeness

Current release identity is root `VERSION`. All three v478 exact-head CI checks
passed; automated re-review then found P2 comment 4355122607 in PR #238. A
100-person ceiling reached partway through the last LinkedIn page could save
complete=true and show no-further-results even though unique matches were omitted.

The controller now records an omitted unique canonical profile separately from
the source's hasNext flag. Both the saved complete field and the completion
message use that combined evidence. Exact 100-person final pages and duplicate
URLs after the cap remain complete when nothing unique was omitted. The existing
100-result/profile-lookup and page/time limits remain; no extra browser/provider
actions, route/schema/permission changes or owner-data/installation edits occur.
The v477 rich-content fallback and v478 unload/owned-tab cleanup remain included.

The new 120-result reproduction failed before the change (complete=true).
Afterward it saves 100 people with complete=false and a limited message; the
label survives closing, refreshing and reopening the ad. Exact-100 and
duplicate-after-cap cases remain complete with exactly 100 joining-date lookups.
An initial test needed to reopen the unchanged ad explicitly: Refresh alone
preserves the current accurate completion message for the same saved revision.

Full isolated Windows Python: **1,776 passed, four skipped, 8,392 subtests
passed** (127.47 seconds). All **46 JavaScript suites passed**, including HR
overflow/exact/duplicate limits, unload cleanup, rich fallback and existing
Jobs/Sourcer/folder/preview flows. Source/static/repository/owner-source
preflight and 24 source-smoke assertions passed with isolated state/receipts;
Windows Antiword was trusted/functional and Tesseract English was functional.
Exact-head CI/review and final merge evidence are retained in
PR #238 and coordination issue #35. No live installed-companion scan is claimed.
