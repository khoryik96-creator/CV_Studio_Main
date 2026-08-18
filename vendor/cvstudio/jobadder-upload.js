// ── JobAdder OAuth + Upload ───────────────────────────────────────────
// Replace these with your JobAdder app credentials from developer.jobadder.com
var JA_REDIRECT_URI  = 'http://localhost:5000/jobadder/callback';
var JA_SCOPES        = 'read write offline_access';
var JA_AUTH_URL      = 'https://id.jobadder.com/connect/authorize';
var JA_TOKEN_URL     = 'https://id.jobadder.com/connect/token';
// JA_API_BASE handled server-side via Flask proxy

window._jaClientSecretConfigured = false;
window._jaConfiguredClientId = '';
window._jaAccountCacheNamespace = '';
function getJAClientId() {
  var field = document.getElementById('settingsJobAdderClientId');
  if (field && field.value.trim()) return field.value.trim();
  try { return localStorage.getItem('ja_client_id') || ''; } catch(e){ return ''; }
}
function getJAClientSecret() {
  var field = document.getElementById('settingsJobAdderClientSecret');
  return field ? field.value.trim() : '';
}
function hasJASavedSecretFor(clientId) {
  return !!window._jaClientSecretConfigured && String(window._jaConfiguredClientId || '') === String(clientId || '').trim();
}
function updateJASecretFieldHint() {
  var field = document.getElementById('settingsJobAdderClientSecret');
  var idField = document.getElementById('settingsJobAdderClientId');
  if (!field) return;
  var clientId = idField ? idField.value.trim() : getJAClientId();
  field.placeholder = hasJASavedSecretFor(clientId) ? 'Saved securely · paste to replace' : 'Client secret';
}
function jaAccountCacheNamespace(info) {
  info = info || {};
  if (!info.connected) return '';
  var material = String(info.account_cache_namespace || '').trim();
  if (!/^[a-f0-9]{64}$/i.test(material)) return '';
  return 'ja' + material.toLowerCase();
}
function applyJAPublicInfo(info, options) {
  info = info || {};
  options = options || {};
  var previousAccountCacheNamespace = String(window._jaAccountCacheNamespace || '');
  var nextAccountCacheNamespace = jaAccountCacheNamespace(info);
  window._jaClientSecretConfigured = !!info.client_secret_configured;
  window._jaConfiguredClientId = String(info.client_id || '');
  window._jaAccountCacheNamespace = nextAccountCacheNamespace;
  if (!options.skipAccountStateInvalidation && previousAccountCacheNamespace
      && previousAccountCacheNamespace !== nextAccountCacheNamespace) {
    if (typeof clearTheSpiderJobAdderAccountState === 'function') clearTheSpiderJobAdderAccountState();
    if (typeof invalidateOneNoteJobAdderMatches === 'function') invalidateOneNoteJobAdderMatches();
    if (typeof clearPPCJobAdderAccountState === 'function') {
      Promise.resolve(clearPPCJobAdderAccountState()).catch(function(){});
    }
  }
  var idField = document.getElementById('settingsJobAdderClientId');
  if (idField) idField.value = window._jaConfiguredClientId || getJAClientId();
  if (window._jaConfiguredClientId) {
    try {
      localStorage.setItem('ja_client_id', window._jaConfiguredClientId);
    } catch(e) {}
  }
  updateJASecretFieldHint();
}

function jaSafeTenantLabel(info) {
  try {
    var parsed = new URL(String((info || {}).api_url || ''));
    return parsed.hostname && parsed.hostname.endsWith('.jobadder.com') ? parsed.hostname : '';
  } catch(e) { return ''; }
}

