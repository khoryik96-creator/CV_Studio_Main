# Email Verifier — implementation and QA

**Historical — do not use as the current release reference.** The repository-root
`VERSION` file is authoritative.

Date: 2026-10-26. Branch: `codex/v24.6.487-email-verifier`.
Baseline: merged master `d9b91d9d3d90cb65956f5811099663a9872bb768` (PR #248).
Scope: the owner explicitly requests a built-in equivalent to email-verification
tools, using CV Studio's own engine without an external verification product.

## Delivered

- A separate Email Verifier module, styled with CV Studio's existing theme,
  with single/list input, CSV import, deduplication and a 200-address batch limit.
- Quick format/domain checks or default mailbox probing, individual reasons,
  typo suggestions and separate role/disposable-domain hints.
- Mailbox accepted, Invalid, Catch-all, Unknown and Domain passed are distinct.
  DNS success alone never claims a mailbox exists. Generic SMTP rejections,
  full mailboxes, greylisting, blocked connections and unsupported syntax remain
  Unknown. Invalid recipients require an explicit enhanced `5.1.1` response.
- Progress, stop-after-current-check, filter/search, clear and filtered CSV export.
  Partial runs retain completed results and explicit not-checked rows. CSV formula
  prefixes are escaped; addresses and remote evidence never become HTML.
- Lists/results are held in tab memory only; refreshing closes that session.
  The interface tells the user to export first. No history database or schema
  migration is introduced.

## Boundaries

The app-independent Python engine uses system DNS through pinned
`dnspython==2.9.0`, plus Python SMTP/TLS support. There is no verification API,
AI call, API key or provider credential. Domain DNS is TTL-cached; mailbox
results are not cached or persisted. Protocol commands never include DATA,
AUTH, VRFY or EXPN, so no message is submitted or sent.

Only public, checked IP literals on port 25 can be contacted. Private, loopback,
link-local, multicast and mixed-address responses fail closed; connection-time
DNS rebinding is avoided. TLS checks the MX hostname. Budgets include 25 seconds
per check, two global checks, one check per domain, bounded DNS lookups and a
deadline/length/count-bounded SMTP reply reader. Stop does not start another
address after the current check completes. A failed local request stops the
queue without automatically replaying it.

One POST-only `/email-verifier` route is added, with an independent 2 KiB
streamed-input limit, structured request-ID errors and no-store responses.
The full 121-route digest is
`6b0b7dfd41ab2b85fa4685de18efdf1aad477fa91a39cbf0b8a8794eb923b221`.
A regression removes only this route and proves the prior 120 routes still
hash to `ee8d33baeb48b961a2f50723faacbeb7fed86b55454b3518ab4a07bcd1e90033`.
Five guards, global size limit, SQLite/journal/Job Leads schemas, storage,
JobAdder, companion and paid-call behavior are unchanged. Module, asset and
protected-source inventories include the new sources and the DNS package.

## Verification evidence

- Full isolated Windows Python suite: **1,833 passed, four skipped, 8,392
  subtests passed** (146.20 seconds). The preceding run found two historical
  route-subset assertions requiring the newly added endpoint to be excluded;
  their original baseline digests were retained and the corrected suite passed.
- All **49 JavaScript suites** passed, including the new parser/queue/import
  race/filtered export/text rendering regression fixture.
- The verifier's **54 focused Python tests** include real SMTP sessions against
  an isolated loopback fixture, with the actual SMTP parser, for accepted,
  invalid and catch-all responses. The fixture verifies that no DATA is sent.
  DNS exceptions, Null MX, implicit MX, syntax, EAI/quoted local parts, SSRF,
  TLS hostname, concurrency and slow/oversized SMTP replies are covered.
- Isolated native Chromium exercised a real local syntax check, five synthetic
  result types, filter/export, module switching and 390-pixel layout. Screenshots
  were inspected; no page-wide overflow or uncaught page error was found.
  Synthetic screenshots do not represent verified real addresses.
- Live system-DNS reads confirmed example.com's Null MX and Gmail's public MX
  addresses. No real-person recipient or external mailbox was probed during QA.
- Source/native preflight, tracked-language syntax, repository/version checks
  and **24 live source smoke assertions** passed. Windows Antiword and Tesseract
  were trusted and functional. No protected compilation or native Mac test was
  performed.

The small disposable-domain hint set was checked against maintained source data;
one unconfirmed initial candidate was removed. Focused checks are repeated after
that data-only refinement and the final unsupported-address wording change.

## Practical limits

Receiving servers can conceal mailbox existence; local networks may block
outgoing port 25 or reject the verifier's null-sender session. These produce
Unknown, not a false invalid or deliverable result. SMTP acceptance is not a
delivery guarantee. This first version does not claim spam-trap detection,
comprehensive reputation intelligence or commercial-provider accuracy.

The owner installation, real install receipt, browser profiles, saved leads and
credentials were not edited. No paid calls, external email delivery, PR, merge,
release package or protected build were performed. The preview uses isolated
state at port 5090. See `EMAIL_VERIFIER_NOTES.md` for maintenance guidance.
