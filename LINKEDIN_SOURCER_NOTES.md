# LinkedIn Sourcer module

## Assessment output limits and failure guidance (v24.6.508)

The review request now declares the same bounds as the existing validator:
integer score 0–100; 1–4 exact supporting quotes; 0–6 unknown requirements;
each text item at most 250 characters. Shared constants drive schema and
validator text/list limits. Each request also supplies its existing stage's
candidate maximum without mutating the shared schema. No supporting quote
means omit the candidate, never manufacture evidence or pad an empty field.
Grounding, observed IDs, duplicate detection and strict score/text checks stay.

Previously the schema omitted these bounds, so provider output could match the
requested shape yet fail local assessment validation. Such failures now use
`AI_PROVIDER_RESPONSE_INVALID` / `review_sourcer_results`, separate from key
authentication. The central transport keeps the request ID and explains that
results already found remain and no AI request was automatically retried.
Real key/authentication guidance remains unchanged. The five already screened
results in the reported screenshot therefore need no credential replacement
based on this response-validation error alone.

There is no truncation of unknown requirements, quote rewriting, acceptance of
unverified claims, automatic paid retry, continuation after a failed assessment
or added provider call. Failed detail checks retain prior search-card evidence
without falsely marking it as profile-detail checked. Existing accounting,
request ceilings, Stop/cleanup, browser authority and storage contracts remain.
Raw provider/profile data is not logged; the supplied request ID was absent from
the existing redacted runtime log, so no exact rejected field is claimed.

## Conservative normal-search Boolean budget (v24.6.504)

LinkedIn documents a consumer Boolean-operator limit without stating its
numeric size: https://www.linkedin.com/help/linkedin/answer/a524411/boolean-query-limitations.
On the owner's account, the reported seven-alias SAP query returned no results;
the four-alias query returned ten visible cards before and after that check,
with the same native Malaysia geography filter.

New standard searches therefore request at most three AND/OR/NOT operators
outside quoted phrases. The original exact core role/skill comes first; full
criteria remain in requirements for assessment. A deterministic validator can
narrow only an overlong flat positive OR list to four aliases, deduplicating
exact case-insensitive alternatives. Country and requirements are copied
unchanged. Quoted operator words/parentheses remain literal. Empty/invalid
aliases, nested logic, AND and NOT in an overbudget plan fail with guidance to
use fewer alternatives or Recruiter, without silently losing constraints.
This is a conservative product budget, not a claimed universal LinkedIn limit.

Recruiter/Lite and review-existing-filtered-search mode retain the original
schema/validator. The existing start request's use_open_search boolean is kept
in the in-memory Run only; summaries, persistence, routes and paid boundaries
are unchanged. No new provider call, automatic retry or paid replay. Older
companions that already support v502 cards/country work with this correction.
An empty first page says no matches; only a later empty page says no more results.

## Modern People cards and pagination (v24.6.502)

Live cards now contain mutual connections' profile links, which made the old
whole-card single-profile check discard otherwise valid candidates. Standard
People search uses only a primary-results list item's first name paragraph to
bind the candidate, requires a visible following paragraph, rejects nested or
ambiguous primary cards and excludes foreign-profile paragraphs from evidence.
Visible additional career paragraphs remain; missing location stays unknown.
The legacy path remains for
older layouts and Recruiter, but standard modern results cannot read sidebar
recommendations. The 40-card/page and existing profile/paid budgets remain.

Native Next detection is scoped to one visible primary-results pagination list
with one current-page indicator and one Next button. Signatures and existing
worker query/country guards still precede a click; disabled Next means last
page. Ambiguous next-page actions are never replayed. `people_results_revision:1`
is required before any standard-search paid request, alongside the existing
Locations capability for new searches. Update companion and refresh both tabs.

Release identity comes from root `VERSION`; stamp changes with `bump_version.py`.
This experimental CV Studio module replaces the separate POC workflow for normal
use. The historical POC remains under `poc/linkedin-sourcer` as an isolated
reference, and is not imported by the main app.

