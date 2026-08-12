async function startFormat(blind) {
  blind = !!blind;
  var raw = '';
  if (_activeInputTab === 'upload') {
    raw = _extractedText;
    if (!raw) { showToast('Upload and extract a file first', 'err'); return; }
  } else {
    raw = document.getElementById('cvInput').value.trim();
    if (!raw) { showToast('Paste a CV first', 'err'); return; }
  }
  var linkedSummaryBullets = formatSummaryBulletsFor(raw, blind);
  var summaryToggle = document.getElementById('singleSummaryToggle');
  var withAutomaticSummary = !blind && !linkedSummaryBullets.length && !!(summaryToggle && summaryToggle.checked);
  var route = aiRoutePayload('cv_single');
  var key = route.api_key;
  if (!key) { showToast('Save an API key for Single CV Formatting route', 'err'); document.getElementById('keyInput').focus(); return; }
  var automaticSummaryRoute = withAutomaticSummary ? aiRoutePayload('summary') : null;
  if (withAutomaticSummary && !automaticSummaryRoute.api_key) { showToast('Save an API key for the CV Summary route or turn off Generate CV Summary', 'err'); return; }
  var singleSummaryDetail = withAutomaticSummary ? getCvSummaryDetailPreference('single') : 'concise';

  var _tabRun = markTabRunning('format');
  document.getElementById('btnFormat').disabled = true;
  document.getElementById('btnBlind').disabled  = true;
  document.getElementById('btnDocx').disabled   = true;
  document.getElementById('blindBadge').style.display = 'none';
  _parsedData = null;
  document.getElementById('jaBar').style.display = 'none';
  var _jaSettingsPanel = document.getElementById('jaSettingsPanel');
  if (_jaSettingsPanel) _jaSettingsPanel.style.display = 'none';
  document.getElementById('jaStatus').textContent = '';
  var bjs3 = document.getElementById('batchJAStatus');
  if (bjs3 && !window._jaToken) bjs3.style.display = 'none';
  window._realCandidateName = '';
  window._filenameGuessedName = '';
  _runCost = 0;
  _runUsage = normalizeUsageClient({});
  document.getElementById('costPill').className = 'cost-pill';

  // Configure steps for blind vs normal
  var totalSteps = blind || withAutomaticSummary ? 4 : 3;
  if (blind) {
    document.getElementById('pstep2label').textContent = 'Blinding CV';
    document.getElementById('pstep3label').textContent = 'Generating DOCX';
  } else if (withAutomaticSummary) {
    document.getElementById('pstep2label').textContent = 'Generating Summary';
    document.getElementById('pstep3label').textContent = 'Generating DOCX';
  } else {
    document.getElementById('pstep2label').textContent = 'Generating DOCX';
    document.getElementById('pstep3label').textContent = 'Done';
  }

  showProgress();

  // ── Step 1: Parse ──────────────────────────────────────────────────────────
  setProgress(5, 'Step 1 — Parsing ' + (cvParseIsLong(raw) ? 'long CV' : 'CV') + ' with ' + route.provider_label + '…', 1, totalSteps);
  setOutput('<div style="color:var(--text3);font-style:italic;padding:20px;">Parsing CV structure…</div>');

  var _fakeProgress = 5;
  var _fakeInterval = setInterval(function() {
    if (_fakeProgress < 42) {
      _fakeProgress += (42 - _fakeProgress) * 0.04;
      document.getElementById('progressFill').style.width = _fakeProgress + '%';
    }
  }, 300);

  try {
    var res = await fetchWithTimeout('/parse', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({api_key: key, api_key_slot: route.api_key_slot, cv_text: raw, model: route.model, provider: route.provider}) }, cvParseTimeoutMs(raw));
    var rawText = await res.text();
    var data;
    try { data = JSON.parse(rawText); } catch(je) { throw new Error('Server returned invalid JSON:\n' + rawText.slice(0,600)); }
    if (!res.ok || data.error) {
      recordPaidAiFailure('Single CV parse failed', data, route.model, route.provider);
      throw new Error(normalizeAiProviderError(data.error || 'Server error: ' + res.status, route));
    }
    clearInterval(_fakeInterval);
    _parsedData = applyFormatSummaryBullets(data.data, raw, blind);
    _labelBulletLevels = Array.isArray(data.bullet_levels) ? data.bullet_levels : null;
    if (!_parsedData) {
      recordPaidAiFailure('Single CV parse returned no data', data, route.model, route.provider);
      throw new Error('No data in response');
    }
    if (data.warning) showToast(data.warning, 'info');
    _runCost += responseCost(data, route.model, route.provider);
    _runUsage = mergeUsageClient(_runUsage, data.usage || {});
    if (withAutomaticSummary) {
      setProgress(44, 'Step 2 — Filling the Summary placeholder with ' + automaticSummaryRoute.provider_label + '…', 2, totalSteps);
      setOutput('<div style="color:var(--text3);font-style:italic;padding:20px;">Generating source-grounded CV Summary…</div>');
      var summaryResult = await requestFormattingSummary(raw, automaticSummaryRoute, singleSummaryDetail);
      _parsedData.summary_bullets = summaryResult.bullets.slice();
      _runCost += summaryResult.cost;
      _runUsage = mergeUsageClient(_runUsage, summaryResult.usage);
    }
    // Save real name before blinding overwrites it
    // If parsed name is "Candidate" (already-blinded file), fall back to filename guess
    var parsedName = (_parsedData && _parsedData.candidate && _parsedData.candidate.name) || '';
    window._realCandidateName = (parsedName && parsedName.toLowerCase() !== 'candidate')
      ? parsedName
      : (window._filenameGuessedName || parsedName);

    // ── Step 2 (blind only): Blind the CV ────────────────────────────────────
    if (blind) {
      setProgress(44, 'Step 2 — Blinding identity & company names…', 2, totalSteps);
      setOutput('<div style="color:var(--text3);font-style:italic;padding:20px;">Redacting identity and masking company names…</div>');

      var _fake2 = 44;
      var _fakeInterval2 = setInterval(function() {
        if (_fake2 < 68) { _fake2 += (68 - _fake2) * 0.04; document.getElementById('progressFill').style.width = _fake2 + '%'; }
      }, 300);

      var bRes = await fetchWithTimeout('/blind', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({api_key: key, api_key_slot: route.api_key_slot, cv_data: _parsedData, model: route.model, provider: route.provider}) }, 180000);
      var bRawText = await bRes.text();
      var bData;
      try { bData = JSON.parse(bRawText); } catch(je) { throw new Error('Blind API returned invalid JSON:\n' + bRawText.slice(0,600)); }
      if (!bRes.ok || bData.error) {
        recordPaidAiFailure('Single CV blinding failed', bData, route.model, route.provider);
        throw new Error(normalizeAiProviderError(bData.error || 'Blinding failed: ' + bRes.status, route));
      }
      clearInterval(_fakeInterval2);
      _parsedData = bData.data;
      if (!_parsedData) {
        recordPaidAiFailure('Single CV blinding returned no data', bData, route.model, route.provider);
        throw new Error('Blinding returned no data');
      }
      _runCost += responseCost(bData, route.model, route.provider);
      _runUsage = mergeUsageClient(_runUsage, bData.usage || {});
      document.getElementById('blindBadge').style.display = 'inline-flex';
    }

    renderPreview(_parsedData);
    showToast(blind ? 'Blinded! Generating DOCX…' : 'Parsed! Generating DOCX…', 'ok');

    // ── Step 2/3: Generate DOCX ───────────────────────────────────────────────
    var docxStep = blind ? 3 : (withAutomaticSummary ? 3 : 2);
    setProgress(blind || withAutomaticSummary ? 72 : 55, `Step ${docxStep} — Generating DOCX…`, docxStep, totalSteps);

    var _fake3 = blind || withAutomaticSummary ? 72 : 55;
    var _fakeInterval3 = setInterval(function() {
      if (_fake3 < 92) { _fake3 += (92 - _fake3) * 0.05; document.getElementById('progressFill').style.width = _fake3 + '%'; }
    }, 200);

    var res2 = await fetchWithTimeout('/generate-docx', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({data: _parsedData, alignment: getCvTextAlignment(), summary_box_autofit: getCvSummaryBoxAutoFit(), bullet_levels: cvMergeLevelLists(_extractedBulletLevels, _labelBulletLevels)}) }, 60000);
    if (!res2.ok) {
      var errText2 = await res2.text();
      var errObj; try { errObj = JSON.parse(errText2); } catch(e2) { throw new Error(errText2.slice(0,400)); }
      throw new Error(errObj.error || 'DOCX generation failed');
    }
    var blob = await res2.blob();
    clearInterval(_fakeInterval3);
    window._docxBlob = blob;
    window._originalBlob  = null; // reset — set below if file was uploaded
    window._isBlind  = blind;
    document.getElementById('btnDocx').disabled = false;
    setProgress(100, 'Done! Click Download DOCX ✓', totalSteps + 1, totalSteps);
    stopTimer();
    var elapsed = ((Date.now() - _startTime) / 1000).toFixed(1);
    document.getElementById('progressTimer').textContent = elapsed + 's ✓';
    var pill = document.getElementById('costPill');
    pill.textContent = 'Est. cost: ' + (_runCost < 0.001 ? '<$0.001' : '$' + _runCost.toFixed(4));
    pill.className = 'cost-pill show';
    // Record to stats — URL will be updated after JA upload
    var _cname = (_parsedData && _parsedData.candidate && _parsedData.candidate.name) ? _parsedData.candidate.name : 'Unknown';
    window._lastFormatStatsRecordId = statsRecord(_cname, _isBlind ? 'blind' : 'format', _runCost, route.model, '', route.provider, statsMetaFromResponse({usage:_runUsage,cost:_runCost,model:route.model,provider:route.provider}, route.model, route.provider));
    window._lastJaUrl = '';
    showToast('Done! Click Download DOCX', 'ok');
    markTabDone('format', _tabRun);

    // ── JobAdder: always show email panel, pre-fill from parsed CV ─────
    var jaBar   = document.getElementById('jaBar');
    var jaEmail = document.getElementById('jaEmail');
    jaBar.style.display = 'flex';
    var parsedEmail = (_parsedData && _parsedData.candidate && _parsedData.candidate.email)
      ? _parsedData.candidate.email : '';
    jaEmail.value = parsedEmail;
    jaEmail.placeholder = parsedEmail ? 'Candidate email for JobAdder' : '⚠ No email found — type it here';
    jaEmail.style.borderColor = (!parsedEmail && window._jaToken) ? '#c05621' : '';
    document.getElementById('btnJA').disabled = !window._jaToken || !parsedEmail.trim();
    var jaConnHint = document.getElementById('jaConnHint');
    if (jaConnHint) jaConnHint.style.display = window._jaToken ? 'none' : 'inline';
    // Auto-upload if JA connected, auto-upload enabled, and email found
    if (window._jaToken && window._jaAutoUpload !== false && parsedEmail.trim()) {
      setTimeout(function() { uploadToJobAdder(); }, 500);
    }

  } catch(e) {
    clearInterval(_fakeInterval); clearInterval(_fakeInterval2); clearInterval(_fakeInterval3);
    var errMsg = e.message || String(e);
    // Make "Failed to fetch" human-readable
    if (errMsg.toLowerCase().includes('failed to fetch') || errMsg.toLowerCase().includes('networkerror')) {
      errMsg = 'Cannot reach the local server.\n\nPlease relaunch CV Studio (double-click CV Studio on your Desktop) then refresh this page and try again.\n\nIf the problem persists, check that port 5000 is not blocked by a firewall or another app.';
    }
    setOutput('<div style="color:var(--red);padding:20px;white-space:pre-wrap;font-family:monospace;font-size:12px;">❌ Error: ' + errMsg + '</div>');
    showToast('Error — see output panel', 'err');
    markTabFailed('format', _tabRun);
    hideProgress();
  }

  document.getElementById('btnFormat').disabled = false;
  document.getElementById('btnBlind').disabled  = false;
}

