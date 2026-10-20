import {Agent, BRIDGE, csv, pause, profileURL} from './core.js';

const $ = id => document.getElementById(id);
let pairing = '', agent = null, abort = null, run = null, results = [], busy = false, connected = false;
const owned = new Map();

function status(message) { $('status').textContent = message; }
function controls() {
  $('start').disabled = busy || !connected;
  $('stop').disabled = !busy && (!run || run.stopped);
  $('export').disabled = !results.length;
  $('clear').disabled = busy;
  for (const id of ['brief', 'mode', 'open-search', 'pages', 'calls', 'consent', 'pair-button']) $(id).disabled = busy;
}
async function save() {
  await chrome.storage.session.set({sourcer: {run, results}});
}
function draw() {
  const holder = $('results');
  holder.replaceChildren();
  $('count').textContent = results.length;
  if (!results.length) {
    const empty = document.createElement('div'); empty.className = 'empty';
    empty.textContent = 'Your candidate list will appear here.'; holder.append(empty);
  }
  for (const row of results) {
    const card = document.createElement('article'); card.className = 'candidate';
    const top = document.createElement('div'); top.className = 'person';
    const link = document.createElement('a');
    link.href = profileURL(row.publicUrl) || profileURL(row.url); link.target = '_blank'; link.rel = 'noopener noreferrer';
    link.textContent = row.name;
    const score = document.createElement('span'); score.className = 'score'; score.textContent = row.score + ' / 100';
    top.append(link, score); card.append(top);
    const provenance = document.createElement('p'); provenance.className = 'source';
    provenance.textContent = (row.checked ? 'PROFILE DETAIL READ' : 'SEARCH CARD ONLY') + (row.publicUrl || /\/in\//.test(row.url) ? ' · Public LinkedIn link' : ' · Recruiter link; login required');
    card.append(provenance);
    const list = document.createElement('ul');
    for (const quote of row.evidence) { const item = document.createElement('li'); item.textContent = quote; list.append(item); }
    card.append(list);
    if (row.unknowns.length) {
      const missing = document.createElement('p'); missing.className = 'unknown';
      missing.textContent = 'Still unknown: ' + row.unknowns.join(' · '); card.append(missing);
    }
    holder.append(card);
  }
  if (run) $('usage').textContent = `${run.calls} / ${run.max_calls} API requests · ${run.tokens.toLocaleString()} reported tokens` + (run.usage_complete ? '' : ' · token usage incomplete');
  controls();
}
async function api(path, body, ignoreStop = false) {
  const response = await fetch(BRIDGE + path, {method: body ? 'POST' : 'GET',
    headers: {Authorization: 'Bearer ' + pairing, ...(body ? {'Content-Type': 'application/json'} : {})},
    ...(body ? {body: JSON.stringify(body)} : {}),
    signal: ignoreStop ? AbortSignal.timeout(10000) : (abort?.signal || AbortSignal.timeout(140000))});
  let value;
  try { value = await response.json(); } catch { throw Error('The local bridge returned an unreadable response.'); }
  if (!response.ok) throw Error(value.error || 'The local bridge could not finish the request.');
  return value;
}
async function loaded(tabId) {
  for (let i = 0; i < 35; i++) {
    if (abort?.signal.aborted) throw Error('Stopped.');
    const tab = await chrome.tabs.get(tabId);
    if (tab.status === 'complete') return tab;
    await pause(500, abort?.signal);
  }
  throw Error('LinkedIn did not finish loading. The agent stopped.');
}
const browser = {
  async activeTab() {
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    if (!tab?.id || !tab.url?.startsWith('https://www.linkedin.com/')) throw Error('Open LinkedIn in the active tab first.');
    return tab;
  },
  async navigate(tabId, url) {
    if (!url.startsWith('https://www.linkedin.com/search/results/people/?') && !profileURL(url)) throw Error('Navigation outside the search/profile boundary was blocked.');
    if (abort?.signal.aborted) throw Error('Stopped.');
    await chrome.tabs.update(tabId, {url});
    if (owned.has(tabId)) owned.set(tabId, profileURL(url));
    await loaded(tabId);
  },
  async createTab(url) {
    if (!profileURL(url) || abort?.signal.aborted) throw Error('The profile action stopped.');
    const tab = await chrome.tabs.create({url, active: false}); owned.set(tab.id, profileURL(url));
    try { await loaded(tab.id); return tab.id; }
    catch (error) { await browser.closeOwnedTab(tab.id); throw error; }
  },
  async read(tabId, method, args) {
    await loaded(tabId);
    const tab = await chrome.tabs.get(tabId);
    if (!tab.url?.startsWith('https://www.linkedin.com/')) throw Error('The tab left LinkedIn. The agent stopped.');
    await chrome.scripting.executeScript({target: {tabId}, files: ['reader.js']});
    const [{result}] = await chrome.scripting.executeScript({target: {tabId},
      func: (name, values) => globalThis.SourcerReader[name](...values), args: [method, args]});
    return result;
  },
  async closeOwnedTab(id) {
    if (!owned.has(id)) return;
    try {
      const tab = await chrome.tabs.get(id);
      if (profileURL(tab.url) === owned.get(id) && !tab.active) await chrome.tabs.remove(id);
    } catch { /* User may already have closed it. */ }
    owned.delete(id);
  }
};

$('pair-button').addEventListener('click', async () => {
  const value = $('pair').value.trim();
  if (!/^[A-Za-z0-9_-]{40,60}$/.test(value)) { status('Paste the pairing code from the local welcome page.'); return; }
  pairing = value;
  try {
    const info = await api('/api/status');
    connected = true; run = info.run;
    await chrome.storage.session.set({pairing});
    $('pair').value = ''; $('connected').textContent = 'Connected · DeepSeek'; $('connection').open = false;
    status(info.configured ? 'Ready. Describe the person you need.' : 'Save your DeepSeek key in CV Studio Settings first.');
    draw();
  } catch { connected = false; status('Could not connect. Start the local bridge and check its pairing code.'); controls(); }
});
$('mode').addEventListener('change', () => {
  $('mode-help').textContent = $('mode').value === 'standard' ? 'Open LinkedIn in the active tab and sign in first.' :
    'Open the Recruiter candidate search in the active tab. If automatic keyword entry is unavailable, use Review open search.';
});
$('start').addEventListener('click', async () => {
  if (busy) return;
  const options = {brief: $('brief').value.trim(), mode: $('mode').value,
    max_pages: Number($('pages').value), max_calls: Number($('calls').value),
    confirm_paid: $('consent').checked, use_open_search: $('open-search').checked};
  if (!options.confirm_paid) { status('Tick the DeepSeek usage and data-sharing confirmation to start.'); return; }
  if (options.brief.length < 5) { status('Describe the role, skills and location you need.'); return; }
  try { await browser.activeTab(); } catch (error) { status(error.message); return; }
  busy = true; results = []; run = null; abort = new AbortController();
  draw();
  agent = new Agent({api, browser, signal: abort.signal, update: patch => {
    if (patch.run) run = patch.run;
    if (patch.results) results = patch.results;
    if (patch.status) status(patch.status);
    if (patch.plan) { $('query').hidden = false; $('query').textContent = 'Search: ' + patch.plan.query; }
    draw(); save().catch(() => status('Browser session storage is unavailable; export your current list before closing.'));
  }});
  try { await agent.start(options); }
  catch (error) { status(abort.signal.aborted ? 'Stopped. Your current list is kept.' : error.message); }
  finally { busy = false; abort = null; draw(); await save(); }
});
$('stop').addEventListener('click', async () => {
  abort?.abort();
  status('Stopping. Current results are kept.');
  try {
    const current = run || agent?.run;
    if (current) run = (await api('/api/stop', {run_id: current.id}, true)).run;
    await save();
    if (!busy) status('Stopped. Current results are kept.');
  } catch { status('Stop was requested locally. The bridge may still have an in-flight call.'); }
  draw();
});
$('clear').addEventListener('click', async () => {
  if (busy) return;
  results = []; $('query').hidden = true; await save(); draw(); status('Candidate list cleared.');
});
$('export').addEventListener('click', () => {
  const url = URL.createObjectURL(new Blob([csv(results)], {type: 'text/csv;charset=utf-8'}));
  const link = document.createElement('a'); link.href = url; link.download = 'sourcing-candidates.csv'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 3000);
});
window.addEventListener('pagehide', () => {
  abort?.abort();
  if (run && !run.stopped) fetch(BRIDGE + '/api/stop', {method: 'POST', keepalive: true,
    headers: {'Content-Type': 'application/json', Authorization: 'Bearer ' + pairing}, body: JSON.stringify({run_id: run.id})}).catch(() => {});
});
const stored = await chrome.storage.session.get(['pairing', 'sourcer']);
pairing = stored.pairing || '';
if (stored.sourcer) { run = stored.sourcer.run; results = stored.sourcer.results || []; }
if (pairing) {
  try {
    const info = await api('/api/status'); connected = true; run = info.run;
    $('connected').textContent = 'Connected · DeepSeek'; $('connection').open = false;
    status(run && !run.stopped ? 'A previous run was interrupted. Press Stop before starting again.' :
      (info.configured ? 'Ready. Your last list is kept for this browser session.' : 'Save your DeepSeek key in CV Studio Settings first.'));
  } catch { status('Start the local bridge and reconnect. Your last list is kept.'); }
}
draw();
