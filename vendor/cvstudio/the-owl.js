// ── The Owl ──────────────────────────────────────────
var THE_OWL_BTN_HTML = 'Generate The Owl Map';
window._theOwlPlainText = '';
window._theOwlHTML = '';
window._theOwlMeta = null;
function getMarketMeta() {
  return {
    location: ((document.getElementById('theOwlLocation') || {}).value || '').trim() || 'Malaysia',
    industries: ((document.getElementById('theOwlIndustries') || {}).value || '').trim() || 'General',
    notes: ((document.getElementById('theOwlNotes') || {}).value || '').trim() || 'None'
  };
}
function updateTheOwlCounts() {
  var ta = document.getElementById('theOwlText');
  var el = document.getElementById('theOwlCharCount');
  if (ta && el) el.textContent = (ta.value || '').length.toLocaleString() + ' chars';
}
function updateTheOwlRouteBadge() {
  var el = document.getElementById('theOwlRouteBadge');
  if (!el) return;
  try {
    var r = resolveAiRoute('the_owl');
    el.textContent = 'Using: ' + r.display + (r.api_key ? '' : ' · no saved key');
  } catch(e) { el.textContent = 'Using: —'; }
}
function theOwlSupportedFileExt(file) {
  var ext = ((file && file.name ? file.name : '').split('.').pop() || '').toLowerCase();
  return ['pdf','docx','doc','txt','rtf','odt','png','jpg','jpeg'].indexOf(ext) >= 0;
}
async function selectTheOwlFile(file) {
  if (!file) return;
  var status = document.getElementById('theOwlFileStatus');
  var target = document.getElementById('theOwlText');
  if (!theOwlSupportedFileExt(file)) {
    if (status) status.textContent = '✗ Unsupported file type';
    showToast('Supported: PDF, DOCX, DOC, TXT, RTF, ODT, PNG, JPG, JPEG', 'err');
    return;
  }
  var run = markTabRunning('theowl');
  if (target) target.dataset.extracting = '1';
  if (status) status.textContent = 'Extracting ' + file.name + '…';
  try {
    var fd = new FormData(); fd.append('file', file);
    var r = await fetchWithTimeout('/extract-text', { method:'POST', body:fd }, 90000);
    var d = await r.json().catch(function(){ return {}; });
    if (!r.ok || d.error) throw new Error(d.error || 'Extraction failed');
    var text = String(d.text || '').trim();
    if (target) target.value = text;
    updateTheOwlCounts();
    if (status) status.textContent = '✓ ' + file.name + ' (' + text.length.toLocaleString() + ' chars extracted)';
    markTabDone('theowl', run);
    showToast('JD extracted for The Owl', 'ok');
  } catch(e) {
    if (status) status.textContent = '✗ ' + (e.message || 'Extraction failed');
    markTabFailed('theowl', run);
    showToast('The Owl extraction failed: ' + (e.message || 'Unknown error'), 'err');
  } finally {
    if (target) delete target.dataset.extracting;
  }
}
function stripMarketInlineMarkdown(s) {
  return String(s || '')
    .replace(/^#{1,6}\s+/, '')
    .replace(/`{3,}/g, '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\s+/g, ' ')
    .trim();
}


var MARKET_KNOWN_SECTION_TITLES = [
  'Role Snapshot',
  'Alternative Job Titles Candidates May Use',
  'Adjacent / Transferable Titles',
  'Screening Scorecard',
  'Sourcing Notes',
  'Red Flags / False Positives Recruiters Should Screen Out',
  'Hidden Talent Pools Recruiters Often Overlook',
  'Industries Where These Talents Are Commonly Found',
  'Types of Companies That Hire These Profiles',
  'Target Companies to Source From in the Selected Market',
  'Candidate Profile Patterns',
  'JobStreet Search Strings',
  'LinkedIn Recruiter Search Strategy',
  'LinkedIn Boolean Strings',
  'Google X-ray Search Strings',
  'Google X Ray Search Strings',
  'Suggested Sourcing Strategy',
  'Salary Positioning and Competitiveness Observations'
];
var MARKET_CANONICAL_SECTION_ORDER = [
  'Role Snapshot',
  'Alternative Job Titles Candidates May Use',
  'Adjacent / Transferable Titles',
  'Screening Scorecard',
  'Sourcing Notes',
  'Red Flags / False Positives Recruiters Should Screen Out',
  'Hidden Talent Pools Recruiters Often Overlook',
  'Industries Where These Talents Are Commonly Found',
  'Types of Companies That Hire These Profiles',
  'Target Companies to Source From in the Selected Market',
  'Candidate Profile Patterns',
  'JobStreet Search Strings',
  'LinkedIn Recruiter Search Strategy',
  'LinkedIn Boolean Strings',
  'Google X-ray Search Strings',
  'Suggested Sourcing Strategy',
  'Salary Positioning and Competitiveness Observations'
];

function escapeMarketRegExp(s) {
  return String(s || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function normaliseMarketKnownHeading(h) {
  h = String(h || '').replace(/\s+/g, ' ').trim();
  if (/^google\s+x\s*ray\s+search\s+strings$/i.test(h)) return 'Google X-ray Search Strings';
  for (var i = 0; i < MARKET_KNOWN_SECTION_TITLES.length; i++) {
    if (MARKET_KNOWN_SECTION_TITLES[i].toLowerCase() === h.toLowerCase()) return MARKET_KNOWN_SECTION_TITLES[i] === 'Google X Ray Search Strings' ? 'Google X-ray Search Strings' : MARKET_KNOWN_SECTION_TITLES[i];
  }
  return h;
}

function matchMarketKnownSectionLead(line) {
  var original = String(line || '').trim();
  if (!original) return null;
  var s = stripMarketInlineMarkdown(original)
    .replace(/^[-*•]\s+/, '')
    .replace(/^\d{1,2}\s*[.)]\s+/, '')
    .trim();
  if (!s) return null;
  for (var i = 0; i < MARKET_KNOWN_SECTION_TITLES.length; i++) {
    var title = MARKET_KNOWN_SECTION_TITLES[i];
    var titlePattern = escapeMarketRegExp(title).replace(/\\\s\+/g, '\\s+').replace(/x\\-ray/i, 'x[-\\s]?ray');
    var re = new RegExp('^(' + titlePattern + ')(?:\\s*(?:[:：]|[-–—])\\s*(.*))?$', 'i');
    var m = s.match(re);
    if (m) {
      return { heading: normaliseMarketKnownHeading(m[1]), rest: String(m[2] || '').trim() };
    }
  }
  return null;
}

function isMarketRule(line) {
  return /^[-_*—–\s]{3,}$/.test(String(line || '').trim()) || /^[-*•]\s*$/.test(String(line || '').trim());
}

function isMarketPreamble(line) {
  const s = stripMarketInlineMarkdown(line).toLowerCase();
  if (!s) return true;
  if (/^here is\b/.test(s) && /market/.test(s)) return true;
  if (/^below is\b/.test(s) && /market/.test(s)) return true;
  if (/^sure[,\s]/.test(s)) return true;
  if (/^recruitment market map$/.test(s)) return true;
  if (/^talent market map$/.test(s)) return true;
  if (/verified market intelligence.*as of/.test(s)) return true;
  if (/^©\s*hyppies/.test(s)) return true;
  if (/^page\s+\d+\s+of\s+\d+/.test(s)) return true;
  if (/^confidential\b/.test(s) && /internal sourcing/.test(s)) return true;
  return false;
}

function isMarketAllCapsHeading(line) {
  const s = stripMarketInlineMarkdown(line).replace(/[:：]$/, '').trim();
  if (!s || s.length > 95 || s.length < 4) return false;
  if (!/[A-Za-z]/.test(s)) return false;
  const letters = s.replace(/[^A-Za-z]/g, '');
  if (letters.length < 3) return false;
  const upper = letters.replace(/[^A-Z]/g, '').length;
  return upper / letters.length > 0.82;
}

function isMarketSoftSubheading(line) {
  const s = stripMarketInlineMarkdown(line).replace(/[:：]$/, '').trim();
  if (!s || s.length > 80 || s.length < 3) return false;
  if (/[-–—]\s+/.test(s)) return false; // likely a company/detail line, not a heading
  if (/[.!?]$/.test(s)) return false;
  if (/^(role|location|company|target location|priority industries)\s*:/i.test(s)) return false;
  if (/^(and|or|but|with|from|for|to)\b/i.test(s)) return false;
  // Title-like lines such as "LinkedIn (Primary)" or "US Tech & SaaS (...)"
  return /^[A-Z0-9][A-Za-z0-9&/()+,.'\s-]+$/.test(s) && s.split(/\s+/).length <= 9;
}


function getLastMarketHeading(blocks, type) {
  for (let i = blocks.length - 1; i >= 0; i--) {
    if (!type || blocks[i].type === type) return String(blocks[i].text || '');
  }
  return '';
}

function isMarketCompanyListContext(blocks) {
  const h2 = getLastMarketHeading(blocks, 'h2').toLowerCase();
  const h3 = getLastMarketHeading(blocks, 'h3').toLowerCase();
  const ctx = h2 + ' ' + h3;
  return /\b(target|source|sourcing|competitor|company|companies|employer|employers|talent pool|talent pools|startups|fintech|saas|gb[s]?|ssc|shared services|payments|banks?|bpo|mnc)\b/.test(ctx);
}

function isMarketSearchStringContext(blocks) {
  const h2 = getLastMarketHeading(blocks, 'h2').toLowerCase();
  const h3 = getLastMarketHeading(blocks, 'h3').toLowerCase();
  const ctx = h2 + ' ' + h3;
  return /\b(jobstreet|linkedin|boolean|x-?ray|x ray|search string|search strings|recruiter search|keyword|keywords|sourcing angle|xray)\b/.test(ctx);
}

function isMarketJobStreetContext(blocks) {
  const h2 = getLastMarketHeading(blocks, 'h2').toLowerCase();
  const h3 = getLastMarketHeading(blocks, 'h3').toLowerCase();
  return /\b(jobstreet|job board|job boards)\b/.test(h2 + ' ' + h3);
}

function isMarketGenericCategoryHeading(line) {
  const s = stripMarketInlineMarkdown(line).replace(/[:：]$/, '').trim().toLowerCase();
  if (!s) return false;
  return /^(banks?|banking|digital banks?|fintech|payments?|e-?wallets?|insurance|telco|telecommunications|technology|tech companies|software|saas|startups?|scaleups?|unicorns?|shared services|gb[sc]|ssc|bpo|mnc|multinationals?|consulting|systems integrators?|vendors?|outsourcing|nearshore|regional hubs?|public sector|government|glc|manufacturing|industrial|oil\s*&\s*gas|healthcare|retail|e-?commerce|logistics|transport|airlines?|semiconductor|electronics|fmcg|consumer|property|construction|education|universities|category|categories|source categories|target categories|priority targets?)$/.test(s);
}
function looksLikeStandaloneMarketCompanyName(line, blocks, nextLine) {
  if (!isMarketCompanyListContext(blocks)) return false;
  if (/^[-*•]\s+/.test(String(line || '').trim())) return false; // bullets are handled by the bullet parser; do not merge them as standalone company headings
  let s = stripMarketInlineMarkdown(line).replace(/[:：]\s*$/, '').trim();
  if (!s || s.length < 2 || s.length > 90) return false;
  if (isMarketGenericCategoryHeading(s)) return false;
  if (/^(role|location|company|target location|priority industries|current date)\s*:/i.test(s)) return false;
  if (/^(target|source|sourcing|candidate|profile|industry|industries|titles?|roles?|search|string|strategy|red flags?|salary)\b/i.test(s)) return false;
  const n = String(nextLine || '').trim();
  if (!n || matchMarketKnownSectionLead(n) || isMarketRule(n) || /^\d{1,2}\.\s+/.test(n) || /^#{1,6}\s+/.test(n)) return false;
  const words = s.split(/\s+/).filter(Boolean);
  if (words.length > 8) return false;
  const letters = s.replace(/[^A-Za-z]/g, '');
  const upperRatio = letters ? letters.replace(/[^A-Z]/g, '').length / letters.length : 0;
  const hasCompanySignal = /\b(bank|digital|group|berhad|bhd|sdn|plc|ltd|pte|inc|corp|corporation|technolog(?:y|ies)|solutions?|systems?|services?|holdings?|labs?|pay|payments?|capital|securities|insurance|assurance|financial|finance|global|data|cloud|consulting|partners?)\b/i.test(s);
  const allCapsOrAcronym = upperRatio > 0.72 && words.length <= 5;
  const titleCaseShort = words.length <= 5 && /^[A-Z0-9][A-Za-z0-9&.,'()\/ +.-]+$/.test(s) && !/[.!?]$/.test(s);
  return hasCompanySignal || allCapsOrAcronym || titleCaseShort;
}

function looksLikeMarketSearchString(line, blocks) {
  const s = String(line || '').trim();
  if (!s || s.length < 5 || s.length > 520) return false;
  if (/^[-*•]\s+/.test(s)) return false;
  if (!isMarketSearchStringContext(blocks)) return false;
  if (isMarketRule(s) || isMarketAllCapsHeading(s) || /^#{1,6}\s+/.test(s) || /^\d{1,2}\.\s+/.test(s)) return false;
  if (/^(note|notes|example|examples)\s*:/i.test(s)) return false;
  if (/^site:linkedin\.com\/in\b/i.test(s)) return true;
  if (/^(title field|keywords field|keyword field|location filter|industry filter|industry\/company filters|company filters|current\/past company|current company|past company|exclusion keywords|exclude|seniority filter)\s*:/i.test(s)) return true;
  if (/(\bAND\b|\bOR\b|\bNOT\b)/.test(s) && /[()"']/.test(s)) return true;
  if (/["“”][^"“”]{3,}["“”]/.test(s) && /\b(kuala lumpur|selangor|malaysia|singapore|jakarta|mandarin|chinese|bahasa|remote|hybrid|lead|manager|analyst|engineer|specialist|architect|developer|consultant)\b/i.test(s)) return true;
  // JobStreet often works best with short plain keyword searches, so detect raw non-quoted searches too.
  // Do not overfit to a small technology/title dictionary: market maps may include tools/domains like UiPath, Workday, Murex, AML, SWIFT, etc.
  if (isMarketJobStreetContext(blocks)) {
    const words = s.split(/\s+/).filter(Boolean);
    if (words.length >= 2 && words.length <= 14 && !/[.!?]$/.test(s) && !/:$/.test(s) && !isMarketGenericCategoryHeading(s)) {
      return true;
    }
  }
  return false;
}

function looksLikeMarketCompanyLine(line, blocks) {
  const s = String(line || '').trim();
  if (!s || s.length < 5 || s.length > 260) return false;
  if (/^[-*•]\s+/.test(s)) return false;
  if (/^(role|location|company|target location|priority industries|current date)\s*:/i.test(s)) return false;
  if (/^(below|these|this|that|where|when|why|how|use|filter|look|target|actively|scrape|cross-reference|community|referral)\b/i.test(s)) return false;
  if (!isMarketCompanyListContext(blocks)) return false;

  // Handles common market-map output such as:
  // "Grab Malaysia – strong billing talent" or "TNG Digital –"
  const dash = s.match(/^([^–—-]{2,90})\s*[–—-]\s*(.*)$/);
  if (!dash) return false;
  const name = dash[1].trim();
  if (name.split(/\s+/).length > 10) return false;
  if (!/[A-Z0-9]/.test(name)) return false;
  if (/\.$/.test(name)) return false;
  return true;
}

function shouldJoinMarketCompanyContinuation(line, blocks) {
  const s = String(line || '').trim();
  if (!s) return false;
  if (isMarketRule(s) || isMarketAllCapsHeading(s) || /^\d{1,2}\.\s+/.test(s) || /^#{1,6}\s+/.test(s) || /^[-*•]\s+/.test(s)) return false;
  if (isMarketSoftSubheading(s)) return false;
  if (looksLikeMarketCompanyLine(s, blocks)) return false;
  return true;
}

function cleanMarketExportLine(line) {
  return stripMarketInlineMarkdown(line)
    .replace(/[\u00A0\t]+/g, ' ')
    .replace(/[–—]/g, ' - ')
    .replace(/\s+-\s+-\s+/g, ' - ')
    .replace(/\s{2,}/g, ' ')
    .trim();
}
function isMarketMarkdownTableLine(line) {
  line = String(line || '').trim();
  return /^\|.+\|$/.test(line) && line.split('|').length >= 4;
}
function isMarketMarkdownTableSeparator(line) {
  return /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(String(line || '').trim());
}
function marketTableCells(line) {
  line = String(line || '').trim().replace(/^\|/, '').replace(/\|$/, '');
  return line.split('|').map(function(c){ return cleanMarketExportLine(c); });
}
function pushMarketTableBlock(blocks, rows) {
  rows = (rows || []).filter(function(r){ return isMarketMarkdownTableLine(r) && !isMarketMarkdownTableSeparator(r); });
  if (!rows.length) return;
  var headers = marketTableCells(rows[0]);
  var bodyRows = rows.slice(1).map(marketTableCells).filter(function(r){ return r.some(Boolean); });
  if (!headers.length || !bodyRows.length) return;
  blocks.push({ type:'table', headers: headers, rows: bodyRows });
}
function marketSectionKey(title) {
  var h = normaliseMarketKnownHeading(title || '');
  return h.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}
function isMarketCompactListHeading(title) {
  var h = String(title || '').toLowerCase();
  return /alternative job titles|adjacent \/ transferable titles|industries where|types of companies|hidden talent pools/.test(h);
}
function reorderMarketBlocks(blocks) {
  blocks = blocks || [];
  var lead = [], known = {}, unknown = [], current = null;
  function flushCurrent(){
    if (!current) return;
    if (current.known) { if (!known[current.title]) known[current.title] = []; known[current.title] = known[current.title].concat(current.blocks); }
    else unknown.push(current.blocks);
    current = null;
  }
  blocks.forEach(function(b){
    if (b.type === 'h2') {
      flushCurrent();
      var norm = normaliseMarketKnownHeading(b.text);
      var isKnown = MARKET_CANONICAL_SECTION_ORDER.indexOf(norm) >= 0 || norm === 'Google X Ray Search Strings';
      if (norm === 'Google X Ray Search Strings') norm = 'Google X-ray Search Strings';
      current = { known:isKnown, title:norm, blocks:[{type:'h2', text:norm}] };
      return;
    }
    if (!current) { lead.push(b); return; }
    current.blocks.push(b);
  });
  flushCurrent();
  var out = lead.slice();
  MARKET_CANONICAL_SECTION_ORDER.forEach(function(title){ if (known[title]) out = out.concat(known[title]); });
  unknown.forEach(function(g){ out = out.concat(g); });
  return out;
}

function parseMarketBlocks(text) {
  const rawLines = String(text || '').replace(/\r\n/g, '\n').split('\n');
  const lines = [];

  // First pass: remove markdown separators/preamble and normalize continuation lines.
  rawLines.forEach(function(raw) {
    let line = String(raw || '').trim();
    if (!line) { lines.push(''); return; }
    if (/^```/.test(line)) return;
    if (isMarketRule(line)) return;
    if (isMarketPreamble(line)) return;
    lines.push(line);
  });

  const blocks = [];
  const push = function(type, text) {
    text = cleanMarketExportLine(text);
    if (!text) return;
    if (blocks.length) {
      const prev = blocks[blocks.length - 1];
      // Merge accidental duplicate headings/paragraphs caused by model formatting.
      if (prev.type === type && prev.text.toLowerCase() === text.toLowerCase()) return;
    }
    blocks.push({ type: type, text: text });
  };

  let i = 0;
  while (i < lines.length) {
    let raw = lines[i];
    if (!raw || !raw.trim()) { i++; continue; }
    raw = raw.trim();

    if (isMarketMarkdownTableLine(raw)) {
      var tableRows = [];
      while (i < lines.length) {
        var tblLine = (lines[i] || '').trim();
        if (!isMarketMarkdownTableLine(tblLine) && !isMarketMarkdownTableSeparator(tblLine)) break;
        tableRows.push(tblLine);
        i++;
      }
      pushMarketTableBlock(blocks, tableRows);
      continue;
    }

    // Guardrail: AI sometimes returns a new section header as a bullet, e.g.
    // "- Candidate Profile Patterns - Education: ...". Without this split,
    // the section becomes clumped under the previous list (usually target companies).
    let knownSectionLead = matchMarketKnownSectionLead(raw);
    if (knownSectionLead) {
      push('h2', knownSectionLead.heading);
      if (knownSectionLead.rest) push('li', knownSectionLead.rest);
      i++;
      continue;
    }

    let numberedHeading = raw.match(/^\d{1,2}\.\s+(.{1,110})$/);
    let mdHeading = raw.match(/^#{1,6}\s+(.+)$/);
    let boldHeading = raw.match(/^\*\*(.{1,110}?)\*\*:?$/);
    let nextLineForCompany = (function() {
      for (let j = i + 1; j < lines.length; j++) {
        const x = (lines[j] || '').trim();
        if (x) return x;
      }
      return '';
    })();
    if (!numberedHeading && !mdHeading && !boldHeading && looksLikeStandaloneMarketCompanyName(raw, blocks, nextLineForCompany)) {
      var cleanCompanyName = stripMarketInlineMarkdown(raw).replace(/[:：]\s*$/, '').trim();
      var detail = String(nextLineForCompany || '').trim().replace(/^[-*•–—-]\s*/, '');
      push('li', detail ? (cleanCompanyName + ' - ' + detail) : cleanCompanyName);
      i += detail ? 2 : 1;
      continue;
    }
    let allCapsHeading = isMarketAllCapsHeading(raw);
    // Short uppercase company names inside target-company sections (e.g. CIMB, DBS, UOB)
    // are talent-pool items, not section headings. Check this before the generic
    // all-caps heading rule so The Owl does not split company lists incorrectly.
    if (allCapsHeading && looksLikeMarketCompanyLine(raw, blocks)) allCapsHeading = false;
    if (numberedHeading || mdHeading || boldHeading || allCapsHeading) {
      const h = numberedHeading ? numberedHeading[1] : mdHeading ? mdHeading[1] : boldHeading ? boldHeading[1] : raw;
      push('h2', h.replace(/[:：]$/, ''));
      i++;
      continue;
    }

    const bullet = raw.match(/^[-*•]\s+(.+)$/);
    if (bullet) {
      let item = bullet[1].trim();
      i++;
      // Join continuation lines that belong to the bullet.
      while (i < lines.length) {
        const nxt = (lines[i] || '').trim();
        if (!nxt) { i++; break; }
        if (matchMarketKnownSectionLead(nxt) || isMarketRule(nxt) || isMarketAllCapsHeading(nxt) || /^\d{1,2}\.\s+/.test(nxt) || /^#{1,6}\s+/.test(nxt) || /^[-*•]\s+/.test(nxt)) break;
        if (isMarketSoftSubheading(nxt)) break;
        if (looksLikeMarketSearchString(nxt, blocks)) break;
        if (looksLikeMarketCompanyLine(nxt, blocks)) break;
        item += ' ' + nxt;
        i++;
      }
      push('li', item);
      continue;
    }

    if (looksLikeMarketCompanyLine(raw, blocks)) {
      let item = raw.trim();
      i++;
      while (i < lines.length) {
        const nxt = (lines[i] || '').trim();
        if (!nxt) { i++; break; }
        // If the company line ended with a dash, the next line is almost always the reason/source angle.
        if (/[-–—]\s*$/.test(item) && !isMarketRule(nxt) && !isMarketAllCapsHeading(nxt) && !/^\d{1,2}\.\s+/.test(nxt) && !/^#{1,6}\s+/.test(nxt) && !/^[-*•]\s+/.test(nxt)) {
          item = item.replace(/\s*[-–—]\s*$/, ' - ') + nxt.replace(/^[–—-]\s*/, '');
          i++;
          continue;
        }
        if (!shouldJoinMarketCompanyContinuation(nxt, blocks)) break;
        item += ' ' + nxt.replace(/^[–—-]\s*/, '- ');
        i++;
      }
      push('li', item);
      continue;
    }

    if (looksLikeMarketSearchString(raw, blocks)) {
      let item = raw.trim();
      i++;
      while (i < lines.length) {
        const nxt = (lines[i] || '').trim();
        if (!nxt) { i++; break; }
        if (matchMarketKnownSectionLead(nxt) || isMarketRule(nxt) || isMarketAllCapsHeading(nxt) || /^\d{1,2}\.\s+/.test(nxt) || /^#{1,6}\s+/.test(nxt) || /^[-*•]\s+/.test(nxt)) break;
        if (isMarketSoftSubheading(nxt) || looksLikeMarketSearchString(nxt, blocks) || looksLikeMarketCompanyLine(nxt, blocks)) break;
        // Join accidental wrapped Boolean/search-string lines, but avoid swallowing normal explanation paragraphs.
        if (item.length < 360 && !/[.!?]$/.test(item)) { item += ' ' + nxt; i++; continue; }
        break;
      }
      push('li', item);
      continue;
    }

    // Treat short title-like lines as subheadings when they introduce a list/section.
    const nextNonBlank = (function() {
      for (let j = i + 1; j < lines.length; j++) {
        const x = (lines[j] || '').trim();
        if (x) return x;
      }
      return '';
    })();
    if (isMarketSoftSubheading(raw) && (nextNonBlank === '' || /^[-*•]\s+/.test(nextNonBlank) || !/[.!?]$/.test(raw))) {
      push('h3', raw.replace(/[:：]$/, ''));
      i++;
      continue;
    }

    // Paragraph. Join wrapped lines until next structural break.
    let para = raw;
    i++;
    while (i < lines.length) {
      const nxt = (lines[i] || '').trim();
      if (!nxt) { i++; break; }
      if (matchMarketKnownSectionLead(nxt) || isMarketRule(nxt) || isMarketAllCapsHeading(nxt) || /^\d{1,2}\.\s+/.test(nxt) || /^#{1,6}\s+/.test(nxt) || /^[-*•]\s+/.test(nxt)) break;
      if (isMarketSoftSubheading(nxt) && !para.endsWith('-') && !para.endsWith(' -')) break;
      if (para.endsWith('-') || para.endsWith(' -')) para = para.replace(/\s*-\s*$/, ' - ') + nxt.replace(/^[-–—]\s*/, '');
      else if (/^[-–—]\s+/.test(nxt)) para += ' ' + nxt.replace(/^[-–—]\s+/, '- ');
      else para += ' ' + nxt;
      i++;
    }
    const metaMatch = para.match(/^(Role|Location|Company|Target location|Priority industries)\s*:/i);
    push(metaMatch ? 'meta' : 'p', para);
  }

  // Final cleanup + canonical section order.
  return reorderMarketBlocks(blocks);
}

function marketTableToHTML(block, escFn) {
  var headers = block.headers || [];
  var rows = block.rows || [];
  if (!headers.length || !rows.length) return '';
  var tableStyle = 'width:100%;border-collapse:collapse;table-layout:fixed;font-size:8.8pt;line-height:1.22;margin:4px 0 8px;';
  var thStyle = 'border:1px solid #dfe5ef;background:#f1f5f9;color:#111827;font-weight:700;padding:5px 6px;text-align:left;vertical-align:top;';
  var tdStyle = 'border:1px solid #dfe5ef;padding:5px 6px;text-align:left;vertical-align:top;';
  var firstTdStyle = tdStyle + 'font-weight:700;';
  var widths = [];
  var colgroup = '';
  if (headers.length === 3 && /criteria/i.test(headers[0] || '') && /weight/i.test(headers[1] || '')) {
    widths = ['35%','14%','51%'];
    colgroup = '<colgroup><col style="width:35%"><col style="width:14%"><col style="width:51%"></colgroup>';
  } else {
    widths = headers.map(function(){ return (100 / Math.max(headers.length,1)).toFixed(2) + '%'; });
  }
  return '<div class="market-table-wrap"><table class="market-table" cellspacing="0" cellpadding="0" border="1" style="' + tableStyle + '">' + colgroup + '<thead><tr>' + headers.map(function(h, i){ return '<th width="' + widths[i] + '" style="width:' + widths[i] + ';' + thStyle + '">' + escFn(h) + '</th>'; }).join('') + '</tr></thead><tbody>' + rows.map(function(row){
    return '<tr>' + headers.map(function(_, i){ return '<td width="' + widths[i] + '" style="width:' + widths[i] + ';' + (i === 0 ? firstTdStyle : tdStyle) + '">' + escFn(row[i] || '') + '</td>'; }).join('') + '</tr>';
  }).join('') + '</tbody></table></div>';
}
function marketDocCompactListHTML(items, escFn) {
  items = items || [];
  if (!items.length) return '';
  var half = Math.ceil(items.length / 2);
  var left = items.slice(0, half);
  var right = items.slice(half);
  function listHtml(arr) { return '<ul class="market-doc-list">' + arr.map(function(x){ return '<li>' + escFn(x) + '</li>'; }).join('') + '</ul>'; }
  return '<table class="market-two-col" role="presentation"><tr><td>' + listHtml(left) + '</td><td>' + listHtml(right) + '</td></tr></table>';
}
function marketBlocksToHTML(blocks, forDoc) {
  blocks = blocks || [];
  let html = '';
  let list = [];
  let currentH2 = '';
  const escFn = forDoc ? _escDoc : esc;
  const flush = function() {
    if (!list.length) return;
    var compact = isMarketCompactListHeading(currentH2);
    if (forDoc && compact) html += marketDocCompactListHTML(list, escFn);
    else {
      var cls = compact ? 'market-list-compact' : 'market-list';
      html += '<ul class="' + cls + '">' + list.map(function(x) { return '<li>' + escFn(x) + '</li>'; }).join('') + '</ul>';
    }
    list = [];
  };
  blocks.forEach(function(b) {
    if (!b) return;
    if (b.type === 'li') { list.push(b.text); return; }
    flush();
    if (b.type === 'h2') {
      currentH2 = String(b.text || '');
      html += forDoc
        ? '<h2 data-section="' + escFn(marketSectionKey(currentH2)) + '">' + escFn(b.text) + '</h2>'
        : '<h3 data-section="' + escFn(marketSectionKey(currentH2)) + '">' + escFn(b.text) + '</h3>';
    }
    else if (b.type === 'h3') html += '<h4>' + escFn(b.text) + '</h4>';
    else if (b.type === 'table') html += marketTableToHTML(b, escFn);
    else if (b.type === 'meta') html += '<p class="market-meta-line"><strong>' + escFn(b.text.split(':')[0]) + ':</strong>' + escFn(b.text.slice(b.text.indexOf(':') + 1)) + '</p>';
    else if (b.text) html += '<p>' + escFn(b.text) + '</p>';
  });
  flush();
  return html;
}

function formatMarketHTML(text) {
  const blocks = parseMarketBlocks(text);
  return '<div class="market-report">' + marketBlocksToHTML(blocks, false) + '</div>';
}

function buildMarketPlainText() {
  return buildTheOwlPlainText();
}



function buildTheOwlPrompt(jd, meta) {
  return `You are The Owl, an elite recruitment market mapping consultant for Southeast Asia recruitment.

Use web search when available to verify current company examples, market language, and talent-pool signals. If web search is unavailable, still produce a useful directional map, but avoid pretending salary or company-list details are verified.

Analyze the following JD and produce these sections in this exact order:

1. Role Snapshot
2. Alternative Job Titles Candidates May Use
3. Adjacent / Transferable Titles
4. Screening Scorecard
5. Sourcing Notes
6. Red Flags / False Positives Recruiters Should Screen Out
7. Hidden Talent Pools Recruiters Often Overlook
8. Industries Where These Talents Are Commonly Found
9. Types of Companies That Hire These Profiles
10. Target Companies to Source From in the Selected Market
11. Candidate Profile Patterns
12. JobStreet Search Strings
13. LinkedIn Recruiter Search Strategy
14. LinkedIn Boolean Strings
15. Google X-ray Search Strings
16. Suggested Sourcing Strategy
17. Salary Positioning and Competitiveness Observations

For the sourcing-string, screening, and notes sections, be highly practical:
- JobStreet Search Strings: give 8-12 short, paste-ready keyword searches. JobStreet searches should be simple keyword phrases, not complex nested Boolean. Use exact title phrases, skill keywords, language requirements, city/location words, and adjacent terms.
- LinkedIn Recruiter Search Strategy: give separate bullets for Title field, Keywords field, Location filter, Industry/company filters, Current/past company filters, and Exclusion keywords.
- LinkedIn Boolean Strings: give 4-6 paste-ready Boolean strings using AND/OR/quotes/parentheses, suitable for LinkedIn keyword search.
- Google X-ray Search Strings: give 4-6 paste-ready searches beginning with site:linkedin.com/in and tailored to the selected location.
- Screening Scorecard: provide a clean Markdown table with exactly these columns: Criteria | Weight | Must-Ask Question. Do not place the whole table on one line. Include hard filters, must-have tools, shift/work setup, language needs, and domain depth.
- Sourcing Notes: provide tactical recruiter notes on where to find the talent, what to pre-screen early, target-company/source-company angles, proprietary-tool equivalents, and friction points such as night shift, language, salary, or location.

FORMAT RULES:
- Return the market map only. Do not write a conversational preamble such as "Here is...".
- Do not use markdown horizontal rules like ---.
- Use short section headers and compact bullets.
- Make title/talent-pool lists very compact: 2-6 words per bullet where possible.
- Keep Alternative Job Titles and Adjacent / Transferable Titles as short bullet lists only; do not explain each title unless there is a non-obvious reason.
- Keep each bullet self-contained; avoid splitting a company name, search string, or Boolean query onto multiple lines.
- Every list item must start with "- ". Do not use standalone paragraphs for company targets or search strings.
- In target company sections, every company must be a bullet using this exact pattern: "- Company Name — reason/source angle".
- In JobStreet Search Strings, every bullet must be one paste-ready search query only, for example: "- \"Accounts Receivable\" Mandarin Kuala Lumpur".
- In LinkedIn Boolean Strings, every bullet must be one paste-ready Boolean string only.
- In Google X-ray Search Strings, every bullet must begin with site:linkedin.com/in.
- In Screening Scorecard, use a Markdown table only. After the table, add one compact bullet for the strongest red flag if needed.
- In Sourcing Notes, write practical recruiter notes like source-company angles, ERP/tool equivalents, screening traps, and outreach friction. Use compact bullets.
- Do not place company names as standalone headings unless they are category headings.
- Do not include code fences.
- Keep the output complete. If you need to be concise, reduce target-company bullets before reducing the four sourcing-string sections.
- Keep it recruiter-practical, specific, and easy to copy into a search plan.

Target location: ${meta.location}
Priority industries: ${meta.industries}
Additional instructions: ${meta.notes}
Current date: ${new Date().toLocaleDateString('en-MY', {day:'2-digit', month:'short', year:'numeric'})}

JOB DESCRIPTION:
${jd}`;
}
async function generateTheOwl() {
  var ta = document.getElementById('theOwlText');
  var jd = ((ta || {}).value || '').trim();
  var fileStatus = ((document.getElementById('theOwlFileStatus') || {}).textContent || '');
  if (ta && ta.dataset.extracting === '1' || /Extracting/i.test(fileStatus)) { showToast('Still extracting — wait for the file extraction to finish', 'info'); return; }
  if (!jd) { showToast('Paste or upload a JD first', 'err'); return; }
  if (jd.length < 80) { showToast('JD looks too short — OCR scanned files or paste more JD text', 'err'); return; }
  var route = aiRoutePayload('the_owl');
  if (!route.api_key) { showToast('Save an API key for The Owl route', 'err'); updateTheOwlRouteBadge(); return; }
  var btn = document.getElementById('theOwlBtn');
  var output = document.getElementById('theOwlOutput');
  var body = document.getElementById('theOwlBody');
  var footer = document.getElementById('theOwlFooter');
  var badge = document.getElementById('theOwlBadge');
  var meta = getMarketMeta();
  window._theOwlPlainText = '';
  window._theOwlHTML = '';
  window._theOwlMeta = meta;
  if (badge) badge.textContent = meta.location;
  if (footer) footer.style.display = 'none';
  if (output) output.classList.add('show');
  if (body) body.innerHTML = '<div style="display:flex;align-items:center;gap:10px;padding:18px;color:var(--text3);"><span class="batch-spinner"></span><span>The Owl is mapping talent pools and source-company angles…</span></div>';
  var run = markTabRunning('theowl');
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="batch-spinner"></span> Generating…'; }
  try {
    var d = await callAIProxy(buildTheOwlPrompt(jd, meta), 6200, true, 3, 'the_owl');
    var text = aiText(d);
    if (!text) {
      recordPaidAiFailure('The Owl returned empty output', d, route.model, route.provider);
      throw new Error('No text response returned from AI provider.');
    }
    var html = formatMarketHTML(text);
    if (body) body.innerHTML = html;
    window._theOwlPlainText = text;
    window._theOwlHTML = html;
    window._theOwlMeta = meta;
    if (footer) footer.style.display = 'flex';
    ['theOwlCopyBtn','theOwlWordBtn','theOwlPdfBtn'].forEach(function(id){ var el=document.getElementById(id); if(el) el.style.display=''; });
    var usage = normalizeUsageClient(d.usage || {});
    var cost = responseCost(d, route.model, route.provider);
    var owlCostEl = document.getElementById('theOwlCost');
    if (owlCostEl) { owlCostEl.style.display='inline-flex'; owlCostEl.textContent = (usage.input_tokens + usage.output_tokens).toLocaleString() + ' tokens · ' + (cost > 0 && cost < 0.0001 ? '<$0.0001' : '$' + cost.toFixed(4)); owlCostEl.title = costDetailsFromResponse(d, route.model, route.provider).cost_method || ''; }
    statsRecord('The Owl — Talent Market Map', 'owl', cost, d.model || route.model, '', d.provider || route.provider, statsMetaFromResponse(d, route.model, route.provider));
    markTabDone('theowl', run);
    var warn = d.warning ? ' · ' + d.warning : '';
    showToast('The Owl map generated' + warn, 'ok');
  } catch(e) {
    if (body) body.innerHTML = '<div style="color:var(--red);padding:16px;line-height:1.5;">Failed to generate The Owl map.<br><span style="color:var(--text3)">' + esc(e.message || 'Unknown error') + '</span></div>';
    if (footer) footer.style.display = 'none';
    markTabFailed('theowl', run);
    showToast('The Owl generation failed: ' + (e.message || 'Unknown error').split('\n')[0], 'err');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = THE_OWL_BTN_HTML; }
  }
}
function buildTheOwlPlainText() {
  var meta = window._theOwlMeta || getMarketMeta();
  var body = window._theOwlPlainText || ((document.getElementById('theOwlBody') || {}).innerText || '');
  return [
    'THE OWL TALENT MAP',
    'Generated: ' + new Date().toLocaleString('en-MY'),
    'Target location: ' + meta.location,
    'Priority industries: ' + meta.industries,
    '',
    parseMarketBlocks(body.trim()).map(function(b) {
      if (b.type === 'h2' || b.type === 'h3') return b.text.toUpperCase();
      if (b.type === 'li') return '- ' + b.text;
      if (b.type === 'table') {
        var head = (b.headers || []).join(' | ');
        var rows = (b.rows || []).map(function(r){ return r.join(' | '); }).join('\n');
        return [head, rows].filter(Boolean).join('\n');
      }
      return b.text;
    }).join('\n')
  ].filter(function(x) { return x !== null && x !== undefined; }).join('\n');
}
async function copyTheOwlReport() {
  var el = document.getElementById('theOwlBody');
  if (!el || !el.innerText.trim()) { showToast('Generate The Owl map first', 'err'); return; }
  var blocks = parseMarketBlocks(window._theOwlPlainText || el.innerText);
  var html = '<div style="font-family:Calibri,Arial,sans-serif;font-size:11pt;line-height:1.5">' + marketBlocksToHTML(blocks, true) + '</div>';
  var plain = buildTheOwlPlainText();
  try {
    if (navigator.clipboard && window.ClipboardItem) {
      await navigator.clipboard.write([new ClipboardItem({'text/html': new Blob([html], {type:'text/html'}), 'text/plain': new Blob([plain], {type:'text/plain'})})]);
      showToast('The Owl report copied with formatting', 'ok');
      return;
    }
    if (navigator.clipboard && navigator.clipboard.writeText) { await navigator.clipboard.writeText(plain); showToast('The Owl report copied as text', 'ok'); return; }
  } catch(e) {}
  var ta = document.createElement('textarea'); ta.value = plain; ta.style.position='fixed'; ta.style.left='-9999px'; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta); showToast('The Owl report copied as text', 'ok');
}
function marketTextToDocHtml(text) {
  return marketBlocksToHTML(parseMarketBlocks(text), true);
}
function theOwlWordShell(title, subtitle, bodyHtml) {
  return '<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word"><head><meta charset="UTF-8"><title>' + _escDoc(title || 'The Owl') + '</title>'
    + '<style>@page{margin:0.58in 0.62in;} body{font-family:Calibri,Arial,sans-serif;color:#1f2937;font-size:9.6pt;line-height:1.34;} .page{max-width:760px;margin:0 auto;} .brand{text-align:center;margin:0 0 10px;} .hero{border:1px solid #e7e5f4;background:#fbfbff;padding:12px 16px;margin:0 0 12px;} .hero h1{font-size:18pt;line-height:1.12;margin:0 0 4px;color:#352a86;font-weight:700;} .subtitle{font-size:8.8pt;color:#666b78;margin:0;line-height:1.3;} h2{font-size:10.1pt;line-height:1.18;text-transform:uppercase;letter-spacing:.035em;margin:13px 0 6px;color:#1d4ed8;border-top:1px solid #e5e7eb;padding-top:7px;page-break-after:avoid;} h4{font-size:9.6pt;line-height:1.22;margin:8px 0 4px;color:#374151;font-weight:700;page-break-after:avoid;} p{margin:3px 0 6px;line-height:1.34;} ul{margin:3px 0 7px 15px;padding:0;} li{margin:2px 0 3px;line-height:1.3;padding-left:1px;} .market-doc-list{margin:0 0 0 14px;padding:0;} .market-two-col{width:100%;border-collapse:collapse;margin:2px 0 7px;table-layout:fixed;} .market-two-col td{width:50%;vertical-align:top;padding:0 10px 0 0;border:0;} .market-meta-line{background:#f7f7fb;border:1px solid #e5e7eb;padding:6px 8px;color:#555;margin:3px 0 6px;} .market-table-wrap{margin:4px 0 8px;} table.market-table{width:100%;border-collapse:collapse;table-layout:fixed;font-size:8.6pt;line-height:1.2;} .market-table th,.market-table td{border:1px solid #dfe5ef;padding:5px 6px;text-align:left;vertical-align:top;} .market-table th{background:#f1f5f9;color:#111827;font-weight:700;} .market-table td:first-child{font-weight:700;} .footer{margin-top:16px;border-top:1px solid #e5e7eb;padding-top:7px;color:#9ca3af;font-size:8pt;text-align:center;}</style></head><body><div class="page"><div class="brand"><img src="' + HYPPIES_LOGO_URI + '" alt="Hyppies" style="width:74px;height:auto;display:block;border:0;margin:0 auto"></div><div class="hero"><h1>' + _escDoc(title || 'The Owl') + '</h1><p class="subtitle">' + _escDoc(subtitle || 'Hyppies') + '</p></div>' + bodyHtml + '<div class="footer">Hyppies · Confidential · For internal sourcing use only</div></div></body></html>';
}
function exportTheOwlWord() {
  var text = (window._theOwlPlainText || ((document.getElementById('theOwlBody') || {}).innerText || '')).trim();
  if (!text) { showToast('Generate The Owl map first', 'err'); return; }
  var meta = window._theOwlMeta || getMarketMeta();
  var bodyHtml = '<p class="market-meta-line"><strong>Target location:</strong> ' + _escDoc(meta.location) + '<br><strong>Priority industries:</strong> ' + _escDoc(meta.industries) + '</p>' + marketTextToDocHtml(text);
  var html = theOwlWordShell('The Owl Talent Map', 'Hyppies · ' + meta.location + ' · ' + meta.industries, bodyHtml);
  var blob = new Blob([html], {type:'application/msword'});
  var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'the-owl-talent-map-' + _safeFileStem(meta.location) + '-' + new Date().toISOString().slice(0,10) + '.doc'; a.click(); URL.revokeObjectURL(a.href);
  showToast('The Owl Word report exported', 'ok');
}
function exportTheOwlPDF() {
  var text = (window._theOwlPlainText || ((document.getElementById('theOwlBody') || {}).innerText || '')).trim();
  if (!text) { showToast('Generate The Owl map first', 'err'); return; }
  if (!(window.jspdf && window.jspdf.jsPDF)) {
    if (window.cvStudioLoadJSPDF) window.cvStudioLoadJSPDF(exportTheOwlPDF, function() { showToast('PDF library not loaded - try Word export instead', 'err'); });
    else showToast('PDF library not loaded - try Word export instead', 'err');
    return;
  }
  var jsPDF = window.jspdf.jsPDF;
  var doc = new jsPDF({ unit:'mm', format:'a4' });
  var pageW=210, pageH=297, margin=14, maxW=pageW-margin*2, y=38;
  var meta = window._theOwlMeta || getMarketMeta();
  var rawBlocks = parseMarketBlocks(text);
  var blocks = [];
  var currentSection = '';
  for (var gi=0; gi<rawBlocks.length; gi++) {
    var gb = rawBlocks[gi];
    if (!gb) continue;
    if (gb.type === 'h2') { currentSection = gb.text || ''; blocks.push(gb); continue; }
    if (gb.type === 'li') {
      var items = [];
      while (gi < rawBlocks.length && rawBlocks[gi] && rawBlocks[gi].type === 'li') { items.push(rawBlocks[gi].text || ''); gi++; }
      gi--;
      blocks.push({ type:'list', items:items, compact:isMarketCompactListHeading(currentSection) });
      continue;
    }
    blocks.push(gb);
  }
  function need(h){ if (y+h <= pageH-18) return; doc.addPage(); pageHead(); y=24; }
  function safe(t){ return cvPdfSafeText(cleanMarketExportLine(t)); }
  function pageHead(){ try{doc.addImage(HYPPIES_LOGO_URI,'JPEG',margin,6,9,9);}catch(e){} doc.setFont('helvetica','bold'); doc.setFontSize(8); doc.setTextColor(53,42,134); doc.text('The Owl', margin+12, 12); doc.setFont('helvetica','normal'); doc.setFontSize(7.2); doc.setTextColor(145,151,165); doc.text(new Date().toLocaleDateString('en-MY'), pageW-margin, 12, {align:'right'}); doc.setDrawColor(226,229,236); doc.line(margin,17,pageW-margin,17); }
  function renderHeader(){ try { doc.addImage(HYPPIES_LOGO_URI,'JPEG',margin,8,18,18); } catch(e) {} doc.setFont('helvetica','bold'); doc.setFontSize(16); doc.setTextColor(53,42,134); doc.text('The Owl Talent Map', margin+24, 16); doc.setFont('helvetica','normal'); doc.setFontSize(8); doc.setTextColor(92,99,115); doc.text('Target location: ' + safe(meta.location), margin+24, 22); doc.text('Priority industries: ' + safe(meta.industries), margin+24, 27); doc.setDrawColor(226,229,236); doc.line(margin,33,pageW-margin,33); }
  function renderList(items, compact){
    items = (items || []).filter(Boolean);
    if (!items.length) return;
    doc.setFont('helvetica','normal'); doc.setFontSize(8.2); doc.setTextColor(25,35,55);
    if (compact && items.length > 3) {
      var gap = 8, colW = (maxW - gap) / 2;
      for (var i=0; i<items.length; i+=2) {
        var left = doc.splitTextToSize(safe(items[i] || ''), colW-6);
        var right = doc.splitTextToSize(safe(items[i+1] || ''), colW-6);
        var h = Math.max(left.length, right.length) * 3.8 + 2.5;
        need(h);
        doc.text('-', margin+1.5, y); doc.text(left, margin+5.5, y);
        if (items[i+1]) { doc.text('-', margin+colW+gap+1.5, y); doc.text(right, margin+colW+gap+5.5, y); }
        y += h;
      }
    } else {
      items.forEach(function(item){ var lines=doc.splitTextToSize(safe(item), maxW-7); need(lines.length*4+2); doc.text('-', margin+1.5, y); doc.text(lines, margin+6, y); y+=lines.length*4+2; });
    }
    y += 1;
  }
  function renderTable(block){
    var headers = (block.headers || []).map(safe);
    var rows = block.rows || [];
    if (!headers.length || !rows.length) return;
    var colW;
    if (headers.length === 3 && /criteria/i.test(headers[0]) && /weight/i.test(headers[1])) colW = [maxW*0.36, maxW*0.09, maxW*0.55];
    else colW = headers.map(function(){ return maxW / headers.length; });
    function rowHeight(cells, fontSize){
      var maxLines = 1;
      cells.forEach(function(cell, i){ var lines = doc.splitTextToSize(safe(cell || ''), colW[i]-4); maxLines = Math.max(maxLines, lines.length); });
      return Math.max(8, maxLines * (fontSize === 7.4 ? 3.4 : 3.7) + 4);
    }
    var hHead = rowHeight(headers, 7.7);
    need(hHead + 2);
    var x=margin;
    doc.setFillColor(241,245,249); doc.setDrawColor(218,226,238);
    doc.setFont('helvetica','bold'); doc.setFontSize(7.6); doc.setTextColor(17,24,39);
    headers.forEach(function(head,i){ doc.rect(x,y,colW[i],hHead,'FD'); doc.text(doc.splitTextToSize(head, colW[i]-4), x+2, y+4.5); x += colW[i]; });
    y += hHead;
    rows.forEach(function(row){
      var h=rowHeight(row,7.4); need(h+1); x=margin; doc.setFont('helvetica','normal'); doc.setFontSize(7.35); doc.setTextColor(31,41,55); doc.setDrawColor(218,226,238);
      row.forEach(function(cell,i){ doc.rect(x,y,colW[i],h,'S'); if(i===0) doc.setFont('helvetica','bold'); else doc.setFont('helvetica','normal'); doc.text(doc.splitTextToSize(safe(cell || ''), colW[i]-4), x+2, y+4.2); x += colW[i]; });
      y += h;
    });
    y += 3;
  }
  renderHeader();
  blocks.forEach(function(b, idx){
    if (!b) return;
    if (b.type === 'h2') { need(13); if(idx>0)y+=1; doc.setDrawColor(232,232,238); doc.line(margin,y-1,pageW-margin,y-1); doc.setFont('helvetica','bold'); doc.setFontSize(9.6); doc.setTextColor(29,78,216); var hs=doc.splitTextToSize(safe(b.text).toUpperCase(), maxW); doc.text(hs,margin,y+5.2); y += 5.2 + hs.length*4.3 + 1.5; return; }
    if (b.type === 'h3') { var h3=doc.splitTextToSize(safe(b.text), maxW); need(h3.length*4+3); doc.setFont('helvetica','bold'); doc.setFontSize(8.7); doc.setTextColor(55,65,81); doc.text(h3,margin,y); y+=h3.length*4+1.5; return; }
    if (b.type === 'list') { renderList(b.items, b.compact); return; }
    if (b.type === 'table') { renderTable(b); return; }
    if (!b.text) return;
    var ps=doc.splitTextToSize(safe(b.text), maxW); need(ps.length*4.1+3); doc.setFont('helvetica', b.type==='meta'?'bold':'normal'); doc.setFontSize(8.3); doc.setTextColor(45,45,50); doc.text(ps, margin, y); y+=ps.length*4.1+2;
  });
  var total=doc.internal.getNumberOfPages();
  for(var pg=1; pg<=total; pg++){ doc.setPage(pg); doc.setDrawColor(235,235,235); doc.line(margin,pageH-14,pageW-margin,pageH-14); doc.setFont('helvetica','normal'); doc.setFontSize(7.2); doc.setTextColor(150,150,150); doc.text('Hyppies - Confidential - For internal sourcing use only', margin, pageH-8); doc.text('Page '+pg+' of '+total, pageW-margin, pageH-8, {align:'right'}); }
  doc.save('the-owl-talent-map-' + _safeFileStem(meta.location) + '-' + new Date().toISOString().slice(0,10) + '.pdf');
  showToast('The Owl PDF report exported', 'ok');
}
function clearTheOwl() {
  clearTabRunState('theowl');
  ['theOwlText','theOwlLocation','theOwlIndustries','theOwlNotes'].forEach(function(id){ var el=document.getElementById(id); if(el) el.value = id === 'theOwlLocation' ? 'Malaysia' : ''; });
  ['theOwlFileStatus'].forEach(function(id){ var el=document.getElementById(id); if(el) el.textContent=''; });
  var file = document.getElementById('theOwlFile'); if (file) file.value='';
  var out=document.getElementById('theOwlOutput'); if(out) out.classList.remove('show');
  var body=document.getElementById('theOwlBody'); if(body) body.innerHTML='';
  var footer=document.getElementById('theOwlFooter'); if(footer) footer.style.display='none';
  var owlCost=document.getElementById('theOwlCost'); if(owlCost){ owlCost.style.display='none'; owlCost.textContent=''; }
  ['theOwlCopyBtn','theOwlWordBtn','theOwlPdfBtn'].forEach(function(id){ var el=document.getElementById(id); if(el) el.style.display='none'; });
  window._theOwlPlainText=''; window._theOwlHTML=''; window._theOwlMeta=null;
  clearTheOwlChat();
  updateTheOwlCounts(); updateTheOwlRouteBadge();
}

// ── The Owl chat + memory monitor ───────────────────────────────────────────
var _theOwlChatMode = 'context';
var _theOwlChatMessages = [];
var _theOwlChatLastReply = '';
var _theOwlMemoryTimer = null;
var THE_OWL_CHAT_MAX_CONTEXT_MESSAGES = 12; // 6 user/assistant turns
var THE_OWL_CHAT_MAX_VISIBLE_MESSAGES = 50;

function formatOwlBytes(bytes) {
  bytes = Number(bytes || 0);
  if (!bytes || !isFinite(bytes)) return '0 MB';
  var mb = bytes / (1024 * 1024);
  if (mb < 1024) return mb.toFixed(mb >= 100 ? 0 : 1) + ' MB';
  return (mb / 1024).toFixed(2) + ' GB';
}
function updateCvMemoryBadge() {
  var el = document.getElementById('cvMemoryBadge');
  if (!el) return;
  try {
    if (window.performance && performance.memory && performance.memory.usedJSHeapSize) {
      var used = performance.memory.usedJSHeapSize;
      var total = performance.memory.totalJSHeapSize || 0;
      var limit = performance.memory.jsHeapSizeLimit || 0;
      el.textContent = 'RAM: ' + formatOwlBytes(used) + ' JS';
      el.className = 'owl-memory-badge header-memory-badge ok';
      el.title = 'Live browser JavaScript heap for this CV Studio tab. Allocated: ' + formatOwlBytes(total) + (limit ? ' · Browser limit: ' + formatOwlBytes(limit) : '') + '. This is not the full OS Task Manager process total.';
      if (limit && used / limit > 0.70) el.className = 'owl-memory-badge header-memory-badge warn';
    } else {
      el.textContent = 'RAM: browser unsupported';
      el.className = 'owl-memory-badge header-memory-badge na';
      el.title = 'This browser does not expose per-tab JavaScript memory to webpages. Chrome/Edge usually support this API.';
    }
  } catch(e) {
    el.textContent = 'RAM: unavailable';
    el.className = 'owl-memory-badge header-memory-badge na';
    el.title = 'Unable to read browser memory API.';
  }
}
function startTheOwlMemoryMonitor() {
  updateCvMemoryBadge();
  if (_theOwlMemoryTimer) return;
  _theOwlMemoryTimer = setInterval(updateCvMemoryBadge, 2500);
}
function setTheOwlChatMode(mode) {
  // v24.6.66: the toggle is redundant. Owl chat always uses available Owl/JD context,
  // but the prompt explicitly allows general questions when context is irrelevant.
  _theOwlChatMode = 'auto';
  var c = document.getElementById('theOwlChatContextBtn');
  var g = document.getElementById('theOwlChatGeneralBtn');
  var opts = document.getElementById('theOwlChatContextOptions');
  if (c) c.classList.add('active');
  if (g) g.classList.remove('active');
  if (opts) opts.style.display = 'none';
  var inp = document.getElementById('theOwlChatInput');
  if (inp) inp.placeholder = '';
}
function pushTheOwlChat(role, text, mode, cost) {
  _theOwlChatMessages.push({ role: role, text: String(text || '').trim(), mode: mode || _theOwlChatMode, cost: cost || 0, ts: new Date().toISOString() });
  if (_theOwlChatMessages.length > THE_OWL_CHAT_MAX_VISIBLE_MESSAGES) {
    _theOwlChatMessages = _theOwlChatMessages.slice(_theOwlChatMessages.length - THE_OWL_CHAT_MAX_VISIBLE_MESSAGES);
  }
  if (role === 'assistant') _theOwlChatLastReply = String(text || '').trim();
  renderTheOwlChat();
}
function owlChatInlineMarkdown(text) {
  return esc(text || '')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|\s)\*([^*\n]{2,80})\*(?=\s|$|[.,;:!?])/g, '$1<em>$2</em>');
}
function owlChatIsTableLine(line) {
  line = String(line || '').trim();
  return /^\|.+\|$/.test(line) && line.split('|').length >= 4;
}
function owlChatIsTableSeparator(line) {
  return /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(String(line || '').trim());
}
function owlChatTableCells(line) {
  line = String(line || '').trim().replace(/^\|/, '').replace(/\|$/, '');
  return line.split('|').map(function(c){ return c.trim(); });
}
function owlChatRenderTable(rows) {
  if (!rows || !rows.length) return '';
  var header = owlChatTableCells(rows[0]);
  var bodyRows = rows.slice(1).filter(function(r){ return !owlChatIsTableSeparator(r); }).map(owlChatTableCells);
  var html = '<table><thead><tr>' + header.map(function(c){ return '<th>' + owlChatInlineMarkdown(c) + '</th>'; }).join('') + '</tr></thead>';
  if (bodyRows.length) html += '<tbody>' + bodyRows.map(function(row){ return '<tr>' + header.map(function(_,i){ return '<td>' + owlChatInlineMarkdown(row[i] || '') + '</td>'; }).join('') + '</tr>'; }).join('') + '</tbody>';
  return html + '</table>';
}
function owlChatMarkdownToHtml(text) {
  var lines = String(text || '').replace(/```(?:markdown|md|text)?/gi, '').replace(/```/g, '').split(/\r?\n/);
  var html = '', list = [], ordered = false;
  function flushList(){
    if (!list.length) return;
    html += (ordered ? '<ol>' : '<ul>') + list.map(function(x){ return '<li>' + owlChatInlineMarkdown(x) + '</li>'; }).join('') + (ordered ? '</ol>' : '</ul>');
    list = []; ordered = false;
  }
  for (var i=0; i<lines.length; i++) {
    var raw = String(lines[i] || '').replace(/\s+$/,'');
    var line = raw.trim();
    if (!line) { flushList(); continue; }

    if (owlChatIsTableLine(line)) {
      flushList();
      var rows = [];
      while (i < lines.length && (owlChatIsTableLine(String(lines[i] || '').trim()) || owlChatIsTableSeparator(String(lines[i] || '').trim()))) {
        rows.push(String(lines[i] || '').trim());
        i++;
      }
      i--;
      html += owlChatRenderTable(rows);
      continue;
    }

    var quote = line.match(/^>\s*(.+)$/);
    if (quote) { flushList(); html += '<blockquote>' + owlChatInlineMarkdown(quote[1]) + '</blockquote>'; continue; }

    var heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) { flushList(); html += '<h4>' + owlChatInlineMarkdown(heading[2].replace(/#+$/,'').trim()) + '</h4>'; continue; }

    var bullet = line.match(/^[-*•]\s+(.+)$/);
    if (bullet) { if (ordered) flushList(); list.push(bullet[1].trim()); ordered = false; continue; }

    var numbered = line.match(/^\d+[.)]\s+(.+)$/);
    if (numbered) { if (list.length && !ordered) flushList(); ordered = true; list.push(numbered[1].trim()); continue; }

    flushList();
    var strongHeading = line.match(/^\*\*(.+?)\*\*:?$/);
    if (strongHeading) html += '<h4>' + owlChatInlineMarkdown(strongHeading[1]) + '</h4>';
    else if (/^[A-Z][A-Za-z0-9 /&()\-]{2,70}:$/.test(line)) html += '<h4>' + owlChatInlineMarkdown(line.replace(/:$/,'')) + '</h4>';
    else html += '<p>' + owlChatInlineMarkdown(line) + '</p>';
  }
  flushList();
  return html || '<p></p>';
}
function renderTheOwlChat() {
  var log = document.getElementById('theOwlChatLog');
  var count = document.getElementById('theOwlChatCount');
  if (count) count.textContent = String(_theOwlChatMessages.length);
  if (!log) return;
  if (!_theOwlChatMessages.length) {
    log.innerHTML = '<div class="owl-chat-empty"></div>';
    return;
  }
  log.innerHTML = _theOwlChatMessages.map(function(m) {
    var who = m.role === 'user' ? 'You' : 'The Owl';
    var cost = m.cost ? ' · $' + m.cost.toFixed(6) : '';
    return '<div class="owl-msg ' + (m.role === 'user' ? 'user' : 'assistant') + '"><div class="owl-msg-meta">' + esc(who + cost) + '</div><div class="owl-msg-body">' + owlChatMarkdownToHtml(m.text) + '</div></div>';
  }).join('');
  log.scrollTop = log.scrollHeight;
}
function clearTheOwlChat() {
  _theOwlChatMessages = [];
  _theOwlChatLastReply = '';
  renderTheOwlChat();
}
function owlTruncateForPrompt(text, limit) {
  text = String(text || '').trim();
  limit = limit || 12000;
  if (text.length <= limit) return text;
  return text.slice(0, Math.floor(limit * 0.72)) + '\n\n[...trimmed to control memory/cost...]\n\n' + text.slice(-Math.floor(limit * 0.28));
}
function theOwlRecentChatForPrompt() {
  return _theOwlChatMessages.slice(-THE_OWL_CHAT_MAX_CONTEXT_MESSAGES).map(function(m) {
    return (m.role === 'user' ? 'User' : 'The Owl') + ': ' + m.text;
  }).join('\n\n');
}
function buildTheOwlChatPrompt(question, mode) {
  var meta = getMarketMeta();
  var report = String(window._theOwlPlainText || ((document.getElementById('theOwlBody') || {}).innerText || '') || '').trim();
  var jd = String(((document.getElementById('theOwlText') || {}).value || '') || '').trim();
  var recent = theOwlRecentChatForPrompt();
  var hasReport = !!report;
  var hasJD = !!jd;
  return `You are The Owl, a practical AI assistant inside CV Studio for a recruiter.

Always consider the available Owl/JD context below when it is relevant. The user may also ask general questions; if the Owl/JD context is irrelevant, answer the general question normally and do not force the context into the answer. Be concise, useful, and honest about assumptions. Use clean short paragraphs or bullets; avoid long essays unless asked.

Do not claim to have checked live sources unless the selected route/tool actually provides evidence. Do not modify the generated Owl report.

Search focus:
- Target location: ${meta.location}
- Priority industries: ${meta.industries}
- Extra notes: ${meta.notes}

Available Owl report context:
${hasReport ? owlTruncateForPrompt(report, 14000) : '[No Owl report available yet]'}

Available original JD context:
${hasJD ? owlTruncateForPrompt(jd, 10000) : '[No original JD available]'}

Recent chat, if any:
${recent || 'None'}

User question:
${question}`;
}
function handleTheOwlChatKeydown(event) {
  if (!event || event.isComposing) return;
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    askTheOwlChat();
  }
}
async function askTheOwlChat() {
  var inp = document.getElementById('theOwlChatInput');
  var btn = document.getElementById('theOwlChatAskBtn');
  var q = ((inp || {}).value || '').trim();
  if (!q) { showToast('Type a question for The Owl first', 'err'); return; }
  var route = aiRoutePayload('the_owl');
  if (!route.api_key) { showToast('Save an API key for The Owl route', 'err'); updateTheOwlRouteBadge(); return; }
  var mode = 'auto';
  var prompt = buildTheOwlChatPrompt(q, mode);
  pushTheOwlChat('user', q, mode, 0);
  if (inp) inp.value = '';
  var run = markTabRunning('theowl');
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="batch-spinner"></span> Asking…'; }
  try {
    var hasOwlContext = !!(String(window._theOwlPlainText || ((document.getElementById('theOwlBody') || {}).innerText || '') || '').trim() || String(((document.getElementById('theOwlText') || {}).value || '') || '').trim());
    var d = await callAIProxy(prompt, 1800, hasOwlContext, 1, 'the_owl');
    var text = aiText(d).trim();
    if (!text) {
      recordPaidAiFailure('The Owl Chat returned empty output', d, route.model, route.provider);
      throw new Error('No text response returned from AI provider.');
    }
    var usage = d.usage || {};
    var cost = responseCost(d, route.model, route.provider);
    pushTheOwlChat('assistant', text, mode, cost);
    statsRecord('The Owl Chat', 'owl_chat_auto', cost, d.model || route.model, '', d.provider || route.provider, statsMetaFromResponse(d, route.model, route.provider));
    markTabDone('theowl', run);
    showToast('The Owl replied' + (cost ? ' · $' + cost.toFixed(6) : ''), 'ok');
  } catch(e) {
    pushTheOwlChat('assistant', 'Provider/error notice: ' + (e.message || 'Unknown error'), mode, 0);
    markTabFailed('theowl', run);
    showToast('The Owl chat failed: ' + (e.message || 'Unknown error').split('\n')[0], 'err');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = 'Ask'; }
    updateCvMemoryBadge();
  }
}
async function copyTheOwlLastReply() {
  if (!_theOwlChatLastReply) { showToast('No Owl reply to copy yet', 'err'); return; }
  try { await navigator.clipboard.writeText(_theOwlChatLastReply); showToast('Last Owl reply copied', 'ok'); }
  catch(e) { var ta=document.createElement('textarea'); ta.value=_theOwlChatLastReply; ta.style.position='fixed'; ta.style.left='-9999px'; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta); showToast('Last Owl reply copied', 'ok'); }
}
async function copyTheOwlChat() {
  if (!_theOwlChatMessages.length) { showToast('No Owl chat to copy yet', 'err'); return; }
  var txt = _theOwlChatMessages.map(function(m){ return (m.role === 'user' ? 'You' : 'The Owl') + ':\n' + m.text; }).join('\n\n');
  try { await navigator.clipboard.writeText(txt); showToast('Owl chat copied', 'ok'); }
  catch(e) { var ta=document.createElement('textarea'); ta.value=txt; ta.style.position='fixed'; ta.style.left='-9999px'; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta); showToast('Owl chat copied', 'ok'); }
}

