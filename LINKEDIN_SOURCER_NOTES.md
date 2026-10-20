# LinkedIn Sourcer module

Release identity comes from root `VERSION`; stamp changes with `bump_version.py`.
This experimental CV Studio module replaces the separate POC workflow for normal
use. The historical POC remains under `poc/linkedin-sourcer` as an isolated
reference, and is not imported by the main app.

## User workflow

1. Open **LinkedIn Sourcer** in CV Studio.
2. Expand **Connect the browser companion once**, download/extract its ZIP, and
   load the extracted folder through Chrome's **Load unpacked** control.
3. Open CV Studio in Chrome and click the companion toolbar icon to connect that
   specific app document. Ordinary service-worker suspension retains that binding
   and run limits after exact-document revalidation. Reloading CV Studio,
   restarting Chrome, or reloading/updating the extension requires reconnecting.
   No additional API key, pairing code or POC server is needed.
4. Open a LinkedIn search tab, return to the module and refresh the tab list.
   Choose People search, Recruiter Lite or Recruiter and select the source tab.
   **Review the search already open** retains its existing filters.
5. Enter the brief, choose 1–15 pages and the API-attempt ceiling, confirm the
   displayed DeepSeek use, and start. Try one page before increasing the limit.
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
