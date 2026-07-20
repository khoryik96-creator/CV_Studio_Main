# Salary / Notice Logic Handover for CV Studio Integration

This file is the corrected source of truth for CV Studio / The 郭 Lab salary and notice normalization.
It supersedes the earlier handover that incorrectly excluded 13th month/AWS and any implementation that lets AI independently calculate final salary numbers.

## 1. JobAdder Current Salary Formula

```text
Current monthly equivalent
= roundCurrency(
    (monthly base × guaranteed salary months ÷ 12)
    + fixed recurring monthly allowances
    + other fixed monthly cash
    + explicitly configured included employer EPF
  )
```

Rounding is deterministic `ROUND_HALF_UP` to the nearest whole currency unit. Do not randomly round to the nearest 100, 500 or 1,000.

## 2. Guaranteed Salary Months

Use one canonical field:

```json
{"guaranteedSalaryMonths": 13.5}
```

Recognize total guaranteed salary months such as:

```text
13th month / 13 months / 13th bonus / x13
13.5th month / 13.5 months / 13.5th bonus / x13.5
14th month / 14 months / 14th bonus / x14
14.5th month / 14.5 months / 14.5th bonus / x14.5
AWS / annual wage supplement = guaranteed 13th month
```

Recruiter shorthand such as `13.5th bonus` means a **13.5-month total package**, not an additional 13.5 bonus months.

Also recognize explicit guaranteed additions:

```text
1 month contractual bonus → 13 total months
2 months contractual bonus → 14 total months
0.5 month guaranteed bonus + AWS → 13.5 total months
```

Do not convert performance, variable or discretionary bonus into guaranteed salary months.

## 3. Fixed Monthly Cash

Include fixed recurring monthly allowances such as transport, phone/mobile, housing, car, meal and fixed cash allowance. Recognize common misspellings including `allowence`, `alowance` and `sllowance`.

Also support recruiter shorthand where a fixed monthly cash component is written as a standalone additive amount without a label, for example `RM12k + 500 + 13.5th bonus`. The separate `500` is treated as fixed monthly cash when it is a safe standalone salary component and no exclusion/time/percentage wording applies.

Exclude unless explicitly guaranteed/fixed:

```text
performance/variable/discretionary bonus
commission/incentive
EPF/KWSP, SOCSO, EIS
claims/reimbursements
medical/insurance benefits
stock/RSU/ESOP/options
employer contributions
```

The Screening Call keeps the original full salary breakdown text even when some components are excluded from the numeric profile field.

## 4. K Shorthand and Currency

Support `8k`, `8.5k`, `22.5k`, ranges such as `8-10k`, and currency prefixes/suffixes such as RM/MYR, SGD and USD.

## 5. Expected Salary Priority

```text
1. Explicit expected fixed amount
2. Explicit expected range
3. Explicit same-as-current intent
4. Percentage increment
5. Percentage range
6. Open / negotiable / N/A
```

A fixed amount wins over a percentage. Percentage calculations must use the already-computed canonical `current.monthlyEquivalent`; never rerun the current parser.

## 6. Notice Period

Keep notice human-readable. Recognize Immediate, days, weeks, months, serving notice and specific availability dates. Never display Immediate as a boolean in candidate-facing UI.

## 7. Deterministic Salary Calculation Rule

> AI extracts clues. Deterministic code calculates. One canonical object displays everywhere.

AI may extract raw components, but it must not independently produce the final current salary, expected salary or JobAdder field value.

Pipeline:

```text
Raw text
→ component extraction
→ canonical salary object
→ deterministic calculation
→ displays / JobAdder / records / exports
```

Never reparse a display string to calculate another value.

Canonical example:

```json
{
  "canonicalVersion": "salary-v1",
  "currency": "MYR",
  "current": {
    "baseMonthly": 10000,
    "fixedMonthlyAllowance": 500,
    "guaranteedSalaryMonths": 13,
    "monthlyEquivalent": 11333,
    "display": "RM 11,333/month equivalent"
  },
  "expected": {
    "type": "percent",
    "percent": 20,
    "basisCurrentAmount": 11333,
    "monthlyAmount": 13600,
    "display": "RM 13,600/month"
  },
  "validation": {
    "expectedBasisMatchesCurrent": true,
    "roundingRule": "ROUND_HALF_UP_TO_WHOLE_CURRENCY",
    "noDisplayReparse": true,
    "calculationOwner": "deterministic_code"
  }
}
```

All OneNote transfer records, UI summaries, profile updates and emergency browser fallback values must read from this same canonical object.

## 8. Idempotency and Validation

The same raw salary input and candidate-current numeric basis must produce the same fingerprint and same numeric output on every run.

For percentage expected salary:

```text
expected.basisCurrentAmount must equal current.monthlyEquivalent
```

If they differ, reject or deterministically recalculate expected salary from the canonical current value.

## 9. Examples

```text
RM10,000 base + RM500 allowance + 13th month
= (10,000 × 13 ÷ 12) + 500
= RM11,333/month equivalent
Expected 20% = RM13,600/month
```

```text
RM10,000 + 2 months contractual bonus
= 10,000 × 14 ÷ 12
= RM11,667/month equivalent
```

```text
2324rm + 32sllowance + 3months
= RM2,356/month equivalent
```

Standalone `3months` is not a guaranteed bonus and does not inflate salary.

```text
rm12k + 500 + 13.5th bonus + 16epf + 2 months bonus
= (12,000 × 13.5 ÷ 12) + 500
= RM14,000/month equivalent
Expected 15-30% = RM16,100 to RM18,200/month
```

The 16% EPF and non-guaranteed 2-month bonus are preserved in the Screening Call breakdown but excluded from the numeric current salary.

## 10. Screening Call and API Mapping

```text
41175 = Current Salary Breakdown
41176 = Expected Salary
41177 = Notice Period
62988 = Presentability rating (1–4)
```

Use the official JobAdder API v2 reference before inferring payloads:

```text
https://api.jobadder.com/v2/docs
references/jobadder_v2_openapi.json
```

