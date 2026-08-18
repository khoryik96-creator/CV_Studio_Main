'use strict';

// Verifies the client-side JobAdder 429 auto-retry that backs the Format,
// Batch, and Create Profile upload flows. A 429 means JobAdder rejected the
// request before processing it, so retrying the identical call is safe; a
// thrown timeout/network error is never retried (the request may have been
// processed server-side, which could duplicate a candidate or attachment).

const assert = require('assert');
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
    if (char === '}' && --depth === 0) return source.slice(start, index + 1);
  }
  throw new Error('Unterminated function: ' + name);
}

function makeResponse(status, retryAfter) {
  return {
    status: status,
    ok: status >= 200 && status < 300,
    headers: { get: function(name) { return name === 'Retry-After' ? (retryAfter || null) : null; } },
    json: async function() { return { status: status }; },
  };
}

function buildContext(fetchImpl) {
  const toasts = [];
  const context = vm.createContext({
    console, Promise, Math, parseInt, isFinite, String, Object,
    setTimeout: function(fn) { fn(); return 0; }, // fire immediately: no real waiting in tests
    fetchWithTimeout: fetchImpl,
    showToast: function(msg, type) { toasts.push({ msg: msg, type: type }); },
  });
  vm.runInContext(
    functionRange(html, 'jaRetrySleep') + '\n' +
    functionRange(html, 'jaRateLimitDelayMs') + '\n' +
    functionRange(html, 'jaPostWithRetry'),
    context,
  );
  return { context, toasts };
}

async function retriesOn429ThenSucceeds() {
  let calls = 0;
  const env = buildContext(function() {
    calls += 1;
    return Promise.resolve(calls === 1 ? makeResponse(429) : makeResponse(200));
  });
  const r = await env.context.jaPostWithRetry('/jobadder/upload_cv', {}, 30000, 'CV upload');
  assert.strictEqual(calls, 2, 'should retry exactly once after a 429');
  assert.strictEqual(r.status, 200, 'should return the successful response');
  assert.strictEqual(env.toasts.length, 1, 'should notify the user it is auto-retrying');
  assert.ok(env.toasts[0].msg.indexOf('CV upload') >= 0, 'toast should name the labelled action');
}

async function nonRateLimitErrorIsNotRetried() {
  let calls = 0;
  const env = buildContext(function() { calls += 1; return Promise.resolve(makeResponse(400)); });
  const r = await env.context.jaPostWithRetry('/jobadder/create_candidate', {}, 15000, 'profile creation');
  assert.strictEqual(calls, 1, 'a non-429 error must not be retried');
  assert.strictEqual(r.status, 400, 'the original error response is returned to the caller');
  assert.strictEqual(env.toasts.length, 0, 'no retry notification for a non-429 error');
}

async function successFirstTryDoesNotRetry() {
  let calls = 0;
  const env = buildContext(function() { calls += 1; return Promise.resolve(makeResponse(200)); });
  const r = await env.context.jaPostWithRetry('/jobadder/upload_cv', {}, 30000, 'CV upload');
  assert.strictEqual(calls, 1, 'a first-try success makes no extra calls');
  assert.strictEqual(r.status, 200);
  assert.strictEqual(env.toasts.length, 0);
}

async function persistent429GivesUpAfterBoundedRetries() {
  let calls = 0;
  const env = buildContext(function() { calls += 1; return Promise.resolve(makeResponse(429)); });
  const r = await env.context.jaPostWithRetry('/jobadder/upload_cv', {}, 30000, 'CV upload');
  assert.strictEqual(calls, 3, 'one initial attempt plus two bounded retries');
  assert.strictEqual(r.status, 429, 'the final 429 is handed back so the caller can surface it');
}

async function thrownTimeoutIsNotRetried() {
  let calls = 0;
  const env = buildContext(function() { calls += 1; return Promise.reject(new Error('Request timed out after 30s')); });
  let threw = null;
  try {
    await env.context.jaPostWithRetry('/jobadder/create_candidate', {}, 15000, 'profile creation');
  } catch (e) { threw = e; }
  assert.ok(threw, 'a thrown timeout should propagate');
  assert.strictEqual(calls, 1, 'a timeout/network error must never be retried (could duplicate the write)');
}

function delayHonoursRetryAfterAndDefaultsAndClamps() {
  const env = buildContext(function() { return Promise.resolve(makeResponse(200)); });
  const delay = env.context.jaRateLimitDelayMs;
  assert.strictEqual(delay(makeResponse(429, '10')), 10000, 'honours a valid Retry-After (seconds)');
  assert.strictEqual(delay(makeResponse(429, null)), 30000, 'defaults to 30s when no header');
  assert.strictEqual(delay(makeResponse(429, '2')), 5000, 'clamps up to a 5s floor');
  assert.strictEqual(delay(makeResponse(429, '999')), 60000, 'clamps down to a 60s ceiling');
  assert.strictEqual(delay(makeResponse(429, 'garbage')), 30000, 'ignores an unparseable header');
}

const cases = [
  ['retries once on 429 then succeeds', retriesOn429ThenSucceeds],
  ['non-429 error is not retried', nonRateLimitErrorIsNotRetried],
  ['first-try success does not retry', successFirstTryDoesNotRetry],
  ['persistent 429 gives up after bounded retries', persistent429GivesUpAfterBoundedRetries],
  ['thrown timeout is not retried', thrownTimeoutIsNotRetried],
  ['delay honours Retry-After, defaults, and clamps', delayHonoursRetryAfterAndDefaultsAndClamps],
];

(async function run() {
  const failures = [];
  for (const [name, test] of cases) {
    try {
      await test();
      console.log('PASS:', name);
    } catch (error) {
      failures.push({ name, error });
      console.error('FAIL:', name, '-', error && error.message ? error.message : error);
    }
  }
  if (failures.length) {
    for (const failure of failures) console.error(failure.error && failure.error.stack ? failure.error.stack : failure.error);
    process.exitCode = 1;
    return;
  }
  console.log('JobAdder 429 auto-retry frontend fixtures passed');
}());
