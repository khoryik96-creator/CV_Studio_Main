// ── Create Profile Tab ────────────────────────────────────────────────
var _jaCreateQueue = []; // [{id, file, status, statusText, jaClass, jaProfileUrl, optional OneNote source metadata}]

function updateJACreateConnStatus() {
  var el = document.getElementById('jaCreateConnStatus');
  if (!el) return;
  if (window._jaToken) {
    el.textContent = '✅ Connected'; el.style.color = '#2f855a';
    document.getElementById('btnJACreateAll').disabled = _jaCreateQueue.length === 0;
  } else {
    el.textContent = '⚠ Not connected — connect in Format CV tab first';
    el.style.color = '#c05621';
    document.getElementById('btnJACreateAll').disabled = true;
  }
}

function handleJACreateDrop(e) {
  e.preventDefault();
  document.getElementById('jaCreateDrop').style.borderColor = 'var(--border)';
  handleJACreateFiles(e.dataTransfer.files);
}

function handleJACreateFiles(files) {
  for (var i = 0; i < files.length; i++) {
    var f = files[i];
    var ext = f.name.toLowerCase();
    if (!ext.endsWith('.pdf') && !ext.endsWith('.docx') && !ext.endsWith('.doc')) continue;
    var id = 'jac_' + Date.now() + '_' + i;
    _jaCreateQueue.push({ id: id, file: f, status: 'pending', statusText: '', jaClass: '', jaProfileUrl: '' });
  }
  renderJACreateList();
  updateJACreateConnStatus();
}

function renderJACreateList() {
  var list = document.getElementById('jaCreateList');
  if (!list) return;
  if (_jaCreateQueue.length === 0) { list.innerHTML = ''; return; }
  list.innerHTML = _jaCreateQueue.map(function(item) {
    var sc = item.jaClass === 'show uploaded' ? '#2f855a'
           : item.jaClass === 'show ja-err'   ? 'var(--red)'
           : item.jaClass === 'show uploading' ? '#2b6cb0'
           : 'var(--text3)';
    var statusHtml;
    if (item.jaProfileUrl) {
      statusHtml = '✅ <a href="' + escAttr(item.jaProfileUrl) + '" target="_blank" rel="noopener noreferrer" style="color:#2f855a;font-weight:600;text-decoration:underline;">View in JobAdder ↗</a>';
    } else if (item.status === 'needemail') {
      statusHtml = '<input type="email" placeholder="" data-jcid="' + item.id + '" '
        + 'onchange="setJACreateEmail(this,this.dataset.jcid)" '
        + 'style="font-size:11px;padding:2px 6px;border:1px solid #c05621;border-radius:4px;width:160px;background:var(--card);color:var(--text1);" />';
    } else {
      statusHtml = item.statusText || 'Pending';
    }
    var sourceMeta = item._oneNoteRowIndex !== undefined ? ('<span style="display:block;font-size:10px;color:var(--text3);margin-top:2px;">From OneNote · ' + esc(item._forcedEmail || '') + '</span>') : '';
    return '<div style="display:flex;align-items:center;gap:10px;padding:10px 12px;background:var(--surface);border:1px solid var(--border);border-radius:8px;">'
      + '<span style="font-size:13px;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">📋 ' + esc(item.file.name) + sourceMeta + '</span>'
      + '<span style="font-size:11px;min-width:140px;color:' + sc + ';">' + statusHtml + '</span>'
      + (item.cost ? '<span style="font-size:11px;color:var(--text3);background:var(--surface);border:1px solid var(--border);border-radius:20px;padding:1px 7px;">🔥 $' + item.cost.toFixed(4) + '</span>' : '')
      + ((item.status === 'pending' || item.status === 'error') ? '<button type="button" data-jcid="' + escAttr(item.id) + '" onclick="event.stopPropagation();runJACreateOne(this.dataset.jcid);return false;" style="font-size:11px;padding:2px 10px;border-radius:6px;border:none;background:#2b6cb0;color:#fff;cursor:pointer;margin-right:4px;">Create</button>' : '')
      + '<button type="button" data-ja-create-remove="1" data-jcid="' + escAttr(item.id) + '" onclick="return removeJACreateItem(this.getAttribute(\'data-jcid\'), event)" aria-label="Remove file" title="Remove file" style="font-size:11px;padding:2px 8px;border-radius:6px;border:1px solid var(--border);background:var(--surface);cursor:pointer;">✕</button>'
      + '</div>';
  }).join('');
}

