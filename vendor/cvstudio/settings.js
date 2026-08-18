// ── Settings panel toggle ────────────────────────────────────────
function ensureSettingsPanelTopLayer() {
  var panel = document.getElementById('settingsPanel');
  if (panel && panel.parentElement !== document.body) document.body.appendChild(panel);
  var backdrop = document.getElementById('settingsBackdrop');
  if (!backdrop) {
    backdrop = document.createElement('div');
    backdrop.id = 'settingsBackdrop';
    backdrop.setAttribute('aria-hidden','true');
    backdrop.onclick = closeSettingsPanel;
    document.body.insertBefore(backdrop, document.body.firstChild);
  }
  return panel;
}
function closeSettingsPanel() {
  var panel = document.getElementById('settingsPanel');
  var backdrop = document.getElementById('settingsBackdrop');
  if (panel) panel.style.display = 'none';
  if (backdrop) backdrop.style.display = 'none';
  if (document.body) document.body.classList.remove('settings-open');
}
function toggleSettings() {
  var panel = ensureSettingsPanelTopLayer();
  if (!panel) return;
  var backdrop = document.getElementById('settingsBackdrop');
  var opening = panel.style.display === 'none' || panel.style.display === '';
  panel.style.display = opening ? 'block' : 'none';
  if (backdrop) backdrop.style.display = opening ? 'block' : 'none';
  if (document.body) document.body.classList.toggle('settings-open', opening);
  if (opening) {
    // Route rows are critical settings controls. Render them lazily on open as
    // well as on page load so they cannot disappear if the load restore path
    // aborts early or the browser opens Settings before the load handler runs.
    ensureAiRoutingRowsVisible();
    setTimeout(ensureAiRoutingRowsVisible, 0);
  }
}
// Close settings when clicking outside
document.addEventListener('click', function(e) {
  var panel = document.getElementById('settingsPanel');
  var btn   = document.getElementById('btnSettingsToggle');
  if (panel && panel.style.display === 'block' && !panel.contains(e.target) && e.target !== btn && !(btn && btn.contains && btn.contains(e.target))) {
    closeSettingsPanel();
  }
});
document.addEventListener('keydown', function(e) {
  if (e && (e.ctrlKey || e.metaKey) && String(e.key || '').toLowerCase() === 'f') {
    var spiderView=document.getElementById('viewTheSpider');
    var spiderPreview=document.getElementById('theSpiderCvPreview');
    if(spiderView&&spiderView.classList.contains('active')&&spiderPreview&&window._theSpiderPreviewSearchText){
      e.preventDefault();
      openTheSpiderPreviewFind();
      return;
    }
  }
  if (e && e.key === 'Escape') {
    var spiderFind=document.getElementById('theSpiderPreviewFind');
    var spiderFindInput=document.getElementById('theSpiderPreviewFindInput');
    if(spiderFind&&(window._theSpiderPreviewMode==='text'||(spiderFindInput&&String(spiderFindInput.value||'').trim()))){closeTheSpiderPreviewFind();return;}
    var invoiceModal=document.getElementById('ppcInvoicePreviewModal');
    if(invoiceModal&&invoiceModal.classList.contains('open')){ppcCloseInvoicePreview();return;}
    closeSettingsPanel();
  }
});


document.addEventListener('DOMContentLoaded', function(){ ensureSettingsPanelTopLayer(); applyBackgroundSettings(backgroundLoadSettings()); renderBackgroundSettings(); });

