# Email Verifier

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
