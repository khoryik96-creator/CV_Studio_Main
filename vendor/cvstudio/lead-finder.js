// ── Lead Finder Tab ──────────────────────────────────────────────────────────
var _leadCompanies = [];
var _leadPeople = [];
var _leadSummary = null;
var _leadCandidateFile = null;
var _leadExtractedText = '';
var _leadLastWarning = '';
var _leadCosts = { search_usd:0, people_usd:0, email_usd:0, total_usd:0, search_tokens:0, people_tokens:0, email_tokens:0, model:'' };
var _leadSelectedCompanyIds = {};
var _leadSelectedPersonIds = {};

function toggleLeadPill(btn) {
  btn.classList.toggle('active');
  if (btn && btn.closest && btn.closest('#leadRegionPills')) leadUpdateRegionPreview();
}

function leadSplitCommaList(value) {
  return String(value || '')
    .split(',')
    .map(function(x){ return x.trim(); })
    .filter(function(x){ return !!x; });
}

function leadUniqueList(items) {
  var seen = {};
  var out = [];
  (items || []).forEach(function(x){
    x = String(x || '').trim();
    if (!x) return;
    var k = x.toLowerCase();
    if (seen[k]) return;
    seen[k] = true;
    out.push(x);
  });
  return out;
}

function leadGetRegions() {
  var picked = Array.from(document.querySelectorAll('#leadRegionPills .lead-pill.active')).map(function(b){ return b.getAttribute('data-region'); });
  var extraEl = document.getElementById('leadExtraCountries');
  var extra = extraEl ? leadSplitCommaList(extraEl.value) : [];
  return leadUniqueList(picked.concat(extra));
}

function leadUpdateRegionPreview() {
  var el = document.getElementById('leadRegionPreview');
  if (!el) return;
  var regions = leadGetRegions();
  el.textContent = regions.length ? ('Selected: ' + regions.join(', ')) : 'Selected: none';
}

function leadGetJobSources() {
  return Array.from(document.querySelectorAll('#leadSourcePills .lead-pill.active')).map(function(b){ return b.getAttribute('data-source'); });
}

function leadUpdateCvCount() {
  var el = document.getElementById('leadCvText');
  var cc = document.getElementById('leadCvCharCount');
  if (el && cc) cc.textContent = (el.value || '').length.toLocaleString() + ' characters';
}

function setupLeadDropZone() {
  var dz = document.getElementById('leadDropZone');
  if (!dz || dz.__leadBound) return;
  dz.__leadBound = true;
  dz.addEventListener('dragover', function(e){ e.preventDefault(); dz.classList.add('dragover'); });
  dz.addEventListener('dragleave', function(){ dz.classList.remove('dragover'); });
  dz.addEventListener('drop', function(e){
    e.preventDefault();
    dz.classList.remove('dragover');
    handleLeadFileInput(e.dataTransfer.files);
  });
}

async function handleLeadFileInput(files) {
  if (!files || !files.length) return;
  var file = files[0];
  _leadCandidateFile = file;
  _leadExtractedText = '';
  var dz = document.getElementById('leadDropZone');
  var nameEl = document.getElementById('leadDzFileName');
  var clearEl = document.getElementById('leadDzClear');
  var countEl = document.getElementById('leadFileCharCount');
  dz.classList.remove('error');
  dz.classList.add('has-file');
  nameEl.textContent = 'Extracting: ' + file.name;
  clearEl.style.display = 'block';
  countEl.style.display = 'block';
  countEl.textContent = 'Extracting text…';
  try {
    var fd = new FormData();
    fd.append('file', file);
    var r = await fetchWithTimeout('/extract-text', { method:'POST', body: fd }, CV_EXTRACT_TEXT_TIMEOUT_MS);
    var d = await r.json();
    if (!r.ok || d.error || d.ok === false) throw new Error(d.error || 'Text extraction failed');
    _leadExtractedText = (d.text || '').trim();
    nameEl.textContent = file.name;
    countEl.textContent = (_leadExtractedText.length || 0).toLocaleString() + ' characters extracted';
    if (_leadExtractedText) document.getElementById('leadCvText').value = _leadExtractedText;
    leadUpdateCvCount();
    showToast('CV extracted for Lead Finder', 'ok');
  } catch(e) {
    dz.classList.add('error');
    nameEl.textContent = file.name;
    countEl.textContent = 'Extraction failed: ' + (e.message || e);
    showToast('Lead Finder extraction failed', 'err');
  }
}

function clearLeadFile() {
  _leadCandidateFile = null;
  _leadExtractedText = '';
  var dz = document.getElementById('leadDropZone');
  if (dz) dz.classList.remove('has-file','error');
  var nameEl = document.getElementById('leadDzFileName'); if (nameEl) nameEl.textContent = '';
  var clearEl = document.getElementById('leadDzClear'); if (clearEl) clearEl.style.display = 'none';
  var countEl = document.getElementById('leadFileCharCount'); if (countEl) { countEl.style.display = 'none'; countEl.textContent = '0 characters extracted'; }
  var input = document.getElementById('leadFileInput'); if (input) input.value = '';
}

function switchLeadSubtab(tab) {
  ['summary','companies','people','export'].forEach(function(t){
    document.getElementById('leadSub' + t.charAt(0).toUpperCase() + t.slice(1)).classList.toggle('active', t === tab);
    document.getElementById('leadPanel' + t.charAt(0).toUpperCase() + t.slice(1)).classList.toggle('active', t === tab);
  });
}

function leadMakeId(prefix, i) { return prefix + '_' + Date.now() + '_' + i; }

function leadUsageTokens(usage) {
  usage = usage || {};
  return (Number(usage.input_tokens) || 0) + (Number(usage.output_tokens) || 0);
}

function leadCostFromResponse(d) {
  d = d || {};
  if (typeof d.cost === 'number') return d.cost;
  if (d.cost_details && typeof d.cost_details.usd === 'number') return d.cost_details.usd;
  if (d.usage) return responseCost(d, d.model || getModel(), d.provider || getLeadProvider());
  return 0;
}

function leadCostLabel(usd) {
  usd = Number(usd) || 0;
  if (usd > 0 && usd < 0.0001) return '<$0.0001';
  return '$' + usd.toFixed(4);
}

function leadMyrLabel(usd) {
  usd = Number(usd) || 0;
  return 'RM ' + (usd * USD_TO_MYR).toFixed(2);
}

function leadRefreshTotalCost() {
  _leadCosts.total_usd = (Number(_leadCosts.search_usd) || 0) + (Number(_leadCosts.people_usd) || 0) + (Number(_leadCosts.email_usd) || 0);
}

function leadFitPercent(c) {
  c = c || {};
  var raw = c.job_fit_percent;
  if (raw === undefined || raw === null || raw === '') raw = c.match_score;
  if (raw === undefined || raw === null || raw === '') raw = c.score;
  var n = parseInt(String(raw || '0').replace('%',''), 10);
  if (!isFinite(n)) n = 0;
  if (n < 0) n = 0;
  if (n > 100) n = 100;
  return n;
}


function leadFitReviewLabel(fit) {
  fit = Number(fit) || 0;
  if (fit >= 80) return { text:'Strong fit', cls:'green' };
  if (fit >= 60) return { text:'Possible fit', cls:'blue' };
  if (fit >= 40) return { text:'Borderline — review', cls:'warn' };
  return { text:'Low fit — still shown', cls:'red' };
}

function leadTodayLocalDate() {
  var d = new Date();
  d.setHours(0,0,0,0);
  return d;
}

function leadDateIsoLocal(d) {
  var yyyy = d.getFullYear();
  var mm = String(d.getMonth() + 1).padStart(2, '0');
  var dd = String(d.getDate()).padStart(2, '0');
  return yyyy + '-' + mm + '-' + dd;
}

function leadDateFromDaysOpen(days) {
  var d = Number(days);
  if (!isFinite(d)) return '';
  var today = leadTodayLocalDate();
  var dt = new Date(today.getTime() - Math.max(0, d) * 86400000);
  return leadDateIsoLocal(dt);
}

