# v24.6.529 Sourcer Candidates folders, shortlist and Trash - QA and handover

Base: unmerged v24.6.528 on `claude/job-leads-signed-clients` (`b7894b5`),
itself from merged v24.6.527 / PR #273 / `3ea7880`.

The owner asked for folders, delete and a shortlist on the LinkedIn Sourcer
Candidates dashboard, like Job Leads, to organise saved candidates. Job Leads'
existing rules were followed: folders with move-selected and delete-folder,
recoverable Trash with Restore and no permanent purge, and stale selections
refused atomically. Job Leads has no literal shortlist, so a per-candidate
star with a "Shortlisted only" filter was added.

## Behavior

- **Folders.**
  - Create (same name rules as Job Leads, up to 200 folders).
  - Move selected (candidates in Trash are refused).
  - Filter by folder, with counts.
  - Delete a folder. Every candidate in it, including Trash, must still be
    current; they become Unfiled and the folder is removed.
  - Creating a folder keeps the selection.
- **Shortlist.** A star per row (`aria-pressed`), a "Shortlisted only" filter,
  and refusal while in Trash.
- **Trash.**
  - Delete selected (confirmed) and Restore selected.
  - Trash is hidden unless chosen.
  - Folder, shortlist and notes are kept.
  - There is no permanent purge, as in Job Leads.
- **Excel.** The export follows the folder and shortlist view (Trash only when
  chosen), with Folder, Shortlisted and In Trash columns.
- **Consistency.**
  - Revisions are checked for every change.
  - A filter change clears the selection, and a refresh drops changed
    candidates.
  - A re-assessment keeps the organisation.
  - Note drafts follow the owner's own changes when the saved note is
    unchanged.

## Storage and contracts

- **Storage:** the same protected `sourcer_candidates` vault, still version 1.
  - Additions: an optional `folders` list, and optional per-row `folder`,
    `shortlisted`, `deleted` and `deleted_at`.
  - Earlier saved dashboards read unchanged.
  - Malformed additions fail closed and are never overwritten.
- **Route contract:** unchanged at 124. The new actions use the existing
  `/linkedin-sourcer` route and its guards.
- **External calls:** no SQLite schema, AI request, LinkedIn request or
  companion change.

## Validation

- **Python:**
  - New tests cover store rules (folders, move, shortlist, Trash, folder
    deletion, stale selections, re-assessment and notes keeping
    organisation).
  - Saved dashboards from before folders still read, and malformed
    organisation data fails closed.
  - The route actions and the Excel view and columns are tested end to end
    through the app.
  - The existing guarded-dashboard test now uses `tests/isolated_app.py`, so it
    also passes when its file runs on its own.
- **Node:** a new `tests/test_sourcer_candidate_folders_frontend.js` covers:
  - creating a folder while keeping the selection, then moving it;
  - folder views and counts;
  - the shortlist star and filter, with a note saved after the owner's own
    change;
  - Trash and Restore, select page, and selections across refreshes;
  - stale refusals, the export view, and folder deletion.
  - The v527 sort test reads the name from its new column.
- **Deliberate breaks:** 31 across the store, filters, export and dashboard;
  all caught after four test gaps were closed. One of those gaps led to a
  behaviour change: creating a folder no longer clears the selection.
- **Real browser:** Chromium against the fictional demo server's five
  seeded candidates:
  - Two candidates were ticked, Controlling was created (still 2 selected) and
    both moved in.
  - The Controlling view showed both. One was starred, and Shortlisted only
    showed just that one.
  - Delete selected asked first and moved one to Trash, hidden from
    Controlling. In the Trash view, Restore (with Delete hidden) brought it
    back.
  - Export downloaded the folder view.
  - Deleting the folder asked first, and its 2 candidates went to Unfiled.
  - No horizontal overflow at 390 px. The only console error was the demo's
    unanswered work-type lookup, which this change does not touch.
- **Node:** all test files pass. `test_apollo_broker.js` failed once while the
  demo server and browser ran at the same time, then passed 3 of 3 alone; it
  is not touched by this change.
