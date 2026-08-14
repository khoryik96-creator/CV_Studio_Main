// ── Wallpaper / background settings ─────────────────────────────────────────
var CV_BG_STORAGE_KEY = 'cvstudio_background_v1';
var CV_BG_PRESETS = [
  {id:'default', label:'Default Blue', bg:'#f7faff', preview:'linear-gradient(135deg,#fbfdff,#edf5ff 52%,#f7faff)', body:''},
  {id:'pink', label:'Light Pink', bg:'#fff6fb', preview:'linear-gradient(135deg,#fffafd,#ffeaf4)', body:'linear-gradient(180deg,#fffafd 0%,#fff2f8 48%,#fff7fb 100%)'},
  {id:'purple', label:'Light Purple', bg:'#f8f4ff', preview:'linear-gradient(135deg,#fbf8ff,#efe7ff)', body:'linear-gradient(180deg,#fbf8ff 0%,#f2ebff 48%,#f8f4ff 100%)'},
  {id:'mint', label:'Soft Mint', bg:'#f2fff8', preview:'linear-gradient(135deg,#fafffd,#e8fff3)', body:'linear-gradient(180deg,#fafffd 0%,#ebfff4 48%,#f4fff9 100%)'},
  {id:'peach', label:'Warm Peach', bg:'#fff8f0', preview:'linear-gradient(135deg,#fffdf8,#ffead7)', body:'linear-gradient(180deg,#fffdf8 0%,#fff0df 48%,#fff8f0 100%)'},
  {id:'lavenderBlue', label:'Blue Purple', bg:'#f4f7ff', preview:'linear-gradient(135deg,#f7fbff,#edf0ff)', body:'linear-gradient(180deg,#fbfdff 0%,#eef3ff 48%,#f6f7ff 100%)'}
];
function backgroundGetPreset(id) {
  return CV_BG_PRESETS.find(function(p){ return p.id === id; }) || CV_BG_PRESETS[0];
}
function backgroundLoadSettings() {
  try {
    var raw = localStorage.getItem(CV_BG_STORAGE_KEY);
    if (!raw) return {mode:'preset', preset:'default'};
    var cfg = JSON.parse(raw) || {};
    if (cfg.mode === 'wallpaper' && cfg.dataUrl) return cfg;
    if (cfg.mode === 'preset') return {mode:'preset', preset:cfg.preset || 'default'};
  } catch(e) {}
  return {mode:'preset', preset:'default'};
}
function backgroundSaveSettings(cfg) {
  try { localStorage.setItem(CV_BG_STORAGE_KEY, JSON.stringify(cfg || {mode:'preset', preset:'default'})); return true; }
  catch(e) { showToast('Background applied for this session, but could not be saved. Uploaded image may be too large.', 'err'); return false; }
}
function applyBackgroundSettings(cfg) {
  cfg = cfg || backgroundLoadSettings();
  var root = document.documentElement;
  var body = document.body;
  if (!body || !root) return;
  if (cfg.mode === 'wallpaper' && cfg.dataUrl) {
    body.classList.add('cv-wallpaper-on');
    root.style.setProperty('--bg', '#f7faff');
    body.style.backgroundColor = '#f7faff';
    body.style.backgroundImage = 'linear-gradient(180deg, rgba(255,255,255,.08), rgba(255,255,255,.16)), url("' + cfg.dataUrl + '")';
    body.style.backgroundSize = 'cover';
    body.style.backgroundRepeat = 'no-repeat';
    body.style.backgroundPosition = 'center center';
    body.style.backgroundAttachment = 'fixed';
  } else {
    var preset = backgroundGetPreset(cfg.preset || 'default');
    body.classList.remove('cv-wallpaper-on');
    root.style.setProperty('--bg', preset.bg || '#f7faff');
    if (preset.id === 'default') {
      body.style.background = '';
      body.style.backgroundColor = '';
      body.style.backgroundImage = '';
      body.style.backgroundSize = '';
      body.style.backgroundRepeat = '';
      body.style.backgroundPosition = '';
      body.style.backgroundAttachment = '';
    } else {
      body.style.background = preset.body || preset.preview;
      body.style.backgroundColor = preset.bg || '#f7faff';
      body.style.backgroundSize = 'auto';
      body.style.backgroundRepeat = 'no-repeat';
      body.style.backgroundPosition = 'center top';
      body.style.backgroundAttachment = 'fixed';
    }
  }
  updateBackgroundPreview(cfg);
}
function updateBackgroundPreview(cfg) {
  cfg = cfg || backgroundLoadSettings();
  var preview = document.getElementById('bgPreviewBox');
  var label = document.getElementById('bgCurrentLabel');
  if (preview) {
    preview.style.backgroundImage = '';
    preview.style.background = '';
    preview.textContent = 'Preview';
    if (cfg.mode === 'wallpaper' && cfg.dataUrl) {
      preview.style.backgroundImage = 'linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.12)), url("' + cfg.dataUrl + '")';
      preview.style.backgroundSize = 'cover';
      preview.style.backgroundPosition = 'center';
      preview.textContent = '';
    } else {
      var preset = backgroundGetPreset(cfg.preset || 'default');
      preview.style.background = preset.preview || preset.body || '#f7faff';
    }
  }
  if (label) label.textContent = (cfg.mode === 'wallpaper') ? ('Wallpaper: ' + (cfg.name || 'Uploaded image')) : ('Preset: ' + backgroundGetPreset(cfg.preset || 'default').label);
  var grid = document.getElementById('bgPresetGrid');
  if (grid) Array.prototype.forEach.call(grid.querySelectorAll('.bg-swatch'), function(btn){ btn.classList.toggle('active', cfg.mode === 'preset' && btn.getAttribute('data-bg-id') === (cfg.preset || 'default')); });
}
function renderBackgroundSettings() {
  var grid = document.getElementById('bgPresetGrid');
  if (grid && !grid.getAttribute('data-rendered')) {
    grid.innerHTML = CV_BG_PRESETS.map(function(p){ return '<button type="button" class="bg-swatch" data-bg-id="' + esc(p.id) + '" onclick="setBackgroundPreset(\'' + escJsAttr(p.id) + '\')" style="background:' + esc(p.preview) + '">' + esc(p.label) + '</button>'; }).join('');
    grid.setAttribute('data-rendered', '1');
  }
  updateBackgroundPreview(backgroundLoadSettings());
}
function setBackgroundPreset(id) {
  var cfg = {mode:'preset', preset:backgroundGetPreset(id).id};
  backgroundSaveSettings(cfg);
  applyBackgroundSettings(cfg);
  renderBackgroundSettings();
  showToast('Background updated', 'ok');
}
function resetBackgroundDefault() {
  try { localStorage.removeItem(CV_BG_STORAGE_KEY); } catch(e) {}
  var input = document.getElementById('bgWallpaperInput'); if (input) input.value = '';
  applyBackgroundSettings({mode:'preset', preset:'default'});
  renderBackgroundSettings();
  showToast('Default background restored', 'ok');
}
function clearBackgroundWallpaper() {
  var cfg = backgroundLoadSettings();
  if (cfg.mode !== 'wallpaper') { showToast('No wallpaper to remove', 'info'); return; }
  setBackgroundPreset('default');
  var input = document.getElementById('bgWallpaperInput'); if (input) input.value = '';
}
function handleBackgroundUpload(file) {
  if (!file) return;
  if (!/^image\/(png|jpe?g|webp)$/i.test(file.type || '')) { showToast('Please upload JPG, JPEG, PNG, or WEBP', 'err'); return; }
  if (file.size > 12 * 1024 * 1024) { showToast('Wallpaper image is too large. Use an image below 12MB.', 'err'); return; }
  var reader = new FileReader();
  reader.onerror = function(){ showToast('Could not read wallpaper image', 'err'); };
  reader.onload = function(ev) {
    var img = new Image();
    img.onerror = function(){ showToast('Could not load wallpaper image', 'err'); };
    img.onload = function() {
      try {
        var maxDim = 1920;
        var w = img.naturalWidth || img.width, h = img.naturalHeight || img.height;
        var scale = Math.min(1, maxDim / Math.max(w, h));
        var cw = Math.max(1, Math.round(w * scale));
        var ch = Math.max(1, Math.round(h * scale));
        var canvas = document.createElement('canvas');
        canvas.width = cw; canvas.height = ch;
        var ctx = canvas.getContext('2d');
        ctx.fillStyle = '#f7faff';
        ctx.fillRect(0, 0, cw, ch);
        ctx.drawImage(img, 0, 0, cw, ch);
        var dataUrl = canvas.toDataURL('image/jpeg', 0.86);
        var cfg = {mode:'wallpaper', dataUrl:dataUrl, name:file.name || 'Uploaded wallpaper'};
        backgroundSaveSettings(cfg);
        applyBackgroundSettings(cfg);
        renderBackgroundSettings();
        showToast('Wallpaper applied', 'ok');
      } catch(e) { showToast('Could not apply wallpaper image', 'err'); }
    };
    img.src = ev.target.result;
  };
  reader.readAsDataURL(file);
}