function renderJAConnectionState(info) {
  info = info || {};
  var connected = !!info.connected;
  var reconnect = !!info.needs_reconnect;
  window._jaToken = connected;
  var login = document.getElementById('btnJALogin');
  if (login) {
    login.textContent = connected ? '✅ JobAdder Connected' : (reconnect ? '↻ Reconnect JobAdder' : '🔗 Connect JobAdder');
    login.style.color = connected ? '#2f855a' : '';
  }
  var email = document.getElementById('jaEmail');
  var upload = document.getElementById('btnJA');
  var hint = document.getElementById('jaConnHint');
  var status = document.getElementById('jaStatus');
  if (upload) upload.disabled = !connected || !String((email || {}).value || '').trim();
  if (hint) hint.style.display = connected ? 'none' : 'inline';
  if (status) status.textContent = connected ? 'JobAdder connected' : (reconnect ? 'Reconnect required' : 'JobAdder not connected');

  var batchBadge = document.getElementById('batchJAConnBadge');
  if (batchBadge) {
    batchBadge.textContent = connected ? ('☁ JA: auto-upload ' + (window._jaAutoUpload === false ? 'off' : 'on')) : (reconnect ? '⚠ JA: reconnect required' : '⚠ JA: not connected');
    batchBadge.style.cssText = 'font-size:11px;font-weight:500;border-radius:20px;padding:2px 10px;margin-left:4px;color:' + (connected ? '#2f855a' : '#c05621') + ';background:' + (connected ? '#f0fff4' : '#fffaf0') + ';border:1px solid ' + (connected ? '#9ae6b4' : '#fbd38d') + ';';
  }
  var batchStatus = document.getElementById('batchJAStatus');
  if (batchStatus) batchStatus.style.display = connected ? 'inline' : 'none';

  var oneNote = document.getElementById('oneNoteConnBadge');
  if (oneNote) {
    oneNote.textContent = connected ? 'JobAdder Connected' : (reconnect ? 'Reconnect JobAdder' : 'Connect JobAdder first');
    oneNote.style.background = connected ? 'rgba(34,197,94,.14)' : 'rgba(245,158,11,.14)';
  }
  ppcSetConnected(connected);
  var spider = document.getElementById('theSpiderBadge');
  if (spider) {
    spider.textContent = connected ? 'JobAdder connected' : (reconnect ? 'JobAdder reconnect required' : 'JobAdder not connected');
    spider.style.color = connected ? '#2f855a' : '#c05621';
  }

  var settingsBadge = document.getElementById('settingsJobAdderStatus');
  var settingsDetail = document.getElementById('settingsJobAdderDetail');
  var secretStatus = document.getElementById('settingsJobAdderSecretStatus');
  var tenant = jaSafeTenantLabel(info);
  if (settingsBadge) settingsBadge.textContent = reconnect ? 'Reconnect required' : (connected ? 'Connected' : 'Not connected');
  if (settingsDetail) settingsDetail.textContent = (reconnect ? 'JobAdder OAuth must be reconnected.' : (connected ? 'JobAdder OAuth connection is available.' : 'JobAdder is signed out in CV Studio.')) + (tenant && connected ? ' Tenant API: ' + tenant + '.' : '');
  if (secretStatus) secretStatus.textContent = info.client_secret_configured ? 'Secure Client Secret: configured' : 'Secure Client Secret: not configured';
  var connectBtn = document.getElementById('settingsJobAdderConnectBtn');
  var reconnectBtn = document.getElementById('settingsJobAdderReconnectBtn');
  var signOutBtn = document.getElementById('settingsJobAdderSignOutBtn');
  if (connectBtn) connectBtn.style.display = connected || reconnect ? 'none' : 'inline-flex';
  if (reconnectBtn) reconnectBtn.style.display = connected || reconnect ? 'inline-flex' : 'none';
  if (signOutBtn) signOutBtn.disabled = !connected && !reconnect;
  updateJAUploadConnStatus();
  updateJACreateConnStatus();
}

function openJobAdderSettings(message) {
  setTimeout(function(){
    var panel = ensureSettingsPanelTopLayer();
    var backdrop = document.getElementById('settingsBackdrop');
    if (panel) panel.style.display = 'block';
    if (backdrop) backdrop.style.display = 'block';
    if (document.body) document.body.classList.add('settings-open');
    showSettingsTab('integrations');
    var card = document.getElementById('settingsJobAdderCard');
    var detail = document.getElementById('settingsJobAdderDetail');
    if (message && detail) detail.textContent = message;
    if (card && card.scrollIntoView) card.scrollIntoView({behavior:'smooth',block:'center'});
    var field = document.getElementById('settingsJobAdderClientId');
    if (field) field.focus();
    refreshIntegrationDiagnostics();
  }, 0);
}

