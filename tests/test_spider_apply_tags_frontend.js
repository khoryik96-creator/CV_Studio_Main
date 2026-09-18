'use strict';

// The browser half of saving a reviewed tag. This is the one path in the AI
// Crawler that changes a live candidate record, so what is pinned here is the
// gap between what a recruiter ticked and what leaves the browser: an unticked
// suggestion is never sent, each candidate is posted on its own, and one
// candidate failing does not take the rest of the batch down with it.

const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const source = fs.readFileSync('vendor/cvstudio/ai-crawler.js', 'utf8');

function plain(value) {
  return JSON.parse(JSON.stringify(value === undefined ? null : value));
}

function fnFrom(src, name) {
  const start = src.search(new RegExp('(?:async\\s+)?function\\s+' + name + '\\('));
  assert.ok(start >= 0, 'missing function: ' + name);
  let brace = src.indexOf('{', start), depth = 0, quote = '', escaped = false;
  for (let i = brace; i < src.length; i += 1) {
    const ch = src[i];
    if (quote) {
      if (escaped) escaped = false;
      else if (ch === '\\') escaped = true;
      else if (ch === quote) quote = '';
      continue;
    }
    if (ch === '"' || ch === "'" || ch.charCodeAt(0) === 96) { quote = ch; continue; }
    if (ch === '{') depth += 1;
    else if (ch === '}' && --depth === 0) return src.slice(start, i + 1);
  }
  throw new Error('unterminated function: ' + name);
}

// A tick box as the review queue renders it.
function box(candidate, field, value, checked) {
  const attrs = { 'data-candidate': candidate, 'data-field': field, 'data-value': value };
  return { checked: !!checked, getAttribute(name) { return attrs[name]; } };
}

const button = { disabled: true, textContent: '' };
const badge = { textContent: '' };
const elements = { theSpiderApplyTagsBtn: button, theSpiderReviewBadge: badge };

let boxes = [];
let posted = [];
let confirmed = true;
let toasts = [];
let rendered = 0;
let queue = [];
let responses = {};

const context = {
  console, JSON, String, Array, Object, Promise, Error,
  document: {
    getElementById(id) { return elements[id] || null; },
    querySelectorAll(selector) {
      assert.strictEqual(selector, '.spider-tag-pick');
      return boxes;
    },
  },
  confirm() { return confirmed; },
  showToast(message, kind) { toasts.push([message, kind]); },
  requireAiCrawlerUnlocked() { return true; },
  aiCrawlerLockPayload() { return 'unlock-code'; },
  getTheSpiderReviewQueue() { return queue; },
  renderTheSpiderReviewQueue() { rendered += 1; },
  THE_SPIDER_REVIEW_FIELD_LABELS: { it_skills: 'IT Skills', industry: 'Industry' },
  fetchWithTimeout(url, options) {
    posted.push({ url, options, body: JSON.parse(options.body) });
    const id = JSON.parse(options.body).candidate_id;
    const reply = responses[id] || { ok: true, json: { applied: {} } };
    if (reply.throws) return Promise.reject(new Error(reply.throws));
    return Promise.resolve({
      ok: reply.ok !== false,
      status: reply.status || 200,
      json() { return Promise.resolve(reply.json || {}); },
    });
  },
};
vm.createContext(context);
[
  'theSpiderTickedTags',
  'theSpiderTickedTagCount',
  'updateTheSpiderApplyButton',
  'applyTheSpiderTagsToJobAdder',
].forEach(name => vm.runInContext(fnFrom(source, name), context));

function reset() {
  boxes = [];
  posted = [];
  toasts = [];
  rendered = 0;
  queue = [];
  responses = {};
  confirmed = true;
  button.disabled = true;
  button.textContent = '';
  badge.textContent = '';
}

// ── only what was ticked is collected ────────────────────────────────────────
reset();
boxes = [
  box('1', 'it_skills', 'SAP', true),
  box('1', 'it_skills', 'Oracle', false),
  box('1', 'industry', 'FMCG', true),
  box('2', 'it_skills', 'Power BI', true),
];
assert.deepStrictEqual(plain(context.theSpiderTickedTags()), {
  '1': { it_skills: ['SAP'], industry: ['FMCG'] },
  '2': { it_skills: ['Power BI'] },
});
assert.strictEqual(context.theSpiderTickedTagCount(context.theSpiderTickedTags()), 3);

// Nothing ticked means nothing collected, and the count never throws on junk.
boxes = [box('1', 'it_skills', 'SAP', false)];
assert.deepStrictEqual(plain(context.theSpiderTickedTags()), {});
[null, undefined, {}].forEach(value => {
  assert.strictEqual(context.theSpiderTickedTagCount(value), 0);
});

// A box missing any of its three pieces is skipped rather than half-sent.
boxes = [
  box('', 'it_skills', 'SAP', true),
  box('1', '', 'SAP', true),
  box('1', 'it_skills', '', true),
];
assert.deepStrictEqual(plain(context.theSpiderTickedTags()), {});

// The same value ticked twice is sent once.
boxes = [box('1', 'it_skills', 'SAP', true), box('1', 'it_skills', 'SAP', true)];
assert.deepStrictEqual(plain(context.theSpiderTickedTags()), { '1': { it_skills: ['SAP'] } });