## 12. OneNote AI-Assisted Extraction and Cost Transparency

OneNote salary handling uses a hybrid pipeline:

```text
OneNote labelled fields
→ AI component extraction when enabled (default route: DeepSeek)
→ strict component validation
→ deterministic code calculation
→ one canonical salary object
→ JobAdder / UI / records / exports
```

AI is never allowed to calculate or supply the final JobAdder salary number. It may only extract components such as:

```json
{
  "baseMonthly": 12000,
  "guaranteedSalaryMonths": 13.5,
  "fixedMonthlyAllowance": 500,
  "otherFixedMonthlyCash": 0,
  "excludedComponents": ["16% EPF", "2 months variable bonus"]
}
```

Deterministic code then calculates:

```text
(12,000 × 13.5 ÷ 12) + 500 = RM14,000
```

Privacy boundary: only Current Salary Breakdown, Expected Salary and Notice Period text are sent to the configured AI route. Candidate name, email, phone and unrelated screening-note content are not included in the salary extraction request.

Fallback boundary: if AI is disabled, no key is available, the provider is unavailable, or the response fails validation, use the local deterministic parser. The Screening Call creation must not fail solely because salary AI is unavailable.

Idempotency/cost boundary: validated AI component extraction is cached locally using a SHA-256 key of provider, model and raw salary fields. The cache stores only structured components, not the raw salary text. Repeated identical inputs reuse the same components, make no new AI call and cost USD 0.

Every canonical result must record:

```json
{
  "fieldExtraction": "ai_component_extraction | ai_component_extraction_cache | local_label_parser",
  "salaryCalculation": "deterministic_code",
  "aiAttempted": true,
  "aiUsed": true,
  "aiApiCalled": true,
  "cacheHit": false,
  "provider": "deepseek",
  "model": "deepseek-v4-flash",
  "inputTokens": 0,
  "outputTokens": 0,
  "costUsd": 0.0
}
```

Dashboard rule:

```text
Local-only transfer → Local · deterministic-salary-v1
AI-assisted transfer → actual provider · actual model
```

Never label a local OneNote transfer as Claude merely because Claude is the app's main provider.


## 12. Currency Detection and JobAdder Population

Currency detection is limited strictly to these two labelled fields:

- Current Salary Breakdown
- Expected Salary

Do not inspect or infer currency from Brief Overview/Summary, Reason For Leaving, Looking For, Leads, Remarks, Presentability, Notice Period, candidate name, email, or the full screening note. A currency mentioned elsewhere is ordinary note content and must be ignored for currency population.

AI may normalize aliases, but the final selected code and JobAdder option are deterministic. Supported aliases include examples such as RM/MYR/ringgit, Rp/IDR/rupiah, S$/SGD, US$/USD, Rs/₹/INR/rupee, RMB/CNY/yuan/renminbi, HK$/HKD, A$/AUD, euro/€ and the other supported regional terms.

If Current Salary and Expected Salary explicitly state different currencies:

> The single JobAdder Currency dropdown must follow Expected Salary.

Current and ideal salary API objects may retain their own detected ISO codes, but candidate custom field 4 is populated with the exact Expected Salary currency option.

Exact supported JobAdder dropdown values:

- Brunei Dollar (BND)
- Cambodian Riel (KHR)
- Indonesian Rupiah (IDR)
- Lao Kip (LAK)
- Malaysian Ringgit (MYR)
- Myanmar Kyat (MMK)
- Philippine Peso (PHP)
- Singapore Dollar (SGD)
- Thai Baht (THB)
- Vietnamese Đồng (VND)
- Chinese Yuan Renminbi (CNY)
- Hong Kong Dollar (HKD)
- Australian Dollar (AUD)
- Euro (EUR) - Used in the European Union
- United States Dollar (USD)
- Indian Rupee (INR)

Public OAuth update model:

```json
{
  "custom": [
    {
      "fieldId": 4,
      "value": "Malaysian Ringgit (MYR)"
    }
  ]
}
```

The normal workflow validates field 4 against `GET /candidates/fields/custom/4` where available. The emergency JobAdder browser helper mirrors Kano's confirmed SPA behavior by updating `customFields[4].value` with the same exact option.


## 12. v24.6.135 Safety and Audit Rules

- Explicit currency aliases in Current Salary Breakdown or Expected Salary override a conflicting AI currency. AI may disambiguate only among multiple explicit currencies in the same salary field.
- AI numeric components are evidence-validated against those two salary fields. Conflicting base, guaranteed-month, allowance or expected-salary values are rejected and deterministic parsing is used.
- Salary variants such as `13.5 mths` and `14th salary` are supported and must never be mistaken for cash amounts.
- A paid/called salary-AI extraction is recorded in OneNote Records and Dashboard even if the later JobAdder transfer fails.
- Candidate Currency custom field 4 is skipped when Candidate GET omits the full `custom` collection, preventing accidental replacement of unseen custom fields.
- Numeric availability dates are validated as real calendar dates before JobAdder write.
- The emergency browser-bridge route rebuilds salary values server-side and does not trust a client-supplied canonical object.


## 13. OneNote Summary / Overview Labels (v24.6.136)

The OneNote parser should map the following recruiter headings into the same `brief_overview` field used for JobAdder question `41172`:

- Brief Overview of Experience
- Brief Overview
- Overview
- Overview of Experience
- Experience Overview
- Work Experience Overview
- Candidate / Profile / Professional / Career Overview
- Summary
- Summary of Experience
- Experience / Work Experience Summary
- Candidate / Profile / Professional / Career Summary

Accept both inline labels such as `Overview: ...` and heading-only layouts where the heading is on one line and the content follows below. Do not change the official JobAdder question text or ID.


## 14. OneNote Parser Safety Hardening (v24.6.137)

- Summary/Overview aliases support inline and heading-only layouts with Markdown bold, bullets, numbering, and hash headings.
- Multiline summary paragraphs may contain blank lines and stop at the next recognized Screening Call field, including recruiter shorthands RFL, LF, CS, ES, and NP.
- Presentability must resolve to one whole rating from 1 to 4. Do not infer a rating from 10/10, 14, 40, years-of-experience numbers, project ratios, or unrelated `x/4` text.
- Invalid/corrupted browser transfer-history storage must be reset safely and must not interrupt the actual JobAdder transfer.

