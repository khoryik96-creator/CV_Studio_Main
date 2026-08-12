'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const html = require('./frontend_sources').frontendSource();

function extractFunction(source, name) {
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
    if (char === '}' && --depth === 0) return source.slice(start, index + 1);
  }
  throw new Error('Unterminated function: ' + name);
}

function functions(names) { return names.map(name => extractFunction(html, name)).join('\n'); }

function localStorageFixture(initial) {
  const values = Object.assign({}, initial || {});
  const storage = {
    getItem(key) { return Object.prototype.hasOwnProperty.call(values, key) ? values[key] : null; },
    setItem(key, value) { values[key] = String(value); },
    removeItem(key) { delete values[key]; },
    key(index) { return Object.keys(values)[index] === undefined ? null : Object.keys(values)[index]; },
    snapshot() { return Object.assign({}, values); },
  };
  Object.defineProperty(storage, 'length', {get() { return Object.keys(values).length; }});
  return storage;
}

function response(payload, ok = true) { return {ok, json: () => Promise.resolve(payload)}; }

const sharedNames = [
  'cvStudioSafeLocalDataKey', 'cvStudioDurableSettingKey', 'cvStudioPrivateSecretField',
  'cvStudioPrivateSafeValue', 'cvStudioStableStorageValue', 'cvStudioSafeExportSettingValue',
  'cvStudioLocalDataSettingsSnapshot', 'cvStudioStoragePost',
];

