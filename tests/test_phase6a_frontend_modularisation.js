'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const moduleRoot = path.join(root, 'vendor', 'cvstudio');
const moduleFiles = {
  api: path.join(moduleRoot, 'api-transport.js'),
  pageNav: path.join(moduleRoot, 'page-nav.js'),
  heartbeat: path.join(moduleRoot, 'server-heartbeat.js'),
};

function sourceOrInline(modulePath, startMarker, endMarker) {
  if (fs.existsSync(modulePath)) return fs.readFileSync(modulePath, 'utf8');
  const start = html.indexOf(startMarker);
  const end = html.indexOf(endMarker, start);
  if (start < 0 || end < 0) {
    throw new Error('Missing characterized inline boundary: ' + startMarker);
  }
  const lineStart = html.lastIndexOf('\n', start) + 1;
  const lineEnd = html.lastIndexOf('\n', end) + 1;
  return html.slice(lineStart, lineEnd);
}

function classListFixture() {
  const values = new Set();
  return {
    add(value) { values.add(value); },
    remove(value) { values.delete(value); },
    contains(value) { return values.has(value); },
    toggle(value, enabled) {
      if (enabled) values.add(value); else values.delete(value);
    },
    values,
  };
}

function styleFixture() {
  const values = {};
  return {
    setProperty(key, value) { values[key] = String(value); },
    removeProperty(key) { delete values[key]; },
    getPropertyValue(key) { return values[key] || ''; },
    values,
  };
}

function jsonResponse(payload, status, url) {
  const body = JSON.parse(JSON.stringify(payload));
  return {
    status,
    ok: status >= 200 && status < 300,
    url,
    headers: new Headers({
      'Content-Type': 'application/json',
      'X-CV-Studio-Request-ID': 'server-request-id',
    }),
    json() { return Promise.resolve(JSON.parse(JSON.stringify(body))); },
    text() { return Promise.resolve(JSON.stringify(body)); },
  };
}

async function apiTransportContract() {
  const calls = [];
  const events = [];
  let networkFailure = false;
  const nativeFetch = function(input, init) {
    calls.push({input, init});
    if (networkFailure) return Promise.reject(new Error('fixture network failure'));
    return Promise.resolve(jsonResponse({
      ok: false,
      message: 'Fixture failure',
      code: 'FIXTURE_FAILURE',
      action: 'retry',
    }, 409, 'http://127.0.0.1:5000/fixture'));
  };
  const window = {
    fetch: nativeFetch,
    location: {
      href: 'http://127.0.0.1:5000/',
      origin: 'http://127.0.0.1:5000',
    },
    crypto: {
      getRandomValues(bytes) {
        for (let index = 0; index < bytes.length; index += 1) bytes[index] = index + 1;
        return bytes;
      },
    },
    dispatchEvent(event) { events.push(event); },
  };
  function CustomEvent(type, options) {
    this.type = type;
    this.detail = options && options.detail;
  }
  const context = vm.createContext({
    console,
    window,
    Headers,
    URL,
    Uint8Array,
    CustomEvent,
    Date,
    Math,
    JSON,
    Object,
    Array,
    String,
    Number,
    Promise,
    Error,
  });
  vm.runInContext(sourceOrInline(
    moduleFiles.api,
    '// Central local API transport',
    '// Replace these with your JobAdder app credentials',
  ), context);

  assert.strictEqual(typeof window.cvStudioNormaliseApiFailure, 'function');
  assert.ok(Array.isArray(window._cvStudioRecentApiErrors));
  const response = await window.fetch('/fixture', {method: 'POST'});
  const data = await response.json();
  const headers = new Headers(calls[0].init.headers);
  assert.strictEqual(headers.get('X-CV-Studio-Request'), '1');
  assert.strictEqual(headers.get('X-CV-Studio-Request-ID'), '0102030405060708');
  assert.strictEqual(data.ok, false);
  assert.strictEqual(data.code, 'FIXTURE_FAILURE');
  assert.strictEqual(data.request_id, 'server-request-id');
  assert.ok(data.error.includes('Retry the action.'));
  assert.ok(data.error.includes('Request ID: server-request-id'));
  assert.strictEqual(window._cvStudioRecentApiErrors.length, 1);
  assert.strictEqual(events.length, 1);
  assert.strictEqual(events[0].type, 'cvstudio-api-error');

  networkFailure = true;
  await assert.rejects(
    window.fetch('/network-failure', {method: 'POST'}),
    error => error.message === 'fixture network failure'
      && error.cvStudioRequestId === '0102030405060708',
  );
  assert.strictEqual(window._cvStudioRecentApiErrors.slice(-1)[0].code, 'NETWORK_ERROR');
}

