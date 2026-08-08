'use strict';

const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const html = fs.readFileSync('index.html', 'utf8');

function fn(name) {
  const start = html.indexOf('function ' + name + '(');
  assert.ok(start >= 0, 'missing function: ' + name);
  let brace = html.indexOf('{', start), depth = 0, quote = '', escaped = false;
  for (let i = brace; i < html.length; i += 1) {
    const ch = html[i];
    if (quote) {
      if (escaped) escaped = false;
      else if (ch === '\\') escaped = true;
      else if (ch === quote) quote = '';
      continue;
    }
    if (ch === '"' || ch === "'" || ch.charCodeAt(0) === 96) { quote = ch; continue; }
    if (ch === '{') depth += 1;
    else if (ch === '}' && --depth === 0) return html.slice(start, i + 1);
  }
  throw new Error('unterminated function: ' + name);
}

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
  'cvStripLeadingBulletMarker',
  'cvNormalizeBulletItems','cvNormalizeStructuredData','versionedUnlockKey','readVersionedUnlock',
  'writeVersionedUnlock','cvScoringIsUnlocked','cvScoringSetUnlocked','updateCvScoringLockUI',
  'requestCvScoringUnlock','aiCrawlerIsUnlocked','updateAiCrawlerLockUI','requestAiCrawlerUnlock',
  'requireAiCrawlerUnlocked','aiCrawlerLockPayload'
].forEach(name => vm.runInContext(fn(name), context));

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
// A redundant leading "* " / "- " marker inside an already-bulleted line is
// stripped so it does not render as a doubled bullet ("• * Mail Server").
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(context.cvNormalizeBulletItems([
    'Maintaining all server in the office such', '* Mail Server', '- Networking',
  ]))),
  ['Maintaining all server in the office such', 'Mail Server', 'Networking']
);
// Enumerators need a trailing space (bar the "(x)" form) and a bare word after
// a dash is not one, so code/math/abbreviation/hyphenated prose is untouched.
['*args', '**bold**', '5 * 3', 'No. 5 priority', 'e.g. do it', '24/7 support', 'e-1 form', 'AI/ML', '-managed vendors'].forEach(t => assert.deepStrictEqual(
  JSON.parse(JSON.stringify(context.cvNormalizeBulletItems([t]))), [t]
));
// Every outline-label style is stripped deterministically: a. a.) 1.) (b) (vi) b) i. 1- -1 -a.
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(context.cvNormalizeBulletItems([
    'a. One', 'a.) Two', '1.) Three', '(b) Four', '(vi)Five', 'b) Six', 'i. Seven', '1- Eight', '-1 Nine', '-a Ten',
  ]))),
  ['One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten']
);
[
  'Advisor (assumed from duties)',
  'Advisor (guessed from context)',
  'Advisor (likely based on responsibilities)',
].forEach(title => assert.strictEqual(context.cvStripInferredTitle(title), ''));
assert.strictEqual(context.cvStripInferredTitle('Advisor'), 'Advisor');
assert.strictEqual(context.cvStripInferredTitle('Advisor (likely to succeed)'), 'Advisor (likely to succeed)');

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
