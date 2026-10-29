# v24.6.519 — HR retry progress, immediate dates and JobAdder links

Local checkpoint from merged v518 `f78aacf` / PR #265. The owner requests fixing
missing dates in a stopped scan, resuming unfinished batch ads, and a contact
link after creation. No publication/merge requested; PR #257 remains excluded.

Read-only browser inspection confirmed the installed app serves518, the shown
batch is stopped with no saved ads and 27 unstarted ads, and the exact-company
modern Experience date becomes visible after scrolling. No live scan, paid
lookup, owner HR save or JobAdder write was performed. Public uncredentialed
JobAdder contact navigation reaches sign-in; authenticated record opening has
not been tested. The regional `/contacts/{ID}` route is confirmed in the
publisher's public [JobAdder for Gmail extension](https://chromewebstore.google.com/detail/jobadder-for-gmail/kdgjajomkcifhcdkbdpiiiomjlnlncho)
template source; its archive was inspected in memory without installation or
execution. Fixtures use only fictional identities and data.

Reproduced UI defects: pending dates showed Not available; a validated date did
not render before cleanup/another person/page. The new regression holds cleanup
after a valid date, checks immediate rendering, and verifies Stop preserves that
display while unfinished dates say Not checked. Transient state is stripped
before save. Profile navigation previously consumed the same 20 waits as date
metadata; separate 60 navigation / 20 Experience / 80 total bounds retain the
four-scroll, exact-source/company/profile, viewed-tab, Stop and deadline guards.
No parser identity or precision rule is loosened. This does not claim recovery
of a historical unknown result or a live owner end-to-end rescan.

Bulk checkpoints bind exact selection/settings and confirmed record revisions.
Failed/stopped/running ads precede waiting ads; unchanged saved ads are skipped.
Changed saved ads are requeued. Different selection/settings or an all-finished
batch request starts fresh. No automatic resumption on reload. Only opaque IDs,
revisions, outcomes and non-secret selected settings enter a bounded browser
checkpoint. No people, emails, URLs or partial results. Invalid/storage-failed
checkpoints fall back safely; same-page memory still resumes when possible.

Existing contact-action responses add a URL only for created/known-existing
positive integer IDs, via the established regional web-base helper. The dialog
offers an explicit Open in JobAdder link, clears it on review/context changes,
and validates HTTPS JobAdder host, exact contact ID and absence of extra query
data. No new route, API read/write, contact creation or duplicate override.

## Validation

- New frontend regressions cover Stop/failure/reload/settings/revisions,
  checkpoint corruption/storage failure, fresh rescan, immediate dates and
  navigation/alternating-stage bounds. Tests failed before the fixes.
- Optional native Chromium uses actual markup/CSS/controller and fictional
  records/RPC with network blocked: immediate date, Stop, resume, previously
  saved skips, correct order and cumulative progress pass. Screenshot inspected.
- JobAdder domain/guard/link routes: 30 tests pass. Frontend tests cover success,
  read-only recovery, hidden stale/uncertain and unsafe/mismatched URLs.
- Complete isolated Python regression: **2,143 passed, four skipped and all
  8,418 subtests passed**. All **78** standard JS test files passed.
- Actual isolated Flask/native Chromium passed existing-company selection,
  authoritative email, review invalidation, one fictional POST, created regional
  contact link, duplicate reopen protection and desktop/mobile layouts. Native
  queue/date and previous Contacts visibility fixtures passed on final code.
  Screenshots were inspected and retained only in ignored runtime output.
- Version/repository consistency, tracked-language syntax, genuine Windows
  dependency preflight and all **24** source-smoke assertions passed.

No schema/security/credential/account boundary changes, owner installation
update, live paid/unlock/JobAdder record action or macOS application claim.
