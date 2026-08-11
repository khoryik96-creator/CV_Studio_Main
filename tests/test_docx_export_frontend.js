'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const source = fs.readFileSync(
  path.resolve(__dirname, '..', 'vendor', 'cvstudio', 'docx-export.js'),
  'utf8',
);
const context = vm.createContext({
  Array,
  ArrayBuffer,
  Blob,
  DataView,
  Object,
  String,
  TextEncoder,
  Uint8Array,
});
vm.runInContext(source, context);

function text(value) {
  return {nodeType: 3, nodeValue: value};
}

function element(tagName, children, textContent) {
  return {
    nodeType: 1,
    tagName,
    childNodes: children || [],
    textContent: textContent == null ? '' : textContent,
    querySelectorAll() { return []; },
  };
}

function preformattedRawReportSurvives() {
  const body = element('BODY', [
    element('PRE', [text('RAW REPORT\nSecond line')], 'RAW REPORT\nSecond line'),
  ]);
  const blocks = context._docxWalk(body, [], 0, false);
  assert.strictEqual(blocks.length, 1);
  assert.strictEqual(blocks[0].type, 'paragraph');
  assert.strictEqual(blocks[0].runs[0].text, 'RAW REPORT\nSecond line');

  const xml = context._docxDocumentXml(blocks, '', '');
  assert.ok(xml.includes('RAW REPORT'));
  assert.ok(xml.includes('<w:br/>'));
  assert.ok(xml.includes('Second line'));
}

function nestedListTextIsNotDuplicatedInParent() {
  const nested = element('UL', [
    element('LI', [text('Child')]),
  ]);
  const list = element('UL', [
    element('LI', [text('Parent'), nested]),
  ]);
  const blocks = context._docxWalk(element('BODY', [list]), [], 0, false);

  assert.strictEqual(blocks.length, 2);
  assert.strictEqual(blocks[0].runs.map(run => run.text).join(''), 'Parent');
  assert.strictEqual(blocks[0].level, 0);
  assert.strictEqual(blocks[1].runs.map(run => run.text).join(''), 'Child');
  assert.strictEqual(blocks[1].level, 1);
  assert.strictEqual(
    blocks.reduce((count, block) => count + block.runs.filter(run => run.text === 'Child').length, 0),
    1,
  );
}

preformattedRawReportSurvives();
nestedListTextIsNotDuplicatedInParent();
console.log('DOCX export frontend regression tests passed.');
