'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const html = require('./frontend_sources').frontendSource();

function functionRange(source, name) {
  const marker = 'function ' + name + '(';
  const functionStart = source.indexOf(marker);
  if (functionStart < 0) throw new Error('Missing function: ' + name);
  const start = functionStart >= 6 && source.slice(functionStart - 6, functionStart) === 'async '
    ? functionStart - 6
    : functionStart;
  const brace = source.indexOf('{', functionStart + marker.length);
  let depth = 0, quote = '', escaped = false, lineComment = false, blockComment = false;
  for (let index = brace; index < source.length; index += 1) {
    const char = source[index], next = source[index + 1] || '';
    if (lineComment) { if (char === '\n') lineComment = false; continue; }
    if (blockComment) { if (char === '*' && next === '/') { blockComment = false; index += 1; } continue; }
    if (quote) { if (escaped) escaped = false; else if (char === '\\') escaped = true; else if (char === quote) quote = ''; continue; }
    if (char === '/' && next === '/') { lineComment = true; index += 1; continue; }
    if (char === '/' && next === '*') { blockComment = true; index += 1; continue; }
    if (char === '"' || char === "'" || char.charCodeAt(0) === 96) { quote = char; continue; }
    if (char === '{') depth += 1;
    if (char === '}' && --depth === 0) return {start, end: index + 1, source: source.slice(start, index + 1)};
  }
  throw new Error('Unterminated function: ' + name);
}

function functions(names) {
  return names.map(name => functionRange(html, name).source).join('\n');
}

function blindJDFixture() {
  return {
    job_title: 'Lead <Architect> & Advisor',
    about_client: 'Private <client> & trusted partner',
    about_role: 'Shape <delivery> & guide the team',
    work_mode: 'Hybrid <3 days> & flexible',
    location: 'Kuala Lumpur <HQ> & Region',
    industry: 'Technology <Services> & Consulting',
    exp_range: '8+ years <leadership> & delivery',
    tech_stack: ['Node <20> & SQL'],
    responsibilities: ['Own <delivery> & mentor engineers'],
    requirements: ['8+ years of experience with <platforms> & delivery'],
    nice_to_have: ['Experience in <regulated> & cloud environments'],
    why_join: ['Build <meaningful> & durable systems'],
    alt_titles: ['Principal <Engineer> & Advisor'],
  };
}

function previewOmitsOnlyStandaloneExperienceBadge() {
  const context = vm.createContext({console, Object, Array, String, Date});
  vm.runInContext(functions(['renderAnonJDCard']), context);
  const jd = blindJDFixture();
  const rendered = context.renderAnonJDCard(jd);

  assert.ok(rendered.includes('Kuala Lumpur &lt;HQ&gt; &amp; Region'));
  assert.ok(rendered.includes('Hybrid &lt;3 days&gt; &amp; flexible'));
  assert.ok(rendered.includes('Technology &lt;Services&gt; &amp; Consulting'));
  assert.ok(!rendered.includes('8+ years &lt;leadership&gt; &amp; delivery'));
  assert.ok(!rendered.includes(jd.exp_range));

  assert.ok(rendered.includes('8+ years of experience with &lt;platforms&gt; &amp; delivery'));
  assert.ok(rendered.includes('Experience in &lt;regulated&gt; &amp; cloud environments'));
  assert.ok(rendered.includes('Private &lt;client&gt; &amp; trusted partner'));
  assert.ok(rendered.includes('Node &lt;20&gt; &amp; SQL'));
  assert.ok(rendered.includes('Own &lt;delivery&gt; &amp; mentor engineers'));
  assert.ok(rendered.includes('Build &lt;meaningful&gt; &amp; durable systems'));
  assert.ok(rendered.includes('Principal &lt;Engineer&gt; &amp; Advisor'));
  assert.strictEqual(jd.exp_range, '8+ years <leadership> & delivery');
}

