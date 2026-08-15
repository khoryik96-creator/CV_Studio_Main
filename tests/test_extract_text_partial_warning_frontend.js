'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const runtime = fs.readFileSync(path.join(root, 'vendor', 'cvstudio', 'runtime-core.js'), 'utf8');
const start = runtime.indexOf('function cvExtractionWarningText');
const end = runtime.indexOf('function cvParseIsLong', start);
if (start < 0 || end < 0) throw new Error('Extraction warning helpers were not found');

const shown = [];
const context = vm.createContext({
  String,
  Error,
  showToast(message, type) { shown.push({message, type}); },
});
vm.runInContext(runtime.slice(start, end), context);

assert.strictEqual(context.cvExtractionWarningText({ok:true, text:'complete'}), '');
assert.strictEqual(
  context.cvExtractionWarningText({partial_extraction:true, warning:'Review this partial CV.'}),
  'Review this partial CV.'
);
assert.strictEqual(
  context.cvShowExtractionWarning({partial_extraction:true, warning:'Review this partial CV.'}),
  'Review this partial CV.'
);
assert.deepStrictEqual(shown, [{message:'Review this partial CV.', type:'warn'}]);
assert.doesNotThrow(() => context.cvRequireCompleteExtraction({ok:true}, 'Batch formatting'));
assert.throws(
  () => context.cvRequireCompleteExtraction(
    {partial_extraction:true, warning:'Review this partial CV.'},
    'Batch formatting'
  ),
  /Batch formatting stopped\. Review this partial CV\./
);

const css = fs.readFileSync(path.join(root, 'vendor', 'cvstudio', 'app.css'), 'utf8');
assert.match(css, /\.toast\.warn\s*\{/);

console.log('Partial extraction warning frontend regression tests passed.');
