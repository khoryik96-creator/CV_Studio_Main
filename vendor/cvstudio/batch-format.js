// ── Batch Format ────────────────────────────────────────────────────────────────
var _batchMode = 'format'; // 'format' | 'blind'
var _batchFiles = []; // [{file, id, status, cvData, filename, cost}]
var _batchRunning = false;
var _batchBlobs = []; // [{filename, blob}]
var _batchTimerInterval = null;
var _batchStartWatchdog = null;

function batchHasProcessingRows() {
  return _batchFiles.some(function(bf){ return bf.status === 'processing'; });
}

function batchHasPendingRows() {
  return _batchFiles.some(function(bf){ return bf.status === 'pending'; });
}

function resetStaleBatchRunState(options) {
  options = options || {};
  if (_batchTimerInterval) {
    clearInterval(_batchTimerInterval);
    _batchTimerInterval = null;
  }
  if (_batchStartWatchdog) {
    clearTimeout(_batchStartWatchdog);
    _batchStartWatchdog = null;
  }
  _batchRunning = false;
  var btn = document.getElementById('btnBatchRun');
  if (btn) btn.disabled = !batchHasPendingRows();
  var timer = document.getElementById('batchTimer');
  if (timer && options.hideTimer !== false) {
    timer.style.display = 'none';
    timer.textContent = '';
  }
  clearTabRunState('batch');
}

function syncBatchRunButton() {
  var btn = document.getElementById('btnBatchRun');
  if (!btn) return;
  // Recover an orphaned running latch. A real running batch always has at least
  // one row in the processing state before the browser can repaint.
  if (_batchRunning && !batchHasProcessingRows()) {
    resetStaleBatchRunState();
  }
  btn.disabled = _batchRunning || !batchHasPendingRows();
}

function setBatchMode(mode) {
  _batchMode = mode;
  document.getElementById('batchTabFormat').className = 'batch-mode-tab' + (mode==='format' ? ' active' : '');
  document.getElementById('batchTabBlind').className  = 'batch-mode-tab' + (mode==='blind'  ? ' active' : '');
  var summaryToggle = document.getElementById('batchSummaryToggle');
  if (summaryToggle) {
    summaryToggle.disabled = mode === 'blind';
    summaryToggle.title = mode === 'blind' ? 'CV Summary generation is available for Format All only' : '';
  }
}

function handleBatchFileSelect(files) {
  var added = 0;
  for (var i = 0; i < files.length; i++) {
    if (_batchFiles.length >= 10) { showToast('Maximum 10 files reached', 'err'); break; }
    var file = files[i];
    var ext = file.name.split('.').pop().toLowerCase();
    var SUPPORTED = ['pdf','docx','doc','txt','rtf','odt','png','jpg','jpeg'];
  if (!SUPPORTED.includes(ext)) { showToast(file.name + ' is not PDF/DOCX — skipped', 'err'); continue; }
    var id = 'bf_' + Date.now() + '_' + i;
    _batchFiles.push({ file: file, id: id, status: 'pending', cvData: null, filename: '', cost: 0 });
    added++;
  }
  // Clear input so same files can be re-added after clear
  document.getElementById('batchFileInput').value = '';
  renderBatchList();
  if (_batchFiles.length > 0) document.getElementById('batchControls').style.display = 'flex';
  // Adding fresh work must never inherit a disabled Start button or orange
  // running badge from an interrupted/cleared earlier batch.
  if (!_batchRunning || !batchHasProcessingRows()) resetStaleBatchRunState();
  syncBatchRunButton();
  updateBatchSummary();
}

