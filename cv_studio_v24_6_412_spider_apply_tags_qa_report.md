# v24.6.412 Saving a reviewed AI Crawler tag into JobAdder

Branch: `claude/ai-crawler-search-refinement`.
Base: v24.6.411 `b52a865`, itself on master `960a0866b357db702e9cc0fdbabdfcc2e60f12ae`.

Second half of the smart-search work. v24.6.411 set aside candidates dropped only
because a JobAdder field was blank and proposed a value from the CV. Those
proposals were read-only: a recruiter still had to retype them into JobAdder.
This adds the save.

## The problem

The suggestion and the field it belongs in were both already on screen, and the
only thing left was a person copying one into the other by hand, once per
candidate. That is where the work was actually being lost.

A save is not a symmetrical change, though. Everything up to this point could be
wrong without cost: a bad suggestion was ignored and forgotten. A write lands in
a live candidate record that other people read and act on, so the two risks worth
designing around are a model inventing a value the tenant does not use, and a
save quietly replacing something a colleague had already filled in.

## What this adds

- **A tick box per suggestion, unticked.** Nothing is selected by default, so
  every value written was chosen deliberately rather than inherited from the
  model's output. The Save button stays disabled until something is ticked and
  names the count it is about to write.
- **`/jobadder/spider_apply_tags`**, a guarded POST that writes one candidate.
- **The candidate is re-read before every write.** The review queue was built
  earlier in the search; somebody may have filled the field in since. The
  decision uses a fresh read of the record, never the queue.
- **A blank field is the only thing that is ever filled.** A field holding
  anything at all is skipped and reported as skipped. There is no overwrite path
  and no force flag.
- **Every value is checked against the tenant's own option list, on the server.**
  `_spider_writable_field_targets` resolves a requested value through the same
  canonical taxonomy the filters use, and rejects anything outside it. Industry
  is resolved per value, because a broad category belongs to custom field #1 and
  a sub-category to #2.
- **Only three fields are writable at all**: Industry, IT Skills, Professional
  Qualifications. Residential Status is never inferred from a CV, so it is not in
  the writable map and a request naming it is refused whole.
- **Each candidate is posted separately**, so one failure does not cost the rest
  of the batch. Failures are reported per row rather than as one summary.

## Why the guards are on the server

The browser already filters suggestions against the option lists it loaded. That
filter is a convenience, not a control: the request can be made without it. Both
the vocabulary check and the blank-only rule are therefore enforced again in the
route, which is the only thing standing between a model's output and a live
record. The browser-side filter stays because it keeps a bad suggestion off the
screen in the first place.

## What is unchanged

Ranked results, ordering, scoring, counts and the existing gates are untouched.
No existing route changed behaviour. `_spider_blank_profile_fields`, the queue
and the suggestion pass are as shipped in v24.6.411.

## The sealed route contract

The route count moved 118 → 119 and the route digest was recomputed, both
deliberately and in the same commit as the route itself. That is the mechanism
working as intended: a new route cannot appear without a visible bump here.
`tests/test_spider_apply_tags_writeback.py::RouteContractTests` pins the new
count so a later accidental revert fails rather than passes.

## Tests

New:

- `tests/test_spider_apply_tags_writeback.py` — 16 tests, 11 subtests. The
  resolver per field, industry choosing its own field, a value outside the
  taxonomy rejected, an unwritable field refused whole, blank told apart from
  filled; then the route: a blank field filled with the exact PUT body asserted,
  a filled field never overwritten with nothing sent at all, a bad value never
  reaching JobAdder, a good value written while a bad one beside it is dropped,
  the candidate re-read before every write, and the 400/401/404 refusals.
- `tests/test_spider_apply_tags_frontend.js` — the tick collection, the button
  state, one request per candidate carrying only that candidate's ticks, an
  unticked suggestion never leaving the browser, a server that wrote nothing
  reported as such rather than as success, and one candidate failing without
  taking the batch down.

Each new test was checked against a deliberately broken copy of the code rather
than trusted for passing. Removing the tick check, sending the whole batch to
every candidate, aborting on the first failure, overwriting a filled field and
writing an invented industry anyway were each introduced in turn, and each was
caught by the test that claims to cover it.

Full suite: **1345 passed, 23 skipped**, plus the two environment-only failures
this container has always had (`antiword` binary absent, Windows registry
unavailable). Node fixtures: **26/26**.

Launcher line endings verified against `origin/master`: `START_HIDDEN.vbs`
242/242, `WATCHDOG.vbs` 89/89, `BUILD_PROTECTED_WINDOWS.bat` 37/37 CRLF, no BOM.

## Worth knowing

- A write is one PUT per candidate, not one per field: all of a candidate's
  newly-filled fields go in a single `custom` payload.
- The resume text cache is cleared after a successful write, because the queue
  was built from the pre-write profile and is now stale.
- The route is not retried on failure (`safe_to_retry=False`, `retries=0`). A PUT
  that may or may not have landed should be repeated by a person who can see the
  record, not automatically.
