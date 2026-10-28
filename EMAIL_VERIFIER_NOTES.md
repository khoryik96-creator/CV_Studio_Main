# Email Verifier

## Review corrections (v24.6.501)

Microsoft DBEB replies may include the documented terminal period before a
diagnostic suffix. Only that optional period is added; MX suffix, SMTP code,
leading enhanced code, exact phrase and word boundary remain mandatory.
Lookalike providers, temporary codes, joined words and repeated punctuation
cannot become missing-recipient evidence.

Each full/deep check now creates one control identity shared by its bounded
SMTP sessions. Its response includes an optional opaque `recheck_token`.
Automatic/list rechecks and explicit same-address HR-card retries return it
so recipient-based greylisting can recognize the original control recipient.
New checks still work without a token. Quick/unsupported checks issue none.

The token contains only a version, expiration, random nonce and HMAC-SHA256.
Its signature binds the canonical address (local-part case preserved), nonce
and expiry to a random process-local key. It expires after four hours and is
invalid after restart. Malformed, tampered, expired, other-address/process or
quick-mode references fail before DNS/SMTP, with fixed guidance to start fresh.
It is a recheck correlation reference, not an account/provider credential or
permission to contact a new destination. No token/result/address cache or
database/schema change was introduced. The server key is volatile only.

The four-hour bound accommodates the existing 200-address/two-pass foreground
queue without arbitrary persistence. A suspended tab may outlive the reference;
the resulting visible error retains prior results and never silently switches
control identity. The reference stays in tab memory and POST bodies, is not
exported, and is cleared by HR input/account changes. Existing 25-second/global/
domain limits, public-IP pinning, null sender and no-mail behaviour remain.
See the v501 QA report for counterfactual/protocol/browser validation.

## Evidence and deeper checks (v24.6.500, local and unmerged)

The owner authorized improving the first-party checker and adding verification
to Job Leads HR cards. No external verifier, account connection, hosted worker,
mail delivery or paid service was introduced. Legacy status/response fields and
the POST route remain; evidence fields and `mode:deep` are additive.

- `mailbox_evidence` separates acceptance/rejection/unconfirmed/conflicting
  answers from `catch_all` domain behaviour. A real address can coexist with
  catch-all acceptance. The assessment is a qualitative recommendation, never
  a measured probability, ownership claim or inbox-delivery guarantee. A known
  disposable hint can add caution without rewriting the SMTP verdict.
