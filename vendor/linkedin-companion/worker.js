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
function pendingPeopleSearch(tab) {
  try {
    const url = new URL(tab.pendingUrl);
    return tab.status === 'loading' && (!tab.url || tab.url === 'about:blank') && linkedin(url.href) &&
      !url.username && !url.password && /^\/search\/results\/people\/?$/.test(url.pathname);
  } catch { return false; }
}
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
    const id = view ? view[1] : /^\/jobs(?:\/search(?:-results)?|\/collections\/[^/]+)?\/?$/.test(u.pathname) && ids.length === 1 ? ids[0] : '';
    return /^[0-9]{1,24}$/.test(id) ? 'https://www.linkedin.com/jobs/view/' + id : '';
  } catch { return ''; }
}
function jobSearchKey(value) {
  try {
    if (typeof value !== 'string' || value.length > 2048) return '';
    const url = new URL(value);
    if (!linkedin(value) || url.username || url.password || !/^\/jobs\/search(?:-results)?\/?$/.test(url.pathname)) return '';
    url.pathname = '/jobs/search/'; url.hash = '';
    for (const name of ['start','currentJobId','trk','trackingId','refId','lipi','position','pageNum','origin','refresh','eBP']) url.searchParams.delete(name);
    url.searchParams.sort(); return url.href;
  } catch { return ''; }
}
function hrCompanyURL(value) {
  return typeof value === 'string' && /^https:\/\/www\.linkedin\.com\/company\/[A-Za-z0-9_-]+\/$/.test(value) ? value : '';
}
function hrSearchKey(value) {
  try {
    const url = new URL(value);
    if (!linkedin(value) || url.username || url.password || !/^\/search\/results\/people\/?$/.test(url.pathname)) return '';
    url.pathname = '/search/results/people/'; url.hash = '';
    for (const name of ['origin','lipi','trk','sid','skipRedirect','page']) url.searchParams.delete(name);
    url.searchParams.sort(); return url.href;
  } catch { return ''; }
}
async function hrScript(bound, run, method, values) {
  live(bound,run);
  const expected = bound.hr.stage === 'company' ? bound.hr.company_url+'people/' : bound.hr.key;
  const check = async () => {
    live(bound,run); const tab = await chrome.tabs.get(bound.source);
    if (tab.status !== 'complete' || (expected.endsWith('/people/') && expected.includes('/company/') ? tab.url !== expected : hrSearchKey(tab.url) !== expected) || tab.pendingUrl && hrSearchKey(tab.pendingUrl) !== hrSearchKey(tab.url)) throw safeError('The HR search changed. Start again from the saved ad.');
  };
  await check();
  await jobScript({target:{tabId:bound.source},files:['reader.js']},jobReaderStartError);
  await check();
  const [injection] = await jobScript({target:{tabId:bound.source},func:(method,values)=>{
    try { return globalThis.SourcerReader[method](...values); }
    catch(error) { return {hrError:/sign in|verification|restriction/i.test(String(error?.message)) ? 'access' : 'layout'}; }
  },args:[method,values]},jobReaderReadError);
  live(bound,run);
  if (injection?.result?.hrError) throw safeError(injection.result.hrError === 'access' ? 'LinkedIn needs sign-in or is showing a restriction. Resolve it in the search tab before trying again.' : 'The company or LinkedIn layout could not be confirmed. Check the company page and try again.');
  return injection?.result;
}
async function hrMutation(bound, run, method, values, nextStage) {
  const before = bound.hr.stage;
  // Persist before clicks/navigation. Suspension during a mutation stops visibly;
  // it never repeats a possibly completed browser action.
  bound.hr.stage = 'interrupted'; await persist(); live(bound,run);
  const result = await hrScript(bound,run,method,values);
  if (typeof result !== 'boolean') throw safeError('The HR browser action was interrupted. Start a new scan.');
  bound.hr.stage = result ? nextStage : before; await persist(); return result;
}
function jobSearchLive(bound, run, tab) {
  live(bound, run);
  if (bound.kind !== 'jobs' || Date.now() - bound.jobStarted > 600000 ||
      jobSearchKey(tab.url) !== bound.jobKey || tab.pendingUrl && jobSearchKey(tab.pendingUrl) !== bound.jobKey) throw safeError('The job search changed or timed out. Choose the job search already open in Chrome to review its current results.');
}
function safeError(message) { const error = Error(message); error.cvstudioSafe = true; return error; }
async function jobScript(options, message) {
  try {
    const results = await chrome.scripting.executeScript(options);
    if (!Array.isArray(results) || !results.length) throw Error();
    return results;
  } catch { throw safeError(message); }
}
const jobReaderStartError = 'The LinkedIn reader could not start. Refresh LinkedIn, then reload and reconnect the latest companion.';
const jobReaderReadError = 'LinkedIn job results could not be read. Refresh LinkedIn and try again. If this repeats, update and reload the companion.';
async function settleJobSearch(bound, run, tab) {
  live(bound,run);
  const actual = jobSearchKey(tab.url);
  if (!actual) throw safeError('The tab left LinkedIn Jobs search. Open a job search and try again.');
  if (tab.pendingUrl && jobSearchKey(tab.pendingUrl) !== actual) return false;
  const requested = new URL(bound.jobKey), resolved = new URL(actual);
  requested.searchParams.delete('location');
  for (const name of ['location','geoId','distance']) resolved.searchParams.delete(name);
  if (requested.href !== resolved.href) throw safeError('LinkedIn changed the search keywords or filters. Choose the already-open search to review its current results.');
  await jobScript({target:{tabId:tab.id},files:['reader.js']},jobReaderStartError);
  live(bound,run);
  const [{result}] = await jobScript({target:{tabId:tab.id},func:method => globalThis.SourcerReader[method](),args:['jobSearchContext']},jobReaderReadError);
  if (!result || typeof result.location !== 'string') throw safeError(jobReaderReadError);
  live(bound,run);
  const current = await chrome.tabs.get(tab.id);
  if (jobSearchKey(current.url) !== actual || current.pendingUrl && jobSearchKey(current.pendingUrl) !== actual) throw safeError('The job search changed while loading. Choose the already-open search to continue.');
  if (current.status !== 'complete') return false;
  if (bound.jobLocation) {
    if (!result?.location) return false;
    const normalize = value => value.trim().replace(/\s+/g,' ').toLocaleLowerCase();
    if (normalize(result.location) !== normalize(bound.jobLocation)) throw safeError('LinkedIn is showing a different location. Set the location on LinkedIn, then choose Job search already open in Chrome.');
  }
  bound.jobKey = actual; bound.jobInitial = false; delete bound.jobLocation;
  await persist(); jobSearchLive(bound,run,await chrome.tabs.get(tab.id)); return true;
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
      !Array.isArray(bound.allowed) || bound.allowed.length > 40 || bound.allowed.some(url => !profile(url)) || bound.kind && !['profiles','jobs','hr'].includes(bound.kind) ||
      bound.run && (!/^[a-f0-9]{32}$/.test(bound.run) || !Number.isInteger(bound.source) || bound.source < 0 || !Number.isInteger(bound.pages) || bound.pages < 1 || bound.pages > 15) ||
      bound.kind === 'jobs' && (!jobSearchKey(bound.jobKey) || !Number.isFinite(bound.jobStarted) || !Number.isInteger(bound.jobScrolls) || bound.jobScrolls < 0 || bound.jobScrolls > 120 ||
        bound.jobInitial && (bound.jobInitial !== true || typeof bound.jobLocation !== 'string' || bound.jobLocation.length > 160)) ||
      bound.kind === 'hr' && (!bound.hr || !hrCompanyURL(bound.hr.company_url) || typeof bound.hr.company !== 'string' || bound.hr.company.length > 200 || typeof bound.hr.country !== 'string' || bound.hr.country.length > 100 ||
        typeof bound.hr.keywords !== 'string' || bound.hr.keywords.length > 600 || !Number.isFinite(bound.hr.started) || !['company','search','type','pick','apply','country_wait','ready','interrupted'].includes(bound.hr.stage) ||
        bound.hr.stage !== 'company' && (!/^[0-9]{1,24}$/.test(bound.hr.company_id || '') || !bound.hr.key) ||
        bound.hr.key && (bound.hr.key.length > 2048 || hrSearchKey(bound.hr.key) !== bound.hr.key))) throw Error('Invalid binding.');
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
    if (bound.kind === 'jobs') Object.assign(connection, {jobKey:bound.jobKey, jobStarted:bound.jobStarted, jobScrolls:bound.jobScrolls,jobInitial:bound.jobInitial === true,jobLocation:bound.jobLocation || ''});
    if (bound.kind === 'hr') connection.hr = {...bound.hr};
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
function sameOwnedPage(value, expected) {
  // LinkedIn may add a single trailing slash while loading an observed profile.
  // Do not equate query/hash changes, another identity or arbitrary redirects.
  return value === expected || !!profile(expected) && !/[?#]/.test(expected) && value === expected.replace(/\/$/,'') + '/';
}
function expectedLoading(tab, expected) { return tab.status === 'loading' && sameOwnedPage(tab.pendingUrl, expected); }
async function ownedTab(id) {
  // An activated or differently redirected tab belongs to the user permanently, including
  // after it becomes inactive again. Event listeners persist that relinquishment.
  const expected = owned.get(id), tab = await chrome.tabs.get(id);
  if (!expected || owned.get(id) !== expected || tab.active || !sameOwnedPage(tab.url, expected) && !expectedLoading(tab, expected) || tab.pendingUrl && !sameOwnedPage(tab.pendingUrl, expected)) {
    if (owned.has(id)) { owned.delete(id); await persist(); }
    throw safeError('The background profile tab changed or was opened manually. Your candidate list is kept. Start again and leave the background profile tabs untouched.');
  }
  return tab;
}
async function closeOwned(id, expected) {
  try {
    const tab = await chrome.tabs.get(id);
    if (owned.get(id) === expected && !tab.active && sameOwnedPage(tab.url, expected) && (!tab.pendingUrl || sameOwnedPage(tab.pendingUrl, expected))) await chrome.tabs.remove(id);
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
  if (owned.has(id) && change.url && !sameOwnedPage(change.url, owned.get(id))) { owned.delete(id); changed = true; }
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
async function pickJob(message, sender) {
  await ready;
  const bound = connection, expected = jobURL(message.url), operation = message.operation === undefined ? 'add' : message.operation;
  if (!['add','remove','folders','create_folder'].includes(operation) || message.folder !== undefined &&
      (typeof message.folder !== 'string' || message.folder.length > 80 || /[\x00-\x1f]/.test(message.folder))) throw safeError('Choose a valid folder or job-ad action.');
  if (operation === 'create_folder' && (typeof message.folder !== 'string' || !message.folder.trim())) throw safeError('Enter a folder name.');
  if (stateFailed || !bound) throw safeError('Open Job Leads in CV Studio and connect its companion toolbar icon first.');
  if (!expected || expected !== message.url || sender.frameId !== 0 || !sender.documentId || !Number.isInteger(sender.tab?.id) ||
      !(jobSearchKey(sender.url) || jobURL(sender.url))) throw safeError('Choose a visible LinkedIn job ad.');
  const foldersOnly = operation === 'folders';
  if (!foldersOnly && (bound.run || jobCapture)) throw safeError('Wait for the current search or ad read to finish, then add this ad.');
  const token = foldersOnly ? null : {}; if (token) jobCapture = token;
  try {
    const appTab = await chrome.tabs.get(bound.tabId);
    live(bound);
    if (!local(appTab.url) || appTab.status !== 'complete' || new URL(appTab.url).origin !== new URL(bound.url).origin) throw safeError('Reconnect the CV Studio tab.');
    const target = {tabId:sender.tab.id,documentIds:[sender.documentId]};
    const verify = async () => {
      live(bound);
      const tab = await chrome.tabs.get(sender.tab.id);
      const same = value => jobSearchKey(sender.url) ? jobSearchKey(value) === jobSearchKey(sender.url) : jobURL(value) === expected;
      if (tab.status !== 'complete' || !same(tab.url) || tab.pendingUrl && !same(tab.pendingUrl)) throw safeError('The LinkedIn page changed. Add the ad again from its current card.');
    };
    await verify();
    let result = {url:expected};
    if (foldersOnly) {
      const [probe] = await chrome.scripting.executeScript({target,func:() => location.origin === 'https://www.linkedin.com'});
      if (!probe?.result || probe.documentId !== sender.documentId) throw safeError('The LinkedIn page changed. Refresh its folders and try again.');
    } else {
      await chrome.scripting.executeScript({target,files:['reader.js']});
      await verify();
      [{result}] = await chrome.scripting.executeScript({target,func:url => globalThis.SourcerReader.readJobPick(url),args:[expected]});
      if (result?.url !== expected || !result.company || !result.role) throw safeError('The ad details have not loaded. Try again after the card appears.');
    }
    await verify();
    const id = crypto.randomUUID().replaceAll('-','');
    const request = {action:operation,...(message.folder === undefined ? {} : {folder:message.folder})};
    const saved = await chrome.tabs.sendMessage(bound.tabId,{type:'CVSTUDIO_JOB_CAPTURE',id,record:result,request},{documentId:bound.documentId});
    if (!saved?.ok) throw safeError(saved?.error || 'Open Job Leads in the connected CV Studio tab, then add this ad again.');
    return {ok:true,duplicate:!!saved.duplicate,folder:saved.folder || '',saved:saved.saved !== false,
      ...(Array.isArray(saved.folders) ? {folders:saved.folders} : {}),...(saved.warning ? {warning:saved.warning} : {})};
  } finally { if (token && jobCapture === token) jobCapture = null; }
}
async function handle(message, sender) {
  await ready;
  if (stateFailed || !connection || sender.tab?.id !== connection.tabId || sender.documentId !== connection.documentId || !local(sender.url)) {
    throw Error('In Chrome, open CV Studio and click the companion toolbar icon to connect this tab.');
  }
  const args = message.args || {};
  if (message.action === 'jobStatus') return {connected:true,job_read:true,job_search:true,job_search_revision:1,company_hr_revision:1,version:chrome.runtime.getManifest().version,busy:!!connection.run || !!jobCapture};
  if (message.action === 'hrBegin') {
    const bound = connection;
    if (!/^[a-f0-9]{32}$/.test(args.run_id || '') || !hrCompanyURL(args.company_url) || typeof args.company !== 'string' || !args.company.trim() || args.company.length > 200 ||
      typeof args.country !== 'string' || args.country.length > 100 || typeof args.keywords !== 'string' || !args.keywords.split(',').some(word=>word.trim()) || args.keywords.length > 600 || /[\x00-\x1f]/.test(args.company+args.country+args.keywords) ||
      !Number.isInteger(args.max_pages) || args.max_pages < 1 || args.max_pages > 15) throw safeError('Choose a LinkedIn company page, country and 1 to 15 pages.');
    if (bound.run === args.run_id && bound.kind === 'hr') return {tab_id:bound.source};
    if (bound.run || jobCapture) throw safeError('Finish the current companion search first.');
    const token = {}; jobCapture = token;
    try {
      const tab = await chrome.tabs.create({url:args.company_url+'people/',active:false}); live(bound);
      Object.assign(bound,{kind:'hr',run:args.run_id,source:tab.id,pages:args.max_pages,allowed:new Set(),
        hr:{company_url:args.company_url,company:args.company.trim(),country:args.country.trim(),keywords:args.keywords.trim(),stage:'company',key:'',started:Date.now()}});
      nextCount=0; await persist(); return {tab_id:tab.id};
    } finally { if (jobCapture === token) jobCapture = null; }
  }
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
      Object.assign(bound, {kind:'jobs',run:args.run_id,source:tab.id,pages:args.max_pages,allowed:new Set(),jobKey:key,jobStarted:Date.now(),jobScrolls:0,jobInitial:!args.use_open,jobLocation:args.use_open ? '' : args.location.trim()});
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
    return tabs.map(tab => ({id: tab.id, url: pendingPeopleSearch(tab) ? tab.pendingUrl : tab.url, title: String(tab.title || 'LinkedIn').slice(0, 160), status: tab.status,
      lastAccessed:Number.isFinite(tab.lastAccessed) ? tab.lastAccessed : 0,active:tab.active === true}));
  }
  if (message.action === 'openPeopleSearch') {
    const bound = connection, token = {};
    if (bound.run || jobCapture) throw safeError('Stop the current browser action before opening a new People search.');
    jobCapture = token;
    try {
      // This source stays open for the user; it is never an owned profile tab.
      // No caller-provided URL or navigation of an existing tab is permitted.
      const url = 'https://www.linkedin.com/search/results/people/';
      const tab = await chrome.tabs.create({url,active:false});
      live(bound);
      return {id:tab.id,url,title:'New LinkedIn People search',status:tab.status};
    } finally { if (jobCapture === token) jobCapture = null; }
  }
  if (message.action === 'begin') {
    if (jobCapture) throw Error('Wait for the job ad to finish reading first.');
    if (!/^[a-f0-9]{32}$/.test(args.run_id || '')) throw Error('Invalid sourcing run.');
    if (connection.run && connection.run !== args.run_id) throw Error('Stop the current browser run first.');
    if (connection.run === args.run_id) return true;
    if (!Number.isInteger(args.max_pages) || args.max_pages < 1 || args.max_pages > 15 || !['standard', 'lite', 'recruiter'].includes(args.mode)) throw Error('Invalid browser run limits.');
    const bound = connection;
    const source = await chrome.tabs.get(args.source_tab_id);
    if (connection !== bound || jobCapture || !linkedin(source.url) && !pendingPeopleSearch(source) || profile(source.url)) throw Error('Choose a LinkedIn search tab.');
    connection.source = source.id; connection.pages = args.max_pages;
    connection.kind = 'profiles';
    connection.allowed = new Set();
    connection.run = args.run_id; nextCount = 0; profileCount = 0; await persist(); live(bound, args.run_id); return true;
  }
  if (!connection.run || connection.run !== args.run_id) throw Error('The browser run has stopped or disconnected.');
  if (message.action === 'end') {
    connection.run = null;
    connection.kind = 'profiles'; delete connection.jobKey; delete connection.jobStarted; delete connection.jobScrolls; delete connection.jobInitial; delete connection.jobLocation;
    delete connection.hr;
    connection.allowed = new Set(); await persist();
    for (const [id, expected] of [...owned]) await closeOwned(id, expected);
    await persist(); return true;
  }
  if (connection.kind === 'hr') {
    const bound = connection, hr = bound.hr, run = args.run_id;
    if (!['hrRead','hrNext'].includes(message.action) || args.tab_id !== bound.source) throw safeError('This action does not belong to the company HR search.');
    if (jobCapture) throw safeError('Wait for the current HR browser action to finish.');
    const token = {}; jobCapture = token;
    try {
    if (Date.now()-hr.started > 600000 || hr.stage === 'interrupted') throw safeError('The HR search timed out or was interrupted. Start a new scan.');
    const tab = await chrome.tabs.get(bound.source); live(bound,run);
    if (!linkedin(tab.url) && !(tab.status === 'loading' && (!tab.url || tab.url === 'about:blank'))) throw safeError('The HR search left LinkedIn.');
    if (tab.status !== 'complete') return {loading:true};
    if (message.action === 'hrNext') {
      if (hr.stage !== 'ready' || typeof args.signature !== 'string' || !args.signature || args.signature.length > 17000) throw safeError('Read the HR results before paging.');
      nextCount++; await persist(); if (nextCount >= bound.pages) throw safeError('The HR page limit was reached.');
      return hrMutation(bound,run,'nextHRSearch',[args.signature,hr.company,hr.country,hr.keywords],'ready');
    }
    if (hr.stage === 'company') {
      const result = await hrScript(bound,run,'readHRCompany',[hr.company_url,hr.company]);
      if (result?.loading || result == null) return {loading:true};
      if (!/^[0-9]{1,24}$/.test(result.company_id || '')) throw safeError('The company employee link could not be confirmed.');
      hr.company_id = result.company_id;
      const url = new URL('https://www.linkedin.com/search/results/people/');
      url.searchParams.set('currentCompany',JSON.stringify([hr.company_id]));
      url.searchParams.set('keywords',hr.keywords.split(',').map(x=>x.trim()).filter(Boolean).map(x=>'"'+x.replaceAll('"','')+'"').join(' OR '));
      hr.key = hrSearchKey(url.href); hr.stage='interrupted'; await persist(); live(bound,run);
      if (hr.key.length > 2048) throw safeError('Shorten the HR keywords before starting a new scan.');
      await chrome.tabs.update(bound.source,{url:hr.key}); live(bound,run); hr.stage='search'; await persist(); return {loading:true};
    }
    if (hr.stage === 'country_wait') {
      const resolved = new URL(tab.url), expected = new URL(hr.key);
      const geo = resolved.searchParams.getAll('geoUrn');
      if (geo.length !== 1 || !/^\["[0-9]{1,24}"\]$/.test(geo[0])) return {loading:true};
      expected.searchParams.set('geoUrn',geo[0]);
      if (hrSearchKey(resolved.href) !== hrSearchKey(expected.href)) throw safeError('LinkedIn changed the company or keywords. Start a new scan.');
      hr.key=hrSearchKey(expected.href); hr.stage='ready'; await persist();
    }
    if (hr.stage === 'search' && !hr.country) { hr.stage='ready'; await persist(); }
    if (hr.stage === 'search') { await hrMutation(bound,run,'hrCountryOpen',[hr.country],'type'); return {loading:true}; }
    if (hr.stage === 'type') { await hrMutation(bound,run,'hrCountryType',[hr.country],'pick'); return {loading:true}; }
    if (hr.stage === 'pick') { await hrMutation(bound,run,'hrCountryPick',[hr.country],'apply'); return {loading:true}; }
    if (hr.stage === 'apply') { await hrMutation(bound,run,'hrCountryApply',[hr.country],'country_wait'); return {loading:true}; }
    const result = await hrScript(bound,run,'readHRSearch',[hr.company,hr.country,hr.keywords]);
    if (result == null || result.loading) return {loading:true};
    if (!Array.isArray(result.people) || result.people.length > 40 || typeof result.signature !== 'string') throw safeError('The HR results could not be read.');
    if (hrSearchKey((await chrome.tabs.get(bound.source)).url) !== hr.key) throw safeError('The HR search changed during the read.');
    return {...result,company_id:hr.company_id,source_url:hr.key};
    } finally { if (jobCapture === token) jobCapture = null; }
  }
  if (connection.kind === 'jobs') {
    const bound = connection;
    if (message.action !== 'read' || args.tab_id !== bound.source || !['readJobSearch','nextJobSearch','scrollJobSearch'].includes(args.method) ||
        !Array.isArray(args.values) || args.values.length > 1 || args.values.some(value => typeof value !== 'string' || value.length > 4096)) throw Error('Unsupported job-search action.');
    const tab = await chrome.tabs.get(bound.source);
    if (bound.jobInitial) {
      if (Date.now() - bound.jobStarted > 600000) throw safeError('The job search timed out. Start a new search.');
      if (tab.status !== 'complete') return {loading:true};
      if (!await settleJobSearch(bound,args.run_id,tab)) return {loading:true};
    }
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
    await jobScript({target:{tabId:tab.id},files:['reader.js']},jobReaderStartError);
    jobSearchLive(bound, args.run_id, await chrome.tabs.get(tab.id));
    const [{result}] = await jobScript({target:{tabId:tab.id},
      func:(method, values) => globalThis.SourcerReader[method](...values), args:[args.method,args.values]},jobReaderReadError);
    if (args.method === 'readJobSearch' ? !result || !Array.isArray(result.jobs) && result.loading !== true : typeof result !== 'boolean') throw safeError(jobReaderReadError);
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
  if (!linkedin(tab.url) && !(owned.has(tab.id) && expectedLoading(tab, owned.get(tab.id))) && !(tab.id === connection.source && pendingPeopleSearch(tab))) throw Error('The selected tab left LinkedIn.');
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
      if (owned.get(tab.id) !== args.url || current.active || !sameOwnedPage(current.url, previous) || current.pendingUrl && !sameOwnedPage(current.pendingUrl, previous)) {
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
    const readerError = 'LinkedIn results could not be read. Refresh LinkedIn, then reload and reconnect the latest companion.';
    await jobScript({target: {tabId: tab.id}, files: ['reader.js']},readerError);
    if (connection?.run !== args.run_id) throw Error('The browser run has stopped.');
    if (args.method === 'readProfile') await ownedTab(tab.id);
    live(bound, args.run_id);
    const [injection] = await jobScript({target: {tabId: tab.id},
      func: (method, values) => {
        try { return globalThis.SourcerReader[method](...values); }
        // Script exceptions may arrive without a serializable result. Return a
        // fixed reason instead of leaking page content or treating failure as empty.
        catch (error) { return {cvstudioReaderError:/sign in|verification check|access or usage restriction/i.test(String(error?.message)) ? 'access' : 'reader'}; }
      }, args: [args.method, args.values || []]},readerError);
    const result = injection?.result;
    live(bound, args.run_id);
    if (result?.cvstudioReaderError) throw safeError(result.cvstudioReaderError === 'access' ? 'LinkedIn needs sign-in or a verification check, or is showing a restriction. Open its tab and resolve this before starting again.' : readerError);
    if (result == null) {
      if (['readSearch','readProfile'].includes(args.method)) return {loading:true};
      throw safeError(readerError);
    }
    if (args.method === 'readSearch' && !Array.isArray(result.profiles)) throw safeError(readerError);
    if (args.method === 'readSearch') { connection.allowed = new Set((result?.profiles || []).map(row => row.url).filter(profile).slice(0,40)); await persist(); }
    return result;
  }
  throw Error('Unsupported browser action.');
}
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (message?.kind === 'sourcer_job_pick') {
    pickJob(message,sender).then(result => reply({result}),error => reply({error:error.cvstudioSafe ? error.message : 'The ad could not be added. Reconnect the companion and try again.'}));
    return true;
  }
  if (message?.kind !== 'sourcer') return false;
  handle(message, sender).then(result => reply({result}), error => reply({error: error.cvstudioSafe ? error.message : 'The browser action stopped. Reconnect the companion or check the LinkedIn page.'}));
  return true;
});