## 15. Recruiter Typo Tolerance (v24.6.141)

Guaranteed salary-month wording must tolerate common recruiter typing variants in the Current Salary Breakdown, including:

```text
13th month bonus
13th monnth bonus
13th mnth bonus
13th mth bonus
13.5 months / 13.5 mths
14th month / 14th salary
```

These variants still establish the guaranteed total salary months. A separate plain `3 months bonus` remains non-guaranteed and excluded unless explicitly labelled contractual, guaranteed, or fixed.

Regression example:

```text
15% epf + 13th monnth bonus + 3 months bonus + rm10k + rm 400 allowance
```

Deterministic result:

```text
Current = (RM10,000 × 13 ÷ 12) + RM400 = RM11,233/month equivalent
Expected 15–20% = RM12,918 to RM13,480/month
```

EPF and the non-guaranteed three-month bonus remain excluded from the monthly-equivalent value but preserved in the Screening Call breakdown text.


## 16. Salary-Field Typo Normalization (v24.6.142)

Recruiters may type salary components and currencies with inconsistent spelling or no spaces. Apply a conservative deterministic normalization layer only to **Current Salary Breakdown** and **Expected Salary** before component extraction. Keep the original text unchanged for Screening Call storage and display.

Recognize common allowance forms such as:

```text
allowance, allowence, alowance, allwance, allwan, alwance, alwan, alwn, sllowance
```

Recognize common month forms such as:

```text
month, months, monnth, moth, mnth, mth, mths, mthh, monht, monhth
```

This includes attached shorthand such as `13thmth`, `13.5thmoth`, and `2mths fixed bonus`.

Recognize Malaysian Ringgit forms and common typos such as:

```text
RM 2000, 2000RM, MYR2000, 2000MYR, ringgit 2000, 2000rngint, rnggit, ringit, ringgt
```

Also normalize conservative salary-only typo families such as `bonous/bouns` → bonus, `efp` → EPF, and `precent/persent` → percent. Do not use broad fuzzy autocorrection across the full OneNote note because currency or salary-like text in Summary, RFL, Looking For, Leads or Remarks must remain ignored.

DeepSeek may assist with unfamiliar wording, but deterministic code remains the only calculator and the local evidence validator must verify AI components against the salary fields. Identical input must remain idempotent.


## 17. Windows Authy Receipt Fix (v24.6.143)

On Windows, a valid Authy code must be retained until `INSTALL_RECEIPT.ps1 -Mode Write` receives and revalidates it. Do not clear the accepted code before assigning the child-process environment value.

The v24.6.142 failure signature was:

```text
Installer access granted.
Could not create the machine authorization receipt.
Setup finished with exit code 13.
```

v24.6.143 fixes that ordering error. The accepted code is held only for receipt creation and is removed immediately afterward. Existing Authy enrollment remains valid; users do not need to scan a new QR code.


## 18. Desktop OneNote Local-Link/COM Reliability (v24.6.144)

Desktop OneNote links in the form below must be treated as first-class local section links:

```text
onenote:///C:\Users\...\Notebook\Section.one#section-id={...}&end
```

Do not require successful root hierarchy enumeration before using such a link. Decode the `.one` path, call OneNote `OpenHierarchy` with `cftNone`, use the returned section ID, then call `GetHierarchy(sectionId, hsPages)`. The PowerShell fallback should run from a temporary `.ps1` with explicit error exit handling and base64 XML output so a successful process cannot be mistaken for a blank hierarchy merely because stdout capture or console encoding failed.


## 19. Desktop OneNote Notebook-Folder Section Selection (v24.6.145)

A local desktop OneNote link may point to the notebook folder instead of one `.one` section file:

```text
onenote:///C:\Users\...\OneNote Notebooks\My Notebook
```

Do not resolve this input to the first matching section. Enumerate all sections in the notebook and populate the Section picker so the user chooses which section to scan. Combine direct OneNote notebook-hierarchy enumeration with local `.one` file discovery, including section-group subfolders, because some Office/COM installations return only the first section from root hierarchy enumeration.

A full `Section.one` link remains a single-section input. Preserve successful sections even when another local section is unavailable or still an unhydrated OneDrive placeholder; surface a warning rather than failing the entire notebook picker.


## 20. Desktop Section Picker Visibility Fix (v24.6.146)

The Notebook and Section picker row must remain visible in **Web**, **Desktop/manual**, and **Both** source modes. v24.6.145 correctly loaded multiple desktop sections but `oneNoteSourceModeChanged()` hid the entire picker row whenever Desktop mode was selected. This produced the contradictory state where the UI said “Detected 2 sections” but no Section dropdown was visible.

Desktop/manual flow must be:

```text
Paste notebook-folder link
→ Load Notebooks / Sections or Use Manual Link
→ visible Section dropdown is populated
→ user chooses one section
→ Scan Source
```

Never hide the Section selector in Desktop mode. Keep the picker unselected when multiple sections are returned, show the detected count beside the picker, and refuse to scan until the user selects one.

## 21. Saved Desktop/Manual OneNote Links (v24.6.147)

Desktop/manual OneNote links can be saved on the current browser/computer with:

- a user-defined name;
- a category of **Notebook**, **Section**, or **Page**;
- the original manual link or exact section name.

Use a version-independent local-storage key so saved links survive future CV Studio upgrades on the same browser profile. Selecting a saved item fills the manual-link field. `Use Saved` must apply category-aware behavior:

```text
Notebook → load all sections and require the user to choose one
Section  → resolve/list pages from that section
Page     → resolve/list that page
```

Users must be able to update the name/category/link and delete saved entries. Do not store imported OneNote page contents, Microsoft tokens, candidate data, salary values, or JobAdder data in the saved-link collection. Corrupted browser storage must fail safely without breaking the OneNote tab.



