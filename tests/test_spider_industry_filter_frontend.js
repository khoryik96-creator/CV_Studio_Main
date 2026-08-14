'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const source = fs.readFileSync(
  path.resolve(__dirname, '..', 'vendor', 'cvstudio', 'ai-crawler.js'),
  'utf8'
);

function functionBlock(name, nextMarker) {
  const marker = 'function ' + name + '(';
  const start = source.indexOf(marker);
  assert.ok(start >= 0, name + ' must remain present');
  const next = source.indexOf(nextMarker, start + marker.length);
  assert.ok(next >= 0, name + ' end marker must remain present');
  return source.slice(start, next >= 0 ? next : source.length);
}

const fallbackBody = functionBlock('buildTheSpiderFallbackQueries', 'function buildTheSpiderDiscoveryQueries(');
const discoveryBody = functionBlock('buildTheSpiderDiscoveryQueries', 'async function generateTheSpider(');
const searchBody = functionBlock('runTheSpiderJobAdderSearch', 'function copyTheSpiderReport(');

assert.ok(
  !fallbackBody.includes('inp.industry') && !discoveryBody.includes('inp.industry'),
  'Industry must never be inserted into latest-resume keyword queries'
);
assert.ok(
  !fallbackBody.includes('terms(inp.it_skills)') && !discoveryBody.includes('inp.it_skills'),
  'IT Skills must never be inserted into latest-resume keyword queries'
);
assert.ok(
  searchBody.includes('if (spiderInputs.industry || spiderInputs.it_skills)'),
  'custom-field searches must use one discovery query before exact backend filtering'
);
assert.ok(
  searchBody.includes('filters:spiderFilters'),
  'the selected Industry must still be sent to the backend filter contract'
);

const context = {
  window: {},
  normaliseTheSpiderBooleanRule(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  },
  splitTheSpiderKeywordTerms(value) {
    return String(value || '').split(/[,;\n]+/).map((item) => item.trim()).filter(Boolean);
  },
  hasTheSpiderBooleanSyntax(value) {
    return /\b(?:AND|OR|NOT)\b|[()"']/i.test(String(value || ''));
  },
  parseTheSpiderQueries() { return []; },
  getTheSpiderInputs() { return {}; }
};
vm.runInNewContext(fallbackBody + '\n' + discoveryBody, context);

const roleQueries = context.buildTheSpiderFallbackQueries({
  role: 'Software Engineer',
  industry: 'Financial Services',
  must: '', nice: '', it_skills: '', qualifications: '', adjacent: false,
  use_owl: false, jd: ''
});
assert.ok(roleQueries.includes('"Software Engineer"'));
assert.ok(roleQueries.every((query) => !query.includes('Financial Services')));

const itSkillQueries = context.buildTheSpiderFallbackQueries({
  role: 'Software Engineer',
  industry: '',
  must: '', nice: '', it_skills: 'Python', qualifications: '', adjacent: false,
  use_owl: false, jd: ''
});
assert.ok(itSkillQueries.includes('"Software Engineer"'));
assert.ok(itSkillQueries.every((query) => !query.includes('Python')));

const booleanQueries = context.buildTheSpiderDiscoveryQueries({
  role: 'Software Engineer',
  industry: 'Financial Services',
  must: 'Python AND AWS',
  strict: true
});
assert.deepStrictEqual(Array.from(booleanQueries), ['Python AND AWS']);

console.log('spider industry frontend corrective tests passed');
