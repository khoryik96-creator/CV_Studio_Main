# CV Studio — CV Formatting Pipeline Notes

Scope: **the CV formatting pipeline only** (source document → parsed JSON →
formatted DOCX). For everything else (server, versioning, JobAdder, etc.) see
`HANDOFF.md`.

CV Studio is a Flask app the owner runs locally at `localhost:5000`, using
DeepSeek for AI. Current version is tracked in the repo-root `VERSION` file.

## The pipeline (source doc → formatted DOCX)

1. **`/extract-text`** (`app.py`) — pulls raw text from the upload: `pdfplumber`
   for PDF and verified `antiword` first for legacy `.doc`. If the verified
   runtime rejects only that document, an optional installed Microsoft Word
   (Windows) or LibreOffice converter may create a temporary macro-free DOCX;
   CV Studio validates it and reuses the normal DOCX table/list extractor. A
   converter never bypasses a missing or untrusted Antiword runtime, including
   an execution-time trust failure. Word link updates are disabled before the
   untrusted input opens, and failed/timed-out converter process trees are
   terminated. OCR
   (`pytesseract` + poppler) remains the scanned-file fallback.
2. **`/parse`** (`parse_cv` in `app.py`) — an AI call (DeepSeek/Claude via
   `call_llm`, using `SYSTEM_PROMPT`) turns raw text into structured JSON:
   `{candidate, work_experiences[roles[bullets]], education, certifications,
   skills}`. Then a **deterministic post-processing chain** runs (order matters),
   in `parse_cv`:
   - `_correct_mistagged_candidate_name`
   - `_reconcile_work_experience_with_authoritative_table`  ← **riskiest** (see below), in `cvstudio_cv_reconcile.py`
   - `_order_same_company_roles_newest_first`
   - `_restore_explicit_project_headings`
   - `_collapse_incomplete_earlier_career`
   - `_clean_candidate_languages_from_redaction` / `_normalize_candidate_languages`
   - **`_normalize_cv_structured_content`** ← where most bullet fixes live, in `cvstudio_cv_normalize.py`
   - `_normalize_cv_data_for_output`
3. **`/generate-docx`** (`app.py`) — re-runs `_normalize_cv_structured_content`
   and `_normalize_cv_data_for_output`, then calls **`generate.js`** (Node +
   `adm-zip`) which fills `template.docx`. `generate.js`'s `smartTokenCase` does
   company/title casing.

## The one root-cause pattern behind almost every formatting bug

### Source ownership and referee boundaries (v24.6.403, v24.6.404)

`_attach_untitled_subsidiary_entries` must not trust the first name mention or
the model's first role. A child block needs a unique source heading followed by
its duties; weaker mid-line/two-column matches also need matching duty words.
Unexplained title/date metadata or ambiguous headings leave the block separate.
These guards are conservative: uncertain grouping preserves the original entries
and wording.

**Look for a two-column block's duty across its whole span, never on the next
line.** pdfplumber interleaves the sidebar into the main column, so a block's own
duties arrive on non-adjacent lines with sidebar fragments between them. The line
immediately after a mid-line heading is a sidebar fragment, not the duty. The
evidence span runs from the heading to the next dated employer heading, which is
also what stops a block borrowing a later employer's duties. For the same reason,
text to the right of a heading only disqualifies it when it carries on the same
sentence — a wrapped sidebar word arrives with no bullet glyph of its own.

A referees list names employers and job titles as clean headings, so a company
matched inside one outranks the real mid-line heading on looks alone. Matches at
or after the referees block are skipped.

For promotions, source role headings select the host role. When the source cannot
say, the newest role of the correct employer takes the block: the employer is the
part that matters, and declining puts the sub-brand back on its own dateless row,
which is the defect the pass exists to remove. A role heading keeps its heading
status through a trailing qualifier -- "Analyst - Kuala Lumpur", "Manager
(Operations)" -- or that fallback fires far more often than it should.

**Ask the ownership question of groups the model already nested, not only of
entries.** The pass began by inspecting top-level entries alone, so a model that
had already filed a sub-brand under the wrong employer got no correction at all.
A nested group moves on the same evidence an entry does, and only when the source
uniquely places its name under a different employer than the one holding it.

**A bullet glyph is the only thing that makes a tail sidebar text.** An unglyphed
phrase on the employer's own line is refused. "BETA SYSTEMS SDN BHD Financial
Controller" is an employer printing its own title, and a model that dropped that
title leaves the entry looking untitled -- absorbing it deletes a whole job and
its title. v24.6.406 tried to tell that apart from a wrapped sidebar phrase with a
list of role nouns; "Financial Controller", "Quantity Surveyor" and "Sommelier"
all walked through it, which is what a word list does. Refusing costs a sub-brand
its nesting in the one constructed case that relied on it, and no real document
has been seen with a wrapped word in that position.

