async function startFormat(blind) {
  blind = !!blind;
  var blindCandidateGenderNeutral = blind && getCvBlindCandidateGenderNeutralization();
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
  var withFormattingReview = !blind && typeof getCvFormattingReview === 'function' && getCvFormattingReview();
  cvResetFormattingReview();
  var reviewSequence = window._cvFormattingReviewSequence;

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
    var res = await fetchWithTimeout('/parse', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({api_key: key, api_key_slot: route.api_key_slot, cv_text: raw, model: route.model, provider: route.provider, auto_correct_language: getCvAutoCorrectLanguage()}) }, cvParseTimeoutMs(raw));
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
    // The /parse source check's warning. A toast alone is not enough: the
    // "Parsed! Generating DOCX..." toast below replaces it almost at once, so it
    // is also kept above the preview once that renders.
    var parseWarning = cvParseWarningText(data, blind);
    // Pay removed from the Summary box is kept on screen like the source check,
    // and holds auto-upload the same way -- only when that parsed summary is the
    // one used, not replaced by a linked or an automatic summary.
    if (data.summary_pay_removed && !linkedSummaryBullets.length && !withAutomaticSummary) parseWarning = cvJoinWarnings(parseWarning, cvSummaryPayNote(data.summary_pay_removed, false));
    if (parseWarning) showToast(parseWarning, 'warn');
    _runCost += responseCost(data, route.model, route.provider);
    _runUsage = mergeUsageClient(_runUsage, data.usage || {});
    if (withAutomaticSummary) {
      setProgress(44, 'Step 2 — Filling the Summary placeholder with ' + automaticSummaryRoute.provider_label + '…', 2, totalSteps);
      setOutput('<div style="color:var(--text3);font-style:italic;padding:20px;">Generating source-grounded CV Summary…</div>');
      var summaryResult = await requestFormattingSummary(raw, automaticSummaryRoute, singleSummaryDetail);
      _parsedData.summary_bullets = summaryResult.bullets.slice();
      if (summaryResult.pay_removed) parseWarning = cvJoinWarnings(parseWarning, cvSummaryPayNote(summaryResult.pay_removed, summaryResult.pay_only));
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

      var bRes = await fetchWithTimeout('/blind', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({api_key: key, api_key_slot: route.api_key_slot, cv_data: _parsedData, model: route.model, provider: route.provider, neutralize_candidate_gender: blindCandidateGenderNeutral}) }, 180000);
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
      if (bData.summary_pay_removed) parseWarning = cvJoinWarnings(parseWarning, cvSummaryPayNote(bData.summary_pay_removed, false));
      document.getElementById('blindBadge').style.display = 'inline-flex';
    }

    renderPreview(_parsedData);
    // After the preview, because rendering it replaces the whole output panel.
    cvShowParseWarningBanner(parseWarning);
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
    // The Word file's own last net can remove pay the preview still showed.
    var docxPayRemoved = res2.headers && res2.headers.get ? res2.headers.get('X-CV-Summary-Pay-Removed') : null;
    if (docxPayRemoved) {
      var docxPayNote = cvSummaryPayNote(docxPayRemoved, false);
      parseWarning = cvJoinWarnings(parseWarning, docxPayNote);
      cvShowParseWarningBanner(docxPayNote);
    }
    window._docxBlob = blob;
    window._originalBlob  = null; // reset — set below if file was uploaded
    window._isBlind  = blind;
    if (withFormattingReview) {
      setProgress(94, 'Checking formatting against the original CV…', docxStep + 1, totalSteps + 1);
      var formattingReview = await cvRunFormattingReview(raw, _parsedData, route, parseWarning);
      if (formattingReview.stale) {
        // Editing the input leaves the completed file available, while clearing
        // or starting a different run owns its own controls.
        if (window._cvFormattingReview && window._cvFormattingReview.sequence === reviewSequence &&
            window._cvFormattingReviewSequence === reviewSequence) {
          document.getElementById('btnFormat').disabled = false;
          document.getElementById('btnBlind').disabled = false;
          document.getElementById('btnDocx').disabled = !window._docxBlob;
          stopTimer(); hideProgress();
          cvRenderFormattingReview(window._cvFormattingReview, 'The input changed during this check. Format the current CV before checking it again.');
        }
        return;
      }
      _runCost += formattingReview.cost;
      _runUsage = mergeUsageClient(_runUsage, formattingReview.usage);
      if (formattingReview.warning) {
        parseWarning = cvJoinWarnings(parseWarning, formattingReview.warning);
        cvShowParseWarningBanner(formattingReview.warning);
      }
    }
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
    // Finishing on a green "Done!" would tell the recruiter the CV is ready when
    // the source check has just said it may be incomplete.
    if (parseWarning) showToast('Done — but read the warning above the preview before sending this CV', 'warn');
    else showToast('Done! Click Download DOCX', 'ok');
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
    // Auto-upload if JA connected, auto-upload enabled, and email found. A CV the
    // source check flagged is held: uploading it half a second later would send
    // it before the recruiter could read the warning. The Upload button still
    // sends it once it has been checked.
    if (window._jaToken && window._jaAutoUpload !== false && parsedEmail.trim()) {
      if (parseWarning) {
        document.getElementById('jaStatus').textContent = '⏸ Auto-upload paused — check the warning above, then upload.';
      } else {
        setTimeout(function() { uploadToJobAdder(); }, 500);
      }
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

function cvReviewCurrentSource() {
  return _activeInputTab === 'upload' ? String(_extractedText || '') : String(document.getElementById('cvInput').value || '').trim();
}
function cvReviewIsCurrent(state) {
  return !!state && window._cvFormattingReview === state && !window._isBlind &&
    state.sequence === window._cvFormattingReviewSequence && state.source === cvReviewCurrentSource() &&
    state.snapshot === JSON.stringify(_parsedData) && state.blob === window._docxBlob;
}
function cvReviewBusy(state, busy) {
  var ids = ['btnFormat', 'btnBlind', 'btnDocx', 'btnJA'];
  if (busy) {
    state.controls = {};
    ids.forEach(function(id) { var node = document.getElementById(id); if (node) { state.controls[id] = node.disabled; node.disabled = true; } });
  } else if (state.controls) {
    ids.forEach(function(id) { var node = document.getElementById(id); if (node) node.disabled = state.controls[id]; });
    state.controls = null;
  }
  state.busy = busy;
}
function cvResetFormattingReview() {
  var previous = window._cvFormattingReview;
  if (previous && previous.busy) cvReviewBusy(previous, false);
  window._cvFormattingReviewSequence = (window._cvFormattingReviewSequence || 0) + 1;
  window._cvFormattingReview = null;
  var panel = document.getElementById('cvFormattingReviewPanel');
  if (panel) { panel.textContent = ''; panel.style.display = 'none'; }
}
function cvReviewText(parent, tag, text) {
  var node = document.createElement(tag);
  node.textContent = String(text || '');
  node.style.whiteSpace = 'pre-wrap'; node.style.overflowWrap = 'anywhere';
  parent.appendChild(node); return node;
}
function cvReviewButton(parent, label, handler, disabled) {
  var button = document.createElement('button');
  button.type = 'button'; button.className = 'sec'; button.textContent = label;
  button.style.marginRight = '8px'; button.onclick = handler; button.disabled = !!disabled;
  parent.appendChild(button);
}
function cvReviewValueText(value) {
  if (typeof value === 'string') return value;
  if (!value || typeof value !== 'object') return '';
  var lines = [];
  ['company', 'institution', 'degree', 'title', 'date_range', 'major', 'grade', 'section_heading'].forEach(function(key) {
    if (typeof value[key] === 'string') lines.push(value[key]);
  });
  if (Array.isArray(value.roles)) value.roles.forEach(function(role) { lines.push(cvReviewValueText(role)); });
  if (Array.isArray(value.bullets)) value.bullets.forEach(function(bullet) { if (typeof bullet === 'string') lines.push('• ' + bullet); });
  return lines.join('\n');
}
function cvRenderFormattingReview(state, message) {
  var panel = document.getElementById('cvFormattingReviewPanel');
  if (!panel) return;
  cvBuildFormattingReviewPanel(panel, state, message, {apply: cvApplyFormattingReview,
    undo: cvUndoFormattingReview, again: cvCheckFormattingReviewAgain});
}
function cvBuildFormattingReviewPanel(panel, state, message, handlers) {
  panel.replaceChildren(); panel.style.display = 'block';
  cvReviewText(panel, 'strong', 'AI formatting review');
  cvReviewText(panel, 'p', message || (state.review && state.review.message) || 'Checking against the original CV…');
  if (state.review && Array.isArray(state.review.issues)) state.review.issues.forEach(function(issue) {
    var block = document.createElement('div');
    block.style.borderTop = '1px solid var(--border)'; block.style.paddingTop = '10px'; block.style.marginTop = '10px';
    cvReviewText(block, 'strong', issue.message);
    cvReviewText(block, 'p', 'From the original CV:'); cvReviewText(block, 'blockquote', issue.source_quote);
    var operation = issue.operation;
    if (issue.can_apply === true && operation) {
      cvReviewText(block, 'p', 'Suggested fix:');
      if (operation.op === 'replace') cvReviewText(block, 'p', String(operation.before || '(empty)') + ' → ' + cvReviewValueText(operation.value));
      else if (operation.op === 'move') {
        var parts = operation.path.split('/'), entry = state.base.work_experiences[Number(parts[2])];
        cvReviewText(block, 'p', 'Move to ' + entry.company + ' — ' + entry.roles[Number(parts[4])].title + ': ' + operation.before);
      }
      else cvReviewText(block, 'p', 'Restore:\n' + cvReviewValueText(operation.value));
      cvReviewButton(block, 'Apply fix', function() { handlers.apply(issue.id); }, handlers.disabled);
    } else cvReviewText(block, 'p', issue.reason || 'Please inspect this manually; no automatic fix is available.');
    panel.appendChild(block);
  });
  if (state.undo) cvReviewButton(panel, 'Undo fix', handlers.undo, handlers.disabled);
  if (state.review || state.undo || message) cvReviewButton(panel, 'Check again (extra AI call)', handlers.again, handlers.disabled);
}
async function cvRunFormattingReview(source, data, route, warning) {
  var previous = window._cvFormattingReview;
  var state = {source: source, snapshot: JSON.stringify(data), blob: window._docxBlob,
    sequence: window._cvFormattingReviewSequence, warning: warning || '', review: null, base: null,
    busy: !!(previous && previous.busy), controls: previous && previous.controls};
  window._cvFormattingReview = state;
  cvRenderFormattingReview(state);
  try {
    var response = await fetchWithTimeout('/generate-ai', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({feature: 'cv_format_review', source_cv_text: source, cv_data: data,
        api_key: route.api_key, api_key_slot: route.api_key_slot, model: route.model, provider: route.provider})}, cvParseTimeoutMs(source));
    var text = await response.text(), result;
    try { result = JSON.parse(text); } catch (e) { throw new Error('The review did not return a readable answer.'); }
    if (!response.ok || result.error) {
      recordPaidAiFailure('CV formatting review failed', result, route.model, route.provider);
      throw new Error(normalizeAiProviderError(result.error || 'Review failed', route));
    }
    var reviewCost = responseCost(result, route.model, route.provider), reviewUsage = result.usage || {};
    if (!cvReviewIsCurrent(state)) {
      // The completed paid check belongs in history even when the input was
      // cleared or replaced. It must not alter the new CV's running total.
      statsRecord((data.candidate || {}).name || 'Unknown', 'format_review', reviewCost, route.model, '', route.provider,
        statsMetaFromResponse({usage: reviewUsage, cost: reviewCost, model: route.model, provider: route.provider}, route.model, route.provider));
      return {stale: true};
    }
    var review = result.format_review;
    if (!review || !Array.isArray(review.issues) || !['reviewed', 'unavailable'].includes(review.status) || !result.format_review_base) {
      review = {status: 'unavailable', issues: [], message: 'The review answer could not be verified. Your existing CV is unchanged.'};
    }
    state.review = review; state.base = result.format_review_base;
    cvRenderFormattingReview(state);
    return {accounted: true, cost: reviewCost, usage: reviewUsage,
      warning: review.status === 'unavailable' ? 'AI formatting review was unavailable. Compare this CV with the original before sending.' :
        (review.issues.length ? 'AI formatting review found possible mistakes. Read its suggestions before sending this CV.' : '')};
  } catch (e) {
    if (!cvReviewIsCurrent(state)) return {stale: true};
    cvRenderFormattingReview(state, 'The AI check could not finish. Your completed CV is still available. ' + (e.message || 'Check the original before sending.'));
    return {cost: 0, usage: {}, warning: 'AI formatting review could not finish. Compare this CV with the original before sending.'};
  }
}
async function cvApplyFormattingReview(issueId) {
  var state = window._cvFormattingReview;
  if (!cvReviewIsCurrent(state) || state.busy || !state.review) { showToast('This suggestion is out of date. Check the current CV again.', 'warn'); return; }
  var issue = state.review.issues.find(function(item) { return item.id === issueId && item.can_apply === true; });
  if (!issue) return;
  var beforeApply = {data: JSON.parse(state.snapshot), blob: state.blob};
  cvReviewBusy(state, true);
  cvRenderFormattingReview(Object.assign({}, state, {review: null}), 'Applying the selected fix and rebuilding the Word file…');
  try {
    var response = await fetchWithTimeout('/generate-ai', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({feature: 'cv_format_review_apply', source_cv_text: state.source,
        cv_data: state.base, review: state.review, issue_id: issueId})}, 60000);
    var result = JSON.parse(await response.text());
    if (!response.ok || result.error || !result.data || !result.format_review_applied) throw new Error(result.error || 'The fix could not be verified.');
    if (!cvReviewIsCurrent(state)) return;
    var reviewSummaryAutoFit = getCvSummaryBoxAutoFit();
    var generated = await fetchWithTimeout('/generate-docx', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({data: result.data, format_review_applied: result.format_review_applied,
        alignment: getCvTextAlignment(), summary_box_autofit: reviewSummaryAutoFit,
        bullet_levels: cvMergeLevelLists(_extractedBulletLevels, _labelBulletLevels)})}, 60000);
    if (!generated.ok) throw new Error('The corrected Word file could not be generated.');
    if (!generated.headers || generated.headers.get('X-CV-Format-Review-Applied') !== '1') throw new Error('The corrected Word file could not be verified.');
    var blob = await generated.blob();
    if (!cvReviewIsCurrent(state)) return;
    state.undo = beforeApply;
    _parsedData = result.data; window._docxBlob = blob;
    state.snapshot = JSON.stringify(_parsedData); state.blob = blob; state.review = null;
    renderPreview(JSON.parse(state.snapshot)); cvShowParseWarningBanner(state.warning);
    cvRenderFormattingReview(state, 'Fix applied. Check the corrected preview before sending. Other suggestions need a new check.');
    var jaStatus = document.getElementById('jaStatus');
    if (jaStatus) jaStatus.textContent = 'Fix applied — check the corrected preview, then upload manually.';
    showToast('Fix applied to the preview and Word file', 'ok');
  } catch (e) {
    if (cvReviewIsCurrent(state)) {
      if (state.undo === beforeApply) {
        _parsedData = beforeApply.data; window._docxBlob = beforeApply.blob;
        state.snapshot = JSON.stringify(_parsedData); state.blob = beforeApply.blob; state.undo = null;
        try { renderPreview(JSON.parse(state.snapshot)); cvShowParseWarningBanner(state.warning); } catch (restoreError) {}
      }
      state.review = null;
      cvRenderFormattingReview(state, 'The fix was not applied. Your previous CV is unchanged. ' + (e.message || 'Please check again.'));
      showToast('Fix not applied — previous CV retained', 'warn');
    }
  } finally {
    if (window._cvFormattingReview === state) cvReviewBusy(state, false);
  }
}
function cvUndoFormattingReview() {
  var state = window._cvFormattingReview;
  if (!cvReviewIsCurrent(state) || state.busy || !state.undo) return;
  _parsedData = state.undo.data; window._docxBlob = state.undo.blob;
  state.snapshot = JSON.stringify(_parsedData); state.blob = window._docxBlob; state.undo = null;
  renderPreview(JSON.parse(state.snapshot)); cvShowParseWarningBanner(state.warning);
  cvRenderFormattingReview(state, 'Previous CV restored. Check again before applying another suggestion.');
}
async function cvCheckFormattingReviewAgain() {
  var state = window._cvFormattingReview;
  if (!cvReviewIsCurrent(state) || state.busy) { showToast('Format the current CV before checking it.', 'warn'); return; }
  var route = aiRoutePayload('cv_single');
  if (!route.api_key) { showToast('Save an API key for Single CV Formatting first', 'err'); return; }
  cvReviewBusy(state, true);
  try {
    var result = await cvRunFormattingReview(state.source, _parsedData, route, state.warning);
    if (!result.stale) {
      _runCost += result.cost; _runUsage = mergeUsageClient(_runUsage, result.usage);
      var pill = document.getElementById('costPill');
      pill.textContent = 'Est. cost: ' + (_runCost < 0.001 ? '<$0.001' : '$' + _runCost.toFixed(4));
      pill.className = 'cost-pill show';
      if (result.accounted) statsRecord((_parsedData.candidate || {}).name || 'Unknown', 'format_review', result.cost, route.model, '', route.provider,
        statsMetaFromResponse({usage: result.usage, cost: result.cost, model: route.model, provider: route.provider}, route.model, route.provider));
      renderPreview(JSON.parse(JSON.stringify(_parsedData)));
      cvShowParseWarningBanner(cvJoinWarnings(state.warning, result.warning));
    }
  } finally {
    var current = window._cvFormattingReview;
    if (current && current.sequence === state.sequence && current.blob === state.blob) cvReviewBusy(current, false);
  }
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
  text = text.replace(/[\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]/g, ' ');
  if (!text) return '';
  text = text.replace(/^[\s]*[-‐-―−•·▪◦*]+[\s]*/, '');
  if (!text) return '';
  var loneEndYear = text.match(/^to\s+(\d{4})$/i);
  if (loneEndYear) text = loneEndYear[1];
  else if (/^to$/i.test(text)) return '';
  text = text.replace(/[–—−]/g, '-');
  text = text.replace(/\b(till\s*date|till\s*now|to\s*date|current|presently|now)\b/gi, 'Present');
  text = text.replace(/\bpresent\b/gi, 'Present');
  // Mirror Python and generate.js; preserve ambiguous two-digit years.
  var monthWord = '(?:January|February|March|April|September|October|November|December|June|July|August|Sept|May|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)';
  var dayWord = '(?:0?[1-9]|[12]\\d|3[01])(?:st|nd|rd|th)?';
  var sharedDayRange = text.match(new RegExp('^(' + monthWord + ')\\.?\\s+' + dayWord + '\\s*(?:-|to)\\s*(' + monthWord + ')\\.?\\s+' + dayWord + ',?\\s+(\\d{4})$', 'i'))
    || text.match(new RegExp('^' + dayWord + '\\s+(' + monthWord + ')\\.?\\s*(?:-|to)\\s*' + dayWord + '\\s+(' + monthWord + ')\\.?,?\\s+(\\d{4})$', 'i'));
  if (sharedDayRange) {
    // Leave the omitted year for the month-order check below.
    text = sharedDayRange[1] + ' to ' + sharedDayRange[2] + ' ' + sharedDayRange[3];
  } else {
    text = text.replace(new RegExp('\\b' + dayWord + '[ \\t]+(' + monthWord + ')\\.?,?\\s+(\\d{4})\\b', 'gi'), '$1 $2');
    text = text.replace(new RegExp('\\b(' + monthWord + ')\\.?[ \\t]+' + dayWord + ',?\\s+(\\d{4})\\b', 'gi'), '$1 $2');
  }
  var monthNumbers = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  var isoRepl = function(m, yyyy, mm){ return monthNumbers[parseInt(mm, 10) - 1] + ' ' + yyyy; };
  text = text.replace(/\b((?:19|20)\d{2})-(0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])\b/g, isoRepl);
  text = text.replace(new RegExp('\\b((?:19|20)\\d{2})-(0[1-9]|1[0-2])\\b(?![ \\t]*' + monthWord + '\\b)', 'gi'), isoRepl);
  text = text.replace(/\s*-\s*/g, ' to ');
  text = text.replace(/\s+to\s+/gi, ' to ');
  text = text.replace(/\b(January|February|March|April|June|July|August|September|Sept|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\b/gi, function(m){ return cvNormMonth(m); });
  text = text.replace(/\b(\d{1,2})\/(\d{4})\b/g, function(m, mm, yyyy){
    var n = parseInt(mm, 10);
    return n >= 1 && n <= 12 ? monthNumbers[n - 1] + ' ' + yyyy : m;
  });
  text = text.replace(/\s+/g, ' ').trim();
  var sameYear = text.match(/^(\d{4})\s+to\s+\1$/i);
  if (sameYear) return sameYear[1];
  var sameYearMonths = text.match(/^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+to\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})$/i);
  if (sameYearMonths) {
    // Cross-year spans keep their unstated start year; never guess backwards.
    if (monthNumbers.indexOf(cvNormMonth(sameYearMonths[1])) > monthNumbers.indexOf(cvNormMonth(sameYearMonths[2]))) return text;
    return cvNormMonth(sameYearMonths[1]) + ' ' + sameYearMonths[3] + ' to ' + cvNormMonth(sameYearMonths[2]) + ' ' + sameYearMonths[3];
  }
  return text;
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

