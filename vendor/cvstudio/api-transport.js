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
  // Central deadline policy so a stalled local route can't hang a button forever.
  // Only same-origin GET/HEAD (status, settings, diagnostics, startup polls — the
  // hang-prone reads) get a default deadline; mutations/uploads/AI keep their
  // current unbounded behaviour unless they opt in with init.timeout. Any caller
  // can override the deadline (init.timeout, ms) or disable it (init.cvStudioNoTimeout).
  var DEFAULT_GET_TIMEOUT_MS = 60000;
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
    var timeoutMs = 0;
    if (Number(init.timeout) > 0) timeoutMs = Number(init.timeout);
    else if (sameOrigin && !unsafe && init.cvStudioNoTimeout !== true && method !== 'CONNECT') timeoutMs = DEFAULT_GET_TIMEOUT_MS;
    var timeoutCtrl = null, timeoutTimer = null, callerSignal = init.signal, onCallerAbort = null, timedOut = false;
    if (timeoutMs > 0 && typeof AbortController !== 'undefined' && init.cvStudioNoTimeout !== true) {
      try {
        timeoutCtrl = new AbortController();
        timeoutTimer = setTimeout(function(){ timedOut = true; try { timeoutCtrl.abort(); } catch(e){} }, timeoutMs);
        // Merge the caller's own AbortController with our deadline so neither is lost.
        if (callerSignal) {
          if (callerSignal.aborted) { try { timeoutCtrl.abort(); } catch(e){} }
          else { onCallerAbort = function(){ try { timeoutCtrl.abort(); } catch(e){} }; try { callerSignal.addEventListener('abort', onCallerAbort); } catch(e){} }
        }
        init.signal = timeoutCtrl.signal;
      } catch(e) { timeoutCtrl = null; }
    }
    function clearDeadline(){ if (timeoutTimer) { try { clearTimeout(timeoutTimer); } catch(e){} timeoutTimer = null; } if (onCallerAbort && callerSignal) { try { callerSignal.removeEventListener('abort', onCallerAbort); } catch(e){} onCallerAbort = null; } }
    var response;
    try{response=await _cvStudioFetch(input,init);}catch(err){
      clearDeadline();
      var rid='';try{rid=String(new Headers(init.headers||{}).get('X-CV-Studio-Request-ID')||'');}catch(e){}
      var rawPath='';try{rawPath=String(typeof input==='string'?input:(input&&input.url)||'').replace(window.location.origin,'');}catch(e){}
      // Our deadline fired (as opposed to the caller aborting their own signal) —
      // surface a distinct TIMEOUT error instead of a generic network failure.
      if (timedOut && !(callerSignal && callerSignal.aborted)) {
        var terr = new Error('Request timed out after ' + Math.round(timeoutMs/1000) + 's — the local server may be busy or unresponsive. Try again, or relaunch CV Studio.');
        try { terr.name = 'TimeoutError'; } catch(e){}
        terr.code = 'TIMEOUT'; terr.cvStudioTimeout = true; terr.retryable = true; terr.cvStudioRequestId = rid;
        pushApiError({at:new Date().toISOString(),path:rawPath,status:0,code:'TIMEOUT',request_id:rid,message:terr.message.slice(0,500),action:'retry',retryable:true});
        throw terr;
      }
      var entry={at:new Date().toISOString(),path:rawPath,status:0,code:'NETWORK_ERROR',request_id:rid,message:String(err&&err.message||'Network request failed').slice(0,500),action:'retry',retryable:true};pushApiError(entry);try{err.cvStudioRequestId=rid;}catch(e){}throw err;
    }
    clearDeadline();
    try{response.cvStudioRequestId=String(response.headers.get('X-CV-Studio-Request-ID')||'');}catch(e){}
    var originalJson=response.json.bind(response),originalText=response.text.bind(response);
    response.json=async function(){return normaliseFailure(await originalJson(),response);};
    response.text=async function(){var rawText=await originalText();if(String(response.headers.get('Content-Type')||'').toLowerCase().indexOf('application/json')>=0){try{return JSON.stringify(normaliseFailure(JSON.parse(rawText||'{}'),response));}catch(e){}}return rawText;};
    return response;
  };
})();
