# CV Studio v24.6.508 — Sourcer assessment output and recovery guidance

Local branch `codex/v24.6.508-sourcer-assessment-output`, from merged v507
`8c99a3da724091b32331767f8302eb9c8ff4495c` / PR #258. No publication/merge.

## Report and root-cause boundary

The owner reported an incomplete-assessment error after five search-card
results were successfully scored. The actual exception is raised by the local
assessment validator for missing/malformed/oversized evidence or unknowns.
That branch follows a provider response; it does not test the key. The provided
request ID was not present in the existing redacted runtime log, and raw AI or
profile data is intentionally not logged. The exact rejected field is unknown.

The schema sent to the provider did not state the validator's item-count,
text-length or score limits. Output could fit that requested schema yet fail
the next deterministic step. The generic error classifier then inferred a
provider failure from the word DeepSeek and appended API-key recovery advice.

## Correction

- Declare existing score 0–100, evidence 1–4, unknowns 0–6 and 250-character
  item bounds in the review schema; shared constants drive schema/validator
  list/text limits. Supply the existing stage candidate maximum per request,
  without mutating the shared schema. Explicitly omit a candidate with no
  supporting quote instead of inventing evidence to fill a field.
- Use a dedicated `SourcerResponseError` for invalid review or unexpected tool
  output. The route preserves legacy error/accounting fields and supplies the
  additive structured error code/action. The transport explains that found
  results remain and no request was retried automatically. Actual key/auth
  guidance remains unchanged; the global error classifier is untouched.
- Preserve exact source grounding, observed IDs, duplicate/score checks, all
  existing validator limits, token/cost accounting and conservative usage flags,
  request/Stop/browser limits and paid non-replay. Do not truncate unknowns or
  quotes, accept partial malformed output, synthesize facts, upgrade prior card
  provenance or continue automatically after a failed assessment.

## Verification

- Fifteen new checks failed on merged v507 before implementation. New tests
  cover schema/validator agreement, screen/detail maximums, immutable shared
  schema, every malformed assessment shape, invalid IDs/scores/unmatched quotes,
  boundary-valid output, empty unknowns/candidates, one paid attempt, retained
  accounting and correct request-correlated route guidance. Genuine auth
  failures retain the settings action.
- Focused Sourcer/domain/route checks pass. The synthetic frontend uses the
  real agent and transport: a detail failure retains earlier search-card scores,
  never marks them detail-checked, makes no retry or Next action and performs
  normal stop/owned-tab cleanup.
- Native isolated Chromium consumes a failure from the actual isolated Flask
  route and executes the actual transport/agent. It verifies retained results,
  correct guidance/correlation and no paid replay. No real browser profile,
  LinkedIn account, API key or paid transport is used.

Final broad validation: **2,055 Python tests passed, four skipped, 8,418
subtests passed**; all **70 JavaScript fixture files** passed. Tracked source
syntax/repository consistency, exact version surfaces, genuine Windows
Antiword/Tesseract dependency preflight and all **24 source-smoke assertions**
passed. The isolated preview on port 5095 serves v24.6.508 using its retained
development state. Final checkpoint identity is recorded in issue #35.

No real provider response/profile content entered Git, fixtures or diagnostics;
no live provider/key probe, new route/storage schema, owner installation/receipt
write, protected build or unrelated JobAdder PR #257 integration occurred.
