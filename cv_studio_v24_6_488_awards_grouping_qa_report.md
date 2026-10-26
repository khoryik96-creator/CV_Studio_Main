# Awards grouping corrective — v24.6.488

Local branch `codex/v24.6.488-awards-grouping`, base master `d9b91d9`.

The supplied original uses an unmarked company and four years above four
award descriptions. The formatted document gave all nine paragraphs the same
native bullet. The existing source-confirmed contribution rule did not cover
this Awards structure. The bounded new Awards rule annotates headings only
after the complete existing item sequence aligns with a unique source section.
No wording, ordering, source company identity or item representation changes.
Blind metadata is rebuilt only from the returned visible text.

Validation:

- Full isolated Windows regression: 1,788 passed, four skipped, 8,415 subtests.
- All 48 JavaScript suites passed, including preview heading/list rendering.
- Exact-master replay: 1,136 distinct synthetic suite inputs; 65 intended
  heading-metadata differences, all other content identical.
- All 1,032 previous registry cases unchanged; 24 additive cases. The extra
  unmatched-source-tail case was added when deliberate mutation exposed a
  missing negative fixture. Final guardrail/awards rerun passed.
- 200 generated legal-name/list-shape cases, Unicode, idempotence, source-free
  export, hostile scan bounds and privacy fixtures passed.
- Repository corpus: 165,424 nonempty source/test/documentation lines produced
  no unintended heading or content change under hostile single-item inputs.
- Eight in-memory guard mutations and one Blind source-copy mutation were all
  detected; no mutated source was saved.
- Tracked-language syntax, repository consistency, owner-source Windows
  preflight, genuine pinned Antiword/Tesseract checks and 24 smoke assertions
  passed. No protected package or native macOS claim.

A separate corrected copy of the supplied formatted DOCX was produced. Only
five company/year paragraph styles changed; all wording, four native award
bullets and other ZIP members were preserved. Both versions were rendered by
the official hash-verified LibreOffice 26.8.1 runtime extracted into ignored
workspace QA storage, without a global installation. Both have six pages.
Pixel comparison proved pages 1–4 and 6 identical; page 5 differences are bounded
to the Awards area. The changed area was visually inspected. Originals were
not overwritten; user document content and paths were not added to Git.

No live AI/paid call, schema/route change, owner installation edit, PR, push or
merge is included. The separate unmerged Email Verifier v487 was preserved.
