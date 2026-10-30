/* Signed JobAdder clients in Job Leads. JobAdder is only read: the owner
 * follows a few signed clients, pulls their LinkedIn job ads through the
 * companion and adds the ads they choose to the main Job ads list. */
(() => {
  'use strict';
  const el = id => document.getElementById('jobLeadsClients' + id);
  const node = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; };
  const JOB_URL = /^https:\/\/www\.linkedin\.com\/jobs\/view\/[0-9]{1,24}$/;
  const COMPANY_URL = /^https:\/\/www\.linkedin\.com\/company\/[A-Za-z0-9_-]{1,100}\/$/;
  const JOBADDER_URL = /^https:\/\/[a-z0-9-]+(?:\.[a-z0-9-]+)*\.jobadder\.com\/companies\/[1-9][0-9]{0,9}$/;
  const LEGAL = new Set(['pt','tbk','sdn','bhd','berhad','pte','ltd','limited','inc','llc','corp','corporation','co','plc','gmbh','the']);
  const MAX_FOUND = 600, MAX_PER_PULL = 15, FOUND_PAGE = 50, ADD_LIMIT = 100, COMPANY_PAGE = 50;
  const fresh = () => ({account:'', signed:[], statuses:null, followed:[], records:[], folders:[], companies:null, found:[], picked:new Set(),
    chosen:null, foundPage:0, working:false, pulling:false, stopped:false, run:'', loaded:false, statusDraft:null});
  let state = fresh(), generation = 0, ready = false;

  // Pure helpers (exported for tests) ---------------------------------------

  function words(name) {
    return String(name || '').toLowerCase().normalize('NFKD').replace(/[^a-z0-9]+/g, ' ').split(' ').filter(word => word && !LEGAL.has(word));
  }
  function sameCompany(a, b) {
    const [short, long] = [words(a), words(b)].sort((x, y) => x.length - y.length);
    return short.length > 0 && short.every(word => long.includes(word));
  }
  // A followed client is pullable once its numeric LinkedIn company is known:
  // from JobAdder or a pasted link, or from an HR scan of the same company page.
  function linkedinId(client, records) {
    if (/^[0-9]{1,24}$/.test(client?.linkedin_id || '')) return client.linkedin_id;
    if (!COMPANY_URL.test(client?.linkedin_url || '')) return '';
    const match = (records || []).find(row => row?.hr?.company_url === client.linkedin_url && /^[0-9]{1,24}$/.test(row.hr.company_id || ''));
    return match ? match.hr.company_id : '';
  }
  function savedAds(client, records) {
    return (records || []).filter(row => !row.deleted && sameCompany(row.company, client.name)).length;
  }
  function savedJob(url, records) { return (records || []).find(row => row.url === url) || null; }
  function cleanJobs(snapshot, client, found) {
    if (!snapshot || !Array.isArray(snapshot.jobs) || snapshot.jobs.length > 40) throw Error('The job-search results could not be confirmed.');
    const added = [];
    for (const raw of snapshot.jobs) {
      const url = typeof raw?.url === 'string' ? raw.url : '';
      if (!JOB_URL.test(url) || typeof raw.company !== 'string' || !raw.company.trim() || typeof raw.role !== 'string' || !raw.role.trim()) continue;
      if (found.some(row => row.url === url) || added.some(row => row.url === url) || found.length + added.length >= MAX_FOUND) continue;
      added.push({url, role:raw.role.slice(0, 240), company:raw.company.slice(0, 200), location:typeof raw.location === 'string' ? raw.location.slice(0, 240) : '',
        date_posted:typeof raw.date_posted === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(raw.date_posted) ? raw.date_posted : '',
        description:typeof raw.description === 'string' ? raw.description.slice(0, 6500) : '', client_id:client.company_id, client_name:client.name});
    }
    return added;
  }

  // Transport ----------------------------------------------------------------

  async function call(body) {
    const response = await fetch('/jobadder/clients', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body), cache:'no-store'});
    let data = {};
    try { data = await response.json(); } catch {}
    if (!response.ok || data.ok === false || data.error) throw Error(data.error || data.message || 'The client list could not be loaded.');
    return data;
  }
  async function leads(body) {
    const response = await fetch('/job-leads', body ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)} : {cache:'no-store'});
    let data = {};
    try { data = await response.json(); } catch {}
    if (!response.ok || data.error) throw Error(data.error || 'Job Leads could not finish this request.');
    return data;
  }
  const jobLeads = () => window.cvStudioJobLeads;
  const namespace = () => String(window._jaAccountCacheNamespace || '');
  // The page's JobAdder account must still be the one the data was read for.
  function sameAccount(account) {
    const current = namespace();
    return !account || !current || current === 'ja' + account;
  }
  const message = text => { el('Message').textContent = text; };
  const progress = text => { el('Progress').textContent = text; };
  const hex = () => crypto.randomUUID().replaceAll('-', '');
  const pause = () => new Promise(resolve => setTimeout(resolve, 350));

  // Rendering ----------------------------------------------------------------

  function link(text, url, pattern) {
    const a = node('a', text);
    if (pattern.test(url || '')) { a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; }
    return a;
  }
  function button(text, action, cls = 'sec') {
    const b = node('button', text, cls); b.type = 'button'; b.addEventListener('click', action); return b;
  }
  // Reading clients never conflicts with Job Leads. Pulling (companion) and
  // adding (saved ads) also wait for Job Leads' own searches and saves.
  function mine() { return state.working || state.pulling; }
  function busy() { return mine() || !!jobLeads()?.isBusy?.(); }
  function controls() {
    const locked = mine(), signedNames = (state.statuses || []).filter(row => state.signed.includes(row.id)).map(row => row.name);
    el('Count').textContent = String(state.followed.length);
    el('Refresh').disabled = locked;
    el('SetupSummary').textContent = state.signed.length ? '· ' + (signedNames.length ? signedNames.join(', ') : state.signed.length + ' chosen') : '· not chosen yet';
    el('StatusesLoad').disabled = locked || !state.loaded;
    const draft = state.statusDraft;
    el('StatusesSave').disabled = locked || !draft || !draft.size || [...draft].sort().join() === [...state.signed].sort().join();
    el('Search').disabled = el('Query').disabled = locked || !state.loaded || !state.signed.length;
    const c = state.companies;
    el('CompaniesPrevious').disabled = locked || !c || c.offset === 0;
    el('CompaniesNext').disabled = locked || !c || c.next === null;
    const pullable = state.followed.filter(client => state.chosen?.has(client.company_id) && linkedinId(client, state.records));
    el('Pull').disabled = busy() || !pullable.length;
    el('Stop').disabled = !state.pulling || state.stopped;
    el('Pages').disabled = locked;
    const fresh = state.found.filter(row => !savedJob(row.url, state.records));
    el('SelectNew').disabled = locked || !fresh.length;
    el('SelectNew').checked = !!fresh.length && fresh.every(row => state.picked.has(row.url));
    el('Add').disabled = busy() || !fresh.some(row => state.picked.has(row.url));
    el('Clear').disabled = locked || !state.found.length;
    el('Folder').disabled = locked;
    el('FoundPrevious').disabled = locked || state.foundPage === 0;
    el('FoundNext').disabled = locked || (state.foundPage + 1) * FOUND_PAGE >= state.found.length;
    for (const control of el('Panel').querySelectorAll('[data-client-action]')) control.disabled = locked || control.dataset.clientAction === 'needs-link';
  }
  function drawStatuses() {
    const target = el('Statuses'); target.replaceChildren();
    if (!state.statuses) { target.append(node('p', state.loaded ? 'Statuses load from JobAdder…' : '', 'job-leads-muted')); return; }
    if (!state.statusDraft) state.statusDraft = new Set(state.signed);
    for (const status of state.statuses) {
      const label = node('label'), box = node('input');
      box.type = 'checkbox'; box.value = String(status.id); box.checked = state.statusDraft.has(status.id); box.dataset.clientAction = '';
      box.addEventListener('change', () => { if (box.checked) state.statusDraft.add(status.id); else state.statusDraft.delete(status.id); controls(); });
      label.append(box, node('span', status.name + (status.active ? '' : ' (inactive)')));
      target.append(label);
    }
  }
  function drawFollowed() {
    const target = el('Followed'); target.replaceChildren();
    el('FollowedEmpty').hidden = !!state.followed.length || !state.loaded;
    for (const client of state.followed) {
      const tr = node('tr'), id = linkedinId(client, state.records);
      const pick = node('td'), box = node('input');
      // 'needs-link' keeps the box disabled whenever controls() re-enables the rest.
      box.type = 'checkbox'; box.checked = !!id && !!state.chosen?.has(client.company_id); box.disabled = !id; box.dataset.clientAction = id ? '' : 'needs-link';
      box.setAttribute('aria-label', 'Pull job ads for ' + client.name);
      box.addEventListener('change', () => { if (box.checked) state.chosen.add(client.company_id); else state.chosen.delete(client.company_id); controls(); });
      pick.append(box); tr.append(pick);
      const name = node('td'); name.append(link(client.name, client.jobadder_url, JOBADDER_URL)); tr.append(name);
      const page = node('td');
      if (client.linkedin_url) page.append(link('LinkedIn page', client.linkedin_url, COMPANY_URL));
      page.append(node('small', id ? (client.linkedin_id ? 'Ready to pull' : 'Ready · company found in a saved HR scan') :
        client.linkedin_url ? 'Paste the link of its "See all jobs" search to pull ads' : 'Add its LinkedIn company page'));
      const editor = node('details'), input = node('input');
      editor.append(node('summary', client.linkedin_url || client.linkedin_id ? 'Change link' : 'Add link'));
      input.type = 'url'; input.maxLength = 2048; input.setAttribute('aria-label', 'LinkedIn link for ' + client.name);
      editor.append(input, button('Save link', () => setLink(client, input.value)));
      page.append(editor); tr.append(page);
      tr.append(node('td', String(savedAds(client, state.records))), node('td', client.pulled_at ? client.pulled_at.slice(0, 10) : 'Never'));
      const actions = node('td'), unfollowButton = button('Unfollow', () => unfollow(client));
      unfollowButton.dataset.clientAction = ''; actions.append(unfollowButton); tr.append(actions);
      for (const control of editor.querySelectorAll('button')) control.dataset.clientAction = '';
      target.append(tr);
    }
  }
  function drawCompanies() {
    const target = el('Companies'), c = state.companies; target.replaceChildren();
    el('CompaniesPage').textContent = '';
    if (!c) return;
    if (!c.rows.length) { const tr = node('tr'), td = node('td', c.offset ? 'No more signed clients.' : 'No signed clients match.'); td.colSpan = 4; tr.append(td); target.append(tr); }
    for (const company of c.rows) {
      const tr = node('tr'), name = node('td'); name.append(link(company.name, company.jobadder_url, JOBADDER_URL));
      const followed = state.followed.some(row => row.company_id === company.company_id);
      const action = node('td'), control = followed ? button('Following · Unfollow', () => unfollow(company)) : button('Follow', () => follow(company), 'primary');
      control.dataset.clientAction = ''; action.append(control);
      tr.append(name, node('td', company.status || '—'), node('td', company.owner || '—'), action);
      target.append(tr);
    }
    el('CompaniesPage').textContent = c.rows.length ? `${c.offset + 1}–${c.offset + c.returned}` + (c.total !== null ? ` of ${c.total}` : '') : '';
  }
  function drawFound() {
    const target = el('Found'); target.replaceChildren();
    el('Review').hidden = !state.found.length;
    el('FoundCount').textContent = String(state.found.length);
    state.foundPage = Math.min(state.foundPage, Math.max(0, Math.ceil(state.found.length / FOUND_PAGE) - 1));
    for (const row of state.found.slice(state.foundPage * FOUND_PAGE, (state.foundPage + 1) * FOUND_PAGE)) {
      const tr = node('tr'), pick = node('td'), saved = savedJob(row.url, state.records);
      if (saved) { state.picked.delete(row.url); pick.append(node('small', saved.deleted ? 'In Trash' : 'Already in Job ads')); }
      else {
        const box = node('input'); box.type = 'checkbox'; box.checked = state.picked.has(row.url); box.dataset.clientAction = '';
        box.setAttribute('aria-label', 'Add ' + row.role);
        box.addEventListener('change', () => { if (box.checked) state.picked.add(row.url); else state.picked.delete(row.url); controls(); });
        pick.append(box);
      }
      const role = node('td'); role.append(link(row.role, row.url, JOB_URL));
      tr.append(pick, role, node('td', row.client_name), node('td', row.company), node('td', row.location || '—'), node('td', row.date_posted || '—'));
      target.append(tr);
    }
    el('FoundPage').textContent = state.found.length ? `${state.foundPage * FOUND_PAGE + 1}–${Math.min((state.foundPage + 1) * FOUND_PAGE, state.found.length)} of ${state.found.length}` : '';
  }
  function drawFolders() {
    const select = el('Folder'), old = select.value; select.replaceChildren();
    const none = node('option', 'Unfiled'); none.value = ''; select.append(none);
    for (const name of state.folders) { const option = node('option', name); option.value = name; select.append(option); }
    select.value = state.folders.includes(old) ? old : '';
  }
  function draw() { drawStatuses(); drawFollowed(); drawCompanies(); drawFound(); controls(); }

  // Actions ------------------------------------------------------------------

  async function work(task, shared = false) {
    if (shared ? busy() : mine()) return;
    const token = generation; state.working = true; controls();
    try { await task(token); }
    catch (error) { if (token === generation) message(error.message); }
    finally { if (token === generation) { state.working = false; draw(); } }
  }
  function accept(data, token) {
    // Ignore a reply for an earlier account or an earlier view of the page.
    if (token !== generation) return false;
    if (!sameAccount(data.account)) { clear(); message('The JobAdder account changed. Click Refresh to load this account\'s clients.'); return false; }
    if (data.account) state.account = data.account;
    return true;
  }
  function setFollowed(rows) {
    const before = new Set(state.followed.map(row => row.company_id));
    state.followed = rows;
    state.chosen ||= new Set();
    for (const client of rows) if (!before.has(client.company_id) && linkedinId(client, state.records)) state.chosen.add(client.company_id);
    for (const id of [...state.chosen]) if (!rows.some(row => row.company_id === id)) state.chosen.delete(id);
  }
  async function refreshRecords() {
    const data = await leads();
    state.records = Array.isArray(data.records) ? data.records : [];
    state.folders = Array.isArray(data.folders) ? data.folders : [];
    drawFolders();
  }
  function load() {
    return work(async token => {
      message('Loading your signed clients…');
      const [overview] = await Promise.all([call({action:'overview'}), refreshRecords()]);
      if (!accept(overview, token)) return;
      state.signed = overview.signed || [];
      setFollowed(overview.followed || []);
      state.loaded = true; state.statusDraft = null;
      message(state.signed.length ? '' : 'Start by choosing which JobAdder statuses mean a signed client.');
      if (!state.signed.length) el('Setup').open = true;
      try {
        const data = await call({action:'statuses'});
        if (!accept(data, token)) return;
        state.statuses = data.statuses || []; state.signed = data.signed || state.signed; state.statusDraft = null;
      } catch (error) { if (token === generation) message(error.message + ' Followed clients are still listed.'); }
    });
  }
  function loadStatuses() {
    return work(async token => {
      const data = await call({action:'statuses'});
      if (!accept(data, token)) return;
      state.statuses = data.statuses || []; state.signed = data.signed || []; state.statusDraft = null;
      message('Statuses reloaded from JobAdder.');
    });
  }
  function saveStatuses() {
    return work(async token => {
      const ids = [...(state.statusDraft || [])].sort((a, b) => a - b);
      const data = await call({action:'set_statuses', status_ids:ids, account:state.account});
      if (!accept(data, token)) return;
      state.signed = data.signed || ids; state.statusDraft = null; state.companies = null;
      message('Saved. Search below to find your signed clients.');
      el('Browse').open = true;
    });
  }
  function searchCompanies(offset = 0) {
    return work(async token => {
      const data = await call({action:'companies', query:el('Query').value.trim(), offset});
      if (!accept(data, token)) return;
      state.companies = {rows:data.companies || [], offset:data.offset || 0, total:data.total ?? null, next:data.next_offset ?? null,
        returned:Math.max((data.next_offset ?? 0) - (data.offset || 0), (data.companies || []).length)};
      message(data.companies?.length ? '' : 'No signed clients found. Check the statuses or the name.');
    });
  }
  function follow(company) {
    return work(async token => {
      const data = await call({action:'follow', company_id:company.company_id, account:state.account});
      if (!accept(data, token)) return;
      setFollowed(data.followed || []);
      const client = state.followed.find(row => row.company_id === company.company_id);
      message(client && linkedinId(client, state.records) ? `Following ${client.name}.` : `Following ${company.name}. Add its LinkedIn company page to pull its ads.`);
    });
  }
  function unfollow(company) {
    return work(async token => {
      const data = await call({action:'unfollow', company_id:company.company_id, account:state.account});
      if (!accept(data, token)) return;
      setFollowed(data.followed || []);
      message(`Stopped following ${company.name}. Ads already in Job ads are kept.`);
    });
  }
  function setLink(client, value) {
    return work(async token => {
      const data = await call({action:'set_linkedin', company_id:client.company_id, link:String(value || '').trim(), account:state.account});
      if (!accept(data, token)) return;
      setFollowed(data.followed || []);
      const updated = state.followed.find(row => row.company_id === client.company_id);
      if (updated && linkedinId(updated, state.records)) state.chosen.add(updated.company_id);
      message(updated && linkedinId(updated, state.records) ? `${client.name} is ready to pull.` :
        `Saved. LinkedIn needs the company's number to list its ads: open the company page, click "See all jobs" and paste that link.`);
    });
  }
  function check(token) { if (state.stopped || token !== generation) throw Error('Stopped.'); }
  async function readPage(rpc, token, tab, previous = '') {
    for (let attempt = 0; attempt < 35; attempt++) {
      check(token);
      const result = await rpc('read', {run_id:state.run, tab_id:tab, method:'readJobSearch', values:[]});
      check(token);
      if (!result?.loading && (!previous || result.empty || result.signature !== previous)) return result;
      await pause();
    }
    throw Error('The LinkedIn results did not finish loading.');
  }
  async function pullClient(rpc, token, client, pages) {
    state.run = hex();
    let found = 0;
    try {
      const source = await rpc('jobSearchBegin', {run_id:state.run, query:'', location:'', max_pages:pages, use_open:false, company_id:linkedinId(client, state.records)});
      check(token);
      let previous = '';
      for (let page = 0; page < pages; page++) {
        let snapshot = await readPage(rpc, token, source.tab_id, previous);
        if (snapshot.empty) break;
        const keep = rows => { const added = cleanJobs(rows, client, state.found); state.found.push(...added); found += added.length; drawFound(); controls(); };
        keep(snapshot);
        for (let scroll = 0; scroll < 8 && !snapshot.atBottom; scroll++) {
          check(token);
          const moved = await rpc('read', {run_id:state.run, tab_id:source.tab_id, method:'scrollJobSearch', values:[snapshot.signature]});
          check(token); if (!moved) break;
          await pause(); snapshot = await readPage(rpc, token, source.tab_id); keep(snapshot);
        }
        if (page + 1 === pages || !snapshot.hasNext || state.found.length >= MAX_FOUND) break;
        previous = snapshot.signature; check(token);
        if (!await rpc('read', {run_id:state.run, tab_id:source.tab_id, method:'nextJobSearch', values:[previous]})) break;
      }
      return found;
    } finally {
      const run = state.run; state.run = '';
      if (run) { try { await rpc('end', {run_id:run}); } catch {} }
    }
  }
  async function pull() {
    const app = jobLeads();
    if (busy() || !app?.rpc) return;
    const pages = Number(el('Pages').value);
    if (![1, 2, 3, 5].includes(pages)) { progress('Choose the pages per client.'); return; }
    const targets = state.followed.filter(client => state.chosen?.has(client.company_id) && linkedinId(client, state.records));
    if (!targets.length) { progress('Tick at least one followed client that has a LinkedIn link.'); return; }
    if (targets.length > MAX_PER_PULL) { progress(`Pull up to ${MAX_PER_PULL} clients at a time. Untick some clients and try again.`); return; }
    const token = generation, activity = app.activityStart?.() ?? null;
    let done = 0, failed = 0, added = 0, failure = '';
    state.pulling = true; state.stopped = false; app.lock(true); controls();
    try {
      progress('Checking the browser companion…');
      const status = await app.rpc('jobStatus', {}, 1500).catch(() => null);
      check(token);
      if (!status?.connected) throw Error('Open this CV Studio address in Chrome or Brave with the companion enabled, then try again.');
      if (status.concurrent_scans_revision !== 1 || status.job_search !== true || status.job_search_company_revision !== 1)
        throw Error('Apply the latest companion update, then refresh CV Studio and LinkedIn to pull client ads. Updating CV Studio alone does not update the companion.');
      if (status.busy) throw Error('Finish the current companion search or ad read first.');
      for (const client of targets) {
        check(token);
        progress(`Pulling ${client.name} (${done + failed + 1} of ${targets.length})… Its LinkedIn search opens in a background tab.`);
        try {
          added += await pullClient(app.rpc, token, client, pages); done++;
          try { const data = await call({action:'pulled', company_id:client.company_id, account:state.account}); if (token === generation && sameAccount(data.account)) setFollowed(data.followed || state.followed); } catch {}
        } catch (error) {
          if (state.stopped || token !== generation) break;
          failed++; failure = `${client.name}: ${error.message}`;
        }
      }
    } catch (error) { if (!state.stopped && token === generation) failure = error.message; }
    finally {
      if (token === generation) {
        state.pulling = false; app.lock(false);
        const fresh = state.found.filter(row => !savedJob(row.url, state.records)).length;
        progress((state.stopped ? 'Stopped. ' : failure && !done ? '' : 'Finished. ') + (done || failed || state.stopped ? `${done} client${done === 1 ? '' : 's'} pulled, ${added} ads found, ${fresh} new to review.` : '') +
          (failed ? ` ${failed} could not be pulled.` : '') + (failure ? ' ' + failure : ''));
        draw();
      }
      app.activityEnd?.(activity, !!failure);
    }
  }
  function stop() { if (state.pulling) { state.stopped = true; controls(); progress('Stopping after the current step…'); } }
  function addSelected() {
    return work(async token => {
      const selection = state.found.filter(row => state.picked.has(row.url) && !savedJob(row.url, state.records));
      if (!selection.length) return;
      if (selection.length > ADD_LIMIT) throw Error(`Add up to ${ADD_LIMIT} ads at a time.`);
      const folder = el('Folder').value;
      if (folder && !state.folders.includes(folder)) throw Error('This folder changed in another window. Choose a folder again.');
      let added = 0, skipped = 0, failure = '';
      try {
        for (const row of selection) {
          if (token !== generation) return;
          const result = await leads({action:'save', record:{url:row.url, company:row.company, role:row.role, location:row.location, date_posted:row.date_posted,
            description:row.description, description_rich:[], description_truncated:true, folder, status:'new', contact:'', notes:'', follow_up:''}});
          if (result.duplicate) skipped++; else added++;
          state.picked.delete(row.url);
        }
      } catch (error) { failure = error.message; }
      if (token !== generation) return;
      try { await refreshRecords(); await jobLeads()?.refresh?.(); } catch (error) { failure = failure || error.message; }
      message(`Added ${added} ad${added === 1 ? '' : 's'} to ${folder || 'Unfiled'} in Job ads.` + (skipped ? ` ${skipped} were already saved; their details were kept.` : '') +
        (failure ? ` ${failure} Remaining ads stay selected.` : ''));
    }, true);
  }

  // Views and account changes ------------------------------------------------

  function show(visible) {
    el('Panel').hidden = !visible; el('Tab').setAttribute('aria-pressed', String(visible));
    if (!visible) return;
    window.cvStudioPeople?.hideHR?.();
    for (const kind of ['Ads', 'Contacts']) {
      const panel = document.getElementById('jobLeadsApollo' + kind + 'Panel'), tab = document.getElementById('jobLeadsApollo' + kind + 'Tab');
      if (panel) panel.hidden = true; if (tab) tab.setAttribute('aria-pressed', 'false');
    }
    void load();
  }
  function clear() {
    // A different JobAdder account or a sign-out: drop every client, status
    // and pulled ad, and stop a running pull at its next step.
    ++generation;
    if (state.pulling) { state.stopped = true; jobLeads()?.lock?.(false); }
    const run = state.run;
    state = fresh();
    if (run) { try { void jobLeads()?.rpc?.('end', {run_id:run}).catch(() => {}); } catch {} }
    if (!ready) return;
    message(''); progress(''); el('Query').value = ''; draw();
  }
  window.clearJobLeadsClientsAccountState = clear;
  window.cvStudioJobLeadsClients = {words, sameCompany, linkedinId, savedAds, cleanJobs, MAX_FOUND, MAX_PER_PULL};

  function init() {
    if (ready || !el('Panel')) return;
    ready = true;
    el('Tab').addEventListener('click', () => show(true));
    for (const id of ['jobLeadsApolloAdsTab', 'jobLeadsApolloContactsTab', 'peopleHRTab']) document.getElementById(id)?.addEventListener('click', () => show(false));
    el('Refresh').addEventListener('click', () => load());
    el('StatusesLoad').addEventListener('click', loadStatuses);
    el('StatusesSave').addEventListener('click', saveStatuses);
    el('Search').addEventListener('click', () => searchCompanies(0));
    el('Query').addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault?.(); void searchCompanies(0); } });
    el('CompaniesPrevious').addEventListener('click', () => searchCompanies(Math.max(0, (state.companies?.offset || 0) - COMPANY_PAGE)));
    el('CompaniesNext').addEventListener('click', () => { if (state.companies?.next !== null) void searchCompanies(state.companies.next); });
    el('Pull').addEventListener('click', pull);
    el('Stop').addEventListener('click', stop);
    el('SelectNew').addEventListener('change', () => {
      for (const row of state.found) if (!savedJob(row.url, state.records)) { if (el('SelectNew').checked) state.picked.add(row.url); else state.picked.delete(row.url); }
      draw();
    });
    el('Add').addEventListener('click', addSelected);
    el('Clear').addEventListener('click', () => { if (!mine()) { state.found = []; state.picked.clear(); state.foundPage = 0; progress('Pulled ads cleared. Ads already in Job ads are kept.'); draw(); } });
    el('FoundPrevious').addEventListener('click', () => { state.foundPage = Math.max(0, state.foundPage - 1); draw(); });
    el('FoundNext').addEventListener('click', () => { state.foundPage++; draw(); });
    window.addEventListener('pagehide', () => { if (state.pulling) state.stopped = true; });
    el('Panel').hidden = true; draw();
  }
  init();
})();