// ── Integrations diagnostics and non-secret local data backup ──────────────
async function refreshIntegrationDiagnostics(){
  try{
    var results=await Promise.all([
      fetch('/jobadder/api_info',{cache:'no-store'}).then(function(r){return r.json();}).catch(function(){return {};}),
      fetch('/onenote/api_info',{cache:'no-store'}).then(function(r){return r.json();}).catch(function(){return {};}),
      fetch('/ppc/outlook/api_info',{cache:'no-store'}).then(function(r){return r.json();}).catch(function(){return {};})
    ]);
    var ja=results[0]||{},one=results[1]||{},out=results[2]||{};
    applyJAPublicInfo(ja);renderJAConnectionState(ja);
    var oneBadge=document.getElementById('settingsOneNoteIntegrationStatus'),oneDetail=document.getElementById('settingsOneNoteIntegrationDetail');
    if(oneBadge)oneBadge.textContent=one.connected?'Connected':'Not connected';if(oneDetail)oneDetail.textContent=one.connected?'Microsoft OneNote web connection is available.':'Web OneNote is not connected; manual/Desktop modes remain available.';
    _ppcOutlookConnected=!!out.connected;_ppcOutlookAccount=out.account||{};_ppcOutlookStorage=out.storage||'';ppcUpdateOutlookConnectButton();
    var provider='';try{provider=getProvider();}catch(e){provider='';}var hasKey=false;try{hasKey=!!getKey();}catch(e){}
    var aiBadge=document.getElementById('settingsAiStatus'),aiDetail=document.getElementById('settingsAiDetail');if(aiBadge)aiBadge.textContent=hasKey?'Configured':'Key missing';if(aiDetail)aiDetail.textContent='Current main provider: '+(provider||'Not selected')+(hasKey?' · API key saved locally.':' · Save its API key in Main API Settings.');
  }catch(e){showToast('Could not refresh all integration statuses.','err');}
}
function cvStudioSafeLocalDataKey(key){
  key=String(key||'');
  if(/token|secret|password|api[_-]?key|authy|receipt|credential|device[_-]?code|owner[_-]?only/i.test(key))return false;
  var exact={
    'cvstudio_ppc_meta_v1':1,'cvstudio_ppc_ui_state_v1':1,'cvstudio_ppc_kpi_visibility_v1':1,'cvstudio_ppc_column_visibility_v1':1,'cvstudio_ppc_invoice_email_v1':1,'cvstudio_ppc_outlook_ms_client_v1':1,'cvstudio_ppc_outlook_drafts_v1':1,
    'cvstudio_onenote_saved_desktop_links_v1':1,'cvstudio_onenote_spelling_correction_v1':1,'cv_studio_onenote_salary_ai_enabled_v1':1,'onenote_source_mode':1,'onenote_ms_client_id':1,'onenote_ms_tenant':1,
    'cvstudio_cv_text_alignment_v1':1,'cvstudio_summary_box_autofit_v1':1,'cvstudio_single_summary_detail_v1':1,'cvstudio_batch_summary_detail_v1':1,'cvstudio_page_nav_pinned_v1':1,'cvstudio_spider_preview_memory_mode_v1':1,'ja_auto_upload':1,'hy_provider':1,'hy_model':1,'hy_lead_provider':1,'hy_lead_model':1,'hy_search_provider':1,'hy_enrichment_provider':1
  };
  if(exact[key])return true;
  if(/^hy_(?:lead_)?model_(?:anthropic|deepseek|openai)$/.test(key))return true;
  var feature=key.indexOf('hy_ai_route_model_')===0?key.slice('hy_ai_route_model_'.length):(key.indexOf('hy_ai_route_')===0?key.slice('hy_ai_route_'.length):'');
  return ['cv_single','summary','appraiser','the_owl','the_spider','cv_batch','ja_create','onenote_salary','jd_anonymizer','company_profile','lead_search','lead_people','lead_email'].indexOf(feature)>=0;
}
function cvStudioDurableSettingKey(key){
  key=String(key||'');
  return cvStudioSafeLocalDataKey(key)&&key!=='cvstudio_ppc_meta_v1'&&key!=='cvstudio_onenote_saved_desktop_links_v1';
}
function cvStudioPrivateSecretField(key){
  var text=String(key||'').trim().toLowerCase(),compact=text.replace(/[^a-z0-9]/g,'');
  if(['access_token','refresh_token','client_secret','api_key','authorization','authorization_code','password','credential','credentials','token'].indexOf(text)>=0)return true;
  var suffixes=['accesstoken','refreshtoken','clientsecret','apikey','authorizationcode','password','credential','credentials','bearertoken','oauthtoken','oauth2token','authtoken','idtoken','sessiontoken','csrftoken','devicecode','secret'];
  return compact.indexOf('authorization')===0||suffixes.some(function(suffix){return compact.slice(-suffix.length)===suffix;});
}
function cvStudioPrivateSafeValue(value,depth){
  depth=Number(depth||0);if(depth>24)return undefined;
  if(Array.isArray(value))return value.slice(0,10000).map(function(item){return cvStudioPrivateSafeValue(item,depth+1);}).filter(function(item){return item!==undefined;});
  if(value&&typeof value==='object'){
    var out={};Object.keys(value).slice(0,10000).forEach(function(key){if(cvStudioPrivateSecretField(key))return;var safe=cvStudioPrivateSafeValue(value[key],depth+1);if(safe!==undefined)out[String(key).slice(0,160)]=safe;});return out;
  }
  if(typeof value==='string')return value.slice(0,262144);
  if(value===null||typeof value==='number'||typeof value==='boolean')return value;
  return undefined;
}
function cvStudioStableStorageValue(value){
  if(Array.isArray(value))return '['+value.map(cvStudioStableStorageValue).join(',')+']';
  if(value&&typeof value==='object')return '{'+Object.keys(value).sort().map(function(key){return JSON.stringify(key)+':'+cvStudioStableStorageValue(value[key]);}).join(',')+'}';
  var encoded=JSON.stringify(value);return encoded===undefined?'null':encoded;
}
function cvStudioSafeExportSettingValue(key,value){
  value=String(value==null?'':value);
  if(/(?:\bBearer\s+[A-Za-z0-9._~-]{12,}|\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{12,}|\b(?:api[_-]?key|client[_-]?secret|access[_-]?token|refresh[_-]?token)\s*[:=])/i.test(value))return null;
  try{var parsed=JSON.parse(value);if(parsed&&typeof parsed==='object')return JSON.stringify(cvStudioPrivateSafeValue(parsed,0));}catch(e){}
  return value;
}
function cvStudioLocalDataSettingsSnapshot(durableOnly){
  var settings={};try{for(var i=0;i<localStorage.length;i++){var key=String(localStorage.key(i)||'');if((durableOnly?cvStudioDurableSettingKey(key):cvStudioSafeLocalDataKey(key))){var safe=cvStudioSafeExportSettingValue(key,localStorage.getItem(key));if(safe!==null)settings[key]=safe;}}}catch(e){}
  return settings;
}
var _phase2bSettingsSqliteCache=null;
var _phase2bSettingsMutationVersion=0;
var _phase2bSettingsDirtyKeys={};
var _phase2bSettingsHydrationPromise=null;
var _phase2bSettingsWriteQueue=Promise.resolve();
function cvStudioStoragePost(path,payload){
  return fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload||{})}).then(function(response){return response.json().catch(function(){return {};}).then(function(data){if(!response.ok||!data.ok)throw new Error(data.message||data.error||'Local storage request failed');return data;});});
}
function cvStudioQueueSettingsPost(path,payload){
  _phase2bSettingsWriteQueue=_phase2bSettingsWriteQueue.catch(function(){}).then(function(){return cvStudioStoragePost(path,payload);});
  return _phase2bSettingsWriteQueue;
}
function cvStudioApplyDurableSettings(settings){
  settings=settings&&typeof settings==='object'&&!Array.isArray(settings)?settings:{};
  try{
    var existing=[];for(var i=0;i<localStorage.length;i++){var key=String(localStorage.key(i)||'');if(cvStudioDurableSettingKey(key))existing.push(key);}
    existing.forEach(function(key){if(!Object.prototype.hasOwnProperty.call(settings,key))localStorage.removeItem(key);});
    Object.keys(settings).forEach(function(key){if(cvStudioDurableSettingKey(key)&&typeof settings[key]==='string')localStorage.setItem(key,settings[key]);});
  }catch(e){}
  _phase2bSettingsSqliteCache=Object.assign({},settings);
  return _phase2bSettingsSqliteCache;
}
function cvStudioRefreshHydratedSettingUi(){
  try{if(typeof normalizeCvTextAlignment==='function'){window._cvTextAlignment=normalizeCvTextAlignment(localStorage.getItem('cvstudio_cv_text_alignment_v1')||'left');if(typeof renderCvTextAlignmentSetting==='function')renderCvTextAlignmentSetting();}}catch(e){}
  try{window._cvSummaryBoxAutoFit=localStorage.getItem('cvstudio_summary_box_autofit_v1')!=='false';if(typeof renderCvSummaryBoxAutoFitSetting==='function')renderCvSummaryBoxAutoFitSetting();}catch(e){}
  try{if(typeof normalizeCvSummaryDetailPreference==='function'){window._cvSingleSummaryDetail=normalizeCvSummaryDetailPreference(localStorage.getItem('cvstudio_single_summary_detail_v1')||'concise');window._cvBatchSummaryDetail=normalizeCvSummaryDetailPreference(localStorage.getItem('cvstudio_batch_summary_detail_v1')||'concise');if(typeof renderCvSummaryDetailSettings==='function')renderCvSummaryDetailSettings();}}catch(e){}
  try{var auto=localStorage.getItem('ja_auto_upload')!=='false';window._jaAutoUpload=auto;var autoBox=document.getElementById('autoUploadToggle'),autoLabel=document.getElementById('autoUploadLabel');if(autoBox)autoBox.checked=auto;if(autoLabel)autoLabel.textContent=auto?'On':'Off';}catch(e){}
  try{if(typeof oneNoteApiLoadSettings==='function')oneNoteApiLoadSettings();if(typeof oneNoteLoadSpellingCorrectionSetting==='function')oneNoteLoadSpellingCorrectionSetting();var salary=document.getElementById('oneNoteSalaryAiEnabled'),salarySaved=localStorage.getItem('cv_studio_onenote_salary_ai_enabled_v1');if(salary)salary.checked=salarySaved===null?true:salarySaved==='1';if(typeof oneNoteSourceModeChanged==='function')oneNoteSourceModeChanged(true);if(typeof oneNoteUpdateSalaryAiBadge==='function')oneNoteUpdateSalaryAiBadge();}catch(e){}
  try{if(typeof pageNavPinStored==='function'){window._pageNavPinEnabled=pageNavPinStored();if(typeof updatePageNavPinButton==='function')updatePageNavPinButton();}}catch(e){}
  try{if(typeof ppcRestoreUiState==='function')ppcRestoreUiState();if(typeof ppcApplyKpiVisibility==='function')ppcApplyKpiVisibility();if(typeof ppcApplyColumnVisibility==='function')ppcApplyColumnVisibility();}catch(e){}
  try{if(typeof storedTheSpiderPreviewMemoryMode==='function'&&typeof applyTheSpiderPreviewMemoryMode==='function'){var memoryMode=storedTheSpiderPreviewMemoryMode();applyTheSpiderPreviewMemoryMode(memoryMode,false);if(memoryMode==='auto'&&typeof scheduleTheSpiderPreviewAutoDiagnostics==='function')scheduleTheSpiderPreviewAutoDiagnostics();}}catch(e){}
  try{if(typeof renderAiRoutingRows==='function')renderAiRoutingRows();else if(typeof ensureAiRoutingRowsVisible==='function')ensureAiRoutingRowsVisible();if(typeof syncQuickAiProviderPanels==='function')syncQuickAiProviderPanels();}catch(e){}
}
function cvStudioDurableSettingSet(key,value){
  key=String(key||'');value=String(value==null?'':value);
  try{localStorage.setItem(key,value);}catch(e){return Promise.resolve(false);}
  if(!cvStudioDurableSettingKey(key))return Promise.resolve(true);
  _phase2bSettingsMutationVersion+=1;var version=_phase2bSettingsMutationVersion;_phase2bSettingsDirtyKeys[key]=version;
  if(_phase2bSettingsSqliteCache)_phase2bSettingsSqliteCache[key]=value;
  var data={};data[key]=value;
  return cvStudioQueueSettingsPost('/storage/browser-settings/upsert',{settings:data}).then(function(){return true;}).catch(function(error){showToast('Setting remains available in this browser, but durable storage failed. '+String((error&&error.message)||''),'err');return false;});
}
function cvStudioDurableSettingRemove(key){
  key=String(key||'');var previous=null;try{previous=localStorage.getItem(key);localStorage.removeItem(key);}catch(e){return Promise.resolve(false);}
  if(!cvStudioDurableSettingKey(key))return Promise.resolve(true);
  _phase2bSettingsMutationVersion+=1;var version=_phase2bSettingsMutationVersion;_phase2bSettingsDirtyKeys[key]=version;
  if(_phase2bSettingsSqliteCache)delete _phase2bSettingsSqliteCache[key];
  return cvStudioQueueSettingsPost('/storage/browser-settings/delete',{keys:[key]}).then(function(){return true;}).catch(function(error){
    if(_phase2bSettingsDirtyKeys[key]===version&&previous!==null){try{localStorage.setItem(key,previous);}catch(e){}if(_phase2bSettingsSqliteCache)_phase2bSettingsSqliteCache[key]=previous;}
    showToast('Setting was not removed from durable storage. '+String((error&&error.message)||''),'err');return false;
  });
}
function cvStudioHydrateBrowserSettings(){
  if(_phase2bSettingsHydrationPromise)return _phase2bSettingsHydrationPromise;
  var startedVersion=_phase2bSettingsMutationVersion,legacy=cvStudioLocalDataSettingsSnapshot(true);
  _phase2bSettingsHydrationPromise=cvStudioStoragePost('/storage/browser-settings/import',{settings:legacy}).then(function(data){
    var current=cvStudioLocalDataSettingsSnapshot(true),merged=Object.assign({},data.settings||{}),upserts={},deletes=[];
    Object.keys(_phase2bSettingsDirtyKeys).forEach(function(key){if(_phase2bSettingsDirtyKeys[key]<=startedVersion)return;if(Object.prototype.hasOwnProperty.call(current,key)){merged[key]=current[key];upserts[key]=current[key];}else{delete merged[key];deletes.push(key);}});
    cvStudioApplyDurableSettings(merged);cvStudioRefreshHydratedSettingUi();
    var writes=[];if(Object.keys(upserts).length)writes.push(cvStudioQueueSettingsPost('/storage/browser-settings/upsert',{settings:upserts}).catch(function(){}));if(deletes.length)writes.push(cvStudioQueueSettingsPost('/storage/browser-settings/delete',{keys:deletes}).catch(function(){}));
    return Promise.all(writes).then(function(){return merged;});
  }).catch(function(){_phase2bSettingsSqliteCache=cvStudioLocalDataSettingsSnapshot(true);return _phase2bSettingsSqliteCache;});
  return _phase2bSettingsHydrationPromise;
}
var _cvStudioPhase2bSettingsStartupPromise=cvStudioHydrateBrowserSettings();
function exportCvStudioLocalData(){
  var settings=cvStudioLocalDataSettingsSnapshot(false);
  var records={onenote_transfer_records:(typeof oneNoteRecordsLoad==='function'?oneNoteRecordsLoad():[]),onenote_saved_links:(typeof oneNoteReadSavedLinks==='function'?oneNoteReadSavedLinks():[])};
  var payload={product:'CV Studio local data',version:'v24.6.338',schema:1,exportedAt:new Date().toISOString(),includes:['PPC metadata and preferences','saved OneNote links and parser preferences','OneNote transfer record history (private application data)','invoice recipient/settings and draft links','CV alignment and navigation preferences','AI routing/provider selections without API keys'],settings:settings,records:records};
  var blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='cv_studio_local_data_'+new Date().toISOString().slice(0,10)+'.json';document.body.appendChild(a);a.click();setTimeout(function(){URL.revokeObjectURL(url);a.remove();},0);showToast('Non-secret local data exported.','ok');
}
function cvStudioPersistImportedLocalData(payload){
  payload=payload||{};var settings=payload.settings&&typeof payload.settings==='object'?payload.settings:{},records=payload.records&&typeof payload.records==='object'?payload.records:{};
  var hydrations=[cvStudioHydrateBrowserSettings()];
  if(typeof ppcMetaHydrateFromSQLite==='function')hydrations.push(ppcMetaHydrateFromSQLite());
  if(typeof oneNoteRecordsHydrateFromSQLite==='function')hydrations.push(oneNoteRecordsHydrateFromSQLite());
  if(typeof oneNoteLinksHydrateFromSQLite==='function')hydrations.push(oneNoteLinksHydrateFromSQLite());
  return Promise.all(hydrations.map(function(item){return Promise.resolve(item).catch(function(){});})).then(function(){
    var writes=[],savedLinksFromSettings=null;
    function confirmedWrite(write,count,label,requireTrue){
      return Promise.resolve(write).then(function(result){
        if(requireTrue&&result!==true)throw new Error('Local-data restore could not persist '+label+' to durable storage.');
        return count;
      },function(error){
        throw new Error('Local-data restore could not persist '+label+' to durable storage. '+String((error&&error.message)||''));
      });
    }
    Object.keys(settings).forEach(function(key){var value=settings[key];if(!cvStudioSafeLocalDataKey(key)||typeof value!=='string')return;
      if(key==='cvstudio_ppc_meta_v1'){
        var metadata=null;try{metadata=JSON.parse(value);}catch(e){return;}
        if(metadata&&typeof metadata==='object'&&!Array.isArray(metadata)){
          try{ppcMetaSave(metadata);var ppcWrite=typeof _ppcMetaWriteQueue==='undefined'?Promise.reject(new Error('PPC durable write did not start')):_ppcMetaWriteQueue;writes.push(confirmedWrite(ppcWrite,1,'PPC metadata',false));}
          catch(error){writes.push(confirmedWrite(Promise.reject(error),1,'PPC metadata',false));}
        }
        return;
      }
      if(key==='cvstudio_onenote_saved_desktop_links_v1'){try{var links=JSON.parse(value);if(Array.isArray(links))savedLinksFromSettings=links;}catch(e){}return;}
      if(cvStudioDurableSettingKey(key))writes.push(confirmedWrite(cvStudioDurableSettingSet(key,value),1,'a browser setting',true));
    });
    var transferRecords=Array.isArray(records.onenote_transfer_records)?records.onenote_transfer_records:null;
    var savedLinks=Array.isArray(records.onenote_saved_links)?records.onenote_saved_links:savedLinksFromSettings;
    if(transferRecords){
      var recordsAccepted=oneNoteRecordsSave(transferRecords);
      writes.push(confirmedWrite(recordsAccepted===true&&typeof _oneNoteRecordsLastWritePromise!=='undefined'?_oneNoteRecordsLastWritePromise:false,transferRecords.length,'OneNote transfer records',true));
    }
    if(savedLinks){
      var linksAccepted=oneNoteWriteSavedLinks(savedLinks);
      writes.push(confirmedWrite(linksAccepted===true&&typeof _oneNoteLinksLastWritePromise!=='undefined'?_oneNoteLinksLastWritePromise:false,savedLinks.length,'saved OneNote links',true));
    }
    return Promise.all(writes).then(function(counts){return counts.reduce(function(total,count){return total+count;},0);});
  });
}
function importCvStudioLocalData(file){
  if(!file)return;var reader=new FileReader();reader.onload=async function(){try{var payload=JSON.parse(String(reader.result||''));if(!payload||payload.product!=='CV Studio local data'||Number(payload.schema)!==1||!payload.settings||typeof payload.settings!=='object')throw new Error('This is not a supported CV Studio local-data backup.');var restored=await cvStudioPersistImportedLocalData(payload);showToast('Restored '+restored+' non-secret local settings and records. Reloading CV Studio…','ok');setTimeout(function(){location.reload();},700);}catch(e){showToast((e&&e.message)||'Could not restore local data.','err');}};reader.onerror=function(){showToast('Could not read the selected backup file.','err');};reader.readAsText(file);
}

