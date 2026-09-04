// ── Company Profile Export ────────────────────────────────────────────
async function exportCompanyDoc() {
  var p = window._lastCompanyProfile;
  if (!p) { showToast('Generate a profile first', 'err'); return; }
  function arr(v) { return Array.isArray(v) ? v : (v ? [String(v)] : []); }
  function narrativeParts(v) {
    var raw = String(v || '').split(/\r?\n+/).map(function(x){ return x.trim(); }).filter(Boolean);
    var hadMarkers = raw.some(function(x){ return /^([\u2022\-*]|\d+[.)])\s+/.test(x); });
    var lines = raw.map(function(x){ return x.replace(/^([\u2022\-*]|\d+[.)])\s+/, '').trim(); }).filter(Boolean);
    if (!lines.length) return { intro:'', bullets:[] };
    if (lines.length <= 2 && !hadMarkers) return { intro: lines.join(' '), bullets: [] };
    return { intro: lines[0] || '', bullets: lines.slice(1) };
  }
  function narrativeDoc(v) {
    var n = narrativeParts(v);
    var out = '';
    if (n.intro) out += '<p style="font-size:11.5pt;line-height:1.68;color:#333;margin:0 0 12px">'+_escDoc(n.intro)+'</p>';
    if (n.bullets.length) out += '<ul style="margin-top:0;margin-bottom:18px">'+n.bullets.map(function(b){return '<li>'+_escDoc(b)+'</li>';}).join('')+'</ul>';
    return out;
  }
  var meta = [p.hq, p.industry, p.website].filter(function(x){return x&&x!=='null';}).join('  |  ');
  var stats = arr(p.stats).filter(function(s){return s&&s.val&&s.val!=='null';}).slice(0,4)
    .map(function(s){ return '<td style="text-align:center;padding:12px 10px;border-right:1px solid #e5e7eb;word-break:break-word;overflow-wrap:anywhere;vertical-align:middle"><div style="font-size:13.5pt;line-height:1.15;font-weight:700;color:#352a86">'+_escDoc(s.val)+'</div><div style="font-size:8pt;line-height:1.25;color:#6b7280;margin-top:4px;">'+_escDoc(s.lbl)+'</div></td>'; }).join('');
  var tags = arr(p.tags).map(function(t){ return '<span class="chip">'+_escDoc(t)+'</span>'; }).join(' ');
  var body = ''
    + (tags ? '<p style="margin-top:0">'+tags+'</p>' : '')
    + (stats ? '<table style="width:100%;table-layout:fixed;border-collapse:collapse;background:#fbfbfd;border:1px solid #e6e8ef;border-radius:10px;margin:4px 0 22px"><tr>'+stats+'</tr></table>' : '')
    + (p.narrative&&p.narrative!=='null' ? narrativeDoc(p.narrative) : '')
    + (arr(p.about).length ? '<h2>About</h2><ul>'+arr(p.about).map(function(b){return '<li>'+_escDoc(b)+'</li>';}).join('')+'</ul>' : '')
    + (arr(p.culture).length ? '<h2>Culture &amp; Values</h2><ul>'+arr(p.culture).map(function(b){return '<li>'+_escDoc(b)+'</li>';}).join('')+'</ul>' : '')
    + (arr(p.tech_stack).length ? '<h2>Tech Stack</h2><p>'+arr(p.tech_stack).map(function(t){return '<span class="chip">'+_escDoc(t)+'</span>';}).join(' ')+'</p>' : '')
    + (arr(p.why_join).length ? '<div class="callout"><h2 style="margin-top:0;border-bottom:0;padding-bottom:0">Why Join</h2><ul>'+arr(p.why_join).map(function(b){return '<li>'+_escDoc(b)+'</li>';}).join('')+'</ul></div>' : '');
  var html = _wordDocShell(p.company_name||'Company Profile', meta||'Hyppies', body);
  var output = await exportWordDocumentToDestination(html, 'company-profile-'+_safeFileStem(p.company_name), 'company_profile');
  cvStudioShowDownloadResult(output.result, 'Company Profile Word .' + output.format);
}