// ── Floating Ask The Owl chat ───────────────────────────────────────────────
var _theOwlFloatDrag = null;
var _theOwlResizeTimer = null;
function owlFloatStorageGet(key, fallback) {
  try { var v = localStorage.getItem(key); return v === null || v === undefined ? fallback : v; } catch(e) { return fallback; }
}
function owlFloatStorageSet(key, value) {
  try { localStorage.setItem(key, String(value)); } catch(e) {}
}
function clampOwlFloatBox(left, top, width, height) {
  var vw = Math.max(320, window.innerWidth || 1024);
  var vh = Math.max(320, window.innerHeight || 768);
  width = Math.max(280, Math.min(Number(width || 420), vw - 16));
  height = Math.max(360, Math.min(Number(height || 620), vh - 16));
  left = Math.max(8, Math.min(Number(left || (vw - width - 24)), vw - width - 8));
  top = Math.max(8, Math.min(Number(top || 72), vh - height - 8));
  return { left:left, top:top, width:width, height:height };
}
function getTheOwlFloatingBox() {
  var card = document.getElementById('theOwlChatCard');
  var w = Number(owlFloatStorageGet('hy_owl_float_w', card ? card.offsetWidth : 420)) || 420;
  var h = Number(owlFloatStorageGet('hy_owl_float_h', card ? card.offsetHeight : 620)) || 620;
  var l = Number(owlFloatStorageGet('hy_owl_float_left', NaN));
  var t = Number(owlFloatStorageGet('hy_owl_float_top', NaN));
  if (!isFinite(l)) l = (window.innerWidth || 1200) - w - 24;
  if (!isFinite(t)) t = 76;
  return clampOwlFloatBox(l, t, w, h);
}
function saveTheOwlFloatingBox() {
  var card = document.getElementById('theOwlChatCard');
  if (!card || !card.classList.contains('owl-chat-floating')) return;
  var r = card.getBoundingClientRect();
  var box = clampOwlFloatBox(r.left, r.top, r.width, r.height);
  owlFloatStorageSet('hy_owl_float_left', Math.round(box.left));
  owlFloatStorageSet('hy_owl_float_top', Math.round(box.top));
  owlFloatStorageSet('hy_owl_float_w', Math.round(box.width));
  owlFloatStorageSet('hy_owl_float_h', Math.round(box.height));
}
function setTheOwlFloatingOpacity(value) {
  var card = document.getElementById('theOwlChatCard');
  var slider = document.getElementById('theOwlFloatOpacity');
  var label = document.getElementById('theOwlFloatOpacityLabel');
  var n = Math.max(55, Math.min(100, parseInt(value || '96', 10) || 96));
  owlFloatStorageSet('hy_owl_float_opacity', n);
  if (slider) slider.value = String(n);
  if (label) label.textContent = n + '%';
  if (card) card.style.opacity = (n / 100).toFixed(2);
}
function setTheOwlFloatingChat(enabled) {
  var card = document.getElementById('theOwlChatCard');
  var dock = document.getElementById('theOwlChatDock');
  var btn = document.getElementById('theOwlFloatToggle');
  if (!card || !dock) return;
  enabled = !!enabled;
  owlFloatStorageSet('hy_owl_chat_floating', enabled ? '1' : '0');
  if (enabled) {
    if (card.parentNode !== document.body) document.body.appendChild(card);
    card.classList.add('owl-chat-floating');
    var box = getTheOwlFloatingBox();
    card.style.left = box.left + 'px';
    card.style.top = box.top + 'px';
    card.style.width = box.width + 'px';
    card.style.height = box.height + 'px';
    setTheOwlFloatingOpacity(owlFloatStorageGet('hy_owl_float_opacity', '96'));
    if (btn) { btn.textContent = 'Dock'; btn.classList.add('active'); }
  } else {
    saveTheOwlFloatingBox();
    card.classList.remove('owl-chat-floating');
    card.style.left = '';
    card.style.top = '';
    card.style.width = '';
    card.style.height = '';
    card.style.opacity = '';
    dock.appendChild(card);
    if (btn) { btn.textContent = 'Float'; btn.classList.remove('active'); }
  }
}
function toggleTheOwlFloatingChat() {
  var card = document.getElementById('theOwlChatCard');
  setTheOwlFloatingChat(!(card && card.classList.contains('owl-chat-floating')));
}
function initTheOwlFloatingChat() {
  var card = document.getElementById('theOwlChatCard');
  var handle = document.getElementById('theOwlChatDragHandle');
  if (!card || !handle || card.dataset.floatInit === '1') {
    setTheOwlFloatingChat(owlFloatStorageGet('hy_owl_chat_floating', '0') === '1');
    return;
  }
  card.dataset.floatInit = '1';
  handle.addEventListener('mousedown', function(e) {
    if (!card.classList.contains('owl-chat-floating')) return;
    if (e.target && e.target.closest && e.target.closest('button,input,textarea,select,a,label')) return;
    var r = card.getBoundingClientRect();
    _theOwlFloatDrag = { dx:e.clientX - r.left, dy:e.clientY - r.top, w:r.width, h:r.height };
    e.preventDefault();
  });
  document.addEventListener('mousemove', function(e) {
    if (!_theOwlFloatDrag) return;
    var box = clampOwlFloatBox(e.clientX - _theOwlFloatDrag.dx, e.clientY - _theOwlFloatDrag.dy, _theOwlFloatDrag.w, _theOwlFloatDrag.h);
    card.style.left = box.left + 'px';
    card.style.top = box.top + 'px';
  });
  document.addEventListener('mouseup', function() {
    if (_theOwlFloatDrag) { _theOwlFloatDrag = null; saveTheOwlFloatingBox(); }
    if (card.classList.contains('owl-chat-floating')) saveTheOwlFloatingBox();
  });
  window.addEventListener('resize', function(){
    if (!card.classList.contains('owl-chat-floating')) return;
    var r = card.getBoundingClientRect();
    var box = clampOwlFloatBox(r.left, r.top, r.width, r.height);
    card.style.left = box.left + 'px'; card.style.top = box.top + 'px'; card.style.width = box.width + 'px'; card.style.height = box.height + 'px';
    saveTheOwlFloatingBox();
  });
  try {
    if (window.ResizeObserver) {
      var ro = new ResizeObserver(function(){
        if (!card.classList.contains('owl-chat-floating')) return;
        clearTimeout(_theOwlResizeTimer);
        _theOwlResizeTimer = setTimeout(saveTheOwlFloatingBox, 150);
      });
      ro.observe(card);
    }
  } catch(e) {}
  setTheOwlFloatingChat(owlFloatStorageGet('hy_owl_chat_floating', '0') === '1');
}

function initTheOwlTabUI() {
  updateTheOwlCounts();
  updateTheOwlRouteBadge();
  setTheOwlChatMode(_theOwlChatMode || 'context');
  renderTheOwlChat();
  startTheOwlMemoryMonitor();
  initTheOwlFloatingChat();
}
