# CV Studio v24.6.486 — HR keyword searches

Repository-root `VERSION` is the release source of truth. This correction starts
from merged master `27f66e5` (v24.6.485) on
`codex/v24.6.486-hr-search-query`.

## Confirmed behavior and correction

The owner supplied a normal LinkedIn People search showing No results found for
the default eleven HR terms joined with OR under an exact current-company filter.
A bounded live Brave comparison reproduced it. The same company returned ten
visible cards for a simple HR query, a three-term query and a five-term query.
Replaying the exact eleven-term query in the diagnostic tab returned zero again.
The company remained checked and its ID unchanged. The temporary tab was closed;
the owner's original search/app tabs were retained. No profile was opened,
contacted or saved, and no private profile content enters these fixtures.

New searches use up to five distinct quoted terms at a time. Empty/duplicate
terms do not inflate query length; remaining terms are retained. The reader still
matches the full original keyword list on observed titles. Five is a conservative
tested group size, not a documented universal maximum for all LinkedIn accounts.
Official guidance describes Boolean syntax and suggests fewer Boolean operators
for unexpectedly low Recruiter results; the actual normal-People diagnosis rests
on the live comparison, not an inference that Recruiter has the same limits:
[Boolean search](https://www.linkedin.com/help/linkedin/answer/a524335) and
[Recruiter search FAQ](https://www.linkedin.com/help/linkedin/answer/a415399/search-in-linkedin-recruiter-and-recruiter-lite-faqs?lang=en).

The worker retains the same run, source tab, company ID, exact country/geo filter,
page/profile ceilings and original ten-minute start time across query transitions.
It validates current filters and observed page signatures before moving. Each
query change is persisted as interrupted before navigation; suspension/failure
cannot replay it. The prior exact query may wait during a requested navigation,
but cannot provide new results. Signatures include the keyword-group identity
when necessary so identical people in different searches do not stall the UI.
Empty intermediate groups are nonterminal. The controller merges unique profile
links across all reviewed pages and looks up each joining date only once.

Completion is conservative: unreviewed groups/pages and shared-limit stops remain
limited. Saved records retain the full original keyword list and final confirmed
source URL through the existing validator/backup format. The UI checks the new
companion capability before starting rather than silently using old query logic.
The page budget reserves first pages for remaining groups when possible; skipped
native pages persist a limited flag even if the final group is empty/exhausted.
The added busy-first-query regression failed before this reservation was added.

## Validation

The new worker test failed against v485: its default query contained eleven terms
instead of at most five. Tests cover complete term coverage, countries, all-empty
progression, duplicate signatures, delayed query commits, stale/filter changes,
shared budgets, restored query validation, timeout and navigation non-replay.
The query source is rechecked after its persistent checkpoint: a takeover blocks
navigation, and same-query loading restores a proven unexecuted change/budget.
UI tests cover an empty first group, duplicate results in later groups, one saved
union, one joining-date lookup per person, limited coverage and outdated companion.

Actual isolated Chromium uses the production companion/reader with synthetic
offline LinkedIn HTML. Test-only pairing uses a simulated toolbar callback; a
pre-created controlled HR source is returned for tab creation. Subsequent native
tab navigation and DOM actions remain real. A fixture models the observed long
query failure. The v485 baseline reproduces an empty search with its oversized
query; corrected code checks all eleven terms in three groups and six native
result pages, both worldwide and Malaysia. Asserted stale-metadata fault hooks
also retain the v485 navigation correction. Outbound networking is blocked by a
dead proxy. This validates transitions/controls, not a completed live owner scan
or a guarantee that LinkedIn will return any particular person.

Final-code validation passed: **1,779 Python tests, four skipped, 8,392 subtests**
(231.92s), all **48 JavaScript suites**, repository/tracked-language validation,
owner-source preflight and **24 source-smoke assertions**. Native Windows
preflight verified trusted functional Antiword 1.3.5 and Tesseract 5.5 English.
No protected compilation was run. Git whitespace validation passed.

## Preserved boundaries and delivery

All 120 sealed routes, five guards, 80 MiB limit, main SQLite schema 10, journal
schema 1, Job Leads schema 2, extension permissions, pairing, owned-profile
cleanup and paid-call non-replay remain. No new provider request, outreach,
credential migration, protected compilation or native Mac application test is
claimed. No owner installation, receipt, profile or saved-lead edits were made.
The request authorizes the fix; a new PR/merge awaits a separate owner request.

Ignored evidence: `runtime/hr486_baseline_native.log`, `runtime/hr486_native.log`,
`runtime/companion486_hr_browser.js`, `runtime/pytest_486_guard_final.log`,
`runtime/js486_guard_*.log`, `runtime/preflight_486_guard.log`. Earlier full runs
and the failing busy-group/takeover regressions informed the final correction;
the results above refer to the code after all corrections.
