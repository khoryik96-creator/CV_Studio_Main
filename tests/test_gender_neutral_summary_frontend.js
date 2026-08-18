'use strict';

// The gender-neutral summary toggle rewrites candidate pronouns in the
// auto-generated Summary (the "ABOUT HIM / HER" section) to "the candidate" /
// "the candidate's" -- never "they/them" -- for single and batch Format CV.
// These tests pin the deterministic neutraliser that both flows call.

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const source = fs.readFileSync(
  path.resolve(__dirname, '..', 'vendor', 'cvstudio', 'settings.js'),
  'utf8',
);

// Pull a named function's full source by brace-matching (the target functions
// contain no braces inside strings or regex, so a simple counter is exact).
function extractFunction(name) {
  const start = source.indexOf('function ' + name + '(');
  assert.notStrictEqual(start, -1, 'function ' + name + ' not found in settings.js');
  const open = source.indexOf('{', start);
  let depth = 0;
  for (let i = open; i < source.length; i++) {
    if (source[i] === '{') depth++;
    else if (source[i] === '}') {
      depth--;
      if (depth === 0) return source.slice(start, i + 1);
    }
  }
  throw new Error('unbalanced braces extracting ' + name);
}

const combined = [
  'cvMatchLeadingCase',
  'cvNeutralizeCandidatePronouns',
  'getCvGenderNeutralSummary',
  'cvNeutralizeSummaryBullets',
].map(extractFunction).join('\n');

// Evaluate the extracted functions against a controllable `window`.
const windowObj = {};
const factory = new Function(
  'window',
  combined + '\nreturn { cvNeutralizeCandidatePronouns, cvNeutralizeSummaryBullets, getCvGenderNeutralSummary };'
);
const mod = factory(windowObj);
const neutralize = mod.cvNeutralizeCandidatePronouns;

function eq(input, expected) {
  assert.strictEqual(neutralize(input), expected, JSON.stringify(input));
}

// Subject pronouns -> "the candidate", preserving sentence-leading capital.
eq('He has 8 years of experience.', 'The candidate has 8 years of experience.');
eq('She leads the platform team.', 'The candidate leads the platform team.');
eq('We think he is strong.', 'We think the candidate is strong.');

// Possessive determiners/pronouns -> "the candidate's".
eq('his experience spans cloud and data', "the candidate's experience spans cloud and data");
eq('Her role covered EMEA delivery.', "The candidate's role covered EMEA delivery.");
eq('The winning idea was his.', "The winning idea was the candidate's.");
eq('The award was hers.', "The award was the candidate's.");

// Object pronouns -> "the candidate".
eq('The client asked to contact him.', 'The client asked to contact the candidate.');
eq('The manager reported to her.', 'The manager reported to the candidate.');

// "her" disambiguation in one sentence: possessive then object.
eq(
  'She improved her skills and the team backed her.',
  "The candidate improved the candidate's skills and the team backed the candidate."
);

// Words that merely contain a pronoun's letters must be untouched.
eq('This theatre here shelters them.', 'This theatre here shelters them.');
eq('The cashier assessed the mishap.', 'The cashier assessed the mishap.');

// Contractions expand instead of leaving a dangling suffix ("The candidate'll").
eq("He's a strong engineer.", 'The candidate is a strong engineer.');
eq("He'll lead the team.", 'The candidate will lead the team.');
eq("She'd delivered results.", 'The candidate had delivered results.');
eq('He’s proven and she’ll grow.', 'The candidate is proven and the candidate will grow.'); // curly quotes

// Sweep: no gendered pronoun may survive, and the transform is idempotent.
[
  "He's proven; his record and her drive impressed them.",
  'She led her team and mentored him herself.',
  'HE MANAGED HIS TEAM.',
].forEach(function(input){
  var once = neutralize(input);
  assert.strictEqual(/\b(he|she|him|his|her|hers|himself|herself)\b/i.test(once), false, 'gendered pronoun survived: ' + once);
  assert.strictEqual(neutralize(once), once, 'not idempotent: ' + once);
});