- The documented Microsoft DBEB `550 5.4.1 Recipient address rejected: Access
  denied` is recipient evidence only on an MX ending in
  `.mail.protection.outlook.com`, at RCPT time with the exact bounded phrase.
  Other hosts, suffix lookalikes, generic Access denied and policy codes stay
  unknown. General missing-recipient evidence requires a leading `5.1.1` and
  the established permanent reply codes. Source:
  [Microsoft DBEB](https://learn.microsoft.com/en-us/exchange/mail-flow-best-practices/use-directory-based-edge-blocking).
- Temporary deferrals, full mailboxes, sender policy, TLS failure, connection
  failure and explicit recipient rejection have distinct fixed outcomes. Raw
  server replies, hosts/IPs and recipient strings are absent from explanations.
  Transient DNS/connection/4xx cases may suggest a later recheck; policy, TLS,
  restricted destinations and mailbox-full answers do not trigger one.
- Full mode retains two sessions. Deep mode tries at most four within the same
  total 25-second budget, comparing the two available MX hosts before second
  address-family attempts. A connection failure prioritises that host's known
  alternate family so blocked IPv4 cannot starve working IPv6. A decisive host
  need not be contacted again through
  its other family. Both modes retain conflicting acceptance/rejection as
  unconfirmed. Catch-all on one responding server remains caution even if
  another rejects a random control. No manufactured-address acceptance can
  establish that the requested mailbox actually exists.
- Deeper UI runs perform one additional check only for temporary unknown
  results, after at least 120 seconds from receipt of that address's first
  result. Waiting uses the browser's monotonic clock and is cancellable at
  one-second boundaries. This is a foreground queue, not durable automatic
  resume. A delayed check can still remain unknown; greylisting may last longer.
  Policy blocks are never automatically replayed. Explicit Recheck uncertain
  also covers catch-all addresses, once per result with the same spacing.
- Previous results remain visible during a recheck and survive transport
  failure. Successful rechecks retain a textual previous result. CSV adds
  assessment, mailbox/domain evidence, provider class, session count and the
  previous result; existing formula protection remains. Checks show their time.
- HR cards accept an optional manually entered email and require Verify email
  before contacting a mail server. An already revealed Apollo email prefills
  that field without triggering a probe or another credit use. Manual edits
  are not overwritten. Input changes and Apollo account clearing invalidate
  old results and pending responses. Verification never rewrites saved ads,
  HR data, notes or protected Apollo records. Results live only in card memory.

No user correspondence or directory is connected in this milestone. Consented
delivery/reply evidence, calibrated outcome-based scoring, comprehensive
licensed risk data and self-hosted SMTP workers are subsequent work requiring
real evidence or infrastructure setup. Controlled protocol tests cannot support
a commercial accuracy percentage. Current operation remains laptop/network
dependent, and unresolved catch-alls remain explicit. RFC reference:
[greylisting](https://www.rfc-editor.org/rfc/rfc6647.html).

The earlier limits below describe the initial checker. The v500 paragraph
supersedes its two-session limit only for the explicit Deep mode. All public
DNS/IP pinning, TLS identity, no-DATA/no-AUTH/no-VRFY/no-EXPN, request/response
bounds, domain/global concurrency, no persistent email lists and credential
boundaries remain.

The v493 correction keeps one IPv4 and one real IPv6 address when an MX
advertises both, within the existing two-address/two-probe/25-second limits.
Previously two A answers filled both slots and every AAAA answer was discarded,
so an IPv4 SMTP timeout prevented using a working IPv6 route. IPv4-only and
IPv6-only ordering remains unchanged. Every DNS answer still passes the public
address guard before selection; mapped IPv4 does not count as an independent
IPv6 route. Connections remain pinned to the selected IP and TLS still checks
the MX hostname. No firewall, new service, additional port, key or mail delivery
is needed for this fallback.

Read-only native connectivity checks confirmed working IPv6 SMTP greetings
where IPv4 connections timed out. One owner-authorized live mailbox check then
completed as catch-all: the server accepted the target and the random control.
This resolves that connection failure; catch-all acceptance cannot establish
that every accepted address is an actual mailbox. A future server that blocks
both address families may still remain unconfirmed.

The v491 pre-merge review correction isolates address-lookup failures to each
MX host. A failed or restricted host contributes no addresses, while another
successfully resolved public host remains usable for quick and mailbox checks.
If no host is usable and any lookup was inconclusive, the result stays unknown;
it is never reinterpreted as a definite missing-domain/server verdict. Public
address validation within each host, SMTP pinning, scan budgets and cleanup
remain unchanged.

The v490 UI calls the machine status `unknown` **Unconfirmed** and displays
independent format, mail-record and mailbox evidence. No verdict semantics or
route fields changed. A timeout before the mail-server greeting is reported as
a connection timeout; a recipient-response timeout, refused connection and TLS
certificate failure each have fixed, distinct guidance. None is an Invalid
verdict and raw exceptions/recipient data are never echoed in the reason.
Finding MX records proves routing exists, not that a mailbox exists. A blocked
port-25 connection cannot be repaired by declaring the address valid; successful
mailbox probing requires a network and remote mail server that permit it.

The repository-root `VERSION` is the release source of truth. This module was
introduced on `codex/v24.6.487-email-verifier` from master `d9b91d9` at the
owner's request for a first-party verifier without a verification service.

## User flow

Open **Email Verifier**, paste addresses or import a CSV with an Email column,
choose mailbox verification (default) or a quick domain check, and verify.
The maximum is 200 unique addresses per run and a 1 MB import. Duplicate
domains are compared without case; local-part case is preserved. Inputs are
not silently corrected. Known spelling mistakes produce a suggestion.

Results can be filtered/searched and exported; export contains only completed
results matching the current filters. Stop finishes the current bounded check
and leaves remaining addresses explicitly not checked. Switching modules keeps
the list; refreshing/closing the browser discards it. There is no saved email
database, browser-storage mirror or background job family in this version.

## Evidence and limits

- Invalid: syntax, NXDOMAIN, a proper Null MX declaration, no implicit MX
  fallback, or an explicit recipient `5.1.1` failure.
- Mailbox accepted: the target is accepted and a randomly generated mailbox
  on the same domain is explicitly rejected with `5.1.1`. This is SMTP
  evidence, not a future-delivery guarantee.
- Catch-all: both the target and made-up address are accepted.
- Unknown: ambiguous replies, policy blocks, greylisting, full mailboxes,
  timeouts, unusable mail-server records or unsupported mailbox syntax.
- Domain passed: quick checks only; individual mailbox existence was not tested.

Role/disposable-domain hints are separate from the verdict. The disposable
list is a small explicit built-in set, not a comprehensive live reputation
feed. The eight hints were checked against the maintained
[disposable-email-domains list](https://github.com/disposable-email-domains/disposable-email-domains),
with [Mailinator](https://www.mailinator.com/) and [YOPmail](https://yopmail.com/)
also confirmed on their official pages on 2026-10-26. No list is fetched at runtime.
No spam-trap detection, mailbox ownership proof or numerical accuracy
claim is made. Quoted, international local parts and address literals stay
unknown; international domains use IDNA. Never infer invalidity from a generic
550, a connection failure or a DNS timeout.

Mailbox probes use port 25. Some networks block it and some servers decline
verification-only/null-sender sessions. Those cases require an Unknown result;
do not work around them by sending mail, impersonating a sender or bypassing
access controls. This version does not depend on DeepSeek, a companion,
ZeroBounce, an external verification API or an API key.

Protocol basis: [SMTP / implicit MX](https://www.rfc-editor.org/rfc/rfc5321.html),
[Null MX](https://www.rfc-editor.org/rfc/rfc7505.html).

## Boundaries

`cvstudio_email_verifier.py` is app-independent. The one POST-only
`/email-verifier` route delegates to it; all prior 120 routes remain exactly
unchanged. The full contract now has 121 routes and SHA-256
`6b0b7dfd41ab2b85fa4685de18efdf1aad477fa91a39cbf0b8a8794eb923b221`.
All five global guards, 80 MiB global request limit, schemas and credential
stores remain. The new endpoint has its own 2 KiB streamed-input ceiling.

DNS uses pinned `dnspython` with the system-configured resolver (no hardcoded
verification endpoint), bounded lookups and a small DNS-only TTL cache.
Installer and protected-source module inventories include the new module;
Nuitka explicitly includes `dns`. Missing resolver support fails visibly within
the module and never prevents unrelated CV Studio features from booting.

The engine allows two checks globally, one per domain, and a 25-second budget
per check. SMTP replies have aggregate deadline, line-length and line-count
bounds. All SMTP destinations must be public IP literals validated from DNS;
non-public/multicast answers are blocked and hostnames are never resolved
again when connecting. STARTTLS validates the MX hostname. No DATA, AUTH, VRFY
or EXPN is issued, and no message is delivered. Raw remote replies and email
lists do not enter diagnostics or persistent state. CSV export escapes formula
prefixes; result rendering uses DOM text nodes.

## Verification

Use the isolated test runner documented in HANDOFF; never authorize a checkout
against the owner's real install receipt. Focused fixtures:

- `tests/test_email_verifier.py`: DNS, malformed input, unsupported syntax,
  SMTP classifications, TLS identity, bounded replies, private targets,
  concurrency, loopback protocol sessions, route guards and exact prior routes.
- `tests/test_email_verifier_frontend.js`: imports, parser edge cases, duplicates,
  formula escaping, queue/stop/failure state, import races and filtered export.

The versioned QA report records actual test counts and what was checked live.
Do not mistake synthetic mailbox fixtures for proof of real-address accuracy.
