// ── Blind JD Tab ─────────────────────────────────────────────────
var _anonTone = 'professional';
var _anonParaphraseLevel = 'medium';
var _anonPreviewMode = 'visual';
var _anonVisualPreview = null;
var _anonPreviewZoom = 1;

function anonEscapeHtml(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function anonNormalizeExtractedTextArtifacts(s) {
  var t = String(s || '');
  if (!t) return t;
  var unicodeMap = {
    '\u019f':'ti', '\u014c':'ft', '\u019e':'tf', '\u01a9':'tt', '\u01ab':'tti',
    '\uf0b7':'•', '\ufffe':'-'
  };
  Object.keys(unicodeMap).forEach(function(k){ t = t.split(k).join(unicodeMap[k]); });
  var cidMap = {'332':'ft','414':'tf','415':'ti','425':'tt','427':'tti'};
  t = t.replace(/\(?cid:(\d+)\)?/gi, function(_, c){ return cidMap[c] || ' '; });
  var fixes = [
    [/\bAccoun\s+ng\b/g,'Accounting'], [/\baccoun\s+ng\b/g,'accounting'],
    [/\bLoca\s+on\b/g,'Location'], [/\bloca\s+on\b/g,'location'],
    [/\bFull\s+me\b/g,'Full time'], [/\bfull\s+me\b/g,'full time'],
    [/\bso\s+ware\b/g,'software'], [/\bSo\s+ware\b/g,'Software'],
    [/\bpla\s+orm\b/g,'platform'], [/\bPla\s+orm\b/g,'Platform'],
    [/\bwri\s+en\b/g,'written'], [/\bWri\s+en\b/g,'Written'],
    [/\bCommi\s+ed\b/g,'Committed'], [/\bcommi\s+ed\b/g,'committed'],
    [/\ba\s+tude\b/g,'attitude'], [/\bA\s+tude\b/g,'Attitude'],
    [/\bcri\s+cal\b/g,'critical'], [/\bCri\s+cal\b/g,'Critical'],
    [/\bpoten\s+al\b/g,'potential'], [/\bPoten\s+al\b/g,'Potential'],
    [/\bop\s+mize\b/g,'optimize'], [/\bOp\s+mize\b/g,'Optimize'],
    [/\bcollec\s+on\b/g,'collection'], [/\bCollec\s+on\b/g,'Collection'],
    [/\bsolu\s+ons\b/g,'solutions'], [/\bSolu\s+ons\b/g,'Solutions'],
    [/\bsolu\s+on\b/g,'solution'], [/\bSolu\s+on\b/g,'Solution'],
    [/\bopera\s+ons\b/g,'operations'], [/\bOpera\s+ons\b/g,'Operations'],
    [/\bopera\s+on\b/g,'operation'], [/\bOpera\s+on\b/g,'Operation'],
    [/\bini\s+a\s+ves\b/g,'initiatives'], [/\bIni\s+a\s+ves\b/g,'Initiatives'],
    [/\biden\s+fy\b/g,'identify'], [/\bIden\s+fy\b/g,'Identify'],
    [/\beffec\s+vely\b/g,'effectively'], [/\bEffec\s+vely\b/g,'Effectively'],
    [/\bCollabora\s+ve\b/g,'Collaborative'], [/\bcollabora\s+ve\b/g,'collaborative'],
    [/\bac\s+vely\b/g,'actively'], [/\bAc\s+vely\b/g,'Actively'],
    [/\bconstruc\s+ve\b/g,'constructive'], [/\bConstruc\s+ve\b/g,'Constructive'],
    [/\bcon\s+nuous\b/g,'continuous'], [/\bCon\s+nuous\b/g,'Continuous'],
    [/\bsuppor\s+ve\b/g,'supportive'], [/\bSuppor\s+ve\b/g,'Supportive'],
    [/\bmo\s+vates\b/g,'motivates'], [/\bMo\s+vates\b/g,'Motivates'],
    [/\bCoordina\s+on\b/g,'Coordination'], [/\bcoordina\s+on\b/g,'coordination'],
    [/\bme\s+culous\b/g,'meticulous'], [/\bMe\s+culous\b/g,'Meticulous'],
    [/\bproac\s+ve\b/g,'proactive'], [/\bProac\s+ve\b/g,'Proactive'],
    [/\bmul\s+ple\b/g,'multiple'], [/\bMul\s+ple\b/g,'Multiple'],
    [/\bpriori\s+es\b/g,'priorities'], [/\bPriori\s+es\b/g,'Priorities'],
    [/\bshi\s+ing\b/g,'shifting'], [/\bShi\s+ing\b/g,'Shifting'],
    [/\bnight\s+shi\s+\b/g,'night shift '], [/\bNight\s+shi\s+\b/g,'Night shift '],
    [/\bcke\s+ng\b/g,'ticketing'], [/\bCke\s+ng\b/g,'Ticketing'],
    [/\bma\s+ers\b/g,'matters'], [/\bMa\s+ers\b/g,'Matters'],
    [/\bsa\s+sfac\s+on\b/g,'satisfaction'], [/\bSa\s+sfac\s+on\b/g,'Satisfaction']
  ];
  fixes.forEach(function(f){ t = t.replace(f[0], f[1]); });
  return t.replace(/[ \t]{2,}/g, ' ').replace(/ *\n */g, '\n').replace(/\n{3,}/g, '\n\n').trim();
}
function anonRawTextChanged() {
  _anonVisualPreview = null;
  if (_anonPreviewMode === 'visual') setAnonPreviewMode('text');
  var ta = document.getElementById('anonRawText');
  var raw = ta ? ta.value : '';
  var cc = document.getElementById('anonCharCount');
  if (cc) cc.textContent = raw.length.toLocaleString() + ' chars';
  updateAnonOriginalPreview();
}
function anonSetPreviewButtonState() {
  var v = document.getElementById('anonPreviewModeVisual');
  var t = document.getElementById('anonPreviewModeText');
  [v, t].forEach(function(b){ if (b) { b.style.background=''; b.style.color=''; b.style.borderColor=''; } });
  var active = _anonPreviewMode === 'text' ? t : v;
  if (active) { active.style.background='var(--blue)'; active.style.color='#fff'; active.style.borderColor='var(--blue)'; }
  anonPreviewZoomLabelUpdate();
}

function setAnonPreviewMode(mode) {
  _anonPreviewMode = (mode === 'text') ? 'text' : 'visual';
  anonSetPreviewButtonState();
  updateAnonOriginalPreview();
}

function anonPreviewZoomLabelUpdate() {
  var lab = document.getElementById('anonPreviewZoomLabel');
  if (lab) lab.textContent = Math.round((_anonPreviewZoom || 1) * 100) + '%';
}

function setAnonPreviewZoom(z) {
  var n = Number(z);
  if (!isFinite(n)) n = 1;
  _anonPreviewZoom = Math.max(0.6, Math.min(2.0, Math.round(n * 10) / 10));
  anonPreviewZoomLabelUpdate();
  updateAnonOriginalPreview();
}

function anonPreviewZoomIn() { setAnonPreviewZoom((_anonPreviewZoom || 1) + 0.1); }
function anonPreviewZoomOut() { setAnonPreviewZoom((_anonPreviewZoom || 1) - 0.1); }

function anonPreviewZoomWrap(innerHtml) {
  var z = _anonPreviewZoom || 1;
  if (Math.abs(z - 1) < 0.001) return innerHtml;
  var w = (100 / z).toFixed(3) + '%';
  return '<div style="transform:scale(' + z + ');transform-origin:top left;width:' + w + ';">' + innerHtml + '</div>';
}

function anonEscapeAttr(s) {
  return anonEscapeHtml(s).replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function anonSafeVisualDataUrl(value, mode) {
  var url = String(value || '').trim();
  if (!url || /["'<>\u0000-\u001f\u007f]/.test(url)) return '';
  if (mode === 'pdf' && !/^data:application\/pdf;base64,/i.test(url)) return '';
  if (mode === 'image' && !/^data:image\/(?:png|jpe?g);base64,/i.test(url)) return '';
  return url;
}


function anonRenderVisualPreview(box, raw) {
  if (!box) return false;
  var pv = _anonVisualPreview || null;
  if (!pv || !pv.ok) return false;
  var note = anonEscapeHtml(pv.note || '');
  var safePdfUrl = anonSafeVisualDataUrl(pv.data_url, 'pdf');
  var safeImageUrl = anonSafeVisualDataUrl(pv.data_url, 'image');
  if (pv.mode === 'pdf' && safePdfUrl) {
    box.style.color = 'var(--text2)';
    box.style.whiteSpace = 'normal';
    box.style.padding = '0';
    box.style.fontSize = '12px';
    var pdfFrame = '<iframe title="Original JD visual PDF preview" src="' + anonEscapeAttr(safePdfUrl + '#toolbar=0&navpanes=0') + '" style="width:100%;height:72vh;min-height:520px;border:0;border-radius:8px;background:#fff;"></iframe>';
    box.innerHTML = anonPreviewZoomWrap(pdfFrame) + (note ? '<div style="font-size:10px;color:var(--text3);padding:8px 12px;border-top:1px solid var(--border);">' + note + '</div>' : '');
    return true;
  }
  if (pv.mode === 'image' && safeImageUrl) {
    box.style.color = 'var(--text2)';
    box.style.whiteSpace = 'normal';
    box.style.padding = '10px';
    box.style.fontSize = '12px';
    var imgView = '<div style="text-align:center;background:#fff;border-radius:6px;padding:8px;"><img alt="Original JD visual preview" src="' + anonEscapeAttr(safeImageUrl) + '" style="max-width:100%;height:auto;box-shadow:0 1px 8px rgba(0,0,0,.12);"/></div>';
    box.innerHTML = anonPreviewZoomWrap(imgView) + (note ? '<div style="font-size:10px;color:var(--text3);margin-top:8px;">' + note + '</div>' : '');
    return true;
  }
  if (pv.mode === 'html' && pv.html) {
    box.style.color = 'var(--text2)';
    box.style.whiteSpace = 'normal';
    box.style.padding = '12px';
    box.style.fontSize = '12px';
    var htmlView = '<div style="background:#fff;color:#111;border-radius:6px;padding:20px;box-shadow:0 1px 8px rgba(0,0,0,.08);font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.45;">' + pv.html + '</div>';
    box.innerHTML = anonPreviewZoomWrap(htmlView) + (note ? '<div style="font-size:10px;color:var(--text3);margin-top:8px;">' + note + '</div>' : '');
    return true;
  }
  return false;
}

function updateAnonOriginalPreview() {
  var ta = document.getElementById('anonRawText');
  var raw = ta ? anonNormalizeExtractedTextArtifacts(ta.value) : '';
  var box = document.getElementById('anonOriginalPreview');
  var count = document.getElementById('anonOriginalPreviewCount');
  if (count) count.textContent = raw.length.toLocaleString() + ' chars';
  if (!box) return;
  if (!raw.trim() && (!_anonVisualPreview || !_anonVisualPreview.ok)) {
    box.style.color = 'var(--text3)';
    box.style.whiteSpace = 'pre-wrap';
    box.style.padding = '14px';
    box.style.fontSize = (12 * (_anonPreviewZoom || 1)) + 'px';
    box.textContent = '';
    return;
  }
  if (_anonPreviewMode !== 'text' && anonRenderVisualPreview(box, raw)) return;
  box.style.color = 'var(--text2)';
  box.style.whiteSpace = 'pre-wrap';
  box.style.padding = '14px';
  box.style.fontSize = (12 * (_anonPreviewZoom || 1)) + 'px';
  box.innerHTML = anonEscapeHtml((raw || '').trim() || 'No extractable text found. Use Visual mode to review the uploaded file layout.');
}

async function loadAnonVisualPreview(file) {
  _anonVisualPreview = null;
  updateAnonOriginalPreview();
  if (!file) return;
  var fd = new FormData();
  fd.append('file', file);
  try {
    var r = await fetchWithTimeout('/preview-file', { method: 'POST', body: fd }, 90000);
    var d = await r.json();
    if (d && d.ok) _anonVisualPreview = d;
    else _anonVisualPreview = { ok:false, note:(d && d.error) || 'Visual preview unavailable; using cleaned text preview.' };
  } catch(e) {
    _anonVisualPreview = { ok:false, note:'Visual preview unavailable; using cleaned text preview.' };
  }
  updateAnonOriginalPreview();
}

function setAnonTone(btn) {
  document.querySelectorAll('[data-tone]').forEach(function(b) {
    b.style.background=''; b.style.color=''; b.style.borderColor='';
  });
  btn.style.background='var(--blue)'; btn.style.color='#fff'; btn.style.borderColor='var(--blue)';
  _anonTone = btn.dataset.tone;
}

function setAnonParaphraseLevel(btn) {
  if (!btn) return;
  document.querySelectorAll('[data-paraphrase]').forEach(function(b) {
    b.style.background=''; b.style.color=''; b.style.borderColor='';
  });
  btn.style.background='var(--blue)'; btn.style.color='#fff'; btn.style.borderColor='var(--blue)';
  _anonParaphraseLevel = btn.dataset.paraphrase || 'medium';
}

function jdAnonParaphraseStrengthInstruction(level) {
  level = String(level || 'medium').toLowerCase();
  if (level === 'low') {
    return 'PARAPHRASE STRENGTH: LOW. Use a light rewrite: preserve the original responsibility/requirement intent and approximate section structure, but change identifying wording, sentence phrasing, verbs, and repeated prose enough that it is not copied verbatim. Keep tech stack, tools, platforms, certifications, methodologies, years of experience, locations/work mode, and must-have requirements exact.';
  }
  if (level === 'high') {
    return 'PARAPHRASE STRENGTH: HIGH. Use a strong rewrite: substantially reword and polish the JD into fresh candidate-facing language. You may merge, split, or reorder bullets for readability, but do not remove or weaken any responsibilities, requirements, tech stack, tools, platforms, certifications, methodologies, years of experience, location/work mode, or candidate-critical requirements. Avoid source sentence patterns and long copied phrases.';
  }
  return 'PARAPHRASE STRENGTH: MEDIUM. Use a balanced rewrite: change sentence structure, verbs, and phrasing while preserving all responsibilities, requirements, seniority, business context, tech stack, tools, platforms, certifications, methodologies, years of experience, location/work mode, and candidate-critical requirements.';
}

function setAnonWorkMode(btn) {
  document.querySelectorAll('[data-wm]').forEach(function(b) {
    b.style.background=''; b.style.color=''; b.style.borderColor='';
  });
  btn.style.background='var(--blue)'; btn.style.color='#fff'; btn.style.borderColor='var(--blue)';
  document.getElementById('anonWorkMode').value = btn.dataset.wm;
}

function setAnonLocation(btn) {
  document.querySelectorAll('[data-loc]').forEach(function(b) {
    b.style.background=''; b.style.color=''; b.style.borderColor='';
  });
  btn.style.background='var(--blue)'; btn.style.color='#fff'; btn.style.borderColor='var(--blue)';
  var isOthers = btn.dataset.loc === '__others__';
  document.getElementById('anonLocationOthers').style.display = isOthers ? 'block' : 'none';
  if (!isOthers) {
    document.getElementById('anonLocation').value = btn.dataset.loc;
    document.getElementById('anonLocationCustom') && (document.getElementById('anonLocationCustom').value = '');
  }
}

async function handleAnonFile(file) {
  if (!file) return;
  var nameEl = document.getElementById('anonFileName');
  var zone   = document.getElementById('anonDropZone');
  nameEl.textContent = '⏳ Extracting…';
  zone.style.opacity = '0.6';
  _anonPreviewMode = 'visual';
  anonSetPreviewButtonState();
  _anonVisualPreview = null;
  updateAnonOriginalPreview();
  var _tabRun = markTabRunning('jdanon');
  try {
    var visualPromise = loadAnonVisualPreview(file);
    if (visualPromise && typeof visualPromise.catch === 'function') visualPromise.catch(function(){});
    var fd = new FormData(); fd.append('file', file);
    var r  = await fetchWithTimeout('/extract-text', { method: 'POST', body: fd }, CV_EXTRACT_TEXT_TIMEOUT_MS);
    var d  = await r.json();
    if (d.error) throw new Error(d.error);
    var extractionWarning = cvShowExtractionWarning(d);
    var text = anonNormalizeExtractedTextArtifacts(d.text || '').trim();
    document.getElementById('anonRawText').value = text;
    document.getElementById('anonCharCount').textContent = text.length.toLocaleString() + ' chars';
    updateAnonOriginalPreview();
    // Do not block text extraction completion on visual preview conversion.
    // Office visual conversion can be slower/unavailable; it updates the left preview asynchronously.
    nameEl.textContent = (extractionWarning ? '⚠ ' : '✓ ') + file.name + ' (' + text.length.toLocaleString() + ' chars)' + (extractionWarning ? ' — partial extraction; review text' : '');
    markTabDone('jdanon', _tabRun);
  } catch(e) {
    nameEl.textContent = '✕ Failed: ' + e.message;
    markTabFailed('jdanon', _tabRun);
    showToast('Extraction failed: ' + e.message, 'err');
  } finally {
    zone.style.opacity = '';
  }
}

function handleAnonDrop(e) {
  e.preventDefault();
  document.getElementById('anonDropZone').style.borderColor = 'var(--border)';
  var file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
  if (file) handleAnonFile(file);
}

function clearAnonJD() {
  clearTabRunState('jdanon');
  document.getElementById('anonRawText').value = '';
  document.getElementById('anonCharCount').textContent = '0 chars';
  _anonVisualPreview = null;
  _anonPreviewMode = 'visual';
  anonSetPreviewButtonState();
  updateAnonOriginalPreview();
  document.getElementById('anonFileName').textContent = '';
  document.getElementById('anonClientDesc').value = '';
  document.getElementById('anonCompanyName').value = '';
  document.getElementById('anonIndustry').value = '';
  document.getElementById('anonWorkMode').value = '';
  document.getElementById('anonLocation').value = '';
  document.getElementById('anonContext').value = '';
  document.getElementById('anonRedact').value = '';
  document.getElementById('anonWhyJoinUs').value = '';
  document.getElementById('anonJDOutput').style.display = 'none';
  var phAnonClear = document.getElementById('anonJDPlaceholder'); if (phAnonClear) phAnonClear.style.display = 'flex';
  document.getElementById('anonJDStatus').textContent = '';
  document.getElementById('anonJDTitle').textContent = 'Blind JD';
  var anonCost = document.getElementById('anonJDCost'); if (anonCost) anonCost.textContent = '';
  var anonFileInput = document.getElementById('anonFileInput'); if (anonFileInput) anonFileInput.value = '';
  window._lastAnonJD = null;
  // Reset all toggle buttons to unselected state
  document.querySelectorAll('#viewJDAnon [data-wm], #viewJDAnon [data-loc], #viewJDAnon [data-tone], #viewJDAnon [data-paraphrase]').forEach(function(b) {
    b.style.background = ''; b.style.color = ''; b.style.borderColor = '';
  });
  document.getElementById('anonLocationOthers').style.display = 'none';
  // Re-apply default tone (Professional)
  var defTone = document.getElementById('anonToneBtn_professional');
  if (defTone) { defTone.style.background='var(--blue)'; defTone.style.color='#fff'; defTone.style.borderColor='var(--blue)'; }
  _anonTone = 'professional';
  var defPara = document.getElementById('anonParaBtn_medium');
  if (defPara) { defPara.style.background='var(--blue)'; defPara.style.color='#fff'; defPara.style.borderColor='var(--blue)'; }
  _anonParaphraseLevel = 'medium';
}

function copyAnonJD() {
  var el = document.getElementById('anonJDBody');
  if (!el || !el.innerText.trim()) { showToast('Generate Blind JD first', 'err'); return; }
  navigator.clipboard.writeText(el.innerText).then(function() {
    showToast('Blind JD copied!', 'ok');
  }).catch(function() {
    showToast('Copy failed', 'err');
  });
}


function jdAnonNormalizeOverlapText(s) {
  return String(s || '')
    .toLowerCase()
    .replace(/[`~!@#$%^&()_=+\[\]{};:'",.<>/?\\|]/g, ' ')
    .replace(/[\u2010-\u2015-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function jdAnonIsMostlyProtectedTechPhrase(phrase) {
  var words = jdAnonNormalizeOverlapText(phrase).split(' ').filter(Boolean);
  if (words.length < 5) return false;
  var corpus = ' ' + words.join(' ') + ' ';
  var hitWords = Object.create(null);
  var terms = [];
  try { if (Array.isArray(JD_ANON_TECH_PRESERVE_TERMS)) terms = terms.concat(JD_ANON_TECH_PRESERVE_TERMS); } catch(e) {}
  terms = terms.concat(['uat','cab','ecab','itil','itsm','cmdb','rca','sla','sql','pl/sql','t-sql','iso 20000','iso 27001','aws','azure','gcp','sap','oracle','servicenow']);
  terms.forEach(function(term) {
    var norm = jdAnonNormalizeTerm ? jdAnonNormalizeTerm(term) : jdAnonNormalizeOverlapText(term);
    if (!norm) return;
    var parts = norm.split(' ').filter(Boolean);
    if (!parts.length) return;
    if (corpus.indexOf(' ' + norm + ' ') >= 0) {
      parts.forEach(function(w) {
        if (w.length >= 2 && !/^(and|or|the|with|for|in|on|of|to)$/.test(w)) hitWords[w] = true;
      });
    }
  });
  var hits = words.filter(function(w){ return !!hitWords[w]; }).length;
  // Avoid retry/warning loops caused only by preserved tech-stack/acronym lists.
  return hits >= 4 && (hits / words.length) >= 0.5;
}

function jdAnonHasLongVerbatimOverlap(line, sourceText) {
  var normalizedLine = jdAnonNormalizeOverlapText(line);
  var normalizedSource = sourceText && sourceText._jdAnonNorm ? sourceText._jdAnonNorm : jdAnonNormalizeOverlapText(sourceText || '');
  var words = normalizedLine.split(' ').filter(Boolean);
  if (words.length < 8 || !normalizedSource) return false;
  var protectedShortPhrases = [
    'user acceptance testing', 'service level agreement', 'subject matter expert',
    'business requirements gathering', 'change management', 'configuration management',
    'incident management', 'problem management', 'project management'
  ];
  for (var n = Math.min(11, words.length); n >= 8; n--) {
    for (var i = 0; i <= words.length - n; i++) {
      var phrase = words.slice(i, i + n).join(' ');
      if (protectedShortPhrases.indexOf(phrase) >= 0) continue;
      if (jdAnonIsMostlyProtectedTechPhrase(phrase)) continue;
      if (normalizedSource.indexOf(phrase) >= 0) return true;
    }
  }
  return false;
}

function jdAnonFindParaphraseIssues(jd, raw) {
  var issues = [];
  var normSource = jdAnonNormalizeOverlapText(raw || '');
  var sourceBox = { _jdAnonNorm: normSource };
  function arr(v) { return Array.isArray(v) ? v : (v ? [String(v)] : []); }
  ['about_client','about_role'].forEach(function(field) {
    var val = jd && jd[field];
    if (val && jdAnonHasLongVerbatimOverlap(val, sourceBox)) issues.push(field);
  });
  ['responsibilities','requirements','nice_to_have','why_join'].forEach(function(field) {
    arr(jd && jd[field]).forEach(function(line) {
      if (jdAnonHasLongVerbatimOverlap(line, sourceBox)) issues.push(field);
    });
  });
  return issues;
}

function jdAnonNormalizeTerm(s) {
  return String(s || '')
    .toLowerCase()
    .replace(/\.net/g, 'dotnet')
    .replace(/node\.?js/g, 'nodejs')
    .replace(/c#/g, 'csharp')
    .replace(/\s+/g, ' ')
    .trim();
}

var JD_ANON_TECH_PRESERVE_TERMS = [
  'ServiceNow','ITSM','CMDB','ITIL','CAB','ECAB','UAT','RCA','SLA','ISO 20000','ISO 27001',
  'AWS','Amazon Web Services','Azure','Microsoft Azure','GCP','Google Cloud','Google Cloud Platform','Alibaba Cloud',
  'Kubernetes','K8s','Docker','Terraform','Ansible','Jenkins','GitHub Actions','GitLab CI','ArgoCD','Helm','Istio',
  'Linux','Unix','Windows Server','Active Directory','Azure AD','Entra ID','PowerShell','Bash','Shell Scripting',
  'Python','Java','JavaScript','TypeScript','Node.js','React','Angular','Vue','C#','.NET','ASP.NET','Spring Boot','FastAPI','Django','Flask','Go','Golang','Scala','PHP','Laravel',
  'SQL','T-SQL','PL/SQL','Oracle','Oracle SQL','PostgreSQL','Postgres','MySQL','SQL Server','MongoDB','Redis','Cassandra','Exadata','RAC','ASM','Data Guard','RMAN',
  'Snowflake','Databricks','Spark','Apache Spark','PySpark','Kafka','Confluent','Flink','Airflow','DBT','dbt','Trino','Presto','ClickHouse','Redshift','BigQuery','Athena','Glue','EMR','Lambda','S3',
  'Power BI','Tableau','Qlik','Looker','SSIS','SSRS','SSAS','Informatica','Talend','Pentaho','Fabric','Dataverse',
  'SAP','SAP FICO','SAP MM','SAP SD','SAP HCM','S/4HANA','SuccessFactors','Ariba','Concur','Workday','Salesforce','Dynamics 365','SharePoint','Jira','Confluence','Excel','VBA',
  'Power Automate','Power Apps','UiPath','Blue Prism','Automation Anywhere','RPA',
  'Splunk','Dynatrace','Grafana','Prometheus','Elastic','Elasticsearch','Kibana','Logstash','Beats','Geneos','SolarWinds','ExtraHop','Loki','Jaeger',
  'Control-M','Control M','Autosys','TWS','cron','Service Manager','ServiceNow ITSM',
  'SWIFT','ISO20022','ISO 20022','RENTAS','RPP','FPX','IBG','PayNet','CCRIS','Murex','Calypso','Finacle','Temenos','T24'
];

function jdAnonEscapeRegExp(s) {
  return String(s || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function jdAnonExtractPreserveTerms(raw, companyName) {
  var text = String(raw || '');
  var found = [];
  var seen = Object.create(null);
  var companyNorm = jdAnonNormalizeTerm(companyName || '');
  var companyAliases = anonCompanyAliasNorms(companyName || '');
  JD_ANON_TECH_PRESERVE_TERMS.slice().sort(function(a,b){ return String(b).length - String(a).length; }).forEach(function(term) {
    var pattern = jdAnonEscapeRegExp(term).replace(/\\ /g, '\\s+');
    var re = new RegExp('(^|[^A-Za-z0-9+#])(' + pattern + ')(?=$|[^A-Za-z0-9+#])', 'i');
    var m = text.match(re);
    if (!m) return;
    var exact = (m[2] || term).trim();
    var norm = jdAnonNormalizeTerm(exact);
    if (!norm || seen[norm]) return;
    if (found.some(function(existing) { var en = jdAnonNormalizeTerm(existing); return en.length > norm.length && en.indexOf(norm) >= 0; })) return;
    // "Go" is also a common English verb in phrases like go-live or go-to-market.
    // Preserve it only when the JD clearly uses Go/Golang as a programming language.
    if (norm === 'go') {
      var goTechCtx = /\b(?:golang|go\s*(?:\/|,|\+|and)\s*(?:python|java|node\.?js|javascript|typescript|c#|\.net|kotlin|scala|ruby|php)|(?:python|java|node\.?js|javascript|typescript|c#|\.net|kotlin|scala|ruby|php)\s*(?:\/|,|\+|and)\s*go|go\s+(?:developer|engineer|programming|language|microservices?|backend|api|services?|runtime)|(?:develop|build|write|code|coding|programming)\s+(?:in\s+)?go)\b/i;
      if (!goTechCtx.test(text)) return;
      exact = 'Go';
    }
    if (norm === 'excel') {
      var excelCtx = /\b(?:microsoft\s+excel|advanced\s+excel|excel\s+(?:skills?|formulas?|pivot|pivots|pivot\s+tables?|vlookup|xlookup|macros?|vba|spreadsheet|spreadsheets|reporting|dashboards?|modelling|modeling)|(?:pivot\s+tables?|vlookup|xlookup|macros?|vba)\s+(?:in\s+)?excel)\b/i;
      if (!excelCtx.test(text)) return;
      exact = 'Excel';
    }
    if (norm === 'fabric') {
      var fabricCtx = /\b(?:microsoft\s+fabric|power\s+bi\s+fabric|data\s+fabric|fabric\s+(?:lakehouse|warehouse|analytics|capacity|data\s+factory|data\s+engineering|real[-\s]?time\s+analytics))\b/i;
      if (!fabricCtx.test(text)) return;
      exact = /microsoft\s+fabric/i.test(text) ? 'Microsoft Fabric' : exact;
    }
    if (norm === 'concur') {
      var concurCtx = /\b(?:sap\s+concur|concur\s+(?:expense|travel|invoice|implementation|configuration|system|platform|module))\b/i;
      if (!concurCtx.test(text)) return;
      exact = /sap\s+concur/i.test(text) ? 'SAP Concur' : exact;
    }
    // Avoid re-inserting a provided client name as a standalone technology unless the JD uses it in a clearly technical phrase.
    if (companyAliases[norm]) {
      var matchStart = (typeof m.index === 'number' ? m.index : 0) + String(m[1] || '').length;
      if (!anonIsProtectedTechContext(text, matchStart, exact)) return;
    }
    seen[norm] = true;
    found.push(exact);
  });
  return found.slice(0, 60);
}

function jdAnonEnsureTechStackPreserved(jd, raw, companyName) {
  if (!jd || typeof jd !== 'object') return jd;
  var requiredTerms = jdAnonExtractPreserveTerms(raw, companyName);
  if (!requiredTerms.length) return jd;
  var stack = Array.isArray(jd.tech_stack) ? jd.tech_stack.slice() : (jd.tech_stack ? [String(jd.tech_stack)] : []);
  var seen = Object.create(null);
  stack.forEach(function(t) { seen[jdAnonNormalizeTerm(t)] = true; });
  requiredTerms.forEach(function(term) {
    var norm = jdAnonNormalizeTerm(term);
    if (!seen[norm]) {
      stack.push(term);
      seen[norm] = true;
    }
  });
  jd.tech_stack = stack;
  return jd;
}

function jdAnonMissingPreservedTechTerms(jd, raw, companyName) {
  var requiredTerms = jdAnonExtractPreserveTerms(raw, companyName);
  if (!requiredTerms.length) return [];
  var stack = Array.isArray(jd && jd.tech_stack) ? jd.tech_stack.join(' | ') : String((jd && jd.tech_stack) || '');
  var corpus = jdAnonNormalizeTerm(stack + ' | ' + JSON.stringify(jd || {}));
  return requiredTerms.filter(function(term) { return corpus.indexOf(jdAnonNormalizeTerm(term)) < 0; });
}


function jdAnonNeedsParaphraseRetry(jd, raw) {
  var issues = jdAnonFindParaphraseIssues(jd, raw);
  // A single long copied responsibility/requirement is already enough to be suspicious.
  return issues.indexOf('responsibilities') >= 0 || issues.indexOf('requirements') >= 0 || issues.length >= 2;
}

function jdAnonParaphraseRetryInstruction(issues) {
  var fields = (issues && issues.length) ? Array.from(new Set(issues)).join(', ') : 'about/responsibilities/requirements';
  return [
    '',
    'CRITICAL RETRY: Your previous output was still too close to the original JD wording in: ' + fields + '.',
    'Rewrite again with fresh recruitment-consultant wording. Do not copy sentence structure from the original JD.',
    'Paraphrase the wording only. Do NOT weaken, remove, merge away, or generalise the role-critical tech stack, systems, tools, platforms, certifications, frameworks, methodologies, years of experience, location/work mode, or candidate-critical facts.',
    'For responsibilities and requirements, change verbs, sentence order, and phrasing while preserving the same role meaning, seniority, must-have skills, tools, certifications, years of experience, location/work mode, and candidate-critical facts.',
    'Allowed and expected to remain exact: job title, technology/tool names, certifications, regulatory acronyms, years of experience, numbers tied to candidate requirements, and standard phrases such as UAT/CAB/ECAB/ITIL/ServiceNow.'
  ].join('\n');
}


async function generateAnonJD() {
  var raw = anonNormalizeExtractedTextArtifacts(document.getElementById('anonRawText').value || '').trim();
  updateAnonOriginalPreview();
  if (!raw) { showToast('Paste or upload a JD first', 'err'); return; }
  if (raw.length < 80) { showToast('JD looks too short — paste more content', 'err'); return; }
  var route = aiRoutePayload('jd_anonymizer');
  if (!route.api_key) { showToast('Save an API key for Blind JD route', 'err'); return; }

  var clientDesc   = (document.getElementById('anonClientDesc').value || '').trim();
  var companyName  = (document.getElementById('anonCompanyName').value || '').trim();
  var industry     = (document.getElementById('anonIndustry').value || '').trim();
  var workMode     = (document.getElementById('anonWorkMode').value || '').trim();
  var location     = (document.getElementById('anonLocation').value || '').trim();
  var context      = (document.getElementById('anonContext').value || '').trim();
  var redact       = (document.getElementById('anonRedact').value || '').trim();
  var whyJoinUs    = (document.getElementById('anonWhyJoinUs').value || '').trim();
  var paraphraseLevel = String(_anonParaphraseLevel || 'medium').toLowerCase();
  var paraphraseInstruction = jdAnonParaphraseStrengthInstruction(paraphraseLevel);

  var industryInstruction;
  if (industry) {
    industryInstruction = 'Industry/sector: ' + industry + ' — use this directly.';
  } else if (companyName) {
    industryInstruction = 'Company name provided: "' + companyName + '". Determine their primary industry from the JD content and company name.';
  } else {
    industryInstruction = 'No industry or company provided. Infer the industry from the JD content (tech stack, role type, domain language, regulatory references).';
  }

  var toneMap = {
    professional:   'formal, professional, third-person where appropriate',
    conversational: 'warm, engaging, first-person plural ("we are looking for…")',
    concise:        'concise and direct — no fluff, bullet-heavy, scannable'
  };

  var prompt = [
    'You are a senior recruitment consultant. Produce a polished, anonymised version of this job description - safe to share with candidates with zero identifying information about the client.',
    '',
    'MANDATORY IDENTITY STRIPPING: Remove employer/client name, brands, proprietary products that identify the employer, office addresses, URLs, emails, phone numbers, internal codes, recruiter names. Do NOT remove tech stack, tools, frameworks, programming languages, cloud services, enterprise systems, certifications, methodologies, or any role requirements.',
    '',
    'MANDATORY PARAPHRASING: Do not merely anonymise by deleting names. Rewrite the job description into fresh candidate-facing wording. Responsibilities, requirements, nice-to-have items, why-join points, about_client, and about_role must be paraphrased and polished, not copied sentence-for-sentence from the original JD.',
    'Avoid preserving long verbatim phrases from the original JD. Change sentence structure, verbs, and phrasing while keeping the meaning, seniority, business context, reporting scope, technologies, certifications, role-critical numbers, and candidate requirements accurate. Paraphrase the prose, not the tech stack. Job title, technology names, certifications, acronyms, methodologies, and exact years of experience should remain exact.',
    paraphraseInstruction,
    '',
    'OUTPUT STYLE: Make the final JD readable and candidate-friendly. Use concise but polished bullet points. Responsibilities should sound like what the person will do; requirements should sound like what the person needs to succeed. Do not repeat the same wording across sections.',
    '',
    'ANONYMITY SCALE GENERALISATION: Do NOT preserve exact company scale figures that can identify the client. Generalise revenue, turnover, AUM, market share, ranking, employee count, office count, country count, continent count, customer count, transaction volume, factory/store/fleet count, and similar metrics. Replace exact figures with broad phrases such as multi-billion-dollar global organisation, large global workforce, broad international footprint, major regional player, or large-scale enterprise transformation.',
    'Do not write searchable combinations like $50 billion, 20,000 professionals, 100 countries, six continents, Fortune 200, top 3, or world\'s largest. Keep candidate requirements such as years of experience, team size requirements, technical versions, certifications, and role-related numbers.',
    '',
    'TECH STACK PRESERVATION: Preserve every genuine technology/tool/platform/system from the original JD exactly, including acronyms and version numbers. Include them in tech_stack and keep them visible in the final output. Only generalise technology-like names if they are clearly proprietary employer product/platform names that would identify the client. Paraphrase responsibilities/requirements around these terms, but do not delete the terms themselves.',
    '',
    'INDUSTRY: ' + industryInstruction,
    '',
    clientDesc ? ('ABOUT CLIENT (use as source, anonymise before output): "' + clientDesc + '"') : 'Write a compelling 2-3 sentence About Our Client paragraph using JD signals WITHOUT naming them.',
    '',
    workMode  ? ('Work mode: ' + workMode)  : '',
    location  ? ('Location: '  + location)  : '',
    context   ? ('Context: '   + context)   : '',
    whyJoinUs ? ('Why Join Us notes: ' + whyJoinUs) : '',
    redact    ? ('Also explicitly remove: ' + redact) : '',
    '',
    'TONE: ' + (toneMap[_anonTone] || toneMap.professional),
    '',
    'Return ONLY a raw JSON object:',
    '{"job_title":"","about_client":"","about_role":"","work_mode":"' + (workMode || 'refer to JD') + '","location":"' + (location || 'refer to JD') + '","industry":"","exp_range":null,"tech_stack":[],"responsibilities":[],"requirements":[],"nice_to_have":[],"why_join":[],"alt_titles":[]}',
    '',
    'Before returning JSON, self-check that responsibilities and requirements are not copied from the original JD. If a bullet sounds identical, rewrite it.',
    '',
    'ORIGINAL JD:',
    '---',
    raw,
    '---'
  ].filter(function(l){ return l !== null && l !== undefined; }).join('\n');
  var btn = document.getElementById('btnAnonJD');
  var statusEl = document.getElementById('anonJDStatus');
  var _tabRun = markTabRunning('jdanon');
  btn.disabled = true; btn.textContent = '⏳ Anonymising…';
  statusEl.textContent = 'Processing… paraphrase: ' + paraphraseLevel;
  document.getElementById('anonJDOutput').style.display = 'none';
  var phAnonStart = document.getElementById('anonJDPlaceholder'); if (phAnonStart) phAnonStart.style.display = 'flex';

  try {
    var data = await callAIProxy(prompt, 4000, false, 3, 'jd_anonymizer');
    var rawOut = aiText(data);
    var _anonTotalUsage = normalizeUsageClient({});
    var _anonTotalUsd = 0;
    var _anonRetryUsed = false;

    function _anonTrackUsage(resp, label) {
      if (!resp) return;
      var trackRoute = aiRoutePayload('jd_anonymizer');
      var cost = responseCost(resp, trackRoute.model, trackRoute.provider);
      _anonTotalUsage = mergeUsageClient(_anonTotalUsage, resp.usage || {});
      _anonTotalUsd += cost;
      statsRecord(label || 'Blind JD', 'jd', cost, resp.model || trackRoute.model, '', resp.provider || trackRoute.provider,
        statsMetaFromResponse(resp, trackRoute.model, trackRoute.provider));
    }

    // Cost tracking. If paraphrase retry runs, the final on-screen cost now includes both calls.
    _anonTrackUsage(data, 'Blind JD');

    // Parse JSON
    var jd;
    try {
      var stripped = rawOut.replace(/```json/gi,'').replace(/```/g,'').trim();
      var fi = stripped.indexOf('{'), li = stripped.lastIndexOf('}');
      if (fi < 0 || li <= fi) throw new Error('No JSON');
      jd = JSON.parse(stripped.slice(fi, li+1));
    } catch(pe) {
      // Fallback: plain text display, still apply local scale softening guard
      rawOut = scrubAnonCompanyNameText(softenAnonScaleText(rawOut), companyName);
      document.getElementById('anonJDBody').innerHTML = '<div style="white-space:pre-wrap">' + anonEscapeHtml(rawOut) + '</div>';
      document.getElementById('anonJDTitle').textContent = 'Blind JD';
      document.getElementById('anonJDOutput').style.display = '';
      var phAnonFallback = document.getElementById('anonJDPlaceholder'); if (phAnonFallback) phAnonFallback.style.display = 'none';
      var fallbackCostEl = document.getElementById('anonJDCost');
      var fallbackTokens = _anonTotalUsage.input_tokens + _anonTotalUsage.output_tokens;
      if (fallbackCostEl) fallbackCostEl.textContent = fallbackTokens ? ('🔥 ' + fallbackTokens.toLocaleString() + ' tokens · $' + _anonTotalUsd.toFixed(4)) : '';
      statusEl.textContent = 'Generated — review formatting';
      markTabDone('jdanon', _tabRun);
      return;
    }

    // Retry once if the first structured output still copies long JD phrases in responsibilities/requirements.
    var _anonParaphraseIssues = jdAnonFindParaphraseIssues(jd, raw);
    if (jdAnonNeedsParaphraseRetry(jd, raw)) {
      statusEl.textContent = 'Rewriting copied JD wording…';
      _anonRetryUsed = true;
      var retryInstruction = jdAnonParaphraseRetryInstruction(_anonParaphraseIssues);
      var retryPrompt = prompt.replace('\nORIGINAL JD:\n---\n', '\n' + retryInstruction + '\n\nORIGINAL JD:\n---\n');
      if (retryPrompt === prompt) retryPrompt = prompt + retryInstruction;
      var retryData = await callAIProxy(retryPrompt, 4000, false, 3, 'jd_anonymizer');
      _anonTrackUsage(retryData, 'Blind JD — Rewrite Retry');
      var retryText = aiText(retryData);
      try {
        var retryStripped = retryText.replace(/```json/gi,'').replace(/```/g,'').trim();
        var rfi = retryStripped.indexOf('{'), rli = retryStripped.lastIndexOf('}');
        if (rfi >= 0 && rli > rfi) {
          var retryJd = JSON.parse(retryStripped.slice(rfi, rli+1));
          var retryIssues = jdAnonFindParaphraseIssues(retryJd, raw);
          var firstCoreIssues = _anonParaphraseIssues.indexOf('responsibilities') >= 0 || _anonParaphraseIssues.indexOf('requirements') >= 0;
          var retryCoreIssues = retryIssues.indexOf('responsibilities') >= 0 || retryIssues.indexOf('requirements') >= 0;
          if (retryIssues.length < _anonParaphraseIssues.length || (firstCoreIssues && !retryCoreIssues)) jd = retryJd;
        }
      } catch(retryParseErr) {
        // Keep first valid JSON if retry returns invalid JSON.
      }
    }

    // Render structured card. Preserve genuine tech/tool/platform terms from the source JD before final anonymisation/scrubbing.
    var _anonMissingTechBeforeLocalGuard = jdAnonMissingPreservedTechTerms(jd, raw, companyName);
    jd = jdAnonEnsureTechStackPreserved(jd, raw, companyName);
    jd = scrubAnonCompanyNameData(softenAnonScaleData(jd), companyName);
    var _anonMissingTechAfterLocalGuard = jdAnonMissingPreservedTechTerms(jd, raw, companyName);
    window._lastAnonJD = jd;
    document.getElementById('anonJDBody').innerHTML = renderAnonJDCard(jd);
    document.getElementById('anonJDTitle').textContent = jd.job_title || 'Blind JD';
    document.getElementById('anonJDOutput').style.display = '';
    var phAnonDone = document.getElementById('anonJDPlaceholder'); if (phAnonDone) phAnonDone.style.display = 'none';
    var _anonTokens = _anonTotalUsage.input_tokens + _anonTotalUsage.output_tokens;
    var costEl = document.getElementById('anonJDCost');
    if (costEl) {
      var retrySuffix = _anonRetryUsed ? ' · includes rewrite retry' : '';
      costEl.textContent = _anonTokens ? ('🔥 ' + _anonTokens.toLocaleString() + ' tokens · $' + _anonTotalUsd.toFixed(4) + retrySuffix) : '';
    }
    var _anonFinalIssues = jdAnonFindParaphraseIssues(jd, raw);
    var _anonFinalCoreIssue = _anonFinalIssues.indexOf('responsibilities') >= 0 || _anonFinalIssues.indexOf('requirements') >= 0;
    if (_anonMissingTechAfterLocalGuard && _anonMissingTechAfterLocalGuard.length) {
      statusEl.textContent = '⚠️ Generated — review tech stack';
    } else if (_anonFinalCoreIssue) {
      statusEl.textContent = '⚠️ Generated — review paraphrasing';
    } else {
      statusEl.textContent = (_anonMissingTechBeforeLocalGuard && _anonMissingTechBeforeLocalGuard.length) ? '✅ Done — tech stack preserved' : '✅ Done';
    }
    markTabDone('jdanon', _tabRun);
    showToast('Blind JD generated!', 'ok');

  } catch(e) {
    statusEl.textContent = '❌ ' + e.message;
    markTabFailed('jdanon', _tabRun);
    showToast('Anonymisation failed: ' + e.message, 'err');
  } finally {
    btn.disabled = false; btn.textContent = 'Generate Blind JD';
  }
}

function renderAnonJDCard(j) {
  j = j || {};
  function arr(v) { return Array.isArray(v) ? v : (v ? [String(v)] : []); }
  function esc2(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
  function pills(items, col) {
    return arr(items).map(function(t){ return '<span style="display:inline-block;background:'+col+';border-radius:20px;padding:2px 9px;margin:2px 3px 2px 0;font-size:11px;font-weight:500;">'+esc2(t)+'</span>'; }).join('');
  }
  function bullets(items, dot) {
    return arr(items).map(function(b){ return '<li style="display:flex;gap:8px;padding:3px 0;"><span style="color:'+dot+';flex-shrink:0;margin-top:2px">•</span><span>'+esc2(b)+'</span></li>'; }).join('');
  }
  function sec(label, html) { return '<div style="margin-bottom:14px"><div style="font-size:11px;font-weight:700;color:var(--text2);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">'+label+'</div>'+html+'</div>'; }

  var meta = [j.location, j.work_mode, j.industry].filter(function(x){return x&&x!=='null';})
    .map(function(x){ return '<span style="background:var(--surface2);border:1px solid var(--border);border-radius:20px;padding:2px 9px;font-size:11px;margin-right:5px;">'+esc2(x)+'</span>'; }).join('');

  return '<div style="display:flex;flex-direction:column;gap:2px;">'
    + '<div style="font-size:16px;font-weight:700;color:var(--text1);margin-bottom:8px;">'+esc2(j.job_title||'Blind JD')+'</div>'
    + (meta ? '<div style="margin-bottom:12px;">'+meta+'</div>' : '')
    + (j.about_client ? sec('About Our Client', '<p style="margin:0;line-height:1.65;">'+esc2(j.about_client)+'</p>'+(j.about_role?'<p style="margin:8px 0 0;line-height:1.65;color:var(--text2);">'+esc2(j.about_role)+'</p>':'')) : '')
    + (arr(j.tech_stack).length ? sec('Tech Stack', pills(j.tech_stack, 'var(--surface2)')) : '')
    + (arr(j.responsibilities).length ? sec('What You Will Do', '<ul style="list-style:none;padding:0;margin:0;">'+bullets(j.responsibilities,'#22c55e')+'</ul>') : '')
    + (arr(j.requirements).length ? sec('What You Need to Succeed', '<ul style="list-style:none;padding:0;margin:0;">'+bullets(j.requirements,'#60a5fa')+'</ul>') : '')
    + (arr(j.nice_to_have).length ? sec('Nice to Have', '<ul style="list-style:none;padding:0;margin:0;">'+bullets(j.nice_to_have,'var(--text3)')+'</ul>') : '')
    + (arr(j.why_join).length ? sec('Why Join Us', '<ul style="list-style:none;padding:0;margin:0;">'+bullets(j.why_join,'#22c55e')+'</ul>') : '')
    + (arr(j.alt_titles).length ? sec('Also Search For', pills(j.alt_titles,'var(--surface2)')) : '')
    + '<div style="margin-top:12px;padding-top:10px;border-top:1px solid var(--border);display:flex;justify-content:space-between;font-size:11px;color:var(--text3);">'
    + '<span>© Hyppies · Confidential · For candidate use only</span>'
    + '<span>'+new Date().toLocaleDateString('en-MY',{day:'2-digit',month:'short',year:'numeric'})+'</span>'
    + '</div></div>';
}

// ── Blind JD Export ─────────────────────────────────────────────
async function exportAnonJDDoc() {
  var j = window._lastAnonJD;
  if (!j) { showToast('Generate Blind JD first', 'err'); return; }
  function arr(v) { return Array.isArray(v) ? v : (v ? [String(v)] : []); }
  function section(label, val) {
    return val ? '<h2>' + _escDoc(label) + '</h2><p>' + _escDoc(val).replace(/\n/g, '<br>') + '</p>' : '';
  }
  function list(label, items) {
    items = arr(items);
    return items.length ? '<h2>' + _escDoc(label) + '</h2><ul>' + items.map(function(b){ return '<li>' + _escDoc(b) + '</li>'; }).join('') + '</ul>' : '';
  }
  var roleDetails = [
    j.about_role,
    j.work_mode ? 'Work Arrangement: ' + j.work_mode : '',
    j.location ? 'Location: ' + j.location : '',
    j.industry ? 'Industry: ' + j.industry : ''
  ].filter(Boolean).join('\n');
  var body = '';
  body += section('About Our Client', j.about_client);
  body += section('About the Role', roleDetails);
  if (arr(j.tech_stack).length) {
    body += '<h2>Tech Stack / Tools</h2><p>' + arr(j.tech_stack).map(function(t){ return '<span class="chip">' + _escDoc(String(t).trim()) + '</span>'; }).join(' ') + '</p>';
  }
  body += list('What You Will Do', j.responsibilities);
  body += list('What You Need to Succeed', j.requirements);
  body += list('Nice to Have', j.nice_to_have);
  if (arr(j.why_join).length) {
    body += '<div class="callout"><h2 style="margin-top:0;border-bottom:0;padding-bottom:0">Why Join Us</h2><ul>' + arr(j.why_join).map(function(b){ return '<li>' + _escDoc(b) + '</li>'; }).join('') + '</ul></div>';
  }
  if (arr(j.alt_titles).length) {
    body += '<h2>Alternative Job Titles</h2><p>' + arr(j.alt_titles).map(function(t){ return '<span class="chip">' + _escDoc(String(t).trim()) + '</span>'; }).join(' ') + '</p>';
  }
  var html = _wordDocShell(j.job_title || 'Role Brief', 'Hyppies', body);
  var output = await exportWordDocumentToDestination(html, 'blind-jd-' + _safeFileStem(j.job_title), 'blind_jd');
  cvStudioShowDownloadResult(output.result, 'Blind JD Word .' + output.format);
}

async function exportAnonJDPDF() {
  var j = window._lastAnonJD;
  if (!j) { showToast('Generate Blind JD first', 'err'); return; }
  if (!(window.jspdf && window.jspdf.jsPDF)) {
    if (window.cvStudioLoadJSPDF) window.cvStudioLoadJSPDF(exportAnonJDPDF, function() { showToast('PDF library not loaded — try Word export instead', 'err'); });
    else showToast('PDF library not loaded — try Word export instead', 'err');
    return;
  }
  var jsPDF = window.jspdf.jsPDF;
  var doc = new jsPDF({ unit:'mm', format:'a4' });
  var margin = 18, pageW = 210, maxW = pageW - margin * 2, lh = 5.5, y = margin;
  var C = { purple:[53,42,134], text:[25,27,34], muted:[92,99,115], dim:[145,151,165],
            hairline:[226,229,236], soft:[248,249,252], green:[22,101,52], greenBg:[240,253,244],
            blue:[24,95,165], blueBg:[231,242,253], amber:[133,79,11], amberBg:[255,247,237], purpleBg:[245,243,255] };
  function safe(s) { return cvPdfSafeText(s); }
  function checkPage(n) { if (y+(n||12)>276){ doc.addPage(); pageHdr(); y=24; } }
  function pageHdr() {
    doc.setFillColor(255,255,255); doc.rect(0,0,210,16,'F');
    try { doc.addImage(HYPPIES_LOGO_URI,'JPEG',margin,4,9,9); } catch(e){}
    doc.setFont('helvetica','bold'); doc.setFontSize(7.5); doc.setTextColor(...C.purple);
    doc.text('Hyppies', margin+13, 9.5);
    doc.setFont('helvetica','normal'); doc.setFontSize(7); doc.setTextColor(...C.dim);
    doc.text(new Date().toLocaleDateString('en-MY'), pageW-margin, 9.5, {align:'right'});
    doc.setDrawColor(...C.hairline); doc.line(margin,15,pageW-margin,15);
  }
  function secHdr(title, bg, fg, reserve) { checkPage(15 + (reserve || 0)); y+=4; doc.setFillColor(...(bg||C.soft)); doc.roundedRect(margin-1,y-5,maxW+2,9,2,2,'F'); doc.setFont('helvetica','bold'); doc.setFontSize(8); doc.setTextColor(...(fg||C.purple)); doc.text(safe(title).toUpperCase(), margin+2, y+1.2); y+=11; }
  function splitWithFont(text, width, style, size) { doc.setFont('helvetica', style || 'normal'); doc.setFontSize(size || 9.2); return doc.splitTextToSize(safe(text), width); }
  function firstBulletReserve(arr) { arr = (arr || []).filter(Boolean); if (!arr.length) return 0; return splitWithFont(arr[0], maxW-8, 'normal', 9.2).length * lh + 7; }
  function firstParaReserve(text) { if (!text) return 0; return splitWithFont(text, maxW, 'normal', 9.3).length * lh + 6; }
  function bullet(text, dot) { var lines=splitWithFont(text,maxW-8,'normal',9.2); checkPage(lines.length*lh+3); doc.setFillColor(...dot); doc.circle(margin+2,y-1,1.15,'F'); doc.setFont('helvetica','normal'); doc.setFontSize(9.2); doc.setTextColor(...C.text); doc.text(lines,margin+7,y); y+=lines.length*lh+2.5; }
  function para(text,col) { var lines=splitWithFont(text,maxW,'normal',9.3); checkPage(lines.length*lh+3); doc.setFont('helvetica','normal'); doc.setFontSize(9.3); doc.setTextColor(...(col||C.text)); doc.text(lines,margin,y); y+=lines.length*lh+3; }

  // First page header with logo
  doc.setFillColor(255,255,255); doc.rect(0,0,210,38,'F');
  try { doc.addImage(HYPPIES_LOGO_URI,'JPEG',margin,6,23,23); } catch(e){}
  doc.setFont('helvetica','bold'); doc.setFontSize(15); doc.setTextColor(...C.purple);
  var titleLines = doc.splitTextToSize(safe(j.job_title||'Blind JD'), 132);
  doc.text(titleLines, margin+30, 13);
  doc.setFont('helvetica','normal'); doc.setFontSize(8); doc.setTextColor(...C.muted);
  var meta = [j.location,j.work_mode,j.industry].filter(function(x){return x&&x!=='null';}).join('  |  ');
  var metaX = margin + 30;
  var metaY = 13 + titleLines.length * 6 + 2;
  var metaLines = doc.splitTextToSize(safe(meta||'Hyppies'), pageW - margin - metaX);
  doc.text(metaLines, metaX, metaY);
  var headerRuleY = Math.max(35, metaY + (metaLines.length - 1) * 3.4 + 4.5);
  doc.setDrawColor(...C.hairline); doc.setLineWidth(0.35); doc.line(margin,headerRuleY,pageW-margin,headerRuleY);
  y = headerRuleY + 9;

  var hasLoc = j.location && j.location !== 'null';
  var hasWm  = j.work_mode && j.work_mode !== 'null';
  var metadataTiles = [[hasLoc, 'Location', j.location, C.amberBg, C.amber], [hasWm, 'Work', j.work_mode, C.blueBg, C.blue]]
    .filter(function(item){ return item[0]; });
  if (metadataTiles.length) {
    var px = margin;
    var tileGap = 4;
    var tileWidth = (maxW - tileGap * (metadataTiles.length - 1)) / metadataTiles.length;
    var tileLayouts = metadataTiles.map(function(item){
      return { item:item, lines:splitWithFont(item[1] + ': ' + item[2], tileWidth - 6, 'bold', 7.6) };
    });
    var maxTileLines = Math.max.apply(null, tileLayouts.map(function(layout){ return layout.lines.length; }));
    var tileHeight = 7.2 + (maxTileLines - 1) * 3.2;
    tileLayouts.forEach(function(layout){
      var item = layout.item;
      doc.setFillColor(...item[3]); doc.roundedRect(px, y, tileWidth, tileHeight, 2, 2, 'F');
      doc.setFont('helvetica','bold'); doc.setFontSize(7.6); doc.setTextColor(...item[4]);
      doc.text(layout.lines, px+3, y+4.8);
      px += tileWidth + tileGap;
    });
    y += tileHeight + 6.8;
  }

  if (j.about_client) { secHdr('About Our Client', C.soft, C.purple, firstParaReserve(j.about_client)); para(j.about_client); if (j.about_role) para(j.about_role, C.muted); y+=2; }
  if ((j.tech_stack||[]).length) { var tl=splitWithFont((j.tech_stack||[]).join('  |  '),maxW,'bold',8.8); secHdr('Tech Stack / Tools', C.blueBg, C.blue, tl.length*lh+6); doc.setFont('helvetica','bold'); doc.setFontSize(8.8); doc.setTextColor(...C.blue); doc.text(tl,margin,y); y+=tl.length*lh+5; }
  if ((j.responsibilities||[]).length) { secHdr('What You Will Do', C.greenBg, C.green, firstBulletReserve(j.responsibilities)); j.responsibilities.forEach(function(b){ bullet(b,[34,197,94]); }); y+=2; }
  if ((j.requirements||[]).length) { secHdr('What You Need to Succeed', C.blueBg, C.blue, firstBulletReserve(j.requirements)); j.requirements.forEach(function(b){ bullet(b,[96,165,250]); }); y+=2; }
  if ((j.nice_to_have||[]).length) { secHdr('Nice to Have', C.soft, C.muted, firstBulletReserve(j.nice_to_have)); j.nice_to_have.forEach(function(b){ bullet(b,C.dim); }); y+=2; }
  if ((j.why_join||[]).length) { secHdr('Why Join Us', C.greenBg, C.green, firstBulletReserve(j.why_join)); j.why_join.forEach(function(b){ bullet(b,[34,197,94]); }); y+=2; }
  if ((j.alt_titles||[]).length) { var al=splitWithFont(j.alt_titles.join('  |  '),maxW,'normal',8.8); secHdr('Alternative Job Titles', C.purpleBg, C.purple, al.length*lh+5); doc.setFont('helvetica','normal'); doc.setFontSize(8.8); doc.setTextColor(...C.muted); doc.text(al,margin,y); y+=al.length*lh+4; }

  var total=doc.internal.getNumberOfPages();
  for(var pg=1;pg<=total;pg++){ doc.setPage(pg); doc.setDrawColor(...C.hairline); doc.setLineWidth(0.25); doc.line(margin,284,pageW-margin,284); doc.setFont('helvetica','normal'); doc.setFontSize(7.5); doc.setTextColor(...C.dim); doc.text('Hyppies  |  Confidential  |  For candidate use only',margin,290); doc.text('Page '+pg+' of '+total,pageW-margin,290,{align:'right'}); }
  var filename = 'blind-jd-'+_safeFileStem(j.job_title)+'-'+new Date().toISOString().slice(0,10)+'.pdf';
  var result = await cvStudioSaveDownloadBlob(doc.output('blob'), filename, 'blind_jd');
  cvStudioShowDownloadResult(result, 'Blind JD PDF');
}
