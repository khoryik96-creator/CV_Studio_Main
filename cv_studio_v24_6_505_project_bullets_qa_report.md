# CV Studio v24.6.505 — Project Experience bullets

Local source checkpoint on `codex/v24.6.505-project-bullets`, based on merged
v504 `8d0e8dc6331aba48efec1aaaeda875ad6e5d3691` (PR #256). Not published or merged.

## Reported defect and cause

A source CV has dated project/client headings, role/team labels, duty bullets
and two nested circle-marker points. The provider preserved their words as one
Additional Information / Project Experience items list. The existing additional
info renderer treated every item as an ordinary bullet. The older explicit
project reader handles a different marked-project layout under work roles, so
it cannot repair this additional-info list. Lowercase-o children also remained
literal text beside the generated bullet.

## Bounded correction

- A unique Project Experience source section and matching items group can
  receive optional text-free positional `item_layout` hints. Dated Project/Role
  headings, or unmarked company followed by dated title, need an exact adjacent
  match of heading, role and first duty. Repeated role labels remain supported
  through their unique project heading. A marked legacy date/title line is
  supported; an ordinary marked role description is not promoted.
- Lowercase-o children require a unique marked source parent and consecutive
  matching existing child items. Wrapped lines and Symbol-font PDF bullets are
  recognized. Native Unicode identity is retained; distinct non-Latin names
  never collapse into the same ASCII-only key.
- No item wording, order, category or list/string representation is changed.
  Preview and Word render confirmed headings bold/unbulleted with keep-next in
  Word; confirmed children receive true level-one numbering/indentation and
  lose only the baked lowercase-o marker. Uncertain or unsupported groups keep
  their existing behavior. Existing contribution/award hints remain separate.
- Source-backed rechecks clear stale hints. Source-free export retains them.
  Blind CV discards provider metadata and rebuilds only text-free positions
  with matching group/count, unchanged duties and numeric anchors. Malformed
  original hints fail closed rather than raising a type error.

## Verification

- Five new checks failed on v504 before the implementation. The final focused
  suite covers arrays/newline strings, repeat export, duplicate source/groups,
  missing/reordered/marked labels, wrapping, five marker types, repeated roles,
  ambiguous parents, Unicode names, section boundaries, hostile input, blinded
  correspondence and malformed data. The real Node DOCX generator is inspected
  for unbulleted bold keep-next headings and level-one nested numbering.
- All 1,056 prior registry cases are unchanged, with one new documented C4 case.
  Replay of 1,137 captured suite inputs against exact merged v504 has zero
  changes. The repository line corpus (over 171,000 nonempty code/test/doc lines)
  has no unintended content/layout changes.
- Twelve deliberate in-memory breaks of source uniqueness, marked headings,
  adjacent-role proof, stale clearing, section boundaries, duplicate parent
  detection, nested layout, Unicode identity, blinded provider-hint removal,
  duty/date anchors and malformed-hint validation were all caught by tests.
- All 69 JavaScript fixture files pass. Native isolated Chromium exercises the
  actual preview function, repeated role labels, heading/duty counts, nested
  indentation, marker removal, escaping and a 390px viewport without overflow.
- The supplied output was corrected separately, retaining all wording/order
  except the two baked circle markers, with 56 heading lines and two true nested
  points. The original remains byte-for-byte unchanged. Word exported an
  eight-page PDF; every rendered page was visually checked. The packaged
  LibreOffice renderer was attempted first but is unavailable in this Windows
  runtime, so installed Word was used through a separate 32-bit automation
  instance. That instance was closed; the user's existing Word document stayed
  open and untouched. No real CV text or document entered Git/test fixtures.
- Tracked source syntax, repository consistency, exact version surfaces,
  genuine Windows Antiword/Tesseract dependency preflight and 24 source-smoke
  assertions pass. No protected compilation or native macOS claim.

Final full regression: **2,006 Python tests passed, four skipped, 8,417 subtests
passed**. The final replay also covers the updated repository corpus; its log
is retained locally with the ignored QA intermediates. The isolated preview on
port 5095 serves v24.6.505 with the retained isolated development state.

No AI/provider/SMTP call, external verification, remote data mutation, route or
storage-schema change, owner installation/receipt edit, PR or merge is included.
