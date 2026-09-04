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

// ── CV download destinations ──────────────────────────────────────
// Configured filesystem destinations are owned by the local CV Studio process
// because embedded Chromium does not reliably honour direct folder writes.
var _cvDownloadLastResult = {};

// Single source of truth for the configurable download destinations. Keep this
// aligned with DOWNLOAD_ALLOWED_EXTENSIONS in cvstudio_downloads.py.
var CV_DOWNLOAD_KINDS = ['formatted', 'blind', 'company_profile', 'summary', 'blind_jd', 'owl'];

function cvStudioEmptyDownloadFolders() {
  var folders = {};
  CV_DOWNLOAD_KINDS.forEach(function(kind){ folders[kind] = null; });
  return folders;
}

function cvStudioDownloadDestinationConfig(kind) {
  var value = String(kind || '').toLowerCase();
  if (value === 'blind') return {kind:'blind', prefix:'cvDownloadBlind', label:'Blind CV'};
  if (value === 'company_profile') return {kind:'company_profile', prefix:'cvDownloadCompanyProfile', label:'Company Profile'};
  if (value === 'summary') return {kind:'summary', prefix:'cvDownloadSummary', label:'Summary Output'};
  if (value === 'blind_jd') return {kind:'blind_jd', prefix:'cvDownloadBlindJd', label:'Blind JD'};
  if (value === 'owl') return {kind:'owl', prefix:'cvDownloadOwl', label:'The Owl'};
  return {kind:'formatted', prefix:'cvDownloadFormatted', label:'Formatted CV'};
}

function cvStudioDownloadDestinationKinds() {
  return CV_DOWNLOAD_KINDS.slice();
}

function normalizeCvDownloadDestination(kind) {
  return cvStudioDownloadDestinationConfig(kind).kind;
}

function cvStudioSafeDownloadFilename(filename) {
  var value = String(filename || 'CV Studio download.docx')
    .replace(/[\/\\\u0000-\u001f<>:\x22|?*]/g, '_')
    .replace(/^[. ]+/g, '')
    .replace(/[. ]+$/g, '')
    .trim();
  if (!value) value = 'CV Studio download.docx';
  var dot = value.lastIndexOf('.');
  var extension = dot > 0 ? value.slice(dot) : '';
  var stem = dot > 0 ? value.slice(0, dot) : value;
  if (/^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])$/i.test(stem)) stem = '_' + stem;
  var maxLength = 180;
  if ((stem + extension).length > maxLength) stem = stem.slice(0, Math.max(1, maxLength - extension.length)).replace(/[. ]+$/g, '');
  return (stem || 'CV Studio download') + extension;
}

function cvStudioFallbackDownloadBlob(blob, filename) {
  var safeName = cvStudioSafeDownloadFilename(filename);
  var url = URL.createObjectURL(blob);
  var anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = safeName;
  document.body.appendChild(anchor);
  anchor.click();
  setTimeout(function(){
    URL.revokeObjectURL(url);
    if (anchor.parentNode) anchor.parentNode.removeChild(anchor);
    else if (typeof anchor.remove === 'function') anchor.remove();
  }, 1000);
  return {method:'browser', filename:safeName};
}

// The generated file is posted back to that local process for saving.
var _cvNativeDownloadFolderState = {native_supported:false, status_loaded:false, folders:cvStudioEmptyDownloadFolders()};
var _cvNativeDownloadFolderLoadPromise = null;

function cvStudioNativeDownloadFolder(kind) {
  kind = normalizeCvDownloadDestination(kind);
  var folders = _cvNativeDownloadFolderState && _cvNativeDownloadFolderState.folders;
  var folder = folders && folders[kind];
  return folder && typeof folder === 'object' ? folder : {configured:false,path:'',available:false};
}

function cvStudioRenderDownloadDestination(kind, folder) {
  kind = normalizeCvDownloadDestination(kind);
  var prefix = cvStudioDownloadDestinationConfig(kind).prefix;
  var previewNode = document.getElementById(prefix + 'FolderPreview');
  if (!previewNode) return;
  var last = _cvDownloadLastResult[kind];
  if (last && last.path) previewNode.textContent = 'Last saved: ' + String(last.path);
  else if (last && last.filename && last.method === 'browser') previewNode.textContent = 'Last download: Browser Downloads\\' + String(last.filename);
  else if (last && last.method === 'uncertain') previewNode.textContent = 'Last save could not be confirmed — check: ' + String(last.folder || folder && folder.path || 'selected folder');
  else if (last && last.method === 'failed') previewNode.textContent = 'Last save failed — destination remains: ' + String(folder && folder.path || 'selected folder');
  else if (folder && folder.configured && folder.path) previewNode.textContent = 'Destination: ' + String(folder.path);
  else previewNode.textContent = 'Destination: your browser\'s configured Downloads folder';
}