async function saveJobAdderSettings() {
  var id = String((document.getElementById('settingsJobAdderClientId') || {}).value || '').trim();
  var secretField = document.getElementById('settingsJobAdderClientSecret');
  var secret = String((secretField || {}).value || '').trim();
  if (!id || (!secret && !hasJASavedSecretFor(id))) {
    showToast(!id ? 'Enter the JobAdder Client ID' : 'Enter the JobAdder Client Secret for this Client ID', 'err');
    return false;
  }
  try {
    var response = await fetchWithTimeout('/jobadder/store_creds', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({client_id:id,client_secret:secret,save_only:true})
    }, 8000);
    var data = await response.json().catch(function(){return {};});
    if (!response.ok || !data.ok) throw new Error(data.error || 'Could not save JobAdder settings');
    if (secretField) secretField.value = '';
    try { localStorage.setItem('ja_client_id', id); localStorage.removeItem('ja_client_secret'); } catch(e) {}
    applyJAPublicInfo(data);
    renderJAConnectionState(data);
    showToast('JobAdder settings saved securely', 'ok');
    return true;
  } catch(e) {
    showToast(e && e.message ? e.message : 'Could not save JobAdder settings', 'err');
    return false;
  }
}

window._jaToken      = null;   // boolean connection marker; tokens remain backend-only
window._jaDocxBlob   = null;   // set after formatting

// ── Step 1: Open OAuth login popup ───────────────────────────────────
async function jobAdderLogin() {
  var clientId = getJAClientId();
  var clientSecret = getJAClientSecret();
  if (clientId && !clientSecret && !hasJASavedSecretFor(clientId)) {
    var enteredClientId = clientId;
    try {
      var currentResponse = await fetch('/jobadder/api_info', {cache:'no-store'});
      var currentInfo = await currentResponse.json().catch(function(){return {};});
      if (currentResponse.ok) {
        applyJAPublicInfo(currentInfo);
        if (String(currentInfo.client_id || '') === enteredClientId) {
          clientId = enteredClientId;
        } else {
          var settingsIdField = document.getElementById('settingsJobAdderClientId');
          if (settingsIdField) settingsIdField.value = enteredClientId;
          clientId = enteredClientId;
        }
      }
    } catch(e) {}
  }
  if (!clientId || (!clientSecret && !hasJASavedSecretFor(clientId))) {
    openJobAdderSettings('JobAdder application setup is required before connecting. Enter the Client ID and Client Secret, then save or connect.');
    showToast('Complete JobAdder application setup in Settings → Integrations & Data', 'err');
    return;
  }
  var startRes = await fetchWithTimeout('/jobadder/store_creds', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({client_id:clientId, client_secret:clientSecret})
  }, 8000);
  var startData = await startRes.json().catch(function(){return {};});
  if (!startRes.ok || !startData.login_session_id || !startData.state) {
    showToast(startData.error || 'Could not start JobAdder login', 'err'); return;
  }
  try { localStorage.setItem('ja_client_id', clientId); localStorage.removeItem('ja_client_secret'); } catch(e) {}
  var params = new URLSearchParams({response_type:'code',client_id:clientId,redirect_uri:JA_REDIRECT_URI,scope:JA_SCOPES,state:startData.state});
  var popup = window.open(JA_AUTH_URL+'?'+params.toString(),'jobadder_login','width=520,height=640,menubar=no,toolbar=no');
  var pollAttempts=0;
  var poll=setInterval(async function(){
    pollAttempts++;
    // A successful OAuth callback closes the popup itself. Continue polling
    // the session-bound backend result after that normal close; otherwise a
    // fast callback can be mistaken for user cancellation and the completed
    // token is never claimed by this tab. The backend session expires safely.
    if (pollAttempts>150) { clearInterval(poll); return; }
    try {
      var r=await fetchWithTimeout('/jobadder/poll_token',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({login_session_id:startData.login_session_id})},5000);
      if (r.status===202) return;
      var d=await r.json().catch(function(){return {};});
      if (!r.ok) { clearInterval(poll); if(popup)popup.close(); showToast(d.error||'JobAdder login failed','err'); return; }
      if (d.connected) {
        clearInterval(poll); if(popup)popup.close(); window._jaToken=true;
        applyJAPublicInfo(d);
        var secretField = document.getElementById('settingsJobAdderClientSecret');
        if (secretField) secretField.value = '';
        try {
          ['ja_access_token','ja_refresh_token','ja_token_expiry','ja_client_secret'].forEach(function(k){localStorage.removeItem(k);});
          if (d.api_url) localStorage.setItem('ja_api_url',String(d.api_url).replace(/\/+$/,''));
        } catch(e) {}
        if (d.api_url) {
          var m=String(d.api_url).match(/https?:\/\/(?:api\.([a-z0-9]+\.jobadder\.com)|([a-z0-9]+)api\.jobadder\.com)/i);
          window._jaWebBase=m?'https://'+(m[1]||(m[2]+'.jobadder.com')):'https://app.jobadder.com';
          try{localStorage.setItem('ja_web_base',window._jaWebBase);}catch(e){}
        }
        updateJAConnectedUI(d);
        refreshIntegrationDiagnostics();
        showToast('JobAdder connected securely','ok');
      }
    } catch(e) {}
  },2000);
}

