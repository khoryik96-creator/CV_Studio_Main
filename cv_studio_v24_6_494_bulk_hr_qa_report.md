# v24.6.494 — selected-ad bulk HR scans

Branch: `codex/v24.6.494-bulk-hr-scans`, stacked on unmerged tested Email
Verifier v493 checkpoint `4ec0fd5`. Last merged base is v492 `15c9948`.
The owner requested bulk ad selection, shared preselected country/pages and
progress. This checkpoint includes the prior authorized v493 correction.

## Behavior

The existing saved-ad checkboxes expose shared HR controls and Scan selected
ads. Country/pages reuse the validated remembered HR preference. Any country
is supported, title keywords are optional settings, and pages are explicitly
per ad. Up to 40 ads can run at once, including selection across board pages.

The controller runs one ad at a time through the same scan function as the
individual action. It captures the shared settings and each selected ad's
revision once, retains exact company/profile authority, saves results through
existing `save_hr`, and awaits companion End before moving on. No new route,
schema, companion permission/action, paid call or persistent job was added.

Native progress counts processed ads and shows the current company/role and
page/joining stage. A status list distinguishes saved/limited results, per-ad
failures, stopped scans and ads not started. Previous successful saves remain
durable. Missing company/layout and stale-write errors preserve prior HR
evidence; connection, access, unconfirmed save or cleanup halt the remaining
queue. An ambiguous save requires refresh and is never replayed or described
as a definite no-write outcome.
Stop/pagehide prevent the next ad, while an already submitted atomic save is
accounted for if it completes. Reload never resumes scans. Unsaved ad-form
fields, original ad content and selection are retained.

## Verification

The new bulk fixture failed before implementation because selected ads had no
bulk action. It now exercises preset Malaysia/10, three distinct serial run IDs
and awaited cleanup, correct per-ad writes/progress, no cross-company preview
mixing, draft preservation, Stop during a read/save, independent per-ad failure,
stale writes, unconfirmed storage failures, missing companion, failed cleanup,
pagehide, validation, Trash
exclusion and the 40-ad cap across board pages. The existing single-ad HR,
joining, preference, job-search/folder and data-protection fixtures remain.

A headless native Chromium check used the real isolated app at port 5093,
fictional intercepted saved ads and simulated companion replies, with external
network blocked. It verified visible prefilled controls, one saved ad while
the second was in flight, the progress bar and status list, Stop retaining
the first save/draft and preventing a third scan, Any-country/3 persistence
across reload, and subsequent serial completion of all three ads. No browser
page errors occurred. Screenshots of settings, in-flight progress and final
progress were inspected. No real LinkedIn scan or owner-data write occurred.

The complete Python gate passed 1,867 tests, four skipped and 8,416 subtests.
All 56 JavaScript fixture files passed, including the single-ad HR/preference
and queue regressions. Tracked/new source syntax, repository consistency,
version identity, owner-source/native dependency preflight and the 24-assertion
source smoke passed. The v493 report retains its separate live SMTP
evidence; this bulk work makes no live provider/mailbox/outreach call. The
owner's installation, server, protected receipt and records remain untouched.

This is an unmerged source checkpoint. No PR, merge, protected compilation or
private release package is included.