## User workflow

1. Open **LinkedIn Sourcer** in CV Studio.
2. In the normal installed CV Studio address, expand **Set up companion / updates**
   and **Copy setup folder**. Remove any old downloaded companion, then use
   Chrome/Brave's **Load unpacked** with that bundled folder. Keep Developer mode
   on. The ZIP remains available for installations requiring manual file updates.
3. Refresh CV Studio, then click the companion toolbar icon once to trust this
   installation/address. The enabled companion then connects automatically to its verified document
   on load, return to the tab, and before browser RPCs. Page refresh/browser
   restart needs no toolbar click. Worker suspension retains an exact live
   document's binding and limits. A replacement document gets no previous run
   authority; active worker runs/captures cannot be stolen by another app tab,
   and a background tab cannot replace an idle binding. The toolbar remains an
   explicit manual connection/recovery option. Search, write and DeepSeek consent
   gates remain explicit. No additional API key, pairing code or POC server is
   needed. A new installation/address or changed identity needs another toolbar
   pairing. Fresh origin-bound HMAC challenges authenticate reconnects against
   the paired backend key; DOM markers alone cannot grant authority. The backend
   root key uses the existing protected vault; only a derived installation/origin
   key enters extension-local storage, restricted to trusted extension contexts.
   Keys never enter page messages, session snapshots, SQLite or diagnostics.
   After normal **Update & Restart**, **Apply companion update** reloads
   matching files already updated in the bundled folder. It reads only its own
   local manifest, refuses active work, and never downloads or evaluates remote
   code. Refresh CV Studio and LinkedIn when ready; drafts are not forcibly
   reloaded. Legacy downloaded copies receive one-time setup guidance. Setup
   must use the normal installation's folder, rather than a development preview.
4. By default, **Start search opens a fresh LinkedIn People search every time**,
   then uses role/skill keywords from the brief. A requested country is returned
   separately by the existing planning call and selected through LinkedIn's
   native **Locations** menu (open, type, exact suggestion, Show results).
   Countries, cities and regional aliases are excluded from the keyword query;
   a plan that still puts its country in the query is rejected visibly.
   The worker confirms the visible selected country and a single observed
   geography filter before reading profiles. It never invents a geography ID,
   calls LinkedIn's private APIs or falls back to geographic keywords.
   No LinkedIn tab needs to be
   opened first. The source stays open for the user and existing tabs are kept.
   To review a filtered search or use Recruiter, expand **Search options** and
   select the search type / **Use the search already open**. In that mode the
   module detects the source and search type automatically; it preserves an existing selection
   or chooses the most recently used compatible search when that metadata exists.
   When recency is missing/tied, an active compatible tab takes priority; a
   remaining tie keeps browser order. Manual selection stays authoritative.
   A status line identifies
   the chosen tab. With existing-search review selected, filters are kept; the brief ranks
   these results and does not change their location filters.
5. Enter the brief, tick **Use DeepSeek for this search**, then **Start search**.
   **Search options** retains manual source/type selection, new-keyword search,
   1–15 pages and the 1–80 request ceiling. The default remains 10 pages / 35
   requests, displayed beside the explicit balance/data-sharing permission.
6. Review exact supporting quotes, missing requirements, source provenance and
   links. Export CSV or Clear when finished. Candidate results stay in browser
   session storage, not durable CV Studio records or diagnostic logs.

Recruiter keyword entry uses a recognized visible field/button. If its layout
is unrecognized, use the generated query manually and select Review open search.
Only observed public URLs are shown; otherwise the Recruiter profile URL remains
labelled as requiring login. Collapsed/unloaded content stays unknown. LinkedIn
restrictions and layout changes stop the run rather than triggering a bypass.
There are no contact, message, project-save, profile-edit or JobAdder actions.