function leadParsePostedDate(raw) {
  raw = String(raw || '').trim();
  if (!raw) return { label: '', days: null };
  var today = leadTodayLocalDate();
  var s = raw.toLowerCase();
  if (['unknown','n/a','na','not available','not visible','not shown','unspecified','none','-'].indexOf(s) >= 0) return { label: '', days: null };
  var m = s.match(/(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})/);
  if (m) {
    var d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
    if (!isNaN(d.getTime())) return { label: leadDateIsoLocal(d), days: Math.max(0, Math.round((today - d) / 86400000)) };
  }
  m = s.match(/\b(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})\b/);
  if (m) {
    var d2 = new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]));
    if (!isNaN(d2.getTime())) return { label: leadDateIsoLocal(d2), days: Math.max(0, Math.round((today - d2) / 86400000)) };
  }
  if (/(today|just posted|few hours|hour ago|hours ago|moments ago|\bnew\b)/.test(s)) return { label: leadDateIsoLocal(today), days: 0 };
  if (/yesterday/.test(s)) { var y = new Date(today.getTime() - 86400000); return { label: leadDateIsoLocal(y), days: 1 }; }
  m = s.match(/(\d+)\s*(day|days|d)\s*ago/); if (m) { var dd = Number(m[1]); var dt = new Date(today.getTime() - dd*86400000); return { label: leadDateIsoLocal(dt), days: dd }; }
  m = s.match(/(\d+)\s*(week|weeks|w)\s*ago/); if (m) { var ww = Number(m[1]) * 7; var wt = new Date(today.getTime() - ww*86400000); return { label: leadDateIsoLocal(wt), days: ww }; }
  m = s.match(/(\d+)\s*(month|months|mo)\s*ago/); if (m) { var mm = Number(m[1]) * 30; var mt = new Date(today.getTime() - mm*86400000); return { label: leadDateIsoLocal(mt), days: mm }; }
  return { label: raw, days: null };
}

function leadFreshnessFromDays(days) {
  if (days === null || days === undefined || days === '') return 'Unknown';
  var d = Number(days);
  if (!isFinite(d)) return 'Unknown';
  if (d <= 0) return 'Today';
  if (d <= 7) return d + ' day(s) open';
  if (d <= 14) return '8-14 days open';
  if (d <= 30) return '15-30 days open';
  return '30+ days open';
}

function leadFreshClass(days) {
  if (days === null || days === undefined || days === '') return '';
  var d = Number(days);
  if (!isFinite(d)) return '';
  if (d <= 7) return ' hot';
  if (d <= 30) return ' warm';
  return ' old';
}

function leadHasDaysOpen(days) {
  return !(days === null || days === undefined || days === '') && isFinite(Number(days));
}

function leadTextBlob(obj, fields) {
  return (fields || []).map(function(f){ return String((obj && obj[f]) || ''); }).join(' ').toLowerCase();
}

function leadPortalInfo(portal) {
  var raw = String(portal || '').trim();
  var s = raw.toLowerCase();
  var info = { label: raw || 'Other', icon: '↗', cls: 'other' };
  if (!s) return info;
  if (s.indexOf('linkedin') >= 0) return { label: raw, icon: 'in', cls: 'linkedin' };
  if (s.indexOf('jobstreet') >= 0) return { label: raw, icon: 'JS', cls: 'jobstreet' };
  if (s.indexOf('indeed') >= 0) return { label: raw, icon: 'ID', cls: 'indeed' };
  if (s.indexOf('glassdoor') >= 0) return { label: raw, icon: 'GD', cls: 'glassdoor' };
  if (s.indexOf('monster') >= 0) return { label: raw, icon: 'M', cls: 'monster' };
  if (s.indexOf('foundit') >= 0) return { label: raw, icon: 'F', cls: 'foundit' };
  if (s.indexOf('hiredly') >= 0) return { label: raw, icon: 'H', cls: 'hiredly' };
  if (s.indexOf('jobsdb') >= 0) return { label: raw, icon: 'J', cls: 'jobsdb' };
  if (s.indexOf('mycareersfuture') >= 0) return { label: raw, icon: 'MCF', cls: 'mycareersfuture' };
  if (s.indexOf('kalibrr') >= 0) return { label: raw, icon: 'K', cls: 'kalibrr' };
  if (s.indexOf('career') >= 0 || s.indexOf('company') >= 0) return { label: raw, icon: 'CO', cls: 'careers' };
  return info;
}

function leadPortalBadgeHtml(portal) {
  var info = leadPortalInfo(portal);
  return '<span class="lead-source-badge ' + escAttr(info.cls) + '"><span class="lead-source-icon">' + esc(info.icon) + '</span><span>' + esc(info.label) + '</span></span>';
}

function leadCompanyId(c, idx) {
  return String((c && c.id) || ('co_' + idx));
}
function leadPersonId(p, idx) {
  return String((p && p.id) || ('pe_' + idx));
}
function leadTogglePersonSelection(id, checked) {
  if (!_leadSelectedPersonIds) _leadSelectedPersonIds = {};
  if (checked) _leadSelectedPersonIds[id] = true;
  else delete _leadSelectedPersonIds[id];
}
function leadSelectedPersonCount() {
  return Object.keys(_leadSelectedPersonIds || {}).filter(function(k){ return !!_leadSelectedPersonIds[k]; }).length;
}
function leadGetSelectedPersonIds() {
  return Object.keys(_leadSelectedPersonIds || {}).filter(function(k){ return !!_leadSelectedPersonIds[k]; });
}

function leadSelectedCompanyCount() {
  return Object.keys(_leadSelectedCompanyIds || {}).filter(function(k){ return !!_leadSelectedCompanyIds[k]; }).length;
}

function leadUpdateSelectedChip() {
  var el = document.getElementById('leadSelectedCountChip');
  if (!el) return;
  var n = leadSelectedCompanyCount();
  el.textContent = n + ' selected';
  el.style.opacity = n ? '1' : '0.78';
}

function leadPruneSelectedCompanies() {
  var valid = {};
  (_leadCompanies || []).forEach(function(c, i){ valid[leadCompanyId(c, i)] = 1; });
  Object.keys(_leadSelectedCompanyIds || {}).forEach(function(k){ if (!valid[k]) delete _leadSelectedCompanyIds[k]; });
}

function leadToggleCompanySelection(id, checked) {
  if (!_leadSelectedCompanyIds) _leadSelectedCompanyIds = {};
  if (checked) _leadSelectedCompanyIds[id] = true;
  else delete _leadSelectedCompanyIds[id];
  leadUpdateSelectedChip();
}

function leadSelectShownCompanies() {
  var rows = leadRealCompanyRows(leadGetCompanyViewRows());
  if (!rows.length) { showToast('No extracted job leads to select. Fallback search links cannot be used for people search.', 'err'); return; }
  rows.forEach(function(c, i){ _leadSelectedCompanyIds[leadCompanyId(c, i)] = true; });
  renderLeadCompanies();
  showToast(rows.length + ' extracted job leads selected', 'ok');
}

function leadClearSelectedCompanies() {
  _leadSelectedCompanyIds = {};
  renderLeadCompanies();
}

function leadIsFallbackCompanyLead(c) {
  return String((c && c.lead_kind) || '').toLowerCase() === 'fallback_search_link';
}

function leadIsNeedsVerificationLead(c) {
  var k = String((c && c.lead_kind) || '').toLowerCase();
  var q = String((c && c.job_url_quality) || '').toLowerCase();
  return k === 'job_lead_needs_verification' || q === 'needs_verification';
}

function leadRealCompanyRows(rows) {
  return (rows || []).filter(function(c){ return !leadIsFallbackCompanyLead(c); });
}

function leadLeadMixCounts(rows) {
  rows = rows || _leadCompanies || [];
  var fallback = rows.filter(leadIsFallbackCompanyLead).length;
  return { total: rows.length, real: rows.length - fallback, fallback: fallback };
}

function leadGetSelectedCompanies() {
  return (_leadCompanies || []).filter(function(c, i){ return !!_leadSelectedCompanyIds[leadCompanyId(c, i)] && !leadIsFallbackCompanyLead(c); });
}

