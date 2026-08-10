// ── Per-feature AI routing ───────────────────────────────────────────────
function aiRouteEsc(s) {
  return String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function aiRouteEscAttr(s) {
  return aiRouteEsc(s).replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
var AI_ROUTE_FEATURES = {
  cv_single:      { label:'Single CV Formatting',            def:'main',        desc:'Format CV / Blind CV.' },
  summary:        { label:'CV Summary',                     def:'main',        desc:'Standalone candidate summary tab.' },
  appraiser:      { label:'CV Scoring',                     def:'main',        desc:'JD vs CV compatibility scoring tab.' },
  the_owl:        { label:'The Owl',                         def:'main',        desc:'Titles, target companies, search strings.' },
  the_spider:     { label:'AI Crawler',                       def:'the_owl',     desc:'JobAdder resume sourcing from JD/Owl context.' },
  cv_batch:       { label:'Batch Format',                   def:'cv_single',   desc:'Batch format/blind runs. Default: same as Single CV.' },
  ja_create:      { label:'JobAdder Create Profile',         def:'cv_single',   desc:'Parses CVs before creating JobAdder profiles.' },
  onenote_salary: { label:'OneNote — Salary extraction',     def:'deepseek',    desc:'AI extracts salary components only; deterministic code calculates final values.' },
  jd_anonymizer:  { label:'Blind JD',                       def:'main',        desc:'Anonymises and rewrites job descriptions.' },
  company_profile:{ label:'Company Profile',                 def:'main',        desc:'Company URL fetch and profile generation.' },
  lead_search:    { label:'Lead Finder — Job Leads',         def:'lead',        desc:'Find Job Leads. DeepSeek should be paired with Tavily/SerpAPI.' },
  lead_people:    { label:'Lead Finder — People',            def:'lead_search', desc:'Find People for selected leads.' },
  lead_email:     { label:'Lead Finder — Emails',            def:'lead_search', desc:'Public business email fallback.' },
  salary_rules:   { label:'Salary Comparison — Tax rules',   def:'deepseek',    desc:'AI extracts tax/contribution rules from official sources for the Salary Comparison page. DeepSeek or Claude only; the saved key is used server-side.' }
};
var AI_ROUTE_ORDER = ['cv_single','summary','appraiser','the_owl','the_spider','cv_batch','ja_create','onenote_salary','jd_anonymizer','company_profile','lead_search','lead_people','lead_email','salary_rules'];
function _routeStore(feature) { return 'hy_ai_route_' + feature; }
function _routeModelStore(feature) { return 'hy_ai_route_model_' + feature; }
function featureDefaultRoute(feature) { return (AI_ROUTE_FEATURES[feature] && AI_ROUTE_FEATURES[feature].def) || 'main'; }
function getFeatureRouteSource(feature) {
  try { return localStorage.getItem(_routeStore(feature)) || featureDefaultRoute(feature); } catch(e) { return featureDefaultRoute(feature); }
}
function getFeatureRouteModelOverride(feature) {
  try { return (localStorage.getItem(_routeModelStore(feature)) || '').trim(); } catch(e) { return ''; }
}
function routeProviderKey(provider) {
  provider = provider === 'claude' ? 'anthropic' : (provider === 'gpt' ? 'openai' : String(provider || '').trim().toLowerCase());
  if (window._hKeysByProvider && window._hKeysByProvider[provider]) return window._hKeysByProvider[provider];
  return _secureAiValue(_aiSecretSlot('main',provider));
}
function routeProviderModel(provider) {
  provider = provider === 'claude' ? 'anthropic' : (provider === 'gpt' ? 'openai' : String(provider || '').trim().toLowerCase());
  if (provider === 'anthropic') {
    if (window._hModelsByProvider && window._hModelsByProvider['anthropic'] && !modelLooksWrongForProvider(window._hModelsByProvider['anthropic'], 'anthropic')) return window._hModelsByProvider['anthropic'];
    try { var sm = localStorage.getItem(_providerModelStore('anthropic')); if (sm && !modelLooksWrongForProvider(sm, 'anthropic')) return sm; } catch(e) {}
    return defaultModelForProvider('anthropic');
  }
  if (window._hModelsByProvider && window._hModelsByProvider[provider] && !modelLooksWrongForProvider(window._hModelsByProvider[provider], provider)) return window._hModelsByProvider[provider];
  try { var saved = localStorage.getItem(_providerModelStore(provider)); if (saved && !modelLooksWrongForProvider(saved, provider)) return saved; } catch(e) {}
  return defaultModelForProvider(provider);
}
function resolveAiRoute(feature, _seen) {
  _seen = _seen || {};
  if (!AI_ROUTE_FEATURES[feature]) feature = 'cv_single';
  if (_seen[feature]) {
    return { feature:feature, source:'main', provider:getProvider(), model:getModel(), api_key:getKey(), api_key_slot:_aiSecretSlot('main',getProvider()), label:'Main AI settings', warning:'AI route cycle detected; using Main AI.' };
  }
  _seen[feature] = true;
  var source = getFeatureRouteSource(feature);
  var modelOverride = getFeatureRouteModelOverride(feature);
  var route;
  if (source === 'cv_single') {
    route = resolveAiRoute('cv_single', _seen);
  } else if (source === 'the_owl') {
    route = resolveAiRoute('the_owl', _seen);
  } else if (source === 'lead_search') {
    route = resolveAiRoute('lead_search', _seen);
  } else if (source === 'lead') {
    route = { feature:feature, source:'lead', provider:getLeadProvider(), model:getLeadModel(), api_key:getLeadKey(), api_key_slot:_aiSecretSlot(getDedicatedLeadKey(getSavedLeadProvider())?'lead':'main',getLeadProvider()), label:'Lead Finder AI settings' };
  } else if (source === 'anthropic' || source === 'openai' || source === 'deepseek') {
    route = { feature:feature, source:source, provider:source, model:routeProviderModel(source), api_key:routeProviderKey(source), api_key_slot:_aiSecretSlot('main',source), label:providerLabel(source) + ' saved key' };
  } else {
    route = { feature:feature, source:'main', provider:getProvider(), model:getModel(), api_key:getKey(), api_key_slot:_aiSecretSlot('main',getProvider()), label:'Main AI settings' };
  }
  route = Object.assign({}, route);
  route.feature = feature;
  route.inherited_source = source;
  if (modelOverride && !modelLooksWrongForProvider(modelOverride, route.provider)) {
    route.model = modelOverride;
    route.model_override = true;
  } else if (modelOverride && modelLooksWrongForProvider(modelOverride, route.provider)) {
    route.warning = 'Ignored model override that does not match provider.';
  }
  route.provider_label = providerLabel(route.provider, route.model);
  route.display = route.provider_label + ' · ' + (route.model || defaultModelForProvider(route.provider));
  return route;
}
function aiRoutePayload(feature) {
  var r = resolveAiRoute(feature);
  return { api_key:r.api_key || '', api_key_slot:r.api_key_slot||_aiSecretSlot('main',r.provider), provider:r.provider || 'anthropic', model:r.model || defaultModelForProvider(r.provider), route:r };
}

var QUICK_AI_PANEL_CONFIG = {
  cv_single:       { claude:'singleAiClaude',    deepseek:'singleAiDeepSeek',    hint:'singleAiQuickHint',    label:'Single CV Formatting' },
  cv_batch:        { claude:'batchAiClaude',     deepseek:'batchAiDeepSeek',     hint:'batchAiQuickHint',     label:'Batch Format' },
  summary:         { claude:'summaryAiClaude',   deepseek:'summaryAiDeepSeek',   hint:'summaryAiQuickHint',   label:'CV Summary' },
  appraiser:       { claude:'appraiserAiClaude', deepseek:'appraiserAiDeepSeek', hint:'appraiserAiQuickHint', label:'CV Scoring' },
  the_owl:         { claude:'owlAiClaude',       deepseek:'owlAiDeepSeek',       hint:'owlAiQuickHint',       label:'The Owl' },
  jd_anonymizer:   { claude:'jdAnonAiClaude',    deepseek:'jdAnonAiDeepSeek',    hint:'jdAnonAiQuickHint',    label:'Blind JD' },
  company_profile: { claude:'companyAiClaude',   deepseek:'companyAiDeepSeek',   hint:'companyAiQuickHint',   label:'Company Profile' }
};
function quickAiPanelIds(feature) { return QUICK_AI_PANEL_CONFIG[feature] || null; }
function quickAiInheritedLabel(route) {
  if (!route) return '';
  var source = route.inherited_source || '';
  if (source === 'cv_single') return ' · inherited from Single CV';
  if (source === 'main') return ' · from Main AI settings';
  if (source === 'lead' || source === 'lead_search') return ' · inherited from Lead Finder';
  return '';
}
function syncQuickAiProviderPanel(feature) {
  var ids=quickAiPanelIds(feature);
  if (!ids) return;
  var route=resolveAiRoute(feature);
  var claude=document.getElementById(ids.claude), deepseek=document.getElementById(ids.deepseek), hint=document.getElementById(ids.hint);
  var provider=route && route.provider ? route.provider : '';
  var keyPresent=!!(route && route.api_key);
  if(claude){claude.classList.toggle('active',provider==='anthropic');claude.classList.toggle('missing',provider==='anthropic'&&!keyPresent);claude.setAttribute('aria-pressed',provider==='anthropic'?'true':'false');}
  if(deepseek){deepseek.classList.toggle('active',provider==='deepseek');deepseek.classList.toggle('missing',provider==='deepseek'&&!keyPresent);deepseek.setAttribute('aria-pressed',provider==='deepseek'?'true':'false');}
  if(hint){
    hint.textContent=(route && route.display ? route.display : 'Provider not configured')+quickAiInheritedLabel(route)+(keyPresent?' · saved key ready':' · save this provider key in Settings');
  }
}
function syncQuickAiProviderPanels(){Object.keys(QUICK_AI_PANEL_CONFIG).forEach(syncQuickAiProviderPanel);}
function syncSalaryAiRouteSnapshot() {
  // Publish the resolved Salary Comparison AI route (provider + model only,
  // never the key) to same-origin localStorage so the separate
  // /salary-comparison/ page can follow this dedicated route. The provider key
  // itself is resolved on the server from the shared AI secret store.
  try {
    var r = aiRoutePayload('salary_rules');
    var provider = (r.provider === 'anthropic' || r.provider === 'claude') ? 'claude'
      : (r.provider === 'deepseek' ? 'deepseek' : '');
    var snap = { provider: provider, model: provider ? (r.model || '') : '' };
    localStorage.setItem('cvstudio_salary_ai_route', JSON.stringify(snap));
  } catch(e) {}
}
function refreshAllAiRouteUi() {
  syncQuickAiProviderPanels();
  try { updateSummaryRouteBadge(); } catch(e) {}
  try { updateAppraiserRouteBadge(); } catch(e) {}
  try { updateTheOwlRouteBadge(); } catch(e) {}
  try { updateTheSpiderRouteBadge(); } catch(e) {}
  try { syncSalaryAiRouteSnapshot(); } catch(e) {}
}
function quickSetAiProvider(feature, provider) {
  var ids=quickAiPanelIds(feature);
  if (!ids) { showToast('This feature has no quick AI provider control','err'); return; }
  provider=provider==='deepseek'?'deepseek':'anthropic';
  try {
    var before=resolveAiRoute(feature);
    cvStudioDurableSettingSet(_routeStore(feature),provider);
    if(before && before.provider!==provider) cvStudioDurableSettingRemove(_routeModelStore(feature));
    refreshAllAiRouteUi();
    var rows=document.getElementById('aiRoutingRows');
    if(rows && rows.children && rows.children.length){var sel=document.getElementById('routeSel_'+feature);if(sel)sel.value=provider;previewAiRoutes();}
    var route=resolveAiRoute(feature);
    showToast(providerLabel(provider)+' selected for '+ids.label+(route.api_key?'':' — save its API key in Settings'),'info');
  } catch(e) { showToast('Could not switch AI provider','err'); }
}
function buildAiRouteOptions(feature) {
  var opts;
  if (feature === 'cv_batch' || feature === 'ja_create') {
    opts = [['cv_single','Same as Single CV Formatting'], ['main','Main AI settings'], ['anthropic','Claude saved key'], ['openai','OpenAI saved key'], ['deepseek','DeepSeek saved key']];
  } else if (feature === 'the_spider') {
    opts = [['the_owl','Same as The Owl'], ['main','Main AI settings'], ['anthropic','Claude saved key'], ['openai','OpenAI saved key'], ['deepseek','DeepSeek saved key']];
  } else if (feature === 'lead_people' || feature === 'lead_email') {
    opts = [['lead_search','Same as Lead Finder Job Leads'], ['lead','Lead Finder AI settings'], ['main','Main AI settings'], ['anthropic','Claude saved key'], ['openai','OpenAI saved key'], ['deepseek','DeepSeek saved key']];
  } else if (feature === 'lead_search') {
    opts = [['lead','Lead Finder AI settings'], ['main','Main AI settings'], ['anthropic','Claude saved key'], ['openai','OpenAI saved key'], ['deepseek','DeepSeek saved key']];
  } else if (feature === 'salary_rules') {
    opts = [['deepseek','DeepSeek saved key'], ['anthropic','Claude saved key'], ['main','Main AI settings']];
  } else {
    opts = [['main','Main AI settings'], ['anthropic','Claude saved key'], ['openai','OpenAI saved key'], ['deepseek','DeepSeek saved key']];
  }
  return opts.map(function(pair){ return '<option value="' + pair[0] + '">' + aiRouteEsc(pair[1]) + '</option>'; }).join('');
}
function renderAiRoutingRows() {
  var box = document.getElementById('aiRoutingRows');
  if (!box) return;
  box.innerHTML = AI_ROUTE_ORDER.map(function(feature){
    var meta = AI_ROUTE_FEATURES[feature];
    var model = getFeatureRouteModelOverride(feature);
    return '<div style="border:1px solid var(--border);border-radius:8px;padding:8px;background:var(--surface);">'
      + '<div style="font-size:12px;font-weight:700;color:var(--text1);margin-bottom:3px;">' + aiRouteEsc(meta.label) + '</div>'
      + '<select id="routeSel_' + feature + '" style="width:100%;font-size:12px;padding:5px 6px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text1);" onchange="previewAiRoutes()">' + buildAiRouteOptions(feature) + '</select>'
      + '<input id="routeModel_' + feature + '" type="text" value="' + aiRouteEscAttr(model) + '" placeholder="" style="margin-top:5px;width:100%;box-sizing:border-box;font-size:12px;padding:5px 8px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text1);" oninput="previewAiRoutes()"/>'
      + '<div id="routePreview_' + feature + '" style="font-size:11px;color:var(--text3);margin-top:4px;line-height:1.3;">—</div>'
      + '<div style="font-size:10.5px;color:var(--text3);margin-top:3px;line-height:1.25;">' + aiRouteEsc(meta.desc) + '</div>'
      + '</div>';
  }).join('');
  AI_ROUTE_ORDER.forEach(function(feature){ var sel = document.getElementById('routeSel_' + feature); if (sel) sel.value = getFeatureRouteSource(feature); });
  previewAiRoutes();
}
function ensureAiRoutingRowsVisible() {
  var box = document.getElementById('aiRoutingRows');
  if (!box) return;
  try {
    if (!box.children || box.children.length < AI_ROUTE_ORDER.length) {
      renderAiRoutingRows();
    } else {
      previewAiRoutes();
    }
  } catch(e) {
    // Never let a preview/render bug leave the settings section empty.
    try {
      box.innerHTML = AI_ROUTE_ORDER.map(function(feature){
        var meta = AI_ROUTE_FEATURES[feature] || {label:feature, desc:''};
        var selected = getFeatureRouteSource(feature);
        var model = getFeatureRouteModelOverride(feature);
        var html = '<div style="border:1px solid var(--border);border-radius:8px;padding:8px;background:var(--surface);">'
          + '<div style="font-size:12px;font-weight:700;color:var(--text1);margin-bottom:3px;">' + aiRouteEsc(meta.label) + '</div>'
          + '<select id="routeSel_' + feature + '" style="width:100%;font-size:12px;padding:5px 6px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text1);">' + buildAiRouteOptions(feature) + '</select>'
          + '<input id="routeModel_' + feature + '" type="text" value="' + aiRouteEscAttr(model) + '" placeholder="" style="margin-top:5px;width:100%;box-sizing:border-box;font-size:12px;padding:5px 8px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text1);"/>'
          + '<div id="routePreview_' + feature + '" style="font-size:11px;color:var(--text3);margin-top:4px;line-height:1.3;">Uses: preview unavailable, but route can still be saved.</div>'
          + '<div style="font-size:10.5px;color:var(--text3);margin-top:3px;line-height:1.25;">' + aiRouteEsc(meta.desc || '') + '</div>'
          + '</div>';
        return html;
      }).join('');
      AI_ROUTE_ORDER.forEach(function(feature){
        var sel = document.getElementById('routeSel_' + feature);
        if (sel) sel.value = getFeatureRouteSource(feature);
      });
    } catch(e2) {
      box.innerHTML = '<div style="grid-column:1/-1;color:#a33;font-size:12px;line-height:1.4;">AI routing controls could not render. Please refresh CV Studio and reinstall the latest ZIP if this persists.</div>';
    }
  }
}

function previewAiRoutes() {
  // Preview the whole routing table as one temporary state. This is important
  // for inherited rows like Batch -> Single CV: if Single is changed but not
  // saved yet, Batch preview should still show the pending inherited provider.
  var oldState = {};
  try {
    AI_ROUTE_ORDER.forEach(function(feature){
      oldState[feature] = {
        src: localStorage.getItem(_routeStore(feature)),
        model: localStorage.getItem(_routeModelStore(feature))
      };
      var sel = document.getElementById('routeSel_' + feature);
      var inp = document.getElementById('routeModel_' + feature);
      if (sel) localStorage.setItem(_routeStore(feature), sel.value || featureDefaultRoute(feature));
      if (inp) localStorage.setItem(_routeModelStore(feature), (inp.value || '').trim());
    });
    AI_ROUTE_ORDER.forEach(function(feature){
      var prev = document.getElementById('routePreview_' + feature);
      if (!prev) return;
      try {
        var r = resolveAiRoute(feature);
        prev.textContent = 'Uses: ' + r.display + (r.api_key ? '' : ' · no saved key yet') + (r.model_override ? ' · override' : '') + (r.warning ? ' · ' + r.warning : '');
      } catch(e) {
        prev.textContent = 'Uses: unavailable';
      }
    });
  } finally {
    try {
      AI_ROUTE_ORDER.forEach(function(feature){
        var old = oldState[feature] || {};
        if (old.src !== null && old.src !== undefined) localStorage.setItem(_routeStore(feature), old.src); else localStorage.removeItem(_routeStore(feature));
        if (old.model !== null && old.model !== undefined) localStorage.setItem(_routeModelStore(feature), old.model); else localStorage.removeItem(_routeModelStore(feature));
      });
    } catch(e2) {}
  }
  var hint = document.getElementById('aiRoutingHint');
  if (hint) hint.textContent = 'Tip: choose DeepSeek for high-volume CV formatting/batch runs, keep Claude/OpenAI for live-web or delicate reasoning. Tavily/SerpAPI still controls external job URL search.';
}
function saveAiRoutes() {
  try {
    AI_ROUTE_ORDER.forEach(function(feature){
      var sel = document.getElementById('routeSel_' + feature);
      var inp = document.getElementById('routeModel_' + feature);
      var src = sel ? (sel.value || featureDefaultRoute(feature)) : featureDefaultRoute(feature);
      var model = inp ? (inp.value || '').trim() : '';
      cvStudioDurableSettingSet(_routeStore(feature), src);
      if (model) cvStudioDurableSettingSet(_routeModelStore(feature), model); else cvStudioDurableSettingRemove(_routeModelStore(feature));
    });
    showToast('AI routes saved', 'ok');
    previewAiRoutes();
    try { refreshAllAiRouteUi(); } catch(e) {}
  } catch(e) { showToast('Could not save AI routes', 'err'); }
}
function resetAiRoutes() {
  try {
    AI_ROUTE_ORDER.forEach(function(feature){ cvStudioDurableSettingRemove(_routeStore(feature)); cvStudioDurableSettingRemove(_routeModelStore(feature)); });
    renderAiRoutingRows();
    refreshAllAiRouteUi();
    showToast('AI routes reset to safe defaults', 'ok');
  } catch(e) { showToast('Could not reset AI routes', 'err'); }
}

async function saveSearchProvider() {
  var sel = document.getElementById('searchProviderSel');
  var input = document.getElementById('searchProviderKeyInput');
  var provider = sel ? (sel.value || 'none') : 'none';
  var key = input ? input.value.trim() : '';
  window._hSearchProvider = provider;
  window._hSearchProviderKey = key;
  try {
    cvStudioDurableSettingSet('hy_search_provider', provider);
    localStorage.removeItem('hy_search_provider_key');
    if(provider!=='none') await _saveSecureAiSecret('search_'+provider,key,false);
  } catch(e) {}
  if (provider !== 'none' && !key) showToast('Search provider saved, but API key is blank', 'err');
  else showToast(provider === 'none' ? 'Search provider disabled — using AI web search' : 'Search provider saved', 'ok');
}
function getSearchProviderConfig() {
  // Runtime calls use saved Search Provider settings only. The visible fields
  // are committed by Save; Test uses getCurrentSearchProviderConfig().
  var provider = window._hSearchProvider || '';
  var key = window._hSearchProviderKey || '';
  try {
    provider = provider || localStorage.getItem('hy_search_provider') || 'none';
    key = key || _secureAiValue('search_'+provider);
  } catch(e) {}
  return { provider: provider || 'none', api_key: key || '' };
}
function getCurrentSearchProviderConfig() {
  var cfg = getSearchProviderConfig();
  var sel = document.getElementById('searchProviderSel');
  var input = document.getElementById('searchProviderKeyInput');
  if (sel && sel.value) cfg.provider = sel.value;
  if (input && input.value.trim()) cfg.api_key = input.value.trim();
  return cfg;
}
async function testSearchProvider() {
  var cfg = getCurrentSearchProviderConfig();
  if (!cfg.provider || cfg.provider === 'none') { showToast('Choose Tavily or SerpAPI first', 'err'); return; }
  if (!cfg.api_key) { showToast('Paste/search-provider API key first', 'err'); return; }
  var btn = document.getElementById('btnSearchProviderTest');
  if (btn) { btn.disabled = true; btn.textContent = '…'; }
  try {
    var res = await fetchWithTimeout('/lead-finder/test-search-provider', {
      method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(cfg)
    }, 25000);
    var data = await res.json();
    if (data.ok) showToast('Search provider works — ' + (data.count || 0) + ' result(s) returned', 'ok');
    else showToast(data.error || 'Search provider test failed', 'err');
  } catch(e) {
    showToast('Search provider test failed — check key/internet', 'err');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Test'; }
  }
}
async function saveEnrichmentProvider() {
  var sel = document.getElementById('enrichmentProviderSel');
  var input = document.getElementById('enrichmentProviderKeyInput');
  var provider = sel ? (sel.value || 'none') : 'none';
  var key = input ? input.value.trim() : '';
  window._hEnrichmentProvider = provider;
  window._hEnrichmentProviderKey = key;
  try {
    cvStudioDurableSettingSet('hy_enrichment_provider', provider);
    localStorage.removeItem('hy_enrichment_provider_key');
    if(provider!=='none') await _saveSecureAiSecret('enrichment_'+provider,key,false);
  } catch(e) {}
  if (provider !== 'none' && !key) showToast('Enrichment provider saved, but API key is blank', 'err');
  else showToast(provider === 'none' ? 'Enrichment provider disabled — using public web search only' : 'Enrichment provider saved', 'ok');
}
function getEnrichmentProviderConfig() {
  // Runtime email enrichment uses saved provider settings only. This prevents
  // an unsaved Apollo/None dropdown edit from changing a real email run.
  var provider = window._hEnrichmentProvider || '';
  var key = window._hEnrichmentProviderKey || '';
  try {
    provider = provider || localStorage.getItem('hy_enrichment_provider') || 'none';
    key = key || _secureAiValue('enrichment_'+provider);
  } catch(e) {}
  return { provider: provider || 'none', api_key: key || '' };
}
async function leadRefreshContactCacheStats() {
  var el = document.getElementById('leadContactCacheStatsText');
  if (!el) return;
  try {
    var res = await fetchWithTimeout('/lead-finder/contact-cache/stats', { method:'GET' }, 8000);
    var data = await res.json();
    if (data && data.ok) {
      el.textContent = 'Contact cache: ' + (data.total_entries || 0) + ' contact(s) looked up (' + (data.with_email || 0) + ' with an email found)';
    } else {
      el.textContent = 'Contact cache: unavailable';
    }
  } catch(e) {
    el.textContent = 'Contact cache: unavailable';
  }
}
async function leadClearContactCache() {
  try {
    var res = await fetchWithTimeout('/lead-finder/contact-cache/clear', { method:'POST' }, 8000);
    var data = await res.json();
    showToast(data && data.ok ? 'Contact cache cleared' : 'Could not clear cache', data && data.ok ? 'ok' : 'err');
  } catch(e) {
    showToast('Could not clear cache', 'err');
  }
  leadRefreshContactCacheStats();
}
async function leadRefreshTitleCacheStats() {
  var el = document.getElementById('leadTitleCacheStatsText');
  if (!el) return;
  try {
    var res = await fetchWithTimeout('/lead-finder/title-cache/stats', { method:'GET' }, 8000);
    var data = await res.json();
    if (data && data.ok) {
      var byFam = data.by_family || {};
      var famBits = Object.keys(byFam).map(function(k){ return k + ':' + byFam[k]; }).join(', ');
      el.textContent = 'Title angle cache: ' + (data.total_entries || 0) + ' saved role signature(s)' + (famBits ? ' (' + famBits + ')' : '');
    } else {
      el.textContent = 'Title angle cache: unavailable';
    }
  } catch(e) {
    el.textContent = 'Title angle cache: unavailable';
  }
}
async function leadClearTitleCache() {
  try {
    var res = await fetchWithTimeout('/lead-finder/title-cache/clear', { method:'POST' }, 8000);
    var data = await res.json();
    showToast(data && data.ok ? 'Title angle cache cleared' : 'Could not clear cache', data && data.ok ? 'ok' : 'err');
  } catch(e) {
    showToast('Could not clear cache', 'err');
  }
  leadRefreshTitleCacheStats();
}
function getModel() {
  // Runtime calls must use the saved model for the saved provider, not a
  // visible but unsaved Settings field. This mirrors the saved-provider guard
  // and prevents accidental provider/model drift when a user edits settings
  // but forgets to click Save.
  var provider = getProvider();
  if (window._hModelsByProvider && window._hModelsByProvider[provider] && !modelLooksWrongForProvider(window._hModelsByProvider[provider], provider)) return window._hModelsByProvider[provider];
  try {
    var saved = localStorage.getItem(_providerModelStore(provider));
    if (saved && !modelLooksWrongForProvider(saved, provider)) return saved;
  } catch(e) {}
  return defaultModelForProvider(provider);
}

async function testKey() {
  var input = document.getElementById('keyInput');
  var typedKey = input ? input.value.trim() : '';
  var key = typedKey || getKey();
  if (!key) { showToast('Paste your API key first', 'err'); return; }
  // When testing a newly typed unsaved key, use the visible provider selection.
  // When testing the saved key, use the saved provider to avoid key/provider mismatch.
  var providerForTest = typedKey ? getCurrentMainProviderSelection() : getProvider();
  var btn = document.getElementById('btnTest');
  btn.disabled = true; btn.textContent = '…';
  try {
    var res  = await fetchWithTimeout('/test', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({api_key:key,api_key_slot:_aiSecretSlot('main',providerForTest),provider:providerForTest}) }, 15000);
    var data = await res.json();
    if (data.ok) {
      setDot('ok');
      var testCost = responseCost(data, data.model, providerForTest);
      statsRecord('Main AI Provider Test', 'provider_test', testCost, data.model, '', data.provider || providerForTest,
        statsMetaFromResponse(data, data.model, providerForTest));
      showToast('Key is valid! Test cost ' + (testCost < 0.0001 ? '<$0.0001' : '$' + testCost.toFixed(4)), 'ok');
    }
    else { setDot('err'); showToast(data.error, 'err'); }
  } catch(e) {
    setDot('err'); showToast('Cannot reach server — is CV Studio running?', 'err');
  }
  btn.disabled = false; btn.textContent = 'Test';
}

async function testLeadKey() {
  var input = document.getElementById('leadKeyInput');
  var typedKey = input ? input.value.trim() : '';
  var dedicatedKey = typedKey || getDedicatedLeadKey();
  var key = dedicatedKey || getKey();
  if (!key) { showToast('Save your Lead Finder API key or Main AI key first', 'err'); return; }
  // Typed unsaved Lead Finder keys should be tested against the visible Lead
  // Finder provider selection. Saved/fallback keys must use the saved provider.
  var providerForTest = typedKey ? getCurrentLeadProviderSelection() : (dedicatedKey ? getLeadProvider() : getProvider());
  var btn = document.getElementById('btnLeadTest');
  btn.disabled = true; btn.textContent = '…';
  try {
    var res  = await fetchWithTimeout('/test', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({api_key:key,api_key_slot:_aiSecretSlot('lead',providerForTest),provider:providerForTest}) }, 15000);
    var data = await res.json();
    if (data.ok) {
      var testCost = responseCost(data, data.model, providerForTest);
      statsRecord('Lead Finder Provider Test', 'provider_test', testCost, data.model, '', data.provider || providerForTest,
        statsMetaFromResponse(data, data.model, providerForTest));
      showToast((dedicatedKey ? 'Lead Finder key is valid!' : 'Main AI key is valid for Lead Finder fallback!') + ' Test cost ' + (testCost < 0.0001 ? '<$0.0001' : '$' + testCost.toFixed(4)), 'ok');
    }
    else { showToast(data.error, 'err'); }
  } catch(e) {
    showToast('Cannot reach server — is CV Studio running?', 'err');
  }
  btn.disabled = false; btn.textContent = 'Test';
}

function setStep(msg) { /* replaced by setProgress */ }
