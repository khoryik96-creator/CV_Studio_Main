'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const html = require('./frontend_sources').frontendSource();
const loaderSource = fs.readFileSync(path.join(root, 'vendor', 'cvstudio', 'lazy-loader.js'), 'utf8');

function sourceContract() {
  assert.strictEqual((html.match(/<script[^>]+vendor\/jspdf\.umd\.min\.js/g) || []).length, 0);
  assert.strictEqual((html.match(/<script[^>]+vendor\/cvstudio\/lazy-loader\.js/g) || []).length, 1);
  assert.strictEqual((loaderSource.match(/\/vendor\/jspdf\.umd\.min\.js\?v=24\.6\.79/g) || []).length, 1);
  [
    ['exportAnonJDPDF', 'PDF library not loaded — try Word export instead'],
    ['exportCompanyPDF', 'PDF library not loaded — try Word export instead'],
    ['exportAppraiserPDF', 'PDF library not loaded — try Word export instead'],
    ['exportTheOwlPDF', 'PDF library not loaded - try Word export instead'],
  ].forEach(([name, message]) => {
    const start = html.indexOf('function ' + name + '()');
    const next = html.indexOf('\nfunction ', start + 10);
    const source = html.slice(start, next < 0 ? html.length : next);
    assert.ok(start >= 0, 'missing global PDF entry point ' + name);
    assert.ok(source.includes('if (!(window.jspdf && window.jspdf.jsPDF)) {'), name + ' accepts a partial jsPDF namespace');
    assert.ok(source.includes('window.cvStudioLoadJSPDF(' + name), name + ' does not wait at its existing entry point');
    assert.ok(source.includes(message), name + ' changed its established visible error');
  });
}

function loaderContract() {
  const appended = [];
  const removed = [];
  const deferredErrors = [];
  const document = {
    createElement(tag) {
      assert.strictEqual(tag, 'script');
      return {
        attributes: {},
        parentNode: {removeChild(element) { removed.push(element); }},
        setAttribute(name, value) { this.attributes[name] = value; },
      };
    },
    head: {appendChild(element) { appended.push(element); }},
  };
  const window = {setTimeout(callback) { try { callback(); } catch (error) { deferredErrors.push(error); } }};
  vm.runInNewContext(loaderSource, {window, document, Object, Array});
  assert.strictEqual(typeof window.cvStudioLoadClassicScript, 'function');
  assert.strictEqual(typeof window.cvStudioLoadJSPDF, 'function');

  const calls = [];
  window.cvStudioLoadJSPDF(() => calls.push('first'), () => calls.push('first-failure'));
  window.cvStudioLoadJSPDF(() => calls.push('second'), () => calls.push('second-failure'));
  assert.strictEqual(appended.length, 1, 'concurrent first entries must share one request');
  assert.strictEqual(appended[0].src, '/vendor/jspdf.umd.min.js?v=24.6.79');
  assert.strictEqual(appended[0].async, true);
  assert.strictEqual(appended[0].attributes['data-cvstudio-lazy-asset'], 'jspdf');
  window.jspdf = {jsPDF: function FakePDF() {}};
  appended[0].onload();
  assert.deepStrictEqual(calls, ['first', 'second'], 'every first invocation must resume after readiness');

  window.cvStudioLoadJSPDF(() => calls.push('ready'), () => calls.push('unexpected-failure'));
  assert.strictEqual(appended.length, 1, 'ready subsequent entry must not request again');
  assert.strictEqual(calls[calls.length - 1], 'ready', 'ready subsequent entry must remain synchronous');

  delete window.jspdf;
  window.cvStudioLoadJSPDF(() => calls.push('partial-ready'), () => calls.push('partial-failure'));
  assert.strictEqual(appended.length, 2);
  window.jspdf = {};
  appended[1].onload();
  assert.strictEqual(calls[calls.length - 1], 'partial-failure', 'an incomplete namespace must fail visibly');
  assert.strictEqual(removed.length, 1, 'an incomplete script must be removed');
  window.cvStudioLoadJSPDF(() => calls.push('partial-retry-success'), () => calls.push('partial-retry-failure'));
  assert.strictEqual(appended.length, 3, 'a retained partial namespace must not block retry');
  window.jspdf.jsPDF = function FakePDF() {};
  appended[2].onload();
  assert.strictEqual(calls[calls.length - 1], 'partial-retry-success');

  delete window.jspdf;
  window.cvStudioLoadJSPDF(() => calls.push('retry-success'), () => calls.push('visible-failure'));
  assert.strictEqual(appended.length, 4);
  appended[3].onerror();
  assert.strictEqual(calls[calls.length - 1], 'visible-failure');
  assert.strictEqual(removed.length, 2, 'failed partial script must be removed');
  window.cvStudioLoadJSPDF(() => calls.push('retry-success'), () => calls.push('retry-failure'));
  assert.strictEqual(appended.length, 5, 'failure state must be cleared for a safe retry');
  window.jspdf = {jsPDF: function FakePDF() {}};
  appended[4].onload();
  assert.strictEqual(calls[calls.length - 1], 'retry-success');

  delete window.jspdf;
  window.cvStudioLoadJSPDF(() => { throw new Error('first callback failed'); }, () => calls.push('unexpected-failure'));
  window.cvStudioLoadJSPDF(() => calls.push('after-throw'), () => calls.push('unexpected-failure'));
  window.jspdf = {jsPDF: function FakePDF() {}};
  appended[5].onload();
  assert.strictEqual(calls[calls.length - 1], 'after-throw', 'one export failure must not strand another concurrent entry');
  assert.strictEqual(deferredErrors.length, 1);
}

sourceContract();
loaderContract();
console.log('PASS: optional jsPDF loads once on demand, resumes all entries, and retries visibly');