function leadGetCompanyViewRows() {
  var rows = _leadCompanies.slice();
  var qEl = document.getElementById('leadCompanyFilter');
  var q = qEl ? String(qEl.value || '').trim().toLowerCase() : '';
  var high = document.getElementById('leadOnlyHighFit');
  var fresh = document.getElementById('leadOnlyFresh');
  if (q) {
    rows = rows.filter(function(c){
      return leadTextBlob(c, ['company','country','region','job_portal','industry','matched_role','hiring_signal','why_matched','source_note']).indexOf(q) >= 0;
    });
  }
  if (high && high.checked) rows = rows.filter(function(c){ return leadFitPercent(c) >= 80; });
  if (fresh && fresh.checked) rows = rows.filter(function(c){ return leadHasDaysOpen(c.days_open) && Number(c.days_open) <= 14; });
  var sortEl = document.getElementById('leadCompanySort');
  var sort = sortEl ? sortEl.value : 'fit';
  rows.sort(function(a,b){
    if (sort === 'fresh') {
      var ad = (a.days_open === '' || a.days_open === undefined || a.days_open === null) ? 99999 : Number(a.days_open);
      var bd = (b.days_open === '' || b.days_open === undefined || b.days_open === null) ? 99999 : Number(b.days_open);
      return ad - bd || (leadFitPercent(b) - leadFitPercent(a));
    }
    if (sort === 'company') return String(a.company || '').localeCompare(String(b.company || ''));
    if (sort === 'portal') return String(a.job_portal || '').localeCompare(String(b.job_portal || '')) || String(a.company || '').localeCompare(String(b.company || ''));
    return leadFitPercent(b) - leadFitPercent(a);
  });
  return rows;
}

function leadIsHrType(p) {
  var t = String((p && (p.contact_type + ' ' + p.title)) || '').toLowerCase();
  return t.indexOf('hr') >= 0 || t.indexOf('talent') >= 0 || t.indexOf('recruit') >= 0 || t.indexOf('people') >= 0;
}

function leadGetPeopleViewRows() {
  var rows = _leadPeople.slice();
  var qEl = document.getElementById('leadPeopleFilter');
  var q = qEl ? String(qEl.value || '').trim().toLowerCase() : '';
  if (q) {
    rows = rows.filter(function(p){
      return leadTextBlob(p, ['name','title','company','country','contact_type','email','notes','verification_status']).indexOf(q) >= 0;
    });
  }
  var sortEl = document.getElementById('leadPeopleSort');
  var sort = sortEl ? sortEl.value : 'email';
  rows.sort(function(a,b){
    if (sort === 'hr') return (leadIsHrType(b) ? 1 : 0) - (leadIsHrType(a) ? 1 : 0) || String(a.company || '').localeCompare(String(b.company || ''));
    if (sort === 'hm') return (leadIsHrType(a) ? 1 : 0) - (leadIsHrType(b) ? 1 : 0) || String(a.company || '').localeCompare(String(b.company || ''));
    if (sort === 'company') return String(a.company || '').localeCompare(String(b.company || '')) || String(a.name || '').localeCompare(String(b.name || ''));
    return ((b.email ? 1 : 0) - (a.email ? 1 : 0)) || String(a.company || '').localeCompare(String(b.company || ''));
  });
  return rows;
}

function leadUpdateWorkflowSteps() {
  var s1 = document.getElementById('leadStepCompanies');
  var s2 = document.getElementById('leadStepPeople');
  var s3 = document.getElementById('leadStepEmails');
  var emails = _leadPeople.filter(function(p){ return !!(p.email || '').trim(); }).length;
  function set(el, cls) { if (!el) return; el.classList.remove('active','done','waiting'); el.classList.add(cls); }
  set(s1, _leadCompanies.length ? 'done' : 'active');
  set(s2, _leadPeople.length ? 'done' : (_leadCompanies.length ? 'active' : 'waiting'));
  set(s3, emails ? 'done' : (_leadPeople.length ? 'active' : 'waiting'));
}

function normalizeLeadData(data) {
  data = data || {};
  var companies = Array.isArray(data.companies) ? data.companies : [];
  var people = Array.isArray(data.people) ? data.people : [];
  companies = companies.filter(function(c){ return String((c && c.lead_kind) || '').toLowerCase() !== 'fallback_search_link'; });
  companies = companies.map(function(c, i){
    c = c || {};
    c.id = c.id || leadMakeId('co', i);
    c.job_fit_percent = leadFitPercent(c);
    c.match_score = c.job_fit_percent; // keep old KPI/export compatibility
    c.job_portal = c.job_portal || c.portal || c.source_portal || '';
    var posted = leadParsePostedDate(c.date_posted || c.posted_date || c.posted || c.job_posted || '');
    var existingDays = (c.days_open !== undefined && c.days_open !== null && c.days_open !== '') ? Number(c.days_open) : null;
    if (posted.days !== null) c.days_open = posted.days;
    else if (existingDays !== null && isFinite(existingDays)) c.days_open = existingDays;
    else c.days_open = '';
    var rawPostedText = String(c.date_posted || '').trim();
    var rawPostedIsUnknown = ['unknown','n/a','na','not available','not visible','not shown','unspecified','none','-'].indexOf(rawPostedText.toLowerCase()) >= 0;
    c.date_posted = posted.label || (c.days_open !== '' ? leadDateFromDaysOpen(c.days_open) : '') || (rawPostedIsUnknown ? '' : rawPostedText);
    var freshRaw = String(c.job_freshness || '').trim();
    c.job_freshness = (!freshRaw || freshRaw.toLowerCase() === 'unknown') ? leadFreshnessFromDays(c.days_open) : freshRaw;
    return c;
  });
  people = people.map(function(p, i){
    p = p || {};
    p.id = p.id || leadMakeId('pe', i);
    p.email_confidence = p.email_confidence || '';
    p.status = p.status || 'New';
    p.verification_status = p.verification_status || (p.email ? 'Needs review' : 'Not found');
    return p;
  });
  return { summary: data.summary || null, companies: companies, people: people, warning: data.warning || '' };
}

function leadGetJobFilters() {
  function v(id) { var el = document.getElementById(id); return el ? String(el.value || '').trim() : ''; }
  return {
    must_have: v('leadMustHave'),
    exclude_keywords: v('leadExcludeKeywords'),
    seniority: v('leadSeniorityFilter'),
    max_days_open: v('leadFreshnessFilter'),
    work_setup: v('leadWorkSetupFilter'),
    employment_type: v('leadEmploymentFilter'),
    company_include: v('leadCompanyInclude'),
    company_exclude: v('leadCompanyExclude')
  };
}

