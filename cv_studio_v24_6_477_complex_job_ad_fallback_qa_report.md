# Historical — v24.6.477 complex job-ad fallback

Release identity comes from root `VERSION`. The owner authorized fixing all
review findings and merging the unmerged company-HR branch. The review found
one actionable regression: rich-markup complexity rejected a readable ad.

## Correction

The reproduction contains 2,001 ordinary inline spans and approximately 12 KB
of readable text, within the existing text/HTML limits. Both modern and legacy
companion readers threw before the fix. The new rich serializer's node counter
includes text nodes, reaching its structural ceiling before text capture.

Only that local rich-budget sentinel now activates a separate iterative plain
walk. It retains company, role and available date/location metadata; removes
optional markup; skips the same active, hidden and UI-control nodes; and avoids
recursive stack overflow. The fallback visits at most 16,000 nodes and retains
at most 20,000 characters. Unfinished traversal, over-limit text or a visible
More control marks an excerpt. Complete fallback text remains complete. Normal
rich captures still preserve headings, lists, computed emphasis and ARIA roles.
Other exceptions and existing identity/access/layout checks remain failures.

No route, schema, extension permission, provider call, outreach or owner record,
receipt or installation change is included. The existing HR scan and optional
company joining-date evidence remain unchanged. No protected package is built.

## Verification

The modern and legacy regression cases failed before implementation and pass
afterward. Coverage includes deep wrappers, retained metadata/dates, embedded
controls/active/hidden content, output/node caps and explicit excerpt markers.
Existing rich formatting, identity, loading and HR tests remain passing.

Full isolated Windows Python: **1,776 passed, four skipped, 8,392 subtests
passed** (146.61 seconds). All **46 JavaScript suites passed**, including the
new overflow cases; an additional targeted assertion confirms unexpected DOM
failures cannot enter the size-only fallback. Existing identity, loading,
rich-formatting, HR, folder, preview and lifecycle checks remain passing.

Source/static/repository/owner-source preflight passed; Windows Antiword was
trusted/functional and Tesseract English was functional. All 24 source-smoke
assertions passed with isolated state and receipts. Exact-head PR checks and automated
review gate the owner-authorized merge; final merge/CI evidence is recorded in
the PR and coordination issue #35. No installed-companion end-to-end scan is
claimed by the synthetic DOM fixtures.
