// ── Batch drag & drop ─────────────────────────────────────────────────────────
window.addEventListener('load', async function() {
  renderStats();
  // existing single-file drag and drop for dropZone...
  var dz = document.getElementById('dropZone');
  if (dz) {
    dz.addEventListener('dragover', function(e) { e.preventDefault(); dz.classList.add('dragover'); });
    dz.addEventListener('dragleave', function(e) { dz.classList.remove('dragover'); });
    dz.addEventListener('drop', function(e) {
      e.preventDefault();
      dz.classList.remove('dragover');
      var file = e.dataTransfer.files[0];
      if (file) handleFileSelect(file);
    });
  }

  // Batch drop zone
  var bdz = document.getElementById('batchDropZone');
  if (bdz) {
    bdz.addEventListener('dragover', function(e) { e.preventDefault(); bdz.classList.add('dragover'); });
    bdz.addEventListener('dragleave', function(e) { bdz.classList.remove('dragover'); });
    bdz.addEventListener('drop', function(e) {
      e.preventDefault();
      bdz.classList.remove('dragover');
      handleBatchFileSelect(e.dataTransfer.files);
    });
  }

  // restore key/model
  try {
    await cvStudioHydrateBrowserSettings();
    await _loadSecureAiInfo();
    var mainProvider = localStorage.getItem('hy_provider') || 'anthropic';
    var leadProvider = localStorage.getItem('hy_lead_provider') || 'anthropic';
    var searchProvider = localStorage.getItem('hy_search_provider'), searchProviderKey = localStorage.getItem('hy_search_provider_key');

    // One-time migration: older versions stored a single flat key/model
    // regardless of provider. If a per-provider slot doesn't exist yet for
    // the saved provider, carry the legacy value over so nobody loses their
    // already-saved key when upgrading.
    var legacyKey = localStorage.getItem('hy_key');
    var legacyModel = localStorage.getItem('hy_model');
    if(legacyKey){await _saveSecureAiSecret(_aiSecretSlot('main',mainProvider),legacyKey,false);localStorage.removeItem('hy_key');}
    if (legacyModel && !localStorage.getItem(_providerModelStore(mainProvider))) {
      cvStudioDurableSettingSet(_providerModelStore(mainProvider), legacyModel);
    }
    var legacyLeadKey = localStorage.getItem('hy_lead_key');
    var legacyLeadModel = localStorage.getItem('hy_lead_model');
    if(legacyLeadKey){await _saveSecureAiSecret(_aiSecretSlot('lead',leadProvider),legacyLeadKey,false);localStorage.removeItem('hy_lead_key');}
    if (legacyLeadModel && !localStorage.getItem(_leadModelStore(leadProvider))) {
      cvStudioDurableSettingSet(_leadModelStore(leadProvider), legacyLeadModel);
    }

    for (var pp of ['anthropic','deepseek','openai']) {
      var mk=localStorage.getItem(_providerKeyStore(pp))||''; if(mk){await _saveSecureAiSecret(_aiSecretSlot('main',pp),mk,false);localStorage.removeItem(_providerKeyStore(pp));}
      var lk=localStorage.getItem(_leadKeyStore(pp))||''; if(lk){await _saveSecureAiSecret(_aiSecretSlot('lead',pp),lk,false);localStorage.removeItem(_leadKeyStore(pp));}
    }
    if(searchProviderKey&&searchProvider&&searchProvider!=='none'){await _saveSecureAiSecret('search_'+searchProvider,searchProviderKey,false);localStorage.removeItem('hy_search_provider_key');searchProviderKey='__BACKEND_SECURE__';}
    var oldEnrichKey=localStorage.getItem('hy_enrichment_provider_key')||'',oldEnrichProvider=localStorage.getItem('hy_enrichment_provider')||'none';
    if(oldEnrichKey&&oldEnrichProvider!=='none'){await _saveSecureAiSecret('enrichment_'+oldEnrichProvider,oldEnrichKey,false);localStorage.removeItem('hy_enrichment_provider_key');}
    await _loadSecureAiInfo();

    window._hProvider = mainProvider;
    window._hLeadProvider = leadProvider;
    var mpSel = document.getElementById('mainProviderSel');
    if (mpSel) mpSel.value = mainProvider;
    var lpSel = document.getElementById('leadProviderSel');
    if (lpSel) lpSel.value = leadProvider;

    // onMainProviderChange/onLeadProviderChange populate the key/model fields
    // (and setDot) from the per-provider store for whatever is now selected --
    // including the legacy value just migrated above.
    if (typeof onMainProviderChange === 'function') onMainProviderChange();
    if (typeof onLeadProviderChange === 'function') onLeadProviderChange();
    if (typeof ensureAiRoutingRowsVisible === 'function') ensureAiRoutingRowsVisible();
    if (typeof initSummaryTabUI === 'function') initSummaryTabUI();
  initAppraiserTabUI();
  initTheOwlTabUI();
  if (typeof initTheSpiderTabUI === 'function') initTheSpiderTabUI();

    if (searchProvider) { var spSel=document.getElementById('searchProviderSel'); if(spSel) spSel.value = searchProvider; window._hSearchProvider = searchProvider; }
    if(searchProvider){searchProviderKey=_secureAiValue('search_'+searchProvider);var spKey=document.getElementById('searchProviderKeyInput');if(spKey&&searchProviderKey==='__BACKEND_SECURE__')spKey.placeholder='Saved securely · paste to replace';window._hSearchProviderKey=searchProviderKey;}
    var enrichProvider = localStorage.getItem('hy_enrichment_provider');
    var enrichProviderKey = _secureAiValue('enrichment_'+(enrichProvider||'none'));
    if (enrichProvider) { var epSel=document.getElementById('enrichmentProviderSel'); if(epSel) epSel.value = enrichProvider; window._hEnrichmentProvider = enrichProvider; }
    if(enrichProviderKey){var epKey=document.getElementById('enrichmentProviderKeyInput');if(epKey&&enrichProviderKey==='__BACKEND_SECURE__')epKey.placeholder='Saved securely · paste to replace';window._hEnrichmentProviderKey=enrichProviderKey;}
    var aiTitleExp = document.getElementById('leadAiTitleExpansion');
    if (aiTitleExp) {
      aiTitleExp.checked = localStorage.getItem('hy_lead_ai_title_expansion') === '1';
      aiTitleExp.addEventListener('change', function(){ localStorage.setItem('hy_lead_ai_title_expansion', this.checked ? '1' : '0'); });
    }
    var allowRefine = document.getElementById('leadAllowProviderRefine');
    if (allowRefine) {
      allowRefine.checked = localStorage.getItem('hy_lead_allow_provider_refine') === '1';
      allowRefine.addEventListener('change', function(){ localStorage.setItem('hy_lead_allow_provider_refine', this.checked ? '1' : '0'); });
    }
    leadRefreshTitleCacheStats();
    leadRefreshContactCacheStats();
  } catch(e) {}
});

