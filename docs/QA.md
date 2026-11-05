# Current validation record

## v24.6.574 — Automated review corrections (includes v572/v573)

PR305's fresh review identified two regressions, reproduced by failing tests:
valid JobStreet split-view URLs / the Philippines host never reached detail
verification, and a rejected tabs.remove could falsely report successful cleanup.
Aliases now resolve to bounded detail reads, with ambiguous/non-ad URLs rejected.
A failed close retains the run and persisted ownership, prevents another search,
and can retry after worker suspension. A tab already removed manually is done.

Focused Python and worker regressions pass after correction. Final review and
Windows/macOS CI results are recorded against the PR's current head.

## v24.6.573 — Review corrections (includes v572)

Local review reproduced late Stop discarding a completed paid review response.
The client now retains output and usage once the paid request has started; Stop
before that point still prevents the review call. The client regression failed
before correction and passes afterwards. A guarded-route regression also checks
that all-rejected provider results retain the expiry/verification warning and do
not trigger an AI fallback.

## v24.6.572 — Lead Finder

JobStreet search snippets no longer establish the employer or availability. A
matching individual ad must supply the advertiser/title/body; explicit expiry
notices and validThrough deadlines exclude expired ads. Unknown or blocked ads
are omitted. No age-only expiry guesses. One selected-Tavily Extract batch can
supplement bounded public reads, using search-provider credits.

DeepSeek Find people first confirms selected employers, reads visible LinkedIn
search cards through the connected companion, then reviews only observed IDs.
Claude keeps its existing web-search request. The new companion search tabs join
CV Studio's group and close after success, errors, Stop or app removal/reload;
user-activated or navigated tabs are retained.

Validated with fictional responses and isolated state:

- Focused Python regressions for ad identity/employer/expiry, bounded transport,
  provider extraction, guarded routes, observed-only people and usage accounting.
- All 101 JavaScript fixtures, including grouping, cleanup, scope isolation,
  worker suspension, changed tabs and cancellation.
- Chromium UI workflows for DeepSeek plan/read/review, unchanged Claude request,
  Stop cleanup and suppression of the post-cancellation review call.
- Version consistency, repository consistency and protected-source checks.

No live API credentials, paid provider calls, installed-app update or signed-in
LinkedIn test was performed. Native extension loading is blocked by the browser's
administrator policy here. The current live availability of the user's two
JobStreet URLs remains unverified; fixtures exercise the reported Elitez/location
mix-up and explicit expiry rather than hardcoding either job ID in production.

The associated pull request contains fresh automated review and CI results.
Historical release reports remain available in Git history. Update this record
for current work instead of adding another version-specific root Markdown file.