async function testSettingsBridgeAndAllowlist() {
  const storage = localStorageFixture({
    hy_provider: 'anthropic',
    hy_model_openai: 'gpt-stale-fixture',
    hy_model_deepseek: 'deepseek-stale-fixture',
    cvstudio_spider_preview_memory_mode_v1: 'high',
    hy_key_openai: 'redacted-fixture-value',
    cvstudio_ppc_ui_state_v1: JSON.stringify({page: 1, clientSecret: 'redacted-fixture-value'}),
  });
  const calls = [], toasts = [];
  let resolveImport, failDelete = false;
  const context = vm.createContext({
    console, Promise, JSON, Object, Array, String, Number, Error, localStorage: storage,
    window: {}, document: {getElementById() { return null; }},
    renderRouteCalls: 0, ensureRouteCalls: 0, syncRouteCalls: 0,
    appliedMemoryModes: [], autoMemorySchedules: 0,
    storedTheSpiderPreviewMemoryMode() { return storage.getItem('cvstudio_spider_preview_memory_mode_v1') || 'high'; },
    applyTheSpiderPreviewMemoryMode(mode, clearExisting) { context.appliedMemoryModes.push([mode, clearExisting]); },
    scheduleTheSpiderPreviewAutoDiagnostics() { context.autoMemorySchedules += 1; },
    renderAiRoutingRows() { context.renderRouteCalls += 1; },
    ensureAiRoutingRowsVisible() { context.ensureRouteCalls += 1; },
    syncQuickAiProviderPanels() { context.syncRouteCalls += 1; },
    showToast(message, kind) { toasts.push({message, kind}); },
    fetch(url, options) {
      const body = JSON.parse((options && options.body) || '{}'); calls.push({url, body});
      if (url.endsWith('/import')) return new Promise(resolve => { resolveImport = () => resolve(response({ok: true, settings: {hy_provider: 'openai', hy_model_openai: 'gpt-current-fixture', hy_model_deepseek: 'deepseek-current-fixture', cvstudio_ppc_ui_state_v1: JSON.stringify({page: 1}), cvstudio_spider_preview_memory_mode_v1: 'low'}})); });
      if (failDelete && url.endsWith('/delete')) return Promise.resolve(response({ok: false, message: 'Delete fixture failed'}, false));
      return Promise.resolve(response({ok: true}));
    },
  });
  vm.runInContext(
    'var _phase2bSettingsSqliteCache=null,_phase2bSettingsMutationVersion=0,_phase2bSettingsDirtyKeys={},_phase2bSettingsHydrationPromise=null,_phase2bSettingsWriteQueue=Promise.resolve();\n' +
    functions(sharedNames.concat(['cvStudioQueueSettingsPost', 'cvStudioApplyDurableSettings', 'cvStudioRefreshHydratedSettingUi', 'cvStudioDurableSettingSet', 'cvStudioDurableSettingRemove', 'cvStudioHydrateBrowserSettings'])),
    context,
  );

  assert.strictEqual(context.cvStudioSafeLocalDataKey('hy_model_openai'), true);
  assert.strictEqual(context.cvStudioSafeLocalDataKey('hy_model_unknown'), false);
  assert.strictEqual(context.cvStudioSafeLocalDataKey('hy_ai_route_summary'), true);
  assert.strictEqual(context.cvStudioSafeLocalDataKey('cvstudio_summary_box_autofit_v1'), true);
  assert.strictEqual(context.cvStudioSafeLocalDataKey('hy_ai_route_unapproved'), false);
  assert.strictEqual(context.cvStudioSafeLocalDataKey('hy_key_openai'), false);

  const hydration = context.cvStudioHydrateBrowserSettings();
  assert.strictEqual(await context.cvStudioDurableSettingSet('hy_provider', 'deepseek'), true);
  assert.strictEqual(await context.cvStudioDurableSettingRemove('hy_model_deepseek'), true);
  resolveImport();
  await hydration;
  assert.strictEqual(storage.getItem('hy_provider'), 'deepseek');
  assert.strictEqual(storage.getItem('hy_model_openai'), 'gpt-current-fixture');
  assert.strictEqual(storage.getItem('hy_model_deepseek'), null);
  assert.ok(calls.some(call => call.url.endsWith('/upsert') && call.body.settings.hy_provider === 'deepseek'));
  assert.ok(calls.some(call => call.url.endsWith('/delete') && call.body.keys[0] === 'hy_model_deepseek'));
  assert.deepStrictEqual(Array.from(context.appliedMemoryModes[0]), ['low', false]);
  assert.strictEqual(context.autoMemorySchedules, 0);
  assert.strictEqual(context.renderRouteCalls, 1);
  assert.strictEqual(context.ensureRouteCalls, 0);
  assert.strictEqual(context.syncRouteCalls, 1);

  storage.setItem('cvstudio_spider_preview_memory_mode_v1', 'auto');
  context.cvStudioRefreshHydratedSettingUi();
  assert.deepStrictEqual(Array.from(context.appliedMemoryModes[1]), ['auto', false]);
  assert.strictEqual(context.autoMemorySchedules, 1);
  assert.strictEqual(context.renderRouteCalls, 2);

  const exportedSettings = context.cvStudioLocalDataSettingsSnapshot(false);
  assert.ok(!Object.prototype.hasOwnProperty.call(exportedSettings, 'hy_key_openai'));
  assert.deepStrictEqual(JSON.parse(exportedSettings.cvstudio_ppc_ui_state_v1), {page: 1});

  failDelete = true;
  assert.strictEqual(await context.cvStudioDurableSettingRemove('hy_model_openai'), false);
  assert.strictEqual(storage.getItem('hy_model_openai'), 'gpt-current-fixture');
  assert.ok(toasts.some(item => item.kind === 'err' && /not removed/.test(item.message)));
}

