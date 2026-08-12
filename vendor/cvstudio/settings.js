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
  if (!silent) showToast(getCvSummaryBoxAutoFit() ? 'Summary boxes will resize when safe; oversized summaries will keep the fixed first-page box.' : 'Summary boxes will keep the template size.', 'ok');
  return getCvSummaryBoxAutoFit();
}
(function restoreCvSummaryBoxAutoFit(){
  var stored = null;
  try { stored = localStorage.getItem(CV_SUMMARY_BOX_AUTO_FIT_STORE); } catch(e) {}
  window._cvSummaryBoxAutoFit = stored !== 'false';
  setTimeout(renderCvSummaryBoxAutoFitSetting, 0);
})();
document.addEventListener('DOMContentLoaded', renderCvSummaryBoxAutoFitSetting);

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
