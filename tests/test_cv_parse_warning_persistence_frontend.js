'use strict';
// The /parse source check's warning has to stay on screen.
//
// It used to be a 3.5-second toast. In the single-CV flow the very next line
// showed "Parsed! Generating DOCX..." in the same toast slot, so the warning was
// visible for well under a second: a CV the app itself had flagged as missing
// three employers was delivered with nobody having seen the flag. In a batch each
// file's toast replaced the previous file's.
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const read = name => fs.readFileSync(path.join(root, 'vendor', 'cvstudio', name), 'utf8');
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
    if (ch === '"' || ch === "'" || ch.charCodeAt(0) === 96) { quote = ch; continue; }
    if (ch === '{') depth += 1;
    else if (ch === '}' && --depth === 0) return src.slice(start, i + 1);
  }
  throw new Error('unterminated function: ' + name);
}

// ── single CV: the banner itself ─────────────────────────────────────────────
function bannerContext() {
  const inserted = [];
  const outputBox = {
    firstChild: {marker: 'preview'},
    insertBefore(node, ref) { inserted.push({node, ref}); },
  };
  const context = {
    String,
    document: {
      getElementById(id) { return id === 'outputBox' ? outputBox : null; },
      createElement(tag) {
        const attrs = {};
        return {tag, className: '', textContent: '', attrs,
          setAttribute(k, v) { attrs[k] = v; },
          set innerHTML(v) { throw new Error('the banner must never be built from HTML'); }};
      },
    },
  };
  vm.createContext(context);
  vm.runInContext(fnFrom(cvFormat, 'cvShowParseWarningBanner'), context);
  return {context, inserted, outputBox};
}

{
  const {context, inserted, outputBox} = bannerContext();
  // The message names employers taken from an uploaded CV, so it is text.
  const hostile = 'Employer(s) missing: <img src=x onerror=alert(1)> Acme & Co';
  context.cvShowParseWarningBanner(hostile);
  assert.strictEqual(inserted.length, 1);
  const {node, ref} = inserted[0];
  assert.strictEqual(ref, outputBox.firstChild, 'the banner goes above the preview');
  assert.strictEqual(node.tag, 'div');
  assert.strictEqual(node.className, 'cv-parse-warning');
  assert.strictEqual(node.attrs.role, 'alert');
  assert.ok(node.textContent.includes(hostile), 'the message is carried verbatim as text');
}
{
  const {context, inserted} = bannerContext();
  for (const empty of ['', '   ', null, undefined]) context.cvShowParseWarningBanner(empty);
  assert.strictEqual(inserted.length, 0, 'no warning, no banner');
}

