# v24.6.493 — Email Verifier IPv6 fallback

Base: merged v492 `15c9948f083f293e033adc2b05b25e5f311c0a31`.
Branch: `codex/v24.6.493-email-ipv6-fallback`. Unmerged source checkpoint.

The owner reported a connection timeout for a known-valid mailbox and requested
a correction. The first IPv4-only diagnostic was too broad: it suggested the
network could not provide SMTP, but a subsequent address-family check found
working IPv6 SMTP connections on the same advertised Microsoft/Google servers.

## Root cause and change

`MailDNS.addresses` collected A answers before AAAA answers, then truncated the
combined list to two entries. An MX with two or more A records therefore lost
every advertised IPv6 address. The existing two SMTP attempts used IPv4 twice,
even when IPv6 was reachable.

The bounded selection now retains the first IPv4 and first real IPv6 address
when both are present. Single-family order remains unchanged. All answers are
deduplicated and validated before selection, including answers beyond the
selected slots. IPv4-mapped IPv6 cannot consume the real IPv6 fallback slot.
The two-address/two-probe cap and single 25-second deadline remain unchanged.

No verdict, route, response schema, request/security guard, SMTP command,
credential store, TLS identity, DNS cache, concurrency or mail-delivery behavior
changed. No firewall exception, elevated action, external verification service,
cloud worker, paid call or new port was added. The owner installation and
existing records/receipts were not modified.

## Verification

Before the correction, three new cases failed against merged v492: two
dual-stack address-selection cases and the integrated IPv4-timeout/IPv6-success
case. Eight other family/safety cases passed. After correction all passed.
Additional duplicate-answer and IPv4-mapped/real-IPv6 cases verify the fallback
cannot be crowded out. Restricted, loopback, private, mapped-private and
multicast answers still fail before any connection, even when otherwise usable
answers appear first. Integrated fixtures preserve the overall deadline and
two-probe limit.

Native TCP checks from the actual Windows host connected to public Microsoft
and Google MX IPv6 endpoints and received SMTP 220 greetings. Their IPv4
endpoints had timed out at four and twelve seconds. A separate normal web
connection and submission-port connection succeeded; no firewall policy was
altered. The evidence identifies an available IPv6 path, without claiming the
exact device/provider responsible for IPv4 timeouts.

One live full check was explicitly within the owner's requested troubleshooting
of their previously supplied address. It used the corrected production engine,
completed over IPv6 and returned `catch_all`: both the intended recipient and
random control were accepted. No DATA/AUTH/VRFY/EXPN was sent and no message was
delivered. The local part, raw server replies and random address are absent
from tests, logs, evidence and this report. This is SMTP acceptance evidence,
not a claim that every accepted address is a real mailbox.

The complete regression gate passed 1,865 Python tests, four skipped and 8,416
subtests. Two edge cases were added after that gate's collection; the final
83-test Email Verifier/version run includes and passes both, together with all
other focused cases. All 55 JavaScript fixture files passed, including the
unchanged email parser, queue, Stop, filtering, CSV safety and result rendering.
Python/JavaScript/PowerShell/shell syntax, repository consistency, version
identity, owner-source/native dependency preflight and the 24-assertion source
smoke passed. No native package was compiled and no new Mac test claim is made.
Synthetic test domains remain fictional; no live network call is added to the
regression suite.

This branch does not guarantee a mailbox verdict where both families are
unreachable or the server refuses verification. Those outcomes remain
Unconfirmed. No PR, merge, protected compilation or release artifact is part
of this checkpoint.
