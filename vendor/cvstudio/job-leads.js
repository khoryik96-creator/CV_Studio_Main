/* Job Leads: durable local records; the companion only fills a reviewable draft. */
(function () {
  'use strict';
  const el = id => document.getElementById('jobLeads' + id);
  const labels = {new:'New', to_contact:'To contact', contacted:'Contacted', follow_up:'Following up', won:'Won', closed:'Closed'};
  const fields = ['url', 'company', 'role', 'contact', 'location', 'date_posted', 'folder', 'status', 'follow_up', 'notes', 'description'];
  const hex = () => crypto.randomUUID().replaceAll('-', '');
  const channel = hex(), pending = new Map();
  const picked = new Set();
  const folderPreferenceKey = 'cvstudio_job_leads_folder';
  let preferredFolder = null;
  try {
    const stored = localStorage.getItem(folderPreferenceKey);
    if (stored !== null && stored.length <= 80 && !/[\x00-\x1f]/.test(stored) && !['*','!trash'].includes(stored)) preferredFolder = stored;
  } catch {}
  function rememberFolder(value) {
    preferredFolder = value;
    try { if (value === null) localStorage.removeItem(folderPreferenceKey); else localStorage.setItem(folderPreferenceKey,value); } catch {}
  }
  let folderNames = [];
  let discovered = [], discoveryPage = 0, discovering = false, discoveryStopped = false, discoveryRun = '';
  const discoveryPicked = new Set();
  let previewUrl = '';
  const receivedCaptures = new Map();
  let rows = [], editing = null, busy = false, dirty = false, page = 0, ready = false, lastReadUrl = '', descriptionTruncated = false, descriptionRich = [];
  const status = message => { el('Message').textContent = message; };
  function localDate() {
    const d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }
  const due = row => row.follow_up && row.follow_up <= localDate() && !['won', 'closed'].includes(row.status);
  function draft() { return {...Object.fromEntries(fields.map(key => [key, el(key).value])), description_truncated:descriptionTruncated, description_rich:descriptionRich}; }
  const richTags = new Set(['p','h3','h4','ul','ol','li','strong','em','br','blockquote']);
  function content(target, plain, rich) {
    target.replaceChildren();
    let count = 0;
    function add(parent, items, depth = 0) {
      if (!Array.isArray(items) || depth > 16) return;
      for (const item of items) {
        if (++count > 4000) return;
        if (typeof item?.text === 'string') parent.appendChild(document.createTextNode(item.text));
        else if (richTags.has(item?.tag)) {
          // Older captures used paragraph nodes for every nested LinkedIn div.
          // Flatten those wrappers at display time without rewriting saved ads.
          if (item.tag === 'p' && item.children?.some(child => ['p','h3','h4','ul','ol','blockquote'].includes(child.tag))) {
            let run = [];
            const flush = () => { if (run.some(child => child.tag || child.text?.trim())) { const p = document.createElement('p'); add(p,run,depth+1); parent.appendChild(p); } run = []; };
            for (const child of item.children) {
              if (['p','h3','h4','ul','ol','blockquote'].includes(child.tag)) { flush(); add(parent,[child],depth+1); }
              else run.push(child);
            }
            flush();
          } else { const child = document.createElement(item.tag); add(child, item.children, depth+1); parent.appendChild(child); }
        }
      }
    }
    if (Array.isArray(rich) && rich.length) add(target, rich);
    else if (plain) {
      // Preserve line breaks and wording; only explicit bullet markers become lists.
      let paragraph = null, list = null;
      for (const line of plain.replace(/\r\n?/g,'\n').split('\n')) {
        const bullet = line.match(/^\s*[•●▪◦‣*-]\s+(.+)$/);
        if (!line.trim()) { paragraph = null; list = null; continue; }
        if (bullet) {
          paragraph = null;
          if (!list) { list = document.createElement('ul'); target.appendChild(list); }
          const item = document.createElement('li'); item.textContent = bullet[1]; list.appendChild(item);
        } else {
          list = null;
          if (!paragraph) { paragraph = document.createElement('p'); target.appendChild(paragraph); }
          else paragraph.appendChild(document.createElement('br'));
          paragraph.appendChild(document.createTextNode(line));
        }
      }
    } else target.textContent = 'No job ad content yet. Fill from link or paste the description below.';
    target.className = 'job-lead-ad-content job-lead-rich';
  }
  function descriptionHint() {
    el('DescriptionNote').textContent = descriptionTruncated || el('description').value.length >= 20000 ? 'Captured excerpt. Open the LinkedIn ad for the complete content.' : 'This captured text is saved with the lead and can be read here later.';
    content(el('Content'), el('description').value, descriptionRich);
  }
  function fill(record) {
    fields.forEach(key => { el(key).value = record?.[key] || (key === 'status' ? 'new' : ''); });
    if (!record?.id) {
      if (preferredFolder !== null) el('folder').value = preferredFolder;
      else if (!['*','!trash',''].includes(el('FolderFilter').value)) el('folder').value = el('FolderFilter').value;
    }
    editing = record?.id ? record : null; dirty = false;
    lastReadUrl = record?.url || '';
    descriptionTruncated = record?.description_truncated === true; descriptionRich = record?.description_rich || []; descriptionHint();
    el('Created').textContent = record?.created_at ? 'Date created: ' + createdLabel(record.created_at) : 'Date created is recorded when you save this lead.';
    el('Heading').textContent = editing ? 'Edit lead' : 'Save a job ad';
    el('Save').textContent = editing ? 'Save changes' : 'Save lead';
  }
  function discard() { return !dirty || window.confirm('Discard the unsaved changes in this lead?'); }
  function lock(value) {
    busy = value;
    for (const id of ['Save', 'New', 'Read', 'Tabs', 'Refresh', 'Restore', 'AutoFill', 'BrowserFill', 'RefreshContent', 'Clear', 'ClearAll', 'FolderNew', 'FolderCreate', 'FolderCancel', 'FolderName', 'FolderDelete', 'Move', 'MoveFolder', 'SelectPage']) el(id).disabled = value;
    for (const name of fields) el(name).disabled = value;
    el('List').querySelectorAll('button').forEach(button => { button.disabled = value; });
    el('List').querySelectorAll('input').forEach(input => { input.disabled = value; });
    discoveryControls();
    if (!value) { updateClear(); updateSelection(); }
  }
  async function api(body) {
    const response = await fetch('/job-leads', body ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body), ...(body.action === 'lookup' ? {timeout:30000} : {})} : {});
    const data = await response.json();
    if (!response.ok || data.error) {
      const error = Error(data.error || 'Job Leads could not finish this request.');
      error.code = data.code; error.requestId = data.request_id;
      throw error;
    }
    return data;
  }
  async function load() {
    const data = await api(); rows = data.records; folderNames = data.folders || [];
    picked.clear(); syncFolders(); render();
    drawDiscovery();
  }
  function filtered() {
    const term = el('Search').value.trim().toLocaleLowerCase(), filter = el('Filter').value, folder = el('FolderFilter').value;
    return rows.filter(row => (folder === '!trash' ? row.deleted : !row.deleted && (folder === '*' || (row.folder || '') === folder)) &&
      (!filter || row.status === filter || filter === 'due' && due(row)) &&
      (!term || [row.company, row.role, row.contact, row.notes, row.location].some(value => value.toLocaleLowerCase().includes(term))));
  }
  function node(tag, text, className) {
    const value = document.createElement(tag); value.textContent = text;
    if (className) value.className = className;
    return value;
  }
  function postedLabel(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return 'Not available';
    const date = new Date(value + 'T00:00:00Z');
    return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat('en-GB', {day:'numeric', month:'short', year:'numeric', timeZone:'UTC'}).format(date) : 'Not available';
  }
  function createdLabel(value) {
    const date = new Date(value);
    return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat('en-GB', {day:'numeric', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit'}).format(date) : 'Not available';
  }
  function updateClear() {
    el('Clear').disabled = busy || el('FolderFilter').value === '!trash' || !filtered().length;
    el('ClearAll').disabled = busy || !rows.some(row => !row.deleted);
  }
  async function moveToTrash(selected, deleted, bulk = false) {
    if (busy || !selected.length) return;
    if (editing && selected.some(row => row.id === editing.id) && !discard()) return;
    if (bulk && !window.confirm(`Move these ${selected.length} saved ads to Trash? You can restore them later.`)) return;
    lock(true);
    try {
      await api({action:deleted ? 'trash' : 'untrash', records:selected.map(row => ({id:row.id, revision:row.revision}))});
      if (editing && selected.some(row => row.id === editing.id)) fill(null);
      await load(); status(deleted ? 'Moved to Trash. Choose Trash in the folder menu to restore.' : 'Lead restored to its folder.');
    } catch (error) { status(error.message); }
    finally { lock(false); }
  }
  function syncFolders() {
    const folder = el('FolderFilter').value;
    const folders = [...new Set([...folderNames, ...rows.map(row => row.folder).filter(Boolean)])].sort((a,b) => a.localeCompare(b));
    el('FolderFilter').replaceChildren(new Option('All folders', '*'), new Option('Unfiled', ''), new Option('Trash', '!trash'), ...folders.map(name => new Option(name, name)));
    el('FolderFilter').value = ['*','','!trash',...folders].includes(folder) ? folder : '*';
    el('Folders').replaceChildren(...folders.map(name => new Option(name, name)));
    const target = el('MoveFolder').value;
    el('MoveFolder').replaceChildren(new Option('Unfiled', ''), ...folders.map(name => new Option(name, name)));
    el('MoveFolder').value = folders.includes(target) ? target : '';
    const searchFolder = el('SearchFolder').value;
    el('SearchFolder').replaceChildren(new Option('Unfiled', ''), ...folders.map(name => new Option(name, name)));
    el('SearchFolder').value = folders.includes(searchFolder) ? searchFolder : '';
  }
  function updateSelection() {
    const visible = filtered().slice(page*40, (page+1)*40).filter(row => !row.deleted);
    el('SelectPage').disabled = busy || !visible.length;
    el('SelectPage').checked = !!visible.length && visible.every(row => picked.has(row.id));
    el('SelectPage').indeterminate = !el('SelectPage').checked && visible.some(row => picked.has(row.id));
    el('Selection').hidden = !picked.size;
    el('SelectedCount').textContent = picked.size + ' selected';
    el('Move').disabled = busy || !picked.size;
    el('FolderDelete').disabled = busy || ['*','','!trash'].includes(el('FolderFilter').value);
  }
  async function createFolder() {
    if (busy) return;
    const name = el('FolderName').value;
    lock(true);
    try {
      const result = await api({action:'create_folder', folder:name});
      await load(); el('FolderFilter').value = result.folder; page = 0; render();
      if (!editing && !dirty) fill(null);
      el('FolderEditor').hidden = true; el('FolderName').value = '';
      status('Folder created. Select saved ads to move them here, or save a new ad to this folder.');
    } catch (error) { status(error.message); }
    finally { lock(false); }
  }
  async function deleteFolder() {
    const folder = el('FolderFilter').value;
    if (busy || ['*','','!trash'].includes(folder)) return;
    const affected = rows.filter(row => row.folder === folder);
    const editingAffected = editing && affected.some(row => row.id === editing.id);
    if (editingAffected && !discard()) return;
    if (!window.confirm(`Delete folder "${folder}"? Its ${affected.length} ads will move to Unfiled, including any in Trash. No ads will be deleted.`)) return;
    lock(true);
    try {
      await api({action:'delete_folder', folder, records:affected.map(row => ({id:row.id, revision:row.revision}))});
      if (preferredFolder === folder) rememberFolder(null);
      await load();
      if (editingAffected) fill(null);
      else if (el('folder').value === folder) el('folder').value = '';
      status('Folder deleted. Its ads are kept in Unfiled; trashed ads remain in Trash.');
    } catch (error) { status(error.message); }
    finally { lock(false); }
  }
  async function moveSelected() {
    if (busy || !picked.size) return;
    const selection = rows.filter(row => picked.has(row.id));
    const editingAffected = editing && picked.has(editing.id);
    if (editingAffected && !discard()) return;
    const folder = el('MoveFolder').value;
    lock(true);
    try {
      await api({action:'move_folder', folder, records:selection.map(row => ({id:row.id, revision:row.revision}))});
      await load();
      if (editingAffected) fill(rows.find(row => row.id === editing.id));
      status(`Moved ${selection.length} selected ads to ${folder || 'Unfiled'}.`);
    } catch (error) { status(error.message); }
    finally { lock(false); }
  }
  function render() {
    const selected = filtered(), list = el('List'); list.replaceChildren();
    el('Total').textContent = String(rows.filter(row => !row.deleted).length);
    el('Due').textContent = String(rows.filter(row => !row.deleted && due(row)).length);
    updateClear();
    page = Math.min(page, Math.max(0, Math.ceil(selected.length / 40)-1));
    el('Count').textContent = selected.length ? `${page*40+1}–${Math.min((page+1)*40, selected.length)} of ${selected.length}` : '0 leads';
    el('Previous').disabled = page === 0; el('Next').disabled = (page+1)*40 >= selected.length;
    updateSelection();
    if (!selected.length) list.appendChild(node('p', rows.length ? 'No leads match these filters.' : 'Save your first LinkedIn job ad to start tracking opportunities.', 'job-leads-muted'));
    selected.slice(page*40, (page+1)*40).forEach(row => {
      const card = node('article', '', 'job-lead-card');
      card.append(node('h3', row.company), node('p', row.role, 'job-lead-role'));
      const meta = node('div', '', 'job-lead-meta');
      meta.append(node('span', labels[row.status], 'job-lead-status'));
      meta.append(node('span', 'Posted: ' + postedLabel(row.date_posted)));
      meta.append(node('span', 'Date created: ' + createdLabel(row.created_at)));
      meta.append(node('span', row.folder || 'Unfiled', 'job-lead-folder'));
      if (row.follow_up) meta.append(node('span', (due(row) ? 'Due · ' : 'Follow up · ') + row.follow_up, due(row) ? 'job-lead-due' : ''));
      card.appendChild(meta);
      if (row.contact) card.appendChild(node('p', 'Contact: ' + row.contact));
      if (row.location) card.appendChild(node('p', row.location, 'job-leads-muted'));
      if (row.notes) card.appendChild(node('p', row.notes.slice(0, 300) + (row.notes.length > 300 ? '…' : ''), 'job-lead-notes'));
      const actions = node('div', '', 'job-leads-actions');
      const link = node('a', 'Open LinkedIn ad'); link.href = row.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
      const edit = node('button', row.deleted ? 'Restore' : 'Edit / view details', 'sec'); edit.type = 'button'; edit.disabled = busy;
      edit.addEventListener('click', () => { if (row.deleted) return moveToTrash([row], false); if (!busy && discard()) { fill(row); status('Editing saved lead.'); el('Form').scrollIntoView({block:'start', behavior:'smooth'}); } });
      actions.append(link, edit); card.appendChild(actions); list.appendChild(card);
      if (!row.deleted) { const remove = node('button', 'Delete', 'sec job-lead-delete'); remove.type = 'button'; remove.disabled = busy; remove.addEventListener('click', () => moveToTrash([row], true)); actions.appendChild(remove); }
      if (!row.deleted) {
        const pick = node('label', '', 'job-lead-select'), checkbox = node('input');
        checkbox.type = 'checkbox'; checkbox.checked = picked.has(row.id); checkbox.disabled = busy;
        checkbox.setAttribute('aria-label', 'Select ' + row.company + ' — ' + row.role);
        checkbox.addEventListener('change', () => { if (busy) return; if (checkbox.checked) picked.add(row.id); else picked.delete(row.id); updateSelection(); });
        pick.append(checkbox, document.createTextNode('Select')); card.appendChild(pick);
      }
      const details = node('details', '', 'job-lead-ad');
      details.appendChild(node('summary', 'View more — job ad content'));
      if (row.description) {
        if (row.description_truncated || row.description.length >= 20000) details.appendChild(node('p', 'Captured excerpt. Open the LinkedIn ad for the complete content.', 'job-leads-muted'));
        const body = node('div', '', 'job-lead-ad-content'); content(body, row.description, row.description_rich); details.appendChild(body);
        if (!row.description_rich?.length) details.appendChild(node('p', 'Plain-text capture. To refresh its original formatting, use Edit / view details → Refresh ad content, then save.', 'job-leads-muted'));
      } else details.appendChild(node('p', 'No job description was saved. Open the LinkedIn ad, or use Edit / view details and Fill from link, then save.', 'job-leads-muted'));
      card.appendChild(details);
    });
  }
  const searchStatus = value => { el('SearchStatus').textContent = value; };
  const savedJob = url => rows.find(row => jobLink(row.url) === url);
  function discoveryControls() {
    for (const name of ['SearchStart','SearchRefresh','SearchMode','SearchQuery','SearchLocation','SearchPages','SearchSource','SearchFolder','SearchClear']) el(name).disabled = busy;
    el('SearchStop').disabled = !discovering || discoveryStopped;
    el('SearchOpen').hidden = el('SearchMode').value !== 'open';
    const visible = discovered.slice(discoveryPage*20, (discoveryPage+1)*20).filter(row => !savedJob(row.url));
    el('SearchSelectPage').disabled = busy || !visible.length;
    el('SearchSelectPage').checked = !!visible.length && visible.every(row => discoveryPicked.has(row.url));
    el('SearchSelectPage').indeterminate = !el('SearchSelectPage').checked && visible.some(row => discoveryPicked.has(row.url));
    el('SearchAdd').disabled = busy || !discovered.some(row => discoveryPicked.has(row.url) && !savedJob(row.url));
    el('SearchPrevious').disabled = busy || discoveryPage === 0;
    el('SearchNext').disabled = busy || (discoveryPage+1)*20 >= discovered.length;
    el('SearchResults').querySelectorAll('button').forEach(button => { button.disabled = busy; });
    el('SearchResults').querySelectorAll('input').forEach(input => { input.disabled = busy || !!savedJob(input.value); });
    const preview = discovered.find(row => row.url === previewUrl);
    el('PreviewRead').disabled = busy || !preview;
    el('PreviewSave').disabled = busy || !preview || !!savedJob(preview.url);
    el('PreviewSave').textContent = preview && savedJob(preview.url) ? 'Already saved' : 'Add this ad';
  }
  function drawPreview() {
    const row = discovered.find(value => value.url === previewUrl);
    el('PreviewTitle').textContent = row?.role || 'Choose an ad to preview';
    el('PreviewCompany').textContent = row?.company || '';
    el('PreviewMeta').textContent = row ? [row.location,row.full ? 'Captured ad content' : 'Search summary · Read full ad for the description',row.description_truncated ? 'Excerpt' : ''].filter(Boolean).join(' · ') : '';
    content(el('PreviewContent'),row?.description || 'Your search results will appear here. Preview an ad, then add it or select several to save together.',row?.description_rich);
  }
  function drawDiscovery() {
    const target = el('SearchResults'); target.replaceChildren();
    discoveryPage = Math.min(discoveryPage, Math.max(0,Math.ceil(discovered.length/20)-1));
    if (!discovered.some(row => row.url === previewUrl)) previewUrl = discovered[0]?.url || '';
    el('SearchCount').textContent = `${discovered.length} found · ${discoveryPicked.size} selected`;
    for (const row of discovered.slice(discoveryPage*20, (discoveryPage+1)*20)) {
      const card = node('article','','job-leads-discovery-card' + (row.url === previewUrl ? ' is-previewing' : ''));
      card.append(node('h3',row.role),node('p',row.company),node('p',row.location || '', 'job-leads-muted'));
      card.append(node('p',row.full ? 'Full ad captured' : 'Search summary only', 'job-leads-muted'));
      const saved = savedJob(row.url), actions = node('div','','job-leads-actions');
      if (saved) { discoveryPicked.delete(row.url); actions.append(node('span',saved.deleted ? 'Already in Trash' : 'Already saved', 'job-leads-muted')); }
      else {
        const pick = node('label','','job-leads-pick'), input = node('input');
        input.type = 'checkbox'; input.value = row.url; input.checked = discoveryPicked.has(row.url);
        input.setAttribute('aria-label','Select found ad ' + row.company + ' — ' + row.role);
        input.addEventListener('change', () => { if (busy) return; if (input.checked) discoveryPicked.add(row.url); else discoveryPicked.delete(row.url); drawDiscovery(); });
        pick.append(input,document.createTextNode('Select')); actions.append(pick);
      }
      const link = node('a','Open on LinkedIn'); link.href = row.url; link.target = '_blank'; link.rel = 'noopener noreferrer'; actions.append(link);
      const preview = node('button','Preview','sec'); preview.type = 'button'; preview.addEventListener('click',() => { if (busy) return; previewUrl = row.url; drawDiscovery(); el('Preview').scrollIntoView({block:'nearest',behavior:'smooth'}); }); actions.append(preview);
      const read = node('button','Read full ad','sec'); read.type = 'button'; read.addEventListener('click', () => previewDiscovered(row)); actions.append(read);
      card.append(actions);
      const details = node('details'), summary = node('summary',row.full ? 'View job ad content' : 'View search summary');
      details.append(summary); const body = node('div'); content(body,row.description,row.description_rich); details.append(body); card.append(details);
      target.append(card);
    }
    if (!discovered.length) target.append(node('p','Search LinkedIn to find ads here.','job-leads-muted'));
    el('SearchCount').textContent = `${discovered.length} found · ${discoveryPicked.size} selected`;
    drawPreview(); discoveryControls();
  }
  function rememberJobs(snapshot) {
    if (!snapshot || !Array.isArray(snapshot.jobs) || snapshot.jobs.length > 40) throw Error('The job-search results could not be confirmed.');
    for (const raw of snapshot.jobs) {
      const url = jobLink(raw?.url || '');
      if (!url || url !== raw.url || typeof raw.company !== 'string' || !raw.company.trim() || typeof raw.role !== 'string' || !raw.role.trim()) continue;
      if (discovered.some(row => row.url === url) || discovered.length >= 600) continue;
      discovered.push({url,company:raw.company.slice(0,200),role:raw.role.slice(0,240),location:typeof raw.location === 'string' ? raw.location.slice(0,240) : '',
        date_posted:typeof raw.date_posted === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(raw.date_posted) ? raw.date_posted : '',
        description:typeof raw.description === 'string' ? raw.description.slice(0,6500) : '',description_truncated:true,description_rich:[],full:false});
    }
    drawDiscovery();
  }
  function checkDiscovery() { if (discoveryStopped) throw Error('Stopped.'); }
  const pauseDiscovery = () => new Promise(resolve => setTimeout(resolve,350));
  async function readDiscovery(tab, previous = '') {
    for (let attempt=0;attempt<35;attempt++) {
      checkDiscovery();
      const result = await rpc('read',{run_id:discoveryRun,tab_id:tab,method:'readJobSearch',values:[]});
      checkDiscovery();
      if (!result?.loading && (!previous || result.empty || result.signature !== previous)) return result;
      await pauseDiscovery();
    }
    throw Error('The job-search page did not finish changing. The ads already found are kept.');
  }
  async function startDiscovery() {
    if (busy) return;
    const pages = Number(el('SearchPages').value), useOpen = el('SearchMode').value === 'open';
    const query = el('SearchQuery').value.trim(), where = el('SearchLocation').value.trim();
    if (!Number.isInteger(pages) || pages < 1 || pages > 15) { searchStatus('Choose 1 to 15 pages.'); return; }
    if (!useOpen && (!query || query.length > 240 || where.length > 160 || /[\x00-\x1f]/.test(query + where))) { searchStatus('Enter job keywords and an optional location.'); return; }
    if (useOpen && !el('SearchSource').value) { searchStatus('Refresh search tabs and choose an open LinkedIn job search.'); return; }
    discovering = true; discoveryStopped = false; discoveryRun = '';
    lock(true); searchStatus('Checking the browser companion…');
    try {
      const companion = await rpc('jobStatus',{},1000).catch(() => null);
      checkDiscovery();
      if (!companion?.connected) throw Error('The companion is not connected to this tab. Open this CV Studio address in Chrome, reload the latest companion and click its toolbar icon. LinkedIn job search cannot run inside the Codex preview.');
      if (companion.job_search !== true || !Number.isInteger(companion.job_search_revision) || companion.job_search_revision < 1) throw Error('Update and reload the latest companion, refresh CV Studio and LinkedIn, then reconnect this tab to enable the current job search. Updating CV Studio alone does not update the companion.');
      if (companion.busy) throw Error('Finish the current companion search or ad read before starting another search.');
      discoveryRun = hex(); discovered = []; discoveryPicked.clear(); discoveryPage = 0;
      drawDiscovery(); searchStatus('Opening the LinkedIn job search in Chrome…');
      const source = await rpc('jobSearchBegin',{run_id:discoveryRun,query,location:where,max_pages:pages,use_open:useOpen,source_tab_id:Number(el('SearchSource').value)});
      checkDiscovery();
      let previous = '';
      for (let index=0;index<pages;index++) {
        let snapshot = await readDiscovery(source.tab_id,previous);
        if (snapshot.empty) break;
        rememberJobs(snapshot);
        for (let scroll=0;scroll<8 && !snapshot.atBottom;scroll++) {
          checkDiscovery();
          const moved = await rpc('read',{run_id:discoveryRun,tab_id:source.tab_id,method:'scrollJobSearch',values:[snapshot.signature]});
          checkDiscovery(); if (!moved) break;
          await pauseDiscovery(); snapshot = await readDiscovery(source.tab_id); rememberJobs(snapshot);
        }
        searchStatus(`Reviewed ${index+1} of ${pages} pages. ${discovered.length} unique ads found.`);
        if (index+1 === pages || !snapshot.hasNext || discovered.length >= 600) break;
        previous = snapshot.signature; checkDiscovery();
        if (!await rpc('read',{run_id:discoveryRun,tab_id:source.tab_id,method:'nextJobSearch',values:[previous]})) break;
      }
      checkDiscovery(); searchStatus(`Found ${discovered.length} ads. Select the ones to add. Search summaries are labelled; use Read full ad for the complete content when available.`);
    } catch (error) { searchStatus(discoveryStopped ? `Stopped. ${discovered.length} ads found so far are kept for review.` : error.message + ' Ads already found are kept.'); }
    finally {
      if (discoveryRun) { try { await rpc('end',{run_id:discoveryRun}); } catch {} }
      discoveryRun = ''; discovering = false; lock(false); drawDiscovery();
    }
  }
  async function previewDiscovered(row) {
    if (busy) return;
    previewUrl = row.url;
    lock(true); searchStatus('Reading the selected ad in Chrome…');
    try {
      const data = await prepareSource(await rpc('jobFromLink',{url:row.url}));
      if (jobLink(data?.url || '') !== row.url || !data.company || !data.role) throw Error('This ad changed while it was being read.');
      if (!data.description?.trim()) throw Error('The full content was not available. Its search summary is kept.');
      Object.assign(row,{company:data.company,role:data.role,location:data.location || '',date_posted:data.date_posted || '',
        description:data.description,description_rich:data.description_rich || [],description_truncated:data.description_truncated === true,full:true});
      searchStatus('Full ad captured for review. Select it and Add selected to list when ready.');
    } catch (error) { searchStatus(error.message + ' The search summary is still available.'); }
    finally { lock(false); drawDiscovery(); }
  }
  async function addDiscovered(onlyUrl) {
    if (busy) return;
    const selection = discovered.filter(row => (typeof onlyUrl === 'string' ? row.url === onlyUrl : discoveryPicked.has(row.url)) && !savedJob(row.url));
    if (!selection.length) return;
    if (selection.length > 100) { searchStatus('Add up to 100 selected ads at a time.'); return; }
    const folder = el('SearchFolder').value; let added = 0, skipped = 0, failure = '';
    lock(true); searchStatus('Adding selected ads to your list…');
    try {
      await load();
      if (folder && !folderNames.includes(folder)) throw Error('This folder changed in another window. Choose a folder again.');
      for (const row of selection) {
        const record = {url:row.url,company:row.company,role:row.role,location:row.location,date_posted:row.date_posted,
          description:row.description,description_rich:row.description_rich,description_truncated:row.description_truncated,
          folder,status:'new',contact:'',notes:'',follow_up:''};
        const result = await api({action:'save',record});
        if (result.duplicate) skipped++; else added++;
        discoveryPicked.delete(row.url);
      }
    } catch (error) { failure = error.message; }
    finally {
      try { await load(); } catch (error) { failure = failure || error.message; }
      lock(false); drawDiscovery();
      searchStatus(`Added ${added} ads to ${folder || 'Unfiled'}.` + (skipped ? ` ${skipped} already saved; existing details were kept.` : '') + (failure ? ` ${failure} Refresh the saved list before trying remaining ads again.` : ''));
    }
  }
  function rpc(action, args = {}, waitMs) {
    return new Promise((resolve, reject) => {
      const id = hex(), timer = setTimeout(() => { pending.delete(id); reject(Error('The Chrome companion did not respond. This fallback only works in Chrome. Open this CV Studio address there and connect the latest companion. Saved ads remain available below.')); }, waitMs ?? (action === 'jobFromLink' ? 35000 : 12000));
      pending.set(id, {resolve, reject, timer});
      window.postMessage({type:'CVSTUDIO_LINKEDIN_REQUEST', id, channel, action, args}, location.origin);
    });
  }
  window.addEventListener('message', event => {
    const data = event.data;
    if (event.source === window && event.origin === location.origin && data?.type === 'CVSTUDIO_LINKEDIN_CAPTURE' && data.channel === channel && /^[a-f0-9]{32}$/.test(data.id || '')) {
      if (!receivedCaptures.has(data.id)) {
        if (receivedCaptures.size >= 20) receivedCaptures.delete(receivedCaptures.keys().next().value);
        receivedCaptures.set(data.id,receiveCapture(data.record,data.request));
      }
      receivedCaptures.get(data.id).then(result => window.postMessage({type:'CVSTUDIO_LINKEDIN_CAPTURE_RESULT',id:data.id,channel,result},location.origin));
      return;
    }
    if (event.source !== window || event.origin !== location.origin || data?.type !== 'CVSTUDIO_LINKEDIN_RESPONSE' || data.channel !== channel) return;
    const item = pending.get(data.id); if (!item) return;
    clearTimeout(item.timer); pending.delete(data.id);
    if (data.error) item.reject(Error(data.error)); else item.resolve(data.result);
  });
  function jobLink(value) {
    try {
      if (value.length > 2048 || value.includes('\\')) return '';
      const u = new URL(value.trim());
      if (u.protocol !== 'https:' || !['www.linkedin.com', 'linkedin.com', 'my.linkedin.com', 'sg.linkedin.com'].includes(u.hostname) || u.username || u.password || u.port) return '';
      const view = u.pathname.match(/^\/jobs\/view\/(?:[^/]*-)?([0-9]{1,24})\/?$/), ids = u.searchParams.getAll('currentJobId');
      const id = view ? view[1] : /^\/jobs(?:\/search(?:-results)?|\/collections\/[^/]+)?\/?$/.test(u.pathname) && ids.length === 1 ? ids[0] : '';
      return /^[0-9]{1,24}$/.test(id) ? 'https://www.linkedin.com/jobs/view/' + id : '';
    } catch { return ''; }
  }
  async function prepareSource(data) {
    if (data?.description_html) data.description_rich = (await api({action:'format_content', description:data.description || '', description_html:data.description_html})).description_rich;
    return data;
  }
  async function receiveCapture(raw, request = {}) {
    if (!ready || busy) return {error:'Wait for the current CV Studio action to finish, then add this ad again.'};
    if (!request || typeof request !== 'object' || Array.isArray(request)) return {error:'Choose a valid job-ad action.'};
    const url = typeof raw?.url === 'string' ? jobLink(raw.url) : '';
    if (!url || raw.url !== url || typeof raw.company !== 'string' || !raw.company.trim() || raw.company.length > 200 ||
        typeof raw.role !== 'string' || !raw.role.trim() || raw.role.length > 240) return {error:'The job details could not be confirmed.'};
    const action = request.action === undefined ? 'add' : request.action;
    if (!['add','remove','folders','create_folder'].includes(action) || request.folder !== undefined &&
        (typeof request.folder !== 'string' || request.folder.length > 80 || /[\x00-\x1f]/.test(request.folder))) return {error:'Choose a valid job-ad action and folder.'};
    const folder = request.folder === undefined ? el('SearchFolder').value : request.folder;
    let changed = false;
    lock(true);
    try {
      await load();
      let existing = rows.find(row => row.url === url);
      if (action === 'folders') return {ok:true,folders:[...folderNames],folder:existing && !existing.deleted ? existing.folder : el('SearchFolder').value,saved:!!existing && !existing.deleted};
      if (action === 'create_folder') {
        const created = await api({action:'create_folder',folder});
        await load();
        return {ok:true,folders:[...folderNames],folder:created.folder,saved:!!existing && !existing.deleted};
      }
      if (editing && existing?.id === editing.id) throw Error('Finish editing this ad in CV Studio before changing it from LinkedIn. Your draft has been kept.');
      if (action === 'remove') {
        if (existing && !existing.deleted) await api({action:'trash',records:[{id:existing.id,revision:existing.revision}]});
        await load(); searchStatus('Removed from LinkedIn selection. The ad can be restored from Trash.');
        return {ok:true,saved:false,folder:existing?.folder || ''};
      }
      if (folder && !folderNames.includes(folder)) throw Error('Choose an existing destination folder in CV Studio.');
      if (existing) {
        if (existing.deleted) {
          await api({action:'untrash',records:[{id:existing.id,revision:existing.revision}]}); changed = true;
          await load(); existing = rows.find(row => row.url === url);
        }
        if (request.folder !== undefined && existing.folder !== folder) {
          await api({action:'move_folder',folder,records:[{id:existing.id,revision:existing.revision}]}); changed = true;
          await load(); existing = rows.find(row => row.url === url);
        }
        searchStatus('This LinkedIn ad is saved in ' + (existing.folder || 'Unfiled') + '. Existing details were kept.');
        return {ok:true,duplicate:true,saved:true,folder:existing.folder || ''};
      }
      const data = await prepareSource({...raw});
      const record = {url,company:data.company,role:data.role,location:data.location || '',date_posted:data.date_posted || '',
        description:data.description || '',description_rich:data.description_rich || [],description_truncated:data.description_truncated === true,
        folder,status:'new',contact:'',notes:'',follow_up:''};
      const saved = await api({action:'save',record});
      await load();
      searchStatus(saved.duplicate ? 'This LinkedIn ad was already saved. Existing details were kept.' : 'Added from LinkedIn to ' + (folder || 'Unfiled') + '.');
      return {ok:true,duplicate:!!saved.duplicate,saved:!saved.record?.deleted,folder:saved.record?.folder || ''};
    } catch (error) {
      if (changed) {
        try { await load(); const current = rows.find(row => row.url === url); return {ok:true,saved:!!current && !current.deleted,folder:current?.folder || '',warning:error.message}; }
        catch {}
      }
      return {error:error.message};
    }
    finally { lock(false); }
  }
  async function fillFromLink(useBrowser = false, refreshContent = false) {
    if (busy) return;
    const url = jobLink(el('url').value);
    if (!url) { status('Paste a LinkedIn job ad link to fill in its details.'); return; }
    if (editing && jobLink(editing.url) !== url) { status('Click New lead before filling a different job ad. Your current lead has been kept.'); return; }
    const previousSource = lastReadUrl, changedSource = previousSource && previousSource !== url;
    if (changedSource && !window.confirm('Use this different job ad? Its details will replace this draft, including contact, notes, status and dates. The folder will be kept.')) {
      el('url').value = previousSource; status('The current job draft has been kept.'); return;
    }
    const before = draft(); lock(true); status(useBrowser ? 'Reading this job ad in Chrome…' : 'Reading public LinkedIn job details…');
    try {
      let data, usedFallback = false;
      if (useBrowser) data = await rpc('jobFromLink',{url});
      else {
        try { data = (await api({action:'lookup',url})).record; }
        catch (publicError) {
          // Probe only after a recognized public-read failure. Never repeat the
          // server request, interrupt a browser run or replay a failed capture.
          if (!['JOB_AD_UNAVAILABLE','JOB_AD_RATE_LIMITED'].includes(publicError.code)) throw publicError;
          const companion = await rpc('jobStatus',{},1000).catch(() => null);
          if (!companion?.connected || companion.job_read !== true || companion.busy) {
            el('BrowserSetup').open = true;
            if (companion?.busy) throw Error(publicError.message + ' Finish the current companion search or read, then try again.');
            throw publicError;
          }
          status('Public details are unavailable. Reading the ad with your connected Chrome companion…');
          try { data = await rpc('jobFromLink',{url}); usedFallback = true; }
          catch {
            el('BrowserSetup').open = true;
            throw Error('The public reader and connected Chrome companion could not read this ad. Open the ad in Chrome and use Refresh job tabs → Read job ad, or enter its details manually.' + (publicError.requestId ? ' Request ID: ' + publicError.requestId : ''));
          }
        }
      }
      data = await prepareSource(data);
      if (jobLink(data?.url || '') !== url || !data.company || !data.role) throw Error('The job details could not be confirmed. Use Read job ad or enter them manually.');
      if (refreshContent && !data.description?.trim()) throw Error('This ad did not provide readable content. Your current content has been kept.');
      if (changedSource) { fill(null); el('folder').value = before.folder; }
      // Never fill contacts, notes, follow-up dates or BD status from ad text,
      // and preserve manual corrections already made to other populated fields.
      for (const key of ['company','role','location','date_posted','description']) {
        if ((changedSource || !before[key].trim() || refreshContent && key === 'description') && typeof data[key] === 'string') {
          el(key).value = data[key];
          if (key === 'description') { descriptionTruncated = data.description_truncated === true; descriptionRich = data.description_rich || []; }
        }
      }
      descriptionHint();
      el('url').value = url; dirty = true; lastReadUrl = url;
      status('Job details filled in' + (usedFallback ? ' using your connected Chrome companion' : '') + '. Review them, optionally add a contact, then Save lead.' + (data.description_truncated ? ' The description is an excerpt.' : ''));
    } catch (error) { if (changedSource) el('url').value = previousSource; status(error.message + ' Your draft has been kept.'); }
    finally { lock(false); }
  }
  window.initJobLeads = async function () {
    if (ready) return;
    ready = true;
    document.getElementById('viewJobLeads').dataset.companionChannel = channel;
    document.getElementById('viewJobLeads').dataset.companionActions = '1';
    el('PreviewRead').addEventListener('click',() => { const row = discovered.find(value => value.url === previewUrl); if (row) return previewDiscovered(row); });
    el('PreviewSave').addEventListener('click',() => addDiscovered(previewUrl));
    el('SearchStart').addEventListener('click',startDiscovery);
    el('SearchStop').addEventListener('click',async () => {
      if (!discovering) return;
      discoveryStopped = true; discoveryControls(); searchStatus('Stopping after the current browser read. Found ads will be kept.');
      if (discoveryRun) { try { await rpc('end',{run_id:discoveryRun}); } catch {} }
    });
    el('SearchMode').addEventListener('change',discoveryControls);
    el('SearchRefresh').addEventListener('click',async () => {
      if (busy) return;
      lock(true);
      try {
        const tabs = await rpc('jobSearchTabs');
        el('SearchSource').replaceChildren(...tabs.map(tab => new Option(tab.title,String(tab.id))));
        searchStatus(tabs.length ? 'Choose the job search to review. Its existing LinkedIn filters will be kept.' : 'Open a LinkedIn Jobs search in Chrome, then refresh search tabs.');
      } catch (error) { searchStatus(error.message); }
      finally { lock(false); }
    });
    el('SearchAdd').addEventListener('click',addDiscovered);
    el('SearchClear').addEventListener('click',() => { if (!busy) { discovered = []; discoveryPicked.clear(); discoveryPage = 0; drawDiscovery(); searchStatus('Search results cleared. Your saved ads are kept.'); } });
    el('SearchPrevious').addEventListener('click',() => { if (!busy) { discoveryPage--; drawDiscovery(); } });
    el('SearchNext').addEventListener('click',() => { if (!busy) { discoveryPage++; drawDiscovery(); } });
    el('SearchSelectPage').addEventListener('change',() => {
      if (busy) return;
      for (const row of discovered.slice(discoveryPage*20,(discoveryPage+1)*20).filter(row => !savedJob(row.url))) {
        if (el('SearchSelectPage').checked) discoveryPicked.add(row.url); else discoveryPicked.delete(row.url);
      }
      drawDiscovery();
    });
    window.addEventListener('pagehide',() => { discoveryStopped = true; if (discoveryRun) rpc('end',{run_id:discoveryRun}).catch(() => {}); });
    fields.forEach(key => el(key).addEventListener('input', () => {
      dirty = true;
      if (key === 'folder') rememberFolder(el(key).value.trim());
      if (key !== 'url' && !lastReadUrl) lastReadUrl = jobLink(el('url').value);
      if (key === 'description') { descriptionTruncated = false; descriptionRich = []; descriptionHint(); }
    }));
    el('folder').addEventListener('change', () => rememberFolder(el('folder').value.trim()));
    el('AutoFill').addEventListener('click', () => fillFromLink());
    el('BrowserFill').addEventListener('click', () => fillFromLink(true));
    el('RefreshContent').addEventListener('click', () => fillFromLink(false, true));
    el('description').addEventListener('paste', async event => {
      const field = el('description'), source = event.clipboardData?.getData('text/html'), plain = event.clipboardData?.getData('text/plain');
      if (busy || !source || !plain || field.value && (field.selectionStart !== 0 || field.selectionEnd !== field.value.length)) return;
      event.preventDefault();
      if (plain.length > 20000 || source.length > 80000) { status('This formatted description is too large. Paste a shorter excerpt. Your draft has been kept.'); return; }
      lock(true);
      try {
        const result = await api({action:'format_content', description:plain, description_html:source});
        field.value = plain; descriptionRich = result.description_rich || []; descriptionTruncated = false; dirty = true; descriptionHint();
        if (!lastReadUrl) lastReadUrl = jobLink(el('url').value);
        status('Job content pasted. Review it, then save the lead.');
      } catch (error) { status(error.message + ' Your draft has been kept.'); }
      finally { lock(false); }
    });
    el('url').addEventListener('paste', event => {
      const value = event.clipboardData?.getData('text/plain') || '';
      if (busy || !jobLink(value)) return;
      event.preventDefault(); el('url').value = value.trim(); dirty = true;
      return fillFromLink();
    });
    el('url').addEventListener('change', () => { const url = jobLink(el('url').value); if (url && url !== lastReadUrl) return fillFromLink(); });
    el('Form').addEventListener('submit', async event => {
      event.preventDefault(); if (busy) return;
      if (lastReadUrl && jobLink(el('url').value) !== lastReadUrl) { status('This is a different job ad. Use Fill from link to replace the draft, or New lead to enter it manually. Your current details have been kept.'); return; }
      lock(true); status('Saving lead…');
      try {
        const value = await api({action:'save', record:{...draft(), ...(editing ? {id:editing.id, revision:editing.revision} : {})}});
        await load();
        if (value.duplicate) {
          status(value.record.deleted ? 'This job is already saved in Trash. Your draft has been kept; restore the existing lead from Trash.' : 'This job is already saved. Your draft has been kept; use Edit / view details on the existing lead to change it.');
        } else { fill(value.record); status('Lead saved on this computer.'); }
      } catch (error) { status(error.message); }
      finally { lock(false); }
    });
    el('New').addEventListener('click', () => { if (!busy && discard()) { fill(null); status('Ready for another job ad.'); } });
    el('Refresh').addEventListener('click', async () => { if (busy) return; lock(true); try { await load(); status('Saved leads refreshed. Reopen a lead to load its latest changes.'); } catch (error) { status(error.message); } finally { lock(false); } });
    for (const id of ['Search', 'Filter', 'FolderFilter']) el(id).addEventListener(id === 'Search' ? 'input' : 'change', () => { picked.clear(); page = 0; render(); });
    el('FolderNew').addEventListener('click', () => { if (!busy) { el('FolderEditor').hidden = false; el('FolderName').focus(); } });
    el('FolderCancel').addEventListener('click', () => { if (!busy) { el('FolderEditor').hidden = true; el('FolderName').value = ''; } });
    el('FolderCreate').addEventListener('click', createFolder);
    el('FolderName').addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); return createFolder(); } });
    el('FolderDelete').addEventListener('click', deleteFolder);
    el('Move').addEventListener('click', moveSelected);
    el('SelectPage').addEventListener('change', () => {
      if (busy) return;
      for (const row of filtered().slice(page*40, (page+1)*40).filter(row => !row.deleted)) {
        if (el('SelectPage').checked) picked.add(row.id); else picked.delete(row.id);
      }
      render();
    });
    el('Clear').addEventListener('click', () => moveToTrash(filtered(), true, true));
    el('ClearAll').addEventListener('click', () => moveToTrash(rows.filter(row => !row.deleted), true, true));
    el('Previous').addEventListener('click', () => { page--; render(); });
    el('Next').addEventListener('click', () => { page++; render(); });
    el('Tabs').addEventListener('click', async () => {
      if (busy) return; lock(true);
      try {
        const tabs = await rpc('jobTabs'); el('Source').replaceChildren(new Option('Choose an open LinkedIn job ad', ''));
        tabs.forEach(tab => { const option = new Option(tab.title, String(tab.id)); option.dataset.url = tab.url; el('Source').appendChild(option); });
        status(tabs.length ? 'Choose the job ad, then click Read job ad.' : 'Open a LinkedIn job ad in Chrome, then refresh job tabs.');
      } catch (error) { status(error.message); } finally { lock(false); }
    });
    el('Read').addEventListener('click', async () => {
      if (busy || !discard()) return;
      const option = el('Source').selectedOptions[0];
      if (!option?.value) { status('Choose an open LinkedIn job ad first.'); return; }
      lock(true); status('Reading the selected job ad…');
      try {
        const data = await prepareSource(await rpc('jobRead', {tab_id:Number(option.value), expected_url:option.dataset.url}));
        fill(data); dirty = true;
        status('Job ad filled in. Review the details, add a contact or notes, then Save lead.' + (data.description_truncated ? ' The captured description is an excerpt.' : ''));
      } catch (error) { status(error.message); } finally { lock(false); }
    });
    el('Export').addEventListener('click', () => {
      const safe = value => { const text = String(value ?? ''); return '"' + (/^[\s]*[=+@-]/.test(text) ? "'" : '') + text.replaceAll('"', '""') + '"'; };
      const keys = ['company','role','folder','created_at','date_posted','contact','status','follow_up','url','location','notes','description'];
      download(new Blob(['\uFEFF' + [keys, ...filtered().map(row => keys.map(key => row[key]))].map(row => row.map(safe).join(',')).join('\r\n')], {type:'text/csv;charset=utf-8'}), 'CV-Studio-Job-Leads.csv');
    });
    el('Backup').addEventListener('click', () => { window.location.href = '/job-leads?action=backup'; });
    el('Restore').addEventListener('click', () => el('File').click());
    el('File').addEventListener('change', async () => {
      const file = el('File').files[0]; if (!file || busy) return;
      lock(true);
      try {
        if (file.size > 12*1024*1024) throw Error('This backup file is too large.');
        const backup = JSON.parse(await file.text());
        const reply = await api({action:'restore', backup}); await load();
        status(`Restored ${reply.added} leads. Skipped ${reply.skipped} jobs already saved; existing notes were kept.`);
      } catch (error) { status(error instanceof SyntaxError ? 'Choose a valid Job Leads backup file.' : error.message); }
      finally { el('File').value = ''; lock(false); }
    });
    window.addEventListener('beforeunload', event => { if (dirty || busy) { event.preventDefault(); event.returnValue = ''; } });
    fill(null); lock(true);
    try {
      await load();
      if (preferredFolder && !folderNames.includes(preferredFolder)) { rememberFolder(null); el('folder').value = ''; }
      status('Ready. Saved leads stay on this computer.');
    }
    catch (error) { status(error.message); }
    finally { lock(false); }
  };
  function download(blob, name) {
    const url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  document.addEventListener('DOMContentLoaded', () => { if (new URLSearchParams(location.search).get('module') === 'jobleads') switchTab('jobleads'); });
})();
