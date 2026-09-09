'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.join(__dirname, '..');
const generator = fs.readFileSync(path.join(root, 'generate.js'), 'utf8');
const browser = fs.readFileSync(path.join(root, 'vendor/cvstudio/cv-format.js'), 'utf8');
function functionSource(source, name) {
  const start = source.indexOf('function ' + name + '(');
  const end = source.indexOf('\n}', start);
  assert(start >= 0 && end > start, 'Missing complete declaration: ' + name);
  return source.slice(start, end + 2);
}
const context = vm.createContext({});
for (const name of ['MONTH_ABBR', 'MONTH_ABBR_BY_NUMBER']) {
  const start = generator.indexOf('const ' + name + ' =');
  assert(start >= 0, name);
  vm.runInContext(generator.slice(start, generator.indexOf(';', start) + 1), context);
}
vm.runInContext(functionSource(generator, 'normalizeDateRange') +
  functionSource(browser, 'cvNormMonth') + functionSource(browser, 'cvNormDateRange'), context);
function outputs(input) {
  return {generator: context.normalizeDateRange(input), browser: context.cvNormDateRange(input)};
}
if (process.argv.includes('--probe')) {
  process.stdout.write(JSON.stringify(JSON.parse(fs.readFileSync(0, 'utf8')).map(outputs)));
} else {
  const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/cv_date_cases.json'), 'utf8'));
  for (const [input, expected] of cases) {
    assert.deepStrictEqual(outputs(input), {generator: expected, browser: expected}, input);
    assert.deepStrictEqual(outputs(expected), {generator: expected, browser: expected}, 'idempotence: ' + input);
  }
  console.log('CV date parity frontend fixtures passed (' + cases.length + ' cases, both normalizers)');
}
