// ── Stats Tracking ────────────────────────────────────────────────────────────
var USD_TO_MYR = parseFloat(localStorage.getItem("cvs_myr_rate")) || 4.47;

function setMYRRate(val) {
  var v = parseFloat(val);
  if (!v || v < 1) return;
  USD_TO_MYR = v;
  localStorage.setItem("cvs_myr_rate", v.toFixed(2));
  renderStats();
}

// Load saved rate into input on page load
window.addEventListener("load", function() {
  var inp = document.getElementById("myrRateInput");
  if (inp) inp.value = USD_TO_MYR.toFixed(2);
});
var _statsFilter = 'week';
var _statsSqliteCache = null;
var _statsMutationVersion = 0;
var _statsClearVersion = 0;
var _statsHydrationPromise = null;
var _statsStorageWriteQueue = Promise.resolve();

function statsLegacyLoad() {
  try { return JSON.parse(localStorage.getItem('guo_lab_stats') || '[]'); } catch(e) { return []; }
}
function statsStableStorageValue(value) {
  if (Array.isArray(value)) return '[' + value.map(statsStableStorageValue).join(',') + ']';
  if (value && typeof value === 'object') {
    return '{' + Object.keys(value).sort().map(function(key){
      return JSON.stringify(key) + ':' + statsStableStorageValue(value[key]);
    }).join(',') + '}';
  }
  var encoded=JSON.stringify(value);
  return encoded===undefined ? 'null' : encoded;
}
function statsStorageRecordKey(record) {
  record = record && typeof record === 'object' ? record : {};
  if (record.id) return 'id:' + String(record.id);
  try { return 'legacy:' + statsStableStorageValue(record); } catch(e) { return 'legacy:' + String(record.ts || '') + '|' + String(record.name || '') + '|' + String(record.mode || ''); }
}
function statsChangedStorageKeys(beforeRecords, afterRecords) {
  var beforeValues = {}, changed = {};
  (Array.isArray(beforeRecords) ? beforeRecords : []).forEach(function(record){
    if (!record || typeof record !== 'object' || Array.isArray(record)) return;
    beforeValues[statsStorageRecordKey(record)] = statsStableStorageValue(record);
  });
  (Array.isArray(afterRecords) ? afterRecords : []).forEach(function(record){
    if (!record || typeof record !== 'object' || Array.isArray(record)) return;
    var key = statsStorageRecordKey(record);
    if (Object.prototype.hasOwnProperty.call(beforeValues, key)
        && beforeValues[key] !== statsStableStorageValue(record)) changed[key] = true;
  });
  return changed;
}
function statsMergeStorageRecords(sqliteRecords, legacyRecords, legacyConflictKeys) {
  var merged = [], positions = {};
  function add(record) {
    if (!record || typeof record !== 'object' || Array.isArray(record)) return;
    var key = statsStorageRecordKey(record);
    if (Object.prototype.hasOwnProperty.call(positions, key)) {
      if (legacyConflictKeys === true
          || (legacyConflictKeys && Object.prototype.hasOwnProperty.call(legacyConflictKeys, key))) {
        merged[positions[key]] = record;
      }
    }
    else { positions[key] = merged.length; merged.push(record); }
  }
  (Array.isArray(sqliteRecords) ? sqliteRecords : []).forEach(add);
  (Array.isArray(legacyRecords) ? legacyRecords : []).forEach(add);
  return merged;
}
function statsLegacySave(records) {
  try { localStorage.setItem('guo_lab_stats', JSON.stringify(records)); } catch(e) {}
}
function statsStoragePost(path, payload) {
  return fetch(path, {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(payload || {})
  }).then(function(response){
    return response.json().catch(function(){return {};}).then(function(data){
      if (!response.ok || !data.ok) throw new Error(data.message || data.error || 'Local storage request failed');
      return data;
    });
  });
}
function statsQueueStoragePost(path, payload) {
  _statsStorageWriteQueue = _statsStorageWriteQueue.catch(function(){}).then(function(){
    return statsStoragePost(path, payload);
  });
  return _statsStorageWriteQueue;
}
function statsLoad() {
  var records = Array.isArray(_statsSqliteCache) ? _statsSqliteCache : statsLegacyLoad();
  return Array.isArray(records) ? records.slice() : [];
}
function statsSave(records) {
  records = Array.isArray(records) ? records.slice() : [];
  _statsSqliteCache = records;
  _statsMutationVersion += 1;
  statsLegacySave(records);
  statsQueueStoragePost('/storage/usage-history/upsert', {records:records}).catch(function(){});
}
function statsHydrateFromSQLite() {
  if (_statsHydrationPromise) return _statsHydrationPromise;
  var startedVersion = _statsMutationVersion;
  var legacy = statsLegacyLoad();
  _statsHydrationPromise = statsStoragePost('/storage/usage-history/import', {records:legacy}).then(function(data){
    var currentLegacy = statsLegacyLoad();
    var clearedDuringHydration = _statsClearVersion > startedVersion;
    var mutatedDuringHydration = _statsMutationVersion !== startedVersion;
    var changedKeys = mutatedDuringHydration ? statsChangedStorageKeys(legacy, currentLegacy) : null;
    var merged = clearedDuringHydration ? currentLegacy : statsMergeStorageRecords(data.records, currentLegacy, changedKeys);
    _statsSqliteCache = merged;
    statsLegacySave(merged);
    if (clearedDuringHydration) {
      return statsQueueStoragePost('/storage/usage-history/clear', {}).catch(function(){}).then(function(){
        if (!merged.length) { renderStats(); return merged; }
        return statsQueueStoragePost('/storage/usage-history/upsert', {records:merged}).catch(function(){}).then(function(){renderStats();return merged;});
      });
    }
    if (_statsMutationVersion !== startedVersion) {
      return statsQueueStoragePost('/storage/usage-history/upsert', {records:merged}).catch(function(){}).then(function(){renderStats();return merged;});
    }
    renderStats();
    return merged;
  }).catch(function(){
    _statsSqliteCache = statsLegacyLoad();
    return _statsSqliteCache;
  });
  return _statsHydrationPromise;
}
window.addEventListener('load', function(){ setTimeout(statsHydrateFromSQLite, 0); });

