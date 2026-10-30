# v24.6.527 Signed clients and candidate sorting

Historical record. The current release is the repository-root `VERSION`.

Branch: `claude/job-leads-signed-clients`, from merged master `7c3f0d5`
(v24.6.526, PR #270). Unmerged. Held PR #257 is excluded.

## Request

The owner asked for two things:

1. **Job Leads dashboard of signed clients.**
   - Show the companies that are signed clients in JobAdder.
   - Let the owner follow or select a few of them.
   - Pull their job ads into the main Job ads.
   - **Owner's choices:** LinkedIn ads; "signed" means a JobAdder company
     status; ads are reviewed before they are added; the pull starts with a
     button.
2. **LinkedIn Sourcer Candidates.** Add filters and ascending/descending order.

## What was built

- **Backend:** `cvstudio_jobadder_clients.py` (`JobAdderClientsService`) behind
  one new `POST /jobadder/clients`.
  - **Actions:** overview, statuses, set_statuses, companies, follow,
    unfollow, set_linkedin and pulled.
  - **JobAdder reads:** company statuses, companies filtered by the chosen
    statuses, and one company at follow time. Reads use only token, timeout,
    fallback and params: no method, body or write retry.
  - **Defensive filter:** a company is labelled signed only if its JobAdder
    status is one of the chosen ones, even if JobAdder ignored the filter.
  - **Storage:** choices are kept per JobAdder account (the one-way browser
    namespace) in a new protected vault, `jobadder_clients`. That vault is
    strict on read failure and does not use the macOS keychain, like the other
    contact vaults.
  - **Limits:** 200 followed clients per account and 20 accounts, with the
    oldest account evicted.
  - **Stale pages:** a page left open under an earlier account cannot change
    choices (409).
  - **Error messages:** JobAdder errors become fixed messages: 401/403 become
    403; 404, 429 and 502 keep their meaning. A failed sign-in refresh is a
    503, and the local overview works without one.
  - **Route contract:** 123 to 124, SHA
    `c24f7c6c98fb0c4855fc1f40a41f54bf70638e5d9e9262382b19d348a125d9e6`. The
    count, SHA, previous-contract exclusions and JobAdder route coverage tests
    are updated.
- **Companion:**
  - `jobSearchBegin` accepts an optional numeric `company_id`, which becomes
    `f_C`. Keywords become optional only with it.
  - Invalid company values never open a tab.
  - `jobStatus` advertises `job_search_company_revision: 1`.
- **Frontend:** `vendor/cvstudio/job-leads-clients.js` and a fourth Job Leads
  tab, **Signed clients**.
  - **Setup and following:** the status picker, a JobAdder client search with
    Follow, and a followed list with JobAdder links, LinkedIn link editing, a
    count of saved ads and the last-pulled date.
  - **LinkedIn company number:** it comes from JobAdder, from a pasted company
    page or "See all jobs" link, or from a saved HR scan of the same company
    page.
  - **Pulling:**
    - It runs one company-filtered search per ticked client, with 1–5 pages,
      up to 15 clients and 600 ads.
    - Stop keeps the ads found so far.
    - Every companion run is ended, and Job Leads is locked during a pull and
      unlocked after.
  - **Review and add:**
    - Pulled ads are listed by client. Ads already saved cannot be ticked.
    - Add selected to Job ads uses the existing save action (status New,
      chosen folder) and reloads the main list.
  - **Accounts:** sign-out and an account change clear the view.
- **Candidates:** sort by Last assessed, Match score, Name, Location or Profile
  read, ascending or descending.
  - **Filters:** minimum match and profile read.
  - **Ordering rules:** names and locations ignore letter case, blank values sort
    last, and ties keep the newest-first order.
  - **Excel:** the export uses the same view, applied by the same server rules.
  - **Remembered choices:** sort and order are remembered in this browser.

## Verification

- **New backend tests:** `tests/test_jobadder_clients.py`, with 36 tests.
  - **Link parsing:** the LinkedIn link rules.
  - **Statuses and companies:** the choice is checked against JobAdder, and the
    defensive filter applies.
  - **Following:** the read-only call shape, follow and link handling, and the
    pasted link surviving a re-follow.
  - **Accounts and limits:** account isolation, limits and eviction.
  - **Storage:** unreadable vault data is refused without being overwritten,
    and save failures are reported.
  - **Errors:** fixed messages, and refresh failure versus a missing token.
  - **Route:** the real Flask route is POST only, bounded, guarded and
    no-store.
- **New frontend tests:**
  - **`tests/test_job_leads_clients_frontend.js`:**
    - Opening the view, the status choice, follow and LinkedIn links.
    - An outdated or disconnected companion, company-filtered pulls,
      de-duplication and unsafe links.
    - Review/add, a busy Job Leads, Stop, account changes, stale replies, the
      15-client limit and a JobAdder outage.
    - It fails if a step never settles.
  - **`tests/test_people_candidate_sort_frontend.js`:** every sort in both
    directions, blank-last, filters, the export view and remembered
    sort/order.
- **Extended tests:**
  - `tests/test_linkedin_job_search.js`: single-company searches.
  - `tests/test_people_dashboards.py`: server sort and filters, and the export
    route.
  - `tests/test_jobadder_account_settings_frontend.js`: sign-out and account
    change clear the view.
- **Deliberate breaks:** 48 breaks across the backend, frontend, companion,
  candidate sorting and account hooks.
  - **Result:** 47 are caught.
  - **Survivor:** removing the second "skip saved ads" check in Add cannot
    change behaviour. Every redraw already drops saved ads from the selection,
    and the server never overwrites an existing ad.
  - **What the breaks found:** they led to the fake page nesting its tables
    inside the panel. Before that, it could not see the bug below.
- **Real browser:** the branch app ran in Chromium with a fictional JobAdder
  account (five companies and four statuses), fictional saved ads and
  candidates, and a simulated companion.
  - **Setup:** two statuses were chosen, and the "Prospect" company was not
    listed. Four clients were followed and a "See all jobs" link was added.
    One client's LinkedIn company came from a saved HR scan.
  - **Pull:** three ticked clients were pulled with company filters 909101,
    7700 and 909103. Five ads came back, one already saved. Three were added to
    a folder and appeared in the main Job ads list.
  - **Bug found:** this run found that the shared "disable while busy" step
    re-enabled the Pull box of a client with no LinkedIn link. It is fixed and
    now covered.
  - **Candidates:** every sort, both orders and the filters behaved as tested,
    the Excel export downloaded, and sort/order survived a reload.
  - **Layout:** a layout pass made the dropdowns and tick box compact. Phone
    width has no horizontal page scroll.
  - **Console:** the only console error was the demo's missing work-type
    lookup, an unrelated page-load request the fake JobAdder did not answer.
- **Full local gate** (Linux, every state path temporary):
  - **Python:** 2248 passed, 23 skipped, 8398 subtests. The 2 failures are the
    known Linux-only ones (Windows startup registration and Antiword).
  - **Node:** all 84 test files pass.
  - **Launcher line endings:** they match master.

## Limits

- **LinkedIn company number:** LinkedIn's company filter needs the company's
  number. A client whose JobAdder link is a named page needs either a saved HR
  scan of that page or the pasted "See all jobs" link.
- **Background tabs:** each pulled client's LinkedIn search stays open in a
  background tab, as the existing search does. The companion never closes
  user-facing search tabs.
- **No live check:** live LinkedIn behaviour was not exercised. The companion
  checks the loaded search still has the same company filter and stops if
  LinkedIn changes it.
- **Saved-ad count:** the count matches company names loosely (legal words
  ignored), so it is a guide rather than an exact link.