// ── Read-only caret guard ──────────────────────────────────────────
function cvIsTextEntryTarget(el) {
  try {
    if (!el || !el.closest) return false;
    var entry = el.closest('textarea,input,select,[contenteditable="true"],[contenteditable="plaintext-only"]');
    if (!entry) return false;
    var tag = String(entry.tagName || '').toUpperCase();
    if (tag === 'INPUT') {
      var type = String(entry.getAttribute('type') || 'text').toLowerCase();
      return !/^(button|submit|reset|checkbox|radio|file|range|color|image|hidden)$/i.test(type);
    }
    return true;
  } catch(e) { return false; }
}
function cvIsTextEntryElement(el) {
  try {
    if (!el) return false;
    var tag = String(el.tagName || '').toUpperCase();
    if (tag === 'TEXTAREA' || tag === 'SELECT') return true;
    if (tag === 'INPUT') {
      var type = String(el.getAttribute('type') || 'text').toLowerCase();
      return !/^(button|submit|reset|checkbox|radio|file|range|color|image|hidden)$/i.test(type);
    }
    return el.isContentEditable === true;
  } catch(e) { return false; }
}
function cvIsSelectableTextTarget(el) {
  try {
    if (!el || !el.closest) return false;
    return !!el.closest('#summaryOutput,.summary-output-scroll,.output-box,.preview-box,.generated-output,.appraiser-output,.owl-report-body,.spider-notes-body,#theSpiderPreviewTextPane,#theSpiderPreviewSearchDoc,#theSpiderPreviewVisualPane,.spider-preview-text-pane,.spider-preview-search-paper,.spider-cv-search-render,.spider-preview-frame-wrap,.spider-cv-preview-page-wrap,.spider-visual-text-layer,.spider-visual-text-word,.lead-summary-card');
  } catch(e) { return false; }
}
function cvClearStrayCaret(e) {
  try {
    var target = e && e.target;
    if (cvIsTextEntryTarget(target) || cvIsSelectableTextTarget(target)) return;
    var ae = document.activeElement;
    if (cvIsTextEntryElement(ae)) ae.blur();
    setTimeout(function(){
      try {
        var ae2 = document.activeElement;
        if (cvIsTextEntryElement(ae2) && !cvIsTextEntryTarget(document.activeElement)) ae2.blur();
        var sel = window.getSelection && window.getSelection();
        if (sel && sel.rangeCount && sel.isCollapsed && !cvIsTextEntryTarget(target) && !cvIsSelectableTextTarget(target)) sel.removeAllRanges();
      } catch(_e) {}
    }, 0);
  } catch(e2) {}
}
function initCvReadonlyCaretGuard() {
  try { if (document.body) document.body.classList.add('cv-caret-guard'); } catch(e) {}
  try { document.addEventListener('pointerdown', cvClearStrayCaret, true); } catch(e) {}
  try { document.addEventListener('mousedown', cvClearStrayCaret, true); } catch(e) {}
}
document.addEventListener('DOMContentLoaded', initCvReadonlyCaretGuard);

// ── Formatted CV paragraph alignment ─────────────────────────────
var CV_TEXT_ALIGNMENT_STORE = 'cvstudio_cv_text_alignment_v1';
window._cvTextAlignment = 'left';

function normalizeCvTextAlignment(value) {
  return String(value || '').toLowerCase() === 'justify' ? 'justify' : 'left';
}
function getCvTextAlignment() {
  return normalizeCvTextAlignment(window._cvTextAlignment);
}
function renderCvTextAlignmentSetting() {
  var value = getCvTextAlignment();
  var left = document.getElementById('cvTextAlignLeft');
  var justify = document.getElementById('cvTextAlignJustify');
  [left, justify].forEach(function(btn){
    if (!btn) return;
    var active = (btn === left && value === 'left') || (btn === justify && value === 'justify');
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    btn.style.background = active ? 'var(--blue)' : 'var(--surface)';
    btn.style.borderColor = active ? 'var(--blue)' : 'var(--border)';
    btn.style.color = active ? '#ffffff' : 'var(--text2)';
    btn.style.boxShadow = active ? '0 3px 9px rgba(37,99,235,.16)' : 'none';
  });
  var sample=document.getElementById('cvAlignmentPreviewBody');
  if(sample){sample.style.textAlign=value==='justify'?'justify':'left';sample.style.textAlignLast='left';}
}
function setCvTextAlignment(value, silent) {
  value = normalizeCvTextAlignment(value);
  window._cvTextAlignment = value;
  try { cvStudioDurableSettingSet(CV_TEXT_ALIGNMENT_STORE, value); } catch(e) {}
  renderCvTextAlignmentSetting();
  if (!silent) showToast(value === 'justify' ? 'Substantive CV body text and bullets will be justified; headings remain left-aligned.' : 'Formatted CV text will align left.', 'ok');
  return value;
}
(function restoreCvTextAlignment(){
  var stored = 'left';
  try { stored = localStorage.getItem(CV_TEXT_ALIGNMENT_STORE) || 'left'; } catch(e) {}
  window._cvTextAlignment = normalizeCvTextAlignment(stored);
  setTimeout(renderCvTextAlignmentSetting, 0);
})();
document.addEventListener('DOMContentLoaded', renderCvTextAlignmentSetting);

var CV_SUMMARY_BOX_AUTO_FIT_STORE = 'cvstudio_summary_box_autofit_v1';
window._cvSummaryBoxAutoFit = true;

