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

const noCall = context.costDetailsFromResponse({
  model: 'claude-sonnet-4-6',
  provider: 'anthropic',
  usage: {},
}, '', '');
assert.strictEqual(noCall.provider_billing_status, 'not_applicable');
assert.strictEqual(noCall.reconciliation_status, 'not_called');
assert.strictEqual(noCall.billing_data_missing, false);

const missingUsage = context.costDetailsFromResponse({
  model: 'claude-sonnet-4-6',
  provider: 'anthropic',
  cost_details: {
    usd: 0,
    input_tokens: 0,
    output_tokens: 0,
    api_calls: 1,
    estimated_cost_usd: null,
    cost_value_type: 'local_estimate_unavailable',
    usage_authority: 'provider_response_missing',
    usage_validation_status: 'missing',
    estimate_status: 'usage_unavailable',
    provider_billing_status: 'unavailable',
    reconciliation_status: 'provider_billing_unavailable',
    billing_data_missing: true,
  },
}, '', '');
assert.strictEqual(missingUsage.estimated_cost_usd, null);
assert.strictEqual(missingUsage.cost_value_type, 'local_estimate_unavailable');
assert.strictEqual(missingUsage.usage_validation_status, 'missing');
assert.strictEqual(missingUsage.estimate_status, 'usage_unavailable');

const nonUsd = context.costDetailsFromResponse({
  model: 'gpt-5.4-mini',
  provider: 'openai',
  cost_details: {
    usd: 0.001,
    input_tokens: 10,
    output_tokens: 1,
    api_calls: 1,
    provider_billing_status: 'authoritative_non_usd',
    provider_authoritative_cost_usd: null,
    provider_authoritative_cost: 0,
    provider_authoritative_cost_currency: 'EUR',
    provider_billing_currency: 'EUR',
    provider_billing_source: 'provider_invoice',
    reconciliation_status: 'currency_conversion_unavailable',
    billing_data_missing: false,
  },
}, '', '');
const nonUsdMeta = context.statsMetaFromResponse(
  {model: 'gpt-5.4-mini', provider: 'openai', cost_details: nonUsd},
  '',
  '',
);
context.statsRecord('Non-USD', 'format', nonUsd.usd, 'gpt-5.4-mini', '', 'openai', nonUsdMeta);
assert.strictEqual(saved[0].provider_authoritative_cost, 0);
assert.strictEqual(saved[0].provider_billing_currency, 'EUR');
assert.strictEqual(saved[0].billing_data_invalid, false);

context.statsRecord('Malformed', 'format', 0.001, 'gpt-5.4-mini', '', 'openai', {
  provider_billing_status: 'authoritative',
  provider_authoritative_cost_usd: 'not-a-number',
  provider_billing_currency: 'USD',
  reconciliation_status: 'reconciled',
  billing_data_missing: false,
});
assert.strictEqual(saved[0].provider_billing_status, 'invalid');
assert.strictEqual(saved[0].provider_authoritative_cost_usd, null);
assert.strictEqual(saved[0].reconciliation_status, 'reconciliation_failed');
assert.strictEqual(saved[0].billing_data_invalid, true);

context.statsRecord('Delayed billing', 'format', 0.001, 'gpt-5.4-mini', '', 'openai', {
  provider_billing_status: 'delayed',
  reconciliation_status: 'provider_billing_delayed',
  billing_data_missing: true,
});
assert.strictEqual(saved[0].provider_billing_status, 'delayed');
assert.strictEqual(saved[0].reconciliation_status, 'provider_billing_delayed');
assert.strictEqual(saved[0].billing_data_missing, true);
assert.strictEqual(saved[0].billing_data_invalid, false);

context.statsRecord('Unsafe source', 'format', 0.001, 'gpt-5.4-mini', '', 'openai', {
  provider_billing_status: 'authoritative',
  provider_authoritative_cost_usd: 0.001,
  provider_authoritative_cost: 0.001,
  provider_authoritative_cost_currency: 'USD',
  provider_billing_currency: 'USD',
  provider_billing_source: 'account-secret-reference',
  reconciliation_status: 'reconciled',
  billing_data_missing: false,
});
assert.strictEqual(saved[0].provider_billing_source, null);
assert.strictEqual(saved[0].provider_billing_status, 'invalid');
assert.strictEqual(saved[0].reconciliation_status, 'reconciliation_failed');

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