function statsRecord(candidateName, mode, costUSD, model, jaUrl, provider, meta) {
  model = model || getModel();
  provider = inferProviderFromModel(model, provider || getProvider());
  meta = meta && typeof meta === 'object' ? meta : {};
  var records = statsLoad();
  var recordId = 'stat_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2,9);
  var authoritativeUsd = meta.provider_authoritative_cost_usd === null || meta.provider_authoritative_cost_usd === undefined ? null : Number(meta.provider_authoritative_cost_usd);
  var authoritativeNative = meta.provider_authoritative_cost === null || meta.provider_authoritative_cost === undefined ? null : Number(meta.provider_authoritative_cost);
  var reconciliationDifference = meta.reconciliation_difference_usd === null || meta.reconciliation_difference_usd === undefined ? null : Number(meta.reconciliation_difference_usd);
  if (!isFinite(authoritativeUsd)) authoritativeUsd = null;
  if (!isFinite(authoritativeNative)) authoritativeNative = null;
  if (!isFinite(reconciliationDifference)) reconciliationDifference = null;
  var billingCurrencyRaw = String(meta.provider_billing_currency || '').trim().toUpperCase().slice(0, 12);
  var billingCurrency = /^[A-Z]{3}$/.test(billingCurrencyRaw) ? billingCurrencyRaw : null;
  var nativeCurrencyRaw = String(meta.provider_authoritative_cost_currency || '').trim().toUpperCase().slice(0, 12);
  var nativeCurrency = /^[A-Z]{3}$/.test(nativeCurrencyRaw) ? nativeCurrencyRaw : null;
  var authoritativeUsdTextRaw = String(meta.provider_authoritative_cost_usd_text || '').trim().slice(0, 64);
  var authoritativeNativeTextRaw = String(meta.provider_authoritative_cost_text || '').trim().slice(0, 64);
  var decimalTextPattern = /^(?:0|[1-9][0-9]{0,29})(?:\.[0-9]{1,18})?$/;
  var authoritativeUsdText = decimalTextPattern.test(authoritativeUsdTextRaw) ? authoritativeUsdTextRaw : (authoritativeUsd === null ? null : String(authoritativeUsd));
  var authoritativeNativeText = decimalTextPattern.test(authoritativeNativeTextRaw) ? authoritativeNativeTextRaw : (authoritativeNative === null ? null : String(authoritativeNative));
  var billingSourceRaw = String(meta.provider_billing_source || '').trim().toLowerCase().slice(0, 160);
  var billingSourceParts = billingSourceRaw ? billingSourceRaw.split(',').map(function(value){ return value.trim(); }).filter(Boolean) : [];
  var allowedBillingSources = ['provider_cost_report', 'provider_invoice', 'provider_response'];
  var billingSource = billingSourceParts.length && billingSourceParts.every(function(value){ return allowedBillingSources.indexOf(value) >= 0; })
    ? billingSourceParts.sort().join(',')
    : null;
  var billingStatus = meta.provider_billing_status || 'unavailable';
  var authorityPresent = authoritativeUsd !== null || authoritativeNative !== null || authoritativeUsdText !== null || authoritativeNativeText !== null || billingCurrency !== null || nativeCurrency !== null || billingSource !== null;
  var authoritativeStatus = billingStatus === 'authoritative' || billingStatus === 'authoritative_non_usd';
  var billingInvalid = meta.billing_data_invalid === true
    || (authoritativeUsd !== null && authoritativeUsd < 0)
    || (authoritativeNative !== null && authoritativeNative < 0)
    || (!!billingCurrencyRaw && billingCurrency === null)
    || (!!nativeCurrencyRaw && nativeCurrency === null)
    || (!!authoritativeUsdTextRaw && !decimalTextPattern.test(authoritativeUsdTextRaw))
    || (!!authoritativeNativeTextRaw && !decimalTextPattern.test(authoritativeNativeTextRaw))
    || (!!billingSourceRaw && billingSource === null)
    || (!authoritativeStatus && authorityPresent)
    || (billingStatus === 'authoritative' && (authoritativeUsd === null || authoritativeUsdText === null || billingCurrency !== 'USD' || billingSource === null))
    || (billingStatus === 'authoritative_non_usd' && (authoritativeNative === null || authoritativeNativeText === null || billingCurrency === null || billingCurrency === 'USD' || billingSource === null))
    || (meta.reconciliation_status === 'reconciled' && reconciliationDifference === null)
    || (authoritativeStatus && meta.billing_data_missing === true);
  if (billingInvalid) billingStatus = 'invalid';
  records.push({
    id: recordId,
    ts: new Date().toISOString(),
    name: candidateName || 'Unknown',
    mode: mode,
    cost: Number(costUSD || 0),
    provider: provider,
    model: model,
    jaUrl: jaUrl || '',
    input_tokens: Number(meta.input_tokens || 0),
    output_tokens: Number(meta.output_tokens || 0),
    cache_hit_tokens: Number(meta.cache_hit_tokens || 0),
    cache_miss_tokens: Number(meta.cache_miss_tokens || 0),
    api_calls: Number(meta.api_calls || 0),
    pricing_model_key: meta.pricing_model_key || '',
    pricing_known: meta.pricing_known !== false,
    cost_method: meta.cost_method || '',
    cost_note: meta.cost_note || '',
    cost_value_type: meta.cost_value_type || 'local_estimate',
    cost_authority: meta.cost_authority || 'local_rate_table',
    usage_authority: meta.usage_authority || (Number(meta.api_calls || 0) > 0 ? 'provider_response' : 'not_returned'),
    provider_billing_status: billingStatus,
    provider_authoritative_cost_usd: authoritativeUsd,
    provider_authoritative_cost_usd_text: authoritativeUsdText,
    provider_authoritative_cost: authoritativeNative,
    provider_authoritative_cost_text: authoritativeNativeText,
    provider_authoritative_cost_currency: nativeCurrency,
    provider_billing_currency: billingCurrency,
    provider_billing_source: billingSource,
    reconciliation_status: billingInvalid ? 'reconciliation_failed' : (meta.reconciliation_status || 'provider_billing_unavailable'),
    reconciliation_difference_usd: reconciliationDifference,
    billing_data_missing: billingInvalid ? false : meta.billing_data_missing !== false,
    billing_data_invalid: billingInvalid,
    estimate_status: String(meta.estimate_status || '').slice(0, 80),
    usage_validation_status: String(meta.usage_validation_status || '').slice(0, 80),
    usage_validation_reason: String(meta.usage_validation_reason || '').slice(0, 160),
    outcome: meta.outcome || 'success'
  });
  statsSave(records);
  renderStats();
  return recordId;
}
function statsAttachJobAdderUrl(recordId, jaUrl, fallbackName, allowedModes) {
  jaUrl = String(jaUrl || '').trim();
  if (!jaUrl) return false;
  var records = statsLoad();
  var updated = false;
  if (recordId) {
    for (var i=records.length-1;i>=0;i--) {
      if (records[i].id === recordId) { records[i].jaUrl = jaUrl; updated = true; break; }
    }
  }
  if (!updated) {
    allowedModes = Array.isArray(allowedModes) && allowedModes.length ? allowedModes : ['format','blind'];
    for (var j=records.length-1;j>=0;j--) {
      if (allowedModes.indexOf(records[j].mode) < 0 || records[j].jaUrl) continue;
      if (!fallbackName || String(records[j].name || '').toLowerCase() === String(fallbackName || '').toLowerCase()) {
        records[j].jaUrl = jaUrl; updated = true; break;
      }
    }
  }
  if (updated) { statsSave(records); renderStats(); }
  return updated;
}

