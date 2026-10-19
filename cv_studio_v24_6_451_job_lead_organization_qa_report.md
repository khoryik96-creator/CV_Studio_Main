# Job Leads folders, Trash, rich content and creation date — 2026-10-19

Historical release evidence; root `VERSION` is the live release identity.

## Scope

Owner requested folders inside Job Leads, clear/delete buttons, readable rich
ad content, and a visible creation date. Source v24.6.451 on
`codex/v24.6.451-job-lead-organization` starts from unmerged v450 `20b1f25`.

- Save to folder creates a grouping when the lead is saved. Folder filtering
  combines with existing search/status filters. Unfiled and All folders remain.
- Delete moves one lead to Trash; Clear shown ads uses the entire current
  filtered selection, while Clear all ads covers all active folders. Bulk
  actions confirm the count. Restore returns a lead to its original folder.
  These are recoverable, revision-checked transactional updates, not a permanent
  purge. A stale item aborts the complete batch. Duplicate saves and old backups
  cannot silently resurrect an existing trashed lead; Trash remains in backups
  and storage-capacity accounting.
- Date created uses the already stored original local creation timestamp,
  shown on cards and edit form. Edits/Trash/restore do not reset it. JSON restore
  now retains a valid supplied creation timestamp; old backups without it use
  import time. LinkedIn posting date stays separate and optional.
- Public ad HTML and companion capture retain headings, paragraphs, bold/italic
  text, lists and line breaks through a bounded passive semantic tree. Only
  allowlisted tag names and plain text can be stored/rendered. Source scripts,
  styles, attributes, media and URLs are never rendered. Frontend construction
  uses DOM elements/text nodes, never source HTML injection. Plain text remains
  available for editing/CSV. Ordinary edits clear rich formatting; whole-field
  formatted paste prepares content locally without AI. Rich content must match
  the retained text; incompatible/oversized markup falls back to that text.
- Refresh ad content explicitly refreshes an older capture into the draft.
  Manual company/contact/notes/status/dates are kept. A failed or empty refresh
  preserves existing content. Save is still explicit.

All additions use existing record JSON and GET/POST `/job-leads` actions. No
schema migration, route change, worker, provider call or credential change.
The 120-route seal, five guards, core schema 10, Job Leads schema 1, journal
schema 1 and Sourcer/provider behavior remain. Version surfaces were generated
through bump_version.py; no protected build or packaged release was produced.

## Verification

- Pre-change focused baseline: **82 passed**.
- Changed extraction, persistence and organization suites: **106 passed**.
  Added checks cover folder/rich persistence, creation timestamps, old backups,
  hostile/invalid/deep/large rich trees, typography/lists, typed metadata,
  stale atomic bulk actions, durable Trash/restore, duplicate/backup protection,
  route guards, request IDs and no-AI/no-durable-write content preparation.
- Full isolated Windows local: **1,713 passed, four skipped, three deselected,
  7,599 subtests passed**, 138.11 seconds. Existing updater environment exclusions:
  `test_python_runtime_resolver_returns_the_exact_validated_interpreter`,
  `test_real_update_preflight_uses_launcher_path_python_before_stale_fixed_install`,
  `test_downloaded_preflight_is_self_contained_for_v357_upgrade_transition`.
  No unfiltered hosted CI result is claimed.
- All **34 JavaScript suites** passed. Job Leads assertions include internal
  folder filtering/defaults, visible creation date, rich paste, optional fields,
  recoverable row delete/restore, cancelled clear, folder-scoped clear, all-ad
  clear including a hidden folder, and empty-refresh draft protection. Existing
  companion binding, source/ownership and sourcing checks remain green.
- Actual in-app UI with isolated synthetic data verified folder filtering,
  Delete/Trash/Restore, saving into a new folder, preserved creation time,
  heading/bold/bullet rendering and blank optional contact. Screenshot retained
  only in ignored runtime. Synthetic leads never entered owner preview state.
- Owner's existing saved ad displays its original creation timestamp. Its public
  page was read through Refresh ad content and its original lists/bold text
  visibly returned in the new unsaved draft. Existing saved record and other
  browser drafts were not modified. This public read does not establish every
  LinkedIn layout or login-only access; no private API/login bypass was used.
- Python/JavaScript/shell syntax, tracked byte/source inventories, verified
  Windows Antiword/Tesseract and adm-zip preflight, and **24-assertion source
  smoke** passed. No native Mac or protected compilation claim.

Preview 5074 retains its prior isolated persistent state; synthetic 5075 is
stopped after verification. No owner data deletion, saved lead mutation, paid
provider call, JobAdder write, outreach, installed app/receipt change, push,
PR, merge or package release occurred.