function renderBatchList() {
  var list = document.getElementById('batchFileList');
  list.innerHTML = _batchFiles.map(function(bf) {
    var icon = bf.status === 'pending'     ? '📄'
             : bf.status === 'processing'  ? '<div class="batch-spinner"></div>'
             : bf.status === 'done-ok'     ? '✅'
             : bf.status === 'done-blind'  ? '🔒'
             : '❌';
    var itemClass = 'batch-file-item' +
      (bf.status === 'processing' ? ' processing' :
       bf.status === 'done-ok'    ? ' done-ok'    :
       bf.status === 'done-blind' ? ' done-blind' :
       bf.status === 'done-err'   ? ' done-err'   : '');
    var statusText = bf.status === 'pending'    ? 'Waiting...'
                   : bf.status === 'processing' ? (bf.stepLabel || 'Processing...')
                   : bf.status === 'done-ok'    ? 'Done — ' + (bf.filename || bf.file.name) + (bf.charCount ? ' · ' + bf.charCount.toLocaleString() + ' chars' : '')
                   : bf.status === 'done-blind' ? 'Blinded — ' + (bf.filename || bf.file.name)
                   : 'Error: ' + (bf.error || 'Unknown error');
    var statusClass = bf.status === 'done-err' ? 'batch-file-status err' : 'batch-file-status';
    var costHtml = bf.cost > 0
      ? '<span class="batch-file-cost show">💰 ' + (bf.cost < 0.0001 ? '<$0.0001' : '$' + bf.cost.toFixed(4)) + '</span>'
      : '<span class="batch-file-cost"></span>';
    var isDone = bf.status === 'done-ok' || bf.status === 'done-blind' || bf.status === 'done-err';
    var isProc = bf.status === 'processing';
    var timerClass = 'batch-file-timer' + (isDone ? ' show done' : isProc ? ' show' : '');
    var timerVal = bf.elapsed != null ? (bf.elapsed.toFixed(1) + 's' + (isDone ? ' ✓' : '')) : '0.0s';
    var timerHtml = (isDone || isProc)
      ? '<span class="' + timerClass + '" id="t-' + bf.id + '">' + timerVal + '</span>'
      : '<span class="batch-file-timer" id="t-' + bf.id + '"></span>';
    var jaHtml;
    if (bf.jaClass === 'show ja-skip') {
      // Render editable email input inline
      jaHtml = '<span class="batch-ja-status show ja-skip" id="ja-' + bf.id + '" title="No email was detected in this CV. Enter one to upload it to JobAdder.">'
        + '<input type="email" class="batch-ja-email-required" placeholder="Enter email for JobAdder" aria-label="Enter candidate email for JobAdder" value="' + escAttr(bf._manualEmail || '') + '" '
        + 'onchange="setBatchManualEmail(this,\'' + bf.id + '\')" '
        + 'onkeydown="if(event.key===\'Enter\'){event.preventDefault();this.blur();}" '
        + 'onclick="event.stopPropagation()" />'
        + '</span>';
    } else if (bf.jaStatus && bf.jaStatus.startsWith('✅')) {
      // Link — use innerHTML-safe version stored on bf
      jaHtml = '<span class="batch-ja-status ' + (bf.jaClass || '') + '" id="ja-' + bf.id + '">' + bf.jaStatus + '</span>';
    } else {
      jaHtml = '<span class="batch-ja-status ' + (bf.jaClass || '') + '" id="ja-' + bf.id + '">' + esc(bf.jaStatus || '') + '</span>';
    }
    var removeBtn = bf.status !== 'processing'
      ? '<button class="batch-file-remove" onclick="removeBatchFile(\'' + bf.id + '\')" title="Remove">✕</button>'
      : '';
    var dlBtn = (bf.status === 'done-ok' || bf.status === 'done-blind')
      ? '<button class="batch-file-dl" onclick="downloadSingleBatchFile(\'' + bf.id + '\')" title="Download">⬇ Download</button>'
      : '';

    // Build mini progress bar for processing/done/err states
    var progHtml = '';
    if (bf.status !== 'pending') {
      var steps = bf.progSteps || [];
      var pct   = bf.progPct  || 0;
      var fillClass = 'batch-prog-fill' +
        (bf.status === 'done-blind' ? ' blind' :
         bf.status === 'done-ok'    ? ' done'  :
         bf.status === 'done-err'   ? ' err'   : '');
      var stepsHtml = steps.map(function(s) {
        var sc = 'batch-prog-step' +
          (s.state === 'active' ? (' active' + (s.blind ? ' blind-step' : '')) :
           s.state === 'done'   ? ' done-step' : '');
        return '<span class="' + sc + '"><span class="sdot"></span>' + s.label + '</span>';
      }).join('<span style="color:var(--border2);font-size:9px;margin:0 1px">›</span>');
      progHtml = '<div class="batch-prog-wrap">'
        + '<div class="batch-prog-track"><div class="' + fillClass + '" style="width:' + pct + '%"></div></div>'
        + '<div class="batch-prog-steps">' + stepsHtml + '</div>'
        + '</div>';
    }

    return '<div class="' + itemClass + '" id="' + bf.id + '">'
      + '<div class="batch-status-icon" style="margin-top:2px">' + icon + '</div>'
      + '<div class="batch-file-info">'
      +   '<div class="batch-file-name">' + esc(bf.file.name) + '</div>'
      +   '<div class="' + statusClass + '">' + esc(statusText) + '</div>'
      +   progHtml
      + '</div>'
      + timerHtml
      + jaHtml
      + costHtml
      + dlBtn
      + removeBtn
      + '</div>';
  }).join('');
}