## 22. Compact OneNote Guidance UI (v24.6.148)

- Remove non-essential always-visible descriptions from the OneNote console.
- Preserve necessary guidance through hover balloons (`title` tooltips) on info icons, labels, and action buttons.
- Keep operational statuses visible: connection, AI provider/cost, section count/selection, errors, and transfer results.
- Keep error details visible rather than hiding them behind hover-only help.
- This is a UI-only change; OneNote parsing/import, salary/DeepSeek, JobAdder writes, saved links, Authy, machine receipts, and locks remain unchanged.


## 23. OneNote Pages Without Email (v24.6.149)

OneNote page import must not fail merely because the page contains no email address. Import the page text and parse its Screening Call fields into a review row. Display a compact Candidate Email input so the recruiter can add the email later and click Match. Missing email is informational only. JobAdder transfer remains blocked until the row has a matched candidate ID and valid Presentability 1–4. Keep separately imported OneNote pages as separate rows.

## 23. Desktop OneNote Import De-duplication and Email-Optional Review (v24.6.149)

- Importing a selected OneNote page does not require an email address. A page without an email remains visible as an editable review row instead of failing with `No email address found in notes`.
- Email is required only for JobAdder candidate matching/transfer. The recruiter may add the email later and click Match.
- Desktop OneNote XML extraction must read leaf `<one:T>` content only. Do not aggregate ancestor Page/Outline/OE `itertext()` because that repeats nested page content.
- Convert embedded `<br>` markup to real line breaks before parsing.
- A page containing multiple candidate emails must create one independent candidate block per unique email. Later candidates must not inherit earlier candidates' fields.

## 24. Saved OneNote Link Workflow (v24.6.150)

The saved-link interaction supersedes the older visible `Use Saved` flow while preserving the same browser-storage data:

```text
Paste/manual link
→ Use Link opens it
→ Save beside Use Link opens a Name + Category popup
```

Within **Saved links**:

- selecting an entry immediately fills the upper Manual link field;
- the selected entry's Name and Category also populate the editable fields;
- there is no separate Use button in the Saved links row;
- the recruiter may edit the loaded link, name, or category and click **Save Changes**;
- **Save Changes** remains disabled until a saved entry is selected;
- selecting alone must not trigger OneNote Graph/COM or scan pages—the upper **Use Link** button remains the explicit action.

New saves use a popup so the user chooses **Notebook**, **Section**, or **Page** at save time. Preserve the version-independent storage key `cvstudio_onenote_saved_desktop_links_v1`, existing entries, defensive validation, duplicate-link update behaviour, and Delete support.

## 25. Pinned Navigation and Persistent OneNote Picker Attention (v24.6.151)

- The main page-tab button panel remains visible while the document scrolls on desktop/tablet-width layouts. Small screens retain normal flow so a multi-row tab panel does not obstruct most of the viewport.
- The OneNote notebook/section picker uses a stronger red attention outline.
- Picker attention is no longer time-limited; it stays until the user clicks the picker row, one of its fields, or a label.
- New section-loading results can request attention again.
- This UI-only patch does not alter OneNote parsing, saved links, COM/Graph integration, salary rules, JobAdder writes, Authy, machine receipts, installers, locks, or source-removal packaging.


## 26. Optional Main Navigation Pin Toggle (v24.6.152)

- Main feature navigation is no longer permanently sticky.
- A **Pin tabs** control sits in the bottom-right corner of the navigation panel.
- When enabled, the panel remains in normal flow until the document scrolls past it, then becomes a measured fixed-position floating panel at the top of the viewport.
- The control changes to **Pinned** and can be clicked again to restore normal scrolling behaviour.
- The setting persists locally through `cvstudio_page_nav_pinned_v1`.
- Small screens at 760 px and below always retain normal flow and hide the pin control.
- Preserve all existing tab order, locks, activity-status outlines, completion/failure alerts, and settings-layer priority.


## 27. Pinned Navigation Stacking-Context Fix (v24.6.153)

The main navigation and several page views are not all under the same DOM parent. The navigation lives inside `.app`, while OneNote, Dashboard, and other later views are body-level siblings. Wallpaper mode gives each direct body child its own `z-index: 1` stacking context. Therefore, a `position: fixed` navigation that remains inside `.app` can still be painted over by a later sibling view.

When the user has enabled **Pin tabs** and scrolls past the navigation:

- keep the spacer in the original `.app` position;
- measure the spacer for exact left/width alignment;
- temporarily move the floating navigation to `document.body`;
- use a high application-layer z-index below Owl/settings/modal layers;
- restore the navigation immediately after the spacer when unpinned or when scrolled back above its anchor.

Preserve the storage key `cvstudio_page_nav_pinned_v1`, the bottom-right toggle, and the 760 px mobile cutoff.


## 28. Pinned Navigation with Active-Page Scroller (v24.6.154)

The optional `Pin tabs` mode now uses a dedicated active-page scroll viewport once the feature panel floats. The navigation remains fixed at the top, while the currently active long page scrolls below it rather than continuing underneath the panel. The active page is temporarily portalled to `document.body` and restored to its original parent and sibling position when unpinned. Tab changes swap the scroll viewport safely and retain a separate inner scroll position for each tab. The existing storage key `cvstudio_page_nav_pinned_v1`, bottom-right toggle, mobile cutoff at 760 px, Settings/Owl layer ordering, and persistent red OneNote picker attention remain unchanged.

Implementation note: once the pinned workspace has activated, it remains active until the user explicitly unpins it or the viewport becomes mobile. This is intentional because the dedicated page scroller locks document scrolling; trying to infer an automatic scroll-back-to-anchor state would cause repeated pin/unpin oscillation.

## 29. macOS Installer and Launcher Hardening (v24.6.155)

The macOS package must use a dedicated Python virtual environment:

```text
~/.guo_lab_cv_studio/venv
```

Do not install CV Studio Python packages into the global Homebrew/system Python. `install.sh` must create the venv and run its own `python -m pip -r requirements.txt`; `start.sh` must use the same venv interpreter and verify all required imports before launch. This avoids externally-managed Python failures and interpreter/pip mismatches.