function toTitleCase(str) {
  return (str || '').replace(/\w\S*/g, function(w) {
    return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
  });
}


function cvNormMonth(m) {
  var map = { jan:'Jan', january:'Jan', feb:'Feb', february:'Feb', mar:'Mar', march:'Mar', apr:'Apr', april:'Apr', may:'May', jun:'Jun', june:'Jun', jul:'Jul', july:'Jul', aug:'Aug', august:'Aug', sep:'Sep', sept:'Sep', september:'Sep', oct:'Oct', october:'Oct', nov:'Nov', november:'Nov', dec:'Dec', december:'Dec' };
  return map[String(m || '').toLowerCase().replace(/\.$/, '')] || String(m || '');
}
function cvNormDateRange(value) {
  var text = String(value == null ? '' : value).trim();
  if (!text) return '';
  var loneEndYear = text.match(/^to\s+(\d{4})$/i);
  if (loneEndYear) text = loneEndYear[1];
  else if (/^to$/i.test(text)) return '';
  text = text.replace(/[–—−]/g, '-');
  text = text.replace(/\b(till\s*date|till\s*now|to\s*date|current|presently|now)\b/gi, 'Present');
  text = text.replace(/\bpresent\b/gi, 'Present');
  text = text.replace(/\s*-\s*/g, ' to ');
  text = text.replace(/\s+to\s+/gi, ' to ');
  text = text.replace(/\b(January|February|March|April|June|July|August|September|Sept|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\b/gi, function(m){ return cvNormMonth(m); });
  return text.replace(/\s+/g, ' ').trim();
}
function cvSmartText(value, kind) {
  var text = String(value == null ? '' : value).trim();
  if (!text) return '';
  var letters = text.match(/[A-Za-z]/g) || [];
  var upper = letters.filter(function(ch){ return ch === ch.toUpperCase(); }).length;
  if (!letters.length || upper / letters.length < 0.72) {
    return kind === 'title' ? text.replace(/\bSR\.?\b/g, 'Sr.').replace(/\bJR\.?\b/g, 'Jr.') : text;
  }
  var keep = { AI:1, ML:1, BI:1, IT:1, HR:1, QA:1, UA:1, UX:1, UI:1, PMO:1, PM:1, AWS:1, GCP:1, SQL:1, ETL:1, ELT:1, SSIS:1, SSRS:1, SSAS:1, ADF:1, DBA:1, RDS:1, EMR:1, EC2:1, S3:1, IAM:1, API:1, APAC:1, SEA:1, ERP:1, SAP:1, FICO:1, MSBI:1, MSC:1, IBM:1, CGI:1, EPAM:1, TCS:1, HP:1, HSBC:1, DBS:1, OCBC:1, UOB:1, AIA:1, IHH:1, RHB:1, CIMB:1, EY:1, KPMG:1, PWC:1, BNM:1, AML:1, LLC:1, LLP:1, PLC:1 };
  var corp = { SDN:'Sdn', BHD:'Bhd', PTE:'Pte', LTD:'Ltd', LMT:'Lmt', PVT:'Pvt', INC:'Inc', CORP:'Corp', CO:'Co', COMPANY:'Company', TECH:'Tech' };
  var titleMap = { SR:'Sr', 'SR.':'Sr.', JR:'Jr', 'JR.':'Jr.', VP:'VP', AVP:'AVP' };
  return text.split(/(\s+|\/|\||,|;|\(|\)|\[|\])/g).map(function(part){
    if (!part || /^\s+$/.test(part) || /^(\/|\||,|;|\(|\)|\[|\])$/.test(part)) return part;
    var stripped = part.replace(/[^A-Za-z0-9&.+#]/g, '');
    var up = stripped.toUpperCase();
    var repl = null;
    if (kind === 'company' && corp[up]) repl = corp[up];
    else if (kind === 'title' && titleMap[up]) repl = titleMap[up];
    else if (keep[up] || (up.length <= 3 && up === stripped && /^[A-Z]+$/.test(stripped))) repl = up;
    else return part.toLowerCase().replace(/[A-Za-z]+/g, function(w){ return w.charAt(0).toUpperCase() + w.slice(1); });
    var idx = part.indexOf(stripped);
    return idx >= 0 ? part.slice(0, idx) + repl + part.slice(idx + stripped.length) : repl;
  }).join('').trim();
}

function cvExperienceHeader(exp) {
  var date = cvNormDateRange((exp && exp.date_range) || '');
  var company = cvSmartText((exp && exp.company) || '', 'company');
  if (date && company) return date + ' | ' + company;
  return company || date || '';
}

function cvNormalizeLanguages(value) {
  var text = String(value || '').trim();
  if (!text) return '';
  text = text.replace(/\([^)]*\)/g, ' ')
    .replace(/\b(native|fluent|professional|business|conversational|basic|intermediate|advanced|written|spoken|read|write|speaking|reading|writing|mother tongue|proficient|bilingual|trilingual|multilingual|language|languages)\b/gi, ' ');
  var aliases = [
    ['English', ['english','eng']],
    ['Bahasa Malaysia', ['bahasa malaysia','bahasa melayu','malay language','malay','bm']],
    ['Chinese', ['chinese','mandarin','putonghua','hua yu','huayu','cantonese','yue','hokkien','hakka','teochew','teo chew','foochow','fuzhou','hainanese','shanghainese','min nan','minnan','taiwanese hokkien']],
    ['Tamil', ['tamil']], ['Hindi', ['hindi']], ['Japanese', ['japanese','nihongo']], ['Korean', ['korean']],
    ['Thai', ['thai']], ['Vietnamese', ['vietnamese']], ['Indonesian', ['bahasa indonesia','indonesian']],
    ['Filipino', ['filipino','tagalog']], ['Arabic', ['arabic']], ['French', ['french']], ['German', ['german']],
    ['Spanish', ['spanish']], ['Portuguese', ['portuguese']], ['Italian', ['italian']], ['Dutch', ['dutch']], ['Russian', ['russian']],
    ['Urdu', ['urdu']], ['Bengali', ['bengali','bangla']], ['Punjabi', ['punjabi']], ['Nepali', ['nepali']],
    ['Burmese', ['burmese','myanmar']], ['Khmer', ['khmer','cambodian']], ['Lao', ['lao','laotian']]
  ];
  function hasAlias(part, alias) {
    var escAlias = alias.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+');
    return new RegExp('(^|[^A-Za-z])' + escAlias + '([^A-Za-z]|$)', 'i').test(part);
  }
  function canon(part) {
    var low = String(part || '').toLowerCase().replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim();
    if (!low) return '';
    for (var i=0;i<aliases.length;i++) {
      for (var j=0;j<aliases[i][1].length;j++) if (hasAlias(low, aliases[i][1][j])) return aliases[i][0];
    }
    return low.split(' ').map(function(w){ return w.charAt(0).toUpperCase() + w.slice(1); }).join(' ');
  }
  var out = [];
  text.split(/[,;|/\n]+|\s+(?:and|or|plus|&)\s+/i).forEach(function(part){
    var name = canon(part.replace(/[^A-Za-zÀ-ÖØ-öø-ÿ\s\-]/g, ' '));
    if (name && out.indexOf(name) < 0) out.push(name);
  });
  var order = {'English':0, 'Bahasa Malaysia':1, 'Chinese':2};
  out.sort(function(a,b){
    var ai = Object.prototype.hasOwnProperty.call(order,a) ? order[a] : 99;
    var bi = Object.prototype.hasOwnProperty.call(order,b) ? order[b] : 99;
    return ai === bi ? a.localeCompare(b) : ai - bi;
  });
  return out.join(', ');
}

function cvStripInferredTitle(value) {
  var text = String(value || '').trim();
  return /\s*[\[(]\s*(?:inferred|implied|assumed|guessed|likely)\s+(?:from|based\s+on)\s+(?:responsibilit(?:y|ies)|duties|job\s+content|role\s+content|context)\s*[\])]\s*$/i.test(text) ? '' : text;
}

function cvCanonicalSectionHeading(value) {
  var text = String(value || '').trim();
  var match = text.match(/^(?:key\s+)?(responsibilit(?:y|ies)|achievements?)\s*:?$/i);
  if (!match) return text;
  return /^achievement/i.test(match[1]) ? 'Key achievements' : 'Key responsibilities';
}

function cvStripLeadingBulletMarker(value) {
  var marker = /^\s*(?:[•●▪◦‣∙·▶►➤⁃»›]|\((?:[ivxlcdmIVXLCDM]{1,7}|[a-zA-Z]|\d{1,3})\)|\d{1,3}[.)](?=\s|[^\W\d_])|\d{1,3}-(?=\s)|(?:[a-z]|[ivxlcdm]{2,7})[.)-](?=\s)|[*‐-―-](?=\s|[^\W\d_]))\s*/;
  var text = String(value == null ? '' : value);
  for (var i = 0; i < 5; i++) {
    var stripped = text.replace(marker, '');
    if (stripped === text) break;
    text = stripped;
  }
  return text;
}