function getCvSummaryBoxAutoFit() {
  return window._cvSummaryBoxAutoFit !== false;
}
function renderCvSummaryBoxAutoFitSetting() {
  var enabled = getCvSummaryBoxAutoFit();
  var checkbox = document.getElementById('cvSummaryBoxAutoFitToggle');
  var label = document.getElementById('cvSummaryBoxAutoFitLabel');
  if (checkbox) checkbox.checked = enabled;
  if (label) label.textContent = enabled ? 'On' : 'Off';
}
function setCvSummaryBoxAutoFit(enabled, silent) {
  window._cvSummaryBoxAutoFit = enabled !== false;
  try { cvStudioDurableSettingSet(CV_SUMMARY_BOX_AUTO_FIT_STORE, getCvSummaryBoxAutoFit() ? 'true' : 'false'); } catch(e) {}
  renderCvSummaryBoxAutoFitSetting();
  if (!silent) showToast(getCvSummaryBoxAutoFit() ? 'Summary boxes will grow up to the safe page-one maximum.' : 'Summary boxes will keep the template size.', 'ok');
  return getCvSummaryBoxAutoFit();
}
(function restoreCvSummaryBoxAutoFit(){
  var stored = null;
  try { stored = localStorage.getItem(CV_SUMMARY_BOX_AUTO_FIT_STORE); } catch(e) {}
  window._cvSummaryBoxAutoFit = stored !== 'false';
  setTimeout(renderCvSummaryBoxAutoFitSetting, 0);
})();
document.addEventListener('DOMContentLoaded', renderCvSummaryBoxAutoFitSetting);

// ── Gender-neutral summary language ──────────────────────────────────────────
// When enabled, the auto-generated CV Summary (the "ABOUT HIM / HER" section)
// refers to the person as "the candidate" instead of he/she/him/her/his/hers,
// for both single and batch Format CV. Deliberately NOT "they/them". The
// "ABOUT HIM / HER" heading is template text (never part of summary_bullets), so
// it is left untouched. This is a deterministic pass over the summary bullets.
var CV_GENDER_NEUTRAL_STORE = 'cvstudio_gender_neutral_summary_v1';
window._cvGenderNeutralSummary = false;

