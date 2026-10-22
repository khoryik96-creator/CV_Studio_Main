# LinkedIn Sourcer module

Release identity comes from root `VERSION`; stamp changes with `bump_version.py`.
This experimental CV Studio module replaces the separate POC workflow for normal
use. The historical POC remains under `poc/linkedin-sourcer` as an isolated
reference, and is not imported by the main app.

## User workflow

1. Open **LinkedIn Sourcer** in CV Studio.
2. Expand **Browser connection help**, download/extract its ZIP, and
   load the extracted folder through Chrome's **Load unpacked** control.
3. Open CV Studio in Chrome and click the companion toolbar icon to connect that
   specific app document. Ordinary service-worker suspension retains that binding
   and run limits after exact-document revalidation. Reloading CV Studio,
   restarting Chrome, or reloading/updating the extension requires reconnecting.
   No additional API key, pairing code or POC server is needed.
4. By default, **Start search opens a fresh LinkedIn People search every time**,
   then uses the generated keywords from the brief. No LinkedIn tab needs to be
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

## Ownership and boundaries

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
