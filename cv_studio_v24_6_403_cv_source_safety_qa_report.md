# v24.6.403 CV source-safety corrective

Branch: `codex/pr210-v24.6.403-cv-source-safety` (PR number provisional).
Base: master `6a454d7f2b313caa1cf7f3320aa34546744eee85`, v24.6.402.
Owner authorized the four audit fixes; no PR or merge requested.

## Fixes

- Project/sub-brand attachment prefers a unique actual heading over prose
  mentions. A weaker two-column match needs corroborating duty words. Repeated
  ambiguous matches remain standalone; children retain source order and wording.
- Multi-role employers locate the host promotion using source title headings,
  independent of the model's role order. Unlocatable or repeated titles leave
  the child separate rather than guessing the newest role.
- Source title/date lines before a block's duties prevent attachment when the
  model omitted that metadata. No title, date or employer is invented.
- Standalone on-request reference statements no longer open referee sections
  and suppress candidate contact fallback. Real reference sections still exclude
  referee contacts, even when they contain an on-request statement.

## Verification — Windows, 2026-09-10

- Focused logic and real parse-to-DOCX suite: 131 passed, 117 subtests passed.
- Complete isolated suite: 1303 passed, 4 skipped, 2911 subtests passed.
- All 24 frontend test groups and 24 live source-smoke assertions passed.
- Existing two-column source fixture, nested bullets, old date-parity cases,
  model-order permutations, retained duty text and idempotence passed.
- Real Flask `/parse` calls with mocked AI plus `/generate-docx` verify the
  corrected employer/promotion and retained standalone jobs. Contact fallback
  is tested through `/parse`, not just a helper.
- Protected-source preflight passed, including syntax, verified Antiword 1.3.5,
  Tesseract 5.5 English and adm-zip 0.6.0. Repository consistency and whitespace
  validation passed. Generated release stamps use `bump_version.py`.

## Boundaries and limitations

No routes, guards, storage schemas, dependencies or live provider behavior were
changed. Tests use synthetic contacts and mocked AI, not live candidate writes
or paid calls. No credentials or installation receipts were changed.

The protected source includes the same reconciliation module and passes its
preflight; no native protected package was compiled or smoke-tested in this
corrective. Protected builds remain manual. Windows tests are not macOS proof.
Conservative ambiguous grouping may require manual adjustment, but retains
entries instead of guessing. Passing automated tests cannot guarantee every
real-world document layout. The previously recorded adm-zip security alert is
outside these four findings and remains unchanged.
