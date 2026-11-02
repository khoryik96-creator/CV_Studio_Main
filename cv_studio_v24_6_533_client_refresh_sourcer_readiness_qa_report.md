# v24.6.533 followed-client refresh and Sourcer readiness/UI corrections

2026-11-02, Asia/Kuala_Lumpur. Local unmerged checkpoint on
`codex/v24.6.533-followed-client-refresh`, based on merged532 / PR277 /
`3488805e0bf9c4e6af3a000ab9c8c7071c59249a`. PR257 stays held.

## Owner requests and implementation

- Refresh followed clients after adding LinkedIn in JobAdder. **Refresh from
  JobAdder** reads each existing followed company's `social.linkedin`, preserving
  selections, history and a manual fallback when the registered field is empty.
  Account and expected-link guards reject stale writes. Refresh cannot follow
  a removed company. Progress and Stop finish the current metadata read, then
  stop before the next. Per-company errors retain the old entry and are shown.
- Named company links previously left Pull disabled because no number was
  stored. They are now selectable. New companion action `jobCompanyID` opens
  one owned inactive company Jobs page and observes a unique numeric company
  filter from visible all-jobs/header employee links on that exact page. It
  does not guess from a name, inspect private APIs, or repurpose a user tab.
  Different IDs, changed URLs, access checks and bounded readiness failure
  stop that client with a manual See all jobs fallback. Numeric fast paths
  remain. Stop/account change/failure cancels the read; late replies cannot
  start searches. Resolved IDs are used only for that pull, not saved against
  possibly changed metadata. Owned-tab checks preserve active/navigated tabs.
- Opening Candidates has no sourcing Stop handler. The old generic read error
  could nevertheless abort the whole run during background detail loading.
  Empty exact-profile DOM is now readiness. Profile reads wait up to90 polls
  (500ms spacing, plus RPC time). An explicit profile readiness timeout or
  fixed profile-reader failure keeps the screen assessment, remains unchecked,
  and continues to later candidates. Only observed detail text enters detail
  AI requests. The final status reports unread profiles. Access, identity,
  country, transport/disconnection and AI errors still stop.
- Known removed-frame/destroyed-context errors are loading only for readSearch
  and readProfile observations, after exact-page/ownership checks. Mutating
  Search/Next/filter actions never gain retry behavior. No paid request is
  retried. Source/country changes still fail visibly.
- Candidate names turn purple on click/middle-click. Standard visited CSS has
  a tab-local fallback: at most2000 SHA-256 URL hashes in sessionStorage, no
  plain profile URLs or candidate records. Redraw and this tab's reload retain
  it; closing the tab does not promise durable visit tracking.
- New folder was missing `type="text"`, so it missed the existing input style.
  It now has a full-width field and separate aligned Create/Cancel row. No
  placeholders or extra descriptions were added.

## Verification

- Intended application suite: **2355 passed,4 skipped,8418 subtests passed**
  (`runtime/audit529/run_pytest.py -q tests`,232s), with isolated data paths.
- All **88 root JavaScript fixtures passed**. Focused client/worker/Sourcer
  fixtures passed again after final cancellation/type checks. Covers missing
  and newly registered links, stale edits/unfollow/account changes, retained
  ticks, per-client refresh failures and Stop, observed-ID validation, access/
  redirect/ownership cleanup, slow/failed profile details, later candidates,
  card-only retention, AI-call counts, observational frame transitions and
  non-replayed Next/Search actions.
- Independent POC bridge suite: **15 passed** in its own process. An initial
  root-wide collection combined it with the application and failed its
  `app not in sys.modules` isolation assertion; these are separate test targets,
  not a product failure. No test was weakened to hide that assertion.
- Actual native Windows Chrome with fictional, isolated service/provider/
  companion fixtures: followed company gets a registered link on refresh,
  named-page checkbox can be ticked before pasting a numeric fallback, reload
  restores choices, filters/status gates and mobile layout work. Sourcer runs
  complete while viewing Candidates; exact query/country/call counts remain.
  Opened-name purple color and reload persistence are asserted, with desktop/
  mobile folder geometry and no page errors. Screenshots inspected under
  ignored `runtime/signed-clients533` and `runtime/sourcer533`.
- Source smoke: **24 assertions**. Repository byte consistency, tracked source
  syntax, Windows-x64 Antiword1.3.5 trust/function, Tesseract5.5 English function,
  owner-source preflight and `git diff --check` pass. No protected build/package
  or genuine Mac test is claimed.

## PR278 pre-merge review correction

Automatic review found that a numeric-only manual fallback could survive import
of a newly registered named page, incorrectly bypassing page resolution. Refresh
now retains an old number only when no new page is supplied or the same page was
already associated with it. A newly imported page clears an unpaired old number.
Two regression cases cover both clearing that stale number and preserving a
numeric-only fallback when JobAdder still has no page. The former fails before
correction. After correction85 focused backend/version tests and the client
frontend fixture pass;the2355 full-suite result above precedes these two cases.
Hosted checks must pass on the corrected head before merge.

## Preserved boundaries and practical limits

124 production routes; existing SQL/vault schemas; protected credentials;
company/profile/account/session/tab authority; review consent and grounding;
paid/unsafe non-replay; previous ads/results/history all retain their contracts.
The new backend action uses the existing clients route and protected store.
No live JobAdder/LinkedIn/provider lookup, paid request, remote write, owner
installation/data/extension change or Apollo hosted deployment occurred.

The actual historical LinkedIn failure and the reported real company's DOM
were not captured/reproduced. Tests exercise confirmed code paths and synthetic
transitions, not a claim that LinkedIn can never change or block reads.
After eventual merge, update **both app and companion**; named-page resolution
checks its new capability and offers update guidance for an older companion.
This checkpoint is not pushed, merged or deployed.
