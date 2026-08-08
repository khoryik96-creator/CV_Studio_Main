'use strict';

const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const html = fs.readFileSync('index.html', 'utf8');
const generate = fs.readFileSync('generate.js', 'utf8');

function fnFrom(source, name) {
  const start = source.indexOf('function ' + name + '(');
  assert.ok(start >= 0, 'missing function: ' + name);
  let brace = source.indexOf('{', start), depth = 0, quote = '', escaped = false;
  for (let i = brace; i < source.length; i += 1) {
    const ch = source[i];
    if (quote) {
      if (escaped) escaped = false;
      else if (ch === '\\') escaped = true;
      else if (ch === quote) quote = '';
      continue;
    }
    if (ch === '"' || ch === "'" || ch.charCodeAt(0) === 96) { quote = ch; continue; }
    if (ch === '{') depth += 1;
    else if (ch === '}' && --depth === 0) return source.slice(start, i + 1);
  }
  throw new Error('unterminated function: ' + name);
}

function fn(name) { return fnFrom(html, name); }

const tab = {innerHTML: '', classList: {add(){}, remove(){}}, title: '', setAttribute(){}};
const storage = new Map();
let promptValue = '';
const context = {
  console, JSON, String, Array, Object,
  LOCK_UNLOCK_VERSION: 'v24.6.246',
  CV_SCORING_LOCK_CODE: '1996',
  window: {prompt(){ return promptValue; }, alert(){}},
  localStorage: {getItem(k){ return storage.get(k) || null; }, setItem(k,v){ storage.set(k,v); }},
  sessionStorage: {getItem(){ return null; }, setItem(){}},
  document: {getElementById(id){ return id === 'tabAppraiser' || id === 'tabTheSpider' ? tab : null; }},
  showToast(){}, esc(v){ return String(v); }, cvTabLabel(label){ return label; }, cvLockedTabLabel(){ return 'Locked'; },
};
vm.createContext(context);
[
  'cvParseIsLong','cvParseTimeoutMs','cvStripInferredTitle','cvCanonicalSectionHeading',
  'cvNormalizeBulletItems','cvNormalizeStructuredData','cvNormDateRange','summaryBulletLines',
  'formatSummaryBulletsFor','applyFormatSummaryBullets','versionedUnlockKey','readVersionedUnlock',
  'writeVersionedUnlock','cvScoringIsUnlocked','cvScoringSetUnlocked','updateCvScoringLockUI',
  'requestCvScoringUnlock','aiCrawlerIsUnlocked','updateAiCrawlerLockUI','requestAiCrawlerUnlock',
  'requireAiCrawlerUnlocked','aiCrawlerLockPayload','cvSkillPreviewHtml'
].forEach(name => vm.runInContext(fn(name), context));
vm.runInContext(fnFrom(generate, 'normalizeDateRange'), context);

assert.deepStrictEqual(
  JSON.parse(JSON.stringify(context.summaryBulletLines('```markdown\n- **Cloud platforms** leader\n* Built delivery teams\n```'))),
  ['**Cloud platforms** leader', 'Built delivery teams']
);
context.window._formatSummaryDraft = {
  cv_text: 'RAW CV',
  bullets: ['**Cloud platforms** leader', 'Built delivery teams']
};
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(context.formatSummaryBulletsFor('RAW CV', false))),
  ['**Cloud platforms** leader', 'Built delivery teams']
);
assert.deepStrictEqual(JSON.parse(JSON.stringify(context.formatSummaryBulletsFor('DIFFERENT CV', false))), []);
assert.deepStrictEqual(JSON.parse(JSON.stringify(context.formatSummaryBulletsFor('RAW CV', true))), []);
const formatted = context.applyFormatSummaryBullets({candidate:{name:'Summary Fixture'}}, 'RAW CV', false);
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(formatted.summary_bullets)),
  ['**Cloud platforms** leader', 'Built delivery teams']
);
const blinded = context.applyFormatSummaryBullets({candidate:{name:'Summary Fixture'}}, 'RAW CV', true);
assert.strictEqual(blinded.summary_bullets, undefined);
assert.ok(html.includes('id="btnSummaryFormat"'));
assert.ok(html.includes('onclick="formatSummaryResume()"'));

const transferElements = {
  summaryCvText: {value: 'RAW CV'},
  cvInput: {value: ''},
  charCount: {textContent: ''}
};
const transferCalls = {inputTab: '', pageTab: '', blind: null};
const transferContext = {
  window: {
    _summaryGeneratedSource: 'RAW CV',
    _summaryGeneratedBullets: ['**Cloud platforms** leader', 'Built delivery teams'],
    _formatSummaryDraft: null
  },
  document: {getElementById(id){ return transferElements[id] || null; }},
  requireSummaryUnlocked(){ return true; },
  showToast(){},
  switchInputTab(tabName){ transferCalls.inputTab = tabName; },
  updateFormatSummaryNote(){},
  switchTab(tabName){ transferCalls.pageTab = tabName; },
  startFormat(blind){ transferCalls.blind = blind; return Promise.resolve(); }
};
vm.createContext(transferContext);
vm.runInContext(fn('formatSummaryResume'), transferContext);
transferContext.formatSummaryResume();
assert.strictEqual(transferElements.cvInput.value, 'RAW CV');
assert.strictEqual(transferCalls.inputTab, 'paste');
assert.strictEqual(transferCalls.pageTab, 'format');
assert.strictEqual(transferCalls.blind, false);
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(transferContext.window._formatSummaryDraft.bullets)),
  ['**Cloud platforms** leader', 'Built delivery teams']
);

