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
| one continuous employer shown as several company blocks | provider split each promotion into a separate experience | `_merge_adjacent_continuous_company_stints` groups only neighbouring same-employer ranges that touch; gapped and non-adjacent returns remain separate, and merged roles are sorted newest-first |
| an older employer appears before a newer employer | provider emitted inconsistent work-history order | `_sort_work_experiences_reverse_chronological` sorts dated employer blocks newest-first after safe grouping |
| education shows years even though the source includes months | provider dropped month precision | `_recover_education_date_range` restores only a nearby source range whose start/end years match the parsed education entry |
| Core Expertise alternates between bullets and one paragraph | provider returned `items` as an array, newline list, or comma-separated string in different runs | `_normalize_cv_structured_content` deterministically converts Core Expertise items into real Word bullets |
| `GitHub: https://github.com/unknown` appears without a source link | provider invented a placeholder portfolio URL | `_remove_ungrounded_cv_github_links` always removes the known placeholder, including source-free export; with source text it retains only matching GitHub paths and ignores terminal sentence periods |
| `Position: Retrieved Resumes (SiVA folder: ...); Date Applied: ...` appears in Additional Information | JobStreet/SiVA application-routing metadata was mistaken for CV content | `_strip_cv_recruitment_tracking_metadata` removes the metadata at a line start or after a `|` item separator wherever the provider placed it |
| Project Involvement History or Participated Training Programme is missing | provider truncated or skipped bracketed sections near the bottom of a long CV | `_recover_cv_source_additional_sections` restores every allowlisted source item, stops at recognized ordinary CV headings, and removes training duplicates from certifications |
| recovered Project/Training items are comma-separated in preview but bulleted in Word | browser preview flattened structured item arrays | `cvSkillPreviewHtml` uses the same multiple-items-as-bullets rule as `generate.js` |

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
  `2020 to 2023`). Keep the matching browser and generator functions in sync.
- **`_strip_cv_recruitment_tracking_metadata`** — removes JobStreet/SiVA
  retrieval/application metadata recursively before it can render in any body
  section.
- **`_recover_cv_source_additional_sections`** — source-aware recovery for the
  explicitly bracketed Project Involvement History and Participated Training
  Programme lists. Exact source wording and order are retained, and recognized
  ordinary CV headings terminate recovery so later sections are not absorbed.
- **`_remove_ungrounded_cv_github_links`** — always removes the known placeholder;
  when source text is available, removes any other provider-emitted GitHub path
  that cannot be matched to the extracted source CV.
- **`_CV_SECTION_HEADING_RE`** — detects "Key responsibilities" / "Key
  achievements" labels.

### Section-object contract

`SYSTEM_PROMPT` (`app.py`) instructs the AI to emit named sub-sections as
`{"heading": "...", "bullets": [...], "kind": "section"}` objects, and plain
bullets as strings. `generate.js` renders a `kind:"section"` heading **without**
a bullet marker (bold) and its `bullets` as list items. When the AI returns a
label flat instead of nested, `_absorb_orphan_section_labels` re-nests it.

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
