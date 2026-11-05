# Current validation record

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
