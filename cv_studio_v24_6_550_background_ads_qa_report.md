# CV Studio v24.6.550 — search scrolling and background job descriptions

Source work on `codex/job-search-results-scroll`, based on merged v24.6.549
(PR294), included with the v24.6.551 card refresh in
[PR295](https://github.com/khoryik96-creator/CV_Studio_Main/pull/295). See the PR
for current CI, review and merge status. Not installed on the owner's machine.

## Behavior

LinkedIn search displays matching ad summaries first. After the search ends,
the current companion loads full descriptions sequentially in the background.
Selection, pagination, preview and saving remain available. Full content and
rich formatting use the existing local formatter and review cache; existing
saved records, contacts, notes and editing drafts remain unchanged.

Progress and individual loading failures are visible. Stop cancels the exact
active operation; resume/retry skips completed descriptions. Clear, new search,
pagehide and foreground companion actions stop/drain the queue before conflicting
work. Cancelled results cannot replace the summary. Individual ad failures let
the queue continue; access restrictions and connection failures pause it.

The previous full-ad reader waited only 16 passive DOM polls after browser load,
and could return an empty description after six polls. It now waits up to 48
polls for both header and description, preserving URL, connection, access and
tab-ownership checks. The full-ad RPC budget is 55 seconds. Automatic background
capture requires `full_ad_background_revision:1`; updating only the app is
insufficient. Unknown layouts and genuine access failures can still prevent reads.

The results list also has the requested independent vertical scrollbar, bounded
to 70vh / 720px. Redraws preserve scroll position, expanded summaries and keyboard
focus; moving to another page starts at the top.

## Verification

- All 94 `tests/test_*.js` frontend fixtures pass. New fixtures exercise list-first
  capture, single active read, rich content, usable selection/saving, cached reads,
  saved-data preservation, individual timeout/retry, queue access-stop, exact
  cancellation and ignored late results, foreground priority and slow full-ad
  header/description readiness. Existing worker fixtures now supply a complete
  description and assert the longer bounded readiness contract.
- 234 focused Job Leads, folder/organization/HR/email, Graph/crypto, version and
  modular-monolith tests pass under isolated temporary application paths. Only
  existing dependency/datetime deprecation warnings appeared.
- Chromium against the fictional local fixture confirms a 25-ad search appears
  before full content; rich capture updates the preview while selection, focus,
  expanded content and scroll position survive. Stop and Clear preserve summaries
  and ignore late results. No page errors or external browser requests occurred.
  Reproduce with `tests/browser/job_leads_email_composer_server.py` and then
  `tests/browser/job_ads_background.py` (Playwright and Chromium required).
- Separate Chromium checks confirm bounded desktop/mobile list height, wheel and
  keyboard scrolling, stationary desktop preview/outer page, and no horizontal
  overflow. Screenshots are temporary local artifacts under `/tmp/cvstudio550`.
- JavaScript syntax, `git -c core.whitespace=cr-at-eol diff --check` and
  `python owner_build_tools/repo_consistency.py` pass.

Initial broad frontend verification found two old worker fixtures returning
header-only success; their fictional success data and readiness assertions were
updated for the deliberate full-description contract. The final complete run
passes all 94 fixtures.

No live authenticated LinkedIn DOM was available. This verifies the workflow and
readiness behavior using controlled responses, not the user's exact failing ad.
No live email, JobAdder, Apollo or AI provider action was performed. No routes,
schemas, permissions or paid-call boundaries changed.
