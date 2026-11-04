# CV Studio v24.6.569 — fresh review after PR302

The last merge reused the completed external review of its exact head commit;
it did not start another review when the user asked. A fresh pass now inspects
the merged v566–v568 code, its backend/browser URL rules, provider scheduling,
SerpAPI request constraints, response/cap processing and UI/snapshot behavior.

One reproducible regression was found: the new search-engine host exclusion
also rejected Google's own employer postings at its current careers application
path and older careers.google.com detail path. The new backend regressions fail
three times on merged568. Browser filtering also discarded these ads and offered
no Open job ad action.

The correction permits only known Google careers detail paths with numeric job
ids and optional ASCII slugs. Google web searches, career listings without a job
id, malformed ids, and invented Google /jobs/view paths remain excluded. Backend
and browser classify the same patterns. No search query or provider spend changes.

Checks cover backend acceptance/strict cleanup, browser response normalization,
Open job ad action, and continued listing/search rejection. The Chromium workflow
also renders a fictional Google careers card, preserving existing Tavily payload,
source-count and narrow-layout checks. Other findings from PR302 remain fixed.
Local validation: 107 focused Python/version checks, the Lead Finder JavaScript
regression, Chromium workflow, repository consistency and whitespace checks pass.
All test job ids and content are fictional; no live Google job availability,
provider/AI calls, credentials or email action. The corrective PR records current
external review, full CI and merge state.
