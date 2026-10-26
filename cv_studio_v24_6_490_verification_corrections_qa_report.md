# Verification and formatting corrections — v24.6.490

Local branch `codex/v24.6.490-verification-corrections` starts from the unmerged
Email Verifier checkpoint `d4fc3ff` on master `d9b91d9`. It integrates the scoped
Awards correction `23e893c` and HR correction `8733bb5` for one preview. Their
separate QA reports describe the original diagnoses and verification.

## Email outcome

The owner tested a known-valid mailbox and received the previous generic SMTP
failure message. A read-only diagnostic found the domain's public MX routing;
a bounded TCP connection to the first public mail-server address timed out.
No recipient command, message or real email address was used in that diagnostic
or committed to tests/logs. This establishes connection failure, not a missing
mailbox and not proof of which network/provider blocked it.

The existing `unknown` machine verdict remains unchanged. Its visible name is
Unconfirmed, and each result shows the independent format, mail-record and
mailbox evidence when supplied. Connection timeout/refusal, mailbox-response
timeout and TLS certificate failure have distinct fixed reasons. No raw server
exception or private address is included. This improves evidence and clarity;
it does not claim to overcome blocked SMTP or guarantee mailbox validity.

## HR and Awards integration

Modern wrapped HR cards are read only inside the recognized Primary content
region. Missing location controls before a click wait within the existing poll
budget. Native paging metadata is accepted while real company, country and
keyword changes remain rejected. HR errors identify the failing step. The
actual companion still needs updating before live use; no owner installation or
existing installed extension was changed during QA.

The Awards normalizer, Blind safety, registry and renderer tests match the
tested v488 checkpoint. A corrected copy of the supplied document was rendered
and compared there; only its Awards area changed, with all wording retained.

## Validation

- Full isolated Windows Python run: **1,847 passed, four skipped, 8,416 subtests**
  in 200.45 seconds. Receipt, database, journal, salary and credential paths were
  isolated before collection; no installed owner receipt was replaced.
- All 52 JavaScript fixture files passed. Final reader-specific and native HR
  reruns passed after limiting the new selector to Primary content.
- Five additional verifier fixtures preserve unknown verdicts and passed DNS/
  syntax evidence across connection, recipient and TLS failures. Existing
  real loopback SMTP protocol/security fixtures passed.
- Native isolated Chromium tested the actual app's invalid-format path and
  synthetic five-status results, Unconfirmed evidence, filtering, CSV export,
  module switching and a 390-pixel mobile viewport with no horizontal overflow.
- The actual isolated companion worker/reader tested ten wrapped cards, all
  eleven keywords across three groups/six pages, Any country and Malaysia,
  native URL paging flags, delayed navigation and rejection of changed filters.
- Whole-suite formatting replay, generated/hostile fixtures and deliberate
  guard mutations are retained in the v488 report. Integrated exact-master
  replay covered 1,137 captured inputs: 65 intended metadata differences, no
  content changes. All 1,032 existing registry cases remain unchanged, with
  24 additive cases. All 166,517 repository-corpus lines retained their content.
- Tracked Python/JavaScript/PowerShell/POSIX syntax, repository consistency,
  exact version surfaces, native Antiword/Tesseract owner-source preflight and
  24 source-smoke assertions passed. No protected build or native Mac claim.

The preview runs in isolated local state on port 5091. No third-party verifier,
AI/paid call, email delivery, outreach, schema migration, owner installation
edit, real saved-lead mutation, PR, push or merge is part of this checkpoint.
