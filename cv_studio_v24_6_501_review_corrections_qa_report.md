# v24.6.501 — email/LinkedIn review corrections

Owner-authorized corrective and merge from `b2d3637` (v500), retaining unmerged
v498/v499 on merged `ff722b3` (v497). Branch:
`codex/v24.6.501-review-corrections`.

## Three findings corrected

1. Documented Microsoft DBEB rejection punctuation is accepted, including a
   terminal period before an AS/diagnostic suffix. Provider, permanent reply
   code, enhanced code, exact phrase and word boundaries remain. Wrong-provider,
   temporary, glued-word and double-period replies remain unconfirmed.
2. Each mailbox check uses one random control identity across its bounded
   connections and a delayed retry. An opaque HMAC reference binds canonical
   email, nonce and a four-hour expiration to the current process. Invalid,
   tampered, expired, cross-address/process and quick-mode references fail
   before DNS. New requests require no extra field; response/request additions
   are optional. No mailbox/token cache, persistent job, credential or schema
   was introduced. Reference expiry/restart fails visibly and preserves results.
3. A semantic paragraph that also matches the structural title detector counts
   once by element identity. Two distinct title elements still fail ambiguity
   checks. Foreign employers/jobs, description and sidebar guards remain.

Automatic retry bounds/spacing, Stop, original-result preservation, domain/global
concurrency and 25-second per-request deadlines remain. HR same-address retries
retain context; edits/account clearing invalidate it. CSV omits retry context.

## Regression evidence

The new backend cases initially failed on v500 (16 failures) for punctuation,
missing retained control identity and missing context validation. The browser
transport assertion also failed before implementation. Existing ambiguity tests
now use two distinct DOM elements rather than an impossible duplicate reference
from one querySelectorAll, preserving their original safety expectation.

Focused fixtures cover recipient/control punctuation, simulated 120-second
recipient greylisting, one control across four sessions, malformed/tampered/
expired/wrong-address/process/quick-mode references, preserved local-part case,
public destinations, bounded control IDs and non-exported/cleared browser state.
All prior verifier, HR and account-isolation fixture expectations remain.

Native Chromium drives the actual app and real verifier engine through an
isolated synthetic SMTP oracle. The automatic two-minute UI retry sends the
same signed context and resolves a deferred control when Microsoft replies with
its punctuated rejection. HR prefill, explicit same-address retry, disconnect,
manual input, CSV, previous evidence and mobile layout checks pass. All mail/
provider responses are controlled; no real mailbox or Apollo request occurs.
The same real semantic-paragraph DOM fails with the unmodified v500 reader and
passes with v501. Existing separate controlled loopback SMTP parser tests remain.

Sealed local validation: **1,956 Python tests passed, 4 skipped; 8,416 subtests**.
All **67 JavaScript fixture files pass**, plus tracked Python/JavaScript/
PowerShell/shell syntax, repository consistency, Windows x64 source/native
preflight and **24 source-smoke assertions**. Verified Antiword and Tesseract
remain functional. No protected compilation or colleague package was produced.

## Preserved boundaries and delivery

All 122 routes/five guards/schema versions/credential and paid-operation gates
remain. No DATA/AUTH/VRFY/EXPN, outgoing message, live recipient probe, external
verifier, hosting setup, account/history connection, Apollo activation or new
browser permission. HMAC references and engine keys are not durable, exported
or stored with ad/HR records; raw SMTP replies and real recipient data remain
excluded from QA/logs. Existing owner installation, port 5000, receipts, saved
records and active companion are untouched. Preview 5094 is isolated.

The final PR, exact tested head, hosted checks/review and merge SHA are recorded
in coordination issue #35. Catch-all uncertainty, network limits and lack of
real-world accuracy calibration remain; no broader accuracy claim is made.