function removeJACreateItem(id, ev) {
  if (ev && ev.preventDefault) ev.preventDefault();
  if (ev && ev.stopPropagation) ev.stopPropagation();
  id = String(id || '');
  var before = _jaCreateQueue.length;
  _jaCreateQueue = _jaCreateQueue.filter(function(x){ return String(x.id) !== id; });
  renderJACreateList();
  var s = document.getElementById('jaCreateAllStatus');
  if (s && before !== _jaCreateQueue.length) s.textContent = '';
  updateJACreateConnStatus();
  return false;
}

// v24.6.80: robust delegated handler for Create Profile remove buttons.
// This avoids inline-click edge cases caused by nested rendered HTML, global blur guards,
// or event bubbling from the file/drop area.
document.addEventListener('click', function(e) {
  var btn = e.target && e.target.closest ? e.target.closest('[data-ja-create-remove]') : null;
  if (!btn) return;
  removeJACreateItem(btn.getAttribute('data-jcid'), e);
}, true);

function clearJACreateQueue() {
  clearTabRunState('jacreate');
  _jaCreateQueue = [];
  renderJACreateList();
  var s = document.getElementById('jaCreateAllStatus');
  if (s) s.textContent = '';
  updateJACreateConnStatus();
}


function extractJACreateEmailFallback(text) {
  var s = String(text || '');
  var m = s.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i);
  return m ? m[0].trim() : '';
}

function cleanJACreatePhoneCandidate(raw) {
  var s = String(raw || '').replace(/\s+/g, ' ').trim();
  s = s.replace(/^(phone|mobile|contact|tel|telephone|handphone)\s*[:\-]?\s*/i, '').trim();
  s = s.replace(/[^+\d().\-\s]/g, '').trim();
  var digits = s.replace(/\D/g, '');
  if (digits.length < 8 || digits.length > 15) return '';
  if (/^(19|20)\d{6,}$/.test(digits)) return ''; // likely date range, not phone
  return s;
}

function extractJACreatePhoneFallback(text) {
  var s = String(text || '');
  var label = s.match(/(?:mobile|mobile phone no\.?|phone|contact|tel|telephone|handphone)\s*(?:no\.?|number)?\s*[:\-]?\s*(\+?\d[\d\s().\-]{6,22}\d)/i);
  if (label) {
    var labelled = cleanJACreatePhoneCandidate(label[1]);
    if (labelled) return labelled;
  }
  var matches = s.match(/\+?\d[\d\s().\-]{7,22}\d/g) || [];
  for (var i = 0; i < matches.length; i++) {
    var c = cleanJACreatePhoneCandidate(matches[i]);
    if (!c) continue;
    var digits = c.replace(/\D/g, '');
    // Prefer plausible MY/SG-style mobile numbers or international numbers.
    if (/^(60|65|01|1)\d{7,12}$/.test(digits) || /^\+/.test(c)) return c;
  }
  return '';
}

function applyJACreateContactFallback(cand, cvText) {
  cand = cand || {};
  if (!cand.email) {
    var e = extractJACreateEmailFallback(cvText);
    if (e) cand.email = e;
  }
  if (!cand.phone) {
    var p = extractJACreatePhoneFallback(cvText);
    if (p) cand.phone = p;
  }
  return cand;
}

