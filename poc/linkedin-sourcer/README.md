# LinkedIn Sourcer POC

A separate, experimental Chrome side panel backed by DeepSeek. This is not a
CV Studio release and does not import `app.py`, change installation receipts,
add main-app routes, store credentials or change the application version.

## Try it

1. Double-click `START_POC.bat`. The first launch creates a separate Python
   environment and installs the two pinned dependencies. It opens the local
   welcome page at `http://127.0.0.1:5073/`.
2. Follow that page's Chrome **Load unpacked** instructions. Choose the
   `extension` directory beside this README, and pin **CV Studio Sourcer POC**.
3. Copy the welcome page's pairing code into the extension's Connect field.
   This is a temporary bridge code, not your DeepSeek API key. On Windows,
   the bridge reads only the existing DPAPI-protected `main_deepseek` slot
   saved through CV Studio Settings. It never writes the vault or receipt.
   A `DEEPSEEK_API_KEY` environment variable is also supported; never commit it.
4. Open a LinkedIn search in the active tab. Choose People search, Recruiter
   Lite or Recruiter. Enter the brief, start with one page, review the displayed
   DeepSeek data-use confirmation, and select **Start sourcing**.
5. The agent plans the query, reads search cards, chooses up to five promising
   profiles per page, opens their detail pages and follows the recognized Next
   page control. It supports up to 15 result pages, with a separate API-request
   ceiling (default 35, hard maximum 80). At most two requests per page plus
   planning are normally needed. Requests are not automatically retried.
6. Review evidence, unknown requirements and profile links. **Export CSV** saves
   the current list; formula-like cells are escaped. **Clear** removes the list.
   Results stay only in extension session storage until Clear or browser exit.

Keep the side panel open. Stop preserves the current list and prevents subsequent
actions. A request already sent to DeepSeek may still finish and be charged.
If the panel closes, no work resumes automatically; use Stop before a new run.
`STOP_POC.bat` stops only the matching POC bridge process started by its launcher.

## Coverage and limits

- **Implemented modes:** standard People search, Recruiter Lite and Recruiter.
  Each has its own result-card selectors. Recruiter layouts use the visible
  Keywords field and search button; private APIs or invented search routes are
  never used. If that form is unrecognized, copy the generated query into the
  site's search yourself and choose **Review the search already open**.
- **Synthetic fixtures tested; live account compatibility not yet verified.**
  LinkedIn varies its layouts. Unknown layouts, repeated pages, login checks,
  verification challenges and usage restrictions stop the run visibly. A missing
  Next control is reported as unrecognized, not proof that all results were read.
- Only profile URLs observed in result cards can be opened. Public `/in/` URLs
  are shown when observed for that candidate. Otherwise the original Recruiter
  profile link is retained and labelled as requiring login; no public URL is
  guessed. Names and links come from the page, never model-generated text.
- Search-card matches and detail-read matches are labelled separately. Exact
  supporting quotations are checked against that candidate's observed text.
  Missing requirements stay unknown; the scores are tentative, not verified fit.
  The POC does not expand every collapsed section or scroll an entire profile;
  unread or unloaded experience cannot be assumed absent.
- No contact requests, messages, saved searches, candidate projects, profile
  edits, hidden/private endpoint calls, credentials/cookie access, CAPTCHA
  handling, restriction bypass or JobAdder writes are implemented.
- LinkedIn prohibits unauthorized automated activity and scraping. This is a
  technical experiment, not a statement that a live deployment is permitted.
  Review the site's terms before choosing a live run.

## Verification without a paid request

From this directory:

```
python -m unittest discover -s tests -p "test_*.py" -v
npm install --ignore-scripts --no-audit --no-fund --package-lock=false
node --test tests/*.test.mjs
```

The browser fixture runner uses Playwright solely for tests; it is not a runtime
dependency. It loads synthetic local pages only. The bridge's transport is mocked
in automated tests. No real LinkedIn credentials or candidate content belongs in
fixtures, logs or Git. A live end-to-end check requires the owner to load the
extension, sign in, and confirm a paid run in the panel.

The loopback bridge enforces host checks, extension-origin checks, a random
pairing token, explicit per-run data-use confirmation, request-size/time/call
bounds, serial execution and no automatic paid-request replay. Profile text is
held only in memory. The key never enters a profile page, extension storage,
browser message or CSV. DeepSeek usage is reported as tokens; incomplete usage
remains explicit. This separate experiment does not write CV Studio usage history.

References: [DeepSeek tool calls](https://api-docs.deepseek.com/guides/tool_calls/),
[current models](https://api-docs.deepseek.com/quick_start/pricing/),
[Chrome side panels](https://developer.chrome.com/docs/extensions/reference/api/sidePanel),
[LinkedIn automation policy](https://www.linkedin.com/help/linkedin/answer/a1341387/prohibited-software-and-extensions?lang=en).
