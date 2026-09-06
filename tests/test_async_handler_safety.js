'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

function load(file, names, extra = {}) {
  const notices = [];
  const context = vm.createContext({showToast: (...args) => notices.push(args), ...extra});
  const source = fs.readFileSync(path.join(__dirname, '../vendor/cvstudio', file), 'utf8');
  for (const name of names) {
    const start = source.search(new RegExp('^(?:async )?function ' + name + '\\(', 'm'));
    assert(start >= 0, name);
    const end = source.indexOf('\n}', start);
    assert(end >= 0, name);
    vm.runInContext(source.slice(start, end + 2), context);
  }
  context.notices = notices;
  return context;
}
const rejected = async () => {throw new Error('controlled failure');};
const ok = (data = {}) => ({ok: true, json: async () => data});

async function wrapperContracts() {
  const cases = [
    ['cv-format.js', 'downloadDocx', []],
    ['batch-format.js', 'openBatchOutputFolder', ['row']],
    ['screening-notes.js', 'oneNoteHandleCvUpload', [[{name: 'fixture.docx'}]]],
    ['screening-notes.js', 'oneNoteLoadSectionsForSelectedNotebook', [true]],
    ['ppc.js', 'ppcSaveOutlookSettingsFromPanel', []],
    ['ppc.js', 'ppcConnectOutlookDrafts', []],
    ['ppc.js', 'ppcTestOutlookConnection', []],
  ];
  for (const [file, name, args] of cases) {
    const c = load(file, [name], {_oneNoteRows: [], _oneNoteCvUploadRowIndex: -1,
      oneNoteSetSectionPickerHint: () => {}});
    c[name + 'Impl'] = rejected;
    assert.strictEqual(await c[name](...args), false, name);
    assert.strictEqual(c.notices.length, 1, name);
    assert.strictEqual(c.notices[0][1], 'err');
    let calls = 0;
    const value = {};
    c[name + 'Impl'] = async (...received) => {calls++; assert.deepStrictEqual(received, args); return value;};
    assert.strictEqual(await c[name](...args), value);
    assert.strictEqual(calls, 1, 'no replay');
    assert.strictEqual(c.notices.length, 1, 'no extra error on success');
  }
}

async function oneNoteSections() {
  const nodes = {oneNoteNotebookSelect: {value: 'fixture', options: [{textContent: 'Notebook'}], selectedIndex: 0},
    oneNoteSectionSelect: {}, oneNotePageList: {style: {}, textContent: ''}};
  let fills = 0;
  const c = load('screening-notes.js', ['oneNoteLoadPicker', 'oneNoteLoadSectionsForSelectedNotebook', 'oneNoteLoadSectionsForSelectedNotebookImpl'], {
    document: {getElementById: id => nodes[id]}, oneNoteRestoreMicrosoftToken: async () => true,
    oneNoteSelectedSourceMode: () => 'graph', oneNoteSetSectionPickerHint: () => {},
    oneNoteEnsureSectionPickerVisible: () => {}, oneNoteSectionLabel: () => 'Section',
    oneNoteFillSelect: () => fills++, fetch: rejected, _oneNotePickerPages: []});
  assert.strictEqual(await c.oneNoteLoadSectionsForSelectedNotebook(true), false);
  assert.strictEqual(fills, 0);
  c.fetch = async () => ({ok: false, json: async () => ({error: 'Controlled HTTP failure'})});
  assert.strictEqual(await c.oneNoteLoadSectionsForSelectedNotebook(true), false);
  c.fetch = async () => ok({items: [{id: 'section'}]});
  await c.oneNoteLoadSectionsForSelectedNotebook(false);
  assert.strictEqual(fills, 1);
  // A handled child failure must not become the parent's "loaded" success.
  c.oneNoteLoadAllNotebookSections = async () => [];
  c.fetch = async url => url.includes('/notebooks') ? ok({items: []}) : rejected();
  c.notices.length = 0;
  assert.strictEqual(await c.oneNoteLoadPicker(), false);
  assert.strictEqual(c.notices.length, 1);
  assert.strictEqual(c.notices[0][1], 'err', 'parent cannot announce a successful load');
}

async function oneNoteUpload() {
  const row = {};
  let calls = 0;
  const c = load('screening-notes.js', ['oneNoteHandleCvUpload', 'oneNoteHandleCvUploadImpl'], {
    _oneNoteRows: [row], _oneNoteCvUploadRowIndex: 0, _jaCreateQueue: [], window: {_jaToken: true},
    document: {getElementById: () => ({value: 'selected'})}, oneNoteRenderRows: () => {},
    oneNoteUpdateSummaryFromRows: () => {}, renderJACreateList: () => {}, updateJACreateConnStatus: () => {},
    runJACreateOne: async () => {calls++; throw new Error('controlled failure');}});
  assert.strictEqual(await c.oneNoteHandleCvUpload([{name: 'fixture.docx'}]), false);
  assert.strictEqual(calls, 1);
  assert.strictEqual(row.profile_create_state, 'error');
  assert.strictEqual(row.selected, false);
  assert.match(row.profile_create_message, /Check JobAdder before retrying/);
  assert.strictEqual(c._oneNoteCvUploadRowIndex, -1);
  c._oneNoteCvUploadRowIndex = 0;
  c.runJACreateOne = async () => {row.profile_create_state = 'done';};
  assert.strictEqual(await c.oneNoteHandleCvUpload([{name: 'fixture.docx'}]), true);
  assert.strictEqual(row.profile_create_state, 'done');
  // A replaced row must never receive the old request's failure state.
  c._oneNoteCvUploadRowIndex = 0;
  const replacement = {};
  c.runJACreateOne = async () => {c._oneNoteRows = [replacement]; throw new Error('controlled failure');};
  assert.strictEqual(await c.oneNoteHandleCvUpload([{name: 'fixture.docx'}]), false);
  assert.deepStrictEqual(replacement, {});
  const queue = [{id: 'one'}, {id: 'two'}];
  const q = load('create-profile.js', ['runJACreateOne'], {_jaCreateQueue: queue,
    window: {_jaToken: true}, runJACreateAll: rejected});
  await assert.rejects(q.runJACreateOne('one'), /controlled failure/);
  assert(queue.every(item => !('_skip' in item)), 'failed one-item run must not poison later runs');
}