The Desktop `CV Studio.command` launcher must point to the exact `start.sh` location used during installation. Do not assume the app folder is only in `~/cv_formatter` or `~/Downloads/cv_formatter`.

Preserve explicit Homebrew PATH support for both:

```text
/opt/homebrew/bin   # Apple Silicon
/usr/local/bin      # Intel
```

Port 5000 remains fixed because the JobAdder OAuth callback is registered at `http://localhost:5000/jobadder/callback`. If another non-Python process holds port 5000, do not kill it; stop with a visible explanation. Desktop/local OneNote COM reading remains Windows-only. macOS users continue using Web/synced Microsoft Graph OneNote or manual pasted notes.


## 30. Batch Missing-Email JobAdder Prompt (v24.6.156)

When Batch Format finishes formatting and JobAdder auto-upload is enabled, a CV with no detected candidate email must remain ready for manual completion. The inline email field must display `Enter email for JobAdder` and use a conspicuous red required-state outline until the recruiter enters an email. Pressing Enter or leaving the field continues through the existing manual-email upload path. Do not change successful automatic uploads where an email was already detected.


## 31. OneNote Unmatched Candidate → Create Profile Bridge (v24.6.157)

When a OneNote screening-note row contains a valid email and JobAdder confirms no candidate match, the row remains visible and displays **Upload CV**. Selecting a PDF, DOCX, or DOC sends the file into the existing Create Profile queue and starts creation automatically. The Create Profile tab uses its existing orange running state. The note email overrides any missing/different email parsed from the CV, preventing cross-candidate creation. The initiating OneNote row shows local running/failure/success feedback; on success it stores the candidate ID/name, displays **Candidate profile is created in JobAdder.**, and becomes a matched row for the normal Screening Call transfer workflow. Profile creation does not automatically transfer the Screening Call.

## 32. OneNote Review, Parsing, Live-Field and Pinned-Notification Hardening (v24.6.157)

- Every selected OneNote page must remain reviewable even when its email is blank; a title-only page must not be silently discarded.
- A blank/invalid candidate-email field in Matched screening notes uses a persistent red pulsating outline and the placeholder `Enter candidate email` until corrected.
- OneNote heading-only layouts may place bounded blank paragraphs between a label and its value. Recognise parenthetical/combined headings including `Reason for Leaving (RFL)`, `Looking For?`, `Current Salary Breakdown (CS)`, `Expected Salary (ES)`, `Notice Period (NP / Availability)`, and `Presentability (Confidence, Comms, Business Awareness)`.
- Continue stopping field collection at the next recognised field, OneNote page marker, different email, or safe name-before-email boundary. Do not regress multi-candidate field isolation.
- Valid Presentability formats include `1`, `2`, `3`, `4`, `1/4` through `4/4`, and a descriptor after the valid fraction such as `3/4 - Good`. Values such as `32`, `10/10`, `14`, or `40` remain invalid.
- Before transfer validation, synchronize the currently visible email, textarea, and Presentability controls into the row model. This prevents an edited control that still has focus from triggering a false missing-field error.
- While Pin tabs is active, global toast notifications must sit above the fixed active-page viewport and below the tab panel vertically. JobAdder modal dialogs and the server reconnect banner must also remain above pinned content.


## 33. OneNote Free-form Canvas / Outline Isolation (v24.6.158)

Desktop OneNote pages are free-form canvases. Each top-level Outline/text box must remain a separate parser block while still reading leaf `<one:T>` nodes only. A single-email block belongs to that candidate even when the email is written at the bottom. Email-less blocks must remain visible as independent review rows, including when the same page has other emailed candidates. Flat imports without Outline markers use repeated core screening headings as a bounded fallback split.


## 34. AI Crawler Two-stage Discovery / Match Fit (v24.6.159)

Candidate retrieval and candidate fit are separate stages. When Boolean Rules / Keywords are available, use them first for JobAdder discovery and do not reject a candidate merely because the CV is not already similar to the JD. Preserve explicit country, residential, IT-skill, qualification, minimum-years and exclude filters as eligibility gates. Then score eligible candidates from 0 to 100 against job scope, role alignment and relevant requirements. Language and education/degree criteria never contribute to the percentage. Return/display every fetched unique candidate at 10% or above, sorted highest fit first, and show keyword-discovery evidence separately from fit evidence.

## 35. Dashboard URL Attachment after JobAdder Upload (v24.6.159)

Dashboard stats records use stable local record IDs. Attach a JobAdder URL to the exact originating record after successful single Format CV upload, Batch Format automatic upload, or Batch Format manual-email upload. The manual-email batch continuation previously set the row-level View link but did not update the Dashboard stats record. Create Profile manual-email continuation must also create a URL-complete Dashboard row. FCV Upload already records only after a URL is available and should retain that behaviour.

## 36. AI Crawler Boolean Keyword-Set Discovery (v24.6.160)

The JobAdder public `Keywords` parameter is documented as a latest-resume keyword search, but it does not promise that a whole string such as `(Trade OR Trading) AND Java` will be parsed as Boolean syntax. AI Crawler must therefore search each atom separately (`Trade`, `Trading`, `Java`) using the official `Keywords`, `Limit`, and `Offset` parameter casing, then combine candidate IDs locally as `(Trade ∪ Trading) ∩ Java`.

JobAdder term-search membership is authoritative discovery evidence because the candidate detail endpoint may not expose the full resume text searched by `Keywords`. Do not reject such candidates merely because the terms are absent from the detail JSON. Internal `_spider*` evidence fields must be excluded from the JD fit blob so discovery evidence does not artificially inflate fit. When Boolean discovery is confirmed but visible detail cannot support a higher fit, retain the candidate at the transparent 10% minimum rather than returning an empty result set.


## 37. JobAdder Native Boolean Candidate Discovery (v24.6.161)

