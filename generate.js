/**
 * Hyppies CV Generator
 * Uses reference DOCX as template, replaces body content with generated XML
 */

const fs   = require('fs');
const path = require('path');
const AdmZip = require('adm-zip');

const dataPath = process.argv[2];
const outPath  = process.argv[3];
const cv = JSON.parse(fs.readFileSync(dataPath, 'utf8'));
const DOCUMENT_ALIGNMENT = String(cv._document_alignment || 'left').toLowerCase() === 'justify' ? 'both' : 'left';
const LEFT_ALIGNMENT_XML = '<w:jc w:val="left"/>';
const BODY_ALIGNMENT_XML = `<w:jc w:val="${DOCUMENT_ALIGNMENT}"/>`;

// ── Nested-list indent recovery ───────────────────────────────────────────────
// The plain-text extraction drops Word's w:ilvl, so multi-level bullets collapse
// to one level. The extraction side-channel (cv._bullet_levels) maps a nested
// source bullet's normalized text to its indent level; here we match each parsed
// bullet back to that level. Unmatched bullets stay at level 0 (unchanged).
// bulletMatchKey MUST mirror app.py _cv_bullet_match_key exactly.
const BULLET_MATCH_STRIP_RE = /^(?:[•●▪◦‣⁃∙·‧*‐‑‒–—―-]\s+|\((?:[0-9]{1,3}|[a-z]|[ivxlcdm]{1,4})\)\s*|\(?(?:[0-9]{1,3}|[a-z]|[ivxlcdm]{1,4})[.)\-]\s+)/i;
function bulletMatchKey(text) {
  let s = String(text == null ? '' : text).replace(/\s+/g, ' ').trim();
  for (;;) {
    const stripped = s.replace(BULLET_MATCH_STRIP_RE, '').trim();
    if (stripped === s) break;
    s = stripped;
  }
  return s.toLowerCase();
}
const BULLET_LEVEL_MAP = new Map();
(Array.isArray(cv._bullet_levels) ? cv._bullet_levels : []).forEach((e) => {
  if (e && e.text != null) BULLET_LEVEL_MAP.set(String(e.text), Math.min(Math.max(Number(e.level) || 0, 0), 8));
});
function bulletLevelFor(text) {
  return BULLET_LEVEL_MAP.get(bulletMatchKey(text)) || 0;
}

const TEMPLATE = path.join(__dirname, 'template.docx');
if (!fs.existsSync(TEMPLATE)) {
  console.error('template.docx not found');
  process.exit(1);
}

// ── Escaping ──────────────────────────────────────────────────────────────────
function esc(s) {
  return (String(s == null ? '' : (typeof s === 'object' ? JSON.stringify(s) : s)))
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}


function normalizeLanguages(value) {
  let text = String(value || '').trim();
  if (!text) return '';
  text = text.replace(/\([^)]*\)/g, ' ')
    .replace(/\b(native|fluent|professional|business|conversational|basic|intermediate|advanced|written|spoken|read|write|speaking|reading|writing|mother tongue|proficient|bilingual|trilingual|multilingual|language|languages)\b/gi, ' ');
  const aliases = [
    ['English', ['english','eng']],
    ['Bahasa Malaysia', ['bahasa malaysia','bahasa melayu','malay language','malay','bm']],
    ['Chinese', ['chinese','mandarin','putonghua','cantonese','hokkien','hakka','teochew','foochow','fuzhou','hainanese','shanghainese']],
    ['Tamil',['tamil']], ['Hindi',['hindi']], ['Japanese',['japanese','nihongo']], ['Korean',['korean']], ['Thai',['thai']],
    ['Vietnamese',['vietnamese']], ['Indonesian',['bahasa indonesia','indonesian']], ['Filipino',['filipino','tagalog']],
    ['Arabic',['arabic']], ['French',['french']], ['German',['german']], ['Spanish',['spanish']], ['Portuguese',['portuguese']],
    ['Italian',['italian']], ['Dutch',['dutch']], ['Russian',['russian']], ['Urdu',['urdu']], ['Bengali',['bengali','bangla']], ['Punjabi',['punjabi']]
  ];
  const seen = [];
  const rxAlias = (alias) => new RegExp('(^|[^A-Za-z])' + alias.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+') + '([^A-Za-z]|$)', 'i');
  const parts = text.split(/[,;|/\n]+|\s+(?:and|or|plus|&)\s+/i);
  for (const p of parts) {
    const low = String(p || '').toLowerCase().replace(/[^a-zà-öø-ÿ\s-]/g,' ').replace(/[_-]+/g,' ').replace(/\s+/g,' ').trim();
    if (!low) continue;
    let name = '';
    for (const [std, arr] of aliases) { if (arr.some(a => rxAlias(a).test(low))) { name = std; break; } }
    if (!name) name = low.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    if (name && !seen.includes(name)) seen.push(name);
  }
  const order = { English:0, 'Bahasa Malaysia':1, Chinese:2 };
  return seen.sort((a,b) => ((order[a] ?? 99) - (order[b] ?? 99)) || a.localeCompare(b)).join(', ');
}


