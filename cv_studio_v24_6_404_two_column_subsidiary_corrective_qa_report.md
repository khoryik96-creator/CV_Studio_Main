# v24.6.404 Two-column sub-brand corrective

Branch: `claude/pr157-chatgpt-fix-zke4cy`.
Base: `debfc47` on `codex/pr210-v24.6.403-cv-source-safety`, v24.6.403.
Carries the v24.6.403 corrective forward; the four fixes below repair the
real-document regressions it introduced and keep everything it tightened.

## What regressed in v24.6.403

The real CV the sub-brand pass was written for stopped attaching, so
`PM BRANDS SDN BHD (HALO DIM SUM)` printed as its own dateless employer row
again. Reproduced against the actual pdfplumber output of the source PDF.

The mid-line corroboration rule required the one source line immediately after
the block heading to contain every word of the model's first duty. pdfplumber
interleaves a two-column layout, so that line is a sidebar fragment and the real
duty is two lines further down:

```
POS & HRIS) PM BRANDS SDN BHD (HALO DIM SUM)
• Cost Optimisation, Pricing & Margin
• Developed the business proposal and rollout plan for the Halo Dim Sum
Management
kiosk concept.
```

The whole suite was green, because the existing two-column fixture keeps the
block heading at the start of its line with the sidebar to its right. The rule
only applied to mid-line matches, so the fixture never exercised it.

## Fixes

- Mid-line corroboration looks for the duty across the block's whole source
  span, bounded by the next dated employer heading, instead of the single
  following line. A block still cannot corroborate itself with a later
  employer's duties.
- Text to the right of a heading is refused only when it carries on the same
  sentence, which is what a prose mention looks like, or when it is the block's
  own date metadata. A wrapped sidebar word arrives with no bullet glyph of its
  own and no longer refuses the heading.
- A company matched inside a referees block is skipped. A referees list names
  employers and job titles as clean headings, so such a match outranked the real
  mid-line heading and took the attachment to the wrong employer.
- When the source cannot say which promotion ran a project — an untitled role, a
  title the source never prints as a heading, two roles sharing one heading —
  the newest role of the correct employer receives it. Declining put the
  sub-brand back on its own dateless row, which is the defect the pass exists to
  remove and which shipped twice before.

Everything else in v24.6.403 is unchanged: the unique-heading preference, the
duplicate-block refusal, the source title/date guard, and the on-request
referee-statement fix.

## Verification

- `tests/fixtures/cv_two_column_sidebar_left.txt` is new: the shape pdfplumber
  actually produces, with the sidebar to the LEFT of the block heading, its duty
  split across interleaved lines, and a referees block repeating the employer
  names. Ten tests over it.
- Those tests fail in seven places against v24.6.403 and in two places against
  v24.6.402, so they pin the behaviour of neither predecessor alone. The two
  v24.6.402 failures are the prose-mention and borrowed-duty cases that
  v24.6.403 correctly tightened.
- One v24.6.403 assertion is restated: an unlocatable or duplicated role title
  now falls back to the newest role instead of leaving the block separate. Its
  replacement checks the block reaches the right employer with its bullets
  intact, and a companion test covers the single-role parent.
- Complete suite: 1291 passed, 23 skipped, and the same 4 environment-only
  failures as master (antiword, waitress twice, a Windows registry test).
  25 of 25 Node fixtures pass.
- End to end through `preview_format.py` on the real pdfplumber extraction:
  PM Brands nests under A&W Malaysia with both its bullets, KGB Holdings follows
  as the next dated employer with its three sub-sections intact, then YBS Agro
  Premiere, then Earlier Career.
- Launcher line endings and byte-order marks verified identical to master.

## Boundaries and limitations

No routes, guards, storage schemas, dependencies or live provider behaviour
change. The AI parse prompt is untouched. Verification used the real source PDF
and fixtures, not live provider calls.

A block heading whose following source line is an unexplained title or date
still keeps the block standalone, which is v24.6.403's deliberate choice and is
unchanged here. Linux verification is not macOS or Windows proof; protected
builds remain manual.

Separately observed and not addressed: a model grouping named "Early Career
(Condensed)" carrying a role title of "Earlier Career" prints both as headings.
The early-career matcher recognises only "earlier career". This reproduces
identically on v24.6.402 and v24.6.403, so it is a pre-existing gap rather than
a regression, and it is left for its own change.
