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

## Review correction (v24.6.407)

The job-title tail test was applied to every tail, including one carrying a bullet
glyph. A two-column competency list beside a heading is full of role nouns --
"• Executive Leadership", "• Chef Training" -- so the heading was refused and the
sub-brand stayed a separate dateless entry.

A bullet glyph already settles that the tail is a sidebar item, so all three
rejections now apply only to an unglyphed tail, which is the only case the
v24.6.404 relaxation was about. Five bullet-led fragments are covered by a new
test, which fails on v24.6.406.

## Review corrections (v24.6.408)

Three findings on the v24.6.406/407 work, each reproduced first.

- **A job title no word list would carry absorbed its job.** "Financial
  Controller", "Quantity Surveyor", "Brand Custodian", "Sommelier" and "Actuary"
  all slipped past the role-noun list, so the job was absorbed into the employer
  above and its title disappeared. The word list is deleted rather than extended:
  an UNGLYPHED tail beside a heading is now refused outright, which is the
  v24.6.403 rule. A bullet-led tail stays eligible, so the two-column case the
  pass exists for is untouched -- that CV ends the line at the heading and never
  depended on the v24.6.404 relaxation. The cost is the constructed
  wrapped-sidebar-word case, which now leaves the block on its own row: a line of
  layout rather than a lost job. A test pins that the real fixture has nothing to
  the right of its heading.
- **A null employment entry crashed /parse with HTTP 500.** The v24.6.406 group
  loop read `exp.get` without checking the entry was a dict, and master handled
  the same response. Reproduced with `None`, `""`, `[]` and `0`. The loop skips a
  non-dict entry, and nine malformed shapes are covered by a test.
- **A sentence after a separator read as a role qualifier.** "Analyst - work
  covered the regional desk" located the Analyst role and took a project with it.
  A qualifier now has to start with a capital or a digit and stay within five
  words, which keeps "- Kuala Lumpur" and "(Operations)" while rejecting prose.

Five tests cover these; all five fail on v24.6.407.

## Review correction (v24.6.409)

Capitalising the first word cleared the v24.6.408 guard: "Analyst - Work covered
the regional desk" starts with a capital, stays within five words, and was read as
a place, so the project moved under Analyst.

A leading capital was the wrong test. A place or a scope reads as a NAME, so every
word in the qualifier now has to be capitalised, bar the small connectors a name
may contain ("of", "the", "de", "bin"). "- Kuala Lumpur", "(Operations)",
"- Head of Operations" and "- Kuala Lumpur Regional Office" still work;
"- Work covered the regional desk" and "- Responsible for the reporting line" no
longer do.

Ten prose forms and nine qualifiers are covered. The prose cases fail on
v24.6.408.

The residue: a sentence in full title case ("- Work Covered The Regional Desk") is
indistinguishable from a name by any textual test and would still pass. It costs a
project's role within the right employer, never a job, and no CV has been seen
that writes a clause that way.

## Verification

- `SourceOwnershipAuditTests` in `tests/test_cv_earlier_career_collapse.py`:
  18 tests, 60 subtests. Against v24.6.405 they fail in 15 places across all four
  findings, and the negative tests pass on both versions.
- Complete suite: 1310 passed, 23 skipped, and the same 4 environment-only
  failures as master (antiword, waitress twice, a Windows registry test).
  25 of 25 Node fixtures pass.
- The real CV is unchanged: PM Brands nests under A&W Malaysia, and KGB's own
  three sub-sections stay under KGB rather than being relocated by the new pass.
  The pass is idempotent on that document.
- Of the seven source shapes held since v24.6.404, six behave as before. The
  constructed wrapped-sidebar-word shape now leaves its block standalone, which
  is the point of the v24.6.408 tail fix.
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