async function wordExportOmitsOnlyTopExperienceSummary() {
  let capturedBlob = null;
  let saved = null;
  function BlobFixture(parts, options) {
    this.parts = parts;
    this.options = options;
    capturedBlob = this;
  }
  const jd = blindJDFixture();
  const context = vm.createContext({
    console,
    window: {_lastAnonJD: jd},
    Object,
    Array,
    String,
    Date,
    Blob: BlobFixture,
    HYPPIES_LOGO_URI: 'data:image/jpeg;base64,fixture',
    async cvStudioSaveDownloadBlob(blob, filename, kind) {
      saved = {blob, filename, kind};
      return {method:'folder', path:'C:\\Blind JD\\' + filename};
    },
    cvStudioShowDownloadResult() {},
    showToast() {},
  });
  vm.runInContext(functions([
    '_escDoc',
    '_wordDocShell',
    '_safeFileStem',
    'wordExportFormat',
    '_buildWordExport',
    'exportWordDocumentToDestination',
    'exportAnonJDDoc',
    'exportAnonJDDocImpl',
  ]), context);
  await context.exportAnonJDDoc();

  assert.ok(capturedBlob, 'Word export should create a blob');
  assert.strictEqual(saved.kind, 'blind_jd');
  assert.ok(saved.filename.endsWith('.doc'));
  const exported = capturedBlob.parts.join('');
  assert.ok(exported.includes('Work Arrangement: Hybrid &lt;3 days&gt; &amp; flexible'));
  assert.ok(exported.includes('Location: Kuala Lumpur &lt;HQ&gt; &amp; Region'));
  assert.ok(exported.includes('Industry: Technology &lt;Services&gt; &amp; Consulting'));
  assert.ok(!exported.includes('Experience: 8+ years'));
  assert.ok(!exported.includes('8+ years &lt;leadership&gt; &amp; delivery'));

  assert.ok(exported.includes('<li>8+ years of experience with &lt;platforms&gt; &amp; delivery</li>'));
  assert.ok(exported.includes('<li>Experience in &lt;regulated&gt; &amp; cloud environments</li>'));
  assert.ok(exported.includes('Private &lt;client&gt; &amp; trusted partner'));
  assert.ok(exported.includes('Node &lt;20&gt; &amp; SQL'));
  assert.ok(!exported.includes('Private <client> & trusted partner'));
  assert.ok(!exported.includes('Node <20> & SQL'));
  assert.strictEqual(jd.exp_range, '8+ years <leadership> & delivery');
}

class FakePDF {
  constructor() {
    this.textCalls = [];
    this.textGroups = [];
    this.roundedRects = [];
    this.pages = 1;
    this.internal = {getNumberOfPages: () => this.pages};
    FakePDF.instance = this;
  }
  setFillColor() {}
  rect() {}
  addImage() {}
  setFont() {}
  setFontSize() {}
  setTextColor() {}
  setDrawColor() {}
  setLineWidth() {}
  line() {}
  circle() {}
  addPage() { this.pages += 1; }
  setPage() {}
  getTextWidth(text) { return String(text).length * 1.5; }
  splitTextToSize(text, width) {
    const words = String(text).split(/\s+/);
    const lines = [];
    let line = '';
    words.forEach(word => {
      const candidate = line ? line + ' ' + word : word;
      if (!line || this.getTextWidth(candidate) <= width) {
        line = candidate;
        return;
      }
      lines.push(line);
      line = word;
    });
    if (line) lines.push(line);
    return lines.length ? lines : [''];
  }
  roundedRect(x, y, width, height, rx, ry, style) {
    this.roundedRects.push({x, y, width, height, rx, ry, style});
  }
  text(value, x, y, options) {
    const values = Array.isArray(value) ? value : [value];
    this.textGroups.push({values: values.map(String), x, y, options});
    values.forEach(item => this.textCalls.push({value: String(item), x, y, options}));
  }
  output(type) { assert.strictEqual(type, 'blob'); return {pdfFixture:true}; }
  save(name) { this.savedName = name; }
}

