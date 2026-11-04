# CV Studio v24.6.567 — selected-portal coverage

Extends the unmerged v566 work in PR302. The former scheduler silently sliced
selected sources to four, spent title/region variations on the first source,
and could stop collecting at the result threshold before later sources ran.
The extractor also capped the first source's ads before location/filter checks.
A six-source Quick query example confirmed that Hiredly and Indeed were absent
from the former request list.

The scheduler now gives every selected UI portal its initial primary-role query
before variations. Quick/Standard reserve a query per selected source, capped at
12 total queries. This can use more credits than their former 5/8-query limits.
The collector completes initial source coverage before its result threshold can
stop further work. With more than five sources, at most three initial requests
run concurrently, while results and warnings are consumed in query order.
Individual transport timeouts and no automatic retries/AI fallback remain.

The extractor filters all candidates before taking one ad per source in rounds
up to the existing lead cap. A selected source may still have no qualifying ad;
this does not invent results or verify live availability. Other Portals can admit
unknown job/career pages, matching the existing documented selection contract.
The summary shows per-source qualifying counts, allocating overlapping company
career/Other categories once.

Regressions cover six sources despite four title angles/two regions, Quick-mode
coverage after exceeding the old results threshold, all 11 UI sources, the hard
query ceiling, at most three concurrent coverage requests at every depth,
JobStreet-heavy results with five other qualifying sources, location filtering
before capping, and source-count overlap. Existing direct-ad-only and snapshot
checks remain. Chromium checks source counts, including a zero, alongside the
saved Tavily request payload and direct-only result cards.

Local validation: 98 focused Python/version checks, the Lead Finder JavaScript
regression, Chromium workflow and repository consistency pass.
Checks use fictional provider responses and keys; no live Tavily, SerpAPI, AI,
email or credential actions. See PR302 for current CI and review state.
