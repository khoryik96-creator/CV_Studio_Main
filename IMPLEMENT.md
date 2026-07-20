# Phase Execution Runbook

1. Read `AGENTS.md`, `ROADMAP.md`, `PHASE_STATUS.md`, the handover and QA report.
2. Verify that the checked-out source is v24.6.217.
3. Verify Git availability.
4. If this folder is not yet a Git repository:
   - initialise Git;
   - respect the existing `.gitignore`;
   - create a baseline commit before changing production code.
5. Inventory all storage files and all read/write call sites in scope.
6. Write a concrete milestone plan into `PHASE_STATUS.md`.
7. Implement one milestone at a time.
8. Run targeted tests after each milestone.
9. Fix every failure before continuing.
10. Update `PHASE_STATUS.md` after each milestone.
11. Create a Git checkpoint after each stable milestone.
12. Run the full regression and static-validation suites at phase completion.
13. Verify migration twice against a v24.6.217 fixture.
14. Verify failure/corruption recovery without deleting legacy JSON.
15. Create the new private owner/source ZIP.
16. Freshly extract the ZIP and byte-verify its contents.
17. Produce:
    - QA report;
    - SHA-256;
    - exact changed-file list;
    - known limitations;
    - Phase 2B handover.
18. Stop. Do not begin Phase 2B.