async function runLeadSearch() {
  if (!requireLeadFinderUnlocked()) return;
  var status = document.getElementById('leadSearchStatus');
  var btn = document.getElementById('btnLeadSearch');
  var route = aiRoutePayload('lead_search');
  var apiKey = route.api_key;
  var cvText = (document.getElementById('leadCvText').value || _leadExtractedText || '').trim();
  var regions = leadGetRegions();
  var jobSources = leadGetJobSources();
  var targetRole = (document.getElementById('leadTargetRole').value || '').trim();
  var context = (document.getElementById('leadContext').value || '').trim();
  var industries = (document.getElementById('leadIndustries').value || '').trim();
  var depth = document.getElementById('leadDepth').value || 'standard';
  var jobFilters = leadGetJobFilters();

  if (!apiKey) { showToast('Save an API key for Lead Finder Job Leads route', 'err'); return; }
  if (!cvText || cvText.length < 80) { showToast('Upload or paste a candidate CV first', 'err'); return; }
  if (!regions.length) { showToast('Select at least one country/region', 'err'); return; }
  if (!jobSources.length) { showToast('Select at least one job source/portal', 'err'); return; }

  var _tabRun = markTabRunning('leadfinder');
  btn.disabled = true;
  status.className = 'lead-status';
  var sp = getSearchProviderConfig();
  status.textContent = 'Phase 1: searching selected-country job portals/job ads for job leads only' + ((sp.provider && sp.provider !== 'none' && sp.api_key) ? ' via ' + sp.provider + ' search provider.' : ' via AI web search.') + ' People discovery runs separately so the request does not keep timing out.';
  switchLeadSubtab('summary');
  document.getElementById('leadSummaryBox').className = 'lead-empty';
  document.getElementById('leadSummaryBox').innerHTML = 'Searching public job leads from selected portals and selected locations. This first step returns job leads quickly; use the People Leads tab to find HR/hiring managers after.';

  try {
    var payload = {
      lead_lock_code: leadFinderLockPayload(),
      api_key: apiKey,
      model: route.model,
      provider: route.provider,
      cv_text: cvText,
      regions: regions,
      job_sources: jobSources,
      target_role: targetRole,
      candidate_context: context,
      industries: industries,
      job_filters: jobFilters,
      search_provider: getSearchProviderConfig(),
      depth: depth,
      allow_ai_title_expansion: !!(document.getElementById('leadAiTitleExpansion') && document.getElementById('leadAiTitleExpansion').checked),
      allow_provider_ai_refine: !!(document.getElementById('leadAllowProviderRefine') && document.getElementById('leadAllowProviderRefine').checked)
    };
    var r = await fetchWithTimeout('/lead-finder/search', {
      method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)
    }, depth === 'deep' ? 125000 : 95000);
    var d = await r.json().catch(function(){ return {}; });
    if (!r.ok || d.error) {
      recordPaidAiFailure('Lead Finder Search failed output', d, route.model, route.provider);
      throw new Error(d.error || 'Lead search failed');
    }
    leadRefreshTitleCacheStats();
    var n = normalizeLeadData(d);
    _leadCompanies = n.companies;
    _leadSelectedCompanyIds = {};
    _leadPeople = n.people;
    _leadSummary = n.summary;
    _leadLastWarning = n.warning || '';
    _leadCosts.search_usd = leadCostFromResponse(d);
    _leadCosts.people_usd = 0;
    _leadCosts.email_usd = 0;
    _leadCosts.search_tokens = d.cost_details ? (Number(d.cost_details.total_tokens) || 0) : leadUsageTokens(d.usage);
    _leadCosts.people_tokens = 0;
    _leadCosts.email_tokens = 0;
    _leadCosts.model = d.model || route.model;
    leadRefreshTotalCost();
    renderLeadFinder();
    status.className = 'lead-status ok';
    var mix = leadLeadMixCounts(_leadCompanies);
    var costPart = ' Cost: ' + leadCostLabel(_leadCosts.search_usd) + ' / ' + leadMyrLabel(_leadCosts.search_usd);
    status.textContent = 'Done — ' + mix.real + ' extracted job lead(s) found. Generic portal/search links are hidden. Next: select useful leads, then run Find People.' + costPart + (_leadLastWarning ? '\nNote: ' + _leadLastWarning : '');
    if (_leadCosts.search_usd > 0 || responseHasPaidUsage(d)) statsRecord('Lead Finder Search' + (mix.real ? '' : ' (0 leads)'), 'lead', _leadCosts.search_usd || 0, d.model || route.model, '', d.provider || route.provider, statsMetaFromResponse(d, route.model, route.provider));
    showToast(mix.real ? 'Lead Finder completed' : 'No extracted job leads returned', mix.real ? 'ok' : 'err');
    markTabDone('leadfinder', _tabRun);
  } catch(e) {
    status.className = 'lead-status err';
    status.textContent = 'Error: ' + (e.message || e);
    document.getElementById('leadSummaryBox').className = 'lead-empty';
    document.getElementById('leadSummaryBox').innerHTML = 'Lead search failed. This usually means the API/network timed out before job search returned. Try Light depth, fewer portals, or verify the Lead Finder API key supports web search.';
    showToast('Lead Finder error', 'err');
    markTabFailed('leadfinder', _tabRun);
  } finally {
    btn.disabled = false;
  }
}

function leadPeopleMergeKey(p) {
  p = p || {};
  var email = String(p.email || '').trim().toLowerCase();
  if (email) return 'email:' + email;
  var profile = String(p.profile_url || p.source_url || '').trim().toLowerCase().replace(/\/$/, '');
  if (profile) return 'url:' + profile;
  return ['person', String(p.name || '').trim().toLowerCase(), String(p.company || '').trim().toLowerCase(), String(p.title || '').trim().toLowerCase()].join('|');
}

function leadMergePeople(existing, incoming) {
  var out = [];
  var byKey = {};
  function addOrMerge(p) {
    p = p || {};
    var key = leadPeopleMergeKey(p);
    if (!key || key === 'person|||') return;
    if (byKey[key] === undefined) {
      byKey[key] = out.length;
      out.push(Object.assign({}, p));
      return;
    }
    var cur = out[byKey[key]];
    Object.keys(p).forEach(function(k){
      if ((cur[k] === undefined || cur[k] === null || cur[k] === '') && p[k] !== undefined && p[k] !== null && p[k] !== '') cur[k] = p[k];
    });
  }
  (existing || []).forEach(addOrMerge);
  (incoming || []).forEach(addOrMerge);
  return out;
}

async function runLeadPeopleSearch(visibleOnly) {
  if (!requireLeadFinderUnlocked()) return;
  var status = document.getElementById('leadPeopleStatus');
  var btn = document.getElementById('btnLeadPeopleSearch');
  var btnShown = document.getElementById('btnLeadPeopleSearchShown');
  var btnSelected = document.getElementById('btnLeadPeopleSearchSelected');
  if (!_leadCompanies.length) { showToast('Run job lead search first', 'err'); return; }
  var mode = visibleOnly === 'selected' ? 'selected' : (visibleOnly ? 'shown' : 'all');
  var companiesToSend = mode === 'selected' ? leadGetSelectedCompanies() : leadRealCompanyRows(mode === 'shown' ? leadGetCompanyViewRows() : _leadCompanies);
  if (!companiesToSend.length) { showToast(mode === 'selected' ? 'Select at least one extracted job lead first. Fallback search links cannot be used for people search.' : 'No extracted job leads to search. Fallback search links need manual review first.', 'err'); return; }
  var route = aiRoutePayload('lead_people');
  var apiKey = route.api_key;
  if (!apiKey) { showToast('Save an API key for Lead Finder People route. Apollo only enriches emails after people are found.', 'err'); return; }
  var _tabRun = markTabRunning('leadfinder');
  var cvText = (document.getElementById('leadCvText').value || _leadExtractedText || '').trim();
  if (btn) btn.disabled = true;
  if (btnShown) btnShown.disabled = true;
  if (btnSelected) btnSelected.disabled = true;
  status.className = 'lead-status';
  status.textContent = 'Searching public web/profile results for likely HR, TA, recruiters and functional hiring managers from ' + companiesToSend.length + (mode === 'selected' ? ' selected' : (mode === 'shown' ? ' shown/filtered' : ' saved')) + ' job leads using common title variations…';
  switchLeadSubtab('people');
  try {
    var r = await fetchWithTimeout('/lead-finder/find-people', {
      method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
        lead_lock_code: leadFinderLockPayload(),
        api_key: apiKey,
        model: route.model,
        provider: route.provider,
        companies: companiesToSend,
        regions: leadGetRegions(),
        target_role: (document.getElementById('leadTargetRole').value || '').trim(),
        candidate_context: (document.getElementById('leadContext').value || '').trim(),
        cv_text: cvText
      })
    }, 135000);
    var d = await r.json().catch(function(){ return {}; });
    if (!r.ok || d.error) {
      recordPaidAiFailure('Lead Finder People Search failed output', d, route.model, route.provider);
      throw new Error(d.error || 'People search failed');
    }
    var n = normalizeLeadData({ people: d.people || [], companies: _leadCompanies, summary: _leadSummary, warning: d.warning || '' });
    var beforePeopleCount = _leadPeople.length;
    _leadPeople = leadMergePeople(_leadPeople, n.people);
    var addedPeopleCount = Math.max(0, _leadPeople.length - beforePeopleCount);
    _leadLastWarning = d.warning || _leadLastWarning;
    var peopleRunCost = leadCostFromResponse(d);
    var peopleRunTokens = d.cost_details ? (Number(d.cost_details.total_tokens) || 0) : leadUsageTokens(d.usage);
    _leadCosts.people_usd = (Number(_leadCosts.people_usd) || 0) + peopleRunCost;
    _leadCosts.people_tokens = (Number(_leadCosts.people_tokens) || 0) + peopleRunTokens;
    _leadCosts.model = d.model || _leadCosts.model || route.model;
    leadRefreshTotalCost();
    renderLeadFinder();
    status.className = 'lead-status ok';
    var noPeopleHint = !_leadPeople.length ? '\nNo public people leads were returned. Try selecting 1-3 specific job leads with clear company names/job URLs, especially LinkedIn/JobStreet results, then run Find People for Selected.' : '';
    var titleAngles = Array.isArray(d.title_search_angles) && d.title_search_angles.length ? '\nRole-specific title angles used: ' + d.title_search_angles.slice(0, 12).join(', ') : '';
    status.textContent = 'People search done. ' + _leadPeople.length + ' total people leads saved (' + addedPeopleCount + ' newly added this run). Run cost: ' + leadCostLabel(peopleRunCost) + ' / ' + leadMyrLabel(peopleRunCost) + '. Total Lead Finder cost: ' + leadCostLabel(_leadCosts.total_usd) + ' / ' + leadMyrLabel(_leadCosts.total_usd) + titleAngles + noPeopleHint + (d.warning ? '\nNote: ' + d.warning : '');
    statsRecord('Lead Finder People Search', 'lead', peopleRunCost || 0, d.model || route.model, '', d.provider || route.provider, statsMetaFromResponse(d, route.model, route.provider));
    showToast('People search completed', 'ok');
    markTabDone('leadfinder', _tabRun);
  } catch(e) {
    status.className = 'lead-status err';
    status.textContent = 'Error: ' + (e.message || e);
    showToast('People search error', 'err');
    markTabFailed('leadfinder', _tabRun);
  } finally {
    if (btn) btn.disabled = false;
    if (btnShown) btnShown.disabled = false;
    if (btnSelected) btnSelected.disabled = false;
  }
}