// ── Output normalization: deterministic headings/date/company/title casing ───
// AI providers sometimes preserve source table casing differently between single
// and batch runs. Normalize only structured header fields; bullet text stays as-is.
const MONTH_ABBR = {
  jan:'Jan', january:'Jan', feb:'Feb', february:'Feb', mar:'Mar', march:'Mar', apr:'Apr', april:'Apr', may:'May',
  jun:'Jun', june:'Jun', jul:'Jul', july:'Jul', aug:'Aug', august:'Aug', sep:'Sep', sept:'Sep', september:'Sep',
  oct:'Oct', october:'Oct', nov:'Nov', november:'Nov', dec:'Dec', december:'Dec'
};
// Number -> house-style month abbreviation, mirroring cvstudio_cv_normalize so
// numeric "MM/YYYY" dates normalise to the same "Mon YYYY" style.
const MONTH_ABBR_BY_NUMBER = { 1:'Jan', 2:'Feb', 3:'Mar', 4:'Apr', 5:'May', 6:'Jun', 7:'Jul', 8:'Aug', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dec' };
const COMPANY_TOKEN_MAP = { SDN:'Sdn', BHD:'Bhd', PTE:'Pte', LTD:'Ltd', LMT:'Lmt', PVT:'Pvt', INC:'Inc', LLC:'LLC', LLP:'LLP', PLC:'PLC', CORP:'Corp', CO:'Co', COMPANY:'Company', TECH:'Tech' };
const COMPANY_BRAND_TOKEN_MAP = { IFAST:'iFAST', GRABPAY:'GrabPay', DATAIKU:'Dataiku', YOUTUBE:'YouTube' };
const ACRONYM_KEEP = new Set(['AI','ML','BI','IT','HR','QA','UA','UX','UI','PMO','PM','AWS','GCP','SQL','ETL','ELT','SSIS','SSRS','SSAS','ADF','DBA','RDS','EMR','EC2','S3','IAM','API','APAC','SEA','ERP','SAP','FICO','MSBI','MSC','IBM','CGI','EPAM','TCS','HP','HSBC','DBS','OCBC','UOB','AIA','IHH','RHB','CIMB','EY','KPMG','PWC','BNM','AML','LLC','LLP','PLC']);
const TITLE_TOKEN_MAP = { 'SR':'Sr', 'SR.':'Sr.', 'JR':'Jr', 'JR.':'Jr.', 'VP':'VP', 'AVP':'AVP' };

function smartTokenCase(token, opts = {}) {
  const raw = String(token == null ? '' : token);
  const stripped = raw.replace(/[^A-Za-z0-9&.+#]/g, '');
  if (!stripped) return raw;
  const upper = stripped.toUpperCase();
  let replacement = null;
  if (opts.company && COMPANY_BRAND_TOKEN_MAP[upper]) replacement = COMPANY_BRAND_TOKEN_MAP[upper];
  else if (opts.company && /^[A-Za-z]+$/.test(stripped) && /[a-z]/.test(stripped) && /[A-Z]/.test(stripped) && !(stripped.charAt(0) === stripped.charAt(0).toUpperCase() && stripped.slice(1) === stripped.slice(1).toLowerCase())) replacement = stripped;
  else if (opts.company && COMPANY_TOKEN_MAP[upper]) replacement = COMPANY_TOKEN_MAP[upper];
  else if (opts.title && TITLE_TOKEN_MAP[upper]) replacement = TITLE_TOKEN_MAP[upper];
  else if (ACRONYM_KEEP.has(upper) || (upper.length <= 3 && upper === stripped && /^[A-Z]+$/.test(stripped)) || (upper === stripped && /^[A-Z]{2,}$/.test(stripped) && !/[AEIOU]/.test(stripped))) replacement = upper;
  else return raw.toLowerCase().replace(/[A-Za-z]+/g, function(w){ return w.charAt(0).toUpperCase() + w.slice(1); });
  const idx = raw.indexOf(stripped);
  return idx >= 0 ? raw.slice(0, idx) + replacement + raw.slice(idx + stripped.length) : replacement;
}

function smartTitleText(value, opts = {}) {
  const text = String(value == null ? '' : value).trim();
  if (!text) return '';
  const letters = text.match(/[A-Za-z]/g) || [];
  const upperCount = letters.filter(ch => ch === ch.toUpperCase()).length;
  const ratio = letters.length ? (upperCount / letters.length) : 0;
  if (ratio < 0.72) {
    if (opts.company) {
      return text.split(/(\s+|\/|\||,|;|\(|\)|\[|\])/g).map(function(part){
        if (!part || /^\s+$/.test(part) || /^(\/|\||,|;|\(|\)|\[|\])$/.test(part)) return part;
        const stripped = String(part).replace(/[^A-Za-z0-9&.+#]/g, '');
        const upper = stripped.toUpperCase();
        if (COMPANY_BRAND_TOKEN_MAP[upper] || COMPANY_TOKEN_MAP[upper] || ACRONYM_KEEP.has(upper)) return smartTokenCase(part, opts);
        // Normalize stray lowercase words in company names while preserving
        // brand-like mixed-case tokens such as iFAST, GrabPay, Dataiku.
        if (/^[a-z]+$/.test(stripped) && stripped.length > 2) return smartTokenCase(part, opts);
        return part;
      }).join('').trim();
    }
    return opts.title ? text.replace(/\bSR\.?\b/g, 'Sr.').replace(/\bJR\.?\b/g, 'Jr.') : text;
  }
  return text.split(/(\s+|\/|\||,|;|\(|\)|\[|\])/g).map(function(part){
    if (!part || /^\s+$/.test(part) || /^(\/|\||,|;|\(|\)|\[|\])$/.test(part)) return part;
    return smartTokenCase(part, opts);
  }).join('').trim();
}

function normalizeDateRange(value) {
  let text = String(value == null ? '' : value).trim();
  if (!text) return '';
  text = text.replace(/[–—−]/g, '-');
  text = text.replace(/\b(till\s*date|till\s*now|to\s*date|current|presently|now)\b/gi, 'Present');
  text = text.replace(/\bpresent\b/gi, 'Present');
  // ISO YYYY-MM(-DD) -> "Mon YYYY" BEFORE turning "-" into "to", so a range like
  // "2020-06 to 2025-07" is not shredded into "2020 to 06 to 2025 to 07".
  const isoRepl = function(m, yyyy, mm){ const n = parseInt(mm, 10); return (n >= 1 && n <= 12) ? (MONTH_ABBR_BY_NUMBER[n] + ' ' + yyyy) : m; };
  text = text.replace(/\b((?:19|20)\d{2})-(0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])\b/g, isoRepl);
  text = text.replace(/\b((?:19|20)\d{2})-(0[1-9]|1[0-2])\b/g, isoRepl);
  text = text.replace(/\s*-\s*/g, ' to ');
  text = text.replace(/\s+to\s+/gi, ' to ');
  text = text.replace(/\b(January|February|March|April|June|July|August|September|Sept|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\b/gi, function(m){
    return MONTH_ABBR[String(m).toLowerCase().replace(/\.$/, '')] || m;
  });
  // Numeric MM/YYYY -> "Mon YYYY" so date format is consistent regardless of
  // whether a given parse run emitted "06/2024" or "Jun 2024".
  text = text.replace(/\b(\d{1,2})\/(\d{4})\b/g, function(m, mm, yyyy){
    const n = parseInt(mm, 10);
    return (n >= 1 && n <= 12) ? (MONTH_ABBR_BY_NUMBER[n] + ' ' + yyyy) : m;
  });
  return text.replace(/\s+/g, ' ').trim();
}

function stripInferredCvTitle(value) {
  const text = String(value || '').trim();
  return /\s*[\[(]\s*(?:inferred|implied|assumed|guessed|likely)\s+(?:from|based\s+on)\s+(?:responsibilit(?:y|ies)|duties|job\s+content|role\s+content|context)\s*[\])]\s*$/i.test(text) ? '' : text;
}

function canonicalCvSectionHeading(value) {
  const text = String(value || '').trim();
  const match = text.match(/^(?:key\s+)?(responsibilit(?:y|ies)|achievements?)\s*:?$/i);
  if (!match) return text;
  return /^achievement/i.test(match[1]) ? 'Key achievements' : 'Key responsibilities';
}

// Strip a redundant leading list glyph the author typed inside a bullet.
// Some source CVs prefix an already-bulleted line with "* " or "- ", which
// renders as a doubled bullet ("• * Mail Server"). Remove one or more leading
// markers followed by whitespace; "*args" / "**bold**" (no space) are left as-is.
const LEADING_BULLET_MARKER_RE = /^(?:[•●▪◦‣⁃∙·‧*‐‑‒–—―-]\s+|\((?:[0-9]{1,3}|[a-z]|[ivxlcdm]{1,4})\)\s*|\(?(?:[0-9]{1,3}|[a-z]|[ivxlcdm]{1,4})[.)\-]\s+)+/i;
function stripLeadingBulletMarker(text) {
  if (typeof text !== 'string') return text;
  return text.replace(LEADING_BULLET_MARKER_RE, '');
}

function normalizeCvBulletItems(items, allowStandaloneSections = true) {
  const source = Array.isArray(items) ? items : ((items == null || items === '') ? [] : [items]);
  const out = [];
  const add = (item) => {
    if (typeof item === 'string') {
      const trimmed = item.trim();
      const candidate = stripLeadingBulletMarker(trimmed);
      const markerRemoved = candidate !== trimmed;
      if (allowStandaloneSections && /^(?:key\s+)?(?:responsibilit(?:y|ies)|achievements?)\s*:?$/i.test(candidate)) {
        out.push({ heading: canonicalCvSectionHeading(candidate), bullets: [], kind: 'section' });
        return;
      }
      if (candidate && ((candidate[0] === '{' && candidate[candidate.length - 1] === '}') || (candidate[0] === '[' && candidate[candidate.length - 1] === ']'))) {
        try {
          const decoded = JSON.parse(candidate);
          if (decoded && typeof decoded === 'object') {
            const before = out.length;
            add(decoded);
            if (out.length === before) out.push(item);
            return;
          }
        } catch (_) {}
      }
      if (candidate) out.push(markerRemoved ? candidate : item);
      return;
    }
    if (Array.isArray(item)) { item.forEach(add); return; }
    if (!item || typeof item !== 'object') {
      if (item != null && String(item).trim()) out.push(String(item));
      return;
    }
    const rawHeading = item.heading || item.title || '';
    const heading = canonicalCvSectionHeading(rawHeading);
    const bullets = normalizeCvBulletItems(item.bullets || item.items || [], false);
    if (heading) {
      const group = { heading, bullets };
      if (item.kind) group.kind = String(item.kind);
      else if (/^(?:key\s+)?(?:responsibilit(?:y|ies)|achievements?)\s*:?$/i.test(String(rawHeading).trim())) group.kind = 'section';
      out.push(group);
    } else {
      bullets.forEach(add);
    }
  };
  source.forEach(add);
  return out;
}

function normalizeCvStructuredContent(cvData) {
  if (!cvData || typeof cvData !== 'object') return cvData;
  const candidate = cvData.candidate || {};
  candidate.current_position = stripInferredCvTitle(candidate.current_position);
  cvData.candidate = candidate;
  (cvData.work_experiences || []).forEach((exp) => {
    (Array.isArray(exp && exp.roles) ? exp.roles : []).forEach((role) => {
      if (!role || typeof role !== 'object') return;
      role.title = stripInferredCvTitle(role.title);
      role.bullets = normalizeCvBulletItems(role.bullets);
    });
  });
  const certifications = Array.isArray(cvData.certifications) ? cvData.certifications : (cvData.certifications ? [cvData.certifications] : []);
  cvData.certifications = certifications.filter((value) => String(value || '').trim());
  const skills = Array.isArray(cvData.skills) ? cvData.skills : [];
  cvData.skills = skills.filter((value) => value && typeof value === 'object' && (String(value.category || '').trim() || String(value.items || '').trim()));
  return cvData;
}

function normalizeCvDataForOutput(cvData) {
  if (!cvData || typeof cvData !== 'object') return cvData;
  normalizeCvStructuredContent(cvData);
  const c = cvData.candidate || {};
  if (c.current_company) c.current_company = smartTitleText(c.current_company, { company: true });
  if (c.current_position) c.current_position = smartTitleText(c.current_position, { title: true });
  cvData.candidate = c;
  (cvData.work_experiences || []).forEach(function(exp){
    if (!exp || typeof exp !== 'object') return;
    if (exp.date_range) exp.date_range = normalizeDateRange(exp.date_range);
    if (exp.company) exp.company = smartTitleText(exp.company, { company: true });
    (Array.isArray(exp.roles) ? exp.roles : []).forEach(function(role){
      if (!role || typeof role !== 'object') return;
      if (role.date_range) role.date_range = normalizeDateRange(role.date_range);
      if (role.title) role.title = smartTitleText(role.title, { title: true });
    });
  });
  (cvData.education || []).forEach(function(edu){ if (edu && edu.date_range) edu.date_range = normalizeDateRange(edu.date_range); });
  return cvData;
}

normalizeCvDataForOutput(cv);

function experienceHeader(exp) {
  const date = normalizeDateRange((exp && exp.date_range) || '');
  const company = smartTitleText((exp && exp.company) || '', { company: true });
  if (date && company) return `${date} | ${company}`;
  return company || date || '';
}


// ── Paragraph builder ─────────────────────────────────────────────────────────
let _paraCounter = 1;
function para(children, pPrXml = '') {
  const pid = (_paraCounter++).toString(16).toUpperCase().padStart(8, '0');
  return `<w:p w14:paraId="${pid}" w14:textId="77777777" w:rsidR="00486419" w:rsidRDefault="00486419">${pPrXml ? '<w:pPr>' + pPrXml + '</w:pPr>' : ''}${children}</w:p>`;
}

function run(text, opts = {}) {
  const t = String(text == null ? '' : (typeof text === 'object' ? JSON.stringify(text) : text));
  const bold = opts.bold ? '<w:b/><w:bCs/>' : '';
  const italic = opts.italic ? '<w:i/><w:iCs/>' : '';
  const color = opts.color ? `<w:color w:val="${opts.color}"/>` : '';
  const size = opts.size ? `<w:sz w:val="${opts.size}"/><w:szCs w:val="${opts.size}"/>` : '';
  const rPr = bold || italic || color || size ? `<w:rPr>${bold}${italic}${color}${size}</w:rPr>` : '';
  const space = (t.startsWith(' ') || t.endsWith(' ')) ? ' xml:space="preserve"' : '';
  return `<w:r>${rPr}<w:t${space}>${esc(t)}</w:t></w:r>`;
}

function emptyPara() {
  return `<w:p><w:pPr><w:rPr><w:color w:val="000000"/></w:rPr></w:pPr></w:p>`;
}

// ── Section headers (blue, bold, 22pt) ────────────────────────────────────────
function sectionHeader(text) {
  const pPr = `${LEFT_ALIGNMENT_XML}<w:keepNext/><w:rPr><w:b/><w:bCs/><w:color w:val="004990"/><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr>`;
  return para(run(text, { bold: true, color: '004990', size: 22 }), pPr);
}

// ── Bold black text (16pt for headers, 24pt for titles) ──────────────────────
function boldBlackPara(text, size = 24) {
  const pPr = `${LEFT_ALIGNMENT_XML}<w:keepNext/><w:rPr><w:b/><w:bCs/><w:color w:val="000000"/><w:sz w:val="${size}"/><w:szCs w:val="${size}"/></w:rPr>`;
  return para(run(text, { bold: true, color: '000000', size }), pPr);
}

// ── Bullet paragraph (uses ListParagraph style, indent, 24pt size) ────────────
function bulletPara(text, alignmentXml = BODY_ALIGNMENT_XML) {
  const t = String(text == null ? '' : (typeof text === 'object' ? (text.text || text.heading || '') : text));
  // Parse **bold** inline
  const parts = t.split(/(\*\*[^*]+\*\*)/g);
  let children = '';
  for (const p of parts) {
    if (p.startsWith('**') && p.endsWith('**')) {
      children += run(p.slice(2, -2), { bold: true, color: '000000', size: 24 });
    } else if (p) {
      children += run(p, { color: '000000', size: 24 });
    }
  }
  // Restore nested-list indent: match this bullet back to its source level.
  // Level 0 keeps the exact prior pPr (left=720), so non-nested output is
  // byte-identical; deeper levels step the indent to match the template's
  // numbering (left = 720 * (level + 1)).
  const level = bulletLevelFor(t);
  const leftIndent = 720 * (level + 1);
  const pPr = `<w:pStyle w:val="ListParagraph"/><w:keepLines/><w:numPr><w:ilvl w:val="${level}"/><w:numId w:val="47"/></w:numPr><w:ind w:left="${leftIndent}" w:hanging="360"/><w:spacing w:before="0" w:after="0"/>${alignmentXml}`;
  return para(children, pPr);
}

// ── About Him table ───────────────────────────────────────────────────────────
function makeAboutTable(c, cv) {
  const fill = 'DEEBF6';
  function tc(width, content, borders = '', span = null) {
    const spanXml = span ? `<w:gridSpan w:val="${span}"/>` : '';
    return `<w:tc><w:tcPr><w:tcW w:w="${width}" w:type="dxa"/>${spanXml}<w:tcBorders>${borders}</w:tcBorders><w:shd w:val="clear" w:color="auto" w:fill="${fill}"/><w:tcMar><w:top w:w="80" w:type="dxa"/><w:left w:w="120" w:type="dxa"/><w:bottom w:w="80" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tcMar></w:tcPr>${content}</w:tc>`;
  }

  const dotBorder = `w:val="dotted" w:sz="4" w:space="0" w:color="000000"`;
  const dBottom = `<w:bottom ${dotBorder}/>`;
  const dRight = `<w:right ${dotBorder}/>`;
  const dLeft = `<w:left ${dotBorder}/>`;
  const dTop = `<w:top ${dotBorder}/>`;

  // Row 1: Name (span 2) | Notice Period
  const row1 = `<w:tr><w:trPr><w:trHeight w:val="719" w:type="exact"/></w:trPr>
    ${tc(6021, para(run(c.name || '', { bold: true, size: 44 })), dBottom + dRight, 2)}
    ${tc(2999, para(run('NOTICE PERIOD: ', { bold: true })) + para(run(c.notice_period || '', { bold: true })), dBottom + dLeft, null)}
  </w:tr>`;

  // Row 2: Position | Company
  const isEmployed = c.is_employed !== false; // default true if missing
  const posLabel = isEmployed ? 'CURRENT POSITION:' : 'LAST POSITION:';
  const compLabel = isEmployed ? 'CURRENT COMPANY:' : 'LAST COMPANY:';
  // Fallback: if current_position/current_company are empty, derive from most recent work experience
  const firstJob = (cv && cv.work_experiences && cv.work_experiences[0]) || null;
  const firstRole = firstJob && firstJob.roles && firstJob.roles[0];
  const posValue = c.current_position || (firstRole && firstRole.title) || '';
  const compValue = c.current_company || (firstJob && firstJob.company) || '';
  const row2 = `<w:tr>
    ${tc(4820, para(run(posLabel, { bold: true })) + para(run(posValue)), dTop + dBottom + dRight)}
    ${tc(4200, para(run(compLabel, { bold: true })) + para(run(compValue)), dTop + dBottom + dLeft, 2)}
  </w:tr>`;

  // Row 3: Languages
  const row3 = `<w:tr>
    ${tc(9020, para(run('LANGUAGES: ' + normalizeLanguages(c.languages || ''), { bold: true })) + emptyPara(), dTop, 3)}
  </w:tr>`;

  return `<w:tbl>
    <w:tblPr>
      <w:tblStyle w:val="a0"/>
      <w:tblW w:w="9020" w:type="dxa"/>
      <w:tblInd w:w="-108" w:type="dxa"/>
      <w:tblBorders><w:top w:val="nil"/><w:left w:val="nil"/><w:bottom w:val="nil"/><w:right w:val="nil"/><w:insideH w:val="nil"/><w:insideV w:val="nil"/></w:tblBorders>
      <w:tblLayout w:type="fixed"/>
      <w:tblLook w:val="0400"/>
    </w:tblPr>
    <w:tblGrid><w:gridCol w:w="4820"/><w:gridCol w:w="1201"/><w:gridCol w:w="2999"/></w:tblGrid>
    ${row1}${row2}${row3}
  </w:tbl>`;
}

// ── Work experience ───────────────────────────────────────────────────────────
function makeWorkSection(experiences) {
  experiences = (experiences || []).filter(exp => exp && typeof exp === 'object' && Array.isArray(exp.roles) && exp.roles.length);
  if (!experiences.length) return '';
  let xml = emptyPara();
  xml += sectionHeader('W O R K   E X P E R I E N C E S                     __________________________________________');
  xml += emptyPara();

  for (let ei = 0; ei < experiences.length; ei++) {
    const exp = experiences[ei];
    const roles = Array.isArray(exp.roles) ? exp.roles : [];
    for (let ri = 0; ri < roles.length; ri++) {
      const role = roles[ri];

      // First role: company date/name header
      if (ri === 0) {
        xml += boldBlackPara(experienceHeader(exp), 24);
      }

      // Role title
      const plainRoleTitle = String(role.title || '').trim();
      const roleTitle = (plainRoleTitle && roles.length > 1 && role.date_range)
        ? `${plainRoleTitle} (${role.date_range})` : plainRoleTitle;
      if (String(roleTitle || '').trim()) xml += boldBlackPara(roleTitle, 24);

      // Reason for leaving
      if (role.reason_for_leaving) {
        xml += para(
          run('Reason for Leaving: ', { bold: true, color: '000000', size: 24 }) +
          run(role.reason_for_leaving, { italic: true, color: '000000', size: 24 }),
          BODY_ALIGNMENT_XML
        );
      }

      // Bullets — support plain strings and {heading, bullets} subheader groups
      const bulletItems = role.bullets || [];
      for (let bi = 0; bi < bulletItems.length; bi++) {
        const b = bulletItems[bi];
        if (typeof b === 'string') {
          xml += bulletPara(b);
        } else if (b && typeof b === 'object' && b.heading) {
          const subBullets = b.bullets || [];
          // Structured headings must remain headings regardless of bullet count.
          if (bi > 0) xml += emptyPara();
          xml += boldBlackPara(b.heading, 24);
          for (const sub of subBullets) {
            xml += bulletPara(sub);
          }
        }
      }

      // 1 empty line after each role within the same company (except last role of last company)
      if (ri < roles.length - 1) {
        xml += emptyPara(); // spacing between roles in same company
      }
    }

    // 2 empty lines between companies (except after the last company)
    if (ei < experiences.length - 1) {
      xml += emptyPara() + emptyPara();
    }
  }
  xml += emptyPara(); // spacing after last company before next section
  return xml;
}

// ── Education ─────────────────────────────────────────────────────────────────
function makeEducationSection(education) {
  education = (education || []).filter(edu => edu && typeof edu === 'object' && (String(edu.institution || '').trim() || String(edu.degree || '').trim() || String(edu.description || '').trim()));
  if (!education.length) return '';
  let xml = sectionHeader('E D U C A T I O N S  &  T R A I N I N G     ______________________________________');
  xml += emptyPara();
  for (const edu of education) {
    // Date range + Institution on first line (bold)
    const datePrefix = edu.date_range ? edu.date_range + ' | ' : '';
    xml += para(run(datePrefix + edu.institution, { bold: true, color: '000000', size: 24 }), LEFT_ALIGNMENT_XML);
    // Degree on second line (bold, same style as institution)
    xml += para(run(edu.degree, { bold: true, color: '000000', size: 24 }), LEFT_ALIGNMENT_XML);
    // Canonical field names are cgpa/honors/description. Also accept a few
    // safe fallback names so content never silently disappears if the AI
    // parser ever drifts from the exact schema.
    const cgpa = edu.cgpa || edu.gpa || '';
    const honors = edu.honors || edu.honours || edu.awards || edu.distinctions || '';
    const description = edu.description || edu.thesis || edu.dissertation || edu.project || '';
    // CGPA, if present, on its own plain (non-bold) line
    if (cgpa && String(cgpa).trim()) {
      xml += para(run(String(cgpa).trim(), { color: '000000', size: 24 }), LEFT_ALIGNMENT_XML);
    }
    // Honors/awards/distinctions, if present, on its own plain line
    if (honors && String(honors).trim()) {
      xml += para(run(String(honors).trim(), { color: '000000', size: 24 }), LEFT_ALIGNMENT_XML);
    }
    // Thesis/project description, if present, italicized and preserved verbatim
    if (description && String(description).trim()) {
      xml += emptyPara();
      xml += para(run(String(description).trim(), { italic: true, color: '000000', size: 24 }), BODY_ALIGNMENT_XML);
    }
    xml += emptyPara();
  }
  return xml;
}

// ── Additional info ───────────────────────────────────────────────────────────
function makeAdditionalSection(certs, skills) {
  certs = (certs || []).filter(c => String(c || '').trim());
  skills = (skills || []).filter(s => s && typeof s === 'object' && (String(s.category || '').trim() || String(s.items || '').trim()));
  if (!certs.length && !skills.length) return '';

  let xml = sectionHeader('A D D I T I O N A L   I N F O R M A T I O N    ______________________________________');
  xml += emptyPara();

  if (certs.length > 0) {
    xml += boldBlackPara('License and Certification:', 24);
    for (const c of certs) {
      xml += bulletPara(c, LEFT_ALIGNMENT_XML);
    }
    xml += emptyPara();
  }

  if (skills.length > 0) {
    xml += boldBlackPara('Skills:', 24);
    xml += emptyPara();
    for (const s of skills) {
      // Category label on its own bold line
      const category = String(s.category || '').trim();
      if (category && !/^skills?$/i.test(category)) xml += boldBlackPara(category + ':', 24);
      // Items — handle both array and newline-separated string
      const rawItems = s.items || '';
      const lines = Array.isArray(rawItems)
        ? rawItems.map(l => String(l).trim()).filter(l => l.length > 0)
        : String(rawItems).split(/\n/).map(l => l.trim()).filter(l => l.length > 0);
      if (!lines.length) continue;
      if (lines.length > 1) {
        for (const line of lines) {
          xml += bulletPara(line, LEFT_ALIGNMENT_XML);
        }
      } else {
        xml += para(run(lines[0], { color: '000000', size: 24 }), LEFT_ALIGNMENT_XML);
      }
      xml += emptyPara();
    }
  }

  return xml;
}

// ── Footer ────────────────────────────────────────────────────────────────────
const FOOTER = `This Introduction shall be deemed Confidential Information for the purposes of Hyppies' standard Terms and Conditions ("T&Cs"). By receiving this Introduction, you and any person in your organization accessing the Information, agree to strictly observe and be bound by the confidentiality obligations set forth in the T&Cs and not to reveal the Information to any third party or contact any third party in relation thereto without Hyppies' prior express written consent. In case you decide to interview the Applicant, you also hereby agree that the T&Cs shall apply and the Fees stated therein (or 30% of the Applicant's Annual Total Remuneration, whatever is higher) shall accrue and be due as soon as you decide to Engage the Applicant. Unless otherwise defined, capitalized terms used herein shall have the same meaning as in the T&Cs.`;

function makeTnCBody() {
  const rPr = `<w:rFonts w:ascii="Quattrocento Sans" w:hAnsi="Quattrocento Sans" w:cs="Quattrocento Sans"/><w:i/><w:iCs/><w:color w:val="A6A6A6"/><w:sz w:val="16"/><w:szCs w:val="16"/>`;

  // framePr anchors the paragraph to the bottom of the page (like a pinned footer in body)
  // w:wrap="none", hAnchor="margin", vAnchor="margin", y=0 from bottom, h=auto
  // w:x and w:w span the full text width (approx 9026 twips for A4 with 1" margins)
  const framePr = `<w:framePr w:w="9026" w:hSpace="0" w:wrap="around" w:vAnchor="margin" w:hAnchor="margin" w:x="0" w:xAlign="left" w:yAlign="bottom"/>`;

  // T&C paragraph — justified, no underline, anchored to bottom via frame
  const tncPPr = `<w:pPr>${framePr}<w:jc w:val="both"/><w:rPr>${rPr}</w:rPr></w:pPr>`;
  const tncPara = `<w:p>${tncPPr}<w:r><w:rPr>${rPr}</w:rPr><w:t xml:space="preserve">${esc(FOOTER)}</w:t></w:r></w:p>`;

  // "Private & Confidential" line — centred, same frame, with spacing above
  const privPPr = `<w:pPr>${framePr}<w:jc w:val="center"/><w:spacing w:before="120"/><w:rPr>${rPr}</w:rPr></w:pPr>`;
  const privPara = `<w:p>${privPPr}<w:r><w:rPr>${rPr}</w:rPr><w:t>Private &amp; Confidential | &#169; Hyppies.com</w:t></w:r></w:p>`;

  return tncPara + privPara;
}

function makeWordFooterXml() {
  const rPr = '<w:rPr><w:rFonts w:ascii="Quattrocento Sans" w:hAnsi="Quattrocento Sans" w:cs="Quattrocento Sans"/><w:i/><w:iCs/><w:color w:val="A6A6A6"/><w:sz w:val="16"/><w:szCs w:val="16"/></w:rPr>';
  const pPr = '<w:pPr><w:jc w:val="center"/><w:rPr><w:rFonts w:ascii="Quattrocento Sans" w:hAnsi="Quattrocento Sans" w:cs="Quattrocento Sans"/><w:i/><w:iCs/><w:color w:val="A6A6A6"/><w:sz w:val="16"/><w:szCs w:val="16"/></w:rPr></w:pPr>';
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:p>${pPr}<w:r>${rPr}<w:t>Private &amp; Confidential | &#169; Hyppies.com</w:t></w:r></w:p>
</w:ftr>`;
}

// ── Main: Read template, replace body ─────────────────────────────────────────
const zip = new AdmZip(TEMPLATE);
const docEntry = zip.getEntry('word/document.xml');
let docXml = docEntry.getData().toString('utf8');

const bodyStart = docXml.indexOf('<w:body>') + '<w:body>'.length;
const bodyEnd = docXml.lastIndexOf('</w:body>');

// Extract the drawing paragraph (design) from the template
const bodyContent = docXml.slice(bodyStart, bodyEnd);
const mcEnd = bodyContent.indexOf('</mc:AlternateContent>') + '</mc:AlternateContent>'.length;
const outerParaEnd = bodyContent.indexOf('</w:p>', mcEnd) + '</w:p>'.length;
const drawingPara = bodyContent.slice(0, outerParaEnd);

// Extract sectPr
const sectPrMatch = docXml.match(/<w:sectPr[\s\S]*?<\/w:sectPr>/);
const sectPr = sectPrMatch ? sectPrMatch[0] : '';

// Build new body content
const c = cv.candidate || {};
const newBodyContent =
  drawingPara +
  makeAboutTable(c, cv) +
  emptyPara() + emptyPara() +
  makeWorkSection(cv.work_experiences || []) +
  makeEducationSection(cv.education || []) +
  makeAdditionalSection(cv.certifications || [], cv.skills || []) +
  emptyPara() +
  makeTnCBody();

// Patch sectPr to reference the footer
const patchedSectPr = sectPr.includes('w:footerReference')
  ? sectPr
  : sectPr.replace('<w:sectPr', '<w:sectPr').replace('>', '><w:footerReference w:type="default" r:id="rIdFooter1"/>');

// Assemble new document
const newDocXml =
  docXml.slice(0, bodyStart) +
  '\n' + newBodyContent + '\n' +
  patchedSectPr +
  '</w:body>' +
  docXml.slice(bodyEnd + '</w:body>'.length);

// Write output manually to avoid adm-zip duplicate entry bug
// Read all entries from template, replace document.xml, write fresh zip
const newDocBuf = Buffer.from(newDocXml, 'utf8');
const outZip = new AdmZip();

// Copy all entries from template except document.xml
zip.getEntries().forEach(entry => {
  if (entry.entryName === 'word/document.xml') return; // skip - we add fresh below
  if (entry.isDirectory) {
    outZip.addFile(entry.entryName, Buffer.alloc(0));
  } else {
    outZip.addFile(entry.entryName, entry.getData());
  }
});

// Add fresh document.xml
outZip.addFile('word/document.xml', newDocBuf);

// ── Inject Word footer ──────────────────────────────────────────────────────
// 1. Add footer XML file
outZip.addFile('word/footer_tnc.xml', Buffer.from(makeWordFooterXml(), 'utf8'));

// 2. Patch _rels/document.xml.rels to register the footer relationship
const relsEntry = outZip.getEntry('word/_rels/document.xml.rels');
if (relsEntry) {
  let relsXml = relsEntry.getData().toString('utf8');
  if (!relsXml.includes('rIdFooter1')) {
    relsXml = relsXml.replace('</Relationships>',
      '<Relationship Id="rIdFooter1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer_tnc.xml"/></Relationships>');
    outZip.updateFile('word/_rels/document.xml.rels', Buffer.from(relsXml, 'utf8'));
  }
}

// 3. Patch [Content_Types].xml to register the footer content type
const ctEntry = outZip.getEntry('[Content_Types].xml');
if (ctEntry) {
  let ctXml = ctEntry.getData().toString('utf8');
  if (!ctXml.includes('footer_tnc.xml')) {
    ctXml = ctXml.replace('</Types>',
      '<Override PartName="/word/footer_tnc.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/></Types>');
    outZip.updateFile('[Content_Types].xml', Buffer.from(ctXml, 'utf8'));
  }
}
outZip.writeZip(outPath);
console.log('OK: ' + outPath);
