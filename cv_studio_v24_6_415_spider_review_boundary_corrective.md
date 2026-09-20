# v24.6.415 Corrective: the browser side of the review boundary

Branch: `claude/ai-crawler-search-refinement`, on v24.6.414 `41c27ac`.

Two more reviews, 21 findings between them. Both agreed the server-side write
guards hold. Nineteen were real and are fixed; two were wrong and are recorded
below with the evidence, because a wrong finding acted on is its own defect.

## Wrong, and why

**"The PUT should send a scalar, not a list."** One review held that
`cvstudio_ja_salary_ai.py` is the only proven custom-field writer in this repo
and it sends `value: "SGD"`. It is not the only one.
`vendor/cvstudio/jobadder-upload.js:467` writes `{fieldId: 1, value: [industry]}`
against this same tenant — an array, to the very industry fields this route
writes. Both shapes exist, the reader here flattens either, and the fields this
route fills hold several tags at once. Kept as a list, with the precedent now
written into the docstring so it is not re-litigated.

**"Industry is validated against a different vocabulary in the browser."** The
browser datalist is filled from `/jobadder/spider_options?name=industry`, which
returns `cvstudio_canonical_industry_taxonomy` — the same taxonomy
`_spider_industry_filter_spec` validates against — and never reaches JobAdder's
`lists/industry`. `test_industry_options_are_local_and_make_no_jobadder_request`
already pins this. No divergence exists.

## The one that mattered

**A signed-out account's candidates stayed on screen and were saveable.**
Neither `clearTheSpiderJobAdderAccountState()` nor `clearTheSpider()` cleared the
review queue. Candidate ids are tenant-scoped, so after a sign-out or account
switch a stale row could be ticked and written against the new account's token —
into whatever record happens to carry that id there. AGENTS.md makes this a hard
rule: v24.6.243 requires sign-out and account replacement to invalidate AI
Crawler search and preview state. This missed it.

Both reset paths now call `clearTheSpiderReviewQueue()`, and the test extracts
each function body to check it. **The first version of that test passed while the
fix was removed** — a loose regex matched the call in the following function. It
brace-extracts now.

## The rest

**Server**

- A reconnect during the queue's CV reads threw away a finished, fully-paid-for
  search. The ranked results were final before that pass began; the queue is
  dropped instead and the results returned.
- `_spider_custom_field_options` did not verify the field's label, unlike the
  read path it mirrors. A tenant that repurposed custom field #3 would have had
  that field's options accepted as IT Skills values and the tag written into it.
  Now checked, and the write refused when the name does not match.
- A failed option-list read returned `ok: true` with "already filled or not
  allowed", reporting an outage as a normal no-op. Now 502 and retryable.
- A transient read failure was reported as 404 "returned no detail for this
  candidate". The fetch helper returns `None` for a timeout, a 5xx and a genuinely
  missing record alike, so it cannot claim the record does not exist. Now 502,
  and the unreachable 502 branch below it is no longer dead.
- A record carrying two entries for one field id produced two identical writes in
  one body. Written once now.
- Every refusal reported "not an allowed value", whatever the actual reason. Seven
  distinct reasons now reach the response, so hitting the value cap reads
  differently from a tag JobAdder does not offer.
- The queue's own CV reads were excluded from the declared request ceiling, and
  the cap was 24 against a resume budget of 20 while claiming to be "close to" it.
  Both corrected; the cap is now the budget.
- The row shipped `card`, which only ever held salary and notice period and which
  nothing read, and pinned the whole merged record — detail copy and all — for the
  rest of the request when only the name was needed. Both dropped.
- The CV excerpt in the search response is a deliberate widening of what that
  response carries. It is now said so in the code rather than left implicit.

**Browser**

- The id lookup for AI suggestions was built from the whole queue, not the batch
  being asked about, so a reply echoing another batch's candidate id attached
  that candidate's CV-derived tags to a row the model never saw. Every server
  guard still passes, because the value is legitimate for *someone*.
- Per-batch re-rendering, added in v24.6.414 to stop losing paid-for batches,
  wiped any tick made while later batches were still running. **That was a
  regression I introduced.** Ticks are captured and restored across a render.
- The queue concatenated every query's capped list into one unbounded list, so a
  six-query run could hold 144 rows and issue 18 paid AI calls. Capped for the run.
- A row answered in an earlier run kept its stale tick boxes when the current run
  said nothing about it, and those were saveable. Cleared per batch.
- An unparseable reply was reported as "No CV gave clear evidence for a tag" —
  indistinguishable from a genuine negative after a paid call. Now distinguished.
- The cap was applied silently on both sides. The panel now says when more were
  set aside than it is showing.

## Noted, not changed

`_spider_custom_write_payload` does duplicate the preservation logic in
`cvstudio_ja_salary_ai.py`. Extracting a shared helper means editing the salary
write path, which is outside this branch and carries its own risk; the
relationship is cross-referenced in both docstrings instead.

One review argued `_spider_blank_fields_from_states` should drop only the field
it finds filled rather than refusing the candidate. It should not. A candidate
whose industry gate collapsed a real mismatch cannot be rescued by tagging their
IT Skills — they still fail the industry gate — so queueing them spends a CV read
and AI tokens on someone who can never qualify. Refusing the whole candidate is
deliberate, and the trade-off is now documented. It does lose one legitimate case:
a candidate with only a sub-category on file whose broad industry is genuinely
blank. After the FMCG-tagged-as-FSI finding in v24.6.414, the conservative side is
the right side.

## Tests

`tests/test_spider_apply_tags_writeback.py` — 39 tests, 20 subtests.
`tests/test_spider_blank_field_review_queue.py` — 28 tests, 20 subtests.
Both frontend fixtures extended.

Twelve mutations were introduced. **Four initially survived** — the label check,
the duplicate write, the outage report, and the account clear — which is the
honest result: those fixes had no coverage until the mutation said so. Tests were
added for each and all four now fail under mutation.

Full suite: **1382 passed, 23 skipped**, plus the two environment-only failures
this container has always had. Node fixtures: **26/26**. Launcher line endings
match `origin/master` exactly.

## Not changed

Ranked results, ordering, scoring, the eligibility gates, and the server write
guards. The sealed route count stays at 119.
