'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
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
    if (char === '}' && --depth === 0) return {start, end: index + 1, source: source.slice(start, index + 1)};
  }
  throw new Error('Unterminated function: ' + name);
}

function functions(names) {
  return names.map(name => {
    if (name === 'renderJAUploadList') {
      const start = html.indexOf('function renderJAUploadList(');
      const end = html.indexOf('function setBatchManualEmail(', start);
      if (start < 0 || end < 0) throw new Error('Missing bounded function: ' + name);
      return html.slice(start, end);
    }
    if (name === 'escAttr') {
      const start = html.indexOf('function escAttr(');
      const end = html.indexOf('function leadIsDirectJobUrl(', start);
      if (start < 0 || end < 0) throw new Error('Missing bounded function: ' + name);
      return html.slice(start, end);
    }
    return functionRange(html, name).source;
  }).join('\n');
}

async function candidateNotFoundDialogEscapesEmail() {
  const appended = [];
  const removed = [];
  const document = {
    createElement() {
      return {
        style: {},
        innerHTML: '',
        addEventListener(type, listener) {
          if (type === 'click') this.clickListener = listener;
        },
      };
    },
    body: {
      appendChild(node) { appended.push(node); },
      removeChild(node) { removed.push(node); },
    },
  };
  const context = vm.createContext({console, document, Promise, Object, Array, String, JSON});
  vm.runInContext(functions(['esc', 'showJADialog']), context);

  const email = 'notfound<&>@example.invalid';
  let rejection = null;
  const choicePromise = context.showJADialog(email).catch(error => {
    rejection = error;
    return 'rejected';
  });
  await Promise.resolve();
  if (rejection) throw rejection;

  assert.strictEqual(appended.length, 1, 'candidate-not-found dialog should be appended');
  const overlay = appended[0];
  assert.ok(overlay.innerHTML.includes('notfound&lt;&amp;&gt;@example.invalid'));
  assert.ok(!overlay.innerHTML.includes(email));
  assert.ok(overlay.innerHTML.includes('data-ja-choice="skip"'));
  assert.ok(overlay.innerHTML.includes('data-ja-choice="create"'));
  overlay.clickListener({
    target: {
      getAttribute(name) { return name === 'data-ja-choice' ? 'skip' : null; },
    },
  });
  assert.strictEqual(await choicePromise, 'skip');
  assert.deepStrictEqual(removed, [overlay]);
}

function uploadQueueEscapesMatchedAndUnmatchedEntries() {
  const list = {innerHTML: ''};
  const context = vm.createContext({
    console,
    document: {getElementById(id) { return id === 'jaUploadList' ? list : null; }},
    Object,
    Array,
    String,
    JSON,
  });
  vm.runInContext(
    'var _jaUploadQueue = [];\n' + functions(['esc', 'escAttr', 'renderJAUploadList']),
    context,
  );
  context._jaUploadQueue = [
    {
      id: 'unmatched-id',
      file: {name: 'unmatched <cv>&.pdf'},
      email: 'unmatched@example.invalid',
      status: 'error',
      statusText: 'No <candidate> & retry',
      jaProfileUrl: '',
    },
    {
      id: 'matched-id',
      file: {name: 'matched <cv>&.pdf'},
      email: 'matched@example.invalid',
      status: 'done',
      statusText: 'Matched <candidate> & uploaded',
      jaProfileUrl: 'https://example.invalid/candidate/fixture',
    },
  ];

  context.renderJAUploadList();
  assert.ok(list.innerHTML.includes('unmatched &lt;cv&gt;&amp;.pdf'));
  assert.ok(list.innerHTML.includes('matched &lt;cv&gt;&amp;.pdf'));
  assert.ok(list.innerHTML.includes('No &lt;candidate&gt; &amp; retry'));
  assert.ok(list.innerHTML.includes('View in JobAdder'));
  assert.ok(!list.innerHTML.includes('unmatched <cv>&.pdf'));
  assert.ok(!list.innerHTML.includes('matched <cv>&.pdf'));
  assert.ok(!list.innerHTML.includes('No <candidate> & retry'));

  context._jaUploadQueue[1].jaProfileUrl = '';
  context.renderJAUploadList();
  assert.ok(list.innerHTML.includes('Matched &lt;candidate&gt; &amp; uploaded'));
  assert.ok(!list.innerHTML.includes('Matched <candidate> & uploaded'));
}

function localCardRenderersRetainEscaping() {
  const context = vm.createContext({console, Object, Array, String, Date});
  vm.runInContext(functions(['renderAnonJDCard', 'renderCompanyCard']), context);

  const anon = context.renderAnonJDCard({
    job_title: '<Lead> & Architect',
    about_client: '<b>Private & unsafe</b>',
    responsibilities: ['Build <systems> & mentor'],
  });
  assert.ok(anon.includes('&lt;Lead&gt; &amp; Architect'));
  assert.ok(anon.includes('&lt;b&gt;Private &amp; unsafe&lt;/b&gt;'));
  assert.ok(!anon.includes('<Lead>'));
  assert.ok(!anon.includes('<b>Private & unsafe</b>'));

  const company = context.renderCompanyCard({
    company_name: '<Acme> & Partners',
    narrative: '<script>unsafe()</script> & narrative',
    about: ['Scale <globally> & safely'],
  });
  assert.ok(company.includes('&lt;Acme&gt; &amp; Partners'));
  assert.ok(company.includes('&lt;script&gt;unsafe()&lt;/script&gt; &amp; narrative'));
  assert.ok(!company.includes('<Acme>'));
  assert.ok(!company.includes('<script>unsafe()</script>'));
}

function everyEsc2UseIsLocallyScoped() {
  const allowed = [
    functionRange(html, 'renderAnonJDCard'),
    functionRange(html, 'renderCompanyCard'),
  ];
  const occurrences = Array.from(html.matchAll(/\besc2\b/g));
  assert.ok(occurrences.length > 0, 'expected the two established local esc2 helpers and their calls');
  const outside = occurrences
    .filter(match => !allowed.some(range => match.index >= range.start && match.index < range.end))
    .map(match => html.slice(0, match.index).split('\n').length);
  assert.deepStrictEqual(outside, [], 'esc2 definitions/calls outside the two established local renderers');
  assert.strictEqual(
    occurrences.filter(match => html.slice(match.index - 9, match.index + 4) === 'function esc2').length,
    2,
    'exactly two locally scoped esc2 definitions should remain',
  );
}

const cases = [
  ['candidate-not-found JobAdder dialog and email escaping', candidateNotFoundDialogEscapesEmail],
  ['matched/unmatched JobAdder upload queue escaping', uploadQueueEscapesMatchedAndUnmatchedEntries],
  ['existing local card renderer escaping', localCardRenderersRetainEscaping],
  ['complete esc2 source-scope inventory', everyEsc2UseIsLocallyScoped],
];

(async function run() {
  const failures = [];
  for (const [name, test] of cases) {
    try {
      await test();
      console.log('PASS:', name);
    } catch (error) {
      failures.push({name, error});
      console.error('FAIL:', name, '-', error && error.message ? error.message : error);
    }
  }
  if (failures.length) {
    for (const failure of failures) console.error(failure.error && failure.error.stack ? failure.error.stack : failure.error);
    process.exitCode = 1;
    return;
  }
  console.log('JobAdder esc2 corrective frontend fixtures passed');
}());