// ── References / referees ─────────────────────────────────────────────────────
// Mirrors _drop_reference_sections in cvstudio_cv_reconcile.py. The server drops
// referees at /parse and again at /generate-docx; doing it here too keeps Preview
// agreeing with the generated DOCX for CV data parsed before that pass existed.
// The word lists live inside the functions so each one can be lifted out and
// exercised on its own, and tests/test_cv_reference_section_omission.py asserts
// they still match the Python sets.

// True only when every word of the label belongs to a referees heading, so a real
// skill such as "Reference Data Management" survives.
function cvReadsAsReferenceHeading(label) {
  var CV_REFERENCE_HEADING_WORDS = ['reference', 'references', 'referee', 'referees'];
  var CV_REFERENCE_HEADING_FILLER = ['and', 'or', 'details', 'detail', 'contacts', 'contact',
    'contactdetails', 'information', 'info', 'personal', 'professional', 'character', 'work',
    'employment', 'academic', 'business', 'available', 'upon', 'on', 'request', 'furnished',
    'provided', 'list', 'section'];
  // Fold accents and drop a possessive "'s" first, so "RÉFÉRENCES" and
  // "Referee's Details" tokenize to the same words as the plain forms.
  var CV_REFERENCE_POSSESSIVE_RE = /[\u0027\u2018\u2019\u02bc\u00b4\u0060]s\b/gi;
  // Possessives go first: NFKD turns an acute accent used as an apostrophe into a
  // combining mark, so folding before stripping would leave a bare "s" token.
  var text = String(label == null ? '' : label)
    .replace(CV_REFERENCE_POSSESSIVE_RE, '')
    .normalize('NFKD').replace(/[\u0300-\u036f]/g, '');
  var tokens = text.split(/[^A-Za-z]+/)
    .filter(Boolean).map(function(token){ return token.toLowerCase(); });
  if (!tokens.length) return false;
  if (!tokens.some(function(token){ return CV_REFERENCE_HEADING_WORDS.indexOf(token) !== -1; })) return false;
  return tokens.every(function(token){
    return CV_REFERENCE_HEADING_WORDS.indexOf(token) !== -1
      || CV_REFERENCE_HEADING_FILLER.indexOf(token) !== -1;
  });
}

