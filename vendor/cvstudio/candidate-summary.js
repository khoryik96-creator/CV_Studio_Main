// ── Candidate Summary Generator ─────────────────────────────────────────────
var _summaryFocus = 'general';
window._summaryLastModifier = 'normal';
window._summaryGeneratedBullets = [];
window._summaryGeneratedSource = '';
window._formatSummaryDraft = null;
window._summarySourceDocxFile = null;
window._summarySourceDocxText = '';
function updateSummaryCharCount() {
  var ta = document.getElementById('summaryCvText');
  var el = document.getElementById('summaryCharCount');
  if (ta && el) el.textContent = (ta.value || '').length.toLocaleString() + ' characters';
}
function updateSummaryRouteBadge() {
  var el = document.getElementById('summaryRouteBadge');
  if (!el) return;
  try { var r = resolveAiRoute('summary'); el.textContent = 'Using: ' + r.display; }
  catch(e) { el.textContent = 'Using: —'; }
}
function setSummaryFocus(btn) {
  if (!btn) return;
  document.querySelectorAll('#summaryFocusSection .summary-focus-btn').forEach(function(b){ b.classList.remove('active'); });
  btn.classList.add('active');
  _summaryFocus = btn.getAttribute('data-dir') || 'general';
  var custom = document.getElementById('summaryCustomDir');
  if (custom) custom.style.display = _summaryFocus === 'custom' ? 'block' : 'none';
}
function getSummaryFocusLabel() {
  var map = { general:'General', technology:'Technology', leadership:'Leadership', commercial:'Commercial' };
  if (_summaryFocus === 'custom') { var v = ((document.getElementById('summaryCustomDir') || {}).value || '').trim(); return v ? ('Custom — ' + v) : 'Custom'; }
  return map[_summaryFocus] || 'General';
}
function getSummaryFocusPrompt() {
  var map = {
    general:'',
    technology:'Strongly emphasise technical skills, programming languages, tech stack, engineering achievements, system design, data/AI/cloud/platform work, and software delivery.',
    leadership:'Strongly emphasise leadership roles, team management, mentoring, stakeholder management, organisational impact, people development, and strategic initiatives.',
    commercial:'Strongly emphasise commercial impact, revenue generation, P&L ownership, client relationships, business growth, measurable ROI, and business outcomes.'
  };
  if (_summaryFocus === 'custom') { var v = ((document.getElementById('summaryCustomDir') || {}).value || '').trim(); return v ? ('Strongly emphasise: ' + v + '.') : ''; }
  return map[_summaryFocus] || '';
}
function boldSafeSummary(text) { return esc(text || '').replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>'); }
function summaryBulletLines(raw) {
  raw = String(raw || '').replace(/```(?:text|markdown|md)?/gi,'').replace(/```/g,'').trim();
  var lines = raw.split('\n').map(function(l){ return l.trim(); }).filter(Boolean);
  var bulletLines = lines.filter(function(l){ return /^[-•*]\s+/.test(l); });
  return (bulletLines.length ? bulletLines : lines)
    .map(function(l){ return l.replace(/^[-•*]\s+/, '').trim(); })
    .filter(Boolean)
    .slice(0, 20);
}
function renderSummaryText(raw) {
  var src = summaryBulletLines(raw);
  if (!src.length) src = ['No summary returned. Try regenerating or use a different provider.'];
  return '<ul class="summary-list">' + src.map(function(t){ return '<li>' + boldSafeSummary(t) + '</li>'; }).join('') + '</ul>';
}
function formatSummaryBulletsFor(raw, blind) {
  var draft = window._formatSummaryDraft;
  if (blind || !draft || String(draft.cv_text || '').trim() !== String(raw || '').trim()) return [];
  return (Array.isArray(draft.bullets) ? draft.bullets : [])
    .map(function(value){ return String(value || '').trim(); })
    .filter(Boolean)
    .slice(0, 20);
}
function applyFormatSummaryBullets(data, raw, blind) {
  var bullets = formatSummaryBulletsFor(raw, blind);
  if (data && typeof data === 'object' && bullets.length) data.summary_bullets = bullets.slice();
  return data;
}
function updateFormatSummaryNote() {
  var note = document.getElementById('formatSummaryNote');
  if (!note) return;
  var draft = window._formatSummaryDraft;
  var count = draft && Array.isArray(draft.bullets) ? draft.bullets.length : 0;
  note.style.display = count ? 'block' : 'none';
  note.textContent = count ? ('Using ' + count + ' CV Summary bullet' + (count === 1 ? '' : 's') + ' in the formatted resume Summary placeholder. Editing or clearing the raw CV will unlink them.') : '';
}
function clearFormatSummaryDraft() {
  window._formatSummaryDraft = null;
  updateFormatSummaryNote();
}
function updateSummaryApplyDocxButton() {
  var btn = document.getElementById('btnSummaryApplyDocx');
  if (!btn) return;
  var ta = document.getElementById('summaryCvText');
  var current = ta ? String(ta.value || '').trim() : '';
  var file = window._summarySourceDocxFile;
  var sourceMatches = String(window._summaryGeneratedSource || '').trim() === current;
  var uploadMatches = String(window._summarySourceDocxText || '').trim() === current;
  var hasBullets = Array.isArray(window._summaryGeneratedBullets) && window._summaryGeneratedBullets.length > 0;
  btn.disabled = !(file && /\.docx$/i.test(String(file.name || '')) && sourceMatches && uploadMatches && hasBullets);
}
async function formatSummaryResume() {
  if (!requireSummaryUnlocked()) return;
  var ta = document.getElementById('summaryCvText');
  var cv = ta ? String(ta.value || '').trim() : '';
  var sourceMatches = String(window._summaryGeneratedSource || '').trim() === cv;
  var bullets = sourceMatches && Array.isArray(window._summaryGeneratedBullets) ? window._summaryGeneratedBullets.slice() : [];
  if (!cv) { showToast('Paste or upload a CV first', 'err'); return; }
  if (!bullets.length) { showToast(sourceMatches ? 'Generate a CV Summary first' : 'The CV changed — regenerate its summary first', 'err'); return; }
  window._formatSummaryDraft = { cv_text: cv, bullets: bullets };
  var input = document.getElementById('cvInput');
  if (input) input.value = cv;
  var count = document.getElementById('charCount');
  if (count) count.textContent = cv.length.toLocaleString() + ' characters';
  switchInputTab('paste');
  updateFormatSummaryNote();
  switchTab('format');
  showToast('CV Summary linked to the resume Summary placeholder', 'ok');
  return startFormat(false);
}
async function applySummaryToUploadedDocx() {
  if (!requireSummaryUnlocked()) return;
  var file = window._summarySourceDocxFile;
  var ta = document.getElementById('summaryCvText');
  var current = ta ? String(ta.value || '').trim() : '';
  var sourceMatches = String(window._summaryGeneratedSource || '').trim() === current;
  var uploadMatches = String(window._summarySourceDocxText || '').trim() === current;
  var bullets = sourceMatches && uploadMatches && Array.isArray(window._summaryGeneratedBullets)
    ? window._summaryGeneratedBullets.slice()
    : [];
  if (!file || !/\.docx$/i.test(String(file.name || ''))) {
    showToast('Upload a DOCX in CV Summary first', 'err');
    return;
  }
  if (!bullets.length) {
    showToast('Generate a Summary for the unchanged uploaded DOCX first', 'err');
    return;
  }
  var btn = document.getElementById('btnSummaryApplyDocx');
  if (btn) btn.disabled = true;
  try {
    var fd = new FormData();
    fd.append('source_docx', file, file.name);
    fd.append('summary_bullets', JSON.stringify(bullets));
    var response = await fetchWithTimeout('/generate-docx', { method:'POST', body:fd }, 60000);
    if (!response.ok) {
      var errorPayload = await response.json().catch(function(){ return {}; });
      throw new Error(errorPayload.error || 'Could not update the DOCX');
    }
    var blob = await response.blob();
    var base = String(file.name || 'Hyppies CV.docx').replace(/\.docx$/i, '');
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    link.download = base + ' - Summary.docx';
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function(){ URL.revokeObjectURL(url); }, 1000);
    showToast('Summary placeholder filled in the uploaded DOCX', 'ok');
  } catch(e) {
    showToast('DOCX Summary failed: ' + (e.message || 'Unknown error'), 'err');
  } finally {
    updateSummaryApplyDocxButton();
  }
}
async function handleSummaryFile(file) {
  if (!file) return;
  if (!requireSummaryUnlocked()) return;
  var status = document.getElementById('summaryFileStatus');
  var ta = document.getElementById('summaryCvText');
  var ext = file.name.split('.').pop().toLowerCase();
  var SUPPORTED = ['pdf','docx','doc','txt','rtf','odt','png','jpg','jpeg'];
  if (SUPPORTED.indexOf(ext) < 0) { showToast('Supported: PDF, DOCX, DOC, TXT, RTF, ODT, PNG, JPG, JPEG', 'err'); return; }
  window._summaryGeneratedBullets = [];
  window._summaryGeneratedSource = '';
  window._summarySourceDocxFile = null;
  window._summarySourceDocxText = '';
  var formatBtn = document.getElementById('btnSummaryFormat');
  if (formatBtn) formatBtn.disabled = true;
  updateSummaryApplyDocxButton();
  var run = markTabRunning('summary');
  if (status) status.textContent = 'Extracting ' + file.name + '…';
  try {
    var fd = new FormData(); fd.append('file', file);
    var r = await fetchWithTimeout('/extract-text', { method:'POST', body:fd }, 70000);
    var d = await r.json();
    if (!r.ok || d.error) throw new Error(d.error || 'Extraction failed');
    if (ta) ta.value = d.text || '';
    if (ext === 'docx') {
      window._summarySourceDocxFile = file;
      window._summarySourceDocxText = String(d.text || '').trim();
    }
    updateSummaryCharCount();
    if (status) status.textContent = '✓ ' + file.name + ' (' + (d.text || '').length.toLocaleString() + ' chars extracted)' + (ext === 'docx' ? ' — generated Summary can fill this DOCX placeholder' : '');
    updateSummaryApplyDocxButton();
    markTabDone('summary', run); showToast('CV ready for summary', 'ok');
  } catch(e) {
    if (status) status.textContent = '✗ ' + (e.message || 'Extraction failed');
    markTabFailed('summary', run); showToast('CV Summary extraction failed: ' + (e.message || 'Unknown error'), 'err');
  }
}
function cvSummaryPrompt(cv, modifier, focusNote) {
  modifier = modifier || 'normal';
  var modNote = modifier === 'shorter' ? 'Use exactly 4-5 bullet points.' : modifier === 'longer' ? 'Use 8-10 detailed bullet points with useful metrics where available.' : 'Use 6-7 bullet points.';
  return 'You are a senior recruitment consultant. Produce a professional candidate summary.\n\nRULES:\n- Output ONLY bullet points, no intro, no headers.\n- Every bullet starts with "- ".\n- Bold the most important keyword or phrase per bullet using **double asterisks**.\n- Third-person, professional, concise.\n- Do not invent employers, dates, certifications, industries, metrics, or achievements that are not supported by the CV.\n- Keep the candidate marketable but accurate.\n- ' + modNote + '\n' + (focusNote ? ('- ' + focusNote + '\n') : '') + '\nCV:\n---\n' + cv + '\n---';
}
async function requestFormattingSummary(raw, route) {
  var response = await fetchWithTimeout('/generate-ai', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
      api_key:route.api_key,
      api_key_slot:route.api_key_slot,
      provider:route.provider,
      model:route.model,
      prompt:cvSummaryPrompt(raw, 'normal', ''),
      max_tokens:1000,
      use_tools:false
    })
  }, 180000);
  var data = await response.json().catch(function(){ return {}; });
  if (!response.ok || data.error) {
    recordPaidAiFailure('CV Summary during formatting failed', data, route.model, route.provider);
    throw new Error(normalizeAiProviderError(data.error || ('API error ' + response.status), route));
  }
  var rawSummary = aiText(data);
  var bullets = summaryBulletLines(rawSummary);
  if (!bullets.length) {
    recordPaidAiFailure('CV Summary during formatting returned empty output', data, route.model, route.provider);
    throw new Error('Empty CV Summary returned');
  }
  return {
    bullets:bullets,
    cost:responseCost(data, route.model, route.provider),
    usage:data.usage || {},
    data:data
  };
}
async function generateSummary(modifier) {
  if (!requireSummaryUnlocked()) return;
  modifier = modifier || 'normal'; window._summaryLastModifier = modifier;
  var ta = document.getElementById('summaryCvText'); var cv = ta ? ta.value.trim() : '';
  if (!cv) { showToast('Paste or upload a CV first', 'err'); return; }
  var route = aiRoutePayload('summary');
  if (!route.api_key) { showToast('Save an API key for CV Summary route', 'err'); return; }
  var focusNote = getSummaryFocusPrompt();
  var prompt = cvSummaryPrompt(cv, modifier, focusNote);
  var output = document.getElementById('summaryOutput'), placeholder = document.getElementById('summaryPlaceholder'), costEl = document.getElementById('summaryCost'), btn = document.getElementById('btnSummaryGen');
  var formatBtn = document.getElementById('btnSummaryFormat');
  window._summaryGeneratedBullets = [];
  window._summaryGeneratedSource = '';
  if (formatBtn) formatBtn.disabled = true;
  updateSummaryApplyDocxButton();
  var run = markTabRunning('summary');
  if (output) { output.style.display = 'block'; output.innerHTML = '<div style="display:flex;align-items:center;gap:10px;color:var(--text3);"><span class="spinner"></span><span>Generating summary with ' + esc(route.display) + '…</span></div>'; }
  if (placeholder) placeholder.style.display = 'none'; if (btn) btn.disabled = true; updateSummaryRouteBadge();
  try {
    var r = await fetchWithTimeout('/generate-ai', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ api_key: route.api_key, api_key_slot: route.api_key_slot, provider: route.provider, model: route.model, prompt: prompt, max_tokens: modifier === 'longer' ? 1600 : 1000, use_tools:false }) }, 180000);
    var d = await r.json().catch(function(){ return {}; });
    if (!r.ok || d.error) {
      recordPaidAiFailure('CV Summary failed output', d, route.model, route.provider);
      throw new Error(normalizeAiProviderError(d.error || ('API error ' + r.status), route));
    }
    var raw = aiText(d);
    if (!raw) {
      recordPaidAiFailure('CV Summary returned empty output', d, route.model, route.provider);
      throw new Error('Empty summary returned');
    }
    window._summaryGeneratedBullets = summaryBulletLines(raw);
    window._summaryGeneratedSource = cv;
    if (!window._summaryGeneratedBullets.length) throw new Error('Empty summary returned');
    if (output) output.innerHTML = renderSummaryText(raw);
    if (formatBtn) formatBtn.disabled = !ta || String(ta.value || '').trim() !== cv;
    updateSummaryApplyDocxButton();
    var usage = normalizeUsageClient(d.usage || {}); var cost = responseCost(d, route.model, route.provider);
    if (costEl) costEl.textContent = (cost > 0 ? ('$' + cost.toFixed(4) + ' · ') : '') + ((usage.input_tokens || 0) + (usage.output_tokens || 0)).toLocaleString() + ' tokens · ' + providerLabel(d.provider || route.provider, d.model || route.model);
    statsRecord('CV Summary — ' + getSummaryFocusLabel(), 'summary', cost, d.model || route.model, '', d.provider || route.provider, statsMetaFromResponse(d, route.model, route.provider));
    markTabDone('summary', run); showToast('CV Summary generated', 'ok');
  } catch(e) {
    if (output) output.innerHTML = '<div style="color:var(--red);font-size:13px;line-height:1.5;">⚠ ' + esc(e.message || 'CV Summary failed') + '</div>';
    markTabFailed('summary', run); showToast('CV Summary failed: ' + (e.message || 'Unknown error').split('\n')[0], 'err');
  } finally { if (btn) btn.disabled = false; }
}
function initSummaryTabUI() {
  try {
    updateSummaryLockUI();
    updateSummaryRouteBadge();
    var ta = document.getElementById('summaryCvText');
    if (ta && !ta._summaryCharCountBound) {
      ta.addEventListener('input', function(){
        updateSummaryCharCount();
        window._summaryGeneratedBullets = [];
        window._summaryGeneratedSource = '';
        if (window._summarySourceDocxFile && String(ta.value || '').trim() !== String(window._summarySourceDocxText || '').trim()) {
          window._summarySourceDocxFile = null;
          window._summarySourceDocxText = '';
          var status = document.getElementById('summaryFileStatus');
          if (status) status.textContent = 'DOCX link cleared because the extracted CV text was edited. Re-upload the DOCX to fill its Summary placeholder.';
        }
        var formatBtn = document.getElementById('btnSummaryFormat');
        if (formatBtn) formatBtn.disabled = true;
        updateSummaryApplyDocxButton();
      });
      ta._summaryCharCountBound = true;
    }
    updateSummaryCharCount();
  } catch(e) {}
}
function suppressSummaryTabAutoCaret() {
  // v24.6.66: opening CV Summary should not leave a blinking text caret
  // in the empty textarea/input. Users can still click/type normally after the tab is open.
  try {
    setTimeout(function(){
      var view = document.getElementById('viewSummary');
      if (!view || !view.classList.contains('active')) return;
      var ae = document.activeElement;
      if (ae && view.contains(ae) && /^(TEXTAREA|INPUT)$/i.test(ae.tagName || '')) ae.blur();
    }, 0);
  } catch(e) {}
}
function fallbackCopyRichSummary(el, plainText) {
  try {
    var sel = window.getSelection();
    var prevRanges = [];
    if (sel) {
      for (var i = 0; i < sel.rangeCount; i++) prevRanges.push(sel.getRangeAt(i).cloneRange());
      sel.removeAllRanges();
      var range = document.createRange();
      range.selectNodeContents(el);
      sel.addRange(range);
    }
    var ok = document.execCommand && document.execCommand('copy');
    if (sel) {
      sel.removeAllRanges();
      prevRanges.forEach(function(r){ sel.addRange(r); });
    }
    if (ok) { showToast('CV Summary copied with formatting', 'ok'); return; }
  } catch(e) {}
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(plainText).then(function(){ showToast('CV Summary copied as plain text', 'ok'); }).catch(function(){ showToast('Copy failed', 'err'); });
  } else {
    showToast('Copy failed', 'err');
  }
}
async function copySummaryOutput() {
  if (!requireSummaryUnlocked()) return;
  var el = document.getElementById('summaryOutput');
  if (!el || el.style.display === 'none' || !el.innerText.trim()) { showToast('Generate a summary first', 'err'); return; }
  var plain = el.innerText.trim();
  var html = '<meta charset="utf-8"><div>' + el.innerHTML + '</div>';
  try {
    if (navigator.clipboard && window.ClipboardItem) {
      await navigator.clipboard.write([new ClipboardItem({
        'text/html': new Blob([html], { type: 'text/html' }),
        'text/plain': new Blob([plain], { type: 'text/plain' })
      })]);
      showToast('CV Summary copied with bold formatting', 'ok');
      return;
    }
  } catch(e) {
    // Fall through to selection-based rich-copy fallback.
  }
  fallbackCopyRichSummary(el, plain);
}
function clearSummaryTab() {
  if (!requireSummaryUnlocked()) return;
  clearTabRunState('summary');
  var f = document.getElementById('summaryFileInput'); if (f) f.value = '';
  var s = document.getElementById('summaryFileStatus'); if (s) s.textContent = '';
  var t = document.getElementById('summaryCvText'); if (t) t.value = '';
  var o = document.getElementById('summaryOutput'); if (o) { o.style.display = 'none'; o.innerHTML = ''; }
  var p = document.getElementById('summaryPlaceholder'); if (p) p.style.display = 'flex';
  var c = document.getElementById('summaryCost'); if (c) c.textContent = '';
  window._summaryGeneratedBullets = [];
  window._summaryGeneratedSource = '';
  window._summarySourceDocxFile = null;
  window._summarySourceDocxText = '';
  var formatBtn = document.getElementById('btnSummaryFormat'); if (formatBtn) formatBtn.disabled = true;
  updateSummaryApplyDocxButton();
  clearFormatSummaryDraft();
  updateSummaryCharCount();
}
