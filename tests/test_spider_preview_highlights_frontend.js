'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const source = fs.readFileSync(
  path.resolve(__dirname, '..', 'vendor', 'cvstudio', 'ai-crawler.js'),
  'utf8'
);
const css = fs.readFileSync(
  path.resolve(__dirname, '..', 'vendor', 'cvstudio', 'app.css'),
  'utf8'
);

function sourceBlock(startMarker, endMarker) {
  const start = source.indexOf(startMarker);
  const end = source.indexOf(endMarker, start + startMarker.length);
  assert.ok(start >= 0, startMarker + ' must remain present');
  assert.ok(end > start, endMarker + ' must follow ' + startMarker);
  return source.slice(start, end);
}

const matching = sourceBlock(
  'function escapeTheSpiderRegex(',
  'function renderTheSpiderBooleanHighlights('
);
const context = {};
vm.runInNewContext(matching, context);

const unusualText = 'Financial\u00a0reporting uses of\ufb01ce account-\ning controls.';
const phraseHits = context.findTheSpiderBooleanTermHits(
  unusualText,
  'Financial reporting'
);
assert.strictEqual(phraseHits.length, 1, 'NBSP must behave like normal spacing');
assert.strictEqual(
  unusualText.slice(phraseHits[0].start, phraseHits[0].end),
  'Financial\u00a0reporting'
);

const ligatureHits = context.findTheSpiderBooleanTermHits(unusualText, 'office');
assert.strictEqual(ligatureHits.length, 1, 'NFKC ligatures must remain highlightable');
assert.strictEqual(
  unusualText.slice(ligatureHits[0].start, ligatureHits[0].end),
  'of\ufb01ce'
);

const wrappedHits = context.findTheSpiderBooleanTermHits(unusualText, 'accounting');
assert.strictEqual(wrappedHits.length, 1, 'line-wrap hyphenation must not hide a term');
assert.strictEqual(
  unusualText.slice(wrappedHits[0].start, wrappedHits[0].end),
  'account-\ning'
);
assert.deepStrictEqual(
  Array.from(context.findTheSpiderBooleanTermHits('accountingx', 'accounting')),
  [],
  'normal word boundaries must remain protected'
);

assert.ok(
  source.includes('function applyTheSpiderHtmlBooleanHighlights(terms)') &&
    source.includes("data-spider-html-highlight', 'boolean'") &&
    source.includes('hasTheSpiderDirectVisualHighlightSurface()'),
  'DOCX/converted-DOC HTML previews must receive direct Boolean highlights'
);
assert.ok(
  css.includes('.spider-cv-doc-html mark.boolean-positive') &&
    css.includes('.spider-cv-doc-html mark.boolean-negative') &&
    css.includes('.spider-cv-doc-html mark.boolean-mixed'),
  'HTML preview highlights must keep the established positive/negative/mixed legend'
);

console.log('spider preview highlight reliability frontend tests passed');