function removeBatchFile(id) {
  _batchFiles = _batchFiles.filter(function(bf) { return bf.id !== id; });
  renderBatchList();
  updateBatchSummary();
  if (_batchFiles.length === 0) document.getElementById('batchControls').style.display = 'none';
  syncBatchRunButton();
}

function clearBatch() {
  // Do not let a real in-flight request keep running against rows the user has
  // just removed. If the orange state is only stale (no processing row), reset
  // it immediately and allow a clean retry.
  if (_batchRunning && batchHasProcessingRows()) {
    showToast('Batch processing is still running. Wait for it to finish before clearing.', 'info');
    return;
  }
  _batchFiles = [];
  _batchBlobs = [];
  resetStaleBatchRunState();
  renderBatchList();
  document.getElementById('batchControls').style.display = 'none';
  document.getElementById('btnBatchDownload').disabled = true;
  document.getElementById('batchTotalCost').style.display = 'none';
  document.getElementById('batchSummary').textContent = '';
  var batchTimerEl = document.getElementById('batchTimer');
  if (batchTimerEl) { batchTimerEl.style.display = 'none'; batchTimerEl.textContent = ''; }
}

function updateBatchSummary() {
  var total = _batchFiles.length;
  var done = _batchFiles.filter(function(b){ return b.status==='done-ok'||b.status==='done-blind'; }).length;
  var errs = _batchFiles.filter(function(b){ return b.status==='done-err'; }).length;
  var s = total + ' file' + (total!==1?'s':'');
  if (done > 0 || errs > 0) s += ' — ' + done + ' done' + (errs>0?' / '+errs+' failed':'');
  document.getElementById('batchSummary').textContent = s;
  // total cost
  var totalCost = _batchFiles.reduce(function(acc,bf){ return acc + (bf.cost||0); }, 0);
  var costEl = document.getElementById('batchTotalCost');
  if (totalCost > 0) {
    costEl.textContent = 'Total est. cost: ' + (totalCost < 0.001 ? '<$0.001' : '$' + totalCost.toFixed(4));
    costEl.style.display = 'inline';
  } else {
    costEl.style.display = 'none';
  }
}

// Helper: update one batch file's progress without full re-render
function batchSetProgress(bf, pct, stepLabel, steps) {
  bf.progPct   = pct;
  bf.stepLabel = stepLabel;
  bf.progSteps = steps;
  // Update only that item's DOM
  var el = document.getElementById(bf.id);
  if (!el) return;
  var fill = el.querySelector('.batch-prog-fill');
  if (fill) fill.style.width = pct + '%';
  var statusEl = el.querySelector('.batch-file-status');
  if (statusEl) statusEl.textContent = stepLabel;
  var stepEls = el.querySelectorAll('.batch-prog-step');
  steps.forEach(function(s, idx) {
    if (!stepEls[idx]) return;
    var sc = 'batch-prog-step' +
      (s.state === 'active' ? (' active' + (s.blind ? ' blind-step' : '')) :
       s.state === 'done'   ? ' done-step' : '');
    stepEls[idx].className = sc;
  });
}