async function pdfExportOmitsExpAndUsesMetadataWidth() {
  const jd = blindJDFixture();
  let saved = null;
  const context = vm.createContext({
    console,
    window: {_lastAnonJD: jd, jspdf: {jsPDF: FakePDF}},
    Object,
    Array,
    String,
    Date,
    HYPPIES_LOGO_URI: 'data:image/jpeg;base64,fixture',
    async cvStudioSaveDownloadBlob(blob, filename, kind) { saved = {blob, filename, kind}; return {method:'folder', path:'C:\\Blind JD\\' + filename}; },
    cvStudioShowDownloadResult() {},
    showToast() {},
  });
  vm.runInContext(functions(['cvPdfSafeText', '_safeFileStem', 'exportAnonJDPDF', 'exportAnonJDPDFImpl']), context);
  await context.exportAnonJDPDF();

  const doc = FakePDF.instance;
  const exportedText = doc.textCalls.map(call => call.value);
  assert.ok(exportedText.includes('Location: Kuala Lumpur <HQ> & Region'));
  assert.ok(exportedText.includes('Work: Hybrid <3 days> & flexible'));
  assert.ok(!exportedText.some(text => /^Exp:/.test(text)));
  assert.ok(!exportedText.includes(jd.exp_range));
  assert.ok(exportedText.includes('8+ years of experience with <platforms> & delivery'));
  assert.ok(exportedText.includes('Experience in <regulated> & cloud environments'));
  assert.ok(exportedText.includes('Private <client> & trusted partner'));
  assert.ok(exportedText.includes('Node <20> & SQL'));

  const metadataTiles = doc.roundedRects.filter(rect => rect.y === 44);
  assert.strictEqual(metadataTiles.length, 2, 'PDF should render only Location and Work tiles');
  assert.deepStrictEqual(
    metadataTiles.map(rect => ({x: rect.x, width: rect.width})),
    [{x: 18, width: 85}, {x: 107, width: 85}],
    'two metadata tiles should fill the complete 174 mm content width with one 4 mm gap',
  );
  assert.strictEqual(metadataTiles[1].x + metadataTiles[1].width, 192);
  assert.strictEqual(saved.kind, 'blind_jd');
  assert.ok(saved.filename.endsWith('.pdf'));
  assert.strictEqual(jd.exp_range, '8+ years <leadership> & delivery');
}

async function pdfLongMetadataWrapsWithinContentBounds() {
  const jd = Object.assign(blindJDFixture(), {
    job_title: 'Manager, Regulatory Reporting',
    location: 'Malaysia',
    work_mode: 'Office-based with hybrid flexibility (60% office environment as per standard working conditions)',
    industry: 'Banking & Financial Services',
  });
  const context = vm.createContext({
    console,
    window: {_lastAnonJD: jd, jspdf: {jsPDF: FakePDF}},
    Object,
    Array,
    String,
    Date,
    HYPPIES_LOGO_URI: 'data:image/jpeg;base64,fixture',
    async cvStudioSaveDownloadBlob() { return {method:'folder', path:'C:\\Blind JD\\output.pdf'}; },
    cvStudioShowDownloadResult() {},
    showToast() {},
  });
  vm.runInContext(functions(['cvPdfSafeText', '_safeFileStem', 'exportAnonJDPDF', 'exportAnonJDPDFImpl']), context);
  await context.exportAnonJDPDF();

  const doc = FakePDF.instance;
  const headerMetadata = doc.textGroups.find(group =>
    group.x === 48 && group.values.join(' ').includes('Office-based with hybrid flexibility'),
  );
  assert.ok(headerMetadata, 'PDF should render the header metadata');
  assert.ok(headerMetadata.values.length > 1, 'long header metadata should wrap');
  headerMetadata.values.forEach(line => {
    assert.ok(
      headerMetadata.x + doc.getTextWidth(line) <= 192,
      'header metadata line should stay inside the right content edge',
    );
  });

  const metadataTiles = doc.roundedRects.slice(0, 2);
  assert.strictEqual(metadataTiles.length, 2);
  assert.strictEqual(metadataTiles[0].height, metadataTiles[1].height);
  assert.ok(metadataTiles[1].height > 7.2, 'metadata tiles should grow for wrapped Work text');

  const workText = doc.textGroups.find(group =>
    group.x === 110 && group.values.join(' ').startsWith('Work: Office-based'),
  );
  assert.ok(workText, 'PDF should render the Work tile text');
  assert.ok(workText.values.length > 1, 'long Work tile text should wrap');
  workText.values.forEach(line => {
    assert.ok(
      workText.x + doc.getTextWidth(line) <= 189,
      'Work tile line should stay inside its padded right edge',
    );
  });
}

