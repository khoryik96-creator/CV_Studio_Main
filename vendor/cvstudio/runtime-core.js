// ── /extract-text client budget ───────────────────────────────────────
// MUST stay above the server's OCR ceiling (OCR_TOTAL_DEADLINE_SECONDS = 180s
// plus the maximum 45s render + 35s OCR operation already in flight). A scanned
// upload can legitimately occupy the server for that long, and aborting it does
// NOT stop the work: the server keeps OCRing and holds the single OCR
// semaphore, so a client that gives up early both loses a good extraction and
// makes the NEXT upload fail with "OCR is already processing another
// document". Every /extract-text call site uses this one budget so the two
// sides cannot drift apart again.
var CV_EXTRACT_TEXT_TIMEOUT_MS = 300000;

// ── Global fetch helper — available to ALL functions ─────────────────
async function fetchWithTimeout(url, options, timeoutMs) {
  timeoutMs = timeoutMs || 120000; // 2 min default
  var controller = new AbortController();
  var timer = setTimeout(function() { controller.abort(); }, timeoutMs);
  try {
    var r = await fetch(url, Object.assign({}, options, { signal: controller.signal }));
    clearTimeout(timer);
    return r;
  } catch(err) {
    clearTimeout(timer);
    if (err.name === 'AbortError') throw new Error('Request timed out after ' + (timeoutMs/1000) + 's — the server may be busy or unresponsive. Try again or relaunch CV Studio.');
    if (err.message && err.message.toLowerCase().includes('failed to fetch')) throw new Error('Cannot reach the local server. Please relaunch CV Studio and try again.\n\nIf this keeps happening, check that nothing else is using port 5000.');
    throw err;
  }
}

function cvParseIsLong(cvText) {
  var text = String(cvText || '');
  var markers = text.match(/^\s*(?:[ivxlcdm]+[.)]\s*)?(?:key\s+)?(?:responsibilit(?:y|ies)|achievements?)\s*:?\s*$/gim) || [];
  return text.length >= 8000 || markers.length >= 8;
}

function cvParseTimeoutMs(cvText) {
  return cvParseIsLong(cvText) ? 330000 : 210000;
}

// Pricing per million tokens, USD — input / output
var MODEL_PRICING = {
  'claude-sonnet-5':           { in: 2.00,  out: 10.00 },  // intro pricing through Aug 31 2026
  'claude-sonnet-4-6':         { in: 3.00,  out: 15.00 },
  'claude-opus-4-8':           { in: 5.00,  out: 25.00 },
  'claude-opus-4-7':           { in: 5.00,  out: 25.00 },
  'claude-opus-4-6':           { in: 5.00,  out: 25.00 },
  'claude-sonnet-4-5':         { in: 3.00,  out: 15.00 },
  'claude-opus-4-5':           { in: 5.00,  out: 25.00 },
  'claude-haiku-4-5-20251001': { in: 1.00,  out: 5.00  },
  'deepseek-v4-flash':         { in: 0.14,  out: 0.28, cache_hit: 0.0028 },
  'deepseek-v4-pro':           { in: 0.435, out: 0.87, cache_hit: 0.003625 },
  'gpt-5.5':                   { in: 5.00,  out: 30.00 },
  'gpt-5.5-pro':               { in: 30.00, out: 180.00 },
  'gpt-5.4':                   { in: 2.50,  out: 15.00 },
  'gpt-5.4-mini':              { in: 0.75,  out: 4.50  },
  'gpt-5.4-nano':              { in: 0.20,  out: 1.25  },
  'gpt-5.4-pro':               { in: 30.00, out: 180.00 }
};
function inferProviderFromModel(model, provider) {
  var key = String(model || '').trim().toLowerCase();
  // Historical OneNote records sometimes retained a stale Claude provider even
  // though the model was deterministic. Model semantics are authoritative here.
  if (key.indexOf('local') === 0 || key.indexOf('deterministic') === 0) return 'local';
  provider = String(provider || '').trim().toLowerCase();
  if (provider === 'local') return 'local';
  if (provider === 'none') return 'none';
  if (provider === 'anthropic' || provider === 'claude' || provider === 'deepseek' || provider === 'openai' || provider === 'gpt') {
    return provider === 'claude' ? 'anthropic' : (provider === 'gpt' ? 'openai' : provider);
  }
  if (key.indexOf('deepseek') === 0) return 'deepseek';
  if (key.indexOf('gpt-') === 0 || key.indexOf('o1') === 0 || key.indexOf('o3') === 0 || key.indexOf('o4') === 0) return 'openai';
  return 'anthropic';
}
function providerLabel(provider, model) {
  provider = inferProviderFromModel(model, provider);
  if (provider === 'local') return 'Local';
  if (provider === 'none') return 'No AI';
  if (provider === 'deepseek') return 'DeepSeek';
  if (provider === 'openai') return 'OpenAI';
  return 'Claude';
}