**A role qualifier is a name, not a sentence.** "Analyst - Kuala Lumpur" is the
same role; "Analyst - Work covered the regional desk" is prose that happens to
start with a role name, and reading it as a qualifier located that role and took a
project with it. A leading capital does not separate them -- prose capitalises its
first word too. Every word after the separator has to read as part of a name:
capitalised, or one of the connectors a name may contain.

**Every new loop over work_experiences has to survive a null entry.** A provider
can return one. One unguarded `exp.get` turned /parse into an HTTP 500 that master
handled without complaint.

**A referees section ends at the next section heading.** Treating the first
referees heading as a cut to the end of the document makes every employer below
it unreachable, and some CVs put referees part-way through.

`_reference_section_spans` does not begin a referee block at a standalone
"References available upon request" statement. Candidate footer contacts below
that statement remain eligible for fallback. The same statement inside a real
referee section does not end that section or expose referee contacts.

### Marker normalization

**Source documents (especially DOCX / plain text) bake a list marker or label
into the text**, and the normalizer didn't strip or restructure it, so it
collides with the formatter's own rendering. Every fix so far is a variant of
this:

| Symptom in output | What the source baked in | Fix location |
|---|---|---|
| `Tdcx` instead of `TDCX` | all-caps vowelless brand token | `_smart_word_case` (Python) **and** `smartTokenCase` (`generate.js`) — keep both in sync |
| `• -Received calls` | leading dash bullet marker | `_strip_leading_bullet_marker` |
| `• (i)Receives calls` | `(i)` / `(ii)` / `1.` / `1)` enumerators | `_CV_LEADING_BULLET_MARKER_RE` |
| lone `• Key responsibilities` above its duties | a sub-heading emitted as a flat bullet | `_absorb_orphan_section_labels` |
| `to 2001` for a graduation year | a leading `- 2001` source marker was converted to `to 2001`, or the provider returned only a range end | `_normalize_cv_date_range`, `normalizeDateRange`, and `cvNormDateRange` remove the dangling separator and keep `2001`; an absent date stays empty |
| lone `-` / `--` bullets | marker-only residue | drop in `_normalize_cv_bullet_items` |
| `No Degree` under a school | provider placeholder for a missing qualification | `_normalize_cv_data_for_output` clears known empty-degree placeholders both alone and after a `No Degree:` prefix |
| `• a.`, `• 1-`, or `• a-` in the output | a bare source enumerator survived beside Word's own marker | `_CV_LEADING_BULLET_MARKER_RE` strips lower-case dot/hyphen and numeric-hyphen enumerators while preserving `3.5`, `5-star`, `-5%`, `i.e.`, capitalised initials and date ranges |
| one continuous employer shown as several company blocks | provider split each promotion into a separate experience | `_merge_adjacent_continuous_company_stints` groups only neighbouring same-employer ranges whose bounded start/end points are all month-precise and touch; year-only or partially month-precise dates, gapped/non-adjacent returns and business-unit suffixes remain separate, while known broad location suffixes can still group |
| an older employer appears before a newer employer | provider emitted inconsistent work-history order | `_sort_work_experiences_reverse_chronological` sorts dated employer blocks newest-first after safe grouping without moving undated source entries out of position |
| concurrent freelance work jumps ahead of the candidate's primary current role | final normalization re-sorted a source-authoritative Professional Experience / Independent Consulting sequence by date | `_extract_authoritative_work_rows` retains safe source subsection headings, while `/generate-docx` preserves the already-reviewed preview order instead of sorting it again |
| a source role or its duties disappear although explicit header/bullet lines are readable | provider omitted the role/bullets and authoritative reconciliation restored only headers | `_extract_authoritative_work_rows` captures explicit source glyph bullets, safe title-first single-year headers, and compact Earlier Experience entries; reconciliation uses the source list only when it is fuller than the provider role |
| an Awards/Volunteer section appears inside the last job duties | source bullet recovery continued beyond the end of Work Experience | authoritative recovery stops at the shared allowlist of real CV section boundaries, including letter-spaced template headings, before collecting more duties; a role-local `ACHIEVEMENTS:` label is retained only when another dated job follows |
| training prose such as `Manager — Leadership Programme 2023` becomes an employer or joins the preceding duty | a generic title word plus a trailing bare year looked like a work header/continuation | bare-year recovery requires either an exact provider employer/title pair or the explicit `Title | Company YYYY` structure; rejected header-shaped prose cannot become a wrapped duty |
| two same-employer entries on opposite sides of a consulting subsection merge | continuous-stint grouping ignored the semantic subsection boundary | an incoming `section_heading` is a hard company-merge boundary |
| education shows years even though the source includes months | provider dropped month precision | `_recover_education_date_range` restores only a nearby source range whose start/end years match the parsed education entry |
| education renders `2018 to 2018` | provider expanded a single source graduation year into an identical-endpoint range | `_normalize_cv_date_range`, `normalizeDateRange`, and `cvNormDateRange` collapse identical year endpoints to the single year |
| source Core Capabilities uses `·` separators but output changes them to commas | provider preserved every word but normalized the visible separators | `_recover_cv_source_skill_item_punctuation` restores the category-anchored source span only when its alphanumeric content exactly matches the parsed items |
| Core Expertise alternates between bullets and one paragraph | provider returned `items` as an array, newline list, or comma-separated string in different runs | `_normalize_cv_structured_content` deterministically converts Core Expertise items into real Word bullets; a one-item provider list containing three or more comma-delimited values is also split, while a genuine phrase with one internal comma such as `Mergers, Acquisitions & Integration` remains one bullet |
| `GitHub: https://github.com/unknown` appears without a source link | provider invented a placeholder portfolio URL | `_remove_ungrounded_cv_github_links` always removes the known placeholder, including source-free export; with source text it retains only matching GitHub paths and ignores terminal sentence periods |
| `Position: Retrieved Resumes (SiVA folder: ...); Date Applied: ...` appears in Additional Information | JobStreet/SiVA application-routing metadata was mistaken for CV content | `_strip_cv_recruitment_tracking_metadata` removes the metadata at a line start or after a `|` item separator wherever the provider placed it |
| Project Involvement History or Participated Training Programme is missing | provider truncated or skipped bracketed sections near the bottom of a long CV | `_recover_cv_source_additional_sections` restores every allowlisted source item, stops at recognized simple or combined CV headings (`&` and literal `AND` are equivalent), preserves ordinary explicitly bulleted items even when their text resembles a heading, but treats numbered, all-caps or colon-emphasized marked headings as real boundaries; training duplicates are removed from certifications |
| recovered Project/Training items are comma-separated in preview but bulleted in Word | browser preview flattened structured item arrays | `cvSkillPreviewHtml` uses the same multiple-items-as-bullets rule as `generate.js` |
| a CV Studio-formatted DOCX becomes double-bulleted or turns bold role subheadings into bullets after Blind CV | `python-docx`'s `Paragraph.text` omits Word numbering, then the blind provider can flatten section objects into plain strings | `_extract_docx_text_preserve_tables` prefixes only paragraphs carrying real Word numbering; `/blind` restores an exact matching original role section/list shape using only already-blinded response text, then re-runs `_normalize_cv_structured_content` |

