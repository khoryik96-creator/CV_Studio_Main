# CV Studio v24.6.514 — source-bound Sourcer evidence

Local branch `codex/v24.6.514-sourcer-evidence-refs`, stacked on unmerged v513
`ec2dda3c57e3b2e6438deb0cd91b832a88e457a7`. The v513 Shiseido Apply correction
is retained; merge base remains merged v511 `44f1887` / PR #261. Separate v512
JobAdder PR #257 is excluded. No publication/merge or owner-install update.

## Report and correction

The owner reported “A claimed match has no supporting text on the observed
page” from Sourcer. That is the existing normalized exact-quotation check,
which rejects invented/paraphrased/cross-profile wording. The request ID was
not present in retained redacted logs. No raw provider/profile content is logged
or reconstructed, and no exact offending quote or benign formatting cause is
claimed as proven. The protection is kept.

New reviews select `evidence_refs` from labelled source passages instead of
generating their own quote strings. The bounded splitter retains non-whitespace
source characters in order, prefers word boundaries and caps each passage at
the existing 250-character quote limit. Profile ID plus fresh per-request nonce
and index bind each label. Full text is represented by passages, not duplicated.
The tool schema keeps the existing score/unknown/count limits and per-stage cap.

The local resolver rejects unknown, stale, cross-profile, malformed or mixed
quote/reference output. It attaches exact original strings, then invokes the
original grounding/identity/score/shape validator. Legacy quote-only responses
remain strictly validated. Invalid responses still stop and preserve previous
results/accounting; no fuzzy matching, inferred supporting fact, silent candidate
filter, partial acceptance, automatic retry or additional provider call occurs.

Public client request/result fields, names/URLs, evidence strings, provenance,
CSV, run summaries, consent, Stop/expiry/limits and billing behavior remain.
Internal references are request memory/provider data only, not persisted or
returned with results. Token usage can differ, and existing guardrails/accounting
still apply. No new route/schema, credential handling, native dependency,
permission, owner data/installation/receipt write or protected build is added.

## Verification

- Eleven new cases fail on v513 before implementation. The new test file covers
  source-ID selection, original Unicode/whitespace text, exact source coverage,
  long/dense/unbroken input bounds, request-unique labels, no duplicate full text,
  stale/cross-profile/unknown references, malformed/empty/oversized reference
  lists, mixed output, unobserved identities, immutable raw output and the
  original grounding check after resolution. Legacy fabricated quotes still fail.
- Route tests use the actual guarded Flask route with synthetic provider output,
  checking original quotes, unchanged usage/cost/result fields and exactly one
  provider attempt. Existing incomplete output/accounting/error guidance and
  prior-results/provenance/non-replay tests remain.
- Native isolated Chromium executes the actual Agent against the actual isolated
  Flask route with a synthetic provider. Plan, screen and detail use exactly
  three attempts; resolved original Unicode quotes appear on a detail-checked
  result, no internal references leak, token accounting survives and Stop settles.
  No real key, paid provider, LinkedIn account or owner records are used. The
  temporary test server is stopped after verification.

Final validation: **2,077 Python tests passed, four skipped, 8,418 subtests**;
all **74 JavaScript fixture files** passed. Syntax/repository consistency,
generated version surfaces, genuine Windows Antiword/Tesseract dependency
preflight and all **24 source-smoke assertions** passed. The isolated preview
on port 5095 serves v24.6.514 with retained separate development state. The
synthetic-provider test server on 5096 was stopped after native verification.
The v513 HR transition and concurrency/source/identity safeguards remain in
this stack. No genuine native macOS app execution or live provider test is claimed.