function cvDropReferenceSkills(skills) {
  var CV_REFERENCE_ON_REQUEST_RE = /^(?:references?|referees?)(?:\s+(?:are|is|can\s+be|will\s+be|shall\s+be))?\s+(?:available|furnished|provided|supplied)(?:\s+(?:up)?on\s+request)?[.!]?$/i;
  return (Array.isArray(skills) ? skills : []).filter(function(entry){
    if (!entry || typeof entry !== 'object') return true;
    if (cvReadsAsReferenceHeading(entry.category)) return false;
    var rawItems = entry.items;
    if (Array.isArray(rawItems)) {
      entry.items = rawItems.filter(function(item){
        return !(typeof item === 'string' && CV_REFERENCE_ON_REQUEST_RE.test(item.trim()));
      });
      return entry.items.length > 0;
    }
    if (typeof rawItems === 'string') {
      var lines = rawItems.split(/\r?\n/);
      var kept = lines.filter(function(line){ return !CV_REFERENCE_ON_REQUEST_RE.test(line.trim()); });
      if (kept.length === lines.length) return true;
      entry.items = kept.join('\n');
      return kept.some(function(line){ return line.trim().length > 0; });
    }
    return true;
  });
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
  var skills = cvDropReferenceSkills(data.skills);
  // Mirror generate.js: a skills group only counts when it has a printable
  // item, so a category with empty items cannot raise a SKILLS heading over
  // nothing and leave the preview disagreeing with the generated DOCX.
  data.skills = skills.filter(function(value){
    if (!value || typeof value !== 'object') return false;
    var rawItems = value.items || '';
    var lines = Array.isArray(rawItems)
      ? rawItems.map(function(line){ return String(line || '').trim(); }).filter(Boolean)
      : String(rawItems).split(/\r?\n/).map(function(line){ return line.trim(); }).filter(Boolean);
    return lines.length > 0;
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
    if (String(exp.section_heading || '').trim()) {
      html += '<div class="preview-role preview-work-subsection">' + esc(String(exp.section_heading).trim()) + '</div>';
    }
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
    var eduMajor = edu.major || edu.specialisation || edu.specialization || '';
    if (eduMajor && String(eduMajor).trim()) html += '<div class="preview-deg">Major: ' + esc(String(eduMajor).trim()) + '</div>';
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

// A persistent notice above the preview. It stays until the next run replaces the
// output panel. textContent, never innerHTML: the message names employers taken
// from the uploaded CV.
// The /parse warning as it should be shown. In Blind mode the source check's
// warning is replaced with one that names no employer: it lists the real company
// names the blind step exists to hide, and the banner keeps it beside the blinded
// preview where a screenshot or screen-share would carry it.
function cvParseWarningText(data, blind) {
  var text = String((data && data.warning) || '').trim();
  if (!text) return '';
  if (blind && data.degraded_reason === 'fidelity_check') {
    return 'The source check flagged this CV: an employer may be missing or unnamed, or detail may have been dropped. Names are hidden in Blind mode — compare it with the original CV before sending.';
  }
  return text;
}

function cvShowParseWarningBanner(message) {
  var text = String(message || '').trim();
  if (!text) return;
  var ob = document.getElementById('outputBox');
  if (!ob) return;
  var banner = document.createElement('div');
  banner.className = 'cv-parse-warning';
  banner.setAttribute('role', 'alert');
  banner.textContent = '\u26a0 ' + text;
  ob.insertBefore(banner, ob.firstChild);
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

async function downloadDocx() {
  try { return await downloadDocxImpl(); }
  catch (e) {
    showToast('CV download could not be confirmed. Check the destination before retrying.', 'err');
    return false;
  }
}
async function downloadDocxImpl() {
  if (!window._docxBlob) { showToast('Format a CV first', 'err'); return; }
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
  var result = await cvStudioSaveDownloadBlob(window._docxBlob, name, window._isBlind ? 'blind' : 'formatted');
  cvStudioShowDownloadResult(result, name);
}

function clearInput() {
  var cancelledReview = !!window._cvFormattingReview;
  cvResetFormattingReview();
  if (cancelledReview) {
    document.getElementById('btnFormat').disabled = false;
    document.getElementById('btnBlind').disabled = false;
    stopTimer();
  }
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
