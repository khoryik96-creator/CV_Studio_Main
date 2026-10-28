# v24.6.512 JobAdder client-contact email scan

Historical record. The current release is the repository-root `VERSION`.

Branch: `claude/pr157-chatgpt-fix-zke4cy` (PR #257, unmerged). It was built on
merged master `b646d8d` (v24.6.501) and rebased on each newer master, most
recently `44f1887` (v24.6.511). It was numbered v24.6.510 until v511 merged
first, so it is now v24.6.512. Master's route contract did not change from v502
to v511, so the 123-route SHA below still holds.

## Request

The owner asked for an agent that scans the email addresses of JobAdder client
contacts and finds the invalid ones. The owner then chose **not to mark
anything in JobAdder**. Instead they wanted a dashboard of every invalid email
with a link to the contact, a scan that starts when they press a button, and
review by the owner.

## What was built

- **Backend.** `JobAdderReadService.client_contacts()` serves one new GET route,
  `/jobadder/client_contacts`.
  - It returns one bounded page of client contacts: id, name, company, primary
    email and the no-longer-with-company flag.
  - It is read-only. It uses the existing JobAdder token and client and never
    passes a method, body or write retry.
  - JobAdder errors return fixed messages: 401/403/429 keep their code and
    anything else becomes 502. The raw response body is never echoed.
  - The route contract goes from 122 to 123, SHA
    `fc424da1fa9e16a08098e5e603c16383194a70efef141d5fa20073d51682849f`.
    Every test that pins the count, the SHA or a previous-route inventory now
    lists the new endpoint, as the `/apollo` addition did.
- **Frontend.** `vendor/cvstudio/email-verifier-jobadder.js` and a new card in
  the Email Verifier panel.
  - **Loading and checking:** it loads the contact pages, then checks each
    unique email through the unchanged `/email-verifier` route. At most two
    checks run at once, never two on one domain, and a 429 "busy" answer means
    wait and retry.
  - **Catch-all domains:** once a domain is known to accept any address, its
    other contacts are shown as Catch-all without being checked one by one.
  - **Blocked network:** a warning appears when mail servers cannot be reached
    at all, which suggests port 25 is blocked.
  - **Stop and Continue:** Stop keeps results and Continue resumes. A failed
    check stops the scan and keeps its results.
  - **Display and export:** the dashboard defaults to Invalid emails, can hide
    contacts no longer with the company, has a search box, shows at most 500
    rows and exports CSV with formula escaping.
  - **Account changes:** both JobAdder sign-out and an account change clear the
    scan.
- **No other changes.** There is no write to JobAdder, no stored email list,
  no change to the verifier engine or its limits, no paid or AI call, and no
  new dependency.

## Verification

- **New backend tests:** `tests/test_email_verifier_jobadder_scan.py`, 14
  tests and 26 subtests. They cover field mapping and bounds, paging with and
  without a total, input checks, no request without a JobAdder connection,
  error handling without echo, the read-only call shape, the real Flask route,
  GET only, and 401.
- **New frontend tests:** `tests/test_email_verifier_jobadder_frontend.js`.
  - **Data handling:** pure helpers, removing duplicate contacts and emails, and
    the 20,000 cap.
  - **Queue and checks:** the two-checks and one-per-domain limits (measured),
    catch-all inference and quick mode, 429 retry, failure then Continue,
    Stop, and a page that does not move forward.
  - **Accounts and network:** not connected, account change through the
    signal, a missed signal, signing back into the same account mid-check,
    and the blocked-network warning.
  - **Output:** the render cap, CSV, and links that open in a new tab with
    `noopener`.
  - **Hang guard:** the fixture fails, rather than passing silently, if a scan
    never settles. This was checked by deliberately leaving one check
    unfinished.
- **Existing test:** `tests/test_jobadder_account_settings_frontend.js` now
  checks that sign-out and an account change both clear the scan.
- **Deliberate breaks.**
  - **Coverage:** 33 breaks across the backend and frontend; 32 are caught.
  - **Survivor:** reducing the wake-up list to one slot cannot change
    behaviour, because with two workers at most one is ever waiting.
  - **Gaps the breaks found:** they led to the new tests for a missed
    account-change signal and for signing back into the same account
    mid-check, and to simplifying a duplicate guard.
  - **Sign-out paths:** removing either of the two sign-out/account-change
    calls in `jobadder-upload.js` fails the account test.
- **Full local gate** (Linux, every state path temporary):
  - **Python (after rebasing on v511):** 2052 passed, 23 skipped, 8427 subtests. The 2 failures are the
    same known Linux-only ones as on master (Windows startup registration and
    Antiword).
  - **Node:** all 76 test files pass.
  - **Launcher line endings:** they match master (242 / 89 / 37).
- **Pre-existing intermittent test:**
  `test_job_leads.py::test_concurrent_saves_share_one_identity_without_lost_edits`
  sometimes fails with a local-storage race. Out of 90 runs each, it failed 4
  times on this branch and 4 on master, so it is unrelated to this change.
- **Real browser.** The branch app ran locally in Chromium with a fake JobAdder
  account (230 made-up contacts across seven made-up companies) and fake mail
  servers.
  - **Result:** the scan finished with 223 unique emails, 41 Invalid, 31
    Unconfirmed, 31 Catch-all, 120 accepted and 7 with no email.
  - **Behaviour:** the filters, the hide-inactive option, CSV export and the
    contact links all worked, with no browser console errors.
  - **Layout:** checked at desktop and phone widths.
  - **Live checks:** no real JobAdder account or real mail server was
    contacted.

## Code review round (same version)

A review of commit `97107c6` raised ten findings. All are fixed, and each fix
has a test that fails when the fix is removed.

1. **A malformed address on a catch-all domain was shown as Catch-all.**
   Addresses on a known catch-all domain now get a format-and-mail-records
   check (`quick`), with no mailbox probe, so a malformed one is Invalid.
2. **A non-JSON page, or one without `items`, ended the scan quietly.** The
   route used `{"items": []}` as a stand-in for an unreadable page. It now has
   no stand-in and requires an `items` list, so such a page is a 502 error.
3. **Contact links ignored the tenant's own JobAdder address.** They now use the
   same tenant address as the rest of CV Studio, accepting only
   `https://…jobadder.com`.
4. **One failed check stopped the whole scan.**
   - **Retries:** a failure is retried twice, then that email is set aside, and
     Continue retries it.
   - **Outage:** five set-aside emails in a row stop the scan.
   - **Busy answers:** they still never count as failures.
5. **A scan started before the account was known was cleared as an "account
   change".** It now takes on the account once it becomes known.
6. **Every redraw re-sorted up to 20,000 rows.** Contacts are now sorted once
   per change, with one shared collator, and grouped by result.
7. **Stop during the first page left "Stopping…" on screen.** The closing
   message no longer depends on having found an email.
8. **The browser's domain key differed from the engine's.** Domains are now in
   their ASCII (IDNA) form, like the engine's lock.
9. **A sign-in refresh failure looked like "not connected".** It is now a
   temporary 503. Temporary page errors and lost connections are retried.
10. **Unused contact status was sent to the browser.** It no longer is.

**Validation after the fixes:**
- **Deliberate breaks:** 49 breaks covering every fix and the earlier guards;
  all 49 are caught. Two of the new tests were added because the first run let
  two breaks through: "a success resets the failures-in-a-row count" and "busy
  answers never use up retries".
- **Python:** 1969 passed. The only failures are the same two Linux-only ones.
- **Node:** all 72 test files pass.

## Limits

- **Network:** results depend on the recruiter's network. Port 25 is often
  blocked, and many company servers accept any address or decline checks.
- **No saving:** a scan of thousands of contacts takes time, and the results
  live only in the open tab. Export before closing.
- **Link format:** the contact link follows CV Studio's existing JobAdder
  candidate link format. One click on a real account will confirm it.
