# v24.6.532 Sourcer Boolean/prompt/country controls and shortlist placement

2026-11-02, Asia/Kuala_Lumpur. Local unmerged checkpoint on
`codex/v24.6.532-sourcer-search-controls`, stacked on local531/4894c43 from
merged530 PR276 / `73061bcc93f7249e67d74e8e192c333c34c99aa6`.

## Owner request and behavior

Move shortlist away from under the selection checkbox. Add a user Boolean and
country filter, supporting prompt-only, Boolean-only or both; in the combined
case the Boolean drives LinkedIn and the prompt guides AI interpretation.

- The star is beside the profile name in a flex name line. Long names wrap
  inside that line while the star stays aligned beside them. The Select column
  contains only its checkbox. Functional shortlist/revision/Trash rules remain.
- Search adds Boolean (up to1000), AI review prompt (up to4000), and Country
  (From prompt / Any country / Choose country plus name). Labels remain accessible,
  no placeholders are added, controls lock during a run, and country preferences
  survive this tab's reload in sessionStorage.
- Exact user Boolean authority: outer whitespace is trimmed, but no term is
  dropped, normalized or rewritten. Straight quotes, balanced groups and operator
  placement are checked. Standard People searches retain the conservative three-
  operator cap; overbudget explicit queries fail before paid/provider work instead
  of being shortened. Recruiter retains its existing query behavior.
- Prompt-only retains AI query planning and existing generated-query narrowing.
  A chosen country or Any overrides inferred geography for filtering only; full
  review criteria remain. Raw generated-country keyword mixing is validated before
  the override, so a new selection cannot hide an invalid generated keyword clause.
- Boolean-only has no AI planning call. Its exact Boolean is the review brief.
  Boolean+prompt+explicit/Any country also skips planning. Boolean+prompt+From
  prompt makes one country/criteria call with no query field in its schema, then
  inserts the immutable owner Boolean in the plan. Profile screening/details
  still use DeepSeek under the existing explicit consent/key and request ceiling.
- Reviews receive the complete prompt and exact Boolean independently, alongside
  the selected country mode/name. Grounded evidence references, unknown fields,
  accounting, Stop and non-replay remain. Current location/native filter is not
  proof of citizenship or work eligibility; model instructions require explicit
  evidence and unknowns instead of inference from name/language/employer.
- Manual controls cannot be silently ignored by Review open search: incompatible
  combinations are rejected before spending. Native automatic country selection
  remains for normal People search; Recruiter uses its own Locations controls.

## Contracts

No new route (124 unchanged), SQLite migration, protected-vault schema change,
credential store, hosted service, retry or background worker. New run fields are
optional and appended to preserve existing positional construction. Existing
prompt-only callers keep defaults. Candidate archive brief remains the review
prompt, or exact Boolean for Boolean-only runs; full manual query/review context
is sent directly to each provider assessment. No new durable criteria schema is
claimed. Source version surfaces are generated from VERSION; backend CRLF retained.

The stack includes the separate531 loading recovery checkpoint; see its QA for
companion deadlines and independent Signed-client/status loading. App+companion
should be updated together after a future merge. Neither checkpoint is published
or merged by this task; heldPR257 remains excluded.

## Verification

- Full isolated Windows Python suite: **2345 passed,4 skipped,8418 subtests**.
  All29 new manual-search cases pass: exact user authority, no paid planning where
  unnecessary, complete prompt/context, explicit/Any/auto geography, no inferred
  eligibility instruction, malformed/overbudget refusal before spending, consent/
  key checks, Recruiter and incompatible reuse. Existing country, query-budget,
  grounding, folder, route, cancellation and accounting cases remain.
- All **85 root JavaScript fixtures** pass in the final sequential sweep.
  New UI cases cover Boolean-only and combined Starts, exact navigation,
  independent country selection, empty-country/overbudget errors before browser/
  paid work, and incompatible reuse. Existing shortlist/sort fixtures retain all
  semantic expectations with the new name-line location.
- Actual isolated Chrome + real Flask/service/protected archive + fictional
  companion/provider: five runs cover prompt-only auto country, Boolean-only
  explicit country, both auto country, prompt-only Any, and both explicit country.
  Each navigates the exact intended query, applies native country only when
  requested, and has exactly the expected plan/screen/detail call counts (13
  fictional provider calls total:3 plans and10 reviews; zero real provider calls).
- Native folder archive, selected-folder persistence, remembered country on
  reload, busy controls, shortlist toggle/save and name-line alignment pass.
  The Boolean box is compact rather than inheriting the CV editor's460px minimum.
  390px mobile has no document overflow and keeps the country field usable.
  Zero page errors. An initial inline-star layout failed the visual alignment
  assertion on long names; the flex name line corrects it and passes the same test.
- 24 isolated live-source smoke assertions pass. Source/static checks,
  repository consistency, Windows Antiword/Tesseract/adm-zip preflight and diff
  checks pass. No protected package or new macOS native claim.
- New failing cases were run before feature implementation: Boolean-only Start
  was rejected by the old required-brief rule, and the old star occupied the
  checkbox cell. Fixtures/providers contain fictional data only.

Native reproduction: start `tests/browser/sourcer_folders_server.py` on5099,
then `tests/browser/sourcer_manual_search.js` using CVSTUDIO_PLAYWRIGHT and optional
CVSTUDIO_CHROMIUM. The script requires the fictional fixture marker and blocks
non-local browser requests. Provider/key dependencies are replaced before serving.
Ignored evidence: runtime/audit529/python532-full.log, javascript532.log,
native532-manual.log, smoke532.log, preflight532.log, consistency532.log and
screenshots under runtime/sourcer532. No private user/candidate content is in QA.

## Limits

No live LinkedIn query or paid DeepSeek request is made. Fixtures prove routing,
criteria/authority, provider-call counts and rendering, not a live model's quality
or LinkedIn layout acceptance. Country is a search filter, not proof of nationality
or work eligibility. Standard explicit Booleans beyond the existing budget need
manual simplification or Recruiter; they are never silently changed. Update531's
manifest timeout also requires an updated companion. Owner installation/data,
installed extension and hosted Apollo broker are unchanged.
