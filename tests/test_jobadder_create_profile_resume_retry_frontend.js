'use strict';

// Create Profile must preserve the already-found/created JobAdder candidate
// when only the original résumé attachment fails.  Its retry button must send
// only that same File again, without re-running extraction or paid parsing.

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

function escapeHtml(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function buildContext(uploadImpl) {
  const list = { innerHTML: '' };
  const calls = { completed: 0, failed: 0, done: 0, tabFailed: 0, toasts: [] };
  const context = vm.createContext({
    console, Promise, String,
    _jaCreateQueue: [],
    document: {
      getElementById: function(id) { return id === 'jaCreateList' ? list : null; },
    },
    esc: escapeHtml,
    escAttr: escapeHtml,
    markTabRunning: function() { return 'fixture-run'; },
    markTabDone: function() { calls.done += 1; },
    markTabFailed: function() { calls.tabFailed += 1; },
    jaUploadOriginalCV: uploadImpl,
    jaProfileUrlAsync: async function(candidateId) { return 'https://jobadder.invalid/candidates/' + candidateId; },
    oneNoteProfileCreateCompleted: function() { calls.completed += 1; },
    oneNoteProfileCreateFailed: function() { calls.failed += 1; },
    showToast: function(message, type) { calls.toasts.push({ message, type }); },
  });
  vm.runInContext(
    functionRange(html, 'renderJACreateList') + '\n' +
    functionRange(html, 'jaCreateErrorMessage') + '\n' +
    'async ' + functionRange(html, 'markJACreateResumeUploadFailure') + '\n' +
    'async ' + functionRange(html, 'retryJACreateResumeUpload'),
    context,
  );
  return { context, list, calls };
}

async function failedProfileRemainsVisibleAndEscaped() {
  const env = buildContext(async function() {});
  const item = {
    id: 'fixture',
    file: { name: 'candidate.docx' },
    status: 'error',
    statusText: '⚠️ Latest CV failed <img src=x onerror=alert(1)>',
    jaClass: 'show ja-err',
    jaProfileUrl: 'https://jobadder.invalid/candidates/123',
    _resumeUploadFailed: true,
  };
  env.context._jaCreateQueue.push(item);
  env.context.renderJACreateList();
  assert.ok(env.list.innerHTML.includes('Retry CV'));
  assert.ok(env.list.innerHTML.includes('View in JobAdder'));
  assert.ok(env.list.innerHTML.includes('&lt;img'));
  assert.ok(!env.list.innerHTML.includes('<img src=x'), 'remote error text must not become HTML');
  assert.ok(!env.list.innerHTML.includes('✅ <a'), 'an incomplete upload must not show all-green success');
}

async function retryUploadsOnlyTheOriginalFile() {
  const sourceFile = { name: 'candidate.docx', marker: 'same File' };
  const uploadCalls = [];
  const env = buildContext(async function(candidateId, file, filename) {
    uploadCalls.push({ candidateId, file, filename });
    return { ok: true };
  });
  const item = {
    id: 'fixture',
    file: sourceFile,
    status: 'error',
    statusText: 'failed',
    jaClass: 'show ja-err',
    jaProfileUrl: '',
    _candidateId: 123,
    _candidateWasCreated: false,
    _resumeUploadFailed: true,
    _parsedCand: {},
  };
  env.context._jaCreateQueue.push(item);
  await env.context.retryJACreateResumeUpload(item);
  assert.strictEqual(uploadCalls.length, 1);
  assert.strictEqual(uploadCalls[0].candidateId, 123);
  assert.strictEqual(uploadCalls[0].file, sourceFile, 'retry must preserve the browser File and its MIME metadata');
  assert.strictEqual(uploadCalls[0].filename, 'candidate.docx');
  assert.strictEqual(item.status, 'done');
  assert.strictEqual(item._resumeUploadFailed, false);
  assert.strictEqual(env.calls.completed, 1);
  assert.strictEqual(env.calls.failed, 0);
  assert.strictEqual(env.calls.done, 1);
}

async function retryFailureKeepsCandidateLinkAndFullReason() {
  const env = buildContext(async function() {
    const error = new Error('JobAdder error: 422 — attachment validation failed');
    error.isResumeUploadFailure = true;
    throw error;
  });
  const item = {
    id: 'fixture',
    file: { name: 'candidate.pdf' },
    status: 'error',
    statusText: '',
    jaClass: 'show ja-err',
    jaProfileUrl: '',
    _candidateId: 123,
    _candidateWasCreated: false,
    _resumeUploadFailed: true,
    _parsedCand: {},
  };
  env.context._jaCreateQueue.push(item);
  await env.context.retryJACreateResumeUpload(item);
  assert.strictEqual(item.status, 'error');
  assert.strictEqual(item._resumeUploadFailed, true);
  assert.ok(item.statusText.includes('Profile exists'));
  assert.ok(item.statusText.includes('attachment validation failed'));
  assert.ok(item.jaProfileUrl.includes('/123'));
  assert.strictEqual(env.calls.completed, 0);
  assert.strictEqual(env.calls.failed, 1);
  assert.strictEqual(env.calls.tabFailed, 1);
}

const cases = [
  ['failed profile remains visible and escaped', failedProfileRemainsVisibleAndEscaped],
  ['retry uploads only the original File', retryUploadsOnlyTheOriginalFile],
  ['retry failure keeps candidate link and reason', retryFailureKeepsCandidateLinkAndFullReason],
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
  console.log('JobAdder Create Profile résumé retry frontend fixtures passed');
}());