function setStatsFilter(filter) {
  _statsFilter = filter;
  document.querySelectorAll('.stats-filter-btn').forEach(function(b) {
    b.classList.toggle('active', b.textContent.toLowerCase().includes(
      filter === 'week' ? 'week' : filter === 'month' ? 'month' : 'all'
    ));
  });
  renderStats();
}

function filterRecords(records) {
  if (_statsFilter === 'all') return records;
  var now = new Date();
  return records.filter(function(r) {
    var d = new Date(r.ts);
    if (_statsFilter === 'week') {
      var weekAgo = new Date(now); weekAgo.setDate(now.getDate() - 7);
      return d >= weekAgo;
    } else {
      return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
    }
  });
}

function renderStats() {
  // Sync MYR rate input
  var rateInp = document.getElementById('myrRateInput');
  if (rateInp && !rateInp.matches(':focus')) rateInp.value = USD_TO_MYR.toFixed(2);
  var all = statsLoad();
  var records = filterRecords(all);

  var fmt   = records.filter(function(r){ return r.mode === 'format'; }).length;
  var blind = records.filter(function(r){ return r.mode === 'blind'; }).length;
  var total = records.length;
  var leadRecords = records.filter(function(r){ return r.mode === 'lead'; });
  var leadCostUSD = leadRecords.reduce(function(s, r){ return s + (r.cost || 0); }, 0);
  var costUSD = records.reduce(function(s, r){ return s + (r.cost || 0); }, 0);
  var costMYR = costUSD * USD_TO_MYR;

  document.getElementById('statsFmt').textContent   = fmt;
  document.getElementById('statsBlind').textContent  = blind;
  document.getElementById('statsTotal').textContent  = total;
  document.getElementById('statsCostUSD').textContent = '$' + costUSD.toFixed(4);
  document.getElementById('statsCostMYR').textContent = 'RM ' + costMYR.toFixed(2);
  var leadUsdEl = document.getElementById('statsLeadCostUSD'); if (leadUsdEl) leadUsdEl.textContent = leadCostLabel(leadCostUSD);
  var leadMyrEl = document.getElementById('statsLeadCostMYR'); if (leadMyrEl) leadMyrEl.textContent = leadMyrLabel(leadCostUSD) + ' · ' + leadRecords.length + ' run' + (leadRecords.length === 1 ? '' : 's');

  var tbody = document.getElementById('statsTableBody');
  var empty = document.getElementById('statsEmpty');
  var table = document.getElementById('statsTable');

  if (records.length === 0) {
    empty.style.display = 'block';
    table.style.display = 'none';
    return;
  }

  empty.style.display = 'none';
  table.style.display = 'table';

  // Show most recent first, max 50 rows
  var sorted = records.slice().reverse().slice(0, 50);
  tbody.innerHTML = sorted.map(function(r) {
    var d = new Date(r.ts);
    var dateStr = d.toLocaleDateString('en-MY', { day:'2-digit', month:'short', year:'numeric' });
    var timeStr = d.toLocaleTimeString('en-MY', { hour:'2-digit', minute:'2-digit' });
    var badge = r.mode === 'blind'   ? '<span class="stats-badge blind">Blind</span>'
           : r.mode === 'create'   ? '<span class="stats-badge" style="background:#e9d8fd;color:#553c9a;border-radius:20px;padding:1px 8px;font-size:11px;font-weight:500;">Create</span>'
           : r.mode === 'appraiser' ? '<span class="stats-badge" style="background:#eef2ff;color:#3730a3;border-radius:20px;padding:1px 8px;font-size:11px;font-weight:500;">CV Scoring</span>'
           : r.mode === 'owl'      ? '<span class="stats-badge" style="background:#fff7ed;color:#9a3412;border-radius:20px;padding:1px 8px;font-size:11px;font-weight:500;">The Owl</span>'
           : r.mode === 'spider'   ? '<span class="stats-badge" style="background:#eef2ff;color:#3730a3;border-radius:20px;padding:1px 8px;font-size:11px;font-weight:500;">AI Crawler</span>'
           : r.mode === 'owl_chat_auto' ? '<span class="stats-badge" style="background:#ffedd5;color:#9a3412;border-radius:20px;padding:1px 8px;font-size:11px;font-weight:500;">Owl Chat</span>'
           : r.mode === 'owl_chat_context' ? '<span class="stats-badge" style="background:#ffedd5;color:#9a3412;border-radius:20px;padding:1px 8px;font-size:11px;font-weight:500;">Owl Context</span>'
           : r.mode === 'owl_chat_general' ? '<span class="stats-badge" style="background:#fef3c7;color:#92400e;border-radius:20px;padding:1px 8px;font-size:11px;font-weight:500;">Owl General</span>'
           : r.mode === 'jd'       ? '<span class="stats-badge" style="background:#fff3cd;color:#856404;border-radius:20px;padding:1px 8px;font-size:11px;font-weight:500;">Blind JD</span>'
           : r.mode === 'company'  ? '<span class="stats-badge" style="background:#d1ecf1;color:#0c5460;border-radius:20px;padding:1px 8px;font-size:11px;font-weight:500;">Company</span>'
           : r.mode === 'summary'  ? '<span class="stats-badge" style="background:#e6fffa;color:#285e61;border-radius:20px;padding:1px 8px;font-size:11px;font-weight:500;">CV Summary</span>'
           : r.mode === 'onenote_activity' ? '<span class="stats-badge" style="background:#dcfce7;color:#166534;border-radius:20px;padding:1px 8px;font-size:11px;font-weight:500;">OneNote Activity</span>'
           : r.mode === 'onenote_salary_failed' ? '<span class="stats-badge" style="background:#fee2e2;color:#991b1b;border-radius:20px;padding:1px 8px;font-size:11px;font-weight:500;">OneNote Salary Failed</span>'
           : r.mode === 'provider_test' ? '<span class="stats-badge" style="background:#e0f2fe;color:#075985;border-radius:20px;padding:1px 8px;font-size:11px;font-weight:500;">Provider Test</span>'
           : r.mode === 'ai_failed' ? '<span class="stats-badge" style="background:#fee2e2;color:#991b1b;border-radius:20px;padding:1px 8px;font-size:11px;font-weight:500;">Paid AI Failed</span>'
           : r.mode === 'lead'     ? '<span class="stats-badge lead">Lead</span>'
           : '<span class="stats-badge format">Format</span>';
    var estimateUnavailable = r.estimate_status === 'usage_unavailable' || r.estimate_status === 'usage_invalid';
    var costStr = estimateUnavailable ? 'n/a' : (!r.cost ? '$0.0000' : (r.cost < 0.0001 ? '<$0.0001' : '$' + r.cost.toFixed(4)));
    var recProvider = inferProviderFromModel(r.model, r.provider);
    var providerShort = providerLabel(recProvider, r.model);
    var modelShort = recProvider === 'local' ? 'deterministic-salary-v1' : ((r.model || '').replace('claude-','').split('-20')[0] || 'unknown-model');
    var providerModel = providerShort + ' · ' + modelShort;
    var myrStr = estimateUnavailable ? 'n/a' : (r.cost ? 'RM ' + (r.cost * USD_TO_MYR).toFixed(3) : 'RM 0.000');
    var hasTokenAudit = Object.prototype.hasOwnProperty.call(r, 'input_tokens') || Object.prototype.hasOwnProperty.call(r, 'output_tokens') || Object.prototype.hasOwnProperty.call(r, 'api_calls');
    var inputTokens = Number(r.input_tokens || 0), outputTokens = Number(r.output_tokens || 0), calls = Number(r.api_calls || 0);
    var tokenText = hasTokenAudit
      ? ((inputTokens + outputTokens).toLocaleString() + ' tok' + (calls ? ' · ' + calls + ' call' + (calls === 1 ? '' : 's') : ''))
      : ((r.cost || 0) > 0 ? 'Legacy · n/a' : 'Legacy record');
    var tokenTitle = hasTokenAudit
      ? ('Input: ' + inputTokens.toLocaleString() + ' | Output: ' + outputTokens.toLocaleString()
        + ' | Cache hit: ' + Number(r.cache_hit_tokens || 0).toLocaleString() + ' | Cache miss: ' + Number(r.cache_miss_tokens || 0).toLocaleString()
        + (r.cost_method ? ' | Method: ' + r.cost_method : '')
        + ' | Cost: ' + (r.cost_value_type || 'local_estimate')
        + ' | Billing: ' + (r.reconciliation_status || 'provider_billing_unavailable')
        + (r.outcome === 'failed' ? ' | Outcome: failed after paid API response' : ''))
      : 'Created before v24.6.215; historical cost is preserved but token/call/cache details cannot be reconstructed.';
    return '<tr>'
      + '<td>' + dateStr + ' ' + timeStr + '</td>'
      + '<td>' + (r.jaUrl ? '<a href="' + escAttr(r.jaUrl) + '" target="_blank" rel="noopener noreferrer" style="color:var(--accent);text-decoration:none;font-weight:500;" title="View in JobAdder">' + esc(r.name) + ' ↗</a>' : esc(r.name)) + '</td>'
      + '<td>' + badge + '</td>'
      + '<td>' + costStr + '</td>'
      + '<td style="color:var(--text2);font-size:12px;font-family:monospace;">' + myrStr + '</td>'
      + '<td style="color:var(--text2);font-size:11px;font-family:monospace;" title="' + escAttr(tokenTitle) + '">' + esc(tokenText) + '</td>'
      + '<td style="color:var(--text3);font-size:11px" title="' + esc(r.model || '') + '">' + esc(providerModel) + '</td>'
      + '</tr>';
  }).join('');
}

