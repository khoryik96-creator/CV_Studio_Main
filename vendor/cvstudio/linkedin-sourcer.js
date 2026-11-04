(function(){
  'use strict';
  const el = id => document.getElementById('liSourcer' + id);
  const hex = () => crypto.randomUUID().replaceAll('-', '');
  const channel = hex(), pending = new Map();
  let agent = null, run = null, abort = null, results = [], browserRun = '', busy = false, runOptions = null, setupSequence = 0;
  let folderBusy = false, folderChoice = '', companionUpdating = false, searchFailed = false;
  const folderPreference = 'cvstudio_linkedin_sourcer_folder';
  try { const value=sessionStorage.getItem(folderPreference);if(typeof value==='string' && value.length<=80 && !/[\x00-\x1f]/.test(value))folderChoice=value; } catch {}
  const guideNames = ['Brief','Consent','Pages','Calls','Source','Refresh','Start','Stop','SetupGuide','FolderName','FolderCreate','Boolean','CountryMode','CountryName','OpenSearch'];
  let guideIssue = '', guideTried = false, guideNotice = '';
  function guide(name = '', invalid = false, focus = false) {
    for (const key of guideNames) {
      el(key).setAttribute('data-guide', String(!busy && key === name));
      el(key).setAttribute('aria-invalid', String(!busy && invalid && key === name));
    }
    if (!busy && focus && name) {
      for (let parent = el(name).parentElement; parent; parent = parent.parentElement) if (parent.tagName === 'DETAILS') parent.open = true;
      el(name).focus();
    }
  }
  function nextGuide() {
    if(companionUpdating){guide();return;}
    let name = !busy && run && !run.stopped ? 'Stop' : guideIssue;
    if (!name) name = el('Brief').value.trim().length < 5 && !el('Boolean').value.trim() ? 'Brief' : !el('Consent').checked ? 'Consent' :
      el('CountryMode').value==='specific' && !el('CountryName').value.trim() ? 'CountryName' :
      !Number.isInteger(Number(el('Pages').value)) || Number(el('Pages').value) < 1 || Number(el('Pages').value) > 15 ? 'Pages' :
      !Number.isInteger(Number(el('Calls').value)) || Number(el('Calls').value) < 1 || Number(el('Calls').value) > 80 ? 'Calls' :
      !freshPeopleSearch() && !el('Source').value ? 'Refresh' : 'Start';
    guide(name, guideTried && ['Brief','Boolean','CountryName','Consent','Pages','Calls'].includes(name));
  }
  function invalidGuide(name) { guideNotice = el('Status').textContent; guide(name,true,true); }
  function tell(value) { el('Status').textContent = value; }
  function controls() {
    el('Panel').classList.toggle('is-running',busy);
    el('Panel').classList.toggle('has-error',!busy && searchFailed);
    el('Start').disabled = busy || folderBusy || companionUpdating; el('Stop').disabled = !busy && (!run || run.stopped);
    el('Export').disabled = !results.length; el('Clear').disabled = busy;
    for (const name of ['Brief', 'Boolean', 'CountryMode', 'CountryName', 'Mode', 'Pages', 'Calls', 'Source', 'OpenSearch', 'Consent', 'Refresh']) el(name).disabled = busy;
    for (const name of ['Folder','FolderNew','FolderName','FolderCreate','FolderCancel']) el(name).disabled = busy || folderBusy;
    el('Limits').textContent = `Up to ${el('Pages').value} pages · ${el('Calls').value} API requests.`;
    nextGuide();
  }
  function folderNotice(value) { el('FolderStatus').textContent=value;el('FolderStatus').hidden=!value; }
  function rememberFolder() { folderChoice=el('Folder').value;try{sessionStorage.setItem(folderPreference,folderChoice);}catch{} }
  function folderOption(value) { const option=document.createElement('option');option.value=value;option.textContent=value || 'Unfiled';return option; }
  async function readFolders(preferred=folderChoice) {
    const data=await api('/api/candidate_folders',{});
    if (!Array.isArray(data.folders) || data.folders.length>200 || data.folders.some(name=>typeof name!=='string' || !name || name.length>80)) throw Error('The candidate folder list could not be read.');
    el('Folder').replaceChildren(folderOption(''),...data.folders.map(folderOption));
    el('Folder').value=data.folders.includes(preferred)?preferred:'';rememberFolder();
    folderNotice(preferred && !folderChoice?'That folder no longer exists. Choose a folder before starting.':'');
  }
  async function refreshFolders() {
    if (busy || folderBusy) return;
    folderBusy=true;controls();
    try {await readFolders();}
    catch(error){folderNotice(error.message);}
    finally{folderBusy=false;controls();}
  }
  async function createFolder() {
    if (busy || folderBusy) return;
    const name=el('FolderName').value.trim();
    if (!name || name.length>80 || /[\x00-\x1f]/.test(name)) {folderNotice('Enter a folder name of up to 80 characters.');guide('FolderName',true,true);return;}
    folderBusy=true;controls();let created=false;
    try {
      const data=await api('/api/candidate_folder_create',{name});
      if(typeof data.folder!=='string' || !data.folder || data.folder.length>80)throw Error('The folder could not be confirmed. Refresh the folder list before trying again.');
      created=true;
      if(![...el('Folder').options].some(option=>option.value===data.folder))el('Folder').append(folderOption(data.folder));
      el('Folder').value=data.folder;rememberFolder();
      await readFolders(data.folder);el('FolderEditor').hidden=true;el('FolderName').value='';
      folderNotice(folderChoice===data.folder?'Folder created. New search results will save here.':'The folder changed before it could be selected. Choose a folder before starting.');
    }catch(error){folderNotice((created?'The folder was created, but its list could not be refreshed. ':'')+error.message);}
    finally{folderBusy=false;controls();}
  }
  const connectionHelp = 'Open this CV Studio page in Chrome or Brave with the companion enabled. It connects automatically. Use Set up companion if needed.';
  async function companionSetup() {
    const controller=new AbortController();let timer;
    try {
      // Bound headers AND JSON; fetch's global deadline ends at the headers.
      return await Promise.race([
        (async()=>{
          const response=await fetch('/linkedin-sourcer?action=companion_setup',{cache:'no-store',signal:controller.signal,timeout:10000});
          const setup=await response.json();
          if (!response.ok || typeof setup.folder !== 'string' || !/^\d+\.\d+\.\d+$/.test(setup.version || '')) throw Error('Companion setup could not be read. Update and restart CV Studio.');
          return setup;
        })(),
        new Promise((_,reject)=>{timer=setTimeout(()=>{reject(Error('CV Studio did not return its update details. Run Update & Restart, then try again.'));controller.abort();},8000);})
      ]);
    } finally {clearTimeout(timer);}

  }
  const companionNote = button => button.parentElement.querySelector('[data-companion-status]');
  window.copyLinkedinCompanionFolder = async function(button) {
    const note=companionNote(button);button.disabled=true;
    try {
      const setup=await companionSetup();
      // Always show a selectable path as well as attempting clipboard copy.
      // Embedded previews and older browsers may not provide Clipboard access.
      note.textContent=setup.folder;
      try { await navigator.clipboard.writeText(setup.folder);note.textContent='Folder copied: '+setup.folder; } catch {}
    } catch(error) { note.textContent=error.message; }
    finally { button.disabled=false; }
  };
  window.reloadLinkedinCompanion = async function(button) {
    const note=companionNote(button);
    if(companionUpdating){note.textContent='A companion update check is already running.';return;}
    if(busy){note.textContent='Stop the current search before updating the companion.';return;}
    companionUpdating=true;button.disabled=true;controls();note.textContent='Reading CV Studio update…';
    try {
      const setup=await companionSetup();
      note.textContent='Connecting to companion…';
      const status=await rpc('jobStatus',{},6000,'The companion did not reply. Refresh this CV Studio tab in Chrome or Brave, then click the companion toolbar icon once. If needed, reload it on the browser Extensions page.');
      if(status?.companion_update_revision!==1)throw Error('Use Set up companion once to replace the old downloaded copy with the CV Studio folder.');
      if(status.busy || status.other_busy)throw Error('Finish or stop both scans before updating the companion.');
      note.textContent='Applying companion update…';
      const result=await rpc('reloadCompanion',{version:setup.version},12000,'The companion update was not confirmed. Refresh CV Studio and LinkedIn, then check the companion version before trying again.');
      note.textContent=result?.current ? 'Your companion is up to date.' : result?.reloading ? 'Companion is reloading. Refresh CV Studio and LinkedIn when ready.' : 'Set up companion once using the CV Studio folder below.';
    } catch(error) { note.textContent=error.message; }
    finally { companionUpdating=false;button.disabled=false;controls(); }
  };
  function rpc(action, args = {}, waitMs = 12000, timeoutMessage = connectionHelp) {
    return new Promise((resolve, reject) => {
      const id = hex();
      const timer = setTimeout(() => { pending.delete(id); reject(Error(timeoutMessage)); }, waitMs);
      pending.set(id, {resolve, reject, timer});
      window.postMessage({type: 'CVSTUDIO_LINKEDIN_REQUEST', id, channel, scope:'profiles', action, args}, location.origin);
    });
  }
  window.addEventListener('message', event => {
    const data = event.data;
    if (event.source !== window || event.origin !== location.origin || data?.type !== 'CVSTUDIO_LINKEDIN_RESPONSE' || data.channel !== channel) return;
    const item = pending.get(data.id); if (!item) return;
    clearTimeout(item.timer); pending.delete(data.id);
    if (data.error) item.reject(Error(data.error)); else item.resolve(data.result);
  });
  async function api(path, body) {
    const action = path.split('/').pop();
    if (action === 'plan') {
      // Reserve the existing bounded browser run before spending on planning.
      // Another app tab becoming visible must not take an in-flight search.
      await begin();
      if (abort?.signal.aborted) throw Error('Stopped.');
    }
    const response = await fetch('/linkedin-sourcer', body ? {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({...body, action}), timeout: 145000} : {timeout: 10000});
    const value = await response.json();
    // Let an already-sent AI request finish even after Stop, so its usage can
    // still enter the existing accounting flow. Agent.check blocks next actions.
    if (responseHasPaidUsage(value)) {
      if (!response.ok || value.error) recordPaidAiFailure('LinkedIn Sourcer', value, 'deepseek-v4-flash', 'deepseek');
      else statsRecord('LinkedIn Sourcer', 'linkedin_sourcer', Number(value.cost || 0), value.model, '', 'deepseek', statsMetaFromResponse(value, value.model, 'deepseek'));
    }
    if (!response.ok || value.error) throw Error(value.error || 'Sourcing request failed.');
    if(value.dashboard_warning) el('DashboardWarning').textContent=value.dashboard_warning;
    if(action==='review') window.cvStudioPeople?.sourcerChanged();
    return value;
  }
  async function begin() {
    if (!run || abort?.signal.aborted) throw Error('Stopped.');
    if (browserRun === run.id) return;
    await rpc('begin', {run_id: run.id, source_tab_id: runOptions.source, mode: runOptions.mode, max_pages: runOptions.max_pages}); browserRun = run.id;
  }
  const browser = {
    async activeTab() {
      if (runOptions.openedSource) return runOptions.openedSource;
      const id = runOptions.source;
      const tabs = await rpc('tabs'); const selected = tabs.find(tab => tab.id === id);
      if (!selected) throw Error('Choose a LinkedIn search tab first.');
      if (CVLinkedinCore.profileURL(selected.url)) throw Error('Choose a LinkedIn search or home tab, rather than a profile page.');
      return selected;
    },
    async navigate(id, url) { await begin(); return rpc('navigate', {run_id: run.id, tab_id: id, url, fresh:!!CVLinkedinCore.profileURL(url)}); },
    async createTab(url) { await begin(); return rpc('create', {run_id: run.id, url}); },
    async closeOwnedTab() { if (browserRun) { try { await rpc('end', {run_id: browserRun}); } finally { browserRun = ''; } } },
    async read(id, method, values) {
      await begin();
      let reason='';
      for (let attempt = 0; attempt < (['setCountry','readProfile'].includes(method) ? 90 : 30); attempt++) {
        if (abort?.signal.aborted) throw Error('Stopped.');
        let value;
        try {value = await rpc('read', {run_id: run.id, tab_id: id, method, values,close_after_read:method==='readProfile'});}
        catch(error) {
          // A fixed reader failure for this detail page does not invalidate
          // its already assessed search card. Never suppress access, changed
          // identity, transport/disconnection, country or mutation errors.
          if(method==='readProfile' && error.message==='LinkedIn results could not be read. Refresh LinkedIn, then reload and reconnect the latest companion.')error.code='LI_PROFILE_NOT_READY';
          throw error;
        }
        if (abort?.signal.aborted) throw Error('Stopped.');
        // A navigation can finish without a script result. Retry reads only;
        // never repeat a search submission or pagination click after ambiguity.
        if (value == null) {
          if (!['readSearch','readProfile'].includes(method)) throw Error('LinkedIn did not confirm the browser action. Check its search tab before starting again.');
        }
        else if (!value.loading) return value;
        reason=value?.wait_reason || '';
        if(attempt===10 && method==='readProfile')tell('Waiting for the background LinkedIn profile… You can keep viewing Candidates.');
        await new Promise(resolve => setTimeout(resolve, 500));
      }
      if(method==='readProfile' && reason==='profile'){const error=Error('This background profile did not finish loading. Its search-card result was kept.');error.code='LI_PROFILE_NOT_READY';throw error;}
      if(reason==='country')throw Error('LinkedIn has not confirmed the selected country yet. Your results are kept. Check Locations in its search tab before starting again.');
      throw Error(method === 'setCountry' ? 'LinkedIn could not confirm the country in Locations. Check the country name and location menu in its search tab, then start again.' : 'LinkedIn results could not be read. Refresh LinkedIn, then reload and reconnect the latest companion.');
    }
  };
  function draw() {
    const target = el('Results'); target.replaceChildren(); el('Count').textContent = results.length;
    for (const row of results) {
      const card = document.createElement('article'); card.className = 'li-sourcer-result';
      const link = document.createElement('a'); link.href = CVLinkedinCore.profileURL(row.publicUrl) || CVLinkedinCore.profileURL(row.url);
      link.target = '_blank'; link.rel = 'noopener noreferrer'; link.textContent = row.name;
      const score = document.createElement('strong'); score.textContent = row.score + ' / 100';
      const heading = document.createElement('div'); heading.className = 'li-sourcer-result-head'; heading.append(link, score); card.append(heading);
      const source = document.createElement('p'); source.className = 'li-sourcer-muted';
      source.textContent = row.checked ? 'Profile detail read' : 'Search card only';
      if (!row.publicUrl && !/\/in\//.test(row.url)) source.textContent += ' · Recruiter link; login required';
      card.append(source);
      const list = document.createElement('ul'); for (const quote of row.evidence) { const item = document.createElement('li'); item.textContent = quote; list.append(item); }
      card.append(list);
      if (row.unknowns.length) { const missing = document.createElement('p'); missing.className = 'li-sourcer-muted'; missing.textContent = 'Still unknown: ' + row.unknowns.join(' · '); card.append(missing); }
      target.append(card);
    }
    if (!results.length) target.textContent = 'No people yet.';
    el('Usage').textContent = run ? `${run.calls} / ${run.max_calls} request attempts · ${run.tokens.toLocaleString()} reported tokens` + (run.usage_complete ? '' : ' · usage incomplete') : '';
    controls();
    try { sessionStorage.setItem('cvstudio_linkedin_sourcer', JSON.stringify({run, results})); } catch { tell('Session storage is unavailable. Export the current list before closing.'); }
  }
  function sourceMode(tab) {
    if (CVLinkedinCore.isSearchURL(tab.url,'standard')) return 'standard';
    if (CVLinkedinCore.isSearchURL(tab.url,'recruiter')) return /\blite\b/i.test(tab.title || '') ? 'lite' : 'recruiter';
    return 'standard';
  }
  const freshPeopleSearch = () => !el('OpenSearch').checked && ['auto','standard'].includes(el('Mode').value);
  async function discoverTabs() {
    const sequence = ++setupSequence;
    el('Connection').textContent = 'Checking your LinkedIn search…';
    try {
      const tabs = (await rpc('tabs',{},2500)).filter(tab => {
        if (CVLinkedinCore.profileURL(tab.url)) return false;
        const mode = el('Mode').value === 'auto' ? sourceMode(tab) : el('Mode').value;
        return CVLinkedinCore.isSearchURL(tab.url,mode) || !el('OpenSearch').checked && mode === 'standard' && /^https:\/\/www\.linkedin\.com\/(?:feed\/?)?(?:[?#]|$)/.test(tab.url);
      }).sort((a,b) => (b.lastAccessed || 0) - (a.lastAccessed || 0) || Number(b.active === true) - Number(a.active === true));
      if (sequence !== setupSequence) return null;
      const selected = el('Source').value; el('Source').replaceChildren();
      for (const tab of tabs) { const option = document.createElement('option'); option.value = String(tab.id); option.textContent = tab.title; el('Source').append(option); }
      if ([...el('Source').options].some(option => option.value === selected)) el('Source').value = selected;
      else if (tabs.length) el('Source').value = String(tabs[0].id);
      const source = tabs.find(tab => String(tab.id) === el('Source').value);
      guideIssue = '';
      el('Connection').textContent = freshPeopleSearch() ? 'Connected · a new People search will open each time you start.' : source ? 'Connected · ' + source.title + (el('OpenSearch').checked ? ' · keeping its filters' : ' · new search keywords') : 'Companion connected. Open a LinkedIn People or Recruiter search, then start. It will be detected automatically.';
      el('ConnectionHint').textContent = freshPeopleSearch() ? 'Country uses LinkedIn Locations. Your chosen country overrides prompt geography.' : el('OpenSearch').checked ? 'Your brief ranks the current results. Set location and other filters on LinkedIn first.' : 'For Recruiter, set Locations there. Use People search for automatic country selection.';
      if (!source && !freshPeopleSearch()) el('Options').open = true;
      nextGuide();
      return source;
    } catch (error) {
      if (sequence === setupSequence) { el('Connection').textContent = connectionHelp; el('Setup').open = true; guideIssue = 'SetupGuide'; nextGuide(); }
      throw error;
    }
  }
  window.refreshLinkedinSourcerTabs = async function() {
    if (busy) return;
    try { await discoverTabs(); } catch { /* Connection guidance is shown beside the brief. */ }
  };
  function countryControls() {el('CountryName').hidden=el('CountryMode').value!=='specific';}
  try {
    const saved=JSON.parse(sessionStorage.getItem('cvstudio_linkedin_sourcer_country') || 'null');
    if(saved && ['auto','any','specific'].includes(saved.mode) && typeof saved.country==='string' && saved.country.length<=100 && !/[\x00-\x1f\x7f]/.test(saved.country)) {
      el('CountryMode').value=saved.mode;el('CountryName').value=saved.country;
    }
  } catch {}
  countryControls();
  for(const name of ['CountryMode','CountryName'])el(name).addEventListener(name==='CountryMode'?'change':'input',()=>{
    countryControls();try{sessionStorage.setItem('cvstudio_linkedin_sourcer_country',JSON.stringify({mode:el('CountryMode').value || 'auto',country:el('CountryName').value.slice(0,100)}));}catch{}
  });
  for (const name of ['Mode','OpenSearch']) el(name).addEventListener('change',window.refreshLinkedinSourcerTabs);
  for (const name of ['Pages','Calls']) el(name).addEventListener('input',controls);
  el('Folder').addEventListener('change',()=>{rememberFolder();folderNotice('');});
  el('FolderNew').addEventListener('click',()=>{if(busy || folderBusy)return;el('FolderEditor').hidden=false;el('FolderName').value='';guide('FolderName',false,true);});
  el('FolderName').addEventListener('input',()=>guide(el('FolderName').value.trim()?'FolderCreate':'FolderName'));
  el('FolderName').addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();void createFolder();}});
  el('FolderCreate').addEventListener('click',createFolder);
  el('FolderCancel').addEventListener('click',()=>{el('FolderEditor').hidden=true;el('FolderName').value='';nextGuide();});
  document.getElementById('peopleSourcerSearchTab')?.addEventListener('click',()=>void refreshFolders());
  for (const name of ['Brief','Boolean','CountryMode','CountryName','Consent','Pages','Calls','Mode','OpenSearch','Source']) el(name).addEventListener(['Consent','Mode','CountryMode','OpenSearch','Source'].includes(name) ? 'change' : 'input', () => {
    if (guideNotice && el('Status').textContent === guideNotice) tell('');
    guideNotice = ''; guideIssue = ''; guideTried = false; nextGuide();
  });
  el('Source').addEventListener('change',() => { if (!busy) window.refreshLinkedinSourcerTabs(); });
  window.initLinkedinSourcer = async function() {
    if (!linkedinSourcerIsUnlocked() || !el('Brief') || busy) return;
    window.refreshLinkedinSourcerTabs();
    await refreshFolders();
    try {
      if (!agent && !busy && !results.length) { const saved = JSON.parse(sessionStorage.getItem('cvstudio_linkedin_sourcer') || 'null'); if (saved) { run = saved.run; results = saved.results || []; } }
      const state = await api('/api/status'); if (!busy) run = state.run;
      if (!state.configured) tell('Save your DeepSeek key in Settings first.');
      else if (run && !run.stopped && !busy) tell('A previous run was interrupted. Press Stop before starting again.');
      draw();
    } catch (error) { tell(error.message); }
  };
  window.startLinkedinSourcer = async function() {
    if (busy || folderBusy || companionUpdating) return;
    if (!requireLinkedinSourcerUnlocked()) return;
    guideIssue = ''; guideTried = true;
    const options = {brief: el('Brief').value.trim(), mode: el('Mode').value, max_pages: Number(el('Pages').value),
      max_calls: Number(el('Calls').value), confirm_paid: el('Consent').checked, use_open_search: el('OpenSearch').checked, folder:el('Folder').value,
      boolean_query:el('Boolean').value.trim(),country_mode:el('CountryMode').value || 'auto',country:el('CountryMode').value==='specific'?el('CountryName').value.trim():''};
    if (!options.confirm_paid) { tell('Tick “Use DeepSeek for this search” below your brief, then start.'); invalidGuide('Consent'); return; }
    if (options.brief.length < 5 && !options.boolean_query) { tell('Enter a prompt, a Boolean search, or both.'); invalidGuide('Brief'); return; }
    const booleanError=CVLinkedinCore.booleanQueryError(options.boolean_query,options.mode==='auto'?'standard':options.mode);
    if(booleanError){tell(booleanError);invalidGuide('Boolean');return;}
    if(options.country_mode==='specific' && !options.country){tell('Enter the country name.');invalidGuide('CountryName');return;}
    if(options.use_open_search && (options.boolean_query || options.country_mode!=='auto')){tell('Turn off Review open search in Search options to apply your Boolean or country selection.');invalidGuide('OpenSearch');return;}
    if(!['auto','standard'].includes(options.mode) && options.country_mode==='specific'){tell('Automatic country filters use LinkedIn People search. In Recruiter set Locations there and review the open search.');invalidGuide('Mode');return;}
    if (!Number.isInteger(options.max_pages) || options.max_pages < 1 || options.max_pages > 15 || !Number.isInteger(options.max_calls) || options.max_calls < 1 || options.max_calls > 80) { el('Options').open = true; tell('Choose 1–15 pages and 1–80 API requests in Search options.'); invalidGuide(!Number.isInteger(options.max_pages) || options.max_pages < 1 || options.max_pages > 15 ? 'Pages' : 'Calls'); return; }
    searchFailed = false; busy = true; abort = new AbortController(); browserRun = ''; draw();
    const activity = markTabRunning('linkedinsourcer',{acknowledgePrevious:true});
    let failed = false;
    try {
      tell('Finding your open LinkedIn search…');
      let source = await discoverTabs();
      if (abort.signal.aborted) throw Error('Stopped.');
      if (freshPeopleSearch()) {
        tell('Opening a new LinkedIn People search…');
        try { source = await rpc('openPeopleSearch'); }
        catch { throw Error('A new People search could not be opened. Reload and reconnect the latest companion, then try again.'); }
        if (abort.signal.aborted) throw Error('Stopped.');
        if (!source || !Number.isInteger(source.id) || !CVLinkedinCore.isSearchURL(source.url,'standard')) throw Error('The companion could not open a People search. Reload and reconnect the latest companion.');
        options.mode = 'standard';
      }
      if (!source) { guideIssue = 'Refresh'; throw Error('Open a LinkedIn People or Recruiter search in this browser, then start again. Your current candidate list is kept.'); }
      options.mode = options.mode === 'auto' ? sourceMode(source) : options.mode;
      const status=await rpc('jobStatus');
      if (status?.profile_browsing_revision !== 1 || status?.concurrent_scans_revision !== 1 || options.mode === 'standard' && (status?.people_results_revision !== 1 || !options.use_open_search && (status?.people_country_revision !== 1 || status?.people_country_ready_revision !== 1))) { guideIssue = 'SetupGuide'; el('Setup').open = true; }
      if(status?.profile_browsing_revision!==1)throw Error('Apply the latest companion update, then refresh CV Studio and LinkedIn to keep browsing safely during scans.');
      if(status?.concurrent_scans_revision!==1)throw Error('Apply the latest companion update, then refresh CV Studio and LinkedIn to run Job Leads and Sourcer together.');
      if(options.mode==='standard'){
        if(status?.people_results_revision!==1 || !options.use_open_search && (status?.people_country_revision!==1 || status?.people_country_ready_revision!==1))throw Error('Apply the latest companion update, then refresh CV Studio and LinkedIn. This search needs the current People-card, pagination and Locations readers.');
      }
      runOptions = {...options,source:source.id,openedSource:freshPeopleSearch() ? source : null};
      agent = new CVLinkedinCore.Agent({api, browser, signal: abort.signal, update: patch => {
        if (patch.run) run = patch.run; if (patch.results) results = patch.results; if (patch.status) tell(patch.status);
        if (patch.plan) el('Query').textContent = 'Search: ' + patch.plan.query + (patch.plan.country && !options.use_open_search ? ' · Location filter: ' + patch.plan.country : '');
        draw();
      }});
      await agent.start(options);
    }
    catch (error) { failed = !abort.signal.aborted; tell(abort.signal.aborted ? 'Stopped. Your current list is kept.' : error.message); }
    finally {
      if (browserRun) { try { await rpc('end', {run_id: browserRun}); } catch {} browserRun = ''; }
      searchFailed = failed; busy = false; abort = null; draw(); if(failed) markTabFailed('linkedinsourcer',activity,{forceBrowser:true}); else markTabDone('linkedinsourcer',activity,{forceBrowser:true});
    }
  };
  window.stopLinkedinSourcer = async function() {
    abort?.abort(); tell('Stopping. An AI request already sent may still finish; no new browser action will follow.');
    try { if (run) run = (await api('/api/stop', {run_id: run.id})).run; }
    catch (error) { tell(error.message); }
    if (browserRun) { try { await rpc('end', {run_id: browserRun}); } catch {} browserRun = ''; }
    draw();
  };
  window.exportLinkedinSourcer = function() {
    const url = URL.createObjectURL(new Blob([CVLinkedinCore.csv(results)], {type: 'text/csv;charset=utf-8'}));
    const link = document.createElement('a'); link.href = url; link.download = 'linkedin-candidates.csv'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 3000);
  };
  window.clearLinkedinSourcer = function() { if (!busy) { searchFailed = false; results = []; draw(); if(typeof clearTabActivityNotifications==='function')clearTabActivityNotifications('linkedinsourcer'); } };
  window.addEventListener('pagehide', () => {
    abort?.abort();
    if (run && !run.stopped) fetch('/linkedin-sourcer', {method: 'POST', keepalive: true,
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action: 'stop', run_id: run.id})}).catch(() => {});
  });
  window.addEventListener('DOMContentLoaded', () => {
    if (new URLSearchParams(location.search).get('module') === 'linkedinsourcer') switchTab('linkedinsourcer');
  });
})();