async function setJACreateEmail(el, id) {
  var email = el.value.trim();
  if (!email) return;
  var item = _jaCreateQueue.find(function(x){ return x.id === id; });
  if (!item) return;
  item._manualEmail = email;
  var _tabRun = markTabRunning('jacreate');
  item.status = 'processing'; item.statusText = '⏳ Processing…'; item.jaClass = 'show uploading';
  renderJACreateList();
  // Re-run just this item
  try {
    var cand = item._parsedCand || {};
    var nameParts = (cand.name || '').split(' ');
    var firstName = nameParts[0] || 'Unknown';
    var lastName  = nameParts.slice(1).join(' ') || '';
    var searchData = await jaSearchCandidate(email);
    var candidates = (searchData.items || []);
    if (candidates.length > 0) {
      var eid2 = candidates[0].candidateId;
      var uF2 = {};
      if (cand.phone) { uF2.mobile = cand.phone; uF2.phone = cand.phone; }
      if (cand.linkedin) { var l2 = cand.linkedin.trim(); if (!l2.startsWith('http')) l2='https://'+l2; uF2.social={linkedin:l2}; }
      if (Object.keys(uF2).length) { try { await jaUpdateCandidate(eid2, uF2); } catch(e){} }
      var oAB = await item.file.arrayBuffer();
      await jaUploadOriginalCV(eid2, new Blob([oAB]), item.file.name);
      item.status='done'; item.jaClass='show uploaded';
      item.jaProfileUrl = await jaProfileUrlAsync(eid2);
      item.statusText = '✅ Updated existing profile';
    } else {
      var eF2 = {};
      if (cand.phone) { eF2.mobile=cand.phone; eF2.phone=cand.phone; }
      if (cand.linkedin) { var l3=cand.linkedin.trim(); if(!l3.startsWith('http'))l3='https://'+l3; eF2.social={linkedin:l3}; }
      var oAB2 = await item.file.arrayBuffer();
      var nC = await jaCreateCandidate(firstName, lastName, email, new Blob([oAB2]), item.file.name, eF2);
      item.status='done'; item.jaClass='show uploaded';
      item.jaProfileUrl = await jaProfileUrlAsync(nC.candidateId);
      item.statusText = '✅ Profile created';
    }
    var manualCreateName = cand.name || item.file.name;
    statsRecord(manualCreateName, 'create', item.cost || 0, item._statsModel || aiRoutePayload('ja_create').model, item.jaProfileUrl || '', item._statsProvider || aiRoutePayload('ja_create').provider, item._statsMeta);
    markTabDone('jacreate', _tabRun);
  } catch(err) {
    item.status='error'; item.statusText='❌ '+(err.message||'Failed').substring(0,50); item.jaClass='show ja-err';
    showToast('Failed: '+(err.message||'').split('|')[0].trim(), 'err');
    markTabFailed('jacreate', _tabRun);
  }
  renderJACreateList();
}

async function runJACreateOne(id) {
  var item = _jaCreateQueue.find(function(x){ return x.id === id; });
  if (!item || !window._jaToken) return;
  // Temporarily run just this item by marking others as skip
  var prev = _jaCreateQueue.map(function(x){ return { id: x.id, status: x.status }; });
  _jaCreateQueue.forEach(function(x){ if (x.id !== id) x._skip = true; });
  await runJACreateAll();
  _jaCreateQueue.forEach(function(x){ delete x._skip; });
}