function cvStudioFormatBytes(value){
  var n=Math.max(0,Number(value)||0);if(n<1024)return Math.round(n)+' B';if(n<1024*1024)return (n/1024).toFixed(1)+' KB';if(n<1024*1024*1024)return (n/1024/1024).toFixed(n>=100*1024*1024?0:1)+' MB';return (n/1024/1024/1024).toFixed(1)+' GB';
}
function cvStudioBrowserDiagnosticSnapshot(){
  var keys=[];try{for(var i=0;i<localStorage.length;i++)keys.push(String(localStorage.key(i)||''));}catch(e){}
  return {user_agent:navigator.userAgent||'',active_tab:String(window.currentTab||window._currentTab||''),visibility_state:document.visibilityState||'',viewport:{width:window.innerWidth||0,height:window.innerHeight||0,device_pixel_ratio:window.devicePixelRatio||1},cache:theSpiderPreviewBrowserCacheStats(),memory_mode:storedTheSpiderPreviewMemoryMode(),local_storage_keys:keys,recent_api_errors:(window._cvStudioRecentApiErrors||[]).slice(-20)};
}
function renderCvStudioDiagnosticStatus(data){
  var pill=document.getElementById('settingsDiagnosticStatus'),usage=document.getElementById('settingsSpiderCacheUsage'),detail=document.getElementById('settingsDiagnosticDetail'),select=document.getElementById('settingsSpiderMemoryMode');
  var profileInfo=currentTheSpiderPreviewMemoryProfile();
  if(select)select.value=profileInfo.selected;
  var browser=theSpiderPreviewBrowserCacheStats(),backend=data&&data.cache&&typeof data.cache==='object'?data.cache:{};
  var browserUsed=Number(browser.payload_bytes||0)+Number(browser.dom_bytes||0),browserMax=Number(browser.payload_max_bytes||0)+Number(browser.dom_max_bytes||0),backendUsed=Number(backend.backend_preview_bytes||0),backendMax=Number(backend.backend_preview_max_bytes||256*1024*1024);
  if(usage)usage.textContent='Browser '+cvStudioFormatBytes(browserUsed)+' / '+cvStudioFormatBytes(browserMax)+' · backend '+cvStudioFormatBytes(backendUsed)+' / '+cvStudioFormatBytes(backendMax)+' · '+browser.prefetch_ready+'/'+browser.prefetch_target+' warmed';
  if(pill){pill.textContent=data&&data.ok?'Ready':'Local only';pill.classList.toggle('ok',!!(data&&data.ok));}
  var mem=data&&data.memory&&typeof data.memory==='object'?data.memory:{};
  if(detail){
    var systemText=Number(mem.total_bytes)>0?('System RAM '+cvStudioFormatBytes(mem.total_bytes)+' · available '+cvStudioFormatBytes(mem.available_bytes)):'System RAM unavailable';
    detail.textContent='Selected '+(profileInfo.selected==='auto'?'Auto':profileInfo.profile.label)+' · resolved '+profileInfo.profile.label+' · '+profileInfo.reason+' · data '+profileInfo.freshness+(profileInfo.age_ms!==null?' ('+Math.max(0,Math.round(profileInfo.age_ms/1000))+'s old)':'')+' · limits browser '+cvStudioFormatBytes(browserMax)+', backend '+cvStudioFormatBytes(backendMax)+' · usage browser '+cvStudioFormatBytes(browserUsed)+', backend '+cvStudioFormatBytes(backendUsed)+' · '+systemText+'. Diagnostic ZIP excludes keys, tokens, CV files, preview payloads and localStorage values.';
  }
}
async function refreshCvStudioDiagnostics(announce){
  try{
    var r=await fetch('/diagnostics/runtime',{cache:'no-store'}),d=await r.json().catch(function(){return {};});
    if(!r.ok||!d.ok)throw new Error(d.error||('Diagnostics failed: HTTP '+r.status));
    window._cvStudioLastRuntimeDiagnostics=d;
    window._cvStudioSystemMemoryTotalBytes=Number(d.memory&&d.memory.total_bytes)||0;
    window._cvStudioSystemMemoryAvailableBytes=Number(d.memory&&d.memory.available_bytes)||0;
    window._cvStudioSystemMemoryReceivedAt=Date.now();
    if(storedTheSpiderPreviewMemoryMode()==='auto')applyTheSpiderPreviewMemoryMode('auto',false);
    renderCvStudioDiagnosticStatus(d);
    if(announce)showToast('Diagnostics refreshed.','ok');
    return d;
  }catch(e){renderCvStudioDiagnosticStatus(null);if(announce)showToast((e&&e.message)||'Could not refresh diagnostics.','err');return null;}
}
async function clearCvStudioPreviewCaches(){
  try{
    resetTheSpiderPreviewCaches();
    var r=await fetch('/diagnostics/clear_preview_cache',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}),d=await r.json().catch(function(){return {};});
    if(!r.ok||!d.ok)throw new Error(d.error||('Cache clear failed: HTTP '+r.status));
    window._cvStudioLastRuntimeDiagnostics=Object.assign({},window._cvStudioLastRuntimeDiagnostics||{ok:true},{cache:d.cache||{}});
    renderCvStudioDiagnosticStatus(window._cvStudioLastRuntimeDiagnostics);showToast('AI Crawler browser and backend preview caches cleared.','ok');
  }catch(e){showToast((e&&e.message)||'Could not clear preview caches.','err');}
}
async function downloadCvStudioDiagnosticBundle(ev){
  var btn=ev&&ev.currentTarget?ev.currentTarget:null;if(btn)btn.disabled=true;
  try{
    var r=await fetch('/diagnostics/support_bundle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({browser:cvStudioBrowserDiagnosticSnapshot()})});
    if(!r.ok){var d=await r.json().catch(function(){return {};});throw new Error(d.error||('Diagnostic bundle failed: HTTP '+r.status));}
    var blob=await r.blob(),disposition=String(r.headers.get('Content-Disposition')||''),match=disposition.match(/filename\*?=(?:UTF-8''|")?([^";]+)/i),filename=match?decodeURIComponent(match[1].replace(/^"|"$/g,'')):'cv_studio_diagnostic_bundle.zip';
    var url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=filename;document.body.appendChild(a);a.click();setTimeout(function(){URL.revokeObjectURL(url);a.remove();},0);showToast('Redacted diagnostic bundle created.','ok');
  }catch(e){showToast((e&&e.message)||'Could not create diagnostic bundle.','err');}finally{if(btn)btn.disabled=false;}
}