// ── Input tab switching ───────────────────────────────────────────────────────
var _activeInputTab = 'paste';
var _extractedText = '';
// Nested-list indent maps carried to /generate-docx: source-derived (docx
// w:ilvl / pdf geometry, from /extract-text) and outline-label (from /parse).
var _extractedBulletLevels = null;
var _labelBulletLevels = null;
// Merge {text, level} lists by key, keeping the deepest level (>= 1 only).
function cvMergeLevelLists(a, b) {
  var map = {};
  [a, b].forEach(function(list) {
    if (!Array.isArray(list)) return;
    list.forEach(function(e) {
      if (e && e.text != null) {
        var key = String(e.text);
        var v = Math.min(Math.max(Number(e.level) || 0, 0), 8);
        if (!(key in map) || v > map[key]) map[key] = v;
      }
    });
  });
  var out = [];
  Object.keys(map).forEach(function(key) { if (map[key] >= 1) out.push({ text: key, level: map[key] }); });
  return out;
}
function cvBulletLevelFor(text) {
  var key = String(text == null ? '' : text).replace(/\s+/g, ' ').trim().toLowerCase();
  var lists = [_extractedBulletLevels, _labelBulletLevels], best = 0;
  for (var i = 0; i < lists.length; i++) {
    if (!Array.isArray(lists[i])) continue;
    for (var j = 0; j < lists[i].length; j++) {
      var e = lists[i][j];
      if (e && String(e.text) === key) { var v = Math.min(Math.max(Number(e.level) || 0, 0), 8); if (v > best) best = v; }
    }
  }
  return best;
}
function cvBulletPreviewHtml(text) {
  var lvl = cvBulletLevelFor(text);
  var style = lvl > 0 ? ' style="margin-left:' + (lvl * 22) + 'px"' : '';
  return '<div class="preview-bullet"' + style + '>' + esc(text) + '</div>';
}