v492's automatic country selection is for fresh normal People searches.
Recruiter searches requesting a country stop with guidance to set Locations
there and review the existing search. Existing-search mode always keeps its
filters. Reload the v492 companion and refresh CV Studio/LinkedIn after updating;
an older companion is rejected before the paid planning call for a new normal
search. Country selection retains exact source/run authority across worker
suspension, stages mutations before invocation, and never repeats an ambiguous
click. Same-filter loading waits cannot consume a pagination click or replay
one already confirmed. Candidate scoring remains behind the existing consent
and request limit, after successful filter confirmation.

## Ownership and boundaries

The v24.6.481 connection correction retries a rejected document-idle handshake
when Chrome reports tab completion. Only the current local top-level content
script receives the readiness notification; it waits for any old in-flight
attempt to settle before a fresh verified connection. No browser action is
queued/replayed by readiness recovery. The document's own load event is an
independent fallback if Chrome omits/delays its completion notification. Only
verified same-URL loading hints can schedule up to 20 handshake-only retries
250 ms apart; pagehide cancels them. Sourcing reserves the existing bounded
worker run before the paid planning request, protecting background planning
from another app tab's automatic connection. Failed/cancelled reservation sends
no plan request; subsequent browser operations reuse the same run and budgets.

- `cvstudio_linkedin_sourcer.py`: app-independent ephemeral run state, bounded
  attempts/time/pages, validated observed URLs, exact quote checks and native
  tool-output validation. A stopped/in-flight run cannot be replaced silently.
- `app.py`: one GET/POST `/linkedin-sourcer` endpoint; protected key resolution,
  central cost guard and `AIProviderClient` call, normalized usage/billing fields,
  structured errors and an explicit four-file companion ZIP. All five existing
  guards apply unchanged. The new POST path is in `_AI_SPEND_EXACT_PATHS`.
- `vendor/cvstudio/linkedin-sourcer*.js`: controller, in-app UI, browser-message
  correlation, existing usage-history integration, session results and CSV safety.
  Stop aborts subsequent controller/browser actions, but lets a sent AI response
  return for cost accounting. Closing the page does not resume work later.
- `vendor/linkedin-companion`: narrow Chrome browser adapter. Toolbar arming binds
  app tab and document IDs; browser commands require that sender and an active
  run. Profile links must have been observed on the chosen source page. Other
  tabs, unobserved links and actions outside the allowlist are rejected. Repeated
  Begin cannot reset the page budget. Only inactive, unchanged, extension-owned
  profile tabs are closed. No provider calls, AI keys, cookie access or HTTP
  exception to the main app guards exists in the companion.
- Worker state uses the extension's `storage.session` memory, with the storage
  permission and existing host allowlist. It retains only binding/run authority,
  bounded observed URLs, counters and owned-tab identities; no keys, captured
  profile content or provider requests. It is not local/sync/disk persistence,
  and is not exposed to content scripts. Recovery validates the original live
  document ID and never replays browser or paid actions. Storage failures stop
  commands visibly. Clicking the toolbar again on the same live document cannot
  reset an active run's budgets.
- Activating or navigating a profile tab relinquishes extension ownership.
  Every profile read/navigation checks ownership and current/pending URLs, with
  another check after script injection. Normal extension-commanded navigation
  (old committed URL, expected pending URL, loading) retains ownership and the
  existing loading-poll behavior, including across suspension. Cleanup preserves
  user-taken-over tabs. Interrupted temporary job tabs receive the same bounded
  ownership tracking and conservative cleanup.

The sealed 119-route hash is
`da29d6476a2dc929fc3b4f06faae8bdffc7ce69261f58901b90de46d0b857e31`.
Excluding the new endpoint must retain the previous 118-route digest; its dedicated
regression proves this. SQLite stays schema 10 and the job journal stays schema 1.
The companion manifest is stamped from `VERSION` using the bare-version anchor.
Keep the service, frontend and four companion assets in architecture/build
inventories when changing them. No protected package has been produced here.

