// ── AI Crawler: JobAdder Resume Sourcing Agent ─────────────────────────────
window._theSpiderPlainText = '';
window._theSpiderHTML = '';
window._theSpiderQueries = [];
window._theSpiderLastResults = [];
window._theSpiderBooleanHighlightPref = null;
window._theSpiderBooleanHighlightTerms = [];
window._theSpiderBooleanHighlightMatches = [];
function updateTheSpiderRouteBadge() {
  var el = document.getElementById('theSpiderRouteBadge');
  if (!el) return;
  try { var r = resolveAiRoute('the_spider'); el.textContent = 'Using: ' + r.display; }
  catch(e) { el.textContent = 'Using: —'; }
}
function updateTheSpiderCounts() {
  var ta = document.getElementById('theSpiderJdText');
  var el = document.getElementById('theSpiderJdCount');
  if (ta && el) el.textContent = (ta.value || '').length.toLocaleString() + ' chars';
}
function updateTheSpiderYearsRange(changed) {
  var minEl = document.getElementById('theSpiderYearsMin');
  var maxEl = document.getElementById('theSpiderYearsMax');
  var label = document.getElementById('theSpiderYearsLabel');
  var fill = document.getElementById('theSpiderYearsFill');
  if (!minEl || !maxEl || !label) return;
  var minYears = parseInt(minEl.value || '0', 10);
  var maxYears = parseInt(maxEl.value || '40', 10);
  if (!isFinite(minYears)) minYears = 0;
  if (!isFinite(maxYears)) maxYears = 40;
  minYears = Math.max(0, Math.min(40, minYears));
  maxYears = Math.max(0, Math.min(40, maxYears));
  if (minYears > maxYears) {
    if (changed === 'max') minYears = maxYears;
    else maxYears = minYears;
  }
  minEl.value = String(minYears);
  maxEl.value = String(maxYears);
  var rangeWrap = minEl.parentElement;
  if (rangeWrap) rangeWrap.classList.toggle('overlap', minYears === maxYears);
  if (minYears === maxYears) {
    minEl.style.zIndex = '5';
    maxEl.style.zIndex = '5';
  } else {
    minEl.style.zIndex = minYears >= 36 ? '5' : '3';
    maxEl.style.zIndex = minYears >= 36 ? '4' : '5';
  }
  if (fill) {
    fill.style.left = (minYears / 40 * 100) + '%';
    fill.style.right = ((40 - maxYears) / 40 * 100) + '%';
  }
  if (minYears <= 0 && maxYears >= 40) label.textContent = 'Any years';
  else if (minYears > 0 && maxYears >= 40) label.textContent = minYears + '+ years';
  else if (minYears <= 0) label.textContent = 'Up to ' + maxYears + ' years';
  else if (minYears === maxYears) label.textContent = minYears + ' years';
  else label.textContent = minYears + '–' + maxYears + ' years';
}
function updateTheSpiderYearsLabel() { updateTheSpiderYearsRange(); }
function normaliseTheSpiderBooleanRule(text) {
  text = String(text || '').replace(/[\u201c\u201d]/g, '"').replace(/[\u2018\u2019]/g, "'");
  text = text.replace(/[\x00-\x1f\x7f]/g, ' ').replace(/\s+/g, ' ').trim();
  return text.slice(0, 1500);
}
function hasTheSpiderBooleanSyntax(text) {
  return /\b(AND|OR|NOT)\b|[()"]/i.test(String(text || ''));
}
function splitTheSpiderKeywordTerms(value) {
  return String(value || '').split(/[,;\n\r]+/).map(function(x){ return x.trim(); }).filter(Boolean);
}
function theSpiderSupportedFileExt(file) {
  var ext = ((file && file.name ? file.name : '').split('.').pop() || '').toLowerCase();
  return ['pdf','docx','doc','txt','rtf','odt','png','jpg','jpeg'].indexOf(ext) >= 0;
}
async function selectTheSpiderFile(file) {
  if (!requireAiCrawlerUnlocked()) return;
  var status = document.getElementById('theSpiderFileStatus');
  var target = document.getElementById('theSpiderJdText');
  if (!file) return;
  if (!theSpiderSupportedFileExt(file)) { if(status) status.textContent='✗ Unsupported file type'; showToast('Supported: PDF, DOCX, DOC, TXT, RTF, ODT, PNG, JPG, JPEG', 'err'); return; }
  var run = markTabRunning('thespider');
  if (status) status.textContent = 'Extracting ' + file.name + '…';
  try {
    var fd = new FormData(); fd.append('file', file);
    var r = await fetchWithTimeout('/extract-text', { method:'POST', body:fd }, CV_EXTRACT_TEXT_TIMEOUT_MS);
    var d = await r.json().catch(function(){ return {}; });
    if (!r.ok || d.error) throw new Error(d.error || 'Extraction failed');
    if (target) target.value = d.text || '';
    updateTheSpiderCounts();
    if (status) status.textContent = '✓ ' + file.name + ' (' + (d.text || '').length.toLocaleString() + ' chars extracted)';
    markTabDone('thespider', run); showToast('JD ready for AI Crawler', 'ok');
  } catch(e) {
    if (status) status.textContent = '✗ ' + (e.message || 'Extraction failed');
    markTabFailed('thespider', run); showToast('AI Crawler extraction failed: ' + (e.message || 'Unknown error'), 'err');
  }
}
function toggleTheSpiderOwlContext() {
  var btn = document.getElementById('theSpiderUseOwl');
  if (btn) btn.classList.toggle('active');
}
function setTheSpiderOutputTab(which) {
  which = which === 'results' ? 'results' : 'notes';
  var noteTab = document.getElementById('theSpiderTabNotes');
  var resultTab = document.getElementById('theSpiderTabResults');
  var notes = document.getElementById('theSpiderOutput');
  var results = document.getElementById('theSpiderSearchOutput');
  if (noteTab) { noteTab.classList.toggle('active', which === 'notes'); noteTab.setAttribute('aria-selected', which === 'notes' ? 'true' : 'false'); }
  if (resultTab) { resultTab.classList.toggle('active', which === 'results'); resultTab.setAttribute('aria-selected', which === 'results' ? 'true' : 'false'); }
  if (notes) { notes.classList.toggle('active', which === 'notes'); notes.classList.toggle('show', which === 'notes'); notes.hidden = which !== 'notes'; }
  if (results) { results.classList.toggle('active', which === 'results'); results.classList.toggle('show', which === 'results'); results.hidden = which !== 'results'; }
}
function showTheSpiderPanel(which) {
  setTheSpiderOutputTab(which || 'notes');
}
function getTheSpiderInputs() {
  function val(id){ var el=document.getElementById(id); return el ? String(el.value || '').trim() : ''; }
  return {
    jd: val('theSpiderJdText'),
    country: val('theSpiderCountry') || 'Malaysia',
    city_state: val('theSpiderCityState'),
    residential: val('theSpiderResidential') || 'Any',
    industry: val('theSpiderIndustry'),
    it_skills: val('theSpiderItSkills'),
    qualifications: val('theSpiderQualifications'),
    salary_currency: val('theSpiderSalaryCurrency') || 'MYR',
    salary_min: val('theSpiderSalaryMin'),
    salary_max: val('theSpiderSalaryMax'),
    include_missing_salary: !!(document.getElementById('theSpiderIncludeMissingSalary') || {}).checked,
    years: val('theSpiderYearsMin'),
    years_min: val('theSpiderYearsMin'),
    years_max: val('theSpiderYearsMax'),
    must: val('theSpiderMust'),
    strict: !!((document.getElementById('theSpiderStrict') || {}).classList || {contains:function(){return false;}}).contains('active'),
    use_owl: !!((document.getElementById('theSpiderUseOwl') || {}).classList || {contains:function(){return false;}}).contains('active')
  };
}
function buildTheSpiderSearchFilters(inp) {
  inp = inp || getTheSpiderInputs();
  return {
    role: '',
    country: inp.country || 'Malaysia',
    city_state: inp.city_state || '',
    residential: inp.residential || 'Any',
    industry: inp.industry || '',
    it_skills: inp.it_skills || '',
    qualifications: inp.qualifications || '',
    salary_currency: inp.salary_currency || 'MYR',
    salary_min: inp.salary_min || '',
    salary_max: inp.salary_max || '',
    include_missing_salary: !!inp.include_missing_salary,
    years: inp.years_min || inp.years || '0',
    years_min: inp.years_min || inp.years || '0',
    years_max: inp.years_max || '40',
    must: inp.must || '',
    nice: '',
    exclude: '',
    targets: '',
    jd: inp.jd || '',
    strict: !!inp.strict,
    adjacent: false
  };
}
function fillTheSpiderDatalist(id, values) {
  var list = document.getElementById(id);
  if (!list || !Array.isArray(values)) return;
  var seen = {};
  list.innerHTML = values.map(function(v){
    v = String(v && (v.name || v.label || v.value || v.title || v) || '').trim();
    if (!v || seen[v.toLowerCase()]) return '';
    seen[v.toLowerCase()] = 1;
    return '<option value="' + escAttr(v) + '"></option>';
  }).join('');
}
function fillTheSpiderSelect(id, values, includeAny) {
  var select = document.getElementById(id);
  if (!select || !Array.isArray(values)) return;
  var current = String(select.value || 'Any');
  var seen = {};
  var options = includeAny ? ['Any'] : [];
  values.forEach(function(v){
    v = String(v && (v.name || v.label || v.value || v.title || v) || '').trim();
    if (!v || seen[v.toLowerCase()] || (includeAny && v.toLowerCase() === 'any')) return;
    seen[v.toLowerCase()] = 1; options.push(v);
  });
  select.innerHTML = options.map(function(v){ return '<option value="' + escAttr(v) + '">' + esc(v) + '</option>'; }).join('');
  select.value = options.indexOf(current) >= 0 ? current : (includeAny ? 'Any' : (options[0] || ''));
}
function normaliseTheSpiderOptionPayload(d) {
  if (!d) return [];
  if (Array.isArray(d)) return d;
  if (Array.isArray(d.items)) return d.items;
  if (Array.isArray(d.values)) return d.values;
  if (Array.isArray(d.valueList)) return d.valueList;
  if (Array.isArray(d.data)) return d.data;
  if (d.data && Array.isArray(d.data.items)) return d.data.items;
  return [];
}
async function loadTheSpiderJobAdderOptions() {
  if (!aiCrawlerIsUnlocked()) return;
  var fallbacks = {
    // Canonical JobAdder industry categories (custom field #1). The backend
    // /jobadder/spider_options adds the granular sub-categories; this pre-fetch
    // fallback carries the broad set so the no-network case still tallies.
    industry: ['Digital & E-Commerce','Financial Services','FMCG','Industrial/Manufacturing','Information Technology & Services','Life Science/Medical','Property & Construction','Professional Services','Education','Government Sector'],
    it_skills: ['SAP','SAP ABAP','SAP FICO','SAP BW','SAP BPC','Oracle','NetSuite','Salesforce','Python','Java','AWS','Azure','GCP','Kubernetes','Docker','SQL','Power BI'],
    qualifications: ['ACCA','CPA','CIMA','MIA','ICAEW','CFA','CIA','PMP','PRINCE2','ITIL','CKA','AWS Certified','Azure Certified','SAP Certified'],
    residential: ['Local Citizen','Permanent Resident','Expat - No Visa Required','Expat - Work Visa Required']
  };
  fillTheSpiderDatalist('theSpiderIndustryOptions', fallbacks.industry);
  fillTheSpiderDatalist('theSpiderItSkillOptions', fallbacks.it_skills);
  fillTheSpiderDatalist('theSpiderQualificationOptions', fallbacks.qualifications);
  fillTheSpiderSelect('theSpiderResidential', fallbacks.residential, true);
  var maps = [
    ['industry','theSpiderIndustryOptions'],
    ['it_skills','theSpiderItSkillOptions'],
    ['qualifications','theSpiderQualificationOptions'],
    ['residential','theSpiderResidential','select',true],
    ['country','theSpiderCountry','select',false]
  ];
  await Promise.all(maps.map(async function(pair){
    try {
      var r = await fetch('/jobadder/spider_options?name=' + encodeURIComponent(pair[0]), {headers:{'X-AI-Crawler-Code':aiCrawlerLockPayload()}});
      var d = await r.json().catch(function(){ return {}; });
      if (r.ok && !d.error) {
        var vals = normaliseTheSpiderOptionPayload(d);
        if (vals.length) {
          if (pair[2] === 'select') fillTheSpiderSelect(pair[1], vals, pair[3] !== false);
          else fillTheSpiderDatalist(pair[1], vals);
        }
      }
    } catch(e) {}
  }));
}
function renderTheSpiderFilterSummary(summary) {
  if (!summary) return '';
  function num(v, fallback){ var n=Number(v); return Number.isFinite(n) ? n : fallback; }
  var matched = num(summary.reported_total, num(summary.returned_before_filter, 0));
  var scanned = num(summary.scanned, num(summary.returned_before_filter, 0));
  var enriched = num(summary.enriched_count, num(summary.enriched_candidate_profiles, 0));
  var resumeScored = num(summary.resume_scored_candidates, 0);
  var excluded = num(summary.excluded_count, num(summary.excluded, 0));
  var kept = num(summary.kept, num(summary.returned_after_filter, 0));
  var mode = String(summary.mode || ((summary.boolean_search || {}).mode) || 'plain');
  var modeLabel = mode === 'native_boolean' ? 'native Boolean' : (mode === 'native_boolean→fallback' ? 'Boolean → positive-keyword fallback' : (mode === 'native_boolean_no_fallback' ? 'native Boolean · no safe fallback' : 'plain keywords'));
  var line = 'JobAdder matched ' + matched + ' · scanned ' + scanned + ' · enriched ' + enriched + (resumeScored ? (' · resume scored ' + resumeScored) : '') + ' · excluded ' + excluded + ' · showing ' + kept + ' (' + modeLabel + ')';
  var html = '<div class="spider-badge" style="display:inline-flex;margin:4px 0 8px;">' + esc(line) + '</div>';
  var bs = summary.boolean_search || {};
  if (bs.fallback === 'plain_keywords') {
    var terms = Array.isArray(bs.fallback_terms) ? bs.fallback_terms.join(' ') : String(bs.query || '');
    var negatives = Array.isArray(bs.negative_terms) ? bs.negative_terms.join(', ') : '';
    html += '<div class="provider-down-alert" style="margin:0 0 8px;border-color:#d69e2e;background:rgba(214,158,46,.08);"><strong>Boolean fallback used:</strong> JobAdder returned 0 for the complete Boolean expression. Showing positive-keyword results for <strong>' + esc(terms || 'extracted terms') + '</strong>.' + (negatives ? ' Visible NOT matches are excluded: <strong>' + esc(negatives) + '</strong>.' : '') + '</div>';
  } else if (bs.fallback === 'skipped_negative_only') {
    html += '<div class="provider-down-alert" style="margin:0 0 8px;border-color:#d69e2e;background:rgba(214,158,46,.08);"><strong>No unsafe fallback:</strong> This Boolean contains no positive discovery term. Add at least one positive keyword instead of using a negative-only search.</div>';
  } else if (bs.mode === 'native_boolean') {
    html += '<div class="spider-muted-line" style="margin:0 0 8px;"><strong>Boolean attempted:</strong> ' + esc(String(bs.query || '—')) + '</div>';
  }
  if (summary.eligible_before_limit > kept) html += '<div class="spider-muted-line" style="margin:0 0 8px;">' + esc(String(summary.eligible_before_limit)) + ' eligible before the display limit.</div>';
  if (kept && !resumeScored) html += '<div class="spider-muted-line" style="margin:0 0 8px;"><strong>Fit source:</strong> JobAdder profile fields only; no latest-resume text was exposed for this result page.</div>';
  var pageWarnings = Array.isArray(summary.pagination_warnings) ? summary.pagination_warnings : [];
  if (summary.pagination_incomplete || pageWarnings.length) html += '<div class="provider-down-alert" style="margin:0 0 8px;border-color:#f0c040;background:#fff8e7;color:#7a5800;"><strong>Search limit reached — results may be incomplete:</strong> ' + esc(pageWarnings.join(' · ') || 'JobAdder ended pagination before its reported total was reached.') + ' This is a safety warning, not a failed search.</div>';
  return html;
}
function getTheSpiderOwlContext(inp) {
  if (!inp || !inp.use_owl) return '';
  var report = String(window._theOwlPlainText || '').trim();
  var meta = window._theOwlMeta || null;
  if (!report) return '';
  return 'CURRENT THE OWL MARKET MAP CONTEXT:\n' + (meta ? ('Market: ' + (meta.location || '') + ' | Industries: ' + (meta.industries || '') + '\n') : '') + report.slice(0, 14000);
}
function theSpiderMarkdownToHtml(text) {
  if (typeof owlChatMarkdownToHtml === 'function') return owlChatMarkdownToHtml(text || '');
  return '<div style="white-space:pre-wrap">' + esc(text || '') + '</div>';
}
function parseTheSpiderQueries(text) {
  var out=[], seen={};
  String(text || '').split(/\r?\n/).forEach(function(line){
    line = line.replace(/^[-*•]\s*/, '').trim();
    var m = line.match(/^(?:JobAdder\s*)?(?:Search\s*)?(?:String|Query)\s*\d*\s*[:：]\s*(.+)$/i);
    if (m) line = m[1].trim();
    if (!line) return;
    var looks = /\b(AND|OR|NOT)\b|\(|\)|\"|\bSAP\b|\bData\b|\bManager\b|\bEngineer\b|\bAnalyst\b|\bConsultant\b|\bDeveloper\b|\bFinance\b|\bHR\b|\bMarketing\b/i.test(line);
    if (!looks || line.length < 5 || line.length > 260) return;
    var k=line.toLowerCase(); if(seen[k]) return; seen[k]=1; out.push(line);
  });
  return out.slice(0, 10);
}
function buildTheSpiderFallbackQueries(inp) {
  inp = inp || getTheSpiderInputs();
  var queries = [], seen = {};
  function add(q){ q=normaliseTheSpiderBooleanRule(q); if(!q || q.length<2 || q.length>260) return; var k=q.toLowerCase(); if(seen[k]) return; seen[k]=1; queries.push(q); }
  function terms(v){ return splitTheSpiderKeywordTerms(v); }
  function quote(x){ x=String(x||'').trim(); return /\s/.test(x) && !/^".*"$/.test(x) ? '"' + x + '"' : x; }
  var mustRaw = normaliseTheSpiderBooleanRule(inp.must);
  var must = terms(inp.must);
  if (mustRaw && hasTheSpiderBooleanSyntax(mustRaw)) {
    add(mustRaw);
  }
  // JobAdder dropdown/profile filters never narrow resume-keyword discovery.
  var hard = hasTheSpiderBooleanSyntax(mustRaw) ? [] : must;
  if (hard.length) add(hard.slice(0,7).map(quote).join(' AND '));
  if (!queries.length && mustRaw) add(mustRaw);
  if (inp.use_owl && window._theOwlPlainText) parseTheSpiderQueries(window._theOwlPlainText).slice(0,3).forEach(add);
  if (!queries.length && inp.jd) {
    var jdForQuery = String(inp.jd || '').split(/\n/).filter(function(line){ return !/\b(language|languages|fluent|spoken|written|mandarin|chinese|cantonese|hokkien|hakka|teochew|malay|bahasa|english|degree|diploma|bachelor|master|phd|education|university|college)\b/i.test(line); }).join(' ');
    var words = jdForQuery.match(/\b(?:SAP|Oracle|NetSuite|Salesforce|AR|Collections|Reconciliation|ABAP|FICO|BPC|SOM|Python|Java|AWS|Azure|Manager|Analyst|Specialist|Engineer|Consultant|Developer)\b/gi) || [];
    add(words.slice(0,7).join(' AND '));
    if (!queries.length) {
      var jdTitle = String(inp.jd || '').split(/\r?\n/).map(function(line){
        return line.replace(/^\s*(?:job\s+title|position|role)\s*[:\-]\s*/i, '').replace(/\s+/g, ' ').trim();
      }).filter(function(line){
        return line.length >= 3 && line.length <= 100 && !/^(?:job description|about the role|overview|responsibilities|requirements)$/i.test(line);
      })[0] || '';
      if (jdTitle) add(quote(jdTitle));
    }
  }
  return queries.slice(0,6);
}
function buildTheSpiderDiscoveryQueries(inp) {
  inp = inp || getTheSpiderInputs();
  var mustRaw = normaliseTheSpiderBooleanRule(inp.must || '');
  if (!mustRaw) return buildTheSpiderFallbackQueries(inp);
  var queries = [], seen = {};
  function add(q){ q=normaliseTheSpiderBooleanRule(q); if(!q || q.length<2 || q.length>1500) return; var k=q.toLowerCase(); if(seen[k]) return; seen[k]=1; queries.push(q); }
  function quote(x){ x=String(x||'').trim(); return /\s/.test(x) && !/^".*"$/.test(x) ? '"' + x + '"' : x; }
  if (hasTheSpiderBooleanSyntax(mustRaw)) {
    // Preserve the recruiter-authored Boolean rule exactly as the primary discovery query.
    add(mustRaw);
  } else {
    var terms = splitTheSpiderKeywordTerms(mustRaw);
    if (terms.length) add(terms.map(quote).join(inp.strict ? ' AND ' : ' OR '));
    terms.slice(0,4).forEach(function(t){ add(quote(t)); });
  }
  return queries.slice(0,6);
}

function cleanTheSpiderPrompt(prompt, inp) {
  inp = inp || {};
  return String(prompt || '')
    .replace('\nTarget role: ' + inp.role, '')
    .replace('\nInclude adjacent titles: ' + (inp.adjacent ? 'Yes' : 'No'), '')
    .replace('\nNice-to-have / adjacent skills:\n' + inp.nice, '')
    .replace('\nExclude / avoid:\n' + inp.exclude, '')
    .replace('\nTarget/source companies:\n' + inp.targets, '')
    .replace(
      '\nSalary/budget: ' + inp.salary,
      '\nExpected monthly salary: ' + (inp.salary_currency || 'MYR') + ' ' + (inp.salary_min || 'No minimum') + ' to ' + (inp.salary_max || 'No maximum') + '; include missing salary: ' + (inp.include_missing_salary ? 'Yes' : 'No')
    )
    .replace(
      '- Industry, salary/budget and target/source companies can guide searches and notes, but do not treat them as fit-score criteria.',
      '- Industry and expected salary are exact eligibility filters; do not treat them as fit-score criteria.'
    )
    .replace(
      '- Use Owl context only to improve adjacent titles, target-company/source-company angles, and profile patterns.',
      '- Use Owl context only to improve role and profile patterns derived from the JD.'
    );
}

async function generateTheSpider(opts) {
  if (!requireAiCrawlerUnlocked()) return;
  opts = opts || {};
  var inp = getTheSpiderInputs();
  if (!inp.jd && !inp.must) { showToast('Add a JD or Boolean Rules / Keywords first', 'err'); return; }
  var route = aiRoutePayload('the_spider');
  var btn = document.getElementById('theSpiderBtn'), body=document.getElementById('theSpiderBody'), out=document.getElementById('theSpiderOutput'), costEl=document.getElementById('theSpiderCost'), status=document.getElementById('theSpiderStatus');
  clearTabRunState('thespider');
  ackBrowserActivityForTab('thespider');
  ackBrowserActivityFailedForTab('thespider');
  var phaseRun = markTabRunning('thespider');
  var keywordOnly = !inp.jd && !!inp.must;
  if (keywordOnly) {
    if (btn && opts.autoSearch) { btn.disabled = true; btn.textContent = 'Sourcing…'; }
    window._theSpiderQueries = buildTheSpiderDiscoveryQueries(inp);
    window._theSpiderPlainText = [
      '## Keyword-Only Sourcing',
      '- JD is optional. AI Crawler is sourcing directly from your Boolean Rules / Keywords and selected filters.',
      '- Boolean Rules / Keywords are used first to discover candidates. The JD is not used to reject candidates during discovery.',
      '- Candidates are then scored 0-100% against job scope and requirements, excluding language and education. Results below 10% are hidden.',
      '',
      '## JobAdder Search Strings',
      (window._theSpiderQueries.length ? window._theSpiderQueries.map(function(q){ return '- ' + q; }).join('\n') : '- Add Boolean Rules / Keywords'),
      '',
      '## Sourcing Notes',
      '- Use NOT inside Boolean Rules / Keywords when you need to exclude a term.',
      '- The complete Boolean expression is sent directly to JobAdder candidate Keywords search and JobAdder decides the native Boolean match.'
    ].join('\n');
    window._theSpiderHTML = theSpiderMarkdownToHtml(window._theSpiderPlainText);
    if (out) out.classList.add('show');
    if (body) body.innerHTML = window._theSpiderHTML + '<h4>Detected JobAdder Queries</h4><div>' + window._theSpiderQueries.map(function(q){ return '<span class="spider-query-chip">' + esc(q) + '</span>'; }).join('') + '</div>';
    var copyBtnKeyword = document.getElementById('theSpiderCopyBtn'); if (copyBtnKeyword) copyBtnKeyword.style.display='';
    showTheSpiderPanel(opts.autoSearch ? 'results' : 'notes');
    try {
      if (opts.autoSearch) await runTheSpiderJobAdderSearch({fromSource:true, keywordOnly:true, tabRunToken:phaseRun});
      else markTabDone('thespider', phaseRun, {forceBrowser:true});
    } finally {
      if (btn && opts.autoSearch) { btn.disabled = false; btn.textContent = 'Retry Sourcing'; }
    }
    return;
  }
  if (!route.api_key) {
    window._theSpiderQueries = buildTheSpiderDiscoveryQueries(inp);
    window._theSpiderPlainText = [
      '## JobAdder Search Strings',
      (window._theSpiderQueries.length ? window._theSpiderQueries.map(function(q){ return '- ' + q; }).join('\n') : '- Add a JD or Boolean Rules / Keywords'),
      '',
      '## Screening Scorecard',
      '- Add an AI key for the AI Crawler route to generate a detailed scorecard.',
      '',
      '## Sourcing Notes',
      '- Running JobAdder search with fallback keyword queries only.'
    ].join('\n');
    window._theSpiderHTML = theSpiderMarkdownToHtml(window._theSpiderPlainText);
    if (out) out.classList.add('show');
    if (body) body.innerHTML = window._theSpiderHTML + '<h4>Detected JobAdder Queries</h4><div>' + window._theSpiderQueries.map(function(q){ return '<span class="spider-query-chip">' + esc(q) + '</span>'; }).join('') + '</div>';
    var copyBtn = document.getElementById('theSpiderCopyBtn'); if (copyBtn) copyBtn.style.display='';
    showTheSpiderPanel(opts.autoSearch ? 'results' : 'notes');
    if (btn && opts.autoSearch) { btn.disabled = true; btn.textContent = 'Sourcing…'; }
    try {
      if (opts.autoSearch) await runTheSpiderJobAdderSearch({fromSource:true, tabRunToken:phaseRun});
      else markTabDone('thespider', phaseRun, {forceBrowser:true});
    } finally {
      if (btn && opts.autoSearch) { btn.disabled = false; btn.textContent = 'Retry Sourcing'; }
    }
    return;
  }
  if (btn) { btn.disabled=true; btn.textContent=opts.autoSearch ? 'Sourcing…' : 'Generating…'; }
  if (out) out.classList.add('show');
  if (body) body.innerHTML = '<div style="display:flex;align-items:center;gap:10px;color:var(--text3);"><span class="spinner"></span><span>Preparing AI Crawler search pack with ' + esc(route.display) + '…</span></div>';
  if (status) status.textContent = 'Working…';
  updateTheSpiderRouteBadge();
  var owlCtx = getTheSpiderOwlContext(inp);
  var spiderMinYears = parseInt(inp.years_min || inp.years || '0', 10);
  var spiderMaxYears = parseInt(inp.years_max == null || inp.years_max === '' ? '40' : inp.years_max, 10);
  if (!isFinite(spiderMinYears)) spiderMinYears = 0;
  if (!isFinite(spiderMaxYears)) spiderMaxYears = 40;
  spiderMinYears = Math.max(0, Math.min(40, spiderMinYears));
  spiderMaxYears = Math.max(spiderMinYears, Math.min(40, spiderMaxYears));
  var spiderRangeLabel = (spiderMinYears <= 0 && spiderMaxYears >= 40) ? 'Any' : (spiderMaxYears >= 40 ? (spiderMinYears + '+ years') : (spiderMinYears === spiderMaxYears ? (spiderMinYears + ' years') : (spiderMinYears + '-' + spiderMaxYears + ' years')));
  var prompt = 'You are AI Crawler, a recruiter sourcing agent inside CV Studio. Your task is to prepare a JobAdder candidate sourcing pack from a JD and recruiter filters, then the app will run actual JobAdder candidate search.\n\nOUTPUT RULES:\n- Use concise Markdown.\n- Do not invent candidate names; actual candidates come only from JobAdder search results.\n- Create practical JobAdder candidate searches, not public web lead searches.\n- Country, residential status, IT skills and qualifications are hard filters.\n- Candidate discovery must use Boolean Rules / Keywords first when supplied. CV Studio will send the complete recruiter-authored Boolean expression directly to JobAdder candidate Keywords search and trust JobAdder\'s native Boolean results. Do not use JD similarity to reject candidates during discovery.\n- After keyword discovery, describe a separate 0-100% match-fit assessment based on the JD job scope and requirements.\n- Language and education/degree requirements must never contribute to match fit, even if they appear elsewhere in the inputs.\n- Industry, salary/budget and target/source companies can guide searches and notes, but do not treat them as fit-score criteria.\n- Use Owl context only to improve adjacent titles, target-company/source-company angles, and profile patterns.\n- Include exact copyable search strings.\n\nReturn sections exactly:\n## Must-Match Profile\n## JobAdder Search Strings\n## Resume Keywords To Prioritise\n## Candidates To Exclude\n## Screening Scorecard\n## Sourcing Notes\n\nScreening Scorecard rules:\n- Prefer a Markdown table with columns: Criteria | Weight | Must-Ask Question.\n- High-weight rows should focus on JD job scope, functional/technical responsibilities, domain/tool experience, nice-to-haves, IT skills/ERP, and one red-flag line.\n- Do not include language or education as scorecard criteria.\n\nSourcing Notes rules:\n- Give tactical notes like where to find the talent in JobAdder, source-company angles, equivalent tools/platforms, proprietary-tool proxies, documentation/process probes, and first-message pre-screen friction points.\n\nInputs:\nTarget role: ' + inp.role + '\nCountry: ' + inp.country + '\nResidential status: ' + inp.residential + '\nIndustry: ' + inp.industry + '\nIT Skills hard filter: ' + inp.it_skills + '\nQualifications hard filter: ' + inp.qualifications + '\nSalary/budget: ' + inp.salary + '\nMinimum years of experience: ' + (spiderMinYears > 0 ? (spiderMinYears + ' years') : 'Any') + '\nMaximum years of experience: ' + (spiderMaxYears >= 40 ? 'No maximum' : (spiderMaxYears + ' years')) + '\nSelected experience range: ' + spiderRangeLabel + '\nStrict Boolean rules: ' + (inp.strict ? 'Yes' : 'No') + '\nInclude adjacent titles: ' + (inp.adjacent ? 'Yes' : 'No') + '\nBoolean Rules / Keywords:\n' + inp.must + '\nNice-to-have / adjacent skills:\n' + inp.nice + '\nExclude / avoid:\n' + inp.exclude + '\nTarget/source companies:\n' + inp.targets + '\n\nJD:\n---\n' + inp.jd.slice(0, 18000) + '\n---\n\n' + owlCtx;
  try {
    var d = await callAIProxy(cleanTheSpiderPrompt(prompt, inp), 2600, false, 0, 'the_spider');
    var raw = aiText(d).trim();
    if (!raw) {
      recordPaidAiFailure('AI Crawler sourcing plan returned empty output', d, route.model, route.provider);
      throw new Error('Empty AI Crawler plan returned');
    }
    window._theSpiderPlainText = raw;
    window._theSpiderHTML = theSpiderMarkdownToHtml(raw);
    window._theSpiderQueries = inp.must ? buildTheSpiderDiscoveryQueries(inp) : parseTheSpiderQueries(raw);
    if (!window._theSpiderQueries.length) window._theSpiderQueries = buildTheSpiderFallbackQueries(inp);
    if (body) body.innerHTML = window._theSpiderHTML + (window._theSpiderQueries.length ? ('<h4>Detected JobAdder Queries</h4><div>' + window._theSpiderQueries.map(function(q){ return '<span class="spider-query-chip">' + esc(q) + '</span>'; }).join('') + '</div>') : '');
    showTheSpiderPanel(opts.autoSearch ? 'results' : 'notes');
    var copyBtn = document.getElementById('theSpiderCopyBtn'); if (copyBtn) copyBtn.style.display='';
    var usage = normalizeUsageClient(d.usage || {}); var cost = responseCost(d, route.model, route.provider);
    if (costEl) { costEl.style.display=''; costEl.textContent = ((usage.input_tokens||0)+(usage.output_tokens||0)).toLocaleString() + ' tokens · $' + cost.toFixed(4); }
    statsRecord('AI Crawler — JobAdder sourcing plan', 'spider', cost, d.model || route.model, '', d.provider || route.provider, statsMetaFromResponse(d, route.model, route.provider));
    if (status) status.textContent = 'Generated';
    if (opts.autoSearch) {
      if (status) status.textContent = 'Sourcing JobAdder…';
      showToast('AI Crawler search pack ready — sourcing JobAdder…', 'ok');
      await runTheSpiderJobAdderSearch({fromSource:true, tabRunToken:phaseRun});
    } else {
      markTabDone('thespider', phaseRun, {forceBrowser:true});
      showToast('AI Crawler plan generated', 'ok');
    }
  } catch(e) {
    if (body) body.innerHTML = providerDownAlertHtml(e.message || 'AI Crawler failed');
    if (status) status.textContent = 'Failed';
    markTabFailed('thespider', phaseRun, {forceBrowser:true}); showToast('AI Crawler failed: ' + (e.message || 'Unknown error').split('\n')[0], 'err');
  } finally {
    if (btn) {
      btn.disabled=false;
      btn.textContent = opts.autoSearch ? 'Retry Sourcing' : 'Source Candidates';
    }
  }
}
async function sourceTheSpiderCandidates() {
  await generateTheSpider({autoSearch:true});
}
function getTheSpiderCandidateId(c) {
  c = c || {};
  var id = c.candidateId || c.candidateID || c.candidate_id || c.id || c.entityId || '';
  if (id && typeof id === 'object') id = id.candidateId || id.id || id.value || '';
  return String(id || '').trim();
}
function theSpiderPreviewCacheKey(candidateId) {
  var id = String(candidateId || '').trim();
  return id ? ('candidate:' + id) : '';
}
function ensureTheSpiderPreviewCaches() {
  if (!(window._theSpiderPreviewPayloadCache instanceof Map)) window._theSpiderPreviewPayloadCache = new Map();
  if (!(window._theSpiderPreviewDomCache instanceof Map)) window._theSpiderPreviewDomCache = new Map();
  if (!(window._theSpiderPreviewPrefetchFailed instanceof Set)) window._theSpiderPreviewPrefetchFailed = new Set();
  if (!(window._theSpiderPreviewPrefetchAttempted instanceof Set)) window._theSpiderPreviewPrefetchAttempted = new Set();
  if (!(window._theSpiderPreviewPrefetchTargets instanceof Set)) window._theSpiderPreviewPrefetchTargets = new Set();
  if (!(window._theSpiderPreviewEvictedKeys instanceof Set)) window._theSpiderPreviewEvictedKeys = new Set();
  if (!(window._theSpiderPreviewValidationInFlight instanceof Map)) window._theSpiderPreviewValidationInFlight = new Map();
  if (!(window._theSpiderPreviewUpgradeInFlight instanceof Map)) window._theSpiderPreviewUpgradeInFlight = new Map();
  if (!Array.isArray(window._theSpiderPreviewPrefetchQueue)) window._theSpiderPreviewPrefetchQueue = [];
  if (!Array.isArray(window._theSpiderPreviewPrefetchAllItems)) window._theSpiderPreviewPrefetchAllItems = [];
}
var THE_SPIDER_PREVIEW_PREFETCH_BATCH_SIZE = 30;
var THE_SPIDER_PREVIEW_PREFETCH_MAX = THE_SPIDER_PREVIEW_PREFETCH_BATCH_SIZE;
var THE_SPIDER_PREVIEW_PREFETCH_MAX_TOTAL = 60;
var THE_SPIDER_PREVIEW_MEMORY_MODE_KEY = 'cvstudio_spider_preview_memory_mode_v1';
var THE_SPIDER_PREVIEW_MEMORY_PROFILES = {
  low:{label:'Low',autoBytes:64*1024*1024,manualBytes:128*1024*1024,payloadBytes:128*1024*1024,payloadEntries:40,domBytes:64*1024*1024,domEntries:2,combinedMb:448},
  standard:{label:'Standard',autoBytes:128*1024*1024,manualBytes:256*1024*1024,payloadBytes:256*1024*1024,payloadEntries:60,domBytes:128*1024*1024,domEntries:3,combinedMb:640},
  high:{label:'High',autoBytes:256*1024*1024,manualBytes:512*1024*1024,payloadBytes:512*1024*1024,payloadEntries:80,domBytes:256*1024*1024,domEntries:3,combinedMb:1024}
};
var THE_SPIDER_PREVIEW_PREFETCH_AUTO_MAX_BYTES = 256 * 1024 * 1024;
var THE_SPIDER_PREVIEW_PREFETCH_MANUAL_MAX_BYTES = 512 * 1024 * 1024;
var THE_SPIDER_PREVIEW_PAYLOAD_MAX_ENTRIES = 80;
var THE_SPIDER_PREVIEW_PAYLOAD_MAX_BYTES = 512 * 1024 * 1024;
var THE_SPIDER_PREVIEW_DOM_MAX_ENTRIES = 3;
var THE_SPIDER_PREVIEW_DOM_MAX_BYTES = 256 * 1024 * 1024;
var THE_SPIDER_PREVIEW_REVALIDATE_MS = 2 * 60 * 1000;
var THE_SPIDER_PREVIEW_DIAGNOSTIC_FRESH_MS = 5 * 60 * 1000;
var _theSpiderPreviewAppliedSelection='';
var _theSpiderPreviewAppliedResolution='';
var _theSpiderPreviewMemoryFreshnessTimer=null;
function storedTheSpiderPreviewMemoryMode(){
  try { var mode=String(localStorage.getItem(THE_SPIDER_PREVIEW_MEMORY_MODE_KEY)||'high'); return /^(auto|low|standard|high)$/.test(mode)?mode:'high'; } catch(e) { return 'high'; }
}
function trustedTheSpiderPreviewMemoryDiagnostic(){
  var received=Number(window._cvStudioSystemMemoryReceivedAt)||0,total=Number(window._cvStudioSystemMemoryTotalBytes)||0,available=Number(window._cvStudioSystemMemoryAvailableBytes)||0,age=received?Math.max(0,Date.now()-received):null;
  var valid=Number.isFinite(total)&&Number.isFinite(available)&&total>0&&available>0&&available<=total;
  var fresh=valid&&age!==null&&age<=THE_SPIDER_PREVIEW_DIAGNOSTIC_FRESH_MS;
  return {valid:valid,fresh:fresh,total:valid?total:0,available:valid?available:0,age_ms:age};
}
function resolvedTheSpiderPreviewMemoryDecision(mode){
  mode=String(mode||storedTheSpiderPreviewMemoryMode());
  if(mode!=='auto'){
    var manual=THE_SPIDER_PREVIEW_MEMORY_PROFILES[mode]?mode:'high';
    return {resolved:manual,reason:'Manual selection is authoritative',freshness:'manual',age_ms:null};
  }
  var diagnostic=trustedTheSpiderPreviewMemoryDiagnostic();
  if(!diagnostic.fresh){
    return {resolved:'standard',reason:diagnostic.valid?'Diagnostic memory data is stale; safe fallback applied':'Trusted memory data is unavailable or malformed; safe fallback applied',freshness:diagnostic.valid?'stale':'unavailable',age_ms:diagnostic.age_ms};
  }
  var resolved='high',reason='Fresh trusted memory data supports the High profile';
  if(diagnostic.available<=3*1024*1024*1024){resolved='low';reason='Fresh available RAM is 3 GB or less';}
  else if(diagnostic.available<=6*1024*1024*1024){resolved='standard';reason='Fresh available RAM is 6 GB or less';}
  else if(diagnostic.total<=10*1024*1024*1024){resolved='low';reason='Fresh total RAM is 10 GB or less';}
  else if(diagnostic.total<=20*1024*1024*1024){resolved='standard';reason='Fresh total RAM is 20 GB or less';}
  return {resolved:resolved,reason:reason,freshness:'fresh',age_ms:diagnostic.age_ms};
}
function resolvedTheSpiderPreviewMemoryMode(mode){return resolvedTheSpiderPreviewMemoryDecision(mode).resolved;}
function currentTheSpiderPreviewMemoryProfile(){
  var selected=storedTheSpiderPreviewMemoryMode(),decision=resolvedTheSpiderPreviewMemoryDecision(selected),resolved=decision.resolved;
  var profile=THE_SPIDER_PREVIEW_MEMORY_PROFILES[resolved]||THE_SPIDER_PREVIEW_MEMORY_PROFILES.high;
  return {selected:selected,resolved:resolved,profile:profile,reason:decision.reason,freshness:decision.freshness,age_ms:decision.age_ms};
}
function theSpiderPreviewBrowserCacheStats(){
  ensureTheSpiderPreviewCaches();
  var payloadBytes=0,domBytes=0;
  window._theSpiderPreviewPayloadCache.forEach(function(item){payloadBytes+=Number(item&&item.bytes)||0;});
  window._theSpiderPreviewDomCache.forEach(function(item){domBytes+=Number(item&&item.domBytes)||0;});
  return {payload_entries:window._theSpiderPreviewPayloadCache.size,payload_bytes:payloadBytes,payload_max_bytes:THE_SPIDER_PREVIEW_PAYLOAD_MAX_BYTES,dom_entries:window._theSpiderPreviewDomCache.size,dom_bytes:domBytes,dom_max_bytes:THE_SPIDER_PREVIEW_DOM_MAX_BYTES,prefetch_ready:currentTheSpiderPreviewReadyKeys().size,prefetch_target:Math.max(0,Number(window._theSpiderPreviewPrefetchTotal)||0)};
}
function trimTheSpiderPreviewCachesToLimits(){
  ensureTheSpiderPreviewCaches();
  var payloadBytes=0;window._theSpiderPreviewPayloadCache.forEach(function(item){payloadBytes+=Number(item&&item.bytes)||0;});
  while(window._theSpiderPreviewPayloadCache.size>THE_SPIDER_PREVIEW_PAYLOAD_MAX_ENTRIES||payloadBytes>THE_SPIDER_PREVIEW_PAYLOAD_MAX_BYTES){
    var key=window._theSpiderPreviewPayloadCache.keys().next().value;if(!key)break;var old=window._theSpiderPreviewPayloadCache.get(key)||{};window._theSpiderPreviewPayloadCache.delete(key);payloadBytes-=Number(old.bytes)||0;
  }
  var domBytes=0;window._theSpiderPreviewDomCache.forEach(function(item){domBytes+=Number(item&&item.domBytes)||0;});
  while(window._theSpiderPreviewDomCache.size>THE_SPIDER_PREVIEW_DOM_MAX_ENTRIES||domBytes>THE_SPIDER_PREVIEW_DOM_MAX_BYTES){
    var domKey=window._theSpiderPreviewDomCache.keys().next().value;if(!domKey)break;var domOld=window._theSpiderPreviewDomCache.get(domKey)||{};window._theSpiderPreviewDomCache.delete(domKey);domBytes-=Number(domOld.domBytes)||0;releaseTheSpiderPreviewDomEntry(domOld);
  }
}
function applyTheSpiderPreviewMemoryMode(mode,clearExisting){
  var selected=/^(auto|low|standard|high)$/.test(String(mode||''))?String(mode):storedTheSpiderPreviewMemoryMode();
  var resolved=resolvedTheSpiderPreviewMemoryMode(selected),profile=THE_SPIDER_PREVIEW_MEMORY_PROFILES[resolved]||THE_SPIDER_PREVIEW_MEMORY_PROFILES.high;
  THE_SPIDER_PREVIEW_PREFETCH_AUTO_MAX_BYTES=profile.autoBytes;THE_SPIDER_PREVIEW_PREFETCH_MANUAL_MAX_BYTES=profile.manualBytes;THE_SPIDER_PREVIEW_PAYLOAD_MAX_BYTES=profile.payloadBytes;THE_SPIDER_PREVIEW_PAYLOAD_MAX_ENTRIES=profile.payloadEntries;THE_SPIDER_PREVIEW_DOM_MAX_BYTES=profile.domBytes;THE_SPIDER_PREVIEW_DOM_MAX_ENTRIES=profile.domEntries;
  var changed=_theSpiderPreviewAppliedSelection!==selected||_theSpiderPreviewAppliedResolution!==resolved;
  if(clearExisting&&changed)resetTheSpiderPreviewCaches();else trimTheSpiderPreviewCachesToLimits();
  _theSpiderPreviewAppliedSelection=selected;_theSpiderPreviewAppliedResolution=resolved;
  window._theSpiderPreviewPrefetchBudgetBytes=Number(window._theSpiderPreviewPrefetchTotal)>THE_SPIDER_PREVIEW_PREFETCH_BATCH_SIZE?THE_SPIDER_PREVIEW_PREFETCH_MANUAL_MAX_BYTES:THE_SPIDER_PREVIEW_PREFETCH_AUTO_MAX_BYTES;
  updateTheSpiderPreviewCacheStatus();
  scheduleTheSpiderPreviewMemoryFreshnessDeadline(selected);
  return {selected:selected,resolved:resolved,profile:profile,changed:changed};
}
function scheduleTheSpiderPreviewMemoryFreshnessDeadline(mode){
  if(_theSpiderPreviewMemoryFreshnessTimer!==null){clearTimeout(_theSpiderPreviewMemoryFreshnessTimer);_theSpiderPreviewMemoryFreshnessTimer=null;}
  if(String(mode||storedTheSpiderPreviewMemoryMode())!=='auto')return;
  var diagnostic=trustedTheSpiderPreviewMemoryDiagnostic();
  if(!diagnostic.fresh||diagnostic.age_ms===null)return;
  var delay=Math.max(1,THE_SPIDER_PREVIEW_DIAGNOSTIC_FRESH_MS-diagnostic.age_ms+1);
  var timerId=setTimeout(function(){
    if(_theSpiderPreviewMemoryFreshnessTimer!==timerId)return;
    _theSpiderPreviewMemoryFreshnessTimer=null;
    if(storedTheSpiderPreviewMemoryMode()!=='auto')return;
    applyTheSpiderPreviewMemoryMode('auto',false);
    renderCvStudioDiagnosticStatus(window._cvStudioLastRuntimeDiagnostics||null);
  },delay);
  _theSpiderPreviewMemoryFreshnessTimer=timerId;
}
async function setTheSpiderPreviewMemoryMode(mode,announce){
  mode=/^(auto|low|standard|high)$/.test(String(mode||''))?String(mode):'high';
  try{cvStudioDurableSettingSet(THE_SPIDER_PREVIEW_MEMORY_MODE_KEY,mode);}catch(e){}
  var result=applyTheSpiderPreviewMemoryMode(mode,true);renderCvStudioDiagnosticStatus(window._cvStudioLastRuntimeDiagnostics||null);
  if(announce){
    if(!result.changed){showToast('AI Crawler preview memory remains '+result.profile.label+'. Existing caches were retained.','ok');return;}
    var backendCleared=false,backendMessage='';
    try{
      var r=await fetch('/diagnostics/clear_preview_cache',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}),d=await r.json().catch(function(){return {};});
      if(r.ok&&d.ok){backendCleared=true;window._cvStudioLastRuntimeDiagnostics=Object.assign({},window._cvStudioLastRuntimeDiagnostics||{ok:true},{cache:d.cache||{}});renderCvStudioDiagnosticStatus(window._cvStudioLastRuntimeDiagnostics);}
      else backendMessage=d.error||('HTTP '+r.status);
    }catch(e){backendMessage=(e&&e.message)||'request failed';}
    if(backendCleared)showToast('AI Crawler preview memory set to '+result.profile.label+(mode==='auto'?' (Auto resolved)':'')+'. Browser and backend preview caches cleared.','ok');
    else showToast('Preview memory set to '+result.profile.label+'. Browser cache cleared; backend clear was not confirmed'+(backendMessage?': '+backendMessage:'')+'.','warn');
  }
}
var _theSpiderPreviewAutoDiagnosticsQueued=false;
function scheduleTheSpiderPreviewAutoDiagnostics(){
  if(storedTheSpiderPreviewMemoryMode()!=='auto'||_theSpiderPreviewAutoDiagnosticsQueued||Number(window._cvStudioSystemMemoryTotalBytes)>0)return;
  _theSpiderPreviewAutoDiagnosticsQueued=true;
  var run=function(){setTimeout(function(){_theSpiderPreviewAutoDiagnosticsQueued=false;if(storedTheSpiderPreviewMemoryMode()==='auto'&&Number(window._cvStudioSystemMemoryTotalBytes)<=0)refreshCvStudioDiagnostics(false);},0);};
  if(document.readyState==='complete')run();else window.addEventListener('load',run,{once:true});
}
applyTheSpiderPreviewMemoryMode(storedTheSpiderPreviewMemoryMode(),false);
scheduleTheSpiderPreviewAutoDiagnostics();
function estimateTheSpiderPreviewPayloadBytes(payload) {
  try { return Math.max(1, JSON.stringify(payload || {}).length * 2); } catch(e) { return 1; }
}
function estimateTheSpiderPreviewDomBytes(payload) {
  payload = payload || {};
  var pages = Math.max(0, Number(payload.shown_pages) || (Array.isArray(payload.page_images) ? payload.page_images.length : 0));
  if (pages) return pages * 6 * 1024 * 1024;
  if (payload.data_url && /^data:image\//i.test(String(payload.data_url))) return 8 * 1024 * 1024;
  return Math.max(256 * 1024, Math.min(8 * 1024 * 1024, estimateTheSpiderPreviewPayloadBytes(payload)));
}
function currentTheSpiderPreviewReadyKeys() {
  ensureTheSpiderPreviewCaches();
  var ready = new Set();
  window._theSpiderPreviewPayloadCache.forEach(function(_entry,key){ if (window._theSpiderPreviewPrefetchTargets.has(key)) ready.add(key); });
  window._theSpiderPreviewDomCache.forEach(function(_entry,key){ if (window._theSpiderPreviewPrefetchTargets.has(key)) ready.add(key); });
  return ready;
}
function updateTheSpiderPreviewCacheStatus() {
  ensureTheSpiderPreviewCaches();
  var el = document.getElementById('theSpiderPreviewCacheStatus');
  if (!el) return;
  var btn = document.getElementById('theSpiderPreviewNextBtn');
  var total = Math.max(0, Number(window._theSpiderPreviewPrefetchTotal) || 0);
  var available = Math.max(total, Number(window._theSpiderPreviewPrefetchAvailableTotal) || 0);
  var maxTotal = Math.min(available, THE_SPIDER_PREVIEW_PREFETCH_MAX_TOTAL);
  var ready = total ? currentTheSpiderPreviewReadyKeys().size : 0;
  var failed = total ? Array.from(window._theSpiderPreviewPrefetchFailed).filter(function(key){ return window._theSpiderPreviewPrefetchTargets.has(key); }).length : 0;
  var pending = !!window._theSpiderPreviewPrefetchRunning || (window._theSpiderPreviewPrefetchQueue || []).length > 0;
  var stopped = String(window._theSpiderPreviewPrefetchStopReason || '');
  var terminal = stopped === 'memory' || stopped === 'failures' || stopped === 'locked' || stopped === 'auth';
  var nextCount = Math.max(0, Math.min(THE_SPIDER_PREVIEW_PREFETCH_BATCH_SIZE, maxTotal - total));
  var canLoadNext = total > 0 && nextCount > 0 && !pending && !terminal;
  var cacheStats = theSpiderPreviewBrowserCacheStats();
  var cacheUsedMb = Math.round((Number(cacheStats.payload_bytes||0)+Number(cacheStats.dom_bytes||0))/1024/1024);
  var cacheLimitMb = Math.round((Number(cacheStats.payload_max_bytes||0)+Number(cacheStats.dom_max_bytes||0))/1024/1024);
  el.title = 'Browser preview cache: ' + cacheUsedMb + ' MB used of ' + cacheLimitMb + ' MB · payload ' + cacheStats.payload_entries + ' · rendered ' + cacheStats.dom_entries;
  el.classList.toggle('running', pending);
  el.classList.toggle('done', total > 0 && !pending && ready > 0);
  if (!total) el.textContent = 'Preview cache ready';
  else if (pending) el.textContent = 'Preloading ' + ready + '/' + total;
  else if (stopped === 'memory') el.textContent = 'Preview cache ' + ready + '/' + total + ' ready · memory cap';
  else if (stopped === 'failures') el.textContent = 'Preview preload stopped · ' + ready + ' ready, ' + failed + ' failed';
  else if (stopped === 'locked') el.textContent = 'Preview preload stopped · AI Crawler locked';
  else if (stopped === 'auth') el.textContent = 'Preview preload stopped · reconnect JobAdder';
  else if (failed) el.textContent = 'Preview preload finished · ' + ready + ' ready, ' + failed + ' failed';
  else if (ready >= total) el.textContent = 'Previews ready ' + ready + '/' + total + (available > total ? ' · ' + (available - total) + ' more available' : '');
  else el.textContent = 'Preview cache ' + ready + '/' + total + ' ready';
  if (total && !pending && cacheUsedMb) el.textContent += ' · ' + cacheUsedMb + ' MB';
  if (btn) {
    btn.classList.toggle('show', canLoadNext);
    btn.disabled = !canLoadNext;
    btn.textContent = nextCount ? ('Preload next ' + nextCount) : 'Preload next 30';
    btn.title = nextCount ? ('Warm the next ' + nextCount + ' candidates in the current displayed order. Total warming stays capped at 60 candidates and 512 MB of lightweight preview payloads.') : '';
  }
}
function spiderPreviewCacheStatusHtml() {
  return '<span class="spider-preview-cache-wrap"><span class="spider-preview-cache-pill" id="theSpiderPreviewCacheStatus">Preview cache ready</span><button type="button" class="spider-preview-next-btn" id="theSpiderPreviewNextBtn" onclick="preloadNextTheSpiderPreviewBatch()">Preload next 30</button></span>';
}
function touchTheSpiderPreviewPayloadCache(key) {
  ensureTheSpiderPreviewCaches();
  if (!key || !window._theSpiderPreviewPayloadCache.has(key)) return null;
  var entry = window._theSpiderPreviewPayloadCache.get(key);
  window._theSpiderPreviewPayloadCache.delete(key);
  entry.lastUsed = Date.now();
  window._theSpiderPreviewPayloadCache.set(key, entry);
  return entry;
}
function releaseTheSpiderPreviewDomEntry(entry) {
  if (!entry || !entry.root) return;
  try {
    entry.root.querySelectorAll('img').forEach(function(img){ img.removeAttribute('src'); });
    if (entry.root.parentNode) entry.root.parentNode.removeChild(entry.root);
  } catch(e) {}
}
function removeTheSpiderPreviewCacheKey(key) {
  ensureTheSpiderPreviewCaches();
  if (!key) return;
  window._theSpiderPreviewPayloadCache.delete(key);
  var domEntry = window._theSpiderPreviewDomCache.get(key);
  if (domEntry) releaseTheSpiderPreviewDomEntry(domEntry);
  window._theSpiderPreviewDomCache.delete(key);
  window._theSpiderPreviewEvictedKeys.add(key);
  updateTheSpiderPreviewCacheStatus();
}
function putTheSpiderPreviewPayloadCache(candidateId, payload, localCandidate) {
  ensureTheSpiderPreviewCaches();
  var key = theSpiderPreviewCacheKey(candidateId);
  if (!key || !payload || payload.error) return null;
  var bytes = estimateTheSpiderPreviewPayloadBytes(payload);
  var existing = window._theSpiderPreviewPayloadCache.get(key);
  if (existing) window._theSpiderPreviewPayloadCache.delete(key);
  var entry = {
    key:key,
    candidateId:String(candidateId||''),
    payload:payload,
    local:localCandidate||{},
    bytes:bytes,
    lastUsed:Date.now(),
    validatedAt:Date.now(),
    attachmentFingerprint:String(payload.attachment_fingerprint || '')
  };
  window._theSpiderPreviewPayloadCache.set(key, entry);
  var totalBytes = 0;
  window._theSpiderPreviewPayloadCache.forEach(function(item){ totalBytes += Number(item && item.bytes) || 0; });
  while (window._theSpiderPreviewPayloadCache.size > THE_SPIDER_PREVIEW_PAYLOAD_MAX_ENTRIES || totalBytes > THE_SPIDER_PREVIEW_PAYLOAD_MAX_BYTES) {
    var oldestKey = window._theSpiderPreviewPayloadCache.keys().next().value;
    if (!oldestKey || oldestKey === key && window._theSpiderPreviewPayloadCache.size <= 1) break;
    var old = window._theSpiderPreviewPayloadCache.get(oldestKey) || {};
    window._theSpiderPreviewPayloadCache.delete(oldestKey);
    window._theSpiderPreviewEvictedKeys.add(oldestKey);
    totalBytes -= Number(old.bytes) || 0;
  }
  updateTheSpiderPreviewCacheStatus();
  // If the just-inserted entry was immediately evicted for exceeding the cap,
  // report that it was not retained rather than describing a dead entry.
  return window._theSpiderPreviewPayloadCache.has(key) ? entry : null;
}
function theSpiderPreviewPrefetchLiveBytes() {
  // Authoritative live total: the bytes of prefetch-target payloads still
  // resident in the cache. Used for the budget decision so eviction/removal is
  // reflected immediately, instead of a monotonic counter that only ever grows
  // and drifts above real usage (stopping prefetch with a false "memory" cap).
  ensureTheSpiderPreviewCaches();
  var targets = window._theSpiderPreviewPrefetchTargets;
  var bytes = 0;
  window._theSpiderPreviewPayloadCache.forEach(function(entry, key){
    if (!(targets instanceof Set) || targets.has(key)) bytes += Number(entry && entry.bytes) || 0;
  });
  return bytes;
}
function preloadTheSpiderPreviewImages(payload, maxPages) {
  var sources = [];
  if (payload && Array.isArray(payload.page_images)) sources = payload.page_images.slice();
  else if (payload && payload.data_url && /^data:image\//i.test(String(payload.data_url))) sources = [payload.data_url];
  maxPages = Math.max(0, Math.min(12, Number(maxPages) || 0));
  sources.slice(0, maxPages).forEach(function(src){
    try {
      var img = new Image();
      img.decoding = 'async';
      img.src = src;
      if (img.decode) img.decode().catch(function(){});
    } catch(e) {}
  });
}
function putTheSpiderPreviewDomCache(entry) {
  ensureTheSpiderPreviewCaches();
  if (!entry || !entry.key || !entry.root) return;
  if (window._theSpiderPreviewDomCache.has(entry.key)) window._theSpiderPreviewDomCache.delete(entry.key);
  entry.lastUsed = Date.now();
  entry.domBytes = Number(entry.domBytes) || estimateTheSpiderPreviewDomBytes(entry.payload);
  window._theSpiderPreviewDomCache.set(entry.key, entry);
  var totalDomBytes = 0;
  window._theSpiderPreviewDomCache.forEach(function(item){ totalDomBytes += Number(item && item.domBytes) || 0; });
  while (window._theSpiderPreviewDomCache.size > THE_SPIDER_PREVIEW_DOM_MAX_ENTRIES || totalDomBytes > THE_SPIDER_PREVIEW_DOM_MAX_BYTES) {
    var oldestKey = window._theSpiderPreviewDomCache.keys().next().value;
    if (!oldestKey || oldestKey === entry.key && window._theSpiderPreviewDomCache.size <= 1) break;
    var old = window._theSpiderPreviewDomCache.get(oldestKey);
    window._theSpiderPreviewDomCache.delete(oldestKey);
    totalDomBytes -= Number(old && old.domBytes) || 0;
    releaseTheSpiderPreviewDomEntry(old);
  }
}
function buildTheSpiderPreviewDomEntry(candidateId, payload, localCandidate) {
  var key = theSpiderPreviewCacheKey(candidateId);
  var root = document.createElement('div');
  root.className = 'spider-preview-cached-entry';
  root.setAttribute('data-spider-preview-cache-key', key);
  root.innerHTML = renderTheSpiderCandidatePreviewPane(payload, localCandidate || {});
  var entry = {
    key:key,
    candidateId:String(candidateId || ''),
    payload:payload,
    local:localCandidate || {},
    root:root,
    searchText:Object.prototype.hasOwnProperty.call(payload || {}, 'search_text') ? String(payload.search_text || '') : String((payload && payload.preview_text) || localTheSpiderCandidatePreview(localCandidate || {})),
    visualLayers:Array.isArray(payload && payload.visual_text_layers) ? payload.visual_text_layers : [],
    attachmentFingerprint:String(payload && payload.attachment_fingerprint || ''),
    validatedAt:Date.now(),
    domBytes:estimateTheSpiderPreviewDomBytes(payload),
    lastUsed:Date.now()
  };
  putTheSpiderPreviewDomCache(entry);
  return entry;
}
function activateTheSpiderPreviewDomEntry(entry) {
  if (!entry || !entry.root) return false;
  var pane = document.getElementById('theSpiderCvPreview');
  if (!pane) return false;
  pane.replaceChildren(entry.root);
  entry.lastUsed = Date.now();
  if (window._theSpiderPreviewDomCache && window._theSpiderPreviewDomCache.has(entry.key)) {
    window._theSpiderPreviewDomCache.delete(entry.key);
    window._theSpiderPreviewDomCache.set(entry.key, entry);
  }
  setTheSpiderPreviewSearchText(entry.searchText || '');
  setTheSpiderVisualTextLayers(entry.visualLayers || []);
  window._theSpiderPreviewActiveCacheKey = entry.key;
  requestAnimationFrame(function(){
    initializeTheSpiderPreviewFinder();
    setTheSpiderPreviewMode('visual', true);
    updateTheSpiderPreviewCacheStatus();
  });
  return true;
}
function cancelTheSpiderServerPreviewPrefetch() {
  try {
    fetch('/jobadder/spider_preview_cancel_prefetch', {
      method:'POST',
      headers:{'Content-Type':'application/json','X-AI-Crawler-Code':aiCrawlerLockPayload()},
      body:'{}',
      keepalive:true
    }).catch(function(){});
  } catch(e) {}
}
function resetTheSpiderPreviewCaches() {
  ensureTheSpiderPreviewCaches();
  cancelTheSpiderServerPreviewPrefetch();
  window._theSpiderPreviewRequestSeq = (Number(window._theSpiderPreviewRequestSeq) || 0) + 1;
  if (window._theSpiderPreviewAbortController) { try { window._theSpiderPreviewAbortController.abort(); } catch(e) {} }
  if (window._theSpiderPreviewPrefetchAbortController) { try { window._theSpiderPreviewPrefetchAbortController.abort(); } catch(e) {} }
  window._theSpiderPreviewAbortController = null;
  window._theSpiderPreviewPrefetchAbortController = null;
  window._theSpiderPreviewPrefetchGeneration = (Number(window._theSpiderPreviewPrefetchGeneration) || 0) + 1;
  window._theSpiderPreviewPrefetchQueue = [];
  window._theSpiderPreviewPrefetchAllItems = [];
  window._theSpiderPreviewPrefetchFailed = new Set();
  window._theSpiderPreviewPrefetchAttempted = new Set();
  window._theSpiderPreviewPrefetchTargets = new Set();
  window._theSpiderPreviewEvictedKeys = new Set();
  window._theSpiderPreviewPrefetchRunning = false;
  window._theSpiderPreviewPrefetchPaused = false;
  window._theSpiderPreviewPrefetchCurrentKey = '';
  window._theSpiderPreviewPrefetchCurrentPromise = null;
  window._theSpiderPreviewPrefetchTotal = 0;
  window._theSpiderPreviewPrefetchAvailableTotal = 0;
  window._theSpiderPreviewPrefetchBytes = 0;
  window._theSpiderPreviewPrefetchBudgetBytes = THE_SPIDER_PREVIEW_PREFETCH_AUTO_MAX_BYTES;
  window._theSpiderPreviewPrefetchConsecutiveFailures = 0;
  window._theSpiderPreviewPrefetchStopReason = '';
  window._theSpiderPreviewPrefetchAuthWarned = false;
  window._theSpiderPreviewPayloadCache.clear();
  window._theSpiderPreviewDomCache.forEach(function(entry){ releaseTheSpiderPreviewDomEntry(entry); });
  window._theSpiderPreviewDomCache.clear();
  window._theSpiderPreviewValidationInFlight.clear();
  window._theSpiderPreviewUpgradeInFlight.clear();
  window._theSpiderPreviewActiveCacheKey = '';
}
async function fetchTheSpiderPreviewPayload(candidateId, controller, timeoutMs, options) {
  options = options || {};
  var query = '?candidate_id=' + encodeURIComponent(candidateId);
  if (options.prefetch) query += '&prefetch=1';
  if (options.validate) query += '&validate=1';
  if (options.allowUnverified) query += '&allow_unverified=1';
  var timer = setTimeout(function(){ try { controller.abort(); } catch(e) {} }, Math.max(1000, Number(timeoutMs) || 45000));
  try {
    var r = await fetch('/jobadder/spider_candidate_preview' + query, {method:'GET',headers:{'X-AI-Crawler-Code':aiCrawlerLockPayload()},signal:controller.signal});
    var d = await r.json().catch(function(){ return {}; });
    if (!r.ok || d.error) {
      var previewErr = new Error(d.error || ('Preview failed: ' + r.status));
      previewErr.status = r.status;
      previewErr.code = d.code || '';
      previewErr.action = d.action || '';
      previewErr.needsReconnect = !!d.needs_reconnect || r.status === 401;
      previewErr.prefetchCancelled = !!d.prefetch_cancelled;
      throw previewErr;
    }
    return d;
  } finally { clearTimeout(timer); }
}
function invalidateTheSpiderPreviewIfFingerprintChanged(entry, validation, idx) {
  if (!entry || !validation || !validation.attachment_fingerprint) return false;
  var previous = String(entry.attachmentFingerprint || (entry.payload && entry.payload.attachment_fingerprint) || '');
  var current = String(validation.attachment_fingerprint || '');
  entry.validatedAt = Date.now();
  if (!previous || previous === current) return false;
  var key = entry.key || theSpiderPreviewCacheKey(entry.candidateId);
  removeTheSpiderPreviewCacheKey(key);
  if (window._theSpiderPreviewRequestedCandidateId === String(entry.candidateId || '')) {
    setTimeout(function(){ openTheSpiderCandidatePreview(entry.candidateId, idx, {forceNetwork:true}); }, 0);
  }
  return true;
}
function scheduleTheSpiderPreviewRevalidation(entry, idx) {
  ensureTheSpiderPreviewCaches();
  if (!entry || !entry.candidateId || !entry.attachmentFingerprint) return;
  if (Date.now() - Number(entry.validatedAt || 0) < THE_SPIDER_PREVIEW_REVALIDATE_MS) return;
  var key = entry.key || theSpiderPreviewCacheKey(entry.candidateId);
  if (window._theSpiderPreviewValidationInFlight.has(key)) return;
  var controller = new AbortController();
  var promise = fetchTheSpiderPreviewPayload(entry.candidateId, controller, 12000, {validate:true})
    .then(function(validation){ invalidateTheSpiderPreviewIfFingerprintChanged(entry, validation, idx); })
    .catch(function(){})
    .finally(function(){ window._theSpiderPreviewValidationInFlight.delete(key); });
  window._theSpiderPreviewValidationInFlight.set(key, promise);
}
function reorderTheSpiderPreviewPrefetchQueue(focusIdx) {
  ensureTheSpiderPreviewCaches();
  var items = window._theSpiderLastResults || [];
  var order = [], seen = {};
  focusIdx = Math.max(0, Math.min(items.length - 1, Number(focusIdx) || 0));
  function addIndex(i) {
    if (i < 0 || i >= items.length) return;
    var id = getTheSpiderCandidateId(items[i]), key = theSpiderPreviewCacheKey(id);
    if (!key || seen[key] || !window._theSpiderPreviewPrefetchTargets.has(key) || window._theSpiderPreviewPayloadCache.has(key) || window._theSpiderPreviewPrefetchAttempted.has(key)) return;
    seen[key] = true; order.push({candidateId:id,idx:i,key:key});
  }
  for (var distance = 1; distance < items.length; distance++) { addIndex(focusIdx + distance); addIndex(focusIdx - distance); }
  items.forEach(function(_c,i){ addIndex(i); });
  window._theSpiderPreviewPrefetchQueue = order;
}
function pauseTheSpiderPreviewPrefetchForForeground(candidateKey) {
  ensureTheSpiderPreviewCaches();
  window._theSpiderPreviewPrefetchPaused = true;
  var samePromise = null;
  if (candidateKey && window._theSpiderPreviewPrefetchCurrentKey === candidateKey) {
    samePromise = window._theSpiderPreviewPrefetchCurrentPromise || null;
  } else if (window._theSpiderPreviewPrefetchAbortController) {
    try { window._theSpiderPreviewPrefetchAbortController.abort(); } catch(e) {}
  }
  return samePromise;
}
function resumeTheSpiderPreviewPrefetch(focusIdx) {
  window._theSpiderPreviewPrefetchPaused = false;
  reorderTheSpiderPreviewPrefetchQueue(focusIdx);
  setTimeout(runTheSpiderPreviewPrefetchQueue, 100);
}
async function upgradeTheSpiderPartialPreview(candidateId, idx, requestSeq) {
  ensureTheSpiderPreviewCaches();
  var key = theSpiderPreviewCacheKey(candidateId);
  if (!key) return;
  if (window._theSpiderPreviewUpgradeInFlight.has(key)) return window._theSpiderPreviewUpgradeInFlight.get(key);
  var task = (async function(){
    var controller = new AbortController();
    window._theSpiderPreviewAbortController = controller;
    try {
      var full = await fetchTheSpiderPreviewPayload(candidateId, controller, 45000, {});
      if (window._theSpiderPreviewRequestSeq !== requestSeq || window._theSpiderPreviewRequestedCandidateId !== String(candidateId || '')) return;
      var local = (window._theSpiderLastResults || [])[Number(idx)] || {};
      putTheSpiderPreviewPayloadCache(candidateId, full, local);
      var oldDom = window._theSpiderPreviewDomCache.get(key);
      if (oldDom) releaseTheSpiderPreviewDomEntry(oldDom);
      window._theSpiderPreviewDomCache.delete(key);
      preloadTheSpiderPreviewImages(full, 12);
      activateTheSpiderPreviewDomEntry(buildTheSpiderPreviewDomEntry(candidateId, full, local));
    } catch(e) {
      if (!(e && e.name === 'AbortError')) showToast('Full CV preview could not be completed; the opening pages remain available.', 'warn');
    } finally {
      if (window._theSpiderPreviewAbortController === controller) window._theSpiderPreviewAbortController = null;
      window._theSpiderPreviewUpgradeInFlight.delete(key);
      if (window._theSpiderPreviewRequestSeq === requestSeq && window._theSpiderPreviewRequestedCandidateId === String(candidateId || '')) resumeTheSpiderPreviewPrefetch(idx);
    }
  })();
  window._theSpiderPreviewUpgradeInFlight.set(key, task);
  return task;
}

async function runTheSpiderPreviewPrefetchQueue() {
  ensureTheSpiderPreviewCaches();
  if (window._theSpiderPreviewPrefetchRunning || window._theSpiderPreviewPrefetchPaused || !aiCrawlerIsUnlocked()) return;
  var generation = Number(window._theSpiderPreviewPrefetchGeneration) || 0;
  window._theSpiderPreviewPrefetchRunning = true;
  updateTheSpiderPreviewCacheStatus();
  try {
    while (!window._theSpiderPreviewPrefetchPaused && generation === Number(window._theSpiderPreviewPrefetchGeneration) && window._theSpiderPreviewPrefetchQueue.length) {
      var prefetchBudget = Math.max(1, Number(window._theSpiderPreviewPrefetchBudgetBytes) || THE_SPIDER_PREVIEW_PREFETCH_AUTO_MAX_BYTES);
      window._theSpiderPreviewPrefetchBytes = theSpiderPreviewPrefetchLiveBytes();
      if (Number(window._theSpiderPreviewPrefetchBytes || 0) >= prefetchBudget) {
        window._theSpiderPreviewPrefetchStopReason = 'memory';
        window._theSpiderPreviewPrefetchQueue = [];
        break;
      }
      var item = window._theSpiderPreviewPrefetchQueue.shift();
      if (!item || !item.key || window._theSpiderPreviewPayloadCache.has(item.key) || window._theSpiderPreviewPrefetchAttempted.has(item.key)) continue;
      var controller = new AbortController();
      window._theSpiderPreviewPrefetchAbortController = controller;
      window._theSpiderPreviewPrefetchCurrentKey = item.key;
      var promise = fetchTheSpiderPreviewPayload(item.candidateId, controller, 45000, {prefetch:true});
      window._theSpiderPreviewPrefetchCurrentPromise = promise;
      try {
        var payload = await promise;
        if (generation !== Number(window._theSpiderPreviewPrefetchGeneration)) return;
        var local = (window._theSpiderLastResults || [])[item.idx] || {};
        if (!aiCrawlerIsUnlocked()) return;
        window._theSpiderPreviewPrefetchAttempted.add(item.key);
        window._theSpiderPreviewPrefetchConsecutiveFailures = 0;
        putTheSpiderPreviewPayloadCache(item.candidateId, payload, local);
        window._theSpiderPreviewPrefetchBytes = theSpiderPreviewPrefetchLiveBytes();
        preloadTheSpiderPreviewImages(payload, Math.min(2, Number(payload.shown_pages) || 2));
      } catch(e) {
        if (e && e.prefetchCancelled) {
          // Foreground click or Clear superseded this background render. It is
          // not a failed candidate and may be queued again later.
        } else if ((e && (e.needsReconnect || e.status === 401 || e.status === 403 || e.status === 423)) && generation === Number(window._theSpiderPreviewPrefetchGeneration)) {
          window._theSpiderPreviewPrefetchQueue = [];
          window._theSpiderPreviewPrefetchPaused = true;
          window._theSpiderPreviewPrefetchStopReason = e.status === 423 || e.status === 403 ? 'locked' : 'auth';
          if (!window._theSpiderPreviewPrefetchAuthWarned) {
            window._theSpiderPreviewPrefetchAuthWarned = true;
            showToast(window._theSpiderPreviewPrefetchStopReason === 'locked' ? 'AI Crawler locked — preview preloading stopped' : 'JobAdder connection expired — preview preloading stopped', 'err');
          }
        } else if (!(e && e.name === 'AbortError') && generation === Number(window._theSpiderPreviewPrefetchGeneration)) {
          window._theSpiderPreviewPrefetchAttempted.add(item.key);
          window._theSpiderPreviewPrefetchFailed.add(item.key);
          window._theSpiderPreviewPrefetchConsecutiveFailures = Number(window._theSpiderPreviewPrefetchConsecutiveFailures || 0) + 1;
          if (window._theSpiderPreviewPrefetchConsecutiveFailures >= 3) {
            window._theSpiderPreviewPrefetchStopReason = 'failures';
            window._theSpiderPreviewPrefetchQueue = [];
          }
        }
      } finally {
        if (window._theSpiderPreviewPrefetchAbortController === controller) window._theSpiderPreviewPrefetchAbortController = null;
        if (window._theSpiderPreviewPrefetchCurrentKey === item.key) {
          window._theSpiderPreviewPrefetchCurrentKey = '';
          window._theSpiderPreviewPrefetchCurrentPromise = null;
        }
        updateTheSpiderPreviewCacheStatus();
      }
      await new Promise(function(resolve){ setTimeout(resolve, 180); });
    }
  } finally {
    window._theSpiderPreviewPrefetchRunning = false;
    updateTheSpiderPreviewCacheStatus();
    if (!window._theSpiderPreviewPrefetchPaused && window._theSpiderPreviewPrefetchQueue.length && generation === Number(window._theSpiderPreviewPrefetchGeneration)) setTimeout(runTheSpiderPreviewPrefetchQueue, 120);
  }
}
function startTheSpiderPreviewPrefetch(items) {
  ensureTheSpiderPreviewCaches();
  items = Array.isArray(items) ? items : [];
  var unique = [], seen = {};
  items.forEach(function(c,idx){
    var id=getTheSpiderCandidateId(c), key=theSpiderPreviewCacheKey(id);
    if (!key || seen[key]) return;
    seen[key]=true; unique.push({candidateId:id,idx:idx,key:key});
  });
  window._theSpiderPreviewPrefetchAvailableTotal = unique.length;
  window._theSpiderPreviewPrefetchAllItems = unique.slice(0, THE_SPIDER_PREVIEW_PREFETCH_MAX_TOTAL);
  var firstBatch = window._theSpiderPreviewPrefetchAllItems.slice(0, THE_SPIDER_PREVIEW_PREFETCH_BATCH_SIZE);
  window._theSpiderPreviewPrefetchFailed = new Set();
  window._theSpiderPreviewPrefetchAttempted = new Set();
  window._theSpiderPreviewEvictedKeys = new Set();
  window._theSpiderPreviewPrefetchTargets = new Set(firstBatch.map(function(item){ return item.key; }));
  window._theSpiderPreviewPrefetchTotal = firstBatch.length;
  window._theSpiderPreviewPrefetchBytes = 0;
  window._theSpiderPreviewPrefetchBudgetBytes = THE_SPIDER_PREVIEW_PREFETCH_AUTO_MAX_BYTES;
  window._theSpiderPreviewPrefetchConsecutiveFailures = 0;
  window._theSpiderPreviewPrefetchStopReason = '';
  window._theSpiderPreviewPrefetchQueue = firstBatch;
  updateTheSpiderPreviewCacheStatus();
  setTimeout(runTheSpiderPreviewPrefetchQueue, 250);
}
function restartTheSpiderPreviewPrefetchForCurrentOrder(items) {
  ensureTheSpiderPreviewCaches();
  items = Array.isArray(items) ? items : [];
  var unique = [], seen = {};
  items.forEach(function(c,idx){
    var id=getTheSpiderCandidateId(c), key=theSpiderPreviewCacheKey(id);
    if (!key || seen[key]) return;
    seen[key]=true; unique.push({candidateId:id,idx:idx,key:key});
  });
  var previousTarget = Math.max(0, Number(window._theSpiderPreviewPrefetchTotal) || 0);
  var targetCount = Math.min(
    unique.length,
    THE_SPIDER_PREVIEW_PREFETCH_MAX_TOTAL,
    Math.max(THE_SPIDER_PREVIEW_PREFETCH_BATCH_SIZE, previousTarget || 0)
  );
  var targetItems = unique.slice(0, targetCount);
  var targetKeys = new Set(targetItems.map(function(item){ return item.key; }));
  var previousAttempted = window._theSpiderPreviewPrefetchAttempted instanceof Set ? window._theSpiderPreviewPrefetchAttempted : new Set();
  var previousFailed = window._theSpiderPreviewPrefetchFailed instanceof Set ? window._theSpiderPreviewPrefetchFailed : new Set();

  window._theSpiderPreviewPrefetchGeneration = (Number(window._theSpiderPreviewPrefetchGeneration) || 0) + 1;
  if (window._theSpiderPreviewPrefetchAbortController) {
    try { window._theSpiderPreviewPrefetchAbortController.abort(); } catch(e) {}
  }
  cancelTheSpiderServerPreviewPrefetch();
  window._theSpiderPreviewPrefetchPaused = false;
  window._theSpiderPreviewPrefetchAllItems = unique.slice(0, THE_SPIDER_PREVIEW_PREFETCH_MAX_TOTAL);
  window._theSpiderPreviewPrefetchAvailableTotal = unique.length;
  window._theSpiderPreviewPrefetchTargets = targetKeys;
  window._theSpiderPreviewPrefetchTotal = targetCount;
  window._theSpiderPreviewPrefetchBudgetBytes = targetCount > THE_SPIDER_PREVIEW_PREFETCH_BATCH_SIZE
    ? THE_SPIDER_PREVIEW_PREFETCH_MANUAL_MAX_BYTES
    : THE_SPIDER_PREVIEW_PREFETCH_AUTO_MAX_BYTES;
  window._theSpiderPreviewPrefetchAttempted = new Set(Array.from(previousAttempted).filter(function(key){ return targetKeys.has(key); }));
  window._theSpiderPreviewPrefetchFailed = new Set(Array.from(previousFailed).filter(function(key){ return targetKeys.has(key); }));

  var liveBytes = 0;
  targetItems.forEach(function(item){
    var entry = window._theSpiderPreviewPayloadCache.get(item.key);
    if (entry) liveBytes += Number(entry.bytes) || 0;
  });
  window._theSpiderPreviewPrefetchBytes = liveBytes;
  var stopped = String(window._theSpiderPreviewPrefetchStopReason || '');
  var fatalStop = stopped === 'locked' || stopped === 'auth' || stopped === 'memory' || stopped === 'failures';
  window._theSpiderPreviewPrefetchQueue = fatalStop ? [] : targetItems.filter(function(item){
    return item && item.key && !window._theSpiderPreviewPayloadCache.has(item.key) && !window._theSpiderPreviewPrefetchAttempted.has(item.key);
  });
  updateTheSpiderPreviewCacheStatus();

  if (!fatalStop && window._theSpiderPreviewPrefetchQueue.length) {
    (function waitForOldQueue(){
      if (window._theSpiderPreviewPrefetchRunning) {
        setTimeout(waitForOldQueue, 60);
        return;
      }
      runTheSpiderPreviewPrefetchQueue();
    })();
  }
}

function preloadNextTheSpiderPreviewBatch() {
  ensureTheSpiderPreviewCaches();
  if (window._theSpiderPreviewPrefetchRunning || (window._theSpiderPreviewPrefetchQueue || []).length) {
    showToast('Preview preloading is still running', 'info');
    return false;
  }
  var stopped = String(window._theSpiderPreviewPrefetchStopReason || '');
  if (stopped === 'memory') { showToast('Preview memory cap reached. Open candidates on demand or start a new search.', 'warn'); return false; }
  if (stopped === 'locked') { showToast('Unlock AI Crawler before preloading more previews', 'err'); return false; }
  if (stopped === 'auth') { showToast('Reconnect JobAdder before preloading more previews', 'err'); return false; }
  if (stopped === 'failures') { showToast('Preview preload stopped after repeated failures', 'warn'); return false; }
  if (!aiCrawlerIsUnlocked()) { showToast('Unlock AI Crawler before preloading more previews', 'err'); return false; }
  var all = Array.isArray(window._theSpiderPreviewPrefetchAllItems) ? window._theSpiderPreviewPrefetchAllItems : [];
  var current = Math.max(0, Number(window._theSpiderPreviewPrefetchTotal) || 0);
  var nextEnd = Math.min(all.length, THE_SPIDER_PREVIEW_PREFETCH_MAX_TOTAL, current + THE_SPIDER_PREVIEW_PREFETCH_BATCH_SIZE);
  if (nextEnd <= current) { showToast('No more preview batches are available', 'info'); updateTheSpiderPreviewCacheStatus(); return false; }
  var nextItems = all.slice(current, nextEnd);
  nextItems.forEach(function(item){ if (item && item.key) window._theSpiderPreviewPrefetchTargets.add(item.key); });
  window._theSpiderPreviewPrefetchTotal = nextEnd;
  window._theSpiderPreviewPrefetchBudgetBytes = THE_SPIDER_PREVIEW_PREFETCH_MANUAL_MAX_BYTES;
  window._theSpiderPreviewPrefetchConsecutiveFailures = 0;
  window._theSpiderPreviewPrefetchStopReason = '';
  window._theSpiderPreviewPrefetchQueue = nextItems.filter(function(item){
    return item && item.key && !window._theSpiderPreviewPayloadCache.has(item.key) && !window._theSpiderPreviewPrefetchAttempted.has(item.key);
  });
  updateTheSpiderPreviewCacheStatus();
  if (!window._theSpiderPreviewPrefetchQueue.length) {
    updateTheSpiderPreviewCacheStatus();
    return true;
  }
  showToast('Preloading candidates ' + (current + 1) + ' to ' + nextEnd, 'info');
  setTimeout(runTheSpiderPreviewPrefetchQueue, 120);
  return true;
}

function renderTheSpiderPreviewShell() {
  window._theSpiderPreviewSearchText = '';
  window._theSpiderPreviewFindHits = [];
  window._theSpiderPreviewFindIndex = -1;
  window._theSpiderPreviewFindQuery = '';
  window._theSpiderPreviewRequestSeq = (Number(window._theSpiderPreviewRequestSeq) || 0) + 1;
  if (window._theSpiderPreviewAbortController) { try { window._theSpiderPreviewAbortController.abort(); } catch(e) {} }
  window._theSpiderPreviewAbortController = null;
  setTimeout(updateTheSpiderPreviewCacheStatus, 0);
  return '<div class="spider-cv-preview" id="theSpiderCvPreview"><div class="spider-cv-preview-head"><div><div class="spider-cv-preview-title">Candidate CV Preview</div><div class="spider-cv-preview-sub">Click a candidate card. Remaining shortlisted previews load quietly in the background.</div></div>' + spiderPreviewCacheStatusHtml() + '</div><div class="spider-cv-preview-empty">No candidate selected yet.</div></div>';
}
function setTheSpiderCandidateSelected(idx) {
  document.querySelectorAll('.spider-candidate-card[data-spider-index]').forEach(function(card){
    card.classList.toggle('selected', String(card.getAttribute('data-spider-index')) === String(idx));
  });
}
function localTheSpiderCandidatePreview(c) {
  c = c || {};
  var name = c.name || [c.firstName,c.lastName].filter(Boolean).join(' ') || c.fullName || 'Candidate';
  var title = c.currentPosition || c.position || c.jobTitle || (c.employment && c.employment.current && c.employment.current.position) || '';
  var company = c.currentCompany || c.employer || (c.employment && c.employment.current && c.employment.current.employer) || '';
  var loc = c.location || c.city || c.country || '';
  var bits = [];
  if (name) bits.push('Name: ' + name);
  if (title || company) bits.push('Current: ' + [title, company].filter(Boolean).join(' @ '));
  if (loc) bits.push('Location: ' + loc);
  ['skills','skill','itSkills','qualifications','education','employment','experience','summary','profile'].forEach(function(k){
    if (!c[k]) return;
    var v = c[k];
    try { if (typeof v !== 'string') v = JSON.stringify(v, null, 2); } catch(e) { v = String(v || ''); }
    v = String(v || '').replace(/\s+/g, ' ').trim();
    if (v) bits.push(k.charAt(0).toUpperCase() + k.slice(1) + ': ' + v.slice(0, 1200));
  });
  return bits.join('\n\n') || 'No preview fields returned in this JobAdder result.';
}
function spiderPreviewFindControls() {
  return '<div class="spider-preview-find" id="theSpiderPreviewFind" role="search" aria-label="Find in candidate CV preview">'
    + '<button type="button" class="spider-preview-mode-btn active" id="theSpiderPreviewVisualBtn" onclick="setTheSpiderPreviewMode(\'visual\')" title="Show original visual CV">Visual</button>'
    + '<button type="button" class="spider-preview-mode-btn" id="theSpiderPreviewTextBtn" onclick="setTheSpiderPreviewMode(\'text\')" title="Show selectable CV text">Select text</button>'
    + '<button type="button" class="spider-preview-copy-btn" id="theSpiderPreviewCopyBtn" onclick="copyTheSpiderPreviewSelection()" title="Copy the text you selected inside the CV preview">Copy selection</button>'
    + '<button type="button" class="spider-preview-boolean-btn" id="theSpiderPreviewBooleanBtn" onclick="toggleTheSpiderBooleanHighlights()" aria-pressed="true" title="Automatically highlight all terms from Boolean Rules / Keywords in the visual and selectable CV preview">Boolean HL: On</button>'
    + '<input id="theSpiderPreviewFindInput" type="search" autocomplete="off" placeholder="Find in CV preview" aria-label="Find in CV preview" oninput="runTheSpiderPreviewFind(0)" onkeydown="handleTheSpiderPreviewFindKey(event)">'
    + '<span class="spider-preview-find-count" id="theSpiderPreviewFindCount">0/0</span>'
    + '<button type="button" onclick="runTheSpiderPreviewFind(-1)" title="Previous match" aria-label="Previous match">↑</button>'
    + '<button type="button" onclick="runTheSpiderPreviewFind(1)" title="Next match" aria-label="Next match">↓</button>'
    + '<button type="button" onclick="closeTheSpiderPreviewFind()" title="Clear manual search" aria-label="Clear manual search">×</button></div>';
}
function getTheSpiderPreviewSelectedText() {
  try {
    var sel = window.getSelection && window.getSelection();
    if (!sel || sel.rangeCount < 1 || sel.isCollapsed) return '';
    var range = sel.getRangeAt(0);
    var textPane = document.getElementById('theSpiderPreviewTextPane');
    var visualPane = document.getElementById('theSpiderPreviewVisualPane');
    var node = range.commonAncestorContainer;
    if (node && node.nodeType === 3) node = node.parentNode;
    if (!node || !((textPane && textPane.contains(node)) || (visualPane && visualPane.contains(node)))) return '';
    return String(sel.toString() || '').replace(/\s+/g, ' ').trim();
  } catch(e) { return ''; }
}
async function copyTheSpiderPreviewSelection() {
  var selected = getTheSpiderPreviewSelectedText();
  if (!selected) {
    if (hasTheSpiderVisualTextLayer() && window._theSpiderPreviewMode !== 'text') {
      showToast('Drag over words directly on the visual CV, then press Ctrl+C or click Copy selection.', 'err');
      return false;
    }
    setTheSpiderPreviewMode('text', true);
    var doc = document.getElementById('theSpiderPreviewSearchDoc');
    if (doc) { try { doc.focus({preventScroll:true}); } catch(e) { try { doc.focus(); } catch(ignore) {} } }
    showToast('Drag over the CV text first, then press Ctrl+C or click Copy selection.', 'err');
    return false;
  }
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) await navigator.clipboard.writeText(selected);
    else {
      var ta = document.createElement('textarea');
      ta.value = selected;
      ta.setAttribute('readonly','');
      ta.style.position='fixed'; ta.style.opacity='0'; ta.style.pointerEvents='none';
      document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove();
    }
    showToast('Selected CV text copied', 'ok');
    return true;
  } catch(e) {
    showToast('Could not copy automatically. Press Ctrl+C while the text remains selected.', 'err');
    return false;
  }
}
function setTheSpiderPreviewSearchText(text) {
  window._theSpiderPreviewSearchText = String(text || '').replace(/\r\n/g,'\n').slice(0, 30000);
  window._theSpiderPreviewFindHits = [];
  window._theSpiderPreviewFindIndex = -1;
  window._theSpiderPreviewFindQuery = '';
  window._theSpiderBooleanHighlightTerms = [];
  window._theSpiderBooleanHighlightMatches = [];
  clearTheSpiderVisualHighlightClasses('boolean');
  window._theSpiderVisualFindHits = [];
  window._theSpiderVisualFindIndex = -1;
  window._theSpiderVisualFindQuery = '';
  window._theSpiderPreviewMode = 'visual';
}
function setTheSpiderVisualTextLayers(layers) {
  window._theSpiderVisualTextLayers = Array.isArray(layers) ? layers : [];
  window._theSpiderVisualFindHits = [];
  window._theSpiderVisualFindIndex = -1;
  window._theSpiderVisualFindQuery = '';
}
function hasTheSpiderVisualTextLayer() {
  return !!(window._theSpiderVisualTextLayers || []).some(function(layer){
    return layer && Array.isArray(layer.items) && layer.items.length && String(layer.text || '').trim();
  });
}
function renderTheSpiderVisualTextLayer(layer, pageIndex) {
  if (!layer || !Array.isArray(layer.items) || !layer.items.length) return '';
  var words = layer.items.map(function(item, itemIndex){
    var x = Math.max(0, Math.min(1, Number(item.x) || 0));
    var y = Math.max(0, Math.min(1, Number(item.y) || 0));
    var w = Math.max(0.0001, Math.min(1 - x, Number(item.w) || 0));
    var h = Math.max(0.0025, Math.min(1 - y, Number(item.h) || 0));
    var start = Math.max(0, Number(item.s) || 0);
    var end = Math.max(start, Number(item.e) || start);
    var token = String(item.t || '');
    return '<span class="spider-visual-text-word" data-spider-visual-page="' + pageIndex + '" data-spider-visual-item="' + itemIndex + '" data-spider-start="' + start + '" data-spider-end="' + end + '" style="left:' + (x*100).toFixed(5) + '%;top:' + (y*100).toFixed(5) + '%;width:' + (w*100).toFixed(5) + '%;height:' + Math.max(h*100,0.35).toFixed(5) + '%;">' + esc(token + ' ') + '</span>';
  }).join('');
  return '<div class="spider-visual-text-layer" data-spider-visual-layer="' + pageIndex + '" aria-label="Selectable CV text layer">' + words + '</div>';
}
function clearTheSpiderVisualHighlightClasses(kind) {
  var selector = '.spider-visual-text-word';
  document.querySelectorAll(selector).forEach(function(word){
    if (!kind || kind === 'boolean') word.classList.remove('boolean-positive','boolean-negative','boolean-mixed');
    if (!kind || kind === 'manual') word.classList.remove('manual-match','active');
    if (!kind) {
      word.removeAttribute('data-spider-visual-match');
      word.removeAttribute('data-spider-visual-term');
    }
  });
}
function theSpiderVisualLayerWords(pageIndex) {
  return Array.prototype.slice.call(document.querySelectorAll('.spider-visual-text-word[data-spider-visual-page="' + pageIndex + '"]'));
}
function applyTheSpiderVisualHitClass(pageIndex, hit, className, matchId, term) {
  var words = theSpiderVisualLayerWords(pageIndex);
  var first = null;
  words.forEach(function(word){
    var start = Number(word.getAttribute('data-spider-start')) || 0;
    var end = Number(word.getAttribute('data-spider-end')) || start;
    if (end <= hit.start || start >= hit.end) return;
    word.classList.add(className);
    word.setAttribute('data-spider-visual-match', String(matchId));
    if (term) word.setAttribute('data-spider-visual-term', term);
    if (!first) first = word;
  });
  return first;
}
function collectTheSpiderVisualBooleanMatches(terms) {
  var matches = [], matchedTerms = {};
  (window._theSpiderVisualTextLayers || []).forEach(function(layer, pageIndex){
    if (!layer || !String(layer.text || '').trim()) return;
    var pageResult = collectTheSpiderBooleanHighlightMatches(String(layer.text || ''), terms || []);
    pageResult.matches.forEach(function(hit){
      matches.push({pageIndex:pageIndex,start:hit.start,end:hit.end,termIndex:hit.termIndex,term:hit.term,kind:hit.kind});
      matchedTerms[hit.termIndex] = true;
    });
  });
  return {matches:matches.slice(0,2000),matchedTerms:matchedTerms};
}
function applyTheSpiderVisualBooleanHighlights(terms) {
  clearTheSpiderVisualHighlightClasses('boolean');
  if (!hasTheSpiderVisualTextLayer() || !terms || !terms.length) return {matches:[],matchedTerms:{}};
  var result = collectTheSpiderVisualBooleanMatches(terms);
  var byPage = {};
  result.matches.forEach(function(hit, idx){
    hit._matchId = 'b' + idx;
    (byPage[hit.pageIndex] = byPage[hit.pageIndex] || []).push(hit);
  });
  Object.keys(byPage).forEach(function(pageKey){
    var pageHits = byPage[pageKey].sort(function(a,b){ return a.start-b.start; });
    var words = theSpiderVisualLayerWords(pageKey).sort(function(a,b){ return (Number(a.getAttribute('data-spider-start'))||0) - (Number(b.getAttribute('data-spider-start'))||0); });
    var wordCursor = 0;
    pageHits.forEach(function(hit){
      while (wordCursor < words.length && (Number(words[wordCursor].getAttribute('data-spider-end'))||0) <= hit.start) wordCursor++;
      var j = wordCursor;
      var cls = hit.kind === 'negative' ? 'boolean-negative' : (hit.kind === 'mixed' ? 'boolean-mixed' : 'boolean-positive');
      while (j < words.length) {
        var word = words[j];
        var start = Number(word.getAttribute('data-spider-start')) || 0;
        var end = Number(word.getAttribute('data-spider-end')) || start;
        if (start >= hit.end) break;
        if (end > hit.start) {
          word.classList.add(cls);
          word.setAttribute('data-spider-visual-match', hit._matchId);
          word.setAttribute('data-spider-visual-term', hit.term || '');
        }
        j++;
      }
    });
  });
  return result;
}
function collectTheSpiderVisualManualHits(query) {
  query = String(query || '');
  if (!query) return [];
  var all = [];
  (window._theSpiderVisualTextLayers || []).forEach(function(layer, pageIndex){
    var text = String((layer && layer.text) || '');
    if (!text) return;
    var lowText = text.toLowerCase(), lowQuery = query.toLowerCase(), pos = 0;
    while (all.length < 500 && (pos = lowText.indexOf(lowQuery, pos)) >= 0) {
      all.push({pageIndex:pageIndex,start:pos,end:pos+query.length});
      pos += Math.max(1, query.length);
    }
  });
  return all;
}
function renderTheSpiderVisualManualHits(hits, activeIndex) {
  clearTheSpiderVisualHighlightClasses('manual');
  var activeWord = null, byPage = {};
  (hits || []).forEach(function(hit, idx){
    hit._matchIndex = idx;
    (byPage[hit.pageIndex] = byPage[hit.pageIndex] || []).push(hit);
  });
  Object.keys(byPage).forEach(function(pageKey){
    var pageHits = byPage[pageKey].sort(function(a,b){ return a.start-b.start; });
    var words = theSpiderVisualLayerWords(pageKey).sort(function(a,b){ return (Number(a.getAttribute('data-spider-start'))||0) - (Number(b.getAttribute('data-spider-start'))||0); });
    var wordCursor = 0;
    pageHits.forEach(function(hit){
      while (wordCursor < words.length && (Number(words[wordCursor].getAttribute('data-spider-end'))||0) <= hit.start) wordCursor++;
      var j = wordCursor, first = null;
      while (j < words.length) {
        var word = words[j];
        var start = Number(word.getAttribute('data-spider-start')) || 0;
        var end = Number(word.getAttribute('data-spider-end')) || start;
        if (start >= hit.end) break;
        if (end > hit.start) {
          word.classList.add('manual-match');
          word.setAttribute('data-spider-visual-match', 'm' + hit._matchIndex);
          if (!first) first = word;
        }
        j++;
      }
      if (hit._matchIndex === activeIndex && first) {
        first.classList.add('active');
        activeWord = first;
      }
    });
  });
  if (activeWord) {
    requestAnimationFrame(function(){
      try { activeWord.scrollIntoView({block:'center',inline:'nearest',behavior:'smooth'}); }
      catch(e) { try { activeWord.scrollIntoView(false); } catch(ignore) {} }
    });
  }
}
function theSpiderBooleanHighlightsEnabled() {
  if (window._theSpiderBooleanHighlightPref === null || window._theSpiderBooleanHighlightPref === undefined) {
    try {
      var stored = localStorage.getItem('cvstudio_spider_boolean_highlights_v2');
      window._theSpiderBooleanHighlightPref = stored === null ? true : stored === '1';
    } catch(e) { window._theSpiderBooleanHighlightPref = true; }
  }
  return !!window._theSpiderBooleanHighlightPref;
}
function setTheSpiderBooleanHighlightPreference(enabled) {
  window._theSpiderBooleanHighlightPref = !!enabled;
  try { localStorage.setItem('cvstudio_spider_boolean_highlights_v2', enabled ? '1' : '0'); } catch(e) {}
  updateTheSpiderBooleanHighlightButton();
}
function updateTheSpiderBooleanHighlightButton() {
  var btn = document.getElementById('theSpiderPreviewBooleanBtn');
  if (!btn) return;
  var enabled = theSpiderBooleanHighlightsEnabled();
  btn.classList.toggle('active', enabled);
  btn.setAttribute('aria-pressed', enabled ? 'true' : 'false');
  btn.textContent = enabled ? 'Boolean HL: On' : 'Boolean HL: Off';
}
function extractTheSpiderBooleanHighlightTerms(raw) {
  raw = normaliseTheSpiderBooleanRule(raw || '');
  if (!raw) return [];
  var found = [], byKey = {};
  function addTerm(value, negative) {
    value = String(value || '').trim();
    if ((/^"[\s\S]*"$/).test(value) || (/^'[\s\S]*'$/).test(value)) value = value.slice(1, -1);
    value = value.replace(/^[,;:]+|[,;:]+$/g, '').replace(/\\(["'])/g, '$1').trim();
    if (!value || /^(AND|OR|NOT)$/i.test(value)) return;
    var visibleCore = value.replace(/[?*]/g, '');
    if (visibleCore.length < 2 || value.length > 120) return;
    var key = value.toLowerCase();
    var kind = negative ? 'negative' : 'positive';
    if (byKey[key]) {
      if (byKey[key].kind !== kind) byKey[key].kind = 'mixed';
      return;
    }
    var item = { text:value, kind:kind };
    byKey[key] = item;
    found.push(item);
  }
  if (!hasTheSpiderBooleanSyntax(raw)) {
    splitTheSpiderKeywordTerms(raw).forEach(function(term){ addTerm(term, false); });
    return found.slice(0, 150);
  }
  var tokens = raw.match(/"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\(|\)|\b(?:AND|OR|NOT)\b|[^\s()]+/gi) || [];
  var negStack = [false], pendingNot = false;
  tokens.forEach(function(token){
    var upper = String(token || '').toUpperCase();
    var quoted = (/^"[\s\S]*"$/).test(token) || (/^'[\s\S]*'$/).test(token);
    if (!quoted && upper === 'NOT') { pendingNot = !pendingNot; return; }
    if (!quoted && token === '(') {
      negStack.push(!!negStack[negStack.length - 1] !== !!pendingNot);
      pendingNot = false;
      return;
    }
    if (!quoted && token === ')') {
      if (negStack.length > 1) negStack.pop();
      pendingNot = false;
      return;
    }
    if (!quoted && (upper === 'AND' || upper === 'OR')) { pendingNot = false; return; }
    var negative = !!negStack[negStack.length - 1] !== !!pendingNot;
    pendingNot = false;
    if (!quoted && /[,;]/.test(token)) String(token).split(/[,;]+/).forEach(function(part){ addTerm(part, negative); });
    else addTerm(token, negative);
  });
  return found.slice(0, 150);
}
function escapeTheSpiderRegex(value) {
  return String(value || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
function findTheSpiderBooleanTermHits(text, term) {
  text = String(text || '');
  term = String(term || '');
  if (!text || !term) return [];
  var wildcard = /[?*]/.test(term), hits = [], maxPerTerm = 300;
  var firstCore = term.replace(/^[?*]+/, '').charAt(0);
  var lastCoreText = term.replace(/[?*]+$/, '');
  var lastCore = lastCoreText.charAt(lastCoreText.length - 1);
  var requireLeft = /[A-Za-z0-9]/.test(firstCore);
  var requireRight = /[A-Za-z0-9]/.test(lastCore) || /[?*]$/.test(term);
  function boundaryOk(start, end) {
    var before = start > 0 ? text.charAt(start - 1) : '';
    var after = end < text.length ? text.charAt(end) : '';
    if (requireLeft && /[A-Za-z0-9]/.test(before)) return false;
    if (requireRight && /[A-Za-z0-9]/.test(after)) return false;
    return true;
  }
  if (!wildcard) {
    var lowText = text.toLowerCase(), lowTerm = term.toLowerCase(), pos = 0;
    while (hits.length < maxPerTerm && (pos = lowText.indexOf(lowTerm, pos)) >= 0) {
      var end = pos + term.length;
      if (boundaryOk(pos, end)) hits.push({start:pos, end:end});
      pos += Math.max(1, term.length);
    }
    return hits;
  }
  var pattern = escapeTheSpiderRegex(term).replace(/\\\*/g, '[A-Za-z0-9_+.#/-]*').replace(/\\\?/g, '[A-Za-z0-9_+.#/-]');
  var rx;
  try { rx = new RegExp(pattern, 'gi'); } catch(e) { return []; }
  var match;
  while (hits.length < maxPerTerm && (match = rx.exec(text))) {
    var start = match.index, end = start + String(match[0] || '').length;
    if (end > start && boundaryOk(start, end)) hits.push({start:start, end:end});
    if (!match[0]) rx.lastIndex += 1;
  }
  return hits;
}
function collectTheSpiderBooleanHighlightMatches(text, terms) {
  var all = [], matchedTerms = {};
  (terms || []).forEach(function(term, termIndex){
    findTheSpiderBooleanTermHits(text, term.text).forEach(function(hit){
      all.push({start:hit.start, end:hit.end, termIndex:termIndex, term:term.text, kind:term.kind});
      matchedTerms[termIndex] = true;
    });
  });
  all.sort(function(a,b){
    if (a.start !== b.start) return a.start - b.start;
    var lenA = a.end - a.start, lenB = b.end - b.start;
    if (lenA !== lenB) return lenB - lenA;
    var rank = {mixed:0, negative:1, positive:2};
    return (rank[a.kind] || 3) - (rank[b.kind] || 3);
  });
  var selected = [], cursor = -1;
  all.forEach(function(hit){
    if (selected.length >= 1500) return;
    if (hit.start < cursor) return;
    selected.push(hit);
    cursor = hit.end;
  });
  return {matches:selected, matchedTerms:matchedTerms, rawMatches:all.length};
}
function renderTheSpiderBooleanHighlights(terms, matches) {
  var doc = document.getElementById('theSpiderPreviewSearchDoc');
  if (!doc) return;
  var text = String(window._theSpiderPreviewSearchText || '');
  if (!text) { doc.innerHTML = '<div class="spider-cv-preview-empty">No searchable text was extracted from this CV.</div>'; return; }
  if (!matches || !matches.length) { doc.innerHTML = esc(text); return; }
  var html = [], cursor = 0;
  matches.forEach(function(hit){
    if (!hit || hit.start < cursor || hit.end <= hit.start || hit.end > text.length) return;
    html.push(esc(text.slice(cursor, hit.start)));
    var cls = hit.kind === 'negative' ? 'boolean-negative' : (hit.kind === 'mixed' ? 'boolean-mixed' : 'boolean-positive');
    var label = hit.kind === 'negative' ? 'Excluded Boolean term' : (hit.kind === 'mixed' ? 'Boolean term appears in included and excluded scopes' : 'Included Boolean term');
    html.push('<mark class="' + cls + '" data-spider-boolean-term="' + escAttr(hit.term) + '" title="' + escAttr(label + ': ' + hit.term) + '">' + esc(text.slice(hit.start, hit.end)) + '</mark>');
    cursor = hit.end;
  });
  html.push(esc(text.slice(cursor)));
  doc.innerHTML = html.join('');
}
function renderTheSpiderPlainSearchText() {
  renderTheSpiderSearchablePreview('', [], -1);
}
function applyTheSpiderBooleanHighlights(forceText) {
  updateTheSpiderBooleanHighlightButton();
  if (!theSpiderBooleanHighlightsEnabled()) return false;
  var input = document.getElementById('theSpiderPreviewFindInput');
  if (input && String(input.value || '').trim()) return false;
  var text = String(window._theSpiderPreviewSearchText || '');
  var terms = extractTheSpiderBooleanHighlightTerms((document.getElementById('theSpiderMust') || {}).value || '');
  var result = collectTheSpiderBooleanHighlightMatches(text, terms);
  var visualResult = applyTheSpiderVisualBooleanHighlights(terms);
  window._theSpiderBooleanHighlightTerms = terms;
  window._theSpiderBooleanHighlightMatches = result.matches;
  var count = document.getElementById('theSpiderPreviewFindCount');
  var box = document.getElementById('theSpiderPreviewFindResults');
  var matchedKeys = {};
  Object.keys(result.matchedTerms || {}).forEach(function(k){ matchedKeys[k] = true; });
  Object.keys((visualResult && visualResult.matchedTerms) || {}).forEach(function(k){ matchedKeys[k] = true; });
  var matchedCount = Object.keys(matchedKeys).length;
  var visibleMatchCount = hasTheSpiderVisualTextLayer() ? ((visualResult && visualResult.matches.length) || 0) : result.matches.length;
  if (count) count.textContent = visibleMatchCount ? (visibleMatchCount + ' hits') : '0 hits';
  if (box) {
    box.style.display = 'block';
    if (!terms.length) box.innerHTML = '<div class="spider-find-hint">Add terms in Boolean Rules / Keywords to use automatic highlighting.</div>';
    else box.innerHTML = '<div class="spider-find-hint"><strong>Boolean highlights:</strong> ' + matchedCount + '/' + terms.length + ' terms found · ' + visibleMatchCount + ' visible matches.'
      + (hasTheSpiderVisualTextLayer() ? ' Highlighted directly on the visual CV.' : ' This file has no coordinate text layer; highlights are available in Select text.')
      + '<span class="spider-boolean-legend"><span><i class="spider-boolean-swatch positive"></i>included</span>'
      + (terms.some(function(t){ return t.kind === 'negative' || t.kind === 'mixed'; }) ? '<span><i class="spider-boolean-swatch negative"></i>NOT / excluded</span>' : '')
      + '</span></div>';
  }
  renderTheSpiderBooleanHighlights(terms, result.matches);
  if (forceText === true && !hasTheSpiderVisualTextLayer()) setTheSpiderPreviewMode('text', true);
  return true;
}
function refreshTheSpiderBooleanHighlights() {
  updateTheSpiderBooleanHighlightButton();
  if (!theSpiderBooleanHighlightsEnabled()) return;
  var input = document.getElementById('theSpiderPreviewFindInput');
  if (input && String(input.value || '').trim()) return;
  if (document.getElementById('theSpiderPreviewSearchDoc')) applyTheSpiderBooleanHighlights(false);
}
function toggleTheSpiderBooleanHighlights() {
  var next = !theSpiderBooleanHighlightsEnabled();
  if (next) {
    var terms = extractTheSpiderBooleanHighlightTerms((document.getElementById('theSpiderMust') || {}).value || '');
    if (!terms.length) { showToast('Add Boolean Rules / Keywords first', 'err'); return; }
  }
  setTheSpiderBooleanHighlightPreference(next);
  if (next) {
    applyTheSpiderBooleanHighlights(false);
    setTheSpiderPreviewMode('visual', true);
    showToast('Boolean keyword highlights on', 'ok');
    return;
  }
  window._theSpiderBooleanHighlightTerms = [];
  window._theSpiderBooleanHighlightMatches = [];
  clearTheSpiderVisualHighlightClasses('boolean');
  var input = document.getElementById('theSpiderPreviewFindInput');
  if (input && String(input.value || '').trim()) runTheSpiderPreviewFind(0);
  else {
    var count = document.getElementById('theSpiderPreviewFindCount');
    var box = document.getElementById('theSpiderPreviewFindResults');
    if (count) count.textContent = '0/0';
    if (box) { box.style.display = 'none'; box.innerHTML = ''; }
    renderTheSpiderPlainSearchText();
  }
  showToast('Boolean keyword highlights off', 'ok');
}
function initializeTheSpiderPreviewFinder() {
  updateTheSpiderBooleanHighlightButton();
  if (theSpiderBooleanHighlightsEnabled() && extractTheSpiderBooleanHighlightTerms((document.getElementById('theSpiderMust') || {}).value || '').length) {
    applyTheSpiderBooleanHighlights(false);
    setTheSpiderPreviewMode('visual', true);
  } else {
    renderTheSpiderPlainSearchText();
    setTheSpiderPreviewMode('visual', true);
  }
}
function renderTheSpiderCurrentTextState() {
  var input = document.getElementById('theSpiderPreviewFindInput');
  var query = String((input && input.value) || '').trim();
  if (query) {
    renderTheSpiderSearchablePreview(query, window._theSpiderPreviewFindHits || [], Number(window._theSpiderPreviewFindIndex));
    return;
  }
  if (theSpiderBooleanHighlightsEnabled() && applyTheSpiderBooleanHighlights(false)) return;
  renderTheSpiderPlainSearchText();
}
function setTheSpiderPreviewMode(mode, skipRender) {
  mode = mode === 'text' ? 'text' : 'visual';
  var visual = document.getElementById('theSpiderPreviewVisualPane');
  var textPane = document.getElementById('theSpiderPreviewTextPane');
  var visualBtn = document.getElementById('theSpiderPreviewVisualBtn');
  var textBtn = document.getElementById('theSpiderPreviewTextBtn');
  if (mode === 'text' && !window._theSpiderPreviewSearchText) mode = 'visual';
  window._theSpiderPreviewMode = mode;
  if (visual) visual.classList.toggle('hidden', mode === 'text');
  if (textPane) textPane.classList.toggle('active', mode === 'text');
  if (visualBtn) visualBtn.classList.toggle('active', mode === 'visual');
  if (textBtn) textBtn.classList.toggle('active', mode === 'text');
  if (mode === 'text' && !skipRender) renderTheSpiderCurrentTextState();
}
function openTheSpiderPreviewFind() {
  var input = document.getElementById('theSpiderPreviewFindInput');
  if (!input) return false;
  if (!window._theSpiderPreviewSearchText && !hasTheSpiderVisualTextLayer()) {
    showToast('This CV preview has no searchable text', 'err');
    return false;
  }
  input.focus();
  input.select();
  if (String(input.value || '').trim()) runTheSpiderPreviewFind(0);
  return true;
}
function closeTheSpiderPreviewFind() {
  var input = document.getElementById('theSpiderPreviewFindInput');
  var count = document.getElementById('theSpiderPreviewFindCount');
  var box = document.getElementById('theSpiderPreviewFindResults');
  if (input) input.value = '';
  window._theSpiderPreviewFindHits=[];
  window._theSpiderPreviewFindIndex=-1;
  window._theSpiderPreviewFindQuery='';
  window._theSpiderVisualFindHits=[];
  window._theSpiderVisualFindIndex=-1;
  window._theSpiderVisualFindQuery='';
  clearTheSpiderVisualHighlightClasses('manual');
  if (theSpiderBooleanHighlightsEnabled() && applyTheSpiderBooleanHighlights(false)) { setTheSpiderPreviewMode('visual', true); return; }
  if (count) count.textContent = '0/0';
  if (box) { box.style.display='none'; box.innerHTML=''; }
  renderTheSpiderPlainSearchText();
  setTheSpiderPreviewMode('visual', true);
}
function handleTheSpiderPreviewFindKey(event) {
  if (!event) return;
  if (event.key === 'Enter') { event.preventDefault(); runTheSpiderPreviewFind(event.shiftKey ? -1 : 1); }
  else if (event.key === 'Escape') { event.preventDefault(); closeTheSpiderPreviewFind(); }
}
function renderTheSpiderSearchablePreview(query, hits, activeIndex) {
  var doc = document.getElementById('theSpiderPreviewSearchDoc');
  if (!doc) return;
  var text = String(window._theSpiderPreviewSearchText || '');
  query = String(query || '');
  hits = Array.isArray(hits) ? hits : [];
  if (!text) {
    doc.innerHTML = '<div class="spider-cv-preview-empty">No searchable text was extracted from this CV.</div>';
    return;
  }
  if (!query || !hits.length) {
    doc.innerHTML = esc(text);
    return;
  }
  var html = [];
  var cursor = 0;
  hits.forEach(function(hit, idx){
    hit = Number(hit);
    if (!isFinite(hit) || hit < cursor || hit > text.length) return;
    html.push(esc(text.slice(cursor, hit)));
    html.push('<mark data-spider-find-hit="' + idx + '"' + (idx === activeIndex ? ' class="active"' : '') + '>' + esc(text.slice(hit, hit + query.length)) + '</mark>');
    cursor = hit + query.length;
  });
  html.push(esc(text.slice(cursor)));
  doc.innerHTML = html.join('');
  var active = doc.querySelector('mark.active');
  if (active) {
    requestAnimationFrame(function(){
      try { active.scrollIntoView({block:'center', inline:'nearest', behavior:'smooth'}); }
      catch(e) { try { active.scrollIntoView(false); } catch(ignore) {} }
    });
  }
}
function runTheSpiderPreviewFind(step) {
  var input = document.getElementById('theSpiderPreviewFindInput');
  var count = document.getElementById('theSpiderPreviewFindCount');
  var box = document.getElementById('theSpiderPreviewFindResults');
  var query = String((input && input.value) || '').trim();
  var text = String(window._theSpiderPreviewSearchText || '');
  if (!query || !text) {
    window._theSpiderPreviewFindHits=[];
    window._theSpiderPreviewFindIndex=-1;
    window._theSpiderPreviewFindQuery='';
    window._theSpiderVisualFindHits=[];
    window._theSpiderVisualFindIndex=-1;
    window._theSpiderVisualFindQuery='';
    clearTheSpiderVisualHighlightClasses('manual');
    if (!query && theSpiderBooleanHighlightsEnabled() && applyTheSpiderBooleanHighlights(false)) {
      setTheSpiderPreviewMode('visual', true);
      return;
    }
    clearTheSpiderVisualHighlightClasses('boolean');
    if (count) count.textContent='0/0';
    if (box) { box.style.display='none'; box.innerHTML=''; }
    renderTheSpiderPlainSearchText();
    if (!query) setTheSpiderPreviewMode('visual', true);
    return;
  }

  var lowText=text.toLowerCase(), lowQuery=query.toLowerCase(), hits=[], pos=0;
  while (hits.length < 250 && (pos=lowText.indexOf(lowQuery,pos)) >= 0) { hits.push(pos); pos += Math.max(1,lowQuery.length); }
  var previousQuery=String(window._theSpiderPreviewFindQuery || '');
  if (previousQuery !== lowQuery) window._theSpiderPreviewFindIndex = hits.length ? 0 : -1;
  else if (hits.length && step) window._theSpiderPreviewFindIndex = (Number(window._theSpiderPreviewFindIndex)||0) + step;
  if (hits.length) {
    while (window._theSpiderPreviewFindIndex < 0) window._theSpiderPreviewFindIndex += hits.length;
    window._theSpiderPreviewFindIndex = window._theSpiderPreviewFindIndex % hits.length;
  } else window._theSpiderPreviewFindIndex=-1;
  window._theSpiderPreviewFindQuery=lowQuery;
  window._theSpiderPreviewFindHits=hits;

  var visualHits = hasTheSpiderVisualTextLayer() ? collectTheSpiderVisualManualHits(query) : [];
  var previousVisualQuery = String(window._theSpiderVisualFindQuery || '');
  if (previousVisualQuery !== lowQuery) window._theSpiderVisualFindIndex = visualHits.length ? 0 : -1;
  else if (visualHits.length && step) window._theSpiderVisualFindIndex = (Number(window._theSpiderVisualFindIndex)||0) + step;
  if (visualHits.length) {
    while (window._theSpiderVisualFindIndex < 0) window._theSpiderVisualFindIndex += visualHits.length;
    window._theSpiderVisualFindIndex = window._theSpiderVisualFindIndex % visualHits.length;
  } else window._theSpiderVisualFindIndex = -1;
  window._theSpiderVisualFindQuery = lowQuery;
  window._theSpiderVisualFindHits = visualHits;

  clearTheSpiderVisualHighlightClasses('boolean');
  renderTheSpiderVisualManualHits(visualHits, window._theSpiderVisualFindIndex);
  renderTheSpiderSearchablePreview(query, hits, window._theSpiderPreviewFindIndex);

  var usingVisual = hasTheSpiderVisualTextLayer();
  var shownHits = usingVisual ? visualHits : hits;
  var shownIndex = usingVisual ? window._theSpiderVisualFindIndex : window._theSpiderPreviewFindIndex;
  if (count) count.textContent = shownHits.length ? ((shownIndex+1) + '/' + shownHits.length) : '0/0';
  if (box) {
    box.style.display='block';
    box.innerHTML = shownHits.length
      ? '<div class="spider-find-hint">Highlighted match ' + (shownIndex+1) + ' of ' + shownHits.length + (usingVisual ? ' directly on the visual CV.' : ' in Select text.') + ' Enter: next · Shift+Enter: previous.</div>'
      : '<div class="spider-find-hint">No match in the loaded CV/profile text.</div>';
  }
  if (!usingVisual) setTheSpiderPreviewMode('text', true);
}
function renderTheSpiderCandidatePreviewPane(d, localCandidate) {
  d = d || {};
  localCandidate = localCandidate || {};
  var id = d.candidate_id || getTheSpiderCandidateId(localCandidate);
  var name = d.name || localCandidate.name || [localCandidate.firstName,localCandidate.lastName].filter(Boolean).join(' ') || localCandidate.fullName || 'Candidate';
  var subtitle = d.source || d.mode || (d.ok ? 'JobAdder preview' : 'Local result preview');
  var txt = d.preview_text || localTheSpiderCandidatePreview(localCandidate);
  var hasExplicitSearchText = Object.prototype.hasOwnProperty.call(d, 'search_text');
  var searchText = hasExplicitSearchText ? String(d.search_text || '') : (d.preview_text || txt);
  setTheSpiderPreviewSearchText(searchText);
  setTheSpiderVisualTextLayers(d.visual_text_layers || []);
  var note = d.note || '';
  if (d.search_note) note = [note, d.search_note].filter(Boolean).join(' · ');
  var link = id ? jaProfileUrl(id) : '';
  var previewOnly = d.download_disabled ? '<span class="spider-preview-only-pill" title="The built-in file download control is removed from this preview. Screen capture cannot be technically prevented.">Preview only</span>' : '';
  var right = '<div style="display:flex;align-items:center;justify-content:flex-end;gap:7px;flex-wrap:wrap;">' + spiderPreviewFindControls() + spiderPreviewCacheStatusHtml() + previewOnly + (link ? '<a class="sec" href="' + escAttr(link) + '" target="_blank" rel="noopener" onclick="event.stopPropagation()" style="font-size:11px;text-decoration:none;white-space:nowrap;">Open Profile</a>' : '') + '</div>';
  var head = '<div class="spider-cv-preview-head"><div><div class="spider-cv-preview-title">' + esc(name) + '</div><div class="spider-cv-preview-sub">' + esc(subtitle) + (note ? ' · ' + esc(note) : '') + '</div></div>' + right + '</div><div class="spider-preview-find-results" id="theSpiderPreviewFindResults" style="display:none;"></div>';
  var visualBody = '';
  if (Array.isArray(d.page_images) && d.page_images.length) {
    visualBody = '<div class="spider-cv-preview-pages" aria-label="Candidate CV preview pages">' + d.page_images.map(function(src, pageIndex){
      var layer = (d.visual_text_layers || [])[pageIndex] || null;
      var textLayer = renderTheSpiderVisualTextLayer(layer, pageIndex);
      return '<div class="spider-cv-preview-page-wrap" data-spider-preview-page="' + pageIndex + '"><img class="spider-cv-preview-page" draggable="false" oncontextmenu="return false" ondragstart="return false" src="' + escAttr(src) + '" alt="Candidate CV preview page ' + (pageIndex + 1) + '">' + textLayer + '</div>';
    }).join('') + '</div>';
  } else if (d.data_url && (d.visual_mode === 'image' || d.mode === 'image' || /^data:image\//i.test(String(d.data_url)))) {
    visualBody = '<div class="spider-cv-preview-body"><img class="spider-cv-preview-image" draggable="false" oncontextmenu="return false" ondragstart="return false" src="' + escAttr(d.data_url) + '" alt="Candidate CV preview"></div>';
  } else if (d.html) {
    visualBody = '<div class="spider-cv-preview-body"><div class="spider-cv-doc-html">' + d.html + '</div></div>';
  } else {
    visualBody = '<div class="spider-cv-preview-body"><pre>' + esc(txt) + '</pre></div>';
  }
  var textPane = '<div class="spider-preview-text-pane" id="theSpiderPreviewTextPane"><div class="spider-preview-search-paper"><pre class="spider-cv-search-render" id="theSpiderPreviewSearchDoc" tabindex="0" aria-label="Selectable candidate CV text">' + esc(searchText || txt || '') + '</pre></div></div>';
  setTimeout(initializeTheSpiderPreviewFinder, 0);
  return head + '<div class="spider-preview-visual-pane" id="theSpiderPreviewVisualPane">' + visualBody + '</div>' + textPane;
}

async function openTheSpiderCandidatePreview(candidateId, idx, options) {
  options = options || {};
  if (!requireAiCrawlerUnlocked()) return;
  ensureTheSpiderPreviewCaches();
  var key = theSpiderPreviewCacheKey(candidateId);
  var requestSeq = (Number(window._theSpiderPreviewRequestSeq) || 0) + 1;
  window._theSpiderPreviewRequestSeq = requestSeq;
  window._theSpiderPreviewRequestedCandidateId = String(candidateId || '');
  setTheSpiderCandidateSelected(idx);
  var pane = document.getElementById('theSpiderCvPreview');
  var local = (window._theSpiderLastResults || [])[Number(idx)] || {};
  if (!pane) return;

  var promotedPrefetch = pauseTheSpiderPreviewPrefetchForForeground(key);
  if (window._theSpiderPreviewAbortController) { try { window._theSpiderPreviewAbortController.abort(); } catch(e) {} }
  window._theSpiderPreviewAbortController = null;

  if (!options.forceNetwork) {
    var domEntry = key && window._theSpiderPreviewDomCache && window._theSpiderPreviewDomCache.get(key);
    if (domEntry) {
      activateTheSpiderPreviewDomEntry(domEntry);
      scheduleTheSpiderPreviewRevalidation(domEntry, idx);
      if (domEntry.payload && domEntry.payload.preview_partial) upgradeTheSpiderPartialPreview(candidateId, idx, requestSeq);
      else resumeTheSpiderPreviewPrefetch(idx);
      return;
    }
    var payloadEntry = touchTheSpiderPreviewPayloadCache(key);
    if (payloadEntry) {
      var built = buildTheSpiderPreviewDomEntry(candidateId, payloadEntry.payload, local);
      built.validatedAt = payloadEntry.validatedAt || Date.now();
      built.attachmentFingerprint = payloadEntry.attachmentFingerprint || built.attachmentFingerprint;
      activateTheSpiderPreviewDomEntry(built);
      scheduleTheSpiderPreviewRevalidation(payloadEntry, idx);
      if (payloadEntry.payload && payloadEntry.payload.preview_partial) upgradeTheSpiderPartialPreview(candidateId, idx, requestSeq);
      else resumeTheSpiderPreviewPrefetch(idx);
      return;
    }
  }
  if (!candidateId) {
    pane.innerHTML = renderTheSpiderCandidatePreviewPane({source:'Local JobAdder search result only', note:'No candidate id returned', preview_text:localTheSpiderCandidatePreview(local)}, local);
    initializeTheSpiderPreviewFinder();
    resumeTheSpiderPreviewPrefetch(idx);
    return;
  }

  pane.innerHTML = '<div class="spider-cv-preview-head"><div><div class="spider-cv-preview-title">Loading candidate CV…</div><div class="spider-cv-preview-sub">Foreground preview has priority; background preloading is paused.</div></div>' + spiderPreviewCacheStatusHtml() + '</div><div class="spider-cv-preview-empty"><span class="spinner"></span> Loading JobAdder resume/profile…</div>';
  updateTheSpiderPreviewCacheStatus();
  var controller = new AbortController();
  window._theSpiderPreviewAbortController = controller;
  try {
    var d;
    if (promotedPrefetch && !options.forceNetwork) d = await promotedPrefetch;
    else d = await fetchTheSpiderPreviewPayload(candidateId, controller, 45000, {allowUnverified: !!options.allowUnverified});
    if (window._theSpiderPreviewRequestSeq !== requestSeq || window._theSpiderPreviewRequestedCandidateId !== String(candidateId || '')) return;
    putTheSpiderPreviewPayloadCache(candidateId, d, local);
    preloadTheSpiderPreviewImages(d, d.preview_partial ? 2 : 12);
    activateTheSpiderPreviewDomEntry(buildTheSpiderPreviewDomEntry(candidateId, d, local));
    if (d.preview_partial) upgradeTheSpiderPartialPreview(candidateId, idx, requestSeq);
  } catch(e) {
    if (window._theSpiderPreviewRequestSeq !== requestSeq || window._theSpiderPreviewRequestedCandidateId !== String(candidateId || '')) return;
    if (e && e.name === 'AbortError') {
      if (window._theSpiderPreviewAbortController !== controller && !promotedPrefetch) return;
      e = new Error('Preview timed out after 45 seconds');
    }
    pane = document.getElementById('theSpiderCvPreview');
    if (!pane) return;
    pane.innerHTML = renderTheSpiderCandidatePreviewPane({source:'Preview unavailable', note:e.message || 'JobAdder preview failed', preview_text:localTheSpiderCandidatePreview(local)}, local);
    initializeTheSpiderPreviewFinder();
    // Verified Antiword could not decode this legacy .doc. Offer an explicit,
    // one-click native recovery (unverified) instead of forcing a manual convert.
    if (e && Number(e.status) === 424 && (e.action === 'convert_to_docx_or_pdf' || e.action === 'run_installer' || e.code === 'LEGACY_DOC_EXTRACTION_FAILED' || e.code === 'ANTIWORD_DEPENDENCY_UNAVAILABLE') && !options.allowUnverified) {
      try {
        var recoverBar = document.createElement('div');
        recoverBar.style.cssText = 'padding:10px 12px;border-top:1px solid #e2e8f0;';
        var recoverBtn = document.createElement('button');
        recoverBtn.className = 'btn';
        recoverBtn.type = 'button';
        recoverBtn.textContent = '↻ Recover text (unverified)';
        recoverBtn.title = 'Extract this legacy .doc with the built-in parser. The text is not Antiword-verified — review before use.';
        recoverBtn.onclick = function(){ openTheSpiderCandidatePreview(candidateId, idx, {forceNetwork:true, allowUnverified:true}); };
        var recoverNote = document.createElement('div');
        recoverNote.style.cssText = 'font-size:12px;color:#64748b;margin-top:6px;';
        recoverNote.textContent = 'Antiword could not decode this .doc (often a Unicode-body Word file). Recover the text with the built-in parser — not verified, so review before use.';
        recoverBar.appendChild(recoverBtn);
        recoverBar.appendChild(recoverNote);
        (pane.querySelector('.spider-cv-preview-empty') || pane).appendChild(recoverBar);
      } catch(_recoverErr) {}
    }
    showToast('AI Crawler preview unavailable: ' + (e.message || 'Unknown error'), 'err');
  } finally {
    if (window._theSpiderPreviewAbortController === controller) window._theSpiderPreviewAbortController = null;
    var finalEntry = window._theSpiderPreviewPayloadCache.get(key);
    if (window._theSpiderPreviewRequestSeq === requestSeq && window._theSpiderPreviewRequestedCandidateId === String(candidateId || '') && !(finalEntry && finalEntry.payload && finalEntry.payload.preview_partial)) resumeTheSpiderPreviewPrefetch(idx);
  }
}

function spiderCandidateFieldValue(obj, patterns, kind) {
  // v24.6.80: robust JobAdder field display for salary + notice-period shapes.
  // JobAdder tenants often return these as nested objects/custom fields rather
  // than flat `currentSalary` / `noticePeriod` strings.
  patterns = (patterns || []).map(function(x){ return String(x || '').toLowerCase(); });
  kind = String(kind || '').toLowerCase();
  var found = [];
  function cleanNum(v) {
    var n = Number(String(v || '').replace(/[^0-9.\-]/g,''));
    if (!isFinite(n) || !n) return '';
    return Math.round(n).toLocaleString();
  }
  function pluralUnit(unit, n) {
    unit = String(unit || '').trim();
    if (!unit) return '';
    var base = unit.replace(/s$/i,'');
    if (/^mth$/i.test(base)) base = 'Month';
    if (/^wk$/i.test(base)) base = 'Week';
    if (/^dy$/i.test(base)) base = 'Day';
    var one = String(n || '').trim() === '1';
    if (/^(month|week|day|year)$/i.test(base)) return base.charAt(0).toUpperCase() + base.slice(1).toLowerCase() + (one ? '' : 's');
    return unit;
  }
  function salaryText(v) {
    if (!v || typeof v !== 'object') return '';
    var currency = v.currency || v.currencyCode || v.currency_code || v.currencyType || v.isoCurrency || '';
    if (currency && typeof currency === 'object') currency = currency.code || currency.value || currency.name || currency.label || '';
    var rate = v.ratePer || v.rateper || v.frequency || v.period || v.periodType || v.salaryPeriod || v.per || '';
    if (rate && typeof rate === 'object') rate = rate.value || rate.name || rate.label || rate.text || '';
    var low = v.low || v.min || v.minimum || v.from || v.start || v.lower || v.amountFrom || v.salaryFrom || v.baseFrom;
    var high = v.high || v.max || v.maximum || v.to || v.end || v.upper || v.amountTo || v.salaryTo || v.baseTo;
    var amount = v.amount || v.value || v.base || v.salary || v.rate || v.package || v.total || v.current || v.expected || v.remuneration;
    if (!low && !high && typeof amount === 'string' && /[A-Za-z$€£¥]|RM|MYR|SGD|USD|IDR/i.test(amount)) {
      var rawSalary = amount.replace(/\s+/g,' ').trim();
      if (rawSalary) return rawSalary;
    }
    var nums = [];
    if (low || high) {
      if (low) nums.push(cleanNum(low));
      if (high) nums.push(cleanNum(high));
    } else if (amount && typeof amount !== 'object') {
      nums.push(cleanNum(amount));
    }
    nums = nums.filter(Boolean);
    if (!nums.length) return '';
    var text = (currency ? String(currency).toUpperCase() + ' ' : '') + nums.join(' to ');
    if (rate) text += ' / ' + pluralUnit(rate, 1);
    return text.trim();
  }
  function noticeText(v) {
    if (v === true || String(v).toLowerCase() === 'true') return 'Immediate';
    if (v === false || String(v).toLowerCase() === 'false') return '';
    if (typeof v === 'number') return v <= 0 ? 'Immediate' : (v + ' Months');
    if (typeof v === 'string') {
      var t = v.replace(/\s+/g,' ').trim();
      if (!t) return '';
      if (/^(true|yes|y|immediate|immediately|available now|asap|start asap)$/i.test(t)) return 'Immediate';
      if (/^(false|no|n|null|none|n\/a)$/i.test(t)) return '';
      return t;
    }
    if (v && typeof v === 'object') {
      var immediateKeys = ['immediate','immediately','availableImmediately','availableNow','asap','isImmediate','canStartImmediately'];
      for (var i=0;i<immediateKeys.length;i++) {
        if (v[immediateKeys[i]] === true || String(v[immediateKeys[i]]).toLowerCase() === 'true') return 'Immediate';
      }
      var period = v.period || v.duration || v.length || v.number || v.amount || v.months || v.days || v.weeks || v.value;
      var unit = v.unit || v.periodUnit || v.durationUnit || v.type || v.frequency;
      if ((period === 0 || period === '0') && !unit) return 'Immediate';
      if (period && unit) {
        var n = String(period).trim();
        if (n === '0') return 'Immediate';
        return n + ' ' + pluralUnit(unit, n);
      }
    }
    return '';
  }
  function valueText(v, localKind) {
    localKind = localKind || kind;
    if (localKind === 'notice') {
      var nt = noticeText(v);
      if (nt) return nt;
    }
    if (v === null || typeof v === 'undefined' || v === '' || v === false) return '';
    if (localKind.indexOf('salary') >= 0 && v && typeof v === 'object') {
      var st = salaryText(v);
      if (st) return st;
    }
    if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') {
      if (localKind.indexOf('salary') >= 0 && v === true) return '';
      return String(v);
    }
    if (Array.isArray(v)) return v.map(function(x){ return valueText(x, localKind); }).filter(Boolean).join(', ');
    if (typeof v === 'object') {
      var period = v.period || v.duration || v.length || v.number || v.amount || v.months || v.days || v.weeks;
      var unit = v.unit || v.periodUnit || v.durationUnit || v.type;
      var rel = v.relative || v.relation || '';
      if (period && unit) {
        var n = String(period).trim();
        if (localKind === 'notice' && n === '0') return 'Immediate';
        var u = pluralUnit(unit, n);
        return (rel && !/^current|now|true$/i.test(String(rel)) ? String(rel).replace(/_/g,' ') + ' ' : '') + n + ' ' + u;
      }
      for (var i=0;i<['value','name','label','text','title','displayName','displayValue','selectedValue'].length;i++) {
        var k = ['value','name','label','text','title','displayName','displayValue','selectedValue'][i];
        if (v[k]) return valueText(v[k], localKind);
      }
      var useful = [];
      Object.keys(v).forEach(function(k){
        if (/^(id|candidateid|created|updated|links?|href|url|self)$/i.test(k)) return;
        if (localKind === 'notice' && /^(relative)$/i.test(k)) return;
        var txt = valueText(v[k], localKind);
        if (txt && txt.length < 80 && useful.indexOf(txt) < 0) useful.push(txt);
      });
      return useful.slice(0,3).join(', ');
    }
    return String(v || '');
  }
  function kindHit(keyPath, label) {
    var raw = String((keyPath || '') + ' ' + (label || '')).toLowerCase();
    var flat = raw.replace(/[\s_\-./]/g,'');
    var salaryLike = /(salary|remuneration|package|compensation|pay|income|wage|base)/i.test(raw);
    if (kind === 'current_salary') {
      if (/expected|expectation|desired|asking|target|preferred/i.test(raw)) return false;
      return salaryLike && (/current|present|last|latest|employmentcurrent|currentemployment|employmentscurrent/i.test(flat) || /employment\.?current\.?salary/i.test(flat));
    }
    if (kind === 'expected_salary') {
      return salaryLike && /expected|expectation|desired|asking|target|preferred/i.test(raw);
    }
    if (kind === 'notice') {
      return /(notice|availability|available|availablefrom|availableimmediately|immediate|commencement|startdate)/i.test(flat);
    }
    return false;
  }
  function patternHit(key, label) {
    var lk = String(key || '').toLowerCase().replace(/[\s_\-]/g,'');
    var ll = String(label || '').toLowerCase().replace(/[\s_\-]/g,'');
    return patterns.some(function(p){ p = p.replace(/[\s_\-]/g,''); return p && (lk === p || lk.indexOf(p) >= 0 || ll.indexOf(p) >= 0); });
  }
  function preferredValue(v) {
    if (v && typeof v === 'object') {
      if (kind.indexOf('salary') >= 0 || kind === 'notice') return v;
      return v.value || v.text || v.displayValue || v.selectedValue || v.amount || v.salary || v.package || v;
    }
    return v;
  }
  function walk(x, depth, path) {
    if (!x || depth > 6 || found.length) return;
    if (Array.isArray(x)) { x.slice(0,120).forEach(function(v, i){ walk(v, depth+1, path + '[' + i + ']'); }); return; }
    if (typeof x !== 'object') return;
    var ownLabel = String(x.label || x.name || x.title || x.fieldName || x.customFieldName || x.displayName || '');
    if (ownLabel && (patternHit('', ownLabel) || kindHit(path, ownLabel))) {
      var ownTxt = valueText(preferredValue(x), kind).replace(/\s+/g,' ').trim();
      if (kind === 'notice') ownTxt = noticeText(ownTxt) || ownTxt;
      if (ownTxt && ownTxt.length < 500 && !/^(true|false)$/i.test(ownTxt)) { found.push(ownTxt); return; }
    }
    Object.keys(x).forEach(function(k){
      if (found.length) return;
      var v = x[k];
      var label = '';
      if (v && typeof v === 'object') label = String(v.label || v.name || v.title || v.fieldName || v.customFieldName || v.displayName || '');
      var fullPath = path ? (path + '.' + k) : String(k);
      var direct = patternHit(k, label) || kindHit(fullPath, label);
      if (direct) {
        var txt = valueText(preferredValue(v), kind).replace(/\s+/g,' ').trim();
        if (kind === 'notice') txt = noticeText(txt) || txt;
        if (txt && txt.length < 500 && !/^(true|false)$/i.test(txt)) { found.push(txt); return; }
      }
      walk(v, depth+1, fullPath);
    });
  }
  walk(obj, 0, '');
  var out = (found[0] || '').replace(/^\[|\]$/g,'').slice(0,180);
  if (kind === 'notice') out = noticeText(out) || out;
  return out;
}
function spiderCardSnapshot(c, key) {
  c = c || {};
  var all = c._spiderCardFields && typeof c._spiderCardFields === 'object' ? c._spiderCardFields : {};
  var item = all[key];
  return item && typeof item === 'object' ? item : null;
}
function spiderCardSalaryDisplay(c, which) {
  var snap = spiderCardSnapshot(c, which === 'expected' ? 'expectedSalary' : 'currentSalary');
  if (snap && snap.display) return String(snap.display);
  return spiderCandidateFieldValue(c,
    which === 'expected'
      ? ['expectedSalary','salaryExpectation','expectedPackage','expectedMonthlySalary','desiredSalary','desiredPackage','askingSalary','salaryExpected','expectedRemuneration','targetSalary','preferredSalary','idealSalary']
      : ['currentSalary','currentSalaryPackage','currentBaseSalary','currentMonthlySalary','currentRemuneration','currentPackage','salaryCurrent','presentSalary','lastDrawnSalary','currentPay','currentCompensation'],
    which === 'expected' ? 'expected_salary' : 'current_salary'
  );
}
function spiderCardNoticeDisplay(c) {
  var snap = spiderCardSnapshot(c, 'notice');
  if (snap && snap.display) return String(snap.display);
  return spiderCandidateFieldValue(c, ['noticePeriod','notice','availability','availableFrom','availabilityDate','availableImmediately','immediate','startDate'], 'notice');
}
function renderSpiderInfoGrid(c) {
  var rows = [
    ['Country', spiderCandidateFieldValue(c, ['country','locationCountry','currentCountry','addressCountry'])],
    ['Residential', spiderCandidateFieldValue(c, ['residentialStatus','residency','residenceStatus','rightToWork','workRights','visaStatus','citizenship'])],
    ['Current Salary', spiderCardSalaryDisplay(c, 'current')],
    ['Expected Salary', spiderCardSalaryDisplay(c, 'expected')],
    ['Notice', spiderCardNoticeDisplay(c)]
  ].filter(function(r){ return r[1]; });
  if (!rows.length) return '';
  return '<div class="spider-info-grid">' + rows.map(function(r){ return '<div><span>' + esc(r[0]) + '</span>' + esc(r[1]) + '</div>'; }).join('') + '</div>';
}
function renderSpiderFitBreakdown(c) {
  var b=c&&c._spiderFitBreakdown&&typeof c._spiderFitBreakdown==='object'?c._spiderFitBreakdown:null;
  var comps=b&&Array.isArray(b.components)?b.components:[];
  if(!comps.length)return '';
  var html='<div class="spider-fit-breakdown">';
  comps.forEach(function(row){
    row=row||{};var matched=Array.isArray(row.matched)?row.matched:[],partial=Array.isArray(row.partial)?row.partial:[],missing=Array.isArray(row.missing)?row.missing:[];
    html+='<div class="spider-fit-component"><span class="label">'+esc(row.label||row.key||'Component')+'</span><span class="points">'+esc(String(row.points==null?0:row.points))+' / '+esc(String(row.max_points==null?0:row.max_points))+' pts</span>';
    var termBits=[];
    if(matched.length)termBits.push('Matched: '+matched.slice(0,4).join(', '));
    if(partial.length)termBits.push('Partial: '+partial.slice(0,4).join(', '));
    if(missing.length)termBits.push('Missing: '+missing.slice(0,4).join(', '));
    if(row.native_boolean_floor)termBits.push('Native Boolean floor raised this component from '+String(row.points_before_adjustment==null?0:row.points_before_adjustment)+' to '+String(row.points==null?0:row.points)+' points; visible term coverage was '+String(row.coverage_before_adjustment_percent==null?0:row.coverage_before_adjustment_percent)+'%');
    if(row.evidence_status==='unavailable')termBits.push('No visible evidence was available for this scored component');
    if(termBits.length)html+='<span class="terms'+(missing.length&&!matched.length&&!partial.length?' missing':'')+'">'+esc(termBits.join(' · '))+'</span>';
    html+='</div>';
  });
  if(b.discovery_floor_applied)html+='<div class="spider-fit-floor">10% discovery floor applied because JobAdder found the candidate but visible scoring evidence was limited.</div>';
  html+='</div>';
  return html;
}
function renderTheSpiderCandidates(items, emptyMessage) {
  items = Array.isArray(items) ? items : [];
  if (!items.length) return '<div style="color:var(--text3);">' + esc(emptyMessage || 'No candidates returned for this query. Try broader strings or fewer must-haves.') + '</div>';
  return '<div class="spider-result-grid">' + items.map(function(c, idx){
    var id = getTheSpiderCandidateId(c);
    var name = c.name || [c.firstName,c.lastName].filter(Boolean).join(' ') || c.fullName || 'Candidate';
    var title = c.currentPosition || c.position || c.jobTitle || (c.employment && c.employment.current && c.employment.current.position) || '';
    var company = c.currentCompany || c.employer || (c.employment && c.employment.current && c.employment.current.employer) || '';
    var loc = c.location || c.city || c.country || (c.address && [c.address.city,c.address.state,c.address.country].filter(Boolean).join(', ')) || '';
    var link = id ? jaProfileUrl(id) : '';
    var matchedList = Array.isArray(c._spiderMatchedFilters) ? c._spiderMatchedFilters : [];
    var discoveryList = Array.isArray(c._spiderDiscoveryEvidence) ? c._spiderDiscoveryEvidence : [];
    var unknownList = Array.isArray(c._spiderUnknownFilters) ? c._spiderUnknownFilters : [];
    var fitPct = Math.max(0, Math.min(100, parseInt(c._spiderFitPercent != null ? c._spiderFitPercent : c._spiderScore, 10) || 0));
    var metaLine = [title, company, loc].filter(Boolean).join(' · ');
    var fitDetails = '<details class="spider-fit-details"><summary>Why this fit' + (c._spiderResumeScored ? ' · resume scored' : '') + '</summary>';
    if (discoveryList.length) fitDetails += '<div class="spider-discovery-line"><strong>Keyword discovery:</strong> ' + esc(discoveryList.slice(0,6).join(' · ')) + '</div>';
    fitDetails += '<div class="spider-fit-line"><strong>Fit evidence:</strong> ' + esc(matchedList.length ? matchedList.slice(0,5).join(' · ') : 'No additional job-scope evidence visible.') + '</div>';
    if (c._spiderFitSource) fitDetails += '<div class="spider-muted-line"><strong>Scored from:</strong> ' + esc(c._spiderResumeScored ? c._spiderFitSource : (c._spiderFitSource + ' · no resume text used')) + '</div>';
    if (unknownList.length) fitDetails += '<div class="spider-muted-line"><strong>Gaps / unknown:</strong> ' + esc(unknownList.slice(0,3).join(' · ')) + '</div>';
    fitDetails += renderSpiderFitBreakdown(c);
    fitDetails += '</details>';
    var actions = '<div class="spider-card-actions"><button type="button" class="sec" onclick="event.stopPropagation();openTheSpiderCandidatePreview(this.closest(&quot;.spider-candidate-card&quot;).getAttribute(&quot;data-spider-id&quot;),' + idx + ')">Preview CV</button>' + (link ? '<a class="sec" href="' + escAttr(link) + '" target="_blank" rel="noopener" onclick="event.stopPropagation()">Open Profile</a>' : '<span></span>') + '</div>';
    return '<div class="spider-candidate-card is-clickable" data-spider-index="' + escAttr(String(idx)) + '" data-spider-id="' + escAttr(id) + '" onclick="openTheSpiderCandidatePreview(this.getAttribute(&quot;data-spider-id&quot;),' + idx + ')"><div class="spider-candidate-top"><div class="spider-candidate-title-wrap"><div class="spider-candidate-name">' + esc(name) + '</div><div class="spider-candidate-meta">' + esc(metaLine) + '</div></div><span class="spider-fit-score">' + fitPct + '%</span></div>' + renderSpiderInfoGrid(c) + fitDetails + actions + '</div>';
  }).join('') + '</div>';
}

function spiderCandidateSortNumber(c, key) {
  var snap = spiderCardSnapshot(c, key);
  if (!snap || snap.sort === null || snap.sort === undefined || snap.sort === '') return null;
  var n = Number(snap.sort);
  return Number.isFinite(n) ? n : null;
}
function spiderCandidateName(c) {
  return String((c && (c.name || [c.firstName,c.lastName].filter(Boolean).join(' ') || c.fullName)) || 'Candidate').toLowerCase();
}
function sortTheSpiderCandidateArray(items, mode) {
  var out = Array.isArray(items) ? items.slice() : [];
  mode = String(mode || 'fit_desc');
  function numeric(a,b,key,asc) {
    var av=spiderCandidateSortNumber(a,key), bv=spiderCandidateSortNumber(b,key);
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;
    return asc ? av-bv : bv-av;
  }
  out.sort(function(a,b){
    if (mode === 'fit_asc' || mode === 'fit_desc') {
      var av=Number(a._spiderFitPercent != null ? a._spiderFitPercent : a._spiderScore)||0;
      var bv=Number(b._spiderFitPercent != null ? b._spiderFitPercent : b._spiderScore)||0;
      return mode === 'fit_asc' ? av-bv : bv-av;
    }
    if (mode === 'current_salary_asc') return numeric(a,b,'currentSalary',true);
    if (mode === 'current_salary_desc') return numeric(a,b,'currentSalary',false);
    if (mode === 'expected_salary_asc') return numeric(a,b,'expectedSalary',true);
    if (mode === 'expected_salary_desc') return numeric(a,b,'expectedSalary',false);
    if (mode === 'notice_asc') return numeric(a,b,'notice',true);
    if (mode === 'notice_desc') return numeric(a,b,'notice',false);
    if (mode === 'updated_desc') {
      var at=Date.parse((a && (a.updatedAt || a.modifiedAt || a.createdAt)) || '')||0;
      var bt=Date.parse((b && (b.updatedAt || b.modifiedAt || b.createdAt)) || '')||0;
      return bt-at;
    }
    return spiderCandidateName(a).localeCompare(spiderCandidateName(b));
  });
  return out;
}
function renderTheSpiderSearchContext() {
  var ctx=window._theSpiderSearchContext || {};
  var body=document.getElementById('theSpiderSearchBody'), badge=document.getElementById('theSpiderSearchBadge');
  var sorted=sortTheSpiderCandidateArray(ctx.items || [], ctx.sort || 'fit_desc');
  window._theSpiderLastResults=sorted;
  if (badge) badge.textContent=sorted.length + ' candidates';
  if (body) body.innerHTML=(ctx.errorsHtml || '') + (ctx.summaryHtml || '') + '<h4>Matched JobAdder Candidates</h4><div class="spider-search-shell"><div class="spider-results-scroll">' + renderTheSpiderCandidates(sorted, ctx.emptyMessage || '') + '</div>' + renderTheSpiderPreviewShell() + '</div><h4>Queries used</h4><div>' + (ctx.queriesHtml || '') + '</div>';
}
function sortTheSpiderResults(mode) {
  window._theSpiderSearchContext=window._theSpiderSearchContext || {};
  window._theSpiderSearchContext.sort=String(mode || 'fit_desc');
  var ctx=window._theSpiderSearchContext || {};
  var sorted=sortTheSpiderCandidateArray(ctx.items || [], ctx.sort || 'fit_desc');
  window._theSpiderLastResults=sorted;
  var badge=document.getElementById('theSpiderSearchBadge');
  if (badge) badge.textContent=sorted.length + ' candidates';
  var body=document.getElementById('theSpiderSearchBody');
  var list=body ? body.querySelector('.spider-results-scroll') : null;
  var activeId=String(window._theSpiderPreviewRequestedCandidateId || '');
  if (!list) {
    renderTheSpiderSearchContext();
  } else {
    list.innerHTML=renderTheSpiderCandidates(sorted, ctx.emptyMessage || '');
  }
  var activeIdx=-1;
  if (activeId) {
    for (var i=0;i<sorted.length;i++) {
      if (getTheSpiderCandidateId(sorted[i]) === activeId) { activeIdx=i; break; }
    }
  }
  if (activeIdx >= 0) setTheSpiderCandidateSelected(activeIdx);
  restartTheSpiderPreviewPrefetchForCurrentOrder(sorted);
  // The preview shell is deliberately left mounted. Its visual/text state,
  // finder selection and cached DOM remain intact while only card order changes.
}

async function runTheSpiderJobAdderSearch(opts) {
  if (!requireAiCrawlerUnlocked()) return;
  opts = opts || {};
  var tabRunToken = opts.tabRunToken || null;
  if (!tabRunToken) {
    clearTabRunState('thespider');
    ackBrowserActivityForTab('thespider');
    ackBrowserActivityFailedForTab('thespider');
    tabRunToken = markTabRunning('thespider');
  }
  resetTheSpiderPreviewCaches();
  var runId = (Number(window._theSpiderSearchRunSeq) || 0) + 1;
  window._theSpiderSearchRunSeq = runId;
  var spiderInputs = getTheSpiderInputs();
  var spiderFilters = buildTheSpiderSearchFilters(spiderInputs);
  var authoredBoolean = normaliseTheSpiderBooleanRule(spiderInputs.must || '');
  var queries = (authoredBoolean && hasTheSpiderBooleanSyntax(authoredBoolean))
    ? [authoredBoolean]
    : ((window._theSpiderQueries && window._theSpiderQueries.length) ? window._theSpiderQueries.slice(0,4) : buildTheSpiderFallbackQueries(spiderInputs).slice(0,4));
  if (!queries.length) { queries = buildTheSpiderFallbackQueries(spiderInputs).slice(0,4); }
  if (spiderInputs.country || spiderInputs.residential !== 'Any' || spiderInputs.industry || spiderInputs.it_skills || spiderInputs.qualifications || spiderInputs.salary_min || spiderInputs.salary_max) {
    // All dropdown/profile values are exact backend eligibility checks, never
    // latest-resume keywords. Use one independent discovery query so the same
    // bounded candidate pool is not eligibility-scanned repeatedly.
    if (authoredBoolean) {
      queries = buildTheSpiderDiscoveryQueries(spiderInputs).slice(0,1);
    } else {
      // Keep the first AI-generated JobAdder query. Rebuilding here from the
      // raw JD can accidentally use a company/header line instead of the role.
      queries = queries.slice(0,1);
    }
  }
  if (!queries.length) { markTabFailed('thespider', tabRunToken, {forceBrowser:true}); showToast('Add a JD or Boolean Rules / Keywords first', 'err'); return; }
  var out=document.getElementById('theSpiderSearchOutput'), body=document.getElementById('theSpiderSearchBody'), badge=document.getElementById('theSpiderSearchBadge');
  if (out) out.classList.add('show');
  var phaseStatus=document.getElementById('theSpiderStatus'); if (phaseStatus) phaseStatus.textContent='Sourcing JobAdder…';
  showTheSpiderPanel('results');
  if (body) body.innerHTML = '<div style="display:flex;align-items:center;gap:10px;color:var(--text3);"><span class="spinner"></span><span>Sourcing matching JobAdder candidates…</span></div>';
  var all=[]; var errors=[]; var filterSummaries=[]; var reconnectRequired=false;
  for (var i=0;i<queries.length;i++) {
    try {
      var r = await fetchWithTimeout('/jobadder/spider_search', {method:'POST', headers:{'Content-Type':'application/json','X-AI-Crawler-Code':aiCrawlerLockPayload()}, body:JSON.stringify({query:queries[i], limit:200, filters:spiderFilters, crawler_lock_code:aiCrawlerLockPayload()})}, 420000);
      var d = await r.json().catch(function(){ return {}; });
      if (window._theSpiderSearchRunSeq !== runId) return;
      if (r.status === 401 || d.needs_reconnect) {
        var authErr = new Error(d.error || 'JobAdder connection expired. Reconnect JobAdder in Settings, then run AI Crawler again.');
        authErr.jobAdderReconnect = true;
        throw authErr;
      }
      if (!r.ok || d.error) throw new Error(d.error || ('JobAdder search failed: ' + r.status));
      var items = d.items || d.candidates || (d.data && d.data.items) || [];
      if (d.filter_summary) filterSummaries.push(d.filter_summary);
      items.forEach(function(x){ x._spiderQuery = queries[i]; all.push(x); });
    } catch(e) {
      if (window._theSpiderSearchRunSeq !== runId) return;
      if (e && e.jobAdderReconnect) {
        reconnectRequired = true;
        errors = [e.message || 'JobAdder connection expired. Reconnect JobAdder in Settings, then run AI Crawler again.'];
        break;
      }
      errors.push(queries[i] + ': ' + (e.message || 'failed'));
    }
  }
  if (window._theSpiderSearchRunSeq !== runId) return;
  var seen={}, dedup=[];
  all.forEach(function(c){
    var id = getTheSpiderCandidateId(c);
    var email = String((c && (c.email || c.emailAddress)) || '').trim().toLowerCase();
    var k = id ? ('id:' + id) : (email ? ('email:' + email) : ('raw:' + JSON.stringify(c).slice(0,160)));
    if(seen[k])return; seen[k]=1; dedup.push(c);
  });
  dedup = dedup.filter(function(c){ return (parseInt(c._spiderFitPercent != null ? c._spiderFitPercent : c._spiderScore, 10) || 0) >= 10; });
  var summaryHtml = filterSummaries.map(renderTheSpiderFilterSummary).join('');
  var totalReported = filterSummaries.reduce(function(sum,s){ var n=Number(s && s.reported_total); return sum + (Number.isFinite(n) ? n : 0); }, 0);
  var emptyMessage = totalReported > 0
    ? ('JobAdder matched ' + totalReported + ' candidate(s), but selected filters removed all. Loosen Country, Residential Status, Industry, IT Skills, Qualifications, Salary, Years, or Strict filters.')
    : 'No candidates returned for this query. Try broader strings or fewer must-haves.';
  var sortEl=document.getElementById('theSpiderSort');
  var sortMode=(sortEl && sortEl.value) || 'fit_desc';
  window._theSpiderSearchContext={
    items:dedup,
    sort:sortMode,
    errorsHtml:errors.length ? '<div class="provider-down-alert" style="margin-bottom:10px;">' + esc(errors.join('\n')) + '</div>' : '',
    summaryHtml:summaryHtml,
    emptyMessage:emptyMessage,
    queriesHtml:queries.map(function(q){ return '<span class="spider-query-chip">' + esc(q) + '</span>'; }).join('')
  };
  renderTheSpiderSearchContext();
  startTheSpiderPreviewPrefetch(window._theSpiderLastResults || []);
  var phaseFailed = reconnectRequired || (errors.length > 0 && dedup.length === 0);
  if (phaseStatus) phaseStatus.textContent = phaseFailed ? 'Failed' : 'Completed';
  if (phaseFailed) markTabFailed('thespider', tabRunToken, {forceBrowser:true});
  else markTabDone('thespider', tabRunToken, {forceBrowser:true});
  if (dedup.length) showToast('JobAdder search returned ' + dedup.length + ' candidate(s) with recalculated fit', 'ok'); else showToast(reconnectRequired ? 'Reconnect JobAdder in Settings' : (errors.length ? 'JobAdder search issue — see output' : (totalReported > 0 ? 'JobAdder matched candidates, but local filters removed all' : 'No candidates found')), (reconnectRequired || errors.length) ? 'err' : 'info');
}
function copyTheSpiderReport() {
  var plan = window._theSpiderPlainText || ((document.getElementById('theSpiderBody') || {}).innerText || '');
  var results = ((document.getElementById('theSpiderSearchBody') || {}).innerText || '').trim();
  var txt = (results ? ('JobAdder Candidate Results\n\n' + results + '\n\n') : '') + (plan || '');
  if (!txt.trim()) { showToast('No AI Crawler report to copy yet', 'err'); return; }
  navigator.clipboard.writeText(txt).then(function(){ showToast('AI Crawler report copied', 'ok'); }).catch(function(){ showToast('Copy failed', 'err'); });
}
function clearTheSpiderJobAdderAccountState() {
  window._theSpiderSearchRunSeq = (Number(window._theSpiderSearchRunSeq) || 0) + 1;
  resetTheSpiderPreviewCaches();
  clearTabRunState('thespider');
  ackBrowserActivityForTab('thespider');
  ackBrowserActivityFailedForTab('thespider');
  var searchOutput = document.getElementById('theSpiderSearchOutput');
  if (searchOutput) searchOutput.classList.remove('show');
  var searchBody = document.getElementById('theSpiderSearchBody');
  if (searchBody) searchBody.innerHTML = '';
  var status = document.getElementById('theSpiderStatus');
  if (status) status.textContent = '';
  window._theSpiderLastResults=[];
  window._theSpiderSearchContext=null;
}
function clearTheSpider() {
  window._theSpiderSearchRunSeq = (Number(window._theSpiderSearchRunSeq) || 0) + 1;
  resetTheSpiderPreviewCaches();
  clearTabRunState('thespider');
  ackBrowserActivityForTab('thespider');
  ackBrowserActivityFailedForTab('thespider');
  ['theSpiderJdText','theSpiderCityState','theSpiderIndustry','theSpiderItSkills','theSpiderQualifications','theSpiderMust','theSpiderSalaryMin','theSpiderSalaryMax'].forEach(function(id){ var el=document.getElementById(id); if(el) el.value=''; });
  var yearsMin=document.getElementById('theSpiderYearsMin'); if(yearsMin) yearsMin.value='0'; var yearsMax=document.getElementById('theSpiderYearsMax'); if(yearsMax) yearsMax.value='40'; updateTheSpiderYearsRange();
  var country=document.getElementById('theSpiderCountry'); if(country) country.value='Malaysia';
  var residential=document.getElementById('theSpiderResidential'); if(residential) residential.value='Any';
  var salaryCurrency=document.getElementById('theSpiderSalaryCurrency'); if(salaryCurrency) salaryCurrency.value='MYR';
  var includeMissingSalary=document.getElementById('theSpiderIncludeMissingSalary'); if(includeMissingSalary) includeMissingSalary.checked=true;
  ['theSpiderOutput','theSpiderSearchOutput'].forEach(function(id){ var el=document.getElementById(id); if(el) el.classList.remove('show'); });
  ['theSpiderBody','theSpiderSearchBody'].forEach(function(id){ var el=document.getElementById(id); if(el) el.innerHTML=''; });
  var copyBtn=document.getElementById('theSpiderCopyBtn'); if(copyBtn) copyBtn.style.display='none';
  var sourceBtn=document.getElementById('theSpiderBtn'); if(sourceBtn){ sourceBtn.disabled=false; sourceBtn.textContent='Source Candidates'; }
  setTheSpiderOutputTab('notes');
  var cost=document.getElementById('theSpiderCost'); if(cost){cost.style.display='none'; cost.textContent='';}
  var status=document.getElementById('theSpiderStatus'); if(status) status.textContent='';
  var file=document.getElementById('theSpiderFile'); if(file) file.value='';
  var fs=document.getElementById('theSpiderFileStatus'); if(fs) fs.textContent='';
  window._theSpiderPlainText=''; window._theSpiderHTML=''; window._theSpiderQueries=[]; window._theSpiderLastResults=[]; window._theSpiderSearchContext=null; var sortEl=document.getElementById('theSpiderSort'); if(sortEl) sortEl.value='fit_desc'; updateTheSpiderCounts();
}
function initTheSpiderTabUI() {
  updateAiCrawlerLockUI();
  updateTheSpiderRouteBadge();
  updateTheSpiderCounts();
  updateTheSpiderYearsLabel();
  if (aiCrawlerIsUnlocked()) loadTheSpiderJobAdderOptions();
}
