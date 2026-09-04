'use strict';

// Auto-correct (spelling / punctuation / capitalization) General Settings
// toggle: persistence + wiring into the CV parse request for single and batch
// formatting.

const assert = require('assert');
const vm = require('vm');
const html = require('./frontend_sources').frontendSource();

function functionRange(source, name) {
  const marker = 'function ' + name + '(';
  const start = source.indexOf(marker);
  if (start < 0) throw new Error('Missing function: ' + name);
  const brace = source.indexOf('{', start + marker.length);
  let depth = 0, quote = '', escaped = false, lineComment = false, blockComment = false;
  for (let index = brace; index < source.length; index += 1) {
    const char = source[index], next = source[index + 1] || '';
    if (lineComment) { if (char === '\n') lineComment = false; continue; }
    if (blockComment) { if (char === '*' && next === '/') { blockComment = false; index += 1; } continue; }
    if (quote) { if (escaped) escaped = false; else if (char === '\\') escaped = true; else if (char === quote) quote = ''; continue; }
    if (char === '/' && next === '/') { lineComment = true; index += 1; continue; }
    if (char === '/' && next === '*') { blockComment = true; index += 1; continue; }
    if (char === '"' || char === "'" || char.charCodeAt(0) === 96) { quote = char; continue; }
    if (char === '{') depth += 1;
    if (char === '}' && --depth === 0) return source.slice(start, index + 1);
  }
  throw new Error('Unterminated function: ' + name);
}

function buildContext() {
  const durable = [];
  const toasts = [];
  const nodes = {
    cvAutoCorrectLanguageToggle: { checked: false },
    cvAutoCorrectLanguageLabel: { textContent: '' },
  };
  const context = vm.createContext({
    window: {},
    CV_AUTOCORRECT_LANGUAGE_STORE: 'cvstudio_autocorrect_language_v1',
    document: { getElementById(id) { return nodes[id] || null; } },
    localStorage: { _v: {}, getItem(k) { return k in this._v ? this._v[k] : null; },
      setItem(k, v) { this._v[k] = String(v); } },
    cvStudioDurableSettingSet(key, value) { durable.push({ key, value }); },
    showToast(msg, type) { toasts.push({ msg, type }); },
  });
  vm.runInContext(
    functionRange(html, 'getCvAutoCorrectLanguage') + '\n' +
    functionRange(html, 'renderCvAutoCorrectLanguageSetting') + '\n' +
    functionRange(html, 'setCvAutoCorrectLanguage'),
    context,
  );
  return { context, durable, toasts, nodes };
}

function defaultsOffAndTogglesOn() {
  const env = buildContext();
  assert.strictEqual(env.context.getCvAutoCorrectLanguage(), false, 'off by default');

  const on = env.context.setCvAutoCorrectLanguage(true);
  assert.strictEqual(on, true);
  assert.strictEqual(env.context.getCvAutoCorrectLanguage(), true);
  assert.deepStrictEqual(env.durable[0], { key: 'cvstudio_autocorrect_language_v1', value: 'true' });
  assert.strictEqual(env.nodes.cvAutoCorrectLanguageToggle.checked, true);
  assert.strictEqual(env.nodes.cvAutoCorrectLanguageLabel.textContent, 'On');
  assert.strictEqual(env.toasts.length, 1, 'announces the change');
  assert.ok(env.toasts[0].msg.toLowerCase().includes('auto-correct'));
}

function togglesOffAndRespectsSilent() {
  const env = buildContext();
  env.context.setCvAutoCorrectLanguage(true);
  const off = env.context.setCvAutoCorrectLanguage(false, true); // silent
  assert.strictEqual(off, false);
  assert.strictEqual(env.context.getCvAutoCorrectLanguage(), false);
  assert.strictEqual(env.durable[env.durable.length - 1].value, 'false');
  assert.strictEqual(env.nodes.cvAutoCorrectLanguageLabel.textContent, 'Off');
  // Only the first (non-silent) toggle produced a toast.
  assert.strictEqual(env.toasts.length, 1);
}

function wiredIntoParseAndSettings() {
  // Both the single and batch format flows must forward the flag to /parse.
  const parseCalls = (html.match(/auto_correct_language:\s*getCvAutoCorrectLanguage\(\)/g) || []).length;
  assert.ok(parseCalls >= 2, 'single and batch /parse requests both send the flag, saw ' + parseCalls);
  // Durable-key allowlist and the Settings control exist.
  assert.ok(html.includes("'cvstudio_autocorrect_language_v1':1"), 'key registered as durable');
  assert.ok(html.includes('id="cvAutoCorrectLanguageToggle"'), 'toggle control present');
  assert.ok(html.includes('onchange="setCvAutoCorrectLanguage(this.checked)"'), 'toggle wired to setter');
}

const cases = [
  ['defaults off and toggles on', defaultsOffAndTogglesOn],
  ['toggles off and respects silent', togglesOffAndRespectsSilent],
  ['wired into parse requests and settings', wiredIntoParseAndSettings],
];

let failures = 0;
for (const [name, fn] of cases) {
  try { fn(); console.log('PASS:', name); }
  catch (e) { failures += 1; console.error('FAIL:', name, '-', e && e.message ? e.message : e); }
}
if (failures) { process.exitCode = 1; }
else { console.log('Auto-correct language frontend fixtures passed'); }