function expRangeSchemaAndUnrelatedContentRemain() {
  const generateSource = functionRange(html, 'generateAnonJD').source;
  const previewSource = functionRange(html, 'renderAnonJDCard').source;
  const wordSource = functionRange(html, 'exportAnonJDDocImpl').source;
  const pdfSource = functionRange(html, 'exportAnonJDPDFImpl').source;

  assert.ok(generateSource.includes('"exp_range":null'));
  assert.ok(generateSource.includes('window._lastAnonJD = jd;'));
  assert.ok(generateSource.includes('years of experience'));
  assert.strictEqual((previewSource.match(/\bexp_range\b/g) || []).length, 0);
  assert.strictEqual((wordSource.match(/\bexp_range\b/g) || []).length, 0);
  assert.strictEqual((pdfSource.match(/\bexp_range\b/g) || []).length, 0);

  [
    'About Our Client',
    'Tech Stack',
    'What You Will Do',
    'What You Need to Succeed',
    'Nice to Have',
    'Why Join Us',
    'Also Search For',
  ].forEach(label => assert.ok(previewSource.includes(label), 'preview lost section: ' + label));
  [
    'About Our Client',
    'About the Role',
    'Tech Stack / Tools',
    'What You Will Do',
    'What You Need to Succeed',
    'Nice to Have',
    'Why Join Us',
    'Alternative Job Titles',
  ].forEach(label => assert.ok(wordSource.includes(label), 'Word export lost section: ' + label));
  [
    'About Our Client',
    'Tech Stack / Tools',
    'What You Will Do',
    'What You Need to Succeed',
    'Nice to Have',
    'Why Join Us',
    'Alternative Job Titles',
  ].forEach(label => assert.ok(pdfSource.includes(label), 'PDF export lost section: ' + label));
}

const cases = [
  ['preview omits only the standalone experience badge', previewOmitsOnlyStandaloneExperienceBadge],
  ['Word export omits only the top Experience summary', wordExportOmitsOnlyTopExperienceSummary],
  ['PDF export omits Exp and fills metadata width', pdfExportOmitsExpAndUsesMetadataWidth],
  ['PDF long metadata wraps within content bounds', pdfLongMetadataWrapsWithinContentBounds],
  ['exp_range schema and unrelated Blind JD content remain', expRangeSchemaAndUnrelatedContentRemain],
];

(async function run() {
  const failures = [];
  for (const [name, test] of cases) {
    try {
      await test();
      console.log('PASS:', name);
    } catch (error) {
      failures.push({name, error});
      console.error('FAIL:', name, '-', error && error.message ? error.message : error);
    }
  }
  if (failures.length) {
    failures.forEach(failure => console.error(failure.error && failure.error.stack ? failure.error.stack : failure.error));
    process.exitCode = 1;
    return;
  }
  console.log('Blind JD experience-summary corrective frontend fixtures passed');
}());
