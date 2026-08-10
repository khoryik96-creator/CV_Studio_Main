// ── OneNote → JobAdder Screening Call Notes ────────────────────────────────
var _oneNoteRows = [];
window._oneNoteJobAdderAccountSeq = 0;
var ONE_NOTE_RECORD_KEY = 'cv_studio_onenote_transfer_records_v1';
var ONE_NOTE_SALARY_AI_KEY = 'cv_studio_onenote_salary_ai_enabled_v1';
var ONE_NOTE_SPELLING_CORRECTION_KEY = 'cvstudio_onenote_spelling_correction_v1';
var _oneNoteRecordsSqliteCache = null;
var _oneNoteRecordsMutationVersion = 0;
var _oneNoteRecordsHydrationPromise = null;
var _oneNoteRecordsWriteQueue = Promise.resolve();
var _oneNoteRecordsLastWritePromise = Promise.resolve(true);
function oneNoteSpellingCorrectionEnabled() {
  var el = document.getElementById('settingsOneNoteSpellingCorrection');
  if (el) return !!el.checked;
  try {
    var saved = localStorage.getItem(ONE_NOTE_SPELLING_CORRECTION_KEY);
    return saved === null ? true : saved === '1';
  } catch(e) { return true; }
}
function oneNoteLoadSpellingCorrectionSetting() {
  var enabled = true;
  try {
    var saved = localStorage.getItem(ONE_NOTE_SPELLING_CORRECTION_KEY);
    enabled = saved === null ? true : saved === '1';
  } catch(e) {}
  var el = document.getElementById('settingsOneNoteSpellingCorrection');
  if (el) el.checked = enabled;
  return enabled;
}
function oneNoteSaveSpellingCorrectionSetting() {
  try { cvStudioDurableSettingSet(ONE_NOTE_SPELLING_CORRECTION_KEY, oneNoteSpellingCorrectionEnabled() ? '1' : '0'); } catch(e) {}
}
function oneNoteSalaryAiEnabled() {
  var el=document.getElementById('oneNoteSalaryAiEnabled');
  return el ? !!el.checked : true;
}
function oneNoteSalaryAiConfig() {
  var route=aiRoutePayload('onenote_salary');
  return {enabled:oneNoteSalaryAiEnabled(),provider:route.provider,model:route.model,api_key:route.api_key};
}
function oneNoteSaveSalaryAiSetting() {
  try { cvStudioDurableSettingSet(ONE_NOTE_SALARY_AI_KEY, oneNoteSalaryAiEnabled() ? '1' : '0'); } catch(e) {}
  oneNoteUpdateSalaryAiBadge();
}
function oneNoteUpdateSalaryAiBadge(canonical) {
  var route=resolveAiRoute('onenote_salary');
  var enabled=oneNoteSalaryAiEnabled();
  var keyPresent=!!(route && route.api_key);
  var routeBadge=document.getElementById('oneNoteSalaryAiRouteBadge');
  if (routeBadge) routeBadge.textContent=enabled ? ((route && route.display) || 'AI') : 'AI Off';
  var el=document.getElementById('oneNoteCostBadge');
  if (!el) return;
  var p=canonical && canonical.processing ? canonical.processing : null;
  if (p) {
    var provider=(p.aiUsed || p.aiApiCalled || Number(p.costUsd||0)>0) ? providerLabel(p.provider,p.model) : 'Local';
    var cache=p.cacheHit ? ' · cached' : '';
    var tokens=Number(p.inputTokens||0)+Number(p.outputTokens||0);
    var cs=(canonical&&canonical.currencySelection)||{}; var currencyText=cs.jobAdderOption ? (' · Currency: '+cs.jobAdderOption+(cs.selectionRule==='expected_salary_currency_wins'?' (expected wins)':'')) : '';
    el.textContent='Salary extraction: '+provider+((p.aiUsed || p.aiApiCalled) && p.model ? ' / '+p.model : '')+cache+(p.aiApiCalled && !p.aiUsed ? ' · AI result unusable; local fallback' : '')+' · Final calculation: deterministic code · '+tokens.toLocaleString()+' tokens · Cost $'+Number(p.costUsd||0).toFixed(4)+' / RM '+(Number(p.costUsd||0)*(typeof USD_TO_MYR==='number'?USD_TO_MYR:4.47)).toFixed(2)+currencyText+(p.fallbackReason?' · Fallback: '+p.fallbackReason:'');
  } else if (!enabled) {
    el.textContent='Salary extraction: Local deterministic parser · AI off · Cost $0.0000 / RM 0.00';
  } else if (!keyPresent) {
    el.textContent='Salary extraction: AI enabled but no saved key for '+((route&&route.provider_label)||'provider')+' · Local fallback · Cost $0.0000';
  } else {
    el.textContent='Salary extraction: '+((route&&route.display)||'AI')+' · Final calculation: deterministic code · Actual tokens/cost shown after transfer';
  }
}
window.addEventListener('load', function(){
  var el=document.getElementById('oneNoteSalaryAiEnabled');
  if (el) { try { var saved=localStorage.getItem(ONE_NOTE_SALARY_AI_KEY); el.checked=saved===null ? true : saved==='1'; } catch(e) {} }
  oneNoteLoadSpellingCorrectionSetting();
  oneNoteUpdateSalaryAiBadge();
});
// v24.6.80: only Presentability is blocking/mandatory. Other Screening Call
// text fields are transferred when found, but may remain blank if not supplied.
var ONE_NOTE_REQUIRED_FIELDS = [
  ['presentability_rating', 'Presentability rating 1-4']
];
var ONE_NOTE_FIELD_LABELS = {
  brief_overview: 'Brief Overview of Experience',
  reason_leaving: 'Reason For Leaving',
  looking_for: 'Looking for',
  current_salary_breakdown: 'Current Salary Breakdown',
  expected_salary: 'Expected Salary',
  notice_period: 'Notice Period',
  leads: 'Leads',
  remarks: 'Remarks',
  presentability_rating: 'Presentability'
};