var _ownerIntegrationLastReport=null;
async function refreshOwnerIntegrationStatus(){
  var card=document.getElementById('ownerIntegrationCard');
  try{var r=await fetch('/owner/integration/status',{cache:'no-store'}),d=await r.json().catch(function(){return {};});if(!r.ok||!d.enabled){if(card)card.style.display='none';return null;}if(card)card.style.display='block';if(d.last_report&&d.last_report.summary){_ownerIntegrationLastReport=d.last_report;renderOwnerIntegrationReport(d.last_report);}return d;}catch(e){if(card)card.style.display='none';return null;}
}
function renderOwnerIntegrationReport(report){var pill=document.getElementById('ownerIntegrationStatus'),detail=document.getElementById('ownerIntegrationDetail'),out=document.getElementById('ownerIntegrationOutput'),s=report&&report.summary||{};if(pill){pill.textContent=report&&report.ok?'Passed':'Needs review';pill.classList.toggle('ok',!!(report&&report.ok));}if(detail)detail.textContent=(Number(s.passed)||0)+' passed · '+(Number(s.failed)||0)+' failed · '+(Number(s.skipped)||0)+' skipped';if(out){out.style.display='block';out.textContent=JSON.stringify(report,null,2);}}
async function runOwnerIntegrationSuite(mode,ev){var btn=ev&&ev.currentTarget?ev.currentTarget:null;if(btn)btn.disabled=true;try{var tests=['local_health','docx_generation'],confirmations={};if(mode==='connected')tests=['local_health','jobadder_candidate_read','onenote_read','outlook_read'];if(mode==='deepseek'){if(!window.confirm('Run one small PAID DeepSeek request using the securely saved main DeepSeek key?'))return false;var typed=window.prompt('Type RUN ONE PAID DEEPSEEK PROBE exactly:','')||'';if(typed!=='RUN ONE PAID DEEPSEEK PROBE')throw new Error('Paid probe cancelled: exact confirmation was not entered.');tests=['deepseek_paid_probe'];confirmations.deepseek=typed;}var candidate=String((document.getElementById('ownerIntegrationCandidateId')||{}).value||'').trim();var r=await fetch('/owner/integration/run',{method:'POST',headers:{'Content-Type':'application/json','X-CV-Studio-Owner-Test':'1'},body:JSON.stringify({tests:tests,fixtures:{jobadder_candidate_id:candidate},confirmations:confirmations})});var d=await r.json().catch(function(){return {};});_ownerIntegrationLastReport=d;renderOwnerIntegrationReport(d);if(!r.ok||!d.ok)throw new Error(d.error||d.message||'Owner integration suite needs review.');showToast('Owner integration suite passed.','ok');return true;}catch(e){showToast((e&&e.message)||'Owner integration suite failed.','err');return false;}finally{if(btn)btn.disabled=false;}}
function downloadOwnerIntegrationReport(){if(!_ownerIntegrationLastReport){showToast('Run an owner integration suite first.','err');return;}var blob=new Blob([JSON.stringify(_ownerIntegrationLastReport,null,2)],{type:'application/json;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='cv_studio_owner_integration_'+new Date().toISOString().replace(/[:.]/g,'-')+'.json';document.body.appendChild(a);a.click();setTimeout(function(){URL.revokeObjectURL(url);a.remove();},0);showToast('Owner integration report downloaded.','ok');}

// ── Settings tabs ───────────────────────────────────────────────────────────
function showSettingsTab(name) {
  name = name || 'routing';
  var suffixMap = {routing:'Routing', api:'Api', onenote:'OneNote', integrations:'Integrations', general:'General', background:'Background'};
  ['routing','api','onenote','integrations','general','background'].forEach(function(k){
    var suffix = suffixMap[k] || (k.charAt(0).toUpperCase() + k.slice(1));
    var pane = document.getElementById('settingsPane' + suffix);
    var btn = document.getElementById('settingsTab' + suffix);
    if (pane) pane.classList.toggle('active', k === name);
    if (btn) btn.classList.toggle('active', k === name);
  });
  if (name === 'routing') setTimeout(ensureAiRoutingRowsVisible, 0);
  if (name === 'onenote') setTimeout(oneNoteApiLoadSettings, 0);
  if (name === 'integrations') { setTimeout(refreshIntegrationDiagnostics, 0); setTimeout(ppcLoadOutlookSettingsPanel, 0); setTimeout(function(){ refreshCvStudioDiagnostics(false); }, 0); setTimeout(refreshOwnerIntegrationStatus, 0); }
  if (name === 'background') setTimeout(renderBackgroundSettings, 0);
  if (name === 'general') setTimeout(renderCvTextAlignmentSetting, 0);
}


// ── Shared Module Icons (visible UI only; internal keys unchanged) ───────────
function cvTabIcon(name) {
  var icons = {
    format: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M7 3.8h7l3 3v13.4H7z"></path><path d="M14 3.8v4h4"></path><path d="M9.2 12h5.6M9.2 15.2h4.2"></path></svg>',
    batch: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.8 4.8 7.4 12 11l7.2-3.6z"></path><path d="m4.8 11.2 7.2 3.6 7.2-3.6"></path><path d="m4.8 15 7.2 3.6 7.2-3.6"></path></svg>',
    summary: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M8 4.5h8l2 2v13H6v-15z"></path><path d="M9 9h6M9 12.5h6M9 16h4"></path></svg>',
    scoring: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="7.2"></circle><circle cx="12" cy="12" r="3.2"></circle><path d="M12 2.8v3M21.2 12h-3M12 21.2v-3M2.8 12h3"></path></svg>',
    owl: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M6.5 7.2 4.8 5.4v7.1c0 4.1 3.1 7.3 7.2 7.3s7.2-3.2 7.2-7.3V5.4l-1.7 1.8"></path><circle cx="9.4" cy="11" r="1.3"></circle><circle cx="14.6" cy="11" r="1.3"></circle><path d="M12 13.2l-1.2 1.3h2.4z"></path></svg>',
    spider: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="2.2"></circle><path d="M12 9.8V5.2M12 14.2v4.6M9.8 12H5.2M14.2 12h4.6M10.4 10.4 7.2 7.2M13.6 10.4l3.2-3.2M10.4 13.6l-3.2 3.2M13.6 13.6l3.2 3.2"></path></svg>',
    upload: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M7 18.5H6.2A4.2 4.2 0 0 1 6 10.1a6 6 0 0 1 11.5-1.8 4.8 4.8 0 0 1 .5 9.5H17"></path><path d="M12 19V11"></path><path d="m8.8 14.2 3.2-3.2 3.2 3.2"></path></svg>',
    profile: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="8" r="3.2"></circle><path d="M4.6 19.2c.7-3 2.8-4.8 5.4-4.8s4.7 1.8 5.4 4.8"></path><path d="M18.2 8.2v5M15.7 10.7h5"></path></svg>',
    blindjd: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 12s3.2-5 8.5-5 8.5 5 8.5 5a12.7 12.7 0 0 1-3.2 3.2M14.4 14.4A3.4 3.4 0 0 1 9.6 9.6"></path><path d="M4.5 4.5 19.5 19.5"></path></svg>',
    company: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M5.5 20V5.5h8V20"></path><path d="M13.5 10h5V20"></path><path d="M8 8h2M8 11h2M8 14h2M16 13h.1M16 16h.1"></path></svg>',
    lead: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="10.5" cy="10.5" r="5.8"></circle><path d="m15 15 4.5 4.5"></path><path d="M10.5 7.8v5.4M7.8 10.5h5.4"></path></svg>',
    dashboard: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 4.5h6v6h-6zM13.5 4.5h6v6h-6zM4.5 13.5h6v6h-6zM13.5 13.5h6v6h-6z"></path></svg>',
    lock: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="10" width="12" height="9" rx="2"></rect><path d="M8.7 10V7.7a3.3 3.3 0 0 1 6.6 0V10"></path></svg>'
  };
  return '<span class="tab-icon" aria-hidden="true">' + (icons[name] || icons.format) + '</span>';
}
function cvTabLabel(label, iconName) {
  return cvTabIcon(iconName) + '<span class="tab-label">' + esc(label) + '</span>';
}
function cvLockedTabLabel() {
  return cvTabIcon('lock') + '<span class="tab-label">Locked</span>';
}

// ── Locked Tab Version-Scoped Persistence ───────────────────────────────────
// Unlocks persist across normal browser/app restarts for the same installed build,
// but deliberately reset after a new CV Studio version is installed. This keeps the
// lock in place after upgrades while avoiding repeated prompts during daily use.
var LOCK_UNLOCK_VERSION = 'v24.6.338';
function versionedUnlockKey(base) {
  return base + '_' + String(LOCK_UNLOCK_VERSION || '').replace(/[^0-9A-Za-z]+/g, '_');
}
function readVersionedUnlock(base) {
  var key = versionedUnlockKey(base);
  try { if (localStorage.getItem(key) === '1') return true; } catch(e) {}
  try { return sessionStorage.getItem(key) === '1'; } catch(e) { return false; }
}
function writeVersionedUnlock(base) {
  var key = versionedUnlockKey(base);
  try { localStorage.setItem(key, '1'); } catch(e) {}
  try { sessionStorage.setItem(key, '1'); } catch(e) {}
}

// ── Summary Tab Lock ─────────────────────────────────────────────────────────
var SUMMARY_LOCK_CODE = '1212';
function summaryIsUnlocked() {
  return readVersionedUnlock('hy_summary_unlocked');
}
function summarySetUnlocked() {
  writeVersionedUnlock('hy_summary_unlocked');
  updateSummaryLockUI();
}
function updateSummaryLockUI() {
  var tab = document.getElementById('tabSummary');
  if (!tab) return;
  if (summaryIsUnlocked()) {
    tab.innerHTML = cvTabLabel('CV Summary', 'summary');
    tab.classList.remove('summary-locked');
    tab.title = 'CV Summary';
    tab.setAttribute('data-base-title', 'CV Summary');
  } else {
    tab.innerHTML = cvLockedTabLabel();
    tab.classList.add('summary-locked');
    tab.title = 'Locked tab';
  }
}
function requestSummaryUnlock() {
  if (summaryIsUnlocked()) return true;
  var code = window.prompt('CV Summary tab is locked. Enter the 4-digit access code to unlock:');
  if (code === SUMMARY_LOCK_CODE) {
    summarySetUnlocked();
    showToast('CV Summary unlocked', 'ok');
    return true;
  }
  window.alert('Incorrect or missing code. Returning to other tabs.');
  updateSummaryLockUI();
  return false;
}
function requireSummaryUnlocked() {
  if (requestSummaryUnlock()) return true;
  switchTab('format');
  return false;
}

var CV_SCORING_LOCK_CODE = '1996';
function cvScoringIsUnlocked() {
  return readVersionedUnlock('hy_cv_scoring_unlocked');
}
function cvScoringSetUnlocked() {
  writeVersionedUnlock('hy_cv_scoring_unlocked');
  updateCvScoringLockUI();
}
function updateCvScoringLockUI() {
  var tab = document.getElementById('tabAppraiser');
  if (!tab) return;
  if (cvScoringIsUnlocked()) {
    tab.innerHTML = cvTabLabel('CV Scoring', 'scoring');
    tab.classList.remove('appraiser-locked');
    tab.title = 'CV Scoring';
    tab.setAttribute('data-base-title', 'CV Scoring');
  } else {
    tab.innerHTML = cvLockedTabLabel();
    tab.classList.add('appraiser-locked');
    tab.title = 'Locked tab';
    tab.setAttribute('data-base-title', 'Locked tab');
  }
}
function requestCvScoringUnlock() {
  if (cvScoringIsUnlocked()) return true;
  var code = window.prompt('CV Scoring is locked. Enter the 4-digit access code to unlock:');
  if (code === CV_SCORING_LOCK_CODE) {
    cvScoringSetUnlocked();
    showToast('CV Scoring unlocked', 'ok');
    return true;
  }
  window.alert('Incorrect or missing code. Returning to other tabs.');
  updateCvScoringLockUI();
  return false;
}

