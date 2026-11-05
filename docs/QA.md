# Current validation record

## v24.6.580 — Visible HR profile links

Per-ad HR cards and saved HR dashboard rows expose an explicit LinkedIn profile
link in addition to their clickable names. Captured profile URLs open in a new
tab with noopener/noreferrer; existing records need no new retrieval or unlock.
Existing URL validation remains in place. No backend/schema changes are needed.

Targeted HR and candidate fixtures pass, including exact target/rel/URL checks.
Chromium checks both saved HR surfaces, correct new-tab navigation and mobile
visibility with fictional data and external pages mocked. No live profile read,
unlock or installed update. The PR records fresh review and full CI results.

## v24.6.579 — Nested CV tables and JobAdder record links

The reported DOCX nests 34 tables inside one layout table. The previous real
upload route extracted 1,057 characters; the corrected route returns 10,897 with
100% distinct source-word coverage, including the name and missing sections.
This lexical check alone does not prove ownership/order. Synthetic tests verify
local date textboxes, merged-cell deduplication and source section order through
shared extraction and the real upload route. A simulated provider parse then
passes through real Word generation with name, employer, role, duties, education
and skills retained. Existing summary/label-table/long-CV regressions and source
guardrails pass. The private sample is not committed; its regenerated artifact
retains 9 work entries, 68 duty statements, 7 skills groups and qualifications.

Unlocked contact links come from confirmed protected history keyed by current
JobAdder account and email. Tests cover local-only status projection, fresh
service/dashboard reload, immediate successful creation, old-refresh races,
account transitions, unsafe links and a history-read failure preserving contacts
with a warning. Confirmed links use matching contact IDs and open in a new tab.
Pending/uncertain creates retain existing recovery and non-replay boundaries.

All 104 JavaScript fixtures pass. A pre-existing broker concurrency fixture's
fixed event-loop spin failed intermittently before the controlled WebCrypto
operation reached its fake provider; the fixture now awaits an explicit bounded
readiness signal. No broker production behavior changed.

No live AI/JobAdder call or installed-app update was performed. Private DOCX/PDF
layout inspection uses LibreOffice here, not native Windows Word. The PR records
fresh review and full Windows/macOS CI for the final head. Re-upload the original
CV after updating so the browser does not reuse its old incomplete extraction.

## v24.6.578 — Saved Job Ads selection buttons

Select all includes active ads matching current filters across every saved-ad
page. Unselect all clears the selection. Buttons sit beside the table's page
controls and respect busy state; the per-page checkbox remains available.

Existing pagination regressions exercise 82-ad cross-page selection, per-page
checkbox synchronization, clearing selection/HR controls, filter scope, empty
results, Trash exclusion and absence of API writes or record changes. Targeted
search/pagination fixtures and version checks pass. The PR records fresh review
and complete Windows/macOS CI. No live data or installed-app update is involved.

## v24.6.577 — LinkedIn company hyperlinks

Company URLs are captured from the actual search card, full ad, matching public
employer header or JobPosting organization. Saved company names open validated
LinkedIn company roots in a new tab. Older rows can reuse matching HR evidence;
rows with no known page retain plain names instead of guessed slugs/search links.
This adds no crawl or paid request. Normal tab grouping still applies.

Focused tests cover canonicalization, hostile URLs, ambiguous metadata, public
header/recommendation scope, persistence/reopen/backup/restore, same-employer edits,
stale-link removal, and search/full/manual/direct capture paths. Browser checks
use isolated fictional responses and block external requests. The PR records
fresh review and full Windows/macOS CI against its final head. No live employer
page verification or installed-app update is claimed.

## v24.6.576 — Numbered Job Leads pages

Numbered result pages sit directly below the scrollable card list, with a
visible ad range. Saved ads also have numbered pages. Large counts use bounded
ellipsis controls. Node regressions cover jumping from page 1 to page 4 of 75
ads, preview synchronization, selection retention, no repeated crawl/tab actions,
saved-ad page counts and resetting/clamping after filters. Chromium checks actual
layout at desktop and 390px widths, current-page accessibility, keyboard focus,
selection retention and no extra background read on page changes.

The full Windows run exposed a stale protected-asset inventory and a silent
extraction exception. The inventory now includes lead-people.js. Failed Extract
requests expose a safe warning without provider details or automatic replay;
a regression checks both visibility and redaction. These checks pass locally.

All browser data is fictional and uses the isolated local fixture. Screenshots
are temporary test output, not another per-version root documentation file.
PR305 records fresh review and CI for the final head, including earlier fixes.

## v24.6.575 — Cross-run people selection correction

Follow-up review found new DeepSeek responses reused sequential person IDs
across runs. A failing regression reproduced distinct profiles receiving the
same selection ID. IDs now derive from canonical observed profile URLs; the test
checks both distinct people across runs and stable IDs for repeat observations.
This preserves independent selection before email enrichment. PR305 contains
review/CI status for the final head, including the earlier corrections below.

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
