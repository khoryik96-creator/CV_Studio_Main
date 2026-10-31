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
    statuses, one company at follow time, and the signed-in user once per
    sign-in. Reads use only token, timeout, fallback and params: no method, body
    or write retry.
  - **Defensive filter:** a company is labelled signed only if its JobAdder
    status is one of the chosen ones, even if JobAdder ignored the filter.
  - **Storage:** choices are kept per JobAdder user in a new protected vault,
    `jobadder_clients`. The key is a one-way hash of region, account name and
    user id from `GET /users/current`, read once per sign-in, so a new sign-in
    to the same user restores the choices. That vault is strict on read failure
    and does not use the macOS keychain, like the other contact vaults.
  - **Limits:** 200 followed clients per user, 20 users with the oldest
    evicted, and 100 remembered sign-ins.
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
  - **Survivor (first round):** removing the second "skip saved ads" check in
    Add could not change behaviour. Every redraw already drops saved ads from
    the selection, and the server never overwrites an existing ad. See the
    review round below for the final break count.
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

## Code review round (same version)

A review of commit `fc58209` raised 15 findings. All are fixed on the same
branch and version, and each fix has a test that fails when the fix is removed.

1. **Choices were lost on every JobAdder sign-in.** They were keyed by the
   connection key, which is new and random on each completed sign-in. They are
   now keyed per user (`GET /users/current`, once per sign-in, hashed with
   region and account name). A new sign-in to the same user restores them;
   another user or account sees nothing.
2. **Two route tests could write the real install receipt.** Run alone, they
   wrote the receipt and imported the app with the owner's own HOME, AppData
   and database. The new `tests/isolated_app.py` points every receipt, vault,
   database and log path at a temporary folder first. A check with an empty
   sentinel HOME confirms nothing is written outside it.
3. **Searches kept opening after the 600-ad review limit.** Once 600 ads wait,
   no further search opens and paging stops. A client cut short is not marked
   as pulled, and the summary says how many were not fully pulled.
4. **"Select all new ads" could exceed the 100-ad add limit.** Selection is now
   per page ("Select new ads on this page"). Add saves up to 100 per click and
   leaves the rest ticked for the next click.
5. **A status removed from JobAdder could never be unticked.** It now starts
   unticked, is flagged in the summary, and Save statuses drops it.
6. **Following again wiped a pasted LinkedIn company number.** The number is
   kept while JobAdder still shows the same named page or none. A different
   page drops it, and a numbered page in JobAdder replaces it.
7. **More than 15 linked clients made the default pull fail.** At most 15 can
   be ticked: the first 15 are ticked by default. Ticks are remembered in the
   browser, and there is an **Untick all** button.
8. **An account change while a search was opening could leave the companion
   busy.** Each pull now always ends the companion run it started, even after
   the view was cleared. Stop ends the current run at once, as Job Leads does.
9. **Excel could list candidates in a different order from the screen.** The
   page and the server now share one rule: case- and accent-insensitive,
   numbers inside text compared as numbers, blank (including only spaces) last.
   A shared list of tricky names holds both to the same order.
10. **A malformed port in a LinkedIn link caused a misleading 503.** It is now
    simply not a LinkedIn page. Non-text actions are input errors (400).
11. **Pull and Add did not update when Job Leads became busy or free.** Job
    Leads' busy state no longer disables them. Clicking while Job Leads is busy
    explains why nothing started.
12. **Reconnecting JobAdder in another tab left a "Click Refresh" loop.** A
    reply for another account now re-reads this page's account through the
    same `applyJAPublicInfo` step the rest of CV Studio uses, then reloads once.
    If they still differ, the owner is asked to reconnect.
13. **The pull summary undercounted after Stop.** It now counts every ad found,
    including a stopped client's.
14. **Saved-ad counts made redraws slow.** About 3 s per redraw at 200 clients
    and 5,000 ads. Counts and the saved-ad lookup are now built once per data
    change; the test file runs that size in under a second.
15. **The pull duplicated Job Leads' search loop.** Both now use
    `vendor/cvstudio/job-search-walk.js` for the page/scroll/next loop, result
    checks and job-link check. Job Leads' own search tests pass unchanged; the
    three tests that load `job-leads.js` also load the shared file.

**Validation after the fixes:**
- **Deliberate breaks:** 78 breaks across the backend, frontend, shared search
  loop, companion, candidate sorting, account hooks and test isolation; all 78
  are caught. The first run let 8 through: each was a gap in a test, not in the
  code, and the tests were strengthened. Examples: the parity list needed
  accented names, and the cap test needed a client cut off mid-search.
- **Python:** 2270 passed. The only failures are the same two Linux-only ones.
- **Node:** all 84 test files pass.
- **Real browser:** the Chromium run was repeated with the fixes. It confirmed
  that after a simulated new sign-in to the same JobAdder user, the 4 followed
  clients and the 3 ticks were still there. The only console errors were the
  demo's unanswered work-type lookups again.

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
