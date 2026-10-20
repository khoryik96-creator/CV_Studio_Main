let connection = null, owned = new Map(), nextCount = 0, profileCount = 0, jobCapture = null;
const SESSION_KEY = 'cvstudioLinkedinSessionV1';
// Chrome session memory survives worker suspension, but not browser/extension
// restarts. Never store credentials, captured content or provider requests here.
let stateFailed = false, writes = Promise.resolve();
function local(value) {
  try { const u = new URL(value); return u.protocol === 'http:' && ['127.0.0.1', 'localhost'].includes(u.hostname) && u.pathname === '/'; }
  catch { return false; }
}
function linkedin(value) { try { return new URL(value).origin === 'https://www.linkedin.com'; } catch { return false; } }
function profile(value) {
  try { const u = new URL(value); return linkedin(value) && !u.username && !u.password && /^\/(in\/[^/]+|talent\/(?:hire\/)?profile\/[^/]+)\/?$/.test(u.pathname); }
  catch { return false; }
}
function jobURL(value) {
  try {
    const u = new URL(value);
    if (!linkedin(value) || u.username || u.password) return '';
    const view = u.pathname.match(/^\/jobs\/view\/(?:[^/]*-)?([0-9]{1,24})\/?$/);
    const ids = u.searchParams.getAll('currentJobId');
    const id = view ? view[1] : /^\/jobs(?:\/search|\/collections\/[^/]+)?\/?$/.test(u.pathname) && ids.length === 1 ? ids[0] : '';
    return /^[0-9]{1,24}$/.test(id) ? 'https://www.linkedin.com/jobs/view/' + id : '';
  } catch { return ''; }
}
function jobSearchKey(value) {
  try {
    if (typeof value !== 'string' || value.length > 2048) return '';
    const url = new URL(value);
    if (!linkedin(value) || url.username || url.password || !/^\/jobs\/search\/?$/.test(url.pathname)) return '';
    url.pathname = '/jobs/search/'; url.hash = '';
    for (const name of ['start','currentJobId','trk','trackingId','refId','lipi','position','pageNum','origin','refresh']) url.searchParams.delete(name);
    url.searchParams.sort(); return url.href;
  } catch { return ''; }
}
function jobSearchLive(bound, run, tab) {
  live(bound, run);
  if (bound.kind !== 'jobs' || Date.now() - bound.jobStarted > 600000 ||
      jobSearchKey(tab.url) !== bound.jobKey || tab.pendingUrl && jobSearchKey(tab.pendingUrl) !== bound.jobKey) throw Error('The job search changed or timed out. Start a new search.');
}
function persist() {
  const snapshot = {version:1, connection:connection ? {...connection, allowed:[...(connection.allowed || [])]} : null,
    owned:[...owned], nextCount:Math.min(nextCount,15), profileCount:Math.min(profileCount,76)};
  const write = writes.catch(() => {}).then(() => {
    if (stateFailed) throw Error('Companion session storage is unavailable.');
    return chrome.storage.session.set({[SESSION_KEY]:snapshot});
  });
  writes = write;
  return write.catch(error => { stateFailed = true; connection = null; throw error; });
}
async function restore() {
  const saved = (await chrome.storage.session.get(SESSION_KEY))[SESSION_KEY];
  if (!saved) return;
  if (saved.version !== 1 || !Array.isArray(saved.owned) || saved.owned.length > 76 ||
      !Number.isInteger(saved.nextCount) || saved.nextCount < 0 || saved.nextCount > 15 ||
      !Number.isInteger(saved.profileCount) || saved.profileCount < 0 || saved.profileCount > 76) throw Error('Invalid companion session.');
  for (const row of saved.owned) {
    if (!Array.isArray(row) || row.length !== 2 || !Number.isInteger(row[0]) || row[0] < 0 || owned.has(row[0]) || typeof row[1] !== 'string' || !row[1] || row[1].length > 2048 || !(profile(row[1]) || jobURL(row[1]) === row[1])) throw Error('Invalid owned tab.');
    owned.set(row[0], row[1]);
  }
  const bound = saved.connection;
  if (!bound) return;
  if (!Number.isInteger(bound.tabId) || bound.tabId < 0 || typeof bound.documentId !== 'string' || !bound.documentId || !local(bound.url) ||
      !Array.isArray(bound.allowed) || bound.allowed.length > 40 || bound.allowed.some(url => !profile(url)) || bound.kind && !['profiles','jobs'].includes(bound.kind) ||
      bound.run && (!/^[a-f0-9]{32}$/.test(bound.run) || !Number.isInteger(bound.source) || bound.source < 0 || !Number.isInteger(bound.pages) || bound.pages < 1 || bound.pages > 15) ||
      bound.kind === 'jobs' && (!jobSearchKey(bound.jobKey) || !Number.isFinite(bound.jobStarted) || !Number.isInteger(bound.jobScrolls) || bound.jobScrolls < 0 || bound.jobScrolls > 120)) throw Error('Invalid binding.');
  try {
    // Restore authority only for the exact still-live app document. Startup
    // verifies state; it never resumes browser actions or paid operations.
    const tab = await chrome.tabs.get(bound.tabId);
    if (!local(tab.url) || new URL(tab.url).origin !== new URL(bound.url).origin || tab.status === 'loading') throw Error('App document changed.');
    const [probe] = await chrome.scripting.executeScript({target:{tabId:bound.tabId, documentIds:[bound.documentId]},
      func:() => !!document.getElementById('viewLinkedinSourcer') && !!document.getElementById('tabLinkedinSourcer')});
    if (!probe?.result || probe.documentId !== bound.documentId) throw Error('App document changed.');
    connection = {tabId:bound.tabId, documentId:bound.documentId, url:bound.url, run:bound.run || null,
      source:bound.source, pages:bound.pages, allowed:new Set(bound.allowed), kind:bound.kind || 'profiles'};
    if (bound.kind === 'jobs') Object.assign(connection, {jobKey:bound.jobKey, jobStarted:bound.jobStarted, jobScrolls:bound.jobScrolls});
    nextCount = saved.nextCount; profileCount = saved.profileCount;
  } catch { connection = null; await persist(); }
}
const ready = restore().catch(() => { stateFailed = true; connection = null; owned.clear(); });
function event(change) {
  return ready.then(async () => { if (change()) await persist(); }).catch(() => { stateFailed = true; connection = null; });
}
function live(bound, run) {
  if (stateFailed || connection !== bound || run && bound.run !== run) throw Error('The companion connection changed.');
}
function expectedLoading(tab, expected) { return tab.status === 'loading' && tab.pendingUrl === expected; }
async function ownedTab(id) {
  // An activated or redirected tab belongs to the user permanently, including
  // after it becomes inactive again. Event listeners persist that relinquishment.
  const expected = owned.get(id), tab = await chrome.tabs.get(id);
  if (!expected || owned.get(id) !== expected || tab.active || tab.url !== expected && !expectedLoading(tab, expected) || tab.pendingUrl && tab.pendingUrl !== expected) {
    if (owned.has(id)) { owned.delete(id); await persist(); }
    throw Error('This profile tab was taken over. Start a new run to continue.');
  }
  return tab;
}
async function closeOwned(id, expected) {
  try {
    const tab = await chrome.tabs.get(id);
    if (owned.get(id) === expected && !tab.active && tab.url === expected && (!tab.pendingUrl || tab.pendingUrl === expected)) await chrome.tabs.remove(id);
  } catch {}
  if (owned.get(id) === expected) owned.delete(id);
}
chrome.action.onClicked.addListener(async tab => {
  try {
    await ready; await writes.catch(() => {});
    if (!local(tab.url)) { await chrome.action.setBadgeText({text: 'APP'}); return; }
    const [{result, documentId}] = await chrome.scripting.executeScript({target: {tabId: tab.id},
      func: () => !!document.getElementById('viewLinkedinSourcer') && !!document.getElementById('tabLinkedinSourcer')});
    if (!result || !documentId) { await chrome.action.setBadgeText({text: 'APP'}); return; }
    if (!stateFailed && connection?.tabId === tab.id && connection.documentId === documentId) { await chrome.action.setBadgeText({text:'ON'}); return; }
    stateFailed = false; connection = null;
    for (const [id, expected] of [...owned]) await closeOwned(id, expected);
    connection = {tabId:tab.id, documentId, url:tab.url, allowed:new Set()};
    nextCount = 0; profileCount = 0;
    await persist(); await chrome.action.setBadgeText({text: 'ON'});
  } catch { connection = null; stateFailed = true; await chrome.action.setBadgeText({text:'ERR'}); }
});
chrome.tabs.onRemoved.addListener(id => event(() => { const changed = connection?.tabId === id || owned.has(id); if (connection?.tabId === id) connection = null; owned.delete(id); return changed; }));
chrome.tabs.onUpdated.addListener((id, change) => event(() => {
  let changed = false;
  if (id === connection?.tabId && change.status === 'loading') { connection = null; changed = true; }
  if (owned.has(id) && change.url && change.url !== owned.get(id)) { owned.delete(id); changed = true; }
  return changed;
}));
chrome.tabs.onActivated.addListener(info => event(() => owned.delete(info.tabId)));
async function readJobTab(bound, id, expected) {
  const verify = tab => {
    if (connection !== bound || bound.run || jobURL(tab.url) !== expected || tab.pendingUrl && jobURL(tab.pendingUrl) !== expected || tab.status !== 'complete') throw Error('The selected job changed or has not loaded.');
  };
  verify(await chrome.tabs.get(id));
  await chrome.scripting.executeScript({target:{tabId:id}, files:['reader.js']});
  // A complete browser load can precede LinkedIn's React detail panel. Wait on
  // that same DOM briefly; never re-navigate or replay a failed network request.
  for (let attempt=0;attempt<16;attempt++) {
    verify(await chrome.tabs.get(id));
    const [{result}] = await chrome.scripting.executeScript({target:{tabId:id},
      func: url => {
        try { return globalThis.SourcerReader.readJob(url); }
        catch (error) { if (error.cvstudioJobLoading) return {loading:true}; throw error; }
      }, args:[expected]});
    verify(await chrome.tabs.get(id));
    if (!result?.loading) {
      if (result?.url !== expected) throw Error('The selected job changed while reading.');
      if (result.description || attempt >= 5) return result;
    }
    if (attempt < 15) await new Promise(resolve => setTimeout(resolve,350));
  }
  throw Error('The job details did not finish loading. Open the ad in Chrome and try Read job ad.');
}
async function handle(message, sender) {
  await ready;
  if (stateFailed || !connection || sender.tab?.id !== connection.tabId || sender.documentId !== connection.documentId || !local(sender.url)) {
    throw Error('In Chrome, open CV Studio and click the companion toolbar icon to connect this tab.');
  }
  const args = message.args || {};
  if (message.action === 'jobSearchTabs') {
    const tabs = await chrome.tabs.query({url:'https://www.linkedin.com/*'});
    return tabs.filter(tab => jobSearchKey(tab.url)).map(tab => ({id:tab.id, url:tab.url, title:String(tab.title || 'LinkedIn job search').slice(0,160)}));
  }
  if (message.action === 'jobSearchBegin') {
    if (!/^[a-f0-9]{32}$/.test(args.run_id || '') || !Number.isInteger(args.max_pages) || args.max_pages < 1 || args.max_pages > 15) throw Error('Choose 1 to 15 job-search pages.');
    if (connection.run === args.run_id && connection.kind === 'jobs') return {tab_id:connection.source};
    if (connection.run || jobCapture) throw Error('Stop the current browser action first.');
    let url;
    if (!args.use_open) {
      if (typeof args.query !== 'string' || !args.query.trim() || args.query.length > 240 || /[\x00-\x1f]/.test(args.query) ||
          typeof args.location !== 'string' || args.location.length > 160 || /[\x00-\x1f]/.test(args.location)) throw Error('Enter valid job keywords and location.');
      const target = new URL('https://www.linkedin.com/jobs/search/');
      target.searchParams.set('keywords', args.query.trim());
      if (args.location.trim()) target.searchParams.set('location', args.location.trim());
      url = target.href;
      if (!jobSearchKey(url)) throw Error('Shorten the job keywords or location.');
    } else if (!Number.isInteger(args.source_tab_id) || args.source_tab_id < 0) throw Error('Choose an open LinkedIn job search.');
    const bound = connection, token = {}; jobCapture = token;
    try {
      // A newly requested search is kept open as a user-facing result. It is
      // never repurposed as an owned profile tab or closed during cleanup.
      const tab = args.use_open ? await chrome.tabs.get(args.source_tab_id) : await chrome.tabs.create({url,active:false});
      live(bound);
      const key = jobSearchKey(url || tab.url);
      if (!key) throw Error('Open a LinkedIn Jobs search first.');
      Object.assign(bound, {kind:'jobs',run:args.run_id,source:tab.id,pages:args.max_pages,allowed:new Set(),jobKey:key,jobStarted:Date.now(),jobScrolls:0});
      nextCount = 0; profileCount = 0;
      await persist(); live(bound, args.run_id); return {tab_id:tab.id};
    } finally { if (jobCapture === token) jobCapture = null; }
  }
  if (message.action === 'jobTabs') {
    const tabs = await chrome.tabs.query({url: 'https://www.linkedin.com/*'});
    return tabs.filter(tab => jobURL(tab.url)).map(tab => ({id:tab.id, url:jobURL(tab.url), title:String(tab.title || 'LinkedIn job').slice(0, 160)}));
  }
  if (message.action === 'jobRead' || message.action === 'jobFromLink') {
    const bound = connection, expected = jobURL(message.action === 'jobRead' ? args.expected_url : args.url);
    if (!expected || bound.run || jobCapture) throw Error('Finish the current browser action before reading a job ad.');
    const token = {}; jobCapture = token;
    let created = null;
    try {
      if (message.action === 'jobRead') return await readJobTab(bound, args.tab_id, expected);
      // Only a canonical job URL explicitly submitted by the bound app may be
      // opened. Never navigate or close any pre-existing user tab.
      if (args.url !== expected) throw Error('Use a canonical LinkedIn job link.');
      for (const [id, value] of [...owned]) if (jobURL(value)) await closeOwned(id, value);
      await persist();
      const tabs = await chrome.tabs.query({url:'https://www.linkedin.com/*'});
      if (connection !== bound || bound.run) throw Error('The companion connection changed.');
      let tab = tabs.find(value => jobURL(value.url) === expected && value.status === 'complete') || tabs.find(value => jobURL(value.url) === expected);
      if (!tab) { tab = await chrome.tabs.create({url:expected, active:false}); created = tab.id; owned.set(created, expected); await persist(); }
      for (let attempt = 0; attempt < 40; attempt++) {
        if (connection !== bound || bound.run) throw Error('The companion connection changed.');
        const current = await chrome.tabs.get(tab.id);
        if (jobURL(current.url) !== expected && !(created === tab.id && (!current.url || current.url === 'about:blank') && current.pendingUrl === expected)) throw Error('The job left its expected page.');
        if (current.status === 'complete') return await readJobTab(bound, tab.id, expected);
        await new Promise(resolve => setTimeout(resolve, 500));
      }
      throw Error('The job ad did not finish loading.');
    } finally {
      if (created !== null) {
        await closeOwned(created, expected);
      }
      if (jobCapture === token) jobCapture = null;
      await persist();
    }
  }
  if (message.action === 'tabs') {
    const tabs = await chrome.tabs.query({url: 'https://www.linkedin.com/*'});
    return tabs.map(tab => ({id: tab.id, url: tab.url, title: String(tab.title || 'LinkedIn').slice(0, 160), status: tab.status}));
  }
  if (message.action === 'begin') {
    if (jobCapture) throw Error('Wait for the job ad to finish reading first.');
    if (!/^[a-f0-9]{32}$/.test(args.run_id || '')) throw Error('Invalid sourcing run.');
    if (connection.run && connection.run !== args.run_id) throw Error('Stop the current browser run first.');
    if (connection.run === args.run_id) return true;
    if (!Number.isInteger(args.max_pages) || args.max_pages < 1 || args.max_pages > 15 || !['standard', 'lite', 'recruiter'].includes(args.mode)) throw Error('Invalid browser run limits.');
    const bound = connection;
    const source = await chrome.tabs.get(args.source_tab_id);
    if (connection !== bound || jobCapture || !linkedin(source.url) || profile(source.url)) throw Error('Choose a LinkedIn search tab.');
    connection.source = source.id; connection.pages = args.max_pages;
    connection.kind = 'profiles';
    connection.allowed = new Set();
    connection.run = args.run_id; nextCount = 0; profileCount = 0; await persist(); live(bound, args.run_id); return true;
  }
  if (!connection.run || connection.run !== args.run_id) throw Error('The browser run has stopped or disconnected.');
  if (message.action === 'end') {
    connection.run = null;
    connection.kind = 'profiles'; delete connection.jobKey; delete connection.jobStarted; delete connection.jobScrolls;
    connection.allowed = new Set(); await persist();
    for (const [id, expected] of [...owned]) await closeOwned(id, expected);
    await persist(); return true;
  }
  if (connection.kind === 'jobs') {
    const bound = connection;
    if (message.action !== 'read' || args.tab_id !== bound.source || !['readJobSearch','nextJobSearch','scrollJobSearch'].includes(args.method) ||
        !Array.isArray(args.values) || args.values.length > 1 || args.values.some(value => typeof value !== 'string' || value.length > 4096)) throw Error('Unsupported job-search action.');
    const tab = await chrome.tabs.get(bound.source);
    if (tab.status === 'loading' && (!tab.url || tab.url === 'about:blank') && jobSearchKey(tab.pendingUrl) === bound.jobKey) return {loading:true};
    jobSearchLive(bound, args.run_id, tab);
    if (tab.status !== 'complete') return {loading:true};
    if (args.method === 'nextJobSearch') {
      nextCount++; await persist(); live(bound, args.run_id);
      if (nextCount >= bound.pages) throw Error('The requested job-page limit was reached.');
    }
    if (args.method === 'scrollJobSearch') {
      bound.jobScrolls++; await persist(); live(bound, args.run_id);
      if (bound.jobScrolls > bound.pages * 8) throw Error('The job-search scroll limit was reached.');
    }
    await chrome.scripting.executeScript({target:{tabId:tab.id},files:['reader.js']});
    jobSearchLive(bound, args.run_id, await chrome.tabs.get(tab.id));
    const [{result}] = await chrome.scripting.executeScript({target:{tabId:tab.id},
      func:(method, values) => globalThis.SourcerReader[method](...values), args:[args.method,args.values]});
    jobSearchLive(bound, args.run_id, await chrome.tabs.get(tab.id));
    return result;
  }
  if (message.action === 'create') {
    if (!profile(args.url) || !connection.allowed.has(args.url) || ++profileCount > 75) throw Error('The profile action is outside the run limits.');
    const bound = connection;
    await persist(); live(bound, args.run_id);
    const tab = await chrome.tabs.create({url: args.url, active: false}); owned.set(tab.id, args.url);
    try { await persist(); live(bound, args.run_id); return tab.id; }
    catch (error) { await closeOwned(tab.id, args.url); throw error; }
  }
  const bound = connection;
  const tab = owned.has(args.tab_id) ? await ownedTab(args.tab_id) : await chrome.tabs.get(args.tab_id);
  if (connection?.run !== args.run_id) throw Error('The browser run has stopped.');
  if (!linkedin(tab.url) && !(owned.has(tab.id) && expectedLoading(tab, owned.get(tab.id)))) throw Error('The selected tab left LinkedIn.');
  if (tab.id !== connection.source && !owned.has(tab.id)) throw Error('This tab does not belong to the sourcing run.');
  if (message.action === 'navigate') {
    const search = args.url?.startsWith('https://www.linkedin.com/search/results/people/?');
    if ((!search && !profile(args.url)) || (search && tab.id !== connection.source) ||
        (profile(args.url) && (!owned.has(tab.id) || !connection.allowed.has(args.url)))) throw Error('This navigation is not supported.');
    if (profile(args.url) && ++profileCount > 75) throw Error('The profile limit was reached.');
    const previous = owned.get(tab.id);
    if (previous) owned.set(tab.id, args.url);
    await persist(); live(bound, args.run_id);
    if (previous) {
      const current = await chrome.tabs.get(tab.id);
      if (owned.get(tab.id) !== args.url || current.active || current.url !== previous || current.pendingUrl && current.pendingUrl !== previous) {
        owned.delete(tab.id); await persist(); throw Error('This profile tab was taken over.');
      }
    }
    live(bound, args.run_id); await chrome.tabs.update(tab.id, {url: args.url});
    return true;
  }
  if (message.action === 'read') {
    if (!['readSearch', 'readProfile', 'search', 'next'].includes(args.method)) throw Error('This browser action is not supported.');
    if (args.method === 'readProfile' ? !owned.has(tab.id) : tab.id !== connection.source) throw Error('This read does not belong to the sourcing run.');
    if (tab.status !== 'complete') return {loading: true};
    if (args.method === 'next') { nextCount++; await persist(); live(bound, args.run_id); if (nextCount >= connection.pages) throw Error('The requested page limit was reached.'); }
    await chrome.scripting.executeScript({target: {tabId: tab.id}, files: ['reader.js']});
    if (connection?.run !== args.run_id) throw Error('The browser run has stopped.');
    if (args.method === 'readProfile') await ownedTab(tab.id);
    live(bound, args.run_id);
    const [{result}] = await chrome.scripting.executeScript({target: {tabId: tab.id},
      func: (method, values) => globalThis.SourcerReader[method](...values), args: [args.method, args.values || []]});
    live(bound, args.run_id);
    if (args.method === 'readSearch') { connection.allowed = new Set((result?.profiles || []).map(row => row.url).filter(profile).slice(0,40)); await persist(); }
    return result;
  }
  throw Error('Unsupported browser action.');
}
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (message?.kind !== 'sourcer') return false;
  handle(message, sender).then(result => reply({result}), () => reply({error: 'The browser action stopped. Reconnect the companion or check the LinkedIn page.'}));
  return true;
});
