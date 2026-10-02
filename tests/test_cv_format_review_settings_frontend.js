'use strict';
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const html = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
const settings = fs.readFileSync(path.join(__dirname, '../vendor/cvstudio/settings.js'), 'utf8');
const appearance = fs.readFileSync(path.join(__dirname, '../vendor/cvstudio/appearance.js'), 'utf8');
const togglePosition = html.indexOf('id="cvFormattingReviewToggle"');
assert.ok(togglePosition > html.indexOf('id="settingsPaneGeneral"') &&
  togglePosition < html.indexOf('id="settingsPaneDownloads"'), 'the only review toggle belongs in General Settings');
assert.strictEqual((html.match(/id="cvFormattingReviewToggle"/g) || []).length, 1);
assert.ok(/id="cvFormattingReviewToggle"[^>]*onchange="setCvFormattingReview\(this.checked\)"/.test(html));
const blockStart = settings.indexOf('var CV_FORMATTING_REVIEW_STORE');
const blockEnd = settings.indexOf('// ── Word export format', blockStart);
assert.ok(blockStart >= 0 && blockEnd > blockStart, 'saved off-by-default setting');
const block = settings.slice(blockStart, blockEnd);
const key = 'cvstudio_formatting_review_v1';
function context(stored, saveMode) {
  const values = new Map(stored === undefined ? [] : [[key, stored]]);
  const writes = [], events = [], toasts = [];
  const nodes = {cvFormattingReviewToggle: {checked: false}, cvFormattingReviewLabel: {textContent: ''}};
  const c = vm.createContext({window: {}, document: {
    getElementById: id => nodes[id] || null, addEventListener: (name, fn) => events.push(fn)},
    localStorage: {getItem: k => values.has(k) ? values.get(k) : null},
    cvStudioDurableSettingSet: (k,v) => {
      if (saveMode === 'throw') throw new Error('Storage unavailable');
      if (saveMode === 'reject') return Promise.reject(new Error('Storage unavailable'));
      if (saveMode === 'false') return Promise.resolve(false);
      values.set(k,v); writes.push({key:k,value:v}); return Promise.resolve(true);
    },
    showToast: (message,kind) => toasts.push({message,kind}), setTimeout: fn => {fn(); return 1;}});
  vm.runInContext(block, c);
  return {c, values, writes, nodes, events, toasts};
}
for (const stored of [undefined, 'false', '1', 'TRUE', 'invalid']) {
  assert.strictEqual(context(stored).c.getCvFormattingReview(), false, 'only explicit true opts into extra paid checks');
}
const h = context();
h.c.setCvFormattingReview(true, true);
assert.strictEqual(h.c.getCvFormattingReview(), true);
assert.strictEqual(h.nodes.cvFormattingReviewToggle.checked, true);
assert.strictEqual(h.nodes.cvFormattingReviewLabel.textContent, 'On');
assert.deepStrictEqual(h.writes, [{key, value:'true'}]);
assert.strictEqual(context(h.values.get(key)).c.getCvFormattingReview(), true, 'reload restores the saved choice');
h.c.setCvFormattingReview(false, true);
assert.strictEqual(context(h.values.get(key)).c.getCvFormattingReview(), false);
assert.ok(appearance.includes("'cvstudio_formatting_review_v1':1"), 'backup/import allowlist includes only this non-secret setting');
const hydrationStart = appearance.indexOf('function cvStudioRefreshHydratedSettingUi(');
const hydrationEnd = appearance.indexOf('function cvStudioDurableSettingSet(', hydrationStart);
vm.runInContext(appearance.slice(hydrationStart, hydrationEnd), h.c);
h.values.set(key, 'true');
h.c.cvStudioRefreshHydratedSettingUi();
assert.strictEqual(h.c.getCvFormattingReview(), true, 'durable hydration refreshes the preference and control');
assert.strictEqual(h.nodes.cvFormattingReviewToggle.checked, true);
h.values.delete(key);
h.c.cvStudioRefreshHydratedSettingUi();
assert.strictEqual(h.c.getCvFormattingReview(), false, 'a removed durable setting resets safely to off');
async function verifySaveFailures() {
  for (const mode of ['throw','reject','false']) {
    const failed = context(undefined, mode);
    failed.c.setCvFormattingReview(true, true);
    await new Promise(resolve => setImmediate(resolve));
    assert.strictEqual(failed.c.getCvFormattingReview(), true, 'failed save still applies to this page');
    assert.strictEqual(failed.values.has(key), false, 'failed save cannot claim durable persistence');
    assert.ok(failed.toasts.some(toast => toast.kind === 'warn' && toast.message.includes('could not be saved')));
  }
  console.log('CV review Settings: placement, strict opt-in, persistence, failed saves, hydration and backup passed');
}
verifySaveFailures().catch(error => {console.error(error); process.exitCode=1;});