// The replacement must never introduce "they/them/their".
const neutral = neutralize('He gave his report to her. She thanked him for his work.');
assert.strictEqual(/\b(they|them|their|theirs)\b/i.test(neutral), false, 'must not use they/them: ' + neutral);
assert.strictEqual(/\b(he|she|him|his|her|hers)\b/i.test(neutral), false, 'no gendered pronoun should remain: ' + neutral);

// The toggle gates cvNeutralizeSummaryBullets: off = unchanged, on = rewritten.
const bullets = ['He is a Docker engineer.', "Proven in his contractor role."];
windowObj._cvGenderNeutralSummary = false;
assert.deepStrictEqual(mod.cvNeutralizeSummaryBullets(bullets), bullets, 'disabled toggle must pass bullets through');

windowObj._cvGenderNeutralSummary = true;
assert.deepStrictEqual(
  mod.cvNeutralizeSummaryBullets(bullets),
  ['The candidate is a Docker engineer.', "Proven in the candidate's contractor role."],
  'enabled toggle must neutralise every bullet'
);
// The neutraliser is non-mutating.
assert.deepStrictEqual(bullets, ['He is a Docker engineer.', "Proven in his contractor role."], 'input array must not be mutated');

// The "ABOUT HIM / HER" heading is never passed through summary_bullets, so it
// is left intact; confirm the neutraliser is only ever applied to bullet data.
const cvFormatSrc = fs.readFileSync(path.resolve(__dirname, '..', 'vendor', 'cvstudio', 'cv-format.js'), 'utf8');
assert.ok(
  cvFormatSrc.includes('cvNeutralizeSummaryBullets(summaryResult.bullets'),
  'single Format CV must neutralise its auto-generated summary bullets'
);
assert.ok(
  cvFormatSrc.includes('cvNeutralizeSummaryBullets(_parsedData.summary_bullets'),
  'single Format CV must also neutralise a manually-linked summary'
);
assert.ok(
  fs.readFileSync(path.resolve(__dirname, '..', 'vendor', 'cvstudio', 'batch-format.js'), 'utf8')
    .includes('cvNeutralizeSummaryBullets(batchSummaryResult.bullets'),
  'batch Format CV must neutralise its summary bullets'
);

// The summary PROMPT gains a gender-neutral instruction only when the toggle is
// on, so the model writes neutrally from the start (belt-and-suspenders with the
// deterministic pass).
const summarySource = fs.readFileSync(
  path.resolve(__dirname, '..', 'vendor', 'cvstudio', 'candidate-summary.js'),
  'utf8',
);
function extractFrom(src, name) {
  const start = src.indexOf('function ' + name + '(');
  assert.notStrictEqual(start, -1, 'function ' + name + ' not found');
  const open = src.indexOf('{', start);
  let depth = 0;
  for (let i = open; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(start, i + 1); }
  }
  throw new Error('unbalanced braces extracting ' + name);
}
const promptFactory = new Function(
  'getCvGenderNeutralSummary',
  extractFrom(summarySource, 'cvSummaryPrompt') + '\nreturn cvSummaryPrompt;'
);
const neutralInstruction = 'Do NOT use gendered pronouns';
const promptOff = promptFactory(function(){ return false; })('CV TEXT', 'normal', '');
assert.ok(!promptOff.includes(neutralInstruction), 'toggle off must not add the neutral instruction');
const promptOn = promptFactory(function(){ return true; })('CV TEXT', 'normal', '');
assert.ok(promptOn.includes(neutralInstruction), 'toggle on must add the neutral instruction');
assert.ok(promptOn.includes('the candidate'), 'neutral instruction names "the candidate"');
assert.ok(promptOn.includes('do NOT use they/them') || promptOn.includes('they/them'), 'neutral instruction forbids they/them');

console.log('Gender-neutral summary frontend tests passed.');