// ── Step 2: Upload DOCX to JobAdder ──────────────────────────────────
function clearJALocalAccountState() {
  try {
    [
      'ja_access_token',
      'ja_refresh_token',
      'ja_token_expiry',
      'ja_api_url',
      'ja_web_base',
      'ja_perm_work_type_id',
      'ja_client_secret'
    ].forEach(function(key){ localStorage.removeItem(key); });
  } catch(e) {}
  window._jaWebBase = '';
  window._jaPermWorkTypeId = null;
}

async function signOutJobAdder() {
  if (!window.confirm('Sign out from JobAdder in CV Studio? Your saved application Client ID and Client Secret will be kept securely.')) return false;
  try {
    var response = await fetch('/jobadder/sign_out', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:'{}'
    });
    var data = await response.json().catch(function(){return {};});
    if (!response.ok || !data.ok || data.connected) throw new Error(data.error || 'JobAdder sign-out failed');
    applyJAPublicInfo(data, {skipAccountStateInvalidation:true});
    renderJAConnectionState(data);
    clearJALocalAccountState();
    clearTheSpiderJobAdderAccountState();
    invalidateOneNoteJobAdderMatches();
    await clearPPCJobAdderAccountState();
    await refreshIntegrationDiagnostics();
    showToast('Signed out from JobAdder in CV Studio', 'ok');
    return true;
  } catch(e) {
    showToast(e && e.message ? e.message : 'Could not sign out from JobAdder in CV Studio', 'err');
    return false;
  }
}