function cvStripAdditionalBulletMarkers(items, alwaysBulleted) {
  var structured = Array.isArray(items);
  var values = structured ? items : String(items || '').split(/(?:\r?\n)+/);
  var nonempty = values.filter(function(value){ return String(value || '').trim(); });
  if (!alwaysBulleted && nonempty.length <= 1) return items;
  var cleaned = nonempty.map(function(value){
    return cvStripLeadingBulletMarker(value).trim();
  }).filter(Boolean);
  return structured ? cleaned : cleaned.join('\n');
}

function cvNormalizeBulletItems(items, allowStandaloneSections) {
  allowStandaloneSections = allowStandaloneSections !== false;
  var source = Array.isArray(items) ? items : ((items == null || items === '') ? [] : [items]);
  var out = [];
  function add(item) {
    if (typeof item === 'string') {
      var candidate = cvStripLeadingBulletMarker(item).trim();
      if (allowStandaloneSections && /^(?:key\s+)?(?:responsibilit(?:y|ies)|achievements?)\s*:?$/i.test(candidate)) {
        out.push({ heading: cvCanonicalSectionHeading(candidate), bullets: [], kind: 'section' });
        return;
      }
      if (candidate && ((candidate[0] === '{' && candidate[candidate.length - 1] === '}') || (candidate[0] === '[' && candidate[candidate.length - 1] === ']'))) {
        try {
          var decoded = JSON.parse(candidate);
          if (decoded && typeof decoded === 'object') {
            var before = out.length;
            add(decoded);
            if (out.length === before) out.push(item);
            return;
          }
        } catch(e) {}
      }
      if (candidate) out.push(candidate);
      return;
    }
    if (Array.isArray(item)) { item.forEach(add); return; }
    if (!item || typeof item !== 'object') {
      if (item != null && String(item).trim()) out.push(String(item));
      return;
    }
    var rawHeading = item.heading || item.title || '';
    var heading = cvCanonicalSectionHeading(rawHeading);
    var bullets = cvNormalizeBulletItems(item.bullets || item.items || [], false);
    if (heading) {
      var group = { heading: heading, bullets: bullets };
      if (item.kind) group.kind = String(item.kind);
      else if (/^(?:key\s+)?(?:responsibilit(?:y|ies)|achievements?)\s*:?$/i.test(String(rawHeading).trim())) group.kind = 'section';
      out.push(group);
    } else {
      bullets.forEach(add);
    }
  }
  source.forEach(add);
  return out;
}