function aiProviderDownMessage(rawMessage, route) {
  var raw = String(rawMessage || '').trim();
  var low = raw.toLowerCase();
  var provider = providerLabel((route && route.provider) || '', (route && route.model) || '');
  // Do not label user/configuration mistakes as provider outage.
  if (/invalid api key|api key required|authentication|unauthorized|forbidden|permission|credit|quota|billing|insufficient|model.*not|unsupported|bad request/i.test(low)) return '';
  var looksDown = /(timed?\s*out|timeout|temporar(?:y|ily)|unavailable|overloaded|overload|server error|bad gateway|gateway|service unavailable|connection reset|connection aborted|connection refused|network|upstream|rate limit|too many requests|429|500|502|503|504|529)/i.test(low);
  if (!looksDown) return '';
  return provider + ' appears down, overloaded, or temporarily unreachable. Try again shortly or switch provider in Settings.';
}
function normalizeAiProviderError(rawMessage, route) {
  var raw = String(rawMessage || 'Unknown API error').trim();
  var down = aiProviderDownMessage(raw, route);
  if (down) return down + (raw ? '\n\nDetails: ' + raw : '');
  return raw;
}
function showAiProviderError(rawMessage, route) {
  var msg = normalizeAiProviderError(rawMessage, route);
  var first = msg.split('\n')[0];
  showToast(first, 'err');
  return msg;
}
function providerDownAlertHtml(message) {
  return '<div class="provider-down-alert">' + esc(String(message || 'AI provider appears unavailable.')) + '</div>';
}
function pricingForModel(model, provider) {
  var key = String(model || '').trim().toLowerCase();
  if (MODEL_PRICING[key]) return { pricing: MODEL_PRICING[key], known: true, model_key: key };
  var p = inferProviderFromModel(model, provider);
  if (p === 'deepseek') return { pricing: MODEL_PRICING['deepseek-v4-flash'], known: false, model_key: 'deepseek-v4-flash' };
  if (p === 'openai') return { pricing: MODEL_PRICING['gpt-5.5'], known: false, model_key: 'gpt-5.5' };
  return { pricing: MODEL_PRICING['claude-sonnet-4-6'], known: false, model_key: 'claude-sonnet-4-6' };
}
function calcCost(model, inputTokens, outputTokens, provider) {
  var p = pricingForModel(model, provider).pricing;
  return (Number(inputTokens || 0) / 1e6) * p.in + (Number(outputTokens || 0) / 1e6) * p.out;
}
function normalizeUsageClient(usage) {
  usage = usage && typeof usage === 'object' ? usage : {};
  function n() {
    var fallback = 0;
    for (var i=0;i<arguments.length;i++) {
      var v = Number(usage[arguments[i]]);
      if (isFinite(v) && v >= 0) {
        v = Math.floor(v);
        if (v > 0) return v;
        fallback = v;
      }
    }
    return fallback;
  }
  var input = n('input_tokens','prompt_tokens');
  var output = n('output_tokens','completion_tokens');
  var hit = n('prompt_cache_hit_tokens','cache_read_input_tokens');
  var miss = n('prompt_cache_miss_tokens','cache_creation_input_tokens');
  if (!input && (hit || miss)) input = hit + miss;
  return {
    input_tokens: input,
    output_tokens: output,
    prompt_cache_hit_tokens: hit,
    prompt_cache_miss_tokens: miss,
    api_calls: n('api_calls')
  };
}
function mergeUsageClient() {
  var total = {input_tokens:0,output_tokens:0,prompt_cache_hit_tokens:0,prompt_cache_miss_tokens:0,api_calls:0};
  for (var i=0;i<arguments.length;i++) {
    var u = normalizeUsageClient(arguments[i]);
    Object.keys(total).forEach(function(k){ total[k] += Number(u[k] || 0); });
  }
  return total;
}
function costDetailsFromResponse(d, fallbackModel, fallbackProvider) {
  d = d && typeof d === 'object' ? d : {};
  var model = d.model || fallbackModel || '';
  var provider = inferProviderFromModel(model, d.provider || fallbackProvider || '');
  var supplied = d.cost_details && typeof d.cost_details === 'object' ? d.cost_details : null;
  if (supplied && isFinite(Number(supplied.usd))) {
    var copy = Object.assign({}, supplied);
    copy.usd = Number(copy.usd || 0);
    copy.input_tokens = Number(copy.input_tokens || 0);
    copy.output_tokens = Number(copy.output_tokens || 0);
    copy.prompt_cache_hit_tokens = Number(copy.prompt_cache_hit_tokens || 0);
    copy.prompt_cache_miss_tokens = Number(copy.prompt_cache_miss_tokens || 0);
    copy.api_calls = Number(copy.api_calls || 0);
    var suppliedCalled = !!(copy.api_calls || copy.input_tokens || copy.output_tokens || copy.prompt_cache_hit_tokens || copy.prompt_cache_miss_tokens);
    copy.model = copy.model || model;
    copy.provider = copy.provider || provider;
    if (!Object.prototype.hasOwnProperty.call(copy, 'estimated_cost_usd')) copy.estimated_cost_usd = copy.usd;
    if (!copy.cost_value_type) copy.cost_value_type = 'local_estimate';
    if (!copy.cost_authority) copy.cost_authority = 'local_rate_table';
    if (!copy.usage_authority) copy.usage_authority = copy.api_calls > 0 ? 'provider_response' : 'not_returned';
    if (!copy.provider_billing_status) copy.provider_billing_status = suppliedCalled ? 'unavailable' : 'not_applicable';
    if (!Object.prototype.hasOwnProperty.call(copy, 'provider_authoritative_cost_usd')) copy.provider_authoritative_cost_usd = null;
    if (!Object.prototype.hasOwnProperty.call(copy, 'provider_authoritative_cost_usd_text')) copy.provider_authoritative_cost_usd_text = copy.provider_authoritative_cost_usd === null ? null : String(copy.provider_authoritative_cost_usd);
    if (!Object.prototype.hasOwnProperty.call(copy, 'provider_authoritative_cost')) copy.provider_authoritative_cost = copy.provider_authoritative_cost_usd;
    if (!Object.prototype.hasOwnProperty.call(copy, 'provider_authoritative_cost_text')) copy.provider_authoritative_cost_text = copy.provider_authoritative_cost === null ? null : String(copy.provider_authoritative_cost);
    if (!Object.prototype.hasOwnProperty.call(copy, 'provider_authoritative_cost_currency')) copy.provider_authoritative_cost_currency = copy.provider_billing_currency || (copy.provider_authoritative_cost_usd === null ? null : 'USD');
    if (!copy.reconciliation_status) copy.reconciliation_status = suppliedCalled ? 'provider_billing_unavailable' : 'not_called';
    if (!Object.prototype.hasOwnProperty.call(copy, 'reconciliation_difference_usd')) copy.reconciliation_difference_usd = null;
    if (!Object.prototype.hasOwnProperty.call(copy, 'billing_data_missing')) copy.billing_data_missing = suppliedCalled;
    if (!Object.prototype.hasOwnProperty.call(copy, 'billing_data_invalid')) copy.billing_data_invalid = false;
    if (!copy.estimate_status) copy.estimate_status = suppliedCalled ? 'available' : 'not_applicable';
    if (!copy.usage_validation_status) copy.usage_validation_status = suppliedCalled ? 'valid' : 'not_applicable';
    if (!Object.prototype.hasOwnProperty.call(copy, 'usage_validation_reason')) copy.usage_validation_reason = null;
    return copy;
  }
  var usage = normalizeUsageClient(d.usage || {});
  var pInfo = pricingForModel(model, provider);
  var rates = pInfo.pricing;
  var usd = 0;
  var method = 'standard_input_output_tokens';
  if (provider === 'deepseek') {
    if (usage.prompt_cache_hit_tokens || usage.prompt_cache_miss_tokens) {
      var residualInput = Math.max(0, usage.input_tokens - usage.prompt_cache_hit_tokens - usage.prompt_cache_miss_tokens);
      usd = usage.prompt_cache_hit_tokens / 1e6 * Number(rates.cache_hit || 0)
        + (usage.prompt_cache_miss_tokens + residualInput) / 1e6 * rates.in
        + usage.output_tokens / 1e6 * rates.out;
      method = residualInput ? 'deepseek_cache_split_plus_unclassified_input_as_miss' : 'deepseek_returned_cache_hit_miss_tokens';
    } else {
      usd = usage.input_tokens / 1e6 * rates.in + usage.output_tokens / 1e6 * rates.out;
      method = 'deepseek_input_priced_as_cache_miss_no_split_returned';
    }
  } else {
    usd = usage.input_tokens / 1e6 * rates.in + usage.output_tokens / 1e6 * rates.out;
  }
  if (typeof d.cost === 'number' && isFinite(d.cost)) usd = Number(d.cost);
  var providerCalled = !!(usage.api_calls || usage.input_tokens || usage.output_tokens || usage.prompt_cache_hit_tokens || usage.prompt_cache_miss_tokens);
  return {
    input_tokens: usage.input_tokens,
    output_tokens: usage.output_tokens,
    total_tokens: usage.input_tokens + usage.output_tokens,
    prompt_cache_hit_tokens: usage.prompt_cache_hit_tokens,
    prompt_cache_miss_tokens: usage.prompt_cache_miss_tokens,
    api_calls: usage.api_calls,
    usd: usd,
    model: model,
    provider: provider,
    pricing_model_key: pInfo.model_key,
    pricing_known: pInfo.known,
    cost_method: method,
    estimated_cost_usd: usd,
    cost_value_type: 'local_estimate',
    cost_authority: 'local_rate_table',
    usage_authority: usage.api_calls > 0 ? 'provider_response' : 'not_returned',
    provider_billing_status: providerCalled ? 'unavailable' : 'not_applicable',
    provider_authoritative_cost_usd: null,
    provider_authoritative_cost_usd_text: null,
    provider_authoritative_cost: null,
    provider_authoritative_cost_text: null,
    provider_authoritative_cost_currency: null,
    provider_billing_currency: null,
    provider_billing_source: null,
    reconciliation_status: providerCalled ? 'provider_billing_unavailable' : 'not_called',
    reconciliation_difference_usd: null,
    billing_data_missing: providerCalled,
    billing_data_invalid: false,
    estimate_status: providerCalled ? 'available' : 'not_applicable',
    usage_validation_status: providerCalled ? 'valid' : 'not_applicable',
    usage_validation_reason: null
  };
}
function responseCost(d, fallbackModel, fallbackProvider) {
  return Number(costDetailsFromResponse(d, fallbackModel, fallbackProvider).usd || 0);
}
function statsMetaFromResponse(d, fallbackModel, fallbackProvider, extra) {
  var c = costDetailsFromResponse(d, fallbackModel, fallbackProvider);
  return Object.assign({
    input_tokens: Number(c.input_tokens || 0),
    output_tokens: Number(c.output_tokens || 0),
    cache_hit_tokens: Number(c.prompt_cache_hit_tokens || 0),
    cache_miss_tokens: Number(c.prompt_cache_miss_tokens || 0),
    api_calls: Number(c.api_calls || 0),
    pricing_model_key: c.pricing_model_key || '',
    pricing_known: c.pricing_known !== false,
    cost_method: c.cost_method || '',
    cost_note: c.note || '',
    cost_value_type: c.cost_value_type || 'local_estimate',
    cost_authority: c.cost_authority || 'local_rate_table',
    usage_authority: c.usage_authority || (Number(c.api_calls || 0) > 0 ? 'provider_response' : 'not_returned'),
    provider_billing_status: c.provider_billing_status || 'unavailable',
    provider_authoritative_cost_usd: Object.prototype.hasOwnProperty.call(c, 'provider_authoritative_cost_usd') ? c.provider_authoritative_cost_usd : null,
    provider_authoritative_cost_usd_text: c.provider_authoritative_cost_usd_text || null,
    provider_authoritative_cost: Object.prototype.hasOwnProperty.call(c, 'provider_authoritative_cost') ? c.provider_authoritative_cost : null,
    provider_authoritative_cost_text: c.provider_authoritative_cost_text || null,
    provider_authoritative_cost_currency: c.provider_authoritative_cost_currency || null,
    provider_billing_currency: c.provider_billing_currency || null,
    provider_billing_source: c.provider_billing_source || null,
    reconciliation_status: c.reconciliation_status || 'provider_billing_unavailable',
    reconciliation_difference_usd: Object.prototype.hasOwnProperty.call(c, 'reconciliation_difference_usd') ? c.reconciliation_difference_usd : null,
    billing_data_missing: c.billing_data_missing !== false,
    billing_data_invalid: c.billing_data_invalid === true,
    estimate_status: c.estimate_status || '',
    usage_validation_status: c.usage_validation_status || '',
    usage_validation_reason: c.usage_validation_reason || ''
  }, extra || {});
}
function responseHasPaidUsage(d) {
  if (!d || typeof d !== 'object') return false;
  var u = normalizeUsageClient(d.usage || {});
  return !!(Number(d.cost || 0) > 0 || u.input_tokens || u.output_tokens || u.api_calls || d.paid_ai_failure);
}
function recordPaidAiFailure(label, d, fallbackModel, fallbackProvider) {
  if (!responseHasPaidUsage(d) || d._costFailureRecorded) return '';
  d._costFailureRecorded = true;
  var details = costDetailsFromResponse(d, fallbackModel, fallbackProvider);
  return statsRecord(label || 'Paid AI output failed', 'ai_failed', details.usd, details.model || fallbackModel, '', details.provider || fallbackProvider,
    statsMetaFromResponse(d, fallbackModel, fallbackProvider, {outcome:'failed'}));
}
var _toastTimer, _parsedData = null, _timerInterval = null, _startTime = null;
var _runCost = 0; // accumulated USD cost for current run
var _runUsage = normalizeUsageClient({}); // aggregate all paid parse/blind calls, including repairs

