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

async function apiTimeoutContract() {
  const timers = [];
  let hangSignal = null;
  const nativeFetch = function(input, init) {
    // Simulate a request that never resolves on its own but rejects on abort,
    // exactly like a real fetch tied to an AbortSignal.
    hangSignal = init && init.signal;
    return new Promise((_resolve, reject) => {
      if (hangSignal) hangSignal.addEventListener('abort', () => {
        const err = new Error('aborted'); err.name = 'AbortError'; reject(err);
      });
    });
  };
  const window = {
    fetch: nativeFetch,
    location: {href: 'http://127.0.0.1:5000/', origin: 'http://127.0.0.1:5000'},
    crypto: {getRandomValues(bytes){ for (let i = 0; i < bytes.length; i += 1) bytes[i] = i + 1; return bytes; }},
    dispatchEvent() {},
  };
  const context = vm.createContext({
    console, window, Headers, URL, Uint8Array, Date, Math, JSON, Object, Array, String, Number, Promise, Error,
    AbortController,
    CustomEvent: function(){},
    setTimeout(fn, ms) { timers.push({fn, ms}); return timers.length; },
    clearTimeout() {},
  });
  vm.runInContext(sourceOrInline(
    moduleFiles.api,
    '// Central local API transport',
    '// Replace these with your JobAdder app credentials',
  ), context);

  // A same-origin GET gets the default deadline: a timer is armed, and firing it
  // aborts the request and surfaces a distinct TIMEOUT error (not a generic one).
  const pending = window.fetch('/status', {method: 'GET'});
  await flushPromises();
  const deadline = timers.find(entry => entry.ms === 60000);
  assert.ok(deadline, 'same-origin GET arms the default 60s deadline');
  deadline.fn();
  await assert.rejects(pending, error => error.code === 'TIMEOUT' && error.cvStudioTimeout === true);
  assert.strictEqual(window._cvStudioRecentApiErrors.slice(-1)[0].code, 'TIMEOUT');

  // Opt-out (cvStudioNoTimeout) and non-GET both skip the default deadline.
  timers.length = 0;
  window.fetch('/stream', {method: 'GET', cvStudioNoTimeout: true});
  window.fetch('/mutate', {method: 'POST'});
  await flushPromises();
  assert.strictEqual(timers.length, 0, 'opt-out GET and POST get no default deadline');
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
  const listeners = {};
  let online = false;
  let reloads = 0;
  let intervalId = 0;
  let hang = false;
  const hangResolvers = [];

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
  function record(type, fn) { (listeners[type] = listeners[type] || []).push(fn); }
  const document = {
    body: {prepend(node) { prepended.push(node); }},
    createElement() { return elementFixture(); },
    querySelector() { return null; },
    getElementById() { return null; },
    visibilityState: 'visible',
    addEventListener(type, fn) { record(type, fn); },
  };
  const window = { addEventListener(type, fn) { record(type, fn); } };
  function fetch(url, options) {
    requests.push({url, options});
    if (hang) return new Promise(resolve => hangResolvers.push(() => resolve({ok: true, status: 204})));
    if (!online) return Promise.reject(new Error('server unavailable'));
    return Promise.resolve({ok: true, status: 204});
  }
  const context = vm.createContext({
    console,
    document,
    window,
    fetch,
    location: {reload() { reloads += 1; }},
    setInterval(listener, milliseconds) {
      const id = ++intervalId;
      intervals.push({id, listener, milliseconds});
      return id;
    },
    clearInterval(id) {
      const index = intervals.findIndex(entry => entry.id === id);
      if (index >= 0) intervals.splice(index, 1);
    },
    setTimeout(listener, milliseconds) {
      timeouts.push({listener, milliseconds});
      return timeouts.length;
    },
    clearTimeout() {},
    Date,
    Promise,
  });
  vm.runInContext(sourceOrInline(
    moduleFiles.heartbeat,
    'Heartbeat: ping server every 10s',
    'try { updateSummaryLockUI(); }',
  ), context);

  const steadyInterval = () => intervals.find(entry => entry.milliseconds === 20000);
  const recoveryInterval = () => intervals.find(entry => entry.milliseconds === 2500);

  // Immediate ping on load hits /heartbeat via POST, and one steady interval is scheduled.
  await flushPromises();
  assert.strictEqual(requests[0].url, '/heartbeat');
  assert.strictEqual(requests[0].options.method, 'POST');
  assert.ok(steadyInterval(), 'steady 20s interval is scheduled');

  // The load ping failed (offline) so a fast-recovery burst is now scheduled too —
  // asserting scheduler state, not a permanently fixed interval count.
  assert.ok(recoveryInterval(), 'fast-recovery interval starts after a missed ping');

  // In-flight guard: while one request is pending, extra triggers (steady tick +
  // wake/focus/online/pageshow) must not open a second overlapping request.
  online = true;
  hang = true;
  const pendingStart = requests.length;
  steadyInterval().listener();
  await flushPromises();
  assert.strictEqual(requests.length, pendingStart + 1, 'one heartbeat starts while pending');
  steadyInterval().listener();
  (listeners.focus || []).forEach(fn => fn());
  (listeners.online || []).forEach(fn => fn());
  (listeners.pageshow || []).forEach(fn => fn());
  await flushPromises();
  assert.strictEqual(requests.length, pendingStart + 1, 'in-flight guard prevents overlapping heartbeats');
  hang = false;
  hangResolvers.splice(0).forEach(resolve => resolve());
  await flushPromises();

  // Drive four consecutive misses to raise the lost-server banner.
  online = false;
  for (let count = 0; count < 4; count += 1) {
    const tick = steadyInterval();
    assert.ok(tick, 'steady interval still scheduled during outage');
    tick.listener();
    await flushPromises();
  }
  assert.strictEqual(prepended.length, 1);
  assert.strictEqual(prepended[0].id, 'reconnect-banner');
  assert.strictEqual(prepended[0].style.background, '#c05621');
  assert.ok(prepended[0].children.some(child => child.textContent.endsWith('Restart Server')));
  assert.ok(recoveryInterval(), 'fast recovery is running during the outage');

  // Recovery: a healthy ping flips to the green banner, stops the fast burst, and reloads once.
  online = true;
  steadyInterval().listener();
  await flushPromises();
  assert.strictEqual(prepended[0].style.background, '#2f855a');
  assert.ok(prepended[0].innerHTML.includes('reloading automatically'));
  assert.ok(!recoveryInterval(), 'fast recovery stops once the server is healthy again');
  const reloadTimeout = timeouts.find(entry => entry.milliseconds === 1500);
  assert.ok(reloadTimeout);
  reloadTimeout.listener();
  assert.strictEqual(reloads, 1);
}

