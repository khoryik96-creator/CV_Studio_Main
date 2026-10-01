'use strict';
// Simulated complete single-CV lifecycles: no provider, upload or browser calls.
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'vendor/cvstudio/cv-format.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const toggle = html.match(/<input[^>]*id="cvFormattingReviewToggle"[^>]*>/);
assert.ok(toggle, 'the user can switch the additional AI check on and off');
assert.ok(!/\bchecked\b/.test(toggle[0]), 'no added paid call by default');
const original = {candidate: {name: 'Synthetic Candidate', email: 'synthetic@example.test'},
  work_experiences: [{company: 'Contoso', roles: [{title: 'Analyst', bullets: ['Built reports.']}]}],
  education: [], skills: [], certifications: []};
const issue = {id: '1', message: '<img src=x onerror=alert(1)> Missing job',
  source_quote: 'Northwind | Manager\nLed operations.', can_apply: true,
  operation: {op: 'add', path: '/work_experiences/-', value: {company: 'Northwind',
    roles: [{title: 'Manager', bullets: ['Led operations.']}]}}};
const clone = value => JSON.parse(JSON.stringify(value));
function harness(options = {}) {
  const nodes = {}, calls = [], uploads = [], stats = [], rendered = [];
  function element(tag = 'div') {
    return {tagName: tag, children: [], style: {}, value: '', checked: false, disabled: false,
      textContent: '', innerHTML: '', className: '', dataset: {},
      classList: {add() {}, remove() {}, contains() { return false; }},
      appendChild(child) { this.children.push(child); return child; },
      replaceChildren(...children) { this.children = children; this.textContent = ''; },
      setAttribute() {}, focus() {}, addEventListener() {}, insertBefore(child) { this.children.unshift(child); },
      querySelectorAll() { return []; }};
  }
  const get = id => nodes[id] || (nodes[id] = element());
  get('cvInput').value = 'Original synthetic CV';
  get('cvFormattingReviewToggle').checked = !!options.on;
  const c = {String, Object, Array, JSON, Math, Date, Promise, console,
    window: {_jaToken: 'synthetic-token'}, document: {getElementById: get, createElement: element},
    _activeInputTab: 'paste', _extractedText: '', _extractedBulletLevels: [], _labelBulletLevels: [],
    _parsedData: null, _startTime: Date.now(), _runCost: 0,
    setInterval() { return 1; }, clearInterval() {},
    setTimeout(fn, ms) { if (ms === 500) uploads.push(fn); return 1; }, clearTimeout() {},
    showToast() {}, markTabRunning: () => 1, markTabDone() {}, markTabFailed() {},
    clearTabRunState() {}, clearFormatSummaryDraft() {},
    showProgress() {}, hideProgress() {}, setProgress() {}, stopTimer() {},
    aiRoutePayload: () => ({api_key: 'synthetic', api_key_slot: 'main_deepseek', provider: 'deepseek', model: 'deepseek-chat'}),
    formatSummaryBulletsFor: () => [], applyFormatSummaryBullets: data => data,
    getCvBlindCandidateGenderNeutralization: () => false, getCvAutoCorrectLanguage: () => false,
    getCvTextAlignment: () => 'left', getCvSummaryBoxAutoFit: () => true,
    cvParseIsLong: () => false, cvParseTimeoutMs: () => 1000,
    normalizeUsageClient: () => ({}), mergeUsageClient: (a,b) => ({api_calls: (a.api_calls || 0) + (b.api_calls || 0)}),
    responseCost: data => data.cost || 0, statsMetaFromResponse: data => data,
    statsRecord(...args) { stats.push(args); return 1; }, recordPaidAiFailure() {},
    normalizeAiProviderError: text => text, cvMergeLevelLists: () => [], cvSummaryPayNote: () => '',
    cvJoinWarnings: (a,b) => [a,b].filter(Boolean).join(' '), uploadToJobAdder() {},
    fetchWithTimeout: async (url, init) => {
      const body = JSON.parse(init.body);
      calls.push({url, body});
      if (url === '/parse') return {ok: true, text: async () => JSON.stringify({data: clone(original), cost: 1, usage: {api_calls: 1}})};
      if (url === '/blind') return {ok: true, text: async () => JSON.stringify({data: clone(original), cost: 1})};
      if (url === '/generate-docx') {
        if (options.exportFailure && calls.filter(call => call.url === url).length > 1) return {ok: false, text: async () => '{"error":"Export failed"}'};
        return {ok: true, blob: async () => ({serial: calls.length}), headers: {get: name => name === 'X-CV-Format-Review-Applied' && body.format_review_applied && !options.missingApprovalHeader ? '1' : null}};
      }
      if (body.feature === 'cv_format_review_apply') {
        if (options.applyDelay) await options.applyDelay;
        const data = clone(original);
        data.work_experiences.push(clone(issue.operation.value));
        return {ok: true, text: async () => JSON.stringify({data, format_review_applied: {signature: 'proof'}})};
      }
      if (options.reviewDelay) await options.reviewDelay;
      if (options.fail) throw new Error('Provider unavailable');
      return {ok: true, text: async () => JSON.stringify({ok: true, cost: 2, usage: {api_calls: 1},
        format_review_base: clone(original), format_review: {status: options.unavailable ? 'unavailable' : 'reviewed',
          message: 'Review complete', signature: 'synthetic-proof', issues: options.clean ? [] : [clone(issue)]}})};
    }};
  Object.defineProperty(c, '_isBlind', {get() { return c.window._isBlind; }});
  vm.createContext(c);
  vm.runInContext(source, c);
  c.renderPreview = data => {
    rendered.push(clone(data));
    if (options.previewFailure && data.work_experiences.length > 1) throw new Error('Preview failed');
  };
  c.cvShowParseWarningBanner = () => {};
  return {c, nodes, calls, uploads, stats, rendered};
}
function descendants(node) { return [node, ...node.children.flatMap(descendants)]; }
async function run() {
  for (const blind of [false, true]) {
    const h = harness({on: blind});
    await h.c.startFormat(blind);
    assert.strictEqual(h.calls.filter(call => call.body.feature === 'cv_format_review').length, 0, 'off/default and Blind do not spend on review');
    assert.ok(h.c.window._docxBlob);
  }
  {
    const h = harness({on: true});
    await h.c.startFormat(false);
    assert.strictEqual(h.calls.filter(call => call.body.feature === 'cv_format_review').length, 1);
    assert.deepStrictEqual(clone(h.c._parsedData), original, 'review never applies a change');
    assert.strictEqual(h.uploads.length, 0, 'issues hold auto-upload');
    assert.strictEqual(h.c._runCost, 3, 'the extra call is included in format cost');
    const content = descendants(h.nodes.cvFormattingReviewPanel);
    assert.ok(content.some(node => node.textContent.includes('<img src=x')), 'provider message appears only as text');
    assert.ok(content.some(node => node.textContent === 'Apply fix'));
    const originalBlob = h.c.window._docxBlob;
    await h.c.cvApplyFormattingReview('1');
    assert.strictEqual(h.c._parsedData.work_experiences.length, 2);
    assert.strictEqual(h.calls.filter(call => call.body.feature === 'cv_format_review').length, 1, 'apply causes no extra paid review');
    assert.ok(h.calls[h.calls.length - 1].body.format_review_applied);
    assert.strictEqual(h.uploads.length, 0, 'applying never uploads automatically');
    assert.strictEqual(h.c._runCost, 3, 'applying and rebuilding spend no AI cost');
    h.c.cvUndoFormattingReview();
    assert.deepStrictEqual(clone(h.c._parsedData), original, 'undo restores exact previous content');
    assert.strictEqual(h.c.window._docxBlob, originalBlob, 'undo restores the exact original file');
  }
  for (const options of [{on: true, fail: true}, {on: true, unavailable: true}]) {
    const h = harness(options);
    await h.c.startFormat(false);
    assert.ok(h.c.window._docxBlob, 'review failure keeps the completed Word file');
    assert.strictEqual(h.nodes.btnDocx.disabled, false);
    assert.strictEqual(h.uploads.length, 0, 'failed/unverified review holds auto-upload');
    assert.strictEqual(h.calls.filter(call => call.body.feature === 'cv_format_review').length, 1, 'a failed paid review is never retried automatically');
  }
  {
    const h = harness({on: true, clean: true});
    await h.c.startFormat(false);
    assert.strictEqual(h.uploads.length, 1, 'a clean review preserves the established upload behavior');
  }
  {
    const h = harness({on: true});
    await h.c.startFormat(false);
    await h.c.cvCheckFormattingReviewAgain();
    assert.strictEqual(h.calls.filter(call => call.body.feature === 'cv_format_review').length, 2);
    assert.strictEqual(h.stats.filter(row => row[1] === 'format_review').length, 1, 'explicit rechecks are recorded separately');
    assert.strictEqual(h.nodes.btnFormat.disabled, false);
    assert.strictEqual(h.c.window._cvFormattingReview.busy, false);
    assert.strictEqual(h.nodes.costPill.textContent, 'Est. cost: $5.0000');
  }
  for (const failure of [{exportFailure: true}, {missingApprovalHeader: true}, {previewFailure: true}]) {
    const h = harness(Object.assign({on: true}, failure));
    await h.c.startFormat(false);
    const blob = h.c.window._docxBlob;
    await h.c.cvApplyFormattingReview('1');
    assert.strictEqual(h.c.window._docxBlob, blob, 'failed regeneration retains previous file');
    assert.deepStrictEqual(clone(h.c._parsedData), original);
  }
  {
    const h = harness({on: true});
    await h.c.startFormat(false);
    h.nodes.cvInput.value = 'Different CV';
    const count = h.calls.length;
    await h.c.cvApplyFormattingReview('1');
    assert.strictEqual(h.calls.length, count, 'changed input cannot receive an old fix');
  }
  {
    let release;
    const wait = new Promise(resolve => { release = resolve; });
    const h = harness({on: true, reviewDelay: wait});
    const formatting = h.c.startFormat(false);
    while (!h.calls.some(call => call.body.feature === 'cv_format_review')) await Promise.resolve();
    h.nodes.cvInput.value = 'Different CV';
    release(); await formatting;
    assert.ok(h.c.window._docxBlob);
    assert.strictEqual(h.stats.filter(row => row[1] === 'format_review').length, 1, 'completed stale reviews retain their paid accounting');
    assert.strictEqual(h.nodes.btnFormat.disabled, false);
    assert.strictEqual(h.nodes.btnDocx.disabled, false);
    assert.ok(descendants(h.nodes.cvFormattingReviewPanel).some(node => node.textContent.includes('input changed')));
  }
  {
    let release;
    const wait = new Promise(resolve => { release = resolve; });
    const h = harness({on: true, reviewDelay: wait});
    const formatting = h.c.startFormat(false);
    while (!h.calls.some(call => call.body.feature === 'cv_format_review')) await Promise.resolve();
    h.c.clearInput();
    release(); await formatting;
    assert.strictEqual(h.c.window._docxBlob, null, 'late review cannot restore a cleared CV');
    assert.strictEqual(h.stats.filter(row => row[1] === 'format_review').length, 1, 'clearing cannot hide a completed paid review');
    assert.strictEqual(h.nodes.btnFormat.disabled, false, 'clearing a pending review restores controls');
    assert.strictEqual(h.nodes.cvFormattingReviewPanel.style.display, 'none');
  }
  {
    const options = {on: true};
    const h = harness(options);
    await h.c.startFormat(false);
    options.fail = true;
    await h.c.cvCheckFormattingReviewAgain();
    assert.strictEqual(h.stats.filter(row => row[1] === 'format_review').length, 0, 'a failed recheck is not recorded as a successful zero-cost review');
    assert.strictEqual(h.nodes.btnFormat.disabled, false);
  }
  {
    let release;
    const wait = new Promise(resolve => { release = resolve; });
    const h = harness({on: true, applyDelay: wait});
    await h.c.startFormat(false);
    const applying = h.c.cvApplyFormattingReview('1');
    h.c.cvResetFormattingReview();
    h.c._parsedData = {candidate: {name: 'Another CV'}};
    const differentBlob = {different: true};
    h.c.window._docxBlob = differentBlob;
    release();
    await applying;
    assert.strictEqual(h.c.window._docxBlob, differentBlob, 'late apply cannot overwrite a new CV');
    assert.strictEqual(h.c._parsedData.candidate.name, 'Another CV');
  }
  console.log('AI formatting review frontend: toggle, source evidence, apply/undo, cost, failure and stale-run checks passed');
}
run().catch(error => { console.error(error); process.exitCode = 1; });
