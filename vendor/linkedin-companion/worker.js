// Separate scan state under one authenticated CV Studio document. The existing
// bounded scan implementation below is instantiated once for each module.
const nativeChrome=chrome, sessions=new Map(), tabLeases=new Map(), inFlight=new Map();
let updatePending=false;
function sessionError(message) { const error=Error(message);error.cvstudioSafe=true;return error; }
function otherOwns(scope,id) {
  return tabLeases.has(id) && tabLeases.get(id)!==scope ||
    [...sessions].some(([name,session])=>name!==scope && session.owns(id));
}
function assertSessionTab(scope,id) {
  if(otherOwns(scope,id))throw sessionError('This tab belongs to the other running scan. Choose a different search tab.');
}
function releaseLeases(scope) {
  if(inFlight.get(scope))return;
  for(const [id,name] of tabLeases)if(name===scope && !sessions.get(scope).owns(id))tabLeases.delete(id);
}
function sessionChrome(scope) {
  return {...nativeChrome,tabs:{...nativeChrome.tabs,
    get:async id=>{assertSessionTab(scope,id);return nativeChrome.tabs.get(id);},
    query:async args=>(await nativeChrome.tabs.query(args)).filter(tab=>!otherOwns(scope,tab.id)),
    create:async args=>{const tab=await nativeChrome.tabs.create(args);assertSessionTab(scope,tab.id);tabLeases.set(tab.id,scope);return tab;},
    update:async(id,args)=>{assertSessionTab(scope,id);return nativeChrome.tabs.update(id,args);},
    remove:async id=>{assertSessionTab(scope,id);return nativeChrome.tabs.remove(id);}
  },scripting:{...nativeChrome.scripting,executeScript:async args=>{
    assertSessionTab(scope,args.target.tabId);return nativeChrome.scripting.executeScript(args);
  }}};
}
const migrateSessions=(async()=>{
  const key='cvstudioLinkedinSessionV1',leadKey='cvstudioLinkedinLeadsSessionV1';
  const legacy=(await nativeChrome.storage.session.get(key))[key];
  if(!legacy || legacy.scope!==undefined || !(['hr','jobs'].includes(legacy.connection?.kind) || !legacy.connection?.run && legacy.connection?.jobCompany))return;
  if((await nativeChrome.storage.session.get(leadKey))[leadKey])throw Error('Ambiguous companion sessions.');
  // One atomic write removes old action authority while transferring its exact
  // bounded snapshot. Startup validates it and never resumes browser actions.
  await nativeChrome.storage.session.set({[key]:null,[leadKey]:{...legacy,scope:'leads'}});
})();


