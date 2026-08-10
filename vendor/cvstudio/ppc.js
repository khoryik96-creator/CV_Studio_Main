// ── PPC / Post Placement Care ───────────────────────────────────────────────
var PPC_META_STORE = 'cvstudio_ppc_meta_v1';
var PPC_UI_STORE = 'cvstudio_ppc_ui_state_v1';
var PPC_CACHE_DB = 'cvstudio_ppc_cache_v1';
var PPC_CACHE_OBJECT_STORE = 'queries';
var PPC_CACHE_FALLBACK_STORE = 'cvstudio_ppc_cache_fallback_v1';
var PPC_KPI_VIS_STORE = 'cvstudio_ppc_kpi_visibility_v1';
var PPC_COLUMN_VIS_STORE = 'cvstudio_ppc_column_visibility_v1';
var PPC_INVOICE_EMAIL_STORE = 'cvstudio_ppc_invoice_email_v1';
var PPC_OUTLOOK_LEGACY_TOKEN_STORE = 'cvstudio_ppc_outlook_ms_token_v1';
var PPC_OUTLOOK_DEVICE_STORE = 'cvstudio_ppc_outlook_ms_device_v1';
var PPC_OUTLOOK_CLIENT_STORE = 'cvstudio_ppc_outlook_ms_client_v1';
var PPC_OUTLOOK_DRAFT_STORE = 'cvstudio_ppc_outlook_drafts_v1';
var PPC_CACHE_SCHEMA = 5;
var PPC_PAGE_SIZE = 100;
var _ppcItems = [];
var _ppcBaseFiltered = [];
var _ppcFiltered = [];
var _ppcPage = 1;
var _ppcLoadedAt = 0;
var _ppcLoadingNow = false;
var _ppcRangeMode = 'year';
var _ppcUiRestored = false;
var _ppcSavedUiState = null;
var _ppcActiveQueryKey = '';
var _ppcMemoryCache = {};
var _ppcAccountRunSeq = 0;
var _ppcKpiFilter = '';
var _ppcSelectedPlacementId = '';
var _ppcOutlookConnected = false;
var _ppcOutlookRestorePromise = null;
var _ppcOutlookAccount = {};
var _ppcOutlookStorage = '';
var _ppcOutlookLastError = null;
var _ppcDraftBusy = {};
var _ppcInvoicePreviewPlacementId = '';
var _ppcInvoicePreviewMessage = null;
var _ppcInvoiceForceNewDraft = false;
var _ppcMetaSqliteCache = null;
var _ppcMetaMutationVersion = 0;
var _ppcMetaHydrationPromise = null;
var _ppcMetaWriteQueue = Promise.resolve();

