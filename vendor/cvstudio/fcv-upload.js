// ── FCV Upload Tab ───────────────────────────────────────────────
var _jaUploadQueue = [];

function updateJAUploadConnStatus() {
  var el = document.getElementById('jaUploadConnStatus');
  if (!el) return;
  if (window._jaToken) {
    el.textContent = '✅ Connected';
    el.style.color = '#2f855a';
    document.getElementById('btnJAUploadAll').disabled = _jaUploadQueue.length === 0;
  } else {
    el.textContent = '⚠ Not connected — connect in Format CV tab first';
    el.style.color = '#c05621';
    document.getElementById('btnJAUploadAll').disabled = true;
  }
}

function handleJAUploadDrop(e) {
  e.preventDefault();
  document.getElementById('jaUploadDrop').style.borderColor = 'var(--border)';
  handleJAUploadFiles(e.dataTransfer.files);
}

function handleJAUploadFiles(files) {
  for (var i = 0; i < files.length; i++) {
    var f = files[i];
    if (!f.name.toLowerCase().endsWith('.docx')) continue;
    var id = 'jau_' + Date.now() + '_' + i;
    _jaUploadQueue.push({ id: id, file: f, email: '', status: 'pending', statusText: '' });
  }
  renderJAUploadList();
  updateJAUploadConnStatus();
}

function isValidJAEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value || '').trim());
}

function renderJAUploadList() {
  var list = document.getElementById('jaUploadList');
  if (!list) return;
  if (_jaUploadQueue.length === 0) { list.innerHTML = ''; return; }
  list.innerHTML = _jaUploadQueue.map(function(item) {
    var sc = item.status === 'done' ? '#2f855a' : item.status === 'error' ? 'var(--red)' : item.status === 'uploading' ? '#2b6cb0' : 'var(--text3)';
    var escapedId = escJsAttr(item.id);
    return '<div style="display:flex;align-items:center;gap:10px;padding:10px 12px;background:var(--surface);border:1px solid var(--border);border-radius:8px;">'
      + '<span style="font-size:13px;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">📄 ' + esc(item.file.name) + '</span>'
      + '<input type="email" placeholder="" value="' + escAttr(item.email) + '"'
      + ' style="font-size:12px;padding:3px 8px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text1);width:200px;height:28px;"'
      + ' oninput="(function(el){var q=_jaUploadQueue.find(function(x){return x.id===\'' + escapedId + '\';});if(q)q.email=el.value;})(this)"/>'
      + '<span style="font-size:11px;min-width:90px;color:' + sc + ';">' + (item.jaProfileUrl ? '✅ <a href="' + escAttr(item.jaProfileUrl) + '" target="_blank" rel="noopener noreferrer" style="color:#2f855a;font-weight:600;text-decoration:underline;">View in JobAdder ↗</a>' : esc(item.statusText || 'Pending')) + '</span>'
      + '<button onclick="removeJAUploadItem(\'' + escapedId + '\')" style="font-size:11px;padding:2px 8px;border-radius:6px;border:1px solid var(--border);background:var(--surface);cursor:pointer;">✕</button>'
      + '</div>';
  }).join('');
}

function setBatchManualEmail(el, id) {
  var b = _batchFiles.find(function(x){ return x.id === id; });
  if (b && el.value.trim()) {
    b._manualEmail = el.value.trim();
    b.jaStatus = '☁ Uploading…';
    b.jaClass  = 'show uploading';
    renderBatchList();
    // Trigger upload now that we have an email
    if (window._jaToken && b.cvData && b._docxBlob) {
      (async function() {
        try {
          var origAB = await b.file.arrayBuffer();
          var jaCanId = await batchUploadToJobAdder(b._docxBlob, b.filename, b._manualEmail, b.cvData, new Blob([origAB]), b.file.name);
          b.jaStatus = '✅ Uploaded';
          b.jaClass  = 'show uploaded';
          var jaLink = jaCanId ? await jaProfileUrlAsync(jaCanId) : '';
          if (jaLink) {
            b.jaStatus = '✅ <a href="' + escAttr(jaLink) + '" target="_blank" rel="noopener noreferrer" style="color:#2f855a;font-weight:700;text-decoration:underline;">View ↗</a>';
            var batchStatsName = (b.cvData && b.cvData.candidate && b.cvData.candidate.name) || b.file.name.replace(/\.[^.]+$/, '');
            statsAttachJobAdderUrl(b._statsRecordId, jaLink, batchStatsName, ['format','blind']);
          }
          renderBatchList();
        } catch(e) {
          b.jaStatus = '❌ Upload failed';
          b.jaClass  = 'show ja-err';
          renderBatchList();
          showToast('JA upload failed: ' + (e.message||'').split('|')[0].trim(), 'err');
        }
      })();
    }
  }
}

