# v24.6.411 AI Crawler blank-field review queue

Branch: `claude/ai-crawler-search-refinement`.
Base: master `960a0866b357db702e9cc0fdbabdfcc2e60f12ae`, v24.6.410.

First half of the smart-search work. Ranked results are untouched; this adds a
second list and an AI pass that reads the CV. Writing suggestions back to
JobAdder is deliberately a separate change.

## The problem

A JobAdder candidate carries custom fields a recruiter fills in by hand:
Industry, IT Skills, Professional Qualifications. When one is blank and a filter
selects on it, the eligibility gate drops the candidate. The recorded reason says
so outright: "IT Skills not visible in JobAdder custom field".

So picking an IT Skill silently removes everyone whose field was never filled in,
including candidates whose CV names the skill on the first page.

The CV is not the problem. Resume text is already fetched, already sits at the
front of the matching blob, and already drives the fit percentage. The gates
simply never consult it.

Years of experience already resolves this correctly: structured employment
history first, then explicit wording in the CV, and it refuses to guess from
vague phrasing such as "20 years in Malaysia". That is the precedent this follows.

## What this adds

- **A blank field is told apart from a mismatch.** `_spider_blank_profile_fields`
  returns the field keys only when every exclusion reason is a blank custom field.
  A single real mismatch alongside it returns nothing, so a candidate the source
  actively disqualifies never reaches the queue.
- **Those candidates are set aside, not discarded.** The search collects them into
  `needs_checking`, returned beside `items` and never inside it. Ranked results,
  ordering and counts are unchanged.
- **A Needs Checking tab** lists them with the blank field named and a CV excerpt.
- **One AI call per batch reads the CV and proposes the missing tag**, choosing
  from the option list JobAdder itself returned. The browser then discards any
  value not in that list, so a model that ignores the vocabulary cannot put an
  invented tag in front of a recruiter.

Residential Status is deliberately excluded from all of this. It is a legal
status, a CV is not authority for it, and inferring it would be both unreliable
and unfair. It stays a plain exclusion.

## Design notes

No route was added. The route surface is contract-sealed at 118 and the browser
already has an AI proxy with cost tracking, provider routing and the crawler
lock, so the suggestion runs through that. The server supplies a bounded CV
excerpt in the payload it already had in hand, which also avoids a second
round trip per candidate.

Nothing in this change writes to JobAdder. A test asserts the suggestion path
contains no JobAdder write call.

## Verification

- `tests/test_spider_blank_field_review_queue.py`: 14 tests, 19 subtests. Covers
  each taggable field, real mismatches, a mismatch mixed with a blank, the
  residential exclusion, malformed input, and the gate reason strings the queue
  keys on so they cannot drift.
- `tests/test_spider_blank_field_review_frontend.js`: the vocabulary filter
  (invented values dropped, casing forgiven, duplicates collapsed, list capped),
  defensive parsing of model output including fences and surrounding prose, queue
  de-duplication, and a check that every helper the new code calls is actually
  defined in the bundle.
- That last check earned its place immediately: the first draft called a helper
  named `aiRoute`, which does not exist. Nothing failed until the button was
  pressed. The test reproduces that failure.
- Complete suite: 1329 passed, 23 skipped, and the same 2 environment-only
  failures as master in this container (a missing antiword binary, a Windows
  registry test). 26 of 26 Node fixtures pass.
- Launcher line endings verified identical to master.

## Boundaries and limitations

No routes, guards, storage schemas or dependencies change. The ranked result
path is untouched.

The queue is capped and the CV excerpt is bounded, so a very large search shows a
review list rather than a second result set, and says when it truncated.

A candidate enriched from profile detail alone carries no CV excerpt and cannot
be tagged. The row says so rather than sending an empty excerpt to the model.

Suggestions are advisory and live only in the browser session. They do not affect
the search, the ranking or the profile. Making them durable is the write-back
change that follows.

Verified against fixtures and unit tests, not a live JobAdder tenant or a live
provider call.