function escJsAttrContract() {
  // escJsAttr() escapes a value for a JS string literal that itself sits inside an
  // inline HTML handler attribute. Simulate the browser: HTML-decode the attribute,
  // then run the resulting handler, and assert the value round-trips inertly (no
  // breakout) even for a crafted payload.
  function grab(signature) {
    const start = html.indexOf(signature);
    if (start < 0) throw new Error('missing ' + signature);
    let depth = 0, started = false;
    for (let j = html.indexOf('{', start); j < html.length; j += 1) {
      if (html[j] === '{') { depth += 1; started = true; }
      else if (html[j] === '}') { depth -= 1; if (started && depth === 0) return html.slice(start, j + 1); }
    }
    throw new Error('unbalanced ' + signature);
  }
  const sandbox = vm.createContext({});
  vm.runInContext(
    [grab('function esc('), grab('function escAttr('), grab('function jsStrEscape('), grab('function escJsAttr(')].join('\n')
      + '\nthis.escJsAttr = escJsAttr;',
    sandbox,
  );
  function htmlDecode(value) {
    return value.replace(/&quot;/g, '"').replace(/&#39;/g, "'")
      .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
  }
  const payloads = ['co_1', "a'b", 'x"y', "co_1'); alert(88); //", '</script>', 'a\\b', 'l1\nl2'];
  for (const raw of payloads) {
    const attr = sandbox.escJsAttr(raw);
    const runner = vm.createContext({captured: null, fn(value) { this.captured = value; }});
    runner.fn = function(value) { runner.captured = value; };
    vm.runInContext("fn('" + htmlDecode(attr) + "')", runner);
    assert.strictEqual(runner.captured, raw, 'escJsAttr breakout/mismatch for ' + JSON.stringify(raw));
  }
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
  ['local API transport deadline policy', apiTimeoutContract],
  ['page navigation globals, storage and listener compatibility', pageNavContract],
  ['server heartbeat timing and recovery compatibility', heartbeatContract],
  ['inline handler value escaping (escJsAttr)', escJsAttrContract],
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