async function exportCompanyPDF() {
  var p = window._lastCompanyProfile;
  if (!p) { showToast('Generate a profile first', 'err'); return; }
  if (!(window.jspdf && window.jspdf.jsPDF)) {
    if (window.cvStudioLoadJSPDF) window.cvStudioLoadJSPDF(exportCompanyPDF, function() { showToast('PDF library not loaded — try Word export instead', 'err'); });
    else showToast('PDF library not loaded — try Word export instead', 'err');
    return;
  }
  function arr(v) { return Array.isArray(v) ? v : (v ? [String(v)] : []); }
  var jsPDF = window.jspdf.jsPDF;
  var doc = new jsPDF({unit:'mm',format:'a4'});
  var margin=18,pageW=210,maxW=pageW-margin*2,lh=5.6,y=margin;
  var C={purple:[53,42,134],text:[25,27,34],muted:[92,99,115],dim:[145,151,165],
         hairline:[226,229,236],soft:[248,249,252],green:[22,101,52],greenBg:[240,253,244],
         greenAc:[34,197,94],blue:[24,95,165],blueBg:[231,242,253],purpleBg:[245,243,255]};
  function safe(s){return cvPdfSafeText(s);}
  function checkPage(n){if(y+(n||12)>276){doc.addPage();pageHdr2();y=24;}}
  function pageHdr2(){doc.setFillColor(255,255,255);doc.rect(0,0,210,16,'F');try{doc.addImage(HYPPIES_LOGO_URI,'JPEG',margin,4,9,9);}catch(e){}doc.setFont('helvetica','bold');doc.setFontSize(7.5);doc.setTextColor(...C.purple);doc.text('Hyppies',margin+13,9.5);doc.setFont('helvetica','normal');doc.setFontSize(7);doc.setTextColor(...C.dim);doc.text(new Date().toLocaleDateString('en-MY'),pageW-margin,9.5,{align:'right'});doc.setDrawColor(...C.hairline);doc.line(margin,15,pageW-margin,15);}
  function secHdr(t,bg,fg,reserve){checkPage(15+(reserve||0));y+=4;doc.setFillColor(...(bg||C.soft));doc.roundedRect(margin-1,y-5,maxW+2,9,2,2,'F');doc.setFont('helvetica','bold');doc.setFontSize(8);doc.setTextColor(...(fg||C.purple));doc.text(safe(t).toUpperCase(),margin+2,y+1.2);y+=11;}
  function splitWithFont(t,w,style,size){doc.setFont('helvetica',style||'normal');doc.setFontSize(size||9.2);return doc.splitTextToSize(safe(t),w);}
  function firstBulletReserve(arr){arr=(arr||[]).filter(Boolean);if(!arr.length)return 0;return splitWithFont(arr[0],maxW-8,'normal',9.2).length*lh+7;}
  function bul(text,dot){var lines=splitWithFont(text,maxW-8,'normal',9.2);checkPage(lines.length*lh+3);doc.setFillColor(...dot);doc.circle(margin+2,y-1,1.15,'F');doc.setFont('helvetica','normal');doc.setFontSize(9.2);doc.setTextColor(...C.text);doc.text(lines,margin+7,y);y+=lines.length*lh+2.5;}
  function para(t,col){var lines=splitWithFont(t,maxW,'normal',9.3);checkPage(lines.length*lh+3);doc.setFont('helvetica','normal');doc.setFontSize(9.3);doc.setTextColor(...(col||C.text));doc.text(lines,margin,y);y+=lines.length*lh+3;}
  function narrativeParts(v){
    var raw=String(v||'').split(/\r?\n+/).map(function(x){return x.trim();}).filter(Boolean);
    var hadMarkers=raw.some(function(x){return /^([\u2022\-*]|\d+[.)])\s+/.test(x);});
    var lines=raw.map(function(x){return x.replace(/^([\u2022\-*]|\d+[.)])\s+/,'').trim();}).filter(Boolean);
    if(!lines.length)return{intro:'',bullets:[]};
    if(lines.length<=2&&!hadMarkers)return{intro:lines.join(' '),bullets:[]};
    return{intro:lines[0]||'',bullets:lines.slice(1)};
  }
  function writeNarrative(v){var n=narrativeParts(v);if(!n.intro&&!n.bullets.length)return;if(n.intro)para(n.intro);if(n.bullets.length){y+=1;n.bullets.forEach(function(b){bul(b,C.blue);});y+=2;}}

  // Header
  doc.setFillColor(255,255,255);doc.rect(0,0,210,38,'F');
  try{doc.addImage(HYPPIES_LOGO_URI,'JPEG',margin,6,23,23);}catch(e){}
  doc.setFont('helvetica','bold');doc.setFontSize(15);doc.setTextColor(...C.purple);
  var titleLines=doc.splitTextToSize(safe(p.company_name||'Company Profile'),132);
  doc.text(titleLines,margin+30,13);
  doc.setFont('helvetica','normal');doc.setFontSize(8);doc.setTextColor(...C.muted);
  var meta=[p.hq,p.industry,p.website].filter(function(x){return x&&x!=='null';}).join('  |  ');
  doc.text(safe(meta||'Hyppies'),margin+30,13+titleLines.length*6+2);
  doc.setDrawColor(...C.hairline);doc.setLineWidth(0.35);doc.line(margin,35,pageW-margin,35);
  y=44;

  // Stats row - wrap long values/labels so 4 tiles do not overlap.
  var stats=arr(p.stats).filter(function(s){return s&&s.val&&s.val!=='null';}).slice(0,4);
  if(stats.length){
    var colW=maxW/stats.length;
    var statRows=stats.map(function(s){
      var vLines=splitWithFont(s.val,colW-5,'bold',10.7);
      if(vLines.length>2)vLines=splitWithFont(s.val,colW-5,'bold',9.4);
      var lLines=splitWithFont(s.lbl,colW-6,'normal',7.0);
      return{v:vLines,l:lLines};
    });
    var maxVal=Math.max.apply(null,statRows.map(function(x){return x.v.length;}));
    var maxLbl=Math.max.apply(null,statRows.map(function(x){return x.l.length;}));
    var rowH=Math.max(24,8+(maxVal*4.9)+(maxLbl*3.7)+5);
    doc.setFillColor(...C.soft);doc.roundedRect(margin-1,y-2,maxW+2,rowH,2,2,'F');
    statRows.forEach(function(sr,i){
      var cx=margin+colW*i+colW/2;
      doc.setFont('helvetica','bold');doc.setFontSize(sr.v.length>2?9.4:10.7);doc.setTextColor(...C.purple);
      doc.text(sr.v,cx,y+7,{align:'center'});
      doc.setFont('helvetica','normal');doc.setFontSize(7.0);doc.setTextColor(...C.muted);
      doc.text(sr.l,cx,y+7+(sr.v.length*4.9)+2.8,{align:'center'});
    });
    y+=rowH+6;
  }

  // Tags
  var tags=arr(p.tags);
  if(tags.length){var tx=margin;doc.setFont('helvetica','bold');doc.setFontSize(7.3);tags.forEach(function(tag){var text=safe(tag),tw=Math.min(doc.getTextWidth(text)+8,58);if(tx+tw>pageW-margin){tx=margin;y+=9;}doc.setFillColor(...C.blueBg);doc.roundedRect(tx,y,tw,6.8,2,2,'F');doc.setFont('helvetica','bold');doc.setFontSize(7.3);doc.setTextColor(...C.blue);doc.text(text,tx+4,y+4.7);tx+=tw+4;});y+=13;}

  if(p.narrative&&p.narrative!=='null')writeNarrative(p.narrative);
  if(arr(p.about).length){secHdr('About',C.greenBg,C.green,firstBulletReserve(arr(p.about)));arr(p.about).forEach(function(b){bul(b,C.greenAc);});y+=2;}
  if(arr(p.culture).length){secHdr('Culture & Values',C.blueBg,C.blue,firstBulletReserve(arr(p.culture)));arr(p.culture).forEach(function(b){bul(b,C.blue);});y+=2;}
  if(arr(p.tech_stack).length){var tl=splitWithFont(arr(p.tech_stack).join('  |  '),maxW,'bold',8.8);secHdr('Tech Stack',C.purpleBg,C.purple,tl.length*lh+7);doc.setFont('helvetica','bold');doc.setFontSize(8.8);doc.setTextColor(...C.purple);doc.text(tl,margin,y);y+=tl.length*lh+6;}
  if(arr(p.why_join).length){secHdr('Why Join',C.greenBg,C.green,firstBulletReserve(arr(p.why_join)));arr(p.why_join).forEach(function(b){bul(b,C.greenAc);});y+=2;}

  var total=doc.internal.getNumberOfPages();
  for(var pg=1;pg<=total;pg++){doc.setPage(pg);doc.setDrawColor(...C.hairline);doc.setLineWidth(0.25);doc.line(margin,284,pageW-margin,284);doc.setFont('helvetica','normal');doc.setFontSize(7.5);doc.setTextColor(...C.dim);doc.text('Hyppies  |  Confidential  |  For candidate use only',margin,290);doc.text('Page '+pg+' of '+total,pageW-margin,290,{align:'right'});}
  var filename = 'company-profile-'+_safeFileStem(p.company_name)+'-'+new Date().toISOString().slice(0,10)+'.pdf';
  var result = await cvStudioSaveDownloadBlob(doc.output('blob'), filename, 'company_profile');
  cvStudioShowDownloadResult(result, 'Company Profile PDF');
}