async function outlookSettings() {
  let saves = 0, deviceClears = 0, starts = 0;
  const c = load('ppc.js', ['ppcSaveOutlookSettingsFromPanel', 'ppcSaveOutlookSettingsFromPanelImpl',
    'ppcDisconnectOutlook', 'ppcConnectOutlookDrafts', 'ppcConnectOutlookDraftsImpl'], {
    ppcOutlookClientLoad: () => ({client_id: 'old', tenant: 'common'}),
    document: {getElementById: id => ({value: id.endsWith('ClientId') ? 'new' : 'common'})},
    ppcOutlookClientIdValid: () => true, _ppcOutlookConnected: true, _ppcOutlookAccount: {fixture: true},
    _ppcOutlookStorage: 'protected', window: {confirm: () => true},
    ppcOutlookClientSave: () => saves++, ppcOutlookDeviceSave: () => deviceClears++,
    ppcUpdateOutlookConnectButton: () => {}, ppcOutlookPurgeLegacyBrowserToken: () => {},
    ppcOutlookDeviceLoad: () => null, ppcOutlookAccountLabel: () => 'fixture account',
    ppcStartOutlookLogin: async () => {starts++; return true;}, fetch: rejected});
  assert.strictEqual(await c.ppcSaveOutlookSettingsFromPanel(), false);
  assert.strictEqual(saves, 0);
  assert.strictEqual(deviceClears, 0);
  assert.strictEqual(c._ppcOutlookConnected, true);
  assert.strictEqual(c._ppcOutlookAccount.fixture, true);
  assert.strictEqual(await c.ppcConnectOutlookDrafts(), false);
  assert.strictEqual(starts, 0);
  c.fetch = async () => ({ok: false, json: async () => ({error: 'controlled HTTP failure'})});
  assert.strictEqual(await c.ppcSaveOutlookSettingsFromPanel(), false);
  assert.strictEqual(saves, 0);
  c.fetch = async () => ok();
  assert.strictEqual(await c.ppcSaveOutlookSettingsFromPanel(), true);
  assert.strictEqual(saves, 1);
  assert.strictEqual(c._ppcOutlookConnected, false);
  c.ppcStartOutlookLogin = rejected;
  assert.strictEqual(await c.ppcConnectOutlookDrafts(), false);
  c.ppcOutlookDeviceLoad = () => ({login_session_id: 'fixture'});
  c.ppcFinishOutlookLogin = rejected;
  assert.strictEqual(await c.ppcConnectOutlookDrafts(), false);
}

async function outlookTestAndDraft() {
  const c = load('ppc.js', ['ppcTestOutlookConnection', 'ppcTestOutlookConnectionImpl'], {
    fetch: rejected, _ppcOutlookConnected: false, _ppcOutlookStorage: '',
    ppcSetOutlookTechnicalError: () => {}, ppcUpdateOutlookConnectButton: () => {},
    ppcOutlookAccountLabel: () => 'fixture account'});
  assert.strictEqual(await c.ppcTestOutlookConnection(), false);
  assert.strictEqual(c._ppcOutlookConnected, false);
  c.fetch = async () => ok({account: {fixture: true}});
  assert.strictEqual(await c.ppcTestOutlookConnection(), true);
  assert.strictEqual(c._ppcOutlookConnected, true);
  let closed = 0, requests = 0, redirected = 0;
  const d = load('ppc.js', ['ppcCreateOutlookTestDraft'], {
    window: {open: () => ({close: () => closed++, location: {replace: () => redirected++}})},
    fetch: async () => {requests++; throw new Error('controlled failure');},
    ppcShowOutlookError: () => {}, ppcUpdateOutlookConnectButton: () => {}});
  assert.strictEqual(await d.ppcCreateOutlookTestDraft(), false);
  assert.strictEqual(closed, 1);
  assert.strictEqual(requests, 1);
  assert.match(d.notices[0][0], /Check Outlook Drafts/);
  d.fetch = async () => ({ok: true, json: rejected});
  assert.strictEqual(await d.ppcCreateOutlookTestDraft(), false);
  assert.strictEqual(closed, 2);
  d.fetch = async () => ok(null);
  assert.strictEqual(await d.ppcCreateOutlookTestDraft(), false);
  d.fetch = async () => ok({});
  assert.strictEqual(await d.ppcCreateOutlookTestDraft(), false);
  assert.strictEqual(closed, 4);
  d.fetch = async () => ok({webLink: 'https://example.invalid/draft'});
  assert.strictEqual(await d.ppcCreateOutlookTestDraft(), true);
  assert.strictEqual(redirected, 1);
  assert.strictEqual(closed, 4);
}

(async () => {
  await wrapperContracts();
  await oneNoteSections();
  await oneNoteUpload();
  await outlookSettings();
  await outlookTestAndDraft();
  console.log('Async handler safety: all workflow and rejection checks passed');
})().catch(error => {console.error(error); process.exitCode = 1;});