async function runLeadEmailSearch() {
  if (!requireLeadFinderUnlocked()) return;
  var status = document.getElementById('leadPeopleStatus');
  var btn = document.getElementById('btnLeadEmailSearch');
  if (!_leadPeople.length) { showToast('Find people first from the People Leads tab', 'err'); return; }
  var enrichCfg = getEnrichmentProviderConfig();
  var route = aiRoutePayload('lead_email');
  var apiKey = route.api_key;
  var hasApolloProvider = enrichCfg && enrichCfg.provider === 'apollo' && !!enrichCfg.api_key;
  if (!apiKey && !hasApolloProvider) { showToast('Save your Lead Finder AI key, or choose Apollo and save an Apollo API key first', 'err'); return; }
  var _tabRun = markTabRunning('leadfinder');
  btn.disabled = true;
  status.className = 'lead-status';
  status.textContent = 'Searching for public business/company-domain emails only — no LinkedIn scraping…';
  try {
    var r = await fetchWithTimeout('/lead-finder/find-emails', {
      method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
        lead_lock_code: leadFinderLockPayload(),
        api_key: apiKey,
        model: route.model,
        provider: route.provider,
        people: _leadPeople,
        companies: _leadCompanies,
        regions: leadGetRegions(),
        enrichment_provider: enrichCfg,
        selected_person_ids: leadGetSelectedPersonIds()
      })
    }, 150000);
    var d = await r.json().catch(function(){ return {}; });
    if (!r.ok || d.error) {
      recordPaidAiFailure('Lead Finder Email Search failed output', d, route.model, route.provider);
      throw new Error(d.error || 'Email search failed');
    }
    leadRefreshContactCacheStats();
    var n = normalizeLeadData({ people: d.people || _leadPeople, companies: _leadCompanies, summary: _leadSummary, warning: d.warning || '' });
    _leadPeople = n.people;
    _leadLastWarning = d.warning || _leadLastWarning;
    _leadCosts.email_usd = leadCostFromResponse(d);
    _leadCosts.email_tokens = d.cost_details ? (Number(d.cost_details.total_tokens) || 0) : leadUsageTokens(d.usage);
    _leadCosts.model = d.model || _leadCosts.model || route.model;
    leadRefreshTotalCost();
    renderLeadFinder();
    status.className = 'lead-status ok';
    status.textContent = 'Email search done. ' + _leadPeople.filter(function(p){ return !!p.email; }).length + ' public business-domain emails recorded. Additional cost: ' + leadCostLabel(_leadCosts.email_usd) + ' / ' + leadMyrLabel(_leadCosts.email_usd) + '. Total Lead Finder cost: ' + leadCostLabel(_leadCosts.total_usd) + ' / ' + leadMyrLabel(_leadCosts.total_usd) + (d.warning ? '\nNote: ' + d.warning : '');
    statsRecord('Lead Finder Email Search', 'lead', _leadCosts.email_usd || 0, d.model || route.model, '', d.provider || route.provider, statsMetaFromResponse(d, route.model, route.provider));
    showToast('Email search completed', 'ok');
    markTabDone('leadfinder', _tabRun);
  } catch(e) {
    status.className = 'lead-status err';
    status.textContent = 'Error: ' + (e.message || e);
    showToast('Email search error', 'err');
    markTabFailed('leadfinder', _tabRun);
  } finally {
    btn.disabled = false;
  }
}

function renderLeadFinder() {
  if (!leadFinderIsUnlocked()) { updateLeadFinderLockUI(); return; }
  setupLeadDropZone();
  leadUpdateRegionPreview();
  var leadMix = leadLeadMixCounts(_leadCompanies);
  var cCount = leadMix.total;
  var pCount = _leadPeople.length;
  var eCount = _leadPeople.filter(function(p){ return !!(p.email || '').trim(); }).length;
  var avg = cCount ? Math.round(_leadCompanies.reduce(function(a,c){ return a + leadFitPercent(c); }, 0) / cCount) : 0;
  var freshCount = _leadCompanies.filter(function(c){ return leadHasDaysOpen(c.days_open) && Number(c.days_open) <= 14; }).length;
  var el;
  el=document.getElementById('leadKpiCompanies'); if(el) el.textContent = cCount;
  el=document.getElementById('leadKpiPeople'); if(el) el.textContent = pCount;
  el=document.getElementById('leadKpiEmails'); if(el) el.textContent = eCount;
  el=document.getElementById('leadKpiAvg'); if(el) el.textContent = avg + '%';
  el=document.getElementById('leadKpiFresh'); if(el) el.textContent = freshCount;
  leadPruneSelectedCompanies();
  leadUpdateWorkflowSteps();
  leadRefreshTotalCost();
  leadUpdateSelectedChip();
  el=document.getElementById('leadKpiCost'); if(el) el.textContent = leadCostLabel(_leadCosts.total_usd);
  el=document.getElementById('leadKpiCostMYR'); if(el) el.textContent = leadMyrLabel(_leadCosts.total_usd);
  renderLeadSummary();
  renderLeadCompanies();
  renderLeadPeople();
}