// ── single CV: where the flow calls it ───────────────────────────────────────
{
  const flow = cvFormat;
  const preview = flow.indexOf('renderPreview(_parsedData);');
  const banner = flow.indexOf('cvShowParseWarningBanner(parseWarning);');
  const parsedToast = flow.indexOf("'Parsed! Generating DOCX…'");
  assert.ok(preview > 0 && banner > 0 && parsedToast > 0);
  // renderPreview replaces the whole output panel, so the banner must follow it.
  assert.ok(banner > preview, 'the banner is added after the preview renders');
  // A warning shown via toast only would be overwritten by this next toast.
  assert.ok(banner < parsedToast);
  // The warning is read from the response and kept in a variable the end of the
  // flow can still see.
  assert.ok(/var parseWarning = cvParseWarningText\(data, blind\);/.test(flow));
  // A flagged run does not finish on a green "Done!".
  assert.ok(/if \(parseWarning\) showToast\('Done — but read the warning above the preview/.test(flow));
  assert.ok(/else showToast\('Done! Click Download DOCX', 'ok'\);/.test(flow));
}

// ── batch: the warning stays on the file it belongs to ───────────────────────
function batchContext(files) {
  const nodes = {};
  const esc = s => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const context = {
    String, Array, Object, JSON, Math,
    window: {},
    document: {getElementById(id) {
      return nodes[id] || (nodes[id] = {innerHTML: '', style: {}, classList: {add() {}, remove() {}}});
    }},
    esc, escAttr: s => esc(s).replace(/"/g, '&quot;').replace(/'/g, '&#39;'),
  };
  vm.createContext(context);
  vm.runInContext(batchFormat, context);
  context._batchFiles = files;
  context.renderBatchList();
  return nodes.batchFileList.innerHTML;
}

{
  const hostile = 'Employer(s) missing: <script>alert(1)</script>';
  const html = batchContext([
    {id: 'a', file: {name: 'a.docx'}, status: 'done-ok', parseWarning: hostile},
    {id: 'b', file: {name: 'b.docx'}, status: 'done-ok'},
    {id: 'c', file: {name: 'c.docx'}, status: 'done-blind', parseWarning: 'Blind check'},
  ]);
  assert.strictEqual((html.match(/class="cv-parse-warning batch"/g) || []).length, 2,
    'one warning per flagged file, none on the clean one');
  assert.ok(!html.includes('<script>alert(1)</script>'), 'the warning is escaped');
  assert.ok(html.includes('&lt;script&gt;alert(1)&lt;/script&gt;'));
  assert.ok(html.includes('Blind check'));
}
{
  // Until a file finishes, its row shows progress, not a verdict.
  const html = batchContext([
    {id: 'p', file: {name: 'p.docx'}, status: 'processing', parseWarning: 'too early'},
    {id: 'q', file: {name: 'q.docx'}, status: 'pending', parseWarning: 'too early'},
    {id: 'r', file: {name: 'r.docx'}, status: 'done-err', error: 'x', parseWarning: 'too early'},
  ]);
  assert.ok(!html.includes('cv-parse-warning'));
}
{
  // The batch flow reads the field with its own helper rather than one from
  // another module: an earlier draft did, and a harness that loads this module
  // on its own marked every file failed.
  assert.ok(/bf\.parseWarning = batchParseWarningText\(pData, isBlind\);/.test(batchFormat));
  assert.ok(!/cvParseWarningText/.test(batchFormat));
}
{
  // The row is rebuilt on every progress update of every other file, and a
  // role="alert" node is announced again each time it is re-inserted.
  const html = batchContext([{id: 'a', file: {name: 'a.docx'}, status: 'done-ok', parseWarning: 'x'}]);
  assert.ok(html.includes('class="cv-parse-warning batch" role="note"'));
  assert.ok(!html.includes('role="alert"'));
}

// ── Blind mode: the warning must not name the employers it just hid ──────────
{
  const fidelity = {warning: 'Employer(s) present in the CV but missing from the parsed result: Acme Sdn Bhd',
    degraded_reason: 'fidelity_check'};
  const truncated = {warning: 'This CV was long and the AI response was cut off.',
    degraded_reason: 'truncated_response_bracket_salvage'};
  for (const [src, name] of [[cvFormat, 'cvParseWarningText'], [batchFormat, 'batchParseWarningText']]) {
    const context = {String};
    vm.createContext(context);
    vm.runInContext(fnFrom(src, name), context);
    const f = context[name];
    assert.strictEqual(f(fidelity, false), fidelity.warning, name + ': formatting keeps the detail');
    const blind = f(fidelity, true);
    assert.ok(blind && !blind.includes('Acme'), name + ': blind mode names no employer');
    assert.ok(/source check flagged/i.test(blind));
    assert.strictEqual(f(truncated, true), truncated.warning, name + ': other warnings unchanged');
    assert.strictEqual(f({}, true), '');
    assert.strictEqual(f(null, false), '');
  }
}

// ── auto-upload waits for a flagged CV to be checked ─────────────────────────
{
  // Single CV: the 500 ms auto-upload is the else-branch of the warning.
  const flow = cvFormat.slice(cvFormat.indexOf('async function startFormat('), cvFormat.indexOf('function toTitleCase('));
  assert.ok(flow.length > 1000);
  const held = flow.indexOf("if (parseWarning) {\n        document.getElementById('jaStatus').textContent = '⏸ Auto-upload paused");
  const upload = flow.indexOf('setTimeout(function() { uploadToJobAdder(); }, 500);');
  assert.ok(held > 0 && upload > held, 'a flagged CV is not auto-uploaded');
  assert.strictEqual((flow.match(/uploadToJobAdder\(\)/g) || []).length, 1);
}

async function batchRun(pData) {
  const uploads = [];
  const nodes = {};
  const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const c = {String, Array, Object, JSON, Math, Promise, console,
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
      if (url === '/parse') return {ok: true, json: async () => pData};
      return {ok: true, blob: async () => ({serial: 1})};
    },
  };
  vm.createContext(c);
  vm.runInContext(batchFormat, c);
  c.batchSetProgress = () => {}; c.updateBatchSummary = () => {};
  c._batchFiles = [{id: 'f1', file: {name: 'f1.pdf', arrayBuffer: async () => new ArrayBuffer(1)}, status: 'pending'}];
  await c.runBatch();
  return {c, uploads, nodes};
}

const batchUploadChecks = (async () => {
  const candidate = {candidate: {name: 'Same Name', email: 'someone@example.test'}};
  // A clean CV is still uploaded automatically, exactly as before.
  {
    const {c, uploads} = await batchRun({data: candidate});
    assert.strictEqual(c._batchFiles[0].status, 'done-ok');
    assert.strictEqual(uploads.length, 1, 'a clean CV auto-uploads');
    assert.ok(!c._batchFiles[0]._jaHeld);
  }
  // A flagged CV is held until the recruiter chooses to send it.
  {
    const {c, uploads, nodes} = await batchRun({data: candidate, warning: 'Employer(s) missing: Beta',
      degraded_reason: 'fidelity_check'});
    const bf = c._batchFiles[0];
    assert.strictEqual(bf.status, 'done-ok');
    assert.strictEqual(uploads.length, 0, 'a flagged CV is not auto-uploaded');
    assert.ok(bf._jaHeld);
    c.renderBatchList();
    assert.ok(nodes.batchFileList.innerHTML.includes('Upload anyway'));
    await c.uploadHeldBatchFile('f1');
    assert.strictEqual(uploads.length, 1, 'Upload anyway sends it');
    assert.strictEqual(uploads[0][2], 'someone@example.test');
    await c.uploadHeldBatchFile('f1');
    assert.strictEqual(uploads.length, 1, 'and only once');
    c.renderBatchList();
    assert.ok(!nodes.batchFileList.innerHTML.includes('Upload anyway'));
    // Signed out: nothing is sent and no button is offered.
    const again = await batchRun({data: candidate, warning: 'w', degraded_reason: 'fidelity_check'});
    again.c.window._jaToken = '';
    await again.c.uploadHeldBatchFile('f1');
    assert.strictEqual(again.uploads.length, 0);
    again.c.renderBatchList();
    assert.ok(!again.nodes.batchFileList.innerHTML.includes('Upload anyway'));
  }
})();

// ── Create Profile keeps its warning on the file's row ───────────────────────
{
  const createProfile = read('create-profile.js');
  const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const list = {innerHTML: ''};
  const context = {String, esc, escAttr: s => esc(s).replace(/"/g, '&quot;'),
    document: {getElementById(id) { return id === 'jaCreateList' ? list : null; }}};
  vm.createContext(context);
  vm.runInContext(fnFrom(createProfile, 'renderJACreateList'), context);
  context._jaCreateQueue = [
    {id: 'x', file: {name: 'x.pdf'}, status: 'done', statusText: 'Done', parseWarning: 'Flagged <b>x</b>'},
    {id: 'y', file: {name: 'y.pdf'}, status: 'done', statusText: 'Done'},
  ];
  vm.runInContext('var _jaCreateQueue = this._jaCreateQueue;', context);
  context.renderJACreateList();
  assert.strictEqual((list.innerHTML.match(/cv-parse-warning/g) || []).length, 1);
  assert.ok(list.innerHTML.includes('Flagged &lt;b&gt;x&lt;/b&gt;'));
  // A re-run clears the previous run's warning before parsing again.
  assert.ok(/item\.status = 'processing'; item\.statusText = '⏳ Extracting CV…'; item\.jaClass = 'show uploading';\n    item\.parseWarning = '';/.test(createProfile));
  assert.ok(/item\.parseWarning = String\(parsed\.warning \|\| ''\)\.trim\(\);/.test(createProfile));
}

// ── the style exists and matches the app's amber warning ─────────────────────
{
  const css = read('app.css');
  assert.ok(/\.cv-parse-warning \{ background: #FFF7D6; color: #7A5200;/.test(css));
  assert.ok(/\.cv-parse-warning\.batch \{/.test(css));
}

batchUploadChecks
  .then(() => console.log('PASS: CV parse warning persistence'))
  .catch(error => { console.error(error); process.exit(1); });
