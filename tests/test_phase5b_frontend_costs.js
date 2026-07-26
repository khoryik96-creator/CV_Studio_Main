'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const html = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');

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

const pricingStart = html.indexOf('var MODEL_PRICING =');
const pricingEnd = html.indexOf('function inferProviderFromModel', pricingStart);
if (pricingStart < 0 || pricingEnd < 0) throw new Error('Missing pricing table');

let saved = null;
const context = vm.createContext({
  console,
  Object,
  Array,
  String,
  Number,
  Math,
  Date,
  isFinite,
  getModel() { return 'claude-sonnet-4-6'; },
  getProvider() { return 'anthropic'; },
  statsLoad() { return []; },
  statsSave(records) { saved = records; },
  renderStats() {},
});

const functions = [
  'inferProviderFromModel',
  'pricingForModel',
  'normalizeUsageClient',
  'costDetailsFromResponse',
  'statsMetaFromResponse',
  'statsRecord',
].map(name => extractFunction(html, name)).join('\n');

vm.runInContext(html.slice(pricingStart, pricingEnd) + functions, context);

const supplied = context.costDetailsFromResponse({
  model: 'claude-sonnet-4-6',
  provider: 'anthropic',
  cost: 0.002,
  cost_details: {
    usd: 0.002,
    input_tokens: 100,
    output_tokens: 10,
    api_calls: 1,
    cost_value_type: 'local_estimate',
    cost_authority: 'local_rate_table',
    usage_authority: 'provider_response',
    provider_billing_status: 'unavailable',
    provider_authoritative_cost_usd: null,
    reconciliation_status: 'provider_billing_unavailable',
    reconciliation_difference_usd: null,
    billing_data_missing: true,
  },
}, '', '');
assert.strictEqual(supplied.cost_value_type, 'local_estimate');
assert.strictEqual(supplied.provider_billing_status, 'unavailable');
assert.strictEqual(supplied.provider_authoritative_cost_usd, null);
assert.strictEqual(supplied.reconciliation_status, 'provider_billing_unavailable');

const fallback = context.costDetailsFromResponse({
  model: 'deepseek-v4-flash',
  provider: 'deepseek',
  usage: {input_tokens: 100, output_tokens: 10, api_calls: 1},
}, '', '');
assert.ok(fallback.usd > 0);
assert.strictEqual(fallback.cost_authority, 'local_rate_table');
assert.strictEqual(fallback.usage_authority, 'provider_response');
assert.strictEqual(fallback.provider_authoritative_cost_usd, null);
assert.strictEqual(fallback.billing_data_missing, true);

const meta = context.statsMetaFromResponse({
  model: 'claude-sonnet-4-6',
  provider: 'anthropic',
  cost_details: supplied,
}, '', '');
context.statsRecord(
  'Fixture',
  'format',
  supplied.usd,
  'claude-sonnet-4-6',
  '',
  'anthropic',
  meta,
);
assert.strictEqual(saved.length, 1);
assert.strictEqual(saved[0].cost_value_type, 'local_estimate');
assert.strictEqual(saved[0].cost_authority, 'local_rate_table');
assert.strictEqual(saved[0].usage_authority, 'provider_response');
assert.strictEqual(saved[0].provider_billing_status, 'unavailable');
assert.strictEqual(saved[0].provider_authoritative_cost_usd, null);
assert.strictEqual(saved[0].reconciliation_status, 'provider_billing_unavailable');

assert.ok(html.includes('Estimated AI API token cost only'));
assert.ok(html.includes('missing provider billing remains explicitly unreconciled'));
assert.ok(html.includes('Created before v24.6.215; historical cost is preserved but token/call/cache details cannot be reconstructed.'));

console.log('Phase 5B frontend AI cost fixtures passed');