function renderLeadSummary() {
  var box = document.getElementById('leadSummaryBox');
  if (!box) return;
  if (!_leadCompanies.length && !_leadPeople.length && !_leadSummary) {
    box.className = 'lead-empty';
    box.innerHTML = 'Lead results will appear here.';
    return;
  }
  box.className = '';
  var s = _leadSummary || {};
  var leadMix = leadLeadMixCounts(_leadCompanies);
  var cCount = leadMix.total;
  var pCount = _leadPeople.length;
  var eCount = _leadPeople.filter(function(p){ return !!(p.email || '').trim(); }).length;
  var directCount = _leadCompanies.filter(function(c){ return leadSafeUrl(c.job_url) && leadIsDirectJobUrl(c.job_url); }).length;
  var avg = cCount ? Math.round(_leadCompanies.reduce(function(a,c){ return a + leadFitPercent(c); }, 0) / cCount) : 0;
  var title = s.candidate_title || s.target_profile || document.getElementById('leadTargetRole')?.value || 'Candidate market lead summary';
  var topAction = '';
  if (_leadCompanies.length && !_leadPeople.length) topAction = '<div class="lead-smart-tip" style="margin-bottom:10px;"><strong>Next best action:</strong> Tick the best extracted job leads, then click <button class="sec" onclick="switchLeadSubtab(\'companies\');" style="padding:4px 9px;font-size:11px;">Review Job Leads</button> or run <button class="sec" onclick="switchLeadSubtab(\'people\');runLeadPeopleSearch(\'selected\');" style="padding:4px 9px;font-size:11px;">Find People for Selected</button>.</div>';
  else if (_leadPeople.length && !_leadPeople.some(function(p){ return !!p.email; })) topAction = '<div class="lead-smart-tip" style="margin-bottom:10px;"><strong>Next best action:</strong> People leads are ready. Click <button class="sec" onclick="switchLeadSubtab(\'people\');runLeadEmailSearch();" style="padding:4px 9px;font-size:11px;">Find Public Business Emails</button> only if you need public company-domain emails. No LinkedIn scraping.</div>';
  var html = topAction + '<div class="lead-dashboard">';
  html += '<div class="lead-summary-card">';
  html += '<div class="lead-summary-title">' + esc(title) + '</div>';
  html += '<div class="lead-summary-meta">';
  if (s.seniority) html += '<span class="lead-chip blue">' + esc(s.seniority) + '</span>';
  if (Array.isArray(s.regions) && s.regions.length) html += '<span class="lead-chip">📍 ' + esc(s.regions.join(', ')) + '</span>';
  if (Array.isArray(s.job_sources_used) && s.job_sources_used.length) html += '<span class="lead-chip">🔎 ' + esc(s.job_sources_used.slice(0,4).join(', ')) + (s.job_sources_used.length > 4 ? ' +' + (s.job_sources_used.length-4) : '') + '</span>';
  if (directCount) html += '<span class="lead-chip green">' + directCount + ' direct job ad link(s)</span>';
  if (leadMix && leadMix.real) html += '<span class="lead-chip green">' + leadMix.real + ' extracted lead(s)</span>';
  html += '</div>';
  if (Array.isArray(s.core_skills) && s.core_skills.length) html += '<div class="lead-summary-section"><strong>Core skills:</strong><br>' + s.core_skills.slice(0,14).map(function(x){ return '<span class="lead-chip">' + esc(x) + '</span>'; }).join(' ') + '</div>';
  if (Array.isArray(s.target_roles) && s.target_roles.length) html += '<div class="lead-summary-section"><strong>Target roles:</strong><br>' + s.target_roles.slice(0,10).map(function(x){ return '<span class="lead-chip blue">' + esc(x) + '</span>'; }).join(' ') + '</div>';
  var angles = Array.isArray(s.target_job_title_angles) ? s.target_job_title_angles : [];
  if (angles.length) html += '<div class="lead-summary-section"><strong>Job title angles searched:</strong><br>' + angles.slice(0,16).map(function(x){ return '<span class="lead-chip">' + esc(x) + '</span>'; }).join(' ') + (angles.length > 16 ? '<span class="lead-chip">+' + (angles.length-16) + ' more</span>' : '') + '</div>';
  if (s.job_filters_used) { var jf=s.job_filters_used, fb=[]; ['must_have','exclude_keywords','seniority','max_days_open','work_setup','employment_type','company_include','company_exclude'].forEach(function(k){ if(jf[k]) fb.push('<span class="lead-chip warn">' + esc(k.replace(/_/g,' ')) + ': ' + esc(jf[k]) + '</span>'); }); if(fb.length) html += '<div class="lead-summary-section"><strong>Relevance filters used:</strong><br>' + fb.join(' ') + '</div>'; }
  if (s.location_filter || s.source_strategy) html += '<div class="lead-summary-section">' + (s.location_filter ? '<strong>Location:</strong> ' + esc(s.location_filter) + '<br>' : '') + (s.source_strategy ? '<strong>Strategy:</strong> ' + esc(s.source_strategy) : '') + '</div>';
  html += '</div>';
  html += '<div class="lead-summary-card">';
  html += '<div class="lead-mini-grid">';
  html += '<div class="lead-mini-stat"><div class="v">' + (leadMix ? leadMix.real : cCount) + '</div><div class="k">Extracted Leads</div></div>';
  html += '<div class="lead-mini-stat"><div class="v">' + pCount + '</div><div class="k">People Leads</div></div>';
  html += '<div class="lead-mini-stat"><div class="v">' + avg + '%</div><div class="k">Avg Job Fit</div></div>';
  html += '<div class="lead-mini-stat"><div class="v">' + directCount + '</div><div class="k">Direct Job Links</div></div>';
  html += '</div>';
  leadRefreshTotalCost();
  html += '<div class="lead-summary-section"><strong>Cost indicator:</strong> ' + esc(leadCostLabel(_leadCosts.total_usd)) + ' / ' + esc(leadMyrLabel(_leadCosts.total_usd)) + '<br><span style="color:var(--text3);">Company: ' + esc(leadCostLabel(_leadCosts.search_usd)) + ' · People: ' + esc(leadCostLabel(_leadCosts.people_usd)) + ' · Email: ' + esc(leadCostLabel(_leadCosts.email_usd)) + '</span></div>';
  if (_leadLastWarning) html += '<div class="lead-summary-section"><span class="lead-chip warn">⚠ Note</span><br>' + esc(_leadLastWarning) + '</div>';
  html += '</div>';
  html += '</div>';
  if (_leadCompanies.length) {
    html += '<div class="lead-summary-card" style="margin-top:12px;"><strong>Top job leads:</strong><div class="lead-result-list" style="margin-top:8px;">';
    leadGetCompanyViewRows().slice(0,5).forEach(function(c){
      html += '<div style="display:flex;justify-content:space-between;gap:10px;align-items:center;border-bottom:1px solid var(--border);padding:7px 0;">';
      html += '<div><strong>' + esc(c.company || 'Unknown company') + '</strong><br><span style="color:var(--text3);font-size:11px;">' + esc(c.matched_role || c.hiring_signal || '') + '</span></div>';
      html += '<div style="display:flex;gap:6px;align-items:center;">' + leadPortalBadgeHtml(c.job_portal || '') + '<span class="lead-score">' + (Number(c.job_fit_percent || c.match_score)||0) + '%</span> <span class="lead-fresh' + leadFreshClass(c.days_open) + '">' + esc(c.job_freshness || leadFreshnessFromDays(c.days_open)) + '</span></div>';
      html += '</div>';
    });
    html += '</div></div>';
  }
  box.innerHTML = html;
}

function renderLeadCompanies() {
  var box = document.getElementById('leadCompaniesBox');
  if (!box) return;
  var st = document.getElementById('leadCompanyStatus');
  leadPruneSelectedCompanies();
  if (!_leadCompanies.length) { if(st) st.textContent=''; leadUpdateSelectedChip(); box.className='lead-empty'; box.innerHTML='Job leads will appear here.'; return; }
  var viewRows = leadGetCompanyViewRows();
  var selectedCount = leadSelectedCompanyCount();
  if (!viewRows.length) { if(st) st.textContent='0 of ' + _leadCompanies.length + ' job leads shown · ' + selectedCount + ' selected'; leadUpdateSelectedChip(); box.className='lead-empty'; box.innerHTML='No job leads match the current filter. Clear the search/filter controls above to see all leads.'; return; }
  var mix = leadLeadMixCounts(viewRows);
  if(st) st.textContent = viewRows.length + ' of ' + _leadCompanies.length + ' extracted leads shown · ' + selectedCount + ' selected';
  box.className = 'lead-result-list';
  var html = '';
  viewRows.forEach(function(c, idx){
    var fit = leadFitPercent(c);
    var fresh = c.job_freshness || leadFreshnessFromDays(c.days_open);
    var daysText = (c.days_open !== undefined && c.days_open !== null && c.days_open !== '') ? esc(c.days_open) + ' day(s)' : 'Days open unknown';
    var cid = leadCompanyId(c, idx);
    var checked = !!_leadSelectedCompanyIds[cid];
    var jobDirect = leadSafeUrl(c.job_url) && leadIsDirectJobUrl(c.job_url);
    var isFallbackSearch = String(c.lead_kind || '').toLowerCase() === 'fallback_search_link';
    var needsVerify = leadIsNeedsVerificationLead(c);
    html += '<div class="lead-company-card ' + (checked ? 'selected' : '') + (isFallbackSearch ? ' fallback' : '') + (needsVerify ? ' needs-verify' : '') + '">';
    html += '<div class="lead-card-top">';
    html += '<div class="lead-card-main">';
    html += '<div class="lead-card-title">' + esc(c.company || 'Unknown company') + '</div>';
    html += '<div class="lead-card-sub">' + esc(c.country || c.region || '') + (c.industry ? ' · ' + esc(c.industry) : '') + '</div>';
    html += '<div class="lead-summary-meta" style="margin-bottom:0;">' + leadPortalBadgeHtml(c.job_portal || '') + (isFallbackSearch ? '<span class="lead-chip warn">Fallback search link</span>' : '') + (needsVerify ? '<span class="lead-chip warn">Needs verification</span>' : '') + '<span class="lead-score">' + esc(fit) + '% fit</span><span class="lead-chip ' + leadFitReviewLabel(fit).cls + '">' + esc(leadFitReviewLabel(fit).text) + '</span><span class="lead-fresh' + leadFreshClass(c.days_open) + '">' + esc(fresh || 'Unknown') + '</span><span class="lead-chip">' + daysText + '</span>' + (jobDirect ? '<span class="lead-chip green">Direct job ad</span>' : (needsVerify ? '<span class="lead-chip warn">Review source</span>' : '<span class="lead-chip warn">No direct job ad URL</span>')) + '</div>';
    html += '</div>';
    html += '<div class="lead-card-actions">' + leadJobActionHtml(c) + '</div>';
    html += '</div>';
    html += '<div class="lead-card-bodyline"><strong>' + esc(c.matched_role || 'Matched role') + '</strong>' + (c.hiring_signal ? '<br>' + esc(c.hiring_signal) : '') + '</div>';
    if (c.why_matched) html += '<div class="lead-card-bodyline"><strong>Why matched:</strong> ' + esc(c.why_matched) + '</div>';
    html += '<div class="lead-card-footer">';
    if (isFallbackSearch) html += '<span class="lead-card-check" style="color:var(--text3);">Fallback link — open/review manually before people search</span>';
    else html += '<label class="lead-card-check"><input type="checkbox" class="lead-check" ' + (checked ? 'checked ' : '') + 'onclick="leadToggleCompanySelection(\'' + escJsAttr(cid) + '\', this.checked); renderLeadCompanies();" /> Select for people search</label>';
    html += '<span style="color:var(--text3);font-size:11px;">Posted: ' + esc(c.date_posted || 'Unknown') + (c.source_note ? ' · ' + esc(c.source_note).slice(0,120) : '') + '</span>';
    html += '</div>';
    html += '</div>';
  });
  box.innerHTML = html;
  leadUpdateSelectedChip();
}

