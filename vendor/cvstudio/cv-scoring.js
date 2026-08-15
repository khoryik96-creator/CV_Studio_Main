// ── CV Scoring: JD vs CV Compatibility Scorer ─────────────────────────────
var _appraiserResult = null;
var _appraiserRawReport = null;
function updateAppraiserRouteBadge() {
  var el = document.getElementById('appraiserRouteBadge');
  if (!el) return;
  try { var r = resolveAiRoute('appraiser'); el.textContent = 'Using: ' + r.display; }
  catch(e) { el.textContent = 'Using: —'; }
}
function updateAppraiserCounts() {
  var jd = document.getElementById('appraiserJdText');
  var cv = document.getElementById('appraiserCvText');
  var jdc = document.getElementById('appraiserJdCount');
  var cvc = document.getElementById('appraiserCvCount');
  if (jdc) jdc.textContent = ((jd && jd.value) ? jd.value.length : 0).toLocaleString() + ' chars';
  if (cvc) cvc.textContent = ((cv && cv.value) ? cv.value.length : 0).toLocaleString() + ' chars';
}
var _appraiserPendingFiles = { jd: null, cv: null };
function appraiserFileTargets(kind) {
  return kind === 'cv'
    ? { textId:'appraiserCvText', statusId:'appraiserCvStatus', inputId:'appraiserCvFile', extractBtnId:'appraiserCvExtractBtn', label:'CV' }
    : { textId:'appraiserJdText', statusId:'appraiserJdStatus', inputId:'appraiserJdFile', extractBtnId:'appraiserJdExtractBtn', label:'JD' };
}
function appraiserSupportedFileExt(file) {
  var ext = ((file && file.name ? file.name : '').split('.').pop() || '').toLowerCase();
  return ['pdf','docx','doc','txt','rtf','odt','png','jpg','jpeg'].indexOf(ext) >= 0;
}
function selectAppraiserFile(file, kind) {
  var t = appraiserFileTargets(kind);
  var status = document.getElementById(t.statusId);
  if (!file) return;
  if (!appraiserSupportedFileExt(file)) {
    if (status) status.textContent = '✗ Unsupported file type';
    showToast('Supported: PDF, DOCX, DOC, TXT, RTF, ODT, PNG, JPG, JPEG', 'err');
    return;
  }
  _appraiserPendingFiles[kind] = file;
  if (status) status.textContent = 'Selected ' + file.name + ' — extracting…';
  return handleAppraiserFile(file, t.textId, t.statusId, kind);
}
function extractAppraiserSelectedFile(kind) {
  var t = appraiserFileTargets(kind);
  var file = _appraiserPendingFiles[kind] || ((document.getElementById(t.inputId) || {}).files || [])[0];
  if (!file) { showToast('Choose or drop a ' + t.label + ' file first', 'info'); return; }
  return handleAppraiserFile(file, t.textId, t.statusId, kind);
}
async function handleAppraiserFile(file, targetTextId, statusId, kind) {
  if (!file) return;
  var status = document.getElementById(statusId);
  var target = document.getElementById(targetTextId);
  if (!appraiserSupportedFileExt(file)) { showToast('Supported: PDF, DOCX, DOC, TXT, RTF, ODT, PNG, JPG, JPEG', 'err'); return; }
  var controls = appraiserFileTargets(kind);
  var extractBtn = document.getElementById(controls.extractBtnId);
  var run = markTabRunning('appraiser');
  if (extractBtn) extractBtn.disabled = true;
  if (target) target.dataset.extracting = '1';
  if (status) status.textContent = 'Extracting ' + file.name + '…';
  try {
    var fd = new FormData(); fd.append('file', file);
    var r = await fetchWithTimeout('/extract-text', { method:'POST', body:fd }, CV_EXTRACT_TEXT_TIMEOUT_MS);
    var d = await r.json().catch(function(){ return {}; });
    if (!r.ok || d.error) throw new Error(d.error || 'Extraction failed');
    var extractionWarning = cvShowExtractionWarning(d);
    var cleaned = appraiserCleanExtractedText(d.text || '');
    if (target) target.value = cleaned;
    if (status) status.textContent = (extractionWarning ? '⚠ ' : '✓ ') + file.name + ' (' + (cleaned || '').length.toLocaleString() + ' chars extracted)' + (extractionWarning ? ' — partial extraction; review text' : '');
    updateAppraiserCounts();
    markTabDone('appraiser', run);
    if (!extractionWarning) showToast((kind === 'cv' ? 'CV' : 'JD') + ' extracted for CV Scoring', 'ok');
  } catch(e) {
    if (status) status.textContent = '✗ ' + (e.message || 'Extraction failed');
    markTabFailed('appraiser', run);
    showToast('CV Scoring extraction failed: ' + (e.message || 'Unknown error'), 'err');
  } finally {
    if (target) delete target.dataset.extracting;
    if (extractBtn) extractBtn.disabled = false;
  }
}
function appraiserRemarksContext() {
  var parts = [];
  var salary = ((document.getElementById('appraiserSalary') || {}).value || '').trim();
  var seniority = ((document.getElementById('appraiserSeniority') || {}).value || '').trim();
  var industry = ((document.getElementById('appraiserIndustry') || {}).value || '').trim();
  var hidden = ((document.getElementById('appraiserHidden') || {}).value || '').trim();
  if (salary) parts.push('Salary/budget expectation: ' + salary);
  if (seniority) parts.push('Expected seniority: ' + seniority);
  if (industry) parts.push('Industry/company context: ' + industry);
  if (hidden) parts.push('Hidden or soft requirements: ' + hidden);
  return parts.join('\n');
}
function appraiserAsArray(v) {
  if (Array.isArray(v)) return v.filter(function(x){ return x !== null && x !== undefined && String(x).trim(); }).map(function(x){ return typeof x === 'string' ? x : JSON.stringify(x); });
  if (v === null || v === undefined || v === '') return [];
  return [String(v)];
}
function appraiserCleanExtractedText(s) {
  s = String(s || '');
  try { if (typeof anonNormalizeExtractedTextArtifacts === 'function') return anonNormalizeExtractedTextArtifacts(s); } catch(e) {}
  return s.trim();
}
function appraiserParseScore(v) {
  if (typeof v === 'number' && isFinite(v)) return Math.max(0, Math.min(100, Math.round(v)));
  var s = String(v || '');
  function clampScore(n){ n = parseFloat(n); return isFinite(n) ? Math.max(0, Math.min(100, Math.round(n))) : 0; }
  // Prefer explicit score formats before bare numbers. Otherwise text such as
  // "8 years experience; score 76/100" can accidentally parse as 8.
  var ratio10 = s.match(/\b(10|[0-9](?:\.\d+)?)\s*\/\s*10\b/);
  if (ratio10) return clampScore(parseFloat(ratio10[1]) * 10);
  var ratio100 = s.match(/\b(100|[1-9]?\d(?:\.\d+)?)\s*\/\s*100\b/);
  if (ratio100) return clampScore(ratio100[1]);
  var percent = s.match(/\b(100|[1-9]?\d(?:\.\d+)?)\s*%/);
  if (percent) return clampScore(percent[1]);
  var labelled = s.match(/\b(?:overall|fit|score|scored|rating)\D{0,24}(100|[1-9]?\d(?:\.\d+)?)\b/i);
  if (labelled) return clampScore(labelled[1]);
  var bare = s.match(/\b(100|[1-9]?\d(?:\.\d+)?)\b/);
  return bare ? clampScore(bare[1]) : 0;
}
function appraiserHasNegativeFitSignal(t) {
  t = String(t || '').toLowerCase();
  return /\b(?:not\s+recommended|do\s+not\s+recommend|would\s+not\s+recommend|not\s+suitable|unsuitable|reject(?:ed)?|decline|no\s*go|poor\s+fit|bad\s+fit|pass(?:\s+on)?|not\s+a\s+fit|no\s+match)\b/.test(t);
}
function appraiserHasConsiderSignal(t) {
  t = String(t || '').toLowerCase();
  return /\b(?:consider|reserve|reservation|maybe|borderline|hold|backup|partial\s+fit)\b/.test(t);
}
function appraiserHasPositiveFitSignal(t) {
  t = String(t || '').toLowerCase();
  return /\b(?:shortlist|submit|proceed|yes|recommended|recommend|suitable|good\s+fit|strong\s+fit)\b/.test(t);
}
function appraiserNormalizeVerdict(v, score) {
  var t = String(v || '').toLowerCase();
  if (appraiserHasNegativeFitSignal(t)) return 'Not Recommended';
  if (appraiserHasConsiderSignal(t)) return 'Consider';
  if (/\b(?:highly|strongly)\s+recommended\b|\bhighly\s+suitable\b|\bstrong\s+fit\b/.test(t)) return score < 45 ? 'Not Recommended' : 'Highly Recommended';
  if (appraiserHasPositiveFitSignal(t)) return score < 45 ? 'Not Recommended' : 'Recommended';
  return score >= 80 ? 'Highly Recommended' : score >= 65 ? 'Recommended' : score >= 45 ? 'Consider' : 'Not Recommended';
}
function appraiserNormalizeRecommendation(v, score) {
  var t = String(v || '').toLowerCase();
  if (appraiserHasNegativeFitSignal(t)) return 'Pass';
  if (appraiserHasConsiderSignal(t)) return 'Consider with Reservations';
  if (appraiserHasPositiveFitSignal(t)) return score < 45 ? 'Pass' : 'Shortlist';
  return score >= 70 ? 'Shortlist' : score >= 45 ? 'Consider with Reservations' : 'Pass';
}
function appraiserNormalizeDimensions(v) {
  var dims = [];
  if (Array.isArray(v)) dims = v;
  else if (v && typeof v === 'object') dims = Object.keys(v).map(function(k){ var d = v[k]; return (d && typeof d === 'object') ? Object.assign({name:k}, d) : {name:k, score:d, note:''}; });
  return dims.map(function(d){
    if (typeof d === 'string') d = { name:d, score:0, note:'' };
    var ds = appraiserParseScore(d.score);
    return { name: d.name || d.dimension || 'Dimension', score: ds, note: d.note || d.explanation || d.reason || '' };
  });
}
function appraiserNormalizeGapPrep(v) {
  if (!v) return [];
  if (!Array.isArray(v)) v = [v];
  return v.map(function(gp){
    if (typeof gp === 'string') return { gap: gp, tips: [] };
    return { gap: gp.gap || gp.name || gp.concern || 'Gap', tips: appraiserAsArray(gp.tips || gp.prep_tips || gp.actions || gp.recommendations) };
  }).filter(function(gp){ return String(gp.gap || '').trim() || gp.tips.length; });
}
function normalizeAppraiserResult(r) {
  r = r || {};
  var sc = appraiserParseScore(r.overall_score || r.score || r.fit_score);
  var dims = appraiserNormalizeDimensions(r.dimensions || r.dimension_scores || r.scoring);
  var rawVerdict = r.verdict || '';
  var rawRecommendation = r.recommendation || '';
  var verdict = appraiserNormalizeVerdict(rawVerdict || rawRecommendation, sc);
  var recommendation = appraiserNormalizeRecommendation(rawRecommendation || rawVerdict, sc);
  var combinedDecisionText = String(rawVerdict || '') + ' ' + String(rawRecommendation || '');
  // Conflict guard: do not let phrases like "Not Recommended" become
  // "Recommended", and never show a shortlist/recommended label for a low score
  // when the recommendation itself says Pass/Reject/Not Recommended.
  if (appraiserHasNegativeFitSignal(combinedDecisionText)) {
    verdict = 'Not Recommended';
    recommendation = 'Pass';
  }
  if (sc < 45 && recommendation === 'Pass' && /Recommended/.test(verdict)) verdict = 'Not Recommended';
  if (sc < 45 && verdict !== 'Not Recommended') verdict = 'Not Recommended';
  if (verdict === 'Not Recommended' && recommendation === 'Shortlist') recommendation = sc >= 45 ? 'Consider with Reservations' : 'Pass';
  return {
    overall_score: sc,
    verdict: verdict,
    verdict_explanation: r.verdict_explanation || r.explanation || r.summary || '',
    dimensions: dims,
    eligibility_bullets: appraiserAsArray(r.eligibility_bullets || r.eligibility || r.fit_evidence),
    strengths: appraiserAsArray(r.strengths || r.key_strengths),
    gaps: appraiserAsArray(r.gaps || r.concerns || r.weaknesses),
    gap_prep: appraiserNormalizeGapPrep(r.gap_prep || r.gap_preparation || r.interview_prep),
    disclaimers: appraiserAsArray(r.disclaimers || r.assumptions || r.limitations),
    recommendation: recommendation
  };
}
async function runAppraiser() {
  var jdEl = document.getElementById('appraiserJdText');
  var cvEl = document.getElementById('appraiserCvText');
  if ((jdEl && jdEl.dataset.extracting === '1') || (cvEl && cvEl.dataset.extracting === '1')) { showToast('Still extracting file text. Please wait before running CV Scoring.', 'info'); return; }
  var jd = appraiserCleanExtractedText(((jdEl || {}).value || '').trim());
  var cv = appraiserCleanExtractedText(((cvEl || {}).value || '').trim());
  if (jdEl && jdEl.value !== jd) jdEl.value = jd;
  if (cvEl && cvEl.value !== cv) cvEl.value = cv;
  updateAppraiserCounts();
  if (!jd) { showToast('Upload or paste the JD first', 'err'); return; }
  if (!cv) { showToast('Upload or paste the CV first', 'err'); return; }
  var route = aiRoutePayload('appraiser');
  if (!route.api_key) { showToast('Save an API key for CV Scoring route', 'err'); return; }
  var btn = document.getElementById('appraiserBtn');
  var body = document.getElementById('appraiserBody');
  var out = document.getElementById('appraiserOutput');
  var costEl = document.getElementById('appraiserCost');
  var copyBtn = document.getElementById('appraiserCopyBtn');
  var wordBtn = document.getElementById('appraiserWordBtn');
  var pdfBtn = document.getElementById('appraiserPdfBtn');
  var run = markTabRunning('appraiser');
  updateAppraiserRouteBadge();
  if (out) out.classList.add('show');
  if (body) body.innerHTML = '<div style="display:flex;align-items:center;gap:10px;padding:22px;color:var(--text3);"><span class="spinner"></span><span>Running CV Scoring with ' + esc(route.display) + '…</span></div>';
  if (btn) btn.disabled = true;
  if (costEl) costEl.textContent = '';
  _appraiserRawReport = null;
  if (copyBtn) copyBtn.style.display = 'none';
  if (wordBtn) wordBtn.style.display = 'none';
  if (pdfBtn) pdfBtn.style.display = 'none';
  var remarks = appraiserRemarksContext();
  var prompt = 'You are an expert recruitment consultant and talent assessor. Analyse how well the candidate CV matches the job description. Be practical, fair, and useful for a recruiter deciding whether to submit the candidate.\n\n'
    + 'Return ONLY a raw JSON object. No markdown fences, no commentary outside JSON.\n\n'
    + 'Required JSON structure:\n'
    + '{\n'
    + '  "overall_score": <integer 0-100>,\n'
    + '  "verdict": "<Highly Recommended | Recommended | Consider | Not Recommended>",\n'
    + '  "verdict_explanation": "<2-3 sentences explaining the fit>",\n'
    + '  "dimensions": [\n'
    + '    {"name":"Technical / Functional Skills","score":<0-100>,"note":"<1 sentence>"},\n'
    + '    {"name":"Experience Level","score":<0-100>,"note":"<1 sentence>"},\n'
    + '    {"name":"Industry / Domain Background","score":<0-100>,"note":"<1 sentence>"},\n'
    + '    {"name":"Education & Qualifications","score":<0-100>,"note":"<1 sentence>"},\n'
    + '    {"name":"Leadership & Communication","score":<0-100>,"note":"<1 sentence>"},\n'
    + '    {"name":"Keyword & Requirement Match","score":<0-100>,"note":"<1 sentence>"}\n'
    + '  ],\n'
    + '  "eligibility_bullets": ["<specific evidence-based fit bullet>", "<bullet>", "<bullet>", "<bullet>", "<bullet>"],\n'
    + '  "strengths": ["<strength>", "<strength>", "<strength>"],\n'
    + '  "gaps": ["<gap or concern>", "<gap or concern>", "<gap or concern>"],\n'
    + '  "gap_prep": [{"gap":"<gap label>", "tips":["<specific prep tip>", "<specific prep tip>", "<specific prep tip>"]}],\n'
    + '  "disclaimers": ["<transparent assumption/limitation>", "<disclaimer>", "<disclaimer>"],\n'
    + '  "recommendation": "<Shortlist | Consider with Reservations | Pass>"\n'
    + '}\n\n'
    + 'Scoring rules:\n'
    + '- Use the JD as ground truth. Do not reward unrelated experience just because it sounds senior.\n'
    + '- Cite evidence from the CV in plain language, but do not invent missing skills.\n'
    + '- Factor in hidden/additional remarks when provided.\n'
    + '- If the CV is missing must-have requirements, lower the score and list the gaps clearly.\n'
    + '- Include interview prep tips that help the candidate close gaps before client interview.\n'
    + '- Keep the report recruiter-friendly, not overly academic.\n\n'
    + (remarks ? 'ADDITIONAL CONTEXT / HIDDEN REQUIREMENTS:\n---\n' + remarks + '\n---\n\n' : '')
    + 'JOB DESCRIPTION:\n---\n' + jd + '\n---\n\nCANDIDATE CV:\n---\n' + cv + '\n---';
  try {
    var r = await fetchWithTimeout('/generate-ai', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ api_key: route.api_key, api_key_slot: route.api_key_slot, provider: route.provider, model: route.model, prompt: prompt, max_tokens: 3600, use_tools:false }) }, 180000);
    var d = await r.json().catch(function(){ return {}; });
    if (!r.ok || d.error) {
      recordPaidAiFailure('CV Scoring failed output', d, route.model, route.provider);
      throw new Error(normalizeAiProviderError(d.error || ('API error ' + r.status), route));
    }
    var raw = aiText(d).trim();
    var usage = d.usage || {};
    var cost = responseCost(d, route.model, route.provider);
    var tokens = (usage.input_tokens || 0) + (usage.output_tokens || 0);
    var costText = (cost > 0 ? ('$' + cost.toFixed(4) + ' · ') : '') + tokens.toLocaleString() + ' tokens · ' + providerLabel(d.provider || route.provider, d.model || route.model);
    var result = null;
    try {
      var stripped = raw.replace(/```json/gi,'').replace(/```/g,'').trim();
      var first = stripped.indexOf('{'), last = stripped.lastIndexOf('}');
      if (first < 0 || last <= first) throw new Error('No JSON object found');
      result = normalizeAppraiserResult(JSON.parse(stripped.slice(first, last + 1)));
    } catch(parseErr) {
      _appraiserResult = null;
      _appraiserRawReport = raw || 'No readable report returned.';
      if (body) body.innerHTML = '<div style="padding:18px;color:var(--text1);font-size:13px;line-height:1.6;white-space:pre-wrap;">' + esc(_appraiserRawReport) + '</div>';
      var badge = document.getElementById('appraiserBadge'); if (badge) badge.textContent = 'Review formatting';
      if (costEl) costEl.textContent = costText + ' · review formatting';
      statsRecord('CV Scoring — JD vs CV Score (format review)', 'appraiser', cost, d.model || route.model, '', d.provider || route.provider, statsMetaFromResponse(d, route.model, route.provider));
      if (copyBtn) copyBtn.style.display = '';
      if (wordBtn) wordBtn.style.display = '';
      if (pdfBtn) pdfBtn.style.display = '';
      markTabDone('appraiser', run);
      showToast('CV Scoring generated — review formatting', 'info');
      return;
    }
    _appraiserResult = result;
    _appraiserRawReport = null;
    renderAppraiserResult(result);
    if (costEl) costEl.textContent = costText;
    statsRecord('CV Scoring — JD vs CV Score', 'appraiser', cost, d.model || route.model, '', d.provider || route.provider, statsMetaFromResponse(d, route.model, route.provider));
    if (copyBtn) copyBtn.style.display = '';
    if (wordBtn) wordBtn.style.display = '';
    if (pdfBtn) pdfBtn.style.display = '';
    markTabDone('appraiser', run);
    showToast('CV Scoring completed: ' + result.overall_score + '/100', 'ok');
  } catch(e) {
    if (body) body.innerHTML = providerDownAlertHtml(e.message || 'CV Scoring failed');
    markTabFailed('appraiser', run);
    showToast('CV Scoring failed: ' + (e.message || 'Unknown error').split('\n')[0], 'err');
  } finally {
    if (btn) btn.disabled = false;
  }
}
function renderAppraiserResult(r) {
  r = normalizeAppraiserResult(r);
  var sc = Number(r.overall_score || 0);
  var sClass = sc >= 70 ? 's-high' : sc >= 45 ? 's-mid' : 's-low';
  var reco = r.recommendation || (sc >= 70 ? 'Shortlist' : sc >= 45 ? 'Consider with Reservations' : 'Pass');
  var recoClass = reco === 'Shortlist' ? 'shortlist' : reco === 'Consider with Reservations' ? 'consider' : 'pass';
  var dims = (r.dimensions || []).map(function(d){
    var ds = Number(d.score || 0); var c = ds >= 70 ? 'c-high' : ds >= 45 ? 'c-mid' : 'c-low';
    return '<div><div class="appraiser-dim-meta"><span class="appraiser-dim-name">' + esc(d.name) + '</span><span class="appraiser-dim-score">' + ds + '/100</span></div><div class="appraiser-bar-bg"><div class="appraiser-bar-fill ' + c + '" style="width:' + Math.max(0, Math.min(100, ds)) + '%"></div></div><div class="appraiser-dim-note">' + esc(d.note || '') + '</div></div>';
  }).join('');
  function list(arr){ return appraiserAsArray(arr).map(function(x){ return '<li>' + esc(x) + '</li>'; }).join(''); }
  var prep = (Array.isArray(r.gap_prep) ? r.gap_prep : []).map(function(gp){ return '<div class="appraiser-gap-prep"><div class="appraiser-gap-name">✗ ' + esc(gp.gap || 'Gap') + '</div><ul class="appraiser-list">' + list(gp.tips || []) + '</ul></div>'; }).join('');
  var body = document.getElementById('appraiserBody');
  var badge = document.getElementById('appraiserBadge');
  if (badge) badge.textContent = sc + '/100';
  if (!body) return;
  body.innerHTML = ''
    + '<div class="appraiser-score-wrap"><div class="appraiser-score-circle ' + sClass + '"><div class="appraiser-score-num">' + sc + '</div><div class="appraiser-score-label">/ 100</div></div><div><div class="appraiser-verdict-title">' + esc(r.verdict) + '</div><div class="appraiser-verdict-body">' + esc(r.verdict_explanation) + '</div></div></div>'
    + (dims ? '<div class="appraiser-dim-list">' + dims + '</div>' : '')
    + (r.eligibility_bullets.length ? '<div class="appraiser-section"><div class="appraiser-section-title">Eligibility Summary</div><ul class="appraiser-list">' + list(r.eligibility_bullets) + '</ul></div>' : '')
    + '<div class="appraiser-sg"><div><div class="appraiser-section-title">Key Strengths</div><ul class="appraiser-list">' + list(r.strengths) + '</ul></div><div><div class="appraiser-section-title">Gaps / Concerns</div><ul class="appraiser-list">' + list(r.gaps) + '</ul></div></div>'
    + (prep ? '<div class="appraiser-section"><div class="appraiser-section-title">How Candidate Can Address Gaps</div>' + prep + '</div>' : '')
    + (r.disclaimers.length ? '<div class="appraiser-section"><div class="appraiser-section-title">Transparency Disclaimers</div><ul class="appraiser-list">' + list(r.disclaimers) + '</ul></div>' : '')
    + '<div class="appraiser-footer"><span style="font-size:12px;color:var(--text3);">Recommendation:</span><span class="appraiser-reco ' + recoClass + '">' + esc(reco) + '</span><span style="margin-left:auto;font-size:11px;color:var(--text3);">Generated ' + new Date().toLocaleString('en-MY') + '</span></div>';
}
function buildAppraiserPlainText(r) {
  r = normalizeAppraiserResult(r || _appraiserResult);
  var lines = [];
  lines.push('APPRAISER — JD VS CV SCORE');
  lines.push('Overall Score: ' + r.overall_score + '/100 — ' + r.verdict);
  lines.push('Recommendation: ' + r.recommendation);
  lines.push('');
  lines.push(r.verdict_explanation || '');
  lines.push('');
  lines.push('DIMENSIONS');
  (r.dimensions || []).forEach(function(d){ lines.push('- ' + d.name + ': ' + d.score + '/100 — ' + d.note); });
  if (r.eligibility_bullets.length) { lines.push('', 'ELIGIBILITY SUMMARY'); r.eligibility_bullets.forEach(function(b){ lines.push('- ' + b); }); }
  if (r.strengths.length) { lines.push('', 'KEY STRENGTHS'); r.strengths.forEach(function(b){ lines.push('- ' + b); }); }
  if (r.gaps.length) { lines.push('', 'GAPS / CONCERNS'); r.gaps.forEach(function(b){ lines.push('- ' + b); }); }
  if (r.gap_prep.length) { lines.push('', 'HOW CANDIDATE CAN ADDRESS GAPS'); r.gap_prep.forEach(function(gp){ lines.push('Gap: ' + (gp.gap || '')); appraiserAsArray(gp.tips).forEach(function(t){ lines.push('  - ' + t); }); }); }
  if (r.disclaimers.length) { lines.push('', 'DISCLAIMERS'); r.disclaimers.forEach(function(b){ lines.push('- ' + b); }); }
  return lines.join('\n');
}
function copyAppraiserReport() {
  if (!_appraiserResult && !_appraiserRawReport) { showToast('Run CV Scoring first', 'err'); return; }
  if (!_appraiserResult && _appraiserRawReport) {
    var rawPlain = String(_appraiserRawReport || '');
    if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(rawPlain).then(function(){ showToast('CV Scoring report copied', 'ok'); }).catch(function(){ showToast('Copy failed', 'err'); }); return; }
  }
  var body = document.getElementById('appraiserBody');
  var plain = buildAppraiserPlainText(_appraiserResult);
  var html = body ? '<meta charset="utf-8"><div style="font-family:Calibri,Arial,sans-serif;font-size:11pt;">' + body.innerHTML + '</div>' : '<pre>' + esc(plain) + '</pre>';
  try {
    if (navigator.clipboard && window.ClipboardItem) {
      navigator.clipboard.write([new ClipboardItem({ 'text/html': new Blob([html], {type:'text/html'}), 'text/plain': new Blob([plain], {type:'text/plain'}) })]).then(function(){ showToast('CV Scoring report copied', 'ok'); }).catch(function(){ navigator.clipboard.writeText(plain); showToast('CV Scoring report copied as text', 'ok'); });
      return;
    }
  } catch(e) {}
  if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(plain).then(function(){ showToast('CV Scoring report copied', 'ok'); }).catch(function(){ showToast('Copy failed', 'err'); }); return; }
  try {
    var ta = document.createElement('textarea'); ta.value = plain; ta.style.position = 'fixed'; ta.style.left = '-9999px'; document.body.appendChild(ta); ta.focus(); ta.select();
    document.execCommand('copy'); document.body.removeChild(ta); showToast('CV Scoring report copied', 'ok');
  } catch(e) { showToast('Copy failed', 'err'); }
}