## Verification limits

Job Leads also uses this companion for bounded Jobs search discovery beginning
with v24.6.455; see `JOB_LEADS_NOTES.md`. Jobs runs are isolated from profile
runs and single-ad reads. The source search is retained for the user, and only
recognized results scrolling/pagination is allowed. Existing profile-run
authority, ownership and cleanup rules remain. The four-file ZIP and permissions
are unchanged; existing installations need the updated files, Reload and a
reconnected app tab before using the new Jobs actions.

Since v459 its reader/content scripts also supply explicit direct-add buttons
on recognized LinkedIn Jobs cards/pages. This uses the existing LinkedIn host
permission and same four packaged assets. Only trusted clicks send a job-only
capture to the exact connected CV Studio document for its ordinary guarded
local save. It adds no profile buttons, provider calls, LinkedIn writes or
ownership/cleanup changes. Active profile/Jobs runs block direct captures.
See Job Leads notes for the bounded initial search-location handshake and
preview/direct-capture test coverage. Updating needs both app and LinkedIn
pages refreshed after the companion files are replaced/reloaded.

The v461 direct controls also select/create local folders and reversibly remove
saved ads through the bound app's existing guarded actions. New local-page
capability checks prevent old pages interpreting these commands as adds. Cards
mount controls in an existing text column; native layout/styles and profile
actions remain unchanged. Folder operations/removal require both updated app and
companion, refreshed pages and reconnection. See Job Leads notes for restore,
partial-failure and editing-draft behavior.

The startup checks the companion and selected/new source before starting paid
work. Missing/disconnected sources in reuse mode and rejected starts keep the previous list.
Stop during detection cannot start a paid request. Automatic discovery runs on
panel initialization and Start, while manual selections remain available.
No paid confirmation, provider retry or exact-document gate is removed.

In v470 fresh People search is the default, as requested by the owner. The narrow
`openPeopleSearch` companion action accepts no destination URL, requires the exact
bound app document and blocks concurrent browser work. It opens an inactive source
tab, keeps it out of profile ownership/cleanup, and handles an initially uncommitted
People URL as loading. Stop during opening prevents the first provider request.
Old companions show explicit update/reconnect guidance before paid work starts.

The v470 reader boundary also handles missing script results: search/profile reads
receive bounded read-only polling; search submissions and pagination clicks are
never replayed after a missing result. Script exceptions return a fixed reason so
sign-in/restriction errors stop with useful guidance, without returning arbitrary
page text. Malformed search snapshots cannot reach `snapshot.empty` or paid review.
This corrects the null/empty crash shown by the owner; the screenshot alone does
not identify which page/transport event caused the original missing result. No
provider retry, consent bypass, route/schema or extension-permission change occurs.

Profile-tab ownership in v463 accepts a single added trailing slash on the exact
observed profile URL. The old byte comparison rejected that same-identity change;
its regression failed before the correction. Query/hash changes, another profile,
user activation and mismatched pending navigations still relinquish ownership.
Checks before/after script injection, suspension recovery, cleanup and page/profile
budgets remain. This reproduces a possible browser-action failure, not proof of the
precise failure shown in the owner's screenshot, which had already screened cards.

`tests/test_linkedin_sourcer.py` exercises the service, real guarded route,
download, provider/cost wiring and cancellation with mocked transport.
`tests/test_linkedin_sourcer_frontend.js` exercises companion authority and all
three 15-page controller modes with synthetic browser state. Native Chrome
exercised the actual app UI with a simulated companion and provider. Live
LinkedIn layouts, real extension installation and a paid DeepSeek call still
require an owner-driven check. They are not implied by those automated results.
`tests/test_linkedin_companion_lifecycle.js` also runs fresh-worker VMs sharing
synthetic session storage, covering revalidation, limits, takeover, storage
failure, loading transitions and cleanup. These are not genuine installed-Chrome
worker suspension/extension-installation tests.
