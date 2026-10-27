# v24.6.492 — HR loading, preferences and native country filtering

Base: merged v491 `4f04818d8666831d2053e0f886726ba120fa6fe6`.
Branch: `codex/v24.6.492-hr-joining-preferences`. Unmerged source checkpoint.

The owner reported false HR joining-date search-change failures, requested
remembered Malaysia/10-page controls, and requested country selection through
LinkedIn Locations rather than Boolean keyword geography.

## Corrections

- HR source verification no longer treats same-identity loading as a filter
  change. All joining verification points wait; exact-owned cleanup is allowed
  while the unchanged search loads. Actual/pending identity changes still fail.
- Explicit HR country mode/name and page count persist in validated bounded
  browser storage, with an in-memory fallback when storage is blocked. Saved
  HR results retain their original country and provenance.
- The existing DeepSeek plan now returns a separate required country field
  (empty for no country). Its schema excludes all geography from role/skill
  keywords. Malformed country output or a country leaked into Boolean keywords
  fails visibly without a search. No extra provider call was added.
- Fresh normal People searches select the exact visible Locations suggestion,
  apply it, and confirm both the visible badge and a single observed geography
  value before reading profiles. State survives worker suspension; ambiguous
  mutations stop rather than replay. Source/filter changes stop evidence reads.
  Pagination waits before a click preserve its budget, and confirmed clicks are
  not repeated simply because the next page is loading.
- Existing-search review preserves manual filters. Automatic Recruiter country
  selection is deliberately unsupported and gives existing-search guidance.
  Older companion capabilities are detected before paid planning/HR scanning.

## Verification

All three new regression fixtures fail against the exact merged baseline for
the missing country action, false joining-date loading error, and absent
preference write, respectively. They pass on this branch. Focused Python tests
cover required/empty/invalid country output and the owner's original geographic
Boolean example. UI fixtures cover applying a planned country, preserving an
existing search, rejecting old companions before paid work, and Stop during
location selection preventing scoring. Worker fixtures cover arbitrary country
labels, same-filter loading, changed/pending filters, visible selection loss,
suspension, ambiguous actions and pagination loading/non-replay.

Native headless Chromium loaded the actual unpacked companion worker/reader in
a disposable profile. All LinkedIn pages were intercepted fictional fixtures,
with external network blocked by a dead proxy. Malaysia and Singapore were
selected through real DOM controls; the SAP query remained role/skill only and
all ten fixture profile cards were read. No hardcoded geography exists in the
production implementation. The fixture's synthetic geography is only test data.

The HR companion fixture completed three keyword groups/all 11 terms and six
result pages each for Any country and Malaysia; six exact-owned joining checks
returned Jun 2020 despite 12 injected same-source loading transitions. The
first navigation of each synthetic profile was deliberately held at blank and
then fulfilled locally to avoid a native popup's first request escaping
Playwright interception. No real LinkedIn account or user profile was accessed.

A separate actual-app browser check at an isolated local preview intercepted
fictional leads and simulated companion replies. Malaysia/10 persisted across
ads, reload and saved scan revision; a brief joining wait completed, and Any
country persisted. The rendered card showed the returned Jun 2020 date. No
owner lead/HR record, receipt or running main installation was modified.

Final gates: 1,854 Python tests passed, four skipped and 8,416 subtests passed.
All 55 JavaScript fixture files passed. Tracked/untracked Python and JavaScript,
shell and PowerShell syntax, repository consistency, version identity, complete
owner-source preflight and the 24-assertion source smoke passed. The actual
Windows Antiword and Tesseract functional preflights passed; no new native
package or cross-platform support claim is made.

No live DeepSeek call, outreach, protected compilation,
private release artifact, PR or merge is included. This does not certify every
live LinkedIn layout; an unrecognized control stops with recovery guidance.
