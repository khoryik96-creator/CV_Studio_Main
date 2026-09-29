'use strict';
// The browser's salary filter for the Summary box must behave exactly like the
// server's (_cv_strip_pay_from_summary in cvstudio_cv_normalize.py). Both run the
// "summary_salary" cases in tests/fixtures/cv_guardrail_cases.json; the Python
// side is tests/test_cv_guardrail_cases.py.
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.join(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'vendor/cvstudio/candidate-summary.js'), 'utf8');
function functionSource(name) {
  const start = source.indexOf('function ' + name + '(');
  const end = source.indexOf('\n}', start);
  assert(start >= 0 && end > start, 'Missing complete declaration: ' + name);
  return source.slice(start, end + 2);
}
const context = vm.createContext({});
// Arrays made inside the sandbox have their own prototype, so compare contents.
const plain = value => JSON.parse(JSON.stringify(value));
vm.runInContext(functionSource('cvSentenceStatesPay') + functionSource('cvSummaryStripPay') +
  functionSource('summaryBulletLines'), context);

const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/cv_guardrail_cases.json'), 'utf8'))
  .cases.filter(c => c.kind === 'summary_salary');
assert(cases.length >= 30, 'the shared salary cases are present');
for (const c of cases) {
  assert.deepStrictEqual(plain(context.cvSummaryStripPay(c.bullets)), c.expect, c.id + ': ' + c.note);
}
// Every AI summary reaches the page through summaryBulletLines.
assert.deepStrictEqual(
  plain(context.summaryBulletLines('- **Senior engineer** with 11 years.\n- Expected salary RM16,000.\n- Built pipelines.')),
  ['**Senior engineer** with 11 years.', 'Built pipelines.']);
// The summary instructions forbid it too.
assert(/Never mention the candidate\\'s salary or pay in any form/.test(source));
console.log('CV Summary salary parity passed (' + cases.length + ' shared cases)');