### Key files/functions (`cvstudio_cv_normalize.py`)

- **`_CV_LEADING_BULLET_MARKER_RE`** — **add new marker styles here.** Matches
  glyph bullets (always strip), parenthesised/numeric enumerators, and
  dash/asterisk (only before a space or a letter, so `-5%` and `3.5` are
  protected).
- **`_normalize_cv_bullet_items`** — the main bullet normaliser: strips markers,
  drops noise, repairs JSON-encoded section objects, absorbs orphan labels. Runs
  on each role's `bullets` list.
- **`_strip_leading_bullet_marker`** — the per-string marker/enumerator strip
  (loops to handle a short run like `• - `).
- **`_absorb_orphan_section_labels`** — when a label like "Key responsibilities"
  arrives as a flat bullet with the duties as loose siblings, re-attaches the
  following plain bullets to it (drops a bare label with nothing after it).
- **`_normalize_cv_date_range`** — date normalisation; strips a **leading** dash
  (a date never starts with a minus) and a dangling leading `to` before one
  four-digit year, but preserves internal range separators (`2020 - 2023` →
  `2020 to 2023`). It also compacts identical year endpoints and expands a
  shared-year month span such as `Jul - Dec 2019` without guessing. Keep the
  matching browser and generator functions in sync.
  The v24.6.395 corrective preserves two-digit years (including mixed precision)
  rather than assuming every number beside a month is a day. Full day/month/year
  dates and explicit day-bearing shared-year ranges reduce to month + year.
  Day-first dates may include a comma after the month, as in 20 March, 2021.
  v24.6.396 accepts Unicode horizontal spaces without crossing lines. Shared
  years expand only when the start month is not later than the ending month;
  `1 Dec - 31 Jan 2026` becomes `Dec to Jan 2026`, not a guessed start year.
  Explicit `Dec 2025 to Jan 2026` stays intact on every pass.
  Python, `cvNormDateRange` and `normalizeDateRange` share cross-language tests
  in `tests/test_cv_date_parity.py` and `tests/test_cv_date_parity.js`.