function ppcMetaLegacyLoad() {
  try {
    var d = JSON.parse(localStorage.getItem(PPC_META_STORE) || '{}');
    return d && typeof d === 'object' && !Array.isArray(d) ? d : {};
  } catch(e) { return {}; }
}
function ppcMetaMerge(sqliteData, legacyData) {
  var merged = {};
  function add(source, preferNewer) {
    if (!source || typeof source !== 'object' || Array.isArray(source)) return;
    Object.keys(source).forEach(function(id){
      var incoming=source[id];
      if (!incoming || typeof incoming !== 'object' || Array.isArray(incoming)) return;
      var existing=merged[id];
      if (!existing) { merged[id]=incoming; return; }
      if (!preferNewer) { merged[id]=incoming; return; }
      var incomingAt=String(incoming.updatedAt||''),existingAt=String(existing.updatedAt||'');
      if (incomingAt && (!existingAt || incomingAt>=existingAt)) merged[id]=incoming;
    });
  }
  add(sqliteData, false);
  add(legacyData, true);
  return merged;
}
function ppcMetaStoragePost(path, payload) {
  return fetch(path, {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(payload || {})
  }).then(function(response){
    return response.json().catch(function(){return {};}).then(function(data){
      if (!response.ok || !data.ok) throw new Error(data.message || data.error || 'Local PPC storage request failed');
      return data;
    });
  });
}
function ppcMetaQueuePost(path, payload) {
  _ppcMetaWriteQueue=_ppcMetaWriteQueue.catch(function(){}).then(function(){return ppcMetaStoragePost(path,payload);});
  return _ppcMetaWriteQueue;
}
function ppcMetaLoad() {
  var source=_ppcMetaSqliteCache && typeof _ppcMetaSqliteCache==='object' && !Array.isArray(_ppcMetaSqliteCache)
    ? _ppcMetaSqliteCache : ppcMetaLegacyLoad();
  return Object.assign({},source||{});
}
function ppcMetaSave(data) {
  data=data&&typeof data==='object'&&!Array.isArray(data)?data:{};
  _ppcMetaSqliteCache=Object.assign({},data);
  _ppcMetaMutationVersion+=1;
  try { localStorage.setItem(PPC_META_STORE, JSON.stringify(data)); } catch(e) {}
  ppcMetaQueuePost('/storage/ppc-metadata/upsert',{metadata:data}).catch(function(){});
}
function ppcMetaHydrateFromSQLite() {
  if (_ppcMetaHydrationPromise) return _ppcMetaHydrationPromise;
  var startedVersion=_ppcMetaMutationVersion,legacy=ppcMetaLegacyLoad();
  _ppcMetaHydrationPromise=ppcMetaStoragePost('/storage/ppc-metadata/import',{metadata:legacy}).then(function(data){
    var merged=ppcMetaMerge(data.metadata,ppcMetaLegacyLoad());
    _ppcMetaSqliteCache=merged;
    try{localStorage.setItem(PPC_META_STORE,JSON.stringify(merged));}catch(e){}
    if(_ppcMetaMutationVersion!==startedVersion)ppcMetaQueuePost('/storage/ppc-metadata/upsert',{metadata:merged}).catch(function(){});
    try{if(_ppcItems.length)ppcApplyFilters(false);}catch(e){}
    return merged;
  }).catch(function(){
    _ppcMetaSqliteCache=ppcMetaLegacyLoad();
    return _ppcMetaSqliteCache;
  });
  return _ppcMetaHydrationPromise;
}
window.addEventListener('load',function(){setTimeout(ppcMetaHydrateFromSQLite,0);});
function ppcUpdateMeta(placementId, field, value) {
  var id = String(placementId || '');
  if (!id) return;
  var all = ppcMetaLoad();
  var row = all[id] && typeof all[id] === 'object' ? all[id] : {};
  if (field === 'payment') row.payment = ['Paid','Unpaid','Invoiced'].indexOf(value) >= 0 ? value : '';
  if (field === 'guaranteeMonths') {
    var guaranteeValue=String(value||'');
    row.guaranteeMonths = /^(?:[1-6]|9|12|resigned_backout)$/.test(guaranteeValue) ? guaranteeValue : '';
  }
  row.updatedAt = new Date().toISOString();
  all[id] = row;
  ppcMetaSave(all);
  ppcApplyFilters(false);
}
function ppcMetaFor(item) {
  var all = ppcMetaLoad();
  return all[String((item || {}).placement_id || '')] || {};
}
function ppcInvoiceEmailValid(value){
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value||'').trim());
}
function ppcInvoiceSettingsLoad(){
  // v24.6.175 restored the saved Outlook recipient. Older v24.6.173
  // recipient values use the same storage key and remain compatible.
  try{
    var d=JSON.parse(localStorage.getItem(PPC_INVOICE_EMAIL_STORE)||'{}');
    if(!d||typeof d!=='object'||Array.isArray(d))d={};
    return {
      recipient:String(d.recipient||d.recipientEmail||d.email||d.to||'').trim(),
      greeting:String(d.greeting||'Syah').trim()||'Syah'
    };
  }catch(e){return {recipient:'',greeting:'Syah'};}
}
function ppcInvoiceSettingsSave(settings){
  try{
    cvStudioDurableSettingSet(PPC_INVOICE_EMAIL_STORE,JSON.stringify({
      recipient:String((settings||{}).recipient||'').trim(),
      greeting:String((settings||{}).greeting||'Syah').trim()||'Syah'
    }));
  }catch(e){}
}
function ppcConfigureInvoiceEmail(){
  var current=ppcInvoiceSettingsLoad();
  var recipient=window.prompt('Invoice recipient email for the Outlook To field',current.recipient||'');
  if(recipient===null)return false;
  recipient=String(recipient||'').trim();
  if(recipient&&!ppcInvoiceEmailValid(recipient)){
    showToast('Enter a valid invoice recipient email, or leave it blank to clear the saved recipient.','err');
    return false;
  }
  var greeting=window.prompt('Greeting name for the invoice request',current.greeting||'Syah');
  if(greeting===null)return false;
  greeting=String(greeting||'').trim()||'Syah';
  ppcInvoiceSettingsSave({recipient:recipient,greeting:greeting});
  ppcRender();
  ppcUpdateOutlookConnectButton();
  showToast(recipient?'Invoice recipient and greeting saved. Connect Outlook once for the exact rich draft format.':'Saved recipient cleared. The next Outlook click will ask for one.','ok');
  return true;
}
function ppcInvoiceMoney(item){
  var raw=(item||{}).placement_fee;
  if(raw===null||raw===undefined||raw==='')return 'Not provided in JobAdder';
  var fee=Number(raw);
  if(!isFinite(fee))return 'Not provided in JobAdder';
  var formatted=fee.toLocaleString('en-MY',{minimumFractionDigits:Number.isInteger(fee)?0:2,maximumFractionDigits:2});
  return (String((item||{}).charge_currency||'').trim()?String(item.charge_currency).trim()+' ':'')+formatted;
}
function ppcFindPlacement(placementId){
  var id=String(placementId||'');return _ppcItems.find(function(item){return String((item||{}).placement_id||'')===id;})||null;
}
function ppcInvoiceSubjectPart(value,fallback){
  var text=String(value||'').replace(/[\r\n\t]+/g,' ').replace(/\s{2,}/g,' ').trim();
  return text||fallback;
}
function ppcBuildInvoiceSubject(item){
  item=item||{};
  return 'Hyppies: Invoice - '
    +ppcInvoiceSubjectPart(item.company_name,'Client not provided')+' - '
    +ppcInvoiceSubjectPart(item.job_title,'Position not provided')+' - '
    +ppcInvoiceSubjectPart(item.candidate_name,'Candidate not provided')+' - '
    +ppcInvoiceSubjectPart(item.placed_by,'Recruiter not provided');
}
function ppcInvoiceRows(item){
  item=item||{};
  var unavailable='Not provided in JobAdder';
  return [
    ['Candidate Name',item.candidate_name||unavailable],
    ['Position Title',item.job_title||unavailable],
    ['Commencement Date',item.start_date?ppcFormatDate(item.start_date):unavailable],
    ['Fee Calculation',ppcInvoiceMoney(item)],
    ['Payment Term',item.billing_payment_terms||unavailable],
    ['Client Email',item.billing_email||unavailable],
    ['Link to the JobAdder',ppcPlacementUrl(item.placement_id)]
  ];
}
function ppcInvoiceHtmlEscape(value){
  return String(value==null?'':value).replace(/[&<>\"]/g,function(ch){return {'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[ch]||ch;});
}
function ppcBuildInvoiceHtml(item,settings){
  var rows=ppcInvoiceRows(item);
  var greeting=ppcInvoiceHtmlEscape((settings||{}).greeting||'Syah');
  var base='font-family:Calibri,Arial,sans-serif;font-size:11pt;line-height:1.25;color:#000000;';
  var table=rows.map(function(row){
    var label=ppcInvoiceHtmlEscape(row[0]),value=ppcInvoiceHtmlEscape(row[1]);
    return '<tr>'
      +'<td width="155" style="'+base+'width:155px;font-weight:700;white-space:nowrap;padding:0 0 4px 0;vertical-align:top;"><strong style="font-weight:700;color:#000000;">'+label+'</strong></td>'
      +'<td width="14" style="'+base+'width:14px;font-weight:700;text-align:left;padding:0 0 4px 0;vertical-align:top;"><strong style="font-weight:700;color:#000000;">:</strong></td>'
      +'<td style="'+base+'padding:0 0 4px 0;vertical-align:top;">'+value+'</td>'
      +'</tr>';
  }).join('');
  return '<div style="'+base+'background:#ffffff;">'
    +'<p style="'+base+'margin:0 0 12px 0;">Hi '+greeting+',</p>'
    +'<p style="'+base+'margin:0 0 14px 0;">Need your help to raise the following invoice for the below:</p>'
    +'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse:collapse;border-spacing:0;mso-table-lspace:0pt;mso-table-rspace:0pt;margin:0 0 14px 0;'+base+'">'+table+'</table>'
    +'<p style="'+base+'margin:0 0 12px 0;">Do let me know if you\'d require any further information. Thanks!</p>'
    +'<p style="'+base+'margin:0;">Thank you!</p>'
    +'</div>';
}
function ppcBuildInvoiceEmail(item,settings){
  var rows=ppcInvoiceRows(item);
  var labels=rows.map(function(row){return row[0];});
  var width=labels.reduce(function(max,label){return Math.max(max,label.length);},0);
  var lines=[
    'Hi '+((settings||{}).greeting||'Syah')+',','',
    'Need your help to raise the following invoice for the below:',''
  ];
  rows.forEach(function(row){lines.push(String(row[0]).padEnd(width,' ')+' : '+row[1]);});
  lines.push('',"Do let me know if you'd require any further information. Thanks!",'','Thank you!');
  return {subject:ppcBuildInvoiceSubject(item),body:lines.join('\r\n'),html:ppcBuildInvoiceHtml(item,settings)};
}
function ppcOutlookClientLoad(){
  var d={};
  try{d=JSON.parse(localStorage.getItem(PPC_OUTLOOK_CLIENT_STORE)||'{}')||{};}catch(e){d={};}
  return {client_id:String(d.client_id||'').trim(),tenant:String(d.tenant||'common').trim()||'common'};
}
function ppcOutlookClientSave(data){
  try{cvStudioDurableSettingSet(PPC_OUTLOOK_CLIENT_STORE,JSON.stringify({client_id:String((data||{}).client_id||'').trim(),tenant:String((data||{}).tenant||'common').trim()||'common'}));}catch(e){}
}
function ppcOutlookClientIdValid(value){return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(String(value||'').trim());}
function ppcOutlookStorageLabel(value){
  value=String(value||'');
  if(value==='windows_dpapi')return 'Windows DPAPI';
  if(value==='macos_keychain')return 'macOS Keychain';
  if(value==='machine_bound_file')return 'Authenticated machine-bound file fallback';
  return value||'Not available';
}
function ppcOutlookAccountLabel(){
  var a=_ppcOutlookAccount||{};
  return String(a.email||a.displayName||'').trim();
}
function ppcSetOutlookTechnicalError(payload){
  _ppcOutlookLastError=payload||null;
  var pre=document.getElementById('settingsOutlookTechnicalText');
  var details=document.getElementById('settingsOutlookTechnicalDetails');
  if(pre){
    if(!payload)pre.textContent='No Microsoft error recorded.';
    else pre.textContent=[payload.error_code?('Code: '+payload.error_code):'',payload.action?('Action: '+payload.action):'',payload.technical_details||payload.detail||''].filter(Boolean).join('\n\n')||String(payload.error||'Unknown Microsoft error');
  }
  if(details&&payload)details.open=true;
  var modalErr=document.getElementById('ppcInvoicePreviewError');
  if(modalErr&&payload){modalErr.textContent=String(payload.error||'Outlook request failed')+(payload.action?' '+payload.action:'');modalErr.classList.add('show');}
}
function ppcShowOutlookError(payload,fallback){
  payload=payload||{};ppcSetOutlookTechnicalError(payload);
  var msg=String(payload.error||fallback||'Microsoft Outlook request failed');
  if(payload.action)msg+=' '+String(payload.action);
  showToast(msg,'err');
  return msg;
}
function ppcOutlookDeviceLoad(){try{var d=JSON.parse(localStorage.getItem(PPC_OUTLOOK_DEVICE_STORE)||'{}');return d&&typeof d==='object'&&!Array.isArray(d)?d:{};}catch(e){return {};}}
function ppcOutlookDeviceSave(d){try{if(d&&d.login_session_id)localStorage.setItem(PPC_OUTLOOK_DEVICE_STORE,JSON.stringify(d));else localStorage.removeItem(PPC_OUTLOOK_DEVICE_STORE);}catch(e){}}
function ppcOutlookPurgeLegacyBrowserToken(){try{localStorage.removeItem(PPC_OUTLOOK_LEGACY_TOKEN_STORE);localStorage.removeItem('cvstudio_ppc_outlook_ms_token_v1');}catch(e){}}
function ppcRenderOutlookIntegrationState(){
  var account=ppcOutlookAccountLabel();
  var cfg=ppcOutlookClientLoad();
  var badge=document.getElementById('ppcOutlookAccountBadge');
  if(badge){badge.textContent=_ppcOutlookConnected?(account?('Outlook: '+account):'Outlook connected'):'Outlook account: —';badge.title=_ppcOutlookConnected?('Connected Microsoft account'+(account?': '+account:'')):'Outlook is not connected';}
  var status=document.getElementById('settingsOutlookStatus');
  if(status){status.textContent=_ppcOutlookConnected?'Connected':'Not connected';status.style.background=_ppcOutlookConnected?'rgba(34,197,94,.14)':'rgba(245,158,11,.14)';}
  var accountEl=document.getElementById('settingsOutlookAccount');
  if(accountEl)accountEl.textContent='Connected account: '+(_ppcOutlookConnected?(account||'Connected account name unavailable'):'—');
  var storageEl=document.getElementById('settingsOutlookStorage');
  if(storageEl)storageEl.textContent='Secret storage: '+ppcOutlookStorageLabel(_ppcOutlookStorage);
  var client=document.getElementById('settingsOutlookClientId'),tenant=document.getElementById('settingsOutlookTenant');
  if(client&&document.activeElement!==client)client.value=cfg.client_id||'';
  if(tenant&&document.activeElement!==tenant)tenant.value=cfg.tenant||'common';
  var settingsBtn=document.getElementById('settingsOutlookConnectBtn');
  if(settingsBtn)settingsBtn.textContent=_ppcOutlookConnected?'Reconnect':(ppcOutlookDeviceLoad().login_session_id?'Finish Login':'Connect');
}
function ppcUpdateOutlookConnectButton(){
  var btn=document.getElementById('ppcOutlookConnectBtn');
  var pending=ppcOutlookDeviceLoad(),cfg=ppcOutlookClientLoad();
  if(btn){
    if(_ppcOutlookConnected){btn.textContent='Outlook connected';btn.classList.add('connected');btn.title='Connected as '+(ppcOutlookAccountLabel()||'Microsoft account')+'. Click to reconnect.';}
    else if(pending&&pending.login_session_id){btn.textContent='Finish Outlook Login';btn.classList.remove('connected');btn.title='Finish the Microsoft device login, then click here.';}
    else if(!cfg.client_id){btn.textContent='Connect Outlook';btn.classList.remove('connected');btn.title='Open Outlook settings and save a dedicated Microsoft app Client ID first.';}
    else{btn.textContent='Connect Outlook';btn.classList.remove('connected');btn.title='Connect Microsoft Outlook using the saved app registration.';}
  }
  ppcRenderOutlookIntegrationState();
}
function ppcOpenOutlookSettings(){
  var panel=ensureSettingsPanelTopLayer(),backdrop=document.getElementById('settingsBackdrop');
  if(panel)panel.style.display='block';if(backdrop)backdrop.style.display='block';if(document.body)document.body.classList.add('settings-open');
  showSettingsTab('integrations');setTimeout(ppcLoadOutlookSettingsPanel,0);return false;
}
function ppcConfigureOutlookClient(){return ppcOpenOutlookSettings();}
function ppcLoadOutlookSettingsPanel(){
  var cfg=ppcOutlookClientLoad();
  var c=document.getElementById('settingsOutlookClientId'),t=document.getElementById('settingsOutlookTenant');
  if(c)c.value=cfg.client_id||'';if(t)t.value=cfg.tenant||'common';
  ppcRenderOutlookIntegrationState();refreshIntegrationDiagnostics();
}
async function ppcSaveOutlookSettingsFromPanel(){
  var old=ppcOutlookClientLoad();
  var clientId=String((document.getElementById('settingsOutlookClientId')||{}).value||'').trim();
  var tenant=String((document.getElementById('settingsOutlookTenant')||{}).value||'common').trim()||'common';
  if(!ppcOutlookClientIdValid(clientId)){showToast('Enter a valid Microsoft Outlook app Client ID in GUID format.','err');return false;}
  var changed=clientId!==old.client_id||tenant!==old.tenant;
  if(changed&&_ppcOutlookConnected){
    if(!window.confirm('Changing the Outlook app settings will disconnect the current Microsoft account. Continue?'))return false;
    await ppcDisconnectOutlook(false);
  }
  ppcOutlookClientSave({client_id:clientId,tenant:tenant});ppcOutlookDeviceSave(null);ppcUpdateOutlookConnectButton();
  showToast('Outlook app settings saved. Connect Outlook to approve User.Read and Mail.ReadWrite.','ok');return true;
}
async function ppcRestoreOutlookToken(force){
  if(_ppcOutlookRestorePromise&&!force)return _ppcOutlookRestorePromise;
  _ppcOutlookRestorePromise=(async function(){
    ppcOutlookPurgeLegacyBrowserToken();
    try{
      var r=await fetch('/ppc/outlook/api_info',{cache:'no-store'}),d=await r.json().catch(function(){return {};});
      if(!r.ok)throw new Error(d.error||'Could not read Outlook connection state');
      _ppcOutlookConnected=!!d.connected;_ppcOutlookAccount=d.account||{};_ppcOutlookStorage=d.storage||'';
      ppcUpdateOutlookConnectButton();return _ppcOutlookConnected;
    }catch(e){_ppcOutlookConnected=false;_ppcOutlookAccount={};ppcUpdateOutlookConnectButton();return false;}
  })();
  try{return await _ppcOutlookRestorePromise;}finally{_ppcOutlookRestorePromise=null;}
}
async function ppcDisconnectOutlook(showMessage){
  ppcOutlookPurgeLegacyBrowserToken();ppcOutlookDeviceSave(null);_ppcOutlookConnected=false;_ppcOutlookAccount={};ppcUpdateOutlookConnectButton();
  try{
    var r=await fetch('/ppc/outlook/disconnect',{method:'POST'}),d=await r.json().catch(function(){return {};});
    if(!r.ok)throw new Error(d.error||'Could not disconnect Outlook');
    _ppcOutlookStorage=d.storage||_ppcOutlookStorage;if(showMessage!==false)showToast('Microsoft Outlook disconnected.','ok');return true;
  }catch(e){if(showMessage!==false)showToast((e&&e.message)||'Could not disconnect Outlook','err');return false;}
}
function ppcOutlookTokenClear(){ppcDisconnectOutlook(false);}
async function ppcStartOutlookLogin(){
  var cfg=ppcOutlookClientLoad();
  if(!ppcOutlookClientIdValid(cfg.client_id)){ppcOpenOutlookSettings();showToast('Save a dedicated Microsoft Outlook app Client ID first.','info');return false;}
  var r=await fetch('/ppc/outlook/device_start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cfg)}),d=await r.json().catch(function(){return {};});
  if(!r.ok){ppcShowOutlookError(d,'Could not start Outlook login');return false;}
  var pending={login_session_id:d.login_session_id,user_code:d.user_code||'',verification_uri:d.verification_uri||'https://microsoft.com/devicelogin',expires_at:Date.now()+((d.expires_in||900)*1000)};
  ppcOutlookDeviceSave(pending);ppcUpdateOutlookConnectButton();ppcSetOutlookTechnicalError(null);
  try{if(navigator.clipboard&&navigator.clipboard.writeText)await navigator.clipboard.writeText(pending.user_code);}catch(e){}
  var loginWindow=null;try{loginWindow=window.open(pending.verification_uri,'_blank');}catch(e){loginWindow=null;}
  window.alert('Microsoft Outlook login code: '+pending.user_code+'\n\nThe code was copied when clipboard access was available. Complete the Microsoft login and approve User.Read and Mail.ReadWrite. Then return to CV Studio and click Finish Outlook Login.');
  showToast(loginWindow?'Microsoft Outlook login opened. Finish it, then click Finish Outlook Login.':'Open microsoft.com/devicelogin, enter '+pending.user_code+', then click Finish Outlook Login.','info');return true;
}
async function ppcFinishOutlookLogin(){
  var dev=ppcOutlookDeviceLoad();
  if(!dev||!dev.login_session_id){showToast('Start Outlook login first.','err');return false;}
  if(dev.expires_at&&Date.now()>Number(dev.expires_at)){ppcOutlookDeviceSave(null);ppcUpdateOutlookConnectButton();showToast('The Outlook login code expired. Start again.','err');return false;}
  var r=await fetch('/ppc/outlook/device_poll',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({login_session_id:dev.login_session_id})}),d=await r.json().catch(function(){return {};});
  if(r.status===202||d.pending){ppcSetOutlookTechnicalError(d);showToast((d.error||'Microsoft Outlook login is still pending.')+' '+(d.action||''),'info');return false;}
  if(!r.ok||!d.connected){ppcShowOutlookError(d,'Outlook login was not completed');if(r.status===400||r.status===401)ppcOutlookDeviceSave(null);ppcUpdateOutlookConnectButton();return false;}
  ppcOutlookDeviceSave(null);_ppcOutlookConnected=true;_ppcOutlookAccount=d.account||{};_ppcOutlookStorage=d.storage||'';ppcSetOutlookTechnicalError(null);ppcUpdateOutlookConnectButton();
  showToast('Microsoft Outlook connected as '+(ppcOutlookAccountLabel()||'the approved account')+'.','ok');return true;
}
async function ppcConnectOutlookDrafts(){
  var dev=ppcOutlookDeviceLoad();if(dev&&dev.login_session_id)return ppcFinishOutlookLogin();
  if(_ppcOutlookConnected){if(!window.confirm('Outlook is connected as '+(ppcOutlookAccountLabel()||'a Microsoft account')+'. Reconnect with another account?'))return true;await ppcDisconnectOutlook(false);}
  return ppcStartOutlookLogin();
}
async function ppcTestOutlookConnection(){
  var r=await fetch('/ppc/outlook/test_connection',{method:'POST'}),d=await r.json().catch(function(){return {};});
  if(!r.ok){ppcShowOutlookError(d,'Outlook connection test failed');if(d.needs_reconnect)await ppcDisconnectOutlook(false);return false;}
  _ppcOutlookConnected=true;_ppcOutlookAccount=d.account||{};_ppcOutlookStorage=d.storage||_ppcOutlookStorage;ppcSetOutlookTechnicalError(null);ppcUpdateOutlookConnectButton();showToast('Outlook connection works for '+(ppcOutlookAccountLabel()||'the connected account')+'.','ok');return true;
}
async function ppcCreateOutlookTestDraft(event){
  if(event){event.preventDefault();event.stopPropagation();}
  var opened=null;try{opened=window.open('about:blank','_blank');}catch(e){}
  if(!opened){showToast('Allow pop-ups for CV Studio to open the test draft.','err');return false;}
  var r=await fetch('/ppc/outlook/create_test_draft',{method:'POST'}),d=await r.json().catch(function(){return {};});
  if(!r.ok){try{opened.close();}catch(e){}ppcShowOutlookError(d,'Could not create the Outlook test draft');if(d.needs_reconnect)await ppcDisconnectOutlook(false);return false;}
  try{opened.opener=null;opened.location.replace(d.webLink);}catch(e){try{opened.location.href=d.webLink;}catch(ignore){}}
  if(d.account){_ppcOutlookAccount=d.account;ppcUpdateOutlookConnectButton();}showToast('Test draft created. Nothing was sent.','ok');return true;
}
function ppcDraftStoreLoad(){try{var d=JSON.parse(localStorage.getItem(PPC_OUTLOOK_DRAFT_STORE)||'{}');return d&&typeof d==='object'&&!Array.isArray(d)?d:{};}catch(e){return {};}}
function ppcDraftStoreSave(data){try{cvStudioDurableSettingSet(PPC_OUTLOOK_DRAFT_STORE,JSON.stringify(data||{}));}catch(e){}}
function ppcLastDraftFor(id){return ppcDraftStoreLoad()[String(id||'')]||null;}
function ppcDraftIsRecent(last,minutes){var d=new Date((last||{}).created_at||'');return !!((last||{}).webLink&&!isNaN(d.getTime())&&(Date.now()-d.getTime())<Math.max(1,Number(minutes||30))*60000);}
function ppcDraftFingerprint(item,settings){
  var message=ppcBuildInvoiceEmail(item,settings),text=String(settings.recipient||'')+'\n'+message.subject+'\n'+message.html,hash=2166136261;
  for(var i=0;i<text.length;i++){hash^=text.charCodeAt(i);hash=Math.imul(hash,16777619);}return (hash>>>0).toString(16)+':'+text.length;
}
function ppcSaveLastDraft(id,data,requestId){
  var all=ppcDraftStoreLoad(),key=String(id||''),old=all[key]||{};all[key]={webLink:String(data.webLink||''),draft_id:String(data.draft_id||''),created_at:String(data.created_at||new Date().toISOString()),subject:String(data.subject||'')};
  if(requestId&&old.pending_request_id&&old.pending_request_id!==requestId){all[key].previous_pending_request_id=String(old.pending_request_id);}
  var keys=Object.keys(all).sort(function(a,b){return String((all[b]||{}).created_at||'').localeCompare(String((all[a]||{}).created_at||''));});keys.slice(300).forEach(function(k){delete all[k];});ppcDraftStoreSave(all);
}
function ppcClearPendingDraftRequest(id,requestId){var all=ppcDraftStoreLoad(),key=String(id||''),entry=all[key]||{};if(!requestId||entry.pending_request_id===requestId){delete entry.pending_request_id;delete entry.pending_at;delete entry.pending_fingerprint;if(Object.keys(entry).length)all[key]=entry;else delete all[key];ppcDraftStoreSave(all);}}
function ppcDraftRequestId(item,settings,forceNew){
  var id=String(item&&item.placement_id||item&&item.id||_ppcInvoicePreviewPlacementId||''),all=ppcDraftStoreLoad(),entry=all[id]||{},fingerprint=ppcDraftFingerprint(item,settings),pendingTime=new Date(entry.pending_at||'').getTime();
  if(!forceNew&&entry.pending_request_id&&entry.pending_fingerprint===fingerprint&&!isNaN(pendingTime)&&(Date.now()-pendingTime)<1800000)return String(entry.pending_request_id);
  var requestId=ppcNewDraftRequestId(id);entry.pending_request_id=requestId;entry.pending_fingerprint=fingerprint;entry.pending_at=new Date().toISOString();all[id]=entry;ppcDraftStoreSave(all);return requestId;
}
function ppcDraftTimeLabel(value){var d=new Date(value);if(isNaN(d.getTime()))return '';try{return d.toLocaleString();}catch(e){return String(value||'');}}
function ppcOpenLastDraft(event,placementId){
  if(event){event.preventDefault();event.stopPropagation();}var last=ppcLastDraftFor(placementId);if(!last||!last.webLink){showToast('No saved Outlook draft link for this placement.','info');return false;}
  var w=null;try{w=window.open(last.webLink,'_blank');if(w)w.opener=null;}catch(e){}if(!w)showToast('The browser blocked the Outlook draft tab. Allow pop-ups for CV Studio.','err');return false;
}
function ppcSetDraftBusy(placementId,busy){var id=String(placementId||'');if(busy)_ppcDraftBusy[id]=true;else delete _ppcDraftBusy[id];ppcRender();var btn=document.getElementById('ppcInvoicePreviewCreateBtn');if(btn){btn.disabled=!!busy;btn.textContent=busy?'Creating draft…':(_ppcInvoiceForceNewDraft?'Create another draft':'Create Outlook Draft');}}
function ppcNewDraftRequestId(placementId){var rand='';try{rand=crypto&&crypto.getRandomValues?Array.from(crypto.getRandomValues(new Uint32Array(2))).map(function(x){return x.toString(16);}).join(''):Math.random().toString(36).slice(2);}catch(e){rand=Math.random().toString(36).slice(2);}return 'ppc:'+String(placementId||'')+':'+Date.now()+':'+rand;}
function ppcRenderInvoiceActions(pid){
  var id=String(pid||''),busy=!!_ppcDraftBusy[id],last=ppcLastDraftFor(id),recent=ppcDraftIsRecent(last,30),primary='';
  if(busy)primary='<a class="ppc-invoice-btn busy" aria-disabled="true" href="#" onclick="event.preventDefault();event.stopPropagation();return false;">Creating draft…</a>';
  else if(recent)primary='<a class="ppc-invoice-btn" href="#" onclick="return ppcOpenLastDraft(event,\''+escAttr(id)+'\')" title="Open the draft created for this placement instead of creating an accidental duplicate.">Open created draft</a>';
  else primary='<a class="ppc-invoice-btn" href="#" onclick="return ppcOpenInvoicePreview(event,\''+escAttr(id)+'\',false)" title="Review the exact recipient, subject and rich Calibri 11 HTML body before creating the Outlook draft.">Review &amp; create</a>';
  var copy='<button type="button" class="ppc-invoice-copy-btn" '+(busy?'disabled ':'')+'onclick="event.stopPropagation();ppcCopyInvoiceFormatted(\''+escAttr(id)+'\',false);return false;" title="Copy the invoice request as rich Calibri 11 HTML with bold aligned labels.">Copy formatted</button>';
  var meta='';if(last&&last.webLink){meta='<div class="ppc-draft-meta">Draft created '+esc(ppcDraftTimeLabel(last.created_at))+(recent?' · <button type="button" class="ppc-last-draft-btn" onclick="return ppcOpenInvoicePreview(event,\''+escAttr(id)+'\',true)">Create another</button>':' · <button type="button" class="ppc-last-draft-btn" onclick="return ppcOpenLastDraft(event,\''+escAttr(id)+'\')">Open last draft</button>')+'</div>';}
  return '<td data-col="invoice-email"><div class="ppc-invoice-actions">'+primary+copy+meta+'</div></td>';
}
async function ppcCreateRichOutlookDraft(item,settings,requestId){
  var connected=_ppcOutlookConnected||await ppcRestoreOutlookToken(false);if(!connected)return {ok:false,needs_connect:true,error:'Outlook rich draft connection is not set up',action:'Connect Outlook in Settings → Integrations & Data.'};
  var message=ppcBuildInvoiceEmail(item,settings);
  try{
    var r=await fetch('/ppc/outlook/create_draft',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({to:settings.recipient,subject:message.subject,html:message.html,request_id:requestId})}),d=await r.json().catch(function(){return {};});
    if(!r.ok)return Object.assign({ok:false,needs_connect:!!d.needs_reconnect},d);
    if(!d.webLink)return {ok:false,error:'Microsoft created the draft but returned no Outlook link'};
    d.subject=message.subject;return Object.assign({ok:true},d);
  }catch(e){return {ok:false,error:'The Outlook draft result could not be confirmed',action:'Retry this placement; CV Studio will reuse the same request ID to avoid a duplicate if Microsoft already created it.',technical_details:(e&&e.message)||String(e),network_uncertain:true,retry_same_request:true};}
}
function ppcCopyInvoiceFormatted(placementId,quiet,settingsOverride){
  var item=ppcFindPlacement(placementId);if(!item){if(!quiet)showToast('Could not find this placement in PPC','err');return Promise.resolve(false);}
  var message=ppcBuildInvoiceEmail(item,settingsOverride||ppcInvoiceSettingsLoad());
  function done(ok,rich){if(!quiet)showToast(ok?(rich?'Formatted Calibri 11 invoice copied. Paste it into Outlook.':'Invoice copied as plain text.'):'Browser blocked clipboard access.',ok?'ok':'err');return ok;}
  try{
    if(navigator.clipboard&&navigator.clipboard.write&&window.ClipboardItem&&window.Blob){var payload={'text/html':new Blob([message.html],{type:'text/html'}),'text/plain':new Blob([message.body],{type:'text/plain'})};return navigator.clipboard.write([new ClipboardItem(payload)]).then(function(){return done(true,true);}).catch(function(){if(navigator.clipboard&&navigator.clipboard.writeText)return navigator.clipboard.writeText(message.body).then(function(){return done(true,false);}).catch(function(){return done(false,false);});return done(false,false);});}
    if(navigator.clipboard&&navigator.clipboard.writeText)return navigator.clipboard.writeText(message.body).then(function(){return done(true,false);}).catch(function(){return done(false,false);});
  }catch(e){}
  return Promise.resolve(done(false,false));
}
function ppcInvoicePreviewSettings(){return {recipient:String((document.getElementById('ppcInvoicePreviewTo')||{}).value||'').trim(),greeting:String((document.getElementById('ppcInvoicePreviewGreeting')||{}).value||'Syah').trim()||'Syah'};}
function ppcUpdateInvoicePreview(){
  var item=ppcFindPlacement(_ppcInvoicePreviewPlacementId);if(!item)return;
  var settings=ppcInvoicePreviewSettings(),message=ppcBuildInvoiceEmail(item,settings);_ppcInvoicePreviewMessage=message;
  var subject=document.getElementById('ppcInvoicePreviewSubject'),body=document.getElementById('ppcInvoicePreviewBody');if(subject)subject.value=message.subject;if(body)body.innerHTML=message.html;
  var missing=[];if(item.placement_fee===null||item.placement_fee===undefined||item.placement_fee==='')missing.push('Fee');if(!item.billing_payment_terms)missing.push('Payment term');if(!item.billing_email)missing.push('Client email');
  var miss=document.getElementById('ppcInvoicePreviewMissing');if(miss){miss.textContent=missing.length?('Missing from JobAdder: '+missing.join(', ')+'. The draft will show “Not provided in JobAdder”.'):'All requested JobAdder invoice fields are available.';miss.style.color=missing.length?'#9a6700':'var(--green)';}
  var acct=document.getElementById('ppcInvoicePreviewAccount');if(acct)acct.textContent='Draft mailbox: '+(_ppcOutlookConnected?(ppcOutlookAccountLabel()||'Connected Microsoft account'):'Outlook is not connected yet');
  var err=document.getElementById('ppcInvoicePreviewError');if(err){err.classList.remove('show');err.textContent='';}
}
function ppcOpenInvoicePreview(event,placementId,forceNew){
  if(event){event.preventDefault();event.stopPropagation();}
  var ppcView=document.getElementById('viewPPC');if(!ppcView||!ppcView.classList.contains('active')){showToast('Outlook invoice preview is available only inside PPC.','err');return false;}
  var item=ppcFindPlacement(placementId);if(!item){showToast('Could not find this placement in PPC','err');return false;}
  _ppcInvoicePreviewPlacementId=String(placementId||'');_ppcInvoiceForceNewDraft=!!forceNew;var settings=ppcInvoiceSettingsLoad();
  var to=document.getElementById('ppcInvoicePreviewTo'),g=document.getElementById('ppcInvoicePreviewGreeting');if(to)to.value=settings.recipient||'';if(g)g.value=settings.greeting||'Syah';
  ppcUpdateInvoicePreview();var btn=document.getElementById('ppcInvoicePreviewCreateBtn');if(btn)btn.textContent=_ppcInvoiceForceNewDraft?'Create another draft':'Create Outlook Draft';var modal=document.getElementById('ppcInvoicePreviewModal');if(modal)modal.classList.add('open');return false;
}
function ppcOpenInvoiceOutlook(event,placementId){return ppcOpenInvoicePreview(event,placementId,false);}
function ppcCloseInvoicePreview(){var modal=document.getElementById('ppcInvoicePreviewModal');if(modal)modal.classList.remove('open');_ppcInvoicePreviewPlacementId='';_ppcInvoicePreviewMessage=null;_ppcInvoiceForceNewDraft=false;}
function ppcCopyInvoicePreviewFormatted(){var id=_ppcInvoicePreviewPlacementId,settings=ppcInvoicePreviewSettings();if(settings.recipient&&!ppcInvoiceEmailValid(settings.recipient)){showToast('The recipient email is invalid. Correct it or clear it before copying.','err');return false;}var saved=ppcInvoiceSettingsLoad();ppcInvoiceSettingsSave({recipient:settings.recipient||saved.recipient||'',greeting:settings.greeting});return ppcCopyInvoiceFormatted(id,false,settings);}
async function ppcConfirmCreateInvoiceDraft(event){
  if(event){event.preventDefault();event.stopPropagation();}var id=String(_ppcInvoicePreviewPlacementId||'');if(!id||_ppcDraftBusy[id])return false;
  var item=ppcFindPlacement(id),settings=ppcInvoicePreviewSettings();if(!item)return false;
  if(!ppcInvoiceEmailValid(settings.recipient)){var err=document.getElementById('ppcInvoicePreviewError');if(err){err.textContent='Enter a valid invoice recipient email.';err.classList.add('show');}return false;}
  ppcInvoiceSettingsSave(settings);
  var opened=null;try{opened=window.open('about:blank','_blank');}catch(e){}if(!opened){showToast('The browser blocked the Outlook draft tab. Allow pop-ups for CV Studio.','err');return false;}
  ppcSetDraftBusy(id,true);var requestId=ppcDraftRequestId(item,settings,_ppcInvoiceForceNewDraft),rich=await ppcCreateRichOutlookDraft(item,settings,requestId);
  if(!rich.ok){try{opened.close();}catch(e){}ppcSetDraftBusy(id,false);if(!rich.retry_same_request&&!rich.network_uncertain)ppcClearPendingDraftRequest(id,requestId);ppcShowOutlookError(rich,'Rich Outlook draft failed');if(rich.needs_connect){ppcClearPendingDraftRequest(id,requestId);await ppcDisconnectOutlook(false);ppcOpenOutlookSettings();}return false;}
  ppcSaveLastDraft(id,rich,requestId);ppcSetOutlookTechnicalError(null);ppcSetDraftBusy(id,false);ppcCloseInvoicePreview();
  if(opened.closed){showToast('The draft was created, but the reserved browser tab was closed. Use Open last draft.','info');ppcRender();return false;}
  try{opened.opener=null;opened.location.replace(rich.webLink);}catch(e){try{opened.location.href=rich.webLink;}catch(ignore){}}
  var note='Rich Outlook draft created. Calibri 11, black text, bold labels and aligned colons are preserved. Outlook may require clicking Edit.';if(rich.reused)note+=' The existing result for this request was reused.';showToast(note,'ok');ppcRender();return false;
}
function ppcOutlookComposeUrl(to,subject){
  // Open a new Outlook compose on the unified OWA host the user actually signs
  // into (outlook.cloud.microsoft). A fresh compose is the only path that makes
  // Outlook auto-insert the user's real signature (including the banner image);
  // an API-created draft never gets it. The body is left empty on purpose so the
  // signature stays intact and the user pastes the copied invoice above it.
  //
  // Do NOT derive the host from a Graph webLink: Graph returns outlook.office365.com,
  // which is not the active session host, so opening it triggers an OAuth sign-in
  // redirect that strips the compose deeplink and dumps the user on the inbox.
  // Verified working format (plain, no exvsurl/ispopout): /mail/deeplink/compose.
  var params=[];
  if(to)params.push('to='+encodeURIComponent(to));
  if(subject)params.push('subject='+encodeURIComponent(subject));
  return 'https://outlook.cloud.microsoft/mail/deeplink/compose'+(params.length?('?'+params.join('&')):'');
}
async function ppcComposeInvoiceInOutlook(event){
  if(event){event.preventDefault();event.stopPropagation();}
  var id=String(_ppcInvoicePreviewPlacementId||'');if(!id)return false;
  var item=ppcFindPlacement(id),settings=ppcInvoicePreviewSettings();if(!item)return false;
  if(settings.recipient&&!ppcInvoiceEmailValid(settings.recipient)){var err=document.getElementById('ppcInvoicePreviewError');if(err){err.textContent='Enter a valid invoice recipient email, or clear it.';err.classList.add('show');}return false;}
  ppcInvoiceSettingsSave({recipient:settings.recipient||ppcInvoiceSettingsLoad().recipient||'',greeting:settings.greeting});
  var message=ppcBuildInvoiceEmail(item,settings);
  // Start the clipboard write and open the tab inside the click gesture so the
  // browser allows both, then redirect the tab to the compose deeplink.
  var copyPromise=ppcCopyInvoiceFormatted(id,true,settings);
  var win=null;try{win=window.open('about:blank','_blank');}catch(e){}
  var copied=false;try{copied=await copyPromise;}catch(e){}
  var url=ppcOutlookComposeUrl(settings.recipient,message.subject);
  if(win){try{win.opener=null;win.location.replace(url);}catch(e){try{win.location.href=url;}catch(ignore){}}}
  else{try{window.open(url,'_blank');}catch(e){}}
  ppcCloseInvoicePreview();
  if(copied)showToast('Invoice copied. In the new Outlook email, click in the body and paste (Ctrl+V / Cmd+V) above your signature, then send.','ok');
  else showToast('Opened a new Outlook email. The clipboard was blocked — use “Copy formatted”, then paste the invoice into the email above your signature.','info');
  ppcRender();return false;
}
function ppcIsoDate(d) {
  var y=d.getFullYear(), m=String(d.getMonth()+1).padStart(2,'0'), day=String(d.getDate()).padStart(2,'0');
  return y+'-'+m+'-'+day;
}
function ppcUiLoad(){try{var d=JSON.parse(localStorage.getItem(PPC_UI_STORE)||'{}');return d&&typeof d==='object'&&!Array.isArray(d)?d:{};}catch(e){return {};}}
function ppcCaptureUiState(){
  return {
    rangeMode:_ppcRangeMode||'year',
    from:String((document.getElementById('ppcFrom')||{}).value||''),
    to:String((document.getElementById('ppcTo')||{}).value||''),
    approvedOnly:!!((document.getElementById('ppcApprovedOnly')||{}).checked),
    search:String((document.getElementById('ppcSearch')||{}).value||''),
    recruiter:String((document.getElementById('ppcRecruiterFilter')||{}).value||''),
    company:String((document.getElementById('ppcCompanyFilter')||{}).value||''),
    type:String((document.getElementById('ppcTypeFilter')||{}).value||''),
    status:String((document.getElementById('ppcStatusFilter')||{}).value||''),
    payment:String((document.getElementById('ppcPaymentFilter')||{}).value||''),
    guarantee:String((document.getElementById('ppcGuaranteeFilter')||{}).value||''),
    kpiFilter:String(_ppcKpiFilter||''),
    sort:String((document.getElementById('ppcSort')||{}).value||'start_desc'),
    page:Number(_ppcPage||1)
  };
}
function ppcUiSave(){try{_ppcSavedUiState=ppcCaptureUiState();cvStudioDurableSettingSet(PPC_UI_STORE,JSON.stringify(_ppcSavedUiState));}catch(e){}}
function ppcSetElementValue(id,value){var el=document.getElementById(id);if(el&&value!==undefined&&value!==null)el.value=String(value);}
function ppcRestoreUiState(){
  var state=ppcUiLoad();
  _ppcSavedUiState=state;
  _ppcRangeMode=state.rangeMode||'year';
  var from=document.getElementById('ppcFrom'),to=document.getElementById('ppcTo'),approved=document.getElementById('ppcApprovedOnly');
  if(from&&state.from!==undefined)from.value=state.from;
  if(to&&state.to!==undefined)to.value=state.to;
  if(approved&&state.approvedOnly!==undefined)approved.checked=!!state.approvedOnly;
  ppcSetElementValue('ppcSearch',state.search||'');
  ppcSetElementValue('ppcTypeFilter',state.type||'');
  ppcSetElementValue('ppcPaymentFilter',state.payment||'');
  ppcSetElementValue('ppcGuaranteeFilter',state.guarantee||'');
  _ppcKpiFilter=['active','upcoming','ending','unpaid','guarantee'].indexOf(String(state.kpiFilter||''))>=0?String(state.kpiFilter):'';
  ppcSetElementValue('ppcSort',state.sort||'start_desc');
  _ppcPage=Math.max(1,Number(state.page||1));
  if(!state.from&&!state.to&&(_ppcRangeMode==='year'||_ppcRangeMode==='lastyear')) ppcSetRange(_ppcRangeMode,false,false);
  document.querySelectorAll('#ppcQuickRange button').forEach(function(btn){btn.classList.toggle('active',btn.getAttribute('data-range')===_ppcRangeMode);});
}
function ppcApplySavedDynamicFilters(){
  var st=_ppcSavedUiState||ppcUiLoad();
  [['ppcRecruiterFilter','recruiter'],['ppcCompanyFilter','company'],['ppcStatusFilter','status']].forEach(function(pair){
    var el=document.getElementById(pair[0]),val=String(st[pair[1]]||'');
    if(el&&val){
      var options=Array.from(el.options||[]),exact=options.find(function(o){return o.value===val;});
      var legacy=!exact&&pair[0]==='ppcRecruiterFilter'?options.find(function(o){return String(o.textContent||'').trim()===val;}):null;
      if(exact)el.value=val;else if(legacy)el.value=legacy.value;
    }
  });
}
function ppcKpiVisibilityLoad(){
  var defaults={total:true,active:true,upcoming:true,ending:true,unpaid:true,guarantee:true};
  try{var saved=JSON.parse(localStorage.getItem(PPC_KPI_VIS_STORE)||'{}');Object.keys(defaults).forEach(function(k){if(typeof saved[k]==='boolean')defaults[k]=saved[k];});}catch(e){}
  return defaults;
}
function ppcKpiVisibilitySave(state){try{cvStudioDurableSettingSet(PPC_KPI_VIS_STORE,JSON.stringify(state||{}));}catch(e){}}
function ppcApplyKpiVisibility(){
  var state=ppcKpiVisibilityLoad();
  document.querySelectorAll('#ppcKpis [data-kpi]').forEach(function(card){var key=card.getAttribute('data-kpi');card.style.display=state[key]===false?'none':'';});
  document.querySelectorAll('#ppcKpiMenu [data-kpi-toggle]').forEach(function(box){var key=box.getAttribute('data-kpi-toggle');box.checked=state[key]!==false;});
}
function ppcSetKpiVisibility(key,visible){
  var state=ppcKpiVisibilityLoad();state[String(key||'')]=!!visible;ppcKpiVisibilitySave(state);ppcApplyKpiVisibility();
  if(!visible&&_ppcKpiFilter===key){_ppcKpiFilter='';ppcApplyFilters(true);}
}
function ppcShowAllKpis(){
  ppcKpiVisibilitySave({total:true,active:true,upcoming:true,ending:true,unpaid:true,guarantee:true});ppcApplyKpiVisibility();ppcCloseKpiMenu();
}
function ppcOpenKpiMenu(event){
  if(event){event.preventDefault();event.stopPropagation();}
  var menu=document.getElementById('ppcKpiMenu');if(!menu)return false;
  ppcApplyKpiVisibility();menu.classList.add('open');
  var x=event&&isFinite(event.clientX)?event.clientX:20,y=event&&isFinite(event.clientY)?event.clientY:20;
  menu.style.left='0px';menu.style.top='0px';
  var rect=menu.getBoundingClientRect(),left=Math.max(8,Math.min(x,window.innerWidth-rect.width-8)),top=Math.max(8,Math.min(y,window.innerHeight-rect.height-8));
  menu.style.left=left+'px';menu.style.top=top+'px';return false;
}
function ppcCloseKpiMenu(){var menu=document.getElementById('ppcKpiMenu');if(menu)menu.classList.remove('open');}
function ppcKpiKey(event,key){if(event&&(event.key==='Enter'||event.key===' ')){event.preventDefault();ppcToggleKpiFilter(key);}}
function ppcToggleKpiFilter(key){
  key=String(key||'');
  _ppcKpiFilter=key&&_ppcKpiFilter===key?'':key;
  _ppcPage=1;ppcApplyFilters(false);
}
function ppcSelectRowFromEvent(event,row){
  if(!row)return;
  _ppcSelectedPlacementId=String(row.getAttribute('data-placement-id')||'');
  document.querySelectorAll('#ppcTableBody tr[data-placement-id]').forEach(function(tr){var selected=String(tr.getAttribute('data-placement-id')||'')===_ppcSelectedPlacementId;tr.classList.toggle('ppc-row-selected',selected);tr.setAttribute('aria-selected',selected?'true':'false');});
}
function ppcKpiMatch(item,key,now,in30){
  var s=ppcDateValue(item.start_date),e=ppcDateValue(item.end_date),meta=ppcMetaFor(item),gi=ppcGuaranteeInfo(item,meta);
  if(key==='active')return (!s||s<=now)&&(!e||e>=now);
  if(key==='upcoming')return !!(s&&s>now);
  if(key==='ending')return !!(e&&e>=now&&e<=in30);
  if(key==='unpaid')return meta.payment==='Unpaid';
  if(key==='guarantee')return gi.key==='soon';
  return true;
}

function ppcColumnVisibilityLoad(){
  var defaults={candidate:true,company:true,job:true,type:true,status:true,start:true,end:true,recruiter:true,owner:true,payment:true,'guarantee-period':true,'guarantee-end':true,'invoice-email':true,placement:true};
  try{var saved=JSON.parse(localStorage.getItem(PPC_COLUMN_VIS_STORE)||'{}');Object.keys(defaults).forEach(function(k){if(typeof saved[k]==='boolean')defaults[k]=saved[k];});}catch(e){}
  return defaults;
}
function ppcColumnVisibilitySave(state){try{cvStudioDurableSettingSet(PPC_COLUMN_VIS_STORE,JSON.stringify(state||{}));}catch(e){}}
function ppcApplyColumnVisibility(){
  var state=ppcColumnVisibilityLoad(),visible=0;
  Object.keys(state).forEach(function(k){if(state[k]!==false)visible++;});
  document.querySelectorAll('#ppcTable [data-col]').forEach(function(cell){var key=cell.getAttribute('data-col');cell.style.display=state[key]===false?'none':'';cell.classList.remove('ppc-visible-first','ppc-visible-last');});
  document.querySelectorAll('#ppcTable tr').forEach(function(row){var visibleCells=Array.from(row.querySelectorAll('[data-col]')).filter(function(cell){return state[cell.getAttribute('data-col')]!==false;});if(visibleCells.length){visibleCells[0].classList.add('ppc-visible-first');visibleCells[visibleCells.length-1].classList.add('ppc-visible-last');}});
  document.querySelectorAll('#ppcColumnMenu [data-col-toggle]').forEach(function(box){var key=box.getAttribute('data-col-toggle');box.checked=state[key]!==false;});
  var table=document.getElementById('ppcTable');if(table)table.style.minWidth=Math.max(720,visible*118)+'px';
}
function ppcSetColumnVisibility(key,visible){
  var state=ppcColumnVisibilityLoad(),shown=Object.keys(state).filter(function(k){return state[k]!==false;}).length;
  if(!visible&&shown<=1){var box=document.querySelector('#ppcColumnMenu [data-col-toggle="'+String(key).replace(/"/g,'')+'"]');if(box)box.checked=true;showToast('Keep at least one PPC column visible','err');return;}
  state[String(key||'')]=!!visible;ppcColumnVisibilitySave(state);ppcApplyColumnVisibility();
}
function ppcShowAllColumns(){
  ppcColumnVisibilitySave({candidate:true,company:true,job:true,type:true,status:true,start:true,end:true,recruiter:true,owner:true,payment:true,'guarantee-period':true,'guarantee-end':true,'invoice-email':true,placement:true});ppcApplyColumnVisibility();ppcCloseColumnMenu();
}
function ppcOpenColumnMenu(event){
  if(event){event.preventDefault();event.stopPropagation();}
  var menu=document.getElementById('ppcColumnMenu');if(!menu)return false;
  ppcApplyColumnVisibility();menu.classList.add('open');
  var x=event&&isFinite(event.clientX)?event.clientX:20,y=event&&isFinite(event.clientY)?event.clientY:20;
  menu.style.left='0px';menu.style.top='0px';
  var rect=menu.getBoundingClientRect(),left=Math.max(8,Math.min(x,window.innerWidth-rect.width-8)),top=Math.max(8,Math.min(y,window.innerHeight-rect.height-8));
  menu.style.left=left+'px';menu.style.top=top+'px';return false;
}
function ppcCloseColumnMenu(){var menu=document.getElementById('ppcColumnMenu');if(menu)menu.classList.remove('open');}

function ppcCacheKeyFor(from,to,approved){
  return ['schema'+PPC_CACHE_SCHEMA,'account'+String(window._jaAccountCacheNamespace||'none'),String(from||'')||'*',String(to||'')||'*',approved?'approved':'all'].join('|');
}
function ppcCacheQueryKey(){
  var from=String((document.getElementById('ppcFrom')||{}).value||''),to=String((document.getElementById('ppcTo')||{}).value||''),approved=!!((document.getElementById('ppcApprovedOnly')||{}).checked);
  return ppcCacheKeyFor(from,to,approved);
}
function ppcItemsInRange(items,from,to){
  return (items||[]).filter(function(item){var d=String((item||{}).start_date||'').slice(0,10);if(!d)return false;if(from&&d<from)return false;if(to&&d>to)return false;return true;});
}
async function ppcCacheDerivedRangesFromAllTime(record,approved){
  if(!record||record.complete===false||!Array.isArray(record.items))return;
  var now=new Date(),year=now.getFullYear();
  var ranges=[
    {from:year+'-01-01',to:year+'-12-31'},
    {from:(year-1)+'-01-01',to:(year-1)+'-12-31'}
  ];
  for(var i=0;i<ranges.length;i++){
    var r=ranges[i],subset=ppcItemsInRange(record.items,r.from,r.to);
    await ppcCachePut({key:ppcCacheKeyFor(r.from,r.to,approved),items:subset,loadedAt:record.loadedAt,truncated:false,complete:true,detailsComplete:record.detailsComplete!==false,totalCount:subset.length,max_records:record.max_records||20000,warning:record.warning||'',derivedFromAllTime:true});
  }
}
function ppcCacheOpen(){
  return new Promise(function(resolve,reject){
    if(!window.indexedDB){reject(new Error('IndexedDB unavailable'));return;}
    var req=indexedDB.open(PPC_CACHE_DB,1);
    req.onupgradeneeded=function(){var db=req.result;if(!db.objectStoreNames.contains(PPC_CACHE_OBJECT_STORE))db.createObjectStore(PPC_CACHE_OBJECT_STORE,{keyPath:'key'});};
    req.onsuccess=function(){resolve(req.result);};req.onerror=function(){reject(req.error||new Error('PPC cache unavailable'));};
  });
}
function ppcCacheFallbackLoad(key){try{var d=JSON.parse(localStorage.getItem(PPC_CACHE_FALLBACK_STORE)||'{}');return d&&d.key===key?d:null;}catch(e){return null;}}
function ppcCacheFallbackSave(record){try{var allItems=(record.items||[]),copy=Object.assign({schema:PPC_CACHE_SCHEMA},record,{items:allItems.slice(0,500),complete:allItems.length<=500&&record.complete!==false});localStorage.setItem(PPC_CACHE_FALLBACK_STORE,JSON.stringify(copy));}catch(e){}}
async function ppcCacheGet(key){
  var expectedNamespace=String(window._jaAccountCacheNamespace||''),expectedRunSeq=Number(_ppcAccountRunSeq||0);
  if(!expectedNamespace)return null;
  if(_ppcMemoryCache[key])return _ppcMemoryCache[key];
  try{
    var db=await ppcCacheOpen();
    var found=await new Promise(function(resolve){var tx=db.transaction(PPC_CACHE_OBJECT_STORE,'readonly'),req=tx.objectStore(PPC_CACHE_OBJECT_STORE).get(key);req.onsuccess=function(){resolve(req.result||null);};req.onerror=function(){resolve(null);};tx.oncomplete=function(){db.close();};});
    if(expectedNamespace!==String(window._jaAccountCacheNamespace||'')||expectedRunSeq!==Number(_ppcAccountRunSeq||0))return null;
    if(found && Number(found.schema||0)!==PPC_CACHE_SCHEMA) found=null;
    if(found)_ppcMemoryCache[key]=found;
    return found;
  }catch(e){
    if(expectedNamespace!==String(window._jaAccountCacheNamespace||'')||expectedRunSeq!==Number(_ppcAccountRunSeq||0))return null;
    var fallback=ppcCacheFallbackLoad(key);if(fallback)_ppcMemoryCache[key]=fallback;return fallback;
  }
}
async function ppcCachePut(record){
  var expectedNamespace=String(window._jaAccountCacheNamespace||''),expectedRunSeq=Number(_ppcAccountRunSeq||0);
  if(!expectedNamespace)return false;
  record=Object.assign({schema:PPC_CACHE_SCHEMA},record||{});
  if(String(record.key||'').indexOf('account'+expectedNamespace+'|')<0)return false;
  _ppcMemoryCache[record.key]=record;
  ppcCacheFallbackSave(record);
  try{
    var db=await ppcCacheOpen();
    if(expectedNamespace!==String(window._jaAccountCacheNamespace||'')||expectedRunSeq!==Number(_ppcAccountRunSeq||0)){db.close();return false;}
    await new Promise(function(resolve,reject){var tx=db.transaction(PPC_CACHE_OBJECT_STORE,'readwrite');tx.objectStore(PPC_CACHE_OBJECT_STORE).put(record);tx.oncomplete=resolve;tx.onerror=function(){reject(tx.error);};});
    db.close();
  }catch(e){}
  return true;
}
function ppcCacheClearPersistent(){
  try{localStorage.removeItem(PPC_CACHE_FALLBACK_STORE);}catch(e){}
  return ppcCacheOpen().then(function(db){
    return new Promise(function(resolve){
      var tx=db.transaction(PPC_CACHE_OBJECT_STORE,'readwrite');
      tx.objectStore(PPC_CACHE_OBJECT_STORE).clear();
      tx.oncomplete=function(){db.close();resolve(true);};
      tx.onerror=function(){try{db.close();}catch(e){}resolve(false);};
      tx.onabort=function(){try{db.close();}catch(e){}resolve(false);};
    });
  }).catch(function(){return false;});
}
async function clearPPCJobAdderAccountState(){
  _ppcAccountRunSeq = Number(_ppcAccountRunSeq || 0) + 1;
  _ppcItems=[];
  _ppcBaseFiltered=[];
  _ppcFiltered=[];
  _ppcMemoryCache={};
  _ppcActiveQueryKey='';
  _ppcLoadedAt=0;
  _ppcSelectedPlacementId='';
  _ppcInvoicePreviewPlacementId='';
  _ppcInvoicePreviewMessage=null;
  _ppcDraftBusy={};
  ppcCloseInvoicePreview();
  await ppcCacheClearPersistent();
  ppcPopulateFilters();
  ppcApplyFilters(true);
  var status=document.getElementById('ppcStatus');
  if(status)status.textContent='JobAdder signed out · reconnect to load placements';
  return true;
}
function ppcSetRange(mode, loadRange, saveState) {
  _ppcRangeMode = mode || 'year';
  var now = new Date();
  var from = document.getElementById('ppcFrom'), to = document.getElementById('ppcTo');
  if (_ppcRangeMode === 'year') {
    if (from) from.value = now.getFullYear()+'-01-01';
    if (to) to.value = now.getFullYear()+'-12-31';
  } else if (_ppcRangeMode === 'lastyear') {
    var y=now.getFullYear()-1;
    if (from) from.value = y+'-01-01';
    if (to) to.value = y+'-12-31';
  } else if (_ppcRangeMode === 'all') {
    if (from) from.value = '';
    if (to) to.value = '';
  }
  document.querySelectorAll('#ppcQuickRange button').forEach(function(btn){ btn.classList.toggle('active', btn.getAttribute('data-range') === _ppcRangeMode); });
  _ppcPage=1;
  if(saveState!==false)ppcUiSave();
  if(loadRange)ppcUseCachedRangeOrFetch();
}
function ppcRangeManualChanged() {
  _ppcRangeMode = 'custom';
  document.querySelectorAll('#ppcQuickRange button').forEach(function(btn){ btn.classList.remove('active'); });
  _ppcPage=1;ppcUiSave();
  var st=document.getElementById('ppcStatus');if(st)st.textContent='Custom date range changed · click Refresh JobAdder to load it.';
}
function ppcApprovedChanged(){_ppcPage=1;ppcUiSave();ppcUseCachedRangeOrFetch();}
function ppcDateValue(value) {
  var s=String(value||'').slice(0,10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return null;
  var d=new Date(s+'T00:00:00');
  return isNaN(d.getTime()) ? null : d;
}
function ppcAddMonths(dateText, months) {
  var d=ppcDateValue(dateText); months=parseInt(months||0,10);
  if (!d || !months) return '';
  var day=d.getDate();
  var out=new Date(d.getFullYear(), d.getMonth()+months, 1);
  var last=new Date(out.getFullYear(), out.getMonth()+1, 0).getDate();
  out.setDate(Math.min(day,last));
  return ppcIsoDate(out);
}
function ppcGuaranteeInfo(item, meta) {
  var raw=String((meta||{}).guaranteeMonths||'');
  if(raw==='resigned_backout') return {key:'resigned',label:'Resigned / Backout',end:''};
  var months=parseInt(raw||0,10);
  if (!months) return {key:'unset', label:'Not set', end:''};
  var end=ppcAddMonths(item.start_date, months);
  if (!end) return {key:'unset', label:'No start date', end:''};
  var today=ppcDateValue(ppcIsoDate(new Date()));
  var endDate=ppcDateValue(end);
  var days=Math.ceil((endDate-today)/86400000);
  if (days < 0) return {key:'expired', label:'Expired', end:end};
  if (days <= 30) return {key:'soon', label:'Ending soon', end:end};
  return {key:'active', label:'Active', end:end};
}
function ppcName(u) { return String((u||{}).name || '').trim(); }
function ppcSetConnected(ok) {
  var b=document.getElementById('ppcConnBadge');
  if (!b) return;
  b.textContent = ok ? 'JobAdder connected' : 'JobAdder not connected';
  b.className = 'ppc-badge ' + (ok ? 'ok' : 'warn');
}
function ppcWebBase() {
  var base=window._jaWebBase;
  if (!base || base === 'https://app.jobadder.com') {
    try { base=localStorage.getItem('ja_web_base') || base; } catch(e) {}
  }
  return base || 'https://app.jobadder.com';
}
function ppcCandidateUrl(id) { return ppcWebBase() + '/candidates/' + encodeURIComponent(id) + '?tab=3'; }
function ppcPlacementUrl(id) { return ppcWebBase() + '/placements/' + encodeURIComponent(id); }
function ppcJobUrl(id) { return ppcWebBase() + '/jobs/' + encodeURIComponent(id); }
function ppcCompanyUrl(id) { return ppcWebBase() + '/companies/' + encodeURIComponent(id); }
function ppcFormatDate(s) {var d=ppcDateValue(s);if(!d)return '—';return d.toLocaleDateString('en-MY',{day:'2-digit',month:'short',year:'numeric'});}
function ppcUniqueOptions(id, values, placeholder) {
  var el=document.getElementById(id); if(!el) return;
  var current=el.value;
  var vals=Array.from(new Set((values||[]).filter(Boolean))).sort(function(a,b){return a.localeCompare(b);});
  el.innerHTML='<option value="">'+esc(placeholder)+'</option>'+vals.map(function(v){return '<option value="'+escAttr(v)+'">'+esc(v)+'</option>';}).join('');
  if(vals.indexOf(current)>=0) el.value=current;
}
function ppcRecruiterOptions() {
  var byId={};
  _ppcItems.forEach(function(item){
    var pairs=Array.isArray(item.recruiter_pairs)?item.recruiter_pairs:[];
    if(!pairs.length){
      var ids=Array.isArray(item.recruiter_ids)?item.recruiter_ids:[],names=Array.isArray(item.recruiters)?item.recruiters:[];
      ids.forEach(function(id,i){pairs.push({user_id:id,name:names[i]||('Recruiter '+id)});});
    }
    pairs.forEach(function(pair){
      var id=String(pair&&pair.user_id!=null?pair.user_id:'').trim(),name=String(pair&&pair.name||'').trim();
      if(id&&!byId[id])byId[id]=name||('Recruiter '+id);
    });
  });
  return Object.keys(byId).map(function(id){return {value:id,label:byId[id]};}).sort(function(a,b){return a.label.localeCompare(b.label);});
}
function ppcNamedOptions(id, pairs, placeholder) {
  var el=document.getElementById(id);if(!el)return;
  var current=String(el.value||'');
  el.innerHTML='<option value="">'+esc(placeholder)+'</option>'+(pairs||[]).map(function(p){return '<option value="'+escAttr(p.value)+'">'+esc(p.label)+'</option>';}).join('');
  if(Array.from(el.options||[]).some(function(o){return o.value===current;}))el.value=current;
}
function ppcPopulateFilters() {
  ppcNamedOptions('ppcRecruiterFilter',ppcRecruiterOptions(),'All placement recruiters');
  ppcUniqueOptions('ppcCompanyFilter', _ppcItems.map(function(x){return x.company_name||'';}), 'All companies');
  ppcUniqueOptions('ppcStatusFilter', _ppcItems.map(function(x){return x.status_name||'';}), 'All statuses');
  ppcApplySavedDynamicFilters();
}
function ppcLoadedMessage(record,prefix){
  var count=(record.items||[]).length,total=Number(record.totalCount||count),stamp=record.loadedAt?new Date(record.loadedAt).toLocaleString('en-MY',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}):'unknown time';
  var msg=(prefix||'Showing saved')+' '+count+(total!==count?' of '+total:'')+' placement'+(count===1?'':'s')+' · last JobAdder refresh '+stamp;
  if(record.derivedFromAllTime)msg+=' · derived from complete All time snapshot';
  if(record.detailsComplete===false)msg+=' · some recruiter/invoice details need refresh';
  return msg;
}
async function ppcLoadCachedRange() {
  var accountNamespace=String(window._jaAccountCacheNamespace||''),accountRunSeq=Number(_ppcAccountRunSeq||0);
  if(!accountNamespace)return false;
  var key=ppcCacheQueryKey(),record=await ppcCacheGet(key);
  var from=String((document.getElementById('ppcFrom')||{}).value||''),to=String((document.getElementById('ppcTo')||{}).value||''),approved=!!((document.getElementById('ppcApprovedOnly')||{}).checked);
  if((!record||!Array.isArray(record.items)||record.complete===false)&&(from||to)){
    var allRecord=await ppcCacheGet(ppcCacheKeyFor('','',approved));
    if(allRecord&&Array.isArray(allRecord.items)&&allRecord.complete!==false){
      record={key:key,items:ppcItemsInRange(allRecord.items,from,to),loadedAt:allRecord.loadedAt,truncated:false,complete:true,detailsComplete:allRecord.detailsComplete!==false,totalCount:ppcItemsInRange(allRecord.items,from,to).length,max_records:allRecord.max_records||20000,warning:allRecord.warning||'',derivedFromAllTime:true};
      await ppcCachePut(record);
    }
  }
  if(accountRunSeq!==Number(_ppcAccountRunSeq||0)||accountNamespace!==String(window._jaAccountCacheNamespace||''))return false;
  if(!record||!Array.isArray(record.items)||record.complete===false)return false;
  _ppcActiveQueryKey=key;_ppcItems=record.items;_ppcLoadedAt=Number(record.loadedAt||0);
  ppcPopulateFilters();ppcApplyFilters(false);
  var st=document.getElementById('ppcStatus');if(st)st.textContent=ppcLoadedMessage(record,'Restored');
  return true;
}
async function ppcUseCachedRangeOrFetch(){
  if(_ppcLoadingNow)return;
  var found=await ppcLoadCachedRange();
  if(!found)await ppcRefresh(false);
}
async function ppcRefresh(force) {
  if (_ppcLoadingNow) return;
  var accountNamespace=String(window._jaAccountCacheNamespace||''),accountRunSeq=Number(_ppcAccountRunSeq||0);
  if(!window._jaToken||!accountNamespace){ppcSetConnected(false);return false;}
  _ppcLoadingNow=true;
  ppcUiSave();
  var btn=document.getElementById('ppcRefreshBtn'), loading=document.getElementById('ppcLoading'), wrap=document.getElementById('ppcTableWrap');
  var hadRows=_ppcItems.length>0;
  if(btn){btn.disabled=true;btn.textContent='Refreshing…';}
  if(!hadRows&&loading){loading.style.display='flex';loading.innerHTML='<span class="spinner"></span>&nbsp; Loading placements from JobAdder…';}
  if(hadRows){var st0=document.getElementById('ppcStatus');if(st0)st0.textContent='Refreshing JobAdder in the background · current saved rows remain visible…';}
  var run=markTabRunning('ppc');
  try {
    var from=(document.getElementById('ppcFrom')||{}).value||'';
    var to=(document.getElementById('ppcTo')||{}).value||'';
    if(from && to && from>to) throw new Error('Start date cannot be after end date');
    var approved=!!((document.getElementById('ppcApprovedOnly')||{}).checked);
    try {
      var infoResp=await fetch('/jobadder/api_info'), info=await infoResp.json();
      if(info && info.api_url){var baseMatch=String(info.api_url).match(/https?:\/\/(?:api\.([a-z0-9]+\.jobadder\.com)|([a-z0-9]+)api\.jobadder\.com)/i);if(baseMatch){window._jaWebBase='https://'+(baseMatch[1]||(baseMatch[2]+'.jobadder.com'));try{localStorage.setItem('ja_web_base',window._jaWebBase);}catch(storeErr){}}}
    } catch(infoErr) {}
    var r=await fetch('/jobadder/ppc/placements',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({start_date:from,end_date:to,approved_only:approved,force:!!force,max_records:20000,detail_limit:20000})});
    var d=await r.json().catch(function(){return {};});
    if(accountRunSeq!==Number(_ppcAccountRunSeq||0)||accountNamespace!==String(window._jaAccountCacheNamespace||''))return false;
    if(!r.ok) throw new Error(d.error || d.detail || ('JobAdder PPC error '+r.status));
    _ppcItems=Array.isArray(d.items)?d.items:[];
    _ppcLoadedAt=Date.now();_ppcActiveQueryKey=ppcCacheQueryKey();
    var cacheRecord={key:_ppcActiveQueryKey,items:_ppcItems,loadedAt:_ppcLoadedAt,truncated:!!d.truncated,complete:d.complete!==false,detailsComplete:d.details_complete!==false,totalCount:Number(d.total_count||_ppcItems.length),max_records:d.max_records||20000,warning:d.warning||'',typeDiagnostics:d.type_diagnostics||[]};
    if(cacheRecord.complete){
      await ppcCachePut(cacheRecord);
      if(accountRunSeq!==Number(_ppcAccountRunSeq||0)||accountNamespace!==String(window._jaAccountCacheNamespace||''))return false;
      if(!from&&!to)await ppcCacheDerivedRangesFromAllTime(cacheRecord,approved);
      if(accountRunSeq!==Number(_ppcAccountRunSeq||0)||accountNamespace!==String(window._jaAccountCacheNamespace||''))return false;
    }
    ppcSetConnected(true);ppcPopulateFilters();ppcApplyFilters(true);
    var msg='Loaded '+_ppcItems.length+(Number(d.total_count||0)&&Number(d.total_count)!==_ppcItems.length?' of '+Number(d.total_count):'')+' placement'+(_ppcItems.length===1?'':'s')+' from JobAdder';
    if(d.complete===false) msg+=' · INCOMPLETE RESPONSE (not cached)';
    if(d.truncated) msg+=' · capped at '+d.max_records;
    if(d.details_complete===false) msg+=' · some recruiter/invoice details used summary fallbacks';
    if(d.warning) msg+=' · '+d.warning;
    var st=document.getElementById('ppcStatus'); if(st) st.textContent=msg+' · refreshed '+new Date().toLocaleTimeString('en-MY',{hour:'2-digit',minute:'2-digit'});
    markTabDone('ppc',run);showToast(msg,'ok');
  } catch(e) {
    if(/connect to jobadder|not authenticated|401/i.test(String(e.message||''))) ppcSetConnected(false);
    if(!hadRows&&loading){loading.style.display='flex';loading.textContent=e.message || 'Could not load JobAdder placements';}
    var st=document.getElementById('ppcStatus'); if(st) st.textContent=(hadRows?'Refresh failed; saved rows kept · ':'')+(e.message || 'PPC refresh failed');
    markTabFailed('ppc',run);showToast(e.message || 'PPC refresh failed','err');
  } finally {
    _ppcLoadingNow=false;
    if(btn){btn.disabled=false;btn.textContent='Refresh JobAdder';}
  }
}
function ppcApplyFilters(resetPage) {
  if(resetPage) _ppcPage=1;
  var q=String((document.getElementById('ppcSearch')||{}).value||'').trim().toLowerCase();
  var recruiter=String((document.getElementById('ppcRecruiterFilter')||{}).value||'');
  var company=String((document.getElementById('ppcCompanyFilter')||{}).value||'');
  var type=String((document.getElementById('ppcTypeFilter')||{}).value||'');
  var status=String((document.getElementById('ppcStatusFilter')||{}).value||'');
  var payment=String((document.getElementById('ppcPaymentFilter')||{}).value||'');
  var guarantee=String((document.getElementById('ppcGuaranteeFilter')||{}).value||'');
  var sort=String((document.getElementById('ppcSort')||{}).value||'start_desc');
  _ppcBaseFiltered=_ppcItems.filter(function(item){
    var meta=ppcMetaFor(item), gi=ppcGuaranteeInfo(item,meta);
    var hay=[item.candidate_name,item.candidate_email,item.company_name,item.job_title,item.placed_by,item.job_owner,item.status_name,item.type].join(' ').toLowerCase();
    if(q && hay.indexOf(q)<0) return false;
    var recruiterIds=(item.recruiter_ids||[]).map(function(id){return String(id);});
    if(recruiter && recruiterIds.indexOf(String(recruiter))<0) return false;
    if(company && company!==item.company_name) return false;
    if(type && type!==item.type) return false;
    if(status && status!==item.status_name) return false;
    var pay=meta.payment||'';
    if(payment==='unset' && pay) return false;
    if(payment && payment!=='unset' && pay!==payment) return false;
    if(guarantee==='unset' && (meta.guaranteeMonths||'')) return false;
    if(guarantee && guarantee!=='unset' && gi.key!==guarantee) return false;
    return true;
  });
  var now=ppcDateValue(ppcIsoDate(new Date())),in30=new Date(now.getTime()+30*86400000);
  _ppcFiltered=_ppcBaseFiltered.filter(function(item){return ppcKpiMatch(item,_ppcKpiFilter,now,in30);});
  _ppcFiltered.sort(function(a,b){
    if(sort==='start_asc') return String(a.start_date||'9999').localeCompare(String(b.start_date||'9999'));
    if(sort==='company') return String(a.company_name||'').localeCompare(String(b.company_name||''));
    if(sort==='candidate') return String(a.candidate_name||'').localeCompare(String(b.candidate_name||''));
    if(sort==='recruiter') return String(a.placed_by||a.created_by||a.job_owner||'').localeCompare(String(b.placed_by||b.created_by||b.job_owner||''));
    return String(b.start_date||'').localeCompare(String(a.start_date||''));
  });
  ppcRender();ppcUiSave();
}
function ppcPaymentClass(value){return value==='Paid'?'payment-paid':value==='Invoiced'?'payment-invoiced':value==='Unpaid'?'payment-unpaid':'';}
function ppcGuaranteePeriodLabel(meta){var v=String((meta||{}).guaranteeMonths||'');return v==='resigned_backout'?'Resigned / Backout':v;}
function ppcRender() {
  var loading=document.getElementById('ppcLoading'), wrap=document.getElementById('ppcTableWrap'), body=document.getElementById('ppcTableBody');
  var total=_ppcFiltered.length, pages=Math.max(1,Math.ceil(total/PPC_PAGE_SIZE));
  _ppcPage=Math.min(Math.max(1,_ppcPage),pages);
  var start=(_ppcPage-1)*PPC_PAGE_SIZE, rows=_ppcFiltered.slice(start,start+PPC_PAGE_SIZE);
  if(!total){
    if(wrap) wrap.style.display='none';
    if(loading){loading.style.display='flex';loading.textContent=_ppcItems.length?'No placements match the current filters.':'No placements found for this date range.';}
  } else {
    if(loading) loading.style.display='none';
    if(wrap) wrap.style.display='block';
    if(body) body.innerHTML=rows.map(function(item){
      var meta=ppcMetaFor(item), gi=ppcGuaranteeInfo(item,meta), pid=item.placement_id;
      var cand=item.candidate_id?'<a class="ppc-link" href="'+escAttr(ppcCandidateUrl(item.candidate_id))+'" target="_blank" rel="noopener">'+esc(item.candidate_name||('Candidate '+item.candidate_id))+' ↗</a>':'<span class="ppc-name">'+esc(item.candidate_name||'Unknown candidate')+'</span>';
      var comp=item.company_id?'<a class="ppc-link" href="'+escAttr(ppcCompanyUrl(item.company_id))+'" target="_blank" rel="noopener">'+esc(item.company_name||('Company '+item.company_id))+' ↗</a>':esc(item.company_name||'—');
      var job=item.job_id?'<a class="ppc-link" href="'+escAttr(ppcJobUrl(item.job_id))+'" target="_blank" rel="noopener">'+esc(item.job_title||('Job '+item.job_id))+' ↗</a>':esc(item.job_title||'—');
      var payment=meta.payment||'';
      var isSelected=String(pid)===String(_ppcSelectedPlacementId||'');
      return '<tr data-placement-id="'+escAttr(String(pid))+'" class="'+(isSelected?'ppc-row-selected':'')+'" aria-selected="'+(isSelected?'true':'false')+'" onclick="ppcSelectRowFromEvent(event,this)">'
       +'<td data-col="candidate">'+cand+'</td>'
       +'<td data-col="company">'+comp+'</td><td data-col="job">'+job+'</td><td data-col="type">'+esc(item.type||'—')+'</td><td data-col="status"><span class="ppc-status-pill '+(String(item.status_name||'').toLowerCase().indexOf('active')>=0?'active':'')+'">'+esc(item.status_name||'—')+'</span></td>'
       +'<td data-col="start">'+ppcFormatDate(item.start_date)+'</td><td data-col="end">'+ppcFormatDate(item.end_date)+'</td><td data-col="recruiter">'+esc(item.placed_by||'—')+(item.created_by?'<div class="ppc-mini">Created by: '+esc(item.created_by)+'</div>':'')+'</td><td data-col="owner">'+esc(item.job_owner||'—')+'</td>'
       +'<td data-col="payment"><select class="ppc-edit-select '+ppcPaymentClass(payment)+'" aria-label="Payment status for '+escAttr(item.candidate_name||'placement')+'" onchange="ppcUpdateMeta(\''+escAttr(String(pid))+'\',\'payment\',this.value)"><option value=""'+(!payment?' selected':'')+'>Not set</option><option value="Unpaid"'+(payment==='Unpaid'?' selected':'')+'>Unpaid</option><option value="Invoiced"'+(payment==='Invoiced'?' selected':'')+'>Invoiced</option><option value="Paid"'+(payment==='Paid'?' selected':'')+'>Paid</option></select></td>'
       +'<td data-col="guarantee-period"><select class="ppc-edit-select" aria-label="Guarantee period for '+escAttr(item.candidate_name||'placement')+'" onchange="ppcUpdateMeta(\''+escAttr(String(pid))+'\',\'guaranteeMonths\',this.value)"><option value="">Not set</option>'+[1,2,3,4,5,6,9,12].map(function(m){return '<option value="'+m+'"'+(String(meta.guaranteeMonths||'')===String(m)?' selected':'')+'>'+m+' month'+(m===1?'':'s')+'</option>';}).join('')+'<option value="resigned_backout"'+(String(meta.guaranteeMonths||'')==='resigned_backout'?' selected':'')+'>Resigned / Backout</option></select></td>'
       +'<td data-col="guarantee-end">'+(gi.end?'<div>'+ppcFormatDate(gi.end)+'</div>':'<span class="ppc-muted">—</span>')+'<span class="ppc-status-pill '+escAttr(gi.key)+'" style="margin-top:4px;">'+esc(gi.label)+'</span></td>'
       +ppcRenderInvoiceActions(pid)
       +'<td data-col="placement"><a class="ppc-link" href="'+escAttr(ppcPlacementUrl(pid))+'" target="_blank" rel="noopener">#'+esc(String(pid))+' ↗</a><div class="ppc-mini">'+(item.approved?'Approved':'Not approved')+'</div></td></tr>';
    }).join('');
  }
  var now=ppcDateValue(ppcIsoDate(new Date())), in30=new Date(now.getTime()+30*86400000);
  var active=0, upcoming=0, ending=0, unpaid=0, guaranteeSoon=0;
  _ppcBaseFiltered.forEach(function(item){
    if(ppcKpiMatch(item,'active',now,in30))active++;
    if(ppcKpiMatch(item,'upcoming',now,in30))upcoming++;
    if(ppcKpiMatch(item,'ending',now,in30))ending++;
    if(ppcKpiMatch(item,'unpaid',now,in30))unpaid++;
    if(ppcKpiMatch(item,'guarantee',now,in30))guaranteeSoon++;
  });
  [['ppcKpiTotal',_ppcBaseFiltered.length],['ppcKpiActive',active],['ppcKpiUpcoming',upcoming],['ppcKpiEnding',ending],['ppcKpiUnpaid',unpaid],['ppcKpiGuarantee',guaranteeSoon]].forEach(function(x){var el=document.getElementById(x[0]);if(el)el.textContent=x[1];});
  document.querySelectorAll('#ppcKpis [data-filter]').forEach(function(card){var key=String(card.getAttribute('data-filter')||'');card.classList.toggle('active-filter',key===_ppcKpiFilter&&!!key);card.setAttribute('aria-pressed',key===_ppcKpiFilter&&!!key?'true':'false');});
  var totalCard=document.querySelector('#ppcKpis [data-kpi="total"]');if(totalCard){totalCard.classList.toggle('active-filter',!_ppcKpiFilter);totalCard.setAttribute('aria-pressed',!_ppcKpiFilter?'true':'false');}
  ppcApplyKpiVisibility();ppcApplyColumnVisibility();
  var info=document.getElementById('ppcPageInfo'); if(info) info.textContent=total?(start+1)+'–'+Math.min(start+PPC_PAGE_SIZE,total)+' of '+total:'0 placements';
  var prev=document.getElementById('ppcPrev'), next=document.getElementById('ppcNext'); if(prev)prev.disabled=_ppcPage<=1;if(next)next.disabled=_ppcPage>=pages;
}
function ppcChangePage(delta){_ppcPage+=Number(delta||0);ppcRender();ppcUiSave();var w=document.getElementById('ppcTableWrap');if(w)w.scrollTop=0;}
function ppcClearFilters(){
  ['ppcSearch','ppcRecruiterFilter','ppcCompanyFilter','ppcTypeFilter','ppcStatusFilter','ppcPaymentFilter','ppcGuaranteeFilter'].forEach(function(id){var el=document.getElementById(id);if(el)el.value='';});
  var sort=document.getElementById('ppcSort');if(sort)sort.value='start_desc';
  _ppcKpiFilter='';_ppcSavedUiState={};ppcApplyFilters(true);
}
function ppcCsvCell(v){var s=String(v==null?'':v);return /[",\n]/.test(s)?'"'+s.replace(/"/g,'""')+'"':s;}
function ppcExportExcel(){
  showToast('PPC Excel export is disabled.','err');
  return false;
}
async function ppcInit(){
  ppcUpdateOutlookConnectButton();
  ppcRestoreOutlookToken(false).catch(function(){});
  if(!_ppcUiRestored){
    ppcRestoreUiState();_ppcUiRestored=true;ppcApplyKpiVisibility();
    ppcApplyColumnVisibility();
    document.addEventListener('click',function(e){var menu=document.getElementById('ppcKpiMenu');if(menu&&menu.classList.contains('open')&&!menu.contains(e.target))ppcCloseKpiMenu();var colMenu=document.getElementById('ppcColumnMenu');if(colMenu&&colMenu.classList.contains('open')&&!colMenu.contains(e.target))ppcCloseColumnMenu();});
    document.addEventListener('keydown',function(e){if(e.key==='Escape'){ppcCloseKpiMenu();ppcCloseColumnMenu();ppcCloseInvoicePreview();}});
    window.addEventListener('resize',function(){ppcCloseKpiMenu();ppcCloseColumnMenu();});window.addEventListener('scroll',function(){ppcCloseKpiMenu();ppcCloseColumnMenu();},true);
  }
  var jobAdderInfo=null;
  try{
    var jobAdderInfoResponse=await fetch('/jobadder/api_info');
    jobAdderInfo=await jobAdderInfoResponse.json();
  }catch(e){
    jobAdderInfo={connected:false};
  }
  applyJAPublicInfo(jobAdderInfo || {});renderJAConnectionState(jobAdderInfo || {});
  if(!(jobAdderInfo&&jobAdderInfo.connected)){
    await clearPPCJobAdderAccountState();
    ppcSetConnected(false);
    return;
  }
  if(jobAdderInfo.api_url){var m=String(jobAdderInfo.api_url).match(/https?:\/\/(?:api\.([a-z0-9]+\.jobadder\.com)|([a-z0-9]+)api\.jobadder\.com)/i);if(m){window._jaWebBase='https://'+(m[1]||(m[2]+'.jobadder.com'));try{localStorage.setItem('ja_web_base',window._jaWebBase);}catch(e){}}}
  var key=ppcCacheQueryKey();
  if(_ppcItems.length&&_ppcActiveQueryKey===key){ppcPopulateFilters();ppcApplyFilters(false);return;}
  var found=await ppcLoadCachedRange();
  if(!found)await ppcRefresh(false);
}
