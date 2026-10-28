# v24.6.500 — first-party email evidence and deeper checks

Local, unmerged `codex/v24.6.500-email-evidence`, stacked on v499 `1e856cb`.
The unmerged v498/v499 HR fixes remain included. Merged master remains v497
`ff722b3`. The owner authorized implementation, not publishing or merging.

## Resulting behaviour

The existing verifier now separates SMTP acceptance/rejection, catch-all domain
behaviour and a qualitative recommendation. Fixed outcomes distinguish
temporary deferral, a full mailbox, policy restrictions, network/TLS failures
and explicit missing recipients. The Microsoft DBEB response is recognized
only with its documented code/phrase on the exact Microsoft MX suffix.
Other policy messages and suffix lookalikes remain unconfirmed. Arbitrary
embedded enhanced codes cannot create missing-recipient evidence.

Full mode retains its two-session limit; Deep mode compares up to two MX
hosts within four sessions and the same total 25-second deadline. A blocked
connection prioritises the known alternate IP family. Conflicting target
answers remain unconfirmed in both modes; an inconclusive connection cannot
overwrite a decisive response. Catch-all results never prove individual
mailbox existence. A known disposable hint adds caution separately.

Deep UI runs allow one delayed recheck for temporary unknowns after at least
120 seconds per address. Policy/TLS/full-mailbox answers cannot be made
automatically retryable by an earlier transient connection. Waiting uses a
monotonic clock, supports Stop/pagehide, retains prior results and cannot
silently resume as a durable worker. Explicit Recheck uncertain also covers
catch-all results, with the same per-result bound/spacing. Failed requests
retain previous results. CSV exports include the additional evidence.

HR cards have an optional email field and explicit verification button.
Existing Apollo emails may prefill that field; nothing probes automatically,
reveals another email or spends a credit. Manual edits are preserved; input
changes/account clearing invalidate previous or pending results. Manual
verification works without Apollo. Saved ads/HR records/notes are untouched.

## Verification evidence

- Baseline: 78 existing Python verifier tests and the existing verifier,
  Apollo and Job Leads frontend fixtures passed before implementation.
- The new evidence tests first failed against the baseline for provider
  handling, separate assessment, deep comparison and temporary outcomes.
- Final focused backend: **109 passed**, including 31 new controlled cases.
  Coverage includes exact provider binding, control rejection, full mailboxes,
  conflicting servers/connections, dual-stack ordering, shared deadlines,
  four-session limits, slots, DNS retry classification, false enhanced-code
  text, partial control evidence and the existing guarded route.
- All **67 JavaScript fixture files pass**. New cases cover delayed retries,
  one-recheck bounds, Stop, server clock skew, preserved results on failure,
  CSV/text safety, late responses, Apollo prefill/disconnect, manual checks,
  no automatic probe and untouched saved records/drafts.
- Native Chromium runs the actual app on isolated port 5094 with fictional
  records and intercepted verifier/Apollo responses. It passes the delayed
  recheck transition, retained previous explanation, evidence rendering,
  CSV download, HR prefill/explicit verification, disconnect clearing and
  narrow mobile layout. Screenshots are ignored runtime QA artifacts.
- Sealed full isolated regression: **1,925 passed, 4 skipped; 8,416 subtests**.
  The earlier complete run also passed before the final two guard cases.
- Final source validation passes tracked Python/JavaScript/PowerShell/shell
  syntax, repository consistency, source/native preflight and **24 live
  source-smoke assertions**. Native Windows x64 Antiword and Tesseract are
  functional. No protected compilation or colleague package was produced.

The first full run exposed three existing updater-test environment failures:
isolating APPDATA hid a user-site dependency from child Python probes. The
ignored local runner now preserves dependency search paths for child processes
while keeping receipt/DB/journal/user data in temporary directories. All three
updater tests then pass; no updater implementation or requirement was changed.

## Boundaries and remaining work

No route/guard/schema/credential/provider-credit change, persistent email
database, new background job, external verifier, outgoing message, live mailbox
probe, account/history connection, server provisioning or protected package.
Public-address DNS validation and connection pinning, TLS hostname checks,
bounded replies, null sender and no DATA/AUTH/VRFY/EXPN remain. Raw SMTP replies
and private recipient data are excluded from explanations/logs. Runtime results
stay in browser memory until an explicit export; ad/HR backups gain no emails.

Network restrictions and catch-all uncertainty remain real limitations.
Consented delivery/reply evidence, authoritative directories, trained/calibrated
scoring, licensed risk feeds and owned SMTP workers are subsequent work.
Synthetic fixtures do not establish a real-world accuracy percentage or an
inbox-delivery guarantee. No additional account or hosting setup occurred.

Owner installation, port 5000, receipts, saved ads and active companion were
left untouched. Preview 5094 uses separate temporary state. No push, PR or merge.