async function runJACreateAll() {
  if (!window._jaToken) { showToast('Connect to JobAdder first', 'err'); return; }
  var _tabRun = markTabRunning('jacreate');
  document.getElementById('btnJACreateAll').disabled = true;
  var statusEl = document.getElementById('jaCreateAllStatus');
  var doneCount = 0, errCount = 0;

  for (var i = 0; i < _jaCreateQueue.length; i++) {
    var item = _jaCreateQueue[i];
    if (item.status === 'done' || item._skip) continue;

    item.status = 'processing'; item.statusText = '⏳ Extracting CV…'; item.jaClass = 'show uploading';
    renderJACreateList();

    try {
      // Step 1: Extract text from CV via Flask
      var fd = new FormData();
      fd.append('file', item.file);
      var extRes = await fetchWithTimeout('/extract-text', { method: 'POST', body: fd }, CV_EXTRACT_TEXT_TIMEOUT_MS);
      var extData = await extRes.json().catch(function(){ return {}; });
      if (!extRes.ok) throw new Error(extData.error || 'Text extraction failed');
      var cvText = extData.text || '';
      if (!cvText.trim()) throw new Error('No text extracted from CV');

      // Step 2: Parse CV with the configured route to extract fields
      var jaRoute = aiRoutePayload('ja_create');
      if (!jaRoute.api_key) throw new Error('Save an API key for JobAdder Create Profile route');
      item.statusText = '⏳ Parsing ' + (cvParseIsLong(cvText) ? 'long CV' : 'CV') + ' with ' + jaRoute.route.provider_label + '…';
      renderJACreateList();
      var parseRes = await fetchWithTimeout('/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: jaRoute.api_key, cv_text: cvText, model: jaRoute.model, provider: jaRoute.provider })
      }, cvParseTimeoutMs(cvText));
      var parsed = await parseRes.json().catch(function(){ return {}; });
      if (!parseRes.ok || parsed.error) {
        recordPaidAiFailure('JobAdder Create Profile parse failed', parsed, jaRoute.model, jaRoute.provider);
        throw new Error(normalizeAiProviderError(parsed.error || ('Parse failed: ' + parseRes.status), jaRoute));
      }
      if (parsed.warning) showToast(parsed.warning, 'info');
      var cand = (parsed && parsed.data && parsed.data.candidate) ? parsed.data.candidate : {};
      cand = applyJACreateContactFallback(cand, cvText);
      // A CV launched from an unmatched OneNote note must create/search using
      // that note's confirmed email, even when the CV contains no email or a
      // different contact address. This keeps the new profile tied to the
      // exact screening-note row that initiated the action.
      if (item._forcedEmail) cand.email = String(item._forcedEmail || '').trim().toLowerCase();
      if (!String(cand.name || '').trim() && item._oneNoteSourceName) cand.name = String(item._oneNoteSourceName || '').trim();
      // Track cost
      var createCost = responseCost(parsed, jaRoute.model, jaRoute.provider);
      item._statsMeta = statsMetaFromResponse(parsed, jaRoute.model, jaRoute.provider);
      item.cost = createCost;
      item._statsModel = parsed.model || jaRoute.model;
      item._statsProvider = parsed.provider || jaRoute.provider;

      // Step 3: Build name parts
      var nameParts = (cand.name || '').split(' ');
      var firstName = nameParts[0] || 'Unknown';
      var lastName  = nameParts.slice(1).join(' ') || '';
      var email     = cand.email || '';

      if (!email) {
        // No email — show inline input for manual entry
        item.status = 'needemail'; item.jaClass = 'show ja-skip';
        item.statusText = ''; item._parsedCand = cand;
        renderJACreateList(); continue;
      }

      // Step 4: Check if candidate already exists
      item.statusText = '⏳ Checking JobAdder…';
      renderJACreateList();
      var searchData = await jaSearchCandidate(email);
      var candidates = (searchData.items || []);

      if (candidates.length > 0) {
        // Existing candidate — update profile fields then upload CV
        var existingId = candidates[0].candidateId;
        item.statusText = '⏳ Updating profile…';
        renderJACreateList();
        // Build update payload from extracted fields
        var updateFields = {};
        if (cand.phone) { updateFields.mobile = cand.phone; updateFields.phone = cand.phone; }
        if (cand.linkedin) {
          var uli = cand.linkedin.trim();
          if (uli && !uli.startsWith('http')) uli = 'https://' + uli;
          updateFields.social = { linkedin: uli };
        }
        if (cand.address && (cand.address.city || cand.address.state || cand.address.countryCode)) {
          updateFields.address = { city: cand.address.city||'', state: cand.address.state||'', countryCode: cand.address.countryCode||'' };
        }
        var uEmpCur = {};
        if (cand.current_position) uEmpCur.position = cand.current_position;
        if (cand.current_company)  uEmpCur.employer  = cand.current_company;
        if (window._jaPermWorkTypeId) uEmpCur.workTypeId = window._jaPermWorkTypeId;
        uEmpCur.salary = { ratePer: 'Month' };
        if (uEmpCur.position || uEmpCur.employer || window._jaPermWorkTypeId) {
          updateFields.employment = { current: uEmpCur };
        }
        var uIndustryCustom = buildIndustryCustomFields(cand);
        if (uIndustryCustom) updateFields.custom = uIndustryCustom;
        if (Object.keys(updateFields).length > 0) {
          try { await jaUpdateCandidate(existingId, updateFields); } catch(ue) { console.warn('Update fields failed:', ue.message); }
        }
        // Upload original CV to Resume slot
        item.statusText = '⏳ Uploading CV…';
        renderJACreateList();
        var origAB = await item.file.arrayBuffer();
        await jaUploadOriginalCV(existingId, new Blob([origAB]), item.file.name);
        item.status = 'done'; item.jaClass = 'show uploaded';
        item.jaProfileUrl = await jaProfileUrlAsync(existingId);
        item.statusText = '✅ Updated existing profile';
        statsRecord(cand.name || item.file.name, 'create', createCost, item._statsModel || jaRoute.model, item.jaProfileUrl, item._statsProvider || jaRoute.provider, item._statsMeta);
        oneNoteProfileCreateCompleted(item, existingId, cand, false);
        doneCount++;
      } else {
        // Create new candidate
        item.statusText = '⏳ Creating profile…';
        renderJACreateList();
        var extraFields = {};
        if (cand.phone) { extraFields.mobile = cand.phone; extraFields.phone = cand.phone; }
        if (cand.linkedin) {
          var li = cand.linkedin.trim();
          if (li && !li.startsWith('http')) li = 'https://' + li;
          extraFields.social = { linkedin: li };
        }
        if (cand.address && (cand.address.city || cand.address.state || cand.address.countryCode)) {
          extraFields.address = { city: cand.address.city||'', state: cand.address.state||'', countryCode: cand.address.countryCode||'' };
        }
        var empCur = {};
        if (cand.current_position) empCur.position = cand.current_position;
        if (cand.current_company)  empCur.employer  = cand.current_company;
        if (window._jaPermWorkTypeId) empCur.workTypeId = window._jaPermWorkTypeId;
        empCur.salary = { ratePer: 'Month' };
        if (empCur.position || empCur.employer || window._jaPermWorkTypeId) {
          extraFields.employment = { current: empCur };
        }
        var cIndustryCustom = buildIndustryCustomFields(cand);
        if (cIndustryCustom) extraFields.custom = cIndustryCustom;

        var origAB2 = await item.file.arrayBuffer();
        var newCand = await jaCreateCandidate(firstName, lastName, email, new Blob([origAB2]), item.file.name, extraFields);
        item.status = 'done'; item.jaClass = 'show uploaded';
        item.jaProfileUrl = await jaProfileUrlAsync(newCand.candidateId);
        item.statusText = '✅ Profile created';
        statsRecord(cand.name || item.file.name, 'create', createCost, item._statsModel || jaRoute.model, item.jaProfileUrl, item._statsProvider || jaRoute.provider, item._statsMeta);
        oneNoteProfileCreateCompleted(item, newCand.candidateId, cand, true);
        doneCount++;
      }

    } catch(err) {
      item.status = 'error';
      item.statusText = '❌ ' + (err.message || 'Failed').substring(0, 50);
      item.jaClass = 'show ja-err';
      showToast('❌ Failed: ' + item.file.name + ' — ' + (err.message||'').split('|')[0].trim(), 'err');
      oneNoteProfileCreateFailed(item, err);
      errCount++;
    }

    renderJACreateList();
    statusEl.textContent = (doneCount + errCount) + ' / ' + _jaCreateQueue.length + ' processed';
  }

  document.getElementById('btnJACreateAll').disabled = false;
  if (doneCount > 0) markTabDone('jacreate', _tabRun); else markTabFailed('jacreate', _tabRun);
  showToast(doneCount + ' profile(s) created' + (errCount ? ', ' + errCount + ' failed' : ''), doneCount > 0 ? 'ok' : 'err');
  statusEl.textContent = doneCount + ' created' + (errCount ? ', ' + errCount + ' failed' : '');
}
