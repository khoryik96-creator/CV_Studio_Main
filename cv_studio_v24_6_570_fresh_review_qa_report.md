# CV Studio v24.6.570 — fresh Lead Finder review findings

A new review after the user challenged the merge's review timing inspected the
merged PR302 code. The preceding merge reused an existing completed review of
its exact head; it did not start another review on that request.

Two reproducible defects were found and corrected:

1. The search-engine host exclusion also rejected Google's own employer job ads.
   Three regressions failed on merged568. Admit only its known careers detail
   paths with numeric posting IDs; retain search/listing/malformed-ID rejection.
   Backend, browser normalization and Open job ad behavior match (v569).
2. Provider extraction capped source-balanced results before final canonical URL
   deduplication. A direct LinkedIn URL and its collection alias could count twice,
   collapse to one card later, and displace another unique job. The regression
   reproduces a three-ad cap yielding two cards despite a third unique ad being
   available. Normalize/deduplicate before balancing, capping and counting.

The new acceptance and alias-cap regressions failed before their corrections.
Focused Python checks cover the real extractor/final-cleanup sequence and both
accepted and rejected Google URL shapes. JavaScript and Chromium cover Google
cards/actions and continued search/listing rejection. Existing provider-coverage,
request-budget/concurrency, source-count, saved-snapshot, Tavily-payload and
responsive UI checks remain. Current external review, full CI and merge state
are recorded in PR303.

Local checks: 108 focused Python/version cases, the Lead Finder JavaScript
regression, Chromium Google-card/workflow checks, repository consistency and
whitespace checks pass.

All provider keys, job IDs and content in checks are fictional. No live provider,
AI or email actions, installed update, or verification of live Google job availability.
