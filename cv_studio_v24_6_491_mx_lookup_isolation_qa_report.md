# Email Verifier MX lookup isolation — v24.6.491

Owner-authorized PR #249 merges the first-party Email Verifier and Awards/HR
corrections. Its automated review of `2903d6a` found one P2 issue: a failed MX
address lookup exited the whole verifier even when another host was usable.
All three hosted checks had passed, but merge was held for this correction.

The verifier now handles `CheckUnavailable` per host. Successfully resolved
public hosts remain available; a failed/restricted host contributes no addresses.
When all hosts are unusable and at least one lookup was inconclusive, the first
safe failure is retained as unknown. Missing-address/domain semantics, public
address validation, fixed-port IP pinning, session/deadline limits and slot cleanup
remain unchanged. No new route, schema, UI verdict or paid/external service.

Five new tests failed before implementation: primary/backup failure in both
quick/full modes and all-host failure/cleanup. A sixth combines a real MailDNS
private-address rejection with a usable public backup and verifies only the
public host reaches the mocked SMTP probe. No real DNS or recipient call occurs.

Focused verifier/version validation passed 70 tests. The complete isolated
Windows regression passed **1,853 tests, four skipped, 8,416 subtests** in
318.76 seconds. All 52 JavaScript fixture files, tracked-language checks,
repository consistency, native Antiword/Tesseract owner-source preflight and
24 smoke assertions passed. Final hosted/merge identities are recorded in
coordination issue #35 after completion.

The v490 exact-source formatting, document visual comparison, native companion
and verifier browser evidence remain applicable: this correction changes only
MX address-lookup failure isolation and generated version surfaces. Owner
installation, receipt, data and credentials remain untouched; no email delivery,
outreach, paid call, protected build or native macOS testing is claimed here.