async function runBatch() {
  if (_batchRunning) {
    if (batchHasProcessingRows()) return;
    // Recover from an interrupted earlier attempt that left the latch/button
    // disabled while every file is still visibly Waiting.
    resetStaleBatchRunState();
  }
  var route = aiRoutePayload('cv_batch');
  var key = route.api_key;
  if (!key) { showToast('Save an API key for Batch Format route', 'err'); return; }
  var batchIsBlind = _batchMode === 'blind';
  var batchSummaryToggle = document.getElementById('batchSummaryToggle');
  var withBatchSummary = !batchIsBlind && !!(batchSummaryToggle && batchSummaryToggle.checked);
  var batchSummaryRoute = withBatchSummary ? aiRoutePayload('summary') : null;
  if (withBatchSummary && !batchSummaryRoute.api_key) { showToast('Save an API key for the CV Summary route or turn off Generate CV Summary', 'err'); return; }
  var batchSummaryDetail = withBatchSummary ? getCvSummaryDetailPreference('batch') : 'concise';

  // Only process pending files
  var pending = _batchFiles.filter(function(bf){ return bf.status === 'pending'; });
  if (pending.length === 0) { showToast('No pending files to process', 'info'); return; }

  var _tabRun = markTabRunning('batch');
  _batchRunning = true;
  _batchBlobs = [];
  document.getElementById('btnBatchRun').disabled = true;
  document.getElementById('btnBatchDownload').disabled = true;

  // Startup watchdog: the first pending row is switched to processing
  // synchronously below. If that never happens, a startup exception occurred;
  // release the disabled button/orange tab instead of leaving Batch Format
  // permanently stuck at Waiting.
  if (_batchStartWatchdog) clearTimeout(_batchStartWatchdog);
  _batchStartWatchdog = setTimeout(function() {
    _batchStartWatchdog = null;
    if (_batchRunning && !batchHasProcessingRows() && batchHasPendingRows()) {
      resetStaleBatchRunState();
      syncBatchRunButton();
      showToast('Batch could not start. The controls were reset — please try again.', 'err');
    }
  }, 750);

  // ── Batch timer ───────────────────────────────────────────────────
  var _batchStartTime = Date.now();
  var _batchTimerEl = document.getElementById('batchTimer');
  if (_batchTimerEl) {
    _batchTimerEl.textContent = '0s';
    _batchTimerEl.style.display = 'inline';
  }
  if (_batchTimerInterval) clearInterval(_batchTimerInterval);
  _batchTimerInterval = setInterval(function() {
    var elapsed = ((Date.now() - _batchStartTime) / 1000).toFixed(1);
    if (_batchTimerEl) _batchTimerEl.textContent = elapsed + 's';
  }, 100);

  var isBlind = batchIsBlind;
  // Snapshot the preference once so changing Settings during a running batch
  // cannot produce a ZIP containing mixed Left and Justify documents.
  var batchDocumentAlignment = getCvTextAlignment();
  // Keep every blinded file in this run consistent if Settings changes while
  // a large batch is still processing.
  var batchBlindCandidateGenderNeutral = isBlind && getCvBlindCandidateGenderNeutralization();

  // Step definitions vary by mode
  function makeSteps(activeIdx) {
    var defs = isBlind
      ? ['Extract', 'Parse', 'Blind', 'Generate DOCX']
      : (withBatchSummary ? ['Extract', 'Parse', 'Summary', 'Generate DOCX'] : ['Extract', 'Parse', 'Generate DOCX']);
    return defs.map(function(label, i) {
      return {
        label: label,
        blind: isBlind && label === 'Blind',
        state: i < activeIdx ? 'done' : i === activeIdx ? 'active' : ''
      };
    });
  }

  var pcts = isBlind || withBatchSummary ? [5, 25, 55, 80] : [5, 35, 75];
  var donePct = 100;

  for (var i = 0; i < _batchFiles.length; i++) {
    var bf = _batchFiles[i];
    if (bf.status !== 'pending') continue;

    bf.status    = 'processing';
    bf.cost      = 0;
    bf.usage     = normalizeUsageClient({});
    bf.elapsed   = 0;
    bf.progPct   = pcts[0];
    bf.stepLabel = 'Extracting text…';
    var _fileStartTime = Date.now();
    // Tick the per-file timer every 100ms
    var _fileTimerInterval = setInterval(function() {
      bf.elapsed = (Date.now() - _fileStartTime) / 1000;
      var el = document.getElementById('t-' + bf.id);
      if (el) el.textContent = bf.elapsed.toFixed(1) + 's';
    }, 100);
    bf.progSteps = makeSteps(0);
    renderBatchList();
    if (_batchStartWatchdog) {
      clearTimeout(_batchStartWatchdog);
      _batchStartWatchdog = null;
    }

    try {
      // ── Step 0: Extract text ─────────────────────────────────────────────
      var formData = new FormData();
      formData.append('file', bf.file);
      var exRes = await fetchWithTimeout('/extract-text', { method: 'POST', body: formData }, CV_EXTRACT_TEXT_TIMEOUT_MS);
      var exData = await exRes.json();
      if (exData.error) throw new Error('Extraction: ' + exData.error);
      cvRequireCompleteExtraction(exData, 'Batch formatting');
      var rawText = exData.text;
      var batchExtractLevels = Array.isArray(exData.bullet_levels) ? exData.bullet_levels : null;
      bf.charCount = rawText.length;

      // ── Step 1: Parse CV ─────────────────────────────────────────────────
      batchSetProgress(bf, pcts[1], 'Parsing ' + (cvParseIsLong(rawText) ? 'long CV' : 'CV') + ' with ' + route.provider_label + '…', makeSteps(1));
      var pRes = await fetchWithTimeout('/parse', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ api_key: key, api_key_slot: route.api_key_slot, cv_text: rawText, model: route.model, provider: route.provider }) }, cvParseTimeoutMs(rawText));
      var pData = await pRes.json().catch(function(){ return {}; });
      if (!pRes.ok || pData.error) {
        recordPaidAiFailure('Batch CV parse failed — ' + bf.file.name, pData, route.model, route.provider);
        throw new Error('Parse: ' + normalizeAiProviderError(pData.error || ('API error ' + pRes.status), route));
      }
      var cvData = pData.data;
      var batchLabelLevels = Array.isArray(pData.bullet_levels) ? pData.bullet_levels : null;
      if (pData.warning) showToast(bf.file.name + ': ' + pData.warning, 'info');
      bf.cost += responseCost(pData, route.model, route.provider);
      bf.usage = mergeUsageClient(bf.usage, pData.usage || {});

      if (withBatchSummary) {
        batchSetProgress(bf, pcts[2], 'Filling Summary placeholder with ' + batchSummaryRoute.provider_label + '…', makeSteps(2));
        var batchSummaryResult = await requestFormattingSummary(rawText, batchSummaryRoute, batchSummaryDetail);
        cvData.summary_bullets = batchSummaryResult.bullets.slice();
        bf.cost += batchSummaryResult.cost;
        bf.usage = mergeUsageClient(bf.usage, batchSummaryResult.usage);
      }

      // Save real name NOW before blind call can overwrite it with "Candidate"
      var parsedCandidateName = (cvData.candidate && cvData.candidate.name) || '';
      var filenameFallback = extractNameFromFilename(bf.file.name);
      var realBatchName = (parsedCandidateName && parsedCandidateName.toLowerCase() !== 'candidate')
        ? parsedCandidateName
        : (filenameFallback || parsedCandidateName);

      // ── Step 2 (blind only): Blind CV ────────────────────────────────────
      if (isBlind) {
        batchSetProgress(bf, pcts[2], 'Blinding identity & company names…', makeSteps(2));
        var bRes = await fetchWithTimeout('/blind', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ api_key: key, api_key_slot: route.api_key_slot, cv_data: cvData, model: route.model, provider: route.provider, neutralize_candidate_gender: batchBlindCandidateGenderNeutral }) }, 180000);
        var bData = await bRes.json().catch(function(){ return {}; });
        if (!bRes.ok || bData.error) {
          recordPaidAiFailure('Batch CV blinding failed — ' + bf.file.name, bData, route.model, route.provider);
          throw new Error('Blind: ' + normalizeAiProviderError(bData.error || ('API error ' + bRes.status), route));
        }
        cvData = bData.data;
        bf.cost += responseCost(bData, route.model, route.provider);
        bf.usage = mergeUsageClient(bf.usage, bData.usage || {});
      }

      // ── Step 3: Generate DOCX ─────────────────────────────────────────────
      var docxStepIdx = isBlind || withBatchSummary ? 3 : 2;
      batchSetProgress(bf, pcts[docxStepIdx], 'Generating DOCX…', makeSteps(docxStepIdx));
      var dRes = await fetchWithTimeout('/generate-docx', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ data: cvData, alignment: batchDocumentAlignment, summary_box_autofit: getCvSummaryBoxAutoFit(), bullet_levels: cvMergeLevelLists(batchExtractLevels, batchLabelLevels) }) }, 60000);
      if (!dRes.ok) { var err2 = await dRes.json(); throw new Error('DOCX: ' + (err2.error||'Failed')); }
      var blob = await dRes.blob();

      // Build filename using real name saved before blind
      var displayName = realBatchName
        ? toTitleCase(realBatchName)
        : bf.file.name.replace(/\.[^.]+$/, '');
      var fname = isBlind ? 'Hyppies CV - ' + displayName + ' (Blinded).docx' : 'Hyppies CV - ' + displayName + '.docx';

      bf.cvData   = cvData;
      bf.filename = fname;
      bf.downloadKind = isBlind ? 'blind' : 'formatted';
      bf.progPct  = donePct;
      bf.progSteps = makeSteps(99); // all done
      bf.status   = isBlind ? 'done-blind' : 'done-ok';
      _batchBlobs.push({ filename: fname, blob: blob, kind: bf.downloadKind });
      bf._docxBlob = blob; // store for manual email upload
      // Record to stats
      bf._statsRecordId = statsRecord(displayName, isBlind ? 'blind' : 'format', bf.cost, route.model, '', route.provider, statsMetaFromResponse({usage:bf.usage,cost:bf.cost,model:route.model,provider:route.provider}, route.model, route.provider)); // exact row URL is attached after upload

      // ── JobAdder auto-upload ──────────────────────────────────────
      if (window._jaToken && window._jaAutoUpload !== false) {
        renderBatchList(); // ensure DOM is fresh before looking up jaEl
        var jaEl = document.getElementById('ja-' + bf.id);
        var jaEmail = (cvData && cvData.candidate && cvData.candidate.email)
          ? cvData.candidate.email : (bf._manualEmail || '');
        if (!jaEmail) {
          // No email found — render editable input via renderBatchList
          bf.jaStatus = '📧 Enter email';
          bf.jaClass  = 'show ja-skip';
          renderBatchList();
        } else {
          bf.jaStatus = '☁ Uploading…';
          renderBatchList(); // re-render so jaEl is fresh and shows uploading state
          jaEl = document.getElementById('ja-' + bf.id);
          bf.jaClass = 'show uploading'; if (jaEl) { jaEl.textContent = '☁ Uploading…'; jaEl.className = 'batch-ja-status show uploading'; }
          try {
            var bfOrigAB = await bf.file.arrayBuffer();
            var jaCanId = await batchUploadToJobAdder(blob, fname, jaEmail, cvData, new Blob([bfOrigAB]), bf.file.name);
            var jaLink = jaCanId ? await jaProfileUrlAsync(jaCanId) : '';
            bf.jaStatus = jaLink
              ? '✅ <a href="' + escAttr(jaLink) + '" target="_blank" rel="noopener noreferrer" style="color:#2f855a;font-weight:700;text-decoration:underline;">View ↗</a>'
              : '✅ Uploaded';
            bf.jaClass = 'show uploaded';
            renderBatchList(); // re-render with stored state — badge stays visible
            // Attach the URL to this exact Batch Format dashboard row.
            if (jaLink) statsAttachJobAdderUrl(bf._statsRecordId, jaLink, displayName, [isBlind ? 'blind' : 'format']);
          } catch(jaErr) {
            var errShort = (jaErr.message || 'Unknown error').split('|')[0].trim().substring(0, 50);
            bf.jaStatus = '❌ Upload failed';
            bf.jaClass  = 'show ja-err';
            renderBatchList();
            jaEl = document.getElementById('ja-' + bf.id);
            if (jaEl) jaEl.title = jaErr.message;
            showToast('⚠ JobAdder upload failed for "' + displayName + '": ' + errShort, 'err');
            console.error('[JA Batch] Upload failed:', jaErr.message);
          }
        }
      }

    } catch(e) {
      bf.status   = 'done-err';
      bf.progPct  = 100;
      bf.error    = e.message;
    }

    // Stop per-file timer and freeze at final elapsed
    clearInterval(_fileTimerInterval);
    bf.elapsed = (Date.now() - _fileStartTime) / 1000;
    var _timerEl = document.getElementById('t-' + bf.id);
    if (_timerEl) {
      _timerEl.textContent = bf.elapsed.toFixed(1) + 's ✓';
      _timerEl.className = 'batch-file-timer show done';
    }

    renderBatchList();
    updateBatchSummary();
  }

  _batchRunning = false;
  document.getElementById('btnBatchRun').disabled = false;
  var okCount = _batchFiles.filter(function(b){ return b.status==='done-ok'||b.status==='done-blind'; }).length;

  // ── Stop batch timer ─────────────────────────────────────────────
  if (_batchTimerInterval) {
    clearInterval(_batchTimerInterval);
    _batchTimerInterval = null;
  }
  if (_batchStartWatchdog) {
    clearTimeout(_batchStartWatchdog);
    _batchStartWatchdog = null;
  }
  var batchElapsed = ((Date.now() - _batchStartTime) / 1000).toFixed(1);
  if (_batchTimerEl) _batchTimerEl.textContent = batchElapsed + 's ✓';
  syncBatchRunButton();

  if (okCount > 0) {
    document.getElementById('btnBatchDownload').disabled = false;
    showToast(okCount + ' CV' + (okCount!==1?'s':'') + ' processed in ' + batchElapsed + 's! Click Download All', 'ok');
    markTabDone('batch', _tabRun);
  } else {
    showToast('All files failed to process', 'err');
    markTabFailed('batch', _tabRun);
  }
}