async function uploadToJobAdder() {
  var email  = document.getElementById('jaEmail').value.trim();
  var status = document.getElementById('jaStatus');
  var btn    = document.getElementById('btnJA');
  if (!email || !window._jaToken || !window._docxBlob) return;

  var _tabRun = markTabRunning('format');
  btn.disabled = true;
  status.textContent = 'Searching candidate…';
  status.style.color = 'var(--text3)';

  try {
    // ── Search for candidate by email (via Flask proxy) ───────────
    var searchData = await jaSearchCandidate(email);
    var candidates = searchData.items || [];
    var candidateId = null;

    if (candidates.length > 0) {
      candidateId = candidates[0].candidateId;
      status.textContent = 'Found: ' + (candidates[0].firstName || '') + ' ' + (candidates[0].lastName || '');
    } else {
      // ── Candidate not found — ask user ────────────────────────
      var choice = await showJADialog(email);
      if (choice === 'skip') {
        status.textContent = 'Skipped.';
        markTabDone('format', _tabRun);
        btn.disabled = false;
        return;
      }
      status.textContent = 'Creating candidate…';
      var nameParts = ((_parsedData && _parsedData.candidate && _parsedData.candidate.name) || '').split(' ');
      var origBlob = window._originalFile ? new Blob([await window._originalFile.arrayBuffer()]) : null;
      var origFname = window._originalFile ? window._originalFile.name : null;
      var extraFields = {};
      if (_parsedData && _parsedData.candidate) {
        var c = _parsedData.candidate;
        if (c.phone) { extraFields.mobile = c.phone; extraFields.phone = c.phone; }
        if (c.linkedin) {
          var li = c.linkedin.trim();
          if (li && !li.startsWith('http')) li = 'https://' + li;
          extraFields.social = { linkedin: li };
        }
        if (c.address && (c.address.city || c.address.state || c.address.countryCode)) {
          extraFields.address = {
            city: c.address.city || '',
            state: c.address.state || '',
            countryCode: c.address.countryCode || ''
          };
        }
        var empCurrent = {};
        if (c.current_position) empCurrent.position = c.current_position;
        if (c.current_company)  empCurrent.employer  = c.current_company;
        if (window._jaPermWorkTypeId) empCurrent.workTypeId = window._jaPermWorkTypeId;
        empCurrent.salary = { ratePer: 'Month' };
        if (c.current_position || c.current_company || window._jaPermWorkTypeId) {
          extraFields.employment = { current: empCurrent };
        }
        var industryCustom = buildIndustryCustomFields(c);
        if (industryCustom) extraFields.custom = industryCustom;
      }
      var newCand = await jaCreateCandidate(nameParts[0] || 'Unknown', nameParts.slice(1).join(' ') || '', email, origBlob, origFname, extraFields);
      candidateId = newCand.candidateId;
      status.textContent = 'Created new candidate.';
    }

    // ── Upload DOCX against candidate (via Flask proxy) ───────────
    status.textContent = 'Uploading CV…';
    var fileName = 'Hyppies CV - ' + ((_parsedData && _parsedData.candidate && _parsedData.candidate.name) || 'Candidate') + '.docx';
    // Update industry custom fields on every upload
    var _singleIndustry = buildIndustryCustomFields(_parsedData && _parsedData.candidate ? _parsedData.candidate : {});
    if (_singleIndustry) {
      try { await jaUpdateCandidate(candidateId, { custom: _singleIndustry }); } catch(e) {}
    }
    await jaUploadCV(candidateId, window._docxBlob, fileName);

    var jaProfileLink = await jaProfileUrlAsync(candidateId);
    window._lastJaUrl = jaProfileLink;
    status.innerHTML = '✅ Uploaded! <a href="' + escAttr(jaProfileLink) + '" target="_blank" rel="noopener noreferrer" '
      + 'style="color:#2f855a;font-weight:600;text-decoration:underline;">View in JobAdder ↗</a>';
    showToast('CV uploaded to JobAdder!', 'ok');
    // Attach the link to the exact single-CV dashboard record.
    var singleStatsName = (_parsedData && _parsedData.candidate && _parsedData.candidate.name) || '';
    statsAttachJobAdderUrl(window._lastFormatStatsRecordId, jaProfileLink, singleStatsName, ['format','blind']);
    markTabDone('format', _tabRun);

  } catch(e) {
    status.textContent = '❌ ' + (e.message || 'Error');
    status.style.color = 'var(--red)';
    markTabFailed('format', _tabRun);
    showToast('JobAdder upload failed', 'err');
  }
  btn.disabled = false;
}

// ── JobAdder via Flask proxy (avoids CORS, handles token server-side) ──

// JobAdder throttles bursts of writes with HTTP 429 ("Try again shortly").
// A 429 means JobAdder rejected the request BEFORE processing it, so nothing
// was created or attached and retrying the exact same call is safe (it cannot
// duplicate a candidate or a CV attachment). Only an explicit 429 response is
// retried here — a timeout or network error is never retried, because there
// the request may actually have been processed server-side.
function jaRetrySleep(ms) {
  return new Promise(function(resolve) { setTimeout(resolve, ms); });
}

function jaRateLimitDelayMs(response) {
  // Honour JobAdder's Retry-After when present, otherwise wait 30s (matching
  // the manual "try again shortly" guidance); clamp so a stray header value
  // can neither hammer the API nor hang the upload indefinitely.
  var seconds = 0;
  try { seconds = parseInt(response.headers.get('Retry-After'), 10); } catch (e) { seconds = 0; }
  if (!isFinite(seconds) || seconds <= 0) seconds = 30;
  if (seconds < 5) seconds = 5;
  if (seconds > 60) seconds = 60;
  return seconds * 1000;
}