function cvNormalizeStructuredData(data) {
  if (!data || typeof data !== 'object') return data;
  var candidate = data.candidate || {};
  candidate.current_position = cvStripInferredTitle(candidate.current_position);
  data.candidate = candidate;
  (data.work_experiences || []).forEach(function(exp) {
    (Array.isArray(exp && exp.roles) ? exp.roles : []).forEach(function(role) {
      if (!role || typeof role !== 'object') return;
      role.title = cvStripInferredTitle(role.title);
      role.bullets = cvNormalizeBulletItems(role.bullets);
    });
  });
  var certifications = Array.isArray(data.certifications) ? data.certifications : (data.certifications ? [data.certifications] : []);
  data.certifications = cvStripAdditionalBulletMarkers(certifications, true);
  var skills = Array.isArray(data.skills) ? data.skills : [];
  data.skills = skills.filter(function(value){
    return value && typeof value === 'object' && (String(value.category || '').trim() || String(value.items || '').trim());
  }).map(function(value){
    value.items = cvStripAdditionalBulletMarkers(value.items || '', false);
    return value;
  });
  return data;
}

function cvSkillPreviewHtml(skill) {
  skill = skill && typeof skill === 'object' ? skill : {};
  var category = String(skill.category || '').trim();
  var rawItems = skill.items || '';
  var lines = Array.isArray(rawItems)
    ? rawItems.map(function(value){ return String(value || '').trim(); }).filter(Boolean)
    : String(rawItems).split(/\r?\n/).map(function(value){ return value.trim(); }).filter(Boolean);
  if (lines.length > 1) {
    lines = lines.map(function(value){ return cvStripLeadingBulletMarker(value).trim(); }).filter(Boolean);
  }
  if (!category && !lines.length) return '';

  var showCategory = category && !/^skills?$/i.test(category);
  if (lines.length > 1) {
    var listHtml = showCategory
      ? '<div class="preview-skill-cat"><strong>' + esc(category) + ':</strong></div>'
      : '';
    lines.forEach(function(line){
      listHtml += '<div class="preview-bullet">' + esc(line) + '</div>';
    });
    return listHtml;
  }

  var item = lines.length ? lines[0] : '';
  if (!showCategory) return '<div class="preview-skill-cat">' + esc(item) + '</div>';
  return '<div class="preview-skill-cat"><strong>' + esc(category) + ':</strong>' + (item ? ' ' + esc(item) : '') + '</div>';
}

