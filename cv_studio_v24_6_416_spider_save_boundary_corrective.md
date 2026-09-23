# v24.6.416 Corrective: the save boundary

Branch: `claude/ai-crawler-search-refinement`, on v24.6.415 `6fe7d9c`.

Two reviews, eight distinct findings. All eight were real and are fixed. **Three
were regressions I introduced in v24.6.415** while fixing the round before it.

## The three I caused

**A finished save re-enabled itself.** v24.6.415 added a deferred tick-restore so
that per-batch rendering would not wipe what the recruiter had ticked. The save
path renders at the end and then disables the button — but the restore is on a
`setTimeout(…, 0)`, so it lands *after* that, putting the ticks back and
re-enabling the button holding the values just written. One click from a second
round of live PUTs, each overwriting its row's "Saved to JobAdder" note with
"Nothing written; the field was already filled".

Rendering now takes a `preserveTicks` flag. Batch rendering keeps them; a
completed save does not.

**The run-wide cap dropped rows silently.** v24.6.415 capped the queue for the
whole run, but applied it by slicing before `setTheSpiderReviewQueue`, so the
truncation flag inside that setter could never fire — and the sliced-off rows
set nothing. Three twenty-row responses lost twenty rows with no notice, directly
contradicting the comment beside it. The test covered a path no caller takes.

The search loop now compares what arrived against the room left and sets the flag
itself. The test asserts on the production path.

**An 800-character excerpt could not answer the question.** The prompt asks what
industry, skills and qualifications the CV shows. 800 characters is the name,
address and phone number. A paid batch call would routinely come back saying the
CV does not say, while the forwarded text was mostly a contact header. Raised to
4000, which is what this file already sends for the same kind of question
elsewhere.

## Account isolation, again

**The save loop had no account guard.** `applyTheSpiderTagsToJobAdder` captured
its id list once and then awaited one POST per candidate with no re-check. A
sign-out or account switch mid-loop leaves the remaining writes pointing this
account's candidate ids at a different tenant's records — the exact hazard
`clearTheSpiderReviewQueue()` exists for, and the class AGENTS.md closed in
v24.6.243. `runTheSpiderJobAdderSearch` guards every await; this loop, which
writes, did not.

Both loops now capture the run sequence and re-check it before each iteration and
after each await. The save stops, says how many it wrote, and clears the stale
rows. `suggestTheSpiderTagsFromCv` gets the same guard, because each batch there
is a paid call for rows nobody is going to be allowed to save.

## The rest

- **Industry skipped field verification.** Its values come from a local taxonomy,
  so it never read the field definition — but fields #1 and #2 are JobAdder's and
  as capable of being repurposed as #3 and #7. On a tenant with field drift the
  reviewed tag landed in an unrelated blank field. Verified now, like the others.
- **An unnamed field definition was taken on trust.** The check only fired when a
  label was present, so a definition with no name passed. `/jobadder/spider_options`
  requires a positive match; so does this now. Absence of contrary evidence is not
  evidence.
- **An outage hid behind a partial success.** `if unreadable_fields and not
  skipped:` reported an unreadable option list only when it was the sole outcome.
  One already-filled field alongside a failed read came back 200 `ok` with
  "Every field was already filled or held a value outside the allowed list" — the
  exact misreport the comment beside it claims to prevent. Now reported whether or
  not something else was skipped, and a partial write names the field it could not
  use.
- **A permanent condition was returned as retryable.** A renamed field came back
  502 `retryable: true` with "Try again in a moment", so a recruiter would retry
  forever. Renames are now 409 with `retryable: false` and a sentence saying it
  will not fix itself.

## Will this regress anything?

Every fix was mutation-tested: the fix was deliberately reverted and the suite
re-run. Ten mutations, **two initially survived** — the excerpt length, which
nothing pinned, and the suggest loop's guard, where my assertion checked that the
run-sequence variable was *mentioned* rather than that it guarded anything. It
passed with both guards deleted. Both assertions were strengthened and both
mutations now fail.

The behaviour changes that could bite, stated plainly:

- **A tenant that renamed Industry, Industry Sub-Category, IT Skills or
  Professional Qualifications will now be refused the write** where before it
  would have gone through. That is the point of the fix, but it is a real change:
  if your JobAdder names those fields differently, saving will return 409 and say
  so. The accepted spellings are in `SPIDER_INDUSTRY_FIELD_LABELS` and
  `SPIDER_WRITABLE_FIELDS`.
- **Industry saves now make one extra JobAdder read** the first time each field is
  used, cached for five minutes per account.
- **The search response is larger**: up to 20 rows × 4000 characters of CV rather
  than 800. The AI prompt grows with it, eight rows per call.
- Nothing else changed shape. Ranked results, ordering, scoring, the eligibility
  gates and the write payload are untouched, and the route count stays at 119.

Full suite: **1387 passed, 23 skipped**, plus the two environment-only failures
this container has always had. Node fixtures: **26/26**. Launcher line endings
match `origin/master` exactly.

## Tests

`tests/test_spider_apply_tags_writeback.py` — 43 tests, 20 subtests.
`tests/test_spider_blank_field_review_queue.py` — 29 tests, 20 subtests.
Both frontend fixtures extended, including the save-completes-disabled case, the
mid-batch account switch, and the surfaced partial-failure notice.

One fixture correction worth recording: the existing tests returned field
definitions with no `name`, which JobAdder does not do. The stricter check caught
that immediately — nine tests failed until the fixtures were made realistic. The
fixture was wrong, not the code.
