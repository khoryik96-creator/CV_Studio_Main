# v24.6.414 Corrective: who belongs in the review queue

Branch: `claude/ai-crawler-search-refinement`, on v24.6.413 `9992125`.

Two further reviews of the branch. Both agreed the write path itself now holds up:
the tenant option-list check, the blank-field guard, the preserve-every-custom-field
payload, the 409 refusal, and the id quoting are real guards, correctly ordered.
One review explicitly withdrew the earlier concern about the list-shaped `value`
and the partial `PUT` body, confirming both match existing precedent in this repo.

Every defect this round is on the **selection** side: deciding who belongs in the
queue in the first place. All were reproduced before anything was changed.

## 1. "Undecided" was read as "the field is blank"

`_spider_blank_fields_from_states` accepted any gate reporting `unknown` as proof
the field held nothing. It is not. `unknown` covers three different situations and
only one of them is a review row:

**The field really is empty.** The case the feature is for.

**The gate collapsed a mismatch into it.** `_spider_industry_match` in any-mode
returns `unknown` whenever no selection matched and at least one was undecided. A
candidate whose Industry #1 says "FMCG", searched against a selection of
"Financial Services" *and* "FSI - Insurance", produces `[mismatch, unknown]` and
collapses to `unknown`. That candidate was queued as "Industry is blank". Worse,
the save guard would not have caught it: the AI's suggested sub-category resolves
to field #2, which genuinely is empty, so the write would have gone through. A
candidate on record as FMCG could have been tagged FSI.

**The record was never read.** A failed detail fetch, an elapsed deadline, or a
candidate past the bounded `eligibility_detail_request_limit` sample leaves every
gate undecided while the fields may be perfectly well filled in.

There was also an asymmetry in the other direction. The IT Skills and
Qualifications gates filter by the field's label, which the save guard
deliberately does not, so a tenant who renamed field #3 or #7 had filled
candidates queued, a resume downloaded and AI tokens spent on them, only to be
refused at save as "already filled". My v24.6.413 docstring claimed the save guard
read "exactly as the matching gates read it", which was true of industry only.

**Fixed.** Blankness is now confirmed against the candidate record rather than
inferred from the verdict. Every field a gate consults is checked — both industry
fields, since a value in either means the candidate has an industry on file — and
read by field id alone, exactly as the save guard reads it, so the queue never
offers what the save would refuse. A record that arrived without its `custom`
collection is never queued: there is nothing to confirm against, and guessing here
writes into a live record. The docstring now says what is actually true.

## 2. A slow queue reported the whole search as partial

The review queue's resume pass called `mark_processing_deadline` on timeout, which
flips `partial_results` and `pagination_incomplete` and emits "CV Studio returned
safe partial results". The ranked results were already final before that pass
began, so a complete result set was being reported as incomplete because optional
extra work ran long.

**Fixed.** The queue pass no longer touches the search deadline. Running out of
time there marks the queue truncated and nothing else.

## 3. An expired connection became a generic 502

`_spider_fetch_candidate_detail` re-raises `_SpiderJobAdderReconnectRequired`
deliberately, and every other spider route honours it. The save route caught it
with a bare `except Exception` and returned 502, losing the `needs_reconnect`
signal that sends the user to Settings.

**Fixed.** 401 with `needs_reconnect`, matching the search route beside it.

## 4. A failing batch discarded the batches already paid for

`renderTheSpiderReviewQueue()` sat after the whole batch loop, inside the `try`.
A throw on batch 3 of 3 skipped it, so batch 1 and 2's suggestions — already on
the rows and already billed — were never shown.

**Fixed.** The queue renders as each batch lands, and again in `finally`, so
whatever happened the user keeps what was gathered. The failure message now says
how many were tagged before it stopped.

## 5. One option-list read per candidate

`_spider_custom_field_options` was called fresh on every request. Saving 24
candidates with two blank fields each meant 48 identical reads of configuration
that changes rarely.

**Fixed.** A five-minute cache keyed on the account namespace and field id, so an
account switch cannot serve another tenant's list, and cleared alongside the other
caches on account transitions. **Only a successful read is cached** — caching a
failure would lock writes out for the whole window over one momentary outage.

## Tests

`tests/test_spider_blank_field_review_queue.py` — 25 tests, 20 subtests.
`tests/test_spider_apply_tags_writeback.py` — 36 tests, 20 subtests.

New coverage, end to end where the fault was only visible there: a candidate with
a different industry on file is not offered for tagging; a candidate whose detail
never loaded is not queued; a renamed but filled field is not queued; a slow queue
does not report the search as partial; an expired connection asks for a reconnect;
the option list is read once across five saves; a failed option read is retried
rather than cached.

Seven mutations were introduced and each was caught: trusting the gate state
without checking the record, allowing a record with no custom collection, marking
the queue timeout against the search deadline, swallowing the reconnect signal,
caching a failed option read, dropping the option cache, and rendering only after
the whole run survives.

The render mutation is worth noting: my first assertion for it **passed** under
mutation, because it only checked ordering against the summary toast and moving
the call one line below the loop still satisfied that. The assertion now
brace-matches the loop body and requires the render to sit inside it. A mutation
test that passes is information about the test, not a pass.

Full suite: **1376 passed, 23 skipped**, plus the two environment-only failures
this container has always had. Node fixtures: **26/26**. Launcher line endings
match `origin/master` exactly.

## Not changed

Ranked results, ordering, scoring, the eligibility gates, and the write path
itself. The sealed route count stays at 119.
