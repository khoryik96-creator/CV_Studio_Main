'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const indexPath = path.resolve(__dirname, '..', 'index.html');
const html = fs.readFileSync(indexPath, 'utf8');

function inlineScripts(source) {
  const scripts = [];
  const expression = /<script\b([^>]*)>([\s\S]*?)<\/script>/gi;
  let match;
  while ((match = expression.exec(source))) {
    if (!/\bsrc\s*=/.test(match[1] || '')) scripts.push(match[2]);
  }
  return scripts;
}

function extractFunction(source, name) {
  const marker = 'function ' + name + '(';
  const start = source.indexOf(marker);
  if (start < 0) throw new Error('Missing function: ' + name);
  const brace = source.indexOf('{', start + marker.length);
  let depth = 0;
  let quote = '';
  let escaped = false;
  let lineComment = false;
  let blockComment = false;
  for (let index = brace; index < source.length; index += 1) {
    const char = source[index];
    const next = source[index + 1] || '';
    if (lineComment) {
      if (char === '\n') lineComment = false;
      continue;
    }
    if (blockComment) {
      if (char === '*' && next === '/') { blockComment = false; index += 1; }
      continue;
    }
    if (quote) {
      if (escaped) escaped = false;
      else if (char === '\\') escaped = true;
      else if (char === quote) quote = '';
      continue;
    }
    if (char === '/' && next === '/') { lineComment = true; index += 1; continue; }
    if (char === '/' && next === '*') { blockComment = true; index += 1; continue; }
    if (char === '"' || char === "'" || char.charCodeAt(0) === 96) { quote = char; continue; }
    if (char === '{') depth += 1;
    if (char === '}') {
      depth -= 1;
      if (depth === 0) return source.slice(start, index + 1);
    }
  }
  throw new Error('Unterminated function: ' + name);
}

function localStorageFixture(initial) {
  const values = Object.assign({}, initial || {});
  return {
    getItem(key) { return Object.prototype.hasOwnProperty.call(values, key) ? values[key] : null; },
    setItem(key, value) { values[key] = String(value); },
    removeItem(key) { delete values[key]; },
    snapshot() { return Object.assign({}, values); },
  };
}

function response(payload, ok = true) {
  return {ok, json: () => Promise.resolve(payload)};
}

for (const [index, source] of inlineScripts(html).entries()) {
  new vm.Script(source, {filename: 'index-inline-' + (index + 1) + '.js'});
}

async function testUsageBridge() {
  const legacy = [
    {
      ts: '2026-07-01T00:00:00Z',
      name: 'Legacy fixture',
      mode: 'format',
      cost: 0.125,
    },
    {
      id: 'stat_sqlite_fixture',
      ts: '2026-07-02T00:00:00Z',
      name: 'SQLite fixture',
      mode: 'lead',
      cost: 0.25,
      jaUrl: '',
    },
  ];
  const sqlite = [{
    id: 'stat_sqlite_fixture',
    ts: '2026-07-02T00:00:00Z',
    name: 'SQLite fixture',
    mode: 'lead',
    cost: 0.25,
    input_tokens: 4,
    jaUrl: 'https://current.invalid/candidate',
  }];
  const reorderedLegacy = {
    cost: 0.125,
    mode: 'format',
    name: 'Legacy fixture',
    ts: '2026-07-01T00:00:00Z',
  };
  const calls = [];
  const toasts = [];
  let failClear = false;
  const storage = localStorageFixture({guo_lab_stats: JSON.stringify(legacy)});
  const context = vm.createContext({
    console,
    Promise,
    JSON,
    Object,
    Array,
    String,
    Error,
    localStorage: storage,
    renderStats() {},
    showToast(message, kind) { toasts.push({message, kind}); },
    confirm() { return true; },
    fetch(url, options) {
      const body = JSON.parse((options && options.body) || '{}');
      calls.push({url, body});
      if (url.endsWith('/import')) {
        return Promise.resolve(response({ok: true, records: sqlite.concat([reorderedLegacy])}));
      }
      if (failClear && url.endsWith('/clear')) {
        return Promise.resolve(response({ok: false, message: 'Clear fixture failed'}, false));
      }
      return Promise.resolve(response({ok: true}));
    },
  });
  const functions = [
    'statsLegacyLoad',
    'statsStableStorageValue',
    'statsStorageRecordKey',
    'statsChangedStorageKeys',
    'statsMergeStorageRecords',
    'statsLegacySave',
    'statsStoragePost',
    'statsQueueStoragePost',
    'statsLoad',
    'statsSave',
    'statsHydrateFromSQLite',
    'clearStats',
  ].map(name => extractFunction(html, name)).join('\n');
  vm.runInContext(
    "var _statsSqliteCache=null,_statsMutationVersion=0,_statsClearVersion=0,_statsHydrationPromise=null,_statsStorageWriteQueue=Promise.resolve();\n" + functions,
    context,
  );

  await context.statsHydrateFromSQLite();
  assert.strictEqual(context.statsLoad().length, 2);
  assert.strictEqual(JSON.parse(storage.getItem('guo_lab_stats')).length, 2);
  assert.ok(!Object.prototype.hasOwnProperty.call(context.statsLoad()[1], 'input_tokens'));
  assert.strictEqual(context.statsLoad()[0].jaUrl, 'https://current.invalid/candidate');
  assert.strictEqual(context.statsLoad()[0].input_tokens, 4);

  const beforeRace = [
    {id: 'changed', name: 'Before'},
    {id: 'unchanged', name: 'Stale legacy'},
  ];
  const currentRace = [
    {id: 'changed', name: 'Browser mutation'},
    {id: 'unchanged', name: 'Stale legacy'},
  ];
  const sqliteRace = [
    {id: 'changed', name: 'SQLite before mutation'},
    {id: 'unchanged', name: 'SQLite authoritative'},
  ];
  const changedKeys = context.statsChangedStorageKeys(beforeRace, currentRace);
  const raceMerged = context.statsMergeStorageRecords(sqliteRace, currentRace, changedKeys);
  assert.strictEqual(raceMerged[0].name, 'Browser mutation');
  assert.strictEqual(raceMerged[1].name, 'SQLite authoritative');

  const next = context.statsLoad();
  next.push({
    id: 'stat_browser_fixture',
    ts: '2026-07-03T00:00:00Z',
    name: 'Browser fixture',
    mode: 'summary',
    cost: 0,
  });
  context.statsSave(next);
  await context._statsStorageWriteQueue;
  assert.strictEqual(JSON.parse(storage.getItem('guo_lab_stats')).length, 3);
  assert.ok(calls.some(call => call.url.endsWith('/upsert') && call.body.records.length === 3));

  assert.strictEqual(await context.clearStats(), true);
  assert.strictEqual(storage.getItem('guo_lab_stats'), null);
  assert.deepStrictEqual(Array.from(context.statsLoad()), []);
  assert.ok(calls.some(call => call.url.endsWith('/clear')));
  assert.ok(toasts.some(toast => toast.kind === 'info' && toast.message === 'History cleared'));

  const retained = [{
    id: 'stat_retained_fixture',
    ts: '2026-07-04T00:00:00Z',
    name: 'Retained after failed clear',
    mode: 'summary',
    cost: 0,
  }];
  context.statsSave(retained);
  await context._statsStorageWriteQueue;
  failClear = true;
  assert.strictEqual(await context.clearStats(), false);
  assert.strictEqual(context.statsLoad().length, 1);
  assert.strictEqual(context.statsLoad()[0].id, 'stat_retained_fixture');
  assert.strictEqual(JSON.parse(storage.getItem('guo_lab_stats')).length, 1);
  assert.ok(toasts.some(toast => toast.kind === 'err' && /not cleared/.test(toast.message)));
}

