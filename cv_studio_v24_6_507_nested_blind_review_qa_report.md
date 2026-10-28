# CV Studio v24.6.507 — Preserve nested-only Blind CV layout

Corrective checkpoint on PR #258, retaining the v505 project layout correction
and v506 DNS recovery. The owner authorized fixing all findings and merging.

Hosted review of `efb3344` found one P2 issue: the Blind CV layout predicate
required a recognized heading even when the source-confirmed layout consisted
only of a parent bullet and nested children. An unchanged blinded response
therefore lost its layout hints and rendered literal lowercase-o markers again.

The predicate now accepts either confirmed headings or confirmed nested points.
Matching group/category/count, unchanged non-heading items and numeric anchors,
valid style values, provider-metadata removal and the ban on copying source
wording are unchanged. No normalizer, renderer, route, schema, DNS/SMTP behavior
or additional paid operation changes in this corrective.

New list/string cases and the real normalization → Blind CV → Node DOCX pipeline
failed three checks before the change. They now pass, including actual level-one
Word numbering without headings. Changed duty text still discards layout. The
documented C4 registry has an additional nested-only blinded case; all previous
cases remain unchanged. Focused project/guardrail/verifier checks pass (171
tests and 2,241 subtests). Final full regression: **2,038 Python tests passed,
four skipped and 8,418 subtests passed**; all **69 JavaScript fixture files**
passed. Native isolated Chromium checks normalized/blinded nested-only preview
indentation and marker removal, plus the prior heading/mobile cases. Exact
merged-v504 replay of 1,137 suite inputs has zero changes; all 1,056 previous
registry cases are unchanged with two C4 additions. The repository corpus
(171,474 lines at the checked snapshot), tracked syntax/repository consistency,
native Windows dependency preflight and all 24 source-smoke assertions pass.
The exact hosted review/merge identity is recorded in issue #35.

The supplied corrected CV has headings and is unaffected by this edge case;
its previously inspected eight-page Word output remains valid. No user document
rewrite, live provider/SMTP call, owner installation edit, protected build or
unrelated JobAdder PR #257 integration is included.
