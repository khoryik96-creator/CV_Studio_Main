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
// Chromium's File System Access API is the only browser-safe way for a local
// page to write to a user-selected folder. Directory handles are kept in
// IndexedDB because localStorage cannot store them. Unsupported browsers and
// expired/denied permissions retain the established browser-download path.
var CV_DOWNLOAD_DIRECTORY_DB = 'cvstudio_download_directories_v1';
var CV_DOWNLOAD_DIRECTORY_STORE = 'directories';
var _cvDownloadDirectoryCache = {};
var _cvDownloadLastResult = {};

function normalizeCvDownloadDestination(kind) {
  return String(kind || '').toLowerCase() === 'blind' ? 'blind' : 'formatted';
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

function cvStudioOpenDownloadDirectoryDb() {
  return new Promise(function(resolve, reject) {
    if (!window.indexedDB) { reject(new Error('IndexedDB is unavailable')); return; }
    var request = window.indexedDB.open(CV_DOWNLOAD_DIRECTORY_DB, 1);
    request.onupgradeneeded = function() {
      var db = request.result;
      if (!db.objectStoreNames.contains(CV_DOWNLOAD_DIRECTORY_STORE)) db.createObjectStore(CV_DOWNLOAD_DIRECTORY_STORE);
    };
    request.onsuccess = function(){ resolve(request.result); };
    request.onerror = function(){ reject(request.error || new Error('Could not open download folder storage')); };
    request.onblocked = function(){ reject(new Error('Download folder storage is blocked')); };
  });
}

function cvStudioDownloadDirectoryTransaction(mode, work) {
  return cvStudioOpenDownloadDirectoryDb().then(function(db) {
    return new Promise(function(resolve, reject) {
      var transaction, result, settled = false;
      function finishError(error) {
        if (settled) return;
        settled = true;
        try { db.close(); } catch(_closeError) {}
        reject(error || new Error('Download folder storage failed'));
      }
      try { transaction = db.transaction(CV_DOWNLOAD_DIRECTORY_STORE, mode); }
      catch(error) { try { db.close(); } catch(_error) {} reject(error); return; }
      var store = transaction.objectStore(CV_DOWNLOAD_DIRECTORY_STORE);
      var request;
      try { request = work(store); }
      catch(error2) { try { transaction.abort(); } catch(_error2) {} finishError(error2); return; }
      request.onsuccess = function(){ result = request.result; };
      request.onerror = function(){ finishError(request.error); };
      transaction.oncomplete = function(){
        if (settled) return;
        settled = true;
        try { db.close(); } catch(_error3) {}
        resolve(result);
      };
      transaction.onabort = transaction.onerror = function(){ finishError(transaction.error); };
    });
  });
}

function cvStudioReadDownloadDirectory(kind) {
  kind = normalizeCvDownloadDestination(kind);
  return cvStudioDownloadDirectoryTransaction('readonly', function(store){ return store.get(kind); });
}

function cvStudioStoreDownloadDirectory(kind, handle) {
  kind = normalizeCvDownloadDestination(kind);
  return cvStudioDownloadDirectoryTransaction('readwrite', function(store){ return store.put(handle, kind); });
}

function cvStudioDeleteDownloadDirectory(kind) {
  kind = normalizeCvDownloadDestination(kind);
  return cvStudioDownloadDirectoryTransaction('readwrite', function(store){ return store.delete(kind); });
}

function cvStudioGetDownloadDirectory(kind) {
  kind = normalizeCvDownloadDestination(kind);
  if (Object.prototype.hasOwnProperty.call(_cvDownloadDirectoryCache, kind)) return Promise.resolve(_cvDownloadDirectoryCache[kind]);
  return cvStudioReadDownloadDirectory(kind).then(function(handle){
    handle = handle && handle.kind === 'directory' ? handle : null;
    _cvDownloadDirectoryCache[kind] = handle;
    return handle;
  }).catch(function(){
    _cvDownloadDirectoryCache[kind] = null;
    return null;
  });
}

function cvStudioDirectoryWritePermission(handle, requestIfNeeded) {
  if (!handle || handle.kind !== 'directory') return Promise.resolve(false);
  var options = {mode:'readwrite'};
  var query;
  try { query = typeof handle.queryPermission === 'function' ? handle.queryPermission(options) : Promise.resolve('prompt'); }
  catch(error) { query = Promise.resolve('prompt'); }
  return Promise.resolve(query).then(function(state){
    if (state === 'granted') return true;
    if (!requestIfNeeded || typeof handle.requestPermission !== 'function') return false;
    try {
      return Promise.resolve(handle.requestPermission(options)).then(function(result){ return result === 'granted'; });
    } catch(error) {
      return false;
    }
  }).catch(function(){ return false; });
}

function cvStudioRenderDownloadDestination(kind, handle) {
  kind = normalizeCvDownloadDestination(kind);
  var prefix = kind === 'blind' ? 'cvDownloadBlind' : 'cvDownloadFormatted';
  var previewNode = document.getElementById(prefix + 'FolderPreview');
  if (!previewNode) return;
  var last = _cvDownloadLastResult[kind];
  if (last && last.filename) {
    previewNode.textContent = last.method === 'folder'
      ? 'Last saved: ' + String(last.folder || (handle && handle.name) || 'Selected folder') + '\\' + String(last.filename)
      : 'Last download: Browser Downloads\\' + String(last.filename);
    return;
  }
  previewNode.textContent = handle
    ? 'Destination: selected folder “' + String(handle.name || 'Chosen folder') + '” (full path hidden by browser)'
    : 'Destination: your browser\'s configured Downloads folder';
}

function cvStudioRenderDownloadDirectory(kind, handle) {
  kind = normalizeCvDownloadDestination(kind);
  var prefix = kind === 'blind' ? 'cvDownloadBlind' : 'cvDownloadFormatted';
  var nameNode = document.getElementById(prefix + 'FolderName');
  var accessNode = document.getElementById(prefix + 'FolderAccess');
  if (!handle) {
    if (nameNode) nameNode.textContent = 'Browser Downloads folder';
    if (accessNode) { accessNode.textContent = 'Browser default'; accessNode.classList.remove('ok'); }
    cvStudioRenderDownloadDestination(kind, null);
    return Promise.resolve(false);
  }
  var folderName = String(handle.name || 'Chosen folder');
  if (nameNode) nameNode.textContent = 'Selected folder: ' + folderName;
  cvStudioRenderDownloadDestination(kind, handle);
  return cvStudioDirectoryWritePermission(handle, false).then(function(granted){
    if (accessNode) {
      accessNode.textContent = granted ? 'Ready to save' : 'Access required';
      accessNode.classList.toggle('ok', granted);
    }
    return granted;
  });
}

function renderCvDownloadSettings() {
  var support = document.getElementById('cvDownloadFolderSupport');
  var supported = typeof window.showDirectoryPicker === 'function' && !!window.indexedDB;
  if (support) {
    support.style.display = supported ? 'none' : 'block';
    support.textContent = supported ? '' : 'This browser does not support remembered folder access. CV Studio will continue using the browser\'s normal Downloads folder.';
  }
  return Promise.all(['formatted','blind'].map(function(kind){
    return cvStudioGetDownloadDirectory(kind).then(function(handle){ return cvStudioRenderDownloadDirectory(kind, handle); });
  }));
}

async function cvStudioChooseDownloadDirectory(kind) {
  kind = normalizeCvDownloadDestination(kind);
  if (typeof window.showDirectoryPicker !== 'function' || !window.indexedDB) {
    renderCvDownloadSettings();
    showToast('This browser cannot remember a download folder. Browser Downloads will be used.', 'info');
    return false;
  }
  try {
    var handle = await window.showDirectoryPicker({id:'cvstudio-' + kind + '-cv', mode:'readwrite'});
    if (!handle || handle.kind !== 'directory') throw new Error('A folder was not selected');
    _cvDownloadDirectoryCache[kind] = handle;
    _cvDownloadLastResult[kind] = null;
    var permitted = await cvStudioDirectoryWritePermission(handle, true);
    var persisted = true;
    try { await cvStudioStoreDownloadDirectory(kind, handle); }
    catch(storageError) { persisted = false; }
    await cvStudioRenderDownloadDirectory(kind, handle);
    if (!permitted) {
      showToast('Folder selected, but write access was not granted. Click Check access before downloading.', 'err');
      return false;
    }
    showToast((kind === 'blind' ? 'Blind' : 'Formatted') + ' CV folder is ready' + (persisted ? '.' : ' for this tab; the browser could not remember it.'), persisted ? 'ok' : 'info');
    return true;
  } catch(error) {
    if (error && error.name === 'AbortError') return false;
    showToast('Could not select the folder. Browser Downloads will remain available.', 'err');
    return false;
  }
}

async function cvStudioVerifyDownloadDirectory(kind) {
  kind = normalizeCvDownloadDestination(kind);
  var handle = await cvStudioGetDownloadDirectory(kind);
  if (!handle) {
    showToast('Choose a folder first.', 'info');
    return false;
  }
  var permitted = await cvStudioDirectoryWritePermission(handle, true);
  await cvStudioRenderDownloadDirectory(kind, handle);
  showToast(
    permitted
      ? (kind === 'blind' ? 'Blind' : 'Formatted') + ' CV folder is ready to save.'
      : 'Write access was not granted. CV Studio will use browser Downloads until access is allowed.',
    permitted ? 'ok' : 'err'
  );
  return permitted;
}

async function cvStudioClearDownloadDirectory(kind) {
  kind = normalizeCvDownloadDestination(kind);
  _cvDownloadDirectoryCache[kind] = null;
  _cvDownloadLastResult[kind] = null;
  var removed = true;
  try { await cvStudioDeleteDownloadDirectory(kind); }
  catch(error) { removed = !window.indexedDB; }
  await cvStudioRenderDownloadDirectory(kind, null);
  showToast(
    (kind === 'blind' ? 'Blind' : 'Formatted') + ' CV will use the browser Downloads folder.' +
      (removed ? '' : ' The saved choice could not be removed permanently; try again before restarting.'),
    removed ? 'ok' : 'err'
  );
  return removed;
}

async function cvStudioUniqueDownloadFilename(handle, filename) {
  var safe = cvStudioSafeDownloadFilename(filename);
  var dot = safe.lastIndexOf('.');
  var extension = dot > 0 ? safe.slice(dot) : '';
  var stem = dot > 0 ? safe.slice(0, dot) : safe;
  function withSuffix(suffix) {
    suffix = String(suffix || '');
    var maxStemLength = Math.max(1, 180 - extension.length - suffix.length);
    var shortenedStem = stem.slice(0, maxStemLength).replace(/[. ]+$/g, '');
    if (!shortenedStem) shortenedStem = 'CV Studio download'.slice(0, maxStemLength);
    return cvStudioSafeDownloadFilename(shortenedStem + suffix + extension);
  }
  for (var index = 0; index < 1000; index += 1) {
    var suffix = index ? ' (' + index + ')' : '';
    var candidate = withSuffix(suffix);
    try {
      await handle.getFileHandle(candidate);
    } catch(error) {
      if (error && error.name === 'NotFoundError') return candidate;
      throw error;
    }
  }
  var timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  for (var attempt = 0; attempt < 100; attempt += 1) {
    var fallbackSuffix = ' - ' + timestamp + (attempt ? '-' + attempt : '');
    var fallbackCandidate = withSuffix(fallbackSuffix);
    try {
      await handle.getFileHandle(fallbackCandidate);
    } catch(error2) {
      if (error2 && error2.name === 'NotFoundError') return fallbackCandidate;
      throw error2;
    }
  }
  throw new Error('Could not find an unused filename in the selected folder');
}

async function cvStudioPrepareDownloadDestination(kind) {
  kind = normalizeCvDownloadDestination(kind);
  var handle = await cvStudioGetDownloadDirectory(kind);
  if (!handle) return {kind:kind, handle:null, configured:false};
  var permitted = await cvStudioDirectoryWritePermission(handle, true);
  await cvStudioRenderDownloadDirectory(kind, handle);
  return {kind:kind, handle:permitted ? handle : null, configured:true, permissionDenied:!permitted};
}

function cvStudioDownloadFallbackReason(error) {
  var name = String(error && error.name || '');
  if (name === 'NotAllowedError' || name === 'SecurityError') return 'write permission was not granted';
  if (name === 'QuotaExceededError') return 'the selected drive has insufficient free space';
  if (name === 'AbortError') return 'the folder write was cancelled';
  return 'the selected folder could not be written to';
}

async function cvStudioSaveDownloadBlob(blob, filename, kind, preparedDestination) {
  kind = normalizeCvDownloadDestination(kind);
  var safeName = cvStudioSafeDownloadFilename(filename);
  var destination = preparedDestination || await cvStudioPrepareDownloadDestination(kind);
  var folderFailure = destination && destination.permissionDenied ? 'write permission was not granted' : '';
  if (destination && destination.handle) {
    var writable = null;
    try {
      var uniqueName = await cvStudioUniqueDownloadFilename(destination.handle, safeName);
      var fileHandle = await destination.handle.getFileHandle(uniqueName, {create:true});
      writable = await fileHandle.createWritable();
      await writable.write(blob);
      await writable.close();
      var saved = {method:'folder', filename:uniqueName, folder:String(destination.handle.name || '')};
      _cvDownloadLastResult[kind] = saved;
      cvStudioRenderDownloadDestination(kind, destination.handle);
      return saved;
    } catch(error) {
      if (writable && typeof writable.abort === 'function') { try { await writable.abort(); } catch(_abortError) {} }
      folderFailure = cvStudioDownloadFallbackReason(error);
      await cvStudioRenderDownloadDirectory(kind, destination.handle);
    }
  }
  var fallback = cvStudioFallbackDownloadBlob(blob, safeName);
  if (destination && destination.configured) {
    fallback.configured = true;
    fallback.fallbackReason = folderFailure || 'the selected folder was unavailable';
  }
  _cvDownloadLastResult[kind] = fallback;
  cvStudioRenderDownloadDestination(kind, null);
  return fallback;
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