function exportStatsExcel() {
  var records = filterRecords(statsLoad());
  if (records.length === 0) { showToast('No data to export for this period', 'err'); return; }

  var filterLabel = _statsFilter === 'week' ? 'This Week' : _statsFilter === 'month' ? 'This Month' : 'All Time';
  var USD_MYR = USD_TO_MYR;

  // Build CSV rows
  var rows = [
    ['The 郭 Lab — Usage & Estimated Cost Report'],
    ['Period:', filterLabel],
    ['Exported:', new Date().toLocaleString('en-MY')],
    [],
    ['Date', 'Time', 'Item', 'Mode', 'Outcome', 'Input Tokens', 'Output Tokens', 'Cache Hit Tokens', 'Cache Miss Tokens', 'API Calls', 'Cost Method', 'Estimate Status', 'Usage Validation', 'Estimate (USD)', 'Estimate (MYR)', 'Cost Authority', 'Usage Authority', 'Billing Status', 'Authoritative Cost (USD)', 'Authoritative Cost (Native)', 'Billing Currency', 'Billing Source', 'Reconciliation Status', 'Difference (USD)', 'Billing Data Invalid', 'Provider', 'Model'],
  ];

  records.slice().reverse().forEach(function(r) {
    var d = new Date(r.ts);
    rows.push([
      d.toLocaleDateString('en-MY', { day: '2-digit', month: 'short', year: 'numeric' }),
      d.toLocaleTimeString('en-MY', { hour: '2-digit', minute: '2-digit' }),
      r.name || 'Unknown',
      r.mode === 'blind' ? 'Blind' : r.mode === 'create' ? 'Create' : r.mode === 'appraiser' ? 'CV Scoring' : r.mode === 'owl' ? 'The Owl' : r.mode === 'spider' ? 'AI Crawler' : r.mode === 'owl_chat_auto' ? 'The Owl Chat' : r.mode === 'owl_chat_context' ? 'The Owl Chat - Context' : r.mode === 'owl_chat_general' ? 'The Owl Chat - General' : r.mode === 'jd' ? 'Blind JD' : r.mode === 'company' ? 'Company Profile' : r.mode === 'summary' ? 'CV Summary' : r.mode === 'onenote_activity' ? 'OneNote Activity' : r.mode === 'onenote_salary_failed' ? 'OneNote Salary Failed' : r.mode === 'provider_test' ? 'Provider Test' : r.mode === 'ai_failed' ? 'Paid AI Failed' : r.mode === 'lead' ? 'Lead Finder' : 'Format',
      r.outcome || 'success',
      Object.prototype.hasOwnProperty.call(r, 'input_tokens') ? Number(r.input_tokens || 0) : '',
      Object.prototype.hasOwnProperty.call(r, 'output_tokens') ? Number(r.output_tokens || 0) : '',
      Object.prototype.hasOwnProperty.call(r, 'cache_hit_tokens') ? Number(r.cache_hit_tokens || 0) : '',
      Object.prototype.hasOwnProperty.call(r, 'cache_miss_tokens') ? Number(r.cache_miss_tokens || 0) : '',
      Object.prototype.hasOwnProperty.call(r, 'api_calls') ? Number(r.api_calls || 0) : '',
      r.cost_method || (Object.prototype.hasOwnProperty.call(r, 'input_tokens') ? '' : 'legacy_cost_only'),
      r.estimate_status || '',
      r.usage_validation_status || '',
      r.estimate_status === 'usage_unavailable' || r.estimate_status === 'usage_invalid' ? '' : (r.cost ? r.cost.toFixed(6) : '0'),
      r.estimate_status === 'usage_unavailable' || r.estimate_status === 'usage_invalid' ? '' : (r.cost ? (r.cost * USD_MYR).toFixed(4) : '0'),
      r.cost_authority || (Object.prototype.hasOwnProperty.call(r, 'input_tokens') ? 'local_rate_table' : 'legacy_stored_value'),
      r.usage_authority || '',
      r.provider_billing_status || 'unavailable',
      r.provider_authoritative_cost_usd_text || (r.provider_authoritative_cost_usd === null || r.provider_authoritative_cost_usd === undefined ? '' : Number(r.provider_authoritative_cost_usd).toFixed(6)),
      r.provider_authoritative_cost_text || (r.provider_authoritative_cost === null || r.provider_authoritative_cost === undefined ? '' : Number(r.provider_authoritative_cost).toFixed(6)),
      r.provider_billing_currency || r.provider_authoritative_cost_currency || '',
      r.provider_billing_source || '',
      r.reconciliation_status || 'provider_billing_unavailable',
      r.reconciliation_difference_usd === null || r.reconciliation_difference_usd === undefined ? '' : Number(r.reconciliation_difference_usd).toFixed(6),
      r.billing_data_invalid === true ? 'yes' : 'no',
      providerLabel(r.provider, r.model),
      (r.model || '').replace('claude-', ''),
    ]);
  });

  // Summary rows
  var totalUSD = records.reduce(function(s, r) { return s + (r.cost || 0); }, 0);
  var fmtCount = records.filter(function(r) { return r.mode === 'format'; }).length;
  var blindCount = records.filter(function(r) { return r.mode === 'blind'; }).length;
  rows.push([]);
  rows.push(['SUMMARY']);
  rows.push(['Total CVs Formatted', fmtCount]);
  rows.push(['Total CVs Blinded', blindCount]);
  var leadExportRecords = records.filter(function(r) { return r.mode === 'lead'; });
  var leadExportUSD = leadExportRecords.reduce(function(s, r) { return s + (r.cost || 0); }, 0);
  rows.push(['Total Lead Finder Runs', leadExportRecords.length]);
  rows.push(['Total Lead Finder Estimate (USD)', '$' + leadExportUSD.toFixed(6)]);
  rows.push(['Total Lead Finder Estimate (MYR)', 'RM ' + (leadExportUSD * USD_MYR).toFixed(4)]);
  var owlExportRecords = records.filter(function(r) { return r.mode === 'owl'; });
  var owlExportUSD = owlExportRecords.reduce(function(s, r) { return s + (r.cost || 0); }, 0);
  rows.push(['Total The Owl Runs', owlExportRecords.length]);
  rows.push(['Total The Owl Estimate (USD)', '$' + owlExportUSD.toFixed(6)]);
  rows.push(['Total The Owl Estimate (MYR)', 'RM ' + (owlExportUSD * USD_MYR).toFixed(4)]);
  var owlChatExportRecords = records.filter(function(r) { return r.mode === 'owl_chat_auto' || r.mode === 'owl_chat_context' || r.mode === 'owl_chat_general'; });
  var owlChatExportUSD = owlChatExportRecords.reduce(function(s, r) { return s + (r.cost || 0); }, 0);
  rows.push(['Total The Owl Chat Messages', owlChatExportRecords.length]);
  rows.push(['Total The Owl Chat Estimate (USD)', '$' + owlChatExportUSD.toFixed(6)]);
  rows.push(['Total The Owl Chat Estimate (MYR)', 'RM ' + (owlChatExportUSD * USD_MYR).toFixed(4)]);
  rows.push(['Total Runs', records.length]);
  rows.push(['Total Estimate (USD)', '$' + totalUSD.toFixed(6)]);
  rows.push(['Total Estimate (MYR)', 'RM ' + (totalUSD * USD_MYR).toFixed(4)]);

  // Convert to CSV string
  var csv = rows.map(function(row) {
    return row.map(function(cell) {
      var s = String(cell === undefined || cell === null ? '' : cell);
      // Wrap in quotes if contains comma, newline or quote
      if (s.includes(',') || s.includes('\n') || s.includes('"')) {
        s = '"' + s.replace(/"/g, '""') + '"';
      }
      return s;
    }).join(',');
  }).join('\r\n');

  // Add BOM for Excel UTF-8 compatibility (handles Chinese characters etc.)
  var blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  var fname = 'GUO_Lab_Report_' + filterLabel.replace(' ', '_') + '_' + new Date().toISOString().slice(0,10) + '.csv';
  var a = document.createElement('a');
  var objUrl = URL.createObjectURL(blob);
  a.href = objUrl;
  a.download = fname;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(function(){ URL.revokeObjectURL(objUrl); }, 1000);
  showToast('Exported ' + records.length + ' records to ' + fname, 'ok');
}

function clearStats() {
  if (!confirm('Clear all usage history? This cannot be undone.')) return;
  var previousRecords = statsLoad();
  _statsSqliteCache = [];
  _statsMutationVersion += 1;
  _statsClearVersion = _statsMutationVersion;
  var clearVersion = _statsMutationVersion;
  try { localStorage.removeItem('guo_lab_stats'); } catch(e) {}
  renderStats();
  var hydration = _statsHydrationPromise;
  return (hydration ? hydration.catch(function(){}) : Promise.resolve()).then(function(){
    return statsQueueStoragePost('/storage/usage-history/clear', {});
  }).then(function(){
    if (_statsMutationVersion !== clearVersion) {
      return statsQueueStoragePost('/storage/usage-history/upsert', {records:statsLoad()});
    }
  }).then(function(){
    showToast('History cleared', 'info');
    return true;
  }).catch(function(error){
    var restored = statsMergeStorageRecords(previousRecords, statsLoad(), true);
    _statsSqliteCache = restored;
    _statsMutationVersion += 1;
    statsLegacySave(restored);
    renderStats();
    showToast('History was not cleared. ' + String((error && error.message) || 'Local storage is unavailable.'), 'err');
    return false;
  });
}


try { updateSummaryLockUI(); } catch(e) {}
try { updateCvScoringLockUI(); } catch(e) {}
try { updateLeadFinderLockUI(); } catch(e) {}
try { updateAiCrawlerLockUI(); } catch(e) {}
window.addEventListener('load', function(){
  try { updateSummaryLockUI(); } catch(e) {}
  try { updateCvScoringLockUI(); } catch(e) {}
  try { updateLeadFinderLockUI(); } catch(e) {}
try { updateAiCrawlerLockUI(); } catch(e) {}
});
