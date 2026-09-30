# v24.6.428 Title-above rows: post-merge review fixes

Branch: `claude/pr157-chatgpt-fix-zke4cy`, from merged master `01688bb` (v24.6.427,
PR #218). v24.6.426 is taken by the unmerged PR #214 crawler branch.

A code review of the merged rule R7 (see
`cv_studio_v24_6_427_title_above_place_rows_qa_report.md`) found three problems.

## Findings and fixes

1. **After an unsure row, the next job's lines joined the previous job.** Take a
   title the reader did not recognise ("CEO") above "Northwind | Singapore |
   dates". The reader rightly made no row, but:
   - it glued that title onto the previous job's last bullet;
   - it filed the next job's bullets under the previous employer.

   On a CV where the other rows were read, those bullets could replace the AI's.
   Now an unsure row ends the previous job, so later bullets join nothing. If
   the line glued onto the previous job's last bullet just before the unsure
   row is shaped like a title, that job's source bullets are unsure too, and the
   AI's are kept. A wrapped duty ("Reporting to General Manager", from the PR
   #218 review) is not title-shaped, so it stays in its bullet as before.
2. **Common titles were not read as titles.** The wrapped-duty check treated
   "and" as a linking word, which made "Marketing and Communications Manager",
   "Training and Development Manager" and "Accounting and Finance Executive"
   look like prose. Also, "CEO", "VP Sales", "Country GM", "Chairman", "Legal
   Counsel", "Sales Representative" and "Senior Buyer" had no job word. Now "and"
   is no longer a linking word, and the title-above check has more job words,
   officer acronyms included.
3. **"Rio de Janeiro, Brazil"** was not a place because of "de". Now a joining
   word (de, da, del, van, von, …) may appear among a city's capitalised words.

## The six steps

1. **Cases first.** There are 15 new R7 cases. 14 failed on master. The other
   one, "CFO and Company Secretary", already worked and is pinned. One case was
   dropped before the fix because it would have pinned a bad master reading.
2. **Existing cases.** All earlier cases pass unchanged, including the PR #218
   review cases (wrapped duty stays in its bullet, "Managing Director").
3. **Whole-suite replay against `01688bb`.** 393 reader calls, 26 reconciler
   calls, 84 education restores and 110 normalize calls were compared. There
   are 14 differences, all on the new cases.
4. (P1 only; not affected.)
5. **Old vs new on the repository.** 2,361 windows and 30 graduation lines
   were compared. The 14 differences are all in the fixture. 13 are the new
   cases. The fourteenth stitches older R7 cases together, and on master the
   stitched text after an unsure row was glued into the previous job's bullets.
   That leak is exactly finding 1, and now nothing is attached. The education
   restore has no differences.
6. **Deliberate breaks.** 43 breaks were tried, including new ones for every
   guard in this change. 42 are caught. The remaining one is the education
   block break described in the v24.6.427 report, which cannot change the
   result. Two new guards were removed because no case could reach them, since
   an existing check already covered what they did. One checked for a bullet
   line (the title-shape check already rejects bullets). The other required a
   city to start with a capital (only a joining word could start one).

## Regression

- Python: 1458 passed, 23 skipped (the usual deselections).
- Node: all `tests/*.js` pass.
- Launcher CRLF counts match master (242 / 89 / 37).
- The reported CV, replayed locally, still comes out as in v24.6.427.

No release or native protected build is produced by this work.
