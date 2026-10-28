# v24.6.516 — Job Leads contact panel visibility

Baseline: merged v515 `2514d1a` / PR #263. The owner authorizes fixing and
merging the sole independent-review finding. The Contacts section has class
`card`, whose author `display:flex` rule wins over the browser's hidden style.
The v515 browser probe found `hidden=true` but computed `display:flex`, leaving
the contact card visible on Job ads and still showing loaded emails on return.

The fix adds only `#jobLeadsApolloContactsPanel[hidden]{display:none}`. Visible
Contacts retains the existing flex-card layout. No controller/backend/Apollo
Worker/account/record/storage/route/schema or paid-call behavior changes.
Version surfaces are generated from root VERSION with `bump_version.py`.

## Regression

`tests/browser/apollo_contacts_visibility.js` loads the actual panel markup,
stylesheet and Apollo controller in fresh Chromium pages. Network is blocked;
local synthetic fetches permit only status and contacts reads. No application,
credential, provider, server or live data is needed. Optional Playwright and
Chromium can be selected with `CVSTUDIO_PLAYWRIGHT` and
`PLAYWRIGHT_BROWSERS_PATH`; these are QA dependencies, not shipped dependencies.

The initial visibility assertion fails on v515 before the CSS change. With
the fix, actual rendered visibility and computed display pass on 1360px desktop
and 390px mobile: initial Job ads hides Contacts, selecting Contacts hides ads,
returning hides Contacts, reopening preserves the contact search, the unsaved
ad draft remains, and a fresh page starts on Job ads. No paid/account mutation
is permitted by the synthetic transport.

Local validation: **48 relevant Python/version tests** and all **75 standard
JavaScript fixture files** passed, along with the new native visibility suite.
The actual isolated app also passed synthetic unlock/archive, 45-row paging,
search, filtered real XLSX download, disconnect/reload retention and desktop/
mobile checks. The temporary synthetic server was stopped. Syntax/repository/
version validation, Windows Antiword/Tesseract dependency preflight and all
24 source-smoke assertions passed. One existing broker fixture exhausted its
short async polling loop during the initial parallel run; its immediate isolated
rerun and the complete confirmation run passed without source changes to that
fixture or broker. Required hosted full-regression results are recorded in
issue #35 before the authorized merge.

Owner installation/5000, its existing local Apollo test edit, credentials,
records and Cloudflare deployment are untouched. The independent v515 review's
live Apollo acceptance gap remains; this CSS correction spends no credits.
Held JobAdder PR #257 is excluded.