// ── Company Profile Tab ───────────────────────────────────────────────
var _companyLen   = 'concise';
var _companyTone  = 'professional';
var _companyFocus = 'general';

function setCompanyOpt(type, btn) {
  var prefix = 'company' + (type === 'len' ? 'Len' : type === 'tone' ? 'Tone' : 'Focus') + '_';
  document.querySelectorAll('[data-p'+type+']').forEach(function(b) {
    b.style.background=''; b.style.color=''; b.style.borderColor='';
  });
  btn.style.background='var(--blue)'; btn.style.color='#fff'; btn.style.borderColor='var(--blue)';
  if (type === 'len')   _companyLen   = btn.dataset.plen;
  if (type === 'tone')  _companyTone  = btn.dataset.ptone;
  if (type === 'focus') _companyFocus = btn.dataset.pfocus;
}


async function fetchCompanyUrl() {
  var urlEl = document.getElementById('companyUrl');
  var url = urlEl ? (urlEl.value || '').trim() : '';
  if (!url) { showToast('Enter a company website or LinkedIn URL first', 'err'); return; }
  var route = aiRoutePayload('company_profile');
  if (!route.api_key) { showToast('Save an API key for Company Profile route', 'err'); return; }
  var statusEl = document.getElementById('companyUrlStatus');
  var btn = document.getElementById('companyFetchBtn');
  if (statusEl) statusEl.textContent = '⏳ Fetching content…';
  if (btn) btn.disabled = true;
  var _tabRun = markTabRunning('company');
  try {
    var prompt = [
      'Fetch or summarise the publicly available company information for this URL and return useful plain text for a recruiter company briefing.',
      'Remove navigation, ads, cookie banners, generic footers, and boilerplate. Keep business description, scale, products, culture, locations, awards, technologies, and candidate-relevant facts.',
      'Return plain text only, no markdown fences.',
      'URL: ' + url
    ].join('\n');
    var data = await callAIProxy(prompt, 2500, true, 5, 'company_profile');
    var fetched = aiText(data).trim();
    if (!fetched || fetched.length < 50) {
      recordPaidAiFailure('Company URL Fetch returned insufficient output', data, route.model, route.provider);
      throw new Error('Could not extract enough content');
    }
    var ta = document.getElementById('companyText');
    var existing = (ta.value || '').trim();
    ta.value = existing ? (existing + '\n\n' + fetched) : fetched;
    if (statusEl) { statusEl.textContent = '✓ Content fetched — review below then click Generate Profile'; statusEl.style.color = 'var(--blue)'; }
    if (data.usage || data.cost_details) { var cUrlRoute = aiRoutePayload('company_profile'); statsRecord('Company URL Fetch', 'company', responseCost(data, cUrlRoute.model, cUrlRoute.provider), data.model || cUrlRoute.model, '', data.provider || cUrlRoute.provider, statsMetaFromResponse(data, cUrlRoute.model, cUrlRoute.provider)); }
    markTabDone('company', _tabRun);
  } catch(e) {
    if (statusEl) { statusEl.textContent = '✕ Fetch failed: ' + e.message; statusEl.style.color = 'var(--red)'; }
    markTabFailed('company', _tabRun);
    showToast('Fetch failed: ' + e.message, 'err');
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function handleCompanyFile(file) {
  if (!file) return;
  var nameEl = document.getElementById('companyFileName');
  var zone   = document.getElementById('companyDropZone');
  nameEl.textContent = '⏳ Extracting…';
  zone.style.opacity = '0.6';
  var _tabRun = markTabRunning('company');
  try {
    var fd = new FormData(); fd.append('file', file);
    var r  = await fetchWithTimeout('/extract-text', { method: 'POST', body: fd }, CV_EXTRACT_TEXT_TIMEOUT_MS);
    var d  = await r.json();
    if (d.error) throw new Error(d.error);
    var extractionWarning = cvShowExtractionWarning(d);
    var text = anonNormalizeExtractedTextArtifacts(d.text || '').trim();
    document.getElementById('companyText').value = text;
    nameEl.textContent = (extractionWarning ? '⚠ ' : '✓ ') + file.name + ' (' + text.length.toLocaleString() + ' chars)' + (extractionWarning ? ' — partial extraction; review text' : '');
    markTabDone('company', _tabRun);
  } catch(e) {
    nameEl.textContent = '✕ Failed: ' + e.message;
    markTabFailed('company', _tabRun);
    showToast('Extraction failed: ' + e.message, 'err');
  } finally {
    zone.style.opacity = '';
  }
}

function handleCompanyDrop(e) {
  e.preventDefault();
  document.getElementById('companyDropZone').style.borderColor = 'var(--border)';
  var file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
  if (file) handleCompanyFile(file);
}

function clearCompanyProfile() {
  clearTabRunState('company');
  document.getElementById('companyText').value = '';
  document.getElementById('companyFileName').textContent = '';
  document.getElementById('companyContext').value = '';
  var companyUrl = document.getElementById('companyUrl'); if (companyUrl) companyUrl.value = '';
  var companyUrlStatus = document.getElementById('companyUrlStatus'); if (companyUrlStatus) companyUrlStatus.textContent = '';
  document.getElementById('companyOutput').style.display = 'none';
  var phCompanyClear = document.getElementById('companyPlaceholder'); if (phCompanyClear) phCompanyClear.style.display = 'flex';
  document.getElementById('companyStatus').textContent = '';
  document.getElementById('companyOutputTitle').textContent = 'Company Profile';
  var companyCost = document.getElementById('companyCost'); if (companyCost) companyCost.textContent = '';
  var companyFileInput = document.getElementById('companyFileInput'); if (companyFileInput) companyFileInput.value = '';
  window._lastCompanyProfile = null;
  // Reset all option buttons
  document.querySelectorAll('#viewCompany [data-plen], #viewCompany [data-ptone], #viewCompany [data-pfocus]').forEach(function(b) {
    b.style.background = ''; b.style.color = ''; b.style.borderColor = '';
  });
  // Re-apply defaults
  var defLen = document.getElementById('companyLen_concise');
  if (defLen) { defLen.style.background='var(--blue)'; defLen.style.color='#fff'; defLen.style.borderColor='var(--blue)'; }
  var defTone = document.getElementById('companyTone_professional');
  if (defTone) { defTone.style.background='var(--blue)'; defTone.style.color='#fff'; defTone.style.borderColor='var(--blue)'; }
  var defFocus = document.getElementById('companyFocus_general');
  if (defFocus) { defFocus.style.background='var(--blue)'; defFocus.style.color='#fff'; defFocus.style.borderColor='var(--blue)'; }
  _companyLen='concise'; _companyTone='professional'; _companyFocus='general';
}

function copyCompanyProfile() {
  var el = document.getElementById('companyBody');
  if (!el || !el.innerText.trim()) { showToast('Generate a profile first', 'err'); return; }
  navigator.clipboard.writeText(el.innerText).then(function() {
    showToast('Company profile copied!', 'ok');
  }).catch(function() { showToast('Copy failed', 'err'); });
}


function companyProfileExtractJson(rawOut) {
  var stripped = String(rawOut || '').replace(/```json/gi,'').replace(/```/g,'').trim();
  var fi = stripped.indexOf('{'), li = stripped.lastIndexOf('}');
  if (fi < 0 || li <= fi) throw new Error('No JSON');
  return JSON.parse(stripped.slice(fi, li+1));
}
function companyProfileMeaningfulText(v) {
  return String(v || '')
    .replace(/\b(null|undefined|n\/a|unknown|company profile)\b/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}
function companyProfileHasUsableContent(p) {
  if (!p || typeof p !== 'object') return false;
  var parts = [];
  ['company_name','industry','hq','website','narrative','work_mode','location'].forEach(function(k){
    var val = companyProfileMeaningfulText(p[k]);
    if (val && !/^company$/i.test(val)) parts.push(val);
  });
  ['tags','about','tech_stack','culture','why_join'].forEach(function(k){
    if (Array.isArray(p[k])) p[k].forEach(function(x){ var val = companyProfileMeaningfulText(x); if (val) parts.push(val); });
    else { var val = companyProfileMeaningfulText(p[k]); if (val) parts.push(val); }
  });
  if (Array.isArray(p.stats)) p.stats.forEach(function(st){
    if (!st) return;
    var val = companyProfileMeaningfulText((st.val || '') + ' ' + (st.lbl || ''));
    if (val) parts.push(val);
  });
  var joined = companyProfileMeaningfulText(parts.join(' '));
  var hasDetail = joined.length >= 80;
  var hasNamedProfile = companyProfileMeaningfulText(p.company_name).length >= 2 && (companyProfileMeaningfulText(p.narrative).length >= 45 || (Array.isArray(p.about) && p.about.join(' ').length >= 45));
  return !!(hasDetail || hasNamedProfile);
}
function companyProfileBlankError(companyUrl) {
  return companyUrl
    ? 'Company Profile came back blank because the provider could not extract enough public company detail from that URL. Paste a more specific company page/website or company text and try again.'
    : 'Company Profile came back blank. Paste more company information and try again.';
}
function companyProfilePlainFallbackProfile(rawText, companyUrl) {
  var clean = String(rawText || '').trim();
  var firstLine = clean.split(/\r?\n+/).map(function(x){
    return x.replace(/^#+\s*/, '').replace(/\*\*/g, '').replace(/^[-•*]\s*/, '').trim();
  }).filter(Boolean)[0] || '';
  var name = (/^company profile$/i.test(firstLine) || firstLine.length > 90) ? 'Company Profile' : (firstLine || 'Company Profile');
  return {
    company_name: name,
    industry: '',
    hq: '',
    website: companyUrl || null,
    tags: ['Plain text fallback'],
    stats: [],
    narrative: clean,
    about: [],
    tech_stack: [],
    culture: [],
    why_join: [],
    work_mode: null,
    location: null,
    _raw_fallback: true
  };
}
function companyProfileUsageBucket() { return { tokens: 0, usd: 0, usage: normalizeUsageClient({}) }; }
function companyProfileRecordUsage(bucket, label, resp) {
  if (!bucket || !resp || !resp.usage) return;
  var route = aiRoutePayload('company_profile');
  var provider = resp.provider || route.provider;
  var model = resp.model || route.model;
  var cost = responseCost(resp, model, provider);
  bucket.usage = mergeUsageClient(bucket.usage, resp.usage || {});
  bucket.tokens = bucket.usage.input_tokens + bucket.usage.output_tokens;
  bucket.usd += cost;
  statsRecord(label, 'company', cost, model, '', provider, statsMetaFromResponse(resp, model, provider));
}
function companyProfileApplyResult(prof, usageBucket) {
  window._lastCompanyProfile = prof;
  document.getElementById('companyBody').innerHTML = renderCompanyCard(prof);
  document.getElementById('companyOutputTitle').textContent = prof.company_name || 'Company Profile';
  document.getElementById('companyOutput').style.display = '';
  var phCompanyDone = document.getElementById('companyPlaceholder'); if (phCompanyDone) phCompanyDone.style.display = 'none';
  var coCostEl = document.getElementById('companyCost');
  if (coCostEl) {
    coCostEl.textContent = usageBucket && usageBucket.tokens ? ('🔥 ' + usageBucket.tokens.toLocaleString() + ' tokens · $' + usageBucket.usd.toFixed(4)) : '';
  }
}

async function generateCompanyProfile() {
  var text = (document.getElementById('companyText').value || '').trim();
  var urlEl = document.getElementById('companyUrl');
  var companyUrl = urlEl ? (urlEl.value || '').trim() : '';
  if (!text && !companyUrl) { showToast('Paste company content, upload a file, or enter a URL first', 'err'); return; }
  var route = aiRoutePayload('company_profile');
  if (!route.api_key) { showToast('Save an API key for Company Profile route', 'err'); return; }
  var ctx = (document.getElementById('companyContext').value || '').trim();

  var lenMap = {
    concise:  'Write a short 1-2 sentence narrative paragraph and 3-4 concise bullets in the about array.',
    standard: 'Write a short 2-sentence narrative paragraph and 5-7 clean bullets in the about array.',
    detailed: 'Write a 3-4 sentence narrative paragraph and 7-9 detailed bullets across the about, culture, and why_join arrays.',
  };
  var toneMap = {
    professional:   'formal, third-person, authoritative',
    conversational: 'warm, engaging, first-person plural where natural',
    punchy:         'energetic, exciting, bold — sell the company to top talent',
  };
  var focusMap = {
    general:  'Cover the company overview, business model, scale, industry position, and culture.',
    tech:     'Emphasise technology stack, engineering culture, product innovation, and technical scale.',
    culture:  'Emphasise people, values, work environment, diversity, growth mindset, and team culture.',
    finance:  'Emphasise business performance, growth trajectory, funding, market position, and revenue/scale metrics.',
  };

  var prompt = [
    'You are a senior recruitment consultant generating a structured company profile for candidate briefing.',
    '',
    'Return ONLY a raw JSON object (no markdown fences, no extra text):',
    '{"company_name":"","industry":"","hq":"","website":null,"tags":[],"stats":[{"val":"","lbl":""},{"val":"","lbl":""},{"val":"","lbl":""},{"val":"","lbl":""}],"narrative":"","about":[],"tech_stack":[],"culture":[],"why_join":[],"work_mode":null,"location":null}',
    '',
    'RULES:',
    '- Tone: ' + (toneMap[_companyTone] || toneMap.professional),
    '- Focus: ' + (focusMap[_companyFocus] || focusMap.general),
    '- Length: ' + (lenMap[_companyLen] || lenMap.concise),
    '- Only include factual details present in the source. Never invent metrics.',
    '- narrative: paragraph text only. Do NOT include bullet points, numbered lists, or line breaks in narrative.',
    '- about: place the requested company overview/highlight bullets here. Each array item must be one clean bullet string without leading hyphens or bullet symbols.',
    '- culture and why_join: use arrays for additional bullets where relevant. Do not put these bullets inside narrative.',
    '- stats: extract up to 4 quantitative data points (headcount, revenue, countries, etc.). Keep stat values short enough for a dashboard tile; move long descriptions into labels.',
    '- tech_stack: only if source mentions specific technologies. Empty array otherwise.',
    '- why_join: 3 genuinely compelling reasons from real signals.',
    ctx ? ('- RECRUITER CONTEXT: ' + ctx) : '',
    '',
    companyUrl ? ('Company URL: ' + companyUrl) : '',
    '',
    'SOURCE MATERIAL:',
    '---',
    text || ('Use the Company URL above as the source if available.'),
    '---',
    '',
    'Return JSON only:'
  ].filter(function(l){ return l !== null && l !== undefined; }).join('\n');
  var btn = document.getElementById('btnGenerateCompany');
  var statusEl = document.getElementById('companyStatus');
  var _tabRun = markTabRunning('company');
  btn.disabled = true; btn.textContent = '⏳ Generating…';
  statusEl.textContent = 'Processing…';
  document.getElementById('companyOutput').style.display = 'none';
  var phCompanyStart = document.getElementById('companyPlaceholder'); if (phCompanyStart) phCompanyStart.style.display = 'flex';

  try {
    var companyUsage = companyProfileUsageBucket();
    var data = await callAIProxy(prompt, 3000, !!companyUrl, 3, 'company_profile');
    var rawOut = aiText(data).trim();
    companyProfileRecordUsage(companyUsage, 'Company Profile', data);

    // Parse JSON and reject blank/empty profiles. Some provider/web-search runs
    // return an empty JSON shell on the first attempt; do not mark that as Done.
    var prof;
    try {
      if (rawOut.length < 20) throw new Error('Blank response');
      prof = companyProfileExtractJson(rawOut);
    } catch(pe) {
      if (companyProfileMeaningfulText(rawOut).length >= 120) {
        var fallbackProf = companyProfilePlainFallbackProfile(rawOut, companyUrl);
        companyProfileApplyResult(fallbackProf, companyUsage);
        statusEl.textContent = '✅ Done';
        markTabDone('company', _tabRun);
        showToast('Company profile generated!', 'ok');
        return;
      }
      throw new Error(companyProfileBlankError(companyUrl));
    }

    if (!companyProfileHasUsableContent(prof)) {
      statusEl.textContent = 'First answer was blank — retrying once…';
      var retryPrompt = prompt + '\n\nIMPORTANT RETRY: Your previous answer produced an empty or unusable company profile. Use the URL/source material and return a populated JSON profile. If the URL is too generic or inaccessible, explain this in narrative instead of returning empty fields. Do not return an empty JSON shell.';
      var retryData = await callAIProxy(retryPrompt, 3500, !!companyUrl, 5, 'company_profile');
      var retryRaw = aiText(retryData).trim();
      companyProfileRecordUsage(companyUsage, 'Company Profile Retry', retryData);
      try {
        prof = companyProfileExtractJson(retryRaw);
      } catch(retryParseErr) {
        if (companyProfileMeaningfulText(retryRaw).length >= 120) {
          var retryFallbackProf = companyProfilePlainFallbackProfile(retryRaw, companyUrl);
          companyProfileApplyResult(retryFallbackProf, companyUsage);
          statusEl.textContent = '✅ Done';
          markTabDone('company', _tabRun);
          showToast('Company profile generated!', 'ok');
          return;
        }
        throw new Error(companyProfileBlankError(companyUrl));
      }
      if (!companyProfileHasUsableContent(prof)) throw new Error(companyProfileBlankError(companyUrl));
    }

    companyProfileApplyResult(prof, companyUsage);
    statusEl.textContent = '✅ Done';
    markTabDone('company', _tabRun);
    showToast('Company profile generated!', 'ok');

  } catch(e) {
    statusEl.textContent = '❌ ' + e.message;
    markTabFailed('company', _tabRun);
    showToast('Generation failed: ' + e.message, 'err');
  } finally {
    btn.disabled = false; btn.textContent = 'Generate Profile';
  }
}

function renderCompanyCard(p) {
  p = p || {};
  function arr(v) { return Array.isArray(v) ? v : (v ? [String(v)] : []); }
  function esc2(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
  function bullets(items, dot) {
    return arr(items).map(function(b){ return '<li style="display:flex;gap:8px;padding:3px 0;"><span style="color:'+dot+';flex-shrink:0;margin-top:2px">•</span><span>'+esc2(b)+'</span></li>'; }).join('');
  }
  function sec(label, html, bg) {
    return '<div style="margin-bottom:14px;'+(bg?'background:'+bg+';border-radius:8px;padding:10px 12px;':'')+'">'
      +'<div style="font-size:11px;font-weight:700;color:var(--text2);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">'+label+'</div>'+html+'</div>';
  }
  function narrativeParts(v) {
    var raw = String(v || '').split(/\r?\n+/).map(function(x){ return x.trim(); }).filter(Boolean);
    var hadMarkers = raw.some(function(x){ return /^([\u2022\-*]|\d+[.)])\s+/.test(x); });
    var lines = raw.map(function(x){ return x.replace(/^([\u2022\-*]|\d+[.)])\s+/, '').trim(); }).filter(Boolean);
    if (!lines.length) return { intro:'', bullets:[] };
    if (lines.length <= 2 && !hadMarkers) return { intro:lines.join(' '), bullets:[] };
    return { intro:lines[0] || '', bullets:lines.slice(1) };
  }
  function narrativeHtml(v) {
    var n = narrativeParts(v);
    var out = '';
    if (n.intro) out += '<p style="margin:0 0 12px;line-height:1.7;font-size:13px;">'+esc2(n.intro)+'</p>';
    if (n.bullets.length) out += '<ul style="list-style:none;padding:0;margin:0 0 12px;">'+bullets(n.bullets,'var(--blue)')+'</ul>';
    return out;
  }

  var initials = String(p.company_name||'?').split(/\s+/).map(function(w){return w[0]||'';}).slice(0,2).join('').toUpperCase();
  var tags = arr(p.tags).map(function(t){ return '<span style="background:var(--surface2);border:1px solid var(--border);border-radius:20px;padding:2px 9px;font-size:11px;margin-right:4px;">'+esc2(t)+'</span>'; }).join('');
  var stats = arr(p.stats).filter(function(s){return s&&s.val&&s.val!=='null';}).map(function(s){
    return '<div style="text-align:center;flex:1;min-width:0;padding:0 4px;"><div style="font-size:14px;line-height:1.18;font-weight:700;color:var(--blue);overflow-wrap:anywhere;word-break:normal;">'+esc2(s.val)+'</div><div style="font-size:10px;line-height:1.25;color:var(--text3);margin-top:3px;overflow-wrap:anywhere;">'+esc2(s.lbl)+'</div></div>';
  }).join('');
  var meta = [p.hq, p.industry, p.website].filter(function(x){return x&&x!=='null';}).map(function(x){return '<span style="color:var(--text3);font-size:12px;margin-right:8px;">'+esc2(x)+'</span>';}).join('');
  var techPills = arr(p.tech_stack).map(function(t){ return '<span style="display:inline-block;background:var(--surface2);border:1px solid var(--border);border-radius:20px;padding:2px 9px;font-size:11px;margin:2px 3px 2px 0;font-weight:500;color:var(--blue);">'+esc2(t)+'</span>'; }).join('');

  return '<div>'
    + '<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">'
    + '<div style="width:44px;height:44px;border-radius:10px;background:var(--blue);color:#fff;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:700;flex-shrink:0;">'+esc2(initials)+'</div>'
    + '<div><div style="font-size:16px;font-weight:700;color:var(--text1);">'+esc2(p.company_name||'Company')+'</div>'
    + (meta ? '<div style="margin-top:2px;">'+meta+'</div>' : '')
    + (tags ? '<div style="margin-top:4px;">'+tags+'</div>' : '')
    + '</div></div>'
    + (stats ? '<div style="display:flex;gap:8px;background:var(--surface2);border-radius:8px;padding:12px;margin-bottom:12px;">'+stats+'</div>' : '')
    + (p.narrative && p.narrative!=='null' ? narrativeHtml(p.narrative) : '')
    + (arr(p.about).length ? sec('About', '<ul style="list-style:none;padding:0;margin:0;">'+bullets(p.about,'var(--blue)')+'</ul>') : '')
    + (arr(p.culture).length ? sec('Culture & Values', '<ul style="list-style:none;padding:0;margin:0;">'+bullets(p.culture,'#60a5fa')+'</ul>') : '')
    + (arr(p.tech_stack).length ? sec('Tech Stack', techPills) : '')
    + (arr(p.why_join).length ? sec('Why Join', '<ul style="list-style:none;padding:0;margin:0;">'+bullets(p.why_join,'#22c55e')+'</ul>', 'var(--surface2)') : '')
    + '<div style="margin-top:10px;padding-top:8px;border-top:1px solid var(--border);font-size:11px;color:var(--text3);">© Hyppies · Confidential · For candidate use only</div>'
    + '</div>';
}