function renderLeadPeople() {
  var box = document.getElementById('leadPeopleBox');
  if (!box) return;
  var stp = document.getElementById('leadPeopleStatus');
  if (!_leadPeople.length) { if(stp && stp.getAttribute('data-busy') !== '1') stp.textContent=''; box.className='lead-empty'; box.innerHTML='People leads will appear here and are saved in this tab.'; return; }
  var viewRows = leadGetPeopleViewRows();
  if (!viewRows.length) { if(stp && stp.getAttribute('data-busy') !== '1') stp.textContent='0 of ' + _leadPeople.length + ' people leads shown'; box.className='lead-empty tight'; box.innerHTML='No people leads match the current filter. Clear the search/filter controls above to see all leads.'; return; }
  if(stp && !/^People search done|Email search done|Searching|Error:/i.test(stp.textContent || '')) stp.textContent = viewRows.length + ' of ' + _leadPeople.length + ' people leads shown';
  box.className = 'lead-result-list';
  var html = '';
  viewRows.forEach(function(p, idx){
    var pid = leadPersonId(p, idx);
    var checked = !!_leadSelectedPersonIds[pid];
    var ctype = String(p.contact_type || '').toLowerCase();
    var cls = ctype.indexOf('hr') >= 0 || ctype.indexOf('talent') >= 0 || ctype.indexOf('recruit') >= 0 || ctype.indexOf('people') >= 0 ? 'hr' : 'hm';
    var url = leadSafeUrl(p.profile_url || p.source_url || '');
    html += '<div class="lead-contact-card">';
    html += '<div class="lead-card-top">';
    html += '<div class="lead-contact-head"><div class="lead-contact-avatar">' + esc(leadInitials(p.name || '')) + '</div><div class="lead-card-main">';
    html += '<div class="lead-card-title">' + esc(p.name || 'Unknown person') + '</div>';
    html += '<div class="lead-card-sub">' + esc(p.title || '') + '</div>';
    html += '<div class="lead-summary-meta" style="margin-bottom:0;"><span class="lead-badge ' + cls + '">' + esc(p.contact_type || 'Hiring contact') + '</span><span class="lead-chip">' + esc(p.company || '') + '</span>' + (p.country ? '<span class="lead-chip">📍 ' + esc(p.country) + '</span>' : '') + '</div>';
    html += '</div></div>';
    html += '<div class="lead-card-actions">' + (url ? '<a class="lead-link-btn" href="' + escAttr(url) + '" target="_blank" rel="noopener">↗ Open Profile</a>' : '<span class="lead-link-btn disabled">No profile link</span>') + '</div>';
    html += '</div>';
    if (!p.email) html += '<label class="lead-card-check"><input type="checkbox" class="lead-check" ' + (checked ? 'checked ' : '') + 'onclick="leadTogglePersonSelection(\'' + escJsAttr(pid) + '\', this.checked); renderLeadPeople();" /> Select for email search</label>';
    if (p.email) html += '<div class="lead-card-bodyline"><span class="lead-badge email">' + esc(p.email) + '</span> <span style="color:var(--text3);">' + esc(p.email_confidence || '') + '</span></div>';
    else html += '<div class="lead-card-bodyline"><span style="color:var(--text3);">No public business email found yet</span></div>';
    if (p.notes) html += '<div class="lead-card-bodyline"><strong>Evidence / note:</strong> ' + esc(p.notes) + '</div>';
    html += '<div class="lead-card-footer"><span style="color:var(--text3);font-size:11px;">' + esc(p.verification_status || p.status || '') + '</span>' + (p.source_url ? '<span style="color:var(--text3);font-size:11px;overflow-wrap:anywhere;">Source: ' + esc(p.source_url).slice(0,120) + '</span>' : '') + '</div>';
    html += '</div>';
  });
  box.innerHTML = html;
  var emailBtn = document.getElementById('btnLeadEmailSearch');
  if (emailBtn) {
    var selCount = leadSelectedPersonCount();
    emailBtn.textContent = selCount ? ('✉ Find Public Business Emails (' + selCount + ' selected)') : '✉ Find Public Business Emails (all)';
  }
}