// ── the button follows the ticks ─────────────────────────────────────────────
reset();
boxes = [box('1', 'it_skills', 'SAP', false)];
context.updateTheSpiderApplyButton();
assert.strictEqual(button.disabled, true);
assert.strictEqual(button.textContent, 'Save ticked tags to JobAdder');
boxes = [box('1', 'it_skills', 'SAP', true), box('2', 'industry', 'FMCG', true)];
context.updateTheSpiderApplyButton();
assert.strictEqual(button.disabled, false);
assert.strictEqual(button.textContent, 'Save 2 tag(s) to JobAdder');

// ── the save itself ──────────────────────────────────────────────────────────
(async function () {
  // Nothing ticked: no request at all.
  reset();
  await context.applyTheSpiderTagsToJobAdder();
  assert.deepStrictEqual(posted, []);
  assert.strictEqual(toasts[0][1], 'err');

  // Declining the confirmation sends nothing either.
  reset();
  confirmed = false;
  boxes = [box('1', 'it_skills', 'SAP', true)];
  await context.applyTheSpiderTagsToJobAdder();
  assert.deepStrictEqual(posted, []);

  // One request per candidate, carrying only that candidate's ticks.
  reset();
  queue = [{ candidate_id: '1' }, { candidate_id: '2' }];
  boxes = [
    box('1', 'it_skills', 'SAP', true),
    box('1', 'it_skills', 'Oracle', false),
    box('2', 'industry', 'FMCG', true),
  ];
  responses = {
    '1': { json: { applied: { it_skills: ['SAP'] } } },
    '2': { json: { applied: { industry: ['FMCG'] } } },
  };
  await context.applyTheSpiderTagsToJobAdder();
  assert.strictEqual(posted.length, 2);
  assert.strictEqual(posted[0].url, '/jobadder/spider_apply_tags');
  assert.strictEqual(posted[0].options.method, 'POST');
  assert.deepStrictEqual(plain(posted[0].body), {
    candidate_id: '1',
    fields: { it_skills: ['SAP'] },
    crawler_lock_code: 'unlock-code',
  });
  assert.deepStrictEqual(plain(posted[1].body.fields), { industry: ['FMCG'] });
  // The untouched suggestion never left the browser.
  assert.ok(!JSON.stringify(posted).includes('Oracle'));
  assert.ok(badge.textContent.startsWith('2 written'));
  assert.strictEqual(toasts[toasts.length - 1][1], 'ok');
  assert.strictEqual(rendered, 1);
  assert.strictEqual(queue[0].suggestion_note, 'Saved to JobAdder: IT Skills = SAP');

  // The server writing nothing is reported as such, not as a success.
  reset();
  queue = [{ candidate_id: '1' }];
  boxes = [box('1', 'it_skills', 'SAP', true)];
  responses = { '1': { json: { applied: {}, skipped: [{ reason: 'already filled' }] } } };
  await context.applyTheSpiderTagsToJobAdder();
  assert.strictEqual(toasts[toasts.length - 1][1], 'err');
  assert.ok(queue[0].suggestion_note.indexOf('already filled') >= 0
    || queue[0].suggestion_note.indexOf('Nothing written') >= 0);
  assert.ok(badge.textContent.indexOf('left alone') >= 0);

  // One candidate failing does not stop the others, and the failure is shown.
  reset();
  queue = [{ candidate_id: '1' }, { candidate_id: '2' }];
  boxes = [box('1', 'it_skills', 'SAP', true), box('2', 'it_skills', 'Oracle', true)];
  responses = {
    '1': { ok: false, status: 502, json: { error: 'JobAdder is down' } },
    '2': { json: { applied: { it_skills: ['Oracle'] } } },
  };
  await context.applyTheSpiderTagsToJobAdder();
  assert.strictEqual(posted.length, 2);
  assert.ok(queue[0].suggestion_note.indexOf('Save failed') === 0);
  assert.strictEqual(queue[1].suggestion_note, 'Saved to JobAdder: IT Skills = Oracle');
  assert.strictEqual(toasts[toasts.length - 1][1], 'err');

  // A thrown request is caught the same way.
  reset();
  queue = [{ candidate_id: '1' }];
  boxes = [box('1', 'it_skills', 'SAP', true)];
  responses = { '1': { throws: 'network gone' } };
  await context.applyTheSpiderTagsToJobAdder();
  assert.ok(queue[0].suggestion_note.indexOf('network gone') >= 0);

  // The button is left usable again rather than stuck on "Saving…".
  assert.strictEqual(button.textContent, 'Save ticked tags to JobAdder');

  // ── the page wires the save up ─────────────────────────────────────────────
  const html = fs.readFileSync('index.html', 'utf8');
  assert.ok(html.includes('id="theSpiderApplyTagsBtn"'));
  assert.ok(html.includes('applyTheSpiderTagsToJobAdder()'));
  // The button starts disabled, so a stray click cannot write an empty batch.
  assert.ok(/id="theSpiderApplyTagsBtn"[^>]*disabled/.test(html));
  // The only write in this module goes through the reviewed-tag route.
  const writes = source.match(/fetch(?:WithTimeout)?\(\s*'\/jobadder\/[a-z_]+'/g) || [];
  writes.forEach(call => {
    assert.ok(
      !call.includes('update_candidate'),
      'the review queue must not write through the generic update route'
    );
  });

  console.log('PASS: AI Crawler reviewed-tag save');
}()).catch(err => { console.error(err); process.exit(1); });