async function testTransferRecordHydrationAndClearRecovery() {
  const legacy = [
    {id: 'same-record', ts: '2026-07-20T01:00:00Z', status: 'stale'},
    {id: 'deleted-record', ts: '2026-07-19T01:00:00Z', status: 'stale'},
  ];
  const storage = localStorageFixture({cv_studio_onenote_transfer_records_v1: JSON.stringify(legacy)});
  const calls = [], toasts = [];
  let resolveImport, failClear = false;
  const context = vm.createContext({
    console, Promise, JSON, Object, Array, String, Number, Error, localStorage: storage,
    ONE_NOTE_RECORD_KEY: 'cv_studio_onenote_transfer_records_v1',
    window: {confirm() { return true; }},
    renderCount: 0,
    oneNoteRenderRecords() { context.renderCount += 1; }, oneNoteRefreshCost() {},
    showToast(message, kind) { toasts.push({message, kind}); },
    fetch(url, options) {
      const body = JSON.parse((options && options.body) || '{}'); calls.push({url, body});
      if (url.endsWith('/import')) return new Promise(resolve => { resolveImport = () => resolve(response({ok: true, records: [
        {id: 'same-record', ts: '2026-07-20T01:00:00Z', status: 'sqlite-current'},
        {id: 'sqlite-record', ts: '2026-07-21T01:00:00Z', status: 'sqlite'},
      ]})); });
      if (failClear && url.endsWith('/clear')) return Promise.resolve(response({ok: false, message: 'Clear fixture failed'}, false));
      return Promise.resolve(response({ok: true}));
    },
  });
  vm.runInContext(
    'var _oneNoteRecordsSqliteCache=null,_oneNoteRecordsMutationVersion=0,_oneNoteRecordsHydrationPromise=null,_oneNoteRecordsWriteQueue=Promise.resolve(),_oneNoteRecordsLastWritePromise=Promise.resolve(true);\n' +
    functions(sharedNames.slice(1).concat([
      'oneNoteRecordsLegacyLoad', 'oneNoteRecordStorageKey', 'oneNoteRecordChangedKeys',
      'oneNoteMergeStorageRecords', 'oneNoteRecordUnion', 'oneNoteRecordsMirrorSave',
      'oneNoteRecordsLoad', 'oneNoteRecordsQueuePost', 'oneNoteRecordsSave',
      'oneNoteRecordsHydrateFromSQLite', 'oneNoteClearRecords',
    ])),
    context,
  );

  const hydration = context.oneNoteRecordsHydrateFromSQLite();
  context.oneNoteRecordsSave([
    {id: 'same-record', ts: '2026-07-20T01:00:00Z', status: 'browser-mutation', clientSecret: 'redacted-fixture-value'},
    legacy[1],
    {id: 'new-record', ts: '2026-07-22T01:00:00Z', status: 'new'},
  ]);
  resolveImport();
  await hydration;
  await context._oneNoteRecordsLastWritePromise;
  const hydrated = context.oneNoteRecordsLoad();
  assert.strictEqual(hydrated.find(row => row.id === 'same-record').status, 'browser-mutation');
  assert.ok(!Object.prototype.hasOwnProperty.call(hydrated.find(row => row.id === 'same-record'), 'clientSecret'));
  assert.ok(hydrated.some(row => row.id === 'sqlite-record'));
  assert.ok(hydrated.some(row => row.id === 'new-record'));
  assert.ok(!hydrated.some(row => row.id === 'deleted-record'));

  assert.strictEqual(await context.oneNoteClearRecords(), true);
  assert.deepStrictEqual(Array.from(context.oneNoteRecordsLoad()), []);
  assert.ok(calls.some(call => call.url.endsWith('/clear')));

  context.oneNoteRecordsSave([{id: 'restore-record', ts: '2026-07-23T01:00:00Z', status: 'kept'}]);
  await context._oneNoteRecordsLastWritePromise;
  failClear = true;
  assert.strictEqual(await context.oneNoteClearRecords(), false);
  assert.strictEqual(context.oneNoteRecordsLoad()[0].id, 'restore-record');
  assert.ok(toasts.some(item => item.kind === 'err' && /not cleared/.test(item.message)));
}