function switchInputTab(tab) {
  _activeInputTab = tab;
  document.getElementById('tabPaste').className = 'input-tab' + (tab === 'paste' ? ' active' : '');
  document.getElementById('tabUpload').className = 'input-tab' + (tab === 'upload' ? ' active' : '');
  document.getElementById('panelPaste').className = 'input-panel' + (tab === 'paste' ? ' active' : '');
  document.getElementById('panelUpload').className = 'input-panel' + (tab === 'upload' ? ' active' : '');
}

// ── File handling ─────────────────────────────────────────────────────────────
function extractNameFromFilename(filename) {
  // Try to extract candidate name from Hyppies filename patterns:
  // "Hyppies CV - Syamim Hakimi Mohd Azha  Python Developer  RBC .pdf" → "Syamim Hakimi Mohd Azha"
  // "Hyppies_CV_-_Eric_Sia_De_Long_(Blinded).docx" → "Eric Sia De Long"
  var s = filename.replace(/\.(docx|pdf)$/i, '');
  s = s.replace(/_/g, ' ');
  // Remove common prefixes
  s = s.replace(/^hyppies\s*cv\s*[-–]\s*/i, '');
  s = s.replace(/^cv\s*[-–]\s*/i, '');
  // Remove (Blinded) suffix and anything in brackets
  s = s.replace(/\s*\([^)]*\)\s*/g, ' ').trim();
  // Strip everything after double space (job title / company appended with __)
  s = s.split(/\s{2,}/)[0].trim();
  // If it looks like a real name (not "Candidate" or empty), return it
  if (s && s.toLowerCase() !== 'candidate' && s.length > 2) return s;
  return '';
}

function handleFileSelect(file) {
  if (!file) return;
  var ext = file.name.split('.').pop().toLowerCase();
  var SUPPORTED = ['pdf','docx','doc','txt','rtf','odt','png','jpg','jpeg'];
  if (!SUPPORTED.includes(ext)) {
    showToast('Supported: PDF, DOCX, DOC, TXT, RTF, ODT, PNG, JPG, JPEG', 'err');
    return;
  }
  // Pre-save name from filename as early fallback
  window._filenameGuessedName = extractNameFromFilename(file.name);
  window._originalFile = file; // store for JA new candidate upload

  var dz = document.getElementById('dropZone');
  dz.classList.remove('has-file', 'error');
  document.getElementById('dzFileName').textContent = '';
  document.getElementById('dzClear').style.display = 'none';
  document.getElementById('extracting').style.display = 'flex';
  document.getElementById('fileCharCount').style.display = 'none';
  _extractedText = '';

  // Upload to server for text extraction
  var _tabRun = markTabRunning('format');
  var formData = new FormData();
  formData.append('file', file);

  fetch('/extract-text', { method: 'POST', body: formData })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      document.getElementById('extracting').style.display = 'none';
      if (data.error) {
        dz.classList.add('error');
        document.getElementById('dzFileName').textContent = '✗ ' + data.error;
        showToast('Extraction failed: ' + data.error, 'err');
        markTabFailed('format', _tabRun);
        return;
      }
      var extractionWarning = cvShowExtractionWarning(data);
      _extractedText = data.text;
      _extractedBulletLevels = Array.isArray(data.bullet_levels) ? data.bullet_levels : null;
      dz.classList.add('has-file');
      document.getElementById('dzFileName').textContent = (extractionWarning ? '⚠ ' : '✓ ') + file.name + ' (' + data.text.length.toLocaleString() + ' chars extracted)' + (extractionWarning ? ' — partial extraction; review text' : '');
      document.getElementById('dzClear').style.display = 'block';
      document.getElementById('fileCharCount').style.display = 'block';
      document.getElementById('fileCharCount').textContent = data.text.length.toLocaleString() + ' characters extracted';
      if (!extractionWarning) showToast('File ready — click Format CV', 'ok');
      markTabDone('format', _tabRun);
    })
    .catch(function(e) {
      document.getElementById('extracting').style.display = 'none';
      dz.classList.add('error');
      var msg = (e.message || '').toLowerCase().includes('failed to fetch') ? 'Server not running — relaunch CV Studio and try again.' : (e.message || 'Unknown error');
      markTabFailed('format', _tabRun);
      showToast('Upload failed: ' + msg, 'err');
    });
}

function clearFile(e) {
  e.stopPropagation();
  clearTabRunState('format');
  _extractedText = '';
  var dz = document.getElementById('dropZone');
  dz.classList.remove('has-file', 'error');
  document.getElementById('dzFileName').textContent = '';
  document.getElementById('dzClear').style.display = 'none';
  document.getElementById('fileCharCount').style.display = 'none';
  document.getElementById('fileInput').value = '';
}