function pageNavContract() {
  const documentListeners = [];
  const windowListeners = [];
  const animationFrames = [];
  const durableWrites = [];
  const toasts = [];
  const stored = {'cvstudio_page_nav_pinned_v1': '1'};
  const nav = {classList: classListFixture(), style: styleFixture()};
  const button = {
    attributes: {},
    setAttribute(key, value) { this.attributes[key] = String(value); },
    title: '',
  };
  const label = {textContent: ''};
  const spacer = {style: styleFixture()};
  const body = {
    classList: classListFixture(),
    style: styleFixture(),
    scrollTop: 0,
  };
  const elements = {
    pageTabs: nav,
    pageTabsSpacer: spacer,
    pageNavPinToggle: button,
    pageNavPinLabel: label,
  };
  const document = {
    body,
    documentElement: {scrollTop: 0},
    getElementById(id) { return elements[id] || null; },
    querySelector() { return null; },
    addEventListener(type, listener, options) {
      documentListeners.push({type, listener, options});
    },
  };
  const window = {
    innerWidth: 1200,
    innerHeight: 900,
    pageYOffset: 0,
    addEventListener(type, listener, options) {
      windowListeners.push({type, listener, options});
    },
    requestAnimationFrame(listener) { animationFrames.push(listener); return animationFrames.length; },
    scrollTo() {},
  };
  const context = vm.createContext({
    console,
    window,
    document,
    localStorage: {
      getItem(key) { return Object.prototype.hasOwnProperty.call(stored, key) ? stored[key] : null; },
      setItem(key, value) { stored[key] = String(value); },
    },
    cvStudioDurableSettingSet(key, value) { durableWrites.push([key, value]); return Promise.resolve(true); },
    showToast(message, kind) { toasts.push([message, kind]); },
    Object,
    Array,
    String,
    Number,
    Math,
    Promise,
  });
  vm.runInContext(sourceOrInline(
    moduleFiles.pageNav,
    'Optional pinned main navigation',
    "document.addEventListener('DOMContentLoaded', initPageNavPin);",
  ), context);

  [
    'pageNavPinSupported',
    'pageNavPinStored',
    'pageNavDocumentScrollTop',
    'updatePageNavPinButton',
    'restorePageNavHome',
    'pageNavRestoreScrollView',
    'pageNavPinActiveView',
    'clearPageNavFloating',
    'refreshPageNavPin',
    'queuePageNavPinRefresh',
    'setPageNavPin',
    'togglePageNavPin',
    'initPageNavPin',
  ].forEach(name => assert.strictEqual(typeof context[name], 'function', 'missing global ' + name));
  assert.strictEqual(context.PAGE_NAV_PIN_STORE, 'cvstudio_page_nav_pinned_v1');
  assert.strictEqual(documentListeners.length, 0);
  document.addEventListener('DOMContentLoaded', context.initPageNavPin);
  assert.strictEqual(documentListeners[0].type, 'DOMContentLoaded');
  assert.strictEqual(documentListeners[0].listener, context.initPageNavPin);

  context.initPageNavPin();
  assert.strictEqual(context._pageNavPinEnabled, true);
  assert.ok(windowListeners.some(entry => entry.type === 'scroll'));
  assert.ok(windowListeners.some(entry => entry.type === 'resize'));
  assert.ok(documentListeners.some(entry => entry.type === 'scroll'));
  context.setPageNavPin(false, true, true);
  assert.deepStrictEqual(durableWrites, [['cvstudio_page_nav_pinned_v1', '0']]);
  assert.strictEqual(button.attributes['aria-pressed'], 'false');
  assert.strictEqual(label.textContent, 'Pin tabs');
  assert.ok(toasts[0][0].includes('unpinned'));
  assert.ok(animationFrames.length > 0);
}

async function flushPromises() {
  await Promise.resolve();
  await new Promise(resolve => setImmediate(resolve));
}