function escAttr(s) {
  return esc(s).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function jsStrEscape(s) {
  return String(s == null ? '' : s)
    .replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"')
    .replace(/\n/g, '\\n').replace(/\r/g, '\\r')
    .replace(/\u2028/g, '\\u2028').replace(/\u2029/g, '\\u2029');
}
function escJsAttr(s) {
  // Safe for a value placed inside a JS string literal that itself sits inside an
  // inline HTML handler attribute, e.g. onclick="fn('VALUE')". The browser
  // HTML-decodes the attribute before the JS runs, so HTML-escaping alone
  // (escAttr) lets an entity like &#39; decode back to a quote and break out of
  // the JS string. JS-escape first, then HTML-escape for the attribute layer.
  return escAttr(jsStrEscape(s));
}

function leadIsDirectJobUrl(url) {
  url = String(url || '').trim();
  if (!/^https?:\/\//i.test(url)) return false;
  var a;
  try { a = new URL(url); } catch(e) { return false; }
  var host = (a.hostname || '').toLowerCase();
  var path = (a.pathname || '').toLowerCase();
  var q = (a.search || '').toLowerCase();
  if (!host || path === '' || path === '/') return false;
  if (host.indexOf('linkedin.com') >= 0) return path.indexOf('/jobs/view') >= 0 || (path.indexOf('/jobs/collections/recommended') >= 0 && /(^|[?&])currentjobid=\d+/.test(q));
  if (host.indexOf('jobstreet') >= 0 || host.indexOf('jobsdb') >= 0) {
    if (/(\/career-advice|\/career-guide|\/careers-advice|\/salary-guide|\/salary-guides|\/salary-report|\/salary-centre|\/salary-center|\/career-resources|\/resources\/|\/trends\/|\/blog\/|\/articles\/|\/news\/|\/insights\/|\/help\/|\/faq)/.test(path)) return false;
    if (/^\/(companies|my-activity|profile|sign-in|login|register|account|saved-jobs|saved|applied-jobs|applied|applications)(\/|$)/.test(path)) return false;
    if (/(^|[?&])job[_-]?id=\d+/.test(q)) return true;
    if (/\/(jobs|job-search)\//.test(path) || /-jobs(\/|$)/.test(path)) return false;
    var jsLeaf = path.replace(/\/+$/,'').split('/').pop();
    if (/^(jobs?|careers?|vacancies|positions|openings|search|listings?|in-[a-z0-9-]+|page-?\d+)$/i.test(jsLeaf || '')) return false;
    return path.replace(/^\/+|\/+$/g,'').length >= 8;
  }
  if (host.indexOf('indeed') >= 0) return path.indexOf('/viewjob') >= 0 || (/^\/(rc\/clk|pagead\/clk)\/?$/.test(path) && /(^|[?&])jk=[^&]+/.test(q));
  if (host.indexOf('glassdoor') >= 0) return path.indexOf('job-listing') >= 0 || q.indexOf('jl=') >= 0;
  if (host.indexOf('hiredly') >= 0) return path.indexOf('/jobs/') >= 0 && path.replace(/^\/+|\/+$/g,'').length > 4;
  if (host.indexOf('mycareersfuture') >= 0) return path.indexOf('/job/') >= 0;
  if (host.indexOf('kalibrr') >= 0) return path.indexOf('/jobs/') >= 0 || path.indexOf('/job/') >= 0;
  if (host.indexOf('monster') >= 0 || host.indexOf('foundit') >= 0) return path.indexOf('/job/') >= 0 || q.indexOf('jobid') >= 0;
  var ats = ['greenhouse.io','lever.co','ashbyhq.com','workdayjobs.com','myworkdayjobs.com','smartrecruiters.com','bamboohr.com','icims.com','jobvite.com','workable.com','successfactors','recruitee.com','comeet.co','oraclecloud.com','brassring.com','jobadder.com','pinpointhq.com','teamtailor.com','personio.com'];
  if (ats.some(function(h){ return host.indexOf(h) >= 0; })) return path.replace(/^\/+|\/+$/g,'').length > 8 && !/(jobs|careers|search|openings)\/?$/.test(path);
  if (/(jobid|job_id|job=|reqid|req_id|requisition|gh_jid|currentjobid)=/.test(q)) return true;
  if (/(\/job\/|\/jobs\/|\/career\/|\/careers\/|\/vacancy\/|\/vacancies\/|\/position\/|\/positions\/|\/opening\/|\/openings\/|\/role\/|\/roles\/)/.test(path)) {
    var leaf = path.replace(/\/+$/,'').split('/').pop();
    return leaf && leaf.length >= 5 && !/^(jobs?|careers?|vacancies|positions|openings|search|listings?)$/.test(leaf);
  }
  return false;
}

function leadJobActionHtml(c) {
  var job = leadSafeUrl(c && c.job_url);
  var src = leadSafeUrl(c && (c.source_url || c.company_url || c.job_url));
  if (job && leadIsDirectJobUrl(job)) return '<a class="lead-link-btn" href="' + escAttr(job) + '" target="_blank" rel="noopener">↗ Open Job Ad</a>';
  if (src && leadIsNeedsVerificationLead(c)) return '<a class="lead-link-btn secondary" href="' + escAttr(src) + '" target="_blank" rel="noopener">↗ Verify Source</a>';
  if (src) return '<a class="lead-link-btn secondary" href="' + escAttr(src) + '" target="_blank" rel="noopener">↗ Source / Search</a>';
  return '<span class="lead-link-btn disabled">No direct link</span>';
}

function leadInitials(name) {
  name = String(name || '').trim();
  if (!name) return '?';
  var parts = name.split(/\s+/).filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0,2).toUpperCase();
  return (parts[0][0] + parts[parts.length-1][0]).toUpperCase();
}

function leadSafeUrl(url) {
  url = String(url || '').trim();
  if (!/^https?:\/\//i.test(url)) return '';
  return url;
}

function leadRows(type) {
  return type === 'people' ? _leadPeople : _leadCompanies;
}

function leadHeaders(type) {
  if (type === 'people') return ['name','title','company','country','contact_type','profile_url','email','email_confidence','email_source','verification_status','source_url','notes','status'];
  return ['lead_kind','company','country','region','job_portal','industry','matched_role','hiring_signal','job_fit_percent','match_score','date_posted','days_open','job_freshness','job_url','job_url_quality','company_url','why_matched','source_url','source_note','date_found'];
}

function toCsv(rows, headers) {
  var out = [headers.join(',')];
  rows.forEach(function(row){
    out.push(headers.map(function(h){
      var v = row && row[h] != null ? String(row[h]) : '';
      v = v.replace(/"/g, '""');
      return '"' + v + '"';
    }).join(','));
  });
  return out.join('\n');
}

function downloadLeadCsv(type) {
  var rows = leadRows(type);
  if (!rows.length) { showToast('No ' + type + ' leads to export', 'err'); return; }
  var headers = leadHeaders(type);
  var csv = toCsv(rows, headers);
  var blob = new Blob(['\ufeff' + csv], {type:'text/csv;charset=utf-8;'});
  var a = document.createElement('a');
  var url = URL.createObjectURL(blob);
  a.href = url;
  a.download = 'Hyppies Lead Finder - ' + (type === 'people' ? 'People Leads' : 'Job Leads') + ' - ' + new Date().toISOString().slice(0,10) + '.csv';
  a.click();
  setTimeout(function(){ URL.revokeObjectURL(url); }, 1000);
}

function copyLeadCompanies() {
  if (!_leadCompanies.length) { showToast('No job leads to copy', 'err'); return; }
  navigator.clipboard.writeText(toCsv(_leadCompanies, leadHeaders('companies')));
  showToast('Job leads copied', 'ok');
}

function copyLeadPeople() {
  if (!_leadPeople.length) { showToast('No people leads to copy', 'err'); return; }
  navigator.clipboard.writeText(toCsv(_leadPeople, leadHeaders('people')));
  showToast('People leads copied', 'ok');
}

function saveLeadSnapshot() {
  try {
    localStorage.setItem('hyppies_lead_finder_snapshot', JSON.stringify({ companies:_leadCompanies, people:_leadPeople, summary:_leadSummary, warning:_leadLastWarning, costs:_leadCosts, selected_company_ids:Object.keys(_leadSelectedCompanyIds||{}), saved_at:new Date().toISOString() }));
    document.getElementById('leadExportStatus').textContent = 'Snapshot saved locally in this browser.';
    showToast('Lead snapshot saved', 'ok');
  } catch(e) { showToast('Could not save snapshot', 'err'); }
}

function loadLeadSnapshot() {
  try {
    var raw = localStorage.getItem('hyppies_lead_finder_snapshot');
    if (!raw) { showToast('No saved snapshot found', 'err'); return; }
    var d = JSON.parse(raw);
    var normalizedSnapshot = normalizeLeadData({ companies: Array.isArray(d.companies) ? d.companies : [], people: Array.isArray(d.people) ? d.people : [], summary: d.summary || null, warning: d.warning || '' });
    _leadCompanies = normalizedSnapshot.companies;
    _leadPeople = normalizedSnapshot.people;
    _leadSummary = normalizedSnapshot.summary;
    _leadLastWarning = d.warning || '';
    _leadCosts = d.costs || { search_usd:0, people_usd:0, email_usd:0, total_usd:0, search_tokens:0, people_tokens:0, email_tokens:0, model:'' };
    _leadCosts.people_usd = Number(_leadCosts.people_usd) || 0;
    _leadCosts.people_tokens = Number(_leadCosts.people_tokens) || 0;
    _leadSelectedCompanyIds = {};
    if (Array.isArray(d.selected_company_ids)) { d.selected_company_ids.forEach(function(id){ if (id) _leadSelectedCompanyIds[String(id)] = true; }); }
    leadRefreshTotalCost();
    renderLeadFinder();
    document.getElementById('leadExportStatus').textContent = 'Snapshot loaded.';
    showToast('Lead snapshot loaded', 'ok');
  } catch(e) { showToast('Could not load snapshot', 'err'); }
}

function clearLeadFinder() {
  clearTabRunState('leadfinder');
  clearLeadFile();
  _leadCompanies = [];
  _leadSelectedCompanyIds = {};
  _leadPeople = [];
  _leadSummary = null;
  _leadLastWarning = '';
  _leadCosts = { search_usd:0, people_usd:0, email_usd:0, total_usd:0, search_tokens:0, people_tokens:0, email_tokens:0, model:'' };
  ['leadCvText','leadTargetRole','leadContext','leadIndustries','leadExtraCountries','leadCompanyFilter','leadPeopleFilter','leadMustHave','leadExcludeKeywords','leadCompanyInclude','leadCompanyExclude'].forEach(function(id){ var el=document.getElementById(id); if(el) el.value=''; });
  ['leadSeniorityFilter','leadFreshnessFilter','leadWorkSetupFilter','leadEmploymentFilter'].forEach(function(id){ var el=document.getElementById(id); if(el) el.value=''; });
  ['leadOnlyHighFit','leadOnlyFresh'].forEach(function(id){ var el=document.getElementById(id); if(el) el.checked=false; });
  var cs=document.getElementById('leadCompanySort'); if(cs) cs.value='fit';
  var psort=document.getElementById('leadPeopleSort'); if(psort) psort.value='email';
  leadUpdateCvCount();
  leadUpdateRegionPreview();
  var s=document.getElementById('leadSearchStatus'); if(s){ s.textContent=''; s.className='lead-status'; }
  var ps=document.getElementById('leadPeopleStatus'); if(ps){ ps.textContent=''; ps.className='lead-status'; }
  var csStatus=document.getElementById('leadCompanyStatus'); if(csStatus){ csStatus.textContent=''; csStatus.className='lead-status'; }
  var exStatus=document.getElementById('leadExportStatus'); if(exStatus){ exStatus.textContent=''; exStatus.className='lead-status'; }
  renderLeadFinder();
}
