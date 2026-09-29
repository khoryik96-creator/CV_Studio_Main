'use strict';
// The CV Summary's pay filter lives on the server (_cv_strip_pay_from_summary),
// the only copy. The page asks for it on both summary requests. Whatever the
// server removes is always shown and kept on screen like the source check's
// warning, and holds JobAdder auto-upload the same way; a summary that was only
// pay never aborts a formatting run and its paid call is always counted.
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.join(__dirname, '..');
const read = name => fs.readFileSync(path.join(root, 'vendor/cvstudio', name), 'utf8');
const source = read('candidate-summary.js');
const cvFormat = read('cv-format.js');
const batchFormat = read('batch-format.js');

function fnFrom(src, name) {
  const start = src.search(new RegExp('(?:async\\s+)?function\\s+' + name + '\\('));
  assert.ok(start >= 0, 'missing function: ' + name);
  let depth = 0, quote = '', escaped = false;
  for (let i = src.indexOf('{', start); i < src.length; i += 1) {
    const ch = src[i];
    if (quote) {
      if (escaped) escaped = false;
      else if (ch === '\\') escaped = true;
      else if (ch === quote) quote = '';
      continue;
    }
    // A line comment may hold an apostrophe ("candidate's"); it is not a quote.
    if (ch === '/' && src[i + 1] === '/') { i = src.indexOf('\n', i); continue; }
    if (ch === '"' || ch === "'" || ch.charCodeAt(0) === 96) { quote = ch; continue; }
    if (ch === '{') depth += 1;
    else if (ch === '}' && --depth === 0) return src.slice(start, i + 1);
  }
  throw new Error('unterminated function: ' + name);
}
const plain = value => JSON.parse(JSON.stringify(value));

