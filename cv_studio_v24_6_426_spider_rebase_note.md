# v24.6.426 AI Crawler review queue: rebased onto current master

PR #214 (AI Crawler: set aside candidates dropped for a blank JobAdder field, read
their CV, and save the reviewed tag back) was written on master `960a086` as
v24.6.411–v24.6.416. Since then master has moved to `bb3b606` through PR #216
(v24.6.411–v24.6.418) and PR #217 (v24.6.419–v24.6.425), which reused those
version numbers.

## What the rebase did

- **Replayed the six commits unchanged** onto master `bb3b606`.
- **Version-only conflicts:** where the two sides of a conflict differed only in
  a version number, master's side was kept. This happened in every
  version-stamped file, including `app.py` and `index.html`.
- **Status notes:** `HANDOFF.md` and `PHASE_STATUS.md` keep both master's entries
  and this PR's entries. The salary work is now marked merged as `bb3b606`, and
  the role-qualifier fix as `960a086`.
- **One final commit** bumps every version-stamped file to v24.6.426. The
  replayed commits keep their original messages.

## Checks

- **Each replayed commit** ran its own crawler tests on the new base before the
  next one was applied. The final commit's server tests: 72 passed.
- **The crawler's net change is unchanged.** Against its old base and against
  the new one, the change is line-for-line identical in all 40 files, ignoring
  version numbers and the two status notes.
- **The route list** was untouched on master, so this PR's change (118 → 119,
  `/jobadder/spider_apply_tags`, with its recomputed fingerprint) applies as
  reviewed.
- The full suite and every page test were run on the result; see the commit and
  PR description.

Nothing in the crawler's behaviour was changed by the rebase. The limits stated
in PR #214 still apply: it has been verified against fixtures only, never a live
JobAdder tenant, so try the save on one candidate first.