function getCvGenderNeutralSummary() {
  return window._cvGenderNeutralSummary === true;
}
// Preserve the original pronoun's leading capitalisation on the replacement so
// a sentence-initial "He" becomes "The candidate", not "the candidate".
function cvMatchLeadingCase(replacement, original) {
  return /^[A-Z]/.test(String(original || ''))
    ? replacement.charAt(0).toUpperCase() + replacement.slice(1)
    : replacement;
}
function cvNeutralizeCandidatePronouns(text) {
  var s = String(text == null ? '' : text);
  if (!s) return s;
  // Expand he/she contractions first so a rewritten pronoun does not leave a
  // dangling suffix ("He'll" -> "The candidate'll"). Straight and curly quotes
  // both count. 's/'d take their most common recruiting-summary sense (is/had);
  // the "has"/"would" senses are rarer and read acceptably either way.
  s = s.replace(/\b(?:he|she)['’]ll\b/gi, function(m){ return cvMatchLeadingCase('the candidate will', m); });
  s = s.replace(/\b(?:he|she)['’]d\b/gi, function(m){ return cvMatchLeadingCase('the candidate had', m); });
  s = s.replace(/\b(?:he|she)['’]s\b/gi, function(m){ return cvMatchLeadingCase('the candidate is', m); });
  // "her" is both possessive ("her role") and object ("assisted her"). Treat a
  // "her" directly followed by another word as possessive -> "the candidate's";
  // a "her" at a clause end / before punctuation is the object -> "the candidate".
  s = s.replace(/\bher\b(?=\s+[A-Za-z])/gi, function(m){ return cvMatchLeadingCase("the candidate's", m); });
  s = s.replace(/\bher\b/gi, function(m){ return cvMatchLeadingCase('the candidate', m); });
  var map = {
    himself: 'the candidate',
    herself: 'the candidate',
    hers: "the candidate's",
    his: "the candidate's",
    him: 'the candidate',
    she: 'the candidate',
    he: 'the candidate'
  };
  // Longest-first so "herself"/"himself" win before "he"/"his" prefixes. The
  // \b anchors already prevent matching inside "the"/"This"/"ashen" etc.
  s = s.replace(/\b(himself|herself|hers|his|him|she|he)\b/gi, function(m){
    var repl = map[m.toLowerCase()];
    return repl ? cvMatchLeadingCase(repl, m) : m;
  });
  return s;
}
// Apply the neutraliser to a list of summary bullets only when the toggle is on.
// Returns a new array; the input is never mutated.
function cvNeutralizeSummaryBullets(bullets) {
  if (!getCvGenderNeutralSummary()) return bullets;
  return (Array.isArray(bullets) ? bullets : []).map(function(value){
    return cvNeutralizeCandidatePronouns(value);
  });
}
function renderCvGenderNeutralSetting() {
  var enabled = getCvGenderNeutralSummary();
  var checkbox = document.getElementById('cvGenderNeutralToggle');
  var label = document.getElementById('cvGenderNeutralLabel');
  if (checkbox) checkbox.checked = enabled;
  if (label) label.textContent = enabled ? 'On' : 'Off';
}
function setCvGenderNeutralSummary(enabled, silent) {
  window._cvGenderNeutralSummary = enabled === true;
  try { cvStudioDurableSettingSet(CV_GENDER_NEUTRAL_STORE, getCvGenderNeutralSummary() ? 'true' : 'false'); } catch(e) {}
  renderCvGenderNeutralSetting();
  if (!silent) showToast(getCvGenderNeutralSummary()
    ? 'Summaries will refer to "the candidate" instead of he/she/him/her.'
    : 'Summaries will use the candidate\'s original pronouns.', 'ok');
  return getCvGenderNeutralSummary();
}
(function restoreCvGenderNeutralSummary(){
  var stored = null;
  try { stored = localStorage.getItem(CV_GENDER_NEUTRAL_STORE); } catch(e) {}
  window._cvGenderNeutralSummary = stored === 'true';
  setTimeout(renderCvGenderNeutralSetting, 0);
})();
document.addEventListener('DOMContentLoaded', renderCvGenderNeutralSetting);

var CV_SINGLE_SUMMARY_DETAIL_STORE = 'cvstudio_single_summary_detail_v1';
var CV_BATCH_SUMMARY_DETAIL_STORE = 'cvstudio_batch_summary_detail_v1';
window._cvSingleSummaryDetail = 'concise';
window._cvBatchSummaryDetail = 'concise';

function normalizeCvSummaryDetailPreference(value) {
  return String(value || '').toLowerCase() === 'detailed' ? 'detailed' : 'concise';
}
function cvSummaryDetailStore(scope) {
  return scope === 'batch' ? CV_BATCH_SUMMARY_DETAIL_STORE : CV_SINGLE_SUMMARY_DETAIL_STORE;
}
function getCvSummaryDetailPreference(scope) {
  return normalizeCvSummaryDetailPreference(
    scope === 'batch' ? window._cvBatchSummaryDetail : window._cvSingleSummaryDetail
  );
}
function renderCvSummaryDetailSettings() {
  ['single', 'batch'].forEach(function(scope) {
    var value = getCvSummaryDetailPreference(scope);
    ['concise', 'detailed'].forEach(function(choice) {
      var id = 'cv' + (scope === 'batch' ? 'Batch' : 'Single') + 'Summary' + (choice === 'detailed' ? 'Detailed' : 'Concise');
      var button = document.getElementById(id);
      if (!button) return;
      var active = value === choice;
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
      button.style.background = active ? 'var(--blue)' : 'var(--surface)';
      button.style.borderColor = active ? 'var(--blue)' : 'var(--border)';
      button.style.color = active ? '#ffffff' : 'var(--text2)';
      button.style.boxShadow = active ? '0 3px 9px rgba(37,99,235,.16)' : 'none';
    });
  });
}
function setCvSummaryDetailPreference(scope, value, silent) {
  scope = scope === 'batch' ? 'batch' : 'single';
  value = normalizeCvSummaryDetailPreference(value);
  if (scope === 'batch') window._cvBatchSummaryDetail = value;
  else window._cvSingleSummaryDetail = value;
  try { cvStudioDurableSettingSet(cvSummaryDetailStore(scope), value); } catch(e) {}
  renderCvSummaryDetailSettings();
  if (!silent) showToast((scope === 'batch' ? 'Batch' : 'Single CV') + ' summaries will be ' + value + '.', 'ok');
  return value;
}
(function restoreCvSummaryDetailPreferences(){
  var single = 'concise', batch = 'concise';
  try {
    single = localStorage.getItem(CV_SINGLE_SUMMARY_DETAIL_STORE) || 'concise';
    batch = localStorage.getItem(CV_BATCH_SUMMARY_DETAIL_STORE) || 'concise';
  } catch(e) {}
  window._cvSingleSummaryDetail = normalizeCvSummaryDetailPreference(single);
  window._cvBatchSummaryDetail = normalizeCvSummaryDetailPreference(batch);
  setTimeout(renderCvSummaryDetailSettings, 0);
})();
document.addEventListener('DOMContentLoaded', renderCvSummaryDetailSettings);

// ── Word export format (.doc / .docx) ────────────────────────────
// Storage getter/setter (wordExportFormat / setWordExportFormat) live in
// hyppies-export.js; this only drives the Settings segmented toggle.
function renderWordExportFormatSetting() {
  var value = (typeof wordExportFormat === 'function') ? wordExportFormat() : 'doc';
  var doc = document.getElementById('wordFormatDoc');
  var docx = document.getElementById('wordFormatDocx');
  [doc, docx].forEach(function(btn){
    if (!btn) return;
    var active = (btn === doc && value === 'doc') || (btn === docx && value === 'docx');
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    btn.style.background = active ? 'var(--blue)' : 'var(--surface)';
    btn.style.borderColor = active ? 'var(--blue)' : 'var(--border)';
    btn.style.color = active ? '#ffffff' : 'var(--text2)';
    btn.style.boxShadow = active ? '0 3px 9px rgba(37,99,235,.16)' : 'none';
  });
}
function setWordExportFormatUI(value) {
  value = value === 'docx' ? 'docx' : 'doc';
  if (typeof setWordExportFormat === 'function') setWordExportFormat(value);
  renderWordExportFormatSetting();
  showToast(value === 'docx' ? 'Word exports will download as clean .docx files.' : 'Word exports will download as richly-styled .doc files.', 'ok');
  return value;
}
document.addEventListener('DOMContentLoaded', renderWordExportFormatSetting);

// ── Auto-upload toggle ────────────────────────────────────────────
window._jaAutoUpload = true; // default on
(function() {
  try {
    var stored = localStorage.getItem('ja_auto_upload');
    if (stored === 'false') {
      window._jaAutoUpload = false;
      var cb = document.getElementById('autoUploadToggle');
      var lb = document.getElementById('autoUploadLabel');
      if (cb) cb.checked = false;
      if (lb) lb.textContent = 'Off';
    }
  } catch(e) {}
})();

function setAutoUpload(enable) {
  window._jaAutoUpload = enable;
  try { cvStudioDurableSettingSet('ja_auto_upload', enable ? 'true' : 'false'); } catch(e) {}
  var lb = document.getElementById('autoUploadLabel');
  if (lb) lb.textContent = enable ? 'On' : 'Off';
  // Update badges
  var batchConnBadge = document.getElementById('batchJAConnBadge');
  if (batchConnBadge && window._jaToken) {
    batchConnBadge.textContent = enable ? '☁ JA: auto-upload on' : '☁ JA: auto-upload off';
  }
  showToast(enable ? '✅ Auto-upload to JobAdder enabled' : '☁ Auto-upload disabled', 'ok');
}

// ── Startup toggle ───────────────────────────────────────────────────
async function loadStartupStatus() {
  try {
    var r = await fetch('/startup/status');
    var d = await r.json();
    var cb = document.getElementById('startupToggle');
    var lb = document.getElementById('startupLabel');
    if (cb) cb.checked = !!d.enabled;
    if (lb) lb.textContent = d.enabled ? 'On' : 'Off';
  } catch(e) {}
}

async function setStartup(enable) {
  var lb = document.getElementById('startupLabel');
  try {
    var r = await fetch(enable ? '/startup/enable' : '/startup/disable', { method: 'POST' });
    var d = await r.json();
    if (d.ok) {
      if (lb) lb.textContent = enable ? 'On' : 'Off';
      showToast(enable ? '✅ CV Studio will launch at Windows startup' : '✅ Startup launch disabled', 'ok');
    } else {
      if (lb) lb.textContent = enable ? 'Off' : 'On';
      var cb = document.getElementById('startupToggle');
      if (cb) cb.checked = !enable;
      showToast('Could not update startup: ' + (d.error || 'unknown error'), 'err');
    }
  } catch(e) {
    if (lb) lb.textContent = enable ? 'Off' : 'On';
    var cb2 = document.getElementById('startupToggle');
    if (cb2) cb2.checked = !enable;
    showToast('Could not reach server', 'err');
  }
}

// Load startup status on page load
window.addEventListener('load', function() { loadStartupStatus(); });