// Wraps a single JobAdder write POST/PUT so an HTTP 429 auto-retries after a
// short wait instead of failing straight to the user. Returns the final
// Response (ok, or the last error) so callers keep their existing handling.
function jaPostWithRetry(url, options, timeoutMs, label) {
  var maxRetries = 2;
  function attempt(n) {
    return fetchWithTimeout(url, options, timeoutMs).then(function(r) {
      if (r.status !== 429 || n >= maxRetries) return r;
      var waitMs = jaRateLimitDelayMs(r);
      try {
        if (typeof showToast === 'function') {
          showToast('JobAdder is busy — auto-retrying ' + (label || 'the upload') +
            ' in ' + Math.round(waitMs / 1000) + 's (attempt ' + (n + 1) + ' of ' + maxRetries + ')…', 'warn');
        }
      } catch (e) {}
      return jaRetrySleep(waitMs).then(function() { return attempt(n + 1); });
    });
  }
  return attempt(0);
}

async function jaSearchCandidate(email) {
  var r = await fetchWithTimeout('/jobadder/search_candidate?email=' + encodeURIComponent(email), {}, 15000);
  if (!r.ok) { var e = await r.json(); throw new Error(e.error || 'Search failed'); }
  return r.json();
}
async function jaCreateCandidate(firstName, lastName, email, originalBlob, originalFname, extraFields) {
  var payload = { firstName: firstName, lastName: lastName, email: email };
  if (extraFields) Object.assign(payload, extraFields);
  var r = await jaPostWithRetry('/jobadder/create_candidate', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  }, 15000, 'profile creation');
  if (!r.ok) { var e = await r.json(); throw new Error(e.error || 'Create failed: ' + (e.detail||'')); }
  var newCand = await r.json();
  // Upload original CV to Resume slot if provided
  if (originalBlob && newCand.candidateId) {
    try {
      await jaUploadOriginalCV(newCand.candidateId, originalBlob, originalFname || 'Original_CV.pdf');
    } catch(e) {
      console.warn('Original CV upload failed:', e.message);
    }
  }
  return newCand;
}
function buildIndustryCustomFields(cand) {
  // fieldId 1 = Industry, fieldId 2 = Industry Sub-Category
  var fields = [];
  if (cand.industry) {
    fields.push({ fieldId: 1, value: [cand.industry] });
  }
  if (cand.industry_sub) {
    fields.push({ fieldId: 2, value: [cand.industry_sub] });
  }
  return fields.length ? fields : null;
}

async function jaUpdateCandidate(candidateId, fields) {
  var r = await jaPostWithRetry('/jobadder/update_candidate', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(Object.assign({ candidateId: candidateId }, fields))
  }, 15000, 'candidate update');
  if (!r.ok) { var e = await r.json(); throw new Error(e.error || 'Update failed'); }
  return r.json();
}

async function jaUploadOriginalCV(candidateId, blob, fname) {
  var fd = new FormData();
  fd.append('candidate_id', candidateId);
  fd.append('file', blob, fname);
  var r = await jaPostWithRetry('/jobadder/upload_original_cv', { method: 'POST', body: fd }, 30000, 'original CV upload');
  if (!r.ok) {
    var e = await r.json();
    var msg = e.error || 'Original CV upload failed';
    if (e.detail) msg += ' | ' + e.detail;
    throw new Error(msg);
  }
  return r.json();
}

async function jaUploadCV(candidateId, blob, fname) {
  var fd = new FormData();
  fd.append('candidate_id', candidateId);
  fd.append('file', blob, fname);
  var r = await jaPostWithRetry('/jobadder/upload_cv', { method: 'POST', body: fd }, 30000, 'CV upload');
  if (!r.ok) {
    var e = await r.json();
    // Show full detail from JobAdder for debugging
    var msg = e.error || 'Upload failed';
    if (e.last_error) msg += ' | ' + e.last_error.url + ' → ' + e.last_error.code + ': ' + (e.last_error.detail || '');
    if (e.detail) msg += ' | ' + e.detail;
    throw new Error(msg);
  }
  return r.json();
}