function buildAppraiserWordBody(r) {
  r = normalizeAppraiserResult(r || _appraiserResult);
  function list(label, arr) {
    arr = appraiserAsArray(arr);
    return arr.length ? '<h2>' + _escDoc(label) + '</h2><ul>' + arr.map(function(b){ return '<li>' + _escDoc(b) + '</li>'; }).join('') + '</ul>' : '';
  }
  var dims = appraiserAsArray(r.dimensions).length ? '<h2>Dimension Scores</h2><table style="width:100%;border-collapse:collapse;margin:8px 0 18px;">'
    + '<tr><th style="text-align:left;border:1px solid #e5e7eb;padding:7px;background:#f8f9fc;">Dimension</th><th style="text-align:left;border:1px solid #e5e7eb;padding:7px;background:#f8f9fc;width:90px;">Score</th><th style="text-align:left;border:1px solid #e5e7eb;padding:7px;background:#f8f9fc;">Notes</th></tr>'
    + (r.dimensions || []).map(function(d){ return '<tr><td style="border:1px solid #e5e7eb;padding:7px;">' + _escDoc(d.name) + '</td><td style="border:1px solid #e5e7eb;padding:7px;">' + _escDoc(d.score + '/100') + '</td><td style="border:1px solid #e5e7eb;padding:7px;">' + _escDoc(d.note || '') + '</td></tr>'; }).join('')
    + '</table>' : '';
  var prep = (r.gap_prep || []).length ? '<h2>How Candidate Can Address Gaps</h2>' + (r.gap_prep || []).map(function(gp){
    return '<p style="margin:10px 0 4px;font-weight:700;color:#991b1b;">' + _escDoc(gp.gap || 'Gap') + '</p><ul>' + appraiserAsArray(gp.tips).map(function(t){ return '<li>' + _escDoc(t) + '</li>'; }).join('') + '</ul>';
  }).join('') : '';
  return ''
    + '<div class="callout"><h2 style="margin-top:0;border-bottom:0;padding-bottom:0">Overall Score</h2><p style="font-size:18pt;font-weight:700;color:#352a86;margin:0 0 6px;">' + _escDoc(r.overall_score + '/100') + '</p><p><strong>' + _escDoc(r.verdict) + '</strong> · Recommendation: <strong>' + _escDoc(r.recommendation) + '</strong></p><p>' + _escDoc(r.verdict_explanation || '') + '</p></div>'
    + dims
    + list('Eligibility Summary', r.eligibility_bullets)
    + list('Key Strengths', r.strengths)
    + list('Gaps / Concerns', r.gaps)
    + prep
    + list('Transparency Disclaimers', r.disclaimers);
}
function exportAppraiserWord() {
  if (!_appraiserResult && !_appraiserRawReport) { showToast('Run CV Scoring first', 'err'); return; }
  if (!_appraiserResult && _appraiserRawReport) {
    var rawHtml = '<pre style="white-space:pre-wrap;font-family:Calibri,Arial,sans-serif;font-size:11pt;line-height:1.55;">' + _escDoc(_appraiserRawReport) + '</pre>';
    var rawDoc = _wordDocShell('CV Scoring Report', 'Review formatting', rawHtml);
    exportWordDocument(rawDoc, 'cv-scoring-report-review-formatting');
    showToast('CV Scoring Word report exported', 'ok');
    return;
  }
  var r = normalizeAppraiserResult(_appraiserResult);
  var html = _wordDocShell('CV Scoring Report', 'JD vs CV Compatibility · Score ' + r.overall_score + '/100 · ' + r.recommendation, buildAppraiserWordBody(r));
  exportWordDocument(html, 'cv-scoring-report');
  showToast('CV Scoring Word report exported', 'ok');
}
function exportAppraiserPDF() {
  if (!_appraiserResult && !_appraiserRawReport) { showToast('Run CV Scoring first', 'err'); return; }
  if (!(window.jspdf && window.jspdf.jsPDF)) {
    if (window.cvStudioLoadJSPDF) window.cvStudioLoadJSPDF(exportAppraiserPDF, function() { showToast('PDF library not loaded — try Word export instead', 'err'); });
    else showToast('PDF library not loaded — try Word export instead', 'err');
    return;
  }
  if (!_appraiserResult && _appraiserRawReport) {
    var RawPDF = window.jspdf.jsPDF; var rawDoc = new RawPDF({unit:'mm', format:'a4'});
    var rawMargin = 18, rawY = 20, rawMaxW = 174, rawLH = 5.3;
    try { rawDoc.addImage(HYPPIES_LOGO_URI, 'JPEG', rawMargin, 8, 18, 18); } catch(e) {}
    rawDoc.setFont('helvetica','bold'); rawDoc.setFontSize(15); rawDoc.text('CV Scoring Report', rawMargin + 24, 16); rawY = 28;
    rawDoc.setFont('helvetica','normal'); rawDoc.setFontSize(9);
    cvPdfSafeText(_appraiserRawReport || '').split(/\r?\n/).forEach(function(line){
      var parts = rawDoc.splitTextToSize(line || ' ', rawMaxW);
      if (rawY + parts.length * rawLH > 278) { rawDoc.addPage(); rawY = 20; }
      rawDoc.text(parts, rawMargin, rawY); rawY += Math.max(1, parts.length) * rawLH;
    });
    rawDoc.save('cv-scoring-report-review-formatting-' + new Date().toISOString().slice(0,10) + '.pdf');
    showToast('CV Scoring PDF exported', 'ok');
    return;
  }
  var r = normalizeAppraiserResult(_appraiserResult);
  var jsPDF = window.jspdf.jsPDF;
  var doc = new jsPDF({unit:'mm', format:'a4'});
  var margin = 18, pageW = 210, maxW = pageW - margin * 2, y = 18, lh = 5.4;
  var C = { purple:[53,42,134], text:[25,27,34], muted:[92,99,115], dim:[145,151,165], hair:[226,229,236], green:[22,101,52], amber:[146,64,14], red:[153,27,27], soft:[248,249,252] };
  function safe(s){ return cvPdfSafeText(s); }
  function check(n){ if (y + (n || 12) > 278) { doc.addPage(); pageHead(); y = 24; } }
  function pageHead(){ doc.setFillColor(255,255,255); doc.rect(0,0,210,16,'F'); try{ doc.addImage(HYPPIES_LOGO_URI,'JPEG',margin,4,9,9); }catch(e){} doc.setFont('helvetica','bold'); doc.setFontSize(7.5); doc.setTextColor(...C.purple); doc.text('Hyppies', margin+13, 9.5); doc.setFont('helvetica','normal'); doc.setFontSize(7); doc.setTextColor(...C.dim); doc.text(new Date().toLocaleDateString('en-MY'), pageW-margin, 9.5, {align:'right'}); doc.setDrawColor(...C.hair); doc.line(margin,15,pageW-margin,15); }
  function split(t,w,style,size){ doc.setFont('helvetica',style||'normal'); doc.setFontSize(size||9); return doc.splitTextToSize(safe(t), w || maxW); }
  function para(t, col){ if(!t) return; var lines = split(t, maxW, 'normal', 9); check(lines.length*lh+3); doc.setFont('helvetica','normal'); doc.setFontSize(9); doc.setTextColor(...(col||C.text)); doc.text(lines, margin, y); y += lines.length*lh + 3; }
  function sec(t){ check(14); y += 3; doc.setFillColor(...C.soft); doc.roundedRect(margin-1, y-5, maxW+2, 8, 2, 2, 'F'); doc.setFont('helvetica','bold'); doc.setFontSize(8); doc.setTextColor(...C.purple); doc.text(safe(t).toUpperCase(), margin+2, y+0.8); y += 10; }
  function bullet(t){ var lines = split(t, maxW-8, 'normal', 8.8); check(lines.length*lh+3); doc.setFillColor(...C.purple); doc.circle(margin+2, y-1, 1, 'F'); doc.setFont('helvetica','normal'); doc.setFontSize(8.8); doc.setTextColor(...C.text); doc.text(lines, margin+7, y); y += lines.length*lh + 2; }
  function list(title, arr){ arr = appraiserAsArray(arr); if(!arr.length) return; sec(title); arr.forEach(bullet); y += 1; }
  // Header
  doc.setFillColor(255,255,255); doc.rect(0,0,210,42,'F');
  try{ doc.addImage(HYPPIES_LOGO_URI,'JPEG',margin,7,22,22); }catch(e){}
  doc.setFont('helvetica','bold'); doc.setFontSize(15); doc.setTextColor(...C.purple); doc.text('CV Scoring Report', margin+29, 15);
  doc.setFont('helvetica','normal'); doc.setFontSize(8); doc.setTextColor(...C.muted); doc.text('JD vs CV Compatibility Report', margin+29, 21);
  doc.setDrawColor(...C.hair); doc.line(margin, 36, pageW-margin, 36); y = 45;
  var sc = Number(r.overall_score || 0); var scoreCol = sc >= 70 ? C.green : sc >= 45 ? C.amber : C.red;
  doc.setFillColor(...C.soft); doc.roundedRect(margin, y-5, maxW, 27, 3, 3, 'F');
  doc.setFont('helvetica','bold'); doc.setFontSize(22); doc.setTextColor(...scoreCol); doc.text(sc + '/100', margin+5, y+8);
  doc.setFont('helvetica','bold'); doc.setFontSize(11); doc.setTextColor(...C.text); doc.text(safe(r.verdict), margin+42, y+4);
  doc.setFont('helvetica','normal'); doc.setFontSize(9); doc.setTextColor(...C.muted); doc.text('Recommendation: ' + safe(r.recommendation), margin+42, y+10);
  y += 30;
  para(r.verdict_explanation || '');
  if ((r.dimensions || []).length) { sec('Dimension Scores'); (r.dimensions || []).forEach(function(d){ check(12); doc.setFont('helvetica','bold'); doc.setFontSize(8.8); doc.setTextColor(...C.text); doc.text(safe(d.name || 'Dimension'), margin, y); doc.setFont('helvetica','normal'); doc.setTextColor(...C.muted); doc.text(safe((d.score || 0) + '/100'), pageW-margin, y, {align:'right'}); y += 5; para(d.note || '', C.muted); }); }
  list('Eligibility Summary', r.eligibility_bullets);
  list('Key Strengths', r.strengths);
  list('Gaps / Concerns', r.gaps);
  if ((r.gap_prep || []).length) { sec('How Candidate Can Address Gaps'); (r.gap_prep || []).forEach(function(gp){ check(8); doc.setFont('helvetica','bold'); doc.setFontSize(8.8); doc.setTextColor(...C.red); doc.text('Gap: ' + safe(gp.gap || ''), margin, y); y += 5; appraiserAsArray(gp.tips).forEach(bullet); }); }
  list('Transparency Disclaimers', r.disclaimers);
  doc.save('cv-scoring-report-' + new Date().toISOString().slice(0,10) + '.pdf');
  showToast('CV Scoring PDF exported', 'ok');
}
function clearAppraiser() {
  clearTabRunState('appraiser');
  ['appraiserJdText','appraiserCvText','appraiserSalary','appraiserSeniority','appraiserIndustry','appraiserHidden'].forEach(function(id){ var el=document.getElementById(id); if(el) el.value=''; });
  ['appraiserJdStatus','appraiserCvStatus','appraiserCost'].forEach(function(id){ var el=document.getElementById(id); if(el) el.textContent=''; });
  ['appraiserJdFile','appraiserCvFile'].forEach(function(id){ var el=document.getElementById(id); if(el) el.value=''; });
  _appraiserPendingFiles = { jd: null, cv: null };
  ['appraiserJdExtractBtn','appraiserCvExtractBtn'].forEach(function(id){ var el=document.getElementById(id); if(el) el.disabled=false; });
  var out = document.getElementById('appraiserOutput'); if (out) out.classList.remove('show');
  var body = document.getElementById('appraiserBody'); if (body) body.innerHTML = '';
  var badge = document.getElementById('appraiserBadge'); if (badge) badge.textContent = '—';
  var copy = document.getElementById('appraiserCopyBtn'); if (copy) copy.style.display = 'none';
  var word = document.getElementById('appraiserWordBtn'); if (word) word.style.display = 'none';
  var pdf = document.getElementById('appraiserPdfBtn'); if (pdf) pdf.style.display = 'none';
  _appraiserResult = null;
  _appraiserRawReport = null;
  updateAppraiserCounts();
}
function initAppraiserTabUI() {
  updateAppraiserRouteBadge();
  updateAppraiserCounts();
}

