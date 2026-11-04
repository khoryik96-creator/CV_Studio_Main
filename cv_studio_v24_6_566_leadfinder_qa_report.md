# CV Studio v24.6.566 — Lead Finder clarity and job-ad links

The reported JobStreet title-listing result was reproducible: the earlier helper
kept a row with employer “Nov 2026”, role “Software Engineer (with Salaries)” and
a listing URL, then generated a Google verification search for it.

Lead Finder now requires a recognizable individual job-ad URL. Provider listing
results are skipped before the lead cap, final selected-source cleanup cannot
leave a generated Google link as a lead, and the browser filters indirect rows
in both fresh responses and saved snapshot reloads. Structured-result flags cannot
make Google search or listing pages qualify as ads. Existing valid individual
JobStreet/LinkedIn/company links remain. This classifies URL shape; it does not
verify live posting availability or completeness.

Queries target LinkedIn /jobs/view/ and JobStreet /job/ paths, using existing
query budgets. No new search/AI/extraction request or fallback spend was added.

The form removes static explanations and empty helper blocks, labels optional
fields, folds extra controls into More options and shows the saved search
provider beside Find job ads. Completion identifies the used search provider.
Result cards remove duplicate status chips and fold match evidence into details;
long search warnings remain available in Search details. AI cost choices remain
explicit. Lead Finder's lock, stored settings and routes are unchanged.

Verification: 99 JavaScript fixtures and 90 focused Python/version checks pass.
Repository consistency and JavaScript syntax/whitespace checks pass.
Chromium checks the form/options, saved Tavily configuration in the outgoing
request, direct-only cards and KPI, and the narrow layout. Flask route regression
uses a mocked Tavily response containing both a listing and a real-shaped ad,
requires the normal session/origin/feature gates, and asserts no extra AI call.
All ads, CVs, keys and responses used for checks are fictional; no live Tavily,
AI/provider call, email send or real credential access. The associated PR records
external CI and review status. Browser preview images are local fixture output.