JobAdder candidate `Keywords` search supports native Boolean expressions. When the recruiter enters a rule such as `(Trade OR Trading) AND Java`, send that complete expression once through the official `Keywords` parameter with the existing `Limit`, `Offset`, and optional `Location` parameters. Do not split the atoms into separate searches and do not recombine candidate IDs locally.

Candidates returned by that native Boolean search are authoritative discovery matches. Candidate-detail JSON may omit the latest-resume text searched by JobAdder, so never revalidate the Boolean rule or its `NOT` terms against those partial detail fields. Continue applying the separate Exclude/Avoid field and other explicit hard filters. After discovery, calculate 0-100 JD/job-scope fit separately, excluding language and education, and retain Boolean-confirmed candidates at a minimum transparent 10% when visible detail is insufficient for a higher score.

This section supersedes section 36's atom-by-atom keyword-set workaround.


## 38. OneNote Selected-Row Presentability Validation (v24.6.162)

OneNote transfer validation is scoped to the rows selected for the current transfer.

```text
Selected + matched + valid Presentability 1-4 -> eligible to transfer
Selected + matched + missing/invalid Presentability -> block and warn
Unchecked matched row with missing/invalid Presentability -> leave visible, but do not block other selected ready rows
```

The app must still synchronize live visible inputs before validation. Row-level missing-field warnings remain visible until corrected.


## 39. OneNote Repeat Transfer and Spelling Correction (v24.6.163)

- A successfully transferred row is normally locked in its done state to prevent accidental duplicates. Editing any visible field reopens that same matched row, selects it, and allows a deliberate second transfer. Each successful retry creates a new Candidate Screening Call; no existing activity is edited.
- OneNote Settings has `Correct common OneNote typos while parsing`, default ON, stored in `cvstudio_onenote_spelling_correction_v1`.
- The parser corrects only recognised screening labels and notice-period spellings. Original Notes remain byte-for-display unchanged.
- Supported notice examples include `3 month`, `3month`, `3mothn`, `3monht`, standard abbreviations, bare recruiter numbers such as `3`, and conservative Immediate misspellings such as `immedaite`/`imediate`. Turning the setting off disables the extended typo correction while normal field parsing remains available.


## 40. OneNote Recruitment Vocabulary Correction (v24.6.164)

The default-on OneNote spelling-correction toggle now covers conservative recruitment vocabulary in parsed screening fields, including common misspellings of allowance, contract/contractual, permanent, expatriate, local, nationality, sponsorship, citizenship, relocation, employment, guaranteed, negotiable, availability, environment, experience, communication, presentability, candidate, residential status, visa/work permit, remote/hybrid/onsite.

Safety boundaries:
- Original Notes are never rewritten.
- Candidate name, email and phone are never corrected.
- Brief Overview uses explicit aliases only to reduce risk around company names and technical terminology.
- Fuzzy correction is restricted to an approved recruitment-term allow-list with tight edit-distance, first-character and last-character checks.
- Correct derivatives such as contractor, allowances, employees and candidates are protected.
- Turning the setting off disables both frontend preview correction and backend transfer correction.


## 41. OneNote Inline Candidate Name and Bulk Selection (v24.6.165)

A candidate name may precede a screening field on the same line:

```text
Gavin Tew rfl: wants to transition into end user environment
```

The parser must treat `Gavin Tew` as the candidate name and populate Reason For Leaving from the text after `rfl:`. Consecutive aliases for the same field, such as `Notice Period:` immediately followed by `np:`, must not split one note into two candidates.

After scanning OneNote pages, the page list provides **Select all** and **Unselect all**. In Matched screening notes, **Select all ready** selects only matched, non-completed rows with valid Presentability, and **Unselect all** clears every preview checkbox.


## 42. Batch Format Waiting/Disabled Recovery (v24.6.166)

The Batch lifecycle must not retain an orphaned running latch. If no row is actually `processing`, adding a file or pressing Start must recover the stale state, clear the orange run badge, and enable Start Processing for pending files. `Clear All` resets the timer, startup watchdog, tab run state, and button state unless a genuine row is currently processing. A startup watchdog must release the UI if an exception occurs before the first pending row visibly changes to Processing.


## 43. PPC / Post Placement Care (v24.6.167)

PPC is a read-only JobAdder placement dashboard. It queries the official `GET /placements` endpoint with exact parameter casing and repeated date/type parameters. Default discovery covers approved Permanent, Contract and Temporary placements whose `StartDate` falls within the current calendar year. Quick ranges support Last year and All time; a single refresh is capped at 5,000 records with an explicit truncation warning.

Displayed JobAdder fields include Placement ID, candidate, company, job title, placement type/status, start/end dates, associated placement recruiters where returned by the full placement detail, `createdBy` as a transparent fallback, and job owner. Detail enrichment is bounded to 500 placements per refresh to avoid excessive requests; later or failed detail rows retain summary fallbacks and show a warning. PPC does not create, modify or delete placements.

Two recruiter-managed fields are stored locally by Placement ID under `cvstudio_ppc_meta_v1`:

```text
Payment: Not set / Unpaid / Invoiced / Paid
Guarantee period: Not set / 1 / 2 / 3 / 4 / 5 / 6 months
```

The guarantee end date is calculated from Start Date plus the selected number of months. Local fields survive JobAdder refreshes and appear in filters, KPI tiles and the Excel-compatible export. They are browser-local and must not be represented as JobAdder fields unless a future explicit write-back mapping is approved.


## 44. PPC cache/filter persistence and quick provider controls (v24.6.168)

- PPC stores placement snapshots per query in IndexedDB (`cvstudio_ppc_cache_v1`) and restores the last UI state from `cvstudio_ppc_ui_state_v1`.
- Switching This year, Last year and All time reuses the corresponding saved snapshot when available. Manual Refresh JobAdder fetches current JobAdder fields without clearing local Payment or Guarantee metadata.
- Single CV and Batch Format expose compact Claude/DeepSeek controls. They use existing saved provider keys/models and update the existing `hy_ai_route_cv_single` / `hy_ai_route_cv_batch` route settings.


## 45. PPC Recruiter Accuracy, Guarantee Options and Complete Year Paging (v24.6.169)