assert.strictEqual(context.cvNormDateRange('to 2001'), '2001');
assert.strictEqual(context.cvNormDateRange(''), '');
assert.strictEqual(context.normalizeDateRange('to 1996'), '1996');
assert.strictEqual(context.normalizeDateRange('to'), '');

assert.strictEqual(context.cvParseTimeoutMs('x'.repeat(7999)), 210000);
assert.strictEqual(context.cvParseTimeoutMs('x'.repeat(8000)), 330000);
// A real dense 8-page CV (~9-10k extracted chars) must get the long fetch budget.
assert.strictEqual(context.cvParseTimeoutMs('x'.repeat(9808)), 330000);
assert.strictEqual(context.cvParseTimeoutMs(Array(8).fill('Key responsibilities').join('\n')), 330000);
assert.strictEqual((html.match(/fetchWithTimeout\('\/parse'/g) || []).length, 3);
assert.ok(html.includes('}, cvParseTimeoutMs(cvText));'));
assert.ok(html.includes('}, cvParseTimeoutMs(raw));'));
assert.ok(html.includes('}, cvParseTimeoutMs(rawText));'));

const data = {candidate:{current_position:'Advisor (implied from responsibilities)'},work_experiences:[{roles:[{title:'Advisor (inferred from duties)',bullets:['{"heading":"Achievement","bullets":["Won award"]}']}]}],certifications:[''],skills:[{category:'Skills',items:'Leadership'}]};
context.cvNormalizeStructuredData(data);
assert.strictEqual(data.candidate.current_position, '');
assert.strictEqual(data.work_experiences[0].roles[0].title, '');
assert.strictEqual(data.work_experiences[0].roles[0].bullets[0].heading, 'Key achievements');
assert.strictEqual(data.work_experiences[0].roles[0].bullets[0].kind, 'section');
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(context.cvNormalizeBulletItems(['Key responsibilities', 'Delivered result']))),
  [{heading:'Key responsibilities', bullets:[], kind:'section'}, 'Delivered result']
);
[
  'Advisor (assumed from duties)',
  'Advisor (guessed from context)',
  'Advisor (likely based on responsibilities)',
].forEach(title => assert.strictEqual(context.cvStripInferredTitle(title), ''));
assert.strictEqual(context.cvStripInferredTitle('Advisor'), 'Advisor');
assert.strictEqual(context.cvStripInferredTitle('Advisor (likely to succeed)'), 'Advisor (likely to succeed)');

const recoveredSkillPreview = context.cvSkillPreviewHtml({
  category: 'Project Involvement History',
  items: ['Firewall Upgrade', 'Network Redesign'],
});
assert.ok(recoveredSkillPreview.includes('<strong>Project Involvement History:</strong>'));
assert.strictEqual((recoveredSkillPreview.match(/class="preview-bullet"/g) || []).length, 2);
assert.ok(!recoveredSkillPreview.includes('Firewall Upgrade, Network Redesign'));
assert.ok(recoveredSkillPreview.indexOf('Firewall Upgrade') < recoveredSkillPreview.indexOf('Network Redesign'));

context.updateCvScoringLockUI();
assert.strictEqual(tab.innerHTML, 'Locked');
promptValue = '1111';
assert.strictEqual(context.requestCvScoringUnlock(), false);
promptValue = '1996';
assert.strictEqual(context.requestCvScoringUnlock(), true);
assert.strictEqual(context.cvScoringIsUnlocked(), true);
assert.strictEqual(tab.innerHTML, 'CV Scoring');

assert.strictEqual(context.aiCrawlerIsUnlocked(), true);
assert.strictEqual(context.requestAiCrawlerUnlock(), true);
assert.strictEqual(context.requireAiCrawlerUnlocked(), true);
assert.strictEqual(context.aiCrawlerLockPayload(), '');

const scoringTab = html.indexOf('id="tabAppraiser"');
assert.ok(scoringTab > html.indexOf('id="tabTheSpider"'));
assert.ok(scoringTab > html.indexOf('id="tabLeadFinder"'));
assert.ok(scoringTab < html.indexOf('id="pageNavPinToggle"'));
assert.ok(html.includes("if (tab === 'appraiser' && !requestCvScoringUnlock())"));
assert.ok(!html.includes("AI Crawler is locked. Enter the 4-digit access code"));
assert.ok(!html.includes("var AI_CRAWLER_LOCK_CODE"));

console.log('PASS: long-CV timeout/output repair and feature access controls');