function cvStudioRenderDownloadDirectory(kind, folder) {
  kind = normalizeCvDownloadDestination(kind);
  folder = folder && typeof folder === 'object' ? folder : {configured:false,path:'',available:false};
  var prefix = cvStudioDownloadDestinationConfig(kind).prefix;
  var nameNode = document.getElementById(prefix + 'FolderName');
  var accessNode = document.getElementById(prefix + 'FolderAccess');
  if (folder.configured) {
    if (nameNode) nameNode.textContent = folder.path || 'Selected folder';
    if (accessNode) {
      accessNode.textContent = folder.available ? 'Configured' : 'Folder unavailable';
      accessNode.classList.toggle('ok', !!folder.available);
    }
  } else {
    if (nameNode) nameNode.textContent = 'Browser Downloads folder';
    if (accessNode) { accessNode.textContent = 'Browser default'; accessNode.classList.remove('ok'); }
  }
  cvStudioRenderDownloadDestination(kind, folder);
  return !!(folder.configured && folder.available);
}

async function cvStudioNativeDownloadFolderRequest(method, payload) {
  var response = await fetch('/downloads/folders', {
    method:method,
    headers:{'Content-Type':'application/json'},
    body:method === 'GET' ? undefined : JSON.stringify(payload || {}),
    cvStudioNoTimeout:true,
  });
  var data = await response.json().catch(function(){ return {}; });
  if (!response.ok || !data.ok) {
    var error = new Error(data.error || data.message || 'Download-folder request failed.');
    error.code = data.code || '';
    throw error;
  }
  return data;
}

async function cvStudioLoadDownloadFolderState() {
  if (_cvNativeDownloadFolderLoadPromise) return _cvNativeDownloadFolderLoadPromise;
  _cvNativeDownloadFolderLoadPromise = (async function(){
    var response = await fetch('/downloads/folders');
    var data = await response.json().catch(function(){ return {}; });
    if (!response.ok || !data.ok) throw new Error(data.error || data.message || 'Could not load download folders.');
    _cvNativeDownloadFolderState = {
      native_supported:!!data.native_supported,
      status_loaded:true,
      folders:data.folders || cvStudioEmptyDownloadFolders(),
    };
    return _cvNativeDownloadFolderState;
  })();
  try {
    return await _cvNativeDownloadFolderLoadPromise;
  } catch(error) {
    _cvNativeDownloadFolderState.status_loaded = false;
    throw error;
  } finally {
    _cvNativeDownloadFolderLoadPromise = null;
  }
}

async function renderCvDownloadSettings() {
  var support = document.getElementById('cvDownloadFolderSupport');
  try {
    var data = await cvStudioLoadDownloadFolderState();
    cvStudioDownloadDestinationKinds().forEach(function(kind){
      cvStudioRenderDownloadDirectory(kind, cvStudioNativeDownloadFolder(kind));
    });
    if (support) {
      support.style.display = data.native_supported ? 'none' : 'block';
      support.textContent = data.native_supported ? '' : 'This platform cannot open a native folder picker. CV Studio will use Browser Downloads unless a supported local build is used.';
    }
    return true;
  } catch(error) {
    if (support) {
      support.style.display = 'block';
      support.textContent = (error && error.message) || 'CV Studio could not load the saved download folders.';
    }
    return false;
  }
}

async function cvStudioChooseDownloadDirectory(kind) {
  kind = normalizeCvDownloadDestination(kind);
  var config = cvStudioDownloadDestinationConfig(kind);
  try {
    var data = await cvStudioNativeDownloadFolderRequest('POST', {kind:kind, action:'select'});
    _cvNativeDownloadFolderState.folders[kind] = data.folder;
    _cvNativeDownloadFolderState.status_loaded = true;
    _cvDownloadLastResult[kind] = null;
    cvStudioRenderDownloadDirectory(kind, data.folder);
    showToast(config.label + ' folder saved: ' + data.folder.path, 'ok');
    return true;
  } catch(error) {
    if (error && error.code === 'DOWNLOAD_FOLDER_SELECTION_CANCELLED') return false;
    showToast((error && error.message) || 'Could not select the download folder.', 'err');
    return false;
  }
}

