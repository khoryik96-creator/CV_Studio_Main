'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const source = fs.readFileSync(
  path.resolve(__dirname, '..', 'vendor', 'cvstudio', 'ai-crawler.js'),
  'utf8'
);
const indexSource = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');

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
  searchBody.includes('spiderInputs.qualifications') &&
    searchBody.includes('spiderInputs.residential') &&
    searchBody.includes('spiderInputs.salary_min'),
  'all profile eligibility filters must use one discovery query before exact backend filtering'
);
assert.ok(
  searchBody.includes('filters:spiderFilters'),
  'the selected Industry must still be sent to the backend filter contract'
);
assert.ok(
  searchBody.includes('queries = queries.slice(0,1)') &&
    !searchBody.includes('else {\n      queries = buildTheSpiderFallbackQueries(spiderInputs).slice(0,1);'),
  'exact filters must limit, not replace, the AI-generated JobAdder query'
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

const filterQueries = context.buildTheSpiderFallbackQueries({
  industry: 'Financial Services',
  must: 'Software Engineer', it_skills: 'Python', qualifications: 'PMP',
  use_owl: false, jd: ''
});
assert.ok(filterQueries.includes('"Software Engineer"'));
assert.ok(filterQueries.every((query) => !query.includes('Financial Services')));
assert.ok(filterQueries.every((query) => !query.includes('Python')));
assert.ok(filterQueries.every((query) => !query.includes('PMP')));

const booleanQueries = context.buildTheSpiderDiscoveryQueries({
  industry: 'Financial Services',
  must: 'Python AND AWS NOT internship',
  strict: true
});
assert.deepStrictEqual(Array.from(booleanQueries), ['Python AND AWS NOT internship']);

const jdOnlyQueries = context.buildTheSpiderFallbackQueries({
  must: '', use_owl: false, jd: 'Job Description\nSenior Accountant'
});
assert.deepStrictEqual(Array.from(jdOnlyQueries), ['"Senior Accountant"']);

for (const removedId of [
  'theSpiderRole', 'theSpiderNice', 'theSpiderExclude',
  'theSpiderTargets', 'theSpiderIncludeAdjacent', 'theSpiderSalary'
]) {
  assert.ok(!indexSource.includes('id="' + removedId + '"'), removedId + ' must be removed');
}
for (const requiredId of [
  'theSpiderSalaryCurrency', 'theSpiderSalaryMin',
  'theSpiderSalaryMax', 'theSpiderIncludeMissingSalary'
]) {
  assert.ok(indexSource.includes('id="' + requiredId + '"'), requiredId + ' must be present');
}
assert.ok(indexSource.includes('Use NOT here to exclude terms.'));

console.log('spider JobAdder eligibility frontend corrective tests passed');
