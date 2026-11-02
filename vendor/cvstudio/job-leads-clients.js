/* Signed and followed JobAdder clients in Job Leads. JobAdder is only read.
 * Signed clients: choose the signed statuses and follow clients. Followed
 * clients: pull their LinkedIn job ads into CV Studio (or open one LinkedIn
 * search to choose ads there), save the chosen ads to Job ads, and review the
 * saved client ads in a dashboard. */
(() => {
  'use strict';
  const el = id => document.getElementById('jobLeadsClients' + id);
  const node = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; };
  const JOB_URL = /^https:\/\/www\.linkedin\.com\/jobs\/view\/[0-9]{1,24}$/;
  const COMPANY_URL = /^https:\/\/www\.linkedin\.com\/company\/[A-Za-z0-9_-]{1,100}\/$/;
  const JOBADDER_URL = /^https:\/\/[a-z0-9-]+(?:\.[a-z0-9-]+)*\.jobadder\.com\/companies\/[1-9][0-9]{0,9}$/;
  const LEGAL = new Set(['pt','tbk','sdn','bhd','berhad','pte','ltd','limited','inc','llc','corp','corporation','co','plc','gmbh','the']);
  const MAX_FOUND = 600, MAX_PER_PULL = 15, FOUND_PAGE = 50, ADS_PAGE = 50, COMPANY_PAGE = 50;
  const TICKS_KEY = 'cvstudio_signed_clients_ticks';
  // Job Leads owns the status names; this view only reads them.
  const statusLabels = () => window.cvStudioJobLeads?.statusLabels || {};
  const fresh = () => ({account:'', signed:[], statuses:null, followed:[], records:[], folders:[], companies:null, found:[], picked:new Set(),
    chosen:null, foundPage:0, adsPage:0, adsShown:0, saving:false, adsPicked:new Set(), adsPageIds:[], hrScanning:false, resolvedIds:new Map(), linkedinSearch:'', working:false, refreshing:false, resolving:false, pulling:false, stopped:false, run:'', loaded:false, statusDraft:null, statusDirty:false, linkGuide:0, recordsReady:false});
  let state = fresh(), generation = 0, ready = false, resyncNeeded = false, recordsRead = 0, returning = null;
  let savedIndex = {records:null, urls:new Map()}, countIndex = {records:null, followed:null, counts:new Map()}, adsIndex = {records:null, followed:null, rows:[]};

  // Pure helpers (exported for tests) ---------------------------------------

  function words(name) {
    return String(name || '').toLowerCase().normalize('NFKD').replace(/[^a-z0-9]+/g, ' ').split(' ').filter(word => word && !LEGAL.has(word));
  }
  function subset(a, b) {
    const [short, long] = a.length <= b.length ? [a, b] : [b, a];
    return short.length > 0 && short.every(word => long.includes(word));
  }
  function sameCompany(a, b) { return subset(words(a), words(b)); }
  // A followed client is pullable once its numeric LinkedIn company is known:
  // from JobAdder or a pasted link, or from an HR scan of the same company page.
  function linkedinId(client, records) {
    if (/^[0-9]{1,24}$/.test(client?.linkedin_id || '')) return client.linkedin_id;
    if (!COMPANY_URL.test(client?.linkedin_url || '')) return '';
    const match = (records || []).find(row => row?.hr?.company_url === client.linkedin_url && /^[0-9]{1,24}$/.test(row.hr.company_id || ''));
    return match ? match.hr.company_id : '';
  }
  const eligible = client => !!linkedinId(client,state.records) || COMPANY_URL.test(client?.linkedin_url || '');
  // A company number the companion already read from the client's page this
  // session is reused, so the page is not reopened for every pull. It is
  // bound to that exact page: a changed LinkedIn link is read again.
  const knownId = client => {
    const cached = state.resolvedIds.get(client.company_id);
    return linkedinId(client, state.records) || (cached && cached.url === client.linkedin_url ? cached.id : '');
  };
  const remember = (client, id) => state.resolvedIds.set(client.company_id, {url:client.linkedin_url, id});
  // One LinkedIn job search for several companies; LinkedIn's company filter
  // takes a comma-separated list of numeric company IDs.
  function linkedinSearch(ids) {
    const clean = [...new Set(ids)].filter(id => /^[0-9]{1,24}$/.test(id));
    if (!clean.length) return '';
    const url = new URL('https://www.linkedin.com/jobs/search/');
    url.searchParams.set('f_C', clean.join(','));
    return url.href;
  }
  // Saved, non-deleted Job ads of followed clients, each listed once. An ad
  // saved from a client pull carries that client; other ads (for example ones
  // added on LinkedIn) go to the followed client whose name matches the ad's
  // company most specifically. The "Ads in Job ads" count uses the same rows.
  function clientAds(records, followed) {
    const clients = (followed || []).map(client => ({client, words:words(client.name)}));
    const byId = new Map(clients.map(item => [item.client.company_id, item.client]));
    const rows = [];
    for (const record of records || []) {
      if (!record || record.deleted) continue;
      const tagged = byId.get(record.client?.company_id);
      if (tagged) { rows.push({record, client:tagged}); continue; }
      const own = words(record.company);
      const match = clients.filter(item => subset(item.words, own)).sort((a, b) =>
        Math.abs(a.words.length - own.length) - Math.abs(b.words.length - own.length) || b.words.length - a.words.length)[0];
      if (match) rows.push({record, client:match.client});
    }
    return rows;
  }
  // Exact posted date when LinkedIn gave one, otherwise its estimate ("≈").
  const postedOf = row => row?.date_posted || row?.date_posted_estimate || '';
  const postedText = row => row?.date_posted || (row?.date_posted_estimate ? '≈ ' + row.date_posted_estimate : '—');
  function savedAds(client, records) {
    return (records || []).filter(row => !row.deleted && sameCompany(row.company, client.name)).length;
  }
  // One results page, checked by the shared search reader, tagged with its
  // client. Ads already listed are skipped; `dropped` counts new ads that did
  // not fit under the review limit.
  function cleanJobs(snapshot, client, found) {
    const added = [], listed = new Set(found.map(row => row.url));
    let dropped = 0;
    for (const row of window.cvStudioJobSearch.rows(snapshot)) {
      if (listed.has(row.url)) continue;
      listed.add(row.url);
      if (found.length + added.length >= MAX_FOUND) { dropped++; continue; }
      added.push({...row, client_id:client.company_id, client_name:client.name});
    }
    return {added, dropped};
  }

  // Transport ----------------------------------------------------------------

  async function readWithin(ms, message, read) {
    const controller=new AbortController();let timer;
    try {
      return await Promise.race([read(controller.signal),new Promise((_,reject)=>{
        timer=setTimeout(()=>{reject(Error(message));controller.abort();},ms);
      })]);
    } finally {clearTimeout(timer);}
  }
  async function call(body) {
    const read=async signal=>{
      const response = await fetch('/jobadder/clients', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body), cache:'no-store',...(signal?{signal}:{})});
      let data = {};
      try { data = await response.json(); } catch {throw Error('The client list response could not be read. Click Refresh to load it again.');}
      if (!response.ok || data.ok === false || data.error) throw Error(data.error || data.message || 'The client list could not be loaded.');
      return data;
    };
    // Only reads have a UI deadline. Never time out/replay a choice write.
    return ['overview','statuses','companies'].includes(body.action)
      ? readWithin(60000,'JobAdder did not finish loading clients. Click Refresh to check again; saved client choices were kept.',read) : read();
  }
  async function leads(body) {
    const read=async signal=>{
      const response = await fetch('/job-leads', body ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)} : {cache:'no-store',signal});
      let data = {};
      try { data = await response.json(); } catch {throw Error('Saved ads could not be read. Click Refresh to load them again.');}
      if (!response.ok || data.error) throw Error(data.error || 'Job Leads could not finish this request.');
      return data;
    };
    return body ? read() : readWithin(15000,'Saved ads did not finish loading. Click Refresh to check again.',read);
  }
  const jobLeads = () => window.cvStudioJobLeads;
  const namespace = () => String(window._jaAccountCacheNamespace || '');
  // The page's JobAdder account must still be the one the data was read for.
  function sameAccount(account) {
    const current = namespace();
    return !account || !current || current === 'ja' + account;
  }
  // Another tab may have reconnected JobAdder: refresh this page's account the
  // way the rest of CV Studio does, which also clears other modules' caches.
  async function syncAccount() {
    try {
      const response = await fetch('/jobadder/api_info', {cache:'no-store'});
      const info = await response.json();
      if (typeof window.applyJAPublicInfo === 'function') window.applyJAPublicInfo(info);
    } catch {}
  }
  const message = text => { el('Message').textContent = text; el('FollowedMessage').textContent = text; };
  const progress = text => { el('Progress').textContent = text; };
  const hex = () => crypto.randomUUID().replaceAll('-', '');
  const BUSY_MESSAGE = 'Job Leads is busy with another search, scan or save. Try again when it finishes.';

  // Cached lookups: rebuilt only when the saved ads or followed clients change.
  function savedJob(url) {
    if (savedIndex.records !== state.records) savedIndex = {records:state.records, urls:new Map(state.records.map(row => [row.url, row]))};
    return savedIndex.urls.get(url) || null;
  }
  function savedCount(client) {
    if (countIndex.records !== state.records || countIndex.followed !== state.followed) {
      const counts = new Map();
      for (const row of allClientAds()) counts.set(row.client.company_id, (counts.get(row.client.company_id) || 0) + 1);
      countIndex = {records:state.records, followed:state.followed, counts};
    }
    return countIndex.counts.get(client.company_id) || 0;
  }
  function storedTicks() {
    try { const value = JSON.parse(localStorage.getItem(TICKS_KEY) || 'null'); return Array.isArray(value) ? value.filter(Number.isSafeInteger) : null; } catch { return null; }
  }
  function rememberTicks() { try { localStorage.setItem(TICKS_KEY, JSON.stringify([...state.chosen])); } catch {} }

  // Rendering ----------------------------------------------------------------

  function link(text, url, pattern) {
    const a = node('a', text);
    if (pattern.test(url || '')) { a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; }
    return a;
  }
  function button(text, action, cls = 'sec') {
    const b = node('button', text, cls); b.type = 'button'; b.addEventListener('click', action); return b;
  }
  function mine() { return state.working || state.pulling || state.hrScanning; }
  const pullable = () => state.followed.filter(client => state.chosen?.has(client.company_id) && eligible(client));
  const knownStatuses = () => new Set((state.statuses || []).map(row => row.id));
  const staleStatuses = () => state.statuses ? state.signed.filter(id => !knownStatuses().has(id)) : [];
  function pageRows() { return state.found.slice(state.foundPage * FOUND_PAGE, (state.foundPage + 1) * FOUND_PAGE); }
  const compareText = (a,b) => String(a || '').localeCompare(String(b || ''),undefined,{numeric:true,sensitivity:'base'});
  function companyChoices(name, values, blank) {
    const select=el(name),old=select.value,choices=new Map();
    for (const value of values) choices.set(JSON.stringify(value || ''),value || blank);
    if (old && !choices.has(old)) {
      try { const value=JSON.parse(old);if(typeof value==='string')choices.set(old,(value || blank)+' (not on this page)'); } catch {}
    }
    const option=(value,label)=>{const n=node('option',label);n.value=value;return n;};
    select.replaceChildren(option('',name==='StatusFilter'?'All statuses':'All owners'),
      ...[...choices].sort((a,b)=>compareText(a[1],b[1])).map(([value,label])=>option(value,label)));
    select.value=choices.has(old)?old:'';
  }
  function companyRows() {
    const status=el('StatusFilter').value,owner=el('OwnerFilter').value,follow=el('FollowingFilter').value;
    const followed=new Set(state.followed.map(row=>row.company_id));
    const sorts={name_asc:['name',1],name_desc:['name',-1],status_asc:['status',1],status_desc:['status',-1],owner_asc:['owner',1],owner_desc:['owner',-1]};
    const [field,direction]=sorts[el('Sort').value] || sorts.name_asc;
    return (state.companies?.rows || []).filter(row=>(!status || JSON.stringify(row.status || '')===status) &&
      (!owner || JSON.stringify(row.owner || '')===owner) && (!follow || followed.has(row.company_id)===(follow==='followed'))).sort((a,b)=>{
        const x=a[field] || '',y=b[field] || '';
        if (!x || !y) { if (x || y) return x?-1:1; }
        else { const difference=direction*compareText(x,y);if(difference)return difference; }
        return compareText(a.name,b.name) || a.company_id-b.company_id;
      });
  }
  const sameIds = (a, b) => [...a].sort((x, y) => x - y).join() === [...b].sort((x, y) => x - y).join();
  // Ticks the owner changed but has not saved: the client list still uses the
  // saved statuses, so searching waits for Save statuses.
  const unsavedStatuses = () => !!state.statusDraft && state.statusDirty && !sameIds(state.statusDraft, state.signed);
  function controls() {
    const locked = mine(), signedNames = (state.statuses || []).filter(row => state.signed.includes(row.id)).map(row => row.name);
    el('Count').textContent = String(state.followed.length);
    el('Refresh').disabled = locked;
    el('RefreshFollowed').disabled = locked || !state.loaded || !state.followed.length;
    const stale = staleStatuses().length;
    el('SetupSummary').textContent = state.signed.length ? '· ' + (signedNames.length ? signedNames.join(', ') : state.signed.length + ' chosen') + (stale ? ` · ${stale} no longer in JobAdder` : '') : '· not chosen yet';
    el('StatusesLoad').disabled = locked;
    const draft = state.statusDraft;
    // An empty choice saves too, so statuses JobAdder no longer lists can all be dropped.
    el('StatusesSave').disabled = locked || !draft || sameIds(draft, state.signed);
    const unsaved = unsavedStatuses();
    el('Search').disabled = el('Query').disabled = locked || !state.loaded || !state.signed.length || unsaved;
    const c = state.companies;
    el('CompaniesPrevious').disabled = locked || !c || c.offset === 0 || unsaved;
    el('CompaniesNext').disabled = locked || !c || c.next === null || unsaved;
    // Job Leads' own busy state is checked when Pull/Add is clicked, so the
    // buttons never sit disabled after Job Leads finishes.
    el('Pull').disabled = locked || !state.recordsReady || !state.signed.length || stale || !pullable().length;
    el('OpenLinkedIn').disabled = locked || !state.signed.length || stale || !pullable().length;
    el('FollowedRefresh').disabled = locked;
    for (const name of ['StatusFilter','OwnerFilter','FollowingFilter','Sort','FiltersReset']) el(name).disabled=locked || !c?.rows.length;
    el('Stop').disabled = !(state.pulling || state.refreshing || state.saving) || state.stopped;
    el('Pages').disabled = locked;
    el('Untick').disabled = locked || !state.chosen?.size;
    el('Ticked').textContent = state.followed.length ? `${pullable().length} of ${MAX_PER_PULL} ticked` : '';
    const newOnPage = pageRows().filter(row => !savedJob(row.url));
    el('SelectNew').disabled = locked || !newOnPage.length;
    el('SelectNew').checked = !!newOnPage.length && newOnPage.every(row => state.picked.has(row.url));
    const waiting = state.found.filter(row => state.picked.has(row.url) && !savedJob(row.url)).length;
    const allNew = state.found.filter(row => !savedJob(row.url)).length;
    el('Add').disabled = locked || !state.recordsReady || !waiting;
    el('SelectAll').disabled = locked || !allNew || waiting === allNew;
    el('SelectNone').disabled = locked || !waiting;
    el('Picked').textContent = state.found.length ? `${waiting} of ${allNew} new ad${allNew === 1 ? '' : 's'} selected` : '';
    el('Clear').disabled = locked || !state.found.length;
    el('Folder').disabled = locked;
    el('FoundPrevious').disabled = locked || state.foundPage === 0;
    el('FoundNext').disabled = locked || (state.foundPage + 1) * FOUND_PAGE >= state.found.length;
    const chosenFolder = (() => { try { return JSON.parse(el('AdsFolder').value || '""'); } catch { return ''; } })();
    const pageIds = state.adsPageIds, size = state.adsPicked.size;
    el('AdsSelectPage').disabled = locked || !pageIds.length;
    el('AdsSelectPage').checked = !!pageIds.length && pageIds.every(id => state.adsPicked.has(id));
    el('AdsSelectAll').disabled = locked || !state.adsShown;
    el('AdsSelection').hidden = !size; el('AdsSelected').textContent = `${size} selected`;
    for (const name of ['AdsMove', 'AdsTrash', 'AdsSelectNone', 'AdsMoveFolder']) el(name).disabled = locked;
    el('AdsFolderNew').disabled = el('AdsFolderCreate').disabled = locked;
    el('AdsFolderDelete').disabled = locked || !chosenFolder;
    el('HR').hidden = !size && !state.hrScanning;
    el('HRStart').disabled = locked || !size;
    el('HRStart').textContent = size && jobLeads()?.clientScanResumes?.([...state.adsPicked]) ? 'Resume unfinished ads' : 'Scan selected ads';
    for (const name of ['HRCountryMode', 'HRCountry', 'HRPages', 'HRKeywords']) el(name).disabled = locked;
    el('HRStop').disabled = !state.hrScanning;
    el('AdsPrevious').disabled = state.adsPage === 0;
    el('AdsNext').disabled = (state.adsPage + 1) * ADS_PAGE >= state.adsShown;
    for (const panel of [el('Panel'), el('FollowedPanel')])
      for (const control of panel.querySelectorAll('[data-client-action]')) control.disabled = locked || control.dataset.clientAction === 'needs-link';
  }
  function drawStatuses() {
    const target = el('Statuses'); target.replaceChildren();
    if (!state.statuses) { target.append(node('p', state.working ? 'Loading company statuses…' : 'Click Reload statuses to load company statuses.', 'job-leads-muted')); return; }
    // A saved status JobAdder no longer lists starts unticked, so saving drops it.
    if (!state.statusDraft) state.statusDraft = new Set(state.signed.filter(id => knownStatuses().has(id)));
    for (const status of state.statuses) {
      const label = node('label'), box = node('input');
      box.type = 'checkbox'; box.value = String(status.id); box.checked = state.statusDraft.has(status.id); box.dataset.clientAction = '';
      box.addEventListener('change', () => {
        if (box.checked) state.statusDraft.add(status.id); else state.statusDraft.delete(status.id);
        state.statusDirty = true; controls();
        if (unsavedStatuses()) message('Click Save statuses to list clients with your new ticks.');
      });
      label.append(box, node('span', status.name + (status.active ? '' : ' (inactive)')));
      target.append(label);
    }
    const stale = staleStatuses().length;
    if (stale) target.append(node('p', `${stale} saved status${stale === 1 ? ' is' : 'es are'} no longer in JobAdder. Save statuses to remove ${stale === 1 ? 'it' : 'them'}.`, 'job-leads-muted'));
  }
  function drawFollowed() {
    const target = el('Followed'); target.replaceChildren();
    el('FollowedEmpty').hidden = !!state.followed.length || !state.loaded;
    for (const client of state.followed) {
      const tr = node('tr'), id = knownId(client), canPull = eligible(client);
      const pick = node('td'), box = node('input');
      // 'needs-link' keeps the box disabled whenever controls() re-enables the rest.
      box.type = 'checkbox'; box.checked = canPull && !!state.chosen?.has(client.company_id); box.disabled = !canPull; box.dataset.clientAction = canPull ? '' : 'needs-link';
      box.setAttribute('aria-label', 'Pull job ads for ' + client.name);
      box.addEventListener('change', () => {
        if (box.checked && pullable().length >= MAX_PER_PULL) { box.checked = false; progress(`Tick up to ${MAX_PER_PULL} clients per pull.`); return; }
        if (box.checked) state.chosen.add(client.company_id); else state.chosen.delete(client.company_id);
        // A prepared LinkedIn search no longer matches the ticked clients.
        state.linkedinSearch = ''; drawLinkedIn();
        rememberTicks(); controls();
      });
      pick.append(box); tr.append(pick);
      const name = node('td'); name.append(link(client.name, client.jobadder_url, JOBADDER_URL)); tr.append(name);
      const page = node('td');
      if (client.linkedin_url) page.append(link('LinkedIn page', client.linkedin_url, COMPANY_URL));
      page.append(node('small', id || client.linkedin_url ? 'Ready' : 'Add its LinkedIn page'));
      const editor = node('details'), input = node('input');
      editor.append(node('summary', canPull ? 'Change link' : 'Add link'));
      editor.open=state.linkGuide===client.company_id;
      input.type = 'url'; input.maxLength = 2048; input.setAttribute('aria-label', 'LinkedIn link for ' + client.name);
      input.dataset.clientAction='';input.setAttribute('data-guide',String(!canPull && editor.open));
      editor.addEventListener('toggle',()=>{input.setAttribute('data-guide',String(!canPull && editor.open));if(!canPull && editor.open)input.focus?.();});
      editor.append(input, button('Save link', () => setLink(client, input.value)));
      page.append(editor); tr.append(page);
      tr.append(node('td', String(savedCount(client))), node('td', client.pulled_at ? client.pulled_at.slice(0, 10) : 'Never'));
      const actions = node('td'), unfollowButton = button('Unfollow', () => unfollow(client));
      unfollowButton.dataset.clientAction = ''; actions.append(unfollowButton); tr.append(actions);
      for (const control of editor.querySelectorAll('button')) control.dataset.clientAction = '';
      target.append(tr);
    }
  }
  function drawCompanies() {
    const target = el('Companies'), c = state.companies; target.replaceChildren();
    el('CompaniesPage').textContent = '';
    companyChoices('StatusFilter',(c?.rows || []).map(row=>row.status),'No status');
    companyChoices('OwnerFilter',(c?.rows || []).map(row=>row.owner),'Unassigned');
    if (!c) return;
    const visible=companyRows();
    if (!visible.length) { const tr = node('tr'), td = node('td', c.rows.length ? 'No clients match the filters on this page.' : c.next !== null ? 'No signed clients on this page.' : c.offset ? 'No more signed clients.' : 'No signed clients match.'); td.colSpan = 4; tr.append(td); target.append(tr); }
    for (const company of visible) {
      const tr = node('tr'), name = node('td'); name.append(link(company.name, company.jobadder_url, JOBADDER_URL));
      const followed = state.followed.some(row => row.company_id === company.company_id);
      const action = node('td'), control = followed ? button('Following · Unfollow', () => unfollow(company)) : button('Follow', () => follow(company), 'primary');
      control.dataset.clientAction = ''; action.append(control);
      tr.append(name, node('td', company.status || '—'), node('td', company.owner || '—'), action);
      target.append(tr);
    }
    el('CompaniesPage').textContent = c.rows.length ? `${visible.length} of ${c.rows.length} on this page · ${c.offset + 1}–${c.offset + c.returned}` + (c.total !== null ? ` of ${c.total}` : '') : '';
  }
  function drawFound() {
    const target = el('Found'); target.replaceChildren();
    el('Review').hidden = !state.found.length;
    el('FoundCount').textContent = String(state.found.length);
    state.foundPage = Math.min(state.foundPage, Math.max(0, Math.ceil(state.found.length / FOUND_PAGE) - 1));
    for (const row of pageRows()) {
      const tr = node('tr'), pick = node('td'), saved = savedJob(row.url);
      if (saved) { state.picked.delete(row.url); pick.append(node('small', saved.deleted ? 'In Trash' : 'Already in Job ads')); }
      else {
        const box = node('input'); box.type = 'checkbox'; box.checked = state.picked.has(row.url); box.dataset.clientAction = '';
        box.setAttribute('aria-label', 'Add ' + row.role);
        box.addEventListener('change', () => { if (box.checked) state.picked.add(row.url); else state.picked.delete(row.url); controls(); });
        pick.append(box);
      }
      const role = node('td'); role.append(link(row.role, row.url, JOB_URL));
      tr.append(pick, role, node('td', row.client_name), node('td', row.company), node('td', row.location || '—'), node('td', postedText(row)));
      target.append(tr);
    }
    el('FoundPage').textContent = state.found.length ? `${state.foundPage * FOUND_PAGE + 1}–${Math.min((state.foundPage + 1) * FOUND_PAGE, state.found.length)} of ${state.found.length}` : '';
  }
  // Saved client ads dashboard ---------------------------------------------

  function allClientAds() {
    if (adsIndex.records !== state.records || adsIndex.followed !== state.followed)
      adsIndex = {records:state.records, followed:state.followed, rows:clientAds(state.records, state.followed)};
    return adsIndex.rows;
  }
  const dayStart = days => { const d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() - days); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); };
  function adsRows() {
    // Folder choices are JSON strings, so Unfiled ("") differs from All folders ('').
    const client = el('AdsClient').value, status = el('AdsStatus').value, folder = el('AdsFolder').value;
    const days = Number(el('AdsPosted').value), since = days ? dayStart(days - 1) : '';
    const query = String(el('AdsQuery').value || '').trim().toLowerCase();
    const sorts = {posted_desc:['date_posted',-1], posted_asc:['date_posted',1], saved_desc:['created_at',-1], saved_asc:['created_at',1],
      role_asc:['role',1], company_asc:['company',1], client_asc:['client',1]};
    const [field, direction] = sorts[el('AdsSort').value] || sorts.posted_desc;
    const value = row => field === 'client' ? row.client.name : field === 'date_posted' ? postedOf(row.record) : row.record[field] || '';
    return allClientAds().filter(({record, client: owner}) =>
      (!client || String(owner.company_id) === client) && (!status || record.status === status) &&
      (!folder || JSON.stringify(record.folder || '') === folder) && (!since || postedOf(record) >= since) &&
      (!query || [record.role, record.company, record.location].some(text => String(text || '').toLowerCase().includes(query))))
      .sort((a, b) => {
        const x = value(a), y = value(b);
        if (!x || !y) { if (x || y) return x ? -1 : 1; }
        else { const difference = direction * compareText(x, y); if (difference) return difference; }
        return compareText(a.record.role, b.record.role) || compareText(a.record.url, b.record.url);
      });
  }
  function adsChoices(name, entries, all) {
    const select = el(name), old = select.value, option = (value, label) => { const n = node('option', label); n.value = value; return n; };
    select.replaceChildren(option(all[0], all[1]), ...entries.map(([value, label]) => option(value, label)));
    select.value = [all[0], ...entries.map(entry => entry[0])].includes(old) ? old : all[0];
  }
  function drawAds() {
    const every = allClientAds();
    const clients = new Map(every.map(row => [String(row.client.company_id), row.client.name]));
    adsChoices('AdsClient', [...clients].sort((a, b) => compareText(a[1], b[1])), ['', 'All clients']);
    adsChoices('AdsStatus', Object.entries(statusLabels()), ['', 'All statuses']);
    adsChoices('AdsFolder', [['', 'Unfiled'], ...state.folders.map(name => [name, name])].map(([name, label]) => [JSON.stringify(name), label]), ['', 'All folders']);
    // A just-created folder becomes the Move target once its option exists.
    const moveTo = el('AdsMoveFolder'), target0 = state.moveTo || moveTo.value; state.moveTo = '';
    moveTo.replaceChildren(...[['', 'Unfiled'], ...state.folders.map(name => [name, name])].map(([value, label]) => { const n = node('option', label); n.value = value; return n; }));
    moveTo.value = state.folders.includes(target0) ? target0 : '';
    const rows = adsRows(), target = el('AdsRows'); target.replaceChildren();
    // Actions apply only to ads the filters still show: a hidden ad is never
    // moved, deleted or scanned because of an earlier selection.
    const shownIds = new Set(rows.map(row => row.record.id));
    for (const id of [...state.adsPicked]) if (!shownIds.has(id)) state.adsPicked.delete(id);
    state.adsShown = rows.length; // controls() pages by this count without re-filtering
    el('AdsCount').textContent = String(every.length);
    state.adsPage = Math.min(state.adsPage, Math.max(0, Math.ceil(rows.length / ADS_PAGE) - 1));
    el('AdsEmpty').hidden = !!rows.length;
    el('AdsEmpty').textContent = !state.recordsReady ? 'Saved ads have not loaded yet. Click Refresh.' : every.length ? 'No ads match the filters.' : 'No saved client ads yet.';
    const shown = rows.slice(state.adsPage * ADS_PAGE, (state.adsPage + 1) * ADS_PAGE);
    state.adsPageIds = shown.map(row => row.record.id);
    for (const {record, client} of shown) {
      const tr = node('tr'), pick = node('td'), box = node('input'), role = node('td'), owner = node('td'), hr = node('td');
      box.type = 'checkbox'; box.checked = state.adsPicked.has(record.id); box.dataset.clientAction = '';
      box.setAttribute('aria-label', 'Select ' + record.role);
      box.addEventListener('change', () => { if (box.checked) state.adsPicked.add(record.id); else state.adsPicked.delete(record.id); controls(); });
      pick.append(box);
      role.append(link(record.role, record.url, JOB_URL)); owner.append(link(client.name, client.jobadder_url, JOBADDER_URL));
      if (record.hr) {
        // HR people are saved on the ad: they are listed (and their emails
        // unlocked) in the HR people tab, which feeds Unlocked contacts.
        const people = Array.isArray(record.hr.people) ? record.hr.people.length : 0;
        hr.append(node('span', `${people} found` + (record.hr.scanned_at ? ' · ' + String(record.hr.scanned_at).slice(0, 10) : '')));
        if (people) { const view = button('View', () => viewHR(record)); view.dataset.clientAction = ''; view.setAttribute('aria-label', 'View HR people for ' + record.company); hr.append(' ', view); }
      } else hr.textContent = 'Not scanned';
      tr.append(pick, node('td', postedText(record)), role, node('td', record.company), owner, node('td', record.location || '—'),
        node('td', statusLabels()[record.status] || record.status || '—'), node('td', record.folder || 'Unfiled'),
        node('td', String(record.created_at || '').slice(0, 10) || '—'), hr);
      target.append(tr);
    }
    el('AdsPage').textContent = rows.length ? `${state.adsPage * ADS_PAGE + 1}–${Math.min((state.adsPage + 1) * ADS_PAGE, rows.length)} of ${rows.length}` + (rows.length !== every.length ? ` (filtered from ${every.length})` : '') : '';
  }
  function drawLinkedIn() {
    el('LinkedInReady').hidden = !state.linkedinSearch;
    const a = el('LinkedInLink');
    if (state.linkedinSearch) a.href = state.linkedinSearch; else a.removeAttribute('href');
  }
  function drawFolders() {
    const select = el('Folder'), old = select.value; select.replaceChildren();
    const none = node('option', 'Unfiled'); none.value = ''; select.append(none);
    for (const name of state.folders) { const option = node('option', name); option.value = name; select.append(option); }
    select.value = state.folders.includes(old) ? old : '';
  }
  // The dashboard re-filters every saved ad, so it is drawn only when shown.
  function draw() { drawStatuses(); drawFollowed(); drawCompanies(); drawFound(); if (!el('FollowedPanel').hidden) drawAds(); drawLinkedIn(); controls(); }

  // Actions ------------------------------------------------------------------

  // `shared` work also touches Job Leads' saved ads, so it waits for Job Leads.
  async function work(task, shared = false) {
    if (mine()) return;
    if (shared && jobLeads()?.isBusy?.()) { message(BUSY_MESSAGE); return; }
    const token = generation; state.working = true; controls();
    try { await task(token); }
    catch (error) { if (token === generation) message(error.message); }
    finally {
      if (token === generation) { state.working = false; draw(); }
      if (resyncNeeded) { resyncNeeded = false; void resync(); }
    }
  }
  function accept(data, token) {
    // Ignore a reply for an earlier view of the page; a reply for another
    // JobAdder account first refreshes this page's account, then reloads.
    if (token !== generation) return false;
    if (!sameAccount(data.account)) { resyncNeeded = true; return false; }
    if (data.account) state.account = data.account;
    return true;
  }
  async function resync() {
    await syncAccount();
    clear();
    message('The JobAdder account changed. Loading this account\'s clients…');
    await load(true);
  }
  function setFollowed(rows) {
    const before = new Set(state.followed.map(row => row.company_id)), first = state.chosen === null;
    state.followed = rows;
    if(rows.some(client=>client.company_id===state.linkGuide && eligible(client)))state.linkGuide=0;
    if (first) {
      // Remembered ticks first; otherwise tick the first clients that can be pulled.
      const stored = storedTicks();
      state.chosen = new Set(stored ? stored.filter(id => rows.some(row => row.company_id === id)) : []);
      if (!stored) for (const client of rows) if (pullable().length < MAX_PER_PULL && eligible(client)) state.chosen.add(client.company_id);
    } else {
      for (const client of rows) if (!before.has(client.company_id) && pullable().length < MAX_PER_PULL && eligible(client)) state.chosen.add(client.company_id);
    }
    for (const id of [...state.chosen]) if (!rows.some(row => row.company_id === id)) state.chosen.delete(id);
    while (pullable().length > MAX_PER_PULL) state.chosen.delete(pullable().at(-1).company_id);
    rememberTicks();
  }
  async function refreshRecords(token = generation) {
    // Reads can overlap (a return-to-tab refresh and a save's refresh); only
    // the most recently started one may replace the saved ads.
    const read = ++recordsRead;
    applyRecords(await leads(), token, read);
  }
  function applyRecords(data, token, read) {
    if (token !== generation || read !== recordsRead) return;
    state.records = Array.isArray(data.records) ? data.records : [];
    state.recordsReady = true;
    state.folders = Array.isArray(data.folders) ? data.folders : [];
    drawFolders();
  }
  function load(retried = false) {
    return work(async token => {
      message('Loading your signed clients…');
      let recordsError='';
      const records=refreshRecords(token).catch(error=>{recordsError=error.message;});
      try {
        const overview = await call({action:'overview'});
        if (token === generation && !sameAccount(overview.account) && retried) {
          clear(); message('The JobAdder account changed. Reconnect JobAdder in Settings, then click Refresh.'); return;
        }
        if (!accept(overview, token)) return;
        state.signed = overview.signed || [];
        setFollowed(overview.followed || []);
        state.loaded = true; state.statusDraft = null; state.statusDirty = false;
        message(state.signed.length ? '' : 'Start in Signed clients: choose the statuses that mean a signed client.');
        if (!state.signed.length) el('Setup').open = true;
        draw(); // Followed clients must not wait for the unrelated ads read.
        let list = false;
        try {
          const data = await call({action:'statuses'});
          if (!accept(data, token)) return;
          state.statuses = data.statuses || []; state.signed = data.signed || state.signed; state.statusDraft = null; state.statusDirty = false;
          if (staleStatuses().length) { el('Setup').open = true; message('A saved signed status is no longer in JobAdder. Check the statuses and click Save statuses.'); }
          // A page reload starts with no browse results, even when followed
          // clients were restored. Read this list once on first open too.
          else list = !!state.signed.length && state.companies === null;
          draw(); // Show statuses even while saved ads are still loading.
        } catch (error) { if (token === generation) message(error.message + (state.followed.length ? ' Followed clients are still listed.' : '')); return; }
        if (!list) return;
        el('Browse').open = true; draw();
        try { await readCompanies(token, 0); }
        catch (error) { if (token === generation) message('Your signed clients could not be listed. ' + error.message); }
      } finally {
        await records;
        if (recordsError && token === generation) message(el('Message').textContent+' Saved ads could not be refreshed. '+recordsError);
      }
    });
  }
  function loadStatuses() {
    return work(async token => {
      const data = await call({action:'statuses'});
      if (!accept(data, token)) return;
      state.statuses = data.statuses || []; state.signed = data.signed || [];
      // Ticks the owner changed survive a reload (minus statuses JobAdder no
      // longer lists); untouched boxes show the saved choice, even one saved elsewhere.
      if (state.statusDraft && state.statusDirty) { const known = knownStatuses(); state.statusDraft = new Set([...state.statusDraft].filter(id => known.has(id))); }
      else { state.statusDraft = null; state.statusDirty = false; }
      const unsaved = unsavedStatuses();
      message(staleStatuses().length ? 'A saved signed status is no longer in JobAdder. Check the statuses and click Save statuses.'
        : unsaved ? 'Statuses reloaded from JobAdder. Your ticks are not saved yet: click Save statuses.' : 'Statuses reloaded from JobAdder.');
    });
  }
  function saveStatuses() {
    return work(async token => {
      const ids = [...(state.statusDraft || [])].sort((a, b) => a - b);
      const data = await call({action:'set_statuses', status_ids:ids, account:state.account});
      if (!accept(data, token)) return;
      state.signed = data.signed || ids; state.statusDraft = null; state.statusDirty = false; state.companies = null;
      if (!state.signed.length) { message('Saved. No status is chosen, so no company counts as a signed client until you choose one.'); return; }
      el('Browse').open = true; message('Saved. Loading your signed clients…'); draw();
      // The choice is saved even if the list cannot be read right now.
      try { await readCompanies(token, 0); } catch (error) { if (token === generation) message('Saved. ' + error.message); }
    });
  }
  // One page of signed clients from JobAdder, inside a running task.
  async function readCompanies(token, offset) {
    const data = await call({action:'companies', query:el('Query').value.trim(), offset});
    if (!accept(data, token)) return;
    const rows = data.companies || [], checked = Number.isSafeInteger(data.checked) ? data.checked : rows.length;
    state.companies = {rows, offset:data.offset || 0, total:data.total ?? null, next:data.next_offset ?? null, returned:checked};
    if (rows.length) message(rows.length === 1 ? '1 signed client found.' : `${rows.length} signed clients found.`);
    else message(state.companies.offset ? 'No more signed clients.' : 'No signed clients found. Check the statuses or the name.');
  }
  function searchCompanies(offset = 0) { return work(token => readCompanies(token, offset)); }
  function follow(company) {
    return work(async token => {
      const data = await call({action:'follow', company_id:company.company_id, account:state.account});
      if (!accept(data, token)) return;
      setFollowed(data.followed || []);
      const client = state.followed.find(row => row.company_id === company.company_id);
      state.linkGuide=client && !eligible(client)?client.company_id:0;
      message(client && eligible(client) ? `Following ${client.name}.` : `Following ${company.name}. Add its LinkedIn page in Followed clients.`);
    });
  }
  function unfollow(company) {
    return work(async token => {
      const data = await call({action:'unfollow', company_id:company.company_id, account:state.account});
      if (!accept(data, token)) return;
      setFollowed(data.followed || []);
      message(`Unfollowed ${company.name}. Its saved ads are kept.`);
    });
  }
  function setLink(client, value) {
    return work(async token => {
      const data = await call({action:'set_linkedin', company_id:client.company_id, link:String(value || '').trim(), account:state.account});
      if (!accept(data, token)) return;
      setFollowed(data.followed || []);
      const updated = state.followed.find(row => row.company_id === client.company_id);
      state.linkGuide=updated && !eligible(updated)?updated.company_id:0;
      if (updated && eligible(updated) && pullable().length < MAX_PER_PULL) { state.chosen.add(updated.company_id); rememberTicks(); }
      message(updated && eligible(updated) ? `${client.name} is ready to pull.` :
        `Saved. Add a LinkedIn company page to pull its ads.`);
    });
  }
  function refreshFollowed() {
    return work(async token => {
      const targets=[...state.followed];let checked=0,failed=0;const errors=[];
      state.refreshing=true;state.stopped=false;controls();
      try {
        for (const client of targets) {
          check(token);progress(`Checking JobAdder ${++checked} of ${targets.length}: ${client.name}…`);
          try {
            const data=await call({action:'refresh_linkedin',account:state.account,company_id:client.company_id,
              expected_url:client.linkedin_url || '',expected_id:client.linkedin_id || ''});
            if (!accept(data,token)) return;
            setFollowed(data.followed || []);draw();
          } catch(error) { if(token!==generation)return;failed++;errors.push(`${client.name}: ${error.message}`); }
          if(state.stopped)break;
        }
        if(token===generation)progress(`${state.stopped?'Stopped. ':''}${checked-failed} of ${targets.length} clients refreshed from JobAdder.`+
          (failed?` ${failed} could not be refreshed. ${errors.join(' ')}`:''));
      } finally {if(token===generation){state.refreshing=false;controls();}}
    });
  }
  function check(token) { if (state.stopped || token !== generation) throw Error('Stopped.'); }
  // Reads a client's numeric LinkedIn company from its company page through
  // the companion, once per page per session. A failed read is cancelled.
  async function resolveCompany(app, token, client, run) {
    state.resolving = true;
    try {
      const resolved = await app.rpc('jobCompanyID', {company_url:client.linkedin_url, operation_id:run}, 35000);
      check(token);
      if (resolved?.company_url !== client.linkedin_url || typeof resolved?.company_id !== 'string' || !/^[0-9]{1,24}$/.test(resolved.company_id))
        throw Error('LinkedIn did not confirm this company. Save its See all jobs search link and try again.');
      remember(client, resolved.company_id);
      return resolved.company_id;
    } catch (error) {
      try { await app.rpc('jobReadCancel', {operation_id:run}, 1500); } catch {}
      throw error;
    } finally { if (token === generation) state.resolving = false; }
  }
  // Pulls one client's company-filtered search. Returns whether every ad it
  // listed fitted in the review list.
  async function pullClient(app, token, client, pages, tally) {
    const run = hex();
    state.run = run;
    let complete = true;
    try {
      const companyId = knownId(client) || await resolveCompany(app, token, client, run);
      check(token);
      const source = await app.rpc('jobSearchBegin', {run_id:run, query:'', location:'', max_pages:pages, use_open:false, company_id:companyId});
      check(token);
      await window.cvStudioJobSearch.walk({rpc:app.rpc, run, tab:source.tab_id, pages, check:() => check(token),
        keep:snapshot => {
          const {added, dropped} = cleanJobs(snapshot, client, state.found);
          state.found.push(...added); tally.ads += added.length; if (dropped) complete = false;
          drawFound(); controls();
        },
        // A full list ends paging early, so this client was not fully pulled.
        full:() => { if (state.found.length < MAX_FOUND) return false; complete = false; return true; }});
      return complete;
    } finally {
      // This run is always ended here, even if the view was cleared meanwhile.
      if (state.run === run) state.run = '';
      try { await app.rpc('end', {run_id:run}); } catch {}
    }
  }
  async function pull() {
    const app = jobLeads();
    if (mine() || !app?.rpc || !window.cvStudioJobSearch) return;
    if (!state.signed.length || staleStatuses().length) { el('Setup').open=true;progress('Choose valid signed-client statuses in Signed clients and click Save statuses before pulling ads.');return; }
    if (!state.recordsReady) { progress('Saved ads have not loaded yet. Click Refresh before pulling ads.'); return; }
    if (app.isBusy?.()) { progress(BUSY_MESSAGE); return; }
    const pages = Number(el('Pages').value);
    if (![1, 2, 3, 5].includes(pages)) { progress('Choose the pages per client.'); return; }
    const targets = pullable();
    if (!targets.length) { progress('Tick at least one followed client that has a LinkedIn link.'); return; }
    if (targets.length > MAX_PER_PULL) { progress(`Pull up to ${MAX_PER_PULL} clients at a time. Untick some clients and try again.`); return; }
    if (state.found.length >= MAX_FOUND) { progress(`The review list is full (${MAX_FOUND} ads). Add or clear ads, then pull again.`); return; }
    const token = generation, activity = app.activityStart?.() ?? null, tally = {ads:0};
    let done = 0, failed = 0, skipped = 0, partial = 0, failure = '', dated = 0;
    const failures = [], empty = [];
    state.pulling = true; state.stopped = false; app.lock(true); controls();
    try {
      progress('Checking the browser companion…');
      const status = await app.rpc('jobStatus', {}, 1500).catch(() => null);
      check(token);
      if (!status?.connected) throw Error('Open this CV Studio address in Chrome or Brave with the companion enabled, then try again.');
      if (status.concurrent_scans_revision !== 1 || status.job_search !== true || status.job_search_company_revision !== 1)
        throw Error('Apply the latest companion update, then refresh CV Studio and LinkedIn to pull client ads. Updating CV Studio alone does not update the companion.');
      if (targets.some(client=>!linkedinId(client,state.records)) && status.job_search_company_link_revision!==1)
        throw Error('Apply the latest companion update to pull ads from a named company page.');
      if (status.busy) throw Error('Finish the current companion search or ad read first.');
      for (const [index, client] of targets.entries()) {
        check(token);
        // Never open another search once nothing more can be listed.
        if (state.found.length >= MAX_FOUND) { skipped = targets.length - index; break; }
        progress(`Pulling ${client.name} (${index + 1} of ${targets.length})…`);
        try {
          if (!await pullClient(app, token, client, pages, tally)) { partial++; continue; }
          done++;
          try { const data = await call({action:'pulled', company_id:client.company_id, account:state.account}); if (token === generation && sameAccount(data.account)) setFollowed(data.followed || state.followed); } catch {}
        } catch (error) {
          if (state.stopped || token !== generation) break;
          // A company with no open jobs on LinkedIn is a finished pull, not a failure.
          if (error.companionCode === 'HR_COMPANY_NO_JOBS') {
            done++; empty.push(client.name);
            try { const data = await call({action:'pulled', company_id:client.company_id, account:state.account}); if (token === generation && sameAccount(data.account)) setFollowed(data.followed || state.followed); } catch {}
            continue;
          }
          failed++; failures.push(`${client.name}: ${error.message}`);
        }
      }
      if (!state.stopped && token === generation) dated = await fillPostedDates(token);
    } catch (error) { if (!state.stopped && token === generation) failure = error.message; }
    finally {
      if (token === generation) {
        state.pulling = false; app.lock(false);
        const fresh = state.found.filter(row => !savedJob(row.url)).length, started = done || failed || partial || state.stopped;
        progress((state.stopped ? 'Stopped. ' : failure && !started ? '' : 'Finished. ') +
          (started ? `${done} client${done === 1 ? '' : 's'} pulled, ${tally.ads} ads found, ${fresh} new to review.` : '') +
          (partial || skipped ? ` The review list is full (${MAX_FOUND} ads): ${partial + skipped} client${partial + skipped === 1 ? ' was' : 's were'} not fully pulled. Add or clear ads, then pull again.` : '') +
          (empty.length ? ` No open jobs on LinkedIn: ${empty.join(', ')}.` : '') +
          (dated ? ` Posted dates added to ${dated} saved ad${dated === 1 ? '' : 's'}.` : '') +
          // Every client's reason is listed, not only the last one.
          (failed ? ` ${failed} could not be pulled: ${failures.join(' ')}` : '') + (failure ? ' ' + failure : ''));
        draw();
      }
      app.activityEnd?.(activity, !!(failure || failed));
    }
  }
  // Saved ads with no posted date take the date (or estimate) this pull just
  // read for the same ad. Nothing else in the saved ad changes.
  async function fillPostedDates(token) {
    let filled = 0;
    for (const row of state.found) {
      if (token !== generation || state.stopped) break;
      const record = savedJob(row.url);
      if (!record || record.deleted || record.date_posted || record.date_posted_estimate || !(row.date_posted || row.date_posted_estimate)) continue;
      const {created_at, updated_at, hr, ...fields} = record;
      try {
        await leads({action:'save', record:{...fields, date_posted:row.date_posted || '', date_posted_estimate:row.date_posted ? '' : row.date_posted_estimate}});
        filled++;
      } catch {} // a conflicting edit keeps the saved ad as it is
    }
    if (filled && token === generation) await refreshRecords(token);
    return filled;
  }
  function stop() {
    if (!state.pulling && !state.refreshing && !state.saving) return;
    state.stopped = true; controls(); progress(state.saving ? 'Stopping after the current save…' : 'Stopping after the current read…');
    if(state.resolving && state.run){try{void jobLeads()?.rpc?.('jobReadCancel',{operation_id:state.run}).catch(()=>{});}catch{}}
    if (state.run) { try { void jobLeads()?.rpc?.('end', {run_id:state.run}).catch(() => {}); } catch {} }
  }
  // Option 2: one visible LinkedIn search for the ticked clients. The owner
  // chooses ads there with the companion's Add to CV Studio buttons. Company
  // numbers that are not known yet are read once through the companion.
  function openSearch(url, opened) {
    state.linkedinSearch = url; drawLinkedIn();
    let tab = null;
    if (opened) { try { tab = window.open(url, '_blank', 'noopener,noreferrer'); } catch {} }
    return tab;
  }
  async function openLinkedIn() {
    if (mine()) return;
    if (!state.signed.length || staleStatuses().length) { el('Setup').open=true;progress('Choose valid signed-client statuses in Signed clients and click Save statuses first.');return; }
    const targets = pullable();
    if (!targets.length) { progress('Tick at least one followed client that has a LinkedIn link.'); return; }
    const missing = targets.filter(client => !knownId(client));
    if (!missing.length) {
      // Opened straight from the click, so the browser allows the new tab.
      openSearch(linkedinSearch(targets.map(knownId)), true);
      progress(`Opened LinkedIn for ${targets.length} client${targets.length === 1 ? '' : 's'}. Add ads there with Add to CV Studio.`);
      return;
    }
    const app = jobLeads();
    if (!app?.rpc) { progress('Open this CV Studio address in Chrome or Brave with the companion enabled, then try again.'); return; }
    if (app.isBusy?.()) { progress(BUSY_MESSAGE); return; }
    const token = generation, failures = [], empty = [];
    state.pulling = true; state.stopped = false; state.linkedinSearch = ''; app.lock(true); draw();
    try {
      progress('Checking the browser companion…');
      const status = await app.rpc('jobStatus', {}, 1500).catch(() => null);
      check(token);
      if (!status?.connected) throw Error('Open this CV Studio address in Chrome or Brave with the companion enabled, then try again.');
      if (status.job_search_company_link_revision !== 1) throw Error('Apply the latest companion update to read company numbers from LinkedIn company pages.');
      if (status.busy) throw Error('Finish the current companion search or ad read first.');
      for (const [index, client] of missing.entries()) {
        check(token);
        progress(`Finding ${client.name} on LinkedIn (${index + 1} of ${missing.length})…`);
        const run = hex(); state.run = run;
        try { await resolveCompany(app, token, client, run); }
        catch (error) {
          if (state.stopped || token !== generation) throw error;
          if (error.companionCode === 'HR_COMPANY_NO_JOBS') empty.push(client.name);
          else failures.push(`${client.name}: ${error.message}`);
        } finally { if (token === generation && state.run === run) state.run = ''; }
      }
      check(token);
      const ready = targets.filter(client => knownId(client));
      const none = empty.length ? ` No open jobs on LinkedIn: ${empty.join(', ')}.` : '';
      if (!ready.length) throw Error((empty.length && !failures.length ? 'None of the ticked clients has open jobs on LinkedIn right now.' : 'No ticked client has a confirmed LinkedIn company yet.') + none);
      // The click that started this has passed, so the browser may block a
      // new tab: the link below opens the search with one more click.
      openSearch(linkedinSearch(ready.map(knownId)), false);
      progress(`Ready for ${ready.length} client${ready.length === 1 ? '' : 's'}: click Open LinkedIn search.` + none +
        (failures.length ? ` ${failures.length} could not be included. ${failures.join(' ')}` : ''));
    } catch (error) {
      if (token === generation) progress((state.stopped ? 'Stopped. ' : '') + (state.stopped ? '' : error.message) + (failures.length ? ' ' + failures.join(' ') : ''));
    } finally {
      if (token === generation) { state.pulling = false; app.lock(false); draw(); }
    }
  }
  function addSelected() {
    if (!state.recordsReady) { progress('Saved ads have not loaded yet. Click Refresh before adding ads.'); return; }
    return work(async token => {
      const selected = state.found.filter(row => state.picked.has(row.url) && !savedJob(row.url));
      if (!selected.length) return;
      const folder = el('Folder').value;
      if (folder && !state.folders.includes(folder)) throw Error('This folder changed in another window. Choose a folder again.');
      let added = 0, skipped = 0, failure = '';
      state.saving = true; state.stopped = false; controls();
      try {
        for (const [index, row] of selected.entries()) {
          if (token !== generation) return;
          // Stop ends the batch between saves; an ad being saved is never cut off.
          if (state.stopped) break;
          progress(`Saving ${index + 1} of ${selected.length}…`);
          // The client the ad was pulled for groups it in Saved client job ads.
          const result = await leads({action:'save', record:{url:row.url, company:row.company, role:row.role, location:row.location, date_posted:row.date_posted,
            date_posted_estimate:row.date_posted ? '' : row.date_posted_estimate || '',
            description:row.description, description_rich:[], description_truncated:true, folder, status:'new', contact:'', notes:'', follow_up:'',
            ...(Number.isSafeInteger(row.client_id) && row.client_id > 0 && row.client_name ? {client:{company_id:row.client_id, name:String(row.client_name).slice(0, 200)}} : {})}});
          if (result.duplicate) skipped++; else added++;
          state.picked.delete(row.url);
        }
      } catch (error) { failure = error.message; }
      finally { if (token === generation) state.saving = false; }
      if (token !== generation) return;
      try { await refreshRecords(); await jobLeads()?.refresh?.(); } catch (error) { failure = failure || error.message; }
      const remaining = state.found.filter(row => state.picked.has(row.url) && !savedJob(row.url)).length;
      const text = (state.stopped ? 'Stopped. ' : '') + `Saved ${added} ad${added === 1 ? '' : 's'} to ${folder || 'Unfiled'}.` + (skipped ? ` ${skipped} were already saved; their details were kept.` : '') +
        (failure ? ` ${failure}` : '') + (remaining ? ` ${remaining} selected ad${remaining === 1 ? ' is' : 's are'} still waiting: click Save selected again.` : '');
      progress(''); message(text);
    }, true);
  }

  // Saved client ads: the same Job ads records and actions -------------------

  const pickedAds = () => allClientAds().filter(row => state.adsPicked.has(row.record.id)).map(row => row.record);
  const identities = records => records.map(record => ({id:record.id, revision:record.revision}));
  // Job ads shows the same records; both lists are re-read after a change.
  async function afterAdsChange(token, text) {
    // Job ads re-reads the store once; this view takes the same reply.
    try {
      const read = ++recordsRead, data = await jobLeads()?.refresh?.();
      if (Array.isArray(data?.records)) applyRecords(data, token, read); else await refreshRecords(token);
    } catch (error) { text += ' ' + error.message; }
    if (token === generation) message(text);
  }
  function moveAds() {
    return work(async token => {
      const records = pickedAds(), folder = el('AdsMoveFolder').value;
      if (!records.length) return;
      if (folder && !state.folders.includes(folder)) throw Error('This folder changed in another window. Choose a folder again.');
      await leads({action:'move_folder', folder, records:identities(records)});
      await afterAdsChange(token, `Moved ${records.length} ad${records.length === 1 ? '' : 's'} to ${folder || 'Unfiled'}.`);
    }, true);
  }
  function trashAds() {
    const records = pickedAds();
    if (!records.length || mine()) return;
    if (!window.confirm(`Move these ${records.length} saved ads to Trash? You can restore them from Trash in Job ads.`)) return;
    return work(async token => {
      await leads({action:'trash', records:identities(records)});
      for (const record of records) state.adsPicked.delete(record.id);
      await afterAdsChange(token, `Moved ${records.length} ad${records.length === 1 ? '' : 's'} to Trash.`);
    }, true);
  }
  function createAdsFolder() {
    return work(async token => {
      const result = await leads({action:'create_folder', folder:el('AdsFolderName').value});
      el('AdsFolderEditor').hidden = true; el('AdsFolderName').value = '';
      if (token === generation) state.moveTo = result.folder;
      await afterAdsChange(token, `Folder ${result.folder} created.`);
    }, true);
  }
  function deleteAdsFolder() {
    let folder = '';
    try { folder = JSON.parse(el('AdsFolder').value || '""'); } catch {}
    if (!folder || mine()) return;
    // Every ad in the folder (Trash included) moves to Unfiled; none is deleted.
    const affected = state.records.filter(record => record.folder === folder);
    if (!window.confirm(`Delete folder "${folder}"? Its ${affected.length} ads move to Unfiled. No ads are deleted.`)) return;
    return work(async token => {
      await leads({action:'delete_folder', folder, records:identities(affected)});
      if (token === generation) { el('AdsFolder').value = ''; state.adsPage = 0; }
      await afterAdsChange(token, `Folder ${folder} deleted. Its ads are now Unfiled.`);
    }, true);
  }
  // Find HR people runs Job ads' own scanner on the selected ads, with this
  // view's settings and progress panel. Results are saved on each ad.
  async function scanAdsHR() {
    const app = jobLeads(), ids = [...state.adsPicked];
    if (mine() || !ids.length || !app?.scanClientAds) return;
    if (app.isBusy?.() || app.hrRunning?.()) { message(BUSY_MESSAGE); return; }
    const token = generation;
    state.hrScanning = true; draw();
    try { await app.scanClientAds(ids); }
    catch (error) { if (token === generation) message(error.message); }
    finally {
      if (token === generation) { state.hrScanning = false; try { await refreshRecords(token); } catch {} draw(); }
    }
  }
  function viewHR(record) {
    show('');
    void window.cvStudioPeople?.showHR?.(String(record.hr?.company_id || ''));
  }

  // Views and account changes ------------------------------------------------

  // view: 'signed', 'followed' or '' (another Job Leads view is showing).
  function show(view) {
    el('Panel').hidden = view !== 'signed'; el('Tab').setAttribute('aria-pressed', String(view === 'signed'));
    el('FollowedPanel').hidden = view !== 'followed'; el('FollowedTab').setAttribute('aria-pressed', String(view === 'followed'));
    if (!view) return;
    if (view === 'followed') { drawAds(); controls(); }
    window.cvStudioPeople?.hideHR?.();
    for (const kind of ['Ads', 'Contacts']) {
      const panel = document.getElementById('jobLeadsApollo' + kind + 'Panel'), tab = document.getElementById('jobLeadsApollo' + kind + 'Tab');
      if (panel) panel.hidden = true; if (tab) tab.setAttribute('aria-pressed', 'false');
    }
    void load();
  }
  function clear() {
    // A different JobAdder account or a sign-out: drop every client, status
    // and pulled ad, and stop a running pull at its next step. The pull still
    // ends its own companion run when its current step returns.
    ++generation;
    if (state.pulling) { state.stopped = true; jobLeads()?.lock?.(false); }
    if (state.hrScanning) jobLeads()?.stopHR?.();
    const run = state.run;
    if(state.resolving && run){try{void jobLeads()?.rpc?.('jobReadCancel',{operation_id:run}).catch(()=>{});}catch{}}
    state = fresh();
    if (run) { try { void jobLeads()?.rpc?.('end', {run_id:run}).catch(() => {}); } catch {} }
    if (!ready) return;
    message(''); progress(''); el('Query').value = '';
    for (const name of ['StatusFilter','OwnerFilter','FollowingFilter'])el(name).value='';el('Sort').value='name_asc';draw();
  }
  window.clearJobLeadsClientsAccountState = clear;
  window.cvStudioJobLeadsClients = {words, sameCompany, linkedinId, savedAds, cleanJobs, linkedinSearch, clientAds, MAX_FOUND, MAX_PER_PULL};
  // Ads added on LinkedIn reach Job Leads directly; re-read them when the
  // owner comes back to this tab so Saved client ads stays current.
  function returned() {
    // focus and visibilitychange both fire on return: one read serves both.
    if (returning || document.hidden || el('FollowedPanel').hidden || mine() || !state.loaded) return;
    const token = generation;
    returning = refreshRecords(token).then(() => { if (token === generation && !mine()) draw(); }).catch(() => {}).finally(() => { returning = null; });
  }

  function init() {
    if (ready || !el('Panel')) return;
    ready = true;
    el('Tab').addEventListener('click', () => show('signed'));
    el('FollowedTab').addEventListener('click', () => show('followed'));
    for (const id of ['jobLeadsApolloAdsTab', 'jobLeadsApolloContactsTab', 'peopleHRTab']) document.getElementById(id)?.addEventListener('click', () => show(''));
    el('Refresh').addEventListener('click', () => load());
    el('FollowedRefresh').addEventListener('click', () => load());
    el('OpenLinkedIn').addEventListener('click', openLinkedIn);
    el('SelectAll').addEventListener('click', () => { if (mine()) return; for (const row of state.found) if (!savedJob(row.url)) state.picked.add(row.url); draw(); });
    el('SelectNone').addEventListener('click', () => { if (mine()) return; state.picked.clear(); draw(); });
    for (const name of ['AdsClient','AdsStatus','AdsFolder','AdsPosted','AdsSort']) el(name).addEventListener('change', () => { state.adsPage = 0; drawAds(); controls(); });
    el('AdsQuery').addEventListener('input', () => { state.adsPage = 0; drawAds(); controls(); });
    el('AdsReset').addEventListener('click', () => { for (const name of ['AdsClient','AdsStatus','AdsFolder','AdsPosted','AdsQuery']) el(name).value = ''; el('AdsSort').value = 'posted_desc'; state.adsPage = 0; drawAds(); controls(); });
    el('AdsSelectPage').addEventListener('change', () => { for (const id of state.adsPageIds) { if (el('AdsSelectPage').checked) state.adsPicked.add(id); else state.adsPicked.delete(id); } drawAds(); controls(); });
    el('AdsSelectAll').addEventListener('click', () => { if (mine()) return; for (const row of adsRows()) state.adsPicked.add(row.record.id); drawAds(); controls(); });
    el('AdsSelectNone').addEventListener('click', () => { if (mine()) return; state.adsPicked.clear(); drawAds(); controls(); });
    el('AdsMove').addEventListener('click', moveAds);
    el('AdsTrash').addEventListener('click', trashAds);
    el('AdsFolderNew').addEventListener('click', () => { if (!mine()) { el('AdsFolderEditor').hidden = false; el('AdsFolderName').focus?.(); } });
    el('AdsFolderCancel').addEventListener('click', () => { el('AdsFolderEditor').hidden = true; el('AdsFolderName').value = ''; });
    el('AdsFolderCreate').addEventListener('click', createAdsFolder);
    el('AdsFolderDelete').addEventListener('click', deleteAdsFolder);
    el('HRStart').addEventListener('click', scanAdsHR);
    el('HRStop').addEventListener('click', () => jobLeads()?.stopHR?.());
    el('AdsPrevious').addEventListener('click', () => { state.adsPage = Math.max(0, state.adsPage - 1); drawAds(); controls(); });
    el('AdsNext').addEventListener('click', () => { state.adsPage++; drawAds(); controls(); });
    window.addEventListener('focus', returned);
    document.addEventListener?.('visibilitychange', returned);
    el('RefreshFollowed').addEventListener('click',refreshFollowed);
    el('StatusesLoad').addEventListener('click', () => state.loaded ? loadStatuses() : load());
    el('StatusesSave').addEventListener('click', saveStatuses);
    el('Search').addEventListener('click', () => searchCompanies(0));
    for (const name of ['StatusFilter','OwnerFilter','FollowingFilter','Sort'])el(name).addEventListener('change',()=>{drawCompanies();controls();});
    el('FiltersReset').addEventListener('click',()=>{for(const name of ['StatusFilter','OwnerFilter','FollowingFilter'])el(name).value='';el('Sort').value='name_asc';drawCompanies();controls();});
    el('Query').addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault?.(); void searchCompanies(0); } });
    el('CompaniesPrevious').addEventListener('click', () => searchCompanies(Math.max(0, (state.companies?.offset || 0) - COMPANY_PAGE)));
    el('CompaniesNext').addEventListener('click', () => { if (state.companies?.next !== null) void searchCompanies(state.companies.next); });
    el('Pull').addEventListener('click', pull);
    el('Stop').addEventListener('click', stop);
    el('Untick').addEventListener('click', () => { if (!mine() && state.chosen) { state.chosen.clear(); state.linkedinSearch = ''; rememberTicks(); draw(); } });
    el('SelectNew').addEventListener('change', () => {
      for (const row of pageRows()) if (!savedJob(row.url)) { if (el('SelectNew').checked) state.picked.add(row.url); else state.picked.delete(row.url); }
      draw();
    });
    el('Add').addEventListener('click', addSelected);
    el('Clear').addEventListener('click', () => { if (!mine()) { state.found = []; state.picked.clear(); state.foundPage = 0; progress('Pulled ads cleared.'); draw(); } });
    el('FoundPrevious').addEventListener('click', () => { state.foundPage = Math.max(0, state.foundPage - 1); draw(); });
    el('FoundNext').addEventListener('click', () => { state.foundPage++; draw(); });
    window.addEventListener('pagehide', () => { if (state.pulling) stop(); });
    el('Panel').hidden = true; el('FollowedPanel').hidden = true; draw();
  }
  init();
})();