- Guarantee Period supports `1, 2, 3, 4, 5, 6, 9, 12 months` and `Resigned / Backout`. The special state is locally stored and does not calculate a guarantee end date.
- `Placed by recruiter` means only the users in JobAdder `Placement.recruiters`. Never include `createdBy`, placement owner, or job owner in that filter. Recruiter filter values use JobAdder user IDs so identical or changed display names cannot cross-match unrelated rows.
- Placement pagination must continue until `totalCount` is reached, even if JobAdder returns fewer rows than the requested `Limit` on an intermediate page. Advance `Offset` by the actual page length.
- PPC cache query keys are schema-versioned; old incomplete current-year snapshots must be invalidated. Start-date range checks remain inclusive of January 1 and December 31.


## 46. PPC Interactive Rows, KPI Quick Filters and Dashboard/Table Visibility (v24.6.170)

- Clicking any PPC placement row applies a green outline to that row and keeps it highlighted until another row is selected.
- The six KPI cards are clickable. `Placements shown` clears the KPI quick filter; `Active now`, `Upcoming starts`, `Ending in 30 days`, `Unpaid`, and `Guarantee ending soon` filter the table on top of all existing PPC filters. Clicking an already selected KPI card clears that quick view.
- KPI counts are based on the normal recruiter/company/date/type/status/payment/guarantee/search result set, before the KPI quick filter is applied.
- Right-clicking anywhere in the KPI card bar opens a checkbox menu for choosing which KPI cards appear. The setting persists locally in `cvstudio_ppc_kpi_visibility_v1`.
- Right-clicking the table header row opens a separate checkbox menu for choosing visible PPC columns. The setting persists in `cvstudio_ppc_column_visibility_v1`; at least one column must remain visible.
- PPC UI persistence stores the active KPI quick filter. If the user hides the active KPI card, CV Studio clears that quick filter so hidden state cannot silently constrain the table.


## 47. Pinned Navigation Notification Layer (v24.6.171)

The global success/error/info toast must remain a viewport-fixed overlay in wallpaper mode. The generic `body.cv-wallpaper-on > *` stacking rule must not convert `#toast` into a normal-flow element or reduce its notification z-index.

When the feature-navigation workspace is floating:

```text
Toast top = pinned navigation bottom + 12 px
Toast right edge = 12 px inside pinned navigation right edge
```

This applies to unlock messages such as `CV Summary unlocked`, processing results, API errors and other global toasts. The toast must stay above the pinned active page and navigation, while unpinning restores its standard top-right viewport position.


## 48. Expanded Quick AI Provider Controls and Regression Audit (v24.6.173)

Direct Claude / DeepSeek controls are available in exactly these seven feature tabs:

```text
Format CV
Batch Format
CV Summary
CV Scoring
The Owl
Blind JD
Company Profile
```

The controls are not separate routing layers. They read and write the same per-feature keys as Settings → AI Routing (`hy_ai_route_<feature>`). The last change made—either in the tab or in Settings—is authoritative. Main API Settings continue to store provider credentials/models; selecting a provider without its saved key must show a configuration warning rather than silently switching providers. All quick panels must be resynchronised together because Batch can inherit Single CV and AI Crawler can inherit The Owl. The route resolver and Settings options must explicitly support `the_owl`; otherwise AI Crawler silently falls back to Main AI. Settings Save/Reset must also refresh route badges so inherited provider labels do not become stale.

Do not add quick toggles to OneNote, AI Crawler, Create Profile, FCV Upload, PPC, Dashboard or Lead Finder unless the user explicitly asks. OneNote salary extraction keeps its dedicated routing behaviour.


## v24.6.173 PPC invoice draft
PPC placement details now expose read-only billing email, payment terms, fee and charge currency for a per-row Outlook invoice-request draft. The internal recipient/greeting are local-only settings and no email is sent automatically.


## 49. PPC Outlook Web reliability and disabled export (v24.6.174)

PPC invoice requests now open through a real browser link to Outlook on the web. The link contains only the encoded subject and body; the `to` parameter is deliberately omitted so the recipient stays blank. The JobAdder billing/client email remains displayed inside the draft body and is never used as the recipient. Invoice setup retains only the greeting name. The PPC Export Excel control is disabled in the UI and its function returns without creating a file.


## 50. PPC saved Outlook invoice recipient (v24.6.175)

The Outlook invoice action uses a locally saved **invoice recipient email** for the Outlook `To` field. This is separate from the JobAdder client/billing email shown inside the draft body. If no valid recipient is stored, the first row-button click prompts for one, saves it under `cvstudio_ppc_invoice_email_v1`, updates the clicked anchor URL during the same user action, and allows the browser to open Outlook Web normally. Invoice setup can update or clear the saved recipient and edit the greeting. PPC Excel export remains disabled.

## 51. PPC complete placement retrieval and email-preview privacy (v24.6.176)

PPC retrieval must not treat a partial JobAdder page as a complete year or all-time result. Fetch Permanent, Contract, Temporary and Credit placement types independently, read each type's `totalCount`, paginate until each expected count is reached, then de-duplicate by Placement ID. A complete All time browser snapshot may seed This year and Last year views, but incomplete responses must not replace a known complete cache.

Full placement details should be enriched for all retrieved rows by default so Placement.recruiters remains accurate beyond the first 500 placements. Preserve local Payment and Guarantee metadata by Placement ID when refreshing or changing date ranges.

Privacy/UI rule: do not display candidate email or JobAdder billing/client email beneath PPC table rows. Candidate and placement links remain visible. The billing/client email may still be inserted into the generated Outlook invoice-request body because that is the user-requested workflow.


## 52. PPC invoice subject and formatted Outlook copy (v24.6.177)

Invoice subjects use:

```text
Hyppies: Invoice - [Client] - [Position] - [Candidate] - [Placed-by Recruiter]
```