- **`_recover_cv_source_skill_item_punctuation`** — restores visible middle-dot
  separators only for a category-anchored source span whose words exactly match
  the provider items after punctuation is ignored. Matched ASCII letter casing
  comes from the provider rather than the source, so the final normalization
  does not undo auto-correction. Source separators, symbols and word order stay
  intact; this pass never invents spelling corrections.
- **`_strip_cv_recruitment_tracking_metadata`** — removes JobStreet/SiVA
  retrieval/application metadata recursively before it can render in any body
  section.
- **`_recover_cv_source_additional_sections`** — source-aware recovery for the
  explicitly bracketed Project Involvement History and Participated Training
  Programme lists. Exact source wording and order are retained, and recognized
  ordinary CV headings, including combined headings such as Education &
  Certification or Education AND Certification, terminate recovery so later
  sections are not absorbed. An explicitly marked bullet remains an item even
  when its wording also appears in the heading allowlist, unless the marker and
  numbered/all-caps/colon emphasis provide strong evidence that it is the next
  real section heading.
- **`_remove_ungrounded_cv_github_links`** — always removes the known placeholder;
  when source text is available, removes any other provider-emitted GitHub path
  that cannot be matched to the extracted source CV.
- **`_CV_SECTION_HEADING_RE`** — detects "Key responsibilities" / "Key
  achievements" labels and the established generic role subheadings
  `Implementation`, `Support`, `Rollout`, and `Activities Description`.

### Section-object contract

`SYSTEM_PROMPT` (`app.py`) instructs the AI to emit named sub-sections as
`{"heading": "...", "bullets": [...], "kind": "section"}` objects, and plain
bullets as strings. `generate.js` renders a `kind:"section"` heading **without**
a bullet marker (bold) and its `bullets` as list items. When the AI returns a
label flat instead of nested, `_absorb_orphan_section_labels` re-nests it.

For a formatted DOCX uploaded again, `_extract_docx_text_preserve_tables`
preserves the otherwise invisible Word list signal by prefixing real numbered
paragraphs with `• ` while leaving ordinary bold headings unmarked. Blind CV
then uses `_blind_restore_cv_bullet_structure` to reapply the original role
container shape only when the original and already-blinded flattened text
counts match exactly. It never copies source wording or unknown source fields;
a mismatch is left untouched instead of guessed.

## ⚠️ Highest-risk code

`_reconcile_work_experience_with_authoritative_table` (`cvstudio_cv_reconcile.py`)
rebuilds work history from a "source table" it re-extracts from `cv_text` via
`_extract_authoritative_work_rows`. If it mis-parses a header (e.g. the
`Company – Title | dates` orientation), it can **swap company/title and delete
bullets/roles**. It has safety valves (defer to the fuller AI parse when all
rows match; a "suspicious" flag). Change with care and always run the
characterization tests.

## Testing — no AI, no Word, no reinstall needed

Formatting is deterministic, so you rarely need the browser or a live parse:

- **`python preview_format.py parsed.json`** — renders a parsed-CV JSON through
  the real `/generate-docx` pipeline and prints it as text; `•` marks a real
  bullet, no marker = heading. Feed it the `data` object from one real `/parse`
  response and reuse it offline forever (no AI cost).
- **Reproduce a bug directly** against a pure function, e.g.
  `_normalize_cv_bullet_items(["(i)Received", "- 2001"])`, and assert on the
  result.
- **Tests:** `tests/test_phase7b_cv_normalize_characterization.py` (unit) and
  `tests/test_long_cv_output_corrective.py` (end-to-end DOCX). Run:
  `SALARY_COMPARISON_DATA_DIR=/tmp/sal/data .venv_test/bin/python -m pytest tests/ -q`
  — expect all pass except one known env-only `antiword` failure (a Windows
  binary that isn't functional on Linux).

## Conventions to follow

- **Bump the version on every code change:** `python bump_version.py X.Y.Z`.
  Never hand-edit version strings — one `VERSION` file drives all surfaces and a
  guard test (`tests/test_version_single_source.py`) enforces it. (A docs-only
  change like this file needs no bump.)
- Keep the Python normalisers and `generate.js` in agreement where logic is
  duplicated (casing lives in both).
- **Do not paraphrase bullet wording** — the pipeline preserves original text;
  fixes are about structure/markers, not rewording.
- Small additive changes with a regression test. Do not rewrite the pipeline.

## Known-minor, deliberately unfixed

Markdown `*emphasis*` as an entire bullet (`*Achieved target*`) → the leading `*`
is stripped and a trailing `*` dangles. Vanishingly rare in CVs, and a "fix"
risks over-stripping real content, so it is left as-is.