function startTimer() {
  _startTime = Date.now();
  clearInterval(_timerInterval);
  _timerInterval = setInterval(function() {
    var elapsed = ((Date.now() - _startTime) / 1000).toFixed(1);
    document.getElementById('progressTimer').textContent = elapsed + 's';
  }, 100);
}

function stopTimer() {
  clearInterval(_timerInterval);
}

function setProgress(pct, label, step, totalSteps) {
  totalSteps = totalSteps || 3;
  document.getElementById('progressFill').style.width = pct + '%';
  document.getElementById('progressLabel').textContent = label;
  var stepIds = ['pstep1','pstep2','pstep3','pstep4'];
  stepIds.forEach(function(id, i) {
    var el = document.getElementById(id);
    if (i >= totalSteps) { el.style.display = 'none'; return; }
    el.style.display = 'flex';
    el.className = 'progress-step';
    if (i + 1 < step) el.classList.add('done');
    else if (i + 1 === step) el.classList.add('active');
  });
}

function showProgress() {
  document.getElementById('progressWrap').classList.add('on');
  document.getElementById('progressTimer').textContent = '0s';
  setProgress(0, 'Starting...', 1);
  startTimer();
}

function hideProgress() {
  stopTimer();
  document.getElementById('progressWrap').classList.remove('on');
}

function showToast(msg, type) {
  var el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast show ' + type;
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(function(){ el.classList.remove('show'); }, 3500);
}

function setDot(state) {
  document.getElementById('dot').className = 'dot' + (state==='ok'?' green':state==='err'?' red':'');
}
