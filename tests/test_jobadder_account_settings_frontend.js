'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const html = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');

function functionSource(source, name) {
  const marker = 'function ' + name + '(';
  let start = source.indexOf(marker);
  if (start < 0) throw new Error('Missing function: ' + name);
  if (source.slice(Math.max(0, start - 6), start) === 'async ') start -= 6;
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

function formatAndSettingsMarkupAreCentralized() {
  const previewHeading = html.indexOf('Preview &amp; Output');
  const formatStart = html.lastIndexOf('<div class="card">', previewHeading);
  const formatEnd = html.indexOf('</div><!-- /viewFormat -->', formatStart);
  const formatMarkup = html.slice(formatStart, formatEnd);
  assert.ok(formatMarkup.includes('id="btnJALogin"'));
  assert.ok(formatMarkup.includes('id="btnJA"'));
  assert.ok(formatMarkup.includes('id="jaStatus"'));
  assert.ok(!formatMarkup.includes('id="jaClientId"'));
  assert.ok(!formatMarkup.includes('id="jaClientSecret"'));
  assert.ok(!formatMarkup.includes('toggleJASettings()'));
  assert.ok(!formatMarkup.includes('JobAdder API Credentials'));

  const cardStart = html.indexOf('id="settingsJobAdderCard"');
  const cardEnd = html.indexOf('</div>', html.indexOf('</div>', cardStart) + 6);
  assert.ok(cardStart > 0 && cardEnd > cardStart);
  const settingsWindow = html.slice(cardStart, cardStart + 6000);
  [
    'settingsJobAdderStatus',
    'settingsJobAdderDetail',
    'settingsJobAdderClientId',
    'settingsJobAdderClientSecret',
    'settingsJobAdderSecretStatus',
    'settingsJobAdderConnectBtn',
    'settingsJobAdderReconnectBtn',
    'saveJobAdderSettings()',
    'signOutJobAdder()',
    'http://localhost:5000/jobadder/callback',
    'https://developer.jobadder.com',
    'Saved securely',
  ].forEach(marker => assert.ok(settingsWindow.includes(marker), 'missing settings marker: ' + marker));
}

function missingSetupOpensAndFocusesSettings() {
  const calls = [];
  const context = vm.createContext({
    console,
    window: {_jaToken: false},
    getJAClientId() { return ''; },
    getJAClientSecret() { return ''; },
    hasJASavedSecretFor() { return false; },
    openJobAdderSettings(message) { calls.push(message); },
    showToast(message, kind) { calls.push(kind + ':' + message); },
  });
  vm.runInContext(functionSource(html, 'jobAdderLogin'), context);
  return context.jobAdderLogin().then(() => {
    assert.strictEqual(calls.length, 2);
    assert.ok(calls[0].includes('application setup is required'));
    assert.ok(calls[1].startsWith('err:'));
    const opener = functionSource(html, 'openJobAdderSettings');
    assert.ok(opener.includes("showSettingsTab('integrations')"));
    assert.ok(opener.includes('settingsJobAdderCard'));
    assert.ok(opener.includes('scrollIntoView'));
    assert.ok(opener.includes('focus'));
  });
}

async function changedClientIdCannotReuseOldSavedSecret() {
  const calls = [];
  const idField = {value: 'fixture-new-client'};
  const context = vm.createContext({
    console,
    window: {_jaToken: false, _jaConfiguredClientId: 'fixture-old-client', _jaClientSecretConfigured: true},
    document: {
      getElementById(id) {
        if (id === 'settingsJobAdderClientId') return idField;
        return null;
      },
    },
    getJAClientId() { return idField.value; },
    getJAClientSecret() { return ''; },
    hasJASavedSecretFor(id) {
      return id === context.window._jaConfiguredClientId && context.window._jaClientSecretConfigured;
    },
    fetch() {
      return Promise.resolve({
        ok: true,
        json() {
          return Promise.resolve({
            connected: false,
            client_id: 'fixture-old-client',
            client_secret_configured: true,
          });
        },
      });
    },
    applyJAPublicInfo(info) {
      context.window._jaConfiguredClientId = info.client_id;
      context.window._jaClientSecretConfigured = !!info.client_secret_configured;
      idField.value = info.client_id;
    },
    openJobAdderSettings(message) { calls.push('open:' + message); },
    showToast(message, kind) { calls.push('toast:' + kind + ':' + message); },
  });
  vm.runInContext(functionSource(html, 'jobAdderLogin'), context);
  await context.jobAdderLogin();
  assert.strictEqual(idField.value, 'fixture-new-client');
  assert.ok(calls.some(item => item.startsWith('open:')));
  assert.ok(calls.some(item => item.startsWith('toast:err:')));
}

function localAccountStateIsClearedWithoutForgettingClientId() {
  const values = new Map([
    ['ja_client_id', 'fixture-client-id'],
    ['ja_access_token', 'fixture-access-token'],
    ['ja_refresh_token', 'fixture-refresh-token'],
    ['ja_token_expiry', '123'],
    ['ja_api_url', 'https://api.jobadder.com/v2'],
    ['ja_web_base', 'https://eu.jobadder.com'],
    ['ja_perm_work_type_id', 'fixture-work-type'],
    ['ja_client_secret', 'legacy-fixture-secret'],
  ]);
  const context = vm.createContext({
    console,
    window: {_jaWebBase: 'https://eu.jobadder.com', _jaPermWorkTypeId: 'fixture-work-type'},
    localStorage: {
      removeItem(key) { values.delete(key); },
      getItem(key) { return values.get(key) || null; },
    },
  });
  vm.runInContext(functionSource(html, 'clearJALocalAccountState'), context);
  context.clearJALocalAccountState();
  assert.strictEqual(values.get('ja_client_id'), 'fixture-client-id');
  [
    'ja_access_token',
    'ja_refresh_token',
    'ja_token_expiry',
    'ja_api_url',
    'ja_web_base',
    'ja_perm_work_type_id',
    'ja_client_secret',
  ].forEach(key => assert.strictEqual(values.has(key), false, 'stale local key: ' + key));
  assert.strictEqual(context.window._jaWebBase, '');
  assert.strictEqual(context.window._jaPermWorkTypeId, null);

  assert.ok(!/localStorage\.setItem\(\s*['"]ja_client_secret['"]/.test(html));
  assert.ok(!/localStorage\.setItem\(\s*['"]ja_access_token['"]/.test(html));
  assert.ok(!/localStorage\.setItem\(\s*['"]ja_refresh_token['"]/.test(html));
}

async function signOutIsConfirmedSuccessOrderedAndFailureVisible() {
  async function run(response) {
    const events = [];
    const context = vm.createContext({
      console,
      window: {
        _jaToken: true,
        confirm(message) { events.push('confirm:' + message); return true; },
      },
      fetch(url, init) {
        events.push('fetch:' + url + ':' + init.method);
        return Promise.resolve({
          ok: response.ok,
          status: response.status,
          json() { return Promise.resolve(response.payload); },
        });
      },
      applyJAPublicInfo(payload) { events.push('apply:' + String(payload.connected)); },
      renderJAConnectionState(payload) {
        events.push('render:' + String(payload.connected));
        context.window._jaToken = !!payload.connected;
      },
      clearJALocalAccountState() { events.push('clear-local'); },
      clearTheSpiderJobAdderAccountState() { events.push('clear-spider-account'); },
      clearPPCJobAdderAccountState() { events.push('clear-ppc-account'); return Promise.resolve(); },
      invalidateOneNoteJobAdderMatches() { events.push('clear-onenote-account'); },
      refreshIntegrationDiagnostics() { events.push('refresh'); return Promise.resolve(); },
      showToast(message, kind) { events.push('toast:' + kind + ':' + message); },
      Error,
    });
    vm.runInContext(functionSource(html, 'signOutJobAdder'), context);
    const result = await context.signOutJobAdder();
    return {events, token: context.window._jaToken, result};
  }

  const success = await run({
    ok: true,
    status: 200,
    payload: {
      ok: true,
      connected: false,
      client_id: 'fixture-client-id',
      client_secret_configured: true,
    },
  });
  assert.strictEqual(success.result, true);
  assert.strictEqual(success.token, false);
  assert.ok(success.events[0].startsWith('confirm:'));
  assert.ok(success.events.includes('fetch:/jobadder/sign_out:POST'));
  assert.ok(success.events.indexOf('fetch:/jobadder/sign_out:POST') < success.events.indexOf('render:false'));
  assert.strictEqual(success.events.filter(item => item.startsWith('toast:ok:')).length, 1);
  assert.ok(success.events.includes('toast:ok:Signed out from JobAdder in CV Studio'));
  assert.ok(success.events.includes('clear-local'));
  assert.ok(success.events.includes('clear-spider-account'));
  assert.ok(success.events.includes('clear-ppc-account'));
  assert.ok(success.events.includes('clear-onenote-account'));
  assert.ok(success.events.includes('refresh'));

  const failure = await run({
    ok: false,
    status: 409,
    payload: {ok: false, error: 'A JobAdder write is still in progress.'},
  });
  assert.strictEqual(failure.result, false);
  assert.strictEqual(failure.token, true);
  assert.ok(!failure.events.includes('clear-local'));
  assert.ok(!failure.events.includes('clear-spider-account'));
  assert.ok(!failure.events.includes('clear-ppc-account'));
  assert.ok(!failure.events.includes('clear-onenote-account'));
  assert.strictEqual(failure.events.filter(item => item.startsWith('toast:err:')).length, 1);
}

function tenantBoundBrowserStateInvalidationIsComplete() {
  const spider = functionSource(html, 'clearTheSpiderJobAdderAccountState');
  [
    '_theSpiderSearchRunSeq',
    'resetTheSpiderPreviewCaches',
    '_theSpiderLastResults=[]',
    '_theSpiderSearchContext=null',
    "getElementById('theSpiderSearchBody')",
  ].forEach(marker => assert.ok(spider.includes(marker), 'crawler cleanup missing: ' + marker));

  const oneNote = functionSource(html, 'invalidateOneNoteJobAdderMatches');
  [
    '_oneNoteJobAdderAccountSeq',
    "candidate_id = ''",
    'raw_match = null',
    'matched_name',
    'selected = false',
    'oneNoteRenderRows',
  ].forEach(marker => assert.ok(oneNote.includes(marker), 'OneNote cleanup missing: ' + marker));
  const lookup = functionSource(html, 'oneNoteLookupCandidateForRow');
  assert.ok(lookup.includes('_oneNoteJobAdderAccountSeq'));
  assert.ok(lookup.includes('jobAdderAccountInvalidated'));

  const ppc = functionSource(html, 'clearPPCJobAdderAccountState');
  [
    '_ppcAccountRunSeq',
    '_ppcItems=[]',
    '_ppcMemoryCache={}',
    'ppcCacheClearPersistent',
  ].forEach(marker => assert.ok(ppc.includes(marker), 'PPC cleanup missing: ' + marker));
  assert.ok(functionSource(html, 'ppcCacheClearPersistent').includes('PPC_CACHE_FALLBACK_STORE'));
  const cacheKey = functionSource(html, 'ppcCacheKeyFor');
  assert.ok(cacheKey.includes('_jaAccountCacheNamespace'));
  const publicInfo = functionSource(html, 'applyJAPublicInfo');
  assert.ok(publicInfo.includes('previousAccountCacheNamespace'));
  assert.ok(publicInfo.includes('nextAccountCacheNamespace'));
  assert.ok(publicInfo.includes('previousAccountCacheNamespace !== nextAccountCacheNamespace'));
  assert.ok(functionSource(html, 'jaAccountCacheNamespace').includes('account_cache_namespace'));
  assert.ok(!functionSource(html, 'saveJobAdderSettings').includes('skipAccountStateInvalidation:true'));
  assert.ok(functionSource(html, 'signOutJobAdder').includes('skipAccountStateInvalidation:true'));
  assert.ok(/PPC_CACHE_SCHEMA\s*=\s*5\b/.test(html));
}

function everyConnectionSurfaceUsesSharedRenderer() {
  const source = functionSource(html, 'renderJAConnectionState');
  [
    'btnJALogin',
    'btnJA',
    'jaStatus',
    'batchJAConnBadge',
    'batchJAStatus',
    'oneNoteConnBadge',
    'ppcSetConnected',
    'theSpiderBadge',
    'settingsJobAdderStatus',
    'settingsJobAdderDetail',
    'updateJAUploadConnStatus',
    'updateJACreateConnStatus',
  ].forEach(marker => assert.ok(source.includes(marker), 'shared status renderer missing: ' + marker));
  assert.ok(functionSource(html, 'updateJAConnectedUI').includes('renderJAConnectionState'));
  assert.ok(functionSource(html, 'refreshIntegrationDiagnostics').includes('renderJAConnectionState'));
}

const cases = [
  ['Format and Settings JobAdder controls are centralized', formatAndSettingsMarkupAreCentralized],
  ['missing setup opens and focuses Settings', missingSetupOpensAndFocusesSettings],
  ['changed Client ID cannot reuse old saved secret', changedClientIdCannotReuseOldSavedSecret],
  ['local account state clears without forgetting Client ID', localAccountStateIsClearedWithoutForgettingClientId],
  ['sign-out success ordering and failure visibility', signOutIsConfirmedSuccessOrderedAndFailureVisible],
  ['tenant-bound browser state invalidation is complete', tenantBoundBrowserStateInvalidationIsComplete],
  ['all connection surfaces use the shared renderer', everyConnectionSurfaceUsesSharedRenderer],
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
    failures.forEach(failure => console.error(failure.error && failure.error.stack ? failure.error.stack : failure.error));
    process.exitCode = 1;
    return;
  }
  console.log('JobAdder account-management frontend fixtures passed');
}());
