# v24.6.410 Role-qualifier script fix

Branch: `claude/pr157-chatgpt-fix-zke4cy`.
Base: master `5b1f2a49717a1e3027e83004a08b09f629a910a5`, v24.6.409.

One finding from a review of merged master, reproduced first and found to be wider
than reported. Two further items in the same review are deliberate limits already
on record and are unchanged. The project records the review flagged are corrected.

## The finding

A role heading printed with an international location could not be placed, so the
project went to the newest promotion instead of the role the source named.

The word test in `_reads_as_qualifier_name` extracted words with `[A-Za-z]`, which
splits "São" into "S" and "o". The lowercase fragment is not a connector, so the
whole qualifier read as prose. The leading-character class `[A-Z0-9(\[]` had the
same flaw, rejecting a name that opens with a non-ASCII capital.

Reproduced on the four reported cases and on more:

```
– São Paulo   – Zürich   – Québec   – München
- Ávila       – Łódź     - Ciudad de México
```

This is the second time an ASCII-only letter class has broken this module. The
first cost the referees heading in v24.6.405.

## The fix

Words are matched as "word character that is not a digit or underscore", which is
any letter in any script. The leading-character class is gone, because the question
is "does every word read as part of a name" and that cannot be written as a
character class.

A caseless script is handled explicitly. "東京" has no uppercase form, so requiring
a capital rejected every CJK, Thai and Arabic place name. A word whose lower and
upper forms are identical counts as a name word: capitalisation cannot signal
anything in a script that has none.

Prose is still prose, including prose that contains an accented word:
"– Duties spanned the São Paulo desk" and "- Work covered the Zürich office" both
stay on the fallback path.

## Verification

- 24 international place names across Latin, Greek, Cyrillic and CJK scripts, each
  with a hyphen and an en dash: 48 subtests. All fail on v24.6.409 except the two
  whose accent happens to fall at the end of the word.
- Three accented prose forms confirm the prose path is unchanged.
- `test_no_predicate_in_this_pass_assumes_ascii` sweeps the same corpus through
  both text predicates that decide placement, because an ASCII class has now
  broken each of them once. Two of my own first-draft assertions in that test were
  wrong and were corrected rather than made to pass: the referees predicate
  promises accented spellings of the English words, not other languages' words for
  them, so "Referencias" and "Referenzen" are out of its scope.
- Complete suite: 1313 passed, 23 skipped, and the same 4 environment-only failures
  as master (antiword, waitress twice, a Windows registry test). 25 of 25 Node
  fixtures pass.
- All four v24.6.405 audit findings stay fixed, the real CV is unchanged, and the
  pass is idempotent on it.
- Launcher line endings and byte-order marks verified identical to master.

## Records corrected

`HANDOFF.md` and `PHASE_STATUS.md` described v24.6.406-v24.6.409 as unmerged and
awaiting testing; both now record PR #211 merged as `5b1f2a4`. Issue #35 is the
append-only coordination log, so its stale entry is superseded by a new comment
rather than edited.

## Observed, not changed

Two `[A-Za-z]` classes remain in `_reconcile_work_experience_with_authoritative_table`:
the `Title – Company` split and a single-letter token test. A title opening with a
non-ASCII letter ("Ökonom – Acme GmbH") would not match the split. That is a
different pass, it predates this branch, and no failure was reproduced through it,
so it is recorded as a lead rather than changed here.

## Boundaries and limitations

No routes, guards, storage schemas, dependencies or live provider behaviour change.
The AI parse prompt is untouched.

Accepting caseless words means a caseless-script fragment after a separator cannot
be told from prose in that script. The word cap and length bound are the only
limits there. Rejecting them instead would lose every CJK place name, which is the
worse trade.

Two limits from earlier versions are unchanged and were confirmed by this review as
deliberate. A clause in full title case ("- Work Covered The Regional Desk") reads
as a name and would misplace a project's role within the right employer. A block
heading with an unglyphed tail keeps its own row rather than risking the deletion of
a real job.

Linux verification is not macOS or Windows proof; protected builds remain manual.