function renderPreview(d) {
  d = cvNormalizeStructuredData(d);
  var c = d.candidate || {};
  var isEmployed = c.is_employed !== false;
  var posLabel = isEmployed ? 'CURRENT POSITION' : 'LAST POSITION';
  var compLabel = isEmployed ? 'CURRENT COMPANY' : 'LAST COMPANY';
  var html = '';

  // About table
  html += '<div class="preview-name">' + esc(toTitleCase(c.name)) + '</div>';
  html += '<table class="preview-table">';
  html += '<tr><td colspan="2"><span class="preview-label">NOTICE PERIOD</span>' + esc(c.notice_period) + '</td></tr>';
  html += '<tr><td><span class="preview-label">' + posLabel + '</span>' + esc(cvSmartText(c.current_position, 'title')) + '</td><td><span class="preview-label">' + compLabel + '</span>' + esc(cvSmartText(c.current_company, 'company')) + '</td></tr>';
  html += '<tr><td colspan="2"><span class="preview-label">LANGUAGES</span>' + esc(cvNormalizeLanguages(c.languages)) + '</td></tr>';
  html += '</table>';

  // Summary placeholder (filled only when explicitly requested)
  html += '<div class="preview-section">SUMMARY</div>';
  var summaryBullets = Array.isArray(d.summary_bullets) ? d.summary_bullets.map(function(value){ return String(value || '').trim(); }).filter(Boolean) : [];
  if (summaryBullets.length) {
    summaryBullets.forEach(function(value){ html += '<div class="preview-bullet">' + boldSafeSummary(value) + '</div>'; });
  } else {
    html += '<div style="color:var(--text3);font-style:italic;font-size:11px;">(left blank)</div>';
  }

  // Work experience
  html += '<div class="preview-section">W O R K &nbsp; E X P E R I E N C E S</div>';
  for (var exp of (d.work_experiences || [])) {
    var roles = Array.isArray(exp.roles) ? exp.roles : [];
    for (var ri = 0; ri < roles.length; ri++) {
      var role = roles[ri];
      if (ri === 0) html += '<div class="preview-company">' + esc(cvExperienceHeader(exp)) + '</div>';
      var plainRoleTitle = cvSmartText(role.title, 'title');
      var rtitle = plainRoleTitle && roles.length > 1 && role.date_range ? plainRoleTitle + ' (' + cvNormDateRange(role.date_range) + ')' : plainRoleTitle;
      if (String(rtitle || '').trim()) html += '<div class="preview-role">' + esc(rtitle) + '</div>';
      if (role.reason_for_leaving) html += '<div class="preview-reason">Reason for Leaving: ' + esc(role.reason_for_leaving) + '</div>';
      for (var b of (role.bullets || [])) {
        if (typeof b === 'object' && b.heading) {
          html += '<div class="preview-role" style="margin-top:4px">' + esc(b.heading) + '</div>';
          for (var sb of (b.bullets || [])) html += cvBulletPreviewHtml(sb);
        } else {
          html += cvBulletPreviewHtml(b);
        }
      }
    }
  }

  // Education
  html += '<div class="preview-section">E D U C A T I O N</div>';
  for (var edu of (d.education || [])) {
    var eduDate = cvNormDateRange(edu.date_range || '');
    var eduInst = String(edu.institution || '').trim();
    var eduTop = eduDate && eduInst ? (eduDate + ' | ' + eduInst) : (eduInst || eduDate);
    if (eduTop) html += '<div class="preview-edu-date">' + esc(eduTop) + '</div>';
    if (edu.degree && String(edu.degree).trim()) html += '<div class="preview-deg">' + esc(String(edu.degree).trim()) + '</div>';
    var eduCgpa = edu.cgpa || edu.gpa || '';
    var eduHonors = edu.honors || edu.honours || edu.awards || edu.distinctions || '';
    var eduDesc = edu.description || edu.thesis || edu.dissertation || edu.project || '';
    if (eduCgpa && String(eduCgpa).trim()) {
      html += '<div class="preview-deg">' + esc(String(eduCgpa).trim()) + '</div>';
    }
    if (eduHonors && String(eduHonors).trim()) {
      html += '<div class="preview-deg">' + esc(String(eduHonors).trim()) + '</div>';
    }
    if (eduDesc && String(eduDesc).trim()) {
      html += '<div class="preview-deg" style="font-style:italic;">' + esc(String(eduDesc).trim()) + '</div>';
    }
  }

  // Certs
  if ((d.certifications || []).length > 0) {
    html += '<div class="preview-section">CERTIFICATIONS</div>';
    for (var cert of d.certifications) html += '<div class="preview-bullet">' + esc(cert) + '</div>';
  }

  // Skills
  if ((d.skills || []).length > 0) {
    html += '<div class="preview-section">SKILLS</div>';
    for (var s of d.skills) {
      html += cvSkillPreviewHtml(s);
    }
  }

  setOutput(html);
}