function createCompanionSession(scope) {
const chrome = sessionChrome(scope);
let connection = null, owned = new Map(), viewed = new Map(), nextCount = 0, profileCount = 0, jobCapture = null;
const SESSION_KEY = scope === 'profiles' ? 'cvstudioLinkedinSessionV1' : 'cvstudioLinkedinLeadsSessionV1';
const TRUST_KEY = 'cvstudioLinkedinTrustedAppsV1';
// Chrome session memory survives worker suspension, but not browser/extension
// restarts. Never store credentials, captured content or provider requests here.
let stateFailed = false, writes = Promise.resolve(), connections = Promise.resolve(), reloading = false;
function local(value) {
  try { const u = new URL(value); return u.protocol === 'http:' && !u.username && !u.password && ['127.0.0.1', 'localhost'].includes(u.hostname) && u.pathname === '/'; }
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
function companyPeopleRoot(value) {
  try { const u=new URL(value);return u.origin==='https://www.linkedin.com' && !u.username && !u.password && /^\/company\/[A-Za-z0-9_-]+\/people\/?$/.test(u.pathname) ? u.origin+u.pathname.replace(/people\/?$/,'') : ''; } catch { return ''; }
}
function linkedinAccessPage(value) {
  try {const u=new URL(value);return u.origin==='https://www.linkedin.com' && /^\/(?:login|checkpoint|challenge|authwall|uas)(?:\/|$)/i.test(u.pathname);}catch{return false;}
}
function hrWaiting(hr, reason='') {
  const stage=hr.stage==='company'?'company':hr.stage.startsWith('company_')?'company_filter':['search','type','pick','apply','country_wait'].includes(hr.stage)?'country_filter':hr.stage==='search_wait'?'navigation':'results';
  return {loading:true,wait_stage:reason || stage};
}
function jobCompanyEvidence(value) {
  return value && typeof value.job_url==='string' && jobURL(value.job_url)===value.job_url && hrCompanyURL(value.company_url) &&
    typeof value.company==='string' && !!value.company.trim() && value.company.length<=200 && !/[\x00-\x1f\x7f]/.test(value.company) && Number.isFinite(value.at);
}
function hrSearchKey(value) {
  try {
    const url = new URL(value);
    if (!linkedin(value) || url.username || url.password || !/^\/search\/results\/people\/?$/.test(url.pathname)) return '';
    url.pathname = '/search/results/people/'; url.hash = '';
    // Native People pagination adds these two options without changing the
    // selected company, country or keyword text. Keep every actual filter.
    for (const name of ['origin','lipi','trk','sid','skipRedirect','page','spellCorrectionEnabled','prioritizeMessage']) url.searchParams.delete(name);
    url.searchParams.sort(); return url.href;
  } catch { return ''; }
}
function hrCompanyGroup(ids) {
  return Array.isArray(ids) && ids.length>=2 && ids.length<=20 && new Set(ids).size===ids.length && ids.every(id=>typeof id==='string' && /^[0-9]{1,24}$/.test(id));
}
function hrKeywordQueries(keywords, grouped=true) {
  const terms=[...new Map(keywords.split(',').map(word=>word.replaceAll('"','').trim()).filter(Boolean).map(word=>[word.toLocaleLowerCase(),word])).values()];
  const queries=[],size=grouped ? 5 : Math.max(terms.length,1);
  for (let index=0;index<terms.length;index+=size) queries.push(terms.slice(index,index+size).map(word=>'"'+word+'"').join(' OR '));
  return queries;
}
function hrQueries(hr) { return hrKeywordQueries(hr.keywords,hr.query_index !== undefined); }
function hrSignature(hr, signature) { return hrQueries(hr).length > 1 ? hr.query_index+':'+signature : signature; }
async function peopleCountry(bound, run, country) {
  const search=bound.peopleSearch;
  if (!search || typeof country !== 'string' || !country.trim() || country.length > 100 || /[\x00-\x1f\x7f]/.test(country)) throw safeError('Start a new People search with a country in your brief.');
  if (search.country && search.country !== country) throw safeError('The requested country changed. Start a new search.');
  if (Date.now()-search.started > 120000 || search.stage === 'interrupted') throw safeError('The location selection was interrupted. Check LinkedIn and start a new search.');
  search.country=country;
  let confirmedKey='';
  const check=async()=>{
    live(bound,run);const tab=await chrome.tabs.get(bound.source);live(bound,run);
    if (search.stage === 'waiting' && hrSearchKey(tab.url) === search.previous && (!tab.pendingUrl || hrSearchKey(tab.pendingUrl) === search.key)) return false;
    if (search.stage === 'country_wait') {
      const resolved=new URL(tab.url),expected=new URL(search.key),geo=resolved.searchParams.getAll('geoUrn');
      resolved.searchParams.delete('geoUrn');expected.searchParams.delete('geoUrn');
      if (hrSearchKey(resolved.href)!==hrSearchKey(expected.href)) throw safeError('The People search changed during location selection. Start again.');
      if (tab.pendingUrl && hrSearchKey(tab.pendingUrl)!==hrSearchKey(tab.url)) return false;
      const ready=tab.status==='complete' && geo.length===1 && /^\["[0-9]{1,24}"\]$/.test(geo[0]);
      if (ready) confirmedKey=hrSearchKey(tab.url);
      return ready;
    }
    if (hrSearchKey(tab.url)!==search.key || tab.pendingUrl && hrSearchKey(tab.pendingUrl)!==search.key) throw safeError('The People search changed during location selection. Start again.');
    return tab.status==='complete';
  };
  if (!await check()) return {loading:true};
  if (search.stage==='waiting') search.stage='open';
  await jobScript({target:{tabId:bound.source},files:['reader.js']},jobReaderStartError);
  if (!await check()) return {loading:true};
  const stages={open:['hrCountryOpen','type'],type:['hrCountryType','pick'],pick:['hrCountryPick','apply'],apply:['hrCountryApply','country_wait']};
  const step=stages[search.stage],before=search.stage;
  if (step) {
    search.stage='interrupted';await persist();live(bound,run);search.stage=before;
    // A same-document loading wait proves that no click needs replaying.
    if (!await check()) { await persist();return {loading:true}; }
    search.stage='interrupted';
  }
  const [injection]=await jobScript({target:{tabId:bound.source},func:(method,country)=>{
    try { return globalThis.SourcerReader[method](country); } catch { return null; }
  },args:[step?.[0] || 'peopleCountrySelected',country]},jobReaderReadError);
  live(bound,run);
  const result=injection?.result;
  if (typeof result!=='boolean') throw safeError('LinkedIn did not confirm the location action. Check its tab and start again.');
  if (step) { search.stage=result ? step[1] : before;await persist();return {loading:true}; }
  if (!result || !await check()) return {loading:true};
  search.key=confirmedKey || search.key;search.stage='ready';await persist();return true;
}
const HR_LOADING = Symbol('HR pre-action loading');
async function hrScript(bound, run, method, values, companyPage='') {
  live(bound,run);
  if(companyPage && (method!=='readHRCompany' || bound.hr.stage!=='company' || !companyPeopleRoot(companyPage)))throw safeError('The company page changed. Start a new scan.','HR_PAGE_CHANGED');
  const expected = bound.hr.stage === 'company' ? companyPage || bound.hr.company_url+'people/' : bound.hr.key;
  const check = async () => {
    live(bound,run); const tab = await chrome.tabs.get(bound.source);
    if ((bound.hr.stage === 'company' ? tab.url !== expected : hrSearchKey(tab.url) !== expected) || tab.pendingUrl && tab.pendingUrl !== expected && hrSearchKey(tab.pendingUrl) !== expected) throw safeError('The HR search changed. Start again from the saved ad.','HR_PAGE_CHANGED');
    return tab.status === 'complete';
  };
  if (!await check()) return HR_LOADING;
  await jobScript({target:{tabId:bound.source},files:['reader.js']},jobReaderStartError);
  if (!await check()) return HR_LOADING;
  const [injection] = await jobScript({target:{tabId:bound.source},func:(method,values)=>{
    try { return globalThis.SourcerReader[method](...values); }
    catch(error) { return {hrError:error.cvstudioHRIdentity?'identity':/sign in|verification|restriction/i.test(String(error?.message)) ? 'access' : 'layout'}; }
  },args:[method,values]},jobReaderReadError);
  live(bound,run);
  if (injection?.result?.hrError) {
    if(injection.result.hrError==='identity')throw safeError('The saved company link now points to a different LinkedIn company. Check the ad before scanning.','HR_COMPANY_MISMATCH');
    const errors={
      readHRCompany:'The company page could not be matched to the saved ad. Check its company name and LinkedIn company page.',
      hrCompanyOpen:'The LinkedIn Current companies filter could not be opened. Check the company search tab.',
      hrCompanyOnly:'The exact saved-ad company could not be selected from LinkedIn\'s grouped company filter. Check the company name and search tab.',
      hrCompanyApply:'The exact company selection could not be applied. Check the LinkedIn company filter.',
      hrCountryOpen:'The LinkedIn location filter could not be opened. Check the HR search tab and start again.',
      hrCountryType:'The LinkedIn location filter could not receive the country. Check the HR search tab and start again.',
      hrCountryPick:'The country suggestion could not be selected. Check the LinkedIn location filter and start again.',
      hrCountryApply:'The selected country could not be applied. Check the LinkedIn location filter and start again.',
      readHRSearch:'The HR results layout could not be read. Refresh the LinkedIn HR search tab and start again.',
      nextHRSearch:'The HR results changed before the next-page click. Start again from the saved ad.'
    };
    throw safeError(injection.result.hrError === 'access' ? 'LinkedIn needs sign-in or is showing a restriction. Resolve it in the search tab before trying again.' : errors[method] || 'The HR page could not be read. Check the LinkedIn search tab and start again.',injection.result.hrError==='access'?'HR_ACCESS_REQUIRED':'HR_LAYOUT_UNCONFIRMED');
  }
  return injection?.result;
}
async function hrMutation(bound, run, method, values, nextStage) {
  const before = bound.hr.stage;
  // Persist before clicks/navigation. Suspension during a mutation stops visibly;
  // it never repeats a possibly completed browser action.
  bound.hr.stage = 'interrupted'; await persist(); live(bound,run);
  const result = await hrScript(bound,run,method,values);
  // This sentinel is produced only before invoking the reader action. Unlike
  // a missing/invalid action result, it proves that no click needs replaying.
  if (result === HR_LOADING) { bound.hr.stage=before; await persist(); return HR_LOADING; }
  if (typeof result !== 'boolean') throw safeError('The HR browser action was interrupted. Start a new scan.');
  bound.hr.stage = result ? nextStage : before; await persist(); return result;
}
function jobSearchLive(bound, run, tab) {
  live(bound, run);
  if (bound.kind !== 'jobs' || Date.now() - bound.jobStarted > 600000 ||
      jobSearchKey(tab.url) !== bound.jobKey || tab.pendingUrl && jobSearchKey(tab.pendingUrl) !== bound.jobKey) throw safeError('The job search changed or timed out. Choose the job search already open in Chrome to review its current results.');
}
function safeError(message, code='') { const error = Error(message); error.cvstudioSafe = true;error.cvstudioCode=code;return error; }
function publicError(error) {
  const safe=error?.cvstudioSafe===true;
  return {error:safe && typeof error.message==='string'?error.message:'The browser action stopped. Reconnect the companion or check the LinkedIn page.',
    ...(safe && /^HR_[A-Z_]{1,50}$/.test(error.cvstudioCode || '')?{error_code:error.cvstudioCode}:{}),
    ...(safe && hrCompanyURL(error.companyURL)?{company_url:error.companyURL}:{}),...(error?.cvstudioLoading?{loading:true}:{})};
}
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
  const snapshot = {version:1, scope, connection:connection ? {...connection, allowed:[...(connection.allowed || [])]} : null,
    owned:[...owned], viewed:[...viewed], nextCount:Math.min(nextCount,15), profileCount:Math.min(profileCount,76)};
  const write = writes.catch(() => {}).then(() => {
    if (stateFailed) throw Error('Companion session storage is unavailable.');
    return chrome.storage.session.set({[SESSION_KEY]:snapshot});
  });
  writes = write;
  return write.catch(error => { stateFailed = true; connection = null; throw error; });
}
async function restore() {
  await migrateSessions;
  await chrome.storage.local.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'});
  const saved = (await chrome.storage.session.get(SESSION_KEY))[SESSION_KEY];
  if (!saved) return;
  if (saved.scope !== undefined && saved.scope !== scope || saved.version !== 1 || !Array.isArray(saved.owned) || saved.owned.length > 76 ||
      !Number.isInteger(saved.nextCount) || saved.nextCount < 0 || saved.nextCount > 15 ||
      !Number.isInteger(saved.profileCount) || saved.profileCount < 0 || saved.profileCount > 76) throw Error('Invalid companion session.');
  for (const row of saved.owned) {
    if (!Array.isArray(row) || row.length !== 2 || !Number.isInteger(row[0]) || row[0] < 0 || owned.has(row[0]) || typeof row[1] !== 'string' || !row[1] || row[1].length > 2048 || !(profile(row[1]) || jobURL(row[1]) === row[1])) throw Error('Invalid owned tab.');
    owned.set(row[0], row[1]);
  }
  const protectedTabs=saved.viewed === undefined ? [] : saved.viewed;
  if (!Array.isArray(protectedTabs) || saved.owned.length+protectedTabs.length>76) throw Error('Invalid viewed tabs.');
  for (const row of protectedTabs) {
    if (!Array.isArray(row) || row.length!==2 || !Number.isInteger(row[0]) || row[0]<0 || owned.has(row[0]) || viewed.has(row[0]) || typeof row[1]!=='string' || !row[1] || row[1].length>2048 || !(profile(row[1]) || jobURL(row[1])===row[1])) throw Error('Invalid viewed tab.');
    viewed.set(row[0],row[1]);
  }
  const bound = saved.connection;
  if (!bound) return;
  if (scope === 'profiles' && ['hr','jobs'].includes(bound.kind) || scope === 'leads' && bound.run && !['hr','jobs'].includes(bound.kind)) throw Error('Invalid session scope.');
  if (bound.jobCompany!==undefined && !jobCompanyEvidence(bound.jobCompany)) throw Error('Invalid job company evidence.');
  if (!Number.isInteger(bound.tabId) || bound.tabId < 0 || typeof bound.documentId !== 'string' || !bound.documentId || !local(bound.url) ||
      !Array.isArray(bound.allowed) || bound.allowed.length > 40 || bound.allowed.some(url => !profile(url)) || bound.kind && !['profiles','jobs','hr'].includes(bound.kind) ||
      bound.run && (!/^[a-f0-9]{32}$/.test(bound.run) || !Number.isInteger(bound.source) || bound.source < 0 || !Number.isInteger(bound.pages) || bound.pages < 1 || bound.pages > 15) ||
      bound.kind === 'jobs' && (!jobSearchKey(bound.jobKey) || !Number.isFinite(bound.jobStarted) || !Number.isInteger(bound.jobScrolls) || bound.jobScrolls < 0 || bound.jobScrolls > 120 ||
        bound.jobInitial && (bound.jobInitial !== true || typeof bound.jobLocation !== 'string' || bound.jobLocation.length > 160)) ||
      bound.kind === 'hr' && (!bound.hr || !hrCompanyURL(bound.hr.company_url) || typeof bound.hr.company !== 'string' || bound.hr.company.length > 200 || typeof bound.hr.country !== 'string' || bound.hr.country.length > 100 ||
        typeof bound.hr.keywords !== 'string' || bound.hr.keywords.length > 600 || !Number.isFinite(bound.hr.started) || !['company','search_wait','company_open','company_only','company_apply','company_wait','search','type','pick','apply','country_wait','ready','interrupted'].includes(bound.hr.stage) ||
        bound.hr.job_url!==undefined && (typeof bound.hr.job_url!=='string' || jobURL(bound.hr.job_url)!==bound.hr.job_url) ||
        bound.hr.expected_company_id!==undefined && (typeof bound.hr.expected_company_id!=='string' || !/^[0-9]{1,24}$/.test(bound.hr.expected_company_id) || bound.hr.job_url!==undefined) ||
        bound.hr.company_group !== undefined && (!hrCompanyGroup(bound.hr.company_group) || bound.hr.company_id ||
          !['search_wait','company_open','company_only','company_apply','company_wait','interrupted'].includes(bound.hr.stage) ||
          !bound.hr.key || new URL(bound.hr.key).searchParams.get('currentCompany')!==JSON.stringify(bound.hr.company_group)) ||
        bound.hr.query_index !== undefined && (!Number.isInteger(bound.hr.query_index) || bound.hr.query_index < 0 || bound.hr.query_index >= hrQueries(bound.hr).length ||
          bound.hr.key && new URL(bound.hr.key).searchParams.get('keywords') !== hrQueries(bound.hr)[bound.hr.query_index]) ||
        bound.hr.omitted_pages !== undefined && typeof bound.hr.omitted_pages !== 'boolean' ||
        bound.hr.company_blank_polls !== undefined && (!Number.isInteger(bound.hr.company_blank_polls) || bound.hr.company_blank_polls<1 || bound.hr.company_blank_polls>12) ||
        bound.hr.company_blank_reloads !== undefined && bound.hr.company_blank_reloads!==1 ||
        bound.hr.joined_count !== undefined && (!Number.isInteger(bound.hr.joined_count) || bound.hr.joined_count < 0 || bound.hr.joined_count > 100) ||
        bound.hr.joining && (!/^https:\/\/www\.linkedin\.com\/in\/[A-Za-z0-9_%~-]+$/.test(bound.hr.joining.url || '') || bound.hr.joining.tab_id !== null && !Number.isInteger(bound.hr.joining.tab_id) ||
          bound.hr.joining.scrolls !== undefined && (!Number.isInteger(bound.hr.joining.scrolls) || bound.hr.joining.scrolls < 0 || bound.hr.joining.scrolls > 4)) ||
        bound.hr.stage !== 'company' && ((!/^[0-9]{1,24}$/.test(bound.hr.company_id || '') && !hrCompanyGroup(bound.hr.company_group)) || !bound.hr.key) ||
        bound.hr.key && (bound.hr.key.length > 2048 || hrSearchKey(bound.hr.key) !== bound.hr.key))) throw Error('Invalid binding.');
  if (bound.peopleSearch && (bound.kind !== 'profiles' || typeof bound.peopleSearch.key !== 'string' || bound.peopleSearch.key.length > 10000 || hrSearchKey(bound.peopleSearch.key) !== bound.peopleSearch.key ||
      typeof bound.peopleSearch.previous !== 'string' || bound.peopleSearch.previous.length > 10000 || bound.peopleSearch.previous && hrSearchKey(bound.peopleSearch.previous) !== bound.peopleSearch.previous ||
      typeof bound.peopleSearch.country !== 'string' || bound.peopleSearch.country.length > 100 || /[\x00-\x1f\x7f]/.test(bound.peopleSearch.country) || !Number.isFinite(bound.peopleSearch.started) ||
      !['waiting','open','type','pick','apply','country_wait','ready','interrupted'].includes(bound.peopleSearch.stage))) throw Error('Invalid People location binding.');
  try {
    // Restore authority only for the exact still-live app document. Startup
    // verifies state; it never resumes browser actions or paid operations.
    const tab = await chrome.tabs.get(bound.tabId);
    if (!local(tab.url) || new URL(tab.url).origin !== new URL(bound.url).origin || tab.status === 'loading') throw Error('App document changed.');
    const [probe] = await chrome.scripting.executeScript({target:{tabId:bound.tabId, documentIds:[bound.documentId]},
      func:() => !!document.getElementById('viewLinkedinSourcer') && !!document.getElementById('tabLinkedinSourcer')});
    if (!probe?.result || probe.documentId !== bound.documentId) throw Error('App document changed.');
    await authenticateApp(tab,bound.documentId);
    const current=await chrome.tabs.get(bound.tabId);
    if (current.url!==tab.url || current.status!=='complete' || current.pendingUrl) throw Error('App document changed.');
    const [confirmed]=await chrome.scripting.executeScript({target:{tabId:bound.tabId,documentIds:[bound.documentId]},
      func:()=>!!document.getElementById('viewLinkedinSourcer') && !!document.getElementById('tabLinkedinSourcer')});
    if (!confirmed?.result || confirmed.documentId!==bound.documentId) throw Error('App document changed.');
    connection = {tabId:bound.tabId, documentId:bound.documentId, url:bound.url, run:bound.run || null,
      source:bound.source, pages:bound.pages, allowed:new Set(bound.allowed), kind:bound.kind || 'profiles'};
    if (bound.kind === 'jobs') Object.assign(connection, {jobKey:bound.jobKey, jobStarted:bound.jobStarted, jobScrolls:bound.jobScrolls,jobInitial:bound.jobInitial === true,jobLocation:bound.jobLocation || ''});
    if (bound.kind === 'hr') connection.hr = {...bound.hr};
    if (bound.jobCompany && Date.now()-bound.jobCompany.at>=0 && Date.now()-bound.jobCompany.at<=120000) connection.jobCompany={...bound.jobCompany};
    if (bound.peopleSearch) connection.peopleSearch = {...bound.peopleSearch};
    nextCount = saved.nextCount; profileCount = saved.profileCount;
  } catch {
    connection = null;
    if (bound.kind === 'hr') await closeHROwnedTabs();
    await persist();
  }
}
const ready = restore().catch(() => { stateFailed = true; connection = null; owned.clear(); viewed.clear(); });
function event(change) {
  return ready.then(async () => { if (await change()) await persist(); }).catch(() => { stateFailed = true; connection = null; });
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
  // Viewing retains exact-page read authority, but permanently removes automatic
  // navigation/closure authority. Actual URL changes still relinquish both.
  const expected = owned.get(id) || viewed.get(id), tab = await chrome.tabs.get(id);
  if (!expected || (owned.get(id) || viewed.get(id)) !== expected || !sameOwnedPage(tab.url, expected) && !expectedLoading(tab, expected) || tab.pendingUrl && !sameOwnedPage(tab.pendingUrl, expected)) {
    if (owned.has(id) || viewed.has(id)) { owned.delete(id); viewed.delete(id); await persist(); }
    throw safeError('The scan profile tab was changed or closed. Your candidate list is kept. Browse in another tab and start again.');
  }
  if (tab.active && protectViewed(id)) await persist();
  return tab;
}
function protectViewed(id) {
  if (!owned.has(id)) return false;
  viewed.set(id,owned.get(id));owned.delete(id);return true;
}
async function closeOwned(id, expected) {
  try {
    const tab = await chrome.tabs.get(id);
    if (owned.get(id) === expected && !tab.active && (sameOwnedPage(tab.url, expected) || expectedLoading(tab, expected)) && (!tab.pendingUrl || sameOwnedPage(tab.pendingUrl, expected))) await chrome.tabs.remove(id);
  } catch {}
  if (owned.get(id) === expected) owned.delete(id);
  if (viewed.get(id) === expected) viewed.delete(id);
}
async function closeHROwnedTabs() {
  // The app may already be gone before its pagehide message can arrive. Exact
  // ownership/current-or-pending URL checks still protect user-taken-over tabs.
  for (const [id, expected] of [...owned,...viewed]) await closeOwned(id,expected);
}
async function authenticateApp(tab, documentId, pair=false) {
  await chrome.storage.local.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'});
  const origin=new URL(tab.url).origin;
  const saved=(await chrome.storage.local.get(TRUST_KEY))[TRUST_KEY];
  const trusted=saved && typeof saved==='object' && !Array.isArray(saved) ? saved : {};
  let key=trusted[origin];
  if (!pair && !/^[a-f0-9]{64}$/.test(key || '')) throw safeError('Connect this CV Studio installation once: click the companion toolbar icon in its tab.');
  const nonce=Array.from(crypto.getRandomValues(new Uint8Array(32)),value=>value.toString(16).padStart(2,'0')).join('');
  const [probe]=await chrome.scripting.executeScript({target:{tabId:tab.id,documentIds:[documentId]},
    func:async function companionProof(nonce,pair) {
      if (!document.getElementById('viewLinkedinSourcer') || !document.getElementById('tabLinkedinSourcer')) return null;
      const response=await fetch('/linkedin-sourcer?action='+(pair?'companion_pair':'companion_challenge')+'&nonce='+nonce,
        {credentials:'same-origin',cache:'no-store',redirect:'error',signal:AbortSignal.timeout(5000)});
      return response.ok ? response.json() : null;
    },args:[nonce,pair]});
  if (pair) key=probe?.result?.key;
  if (probe?.documentId !== documentId || !/^[a-f0-9]{64}$/.test(key || '') || !/^[a-f0-9]{64}$/.test(probe?.result?.proof || '')) throw safeError('CV Studio could not be verified. Update it, refresh its tab and click the companion toolbar icon.');
  const bytes=value=>Uint8Array.from(value.match(/../g),part=>parseInt(part,16));
  const signing=await crypto.subtle.importKey('raw',bytes(key),{name:'HMAC',hash:'SHA-256'},false,['verify']);
  if (!await crypto.subtle.verify('HMAC',signing,bytes(probe.result.proof),new TextEncoder().encode('CVStudio companion v1|'+origin+'|'+nonce))) throw safeError('This CV Studio installation changed. Open the intended app and click the companion toolbar icon to trust it again.');
  return {origin,key,trusted};
}
function connectApp(sender, pair=false) {
  const connect = async () => {
    if (stateFailed || reloading || sender.id !== chrome.runtime.id || sender.frameId !== 0 || !sender.documentId || !local(sender.url)) throw safeError('Open CV Studio in this browser to connect the companion.');
    const tab = await chrome.tabs.get(sender.tab?.id);
    if (tab.status !== 'complete' || tab.pendingUrl || tab.url !== sender.url) {
      const error=safeError('Wait for CV Studio to finish loading.');
      error.cvstudioLoading=tab.status === 'loading' && (!tab.pendingUrl || tab.pendingUrl === sender.url) && tab.url === sender.url;
      throw error;
    }
    if (!pair && connection?.tabId === tab.id && connection.documentId === sender.documentId) return;
    const previous = connection;
    if (previous?.run || jobCapture || previous && !tab.active) throw safeError('Finish the companion action in the other CV Studio tab first.');
    const [probe] = await chrome.scripting.executeScript({target:{tabId:tab.id,documentIds:[sender.documentId]},
      func:()=>!!document.getElementById('viewLinkedinSourcer') && !!document.getElementById('tabLinkedinSourcer')});
    if (!probe?.result || probe.documentId !== sender.documentId) throw safeError('This page is not CV Studio.');
    const identity=await authenticateApp(tab,sender.documentId,pair);
    if (connection !== previous || previous?.run || jobCapture) throw safeError('The companion is busy. Try again after it finishes.');
    // A new binding grants no old run authority. Automatic connection never
    // starts searches, repeats browser mutations or confirms provider spending.
    connection = null;
    for (const [id, expected] of [...owned,...viewed]) await closeOwned(id,expected);
    const current=await chrome.tabs.get(tab.id);
    if (connection || current.status !== 'complete' || current.pendingUrl || current.url !== sender.url) throw safeError('CV Studio changed while connecting. Refresh its tab.');
    const [confirmed]=await chrome.scripting.executeScript({target:{tabId:tab.id,documentIds:[sender.documentId]},
      func:()=>!!document.getElementById('viewLinkedinSourcer') && !!document.getElementById('tabLinkedinSourcer')});
    if (connection || !confirmed?.result || confirmed.documentId !== sender.documentId) throw safeError('CV Studio changed while connecting. Refresh its tab.');
    if (pair) {
      const entries=Object.entries(identity.trusted).filter(([origin,key])=>origin!==identity.origin && /^[a-f0-9]{64}$/.test(key)).slice(-7);
      await chrome.storage.local.set({[TRUST_KEY]:Object.fromEntries([...entries,[identity.origin,identity.key]])});
      const latest=await chrome.tabs.get(tab.id);
      const [document]=await chrome.scripting.executeScript({target:{tabId:tab.id,documentIds:[sender.documentId]},
        func:()=>!!document.getElementById('viewLinkedinSourcer') && !!document.getElementById('tabLinkedinSourcer')});
      if (connection || latest.status!=='complete' || latest.pendingUrl || latest.url!==sender.url || !document?.result || document.documentId!==sender.documentId) throw safeError('CV Studio changed while connecting. Refresh its tab.');
    }
    connection = {tabId:tab.id,documentId:sender.documentId,url:tab.url,allowed:new Set()};
    nextCount=0;profileCount=0;
    await persist();await chrome.action.setBadgeText({text:'ON'});
  };
  const result=connections.catch(()=>{}).then(connect);
  connections=result;return result;
}
async function pair(tab) {
  try {
    await ready; await writes.catch(() => {});
    if (!local(tab.url)) { await chrome.action.setBadgeText({text: connection ? 'ON' : ''}); return; }
    const [{result, documentId}] = await chrome.scripting.executeScript({target: {tabId: tab.id},
      func: () => !!document.getElementById('viewLinkedinSourcer') && !!document.getElementById('tabLinkedinSourcer')});
    if (!result || !documentId) { await chrome.action.setBadgeText({text: 'APP'}); return; }
    if (connection?.run || jobCapture) { await chrome.action.setBadgeText({text:'ON'}); return; }
    stateFailed = false;
    await connectApp({id:chrome.runtime.id,tab,frameId:0,documentId,url:tab.url},true);
  } catch { await chrome.action.setBadgeText({text:'APP'}); }
}
function removed(id) { return event(async () => {
  const appRemoved=connection?.tabId === id, hrRemoved=appRemoved && connection.kind === 'hr';
  const changed=appRemoved || owned.has(id) || viewed.has(id);
  if (appRemoved) connection=null;
  owned.delete(id);
  viewed.delete(id);
  if (hrRemoved) await closeHROwnedTabs();
  return changed;
}); }
function updated(id,change) { return event(async () => {
  let changed = false;
  if (id === connection?.tabId && change.status === 'loading') {
    const wasHR=connection.kind === 'hr'; connection = null; changed = true;
    if (wasHR) await closeHROwnedTabs();
  }
  if ((owned.has(id) || viewed.has(id)) && change.url && !sameOwnedPage(change.url,owned.get(id) || viewed.get(id))) { owned.delete(id); viewed.delete(id); changed = true; }
  if (change.status === 'complete') {
    try {
      const tab=await chrome.tabs.get(id);
      if (local(tab.url) && tab.status === 'complete' && !tab.pendingUrl) {
        // document_idle can precede tab completion. Ask the current top-level
        // content script to retry its own verified handshake, never an action.
        await chrome.tabs.sendMessage(id,{type:'CVSTUDIO_COMPANION_READY'},{frameId:0});
      }
    } catch { /* A closed/replaced document will connect on its next load. */ }
  }
  return changed;
}); }
function activated(info) { return event(() => protectViewed(info.tabId)); }
async function readJobTab(bound, id, expected, companyOnly=false) {
  const verify = tab => {
    if(jobCapture?.cancelled)throw safeError('The job company read was stopped.','HR_STOPPED');
    if(linkedinAccessPage(tab.url) || linkedinAccessPage(tab.pendingUrl))throw safeError('LinkedIn needs sign-in or a verification check. Resolve it in its browser tab before scanning again.','HR_ACCESS_REQUIRED');
    if (connection !== bound || bound.run || jobURL(tab.url) !== expected || tab.pendingUrl && jobURL(tab.pendingUrl) !== expected) throw safeError('The selected job changed. Open its LinkedIn tab and try again.');
    return tab.status==='complete';
  };
  let injected=false, previousCompany='',hadCompany=false;
  // A complete browser load can precede LinkedIn's React detail panel. Wait on
  // that same DOM briefly; never re-navigate or replay a failed network request.
  const limit=companyOnly?48:16;
  for (let attempt=0;attempt<limit;attempt++) {
    if (!verify(await chrome.tabs.get(id))) { injected=false;previousCompany='';if(attempt+1<limit)await new Promise(resolve=>setTimeout(resolve,350));continue; }
    if (!injected) { await jobScript({target:{tabId:id}, files:['reader.js']},jobReaderStartError);injected=true; }
    if (!verify(await chrome.tabs.get(id))) { injected=false;previousCompany='';if(attempt+1<limit)await new Promise(resolve=>setTimeout(resolve,350));continue; }
    const [injection] = await jobScript({target:{tabId:id},
      func: (url,companyOnly) => {
        try { return globalThis.SourcerReader.readJob(url,companyOnly); }
        catch (error) {
          if (error.cvstudioJobLoading) return {loading:true,unavailable:globalThis.SourcerReader.jobUnavailable()};
          return {jobError:/sign in|verification|restriction/i.test(String(error?.message))?'access':'layout'};
        }
      }, args:[expected,companyOnly]},jobReaderReadError);
    const result=injection?.result;
    if (!verify(await chrome.tabs.get(id))) { injected=false;previousCompany='';if(attempt+1<limit)await new Promise(resolve=>setTimeout(resolve,350));continue; }
    if(result?.unavailable)throw safeError('LinkedIn says this job ad is unavailable. Its previous saved details were kept.','HR_AD_UNAVAILABLE');
    if (result?.jobError) throw safeError(result.jobError==='access' ? 'LinkedIn needs sign-in or is showing a verification or usage restriction. Check the LinkedIn tab before trying again.' : jobReaderReadError,result.jobError==='access'?'HR_ACCESS_REQUIRED':'HR_AD_LAYOUT');
    if (!result?.loading) {
      if (result?.url !== expected) throw safeError('The selected job could not be confirmed. Open its LinkedIn tab and try again.');
      if (companyOnly) {
        if(typeof result.company==='string' && result.company.trim())hadCompany=true;
        const evidence={job_url:expected,company_url:result.company_url,company:result.company,at:Date.now()};
        if (jobCompanyEvidence(evidence)) {
          const signature=JSON.stringify([evidence.company_url,evidence.company,result.role]);
          if (signature===previousCompany) { bound.jobCompany=evidence;await persist();return result; }
          previousCompany=signature;
        } else previousCompany='';
      } else if (result.description || attempt >= 5) return result;
    } else previousCompany='';
    // A same-URL reload may finish between polls. Reinject into the current
    // document before the next passive read instead of trusting the old world.
    injected=false;
    if (attempt+1 < limit) await new Promise(resolve => setTimeout(resolve,350));
  }
  if(companyOnly && hadCompany)throw safeError('The ad loaded, but LinkedIn did not provide a single employer link. Open the ad or set its confirmed company page in Search options.','HR_EMPLOYER_LINK_MISSING');
  throw safeError('The job header did not finish loading or its layout is not recognized. Open the ad in Chrome or Brave and try again.','HR_AD_TIMEOUT');
}
async function pickJob(message, sender) {
  await ready;
  const bound = connection, expected = jobURL(message.url), operation = message.operation === undefined ? 'add' : message.operation;
  if (!['add','remove','folders','create_folder'].includes(operation) || message.folder !== undefined &&
      (typeof message.folder !== 'string' || message.folder.length > 80 || /[\x00-\x1f]/.test(message.folder))) throw safeError('Choose a valid folder or job-ad action.');
  if (operation === 'create_folder' && (typeof message.folder !== 'string' || !message.folder.trim())) throw safeError('Enter a folder name.');
  if (stateFailed || !bound) throw safeError('Open Job Leads in CV Studio in this browser. The companion connects automatically.');
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
  if (message.action === 'connect') {
    await connectApp(sender);
    return {connected:true,version:chrome.runtime.getManifest().version};
  }
  if (stateFailed || !connection || sender.tab?.id !== connection.tabId || sender.documentId !== connection.documentId || !local(sender.url)) {
    throw Error('In Chrome, open CV Studio and click the companion toolbar icon to connect this tab.');
  }
  const args = message.args || {};
  if (reloading && message.action !== 'jobStatus') throw safeError('The companion is updating. Refresh CV Studio and LinkedIn when ready.');
  if (message.action === 'reloadCompanion') {
    if (connection.run || jobCapture || owned.size) throw safeError('Finish or stop the current companion action before updating.');
    if (!/^\d+\.\d+\.\d+$/.test(args.version || '')) throw safeError('Refresh CV Studio and try the companion update again.');
    const bound=connection;
    const response=await fetch(chrome.runtime.getURL('manifest.json'),{cache:'no-store'});
    const installed=await response.json();
    if (!response.ok || installed.manifest_version !== 3 || installed.name !== 'CV Studio LinkedIn Companion' || installed.version !== args.version) throw safeError('Use Set up companion once and select the CV Studio folder. This downloaded copy is not updated with the app.');
    live(bound);
    if (bound.run || jobCapture || owned.size) throw safeError('Finish or stop the current companion action before updating.');
    if (chrome.runtime.getManifest().version === args.version) return {current:true};
    if (!reloading) { reloading=true;setTimeout(()=>chrome.runtime.reload(),100); }
    return {reloading:true};
  }
  if(message.action==='jobReadCancel') {
    if(typeof args.operation_id!=='string' || !/^[a-f0-9]{32}$/.test(args.operation_id))throw safeError('Choose the active job company read.','HR_PAGE_CHANGED');
    if(jobCapture?.bound!==connection || jobCapture.operation!==args.operation_id)return false;
    jobCapture.cancelled=true;return true;
  }
  if (message.action === 'jobStatus') return {connected:true,job_read:true,job_search:true,job_search_revision:1,company_hr_revision:1,hr_company_identity_revision:1,hr_company_filter_revision:1,hr_company_source_revision:1,hr_resilience_revision:1,hr_layout_revision:1,hr_apply_transition_revision:1,hr_joined_revision:1,hr_joined_loading_revision:1,hr_employment_revision:1,hr_date_check_revision:1,hr_keyword_revision:1,people_country_revision:1,people_results_revision:1,profile_browsing_revision:1,concurrent_scans_revision:1,companion_update_revision:1,version:chrome.runtime.getManifest().version,busy:!!connection.run || !!jobCapture};
  if (message.action === 'hrDate') {
    const bound=connection;
    if(bound.run || jobCapture) throw safeError('Wait for the current HR action to finish before checking employment.');
    if(!/^https:\/\/www\.linkedin\.com\/in\/[A-Za-z0-9_%~-]+$/.test(args.url || '') ||
        !/^https:\/\/www\.linkedin\.com\/company\/[A-Za-z0-9_-]+\/$/.test(args.company_url || '') ||
        !/^[0-9]{1,24}$/.test(args.company_id || '') || !/^[a-f0-9]{32}$/.test(args.operation_id || '')) throw safeError('Choose a saved HR person and company.');
    const token={bound,operation:args.operation_id};jobCapture=token;let created=null,scrolls=0,metadata=0,committed=false;
    try {
      await closeHROwnedTabs();live(bound);
      const tab=await chrome.tabs.create({url:args.url,active:false});created=tab.id;owned.set(created,args.url);await persist();
      for(let attempt=0;attempt<100;attempt++) {
        live(bound);if(token.cancelled || bound.run)throw safeError('The employment check stopped. Saved dates were kept.');
        const opening=await chrome.tabs.get(created);live(bound);
        if(!committed && opening.status==='loading' && (!opening.url || opening.url==='about:blank') && (!opening.pendingUrl || sameOwnedPage(opening.pendingUrl,args.url))) {
          await new Promise(resolve=>setTimeout(resolve,500));continue;
        }
        const current=await ownedTab(created);live(bound);committed=true;
        if(current.status==='complete') {
          await jobScript({target:{tabId:created},files:['reader.js']},jobReaderStartError);
          await ownedTab(created);live(bound);if(token.cancelled)throw safeError('The employment check stopped. Saved dates were kept.');
          const [read]=await jobScript({target:{tabId:created},func:values=>{
            try{return globalThis.SourcerReader.readHRJoined(...values);}
            catch{return {hrError:true};}
          },args:[[args.url,args.company_url,args.company_id]]},'The employment dates could not be read.');
          await ownedTab(created);live(bound);if(token.cancelled)throw safeError('The employment check stopped. Saved dates were kept.');
          const value=read?.result;
          if(value?.hrError)throw safeError('LinkedIn needs sign-in, or the profile could not be confirmed. Saved dates were kept.');
          if(value && !value.loading) {
            const {joined,left,current}=value;
            const date=s=>typeof s==='string' && /^(?:(?:19|20)\d{2}(?:-(?:0[1-9]|1[0-2]))?)?$/.test(s);
            if(!date(joined) || !date(left) || ![true,false,null].includes(current) ||
                current===true && (!joined || left) || current===false && (!joined || !left) || current===null && (joined || left) ||
                left && (joined.length===4?joined+'-01':joined)>(left.length===4?left+'-12':left))throw safeError('The employment dates could not be confirmed.');
            return {url:args.url,joined,left,current};
          }
          if(++metadata>=40)break;
          if(scrolls<8 && !viewed.has(created)) {
            scrolls++;await jobScript({target:{tabId:created},func:url=>document.visibilityState==='visible'?false:globalThis.SourcerReader.prepareHRJoined(url),args:[args.url]},'The Experience section could not be loaded.');
          }
        }
        await new Promise(resolve=>setTimeout(resolve,500));
      }
      throw safeError('LinkedIn did not finish loading Experience. Saved dates were kept; try Check employment again.');
    } finally {
      if(created!==null)await closeOwned(created,args.url);
      if(jobCapture===token)jobCapture=null;await persist();
    }
  }
  if (message.action === 'hrBegin') {
    const bound = connection;
    if (!/^[a-f0-9]{32}$/.test(args.run_id || '') || !hrCompanyURL(args.company_url) || typeof args.company !== 'string' || !args.company.trim() || args.company.length > 200 ||
      typeof args.country !== 'string' || args.country.length > 100 || typeof args.keywords !== 'string' || args.keywords.length > 600 || !hrKeywordQueries(args.keywords).length || /[\x00-\x1f]/.test(args.company+args.country+args.keywords) ||
      !Number.isInteger(args.max_pages) || args.max_pages < 1 || args.max_pages > 15) throw safeError('Choose a LinkedIn company page, country and 1 to 15 pages.');
    if(args.expected_company_id!==undefined && (typeof args.expected_company_id!=='string' || !/^[0-9]{1,24}$/.test(args.expected_company_id) || args.job_url!==undefined))throw safeError('The previously saved company identity is invalid.','HR_COMPANY_MISMATCH');
    if (bound.run === args.run_id && bound.kind === 'hr') return {tab_id:bound.source};
    if (bound.run || jobCapture) throw safeError('Finish the current companion search first.');
    if (args.job_url!==undefined && (!jobCompanyEvidence(bound.jobCompany) || bound.jobCompany.job_url!==args.job_url ||
        bound.jobCompany.company_url!==args.company_url || bound.jobCompany.company!==args.company.trim() || Date.now()-bound.jobCompany.at<0 || Date.now()-bound.jobCompany.at>120000)) throw safeError('Read the job ad company again before starting this scan. Its exact employer link was not confirmed.');
    const token = {}; jobCapture = token;
    try {
      const tab = await chrome.tabs.create({url:args.company_url+'people/',active:false}); live(bound);
      Object.assign(bound,{kind:'hr',run:args.run_id,source:tab.id,pages:args.max_pages,allowed:new Set(),
        hr:{company_url:args.company_url,company:args.company.trim(),...(args.job_url!==undefined?{job_url:args.job_url}:{}),...(args.expected_company_id!==undefined?{expected_company_id:args.expected_company_id}:{}),country:args.country.trim(),keywords:args.keywords.trim(),query_index:0,stage:'company',key:'',started:Date.now(),joined_count:0}});
      delete bound.jobCompany;
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
    if(args.operation_id!==undefined && (typeof args.operation_id!=='string' || !/^[a-f0-9]{32}$/.test(args.operation_id)))throw safeError('The job read identifier is invalid.','HR_PAGE_CHANGED');
    const token = {bound,operation:args.operation_id}; jobCapture = token;
    let created = null;
    try {
      if (message.action === 'jobRead') return await readJobTab(bound, args.tab_id, expected);
      // Only a canonical job URL explicitly submitted by the bound app may be
      // opened. Never navigate or close any pre-existing user tab.
      if (args.url !== expected) throw Error('Use a canonical LinkedIn job link.');
      delete bound.jobCompany;
      for (const [id, value] of [...owned,...viewed]) if (jobURL(value)) await closeOwned(id, value);
      await persist();
      const tabs = await chrome.tabs.query({url:'https://www.linkedin.com/*'});
      if (connection !== bound || bound.run) throw Error('The companion connection changed.');
      let tab = tabs.find(value => jobURL(value.url) === expected && value.status === 'complete') || tabs.find(value => jobURL(value.url) === expected);
      if (!tab) { tab = await chrome.tabs.create({url:expected, active:false}); created = tab.id; owned.set(created, expected); await persist(); }
      for (let attempt = 0; attempt < 40; attempt++) {
        if(token.cancelled)throw safeError('The job company read was stopped.','HR_STOPPED');
        if (connection !== bound || bound.run) throw Error('The companion connection changed.');
        const current = await chrome.tabs.get(tab.id);
        if(linkedinAccessPage(current.url) || linkedinAccessPage(current.pendingUrl))throw safeError('LinkedIn needs sign-in or a verification check. Resolve it in its browser tab before scanning again.','HR_ACCESS_REQUIRED');
        const starting=created===tab.id && current.status==='loading' && (!current.url || current.url==='about:blank') && (!current.pendingUrl || current.pendingUrl===expected);
        if (jobURL(current.url) !== expected && !starting) throw safeError('The job left its expected LinkedIn page. Check the ad before trying again.');
        if (current.status === 'complete') return await readJobTab(bound, tab.id, expected,args.company_only===true);
        await new Promise(resolve => setTimeout(resolve, 500));
      }
      throw safeError('The LinkedIn ad did not finish loading. Open it in your browser, wait for the page to load, then try again.');
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
    delete connection.peopleSearch;
    connection.allowed = new Set(); await persist();
    for (const [id, expected] of [...owned,...viewed]) await closeOwned(id, expected);
    await persist(); return true;
  }
  if (connection.kind === 'hr') {
    const bound = connection, hr = bound.hr, run = args.run_id;
    if (!['hrRead','hrNext','hrJoined','hrJoinedClose'].includes(message.action) || args.tab_id !== bound.source) throw safeError('This action does not belong to the company HR search.');
    if (jobCapture) throw safeError('Wait for the current HR browser action to finish.');
    const token = {}; jobCapture = token;
    try {
    if (Date.now()-hr.started > 600000 || hr.stage === 'interrupted') throw safeError('The HR search timed out or was interrupted. Start a new scan.');
    const tab = await chrome.tabs.get(bound.source); live(bound,run);
    if (!linkedin(tab.url) && !(tab.status === 'loading' && (!tab.url || tab.url === 'about:blank'))) throw safeError('The HR search left LinkedIn.','HR_PAGE_CHANGED');
    if (['hrJoined','hrJoinedClose'].includes(message.action)) {
      const verify = async () => {
        live(bound,run); const source=await chrome.tabs.get(bound.source);
        live(bound,run);
        if (hr.stage !== 'ready' || hrSearchKey(source.url) !== hr.key || source.pendingUrl && hrSearchKey(source.pendingUrl) !== hr.key) throw safeError('The HR search changed while checking joining dates. Start a new scan.','HR_PAGE_CHANGED');
        return source.status === 'complete';
      };
      const sourceReady=await verify();
      if (message.action === 'hrJoinedClose') {
        // Cleanup returns no profile evidence. An unchanged loading search may
        // still release its exact inactive owned lookup before the next person.
        if (hr.joining && hr.joining.tab_id !== null) await closeOwned(hr.joining.tab_id,hr.joining.url);
        delete hr.joining; await persist(); return true;
      }
      if (!sourceReady) return hrWaiting(hr);
      if (!/^https:\/\/www\.linkedin\.com\/in\/[A-Za-z0-9_%~-]+$/.test(args.url || '') || !bound.allowed.has(args.url)) throw safeError('Choose an HR profile observed on this results page.');
      if (!hr.joining) {
        if ((hr.joined_count || 0) >= 100 || owned.size+viewed.size >= 76) throw safeError('The joining-date lookup limit was reached.');
        // Persist the attempt before opening. If suspension occurs mid-create,
        // the absent tab ID stops visibly rather than opening another tab.
        hr.joined_count=(hr.joined_count || 0)+1; hr.joining={url:args.url,tab_id:null,scrolls:0};
        await persist(); live(bound,run);
        const created=await chrome.tabs.create({url:args.url,active:false});
        owned.set(created.id,args.url);
        try { live(bound,run); hr.joining.tab_id=created.id; await persist(); }
        catch(error) { await closeOwned(created.id,args.url); throw error; }
        return hrWaiting(hr,'profile_navigation');
      }
      if (hr.joining.url !== args.url || hr.joining.tab_id === null) throw safeError('The joining-date lookup was interrupted. Start a new scan.');
      const id=hr.joining.tab_id;
      const profileTab=await ownedTab(id); live(bound,run);
      if (profileTab.status !== 'complete') return hrWaiting(hr,'profile_navigation');
      await jobScript({target:{tabId:id},files:['reader.js']},jobReaderStartError);
      await ownedTab(id); if (!await verify()) return hrWaiting(hr);
      const [injection]=await jobScript({target:{tabId:id},func:(values)=>{
        try { return globalThis.SourcerReader.readHRJoined(...values); }
        catch(error) { return {hrError:/sign in|verification|restriction/i.test(String(error?.message)) ? 'access' : 'layout'}; }
      },args:[[args.url,hr.company_url,hr.company_id]]},'The HR joining date could not be read. Refresh LinkedIn and try again.');
      await ownedTab(id); if (!await verify()) return hrWaiting(hr);
      const result=injection?.result;
      if (result?.hrError) throw safeError(result.hrError === 'access' ? 'LinkedIn needs sign-in or is showing a restriction. Resolve it before scanning again.' : 'The HR profile changed or could not be confirmed.');
      if (result == null || result.loading) {
        const leaveViewed = async () => {
          await closeOwned(id,args.url); delete hr.joining; await persist(); live(bound,run);
          return {url:args.url,joined:''};
        };
        if (viewed.has(id)) return leaveViewed();
        // LinkedIn lazy-loads Experience after scrolling. Only our unchanged
        // inactive tab can be scrolled; persist its small budget first.
        if ((hr.joining.scrolls || 0) < 4) {
          hr.joining.scrolls=(hr.joining.scrolls || 0)+1; await persist();
          await ownedTab(id); if (!await verify()) return hrWaiting(hr);
          if (viewed.has(id)) return leaveViewed();
          await jobScript({target:{tabId:id},func:url=>document.visibilityState==='visible'?false:globalThis.SourcerReader.prepareHRJoined(url),args:[args.url]},'The profile Experience section could not be loaded.');
          await ownedTab(id); if (!await verify()) return hrWaiting(hr);
        }
        return hrWaiting(hr,'profile_experience');
      }
      if (typeof result.joined !== 'string' || !/^(?:(?:19|20)\d{2}(?:-(?:0[1-9]|1[0-2]))?)?$/.test(result.joined)) throw safeError('The joining date could not be confirmed.');
      const employment={};
      if ('left' in result || 'current' in result) {
        const {joined,left,current}=result;
        if (typeof left !== 'string' || !/^(?:(?:19|20)\d{2}(?:-(?:0[1-9]|1[0-2]))?)?$/.test(left) || ![true,false,null].includes(current) ||
            current===true && (!joined || left) || current===false && (!joined || !left) || current===null && (joined || left) ||
            left && (joined.length===4?joined+'-01':joined)>(left.length===4?left+'-12':left)) throw safeError('The employment dates could not be confirmed.');
        Object.assign(employment,{left,current});
      }
      await closeOwned(id,args.url); delete hr.joining; await persist(); live(bound,run);
      return {url:args.url,joined:result.joined,...employment};
    }
    if (tab.status !== 'complete') return hrWaiting(hr);
    if (hr.joining) throw safeError('Finish the current joining-date lookup before paging.');
    if (message.action === 'hrNext') {
      if (hr.stage !== 'ready' || typeof args.signature !== 'string' || !args.signature || args.signature.length > 17000) throw safeError('Read the HR results before paging.');
      const queries=hrQueries(hr), snapshot=await hrScript(bound,run,'readHRSearch',[hr.company,hr.country,hr.keywords]);
      if (snapshot === HR_LOADING || snapshot == null || snapshot.loading) return hrWaiting(hr);
      if (typeof snapshot.signature !== 'string' || typeof snapshot.hasNext !== 'boolean') throw safeError('The HR results could not be confirmed.','HR_LAYOUT_UNCONFIRMED');
      if(hrSignature(hr,snapshot.signature)!==args.signature)return {refresh:true};
      const moreQueries=(hr.query_index || 0)+1 < queries.length;
      if (!snapshot.hasNext && !moreQueries) return false;
      // Within the existing total limit, reserve a first page for the remaining
      // groups instead of spending every page on one broad keyword query.
      const changeQuery=moreQueries && (!snapshot.hasNext || bound.pages-nextCount-1 <= queries.length-hr.query_index-1);
      nextCount++; await persist(); if (nextCount >= bound.pages) throw safeError('The HR page limit was reached.');
      if (changeQuery) {
        const oldKey=hr.key,oldIndex=hr.query_index,oldOmitted=hr.omitted_pages;
        const url=new URL(oldKey);url.searchParams.set('keywords',queries[oldIndex+1]);url.searchParams.delete('page');
        const target=hrSearchKey(url.href);if (target.length > 2048) throw safeError('Shorten the HR keywords before starting a new scan.');
        hr.stage='interrupted';await persist();live(bound,run);
        const current=await chrome.tabs.get(bound.source);live(bound,run);
        if (hrSearchKey(current.url) !== oldKey || current.pendingUrl && hrSearchKey(current.pendingUrl) !== oldKey) throw safeError('The HR search changed. Start again from the saved ad.');
        if (current.status !== 'complete') { hr.stage='ready';nextCount--;await persist();return hrWaiting(hr); }
        // Persist before navigating: suspension cannot repeat a possibly
        // completed query change or reset the shared page/profile/time budgets.
        if (snapshot.hasNext) hr.omitted_pages=true;
        hr.query_index=oldIndex+1;hr.key=target;await persist();live(bound,run);
        const confirmed=await chrome.tabs.get(bound.source);live(bound,run);
        if (hrSearchKey(confirmed.url) !== oldKey || confirmed.pendingUrl && hrSearchKey(confirmed.pendingUrl) !== oldKey) throw safeError('The HR search changed. Start again from the saved ad.');
        if (confirmed.status !== 'complete') {
          hr.query_index=oldIndex;hr.key=oldKey;hr.stage='ready';
          if (oldOmitted === undefined) delete hr.omitted_pages;else hr.omitted_pages=oldOmitted;
          nextCount--;await persist();return hrWaiting(hr);
        }
        await chrome.tabs.update(bound.source,{url:target});live(bound,run);
        hr.stage='search_wait';await persist();return true;
      }
      const result=await hrMutation(bound,run,'nextHRSearch',[snapshot.signature,hr.company,hr.country,hr.keywords],'ready');
      if (result === HR_LOADING || result === false) { nextCount--; await persist(); return hrWaiting(hr); }
      return result;
    }
    if (hr.stage === 'company') {
      const actualRoot=companyPeopleRoot(tab.url);
      if(!actualRoot)throw safeError('The company page is unavailable or needs sign-in. Check its LinkedIn tab.',linkedinAccessPage(tab.url)?'HR_ACCESS_REQUIRED':'HR_COMPANY_UNAVAILABLE');
      if(tab.pendingUrl && tab.pendingUrl!==tab.url && companyPeopleRoot(tab.pendingUrl))return hrWaiting(hr,'navigation');
      if(actualRoot!==hr.company_url && !hr.expected_company_id) {
        const error=safeError('LinkedIn redirected the company link. The employer link must be checked again before scanning.','HR_COMPANY_REDIRECT');error.companyURL=actualRoot;throw error;
      }
      const result = await hrScript(bound,run,'readHRCompany',[actualRoot,hr.company,!!hr.job_url,hr.expected_company_id || ''],tab.url);
      const confirmed=await chrome.tabs.get(bound.source);live(bound,run);
      if(confirmed.url!==tab.url || confirmed.pendingUrl && confirmed.pendingUrl!==tab.url)throw safeError('The company page changed while confirming its identity.','HR_PAGE_CHANGED');
      if(confirmed.status!=='complete')return hrWaiting(hr);
      // LinkedIn can finish navigation with an empty, unbooted document. One
      // passive reload of this run's unchanged inactive company source is safe
      // before any filter/profile work. Persist first; ambiguity never replays.
      if(result?.blank_document===true && result.loading===true){
        hr.company_blank_polls=Math.min(12,(hr.company_blank_polls || 0)+1);
        if(hr.company_blank_polls>=12 && !hr.company_blank_reloads && !confirmed.active){
          hr.company_blank_reloads=1;await persist();live(bound,run);
          const current=await chrome.tabs.get(bound.source);live(bound,run);
          if(current.url!==confirmed.url || current.pendingUrl && current.pendingUrl!==current.url)throw safeError('The company page changed before reloading.','HR_PAGE_CHANGED');
          if(current.active || current.status!=='complete')return hrWaiting(hr);
          await chrome.tabs.reload(bound.source);live(bound,run);return hrWaiting(hr);
        }
        await persist();return hrWaiting(hr);
      }
      delete hr.company_blank_polls;
      if(hr.expected_company_id && result?.company_id && result.company_id!==hr.expected_company_id)throw safeError('This company link now points to a different LinkedIn company. Check the saved ad before scanning.','HR_COMPANY_MISMATCH');
      if ((hr.job_url || hr.expected_company_id) && result?.company_name!==undefined) {
        if (typeof result.company_name!=='string' || !result.company_name.trim() || result.company_name.length>200 || /[\x00-\x1f\x7f]/.test(result.company_name)) throw safeError('The LinkedIn company name could not be confirmed.');
        hr.company=result.company_name.trim();
      }
      if (hrCompanyGroup(result?.company_ids)) hr.company_group=[...result.company_ids];
      else {
        if (result === HR_LOADING || result?.loading || result == null) return hrWaiting(hr);
        if (typeof result.company_id!=='string' || !/^[0-9]{1,24}$/.test(result.company_id)) throw safeError('The company employee link could not be confirmed.');
        hr.company_id = result.company_id;
      }
      hr.company_url=actualRoot;
      const url = new URL('https://www.linkedin.com/search/results/people/');
      url.searchParams.set('currentCompany',JSON.stringify(hr.company_group || [hr.company_id]));
      url.searchParams.set('keywords',hrQueries(hr)[0]);
      hr.key = hrSearchKey(url.href); hr.stage='interrupted'; await persist(); live(bound,run);
      if (hr.key.length > 2048) throw safeError('Shorten the HR keywords before starting a new scan.');
      const beforeNavigation=await chrome.tabs.get(bound.source);live(bound,run);
      if(beforeNavigation.url!==tab.url || beforeNavigation.pendingUrl && beforeNavigation.pendingUrl!==tab.url)throw safeError('The company page changed before the search could open.','HR_PAGE_CHANGED');
      if(beforeNavigation.status!=='complete'){
        hr.stage='company';hr.key='';delete hr.company_group;delete hr.company_id;await persist();return hrWaiting(hr);
      }
      await chrome.tabs.update(bound.source,{url:hr.key}); live(bound,run); hr.stage='search_wait'; await persist(); return hrWaiting(hr);
    }
    if (hr.stage === 'search_wait') {
      // tabs.update resolves before the old complete document necessarily
      // commits the requested navigation. Wait only for our exact target;
      // never read the old company page as People results or navigate again.
      let previous=hr.company_url+'people/';
      if (hr.query_index > 0) { const url=new URL(hr.key);url.searchParams.set('keywords',hrQueries(hr)[hr.query_index-1]);previous=hrSearchKey(url.href); }
      const previousMatches=hr.query_index>0?hrSearchKey(tab.url)===previous:companyPeopleRoot(tab.url)===hr.company_url;
      if (tab.pendingUrl && hrSearchKey(tab.pendingUrl) !== hr.key || !previousMatches && hrSearchKey(tab.url) !== hr.key) throw safeError('The HR search changed. Start again from the saved ad.','HR_PAGE_CHANGED');
      if (hrSearchKey(tab.url) !== hr.key) return hrWaiting(hr);
      hr.stage=hr.company_group ? 'company_open' : hr.query_index > 0 ? 'ready' : 'search'; await persist();
    }
    if (hr.stage==='company_open') { await hrMutation(bound,run,'hrCompanyOpen',[],'company_only'); return hrWaiting(hr); }
    if (hr.stage==='company_only') { await hrMutation(bound,run,'hrCompanyOnly',[hr.company,hr.company_group.length],'company_apply'); return hrWaiting(hr); }
    if (hr.stage==='company_apply') { await hrMutation(bound,run,'hrCompanyApply',[hr.company],'company_wait'); return hrWaiting(hr); }
    if (hr.stage==='company_wait') {
      const resolve=value=>{
        const key=hrSearchKey(value);if(key===hr.key || key==='https://www.linkedin.com/search/results/people/') return null;
        // LinkedIn's native Show results link can retain the keywords while
        // temporarily omitting currentCompany. Wait for the confirmed company;
        // this intermediate page must never authorize any profile reads.
        const withoutCompany=new URL(hr.key);withoutCompany.searchParams.delete('currentCompany');
        if(!new URL(value).searchParams.has('currentCompany') && key===hrSearchKey(withoutCompany.href))return null;
        let ids;try { ids=JSON.parse(new URL(value).searchParams.get('currentCompany')); } catch {}
        const pendingExpected=new URL(hr.key);pendingExpected.searchParams.set('currentCompany',JSON.stringify(ids));
        // Only passive waiting for still-known group members is allowed. The
        // final employer must remain singular before any people can be read.
        if(Array.isArray(ids) && ids.length>1 && new Set(ids).size===ids.length && ids.every(id=>hr.company_group.includes(id)) && key===hrSearchKey(pendingExpected.href))return null;
        if (!Array.isArray(ids) || ids.length!==1 || !hr.company_group.includes(ids[0]) || hr.expected_company_id && ids[0]!==hr.expected_company_id) throw safeError('The grouped company selection changed. Start a new scan.','HR_COMPANY_MISMATCH');
        const expected=new URL(hr.key);expected.searchParams.set('currentCompany',JSON.stringify(ids));
        if(key!==hrSearchKey(expected.href)) throw safeError('The company search filters changed. Start a new scan.');
        return {key,id:ids[0]};
      };
      const selected=resolve(tab.url),pending=tab.pendingUrl?resolve(tab.pendingUrl):null;
      if (!selected) return hrWaiting(hr);
      if (pending && pending.key!==selected.key) throw safeError('The grouped company selection changed. Start a new scan.');
      if (tab.pendingUrl && !pending) return hrWaiting(hr);
      hr.company_id=selected.id;hr.key=selected.key;delete hr.company_group;hr.stage='search';await persist();return hrWaiting(hr);
    }
    if (hr.stage === 'country_wait') {
      const resolved = new URL(tab.url), expected = new URL(hr.key);
      const geo = resolved.searchParams.getAll('geoUrn');
      if (geo.length !== 1 || !/^\["[0-9]{1,24}"\]$/.test(geo[0])) return hrWaiting(hr);
      expected.searchParams.set('geoUrn',geo[0]);
      if (hrSearchKey(resolved.href) !== hrSearchKey(expected.href)) throw safeError('LinkedIn changed the company or keywords. Start a new scan.');
      hr.key=hrSearchKey(expected.href); hr.stage='ready'; await persist();
    }
    if (hr.stage === 'search' && !hr.country) { hr.stage='ready'; await persist(); }
    if (hr.stage === 'search') { await hrMutation(bound,run,'hrCountryOpen',[hr.country],'type'); return hrWaiting(hr); }
    if (hr.stage === 'type') { await hrMutation(bound,run,'hrCountryType',[hr.country],'pick'); return hrWaiting(hr); }
    if (hr.stage === 'pick') { await hrMutation(bound,run,'hrCountryPick',[hr.country],'apply'); return hrWaiting(hr); }
    if (hr.stage === 'apply') { await hrMutation(bound,run,'hrCountryApply',[hr.country],'country_wait'); return hrWaiting(hr); }
    const result = await hrScript(bound,run,'readHRSearch',[hr.company,hr.country,hr.keywords]);
    if (result === HR_LOADING || result == null || result.loading) return hrWaiting(hr,result?.wait_stage || '');
    if (!Array.isArray(result.people) || result.people.length > 40 || typeof result.signature !== 'string') throw safeError('The HR results could not be read.');
    if (hrSearchKey((await chrome.tabs.get(bound.source)).url) !== hr.key) throw safeError('The HR search changed during the read.');
    bound.allowed=new Set(result.people.map(person=>person.url).filter(url=>typeof url === 'string' && /^https:\/\/www\.linkedin\.com\/in\/[A-Za-z0-9_%~-]+$/.test(url)));
    await persist(); live(bound,run);
    const hasNext=result.hasNext || (hr.query_index || 0)+1 < hrQueries(hr).length || hr.omitted_pages === true;
    return {...result,signature:hrSignature(hr,result.signature),hasNext,empty:result.empty && !hasNext,
      query_index:hr.query_index || 0,query_count:hrQueries(hr).length,company_id:hr.company_id,company_name:hr.company,company_url:hr.company_url,source_url:hr.key};
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
  if (jobCapture) throw safeError('Wait for the current companion action to finish.');
  if (message.action === 'create') {
    if (!profile(args.url) || !connection.allowed.has(args.url) || ++profileCount > 75) throw Error('The profile action is outside the run limits.');
    const bound = connection;
    await persist(); live(bound, args.run_id);
    const tab = await chrome.tabs.create({url: args.url, active: false}); owned.set(tab.id, args.url);
    try { await persist(); live(bound, args.run_id); return tab.id; }
    catch (error) { await closeOwned(tab.id, args.url); throw error; }
  }
  const bound = connection;
  const tab = owned.has(args.tab_id) || viewed.has(args.tab_id) ? await ownedTab(args.tab_id) : await chrome.tabs.get(args.tab_id);
  if (connection?.run !== args.run_id) throw Error('The browser run has stopped.');
  if (!linkedin(tab.url) && !((owned.has(tab.id) || viewed.has(tab.id)) && expectedLoading(tab,owned.get(tab.id) || viewed.get(tab.id))) && !(tab.id === connection.source && pendingPeopleSearch(tab))) throw Error('The selected tab left LinkedIn.');
  if (tab.id !== connection.source && !owned.has(tab.id) && !viewed.has(tab.id)) throw safeError('The scan profile tab changed or closed. Your candidate list is kept.');
  if (message.action === 'navigate') {
    if(args.fresh!==undefined && typeof args.fresh!=='boolean')throw safeError('The profile navigation request is invalid.');
    const search = args.url?.startsWith('https://www.linkedin.com/search/results/people/?');
    if ((!search && !profile(args.url)) || (search && tab.id !== connection.source) ||
        (profile(args.url) && (!owned.has(tab.id) && !viewed.has(tab.id) || !connection.allowed.has(args.url)))) throw Error('This navigation is not supported.');
    if (profile(args.url) && ++profileCount > 75) throw Error('The profile limit was reached.');
    const previous = owned.get(tab.id) || viewed.get(tab.id);
    const replacement = async () => {
      // The viewed page is released before opening another exact observed URL.
      // It can never be closed by a suspended or older worker afterward.
      if(args.fresh===true)await closeOwned(tab.id,previous);
      owned.delete(tab.id);viewed.delete(tab.id);await persist();live(bound,args.run_id);
      const created=await chrome.tabs.create({url:args.url,active:false});owned.set(created.id,args.url);
      try {await persist();live(bound,args.run_id);return {tab_id:created.id};}
      catch(error){await closeOwned(created.id,args.url);throw error;}
    };
    if (previous) {
      const current=await ownedTab(tab.id);live(bound,args.run_id);
      if (args.fresh===true || viewed.has(tab.id) || current.active) return replacement();
      owned.set(tab.id,args.url);
    }
    if (search) {
      if (bound.peopleSearch) throw safeError('Start a new run before changing the People search.');
      bound.peopleSearch={key:hrSearchKey(args.url),previous:hrSearchKey(tab.url),country:'',stage:'waiting',started:Date.now()};
    }
    await persist(); live(bound, args.run_id);
    if (previous) {
      const current = await chrome.tabs.get(tab.id);
      if ((!owned.has(tab.id) && !viewed.has(tab.id)) || !sameOwnedPage(current.url, previous) || current.pendingUrl && !sameOwnedPage(current.pendingUrl, previous)) {
        owned.delete(tab.id);viewed.delete(tab.id); await persist(); throw safeError('The scan profile tab changed. Your candidate list is kept.');
      }
      if (viewed.has(tab.id) || current.active) return replacement();
    }
    live(bound, args.run_id); await chrome.tabs.update(tab.id, {url: args.url});
    return true;
  }
  if (message.action === 'read') {
    if (args.method==='setCountry') {
      if (tab.id!==bound.source || !Array.isArray(args.values) || args.values.length!==1) throw Error('Invalid People location request.');
      const token={};jobCapture=token;
      try { return await peopleCountry(bound,args.run_id,args.values[0]); }
      finally { if(jobCapture===token)jobCapture=null; }
    }
    if (!['readSearch', 'readProfile', 'search', 'next'].includes(args.method)) throw Error('This browser action is not supported.');
    if (args.method === 'readProfile' ? !owned.has(tab.id) && !viewed.has(tab.id) : tab.id !== connection.source) throw Error('This read does not belong to the sourcing run.');
    if (tab.status !== 'complete') return {loading: true};
    const readerError = 'LinkedIn results could not be read. Refresh LinkedIn, then reload and reconnect the latest companion.';
    const checkCountry=async()=>{
      const filter=bound.peopleSearch;
      if (!filter?.country) return true;
      live(bound,args.run_id);const source=await chrome.tabs.get(bound.source);live(bound,args.run_id);
      if (filter.stage!=='ready' || hrSearchKey(source.url)!==filter.key || source.pendingUrl && hrSearchKey(source.pendingUrl)!==filter.key) throw safeError('The selected location or search changed. Start a new search.');
      return source.status==='complete';
    };
    if (!await checkCountry()) return {loading:true};
    await jobScript({target: {tabId: tab.id}, files: ['reader.js']},readerError);
    if (!await checkCountry()) return {loading:true};
    if (tab.id===bound.source && bound.peopleSearch?.country) {
      const [selected]=await jobScript({target:{tabId:tab.id},func:country=>globalThis.SourcerReader.peopleCountrySelected(country),args:[bound.peopleSearch.country]},readerError);
      if (!selected?.result || !await checkCountry()) return {loading:true};
    }
    if (connection?.run !== args.run_id) throw Error('The browser run has stopped.');
    if (args.method === 'readProfile') await ownedTab(tab.id);
    live(bound, args.run_id);
    if (args.method === 'next') { nextCount++; await persist(); live(bound, args.run_id); if (nextCount >= connection.pages) throw Error('The requested page limit was reached.'); }
    const [injection] = await jobScript({target: {tabId: tab.id},
      func: (method, values) => {
        try { return globalThis.SourcerReader[method](...values); }
        // Script exceptions may arrive without a serializable result. Return a
        // fixed reason instead of leaking page content or treating failure as empty.
        catch (error) { return {cvstudioReaderError:/sign in|verification check|access or usage restriction/i.test(String(error?.message)) ? 'access' : 'reader'}; }
      }, args: [args.method, args.values || []]},readerError);
    const result = injection?.result;
    live(bound, args.run_id);
    if (args.method === 'readProfile') { await ownedTab(tab.id); live(bound,args.run_id); }
    // A successful Next may already be loading the new page. Never replay its
    // click merely because the unchanged filters are temporarily loading.
    if (!await checkCountry() && args.method !== 'next') return {loading:true};
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
return {ready,handle,pickJob,pair,connectApp,removed,updated,activated,publicError,
  binding:()=>connection, busy:()=>!!connection?.run || !!jobCapture,
  hasOwned:()=>!!owned.size,
  owns:id=>!!connection?.run && connection.source===id || owned.has(id) || viewed.has(id)};
}

sessions.set('profiles',createCompanionSession('profiles'));
sessions.set('leads',createCompanionSession('leads'));
const allReady=Promise.all([...sessions.values()].map(session=>session.ready));
let bindingWrites=Promise.resolve();
function connectSessions(sender) {
  const work=async()=>{
    await allReady;
    if(updatePending)throw sessionError('The companion is updating. Refresh CV Studio and LinkedIn when ready.');
    for(const session of sessions.values()){
      const bound=session.binding();
      if(session.busy() && (bound?.tabId!==sender.tab?.id || bound?.documentId!==sender.documentId))throw sessionError('Finish the companion action in the other CV Studio tab first.');
    }
    for(const session of sessions.values())await session.connectApp(sender);
  };
  const result=bindingWrites.catch(()=>{}).then(work);bindingWrites=result;return result;
}
nativeChrome.action.onClicked.addListener(async tab=>{
  await allReady;
  if(updatePending || [...sessions.values()].some(session=>session.busy())){await nativeChrome.action.setBadgeText({text:'ON'});return;}
  for(const session of sessions.values())await session.pair(tab);
});
for(const [event,method] of [['onRemoved','removed'],['onUpdated','updated'],['onActivated','activated']]){
  nativeChrome.tabs[event].addListener((...args)=>Promise.all([...sessions].map(async([scope,session])=>{
    await session[method](...args);releaseLeases(scope);
  })));
}
const leadActions=new Set(['hrDate','hrBegin','hrRead','hrNext','hrJoined','hrJoinedClose','jobRead','jobFromLink','jobReadCancel','jobTabs','jobSearchTabs','jobSearchBegin']);
function messageScope(message) {
  if(message.scope!==undefined){
    if(!sessions.has(message.scope))throw sessionError('Refresh CV Studio to use the current companion.');
    if(message.scope==='profiles' && leadActions.has(message.action) || message.scope==='leads' && ['begin','openPeopleSearch','create','navigate','tabs'].includes(message.action))throw sessionError('This browser action belongs to the other module.');
    return message.scope;
  }
  if(leadActions.has(message.action))return 'leads';
  if(['end','read','create','navigate'].includes(message.action)){
    const matches=[...sessions].filter(([,session])=>session.binding()?.run && session.binding().run===message.args?.run_id);
    if(matches.length>1)throw sessionError('The browser run could not be identified. Stop and start it again.');
    if(matches.length)return matches[0][0];
  }
  return 'profiles';
}
async function dispatch(message,sender) {
  await allReady;
  if(message.action==='connect'){await connectSessions(sender);return {connected:true,version:nativeChrome.runtime.getManifest().version};}
  const scope=messageScope(message),session=sessions.get(scope);
  if(updatePending && !['jobStatus','end','jobReadCancel'].includes(message.action))throw sessionError('The companion is updating. Refresh CV Studio and LinkedIn when ready.');
  for(const peer of sessions.values()){
    const bound=peer.binding();
    if(peer.busy() && (bound?.tabId!==sender.tab?.id || bound?.documentId!==sender.documentId))throw sessionError('Finish the companion action in the other CV Studio tab first.');
  }
  if(message.action==='reloadCompanion'){
    if([...sessions.values()].some(s=>s.busy() || s.hasOwned()))throw sessionError('Finish or stop both scans before updating the companion.');
    updatePending=true;
  }
  if(['begin','hrBegin','jobSearchBegin'].includes(message.action) && [...sessions].some(([name,s])=>name!==scope && s.binding()?.run===message.args?.run_id && s.binding()?.run))throw sessionError('A scan is already using this run identifier. Start again.');
  // Old app pages retain the single-run contract. Only the current scoped UI
  // may start a second session; it first checks the capability before spending.
  if(message.scope===undefined && !['jobStatus','tabs','jobTabs','jobSearchTabs','end','jobReadCancel'].includes(message.action) && [...sessions].some(([name,s])=>name!==scope && s.busy()))throw sessionError('Update CV Studio before running both scans together.');
  const token=(inFlight.get(scope)||0)+1;inFlight.set(scope,token);
  let reloading=false;
  try{
    if(message.action==='begin' || message.action==='jobSearchBegin' && message.args?.use_open){
      const id=message.args?.source_tab_id;if(Number.isInteger(id)){assertSessionTab(scope,id);tabLeases.set(id,scope);}
    }
    const result=await session.handle(message,sender);
    if(message.action==='reloadCompanion')reloading=result?.reloading===true;
    if(message.action==='jobStatus')return {...result,busy:message.scope===undefined?[...sessions.values()].some(s=>s.busy()):result.busy,other_busy:[...sessions].some(([name,s])=>name!==scope&&s.busy())};
    return result;
  }finally{inFlight.set(scope,inFlight.get(scope)-1);releaseLeases(scope);if(message.action==='reloadCompanion' && !reloading)updatePending=false;}
}
nativeChrome.runtime.onMessage.addListener((message,sender,reply)=>{
  const errors=sessions.get('profiles').publicError;
  if(message?.kind==='sourcer_job_pick'){
    const scope='leads';inFlight.set(scope,(inFlight.get(scope)||0)+1);
    allReady.then(()=>{
      if(updatePending)throw sessionError('The companion is updating. Refresh CV Studio and LinkedIn when ready.');
      const bound=sessions.get(scope).binding();
      if([...sessions.values()].some(s=>s.busy() && (s.binding()?.tabId!==bound?.tabId || s.binding()?.documentId!==bound?.documentId)))throw sessionError('Open Job Leads in the CV Studio tab that is running the scan.');
      return sessions.get(scope).pickJob(message,sender);
    }).then(result=>reply({result}),error=>reply(errors(error))).finally(()=>{inFlight.set(scope,inFlight.get(scope)-1);releaseLeases(scope);});return true;
  }
  if(message?.kind!=='sourcer')return false;
  dispatch(message,sender).then(result=>reply({result}),error=>reply(errors(error)));return true;
});
