'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const html = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');
const start = html.indexOf('var _externalScriptIds = null;');
const end = html.indexOf('function buildReport()', start);
if (start < 0 || end < 0) throw new Error('Doctor element scanner source was not found');
const scannerSource = html.slice(start, end);

async function dynamicAndOptionalIdsAreNotReportedMissing() {
  const scripts = [
    {src: '', textContent: "getElementById('inline-required')"},
    {src: 'http://127.0.0.1:5000/vendor/cvstudio/fixture.js', textContent: ''},
  ];
  const moduleSource = [
    "getElementById('dynamic-created')",
    "getElementById('directly-created')",
    "getElementById('external-required')",
    "getElementById('jaSettingsPanel')",
    "'<div id=\"dynamic-created\"></div>'",
    "node.id = 'directly-created'",
    "var id = 'external-required'",
  ].join(';');
  const document = {
    getElementsByTagName(name) {
      assert.strictEqual(name, 'script');
      return scripts;
    },
    getElementById() { return null; },
  };
  const context = vm.createContext({
    document,
    fetch() {
      return Promise.resolve({ok: true, text() { return Promise.resolve(moduleSource); }});
    },
    location: {href: 'http://127.0.0.1:5000/', origin: 'http://127.0.0.1:5000'},
    Object,
    Promise,
    URL,
  });
  vm.runInContext(scannerSource, context);
  context.scanExternalScripts();
  await new Promise(resolve => setImmediate(resolve));

  const missing = Array.from(context.missingElements()).sort();
  assert.deepStrictEqual(missing, ['external-required', 'inline-required']);
}

dynamicAndOptionalIdsAreNotReportedMissing().then(() => {
  console.log('Doctor frontend regression tests passed.');
}).catch(error => {
  console.error(error && error.stack ? error.stack : error);
  process.exitCode = 1;
});
