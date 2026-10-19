import test from 'node:test';
import assert from 'node:assert/strict';
import {Agent, csv, mergeCandidates, profileURL, isSearchURL} from '../extension/core.js';

const profile = (id, n = 0) => ({id, name: `Sample Person ${n}`, url: `https://www.linkedin.com/in/sample-${n}`, text: 'Finance and SAP', score: 80, evidence: ['Finance'], unknowns: ['Location']});
test('only observed LinkedIn profile URLs are accepted; CSV cells cannot execute formulas', () => {
  for (const url of ['javascript:alert(1)', 'https://linkedin.com.evil.invalid/in/x', 'https://x:y@www.linkedin.com/in/x', 'https://www.linkedin.com/messaging/x']) assert.equal(profileURL(url), '');
  assert.equal(profileURL('https://www.linkedin.com/in/test?tracking=x'), 'https://www.linkedin.com/in/test');
  assert(isSearchURL('https://www.linkedin.com/talent/search', 'lite'));
  assert(!isSearchURL('https://www.linkedin.com/talent/profile/test', 'recruiter'));
  assert.match(csv([{...profile('p0'), name: '=HYPERLINK("x")'}]), /'=HYPERLINK/);
});
test('deduplication retains detail-read provenance', () => {
  let rows = mergeCandidates([], [profile('p0')], true);
  rows = mergeCandidates(rows, [{...profile('p9'), score: 99}]);
  assert.equal(rows.length, 1); assert.equal(rows[0].score, 80); assert(rows[0].checked);
});

function harness(mode, pages = 15, {repeat = false, stopOnReview = false, invented = false} = {}) {
  let page = 1, opens = 0, nexts = 0, calls = 0, stops = 0;
  const abort = new AbortController(), updates = [];
  const run = {id: 'run', max_calls: 80, calls: 0, tokens: 0};
  const api = async (path, value) => {
    if (path === '/api/start') return {run};
    if (path === '/api/plan') return {plan: {query: 'Finance SAP'}, run};
    if (path === '/api/stop') { stops++; return {run: {...run, stopped: true}}; }
    if (path === '/api/review') {
      calls++;
      if (stopOnReview) abort.abort();
      return {run, candidates: [{...profile('p0', page), ...(invented ? {url: 'https://www.linkedin.com/in/not-on-page'} : {})}]};
    }
    throw Error('unexpected API route');
  };
  const browser = {
    activeTab: async () => ({id: 1, url: mode === 'standard' ? 'https://www.linkedin.com/search/results/people/' : 'https://www.linkedin.com/talent/search'}),
    navigate: async () => {},
    createTab: async () => { opens++; return 2; },
    closeOwnedTab: async () => {},
    read: async (tab, method) => {
      if (method === 'search') return true;
      if (method === 'readSearch') return {profiles: [profile('p0', page)], signature: String(repeat ? 1 : page), hasNext: page < pages, paginationKnown: true};
      if (method === 'readProfile') return {text: 'Finance and SAP', name: `Sample Person ${page}`};
      if (method === 'next') { nexts++; page++; return true; }
      throw Error('unexpected browser action');
    }
  };
  const agent = new Agent({api, browser, signal: abort.signal, update: value => updates.push(value), wait: async () => {}});
  return {agent, abort, updates, options: {brief: 'Finance SAP', mode, max_pages: pages, max_calls: 80, confirm_paid: true, use_open_search: false},
    counts: () => ({opens, nexts, calls, stops})};
}
for (const mode of ['standard', 'lite', 'recruiter']) {
  test(`page-by-page sourcing across 15 synthetic ${mode} pages`, async () => {
    const h = harness(mode);
    await h.agent.start(h.options);
    assert.equal(h.agent.results.length, 15);
    assert.equal(h.counts().nexts, 14);
    assert.equal(h.counts().calls, 30);
    assert.equal(h.counts().stops, 1);
    assert(h.agent.results.every(p => p.checked));
  });
}
test('repeated pages stop instead of looping', async () => {
  const h = harness('standard', 3, {repeat: true});
  await assert.rejects(h.agent.start(h.options), /did not become ready|repeated/);
  assert.equal(h.counts().nexts, 1); assert.equal(h.counts().stops, 1);
});
test('Stop during screening prevents profile opening and pagination', async () => {
  const h = harness('standard', 3, {stopOnReview: true});
  await assert.rejects(h.agent.start(h.options), /Stopped/);
  assert.equal(h.counts().opens, 0); assert.equal(h.counts().nexts, 0); assert.equal(h.counts().stops, 1);
});
test('a fabricated model URL is never opened', async () => {
  const h = harness('standard', 1, {invented: true});
  await assert.rejects(h.agent.start(h.options), /unobserved profile/);
  assert.equal(h.counts().opens, 0);
});
test('an incompatible active page is rejected before a paid request', async () => {
  let calls = 0;
  const agent = new Agent({api: async () => { calls++; throw Error('must not call'); },
    browser: {activeTab: async () => ({id: 1, url: 'https://www.linkedin.com/feed/'})},
    signal: new AbortController().signal, update: () => {}});
  await assert.rejects(agent.start({mode: 'recruiter', use_open_search: false}), /Open the selected/);
  assert.equal(calls, 0);
});
