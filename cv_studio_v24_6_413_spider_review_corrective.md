# v24.6.413 Corrective: the blank-field review queue never ran, and the save was unsafe

Branch: `claude/ai-crawler-search-refinement`, on v24.6.412 `13f5390`.

A review of v24.6.411 and v24.6.412 found fifteen problems. Thirteen were real
and two were overstated but still worth fixing. All were reproduced against the
code before anything was changed. This corrective addresses every one of them.

Two were serious enough that the feature should not have been offered for merge.

## 1. The feature never ran at all

The queue was collected inside the scorer. The scorer never sees these
candidates, because the eligibility pass has already dropped them:

```
for item in raw_items:
    states = eligibility_filter_states(candidate)
    if active_states and all(status in {"match", "match_missing"} ...):
        eligibility_matched_items.append(candidate)
    else:
        custom_filter_excluded_count += 1     # <- blank field lands here
raw_items = eligibility_matched_items          # <- and is gone
```

A blank custom field makes its gate return "unknown", which is not in the kept
set, so the candidate is removed before ranking. The scorer branches that emit
"IT Skills not visible in JobAdder custom field" are therefore unreachable
whenever the corresponding filter is active — and they only run when it is
active. The Needs Checking tab was empty on every possible search.

**Fixed** by collecting at the point of the drop, keyed on the gate's own
verdict. `_spider_blank_fields_from_states` reads the state map the eligibility
pass already builds: any gate that actively decided against the candidate, or any
undecided gate this queue cannot repair (residential status, country, salary),
means no review row.

Because these candidates never reach resume scoring, their CVs were never
fetched. A bounded pass now reads them on the same processing deadline, and the
queue limit dropped from 60 to 24 to match what that pass can afford. A row
without a CV is useless to this feature, so the queue no longer promises more
rows than it can actually help.

## 2. The save could clear a candidate's other custom fields

This codebase already documents the hazard, in `cvstudio_ja_salary_ai.py`:

> Preserve every existing public-API custom field value while replacing/adding
> field 4. This mirrors Kano's full customFields clone and avoids clearing
> unrelated Industry/Skills/etc. values if the tenant treats UpdateCandidate.custom
> as replacement-like.

That path also refuses to write at all when the candidate GET did not include the
custom collection. The new route did neither. It sent only the field it was
filling, and in the wrong shape: a dict keyed by stringified field id, where
JobAdder and every other write in this repo use a list of `{fieldId, value}`.

So the write either failed outright while the interface reported success, or, on
a tenant with replacement semantics, cleared Currency and Residential Status on a
record it had just "only filled a blank" in.

**Fixed** with `_spider_custom_write_payload`, which clones every existing custom
field, replaces only the named ones, emits JobAdder's list shape, and returns a
refusal when the record arrived without its custom collection. The route answers
409 in that case rather than guessing. The response now reports how many fields
it preserved.

## 3. Two of the three fields had no value checking

The code comments, the commit message and the pull request all said every value
was checked against the tenant's own option list. That was only true for
Industry. IT Skills and Professional Qualifications took the other branch and
passed the text straight through, so a direct request could write any string at
all into a live record. The browser-side filter is not a control, because the
request can be made without it.

**Fixed.** `_spider_writable_field_targets` now takes the tenant's option list and
rejects anything outside it, returning JobAdder's own spelling rather than the
caller's casing. When the list cannot be read, the field is refused rather than
written — nothing is entitled to vouch for the value otherwise. The route reads
the list from `candidates/fields/custom/{id}` at write time.

## 4. The rest

- **A bare string wrote one tag per character.** `_spider_writable_field_targets('it_skills', 'SAP')` returned `{3: ['S','A','P']}`. Only a list is accepted now, and value count and length are capped.
- **Every review row showed "Candidate 48213".** The row read `card.name`; `_spider_card_fields` only ever returns salary and notice period. The search now sends the name, via the existing `_spider_preview_name` helper. The test had asserted a shape the server never produces, which is why it passed.
- **A renamed custom field read as blank and would be overwritten.** The blank check required the field's label to match a fixed list; the matching gates read by field id and ignore the label. Now it reads exactly as the gates do.
- **The candidate id went into the JobAdder path unescaped**, unlike the read path beside it. Now quoted.
- **A successful write cleared the whole resume and preview cache** for every candidate. Nothing cached is invalidated by a custom-field write: the caches hold CV text and rendered previews, the CV did not change, and candidate detail is read fresh every time and never cached. The clear is gone.
- **Blank-field detection keyed on the English wording of error messages.** Rewording a user-facing string would have emptied the queue silently. It reads the gate name now.
- **The AI batch was 20 candidates into a 1600-token reply.** A reply cut off mid-object parses as nothing, discarding a whole batch after being billed for it. Batch is 8, cap is 2000.
- **The datalist ids were duplicated** 2,670 lines from the originals in `THE_SPIDER_MULTI_CONFIG`. Read from there now.
- **A dead `usage` variable**, copy-pasted from the plan path where it drives a cost label. Removed.

Two findings were overstated and are noted rather than treated as reported: the
token cap would not have failed on every batch, and the unescaped path was not
the only one in the file. Both are fixed regardless.

## Why the tests did not catch any of this

Every test exercised a function in isolation, with fixtures I wrote to match what
I believed the surrounding code did. Where that belief was wrong the fixture was
wrong in the same direction, so the test agreed with the bug. The review-row name
test is the clearest case: it asserted `{card: {name: 'Alex Tan'}}` resolves to
'Alex Tan', which is correct code against data the server never sends.

The mutation testing I did before was real, but it only ever tested my code
against my own assumptions, so it could not catch a wrong assumption.

**The new test runs the actual search route end to end**, with JobAdder mocked at
the boundary, and asserts a blank-field candidate comes back in the queue. It
fails against the original code — I restored the defect and confirmed four tests
go red. A test at that level is the only one that could have caught the first
finding, and there was none.

Also pinned: the queue is collected before `raw_items` is replaced, ranked results
are byte-identical with and without the queue, the write preserves other fields,
the PUT uses JobAdder's list shape, a record without its custom collection is
refused, a renamed field still reads as filled, and the id is escaped.

## Tests

`tests/test_spider_blank_field_review_queue.py` — 18 tests, 16 subtests,
including 8 that drive `/jobadder/spider_search` end to end.
`tests/test_spider_apply_tags_writeback.py` — 33 tests, 20 subtests.
Frontend fixtures updated for the corrected name and option-list sources.

Seven mutations were introduced and each was caught by the test that claims to
cover it: removing the vocabulary check, restoring the keyed-object payload,
dropping the field preservation, writing without the custom collection,
re-adding the label requirement, unescaping the id, and reading the name from
card. The original collection-site defect was also restored and confirmed red.

Full suite: **1366 passed, 23 skipped**, plus the two environment-only failures
this container has always had (antiword binary absent, Windows registry
unavailable). Node fixtures: **26/26**.

## Not changed

Ranked results, ordering, scoring and the existing eligibility gates. The search
response gained two summary counters and one list; nothing existing changed
shape. The sealed route count stays at 119 — no route was added or removed by
this corrective.
