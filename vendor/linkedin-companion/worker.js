let connection = null, owned = new Map(), nextCount = 0, profileCount = 0;
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
chrome.action.onClicked.addListener(async tab => {
  if (!local(tab.url)) { await chrome.action.setBadgeText({text: 'APP'}); return; }
  const [{result, documentId}] = await chrome.scripting.executeScript({target: {tabId: tab.id},
    func: () => !!document.getElementById('viewLinkedinSourcer') && !!document.getElementById('tabLinkedinSourcer')});
  if (!result) { await chrome.action.setBadgeText({text: 'APP'}); return; }
  connection = {tabId: tab.id, documentId, url: tab.url};
  await chrome.action.setBadgeText({text: 'ON'});
});
chrome.tabs.onRemoved.addListener(id => { if (connection?.tabId === id) connection = null; owned.delete(id); });
chrome.tabs.onUpdated.addListener((id, change) => { if (id === connection?.tabId && change.status === 'loading') connection = null; });
async function handle(message, sender) {
  if (!connection || sender.tab?.id !== connection.tabId || sender.documentId !== connection.documentId || !local(sender.url)) {
    throw Error('In Chrome, open CV Studio and click the companion toolbar icon to connect this tab.');
  }
  const args = message.args || {};
  if (message.action === 'jobTabs') {
    const tabs = await chrome.tabs.query({url: 'https://www.linkedin.com/*'});
    return tabs.filter(tab => jobURL(tab.url)).map(tab => ({id:tab.id, url:jobURL(tab.url), title:String(tab.title || 'LinkedIn job').slice(0, 160)}));
  }
  if (message.action === 'jobRead') {
    const bound = connection, expected = jobURL(args.expected_url);
    if (connection.run) throw Error('Stop the sourcing run before reading a job ad.');
    const tab = await chrome.tabs.get(args.tab_id);
    if (!expected || jobURL(tab.url) !== expected || tab.status !== 'complete' || connection !== bound) throw Error('The selected job changed or has not loaded. Refresh job tabs.');
    await chrome.scripting.executeScript({target:{tabId:tab.id}, files:['reader.js']});
    if (connection !== bound || bound.run) throw Error('The companion connection changed.');
    const [{result}] = await chrome.scripting.executeScript({target:{tabId:tab.id},
      func: url => globalThis.SourcerReader.readJob(url), args:[expected]});
    const current = await chrome.tabs.get(tab.id);
    if (connection !== bound || bound.run || jobURL(current.url) !== expected || result?.url !== expected) throw Error('The selected job changed while reading.');
    return result;
  }
  if (message.action === 'tabs') {
    const tabs = await chrome.tabs.query({url: 'https://www.linkedin.com/*'});
    return tabs.map(tab => ({id: tab.id, url: tab.url, title: String(tab.title || 'LinkedIn').slice(0, 160), status: tab.status}));
  }
  if (message.action === 'begin') {
    if (!/^[a-f0-9]{32}$/.test(args.run_id || '')) throw Error('Invalid sourcing run.');
    if (connection.run && connection.run !== args.run_id) throw Error('Stop the current browser run first.');
    if (connection.run === args.run_id) return true;
    if (!Number.isInteger(args.max_pages) || args.max_pages < 1 || args.max_pages > 15 || !['standard', 'lite', 'recruiter'].includes(args.mode)) throw Error('Invalid browser run limits.');
    const bound = connection;
    const source = await chrome.tabs.get(args.source_tab_id);
    if (connection !== bound || !linkedin(source.url) || profile(source.url)) throw Error('Choose a LinkedIn search tab.');
    connection.source = source.id; connection.pages = args.max_pages;
    connection.allowed = new Set();
    connection.run = args.run_id; nextCount = 0; profileCount = 0; return true;
  }
  if (!connection.run || connection.run !== args.run_id) throw Error('The browser run has stopped or disconnected.');
  if (message.action === 'end') {
    connection.run = null;
    for (const [id, expected] of owned) {
      try { const tab = await chrome.tabs.get(id); if (!tab.active && tab.url === expected) await chrome.tabs.remove(id); } catch {}
    }
    owned.clear(); return true;
  }
  if (message.action === 'create') {
    if (!profile(args.url) || !connection.allowed.has(args.url) || ++profileCount > 75) throw Error('The profile action is outside the run limits.');
    const tab = await chrome.tabs.create({url: args.url, active: false}); owned.set(tab.id, args.url); return tab.id;
  }
  const tab = await chrome.tabs.get(args.tab_id);
  if (connection?.run !== args.run_id) throw Error('The browser run has stopped.');
  if (!linkedin(tab.url)) throw Error('The selected tab left LinkedIn.');
  if (tab.id !== connection.source && !owned.has(tab.id)) throw Error('This tab does not belong to the sourcing run.');
  if (message.action === 'navigate') {
    const search = args.url?.startsWith('https://www.linkedin.com/search/results/people/?');
    if ((!search && !profile(args.url)) || (search && tab.id !== connection.source) ||
        (profile(args.url) && (!owned.has(tab.id) || !connection.allowed.has(args.url)))) throw Error('This navigation is not supported.');
    if (profile(args.url) && ++profileCount > 75) throw Error('The profile limit was reached.');
    await chrome.tabs.update(tab.id, {url: args.url});
    if (owned.has(tab.id)) owned.set(tab.id, args.url);
    return true;
  }
  if (message.action === 'read') {
    if (!['readSearch', 'readProfile', 'search', 'next'].includes(args.method)) throw Error('This browser action is not supported.');
    if (args.method === 'readProfile' ? !owned.has(tab.id) : tab.id !== connection.source) throw Error('This read does not belong to the sourcing run.');
    if (tab.status !== 'complete') return {loading: true};
    if (args.method === 'next' && ++nextCount >= connection.pages) throw Error('The requested page limit was reached.');
    await chrome.scripting.executeScript({target: {tabId: tab.id}, files: ['reader.js']});
    if (connection?.run !== args.run_id) throw Error('The browser run has stopped.');
    const [{result}] = await chrome.scripting.executeScript({target: {tabId: tab.id},
      func: (method, values) => globalThis.SourcerReader[method](...values), args: [args.method, args.values || []]});
    if (args.method === 'readSearch') connection.allowed = new Set((result?.profiles || []).map(row => row.url).filter(profile));
    return result;
  }
  throw Error('Unsupported browser action.');
}
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (message?.kind !== 'sourcer') return false;
  handle(message, sender).then(result => reply({result}), () => reply({error: 'The browser action stopped. Reconnect the companion or check the LinkedIn page.'}));
  return true;
});