async function testSavedLinkHydrationAndWriteRecovery() {
  const legacy = [
    {id: 'same-link', name: 'Stale', kind: 'section', link: 'opaque-link-a'},
    {id: 'deleted-link', name: 'Deleted', kind: 'page', link: 'opaque-link-b'},
  ];
  const storage = localStorageFixture({cvstudio_onenote_saved_desktop_links_v1: JSON.stringify(legacy)});
  const calls = [], toasts = [];
  let resolveImport, failReplace = false;
  const context = vm.createContext({
    console, Promise, JSON, Object, Array, String, Number, Error, localStorage: storage,
    ONE_NOTE_SAVED_LINKS_KEY: 'cvstudio_onenote_saved_desktop_links_v1', ONE_NOTE_SAVED_LINKS_MAX: 100,
    showToast(message, kind) { toasts.push({message, kind}); }, oneNoteRenderSavedLinks() {},
    fetch(url, options) {
      const body = JSON.parse((options && options.body) || '{}'); calls.push({url, body});
      if (url.endsWith('/import')) return new Promise(resolve => { resolveImport = () => resolve(response({ok: true, links: [
        {id: 'same-link', name: 'SQLite', kind: 'section', link: 'opaque-link-a'},
        {id: 'sqlite-link', name: 'SQLite only', kind: 'notebook', link: 'opaque-link-c'},
      ]})); });
      if (failReplace && url.endsWith('/replace')) return Promise.resolve(response({ok: false, message: 'Replace fixture failed'}, false));
      return Promise.resolve(response({ok: true}));
    },
  });
  vm.runInContext(
    'var _oneNoteLinksSqliteCache=null,_oneNoteLinksMutationVersion=0,_oneNoteLinksHydrationPromise=null,_oneNoteLinksWriteQueue=Promise.resolve(),_oneNoteLinksLastWritePromise=Promise.resolve(true);\n' +
    functions(sharedNames.slice(1).concat([
      'oneNoteSavedLinkKind', 'oneNoteSimpleHash', 'oneNoteReadSavedLinksLegacy',
      'oneNoteLinkStorageKey', 'oneNoteLinkChangedKeys', 'oneNoteMergeSavedLinks',
      'oneNoteReadSavedLinks', 'oneNoteWriteSavedLinks', 'oneNoteLinksHydrateFromSQLite',
    ])),
    context,
  );

  const hydration = context.oneNoteLinksHydrateFromSQLite();
  context.oneNoteWriteSavedLinks([
    {id: 'same-link', name: 'Browser edit', kind: 'section', link: 'opaque-link-a', clientSecret: 'redacted-fixture-value'},
    legacy[1],
    {id: 'new-link', name: 'New', kind: 'page', link: 'opaque-link-new'},
  ]);
  resolveImport();
  await hydration;
  await context._oneNoteLinksLastWritePromise;
  const hydrated = context.oneNoteReadSavedLinks();
  assert.strictEqual(hydrated.find(row => row.id === 'same-link').name, 'Browser edit');
  assert.ok(!Object.prototype.hasOwnProperty.call(hydrated.find(row => row.id === 'same-link'), 'clientSecret'));
  assert.ok(hydrated.some(row => row.id === 'sqlite-link'));
  assert.ok(hydrated.some(row => row.id === 'new-link'));
  assert.ok(!hydrated.some(row => row.id === 'deleted-link'));

  const beforeFailure = context.oneNoteReadSavedLinks();
  failReplace = true;
  context.oneNoteWriteSavedLinks([{id: 'failed-link', name: 'Failed', kind: 'page', link: 'opaque-link-failed'}]);
  assert.strictEqual(await context._oneNoteLinksLastWritePromise, false);
  assert.deepStrictEqual(
    Array.from(context.oneNoteReadSavedLinks(), row => row.id),
    Array.from(beforeFailure, row => row.id),
  );
  assert.ok(toasts.some(item => item.kind === 'err' && /restored/.test(item.message)));
}