async function downloadSingleBatchFile(id) {
  var bf = _batchFiles.find(function(f) { return f.id === id; });
  if (!bf || !bf.filename) { showToast('File not ready', 'err'); return; }
  var item = _batchBlobs.find(function(b) { return b.filename === bf.filename; });
  if (!item) { showToast('File not found in memory', 'err'); return; }
  var kind = item.kind || bf.downloadKind || (bf.status === 'done-blind' ? 'blind' : 'formatted');
  var result = await cvStudioSaveDownloadBlob(item.blob, item.filename, kind);
  if (result.method === 'folder') showToast('Saved ' + result.filename + ' to ' + (result.folder || 'the selected folder') + '.', 'ok');
  else if (result.configured) showToast('Download was not saved: ' + result.fallbackReason + '. Check or choose the folder in Settings → Downloads.', 'err');
  else showToast('Downloaded ' + result.filename + ' using the browser Downloads folder.', 'ok');
}

async function downloadBatchZip() {
  if (_batchBlobs.length === 0) { showToast('No processed files to download', 'err'); return; }
  var firstItem = _batchBlobs[0];
  var firstFile = _batchFiles.find(function(file){ return file.filename === firstItem.filename; });
  var kind = firstItem.kind || (firstFile && firstFile.downloadKind) || (firstFile && firstFile.status === 'done-blind' ? 'blind' : 'formatted');
  var destination = await cvStudioPrepareDownloadDestination(kind);
  if (destination.statusFailed) {
    showToast('Download was not started: ' + destination.fallbackReason + '. Reload CV Studio or check Settings → Downloads.', 'err');
    return;
  }
  if (!destination.handle) {
    _batchBlobs.forEach(function(item, index) {
      setTimeout(function(){ cvStudioSaveDownloadBlob(item.blob, item.filename, kind, destination); }, index * 300);
    });
    showToast(
      (destination.configured ? 'Selected folder needs write access. ' : '') +
      'Downloading ' + _batchBlobs.length + ' file' + (_batchBlobs.length !== 1 ? 's' : '') + ' using the browser Downloads folder...',
      destination.configured ? 'err' : 'ok'
    );
    return;
  }
  var folderCount = 0;
  var failedCount = 0;
  for (var i = 0; i < _batchBlobs.length; i += 1) {
    var item = _batchBlobs[i];
    var result = await cvStudioSaveDownloadBlob(item.blob, item.filename, kind, destination);
    if (result.method === 'folder') folderCount += 1;
    else if (result.method === 'failed') failedCount += 1;
  }
  if (folderCount === _batchBlobs.length) showToast('Saved ' + folderCount + ' file' + (folderCount !== 1 ? 's' : '') + ' to the selected folder.', 'ok');
  else if (failedCount) showToast('Saved ' + folderCount + ' file' + (folderCount !== 1 ? 's' : '') + '; ' + failedCount + ' could not be saved. Check the folder in Settings → Downloads.', 'err');
  else showToast('Downloaded ' + _batchBlobs.length + ' file' + (_batchBlobs.length !== 1 ? 's' : '') + (folderCount ? ' (' + folderCount + ' saved to the selected folder)' : ' using the browser Downloads folder') + '.', 'ok');
}
