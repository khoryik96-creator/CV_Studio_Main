# v24.6.517 — reviewed JobAdder company-contact creation

Local checkpoint from merged v516 `fad1a39`. The owner requests company-contact
creation from unlocked emails and confirms existing JobAdder company selection
only. There is no company creation, candidate creation, outreach, Apollo unlock,
live provider test, publication or merge in this checkpoint.

The contact table opens a review dialog with editable first/last names and
position, authoritative unlocked email and observed LinkedIn profile. A verified
existing company, exact-email duplicate read, payload/account-bound expiring
review nonce and explicit Create click precede a single POST. The server repeats
the safe duplicate read immediately before its durable pending marker and POST.
Transport retries and401 replay are disabled. Timeout, malformed success or lost
local result save cannot trigger another POST; restart keeps read-only recovery.
Existing duplicates, including another employer, are never overridden or moved.
No country is invented from the scan filter or sent as an address.

One additive paired-session/critical-write-guarded POST route seals123 routes.
The new characterization removes that one endpoint and verifies the exact
previous122-route digest. Existing historical count/route exclusions were
updated for the legitimate additive boundary, keeping their original historical
digests, five guards and80MiB application limit. Operation metadata uses a new
protected vault; no plain SQLite or credential migration is introduced.

## Local checks

-22 new domain/route cases cover confirmation, account/name/company changes,
 expiry, exact/global duplicates and races, source authority, pending-before-
 transport, restart/lost-response non-replay, malformed reads, storage failures,
 no401 replay, prior-route preservation and real guarded local routing.
- The new UI fixture covers source fill, company selection, invalidating review,
 explicit single create, inability to fake-cancel an active write, read-only
 recovery and preservation of ad drafts/data. All76 standard JS files passed.
- Actual isolated Flask/native Chromium uses synthetic JobAdder transport and
 separate protected storage. Company selection, reviewed creation, field-change
 invalidation, one POST, duplicate reopen protection and desktop/mobile layouts
 passed; screenshots were inspected. No real account/contact/credit was used.
- Initial broad Python run:2108 passed,4 skipped,8418 subtests;13 failures were
 old global route-count expectations. Those expectations and the sign-out
 historical exclusion were corrected; all85 tests in those affected files now
 pass (three platform skips,27 subtests). Core contact/guard coverage passed.
 A final full regression will run with the stacked employment-date correction.
- Syntax/repository/version, genuine Windows dependency preflight and all24
 source-smoke assertions passed. No genuine macOS app or protected build claim.

The separately requested owner update-block repair preserved the local Apollo
edit in a stash and local commit on a backup branch, then rebased the redundant
public broker config onto masterv516. Source is clean with the correct named
User-Agent. No owner server restart, credential, receipt or record change.

PR #257 stays on hold. This checkpoint is local and not pushed or merged.