// ── Batch JobAdder upload helper ─────────────────────────────────────
async function batchUploadToJobAdder(blob, fname, email, cvData, originalBlob, originalFname) {
  var searchData  = await jaSearchCandidate(email);
  var candidates  = searchData.items || [];
  var candidateId = null;

  if (candidates.length > 0) {
    candidateId = candidates[0].candidateId;
  } else {
    var nameParts = ((cvData && cvData.candidate && cvData.candidate.name) || '').split(' ');
    var batchExtra = {};
    if (cvData && cvData.candidate) {
      var bc = cvData.candidate;
      if (bc.phone) { batchExtra.mobile = bc.phone; batchExtra.phone = bc.phone; }
      if (bc.linkedin) {
        var bli = bc.linkedin.trim();
        if (bli && !bli.startsWith('http')) bli = 'https://' + bli;
        batchExtra.social = { linkedin: bli };
      }
      if (bc.address && (bc.address.city || bc.address.state || bc.address.countryCode)) {
        batchExtra.address = {
          city: bc.address.city || '',
          state: bc.address.state || '',
          countryCode: bc.address.countryCode || ''
        };
      }
      var bEmpCurrent = {};
      if (bc.current_position) bEmpCurrent.position = bc.current_position;
      if (bc.current_company)  bEmpCurrent.employer  = bc.current_company;
      if (window._jaPermWorkTypeId) bEmpCurrent.workTypeId = window._jaPermWorkTypeId;
      bEmpCurrent.salary = { ratePer: 'Month' };
      if (bc.current_position || bc.current_company || window._jaPermWorkTypeId) {
        batchExtra.employment = { current: bEmpCurrent };
      }
      var bIndustryCustom = buildIndustryCustomFields(bc);
      if (bIndustryCustom) batchExtra.custom = bIndustryCustom;
    }
    var newCand   = await jaCreateCandidate(nameParts[0] || 'Unknown', nameParts.slice(1).join(' ') || '', email, originalBlob, originalFname, batchExtra);
    candidateId   = newCand.candidateId;
  }
  // Update industry custom fields on every upload
  var _batchIndustry = cvData && cvData.candidate ? buildIndustryCustomFields(cvData.candidate) : null;
  if (_batchIndustry) {
    try { await jaUpdateCandidate(candidateId, { custom: _batchIndustry }); } catch(e) {}
  }
  await jaUploadCV(candidateId, blob, fname);
  return candidateId;
}

// ── Dialog: candidate not found ───────────────────────────────────────
function showJADialog(email) {
  return new Promise(function(resolve) {
    var overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.72);z-index:2147483646;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(2px);';
    overlay.innerHTML = [
      '<div style="background:#ffffff;color:#1a1a1a;border-radius:14px;padding:28px 32px;max-width:380px;width:90%;box-shadow:0 16px 48px rgba(0,0,0,0.5);">',
        '<p style="font-size:15px;font-weight:600;margin:0 0 8px;color:#1a1a1a;">Candidate not found</p>',
        '<p style="font-size:13px;color:#444;margin:0 0 20px;">No JobAdder candidate found with email <strong>' + esc(email) + '</strong>. What would you like to do?</p>',
        '<div style="display:flex;gap:10px;justify-content:flex-end;">',
          '<button data-ja-choice="skip" style="padding:8px 16px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text1);cursor:pointer;font-size:13px;">Skip</button>',
          '<button data-ja-choice="create" style="padding:8px 16px;border-radius:8px;border:none;background:#2b6cb0;color:#fff;cursor:pointer;font-size:13px;font-weight:700;box-shadow:0 2px 6px rgba(0,0,0,0.25);">Create New Candidate</button>',
        '</div>',
      '</div>'
    ].join('');
    overlay._resolve = function(val) { document.body.removeChild(overlay); resolve(val); };
    overlay.addEventListener('click', function(e) {
      var choice = e.target.getAttribute('data-ja-choice');
      if (choice) overlay._resolve(choice);
    });
    document.body.appendChild(overlay);
  });
}

// ── JobAdder token auto-refresh timer ────────────────────────────────
setInterval(async function(){
  if(!window._jaToken)return;
  try{var r=await fetch('/jobadder/refresh_token',{method:'POST'}),d=await r.json().catch(function(){return {};});if(r.ok||r.status===401){applyJAPublicInfo(d);renderJAConnectionState(d);}}catch(e){}
},5*60*1000);
