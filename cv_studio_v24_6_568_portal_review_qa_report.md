# CV Studio v24.6.568 — selected-portal review correction

Review of PR302 found one additional defect: source-first queries differed by
site restriction, but SerpAPI stripped those restrictions when converting them
to Google Jobs queries. Successful structured responses could therefore use the
whole source-coverage budget on repeated identical paid searches.

Site-constrained SerpAPI queries now use Google Search directly with the original
query. Each consumes one search request and keeps the selected portal constraint.
Unscoped queries retain structured Google Jobs and the existing organic fallback.
Tavily scheduling and the v567 source-balancing corrections are unchanged.

The new regression inspects actual outgoing engine/query parameters for three
selected portals, verifies three distinct constrained queries and exactly one
request each, and preserves existing structured/unscoped fallback checks.
All 99 focused Python/version checks pass. Tests use mocked responses and fictional
keys; no live Tavily, SerpAPI, AI or email actions. PR302 records current CI and
review status. Both this correction and the earlier v566/v567 work are unmerged.
