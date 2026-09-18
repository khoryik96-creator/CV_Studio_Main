'use strict';

// The browser half of the blank-field review queue. The parts worth pinning are
// the ones that stand between a model's output and what a recruiter sees: only
// values JobAdder actually offers may survive, and malformed model output must
// never throw.

const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const source = fs.readFileSync('vendor/cvstudio/ai-crawler.js', 'utf8');

// Values built inside the vm carry that realm's prototypes, so deepStrictEqual
// would compare the realm rather than the data. Normalise before comparing.
function plain(value) {
  return JSON.parse(JSON.stringify(value === undefined ? null : value));
}

function fnFrom(src, name) {
  const start = src.indexOf('function ' + name + '(');
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

// A datalist standing in for the options JobAdder returned.
const optionLists = {
  theSpiderIndustryOptions: ['FMCG', 'Financial Services', 'Information Technology & Services'],
  theSpiderItSkillOptions: ['SAP', 'SAP FICO', 'Oracle', 'Power BI'],
  theSpiderQualificationOptions: ['ACCA', 'CPA', 'PMP'],
};

function makeList(values) {
  return {
    querySelectorAll() {
      return values.map(value => ({ value, textContent: value }));
    },
  };
}

const context = {
  console, JSON, String, Array, Object,
  document: {
    getElementById(id) {
      return optionLists[id] ? makeList(optionLists[id]) : null;
    },
  },
};
vm.createContext(context);
[
  'theSpiderReviewFieldOptions',
  'theSpiderReviewAcceptedValues',
  'parseTheSpiderReviewSuggestions',
  'theSpiderReviewRowName',
  'setTheSpiderReviewQueue',
  'getTheSpiderReviewQueue',
].forEach(name => vm.runInContext(fnFrom(source, name), context));
// The datalist ids come from the filter controls' own config, so this test
// loads that rather than a second copy of the same three names.
vm.runInContext(
  source.match(/var THE_SPIDER_MULTI_CONFIG = \{[\s\S]*?\};/)[0],
  context
);

// ── the fixed vocabulary is read from the loaded options ─────────────────────
assert.deepStrictEqual(
  plain(context.theSpiderReviewFieldOptions('it_skills')),
  ['SAP', 'SAP FICO', 'Oracle', 'Power BI']
);
assert.deepStrictEqual(plain(context.theSpiderReviewFieldOptions('nonsense')), []);

// ── only values JobAdder offers survive ──────────────────────────────────────
assert.deepStrictEqual(
  plain(context.theSpiderReviewAcceptedValues('it_skills', ['SAP', 'Oracle'])),
  ['SAP', 'Oracle']
);
// A value the model invented is dropped rather than shown.
assert.deepStrictEqual(
  plain(context.theSpiderReviewAcceptedValues('it_skills', ['SAP Business One', 'Cobol'])),
  []
);
// Casing and padding are forgiven, but the stored value is JobAdder's spelling.
assert.deepStrictEqual(
  plain(context.theSpiderReviewAcceptedValues('it_skills', ['  sap fico ', 'ORACLE'])),
  ['SAP FICO', 'Oracle']
);
// Duplicates collapse and the list is capped.
assert.deepStrictEqual(
  plain(context.theSpiderReviewAcceptedValues('it_skills', ['SAP', 'sap', 'SAP'])),
  ['SAP']
);
assert.strictEqual(
  plain(context.theSpiderReviewAcceptedValues('it_skills', ['SAP', 'SAP FICO', 'Oracle', 'Power BI'])).length,
  3
);
// Nothing usable in, nothing out, and never a throw.
[null, undefined, '', 0, {}, 'SAP', [null], [{}]].forEach(value => {
  assert.deepStrictEqual(plain(context.theSpiderReviewAcceptedValues('it_skills', value)), []);
});

// ── model output is parsed defensively ───────────────────────────────────────
assert.deepStrictEqual(
  plain(context.parseTheSpiderReviewSuggestions('{"suggestions":[{"candidate_id":"7","it_skills":["SAP"]}]}')),
  [{ candidate_id: '7', it_skills: ['SAP'] }]
);
// A fenced block, which models add despite being asked not to.
assert.deepStrictEqual(
  plain(context.parseTheSpiderReviewSuggestions('```json\n{"suggestions":[{"candidate_id":"7"}]}\n```')),
  [{ candidate_id: '7' }]
);
// Prose either side of the JSON.
assert.deepStrictEqual(
  plain(context.parseTheSpiderReviewSuggestions('Here you go:\n{"suggestions":[{"candidate_id":"9"}]}\nHope that helps.')),
  [{ candidate_id: '9' }]
);
// Anything unusable returns an empty list instead of throwing.
['', '   ', 'no json here', '{broken', '[]', '{}', '{"suggestions":"nope"}', null, undefined].forEach(raw => {
  assert.deepStrictEqual(plain(context.parseTheSpiderReviewSuggestions(raw)), []);
});
// Non-object rows are discarded.
assert.deepStrictEqual(
  plain(context.parseTheSpiderReviewSuggestions('{"suggestions":[null,"x",3,{"candidate_id":"1"}]}')),
  [{ candidate_id: '1' }]
);

// ── the queue de-duplicates and survives junk ────────────────────────────────
context.renderTheSpiderReviewQueue = function () {};
vm.runInContext('var window = {};', context);
context.setTheSpiderReviewQueue([
  { candidate_id: '1', blank_fields: ['it_skills'] },
  { candidate_id: '1', blank_fields: ['industry'] },
  { candidate_id: '2', blank_fields: ['industry'] },
  null,
  'nonsense',
  { blank_fields: ['industry'] },
]);
assert.deepStrictEqual(
  plain(context.getTheSpiderReviewQueue().map(row => row.candidate_id)),
  ['1', '2']
);
context.setTheSpiderReviewQueue(null);
assert.deepStrictEqual(plain(context.getTheSpiderReviewQueue()), []);

// ── a row always has something to show a person ──────────────────────────────
// The name comes from the row, which is where the search puts it. An earlier
// draft read row.card.name, a shape the server never sends, so every row showed
// a bare id while this test passed on invented data.
assert.strictEqual(context.theSpiderReviewRowName({ name: 'Alex Tan' }), 'Alex Tan');
assert.strictEqual(context.theSpiderReviewRowName({ candidate_id: '42' }), 'Candidate 42');
assert.strictEqual(context.theSpiderReviewRowName({}), 'Candidate ');
// The card holds salary and notice period only; it must not be mistaken for a name.
assert.strictEqual(
  context.theSpiderReviewRowName({ candidate_id: '42', card: { name: 'Nope' } }),
  'Candidate 42'
);

// ── the page still declares the tab and never writes to JobAdder from here ───
const html = fs.readFileSync('index.html', 'utf8');
assert.ok(html.includes('id="theSpiderTabReview"'));
assert.ok(html.includes('id="theSpiderReviewBody"'));
assert.ok(html.includes('suggestTheSpiderTagsFromCv()'));
assert.ok(
  !/suggestTheSpiderTagsFromCv[\s\S]{0,4000}?fetch\(\s*['"]\/jobadder\/(?!spider_options)/.test(source),
  'the suggest path must not write to JobAdder'
);

// ── every helper the new code calls has to exist somewhere in the bundle ─────
// A first draft of this feature called a helper named aiRoute, which does not
// exist. Nothing failed until the button was pressed.
const bundle = fs.readdirSync('vendor/cvstudio')
  .filter(name => name.endsWith('.js'))
  .map(name => fs.readFileSync('vendor/cvstudio/' + name, 'utf8'))
  .join('\n') + '\n' + html;
const suggestBody = fnFrom(source, 'suggestTheSpiderTagsFromCv')
  + fnFrom(source, 'renderTheSpiderReviewQueue')
  + fnFrom(source, 'theSpiderReviewSuggestionPrompt')
  + fnFrom(source, 'setTheSpiderReviewQueue');
const declaredLocally = new Set(
  (suggestBody.match(/\bvar\s+([A-Za-z_$][\w$]*)/g) || []).map(m => m.split(/\s+/)[1])
);
const builtIns = new Set([
  'String', 'Array', 'Object', 'JSON', 'Number', 'Boolean', 'Math', 'Date',
  'Promise', 'document', 'window', 'console', 'parseInt', 'parseFloat', 'isNaN',
  'Error', 'RegExp', 'Set', 'Map', 'if', 'for', 'while', 'switch', 'catch',
  'function', 'return', 'typeof', 'await', 'new', 'var', 'let', 'const',
  'setTimeout', 'clearTimeout', 'confirm', 'alert', 'fetch',
  'else', 'do', 'try', 'in', 'of', 'delete', 'void', 'throw',
]);
const called = new Set(
  (suggestBody.match(/(?:^|[^.\w$])([A-Za-z_$][\w$]*)\s*\(/g) || [])
    .map(m => m.replace(/[^A-Za-z_$\w]/g, '').replace(/\($/, ''))
    .map(name => name.replace(/\($/, ''))
);
const missing = [];
called.forEach(name => {
  if (!name || builtIns.has(name) || declaredLocally.has(name)) return;
  const declared = new RegExp(
    '(?:function\\s+' + name + '\\b|var\\s+' + name + '\\s*=|window\\.' + name + '\\s*=)'
  );
  if (!declared.test(bundle)) missing.push(name);
});
assert.deepStrictEqual(missing, [], 'undefined helpers called: ' + missing.join(', '));

console.log('PASS: AI Crawler blank-field review queue');