async function cvStudioVerifyDownloadDirectory(kind) {
  kind = normalizeCvDownloadDestination(kind);
  var config = cvStudioDownloadDestinationConfig(kind);
  try {
    var data = await cvStudioNativeDownloadFolderRequest('POST', {kind:kind, action:'check'});
    _cvNativeDownloadFolderState.folders[kind] = data.folder;
    _cvNativeDownloadFolderState.status_loaded = true;
    cvStudioRenderDownloadDirectory(kind, data.folder);
    showToast(config.label + ' folder is writable: ' + data.folder.path, 'ok');
    return true;
  } catch(error) {
    await renderCvDownloadSettings();
    showToast((error && error.message) || 'The selected folder is not writable.', 'err');
    return false;
  }
}

async function cvStudioClearDownloadDirectory(kind) {
  kind = normalizeCvDownloadDestination(kind);
  var config = cvStudioDownloadDestinationConfig(kind);
  try {
    var data = await cvStudioNativeDownloadFolderRequest('DELETE', {kind:kind});
    _cvNativeDownloadFolderState.folders[kind] = data.folder;
    _cvNativeDownloadFolderState.status_loaded = true;
    _cvDownloadLastResult[kind] = null;
    cvStudioRenderDownloadDirectory(kind, data.folder);
    showToast(config.label + ' will use Browser Downloads.', 'ok');
    return true;
  } catch(error) {
    showToast((error && error.message) || 'Could not clear the download folder.', 'err');
    return false;
  }
}

async function cvStudioPrepareDownloadDestination(kind) {
  kind = normalizeCvDownloadDestination(kind);
  try {
    await cvStudioLoadDownloadFolderState();
  } catch(error) {
    return {
      kind:kind,
      configured:false,
      statusFailed:true,
      fallbackReason:(error && error.message) || 'CV Studio could not verify the configured download folder',
      folder:null,
      handle:null,
    };
  }
  var folder = cvStudioNativeDownloadFolder(kind);
  return {kind:kind, configured:!!folder.configured, folder:folder, handle:folder.configured ? {native:true} : null};
}

async function cvStudioSaveDownloadBlob(blob, filename, kind, preparedDestination) {
  kind = normalizeCvDownloadDestination(kind);
  var safeName = cvStudioSafeDownloadFilename(filename);
  function cvStudioAddBrowserFallback(resultObj) {
    // A configured-folder save failed or could not be confirmed: never lose the
    // generated file -- also hand it to the browser Downloads folder so the user
    // still receives it (worst case a duplicate, never a silent data loss).
    try {
      cvStudioFallbackDownloadBlob(blob, safeName);
      resultObj.browserFallback = true;
    } catch (fallbackError) {
      resultObj.browserFallback = false;
    }
    return resultObj;
  }
  var destination = preparedDestination || await cvStudioPrepareDownloadDestination(kind);
  if (destination && destination.statusFailed) {
    var unavailable = {
      method:'failed',
      configured:true,
      filename:safeName,
      fallbackReason:destination.fallbackReason || 'CV Studio could not verify the configured download folder',
    };
    _cvDownloadLastResult[kind] = unavailable;
    cvStudioRenderDownloadDestination(kind, destination.folder);
    return cvStudioAddBrowserFallback(unavailable);
  }
  if (destination && destination.configured) {
    var response;
    var data;
    try {
      var form = new FormData();
      form.append('kind', kind);
      form.append('filename', safeName);
      form.append('file', blob, safeName);
      response = await fetch('/downloads/save', {method:'POST', body:form, cvStudioNoTimeout:true});
      data = await response.json();
    } catch(error) {
      var uncertain = {
        method:'uncertain',
        configured:true,
        uncertain:true,
        filename:safeName,
        folder:String(destination.folder && destination.folder.path || ''),
        fallbackReason:'CV Studio could not confirm whether the file was saved. Check the selected folder before retrying.',
      };
      _cvDownloadLastResult[kind] = uncertain;
      cvStudioRenderDownloadDestination(kind, destination.folder);
      return cvStudioAddBrowserFallback(uncertain);
    }
    if (!response.ok || !data.ok) {
      var failed = {
        method:'failed',
        configured:true,
        filename:safeName,
        fallbackReason:data.error || data.message || 'the selected folder could not be written to',
      };
      _cvDownloadLastResult[kind] = failed;
      cvStudioRenderDownloadDestination(kind, destination.folder);
      return cvStudioAddBrowserFallback(failed);
    }
    var saved = {method:'folder', filename:data.filename, folder:data.folder, path:data.path};
    _cvDownloadLastResult[kind] = saved;
    cvStudioRenderDownloadDestination(kind, destination.folder);
    return saved;
  }
  var browser = cvStudioFallbackDownloadBlob(blob, safeName);
  _cvDownloadLastResult[kind] = browser;
  cvStudioRenderDownloadDestination(kind, destination && destination.folder);
  return browser;
}