function setOutput(html) {
  var ob = document.getElementById('outputBox');
  ob.className = 'output-box';
  ob.innerHTML = html;
}

function esc(s) {
  var str = (s == null) ? '' : (typeof s === 'object' ? (Array.isArray(s) ? s.join(', ') : JSON.stringify(s)) : String(s));
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function downloadDocx() {
  if (!window._docxBlob) { showToast('Format a CV first', 'err'); return; }
  var a = document.createElement('a');
  a.href = URL.createObjectURL(window._docxBlob);
  var name;
  if (window._isBlind) {
    var realName = window._realCandidateName || (_parsedData && _parsedData.candidate && _parsedData.candidate.name) || '';
    name = realName
      ? 'Hyppies CV - ' + toTitleCase(realName) + ' (Blinded).docx'
      : 'Hyppies CV - Blinded - ' + new Date().toISOString().slice(0,16).replace('T','_').replace(':','h') + 'm.docx';
  } else {
    name = (_parsedData && _parsedData.candidate && _parsedData.candidate.name)
      ? 'Hyppies CV - ' + toTitleCase(_parsedData.candidate.name) + '.docx'
      : 'Hyppies CV - Formatted.docx';
  }
  a.download = name;
  a.click();
  setTimeout(function(){ URL.revokeObjectURL(a.href); }, 1000);
}

function clearInput() {
  clearTabRunState('format');
  clearFormatSummaryDraft();
  // Clear text input
  document.getElementById('cvInput').value = '';
  document.getElementById('charCount').textContent = '0 characters';
  // Clear uploaded file
  _extractedText = '';
  _parsedData = null;
  _cname = '';
  window._docxBlob = null;
  window._originalFile = null;
  window._lastJaUrl = '';
  var dz = document.getElementById('dropZone');
  dz.classList.remove('has-file','error');
  document.getElementById('dzFileName').textContent = '';
  document.getElementById('dzClear').style.display = 'none';
  document.getElementById('fileCharCount').style.display = 'none';
  document.getElementById('fileInput').value = '';
  // Clear preview and JA bar
  var ob = document.getElementById('outputBox');
  if (ob) { ob.className = 'output-box empty'; ob.innerHTML = ''; }
  document.getElementById('jaBar').style.display = 'none';
  document.getElementById('jaStatus').textContent = '';
  document.getElementById('jaEmail').value = '';
  // Reset progress
  document.getElementById('progressWrap').classList.remove('on');
  var stepText = document.getElementById('stepText');
  if (stepText) stepText.textContent = '';
  var btnDocx = document.getElementById('btnDocx');
  if (btnDocx) btnDocx.disabled = true;
}

document.getElementById('cvInput').addEventListener('input', function() {
  clearFormatSummaryDraft();
  document.getElementById('charCount').textContent = this.value.length.toLocaleString() + ' characters';
});
document.getElementById('cvInput').addEventListener('paste', function() {
  setTimeout(function() {
    var v = document.getElementById('cvInput').value;
    document.getElementById('charCount').textContent = v.length.toLocaleString() + ' characters';
  }, 0);
});