async function heartbeatContract() {
  const intervals = [];
  const timeouts = [];
  const prepended = [];
  const requests = [];
  let online = false;
  let reloads = 0;

  function elementFixture() {
    return {
      id: '',
      style: {},
      innerHTML: '',
      textContent: '',
      disabled: false,
      children: [],
      appendChild(child) { this.children.push(child); },
      remove() {},
    };
  }
  const document = {
    body: {prepend(node) { prepended.push(node); }},
    createElement() { return elementFixture(); },
    querySelector() { return null; },
    getElementById() { return null; },
  };
  function fetch(url, options) {
    requests.push({url, options});
    if (!online) return Promise.reject(new Error('server unavailable'));
    return Promise.resolve({ok: true, status: 204});
  }
  const context = vm.createContext({
    console,
    document,
    fetch,
    location: {reload() { reloads += 1; }},
    setInterval(listener, milliseconds) {
      intervals.push({listener, milliseconds});
      return intervals.length;
    },
    clearInterval() {},
    setTimeout(listener, milliseconds) {
      timeouts.push({listener, milliseconds});
      return timeouts.length;
    },
    Promise,
  });
  vm.runInContext(sourceOrInline(
    moduleFiles.heartbeat,
    'Heartbeat: ping server every 10s',
    'try { updateSummaryLockUI(); }',
  ), context);

  await flushPromises();
  assert.strictEqual(requests[0].url, '/heartbeat');
  assert.strictEqual(requests[0].options.method, 'POST');
  assert.strictEqual(intervals.length, 1);
  assert.strictEqual(intervals[0].milliseconds, 20000);
  for (let count = 0; count < 3; count += 1) {
    intervals[0].listener();
    await flushPromises();
  }
  assert.strictEqual(prepended.length, 1);
  assert.strictEqual(prepended[0].id, 'reconnect-banner');
  assert.strictEqual(prepended[0].style.background, '#c05621');
  assert.ok(prepended[0].children.some(child => child.textContent.endsWith('Restart Server')));

  online = true;
  intervals[0].listener();
  await flushPromises();
  assert.strictEqual(prepended[0].style.background, '#2f855a');
  assert.ok(prepended[0].innerHTML.includes('reloading automatically'));
  const reloadTimeout = timeouts.find(entry => entry.milliseconds === 1500);
  assert.ok(reloadTimeout);
  reloadTimeout.listener();
  assert.strictEqual(reloads, 1);
}

function extractedScriptOrderContract() {
  const relativeModules = [
    'vendor/cvstudio/api-transport.js',
    'vendor/cvstudio/page-nav.js',
    'vendor/cvstudio/server-heartbeat.js',
  ];
  const present = relativeModules.filter(relative => fs.existsSync(path.join(root, relative)));
  if (!present.length) return;
  assert.deepStrictEqual(present, relativeModules.slice(0, present.length));
  const positions = present.map(relative => html.indexOf('/' + relative));
  positions.forEach((position, index) => assert.ok(position >= 0, 'module is not loaded: ' + present[index]));
  assert.strictEqual(new Set(positions).size, present.length);
  assert.ok(positions[0] < html.indexOf('var JA_REDIRECT_URI'));
  if (positions.length > 1) {
    assert.ok(positions[0] < positions[1]);
    assert.ok(positions[1] < html.indexOf('var JA_REDIRECT_URI'));
    assert.ok(positions[1] < html.indexOf('var _cvStudioPhase2bSettingsStartupPromise'));
    const adapter = html.indexOf("document.addEventListener('DOMContentLoaded', initPageNavPin);");
    assert.ok(adapter > html.indexOf('function downloadBatchZip'));
    assert.ok(adapter < html.indexOf('Ensure Settings AI Routing controls exist'));
  }
  if (positions.length > 2) {
    assert.ok(positions[2] > html.indexOf('function clearStats'));
    assert.ok(positions[2] < html.lastIndexOf('try { updateSummaryLockUI(); }'));
  }
}

const cases = [
  ['local API transport request/error compatibility', apiTransportContract],
  ['page navigation globals, storage and listener compatibility', pageNavContract],
  ['server heartbeat timing and recovery compatibility', heartbeatContract],
  ['deterministic extracted script ordering', extractedScriptOrderContract],
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
  console.log('Phase 6A frontend modularisation fixtures passed');
}());