function cvStudioShowDownloadResult(result, label) {
  label = String(label || 'File');
  if (result && result.method === 'folder') {
    showToast(label + ' saved to ' + String(result.path || result.folder || 'the selected folder'), 'ok');
    return true;
  }
  if (result && result.method === 'browser') {
    showToast(label + ' downloaded using the browser Downloads folder.', 'ok');
    return true;
  }
  if (result && result.browserFallback) {
    // The configured folder failed but the file was not lost: it went to the
    // browser Downloads folder instead. Surface it as a warning, not an error.
    var fbWhy = result.fallbackReason ? ' (' + String(result.fallbackReason).replace(/[. ]+$/g, '') + ')' : '';
    showToast(label + " couldn't be saved to the selected folder" + fbWhy + '; downloaded to your browser instead. Check Settings → Downloads.', 'warn');
    return true;
  }
  if (result && result.uncertain) {
    showToast(result.fallbackReason || (label + ' save could not be confirmed.'), 'err');
    return false;
  }
  var reason = result && result.fallbackReason ? ': ' + result.fallbackReason.replace(/[. ]+$/g, '') + '. ' : '. ';
  showToast(label + ' was not saved' + reason + 'Check its folder in Settings → Downloads.', 'err');
  return false;
}

document.addEventListener('DOMContentLoaded', renderCvDownloadSettings);

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

// Blind CV candidate-gender neutralization
var CV_BLIND_CANDIDATE_GENDER_NEUTRAL_STORE = 'cvstudio_blind_candidate_gender_neutral_v1';
window._cvBlindCandidateGenderNeutral = false;

function getCvBlindCandidateGenderNeutralization() {
  return window._cvBlindCandidateGenderNeutral === true;
}
function renderCvBlindCandidateGenderNeutralizationSetting() {
  var enabled = getCvBlindCandidateGenderNeutralization();
  var checkbox = document.getElementById('cvBlindCandidateGenderNeutralToggle');
  var label = document.getElementById('cvBlindCandidateGenderNeutralLabel');
  if (checkbox) checkbox.checked = enabled;
  if (label) label.textContent = enabled ? 'On' : 'Off';
}
function setCvBlindCandidateGenderNeutralization(enabled, silent) {
  window._cvBlindCandidateGenderNeutral = enabled === true;
  try {
    cvStudioDurableSettingSet(
      CV_BLIND_CANDIDATE_GENDER_NEUTRAL_STORE,
      getCvBlindCandidateGenderNeutralization() ? 'true' : 'false'
    );
  } catch(e) {}
  renderCvBlindCandidateGenderNeutralizationSetting();
  if (!silent) {
    showToast(
      getCvBlindCandidateGenderNeutralization()
        ? 'Blind CV will neutralize only pronouns that refer to the candidate.'
        : 'Blind CV will keep candidate pronouns unchanged.',
      'ok'
    );
  }
  return getCvBlindCandidateGenderNeutralization();
}
(function restoreCvBlindCandidateGenderNeutralization(){
  var stored = null;
  try { stored = localStorage.getItem(CV_BLIND_CANDIDATE_GENDER_NEUTRAL_STORE); } catch(e) {}
  window._cvBlindCandidateGenderNeutral = stored === 'true';
  setTimeout(renderCvBlindCandidateGenderNeutralizationSetting, 0);
})();
document.addEventListener('DOMContentLoaded', renderCvBlindCandidateGenderNeutralizationSetting);

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
    if (d.repair_required) {
      if (lb) lb.textContent = 'Repairing…';
      await setStartup(true, { repair: true });
      return;
    }
    if (lb) lb.textContent = d.enabled ? 'On' : 'Off';
  } catch(e) {}
}

async function setStartup(enable, options) {
  options = options || {};
  var lb = document.getElementById('startupLabel');
  try {
    var r = await fetch(enable ? '/startup/enable' : '/startup/disable', { method: 'POST' });
    var d = await r.json();
    if (d.ok) {
      if (lb) lb.textContent = enable ? 'On' : 'Off';
      showToast(options.repair ? '✅ Windows startup location updated' : (enable ? '✅ CV Studio will launch at Windows startup' : '✅ Startup launch disabled'), 'ok');
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
