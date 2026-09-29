'use strict';
// The CV Summary's pay filter lives on the server (_cv_strip_pay_from_summary),
// the only copy. The page asks for it on both summary requests and treats a
// summary the server emptied as "only pay" -- not as a failed paid call, but
// still a paid one whose cost is counted.
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.join(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'vendor/cvstudio/candidate-summary.js'), 'utf8');

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

// No browser copy of the filter, and no regex lookbehind anywhere in the page's
// scripts: Safari before 16.4 rejects it while parsing, taking the whole file down.
assert.ok(!/cvSummaryStripPay|cvSentenceStatesPay/.test(source), 'no browser copy of the filter');
for (const name of fs.readdirSync(path.join(root, 'vendor/cvstudio'))) {
  if (!name.endsWith('.js')) continue;
  const text = fs.readFileSync(path.join(root, 'vendor/cvstudio', name), 'utf8');
  assert.ok(!/\(\?<[=!]/.test(text), name + ' uses regex lookbehind');
}

// Both summary requests ask the server to remove the candidate's pay.
assert.strictEqual((source.match(/strip_candidate_pay:\s*true/g) || []).length, 2);
assert.ok(/prompt:cvSummaryPrompt\(raw, cvSummaryModifierForPreference\(detailPreference\), ''\),\n\s*max_tokens:1000,\n\s*use_tools:false,\n\s*strip_candidate_pay:true/.test(source));
assert.ok(/var summaryRequest = \{[^}]*strip_candidate_pay:true \};/.test(source));
// The instructions forbid it too.
assert.ok(/Never mention the candidate\\'s salary or pay in any form/.test(source));

async function formattingSummary(response) {
  const failures = [], toasts = [];
  const context = {
    String, Array, JSON, Error,
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

(async () => {
  // Every line was pay: the formatting run carries on with an empty Summary box,
  // the paid call's cost goes into the run, a warning says why, and nothing is
  // recorded as a failed paid call.
  {
    const {error, result, failures, toasts} = await formattingSummary({content: [{type: 'text', text: ''}], summary_pay_removed: 2, usage: {output_tokens: 9}});
    assert.strictEqual(error, null);
    assert.deepStrictEqual(JSON.parse(JSON.stringify(result.bullets)), []);
    assert.strictEqual(result.cost, 0.25, 'the paid call is counted with the run');
    assert.deepStrictEqual(JSON.parse(JSON.stringify(result.usage)), {output_tokens: 9});
    assert.strictEqual(result.pay_only, true);
    assert.strictEqual(failures.length, 0, 'not recorded as a failed paid call');
    assert.ok(toasts.length === 1 && /only described the candidate's pay/.test(toasts[0][0]) && toasts[0][1] === 'warn');
  }
  // A genuinely empty answer is still a provider failure, as before.
  {
    const {error, failures} = await formattingSummary({content: [{type: 'text', text: ''}], summary_pay_removed: 0, usage: {}});
    assert.ok(error && /Empty CV Summary returned/.test(error.message));
    assert.strictEqual(failures.length, 1);
  }
  // A filtered summary with lines left is used as it is.
  {
    const {error, result, toasts} = await formattingSummary({content: [{type: 'text', text: '- Built pipelines.'}], summary_pay_removed: 1, usage: {}});
    assert.strictEqual(error, null);
    assert.deepStrictEqual(JSON.parse(JSON.stringify(result.bullets)), ['Built pipelines.']);
    assert.strictEqual(toasts.length, 0);
    assert.ok(!result.pay_only);
  }
  // Both callers take the result as they always have, so the run goes on.
  for (const [file, pattern] of [
    ['cv-format.js', /var summaryResult = await requestFormattingSummary\([^)]*\);\n\s*_parsedData\.summary_bullets = summaryResult\.bullets\.slice\(\);\n\s*_runCost \+= summaryResult\.cost;/],
    ['batch-format.js', /var batchSummaryResult = await requestFormattingSummary\([^)]*\);\n\s*cvData\.summary_bullets = batchSummaryResult\.bullets\.slice\(\);\n\s*bf\.cost \+= batchSummaryResult\.cost;/],
  ]) {
    assert.ok(pattern.test(fs.readFileSync(path.join(root, 'vendor/cvstudio', file), 'utf8')), file);
  }
  // The Summary tab: the same distinction, before its own empty-output record.
  const generate = fnFrom(source, 'generateSummary');
  const payCheck = generate.indexOf("if (!summaryBulletLines(raw).length && d.summary_pay_removed > 0) {");
  const payBranch = generate.slice(payCheck, generate.indexOf('}', payCheck));
  const emptyRecord = generate.indexOf("recordPaidAiFailure('CV Summary returned empty output'");
  assert.ok(payCheck > 0 && emptyRecord > payCheck, 'pay-only is decided before the empty-output record');
  // The paid call is recorded as a summary, then the clear message is shown.
  assert.ok(/statsRecord\([^;]*'summary', responseCost\(d, route\.model, route\.provider\)/.test(payBranch), 'the paid call is recorded');
  assert.ok(payBranch.indexOf('statsRecord(') < payBranch.indexOf('throw new Error'));
  assert.ok(!/recordPaidAiFailure/.test(payBranch));
  console.log('CV Summary pay filter frontend passed');
})().catch(error => { console.error(error); process.exit(1); });