function removeJAUploadItem(id) {
  _jaUploadQueue = _jaUploadQueue.filter(function(x){ return x.id !== id; });
  renderJAUploadList();
  updateJAUploadConnStatus();
}

function clearJAUploadQueue() {
  clearTabRunState('jaupload');
  _jaUploadQueue = [];
  renderJAUploadList();
  var s = document.getElementById('jaUploadAllStatus');
  if (s) s.textContent = '';
  updateJAUploadConnStatus();
}

async function runJAUploadAll() {
  if (!window._jaToken) { showToast('Connect to JobAdder first', 'err'); return; }
  var statusEl = document.getElementById('jaUploadAllStatus');
  var _tabRun = markTabRunning('jaupload');
  document.getElementById('btnJAUploadAll').disabled = true;
  var doneCount = 0, errCount = 0;

  for (var i = 0; i < _jaUploadQueue.length; i++) {
    var item = _jaUploadQueue[i];
    if (item.status === 'done') continue;
    if (!item.email.trim()) {
      item.status = 'error'; item.statusText = '❌ No email';
      renderJAUploadList(); errCount++; continue;
    }
    if (!isValidJAEmail(item.email)) {
      item.status = 'error'; item.statusText = '❌ Invalid email';
      renderJAUploadList(); errCount++; continue;
    }
    item.status = 'uploading'; item.statusText = '☁ Uploading…';
    renderJAUploadList();
    try {
      var searchData = await jaSearchCandidate(item.email.trim());
      var candidates = (searchData.items || []);
      var candidateId = null;
      if (candidates.length > 0) {
        candidateId = candidates[0].candidateId;
      } else {
        var guessName = item.file.name.replace(/Hyppies CV - ?/i,'').replace(/[(]Blinded[)]/i,'').replace(/[.]docx$/i,'').trim();
        var parts = guessName.split(' ');
        var newCand = await jaCreateCandidate(parts[0]||'Unknown', parts.slice(1).join(' ')||'', item.email.trim(), null, null);
        candidateId = newCand.candidateId;
      }
      var ab = await item.file.arrayBuffer();
      var fileBlob = new Blob([ab], {type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'});
      await jaUploadCV(candidateId, fileBlob, item.file.name);
      item.status = 'done';
      item.statusText = '✅ Uploaded';
      item.jaProfileUrl = await jaProfileUrlAsync(candidateId);
      var guessDisplayName = item.file.name.replace(/Hyppies CV - ?/i,'').replace(/[(]Blinded[)]/i,'').replace(/[.]docx$/i,'').trim();
      statsRecord(guessDisplayName, 'format', 0, aiRoutePayload('cv_single').model, item.jaProfileUrl, aiRoutePayload('cv_single').provider);
      doneCount++;
    } catch(err) {
      item.status = 'error'; item.statusText = '❌ ' + (err.message||'Failed'); errCount++;
    }
    renderJAUploadList();
    statusEl.textContent = (doneCount+errCount) + ' / ' + _jaUploadQueue.length + ' done';
  }

  document.getElementById('btnJAUploadAll').disabled = false;
  if (doneCount > 0) markTabDone('jaupload', _tabRun); else markTabFailed('jaupload', _tabRun);
  showToast(doneCount + ' uploaded' + (errCount ? ', ' + errCount + ' failed' : ''), doneCount > 0 ? 'ok' : 'err');
  statusEl.textContent = doneCount + ' uploaded' + (errCount ? ', ' + errCount + ' failed' : '');
}



// ── JobAdder profile URL helper ──────────────────────────────────────
function jaProfileUrl(candidateId) {
  // Priority: in-memory > localStorage (if not the generic fallback) > server-stored > generic fallback
  var memBase = window._jaWebBase;
  var lsBase  = (function(){ try { return localStorage.getItem('ja_web_base') || ''; } catch(e){ return ''; } })();
  // Ignore stale 'app.jobadder.com' values in localStorage
  if (lsBase === 'https://app.jobadder.com') lsBase = '';
  var base = (memBase && memBase !== 'https://app.jobadder.com') ? memBase
           : lsBase
           || 'https://app.jobadder.com';
  return base + '/candidates/' + candidateId + '?tab=3';
}

async function jaProfileUrlAsync(candidateId) {
  // Always fetch fresh from server before building URL — guarantees correct region
  if (!window._jaWebBase || window._jaWebBase === 'https://app.jobadder.com') {
    try {
      var r = await fetch('/jobadder/api_info');
      var d = await r.json();
      if (d.api_url) {
        var m = d.api_url.match(/https?:\/\/(?:api\.([a-z0-9]+\.jobadder\.com)|([a-z0-9]+)api\.jobadder\.com)/i);
        if (m) {
          var region = m[1] || (m[2] + '.jobadder.com');
          window._jaWebBase = 'https://' + region;
          try { localStorage.setItem('ja_web_base', window._jaWebBase); } catch(e) {}
        }
      }
    } catch(e) {}
  }
  return jaProfileUrl(candidateId);
}

// ── Restore JA session on page load ──────────────────────────────────
(async function(){
  try {
    var stored=localStorage.getItem('ja_web_base'); if(stored&&stored!=='https://app.jobadder.com')window._jaWebBase=stored;
    var legacy={access_token:localStorage.getItem('ja_access_token')||'',refresh_token:localStorage.getItem('ja_refresh_token')||'',api_url:localStorage.getItem('ja_api_url')||'',client_id:localStorage.getItem('ja_client_id')||'',client_secret:localStorage.getItem('ja_client_secret')||'',expires_at:parseInt(localStorage.getItem('ja_token_expiry')||'0')};
    var legacyMigrated=!(legacy.access_token||legacy.refresh_token);
    if(!legacyMigrated){
      var mr=await fetch('/jobadder/restore_token',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(legacy)});
      var md=await mr.json().catch(function(){return {};});
      legacyMigrated=!!(mr.ok&&md.ok&&md.connected);
    }
    // Never delete the only copy of a legacy credential until the backend has
    // confirmed that it was durably stored. A failed DPAPI/Keychain/file write
    // can then be retried on the next launch instead of silently disconnecting.
    if(legacyMigrated){['ja_access_token','ja_refresh_token','ja_token_expiry','ja_client_secret'].forEach(function(k){localStorage.removeItem(k);});}
  } catch(e) {}
  try {
    var r=await fetch('/jobadder/api_info',{cache:'no-store'}),d=await r.json();
    applyJAPublicInfo(d);
    renderJAConnectionState(d);
    if(d.connected){updateJAConnectedUI(d);}
    if(d.api_url){var m=String(d.api_url).match(/https?:\/\/(?:api\.([a-z0-9]+\.jobadder\.com)|([a-z0-9]+)api\.jobadder\.com)/i);if(m){window._jaWebBase='https://'+(m[1]||(m[2]+'.jobadder.com'));localStorage.setItem('ja_web_base',window._jaWebBase);}}
  } catch(e) {}
})();

async function syncTokenToFlask(){ return true; }

function updateJAConnectedUI(info) {
  info = Object.assign({
    connected:true,
    client_id:window._jaConfiguredClientId || getJAClientId(),
    client_secret_configured:window._jaClientSecretConfigured
  }, info || {});
  renderJAConnectionState(info);
  // Fetch work type list to find Permanent ID
  fetch('/jobadder/lists?name=worktype').then(function(r){ return r.json(); }).then(function(d) {
    var items = d.items || [];
    var perm = items.find(function(x){ return x.name && x.name.toLowerCase().includes('permanent'); });
    if (perm) {
      window._jaPermWorkTypeId = perm.workTypeId;
      try { localStorage.setItem('ja_perm_work_type_id', perm.workTypeId); } catch(e) {}
    }
  }).catch(function(){});
}


