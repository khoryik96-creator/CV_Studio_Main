# CV Studio v24.6.472 — Per-ad saved-state correction

Historical QA record; root `VERSION` is authoritative.

PR #237 automatic review found one P1 on v471. Publishing a shared folder catalog
enabled every new card's menu without reading each card's saved status. An already
saved card could display Add and send the shared/default destination, which the
existing guarded duplicate handler would interpret as a requested folder move.

Every Add now performs its own bounded metadata read for the exact clicked URL,
independently of shared/coalesced catalog reads. A saved active ad updates the
control to Added and returns without any Add/move/remove write. A new ad continues
to the existing Add action with the destination chosen at the click. Unknown,
failed or timed-out state checks issue no write. The shared metadata timeout is
reused; late responses cannot resume a timed-out action. Existing explicit removal,
Trash restoration, confirmed worker writes, source identity, duplicate/revision
handling, route/schema and provider behavior remain unchanged.

The new actual-content-controller reproduction failed on v471: the second card,
whose menu came from another card's catalog, sent Add instead of fetching its own
metadata. It now makes only a folders read when the response identifies an existing
ad. The button becomes Added and shows the actual saved folder. A separate new
third card verifies metadata followed by Add using the chosen SAP folder. Existing
failure, empty-folder, shared refresh, creation, removal, timeout, source/destination
and cross-card status isolation tests remain.

All **42 JavaScript suites passed**. Full isolated Windows Python:
**1,750 passed, four skipped, 8,392 subtests**, 146.73 seconds. State and receipt
paths were isolated before collection. Final static/native preflight and PR CI
results are recorded in the coordination log before merge.

Actual browser verification uses real companion controls on two fictional cards
with a simulated connection. The second ad starts saved in Priority while its
card only knows the shared catalog. With SAP selected across the page, clicking
that card's Add produced Added / Already saved in Priority with zero Add writes
and its original Priority folder retained. Adding the genuinely new first ad
then used SAP. No real LinkedIn data, owner record, installed extension or paid
provider call was used. Fixture/screenshot remain ignored under runtime.

This corrective stays within the owner's authorized merge of PR #237. No owner
installation/receipt/credential change or protected package is produced. Both
the updated app and companion must be refreshed/reconnected for live use.