function oneNoteNormalizeText(s) {
  var text = String(s || '').replace(/\r\n?/g, '\n');
  // Desktop OneNote can expose HTML-like fragments inside XML text nodes.
  // Normalize the common block tags here as a second safety net so pasted
  // import output containing <br /> still parses into proper candidate blocks.
  text = text.replace(/<br\s*\/?\s*>/gi, '\n');
  text = text.replace(/<\/?(?:div|p|li|tr|td|h[1-6]|ul|ol|table|section|article|blockquote)[^>]*>/gi, '\n');
  text = text.replace(/<[^>]+>/g, ' ');
  text = text.replace(/&nbsp;|&#160;/gi, ' ')
             .replace(/&amp;/gi, '&')
             .replace(/&lt;/gi, '<')
             .replace(/&gt;/gi, '>')
             .replace(/&quot;/gi, '"')
             .replace(/&#39;|&apos;/gi, "'");
  return text.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, ' ')
             .replace(/[ \t]+\n/g, '\n')
             .replace(/\n[ \t]+/g, '\n')
             .replace(/\n{3,}/g, '\n\n')
             .trim();
}
function oneNoteEmailOccurrences(text) {
  var rx = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/ig;
  var out = [], m;
  while ((m = rx.exec(String(text || ''))) !== null) {
    out.push({email:String(m[0] || '').toLowerCase(), index:m.index, end:rx.lastIndex});
  }
  return out;
}
function oneNoteEmails(text) {
  var out = [], seen = {};
  oneNoteEmailOccurrences(text).forEach(function(item){
    if (!seen[item.email]) { seen[item.email] = 1; out.push(item); }
  });
  return out;
}

// Imported OneNote pages are separated by a stable marker from the backend.
// Keep each page as its own review row so a page without an email still imports
// instead of being discarded or merged into the next candidate's notes.
function oneNoteSplitImportedPageBlocks(raw) {
  var text = String(raw || '');
  var rx = /^---\s*OneNote Page:\s*(.*?)\s*---\s*$/gmi;
  var marks = [], m;
  while ((m = rx.exec(text)) !== null) marks.push({title:String(m[1] || '').trim(), start:m.index, end:rx.lastIndex});
  if (!marks.length) return text.trim() ? [{title:'', text:text.trim()}] : [];
  var out = [];
  for (var i=0;i<marks.length;i++) {
    var body = text.slice(marks[i].end, i+1<marks.length ? marks[i+1].start : text.length).trim();
    // A selected OneNote page must still reach review even when Graph/COM only
    // supplied its title or the visible body consisted of spacing nodes.
    if (body || marks[i].title) out.push({title:marks[i].title, text:body || marks[i].title});
  }
  return out;
}
function oneNoteValidCandidateEmail(value) {
  return /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i.test(String(value || '').trim());
}

function jaActivityUrl(candidateId) {
  var memBase = window._jaWebBase;
  var lsBase  = (function(){ try { return localStorage.getItem('ja_web_base') || ''; } catch(e){ return ''; } })();
  if (lsBase === 'https://app.jobadder.com') lsBase = '';
  var base = (memBase && memBase !== 'https://app.jobadder.com') ? memBase
           : lsBase
           || 'https://app.jobadder.com';
  return base + '/candidates/' + candidateId + '?tab=2&activityView=Activity';
}
function oneNoteRecordsLegacyLoad() {
  try {
    var parsed = JSON.parse(localStorage.getItem(ONE_NOTE_RECORD_KEY) || '[]');
    return Array.isArray(parsed) ? parsed.map(function(item){return cvStudioPrivateSafeValue(item,0);}).filter(function(item){ return item && typeof item === 'object' && !Array.isArray(item); }).slice(0,200) : [];
  } catch(e) { return []; }
}
function oneNoteRecordStorageKey(record) {
  record=record&&typeof record==='object'?record:{};
  return record.id?('id:'+String(record.id)):('legacy:'+cvStudioStableStorageValue(record));
}
function oneNoteRecordChangedKeys(beforeRecords,afterRecords) {
  var before={},after={},changed={};
  (Array.isArray(beforeRecords)?beforeRecords:[]).forEach(function(record){before[oneNoteRecordStorageKey(record)]=cvStudioStableStorageValue(record);});
  (Array.isArray(afterRecords)?afterRecords:[]).forEach(function(record){after[oneNoteRecordStorageKey(record)]=cvStudioStableStorageValue(record);});
  Object.keys(before).concat(Object.keys(after)).forEach(function(key){if(!Object.prototype.hasOwnProperty.call(before,key)||!Object.prototype.hasOwnProperty.call(after,key)||before[key]!==after[key])changed[key]=true;});
  return changed;
}
function oneNoteMergeStorageRecords(sqliteRecords,currentRecords,changedKeys) {
  var merged=[],positions={},current={};
  (Array.isArray(sqliteRecords)?sqliteRecords:[]).forEach(function(record){var key=oneNoteRecordStorageKey(record);if(!Object.prototype.hasOwnProperty.call(positions,key)){positions[key]=merged.length;merged.push(record);}});
  (Array.isArray(currentRecords)?currentRecords:[]).forEach(function(record){current[oneNoteRecordStorageKey(record)]=record;});
  Object.keys(changedKeys||{}).forEach(function(key){var position=positions[key];if(Object.prototype.hasOwnProperty.call(current,key)){if(position===undefined){positions[key]=merged.length;merged.push(current[key]);}else merged[position]=current[key];}else if(position!==undefined){merged[position]=null;}});
  return merged.filter(function(record){return !!record;}).slice(0,200);
}
function oneNoteRecordUnion(primary,secondary) {
  var out=[],seen={};(Array.isArray(primary)?primary:[]).concat(Array.isArray(secondary)?secondary:[]).forEach(function(record){var key=oneNoteRecordStorageKey(record);if(!seen[key]){seen[key]=true;out.push(record);}});return out.slice(0,200);
}
function oneNoteRecordsMirrorSave(records) {
  try { localStorage.setItem(ONE_NOTE_RECORD_KEY, JSON.stringify(records||[])); } catch(e) {}
}
function oneNoteRecordsLoad() {
  var records=Array.isArray(_oneNoteRecordsSqliteCache)?_oneNoteRecordsSqliteCache:oneNoteRecordsLegacyLoad();
  return Array.isArray(records)?records.slice():[];
}
function oneNoteRecordsQueuePost(path,payload) {
  _oneNoteRecordsWriteQueue=_oneNoteRecordsWriteQueue.catch(function(){}).then(function(){return cvStudioStoragePost(path,payload);});
  return _oneNoteRecordsWriteQueue;
}
function oneNoteRecordsSave(records) {
  var safe=Array.isArray(records)?records.map(function(item){return cvStudioPrivateSafeValue(item,0);}).filter(function(item){return item&&typeof item==='object'&&!Array.isArray(item);}).slice(0,200):[];
  _oneNoteRecordsSqliteCache=safe;_oneNoteRecordsMutationVersion+=1;oneNoteRecordsMirrorSave(safe);
  _oneNoteRecordsLastWritePromise=oneNoteRecordsQueuePost('/storage/onenote-transfer-records/replace',{records:safe}).then(function(){return true;}).catch(function(error){showToast('OneNote record remains in this browser, but durable storage failed. '+String((error&&error.message)||''),'err');return false;});
  return true;
}
function oneNoteRecordsHydrateFromSQLite() {
  if(_oneNoteRecordsHydrationPromise)return _oneNoteRecordsHydrationPromise;
  var startedVersion=_oneNoteRecordsMutationVersion,legacy=oneNoteRecordsLegacyLoad();
  _oneNoteRecordsHydrationPromise=cvStudioStoragePost('/storage/onenote-transfer-records/import',{records:legacy}).then(function(data){
    var current=oneNoteRecordsLegacyLoad(),changed=_oneNoteRecordsMutationVersion!==startedVersion?oneNoteRecordChangedKeys(legacy,current):{},merged=oneNoteMergeStorageRecords(data.records,current,changed);
    _oneNoteRecordsSqliteCache=merged;oneNoteRecordsMirrorSave(merged);
    if(_oneNoteRecordsMutationVersion!==startedVersion)_oneNoteRecordsLastWritePromise=oneNoteRecordsQueuePost('/storage/onenote-transfer-records/replace',{records:merged}).then(function(){return true;}).catch(function(){return false;});
    try{oneNoteRenderRecords();oneNoteRefreshCost();}catch(e){}
    return merged;
  }).catch(function(){_oneNoteRecordsSqliteCache=oneNoteRecordsLegacyLoad();return _oneNoteRecordsSqliteCache;});
  return _oneNoteRecordsHydrationPromise;
}
window.addEventListener('load',function(){setTimeout(oneNoteRecordsHydrateFromSQLite,0);});
function oneNoteRecordTransfer(row, resp) {
  var url = (resp && resp.activity_url) || jaActivityUrl(row.candidate_id);
  var canon = (resp && resp.salary_canonical) || null;
  var proc = ((canon || {}).processing || {});
  var rec = {
    id: 'onr_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2,9),
    ts: new Date().toISOString(),
    name: (row.fields && row.fields.name) || row.matched_name || row.email || 'Candidate',
    email: row.email || '',
    candidate_id: row.candidate_id || '',
    url: url,
    mode: (resp && resp.mode) || 'candidate_activity',
    status: 'Transferred',
    salary_canonical: canon,
    ai_used: !!proc.aiUsed,
    ai_api_called: !!proc.aiApiCalled,
    ai_attempted: !!proc.aiAttempted,
    ai_provider: String(proc.provider || 'none'),
    ai_model: String(proc.model || 'none'),
    ai_cost_usd: Number(proc.costUsd || 0),
    processing_mode: String(proc.salaryCalculation || 'deterministic_code'),
    ai_event_key: 'success:' + String(row.candidate_id || '') + ':' + String((((canon||{}).validation||{}).salaryFingerprint) || '')
  };
  var records = oneNoteRecordsLoad();
  records.unshift(rec);
  oneNoteRecordsSave(records);
  oneNoteRenderRecords();
  var chargeableAi = rec.ai_used || rec.ai_api_called || rec.ai_cost_usd > 0;
  try { statsRecord(rec.name, 'onenote_activity', rec.ai_cost_usd || 0, chargeableAi ? (rec.ai_model || 'ai-salary-extraction') : 'deterministic-salary-v1', rec.url, chargeableAi ? (rec.ai_provider || 'deepseek') : 'local', {input_tokens:Number(proc.inputTokens||0),output_tokens:Number(proc.outputTokens||0),cache_hit_tokens:Number(proc.promptCacheHitTokens||0),cache_miss_tokens:Number(proc.promptCacheMissTokens||0),api_calls:Number(proc.apiCalls || (proc.aiApiCalled?1:0)),pricing_model_key:proc.pricingModelKey||'',pricing_known:proc.pricingKnown!==false,cost_method:proc.costMethod||'',cost_value_type:proc.costValueType||'local_estimate',cost_authority:proc.costAuthority||'local_rate_table',usage_authority:proc.usageAuthority||'',provider_billing_status:proc.providerBillingStatus||'not_applicable',provider_authoritative_cost_usd:proc.providerAuthoritativeCostUsd,provider_authoritative_cost_usd_text:proc.providerAuthoritativeCostUsdText,provider_authoritative_cost:proc.providerAuthoritativeCost,provider_authoritative_cost_text:proc.providerAuthoritativeCostText,provider_authoritative_cost_currency:proc.providerAuthoritativeCostCurrency,provider_billing_currency:proc.providerBillingCurrency,provider_billing_source:proc.providerBillingSource,reconciliation_status:proc.reconciliationStatus||'not_called',reconciliation_difference_usd:proc.reconciliationDifferenceUsd,billing_data_missing:proc.billingDataMissing===true,billing_data_invalid:proc.billingDataInvalid===true,estimate_status:proc.estimateStatus||'',usage_validation_status:proc.usageValidationStatus||'',usage_validation_reason:proc.usageValidationReason||'',outcome:'success'}); } catch(e) {}
  return rec;
}
function oneNoteRecordFailedAiCost(row, resp) {
  var canon = (resp && resp.salary_canonical) || row.salary_canonical || null;
  var proc = ((canon || {}).processing || {});
  var paidOrCalled = !!proc.aiApiCalled || Number(proc.costUsd || 0) > 0 || Number(proc.inputTokens || 0) > 0 || Number(proc.outputTokens || 0) > 0;
  if (!paidOrCalled) return null;
  var fingerprint = String((((canon||{}).validation||{}).salaryFingerprint) || 'no-fingerprint');
  var key = 'failed:' + String(row.candidate_id || '') + ':' + fingerprint + ':' + String(proc.provider || '') + ':' + String(proc.model || '') + ':' + String(proc.inputTokens || 0) + ':' + String(proc.outputTokens || 0) + ':' + Number(proc.costUsd || 0).toFixed(8);
  var records = oneNoteRecordsLoad();
  if (records.some(function(item){ return item && item.ai_event_key === key; })) return null;
  var rec = {
    id: 'onr_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2,9),
    ts: new Date().toISOString(),
    name: (row.fields && row.fields.name) || row.matched_name || row.email || 'Candidate',
    email: row.email || '',
    candidate_id: row.candidate_id || '',
    url: '',
    mode: 'salary_ai_failed',
    status: 'Failed after salary AI extraction',
    salary_canonical: canon,
    ai_used: !!proc.aiUsed,
    ai_api_called: !!proc.aiApiCalled,
    ai_attempted: !!proc.aiAttempted,
    ai_provider: String(proc.provider || 'none'),
    ai_model: String(proc.model || 'none'),
    ai_cost_usd: Number(proc.costUsd || 0),
    processing_mode: String(proc.salaryCalculation || 'deterministic_code'),
    ai_event_key: key
  };
  records.unshift(rec);
  oneNoteRecordsSave(records);
  oneNoteRenderRecords();
  try { statsRecord(rec.name, 'onenote_salary_failed', rec.ai_cost_usd || 0, rec.ai_model || 'salary-ai-extraction', '', rec.ai_provider || 'deepseek', {input_tokens:Number(proc.inputTokens||0),output_tokens:Number(proc.outputTokens||0),cache_hit_tokens:Number(proc.promptCacheHitTokens||0),cache_miss_tokens:Number(proc.promptCacheMissTokens||0),api_calls:Number(proc.apiCalls || (proc.aiApiCalled?1:0)),pricing_model_key:proc.pricingModelKey||'',pricing_known:proc.pricingKnown!==false,cost_method:proc.costMethod||'',cost_value_type:proc.costValueType||'local_estimate',cost_authority:proc.costAuthority||'local_rate_table',usage_authority:proc.usageAuthority||'',provider_billing_status:proc.providerBillingStatus||'unavailable',provider_authoritative_cost_usd:proc.providerAuthoritativeCostUsd,provider_authoritative_cost_usd_text:proc.providerAuthoritativeCostUsdText,provider_authoritative_cost:proc.providerAuthoritativeCost,provider_authoritative_cost_text:proc.providerAuthoritativeCostText,provider_authoritative_cost_currency:proc.providerAuthoritativeCostCurrency,provider_billing_currency:proc.providerBillingCurrency,provider_billing_source:proc.providerBillingSource,reconciliation_status:proc.reconciliationStatus||'provider_billing_unavailable',reconciliation_difference_usd:proc.reconciliationDifferenceUsd,billing_data_missing:proc.billingDataMissing!==false,billing_data_invalid:proc.billingDataInvalid===true,estimate_status:proc.estimateStatus||'',usage_validation_status:proc.usageValidationStatus||'',usage_validation_reason:proc.usageValidationReason||'',outcome:'failed'}); } catch(e) {}
  return rec;
}
function oneNoteRenderRecords() {
  var el = document.getElementById('oneNoteRecordList');
  if (!el) return;
  var records = oneNoteRecordsLoad();
  if (!records.length) {
    el.innerHTML = '<div class="onenote-muted" style="border:1px dashed var(--border);border-radius:12px;padding:14px;">No transfers recorded yet.</div>';
    return;
  }
  el.innerHTML = records.map(function(r){
    var d = new Date(r.ts || Date.now());
    var stamp = isNaN(d.getTime()) ? '-' : (d.toLocaleDateString('en-MY',{day:'2-digit',month:'short',year:'numeric'}) + ' ' + d.toLocaleTimeString('en-MY',{hour:'2-digit',minute:'2-digit'}));
    return '<div class="onenote-record-item">'
      + '<div class="onenote-record-head"><span>' + esc(r.name || r.email || 'Candidate') + '</span><span class="onenote-status ' + (String(r.status||'').indexOf('Failed')===0 ? 'err' : 'ok') + '">' + esc(r.status || 'Transferred') + '</span></div>'
      + '<div class="onenote-record-meta">' + esc(stamp) + (r.email ? ' · ' + esc(r.email) : '') + (r.candidate_id ? ' · ID ' + esc(r.candidate_id) : '') + '</div>'
      + (r.salary_canonical ? ('<div class="onenote-record-meta" style="margin-top:5px;line-height:1.45;">' + esc(((r.salary_canonical.current||{}).display || 'Current not updated') + ' · ' + ((r.salary_canonical.expected||{}).display || 'Expected not updated') + (((r.salary_canonical.notice||{}).display) ? (' · Notice: ' + (r.salary_canonical.notice||{}).display) : '')) + '</div>') : '')
      + (r.salary_canonical && (r.salary_canonical.currencySelection||{}).jobAdderOption ? ('<div class="onenote-record-meta" style="margin-top:4px;line-height:1.45;">' + esc('JobAdder Currency: ' + (r.salary_canonical.currencySelection||{}).jobAdderOption + ((r.salary_canonical.currencySelection||{}).selectionRule === 'expected_salary_currency_wins' ? ' · Expected Salary wins' : '')) + '</div>') : '')
      + '<div class="onenote-record-meta" style="margin-top:4px;line-height:1.45;">' + esc((r.ai_used ? ('AI extracted components: ' + (r.ai_provider || 'provider') + (r.ai_model && r.ai_model !== 'none' ? (' / ' + r.ai_model) : '')) : (r.ai_api_called || Number(r.ai_cost_usd||0)>0) ? ('AI attempted: ' + (r.ai_provider || 'provider') + ' · unusable result, local fallback') : 'AI: Not called · Local deterministic') + ' · Cost $' + Number(r.ai_cost_usd || 0).toFixed(4) + ' / RM ' + (Number(r.ai_cost_usd || 0) * (typeof USD_TO_MYR === 'number' ? USD_TO_MYR : 4.47)).toFixed(2)) + '</div>'
      + (r.url ? '<div style="margin-top:6px;"><a class="sec" href="' + escAttr(r.url) + '" target="_blank" rel="noopener" style="font-size:11px;text-decoration:none;">Open Activity ↗</a></div>' : '')
      + '</div>';
  }).join('');
}
function oneNoteClearRecords() {
  if (!window.confirm('Clear OneNote transfer record history from this browser?')) return;
  var previous=oneNoteRecordsLoad();
  _oneNoteRecordsSqliteCache=[];_oneNoteRecordsMutationVersion+=1;var clearVersion=_oneNoteRecordsMutationVersion;oneNoteRecordsMirrorSave([]);
  oneNoteRenderRecords();
  var hydration=_oneNoteRecordsHydrationPromise;
  return (hydration?hydration.catch(function(){}):Promise.resolve()).then(function(){return oneNoteRecordsQueuePost('/storage/onenote-transfer-records/clear',{});}).then(function(){
    if(_oneNoteRecordsMutationVersion!==clearVersion)return oneNoteRecordsQueuePost('/storage/onenote-transfer-records/replace',{records:oneNoteRecordsLoad()});
  }).then(function(){showToast('OneNote transfer record history cleared','info');return true;}).catch(function(error){
    var restored=oneNoteRecordUnion(oneNoteRecordsLoad(),previous);_oneNoteRecordsSqliteCache=restored;_oneNoteRecordsMutationVersion+=1;oneNoteRecordsMirrorSave(restored);oneNoteRenderRecords();showToast('OneNote transfer record history was not cleared. '+String((error&&error.message)||'Local storage is unavailable.'),'err');return false;
  });
}
function oneNoteSwitchMiniTab(which) {
  which = which === 'record' ? 'record' : 'console';
  var c = document.getElementById('oneNotePaneConsole');
  var r = document.getElementById('oneNotePaneRecord');
  var bc = document.getElementById('oneNoteMiniConsole');
  var br = document.getElementById('oneNoteMiniRecord');
  if (c) c.classList.toggle('active', which === 'console');
  if (r) r.classList.toggle('active', which === 'record');
  if (bc) bc.classList.toggle('active', which === 'console');
  if (br) br.classList.toggle('active', which === 'record');
  if (which === 'record') oneNoteRenderRecords();
}
function oneNoteShowSuccess(msg) {
  var el = document.getElementById('oneNoteSuccessBanner');
  if (!el) return;
  el.style.display = 'block';
  el.textContent = msg || 'Transferred successfully.';
  setTimeout(function(){ try { el.style.display = 'none'; } catch(e) {} }, 9000);
}
function oneNoteNearestBlock(raw, emailMatch, nextEmail, previousEmail) {
  raw = String(raw || '');
  var start = 0;

  if (previousEmail) {
    // The previous implementation searched from the beginning for every email.
    // On a page containing multiple candidates, candidate 2 therefore inherited
    // candidate 1's RFL/CS/ES fields.  The current email is the safest boundary.
    // Include at most one immediately preceding name-like line, never earlier
    // screening fields from the previous candidate.
    start = emailMatch.index;
    var beforeEmail = raw.slice(0, emailMatch.index).replace(/[ \t]+$/g, '');
    var linesBefore = beforeEmail.split('\n');
    var candidateLine = '';
    var candidateLineStart = -1;
    for (var li = linesBefore.length - 1; li >= 0; li--) {
      var trimmed = String(linesBefore[li] || '').trim();
      if (!trimmed) continue;
      candidateLine = trimmed;
      candidateLineStart = beforeEmail.lastIndexOf(linesBefore[li]);
      break;
    }
    var looksLikeName = candidateLine && candidateLine.length <= 80
      && candidateLine.indexOf('@') < 0
      && candidateLine.indexOf(':') < 0
      && !/\d/.test(candidateLine)
      && !oneNoteIsKnownFieldBoundary(candidateLine);
    if (looksLikeName && candidateLineStart >= previousEmail.end) start = candidateLineStart;
  } else {
    var before = raw.slice(0, emailMatch.index);
    var sep = Math.max(before.lastIndexOf('\n---'), before.lastIndexOf('\n==='), before.lastIndexOf('\nCandidate '), before.lastIndexOf('\nName:'), before.lastIndexOf('\nNAME:'));
    if (sep >= 0) start = sep + 1;
  }

  var end = nextEmail ? nextEmail.index : raw.length;
  if (nextEmail) {
    var between = raw.slice(emailMatch.end, nextEmail.index);
    var rel = Math.max(between.lastIndexOf('\n---'), between.lastIndexOf('\n==='), between.lastIndexOf('\nCandidate '), between.lastIndexOf('\nName:'), between.lastIndexOf('\nNAME:'));
    if (rel >= 0) end = emailMatch.end + rel;
  }

  var block = raw.slice(Math.max(0, start), Math.max(start, end)).trim();
  if (block.length < 20) block = raw.slice(emailMatch.index, Math.min(raw.length, emailMatch.end + 1600)).trim();
  return block;
}
function oneNoteLabelPattern(labels) {
  return labels.map(function(x){ return String(x).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }).join('|');
}
// v24.6.137: normalize common OneNote/Markdown heading decoration before
// matching labels. This keeps bullets, numbering, bold wrappers and hash-style
// headings from changing the meaning of the underlying screening field.
function oneNoteNormalizeLabelLine(line) {
  var s = String(line || '').replace(/[​-‍﻿]/g, '').replace(/ /g, ' ').trim();
  s = s.replace(/^\s*(?:[-•▪◦‣►]\s*|\*\s+|\d+[.)]\s*|[☐☑✓✔]\s*)/, '');
  s = s.replace(/^\s*#{1,6}\s*/, '').replace(/\s*#{1,6}\s*$/, '');
  for (var i=0;i<2;i++) {
    s = s.replace(/^\s*\*\*(.*?)\*\*(.*)$/, '$1$2');
    s = s.replace(/^\s*__(.*?)__(.*)$/, '$1$2');
    s = s.replace(/^\s*`([^`]+)`(.*)$/, '$1$2');
  }
  return s.replace(/[ 	]+/g, ' ').trim();
}

function oneNoteEditDistanceLimited(a, b, maxDistance) {
  a = String(a || ''); b = String(b || '');
  if (Math.abs(a.length - b.length) > maxDistance) return maxDistance + 1;
  var prev = [], cur = [];
  for (var j=0;j<=b.length;j++) prev[j]=j;
  for (var i=1;i<=a.length;i++) {
    cur[0]=i; var rowMin=cur[0];
    for (var k=1;k<=b.length;k++) {
      var cost = a.charAt(i-1) === b.charAt(k-1) ? 0 : 1;
      cur[k] = Math.min(cur[k-1]+1, prev[k]+1, prev[k-1]+cost);
      if (i>1 && k>1 && a.charAt(i-1)===b.charAt(k-2) && a.charAt(i-2)===b.charAt(k-1)) cur[k]=Math.min(cur[k], prev[k-2]+1);
      if (cur[k] < rowMin) rowMin=cur[k];
    }
    if (rowMin > maxDistance) return maxDistance + 1;
    var tmp=prev; prev=cur; cur=tmp;
  }
  return prev[b.length];
}
function oneNoteTypoKey(value) {
  return String(value || '').toLowerCase().replace(/\([^)]*\)/g, ' ').replace(/[^a-z0-9]+/g, ' ').replace(/\s+/g, ' ').trim();
}
function oneNoteFuzzyLabelLineParts(plain, labels) {
  if (!oneNoteSpellingCorrectionEnabled()) return null;
  plain = String(plain || '').trim();
  if (!plain || plain.length > 240 || plain.indexOf('@') >= 0) return null;
  var sep = plain.match(/^(.{3,100}?)(\s*(?:\?|[:：=]|=>|[-–—])\s*)(.*?)\s*$/);
  var prefix = sep ? String(sep[1] || '').trim() : plain;
  var value = sep ? String(sep[3] || '').trim() : '';
  var candidate = oneNoteTypoKey(prefix);
  if (!candidate || candidate.length < 4 || (!sep && candidate.split(' ').length > 6) || /\d/.test(candidate)) return null;
  var best = null;
  (labels || []).forEach(function(label){
    var target = oneNoteTypoKey(label);
    if (!target || target.length < 4) return;
    var longest = Math.max(candidate.length, target.length);
    var allowed = longest <= 6 ? 1 : (longest <= 13 ? 2 : 3);
    if (candidate.charAt(0) !== target.charAt(0) || Math.abs(candidate.length-target.length) > allowed) return;
    var distance = oneNoteEditDistanceLimited(candidate, target, allowed);
    if (distance <= allowed && distance / longest <= 0.24 && (!best || distance < best.distance || (distance === best.distance && target.length > best.target.length))) {
      best = {label:String(label).toLowerCase(), value:value, headingOnly:!value, corrected:true, originalLabel:prefix, distance:distance, target:target};
    }
  });
  return best;
}
var ONE_NOTE_RECRUITMENT_TYPO_ALIASES = {
  allwan:'allowance',alwan:'allowance',alwance:'allowance',alowance:'allowance',allowence:'allowance',
  allownce:'allowance',allownace:'allowance',allowanec:'allowance',allwance:'allowance',sllowance:'allowance',
  contrcat:'contract',contrct:'contract',conttract:'contract',contrat:'contract',conract:'contract',cotract:'contract',
  contrctual:'contractual',contractaul:'contractual',contractural:'contractual',
  permenant:'permanent',permanant:'permanent',permament:'permanent',permenent:'permanent',permnent:'permanent',
  permanet:'permanent',permanenet:'permanent',premanent:'permanent',
  expatrite:'expatriate',expatraite:'expatriate',expatriat:'expatriate',expartriate:'expatriate',
  expatirate:'expatriate',expatriete:'expatriate',
  loacl:'local',lcoal:'local',locla:'local',
  nationalty:'nationality',nationallity:'nationality',natinality:'nationality',nationlity:'nationality',
  sponsosrhip:'sponsorship',sponorship:'sponsorship',sponsorsip:'sponsorship',sponserhip:'sponsorship',
  sponsership:'sponsorship',sponsrship:'sponsorship',sponshorship:'sponsorship',sponsorhip:'sponsorship',
  citizneship:'citizenship',citizenhip:'citizenship',citizanship:'citizenship',citiznship:'citizenship',
  relocaiton:'relocation',relcoation:'relocation',relocaton:'relocation',
  employement:'employment',emplyoment:'employment',employmnt:'employment',
  salry:'salary',sallary:'salary',bonous:'bonus',bouns:'bonus',
  guaranted:'guaranteed',garanteed:'guaranteed',guaranteeed:'guaranteed',
  negotiabe:'negotiable',negotible:'negotiable',negtiable:'negotiable',
  availablity:'availability',availibility:'availability',avalability:'availability',
  enviroment:'environment',environement:'environment',experiance:'experience',experince:'experience',
  communcation:'communication',comunication:'communication',communicaiton:'communication',
  presntability:'presentability',presentabilty:'presentability',
  candiadte:'candidate',candiate:'candidate',residental:'residential',residnetial:'residential',
  viza:'visa',vissa:'visa',pemrit:'permit',permmit:'permit',stauts:'status',
  reomte:'remote',hybird:'hybrid',oniste:'onsite'
};
var ONE_NOTE_RECRUITMENT_FUZZY_TERMS = [
  'allowance','contract','contractual','permanent','expatriate','nationality','sponsorship','citizenship',
  'relocation','employment','guaranteed','negotiable','availability','environment','experience',
  'communication','presentability','candidate','residential'
];
var ONE_NOTE_RECRUITMENT_PROTECTED_WORDS = {
  allowance:1,allowances:1,contract:1,contracts:1,contracted:1,contracting:1,contractor:1,contractors:1,
  contractual:1,contractually:1,permanent:1,permanently:1,expatriate:1,expatriates:1,local:1,locals:1,
  nationality:1,nationalities:1,sponsorship:1,sponsorships:1,sponsor:1,sponsored:1,sponsoring:1,
  citizenship:1,citizenships:1,citizen:1,citizens:1,relocation:1,relocate:1,relocated:1,relocating:1,
  employment:1,employed:1,employer:1,employers:1,employee:1,employees:1,salary:1,salaries:1,bonus:1,bonuses:1,
  guaranteed:1,guarantee:1,guarantees:1,negotiable:1,availability:1,available:1,environment:1,environments:1,
  experience:1,experienced:1,experiences:1,communication:1,communications:1,presentability:1,candidate:1,candidates:1,
  residential:1,residence:1,visa:1,visas:1,permit:1,permits:1,status:1,remote:1,hybrid:1,onsite:1
};
function oneNoteCaseLike(original, corrected) {
  original = String(original || ''); corrected = String(corrected || '');
  if (original && original === original.toUpperCase()) return corrected.toUpperCase();
  if (/^[A-Z][a-z]+$/.test(original)) return corrected.charAt(0).toUpperCase() + corrected.slice(1);
  return corrected;
}
function oneNoteRecruitmentTypoTarget(token, allowFuzzy) {
  var lower = String(token || '').toLowerCase();
  if (!lower || ONE_NOTE_RECRUITMENT_PROTECTED_WORDS[lower]) return '';
  if (ONE_NOTE_RECRUITMENT_TYPO_ALIASES[lower]) return ONE_NOTE_RECRUITMENT_TYPO_ALIASES[lower];
  if (!allowFuzzy || lower.length < 8) return '';
  var best = null;
  ONE_NOTE_RECRUITMENT_FUZZY_TERMS.forEach(function(target){
    if (lower.charAt(0) !== target.charAt(0) || lower.charAt(lower.length-1) !== target.charAt(target.length-1)) return;
    if (Math.abs(lower.length - target.length) > 2) return;
    var allowed = Math.max(lower.length, target.length) >= 11 ? 2 : 1;
    var distance = oneNoteEditDistanceLimited(lower, target, allowed);
    if (distance <= allowed && distance / Math.max(lower.length, target.length) <= 0.20 && (!best || distance < best.distance)) {
      best = {target:target,distance:distance};
    }
  });
  return best ? best.target : '';
}
function oneNoteCorrectRecruitmentText(value, allowFuzzy) {
  var raw = String(value == null ? '' : value);
  if (!raw || !oneNoteSpellingCorrectionEnabled()) return {value:raw,changes:[]};
  var changes = [];
  var corrected = raw.replace(/[A-Za-z]+/g, function(token){
    var target = oneNoteRecruitmentTypoTarget(token, allowFuzzy !== false);
    if (!target || target.toLowerCase() === token.toLowerCase()) return token;
    var replacement = oneNoteCaseLike(token, target);
    if (changes.length < 12) changes.push(token + ' → ' + replacement);
    return replacement;
  });
  return {value:corrected,changes:changes};
}
function oneNoteApplyRecruitmentCorrections(fields) {
  fields = fields || {};
  if (!oneNoteSpellingCorrectionEnabled()) return fields;
  var corrections = Array.isArray(fields._spelling_corrections) ? fields._spelling_corrections.slice() : [];
  [
    ['brief_overview','Overview',false],['reason_leaving','RFL',true],['looking_for','Looking For',true],
    ['current_salary_breakdown','Current Salary',true],['expected_salary','Expected Salary',true],
    ['notice_period','Notice',true],['leads','Leads',true],['remarks','Remarks',true],['role','Role',true],
    ['location','Location',true],['red_flags','Red Flags',true],['next_steps','Next Steps',true],['raw_presentability','Presentability',true]
  ].forEach(function(spec){
    var key=spec[0], label=spec[1], before=String(fields[key] || '');
    if (!before) return;
    var result=oneNoteCorrectRecruitmentText(before, spec[2]);
    if (result.value !== before) fields[key]=result.value;
    result.changes.forEach(function(change){ if (corrections.length < 16) corrections.push(label + ': ' + change); });
  });
  if (corrections.length) fields._spelling_corrections = corrections;
  return fields;
}

function oneNoteCorrectNoticeValue(value) {
  var raw = String(value == null ? '' : value).trim();
  if (!raw || !oneNoteSpellingCorrectionEnabled()) return raw;
  if (/\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}\b/.test(raw) || /\b\d{1,2}[/-]\d{1,2}[/-]20\d{2}\b/.test(raw)) return raw;
  var lower = raw.toLowerCase().replace(/[–—]/g, '-').replace(/\s+/g, ' ').trim();
  var tokens = lower.match(/[a-z]+|\d+|[^a-z\d]+/g) || [];
  var immediateAliases = {imm:1,immed:1,imdt:1,immdiate:1,immedaite:1,imediate:1,immediatey:1,immediatly:1,immediatley:1,immediatelly:1,immidiately:1,immidiate:1};
  var monthAliases = {mth:'month',mths:'months',mnth:'month',mnths:'months',monht:'month',monhts:'months',monhth:'month',monhths:'months',moth:'month',moths:'months',mothn:'month',mothns:'months',monnth:'month',monnths:'months',monthh:'month',monthhs:'months',mnt:'month',mnts:'months',mo:'month',mos:'months'};
  var weekAliases = {wk:'week',wks:'weeks',wek:'week',weks:'weeks',weeek:'week',weeeks:'weeks'};
  var dayAliases = {dy:'day',dys:'days',daay:'day',daays:'days',dayz:'days'};
  var foundImmediate = false;
  tokens = tokens.map(function(tok){
    if (!/^[a-z]+$/.test(tok)) return tok;
    if (tok === 'immediate' || tok === 'immediately' || immediateAliases[tok]) { foundImmediate=true; return 'immediate'; }
    if (tok.length >= 7 && tok.length <= 12 && (oneNoteEditDistanceLimited(tok, 'immediate', 2) <= 2 || oneNoteEditDistanceLimited(tok, 'immediately', 2) <= 2)) { foundImmediate=true; return 'immediate'; }
    if (monthAliases[tok]) return monthAliases[tok];
    if (weekAliases[tok]) return weekAliases[tok];
    if (dayAliases[tok]) return dayAliases[tok];
    return tok;
  });
  var corrected = tokens.join('').replace(/\s+/g, ' ').trim();
  if (foundImmediate || /\b(?:available|availble|avalable)\s+now\b/.test(corrected)) return 'Immediate';
  if (/^(?:0|none|nil|n\/a)$/i.test(corrected)) return 'Immediate';
  var numberWords = {one:1,a:1,an:1,two:2,three:3,four:4,five:5,six:6};
  var wordMatch = corrected.match(/^(one|a|an|two|three|four|five|six)\s*(day|days|week|weeks|month|months)$/i);
  if (wordMatch) corrected = String(numberWords[wordMatch[1].toLowerCase()]) + ' ' + wordMatch[2].toLowerCase();
  var m = corrected.match(/^(\d+)\s*(day|days|week|weeks|month|months)$/i);
  if (m) {
    var n = Number(m[1]);
    var unit = m[2].toLowerCase();
    if (unit.indexOf('month') === 0) return n + ' month' + (n === 1 ? '' : 's');
    if (unit.indexOf('week') === 0) return n + ' week' + (n === 1 ? '' : 's');
    return n + ' day' + (n === 1 ? '' : 's');
  }
  if (/^\d+$/.test(corrected)) {
    var bare = Number(corrected);
    if (bare === 0) return 'Immediate';
    if (bare >= 1 && bare <= 12) return bare + ' month' + (bare === 1 ? '' : 's');
  }
  return corrected || raw;
}

var ONE_NOTE_OVERVIEW_LABELS = [
  'summary / brief overview of experience',
  'brief overview of experience / summary',
  'brief overview of experience',
  'brief overview / summary',
  'brief overview',
  'overview',
  'overview of experience',
  'experience overview',
  'brief experience overview',
  'work experience overview',
  'candidate overview',
  'profile overview',
  'professional overview',
  'career overview',
  'summary',
  'summary of experience',
  'experience summary',
  'work experience summary',
  'candidate summary',
  'profile summary',
  'professional summary',
  'career summary'
];
// Strong field boundaries used while collecting wrapped/multiline values.
// Include recruiter shorthands, but require an exact heading or a label
// separator so ordinary prose such as "current role" is not treated as a field.
var ONE_NOTE_FIELD_BOUNDARY_LABELS = ONE_NOTE_OVERVIEW_LABELS.concat([
  'reason for leaving / rfl','rfl / reason for leaving','reason for leaving','reason leaving','leaving reason','rfl',
  'looking for / lf','lf / looking for','looking for?','looking for','seeking','target role','preferred role','motivation','interest','lf',
  'current salary breakdown / cs','cs / current salary breakdown','current / last drawn / cs','current salary breakdown','current salary','last drawn salary','last drawn','current comp','current package','current basic','salary breakdown','current','cs',
  'expected salary / es','es / expected salary','expected / asking salary / es','expected salary','asking salary','salary expectation','expected package','expected basic','expected','es',
  'notice period / np','np / notice period','notice period / availability','notice period','notice','availability','available from','last day','np',
  'leads','lead','agency representation',
  'remarks','remark','things to take note','take note',
  'presentability (confidence, comms, business awareness)','presentability / communications','presentability','presentability rating','communications','communication','comms','confidence','business awareness',
  'email','candidate email','phone','mobile','contact','contact number','hp',
  'name','candidate name','cdd','cdd name',
  'role','position','job title','applied role',
  'location','current location','based in',
  'red flags','red flag','concerns','risk','risks',
  'next steps','next step','follow up','follow-up'
]);

function oneNoteLooksLikeInlineCandidateName(value) {
  var prefix = String(value || '').replace(/\s*[-–—|,:]\s*$/, '').trim();
  if (prefix.length < 2 || prefix.length > 80 || /[@:=?]/.test(prefix) || /\d/.test(prefix)) return '';
  var words = prefix.split(/\s+/).filter(Boolean);
  if (!words.length || words.length > 6) return '';
  if (/^(?:email|phone|mobile|current|expected|notice|salary|summary|overview|role|position|reason|rfl|looking|lf|cs|es|np|leads?|remarks?|presentability|communications?|comms|confidence|location|candidate|cdd)\b/i.test(prefix)) return '';
  var hasLetter = words.every(function(word){ return /[A-Za-zÀ-ÖØ-öø-ÿĀ-ɏ一-鿿]/.test(word); });
  return hasLetter ? prefix : '';
}
function oneNoteInlineNamedFieldParts(plain, labels) {
  plain = String(plain || '').trim();
  if (!plain || plain.length > 500 || plain.indexOf('@') >= 0) return null;
  var lower = plain.toLowerCase();
  var ordered = (labels || []).slice().sort(function(a,b){ return String(b).length - String(a).length; });
  for (var i=0;i<ordered.length;i++) {
    var label = String(ordered[i] || '').trim();
    if (!label) continue;
    var lowLabel = label.toLowerCase();
    var from = 1;
    while (from < lower.length) {
      var at = lower.indexOf(lowLabel, from);
      if (at < 0) break;
      from = at + Math.max(1, lowLabel.length);
      if (at <= 0 || !/[\s|–—-]/.test(lower.charAt(at - 1))) continue;
      var tail = plain.slice(at + label.length);
      var m = tail.match(/^\s*(?:\?|[:：=]|=>|[-–—])\s*(.*?)\s*$/);
      if (!m) continue;
      var inlineName = oneNoteLooksLikeInlineCandidateName(plain.slice(0, at));
      if (!inlineName) continue;
      var value = String(m[1] || '').trim();
      return {label:lowLabel,value:value,headingOnly:!value,inlineName:inlineName};
    }
  }
  return null;
}
function oneNoteLabelLineParts(line, labels) {
  var plain = oneNoteNormalizeLabelLine(line);
  if (!plain) return null;
  var lower = plain.toLowerCase();
  var ordered = (labels || []).slice().sort(function(a,b){ return String(b).length - String(a).length; });
  for (var i=0;i<ordered.length;i++) {
    var label = String(ordered[i] || '').trim();
    if (!label) continue;
    var lowLabel = label.toLowerCase();
    var headingCandidates = [lowLabel, lowLabel + '?'];
    if (headingCandidates.indexOf(lower) >= 0) return {label:lowLabel,value:'',headingOnly:true};

    // Recruiter templates often append a parenthetical explanation to the
    // heading, for example "Presentability (Confidence, Comms, Business
    // Awareness)". Treat that as the same field rather than as its value.
    if (lower.indexOf(lowLabel) === 0) {
      var tail = plain.slice(label.length);
      if (/^\s*\([^)]{1,180}\)\s*\??\s*$/.test(tail)) return {label:lowLabel,value:'',headingOnly:true};
      var m = tail.match(/^\s*(?:\?|[:：=]|=>|[-–—])\s*(.*?)\s*$/);
      if (m) return {label:lowLabel,value:String(m[1] || '').trim(),headingOnly:!String(m[1] || '').trim()};
      // OneNote table exports can turn label/value cells into a single line
      // separated by several spaces or a tab.
      m = tail.match(/^(?:	+|\s{2,})(.*?)\s*$/);
      if (m) return {label:lowLabel,value:String(m[1] || '').trim(),headingOnly:!String(m[1] || '').trim()};
    }
  }
  var inline = oneNoteInlineNamedFieldParts(plain, labels);
  if (inline) return inline;
  return oneNoteFuzzyLabelLineParts(plain, labels);
}
function oneNoteIsKnownFieldBoundary(line) {
  var clean = oneNoteNormalizeLabelLine(line);
  if (!clean) return false;
  if (oneNoteValidCandidateEmail(clean) || /^---\s*OneNote Page:/i.test(clean)) return true;
  return !!oneNoteLabelLineParts(clean, ONE_NOTE_FIELD_BOUNDARY_LABELS);
}
function oneNoteLineField(block, labels) {
  var text = String(block || '').replace(/\r\n?/g, '\n');
  var lines = text.split('\n');
  for (var i=0;i<lines.length;i++) {
    var parsed = oneNoteLabelLineParts(lines[i], labels);
    if (!parsed) continue;
    var parts = [];
    if (parsed.value) parts.push(parsed.value);
    var blankRun = 0;
    // OneNote frequently inserts blank paragraphs between a heading and its
    // value. Skip bounded spacing, then collect wrapped values until another
    // recognised field/email begins. This remains bounded to avoid absorbing
    // the rest of a malformed page.
    for (var j=i+1;j<Math.min(lines.length, i+18);j++) {
      var nxt = oneNoteNormalizeLabelLine(lines[j]);
      if (!nxt) {
        blankRun++;
        if (!parts.length && blankRun <= 4) continue;
        if (parts.length && blankRun <= 1) continue;
        break;
      }
      blankRun = 0;
      if (oneNoteIsKnownFieldBoundary(nxt)) break;
      // A candidate name is commonly placed immediately before the next email.
      // Do not append that name to the previous candidate's final field.
      var look = j + 1;
      while (look < Math.min(lines.length, j + 4) && !oneNoteNormalizeLabelLine(lines[look])) look++;
      if (look < lines.length && oneNoteValidCandidateEmail(oneNoteNormalizeLabelLine(lines[look]))) break;
      if (parts.join('\n').length + nxt.length + 1 > 4000) break;
      parts.push(nxt);
    }
    while (parts.length && !String(parts[parts.length-1] || '').trim()) parts.pop();
    if (parts.length) return parts.join('\n').trim();
  }
  return '';
}

function oneNoteOverviewField(block) {
  var text = String(block || '').replace(/\r\n?/g, '\n');
  var lines = text.split('\n');
  for (var i=0;i<lines.length;i++) {
    var parsed = oneNoteLabelLineParts(lines[i], ONE_NOTE_OVERVIEW_LABELS);
    if (!parsed) continue;
    var parts = [];
    if (parsed.value) parts.push(parsed.value);
    for (var j=i+1;j<Math.min(lines.length, i+60);j++) {
      var raw = String(lines[j] || '');
      var nxt = raw.trim();
      if (nxt && oneNoteIsKnownFieldBoundary(nxt)) break;
      if (!nxt) {
        if (parts.length && parts[parts.length-1] !== '') parts.push('');
        continue;
      }
      var currentLen = parts.join('\n').length;
      if (currentLen + nxt.length + 1 > 8000) break;
      parts.push(nxt);
    }
    while (parts.length && parts[parts.length-1] === '') parts.pop();
    if (parts.length) return parts.join('\n').trim();
  }
  return '';
}

function oneNoteMergeOverview(base, label, extra) {
  base = String(base || '').trim();
  extra = String(extra || '').trim();
  if (!extra) return base;
  // Pure rating lines belong to Presentability, not overview clutter.
  if (/^[1-4](?:\s*\/\s*4|\s*out of\s*4)?\.?$/i.test(extra)) return base;
  var line = label + ': ' + extra;
  return base ? (base + '\n' + line) : line;
}
function oneNoteGuessName(block, email) {
  var name = oneNoteLineField(block, ['name','candidate','candidate name','cdd','cdd name']);
  if (name) return name;
  var lines = String(block || '').split('\n').map(function(x){ return x.trim(); }).filter(Boolean);
  for (var i=0;i<Math.min(lines.length, 5);i++) {
    var line = lines[i];
    var inlineField = oneNoteInlineNamedFieldParts(oneNoteNormalizeLabelLine(line), ONE_NOTE_FIELD_BOUNDARY_LABELS);
    if (inlineField && inlineField.inlineName) return inlineField.inlineName;
    if (line.indexOf('@') >= 0) {
      var beforeEmail = line.split(/(?=[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})/i)[0].replace(/[:：\-–—]+\s*$/, '').trim();
      if (beforeEmail.length >= 2 && beforeEmail.length <= 80 && !/^(email|candidate email)$/i.test(beforeEmail)) return beforeEmail;
      continue;
    }
    if (oneNoteIsKnownFieldBoundary(line)) continue;
    if (/^(email|phone|mobile|current|expected|notice|salary|notes?|summary|overview|role|position|reason|rfl|looking|lf|cs|es|np|leads?|client|remarks?|presentability|communications?|comms|confidence|business awareness|location|red flags?|next steps?)\b/i.test(line)) continue;
    if (line.length >= 3 && line.length <= 80) return line.replace(/^[-•*\d.)\s]+/, '').trim();
  }
  return email;
}
function oneNoteRatingFromText(value) {
  var s = String(value || '').trim();
  if (!s) return '';
  // Prefer the first visible value line. A malformed/repeated OneNote export
  // may append the next candidate name after an otherwise valid 3/4 value.
  var firstLine = s.split(/\r?\n/).map(function(x){return x.trim();}).filter(Boolean)[0] || s;
  var m = firstLine.match(/^\s*[^\d]{0,60}([1-4])\s*(?:\/\s*4|out of\s*4)(?:\s*[-–—:|]\s*[^\d].*)?\s*$/i);
  if (m) return m[1];
  m = firstLine.match(/^\s*(?:rating|score)?\s*[:=\-–—]?\s*([1-4])\s*$/i);
  if (m) return m[1];
  m = firstLine.match(/^\s*([1-4])\s*[-–—:]\s*[^\d].*$/i);
  if (m) return m[1];
  m = s.match(/\b(?:rating|score)\s*[:=\-–—]?\s*([1-4])\b/i);
  return m ? m[1] : '';
}
function oneNotePresentabilityRating(block) {
  var raw = oneNoteLineField(block, [
    'presentability (confidence, comms, business awareness)','presentability / communications','presentability','presentability rating','confidence comms business awareness','confidence, comms, business awareness','communications','communication','comms','confidence','business awareness'
  ]);
  return oneNoteRatingFromText(raw);
}
function oneNoteExtractFields(block, email) {
  var currentSalary = oneNoteLineField(block, ['current salary breakdown / cs','cs / current salary breakdown','current / last drawn / cs','current salary breakdown','current salary','last drawn salary','last drawn','current','cs','current comp','current package','current basic','salary breakdown']);
  var lookingFor = oneNoteLineField(block, ['looking for / lf','lf / looking for','looking for?','looking for','lf','looking','seeking','target role','target','preferred role','motivation','interest','why interested']);
  var overview = oneNoteOverviewField(block);
  var commNote = oneNoteLineField(block, ['communication','communications','comms']);
  overview = oneNoteMergeOverview(overview, 'Communication', commNote);
  var rawNotice = oneNoteLineField(block, ['notice period / np','np / notice period','notice period / availability','notice period','np','notice','availability','available']);
  var correctedNotice = oneNoteCorrectNoticeValue(rawNotice);
  var fields = {
    name: oneNoteGuessName(block, email),
    email: email,
    phone: oneNoteLineField(block, ['phone','mobile','contact','contact number','hp']),
    role: oneNoteLineField(block, ['role','position','job title','applied role']),
    brief_overview: overview,
    reason_leaving: oneNoteLineField(block, ['reason for leaving / rfl','rfl / reason for leaving','reason for leaving','rfl','reason leaving','leaving reason','why leaving','reason']),
    looking_for: lookingFor,
    current_salary_breakdown: currentSalary,
    expected_salary: oneNoteLineField(block, ['expected salary / es','es / expected salary','expected / asking salary / es','expected salary','asking salary','expected','es','expectation','expected package','expected basic']),
    notice_period: correctedNotice,
    leads: oneNoteLineField(block, ['leads','lead','client','active','representation','agency representation']),
    remarks: oneNoteLineField(block, ['remarks','remark','things to take note','take note']),
    presentability_rating: oneNotePresentabilityRating(block),
    raw_presentability: oneNoteLineField(block, ['presentability (confidence, comms, business awareness)','presentability / communications','presentability','presentability rating','communications','communication','comms','confidence comms business awareness','confidence, comms, business awareness']),
    location: oneNoteLineField(block, ['location','current location','based in']),
    red_flags: oneNoteLineField(block, ['red flags','red flag','concerns','risk','risks']),
    next_steps: oneNoteLineField(block, ['next steps','next step','follow up','follow-up'])
  };
  if (rawNotice && correctedNotice && rawNotice !== correctedNotice) fields._spelling_corrections = ['Notice: ' + rawNotice + ' → ' + correctedNotice];
  return oneNoteApplyRecruitmentCorrections(fields);
}
// A OneNote page can contain several free-form text boxes. Desktop imports now
// expose those boxes with a stable marker, while older/manual/Graph text may
// still be flat. Build candidate-sized clusters in both cases. A repeated
// screening heading starts a new cluster, and an email may appear at either the
// beginning or the end of its cluster.
function oneNoteCanonicalFieldInfo(line) {
  var defs = [
    ['brief_overview', ONE_NOTE_OVERVIEW_LABELS],
    ['reason_leaving', ['reason for leaving / rfl','rfl / reason for leaving','reason for leaving','rfl','reason leaving','leaving reason','why leaving','reason']],
    ['looking_for', ['looking for / lf','lf / looking for','looking for?','looking for','lf','looking','seeking','target role','target','preferred role','motivation','interest','why interested']],
    ['current_salary_breakdown', ['current salary breakdown / cs','cs / current salary breakdown','current / last drawn / cs','current salary breakdown','current salary','last drawn salary','last drawn','current','cs','current comp','current package','current basic','salary breakdown']],
    ['expected_salary', ['expected salary / es','es / expected salary','expected / asking salary / es','expected salary','asking salary','expected','es','expectation','expected package','expected basic']],
    ['notice_period', ['notice period / np','np / notice period','notice period / availability','notice period','np','notice','availability','available']],
    ['leads', ['leads','lead','client','active','representation','agency representation']],
    ['remarks', ['remarks','remark','things to take note','take note']],
    ['presentability_rating', ['presentability (confidence, comms, business awareness)','presentability / communications','presentability','presentability rating','communications','communication','comms','confidence comms business awareness','confidence, comms, business awareness']]
  ];
  for (var i=0;i<defs.length;i++) {
    var parsed = oneNoteLabelLineParts(line, defs[i][1]);
    if (parsed) return {key:defs[i][0], value:String(parsed.value || '').trim(), parsed:parsed};
  }
  return null;
}
function oneNoteCanonicalFieldKey(line) {
  var info = oneNoteCanonicalFieldInfo(line);
  return info ? info.key : '';
}
function oneNoteComparableFieldValue(value, key) {
  var normalized = String(value || '').toLowerCase().replace(/[–—]/g, '-').replace(/\s+/g, ' ').trim();
  if (key === 'notice_period' && normalized) normalized = String(oneNoteCorrectNoticeValue(normalized) || normalized).toLowerCase();
  return normalized;
}
function oneNoteCandidateClusters(raw) {
  var lines = String(raw || '').replace(/\r\n?/g, '\n').split('\n');
  var hasExplicitMarkers = lines.some(function(line){ return /^---\s*OneNote Note Block:\s*.*---\s*$/i.test(String(line || '').trim()); });
  var out = [], current = null;
  function fresh() { return {lines:[], emails:{}, fieldKeys:{}, fieldValues:{}, fieldCount:0, lastFieldKey:''}; }
  function hasContent(c) { return !!(c && c.lines.some(function(x){ return String(x || '').trim(); })); }
  function flush() {
    if (!hasContent(current)) { current = fresh(); return; }
    var text = current.lines.join('\n').replace(/^\s+|\s+$/g, '');
    if (text) out.push({text:text, emails:Object.keys(current.emails), fieldKeys:Object.keys(current.fieldKeys)});
    current = fresh();
  }
  current = fresh();
  lines.forEach(function(line){
    var clean = oneNoteNormalizeLabelLine(line);
    if (/^---\s*OneNote Note Block:\s*.*---\s*$/i.test(String(line || '').trim())) { flush(); return; }
    var lineEmails = oneNoteEmailOccurrences(line).map(function(x){ return x.email; });
    var distinctNewEmail = lineEmails.some(function(email){ return !current.emails[email]; });
    var existingEmails = Object.keys(current.emails);
    var fieldInfo = oneNoteCanonicalFieldInfo(line);
    var key = fieldInfo ? fieldInfo.key : '';
    var fieldValue = fieldInfo ? oneNoteComparableFieldValue(fieldInfo.value, key) : '';
    var repeatedField = !!(key && current.fieldKeys[key]);
    var adjacentSameAlias = !!(repeatedField && current.lastFieldKey === key && fieldValue && current.fieldValues[key] === fieldValue);
    var meaningfulCurrent = current.fieldCount >= 2 || existingEmails.length > 0;

    // A different email after a completed field set is the next candidate.
    // Do not split an email that appears at the bottom of an email-less block.
    if (hasContent(current) && distinctNewEmail && existingEmails.length > 0 && meaningfulCurrent) flush();
    // Flat legacy/Graph text has no Outline marker. Repeating RFL/CS/etc. after
    // a meaningful set is a reliable new-candidate boundary. Consecutive
    // aliases carrying the same normalized value (for example Notice Period
    // followed by NP) are one field, not a new person.
    else if (!hasExplicitMarkers && hasContent(current) && repeatedField && current.fieldCount >= 3 && !adjacentSameAlias) flush();

    current.lines.push(line);
    lineEmails.forEach(function(email){ current.emails[email] = 1; });
    if (key && !current.fieldKeys[key]) { current.fieldKeys[key] = 1; current.fieldCount++; }
    if (key) {
      if (fieldValue) current.fieldValues[key] = fieldValue;
      current.lastFieldKey = key;
    }
  });
  flush();
  return out;
}

function oneNoteMissingFields(fields) {
  fields = fields || {};
  return ONE_NOTE_REQUIRED_FIELDS.filter(function(x){
    var val = String(fields[x[0]] || '').trim();
    if (x[0] === 'presentability_rating') return !/^[1-4]$/.test(val);
    return !val;
  });
}
function oneNoteRefreshRowStatus(row) {
  if (!row) return;
  if (row.status === 'done') { row.selected = false; return; }
  var missing = oneNoteMissingFields(row.fields || {});
  row.missing = missing;
  if (!String(row.email || '').trim()) {
    if (row.status !== 'err' && row.status !== 'pending') { row.status = 'warn'; row.statusText = 'Add email to match'; }
    row.selected = false;
  } else if (!row.candidate_id) {
    if (row.status !== 'err' && row.status !== 'pending') { row.status = 'warn'; row.statusText = 'Not matched'; }
    row.selected = false;
  } else if (missing.length) {
    row.status = 'warn'; row.statusText = row.retransfer_ready ? 'Edited · missing fields' : 'Missing fields'; row.selected = false;
  } else if (row.status !== 'ok' && row.status !== 'pending') {
    row.status = 'ok'; row.statusText = row.retransfer_ready ? 'Edited · ready again' : 'Matched'; row.selected = true;
  } else if (row.status === 'ok') {
    row.statusText = row.retransfer_ready ? 'Edited · ready again' : 'Matched'; row.selected = row.selected !== false;
  }
}
function oneNoteSetFieldLive(idx, key, value) {
  var row = _oneNoteRows[idx];
  if (!row) return;
  row.fields = row.fields || {};
  var nextValue = String(value == null ? '' : value).trim();
  var changed = String(row.fields[key] == null ? '' : row.fields[key]).trim() !== nextValue;
  if (changed && row.status === 'done') {
    // Every successful transfer creates a new Screening Call. Editing a row
    // after success therefore reopens it for an intentional second transfer
    // instead of leaving the old done-state to suppress selection/validation.
    row.status = 'ok';
    row.statusText = 'Edited · ready again';
    row.selected = true;
    row.retransfer_ready = true;
    row.transfer_error = '';
    row.transfer_error_detail = '';
    row.transfer_warning = '';
  }
  row.fields[key] = nextValue;
  if (changed && row.fields._spelling_corrections) delete row.fields._spelling_corrections;
  oneNoteRefreshRowStatus(row);
}
function oneNoteSetField(idx, key, value) {
  oneNoteSetFieldLive(idx, key, value);
  oneNoteRenderRows();
}
function oneNoteApplyRowEmail(idx, value, render) {
  var row = _oneNoteRows[idx];
  if (!row) return;
  var email = String(value || '').trim().toLowerCase();
  if (email === String(row.email || '').trim().toLowerCase()) {
    if (render) oneNoteRenderRows();
    return;
  }
  row.email = email;
  row.fields = row.fields || {};
  row.fields.email = email;
  row.candidate_id = '';
  row.matched_name = '';
  row.raw_match = null;
  row.no_match_found = false;
  row.profile_create_state = '';
  row.profile_create_message = '';
  row.selected = false;
  row.status = 'warn';
  row.statusText = email ? (oneNoteValidCandidateEmail(email) ? 'Ready to match' : 'Enter a valid email') : 'Add email to match';
  oneNoteRefreshRowStatus(row);
  if (render) oneNoteRenderRows();
}
function oneNoteSetRowEmail(idx, value) {
  oneNoteApplyRowEmail(idx, value, true);
}
function oneNoteEmailInputVisual(el, idx) {
  if (!el) return;
  var val = String(el.value || '').trim();
  el.classList.toggle('onenote-email-missing', !val);
  el.classList.toggle('onenote-email-invalid', !!val && !oneNoteValidCandidateEmail(val));
  // Visual feedback is live, but the stored email is committed by change or
  // oneNoteSyncVisibleInputs(). This prevents an unblurred edit from retaining
  // a stale JobAdder candidate ID that belonged to the previous email.
}
function oneNoteSyncVisibleInputs() {
  var root = document.getElementById('oneNoteResults');
  if (!root) return;
  root.querySelectorAll('[data-onenote-row][data-onenote-key]').forEach(function(el){
    var idx = Number(el.getAttribute('data-onenote-row'));
    var key = String(el.getAttribute('data-onenote-key') || '');
    if (!Number.isInteger(idx) || !_oneNoteRows[idx] || !key) return;
    if (key === 'email') {
      oneNoteApplyRowEmail(idx, el.value, false);
      oneNoteEmailInputVisual(el, idx);
    } else {
      oneNoteSetFieldLive(idx, key, el.value);
    }
  });
}
async function oneNoteLookupCandidateForRow(row) {
  if (!row || !oneNoteValidCandidateEmail(row.email)) return false;
  var accountSeq = Number(window._oneNoteJobAdderAccountSeq) || 0;
  var r = await fetchWithTimeout('/jobadder/search_candidate?email=' + encodeURIComponent(row.email), {}, 16000);
  var d = await r.json().catch(function(){ return {}; });
  if ((Number(window._oneNoteJobAdderAccountSeq) || 0) !== accountSeq) {
    var invalidated = new Error('JobAdder account changed while matching. Match again after reconnecting.');
    invalidated.jobAdderAccountInvalidated = true;
    throw invalidated;
  }
  if (!r.ok) throw new Error(d.error || d.detail || ('JobAdder search failed: ' + r.status));
  var items = oneNoteCandidateItems(d);
  var match = items[0] || null;
  row.raw_match = match;
  row.candidate_id = oneNoteCandidateId(match);
  row.matched_name = oneNoteCandidateName(match);
  row.no_match_found = !row.candidate_id;
  if (row.candidate_id) { row.status = 'ok'; row.statusText = 'Matched'; row.selected = true; row.profile_create_state = ''; row.profile_create_message = ''; }
  else { row.status = 'warn'; row.statusText = 'No candidate found'; row.selected = false; }
  oneNoteRefreshRowStatus(row);
  return !!row.candidate_id;
}
async function oneNoteMatchRow(idx) {
  var row = _oneNoteRows[idx];
  if (!row) return false;
  if (!oneNoteValidCandidateEmail(row.email)) {
    row.status = 'warn'; row.statusText = 'Enter a valid email'; row.selected = false; oneNoteRenderRows();
    showToast('Enter a valid candidate email, then click Match', 'info');
    return false;
  }
  row.status = 'pending'; row.statusText = 'Matching…'; row.selected = false; oneNoteRenderRows();
  try {
    var ok = await oneNoteLookupCandidateForRow(row);
    oneNoteRenderRows();
    showToast(ok ? 'Candidate matched' : 'No JobAdder candidate found for this email', ok ? 'ok' : 'info');
    return ok;
  } catch(e) {
    if (e && e.jobAdderAccountInvalidated) return false;
    row.status = 'err'; row.statusText = (e.message || 'Match failed').split('\n')[0]; row.selected = false; oneNoteRenderRows();
    showToast(e.message || 'Candidate match failed', 'err');
    return false;
  }
}
var _oneNoteCvUploadRowIndex = -1;
function oneNoteUpdateSummaryFromRows() {
  var summary = document.getElementById('oneNoteSummary');
  if (!summary || !_oneNoteRows.length) return;
  var matched = _oneNoteRows.filter(function(x){ return !!x.candidate_id; }).length;
  var ready = _oneNoteRows.filter(function(x){ return !!x.candidate_id && !oneNoteMissingFields(x.fields).length; }).length;
  var needsEmail = _oneNoteRows.filter(function(x){ return !String(x.email || '').trim(); }).length;
  var creating = _oneNoteRows.filter(function(x){ return x.profile_create_state === 'running'; }).length;
  summary.textContent = matched + ' matched / ' + _oneNoteRows.length + ' imported. ' + ready + ' ready'
    + (needsEmail ? (' · ' + needsEmail + ' need email') : '')
    + (creating ? (' · ' + creating + ' creating profile') : '') + '.';
}
function oneNoteUploadCvForRow(idx) {
  var row = _oneNoteRows[idx];
  if (!row || row.candidate_id || row.profile_create_state === 'running') return false;
  if (!row.no_match_found) {
    showToast('Click Match first. Upload CV appears after JobAdder confirms no candidate was found.', 'info');
    return false;
  }
  if (!oneNoteValidCandidateEmail(row.email)) {
    showToast('Enter a valid candidate email before uploading the CV', 'err');
    return false;
  }
  if (!window._jaToken) {
    row.profile_create_state = 'error';
    row.profile_create_message = 'Connect to JobAdder first, then click Upload CV again.';
    oneNoteRenderRows();
    showToast('Connect to JobAdder first', 'err');
    return false;
  }
  var input = document.getElementById('oneNoteCvUploadInput');
  if (!input) return false;
  _oneNoteCvUploadRowIndex = idx;
  input.value = '';
  input.click();
  return true;
}
async function oneNoteHandleCvUpload(files) {
  var idx = _oneNoteCvUploadRowIndex;
  _oneNoteCvUploadRowIndex = -1;
  var row = _oneNoteRows[idx];
  var file = files && files[0];
  var input = document.getElementById('oneNoteCvUploadInput');
  if (input) input.value = '';
  if (!row || !file) return false;
  var lower = String(file.name || '').toLowerCase();
  if (!/\.(pdf|docx|doc)$/.test(lower)) {
    row.profile_create_state = 'error';
    row.profile_create_message = 'Unsupported CV file. Upload PDF, DOCX, or DOC.';
    oneNoteRenderRows();
    showToast('Upload a PDF, DOCX, or DOC CV', 'err');
    return false;
  }
  if (!window._jaToken) {
    row.profile_create_state = 'error';
    row.profile_create_message = 'Connect to JobAdder first, then click Upload CV again.';
    oneNoteRenderRows();
    showToast('Connect to JobAdder first', 'err');
    return false;
  }
  row.profile_create_state = 'running';
  row.profile_create_message = 'Creating candidate profile from ' + file.name + '…';
  row.status = 'pending';
  row.statusText = 'Creating profile…';
  row.selected = false;
  oneNoteRenderRows();
  oneNoteUpdateSummaryFromRows();

  var id = 'jac_onenote_' + Date.now() + '_' + idx;
  _jaCreateQueue.push({
    id: id,
    file: file,
    status: 'processing',
    statusText: '⏳ Queued from OneNote…',
    jaClass: 'show uploading',
    jaProfileUrl: '',
    _forcedEmail: String(row.email || '').trim().toLowerCase(),
    _oneNoteRowIndex: idx,
    _oneNoteSourceTitle: row.source_title || '',
    _oneNoteSourceName: (row.fields || {}).name || row.matched_name || ''
  });
  renderJACreateList();
  updateJACreateConnStatus();
  await runJACreateOne(id);
  return true;
}
function oneNoteProfileCreateCompleted(item, candidateId, cand, createdNew) {
  if (!item || item._oneNoteRowIndex === undefined) return;
  var row = _oneNoteRows[item._oneNoteRowIndex];
  if (!row) return;
  row.candidate_id = String(candidateId || '');
  row.raw_match = { candidateId: candidateId, name: (cand || {}).name || '' };
  row.matched_name = (cand || {}).name || (row.fields || {}).name || row.email || '';
  row.no_match_found = false;
  row.profile_create_state = 'done';
  row.profile_create_message = createdNew
    ? 'Candidate profile is created in JobAdder.'
    : 'Candidate profile is ready in JobAdder and the CV was uploaded.';
  row.status = 'ok';
  row.statusText = createdNew ? 'Profile created' : 'Profile ready';
  row.selected = !oneNoteMissingFields(row.fields || {}).length;
  oneNoteRefreshRowStatus(row);
  oneNoteRenderRows();
  oneNoteUpdateSummaryFromRows();
  showToast(createdNew ? 'Candidate profile created from OneNote CV' : 'Candidate profile found and CV uploaded', 'ok');
}
function oneNoteProfileCreateFailed(item, err) {
  if (!item || item._oneNoteRowIndex === undefined) return;
  var row = _oneNoteRows[item._oneNoteRowIndex];
  if (!row) return;
  row.profile_create_state = 'error';
  row.profile_create_message = 'Candidate profile creation failed: ' + String((err && err.message) || err || 'Unknown error').split('|')[0].trim();
  row.status = 'err';
  row.statusText = 'Profile creation failed';
  row.selected = false;
  oneNoteRenderRows();
  oneNoteUpdateSummaryFromRows();
}
function oneNoteBuildStructuredNote(row) {
  var f = row.fields || {};
  var rating = String(f.presentability_rating || '').trim();
  var ratingLine = rating ? (rating + '/4' + (f.raw_presentability && f.raw_presentability.indexOf(rating) < 0 ? ' - ' + f.raw_presentability : '')) : '';
  var parts = [];
  parts.push('Screening Call Activity');
  parts.push('Candidate: ' + (f.name || row.matched_name || row.email || 'Unknown'));
  parts.push('Email: ' + (row.email || ''));
  if (f.phone) parts.push('Phone: ' + f.phone);
  if (f.role) parts.push('Role / Position: ' + f.role);
  if (f.location) parts.push('Location: ' + f.location);
  parts.push('');
  parts.push('Brief Overview of Experience (optional): ' + (f.brief_overview || ''));
  parts.push('Reason For Leaving: ' + (f.reason_leaving || ''));
  parts.push('Looking for: ' + (f.looking_for || ''));
  parts.push('Current Salary Breakdown: ' + (f.current_salary_breakdown || ''));
  parts.push('Expected Salary: ' + (f.expected_salary || ''));
  parts.push('Notice Period: ' + (f.notice_period || ''));
  if (f.leads) parts.push('Leads: ' + f.leads);
  if (f.remarks) parts.push('Remarks: ' + f.remarks);
  parts.push('Presentability (Confidence, Comms, Business Awareness) (mandatory): ' + ratingLine);
  if (f.red_flags) parts.push('Red Flags / Concerns: ' + f.red_flags);
  if (f.next_steps) parts.push('Next Steps: ' + f.next_steps);
  parts.push('\nOriginal Notes:\n' + oneNoteNormalizeText(row.block || ''));
  parts.push('\nLogged from CV Studio OneNote tab.');
  return parts.join('\n');
}
function oneNoteCandidateId(c) {
  var id = c && (c.candidateId || c.candidateID || c.candidate_id || c.id || c.entityId);
  if (id && typeof id === 'object') id = id.candidateId || id.id || id.value || '';
  return id ? String(id) : '';
}
function oneNoteCandidateName(c) {
  if (!c) return '';
  var n = c.name || c.fullName || c.displayName || c.candidateName || '';
  if (!n) n = [c.firstName || c.first_name || '', c.lastName || c.last_name || ''].join(' ').trim();
  return n || '';
}
function oneNoteCandidateItems(data) {
  if (!data) return [];
  if (Array.isArray(data.items)) return data.items;
  if (data.data && Array.isArray(data.data.items)) return data.data.items;
  if (Array.isArray(data.candidates)) return data.candidates;
  if (Array.isArray(data)) return data;
  return [];
}
function oneNoteStoredSourceMode() {
  var v = 'web';
  try { v = (localStorage.getItem('onenote_source_mode') || 'web').trim().toLowerCase(); } catch(e) {}
  return (v === 'desktop' || v === 'both') ? v : 'web';
}
function oneNoteApiSyncFields(clientId, tenant, mode) {
  clientId = String(clientId || '');
  tenant = String(tenant || 'common') || 'common';
  mode = (mode === 'desktop' || mode === 'both') ? mode : 'web';
  var ids = ['oneNoteMsClientId', 'settingsOneNoteClientId'];
  ids.forEach(function(id){ var el = document.getElementById(id); if (el) el.value = clientId; });
  var tids = ['oneNoteMsTenant', 'settingsOneNoteTenant'];
  tids.forEach(function(id){ var el = document.getElementById(id); if (el) el.value = tenant; });
  var modeEl = document.getElementById('oneNoteSourceMode');
  var settingsModeEl = document.getElementById('settingsOneNoteSourceMode');
  if (modeEl) modeEl.value = mode;
  if (settingsModeEl) settingsModeEl.value = mode;
  var badge = document.getElementById('settingsOneNoteStatus');
  if (badge) badge.textContent = clientId ? ('Saved · ' + mode) : 'Not configured';
}
function oneNoteApiLoadSettings() {
  try {
    var clientId = localStorage.getItem('onenote_ms_client_id') || '';
    var tenant = localStorage.getItem('onenote_ms_tenant') || 'common';
    var mode = oneNoteStoredSourceMode();
    oneNoteApiSyncFields(clientId, tenant, mode);
    oneNoteLoadSpellingCorrectionSetting();
  } catch(e) {}
}
function oneNoteApiSaveSettings(silent) {
  try {
    var sc = document.getElementById('settingsOneNoteClientId');
    var st = document.getElementById('settingsOneNoteTenant');
    var sm = document.getElementById('settingsOneNoteSourceMode');
    var tc = document.getElementById('oneNoteMsClientId');
    var tt = document.getElementById('oneNoteMsTenant');
    var tm = document.getElementById('oneNoteSourceMode');
    var clientId = ((sc && sc.value) || (tc && tc.value) || localStorage.getItem('onenote_ms_client_id') || '').trim();
    var tenant = ((st && st.value) || (tt && tt.value) || localStorage.getItem('onenote_ms_tenant') || 'common').trim() || 'common';
    var mode = ((sm && sm.value) || (tm && tm.value) || oneNoteStoredSourceMode()).trim().toLowerCase();
    if (!(mode === 'desktop' || mode === 'both')) mode = 'web';
    cvStudioDurableSettingSet('onenote_ms_client_id', clientId);
    cvStudioDurableSettingSet('onenote_ms_tenant', tenant);
    cvStudioDurableSettingSet('onenote_source_mode', mode);
    oneNoteSaveSpellingCorrectionSetting();
    oneNoteApiSyncFields(clientId, tenant, mode);
    try { oneNoteSourceModeChanged(true); } catch(e2) {}
    if (!silent) showToast('OneNote API settings saved', 'ok');
  } catch(e) { if (!silent) showToast('Could not save OneNote settings', 'err'); }
}
function oneNoteApiCopyToTab() {
  oneNoteApiSaveSettings(true);
  try { oneNoteSourceModeChanged(true); } catch(e) {}
  showToast('OneNote settings applied to tab', 'ok');
}
function oneNoteMsLoadSettings() {
  oneNoteApiLoadSettings();
}
function oneNoteMsSaveSettings() {
  try {
    var c = document.getElementById('oneNoteMsClientId');
    var t = document.getElementById('oneNoteMsTenant');
    var m = document.getElementById('oneNoteSourceMode');
    if (c) cvStudioDurableSettingSet('onenote_ms_client_id', c.value.trim());
    if (t) cvStudioDurableSettingSet('onenote_ms_tenant', t.value.trim() || 'common');
    if (m) cvStudioDurableSettingSet('onenote_source_mode', oneNoteSelectedSourceMode());
    oneNoteApiLoadSettings();
  } catch(e) {}
}
async function oneNoteRestoreMicrosoftToken() {
  try {
    oneNoteMsLoadSettings();
    var raw=localStorage.getItem('onenote_ms_token')||'';
    if(raw){
      try{
        var mr=await fetch('/onenote/store_token',{method:'POST',headers:{'Content-Type':'application/json'},body:raw});
        var md=await mr.json().catch(function(){return {};});
        if(mr.ok&&md.ok&&md.connected)localStorage.removeItem('onenote_ms_token');
      }catch(e){}
    }
    var r=await fetch('/onenote/api_info',{cache:'no-store'}),d=await r.json().catch(function(){return {};});
    window._oneNoteConnected=!!d.connected;
    window._oneNoteAccountEmail=String(d.account_email||'');
    return d;
  } catch(e) { return {}; }
}
function oneNoteShowMicrosoftCode(d) {
  var box = document.getElementById('oneNoteMsCode');
  if (!box) return;
  if (!d) { box.style.display = 'none'; box.textContent = ''; return; }
  box.style.display = 'block';
  var url = d.verification_uri || d.verification_url || 'https://microsoft.com/devicelogin';
  box.innerHTML = '1) Open: <a href="' + escAttr(url) + '" target="_blank" rel="noopener">' + esc(url) + '</a><br>2) Enter code: <b style="font-size:16px;color:var(--text1);">' + esc(d.user_code || '') + '</b><br>3) Click Finish Login here.';
}
function oneNoteRefreshCost() {
  var el = document.getElementById('oneNoteCostBadge');
  if (!el) return;
  var records = oneNoteRecordsLoad();
  var total = records.reduce(function(sum, r){ return sum + Number((r && r.ai_cost_usd) || 0); }, 0);
  var anyAi = records.some(function(r){ return !!(r && (r.ai_used || r.ai_api_called || Number(r.ai_cost_usd||0)>0)); });
  if (!anyAi && total === 0) {
    el.textContent = 'Salary processing: Local deterministic parser · AI not used · AI cost $0.0000 / RM 0.00';
    return;
  }
  el.textContent = 'OneNote AI usage recorded: ' + (anyAi ? 'Yes' : 'No') + ' · Total AI cost $' + total.toFixed(4) + ' / RM ' + (total * (typeof USD_TO_MYR === 'number' ? USD_TO_MYR : 4.47)).toFixed(2);
}
async function oneNoteRunAction(fnName) {
  var fn = window[fnName];
  if (typeof fn !== 'function') { showToast('OneNote action missing: ' + fnName, 'err'); return false; }
  var run = markTabRunning('onenote');
  oneNoteRefreshCost();
  try {
    var ok = await fn();
    if (ok === false) { markTabFailed('onenote', run); return false; }
    markTabDone('onenote', run);
    oneNoteRefreshCost();
    return true;
  } catch(e) {
    markTabFailed('onenote', run);
    showToast((e && e.message) || 'OneNote action failed', 'err');
    return false;
  }
}
async function oneNoteStartMicrosoftLogin() {
  oneNoteMsSaveSettings();
  var clientId = (document.getElementById('oneNoteMsClientId') || {}).value || '';
  var tenant = (document.getElementById('oneNoteMsTenant') || {}).value || 'common';
  clientId = clientId.trim(); tenant = tenant.trim() || 'common';
  if (!clientId) { showToast('Enter Microsoft app Client ID first', 'err'); return false; }
  var r = await fetch('/onenote/device_start', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({client_id:clientId, tenant:tenant})});
  var d = await r.json().catch(function(){ return {}; });
  if (!r.ok) { showToast(d.error || 'Microsoft login start failed', 'err'); return false; }
  window._oneNoteMsDevice = {login_session_id:d.login_session_id, client_id:clientId, tenant:tenant};
  oneNoteShowMicrosoftCode(d);
  showToast('Open Microsoft login page and enter the code', 'info');
  return true;
}
async function oneNoteFinishMicrosoftLogin() {
  var dev=window._oneNoteMsDevice||{};
  if(!dev.login_session_id){showToast('Click Connect Microsoft OneNote first','err');return false;}
  var r=await fetch('/onenote/device_poll',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({login_session_id:dev.login_session_id})});
  var d=await r.json().catch(function(){return {};});
  if(!r.ok){showToast((d.detail&&d.detail.indexOf('authorization_pending')>=0)?'Microsoft login still pending':(d.error||'Microsoft login not complete'),'err');return false;}
  try{localStorage.removeItem('onenote_ms_token');}catch(e){}
  window._oneNoteConnected=true; oneNoteShowMicrosoftCode(null); updateOneNoteConnStatus(); showToast('Microsoft OneNote connected securely','ok'); return true;
}

var _oneNotePickerPages = [];
var _oneNoteDesktopSectionsCache = [];
function oneNotePickerOptionLabel(item) {
  item = item || {};
  return String(item._label || item.displayName || item.title || 'Untitled').trim() || 'Untitled';
}
function oneNoteSectionLabel(section, notebookName) {
  var name = (section && (section.displayName || section.name || section.title)) || 'Untitled section';
  return notebookName ? (name + ' · ' + notebookName) : name;
}
function oneNoteSelectedTop() {
  var top = parseInt(((document.getElementById('oneNoteTop') || {}).value || '25'), 10) || 25;
  return Math.max(1, Math.min(top, 100));
}
function oneNotePickerFilters() {
  return {
    search: ((document.getElementById('oneNoteSearch') || {}).value || '').trim(),
    date_from: ((document.getElementById('oneNoteDateFrom') || {}).value || '').trim(),
    date_to: ((document.getElementById('oneNoteDateTo') || {}).value || '').trim(),
    date_mode: ((document.getElementById('oneNoteDateMode') || {}).value || 'created').trim() || 'created',
    top: oneNoteSelectedTop()
  };
}
function oneNoteSelectedSourceMode() {
  var v = ((document.getElementById('oneNoteSourceMode') || {}).value || oneNoteStoredSourceMode()).trim().toLowerCase();
  return (v === 'desktop' || v === 'both') ? v : 'web';
}
function oneNoteLooksLikeLocalNotebookFolderLink(value) {
  var raw = String(value || '').trim();
  if (!/^onenote:\/\/\//i.test(raw)) return false;
  var decoded = raw;
  try { decoded = decodeURIComponent(raw); } catch(e) {}
  var pathOnly = decoded.split('#')[0].split('?')[0].replace(/[\\/]+$/, '');
  return /^onenote:\/\/\/[A-Za-z]:[\\/]/i.test(pathOnly) && !/\.one$/i.test(pathOnly);
}
var ONE_NOTE_SAVED_LINKS_KEY = 'cvstudio_onenote_saved_desktop_links_v1';
var ONE_NOTE_SAVED_LINKS_MAX = 100;
var _oneNoteLinksSqliteCache = null;
var _oneNoteLinksMutationVersion = 0;
var _oneNoteLinksHydrationPromise = null;
var _oneNoteLinksWriteQueue = Promise.resolve();
var _oneNoteLinksLastWritePromise = Promise.resolve(true);
function oneNoteSavedLinkKind(value) {
  value = String(value || '').trim().toLowerCase();
  return (value === 'section' || value === 'page') ? value : 'notebook';
}
function oneNoteSavedLinkKindLabel(value) {
  value = oneNoteSavedLinkKind(value);
  return value.charAt(0).toUpperCase() + value.slice(1);
}
function oneNoteReadSavedLinksLegacy() {
  var raw = '';
  try { raw = localStorage.getItem(ONE_NOTE_SAVED_LINKS_KEY) || ''; } catch(e) { return []; }
  if (!raw) return [];
  var parsed;
  try { parsed = JSON.parse(raw); } catch(e2) { return []; }
  if (!Array.isArray(parsed)) return [];
  var out = [];
  var seen = {};
  parsed.forEach(function(item, idx){
    item=cvStudioPrivateSafeValue(item,0);
    if (!item || typeof item !== 'object') return;
    var link = String(item.link || '').trim();
    var name = String(item.name || '').trim().slice(0, 80);
    if (!link || !name || link.length > 4096) return;
    var id = String(item.id || '').trim() || ('legacy-' + idx + '-' + Math.abs(oneNoteSimpleHash(link + '|' + name)));
    if (seen[id]) return;
    seen[id] = true;
    out.push(Object.assign({},item,{
      id:id,
      name:name,
      kind:oneNoteSavedLinkKind(item.kind || item.type),
      link:link,
      createdAt:String(item.createdAt || ''),
      updatedAt:String(item.updatedAt || '')
    }));
  });
  return out.slice(0, ONE_NOTE_SAVED_LINKS_MAX);
}
function oneNoteLinkStorageKey(item){return String((item||{}).id||'legacy:'+cvStudioStableStorageValue(item||{}));}
function oneNoteLinkChangedKeys(beforeItems,afterItems){
  var before={},after={},changed={};(Array.isArray(beforeItems)?beforeItems:[]).forEach(function(item){before[oneNoteLinkStorageKey(item)]=cvStudioStableStorageValue(item);});(Array.isArray(afterItems)?afterItems:[]).forEach(function(item){after[oneNoteLinkStorageKey(item)]=cvStudioStableStorageValue(item);});Object.keys(before).concat(Object.keys(after)).forEach(function(key){if(!Object.prototype.hasOwnProperty.call(before,key)||!Object.prototype.hasOwnProperty.call(after,key)||before[key]!==after[key])changed[key]=true;});return changed;
}
function oneNoteMergeSavedLinks(sqliteItems,currentItems,changedKeys){
  var merged=[],positions={},current={};(Array.isArray(sqliteItems)?sqliteItems:[]).forEach(function(item){var key=oneNoteLinkStorageKey(item);if(!Object.prototype.hasOwnProperty.call(positions,key)){positions[key]=merged.length;merged.push(item);}});(Array.isArray(currentItems)?currentItems:[]).forEach(function(item){current[oneNoteLinkStorageKey(item)]=item;});Object.keys(changedKeys||{}).forEach(function(key){var position=positions[key];if(Object.prototype.hasOwnProperty.call(current,key)){if(position===undefined){positions[key]=merged.length;merged.push(current[key]);}else merged[position]=current[key];}else if(position!==undefined)merged[position]=null;});return merged.filter(function(item){return !!item;}).slice(0,ONE_NOTE_SAVED_LINKS_MAX);
}
function oneNoteReadSavedLinks(){var items=Array.isArray(_oneNoteLinksSqliteCache)?_oneNoteLinksSqliteCache:oneNoteReadSavedLinksLegacy();return Array.isArray(items)?items.slice():[];}
function oneNoteSimpleHash(value) {
  var h = 2166136261;
  value = String(value || '');
  for (var i=0; i<value.length; i++) { h ^= value.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h | 0;
}
function oneNoteWriteSavedLinks(items) {
  var previous=oneNoteReadSavedLinks();
  try {
    var safe=Array.isArray(items)?items.map(function(item){return cvStudioPrivateSafeValue(item,0);}).filter(function(item){return item&&typeof item==='object'&&!Array.isArray(item);}).slice(0,ONE_NOTE_SAVED_LINKS_MAX):[];
    _oneNoteLinksSqliteCache=safe;_oneNoteLinksMutationVersion+=1;var version=_oneNoteLinksMutationVersion;
    localStorage.setItem(ONE_NOTE_SAVED_LINKS_KEY, JSON.stringify(safe));
    _oneNoteLinksWriteQueue=_oneNoteLinksWriteQueue.catch(function(){}).then(function(){return cvStudioStoragePost('/storage/onenote-saved-links/replace',{links:safe});});
    _oneNoteLinksLastWritePromise=_oneNoteLinksWriteQueue.then(function(){return true;}).catch(function(error){
      if(_oneNoteLinksMutationVersion===version){_oneNoteLinksSqliteCache=previous;try{localStorage.setItem(ONE_NOTE_SAVED_LINKS_KEY,JSON.stringify(previous));oneNoteRenderSavedLinks();}catch(e){}}
      showToast('Saved OneNote links were restored because durable storage failed. '+String((error&&error.message)||''),'err');return false;
    });
    return true;
  } catch(e) {
    showToast('Could not save OneNote link on this browser', 'err');
    return false;
  }
}
function oneNoteLinksHydrateFromSQLite(){
  if(_oneNoteLinksHydrationPromise)return _oneNoteLinksHydrationPromise;
  var startedVersion=_oneNoteLinksMutationVersion,legacy=oneNoteReadSavedLinksLegacy();
  _oneNoteLinksHydrationPromise=cvStudioStoragePost('/storage/onenote-saved-links/import',{links:legacy}).then(function(data){
    var current=oneNoteReadSavedLinksLegacy(),changed=_oneNoteLinksMutationVersion!==startedVersion?oneNoteLinkChangedKeys(legacy,current):{},merged=oneNoteMergeSavedLinks(data.links,current,changed);
    _oneNoteLinksSqliteCache=merged;try{localStorage.setItem(ONE_NOTE_SAVED_LINKS_KEY,JSON.stringify(merged));}catch(e){}
    if(_oneNoteLinksMutationVersion!==startedVersion){_oneNoteLinksWriteQueue=_oneNoteLinksWriteQueue.catch(function(){}).then(function(){return cvStudioStoragePost('/storage/onenote-saved-links/replace',{links:merged});});_oneNoteLinksLastWritePromise=_oneNoteLinksWriteQueue.then(function(){return true;}).catch(function(){return false;});}
    try{oneNoteRenderSavedLinks();}catch(e){}return merged;
  }).catch(function(){_oneNoteLinksSqliteCache=oneNoteReadSavedLinksLegacy();return _oneNoteLinksSqliteCache;});
  return _oneNoteLinksHydrationPromise;
}
window.addEventListener('load',function(){setTimeout(oneNoteLinksHydrateFromSQLite,0);});
function oneNoteNewSavedLinkId() {
  try { if (window.crypto && typeof window.crypto.randomUUID === 'function') return window.crypto.randomUUID(); } catch(e) {}
  return 'osl-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10);
}
function oneNoteRenderSavedLinks(selectId) {
  var sel = document.getElementById('oneNoteSavedLinkSelect');
  var count = document.getElementById('oneNoteSavedLinkCount');
  var items = oneNoteReadSavedLinks();
  var order = {notebook:0, section:1, page:2};
  items.sort(function(a,b){
    var k = (order[a.kind] || 0) - (order[b.kind] || 0);
    return k || String(a.name || '').localeCompare(String(b.name || ''));
  });
  if (count) count.textContent = items.length + ' saved';
  if (!sel) return items;
  while (sel.firstChild) sel.removeChild(sel.firstChild);
  var placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = items.length ? 'Choose saved notebook, section, or page' : 'No saved links yet';
  sel.appendChild(placeholder);
  ['notebook','section','page'].forEach(function(kind){
    var groupItems = items.filter(function(item){ return item.kind === kind; });
    if (!groupItems.length) return;
    var group = document.createElement('optgroup');
    group.label = oneNoteSavedLinkKindLabel(kind) + 's';
    groupItems.forEach(function(item){
      var opt = document.createElement('option');
      opt.value = item.id;
      opt.textContent = item.name;
      opt.title = item.link;
      group.appendChild(opt);
    });
    sel.appendChild(group);
  });
  if (selectId && items.some(function(item){ return item.id === selectId; })) sel.value = selectId;
  else sel.value = '';
  oneNoteSavedLinkSelected();
  return items;
}
var oneNoteSaveDialogEditingId = '';
function oneNoteSavedLinkSelected() {
  var sel = document.getElementById('oneNoteSavedLinkSelect');
  var id = sel ? String(sel.value || '') : '';
  var item = oneNoteReadSavedLinks().filter(function(row){ return row.id === id; })[0];
  var nameEl = document.getElementById('oneNoteSavedLinkName');
  var typeEl = document.getElementById('oneNoteSavedLinkType');
  var linkEl = document.getElementById('oneNoteManualLink');
  var saveBtn = document.getElementById('oneNoteSaveLinkBtn');
  if (!item) {
    if (nameEl) nameEl.value = '';
    if (typeEl) typeEl.value = 'notebook';
    if (saveBtn) { saveBtn.textContent = 'Save Changes'; saveBtn.disabled = true; }
    return false;
  }
  // Selecting a saved entry now immediately loads all editable details. The
  // upper Use Link button remains the single explicit action that opens it.
  if (nameEl) nameEl.value = item.name;
  if (typeEl) typeEl.value = item.kind;
  if (linkEl) linkEl.value = item.link;
  if (saveBtn) { saveBtn.textContent = 'Save Changes'; saveBtn.disabled = false; }
  return true;
}
function oneNoteGuessSavedLinkKind(link) {
  var raw = String(link || '').trim();
  if (oneNoteLooksLikeLocalNotebookFolderLink(raw)) return 'notebook';
  if (/page-id=|pageid=|[?&#]page=/i.test(raw)) return 'page';
  if (/section-id=|sectionid=|\.one(?:#|\?|$)/i.test(raw)) return 'section';
  return 'notebook';
}
function oneNoteOpenSaveLinkDialog() {
  var linkEl = document.getElementById('oneNoteManualLink');
  var link = linkEl ? String(linkEl.value || '').trim() : '';
  if (!link) { showToast('Paste a OneNote notebook, section, or page link first', 'err'); if (linkEl) linkEl.focus(); return false; }
  if (link.length > 4096) { showToast('This OneNote link is too long to save', 'err'); return false; }
  var existing = oneNoteReadSavedLinks().filter(function(item){ return item.link === link; })[0];
  oneNoteSaveDialogEditingId = existing ? existing.id : '';
  var modal = document.getElementById('oneNoteSaveLinkModal');
  var title = document.getElementById('oneNoteSaveLinkModalTitle');
  var path = document.getElementById('oneNoteSaveLinkModalPath');
  var nameEl = document.getElementById('oneNoteSaveLinkModalName');
  var typeEl = document.getElementById('oneNoteSaveLinkModalType');
  var submit = document.getElementById('oneNoteSaveLinkModalSubmit');
  if (!modal || !nameEl || !typeEl) return false;
  if (title) title.textContent = existing ? 'Update Saved Link' : 'Save OneNote Link';
  if (path) path.textContent = link;
  nameEl.value = existing ? existing.name : '';
  typeEl.value = existing ? existing.kind : oneNoteGuessSavedLinkKind(link);
  if (submit) submit.textContent = existing ? 'Save Changes' : 'Save Link';
  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
  setTimeout(function(){ try { nameEl.focus(); nameEl.select(); } catch(e) {} }, 20);
  return true;
}
function oneNoteCloseSaveLinkDialog() {
  var modal = document.getElementById('oneNoteSaveLinkModal');
  if (modal) { modal.classList.remove('open'); modal.setAttribute('aria-hidden', 'true'); }
  oneNoteSaveDialogEditingId = '';
  return true;
}
function oneNoteConfirmSaveManualLink() {
  var linkEl = document.getElementById('oneNoteManualLink');
  var nameEl = document.getElementById('oneNoteSaveLinkModalName');
  var typeEl = document.getElementById('oneNoteSaveLinkModalType');
  var link = linkEl ? String(linkEl.value || '').trim() : '';
  var name = nameEl ? String(nameEl.value || '').trim() : '';
  var kind = oneNoteSavedLinkKind(typeEl ? typeEl.value : 'notebook');
  if (!link) { oneNoteCloseSaveLinkDialog(); showToast('Paste a OneNote notebook, section, or page link first', 'err'); return false; }
  if (link.length > 4096) { showToast('This OneNote link is too long to save', 'err'); return false; }
  if (!name) { showToast('Give this OneNote link a name', 'err'); if (nameEl) nameEl.focus(); return false; }
  name = name.slice(0, 80);
  var items = oneNoteReadSavedLinks();
  var existing = items.filter(function(item){ return item.id === oneNoteSaveDialogEditingId; })[0];
  if (!existing) existing = items.filter(function(item){ return item.link === link; })[0];
  var wasExisting = !!existing;
  var now = new Date().toISOString();
  if (existing) {
    existing.name = name;
    existing.kind = kind;
    existing.link = link;
    existing.updatedAt = now;
  } else {
    if (items.length >= ONE_NOTE_SAVED_LINKS_MAX) { showToast('Saved OneNote link limit reached (' + ONE_NOTE_SAVED_LINKS_MAX + ')', 'err'); return false; }
    existing = {id:oneNoteNewSavedLinkId(), name:name, kind:kind, link:link, createdAt:now, updatedAt:now};
    items.push(existing);
  }
  if (!oneNoteWriteSavedLinks(items)) return false;
  oneNoteCloseSaveLinkDialog();
  oneNoteRenderSavedLinks(existing.id);
  oneNoteSavedLinkSelected();
  showToast((wasExisting ? 'Updated' : 'Saved') + ' OneNote ' + kind + ' link: ' + name, 'ok');
  return true;
}
// Backward-compatible function name retained for older cached HTML/actions.
function oneNoteSaveManualLink() { return oneNoteOpenSaveLinkDialog(); }
function oneNoteSaveSelectedLinkChanges() {
  var sel = document.getElementById('oneNoteSavedLinkSelect');
  var selectedId = sel ? String(sel.value || '') : '';
  if (!selectedId) { showToast('Choose a saved OneNote link to edit', 'err'); return false; }
  var linkEl = document.getElementById('oneNoteManualLink');
  var nameEl = document.getElementById('oneNoteSavedLinkName');
  var typeEl = document.getElementById('oneNoteSavedLinkType');
  var link = linkEl ? String(linkEl.value || '').trim() : '';
  var name = nameEl ? String(nameEl.value || '').trim() : '';
  var kind = oneNoteSavedLinkKind(typeEl ? typeEl.value : 'notebook');
  if (!link) { showToast('The selected saved link has no manual link value', 'err'); if (linkEl) linkEl.focus(); return false; }
  if (link.length > 4096) { showToast('This OneNote link is too long to save', 'err'); return false; }
  if (!name) { showToast('Give this saved link a name', 'err'); if (nameEl) nameEl.focus(); return false; }
  name = name.slice(0, 80);
  var items = oneNoteReadSavedLinks();
  var existing = items.filter(function(item){ return item.id === selectedId; })[0];
  if (!existing) { oneNoteRenderSavedLinks(); showToast('Saved link was not found', 'err'); return false; }
  existing.name = name;
  existing.kind = kind;
  existing.link = link;
  existing.updatedAt = new Date().toISOString();
  if (!oneNoteWriteSavedLinks(items)) return false;
  oneNoteRenderSavedLinks(existing.id);
  oneNoteSavedLinkSelected();
  showToast('Saved changes to OneNote ' + kind + ' link: ' + name, 'ok');
  return true;
}
function oneNoteDeleteSavedLink() {
  var sel = document.getElementById('oneNoteSavedLinkSelect');
  var id = sel ? String(sel.value || '') : '';
  if (!id) { showToast('Choose a saved OneNote link to delete', 'err'); return false; }
  var items = oneNoteReadSavedLinks();
  var item = items.filter(function(row){ return row.id === id; })[0];
  if (!item) { oneNoteRenderSavedLinks(); showToast('Saved link was not found', 'err'); return false; }
  if (typeof window.confirm === 'function' && !window.confirm('Delete saved ' + oneNoteSavedLinkKindLabel(item.kind).toLowerCase() + ' link "' + item.name + '"?')) return false;
  items = items.filter(function(row){ return row.id !== id; });
  if (!oneNoteWriteSavedLinks(items)) return false;
  oneNoteRenderSavedLinks();
  var nameEl = document.getElementById('oneNoteSavedLinkName');
  var typeEl = document.getElementById('oneNoteSavedLinkType');
  var saveBtn = document.getElementById('oneNoteSaveLinkBtn');
  if (nameEl) nameEl.value = '';
  if (typeEl) typeEl.value = 'notebook';
  if (saveBtn) { saveBtn.textContent = 'Save Changes'; saveBtn.disabled = true; }
  showToast('Deleted saved OneNote link: ' + item.name, 'ok');
  return true;
}
// Retained as a compatibility helper. The visible Saved links row no longer
// has a Use button; selecting an entry fills the upper manual-link field.
async function oneNoteUseSavedLink() {
  if (!oneNoteSavedLinkSelected()) { showToast('Choose a saved OneNote link first', 'err'); return false; }
  return oneNoteLoadPagesFromManualLink();
}
document.addEventListener('keydown', function(event){
  if (event.key === 'Escape') {
    var modal = document.getElementById('oneNoteSaveLinkModal');
    if (modal && modal.classList.contains('open')) oneNoteCloseSaveLinkDialog();
  }
});
function oneNoteSetSectionPickerHint(message, state) {
  var hint = document.getElementById('oneNoteSectionPickerHint');
  if (!hint) return;
  hint.className = 'onenote-section-picker-hint' + (state ? (' ' + state) : '');
  hint.innerHTML = message || 'Choose a section';
  hint.title = 'Load sections, choose one, then scan. Notebook links list all available sections; section/page links can open directly.';
}
function oneNoteAcknowledgeSectionPickerAttention(event) {
  var row = document.getElementById('oneNoteWebPickerRow');
  if (!row || !row.classList.contains('onenote-picker-attention')) return false;
  var target = event && event.target ? event.target : null;
  if (target && target !== row && !target.closest('select,input,button,label,.onenote-field-wrap')) return false;
  row.classList.remove('onenote-picker-attention');
  return true;
}
function oneNoteEnsureSectionPickerVisible(attention) {
  var row = document.getElementById('oneNoteWebPickerRow');
  if (!row) return;
  row.style.display = 'grid';
  row.hidden = false;
  row.setAttribute('aria-hidden', 'false');
  if (attention) {
    row.classList.remove('onenote-picker-attention');
    void row.offsetWidth;
    row.classList.add('onenote-picker-attention');
  }
}
function oneNoteSourceModeChanged(silent) {
  var mode = oneNoteSelectedSourceMode();
  try { if(!silent&&localStorage.getItem('onenote_source_mode')!==mode)cvStudioDurableSettingSet('onenote_source_mode', mode); } catch(e) {}
  var settingsModeEl = document.getElementById('settingsOneNoteSourceMode');
  if (settingsModeEl && settingsModeEl.value !== mode) settingsModeEl.value = mode;
  var manual = document.getElementById('oneNoteManualPickerRow');
  var savedLinksPanel = document.getElementById('oneNoteSavedLinksPanel');
  // The section picker is required in every mode. v24.6.145 populated it
  // in Desktop mode but hid the entire row, so users saw the “Detected N
  // sections” message without any dropdown to choose from.
  oneNoteEnsureSectionPickerVisible(false);
  if (manual) manual.style.display = (mode === 'web') ? 'none' : 'grid';
  if (savedLinksPanel) savedLinksPanel.style.display = (mode === 'web') ? 'none' : 'block';
  if (mode === 'web') oneNoteSetSectionPickerHint('Choose a section', '');
  else if (mode === 'desktop') oneNoteSetSectionPickerHint('Paste or choose a saved link', 'warn');
  else oneNoteSetSectionPickerHint('Choose a section or link', '');
  var list = document.getElementById('oneNotePageList');
  if (list && !silent) { list.style.display = 'none'; list.textContent = ''; }
}
function oneNoteFillSelect(el, items, placeholder) {
  if (!el) return;
  el.innerHTML = '<option value="">' + esc(placeholder || 'Select') + '</option>';
  (items || []).forEach(function(it){
    var opt = document.createElement('option');
    opt.value = it.id || '';
    opt.textContent = oneNotePickerOptionLabel(it);
    if (it._source) opt.title = it._source;
    el.appendChild(opt);
  });
}
async function oneNoteLoadAllNotebookSections(notebooks) {
  var merged = [];
  var seen = {};
  for (var i=0; i<(notebooks || []).length; i++) {
    var nb = notebooks[i] || {};
    if (!nb.id) continue;
    try {
      var r = await fetch('/onenote/sections?top=200&notebook_id=' + encodeURIComponent(nb.id));
      var d = await r.json().catch(function(){ return {}; });
      if (!r.ok) continue;
      (d.items || []).forEach(function(sec){
        if (!sec || !sec.id || seen[sec.id]) return;
        seen[sec.id] = true;
        sec._label = oneNoteSectionLabel(sec, nb.displayName || nb.name || 'Notebook');
        sec._source = 'Notebook: ' + (nb.displayName || nb.name || '');
        merged.push(sec);
      });
    } catch(e) {}
  }
  merged.sort(function(a,b){ return String(a._label || '').localeCompare(String(b._label || '')); });
  return merged;
}
function oneNoteSetAllPageChecks(selected) {
  var checks = Array.prototype.slice.call(document.querySelectorAll('#oneNotePageList .oneNotePageCheck'));
  checks.forEach(function(ch){ ch.checked = !!selected; });
  if (checks.length) showToast((selected ? 'Selected ' : 'Unselected ') + checks.length + ' scanned OneNote page(s)', 'info');
}
function oneNoteRenderPagePicker(pages) {
  _oneNotePickerPages = pages || [];
  var list = document.getElementById('oneNotePageList');
  if (!list) return;
  list.style.display = 'block';
  if (!_oneNotePickerPages.length) {
    list.innerHTML = 'No pages found for this section/search/date range.';
    return;
  }
  var tools = '<div class="onenote-page-select-tools"><b>' + _oneNotePickerPages.length + ' page' + (_oneNotePickerPages.length === 1 ? '' : 's') + '</b>'
    + '<div class="onenote-page-select-actions"><button type="button" class="sec" onclick="oneNoteSetAllPageChecks(true)">Select all</button>'
    + '<button type="button" class="sec" onclick="oneNoteSetAllPageChecks(false)">Unselect all</button></div></div>';
  list.innerHTML = tools + _oneNotePickerPages.map(function(p, idx){
    var title = p.title || 'Untitled OneNote page';
    var modified = p.lastModifiedDateTime || '-';
    var created = p.createdDateTime || '-';
    return '<label class="onenote-page-choice"><input type="checkbox" class="oneNotePageCheck" data-idx="' + idx + '" checked />'
      + '<div><b>' + esc(title) + '</b><span>Modified: ' + esc(modified) + ' / Created: ' + esc(created) + '</span></div></label>';
  }).join('');
}

async function oneNoteLoadDesktopPicker(silent) {
  var list = document.getElementById('oneNotePageList');
  var nbSel = document.getElementById('oneNoteNotebookSelect');
  var secSel = document.getElementById('oneNoteSectionSelect');
  if (list && !silent) { list.style.display = 'block'; list.innerHTML = '<span class="spinner"></span> Loading desktop OneNote sections…'; }
  try {
    var manualLink = ((document.getElementById('oneNoteManualLink') || {}).value || '').trim();
    var desktopSectionsUrl = '/onenote/desktop_sections?top=300' + (manualLink ? ('&input=' + encodeURIComponent(manualLink)) : '');
    var r = await fetch(desktopSectionsUrl);
    var d = await r.json().catch(function(){ return {}; });
    if (!r.ok) throw new Error(d.error || d.hint || 'Could not load desktop OneNote sections');
    var notebooks = (d.notebooks || []).map(function(nb){
      return {id:'desktop_nb:' + (nb.displayName || nb.id || ''), displayName:(nb.displayName || 'Desktop notebook'), _source:'desktop'};
    });
    var sections = (d.items || []).map(function(sec){
      sec.id = 'desktop:' + (sec.id || '');
      sec._label = sec._label || ((sec.displayName || 'Untitled section') + (sec._parentNotebookName ? (' · ' + sec._parentNotebookName) : ' · Desktop OneNote'));
      sec._source = 'desktop';
      return sec;
    }).filter(function(sec){ return sec.id && sec.id !== 'desktop:'; });
    _oneNoteDesktopSectionsCache = sections.slice();
    oneNoteFillSelect(nbSel, notebooks, 'Desktop notebooks');
    oneNoteFillSelect(secSel, sections, 'Select desktop section');
    oneNoteEnsureSectionPickerVisible(sections.length > 0);
    _oneNotePickerPages = [];
    var manualCount = parseInt(d.manual_sections_count || 0, 10) || 0;
    var warningCount = (d.manual_warnings || []).length;
    if (list && !silent) { list.innerHTML = ''; list.style.display = 'none'; }
    if (manualCount > 1) {
      oneNoteSetSectionPickerHint('<b>' + manualCount + ' sections</b> · choose one' + (warningCount ? (' · ' + warningCount + ' skipped') : ''), 'ready');
    } else if (manualCount === 1) {
      oneNoteSetSectionPickerHint('<b>1 section</b> · select it', 'ready');
    } else {
      oneNoteSetSectionPickerHint(sections.length ? ('<b>' + sections.length + ' sections</b> · choose one') : 'No sections found', sections.length ? 'ready' : 'warn');
    }
    showToast((manualCount > 1 ? ('Notebook folder sections detected: ' + manualCount + ' · choose one') : ('Desktop OneNote sections loaded: ' + sections.length)), sections.length ? 'ok' : 'info');
    return true;
  } catch(e) {
    oneNoteEnsureSectionPickerVisible(false);
    oneNoteSetSectionPickerHint('Section loading failed', 'warn');
    if (list && !silent) list.textContent = (e.message || String(e)) + '\nTip: keep Microsoft 365 desktop OneNote open. Paste a local notebook-folder link or full onenote:///...Section.one link before loading or scanning; pywin32 is optional because CV Studio also has a PowerShell COM fallback.';
    showToast(e.message || 'Desktop OneNote picker failed', 'err');
    return false;
  }
}

async function oneNoteLoadPicker() {
  var mode = oneNoteSelectedSourceMode();
  if (mode === 'desktop') return await oneNoteLoadDesktopPicker(false);
  await oneNoteRestoreMicrosoftToken();
  var list = document.getElementById('oneNotePageList');
  if (list) { list.style.display = 'block'; list.innerHTML = '<span class="spinner"></span> Loading OneNote notebooks and sections…'; }
  var nbSel = document.getElementById('oneNoteNotebookSelect');
  var secSel = document.getElementById('oneNoteSectionSelect');
  try {
    var nr = await fetch('/onenote/notebooks?top=100');
    var nd = await nr.json().catch(function(){ return {}; });
    if (!nr.ok) throw new Error(nd.error || 'Could not load OneNote notebooks');
    var notebooks = nd.items || [];
    oneNoteFillSelect(nbSel, notebooks, 'All notebooks');
    var allSections = await oneNoteLoadAllNotebookSections(notebooks);
    if (mode === 'both') {
      try {
        var dr = await fetch('/onenote/desktop_sections?top=300');
        var dd = await dr.json().catch(function(){ return {}; });
        if (dr.ok) {
          var deskSecs = (dd.items || []).map(function(sec){
            sec.id = 'desktop:' + (sec.id || '');
            sec._label = sec._label || ((sec.displayName || 'Untitled section') + (sec._parentNotebookName ? (' · ' + sec._parentNotebookName) : ' · Desktop OneNote'));
            sec._source = 'desktop';
            return sec;
          }).filter(function(sec){ return sec.id && sec.id !== 'desktop:'; });
          _oneNoteDesktopSectionsCache = deskSecs.slice();
          allSections = allSections.concat(deskSecs);
        }
      } catch(e) {}
    }
    if (!allSections.length) {
      await oneNoteLoadSectionsForSelectedNotebook(true);
    } else {
      oneNoteFillSelect(secSel, allSections, 'Select section');
    }
    var loadedSectionCount = Math.max((allSections || []).length, secSel && secSel.options ? Math.max(0, secSel.options.length - 1) : 0);
    oneNoteEnsureSectionPickerVisible(loadedSectionCount > 0);
    oneNoteSetSectionPickerHint(loadedSectionCount ? ('<b>' + loadedSectionCount + ' sections</b> · choose one') : 'No sections found', loadedSectionCount ? 'ready' : 'warn');
    if (list) { list.innerHTML = ''; list.style.display = 'none'; }
    showToast('OneNote sections loaded', 'ok');
    return true;
  } catch(e) {
    if (list) list.textContent = e.message || String(e);
    showToast(e.message || 'OneNote picker failed', 'err');
    return false;
  }
}
async function oneNoteLoadSectionsForSelectedNotebook(silent) {
  await oneNoteRestoreMicrosoftToken();
  var nbSel = document.getElementById('oneNoteNotebookSelect');
  var secSel = document.getElementById('oneNoteSectionSelect');
  var notebookId = nbSel ? (nbSel.value || '') : '';
  var list = document.getElementById('oneNotePageList');
  if (String(notebookId || '').indexOf('desktop_nb:') === 0) {
    var nbName = String(notebookId || '').replace(/^desktop_nb:/, '').toLowerCase();
    var filtered = (_oneNoteDesktopSectionsCache || []).filter(function(sec){
      var parent = String(sec._parentNotebookName || sec._label || '').toLowerCase();
      return !nbName || parent.indexOf(nbName) >= 0;
    });
    oneNoteFillSelect(secSel, filtered, 'Select desktop section');
    oneNoteEnsureSectionPickerVisible(filtered.length > 0);
    oneNoteSetSectionPickerHint(filtered.length ? ('<b>' + filtered.length + ' sections</b> · choose one') : 'No sections found', filtered.length ? 'ready' : 'warn');
    _oneNotePickerPages = [];
    if (list && !silent) { list.style.display = 'none'; list.textContent = ''; }
    return;
  }
  if (oneNoteSelectedSourceMode() === 'desktop') {
    await oneNoteLoadDesktopPicker(silent);
    return;
  }
  if (!notebookId && !silent) {
    await oneNoteLoadPicker();
    return;
  }
  var url = '/onenote/sections?top=200' + (notebookId ? ('&notebook_id=' + encodeURIComponent(notebookId)) : '');
  var r = await fetch(url);
  var d = await r.json().catch(function(){ return {}; });
  if (!r.ok) { showToast(d.error || 'Could not load OneNote sections', 'err'); return; }
  var items = d.items || [];
  if (notebookId) {
    var nbName = nbSel && nbSel.options && nbSel.selectedIndex >= 0 ? nbSel.options[nbSel.selectedIndex].textContent : '';
    items.forEach(function(sec){ sec._label = oneNoteSectionLabel(sec, nbName && nbName !== 'All notebooks' ? nbName : ''); });
  }
  oneNoteFillSelect(secSel, items, 'Select section');
  oneNoteEnsureSectionPickerVisible(items.length > 0);
  oneNoteSetSectionPickerHint(items.length ? ('<b>' + items.length + ' sections</b> · choose one') : 'No sections found', items.length ? 'ready' : 'warn');
  _oneNotePickerPages = [];
  if (list && !silent) { list.style.display = 'none'; list.textContent = ''; }
}
function oneNoteClearPagePickerForSectionChange() {
  _oneNotePickerPages = [];
  var secSel = document.getElementById('oneNoteSectionSelect');
  var label = secSel && secSel.selectedIndex > 0 && secSel.options ? secSel.options[secSel.selectedIndex].textContent : '';
  oneNoteSetSectionPickerHint(label ? ('Selected: <b>' + esc(label) + '</b>') : 'Choose a section', label ? 'ready' : 'warn');
  var list = document.getElementById('oneNotePageList');
  if (list) { list.style.display = 'none'; list.textContent = ''; }
}
async function oneNoteFetchManualPages() {
  var inp = document.getElementById('oneNoteManualLink');
  var manual = inp ? (inp.value || '').trim() : '';
  if (!manual) throw new Error('Paste a OneNote section/page link, Graph ID, or section name first');
  var f = oneNotePickerFilters();
  var qs = '?input=' + encodeURIComponent(manual)
    + '&top=' + encodeURIComponent(f.top)
    + '&search=' + encodeURIComponent(f.search)
    + '&date_from=' + encodeURIComponent(f.date_from)
    + '&date_to=' + encodeURIComponent(f.date_to)
    + '&date_mode=' + encodeURIComponent(f.date_mode);
  var r = await fetch('/onenote/manual_pages' + qs);
  var d = await r.json().catch(function(){ return {}; });
  if (!r.ok) throw new Error(d.error || 'Could not resolve manual input. Try a OneNote web section/page link, notebook name, or paste notes below.');
  return d;
}
async function oneNoteFetchDesktopPages(manualOverride) {
  var inp = document.getElementById('oneNoteManualLink');
  var manual = manualOverride != null ? String(manualOverride || '').trim() : (inp ? (inp.value || '').trim() : '');
  if (!manual) throw new Error('Paste a desktop OneNote section/page link or type the exact section tab name first');
  var f = oneNotePickerFilters();
  var qs = '?input=' + encodeURIComponent(manual)
    + '&top=' + encodeURIComponent(f.top)
    + '&search=' + encodeURIComponent(f.search)
    + '&date_from=' + encodeURIComponent(f.date_from)
    + '&date_to=' + encodeURIComponent(f.date_to)
    + '&date_mode=' + encodeURIComponent(f.date_mode);
  var r = await fetch('/onenote/desktop_pages' + qs);
  var d = await r.json().catch(function(){ return {}; });
  if (!r.ok) {
    var msg = d.error || d.hint || 'Could not read desktop OneNote. Try Load Notebooks / Sections, or paste notes manually.';
    if (d.detail) msg += '\nDetail: ' + d.detail;
    throw new Error(msg);
  }
  return d;
}
async function oneNoteFetchSelectedSectionPages() {
  var secSel = document.getElementById('oneNoteSectionSelect');
  var sectionId = secSel ? (secSel.value || '') : '';
  if (!sectionId) throw new Error('Select a OneNote section first');
  var f = oneNotePickerFilters();
  var isDesktop = String(sectionId || '').indexOf('desktop:') === 0;
  var qs = '?section_id=' + encodeURIComponent(sectionId)
    + '&top=' + encodeURIComponent(f.top)
    + '&search=' + encodeURIComponent(f.search)
    + '&date_from=' + encodeURIComponent(f.date_from)
    + '&date_to=' + encodeURIComponent(f.date_to)
    + '&date_mode=' + encodeURIComponent(f.date_mode);
  var r = await fetch((isDesktop ? '/onenote/desktop_pages' : '/onenote/section_pages') + qs);
  var d = await r.json().catch(function(){ return {}; });
  if (!r.ok) throw new Error(d.error || (isDesktop ? 'Could not load desktop OneNote pages' : 'Could not load OneNote pages'));
  return d;
}
async function oneNoteScanBySourceMode() {
  await oneNoteRestoreMicrosoftToken();
  var mode = oneNoteSelectedSourceMode();
  var list = document.getElementById('oneNotePageList');
  if (list) { list.style.display = 'block'; list.innerHTML = '<span class="spinner"></span> Scanning OneNote source…'; }
  try {
    if (mode === 'web') {
      var wd = await oneNoteFetchSelectedSectionPages();
      oneNoteRenderPagePicker(wd.items || []);
      showToast('Loaded ' + ((wd.items || []).length) + ' web/synced page(s)', 'ok');
      return true;
    }
    if (mode === 'desktop') {
      var md;
      var secSel = document.getElementById('oneNoteSectionSelect');
      var sectionId = secSel ? (secSel.value || '') : '';
      var manualDesktop = ((document.getElementById('oneNoteManualLink') || {}).value || '').trim();
      // In Desktop mode, ignore stale web/Graph section ids. Use a selected
      // desktop section, otherwise use the pasted desktop link/name.
      if (sectionId && String(sectionId).indexOf('desktop:') === 0) {
        md = await oneNoteFetchSelectedSectionPages();
      } else if (manualDesktop) {
        if (oneNoteLooksLikeLocalNotebookFolderLink(manualDesktop)) {
          await oneNoteLoadDesktopPicker(false);
          throw new Error('Local OneNote notebook folder detected. Choose a section from the Section dropdown, then click Scan Source again.');
        }
        md = await oneNoteFetchDesktopPages(manualDesktop);
      } else {
        throw new Error('Desktop mode: click Load Notebooks / Sections and pick a desktop section, or paste a desktop OneNote section/page link/name first.');
      }
      oneNoteRenderPagePicker(md.items || []);
      showToast('Desktop OneNote resolved: ' + ((md.items || []).length) + ' page(s)' + (md.resolved_as ? (' · ' + md.resolved_as) : ''), (md.items || []).length ? 'ok' : 'info');
      return true;
    }
    var all = [];
    var seen = {};
    var notes = [];
    var hadInput = false;
    var secSel = document.getElementById('oneNoteSectionSelect');
    var sectionId = secSel ? (secSel.value || '') : '';
    if (sectionId) {
      hadInput = true;
      try {
        var sd = await oneNoteFetchSelectedSectionPages();
        (sd.items || []).forEach(function(p){ if (p && p.id && !seen[p.id]) { seen[p.id] = true; all.push(p); } });
        notes.push('web/synced ' + ((sd.items || []).length));
      } catch(e1) { notes.push('web/synced failed: ' + (e1.message || e1)); }
    }
    var manual = ((document.getElementById('oneNoteManualLink') || {}).value || '').trim();
    if (manual) {
      hadInput = true;
      try {
        var md2;
        try { md2 = await oneNoteFetchDesktopPages(); }
        catch(desktopErr2) { md2 = await oneNoteFetchManualPages(); md2._desktop_warning = desktopErr2.message || String(desktopErr2); }
        (md2.items || []).forEach(function(p){ if (p && p.id && !seen[p.id]) { seen[p.id] = true; all.push(p); } });
        notes.push('manual/desktop ' + ((md2.items || []).length));
      } catch(e2) { notes.push('manual failed: ' + (e2.message || e2)); }
    }
    if (!hadInput) throw new Error('Choose a section, paste a manual link/name, or both.');
    oneNoteRenderPagePicker(all);
    if (list && !all.length) list.textContent = 'No pages found. ' + notes.join(' · ');
    showToast('Both mode loaded ' + all.length + ' unique page(s)' + (notes.length ? (' · ' + notes.join(', ')) : ''), all.length ? 'ok' : 'info');
    return true;
  } catch(e) {
    if (list) list.textContent = e.message || String(e);
    showToast(e.message || 'OneNote scan failed', 'err');
    return false;
  }
}
async function oneNoteLoadPagesFromManualLink() {
  await oneNoteRestoreMicrosoftToken();
  var inp = document.getElementById('oneNoteManualLink');
  var manual = inp ? (inp.value || '').trim() : '';
  if (!manual) { showToast('Paste a OneNote section/page link, Graph ID, or section name first', 'err'); return false; }
  var f = oneNotePickerFilters();
  var list = document.getElementById('oneNotePageList');
  if (oneNoteLooksLikeLocalNotebookFolderLink(manual)) {
    var pickerOk = await oneNoteLoadDesktopPicker(false);
    if (pickerOk) showToast('Local notebook folder detected. Choose the section you want to scan.', 'ok');
    return pickerOk;
  }
  if (list) { list.style.display = 'block'; list.innerHTML = '<span class="spinner"></span> Resolving manual OneNote link/name…'; }
  var d;
  try {
    d = await oneNoteFetchDesktopPages();
  } catch(desktopErr) {
    try {
      d = await oneNoteFetchManualPages();
      d._desktop_warning = desktopErr.message || String(desktopErr);
    } catch(graphErr) {
      if (list) list.textContent = (graphErr.message || 'Could not resolve manual OneNote input') + '\nDesktop attempt: ' + (desktopErr.message || desktopErr);
      showToast(graphErr.message || 'Could not resolve manual input. Try typing exact section tab name or paste notes below.', 'err');
      return false;
    }
  }
  oneNoteRenderPagePicker(d.items || []);
  showToast('Manual OneNote input resolved: ' + ((d.items || []).length) + ' page(s)' + (d.resolved_as ? (' · ' + d.resolved_as) : ''), 'ok');
  return true;
}
async function oneNoteLoadPagesForSelectedSection() {
  var secSel = document.getElementById('oneNoteSectionSelect');
  var sectionId = secSel ? (secSel.value || '') : '';
  if (!sectionId) { showToast('Select a OneNote section first', 'err'); return false; }
  if (String(sectionId || '').indexOf('desktop:') !== 0) await oneNoteRestoreMicrosoftToken();
  var list = document.getElementById('oneNotePageList');
  if (list) { list.style.display = 'block'; list.innerHTML = '<span class="spinner"></span> Loading pages from selected section…'; }
  try {
    var d = await oneNoteFetchSelectedSectionPages();
    oneNoteRenderPagePicker(d.items || []);
    var filt = d.filters || {};
    showToast('Loaded ' + ((d.items || []).length) + ' page(s) from selected section' + (d.source === 'desktop' ? ' · desktop' : '') + (filt.date_mode ? (' · ' + filt.date_mode + ' date') : ''), (d.items || []).length ? 'ok' : 'info');
    return true;
  } catch(e) {
    if (list) list.textContent = e.message || 'Could not load OneNote pages';
    showToast(e.message || 'Could not load OneNote pages', 'err');
    return false;
  }
}
async function oneNoteImportSelectedPages() {
  await oneNoteRestoreMicrosoftToken();
  var checks = Array.prototype.slice.call(document.querySelectorAll('.oneNotePageCheck:checked'));
  var pages = checks.map(function(ch){ return _oneNotePickerPages[parseInt(ch.getAttribute('data-idx') || '-1', 10)]; }).filter(Boolean);
  if (!pages.length) { showToast('No pages selected. Scan first, then tick at least one page.', 'err'); return false; }
  var rawEl = document.getElementById('oneNoteRaw');
  var list = document.getElementById('oneNotePageList');
  if (list) { list.style.display = 'block'; list.innerHTML = '<span class="spinner"></span> Importing checked OneNote page(s)…'; }
  var r = await fetch('/onenote/import_selected', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({page_ids:pages.map(function(p){return p.id;}), pages:pages})});
  var d = await r.json().catch(function(){ return {}; });
  if (!r.ok) { if (list) list.textContent = d.error || 'Selected OneNote import failed'; showToast(d.error || 'Selected OneNote import failed', 'err'); return false; }
  if (rawEl) rawEl.value = d.combined_text || '';
  if (list) {
    var imported = d.pages || [];
    list.innerHTML = imported.length ? imported.map(function(p){ return '<div><b>' + esc(p.title || 'Untitled') + '</b><br><span>Imported selected page · Modified: ' + esc(p.lastModifiedDateTime || '-') + '</span></div>'; }).join('<hr style="border:none;border-top:1px solid var(--border);margin:6px 0;">') : 'No selected pages imported.';
  }
  showToast('Imported ' + ((d.pages || []).length) + ' checked OneNote page(s)', 'ok');
  if ((d.combined_text || '').trim()) await oneNoteParseAndMatch();
  return true;
}
async function oneNoteImportRecentPages() {
  await oneNoteRestoreMicrosoftToken();
  var search = ((document.getElementById('oneNoteSearch') || {}).value || '').trim();
  var dateFrom = ((document.getElementById('oneNoteDateFrom') || {}).value || '').trim();
  var dateTo = ((document.getElementById('oneNoteDateTo') || {}).value || '').trim();
  var dateMode = ((document.getElementById('oneNoteDateMode') || {}).value || 'either').trim() || 'either';
  var top = parseInt(((document.getElementById('oneNoteTop') || {}).value || '10'), 10) || 10;
  top = Math.max(1, Math.min(top, 100));
  var rawEl = document.getElementById('oneNoteRaw');
  var list = document.getElementById('oneNotePageList');
  if (list) { list.style.display = 'block'; list.innerHTML = '<span class="spinner"></span> Importing OneNote pages…'; }
  var r = await fetch('/onenote/import_recent', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({search:search, top:top, date_from:dateFrom, date_to:dateTo, date_mode:dateMode})});
  var d = await r.json().catch(function(){ return {}; });
  if (!r.ok) { if (list) list.textContent = d.error || 'OneNote import failed'; showToast(d.error || 'OneNote import failed', 'err'); return false; }
  if (rawEl) rawEl.value = d.combined_text || '';
  if (list) {
    var pages = d.pages || [];
    list.innerHTML = pages.length ? pages.map(function(p){ return '<div><b>' + esc(p.title || 'Untitled') + '</b><br><span>Modified: ' + esc(p.lastModifiedDateTime || '-') + ' / Created: ' + esc(p.createdDateTime || '-') + '</span></div>'; }).join('<hr style="border:none;border-top:1px solid var(--border);margin:6px 0;">') : 'No OneNote pages found for this search/date range.';
  }
  showToast('Imported ' + ((d.pages || []).length) + ' OneNote page(s)', 'ok');
  if ((d.combined_text || '').trim()) await oneNoteParseAndMatch();
  return true;
}
function updateOneNoteConnStatus() {
  oneNoteMsLoadSettings();
  oneNoteRefreshCost();
  var badge = document.getElementById('oneNoteConnBadge');
  if (badge) {
    fetch('/jobadder/api_info').then(function(r){ return r.json(); }).then(function(d){
      applyJAPublicInfo(d || {});renderJAConnectionState(d || {});
    }).catch(function(){ badge.textContent = 'JobAdder unknown'; });
  }
  fetch('/onenote/api_info',{cache:'no-store'}).then(function(r){ return r.json(); }).then(function(d){
    var ms = document.getElementById('oneNoteMsBadge');
    if (!ms) return;
    window._oneNoteConnected=!!(d&&d.connected);
    window._oneNoteAccountEmail=String((d&&d.account_email)||'');
    ms.textContent = d && d.connected ? ('Microsoft OneNote Connected' + (d.account_email ? ' · ' + d.account_email : '')) : 'OneNote not connected';
    ms.className = 'onenote-status ' + (d && d.connected ? 'ok' : 'warn');
  }).catch(function(){
    var ms = document.getElementById('oneNoteMsBadge');
    if (ms) { ms.textContent = 'OneNote unknown'; ms.className = 'onenote-status warn'; }
  });
}
async function oneNoteParseAndMatch() {
  updateOneNoteConnStatus();
  var rawEl = document.getElementById('oneNoteRaw');
  var results = document.getElementById('oneNoteResults');
  var summary = document.getElementById('oneNoteSummary');
  var raw = oneNoteNormalizeText(rawEl && rawEl.value);
  if (!raw) { showToast('Paste or import OneNote screening notes first', 'err'); return false; }

  var pageBlocks = oneNoteSplitImportedPageBlocks(raw);
  _oneNoteRows = [];
  pageBlocks.forEach(function(page){
    var blockText = String((page || {}).text || '').trim();
    if (!blockText) return;
    var clusters = oneNoteCandidateClusters(blockText);
    if (!clusters.length) clusters = [{text:blockText, emails:oneNoteEmails(blockText).map(function(x){return x.email;})}];
    clusters.forEach(function(cluster, clusterIndex){
      var clusterText = String((cluster || {}).text || '').trim();
      if (!clusterText) return;
      var occurrences = oneNoteEmailOccurrences(clusterText);
      var emails = oneNoteEmails(clusterText);
      var sourceTitle = String((page || {}).title || 'Imported OneNote page');
      if (clusters.length > 1) sourceTitle += ' · Note ' + (clusterIndex + 1);
      if (emails.length === 1) {
        // A free-form text box can place the email above or below the answers.
        // The whole visual block belongs to that one candidate.
        var em = emails[0];
        var fields = oneNoteExtractFields(clusterText, em.email);
        _oneNoteRows.push({ email:em.email, block:clusterText, source_title:sourceTitle, fields:fields, selected:true, status:'pending', statusText:'Matching…', candidate_id:'', matched_name:'', raw_match:null, missing:[] });
      } else if (emails.length > 1) {
        // Retain the proven bounded splitter for the rarer case where several
        // candidates were typed into one single OneNote text box.
        emails.forEach(function(em){
          var previousDifferent = null, nextDifferent = null;
          for (var oi = 0; oi < occurrences.length; oi++) {
            var occ = occurrences[oi];
            if (occ.index < em.index && occ.email !== em.email) previousDifferent = occ;
            if (occ.index > em.index && occ.email !== em.email) { nextDifferent = occ; break; }
          }
          var block = oneNoteNearestBlock(clusterText, em, nextDifferent, previousDifferent);
          var fields = oneNoteExtractFields(block, em.email);
          _oneNoteRows.push({ email:em.email, block:block, source_title:sourceTitle, fields:fields, selected:true, status:'pending', statusText:'Matching…', candidate_id:'', matched_name:'', raw_match:null, missing:[] });
        });
      } else {
        var fields = oneNoteExtractFields(clusterText, '');
        // Use the page title as the candidate name only when the entire page is
        // one email-less note. For an orphan visual block, keep a clear block
        // label rather than pretending the page title is the person's name.
        if (!fields.name && clusters.length === 1 && page && page.title) fields.name = page.title;
        _oneNoteRows.push({ email:'', block:clusterText, source_title:sourceTitle, fields:fields, selected:false, status:'warn', statusText:'Add email to match', candidate_id:'', matched_name:'', raw_match:null, missing:[] });
      }
    });
  });
  if (!_oneNoteRows.length) {
    if (summary) summary.textContent = 'Imported text is empty.';
    if (results) results.innerHTML = '<div class="onenote-muted" style="padding:18px;border:1px dashed var(--border);border-radius:14px;">No readable screening-note content found.</div>';
    showToast('Imported pages contained no readable text', 'info');
    return true;
  }

  var withEmail = _oneNoteRows.filter(function(row){ return oneNoteValidCandidateEmail(row.email); });
  var withoutEmail = _oneNoteRows.length - withEmail.length;
  if (summary) summary.textContent = withEmail.length ? ('Matching ' + withEmail.length + ' email(s) against JobAdder…') : (_oneNoteRows.length + ' note(s) imported · add candidate email to match');
  if (results) oneNoteRenderRows();

  for (var i=0;i<_oneNoteRows.length;i++) {
    var row = _oneNoteRows[i];
    if (!oneNoteValidCandidateEmail(row.email)) { oneNoteRefreshRowStatus(row); continue; }
    try {
      await oneNoteLookupCandidateForRow(row);
    } catch(e) {
      if (e && e.jobAdderAccountInvalidated) return false;
      row.status = 'err'; row.statusText = (e.message || 'Match failed').split('\n')[0]; row.selected = false;
    }
    oneNoteRenderRows();
  }
  var matched = _oneNoteRows.filter(function(x){ return x.candidate_id; }).length;
  var ready = _oneNoteRows.filter(function(x){ return x.candidate_id && !oneNoteMissingFields(x.fields).length; }).length;
  var needsEmail = _oneNoteRows.filter(function(x){ return !String(x.email || '').trim(); }).length;
  oneNoteUpdateSummaryFromRows();
  if (ready) showToast('OneNote ready: ' + ready + ' candidate(s)', 'ok');
  else if (needsEmail) showToast('Pages imported. Add candidate email to unmatched note(s) when ready.', 'info');
  else showToast(matched ? 'Matched but missing Presentability rating' : 'Pages imported; no JobAdder candidates matched', 'info');
  return true;
}

function oneNoteInput(idx, key, label, required) {
  var row = _oneNoteRows[idx] || {}, f = row.fields || {};
  var val = f[key] || '';
  var missing = required && !String(val || '').trim();
  return '<div class="onenote-field ' + (missing ? 'missing' : (required ? '' : 'optional')) + '"><b>' + esc(label) + (required ? ' *' : '') + '</b>'
    + '<textarea class="onenote-edit-field ' + (missing ? 'missing' : '') + '" rows="1" data-onenote-row="' + idx + '" data-onenote-key="' + escAttr(key) + '" oninput="oneNoteSetFieldLive(' + idx + ',\'' + escJsAttr(key) + '\',this.value)" onchange="oneNoteSetField(' + idx + ',\'' + escJsAttr(key) + '\',this.value)">' + esc(val) + '</textarea></div>';
}
function oneNoteRatingInput(idx) {
  var row = _oneNoteRows[idx] || {}, f = row.fields || {};
  var val = String(f.presentability_rating || '').trim();
  var missing = !/^[1-4]$/.test(val);
  var opts = ['','1','2','3','4'].map(function(x){ return '<option value="' + escAttr(x) + '" ' + (x === val ? 'selected' : '') + '>' + (x ? (x + ' / 4') : 'Select 1-4') + '</option>'; }).join('');
  return '<div class="onenote-field ' + (missing ? 'missing' : '') + '"><b>Presentability *</b>'
    + '<select class="onenote-rating-select" data-onenote-row="' + idx + '" data-onenote-key="presentability_rating" oninput="oneNoteSetFieldLive(' + idx + ',\'presentability_rating\',this.value)" onchange="oneNoteSetField(' + idx + ',\'presentability_rating\',this.value)">' + opts + '</select></div>';
}
function oneNoteRenderRows() {
  var el = document.getElementById('oneNoteResults');
  if (!el) return;
  if (!_oneNoteRows.length) { el.innerHTML = '<div class="onenote-muted" style="padding:18px;border:1px dashed var(--border);border-radius:14px;">No notes parsed yet.</div>'; return; }
  el.innerHTML = _oneNoteRows.map(function(row, idx){
    var f = row.fields || {};
    oneNoteRefreshRowStatus(row);
    var missing = oneNoteMissingFields(f);
    var fields = [
      oneNoteInput(idx, 'brief_overview', 'Summary / Brief Overview of Experience', false),
      oneNoteInput(idx, 'reason_leaving', 'Reason For Leaving', false),
      oneNoteInput(idx, 'looking_for', 'Looking for', false),
      oneNoteInput(idx, 'current_salary_breakdown', 'Current Salary Breakdown', false),
      oneNoteInput(idx, 'expected_salary', 'Expected Salary', false),
      oneNoteInput(idx, 'notice_period', 'Notice Period', false),
      oneNoteInput(idx, 'leads', 'Leads', false),
      oneNoteInput(idx, 'remarks', 'Remarks', false),
      oneNoteRatingInput(idx)
    ].join('');
    var missingBox = missing.length ? '<div class="onenote-missing-list"><b>Missing mandatory:</b> ' + esc(missing.map(function(x){return x[1];}).join(', ')) + '</div>' : '<div class="onenote-complete-note">Ready: Presentability rating is filled.</div>';
    var errBox = row.transfer_error ? ('<div class="onenote-error-detail">' + esc(row.transfer_error) + '</div><div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px;"><button type="button" class="onenote-error-copy" onclick="oneNoteCopyTransferError(' + idx + ')">Copy JobAdder error</button><button type="button" class="onenote-error-copy" onclick="oneNoteCopyBrowserScript(' + idx + ')">Copy Emergency Create Script</button><button type="button" class="onenote-error-copy" onclick="oneNoteCopyBrowserPayload(' + idx + ')">Copy Emergency Payload</button></div><div class="onenote-muted" style="margin-top:5px;">The official OAuth activity write failed. The browser script is an emergency CREATE-only fallback using the logged-in JobAdder tab; it never updates an existing Screening Call.</div>') : '';
    var warningBox = row.transfer_warning ? ('<div style="margin-top:7px;padding:8px 10px;border:1px solid #f59e0b;border-radius:9px;background:rgba(245,158,11,.08);font-size:11px;line-height:1.45;color:var(--text2);"><b>Profile update warning:</b> ' + esc(row.transfer_warning) + '</div>') : '';
    var profileState = String(row.profile_create_state || '');
    var profileBox = row.profile_create_message ? ('<div class="onenote-profile-create-note ' + escAttr(profileState) + '">' + esc(row.profile_create_message) + '</div>') : '';
    var corrections = Array.isArray(f._spelling_corrections) ? f._spelling_corrections : [];
    var correctionBox = corrections.length ? ('<div class="onenote-muted" style="margin-top:6px;font-size:10px;" title="Original Notes are unchanged.">Spelling correction: ' + esc(corrections.join(' · ')) + '</div>') : '';
    var profileRunning = profileState === 'running';
    var uploadCvButton = (!row.candidate_id && row.no_match_found && oneNoteValidCandidateEmail(row.email) && !profileRunning)
      ? '<button type="button" class="primary" onclick="oneNoteUploadCvForRow(' + idx + ')" style="font-size:10px;padding:4px 8px;">Upload CV</button>' : '';
    var link = row.candidate_id ? jaProfileUrl(row.candidate_id) : '';
    return '<div class="onenote-row ' + escAttr(row.status || '') + '">'
      + '<input type="checkbox" ' + (row.selected ? 'checked' : '') + ' ' + (!row.candidate_id || missing.length ? 'disabled' : '') + ' onchange="_oneNoteRows[' + idx + '].selected=this.checked">'
      + '<div><div class="onenote-name">' + esc(f.name || row.matched_name || row.email || row.source_title || 'Imported OneNote page') + '</div>'
      + '<div class="onenote-meta" style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">'
      + '<input type="email" class="onenote-email-input ' + (!String(row.email || '').trim() ? 'onenote-email-missing' : (!oneNoteValidCandidateEmail(row.email) ? 'onenote-email-invalid' : '')) + '" value="' + escAttr(row.email || '') + '" placeholder="Enter candidate email" title="Email is optional for importing. Add it when you want to match and transfer this note to JobAdder." data-onenote-row="' + idx + '" data-onenote-key="email" oninput="oneNoteEmailInputVisual(this,' + idx + ')" onchange="oneNoteSetRowEmail(' + idx + ',this.value)">'
      + (!row.candidate_id && !profileRunning ? '<button type="button" class="sec" onclick="oneNoteMatchRow(' + idx + ')" style="font-size:10px;padding:4px 8px;">Match</button>' : '')
      + uploadCvButton
      + (row.matched_name ? '<span>JobAdder: ' + esc(row.matched_name) + '</span>' : '') + (row.candidate_id ? '<span>· ID ' + esc(row.candidate_id) + '</span>' : '') + '</div>'
      + '<div class="onenote-fields">' + fields + '</div>'
      + missingBox + profileBox + correctionBox + errBox + warningBox + '</div>'
      + '<div style="display:flex;flex-direction:column;gap:6px;align-items:flex-end;"><span class="onenote-status ' + escAttr(row.status || '') + '">' + esc(row.statusText || '') + '</span>'
      + (link ? '<a class="sec" href="' + escAttr(jaActivityUrl(row.candidate_id)) + '" target="_blank" rel="noopener" style="font-size:11px;text-decoration:none;">Open Activity</a><a class="sec" href="' + escAttr(link) + '" target="_blank" rel="noopener" style="font-size:11px;text-decoration:none;">Open Profile</a>' : '')
      + '</div></div>';
  }).join('');
}
function oneNoteSelectMatchedOnly() {
  var count = 0;
  _oneNoteRows.forEach(function(r){
    oneNoteRefreshRowStatus(r);
    r.selected = !!r.candidate_id && r.status !== 'done' && !oneNoteMissingFields(r.fields).length;
    if (r.selected) count++;
  });
  oneNoteRenderRows();
  showToast(count ? ('Selected ' + count + ' transfer-ready note(s)') : 'No notes currently meet the transfer criteria', count ? 'ok' : 'info');
}
function oneNoteUnselectAllRows() {
  _oneNoteRows.forEach(function(r){ r.selected = false; });
  oneNoteRenderRows();
  showToast('Unselected all screening-note rows', 'info');
}
function oneNoteShortTransferError(d, httpStatus) {
  d = d || {};
  var base = d.error || d.why || d.detail || ('JobAdder transfer failed' + (httpStatus ? ': ' + httpStatus : ''));
  var attempts = Array.isArray(d.attempts) ? d.attempts : [];
  if (attempts.length) {
    var first = attempts.find(function(a){ return a && (a.detail || a.error); }) || attempts[0];
    if (first) {
      var msg = first.detail || first.error || '';
      if (msg) base += ' — ' + msg;
    }
  }
  return String(base || 'Transfer failed').slice(0, 260);
}
function oneNotePrettyTransferError(d, httpStatus) {
  d = d || {};
  var lines = [];
  lines.push('Transfer failed. No Candidate Note or existing Screening Call was modified.');
  if (httpStatus) lines.push('HTTP: ' + httpStatus);
  if (d.error) lines.push('Error: ' + d.error);
  if (d.why) lines.push('Why: ' + d.why);
  if (d.next_step) lines.push('Next: ' + d.next_step);
  if (d.candidate_id) lines.push('Candidate ID: ' + d.candidate_id);
  if (d.email) lines.push('Email: ' + d.email);
  var attempts = Array.isArray(d.attempts) ? d.attempts : [];
  if (attempts.length) {
    lines.push('');
    lines.push('JobAdder attempts:');
    attempts.slice(0, 10).forEach(function(a, i){
      var msg = a.detail || a.error || a.raw || '';
      lines.push((i+1) + '. ' + (a.path || 'unknown path') + ' → ' + (a.status || 'error') + (msg ? ' — ' + String(msg).slice(0, 350) : ''));
    });
  }
  return lines.join('\n');
}
function oneNoteCopyTransferError(idx) {
  var row = _oneNoteRows[idx] || {};
  var text = row.transfer_error_detail || row.transfer_error || 'No transfer error detail.';
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(function(){ showToast('Copied JobAdder error detail', 'ok'); }).catch(function(){ window.prompt('Copy JobAdder error detail:', text); });
  } else {
    window.prompt('Copy JobAdder error detail:', text);
  }
}
function oneNoteCopyTextWithPrompt(text, okMsg, promptTitle) {
  text = String(text || '');
  if (!text) { showToast('Nothing to copy', 'err'); return; }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(function(){ showToast(okMsg || 'Copied', 'ok'); }).catch(function(){ window.prompt(promptTitle || 'Copy:', text); });
  } else {
    window.prompt(promptTitle || 'Copy:', text);
  }
}
async function oneNoteGetBrowserBridge(idx) {
  var row = _oneNoteRows[idx] || {};
  if (!row.candidate_id) throw new Error('No JobAdder candidate ID for this row');
  // v24.6.137: always build a fresh emergency helper. Older cached helper scripts can linger
  // inside the current browser tab after an app update and may still send blank
  // fields or old routes.
  var payload = { candidate_id: row.candidate_id, email: row.email, fields: row.fields || {}, note_text: oneNoteBuildStructuredNote(row), salary_canonical: row.salary_canonical || null, spelling_correction: oneNoteSpellingCorrectionEnabled() };
  var r = await fetchWithTimeout('/jobadder/onenote_browser_bridge', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)}, 16000);
  var d = await r.json().catch(function(){ return {}; });
  if (!r.ok || !d.ok) throw new Error(d.error || 'Could not build JobAdder browser helper');
  row.browser_bridge = d.browser_bridge || null;
  return row.browser_bridge;
}
async function oneNoteCopyBrowserScript(idx) {
  try {
    var bridge = await oneNoteGetBrowserBridge(idx);
    // v24.6.137: copy executable JavaScript only. Plain-English instructions
    // in the clipboard make Chrome DevTools throw "Invalid or unexpected token"
    // when pasted directly into the Console.
    var scriptText = String((bridge && bridge.script) || '');
    oneNoteCopyTextWithPrompt(scriptText, 'Copied JobAdder create script', 'Copy this script only, then paste it into JobAdder Console:');
  } catch(e) {
    showToast(e.message || 'Could not build browser script', 'err');
  }
}
async function oneNoteCopyBrowserPayload(idx) {
  try {
    var bridge = await oneNoteGetBrowserBridge(idx);
    oneNoteCopyTextWithPrompt(JSON.stringify((bridge && bridge.payload) || {}, null, 2), 'Copied JobAdder browser payload', 'Copy JobAdder browser payload:');
  } catch(e) {
    showToast(e.message || 'Could not build browser payload', 'err');
  }
}
async function oneNoteTransferSelected() {
  if (!_oneNoteRows.length) { showToast('Parse & Match notes first', 'err'); return false; }
  // A focused textarea/select may not have emitted change yet. Read the live DOM
  // before validation so what the recruiter can see is what gets transferred.
  oneNoteSyncVisibleInputs();
  oneNoteRenderRows();
  var noteType = (document.getElementById('oneNoteType') && document.getElementById('oneNoteType').value || 'Screening Call').trim() || 'Screening Call';
  // Validate only rows the recruiter selected for this transfer. A different
  // matched row may intentionally remain unchecked while its Presentability is
  // still blank/invalid; it must not block ready selected candidates.
  var incomplete = _oneNoteRows.filter(function(r){ return r.selected && r.candidate_id && oneNoteMissingFields(r.fields).length; });
  if (incomplete.length) { showToast(incomplete.length + ' selected row(s) missing Presentability rating', 'err'); oneNoteRenderRows(); return false; }
  var targets = _oneNoteRows.filter(function(r){ return r.selected && r.candidate_id && !oneNoteMissingFields(r.fields).length; });
  if (!targets.length) { showToast('No matched candidates with Presentability selected to transfer', 'err'); return false; }
  if (!window.confirm('Transfer ' + targets.length + ' selected Screening Call activity/activities to JobAdder?\n\nThese should log under Activities for the currently connected JobAdder account.')) return false;
  var ok = 0, fail = 0, profileWarnings = 0;
  for (var i=0;i<_oneNoteRows.length;i++) {
    var row = _oneNoteRows[i];
    if (!row.selected || !row.candidate_id || oneNoteMissingFields(row.fields).length) continue;
    row.status = 'pending'; row.statusText = 'Transferring…'; row.transfer_error = ''; row.transfer_error_detail = ''; row.transfer_warning = ''; row.browser_bridge = null; oneNoteRenderRows();
    try {
      var payload = { candidate_id: row.candidate_id, email: row.email, note_type: noteType, fields: row.fields, note_text: oneNoteBuildStructuredNote(row), create_as: 'activity', salary_ai: oneNoteSalaryAiConfig(), spelling_correction: oneNoteSpellingCorrectionEnabled() };
      var r = await fetchWithTimeout('/jobadder/onenote_log_screening', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)}, 90000);
      var d = await r.json().catch(function(){ return {}; });
      if (!r.ok || !d.ok) {
        row.browser_bridge = d && d.browser_bridge ? d.browser_bridge : null;
        if (d && d.salary_canonical) { row.salary_canonical = d.salary_canonical; oneNoteUpdateSalaryAiBadge(d.salary_canonical); }
        oneNoteRecordFailedAiCost(row, d || {});
        row.transfer_error = oneNoteShortTransferError(d, r.status);
        row.transfer_error_detail = oneNotePrettyTransferError(d, r.status) + '\n\nFull JSON:\n' + JSON.stringify(d || {}, null, 2);
        throw new Error(row.transfer_error);
      }
      row.transfer_count = Number(row.transfer_count || 0) + 1;
      row.status = 'done'; row.statusText = row.transfer_count > 1 ? 'Transferred again ✓' : 'Transferred ✓'; row.selected = false; row.retransfer_ready = false; row.transfer_error = ''; row.transfer_error_detail = ''; row.browser_bridge = null; row.activity_url = d.activity_url || jaActivityUrl(row.candidate_id);
      row.transfer_warning = String((d && d.warning) || '').trim(); row.salary_canonical = (d && d.salary_canonical) || null; oneNoteUpdateSalaryAiBadge(row.salary_canonical);
      if (row.transfer_warning) { row.statusText = row.transfer_count > 1 ? 'Transferred again ✓ · profile warning' : 'Transferred ✓ · profile warning'; profileWarnings++; }
      oneNoteRecordTransfer(row, d); ok++;
    } catch(e) {
      row.status = 'err'; row.statusText = (e.message || 'Transfer failed').split('\n')[0].slice(0, 80);
      if (!row.transfer_error) row.transfer_error = (e.message || 'Transfer failed');
      fail++;
    }
    oneNoteRenderRows();
  }
  if (ok) { var lastCanon=((_oneNoteRows.filter(function(x){return x.salary_canonical;}).slice(-1)[0]||{}).salary_canonical||{}); var lastProc=lastCanon.processing||{}; var cs=lastCanon.currencySelection||{}; var aiMsg=lastProc.aiUsed ? (' Salary components/currency extracted by '+providerLabel(lastProc.provider,lastProc.model)+(lastProc.cacheHit?' from cache':'')+'; deterministic code calculated final values. AI cost $'+Number(lastProc.costUsd||0).toFixed(4)+'.') : ' Salary calculation/currency detection used the local deterministic fallback; AI cost $0.0000.'; var currencyMsg=cs.jobAdderOption ? (' JobAdder Currency set to '+cs.jobAdderOption+(cs.selectionRule==='expected_salary_currency_wins'?' using Expected Salary priority.':'.')) : ''; oneNoteShowSuccess('Transferred successfully: ' + ok + ' Screening Call activit' + (ok === 1 ? 'y' : 'ies') + ' to JobAdder.' + (profileWarnings ? (' ' + profileWarnings + ' candidate profile update(s) need review.') : ' Salary/notice profile updates completed or were safely skipped when blank.') + aiMsg + currencyMsg); oneNoteSwitchMiniTab('record'); }
  showToast('OneNote transfer done: ' + ok + ' ok' + (profileWarnings ? ', ' + profileWarnings + ' profile warning' + (profileWarnings === 1 ? '' : 's') : '') + (fail ? ', ' + fail + ' failed' : ''), fail ? 'err' : (profileWarnings ? 'info' : 'ok'));
  return fail ? false : true;
}
var _oneNoteActivityDiagnosticReportText = '';
var _oneNoteActivityDiagnosticFilename = 'jobadder_activity_diagnostic.json';
function oneNoteSetActivityDiagnosticStatus(text, cls) {
  var el = document.getElementById('oneNoteActivityDiagnosticStatus');
  if (!el) return;
  el.textContent = text || 'Not run';
  el.className = 'onenote-status' + (cls ? (' ' + cls) : '');
}
function oneNoteInitActivityDiagnostic() {
  try {
    var cid = localStorage.getItem('cvstudio_activity_diag_candidate_id') || '';
    var aid = localStorage.getItem('cvstudio_activity_diag_activity_id') || '';
    var c = document.getElementById('oneNoteActivityDiagnosticCandidateId');
    var a = document.getElementById('oneNoteActivityDiagnosticActivityId');
    if (c && cid) c.value = cid;
    if (a && aid) a.value = aid;
  } catch(e) {}
}
async function oneNoteRunActivityDiagnostic() {
  var candidateEl = document.getElementById('oneNoteActivityDiagnosticCandidateId');
  var activityEl = document.getElementById('oneNoteActivityDiagnosticActivityId');
  var output = document.getElementById('oneNoteActivityDiagnosticOutput');
  var button = document.getElementById('oneNoteActivityDiagnosticRunBtn');
  var candidateId = String(candidateEl && candidateEl.value || '').trim();
  var activityId = String(activityEl && activityEl.value || '').trim();
  if (!/^\d+$/.test(candidateId)) throw new Error('Candidate ID must contain digits only');
  if (!/^\d+$/.test(activityId)) throw new Error('Activity ID must contain digits only');
  try {
    localStorage.setItem('cvstudio_activity_diag_candidate_id', candidateId);
    localStorage.setItem('cvstudio_activity_diag_activity_id', activityId);
  } catch(e) {}
  if (button) button.disabled = true;
  oneNoteSetActivityDiagnosticStatus('Running…', 'pending');
  if (output) {
    output.style.display = 'block';
    output.textContent = 'Running two read-only JobAdder OAuth GET requests…';
  }
  try {
    var r = await fetchWithTimeout('/jobadder/onenote_activity_diagnostic', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({candidate_id:candidateId, activity_id:activityId})
    }, 70000);
    var raw = await r.text();
    var d = {};
    try { d = raw ? JSON.parse(raw) : {}; } catch(parseErr) { d = {error:'CV Studio returned non-JSON diagnostic output', raw_response:raw}; }
    _oneNoteActivityDiagnosticFilename = d.filename || ('jobadder_activity_diagnostic_' + candidateId + '_' + activityId + '.json');
    _oneNoteActivityDiagnosticReportText = JSON.stringify(d.report || d, null, 2);
    if (output) output.textContent = _oneNoteActivityDiagnosticReportText;
    if (!r.ok || !d.ok) {
      throw new Error(d.error || ('Diagnostic failed: HTTP ' + r.status));
    }
    var requests = d.report && Array.isArray(d.report.requests) ? d.report.requests : [];
    var statuses = requests.map(function(x){ return x && x.status != null ? x.status : 'network error'; }).join(', ');
    oneNoteSetActivityDiagnosticStatus('Done' + (statuses ? (' · ' + statuses) : ''), requests.some(function(x){ return x && x.ok; }) ? 'done' : 'warn');
    showToast('Activity diagnostic complete. Download the report and send it here.', 'ok');
    return true;
  } catch(e) {
    oneNoteSetActivityDiagnosticStatus('Failed', 'err');
    if (output && !_oneNoteActivityDiagnosticReportText) output.textContent = String(e && e.message || e);
    throw e;
  } finally {
    if (button) button.disabled = false;
  }
}
function oneNoteCopyActivityDiagnostic() {
  if (!_oneNoteActivityDiagnosticReportText) { showToast('Run the activity diagnostic first', 'err'); return; }
  oneNoteCopyTextWithPrompt(_oneNoteActivityDiagnosticReportText, 'Copied activity diagnostic report', 'Copy diagnostic report:');
}
function oneNoteDownloadActivityDiagnostic() {
  if (!_oneNoteActivityDiagnosticReportText) { showToast('Run the activity diagnostic first', 'err'); return; }
  try {
    var blob = new Blob([_oneNoteActivityDiagnosticReportText], {type:'application/json;charset=utf-8'});
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = _oneNoteActivityDiagnosticFilename || 'jobadder_activity_diagnostic.json';
    document.body.appendChild(a);
    a.click();
    setTimeout(function(){ URL.revokeObjectURL(url); a.remove(); }, 0);
    showToast('Diagnostic report downloaded', 'ok');
  } catch(e) {
    showToast(e.message || 'Could not download diagnostic report', 'err');
  }
}

var _oneNoteActivityCreateDiagnosticReportText = '';
var _oneNoteActivityCreateDiagnosticFilename = 'jobadder_activity_create_official_schema_diagnostic.json';
function oneNoteSetActivityCreateDiagnosticStatus(text, cls) {
  var el = document.getElementById('oneNoteActivityCreateDiagnosticStatus');
  if (!el) return;
  el.textContent = text || 'Not run';
  el.className = 'onenote-status' + (cls ? (' ' + cls) : '');
}
async function oneNoteRunActivityCreateDiagnostic() {
  var candidateEl = document.getElementById('oneNoteActivityCreateCandidateId');
  var confirmEl = document.getElementById('oneNoteActivityCreateConfirm');
  var output = document.getElementById('oneNoteActivityCreateDiagnosticOutput');
  var button = document.getElementById('oneNoteActivityCreateDiagnosticRunBtn');
  var candidateId = String(candidateEl && candidateEl.value || '').trim();
  var confirmation = String(confirmEl && confirmEl.value || '').trim();
  if (candidateId !== '41262878') throw new Error('Controlled test must remain locked to Max Low candidate 41262878');
  if (confirmation !== 'CREATE ONE MAX LOW TEST') throw new Error('Type CREATE ONE MAX LOW TEST exactly');
  if (!window.confirm('Create ONE new Candidate Screening Call on dummy candidate Max Low (41262878)?\n\nThis will send exactly one OAuth POST. It will not edit activity 503608 or create a Candidate Note.')) return false;
  if (button) button.disabled = true;
  if (confirmEl) confirmEl.disabled = true;
  oneNoteSetActivityCreateDiagnosticStatus('Running one POST…', 'pending');
  if (output) {
    output.style.display = 'block';
    output.textContent = 'Running preflight GET → one official-schema OAuth POST → verification GET…';
  }
  try {
    var r = await fetchWithTimeout('/jobadder/onenote_activity_create_diagnostic', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({candidate_id:candidateId, confirmation:confirmation})
    }, 100000);
    var raw = await r.text();
    var d = {};
    try { d = raw ? JSON.parse(raw) : {}; } catch(parseErr) { d = {error:'CV Studio returned non-JSON create diagnostic output', raw_response:raw}; }
    _oneNoteActivityCreateDiagnosticFilename = d.filename || ('jobadder_activity_create_official_schema_diag_' + candidateId + '.json');
    _oneNoteActivityCreateDiagnosticReportText = JSON.stringify(d.report || d, null, 2);
    if (output) output.textContent = _oneNoteActivityCreateDiagnosticReportText;
    if (!r.ok || !d.ok) throw new Error(d.error || ('Create diagnostic failed: HTTP ' + r.status));
    var report = d.report || {};
    var post = report.controlled_post || {};
    var createdId = report.created_activity_id;
    var success = !!(post.ok && createdId);
    oneNoteSetActivityCreateDiagnosticStatus(success ? ('Created · ' + createdId) : ('Finished · HTTP ' + (post.status == null ? 'network error' : post.status)), success ? 'done' : 'warn');
    showToast(success ? ('Controlled test created activity ' + createdId + '. Download the report and upload it here.') : 'Controlled test finished without a confirmed activity. Download the report and upload it here.', success ? 'ok' : 'err');
    return true;
  } catch(e) {
    oneNoteSetActivityCreateDiagnosticStatus('Failed', 'err');
    if (output && !_oneNoteActivityCreateDiagnosticReportText) output.textContent = String(e && e.message || e);
    throw e;
  } finally {
    // Intentionally keep the button and confirmation disabled after any network
    // attempt. The backend also enforces one POST per app session.
  }
}
function oneNoteCopyActivityCreateDiagnostic() {
  if (!_oneNoteActivityCreateDiagnosticReportText) { showToast('Run the controlled create test first', 'err'); return; }
  oneNoteCopyTextWithPrompt(_oneNoteActivityCreateDiagnosticReportText, 'Copied controlled create report', 'Copy controlled create report:');
}
function oneNoteDownloadActivityCreateDiagnostic() {
  if (!_oneNoteActivityCreateDiagnosticReportText) { showToast('Run the controlled create test first', 'err'); return; }
  try {
    var blob = new Blob([_oneNoteActivityCreateDiagnosticReportText], {type:'application/json;charset=utf-8'});
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = _oneNoteActivityCreateDiagnosticFilename || 'jobadder_activity_create_official_schema_diagnostic.json';
    document.body.appendChild(a);
    a.click();
    setTimeout(function(){ URL.revokeObjectURL(url); a.remove(); }, 0);
    showToast('Controlled create report downloaded', 'ok');
  } catch(e) {
    showToast(e.message || 'Could not download controlled create report', 'err');
  }
}

function oneNoteClear() {
  var raw = document.getElementById('oneNoteRaw');
  if (raw) raw.value = '';
  _oneNoteRows = [];
  var summary = document.getElementById('oneNoteSummary');
  if (summary) summary.textContent = 'No notes parsed yet.';
  oneNoteRenderRows();
}
function invalidateOneNoteJobAdderMatches() {
  window._oneNoteJobAdderAccountSeq = (Number(window._oneNoteJobAdderAccountSeq) || 0) + 1;
  _oneNoteRows.forEach(function(row) {
    row.candidate_id = '';
    row.raw_match = null;
    row.matched_name = '';
    row.no_match_found = false;
    row.selected = false;
    row.browser_bridge = null;
    row.activity_url = '';
    row.retransfer_ready = false;
    row.status = 'warn';
    row.statusText = oneNoteValidCandidateEmail(row.email)
      ? 'JobAdder signed out · Match again after reconnecting'
      : 'Add email to match';
  });
  var summary = document.getElementById('oneNoteSummary');
  if (summary && _oneNoteRows.length) {
    summary.textContent = 'JobAdder signed out. Reconnect, then Parse & Match again.';
  }
  oneNoteRenderRows();
}
