'use strict';

// AI output can contain labels, arrays, placeholders or concatenated prose in
// contact fields. Create Profile must reduce those values to one valid email
// and one plausible phone before searching or writing to JobAdder.

const assert = require('assert');
const vm = require('vm');
const html = require('./frontend_sources').frontendSource();

function functionRange(source, name) {
  const marker = 'function ' + name + '(';
  const start = source.indexOf(marker);
  if (start < 0) throw new Error('Missing function: ' + name);
  const brace = source.indexOf('{', start + marker.length);
  let depth = 0, quote = '', escaped = false;
  for (let i = brace; i < source.length; i += 1) {
    const c = source[i];
    if (quote) {
      if (escaped) escaped = false;
      else if (c === '\\') escaped = true;
      else if (c === quote) quote = '';
      continue;
    }
    if (c === '"' || c === "'") { quote = c; continue; }
    if (c === '{') depth += 1;
    if (c === '}' && --depth === 0) return source.slice(start, i + 1);
  }
  throw new Error('Unterminated function: ' + name);
}

const context = vm.createContext({ String, Array });
vm.runInContext(
  functionRange(html, 'extractJACreateEmailFallback') + '\n' +
  functionRange(html, 'cleanJACreateEmailCandidate') + '\n' +
  functionRange(html, 'cleanJACreatePhoneCandidate') + '\n' +
  functionRange(html, 'extractJACreatePhoneFallback') + '\n' +
  functionRange(html, 'applyJACreateContactFallback'),
  context,
);

const cvText = [
  'Candidate Name',
  'Email: candidate@example.com',
  'Mobile: +60 12-345 6789',
].join('\n');

const cleaned = context.applyJACreateContactFallback({
  email: 'Email not provided',
  phone: 'Mobile: +60 12-345 6789 Address: a very long field accidentally concatenated by AI '.repeat(3),
}, cvText);
assert.strictEqual(cleaned.email, 'candidate@example.com');
assert.strictEqual(cleaned.phone, '+60 12-345 6789');

const arrayEmail = context.applyJACreateContactFallback({
  email: [{ address: 'ARRAY.USER@EXAMPLE.COM' }],
  phone: 'not available',
}, cvText);
assert.strictEqual(arrayEmail.email, 'array.user@example.com');
assert.strictEqual(arrayEmail.phone, '+60 12-345 6789');

const noContacts = context.applyJACreateContactFallback({
  email: 'N/A',
  phone: '2020 - 2023',
}, 'Candidate without contact details');
assert.strictEqual(noContacts.email, '');
assert.strictEqual(noContacts.phone, '');

console.log('JobAdder Create Profile contact sanitization frontend fixtures passed');
