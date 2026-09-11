# v24.6.406 Source-ownership audit corrective

Branch: `claude/pr157-chatgpt-fix-zke4cy`.
Base: master `7f2553822ea3bca7aae252b97c4bc9df4a5b40c9`, v24.6.405.

Four findings from an audit of v24.6.405, each reproduced against the module
before being fixed. Two further items in the same report are addressed below
under "Reported and not changed".

## Findings, reproduced

| # | Finding | Reproduced result on v24.6.405 |
|---|---|---|
| 1 | The model already nested the block under the wrong employer | PM Brands under KGB Holdings |
| 2 | A role heading printed with a place after it cannot be placed | an older project under the newer Director role |
| 3 | An employer printing its title on the same line reads as sidebar | a whole job absorbed and deleted |
| 4 | A referees section cuts the document to its end | employers below it unreachable |

## Fixes

- **A nested group is re-read from the source too.** The attach loop only ever
  inspected top-level entries, so a block the model had already filed under an
  employer got no correction at all. Groups now go through the same ownership
  question, on the same evidence: a single located heading, sitting under a
  different employer than the one holding it. A group the source places inside
  its current host, or cannot place at all, stays exactly where it is. The move
  carries the group whole, so no bullet is rebuilt or lost.
- **A role heading keeps its heading status through a qualifier.** "Analyst -
  Kuala Lumpur", "Manager (Operations)", "Director | Group" are the same role.
  Previously only an empty, bullet-led or date tail counted, so a role the source
  prints this way was unplaceable and the fallback handed its project to the
  newest promotion. Prose continuing past the title still disqualifies it.
- **A job title on the employer's own line is metadata, not sidebar.** v24.6.404
  relaxed the tail rule so a wrapped two-column sidebar word would not refuse a
  heading. That also let "BETA SYSTEMS SDN BHD Senior Manager" through, and a
  model that dropped the title left the entry looking untitled, so a real job was
  absorbed into another employer and vanished. A tail carrying a role noun is
  refused again; a sidebar wrap such as "Management" or "Development" is not a
  role noun and still passes.
- **A referees section now ends.** It was treated as a cut running to the end of
  the document, so a CV that puts referees part-way through lost every employer
  below them. The section ends at the next recognised section heading. A trailing
  referees block still runs to the end, and a company named inside one is still
  skipped.

## Verification

- `SourceOwnershipAuditTests` in `tests/test_cv_earlier_career_collapse.py`:
  13 tests, 30 subtests. Against v24.6.405 they fail in 15 places across all four
  findings, and the negative tests pass on both versions.
- Complete suite: 1305 passed, 23 skipped, and the same 4 environment-only
  failures as master (antiword, waitress twice, a Windows registry test).
  25 of 25 Node fixtures pass.
- The real CV is unchanged: PM Brands nests under A&W Malaysia, and KGB's own
  three sub-sections stay under KGB rather than being relocated by the new pass.
  The pass is idempotent on that document.
- The seven source shapes held since v24.6.404 all behave as before.
- Launcher line endings and byte-order marks verified identical to master.

## Reported and not changed

**Duplicate "Early Career (Condensed)" / "Earlier Career" headings.** The owner
reviewed this and chose to leave it. The cause is recorded in the v24.6.404
report: the model puts the source heading in the company field and a second one
in the role title, and the collapse pass declines to regroup a single entry.

**Core Competency renders as a comma-separated paragraph.** Confirmed, and no
information is lost. It is not safely fixable by splitting the line, because two
of this CV's own competencies contain commas:

```
Business Systems Implementation (ERP, POS & HRIS)
Cost Optimisation, Pricing & Margin Management
```

Splitting on commas turns ten competencies into twelve fragments, two of them
cut in half. The source cannot be used to re-split them directly either: the
sidebar is interleaved into the experience column and wrapped mid-phrase
("• Cost Optimisation, Pricing & Margin" on one line, "Management" three lines
later with body text between).

A sound version exists and is worth its own change: at parse time, where the
source text is available, split at a comma only when the text following it begins
a bulleted source item. That distinguishes the two cases above from the eight
genuine separators. Shipping a bracket-aware comma split without that anchor
would mangle the second line, so it is deliberately not included here.

## Boundaries and limitations

No routes, guards, storage schemas, dependencies or live provider behaviour
change. The AI parse prompt is untouched. Verification used the real source PDF
and fixtures, not live provider calls.

The role-lookup fallback is unchanged: when the source genuinely cannot say which
promotion owns a project, the newest role of the correct employer still receives
it. Finding 2 removes the common reason the source could not say, it does not
remove the fallback. A block heading whose following source line is an unexplained
title or date still keeps the block standalone.

The relocation pass acts only when the source uniquely places a name under a
different employer. A CV that never prints a nested group's name as a locatable
heading gets no correction, by design.

Linux verification is not macOS or Windows proof; protected builds remain manual.