async function testAdditiveSchemaOneImportPersistence() {
  const exportSource = extractFunction(html, 'exportCvStudioLocalData');
  assert.ok(exportSource.includes("schema:1"));
  assert.ok(exportSource.includes('settings:settings,records:records'));
  const calls = {settings: [], ppc: null, transfers: null, links: null};
  const context = vm.createContext({
    console, Promise, JSON, Object, Array, String, Number, Error,
    cvStudioHydrateBrowserSettings: () => Promise.resolve({}),
    ppcMetaHydrateFromSQLite: () => Promise.resolve({}),
    oneNoteRecordsHydrateFromSQLite: () => Promise.resolve([]),
    oneNoteLinksHydrateFromSQLite: () => Promise.resolve([]),
    cvStudioDurableSettingSet(key, value) { calls.settings.push({key, value}); return Promise.resolve(true); },
    ppcMetaSave(value) { calls.ppc = value; },
    oneNoteRecordsSave(value) { calls.transfers = value; return true; },
    oneNoteWriteSavedLinks(value) { calls.links = value; return true; },
    _ppcMetaWriteQueue: Promise.resolve(), _oneNoteRecordsLastWritePromise: Promise.resolve(true), _oneNoteLinksLastWritePromise: Promise.resolve(true),
  });
  vm.runInContext(functions(['cvStudioSafeLocalDataKey', 'cvStudioDurableSettingKey', 'cvStudioPersistImportedLocalData']), context);
  const restored = await context.cvStudioPersistImportedLocalData({
    product: 'CV Studio local data', schema: 1,
    settings: {
      hy_model_openai: 'gpt-import-fixture',
      hy_key_openai: 'redacted-fixture-value',
      cvstudio_ppc_meta_v1: JSON.stringify({'placement-fixture': {payment: 'Paid'}}),
      cvstudio_onenote_saved_desktop_links_v1: JSON.stringify([{id: 'legacy-link'}]),
    },
    records: {
      onenote_transfer_records: [{id: 'import-record'}],
      onenote_saved_links: [{id: 'record-link'}],
    },
  });
  assert.strictEqual(restored, 4);
  assert.deepStrictEqual(calls.settings, [{key: 'hy_model_openai', value: 'gpt-import-fixture'}]);
  assert.strictEqual(calls.ppc['placement-fixture'].payment, 'Paid');
  assert.strictEqual(calls.transfers[0].id, 'import-record');
  assert.strictEqual(calls.links[0].id, 'record-link');
}

async function testImportRejectsFailedDurableWrites() {
  async function runScenario(overrides, payload) {
    const context = vm.createContext(Object.assign({
      console, Promise, JSON, Object, Array, String, Number, Error,
      cvStudioHydrateBrowserSettings: () => Promise.resolve({}),
      ppcMetaHydrateFromSQLite: () => Promise.resolve({}),
      oneNoteRecordsHydrateFromSQLite: () => Promise.resolve([]),
      oneNoteLinksHydrateFromSQLite: () => Promise.resolve([]),
      cvStudioDurableSettingSet: () => Promise.resolve(true),
      ppcMetaSave() {},
      oneNoteRecordsSave: () => true,
      oneNoteWriteSavedLinks: () => true,
      _ppcMetaWriteQueue: Promise.resolve(),
      _oneNoteRecordsLastWritePromise: Promise.resolve(true),
      _oneNoteLinksLastWritePromise: Promise.resolve(true),
    }, overrides || {}));
    vm.runInContext(functions(['cvStudioSafeLocalDataKey', 'cvStudioDurableSettingKey', 'cvStudioPersistImportedLocalData']), context);
    await assert.rejects(
      context.cvStudioPersistImportedLocalData(payload),
      /durable storage/i,
    );
  }

  await runScenario(
    {cvStudioDurableSettingSet: () => Promise.resolve(false)},
    {settings: {hy_model_openai: 'gpt-rejected-fixture'}, records: {}},
  );
  await runScenario(
    {_oneNoteLinksLastWritePromise: Promise.resolve(false)},
    {settings: {}, records: {onenote_saved_links: [{id: 'rejected-link'}]}},
  );
  await runScenario(
    {_ppcMetaWriteQueue: Promise.reject(new Error('PPC durable fixture failure'))},
    {settings: {cvstudio_ppc_meta_v1: JSON.stringify({fixture: {payment: 'Paid'}})}, records: {}},
  );
}

Promise.resolve()
  .then(testSettingsBridgeAndAllowlist)
  .then(testTransferRecordHydrationAndClearRecovery)
  .then(testSavedLinkHydrationAndWriteRecovery)
  .then(testAdditiveSchemaOneImportPersistence)
  .then(testImportRejectsFailedDurableWrites)
  .then(() => process.stdout.write('Phase 2B frontend storage fixture passed\n'))
  .catch(error => { process.stderr.write(((error && error.stack) || String(error)) + '\n'); process.exitCode = 1; });
