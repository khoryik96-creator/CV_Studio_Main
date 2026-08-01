// Central local API transport: request IDs, localhost CSRF header, structured
// error normalisation and a bounded browser-side diagnostic history.
(function(){
  var _cvStudioFetch = window.fetch.bind(window);
  window._cvStudioRecentApiErrors = window._cvStudioRecentApiErrors || [];
  function newRequestId(){
    try { if(window.crypto&&window.crypto.getRandomValues){var b=new Uint8Array(8);window.crypto.getRandomValues(b);return Array.prototype.map.call(b,function(x){return x.toString(16).padStart(2,'0');}).join('');} } catch(e){}
    return 'web'+Date.now().toString(36)+Math.random().toString(36).slice(2,10);
  }
  function pushApiError(entry){window._cvStudioRecentApiErrors.push(entry);if(window._cvStudioRecentApiErrors.length>30)window._cvStudioRecentApiErrors.splice(0,window._cvStudioRecentApiErrors.length-30);try{window.dispatchEvent(new CustomEvent('cvstudio-api-error',{detail:entry}));}catch(e){}}
  function actionHint(action){
    var map={open_jobadder_settings:'Open JobAdder settings and reconnect.',open_onenote_settings:'Open OneNote settings and reconnect.',open_outlook_settings:'Open Outlook settings and reconnect.',open_ai_settings:'Open Main API Settings and check the provider key.',open_settings:'Open Settings and review the connection.',retry:'Retry the action.',retry_later:'Try again shortly.',retry_or_switch_provider:'Retry shortly or switch provider.',use_smaller_file:'Use a smaller file or split the request.',unlock_feature:'Unlock this feature first.',reopen_local_app:'Close this page and reopen CV Studio from its local launcher.',reload_browser:'Reload CV Studio in this browser tab and try again.'};
    return map[String(action||'')]||'';
  }
  function normaliseFailure(data,response){
    if(!data||typeof data!=='object')data={};
    var status=Number(response&&response.status)||500;
    var failed=status>=400||data.ok===false||(String(data.error||'').trim()&&data.ok!==true);
    if(!failed)return data;
    var rid=String(data.request_id||(response&&response.headers&&response.headers.get('X-CV-Studio-Request-ID'))||'').trim();
    var message=String(data.message||data.error||data.detail||('Request failed: HTTP '+status)).trim();
    var hint=actionHint(data.action),display=message;
    if(hint&&display.indexOf(hint)<0)display+='\n\n'+hint;
    if(rid&&display.indexOf('Request ID:')<0)display+='\n\nRequest ID: '+rid;
    data.ok=false;data.message=message;data.error=display;data.request_id=rid;data.code=String(data.code||'CVSTUDIO_ERROR');data.retryable=!!data.retryable;
    var entry={at:new Date().toISOString(),path:String(response&&response.url||'').replace(window.location.origin,''),status:status,code:data.code,request_id:rid,message:message.slice(0,500),action:String(data.action||''),retryable:!!data.retryable};
    pushApiError(entry)
    return data;
  }
  window.cvStudioNormaliseApiFailure=normaliseFailure;
  window.fetch = async function(input, init) {
    init = init || {};
    var method = String(init.method || (input && input.method) || 'GET').toUpperCase();
    var unsafe = method === 'POST' || method === 'PUT' || method === 'PATCH' || method === 'DELETE';
    var sameOrigin = false;
    try { var raw = typeof input === 'string' ? input : (input && input.url) || ''; sameOrigin = new URL(raw, window.location.href).origin === window.location.origin; } catch(e) {}
    if (sameOrigin) {
      var headers = new Headers(init.headers || (input && input.headers) || {});
      if (!headers.has('X-CV-Studio-Request-ID')) headers.set('X-CV-Studio-Request-ID', newRequestId());
      if (unsafe && !headers.has('X-CV-Studio-Request')) headers.set('X-CV-Studio-Request', '1');
      init.headers = headers;
    }
    var response;
    try{response=await _cvStudioFetch(input,init);}catch(err){
      var rid='';try{rid=String(new Headers(init.headers||{}).get('X-CV-Studio-Request-ID')||'');}catch(e){}
      var rawPath='';try{rawPath=String(typeof input==='string'?input:(input&&input.url)||'').replace(window.location.origin,'');}catch(e){}
      var entry={at:new Date().toISOString(),path:rawPath,status:0,code:'NETWORK_ERROR',request_id:rid,message:String(err&&err.message||'Network request failed').slice(0,500),action:'retry',retryable:true};pushApiError(entry);try{err.cvStudioRequestId=rid;}catch(e){}throw err;
    }
    try{response.cvStudioRequestId=String(response.headers.get('X-CV-Studio-Request-ID')||'');}catch(e){}
    var originalJson=response.json.bind(response),originalText=response.text.bind(response);
    response.json=async function(){return normaliseFailure(await originalJson(),response);};
    response.text=async function(){var rawText=await originalText();if(String(response.headers.get('Content-Type')||'').toLowerCase().indexOf('application/json')>=0){try{return JSON.stringify(normaliseFailure(JSON.parse(rawText||'{}'),response));}catch(e){}}return rawText;};
    return response;
  };
})();
