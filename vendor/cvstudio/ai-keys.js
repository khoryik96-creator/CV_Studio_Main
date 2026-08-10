function defaultModelForProvider(provider) {
  provider = String(provider || '').trim().toLowerCase();
  if (provider === 'deepseek') return 'deepseek-v4-flash';
  if (provider === 'openai' || provider === 'gpt') return 'gpt-5.5';
  return 'claude-sonnet-4-6';
}
function modelLooksWrongForProvider(model, provider) {
  var key = String(model || '').trim().toLowerCase();
  provider = String(provider || '').trim().toLowerCase();
  if (!key) return true;
  if (provider === 'deepseek') return key.indexOf('gpt-') === 0 || key.indexOf('o1') === 0 || key.indexOf('o3') === 0 || key.indexOf('o4') === 0 || key.indexOf('claude-') === 0;
  if (provider === 'openai' || provider === 'gpt') return key.indexOf('deepseek') === 0 || key.indexOf('claude-') === 0;
  if (provider === 'anthropic' || provider === 'claude') return key.indexOf('deepseek') === 0 || key.indexOf('gpt-') === 0 || key.indexOf('o1') === 0 || key.indexOf('o3') === 0 || key.indexOf('o4') === 0;
  return false;
}
function normalizeModelForProvider(input, provider) {
  var fallback = defaultModelForProvider(provider);
  if (!input) return fallback;
  input.placeholder = provider === 'deepseek' ? 'DeepSeek model, e.g. deepseek-v4-flash' : (provider === 'openai' ? 'OpenAI model, e.g. gpt-5.5' : 'Model name');
  var current = String(input.value || '').trim();
  if (!current || modelLooksWrongForProvider(current, provider)) {
    input.value = fallback;
    return fallback;
  }
  return current;
}
var _secureAiKeys = {};
var _secureAiConfigured = {};
function _aiProviderNorm(provider){provider=String(provider||'anthropic').toLowerCase();return provider==='claude'?'anthropic':(provider==='gpt'?'openai':provider);}
function _aiSecretSlot(scope,provider){return (scope==='lead'?'lead_':'main_')+_aiProviderNorm(provider);}
function _secureAiValue(slot){return _secureAiKeys[slot]||(_secureAiConfigured[slot]?'__BACKEND_SECURE__':'');}
async function _saveSecureAiSecret(slot,key,clearBlank){
  var payload={secrets:{},clear_blank:!!clearBlank}; payload.secrets[slot]=key||'';
  var r=await fetch('/secure-secrets/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),d=await r.json().catch(function(){return {};});
  if(!r.ok)throw new Error(d.error||'Could not save key securely');
  _secureAiConfigured=d.configured||{}; _secureAiKeys[slot]=_secureAiConfigured[slot]?'__BACKEND_SECURE__':''; return d;
}
async function _loadSecureAiInfo(){
  try{var r=await fetch('/secure-secrets/info',{cache:'no-store'}),d=await r.json();_secureAiConfigured=d.configured||{};Object.keys(_secureAiConfigured).forEach(function(k){if(_secureAiConfigured[k])_secureAiKeys[k]='__BACKEND_SECURE__';});}catch(e){}
}
function _providerKeyStore(provider)   { return 'hy_key_' + provider; }
function _providerModelStore(provider) { return 'hy_model_' + provider; }
function _leadKeyStore(provider)   { return 'hy_lead_key_' + provider; }
function _leadModelStore(provider) { return 'hy_lead_model_' + provider; }

function onMainProviderChange() {
  var provider = document.getElementById('mainProviderSel').value;
  var modelSel = document.getElementById('modelSel');
  var modelInput = document.getElementById('mainModelInput');
  var note = document.getElementById('mainProviderNote');
  var keyInput = document.getElementById('keyInput');

  // Load whatever key/model were previously saved for THIS provider, so
  // switching providers doesn't require re-typing a key already saved before.
  var savedKey = '', savedModel = '';
  try {
    savedKey = _secureAiValue(_aiSecretSlot('main',provider));
    savedModel = localStorage.getItem(_providerModelStore(provider)) || '';
  } catch(e) {}
  keyInput.value = savedKey==='__BACKEND_SECURE__'?'':savedKey; if(savedKey==='__BACKEND_SECURE__')keyInput.placeholder='Saved securely · paste to replace';

  if (provider === 'anthropic') {
    modelSel.style.display = '';
    modelInput.style.display = 'none';
    note.style.display = 'none';
    keyInput.placeholder = 'Paste API key: sk-ant-api03-...';
    if (savedModel) modelSel.value = savedModel;
  } else {
    modelSel.style.display = 'none';
    modelInput.style.display = '';
    modelInput.value = savedModel;
    normalizeModelForProvider(modelInput, provider);
    keyInput.placeholder = provider === 'deepseek' ? 'Paste DeepSeek API key' : 'Paste OpenAI API key: sk-...';
    if (provider === 'deepseek') {
      note.textContent = 'DeepSeek cannot browse the web itself. Fine for CV formatting; Lead Finder live-search features need an External Job Search Provider (Tavily/SerpAPI) configured when using DeepSeek.';
      note.style.display = '';
    } else {
      note.style.display = 'none';
    }
  }
  setDot(savedKey ? 'ok' : 'off');
  if (typeof previewAiRoutes === 'function') previewAiRoutes();
}
function onLeadProviderChange() {
  var provider = document.getElementById('leadProviderSel').value;
  var modelInput = document.getElementById('leadModelInput');
  var note = document.getElementById('leadProviderNote');
  var keyInput = document.getElementById('leadKeyInput');

  var savedKey = '', savedModel = '';
  try {
    savedKey = _secureAiValue(_aiSecretSlot('lead',provider));
    savedModel = localStorage.getItem(_leadModelStore(provider)) || '';
  } catch(e) {}
  keyInput.value = savedKey==='__BACKEND_SECURE__'?'':savedKey; if(savedKey==='__BACKEND_SECURE__')keyInput.placeholder='Saved securely · paste to replace';

  if (provider === 'anthropic') {
    modelInput.style.display = 'none';
    note.style.display = 'none';
    keyInput.placeholder = 'Separate key for Lead Finder';
  } else {
    modelInput.style.display = '';
    modelInput.value = savedModel;
    normalizeModelForProvider(modelInput, provider);
    keyInput.placeholder = provider === 'deepseek' ? 'Paste DeepSeek API key' : 'Paste OpenAI API key: sk-...';
    if (provider === 'deepseek') {
      note.textContent = 'DeepSeek cannot browse the web itself — configure an External Job Search Provider (Tavily/SerpAPI) below so Lead Finder can still find leads.';
      note.style.display = '';
    } else {
      note.style.display = 'none';
    }
  }
  if (typeof previewAiRoutes === 'function') previewAiRoutes();
}
async function saveKey() {
  var key = document.getElementById('keyInput').value.trim();
  var provider = document.getElementById('mainProviderSel').value;
  var model = provider === 'anthropic' ? document.getElementById('modelSel').value : normalizeModelForProvider(document.getElementById('mainModelInput'), provider);
  if (!key) { showToast('Paste your API key first', 'err'); return; }
  window._hKeysByProvider = window._hKeysByProvider || {};
  window._hModelsByProvider = window._hModelsByProvider || {};
  window._hKeysByProvider[provider] = key;
  window._hModelsByProvider[provider] = model;
  window._hProvider = provider;
  try {
    await _saveSecureAiSecret(_aiSecretSlot('main',provider),key,false);
    localStorage.removeItem(_providerKeyStore(provider));
    cvStudioDurableSettingSet(_providerModelStore(provider), model);
    cvStudioDurableSettingSet('hy_provider', provider);
    window._hKeysByProvider[provider]='__BACKEND_SECURE__';
    document.getElementById('keyInput').value='';
  } catch(e) { showToast(e.message||'Could not save API key','err'); return; }
  setDot('ok');
  showToast('API key saved for ' + providerLabel(provider) + '!', 'ok');
  if (typeof previewAiRoutes === 'function') previewAiRoutes();
  if (typeof refreshAllAiRouteUi === 'function') refreshAllAiRouteUi();
  else if (typeof syncQuickAiProviderPanels === 'function') syncQuickAiProviderPanels();
}

function getKey() {
  var provider = getProvider();
  if (window._hKeysByProvider && window._hKeysByProvider[provider]) return window._hKeysByProvider[provider];
  return _secureAiValue(_aiSecretSlot('main',provider));
}
function getProvider() {
  // Runtime calls should use the saved provider, not merely whatever is
  // currently selected in the Settings dropdown. Otherwise a user can change
  // Claude -> DeepSeek visually, forget to click Save, and the app will send
  // the old saved Claude key to DeepSeek. The dropdown is only committed by Save.
  if (window._hProvider) return window._hProvider;
  try { return localStorage.getItem('hy_provider') || 'anthropic'; } catch(e) { return 'anthropic'; }
}
function getCurrentMainProviderSelection() {
  var sel = document.getElementById('mainProviderSel');
  return (sel && sel.value) ? sel.value : getProvider();
}
async function saveLeadKey() {
  var input = document.getElementById('leadKeyInput');
  var key = input ? input.value.trim() : '';
  var provider = document.getElementById('leadProviderSel').value;
  var model = provider === 'anthropic' ? '' : normalizeModelForProvider(document.getElementById('leadModelInput'), provider);
  window._hLeadProvider = provider;
  window._hLeadModelsByProvider = window._hLeadModelsByProvider || {};
  window._hLeadModelsByProvider[provider] = model;
  try { cvStudioDurableSettingSet('hy_lead_provider', provider); cvStudioDurableSettingSet(_leadModelStore(provider), model); } catch(e) {}
  window._hLeadKeysByProvider = window._hLeadKeysByProvider || {};
  if (!key) {
    window._hLeadKeysByProvider[provider] = '';
    try { await _saveSecureAiSecret(_aiSecretSlot('lead',provider),'',true); localStorage.removeItem(_leadKeyStore(provider)); } catch(e) {}
    showToast('Lead Finder API key cleared for ' + providerLabel(provider) + ' — using Main AI key', 'ok');
    if (typeof previewAiRoutes === 'function') previewAiRoutes();
    return;
  }
  try { await _saveSecureAiSecret(_aiSecretSlot('lead',provider),key,false); localStorage.removeItem(_leadKeyStore(provider)); } catch(e) { showToast(e.message||'Could not save Lead Finder key','err'); return; }
  window._hLeadKeysByProvider[provider] = '__BACKEND_SECURE__'; if(input)input.value='';
  showToast('Lead Finder API key saved for ' + providerLabel(provider) + '!', 'ok');
  if (typeof previewAiRoutes === 'function') previewAiRoutes();
}
function getLeadKey() {
  var provider = getLeadProvider();
  var dedicated = getDedicatedLeadKey(provider);
  if (dedicated) return dedicated;
  return getKey();
}
function getSavedLeadProvider() {
  if (window._hLeadProvider) return window._hLeadProvider;
  try { return localStorage.getItem('hy_lead_provider') || 'anthropic'; } catch(e) { return 'anthropic'; }
}
function getLeadProvider() {
  // If no dedicated Lead Finder key is set for the saved Lead Finder provider,
  // Lead Finder falls back to the Main AI key -- so it should also fall back to
  // the saved Main AI provider/model. Keep this check non-recursive: calling
  // getDedicatedLeadKey() without a concrete provider used to call back into
  // getLeadProvider() and crash Lead Finder with a maximum call stack error.
  var savedLeadProvider = getSavedLeadProvider();
  if (!getDedicatedLeadKey(savedLeadProvider)) return getProvider();
  return savedLeadProvider;
}
function getCurrentLeadProviderSelection() {
  var sel = document.getElementById('leadProviderSel');
  return (sel && sel.value) ? sel.value : getLeadProvider();
}
function getLeadModel() {
  if (!getDedicatedLeadKey()) return getModel();
  var provider = getLeadProvider();
  if (provider === 'anthropic') {
    // Dedicated Lead Finder Claude key must never inherit a non-Claude Main model
    // such as deepseek-v4-flash or gpt-5.5. Use saved Claude model only.
    if (window._hModelsByProvider && window._hModelsByProvider['anthropic'] && !modelLooksWrongForProvider(window._hModelsByProvider['anthropic'], 'anthropic')) return window._hModelsByProvider['anthropic'];
    try { var savedClaudeModel = localStorage.getItem(_providerModelStore('anthropic')); if (savedClaudeModel && !modelLooksWrongForProvider(savedClaudeModel, 'anthropic')) return savedClaudeModel; } catch(e) {}
    return defaultModelForProvider('anthropic');
  }
  if (window._hLeadModelsByProvider && window._hLeadModelsByProvider[provider] && !modelLooksWrongForProvider(window._hLeadModelsByProvider[provider], provider)) return window._hLeadModelsByProvider[provider];
  try { var saved = localStorage.getItem(_leadModelStore(provider)); if (saved && !modelLooksWrongForProvider(saved, provider)) return saved; } catch(e) {}
  return defaultModelForProvider(provider);
}
function getDedicatedLeadKey(provider) {
  provider = provider || getSavedLeadProvider();
  if (window._hLeadKeysByProvider && window._hLeadKeysByProvider[provider]) return window._hLeadKeysByProvider[provider];
  return _secureAiValue(_aiSecretSlot('lead',provider));
}