async function testPpcBridge() {
  const legacy = {
    'placement-fixture': {
      payment: 'Invoiced',
      guaranteeMonths: '3',
      updatedAt: '2026-07-02T00:00:00Z',
    },
  };
  const sqlite = {
    'placement-fixture': {
      payment: 'Paid',
      guaranteeMonths: '3',
      updatedAt: '2026-07-03T00:00:00Z',
    },
    'placement-sqlite': {
      payment: 'Paid',
      guaranteeMonths: '1',
      updatedAt: '2026-07-01T00:00:00Z',
    },
  };
  const calls = [];
  const storage = localStorageFixture({cvstudio_ppc_meta_v1: JSON.stringify(legacy)});
  const context = vm.createContext({
    console,
    Promise,
    JSON,
    Object,
    Array,
    String,
    Error,
    localStorage: storage,
    PPC_META_STORE: 'cvstudio_ppc_meta_v1',
    _ppcItems: [],
    ppcApplyFilters() {},
    fetch(url, options) {
      const body = JSON.parse((options && options.body) || '{}');
      calls.push({url, body});
      if (url.endsWith('/import')) {
        return Promise.resolve(response({ok: true, metadata: sqlite}));
      }
      return Promise.resolve(response({ok: true}));
    },
  });
  const functions = [
    'ppcMetaLegacyLoad',
    'ppcMetaMerge',
    'ppcMetaStoragePost',
    'ppcMetaQueuePost',
    'ppcMetaLoad',
    'ppcMetaSave',
    'ppcMetaHydrateFromSQLite',
  ].map(name => extractFunction(html, name)).join('\n');
  vm.runInContext(
    "var _ppcMetaSqliteCache=null,_ppcMetaMutationVersion=0,_ppcMetaHydrationPromise=null,_ppcMetaWriteQueue=Promise.resolve();\n" + functions,
    context,
  );

  await context.ppcMetaHydrateFromSQLite();
  const hydrated = context.ppcMetaLoad();
  assert.strictEqual(hydrated['placement-fixture'].payment, 'Paid');
  assert.strictEqual(hydrated['placement-sqlite'].payment, 'Paid');
  assert.strictEqual(Object.keys(JSON.parse(storage.getItem('cvstudio_ppc_meta_v1'))).length, 2);

  hydrated['placement-fixture'] = {
    payment: 'Paid',
    guaranteeMonths: '3',
    updatedAt: '2026-07-03T00:00:00Z',
  };
  context.ppcMetaSave(hydrated);
  await context._ppcMetaWriteQueue;
  assert.strictEqual(JSON.parse(storage.getItem('cvstudio_ppc_meta_v1'))['placement-fixture'].payment, 'Paid');
  assert.ok(calls.some(call => call.url.endsWith('/upsert')));
}

Promise.resolve()
  .then(testUsageBridge)
  .then(testPpcBridge)
  .then(() => {
    process.stdout.write('Phase 2A frontend storage fixture passed\n');
  })
  .catch(error => {
    process.stderr.write((error && error.stack) || String(error));
    process.stderr.write('\n');
    process.exitCode = 1;
  });