The recruiter component must come from the actual Placement recruiter (`placed_by`), never Job Owner. Outlook Web compose deep links are retained for zero-setup access and prefill a plain-text body. Because that deep-link body is plain text, each PPC row also provides `Copy formatted`; it copies an HTML version with black Calibri 11 text, bold labels, and a borderless label/colon/value table for alignment. `Open Outlook Web` also attempts this clipboard copy. Exact rich insertion requires pasting the formatted clipboard content if Outlook renders only the plain-text deeplink body. Client email remains inside the invoice body only and is not previewed on the PPC dashboard.


## 53. PPC Outlook draft navigation reliability (v24.6.178)

`Open Outlook Web` must not rely on changing an anchor URL during default click navigation. It reserves a tab during the original user click and explicitly sends that tab to `https://outlook.office.com/mail/0/deeplink/compose?popoutv2=1` with encoded `to`, `subject`, and `body` parameters. This avoids Outlook opening only its inbox shell with the draft parameters lost. The action still saves/prompts for the internal invoice recipient, retains the Hyppies invoice subject, and attempts the formatted Calibri 11 clipboard copy.


## 54. PPC selected-row highlight geometry (v24.6.178)

PPC row selection must not use real top/bottom borders on cells in the collapsed table because they alter row geometry and can create uneven corners around dropdowns or hidden columns. Use inset shadows: a subtle green fill, 1 px top/bottom lines, a 4 px left accent on the first visible cell, and a 1 px right edge on the last visible cell.


## 55. PPC rich Outlook HTML draft creation (v24.6.179)

Outlook Web compose deeplinks accept the body as plain text and cannot preserve the HTML formatting used by `Copy formatted`. v24.6.179 therefore uses a separate Microsoft Graph delegated connection for PPC rich drafts. The scope is `offline_access User.Read Mail.ReadWrite`; OneNote remains on its existing `offline_access User.Read Notes.Read` connection. PPC creates a draft with `POST /me/messages`, an HTML body, recipient and subject, then opens the returned `webLink`. It never sends the message. The original deeplink was retained as a fallback in v24.6.179, but that fallback is superseded and removed in v24.6.180 because it recreated the rejected plain-text formatting.


## 56. Formatted CV alignment setting (v24.6.179)

General Settings now stores `cvstudio_cv_text_alignment_v1` with two values: `left` (default) and `justify`. The browser passes the value only at DOCX-generation time, after parsing and optional blinding, so the result is independent of Claude/DeepSeek/OpenAI routing. Single and batch formatted/blinded DOCX paths use the same validated backend value. The Node DOCX generator maps `justify` to WordprocessingML `w:jc w:val="both"`; missing or invalid values map to `left`.

The Open Outlook action does not knowingly open the plain-text fallback when rich-draft authorization is missing; it starts the Outlook connection and asks the user to retry after login. Graph-created message web links append `ispopout=1`. A plain fallback remains only for a non-auth Graph/runtime failure, with the correct rich copy still prepared.


## 57. Outlook rich-draft hardening and backend token storage (v24.6.180)

PPC no longer opens the plain-text Outlook compose deeplink when Microsoft Graph draft creation fails. The reserved tab is closed and the user is directed to the separate Copy formatted action. Outlook configuration is explicit and separate from OneNote: a saved Outlook Client ID/tenant must support delegated Mail.ReadWrite plus public-client device-code authentication. Outlook OAuth tokens are stored in an authenticated machine-bound backend file, not browser localStorage; copied or tampered stores do not load. A Graph draft webLink can still open in Outlook reading/review mode, so the UI states that Edit may be required. Batch CV alignment is snapshotted once per run to prevent mixed Left/Justify files.

## 58. Outlook workflow, integrations and selective CV justification (v24.6.181)

PPC Outlook invoice drafts now use a review-first workflow. Each row opens an invoice preview showing the exact recipient, subject, rich HTML body, connected mailbox, and any missing JobAdder invoice fields before draft creation. A placement can have only one draft request in progress, and the backend uses a short-lived idempotency cache keyed by request ID and message payload so accidental duplicate submissions do not create duplicate drafts. The most recent created draft link and timestamp are stored locally per placement for `Open last draft`; creating a draft never changes PPC Payment to Invoiced and never sends the message.

Outlook configuration moved to Settings → Integrations & Data. The page shows the dedicated Microsoft Client ID and tenant, connection status, connected account, secret-storage method, test connection, test draft, reconnect, disconnect, and friendly instructions for Microsoft errors. Raw error detail remains available only inside Technical details. Device-code attempts use independent random expiring login session IDs so parallel browser tabs cannot overwrite one another.

Outlook tokens remain backend-only. v24.6.181 prefers Windows DPAPI on Windows and macOS Keychain on macOS. Linux or an unavailable native vault uses the authenticated machine-bound file fallback. The v24.6.180 protected file is migrated once where possible. Browser localStorage contains only non-secret Outlook settings, a pending random login session ID, and local draft links; it never contains access or refresh tokens.

General Settings retains Left as the default formatted-CV alignment. Justify now applies only to substantive body text, descriptions, and bullets. Section headings, company/date lines, job titles, education headings/details such as institution and degree, and short skills rows remain left aligned. The batch workflow snapshots alignment when a run starts so a mid-run settings change cannot mix alignment modes within that batch.

Integrations & Data can export and restore an explicit whitelist of non-secret local preferences and metadata. It excludes values whose storage key or field names indicate tokens, secrets, passwords, API keys, credentials, Authy data, Microsoft device codes, machine receipts, or owner-only content.

## 59. Decimal notice and local restart hardening (v24.6.182)

Notice parsing must capture the complete decimal token and never allow a regex to restart after the decimal point. Required normalization is `1.5 months → 1 Month`, `2.5 → 2 Months`, `3.5 → 3 Months`, and `0.5 month → 2 Weeks`. Normalization metadata must identify any decimal truncation/conversion.

The local `/restart` action is POST-only and requires `X-CV-Studio-Restart: 1`, loopback client address, and local Origin/Referer validation. Cross-site GET/image restart requests are no longer possible.

The PPC invoice preview is scoped to PPC: switching to any other feature closes it, and its opener refuses to run unless `viewPPC` is active.