// No browser copy of the filter, and no regex lookbehind anywhere in the page's
// scripts: Safari before 16.4 rejects it while parsing, taking the whole file down.
assert.ok(!/cvSummaryStripPay|cvSentenceStatesPay/.test(source), 'no browser copy of the filter');
for (const name of fs.readdirSync(path.join(root, 'vendor/cvstudio'))) {
  if (!name.endsWith('.js')) continue;
  assert.ok(!/\(\?<[=!]/.test(read(name)), name + ' uses regex lookbehind');
}

// Both summary requests ask the server to remove the candidate's pay.
assert.strictEqual((source.match(/strip_candidate_pay:\s*true/g) || []).length, 2);
assert.ok(/prompt:cvSummaryPrompt\(raw, cvSummaryModifierForPreference\(detailPreference\), ''\),\n\s*max_tokens:1000,\n\s*use_tools:false,\n\s*strip_candidate_pay:true/.test(source));
assert.ok(/var summaryRequest = \{[^}]*strip_candidate_pay:true \};/.test(source));
// The instructions forbid it too.
assert.ok(/Never mention the candidate\\'s salary or pay in any form/.test(source));

// ── the note ────────────────────────────────────────────────────────────────
{
  const c = {String, Number};
  vm.createContext(c);
  vm.runInContext(fnFrom(source, 'cvSummaryPayNote') + fnFrom(source, 'cvJoinWarnings'), c);
  assert.strictEqual(c.cvSummaryPayNote(0, false), '');
  assert.strictEqual(c.cvSummaryPayNote(undefined, true), '');
  assert.strictEqual(c.cvSummaryPayNote('2', false), "Removed 2 sentences about the candidate's pay from the CV Summary. Check the Summary before sending.");
  assert.strictEqual(c.cvSummaryPayNote(1, false), "Removed 1 sentence about the candidate's pay from the CV Summary. Check the Summary before sending.");
  assert.strictEqual(c.cvSummaryPayNote(3, true), "The CV Summary only described the candidate's pay, so the Summary box was left empty.");
  assert.strictEqual(c.cvJoinWarnings('', 'B.'), 'B.');
  assert.strictEqual(c.cvJoinWarnings('A.', ''), 'A.');
  assert.strictEqual(c.cvJoinWarnings('A.', 'B.'), 'A. B.');
}

// ── requestFormattingSummary ────────────────────────────────────────────────
async function formattingSummary(response) {
  const failures = [], toasts = [];
  const context = {
    String, Array, JSON, Error, Number,
    fetchWithTimeout: async () => ({ok: true, json: async () => response}),
    aiText: data => (data.content || []).map(block => block.text || '').join(''),
    recordPaidAiFailure: (...args) => failures.push(args),
    showToast: (...args) => toasts.push(args),
    normalizeAiProviderError: s => s, responseCost: () => 0.25,
    cvModel: '',
  };
  vm.createContext(context);
  vm.runInContext(fnFrom(source, 'summaryBulletLines') + fnFrom(source, 'cvSummaryPrompt') +
    fnFrom(source, 'cvSummaryModifierForPreference') + fnFrom(source, 'requestFormattingSummary'), context);
  let error = null, result = null;
  try {
    result = await context.requestFormattingSummary('RAW CV', {api_key: 'k', provider: 'anthropic', model: 'm'}, 'concise');
  } catch (e) {
    error = e;
  }
  return {error, result, failures, toasts};
}

// ── the batch flow, with synthetic responses ───────────────────────────────
async function batchRun(responses) {
  const uploads = [], nodes = {};
  const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const c = {String, Array, Object, JSON, Math, Promise, Number, console,
    window: {_jaToken: 'synthetic-token'}, FormData: class { append() {} }, Blob: class {},
    document: {getElementById(id) {
      return nodes[id] || (nodes[id] = {value: '', checked: false, disabled: false, dataset: {},
        style: {display: ''}, textContent: '', innerHTML: '', querySelector() { return null; },
        querySelectorAll() { return []; }, classList: {add() {}, remove() {}, contains() { return false; }}});
    }},
    esc, escAttr: s => esc(s).replace(/"/g, '&quot;').replace(/'/g, '&#39;'),
    setTimeout() { return 1; }, clearTimeout() {}, setInterval() { return 1; }, clearInterval() {},
    showToast() {}, clearTabRunState() {}, markTabRunning: () => 1, markTabDone() {}, markTabFailed() {},
    aiRoutePayload: () => ({api_key: 'synthetic-key', provider: 'mock'}),
    getCvTextAlignment: () => 'left', getCvBlindCandidateGenderNeutralization: () => false,
    getCvSummaryBoxAutoFit: () => true, getCvAutoCorrectLanguage: () => false,
    normalizeUsageClient: () => ({}), mergeUsageClient: () => ({}), responseCost: () => 0,
    cvRequireCompleteExtraction() {}, cvParseIsLong: () => false, cvParseTimeoutMs: () => 1000,
    CV_EXTRACT_TEXT_TIMEOUT_MS: 1000, cvMergeLevelLists: () => [], recordPaidAiFailure() {},
    normalizeAiProviderError: s => s, extractNameFromFilename: () => '', toTitleCase: s => s,
    statsRecord: () => 1, statsMetaFromResponse: () => ({}), statsAttachJobAdderUrl() {},
    jaProfileUrlAsync: async () => '',
    batchUploadToJobAdder: async (...args) => { uploads.push(args); return 'cand-1'; },
    fetchWithTimeout: async url => {
      if (url === '/extract-text') return {json: async () => ({text: 'Synthetic CV'})};
      if (url === '/parse') return {ok: true, json: async () => responses.parse};
      if (url === '/blind') return {ok: true, json: async () => responses.blind};
      const headers = responses.docxHeaders || {};
      return {ok: true, blob: async () => ({serial: 1}), headers: {get: name => (name in headers ? headers[name] : null)}};
    },
  };
  vm.createContext(c);
  vm.runInContext(batchFormat, c);
  // The page loads cv-format.js and candidate-summary.js too.
  vm.runInContext(fnFrom(cvFormat, 'cvParseWarningText') + fnFrom(source, 'cvSummaryPayNote') +
    fnFrom(source, 'cvJoinWarnings'), c);
  c.batchSetProgress = () => {}; c.updateBatchSummary = () => {};
  if (responses.mode) c._batchMode = responses.mode;
  c._batchFiles = [{id: 'f1', file: {name: 'f1.pdf', arrayBuffer: async () => new ArrayBuffer(1)}, status: 'pending'}];
  await c.runBatch();
  return {c, uploads, nodes};
}

(async () => {
  // Every line was pay: the formatting run carries on with an empty Summary box,
  // the paid call's cost goes into the run, and nothing is recorded as a failed
  // paid call. The caller keeps the warning on screen.
  {
    const {error, result, failures, toasts} = await formattingSummary({content: [{type: 'text', text: ''}], summary_pay_removed: 2, usage: {output_tokens: 9}});
    assert.strictEqual(error, null);
    assert.deepStrictEqual(plain(result.bullets), []);
    assert.strictEqual(result.cost, 0.25, 'the paid call is counted with the run');
    assert.deepStrictEqual(plain(result.usage), {output_tokens: 9});
    assert.strictEqual(result.pay_only, true);
    assert.strictEqual(result.pay_removed, 2);
    assert.strictEqual(failures.length, 0, 'not recorded as a failed paid call');
    assert.strictEqual(toasts.length, 0, 'the caller shows it, where it stays');
  }
  // A genuinely empty answer is still a provider failure, as before.
  {
    const {error, failures} = await formattingSummary({content: [{type: 'text', text: ''}], summary_pay_removed: 0, usage: {}});
    assert.ok(error && /Empty CV Summary returned/.test(error.message));
    assert.strictEqual(failures.length, 1);
  }
  // A filtered summary with lines left is used, and the removal is reported.
  {
    const {error, result} = await formattingSummary({content: [{type: 'text', text: '- Built pipelines.'}], summary_pay_removed: 1, usage: {}});
    assert.strictEqual(error, null);
    assert.deepStrictEqual(plain(result.bullets), ['Built pipelines.']);
    assert.ok(!result.pay_only);
    assert.strictEqual(result.pay_removed, 1);
  }
  // A summary with nothing removed reports nothing.
  {
    const {result} = await formattingSummary({content: [{type: 'text', text: '- Built pipelines.'}], usage: {}});
    assert.strictEqual(result.pay_removed, 0);
  }

  // Batch: a clean CV still uploads automatically, exactly as before.
  const candidate = {candidate: {name: 'Same Name', email: 'someone@example.test'}};
  {
    const {c, uploads} = await batchRun({parse: {data: candidate}});
    assert.strictEqual(c._batchFiles[0].status, 'done-ok');
    assert.strictEqual(c._batchFiles[0].parseWarning, '');
    assert.strictEqual(uploads.length, 1);
  }
  // Pay removed by /parse, by the Word file's last net, or by /blind: the row
  // keeps the note and auto-upload waits, as for the source check.
  for (const [label, responses, expected] of [
    ['parse', {parse: {data: candidate, summary_pay_removed: 1}}, 'Removed 1 sentence'],
    ['docx', {parse: {data: candidate}, docxHeaders: {'X-CV-Summary-Pay-Removed': '2'}}, 'Removed 2 sentences'],
    ['blind', {mode: 'blind', parse: {data: candidate}, blind: {data: {candidate: {name: 'Candidate', email: 'someone@example.test'}}, summary_pay_removed: 1}}, 'Removed 1 sentence'],
  ]) {
    const {c, uploads, nodes} = await batchRun(responses);
    const bf = c._batchFiles[0];
    assert.ok(/^done-/.test(bf.status), label + ' finishes: ' + bf.status);
    assert.ok(bf.parseWarning.includes(expected), label + ': ' + bf.parseWarning);
    assert.strictEqual(uploads.length, 0, label + ': not auto-uploaded');
    assert.ok(bf._jaHeld, label + ': held for the recruiter');
    c.renderBatchList();
    assert.ok(nodes.batchFileList.innerHTML.includes('about the candidate&#39;s pay') ||
      nodes.batchFileList.innerHTML.includes("about the candidate's pay"), label + ' row shows it');
  }
  // A source-check warning and a pay note are both kept.
  {
    const {c} = await batchRun({parse: {data: candidate, warning: 'Employer(s) missing: Beta', summary_pay_removed: 1}});
    assert.strictEqual(c._batchFiles[0].parseWarning,
      "Employer(s) missing: Beta Removed 1 sentence about the candidate's pay from the CV Summary. Check the Summary before sending.");
  }

  // Single CV: the same notes join the one kept warning, and the automatic
  // summary's note comes from the result, pay-only or not.
  {
    const flow = cvFormat.slice(cvFormat.indexOf('async function startFormat('), cvFormat.indexOf('function toTitleCase('));
    assert.ok(/if \(data\.summary_pay_removed\) parseWarning = cvJoinWarnings\(parseWarning, cvSummaryPayNote\(data\.summary_pay_removed, false\)\);\n\s*if \(parseWarning\) showToast\(parseWarning, 'warn'\);/.test(flow));
    assert.ok(/_parsedData\.summary_bullets = summaryResult\.bullets\.slice\(\);\n\s*if \(summaryResult\.pay_removed\) parseWarning = cvJoinWarnings\(parseWarning, cvSummaryPayNote\(summaryResult\.pay_removed, summaryResult\.pay_only\)\);\n\s*_runCost \+= summaryResult\.cost;/.test(flow));
    assert.ok(/if \(bData\.summary_pay_removed\) parseWarning = cvJoinWarnings/.test(flow));
    // All of it before the banner and the auto-upload decision.
    const banner = flow.indexOf('cvShowParseWarningBanner(parseWarning);');
    assert.ok(flow.indexOf('bData.summary_pay_removed') < banner);
    const docxNote = flow.indexOf("res2.headers.get('X-CV-Summary-Pay-Removed')");
    const hold = flow.indexOf("if (parseWarning) {\n        document.getElementById('jaStatus').textContent");
    assert.ok(docxNote > banner && hold > docxNote, 'the Word file note is shown and holds upload');
    assert.ok(/cvShowParseWarningBanner\(docxPayNote\);/.test(flow));
  }
  // Batch: the automatic summary's note joins the row warning.
  assert.ok(/cvData\.summary_bullets = batchSummaryResult\.bullets\.slice\(\);\n\s*if \(batchSummaryResult\.pay_removed\) bf\.parseWarning = cvJoinWarnings\(bf\.parseWarning, cvSummaryPayNote\(batchSummaryResult\.pay_removed, batchSummaryResult\.pay_only\)\);\n\s*bf\.cost \+= batchSummaryResult\.cost;/.test(batchFormat));

  // The Summary tab: pay-only is decided before its own empty-output record, the
  // paid call is recorded as a summary first, and a partial removal is shown.
  const generate = fnFrom(source, 'generateSummary');
  const payCheck = generate.indexOf("if (!summaryBulletLines(raw).length && d.summary_pay_removed > 0) {");
  const payBranch = generate.slice(payCheck, generate.indexOf('}', payCheck));
  const emptyRecord = generate.indexOf("recordPaidAiFailure('CV Summary returned empty output'");
  assert.ok(payCheck > 0 && emptyRecord > payCheck, 'pay-only is decided before the empty-output record');
  assert.ok(/statsRecord\([^;]*'summary', responseCost\(d, route\.model, route\.provider\)/.test(payBranch), 'the paid call is recorded');
  assert.ok(payBranch.indexOf('statsRecord(') < payBranch.indexOf('throw new Error'));
  assert.ok(!/recordPaidAiFailure/.test(payBranch));
  assert.ok(/var payNote = cvSummaryPayNote\(d\.summary_pay_removed, false\);/.test(generate));
  assert.ok(/renderSummaryText\(raw\) \+ \(payNote \? '<div class="cv-parse-warning" role="note">\\u26a0 ' \+ esc\(payNote\) \+ '<\/div>' : ''\)/.test(generate));
  assert.ok(/if \(payNote\) showToast\(payNote, 'warn'\);/.test(generate));
  console.log('CV Summary pay filter frontend passed');
})().catch(error => { console.error(error); process.exit(1); });
