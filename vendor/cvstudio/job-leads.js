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
  let previewUrl = '', previewCapture = null, previewSource = 'saved', previewDismissed = false;
  let hrRow = '', hrRun = '', hrCapture = '', hrStopped = false, hrRunning = false;
  let bulkHR = null;
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
    window.cvStudioApollo?.busy(value);
    el('Previous').disabled=value || page===0;el('Next').disabled=value || (page+1)*40>=filtered().length;
    for (const name of ['Search','Filter','FolderFilter']) el(name).disabled = value && hrRunning;
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
    previewCapture = null;
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
    if (busy || !selected.length) return false;
    if (editing && selected.some(row => row.id === editing.id) && !discard()) return false;
    if (bulk && !window.confirm(`Move these ${selected.length} saved ads to Trash? You can restore them later.`)) return false;
    lock(true);
    try {
      await api({action:deleted ? 'trash' : 'untrash', records:selected.map(row => ({id:row.id, revision:row.revision}))});
      if (editing && selected.some(row => row.id === editing.id)) fill(null);
      await load(); status(deleted ? 'Moved to Trash. Choose Trash in the folder menu to restore.' : 'Lead restored to its folder.');
      return true;
    } catch (error) { status(error.message); return false; }
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
    el('BulkHR').hidden = !picked.size;
    el('SelectedCount').textContent = picked.size + ' selected';
    el('Move').disabled = busy || !picked.size;
    el('FolderDelete').disabled = busy || ['*','','!trash'].includes(el('FolderFilter').value);
    bulkHRControls();
  }
  async function createFolder() {
    if (busy) return;
    const name = el('FolderName').value;
    lock(true);
    try {
      const result = await api({action:'create_folder', folder:name});
      await load(); el('FolderFilter').value = result.folder; applySavedFilters();
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
    el('Previous').disabled = busy || page === 0; el('Next').disabled = busy || (page+1)*40 >= selected.length;
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
      const preview = node('button', 'Preview', 'sec'); preview.type = 'button'; preview.disabled = busy;
      preview.addEventListener('click', () => { if (!busy) selectPreview(row.url, true); });
      actions.append(link, preview, edit); card.appendChild(actions); list.appendChild(card);
      if (!row.deleted) {
        const hr = node('button',row.hr ? `HR people (${row.hr.people.length})` : 'HR people','sec'); hr.type='button'; hr.disabled=busy;
        hr.addEventListener('click',()=>{ if (!busy) { selectPreview(row.url); el('HR').scrollIntoView({block:'nearest',behavior:'smooth'}); } }); actions.append(hr);
      }
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
  const previewRow = () => previewCapture?.url === previewUrl ? previewCapture : savedJob(previewUrl) || discovered.find(row => row.url === previewUrl);
  const previewSequence = () => previewSource === 'search' ? discovered : filtered();
  function applySavedFilters() {
    if (hrRunning) return;
    picked.clear(); page = 0; render();
    if (previewSource === 'saved' && !previewSequence().some(row => row.url === previewUrl)) { previewUrl = ''; previewCapture = null; }
    drawDiscovery();
  }
  function selectPreview(url, scroll = false, source = 'saved') {
    previewUrl = url; previewSource = source; previewDismissed = false;
    if (source === 'search') {
      const index = discovered.findIndex(row => row.url === url);
      if (index >= 0) discoveryPage = Math.floor(index/20);
    }
    drawDiscovery(); el('SearchPanel').open = true;
    if (scroll) el('Preview').scrollIntoView({block:'nearest',behavior:'smooth'});
  }
  function closePreview() {
    if (busy) return;
    previewUrl = ''; previewCapture = null; previewDismissed = true; drawDiscovery();
  }
  function navigatePreview(delta) {
    if (busy || !previewRow()) return;
    const sequence = previewSequence(), index = sequence.findIndex(row => row.url === previewUrl);
    const next = sequence[index+delta];
    if (next) selectPreview(next.url, false, previewSource);
  }
  function navigateResults(delta) {
    if (busy) return;
    const next = discoveryPage+delta;
    if (next < 0 || next*20 >= discovered.length) return;
    selectPreview(discovered[next*20].url, false, 'search');
  }
  async function managePreview() {
    const saved = savedJob(previewUrl);
    if (busy || !saved) return;
    const source = previewSource, sequence = previewSequence();
    const index = sequence.findIndex(row => row.url === saved.url);
    const neighbor = sequence[index+1] || sequence[index-1];
    if (!await moveToTrash([saved], !saved.deleted) || source === 'search') return;
    const current = previewSequence();
    const next = current.find(row => row.url === neighbor?.url) || current[0];
    if (next) selectPreview(next.url, false, source);
    else closePreview();
  }
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
    const preview = previewRow(), saved = preview && savedJob(preview.url);
    const sequence = previewSequence(), index = sequence.findIndex(row => row.url === previewUrl);
    el('PreviewRead').hidden = !preview; el('PreviewSave').hidden = !preview;
    el('PreviewRead').disabled = busy || !preview;
    el('PreviewSave').disabled = busy || !preview || !!savedJob(preview.url);
    el('PreviewSave').textContent = saved ? saved.deleted ? 'In Trash' : 'Already saved' : 'Add this ad';
    el('PreviewPrevious').disabled = busy || !preview || index <= 0;
    el('PreviewNext').disabled = busy || !preview || index+1 >= sequence.length;
    el('PreviewClose').hidden = !preview; el('PreviewClose').disabled = busy;
    el('PreviewRemove').hidden = !saved; el('PreviewRemove').disabled = busy || !saved;
    el('PreviewRemove').textContent = saved?.deleted ? 'Restore ad' : 'Move to Trash';
    el('PreviewRemove').className = 'sec' + (saved?.deleted ? '' : ' job-lead-delete');
    el('HRStart').disabled = busy || !saved || saved.deleted;
    for (const name of ['HRCountryMode','HRCountry','HRKeywords','HRPages','HRCompanyURL']) el(name).disabled = busy;
    el('HRStop').disabled = !hrRunning || hrStopped;
    bulkHRControls();
    el('SearchPagination').hidden = discovered.length <= 20;
  }
  function drawPreview() {
    const row = previewRow(), saved = row && row === savedJob(row.url);
    const sequence = previewSequence(), index = sequence.findIndex(item => item.url === previewUrl);
    el('PreviewPosition').textContent = row ? (previewSource === 'search' ? 'Search results' : 'Saved ads') +
      (index >= 0 ? ` · ${index+1} of ${sequence.length}` : ' · Outside current filters') : '';
    el('PreviewTitle').textContent = row?.role || 'Choose an ad to preview';
    el('PreviewCompany').textContent = row?.company || '';
    el('PreviewMeta').textContent = row ? [row.location,saved ? 'Saved ad content' : row.full ? 'Captured ad content' : 'Search summary · Read full ad for the description',row.description_truncated ? 'Excerpt' : ''].filter(Boolean).join(' · ') : '';
    content(el('PreviewContent'),row ? row.description || 'No description captured. Use Read full ad to try reading it from LinkedIn.' : 'Search LinkedIn, add an ad with the companion, or choose Preview on a saved ad.',row?.description_rich);
    drawHR(row ? savedJob(row.url) : null);
  }
  function drawDiscovery() {
    const target = el('SearchResults'); target.replaceChildren();
    discoveryPage = Math.min(discoveryPage, Math.max(0,Math.ceil(discovered.length/20)-1));
    if (!previewRow() && !previewDismissed) previewUrl = previewSequence()[0]?.url || '';
    el('SearchResults').hidden = !discovered.length;
    el('Curation').className = 'job-leads-curation' + (!discovered.length ? ' no-search-results' : '');
    if (savedJob(previewUrl) && !savedJob(previewUrl).deleted) el('Curation').className += ' has-hr';
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
      const preview = node('button','Preview','sec'); preview.type = 'button'; preview.addEventListener('click',() => { if (!busy) selectPreview(row.url, true, 'search'); }); actions.append(preview);
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
  const hrDefaultKeywords = 'HR, human resources, CHRO, chief people officer, talent acquisition, TA, recruitment, hiring, recruiter, HRBP, end to end recruitment';
  const hrPreferenceKey = 'cvstudio_job_leads_hr_preferences';
  function validHRPreferences(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value) || !['','specific'].includes(value.countryMode) ||
        typeof value.country !== 'string' || value.country.length > 100 || /[\x00-\x1f\x7f]/.test(value.country) ||
        ![1,3,5,10,15].includes(value.pages)) return null;
    return {countryMode:value.countryMode,country:value.country.trim(),pages:value.pages};
  }
  let preferredHR = null;
  try {
    const stored=localStorage.getItem(hrPreferenceKey);
    if (stored && stored.length <= 1024) preferredHR=validHRPreferences(JSON.parse(stored));
  } catch {}
  function setHRPreferenceControls(prefix, value) {
    el(prefix+'CountryMode').value=value.countryMode;el(prefix+'Country').value=value.country;
    el(prefix+'Country').hidden=el(prefix+'CountryLabel').hidden=!value.countryMode;
    el(prefix+'Pages').value=String(value.pages);
  }
  function rememberHRPreferences(prefix = 'HR') {
    if (busy) return;
    const value=validHRPreferences({countryMode:el(prefix+'CountryMode').value,country:el(prefix+'Country').value,pages:Number(el(prefix+'Pages').value)});
    if (!value) return;
    preferredHR=value;
    setHRPreferenceControls(prefix === 'HR' ? 'BulkHR' : 'HR',value);
    try { localStorage.setItem(hrPreferenceKey,JSON.stringify(value)); } catch {}
  }
  function hrJoinedLabel(value) {
    if (typeof value !== 'string' || !/^(?:19|20)\d{2}(?:-(?:0[1-9]|1[0-2]))?$/.test(value)) return 'Not available';
    return value.length === 4 ? value : ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][Number(value.slice(5))-1]+' '+value.slice(0,4);
  }
  function hrPeople(people) {
    const target = el('HRResults'); target.replaceChildren();
    window.cvStudioApollo?.begin(savedJob(previewUrl));
    for (const person of people || []) {
      if (!/^https:\/\/www\.linkedin\.com\/in\/[A-Za-z0-9_%~-]+\/?$/.test(person?.url || '')) continue;
      const card = node('article','','job-leads-hr-person'), link = node('a',person.name);
      link.href=person.url; link.target='_blank'; link.rel='noopener noreferrer';
      card.append(link,node('p',person.title),node('p',person.location || 'Location not shown','job-leads-muted'),node('p','Joined company: '+hrJoinedLabel(person.joined),'job-leads-muted'),node('p','Matched: '+person.matched,'job-leads-muted'));
      window.cvStudioEmailVerifier?.decorate(card,person);
      window.cvStudioApollo?.decorate(card,person);
      target.append(card);
    }
  }
  function drawHR(row) {
    el('HR').hidden = !row || row.deleted;
    if (!row || row.deleted) { hrRow=''; return; }
    el('HRCompany').textContent = row.hr?.company_name || row.company;
    const key = row.id+'|'+row.company+'|'+row.revision;
    if (key === hrRow) return;
    hrRow = key;
    const search = row.hr;
    const preference=preferredHR || {countryMode:search?.country ? 'specific' : '',country:search?.country || '',pages:3};
    el('HRCountryMode').value = preference.countryMode;
    el('HRCountry').value = preference.country;
    el('HRCountry').hidden = el('HRCountryLabel').hidden = !preference.countryMode;
    el('HRKeywords').value = search?.keywords || hrDefaultKeywords;
    el('HRPages').value = String(preference.pages); el('HRCompanyURL').value=search?.company_url || '';
    el('HRMessage').textContent = search ? `${search.people.length} saved matches · ${search.country || 'Any country'} · Last scan ${createdLabel(search.scanned_at)}. ${search.complete ? '' : 'Limited scan; more matches may be available. '}LinkedIn company association; titles are keyword matches.` : 'Use the connected Chrome companion to scan this company. Results will be saved with this ad. No AI charge.';
    hrPeople(search?.people);
  }
  function checkHR() { if (hrStopped) throw Error('Stopped.'); }
  function hrSettings(prefix) {
    const country=el(prefix+'CountryMode').value ? el(prefix+'Country').value.trim() : '';
    const keywords=el(prefix+'Keywords').value.trim(),pages=Number(el(prefix+'Pages').value);
    if (!['','specific'].includes(el(prefix+'CountryMode').value) || el(prefix+'CountryMode').value && !country || country.length>100 ||
        !keywords.split(',').some(word=>word.trim()) || keywords.length>600 || /[\x00-\x1f\x7f]/.test(country+keywords) || !Number.isInteger(pages) || pages<1 || pages>15) throw Error('Enter a country name, comma-separated keywords and 1 to 15 pages.');
    return {country,keywords,pages};
  }
  async function startHR() {
    const row = savedJob(previewUrl);
    if (busy || !row || row.deleted) return;
    let settings;try { settings=hrSettings('HR'); } catch(error) { el('HRMessage').textContent=error.message;return; }
    rememberHRPreferences();
    const activity=beginScanActivity();let outcome;
    hrStopped=false; hrRunning=true; hrRun=''; lock(true);
    try { outcome=await scanHR(row,{...settings,companyURL:el('HRCompanyURL').value.trim()},value=>{el('HRMessage').textContent=value;},hrPeople); }
    finally { hrRunning=false;lock(false);finishScanActivity(activity,!outcome || outcome.state==='failed' || outcome.stopQueue); }
  }
  function previousHRCompany(row) {
    const h=row.hr;
    if(!h || h.company!==row.company || typeof h.company_id!=='string' || !/^[0-9]{1,24}$/.test(h.company_id) || !/^https:\/\/www\.linkedin\.com\/company\/[A-Za-z0-9_-]+\/$/.test(h.company_url || ''))return null;
    try { const u=new URL(h.source_url);if(u.origin!=='https://www.linkedin.com' || u.username || u.password || u.hash || u.pathname.replace(/\/$/,'')!=='/search/results/people' || u.searchParams.getAll('currentCompany').length!==1 || u.searchParams.get('currentCompany')!==JSON.stringify([h.company_id]))return null; } catch {return null;}
    return {url:h.company_url,id:h.company_id};
  }
  function hrWaitMessage(stage,country) {
    return {company:'Checking the LinkedIn company identity…',company_filter:'Waiting for LinkedIn’s company filter…',country_filter:'Waiting for LinkedIn’s location filter'+(country?' · '+country:'')+'…',navigation:'Waiting for the LinkedIn search to open…',results:'Waiting for LinkedIn HR results…'}[stage] || '';
  }
  function hrTimeoutMessage(stage,country) {
    return {company:'The LinkedIn company identity did not finish loading.',company_filter:'LinkedIn’s company filter did not confirm the company.',country_filter:'LinkedIn’s location filter did not confirm '+(country || 'the selected country')+'.',navigation:'The expected LinkedIn search did not finish opening.',results:'The LinkedIn HR results did not finish loading.'}[stage] || 'LinkedIn did not finish loading the HR results.';
  }
  async function scanHR(row, {country,keywords,pages,companyURL,expectedRedirectURL}, notify, showPeople, recovery=0) {
    const found = new Map();let finalSnapshot=null,omitted=false,outcome,cleanupFailed=false,saving=false,retryCompanyURL='';
    let companyName=row.hr?.company_name || row.company, jobURL='',expectedID='';
    hrRun='';
    try {
      notify('Checking the companion…');
      const companion = await rpc('jobStatus',{},1500); checkHR();
      if (!companion?.connected || companion.company_hr_revision !== 1 || companion.hr_company_identity_revision !== 1 || companion.hr_company_filter_revision !== 1 || companion.hr_company_source_revision !== 1 || companion.hr_resilience_revision !== 1 || companion.hr_joined_revision !== 1 || companion.hr_joined_loading_revision !== 1 || companion.hr_keyword_revision !== 1) throw Error('Apply the latest companion update, then refresh CV Studio and LinkedIn to use the corrected HR search and joining-date checks.');
      if (companion.busy) throw Error('Finish the current companion search or ad read first.');
      const saved=previousHRCompany(row),manual=companyURL && (!saved || companyURL!==saved.url);
      if (!manual) {
        notify('Reading the company link from the saved ad…');
        let captured;
        hrCapture=hex();
        try { captured=await rpc('jobFromLink',{url:row.url,company_only:true,operation_id:hrCapture}); }
        catch(error) {
          checkHR();
          if(!expectedRedirectURL && saved && ['HR_AD_UNAVAILABLE','HR_AD_TIMEOUT','HR_AD_LAYOUT','HR_EMPLOYER_LINK_MISSING'].includes(error.companionCode)){
            companyURL=saved.url;expectedID=saved.id;notify('The ad could not be read. Confirming the previously saved LinkedIn company identity…');
          } else throw error;
        } finally {hrCapture='';}
        checkHR();
        if(!expectedID){
          if (captured?.url !== row.url) throw Error('LinkedIn did not confirm this exact job ad. Refresh its tab and try again.');
          if (typeof captured.company!=='string' || !captured.company.trim() || captured.company.length>200 || /[\x00-\x1f\x7f]/.test(captured.company)) throw Error('The job ad employer has not loaded. Open the ad in LinkedIn and try again.');
          companyURL=captured.company_url || '';companyName=captured.company.trim();jobURL=row.url;
        }
      }
      const companyMatch=companyURL.match(/^https:\/\/www\.linkedin\.com\/company\/([A-Za-z0-9_-]+)(?:\/(?:people|about|life))?\/?$/);
      if (!companyMatch) throw Error('The company link is unavailable. Enter its LinkedIn company page under Search options.');
      companyURL='https://www.linkedin.com/company/'+companyMatch[1]+'/';
      if(expectedRedirectURL && companyURL!==expectedRedirectURL)throw Error('LinkedIn still shows the old company link on this ad. Open it and confirm its employer link before trying again.');
      checkHR(); hrRun=hex();
      const source = await rpc('hrBegin',{run_id:hrRun,company_url:companyURL,company:companyName,...(jobURL?{job_url:jobURL}:{}),...(expectedID?{expected_company_id:expectedID}:{}),country,keywords,max_pages:pages}); checkHR();
      if (!Number.isInteger(source?.tab_id)) throw Error('The HR search did not open.');
      let previous='',pageRefreshes=0;
      for (let pageIndex=0;pageIndex<pages;pageIndex++) {
        let snapshot=null,waitStage='results';
        for (let attempt=0;attempt<120;attempt++) {
          checkHR(); notify(`Finding ${country || 'worldwide'} HR people · page ${pageIndex+1} of ${pages}…`);
          const value = await rpc('hrRead',{run_id:hrRun,tab_id:source.tab_id}); checkHR();
          if (value && !value.loading && (!previous || value.empty || value.signature !== previous)) { snapshot=value; break; }
          if(hrWaitMessage(value?.wait_stage,country)){waitStage=value.wait_stage;notify(hrWaitMessage(waitStage,country)+` · page ${pageIndex+1} of ${pages}`);}
          await pauseDiscovery();
        }
        if (!snapshot || !Array.isArray(snapshot.people) || snapshot.people.length > 40 || typeof snapshot.signature !== 'string') {
          const error=Error(hrTimeoutMessage(waitStage,country)+' Check that stage in the LinkedIn tab and try again.');error.stopQueue=['company_filter','country_filter'].includes(waitStage);throw error;
        }
        finalSnapshot=snapshot;
        for (const person of snapshot.people) {
          if (typeof person?.url !== 'string' || !/^https:\/\/www\.linkedin\.com\/in\/[A-Za-z0-9_%~-]+\/?$/.test(person.url) || typeof person.name !== 'string' || typeof person.title !== 'string' || typeof person.location !== 'string' || typeof person.matched !== 'string') throw Error('An HR result could not be confirmed.');
          const profileURL=person.url.replace(/\/$/,'');
          if (found.size >= 100 && !found.has(profileURL)) { omitted=true; continue; }
          if (found.size < 100 && !found.has(profileURL)) {
            const entry={...person,url:profileURL,joined:''};
            found.set(profileURL,entry); showPeople([...found.values()]);
            // Read only this observed profile, one background tab at a time.
            // A missing/slow Experience section is optional evidence, never a
            // fabricated date or reason to erase otherwise valid HR matches.
            for (let attempt=0;attempt<20;attempt++) {
              checkHR(); notify(`Checking when ${person.name} joined ${row.company}…`);
              const value=await rpc('hrJoined',{run_id:hrRun,tab_id:source.tab_id,url:profileURL}); checkHR();
              if (value && !value.loading) {
                if (value.url !== profileURL || typeof value.joined !== 'string' || !/^(?:(?:19|20)\d{2}(?:-(?:0[1-9]|1[0-2]))?)?$/.test(value.joined)) throw Error('An HR joining date could not be confirmed.');
                entry.joined=value.joined; break;
              }
              await pauseDiscovery();
            }
            checkHR(); await rpc('hrJoinedClose',{run_id:hrRun,tab_id:source.tab_id}); checkHR();
          }
        }
        showPeople([...found.values()]);
        if (snapshot.empty || !snapshot.hasNext || found.size >= 100 || pageIndex+1 === pages) break;
        previous=snapshot.signature;
        let advanced=null;
        for (let attempt=0;attempt<120;attempt++) {
          checkHR(); advanced=await rpc('hrNext',{run_id:hrRun,tab_id:source.tab_id,signature:previous}); checkHR();
          if (!advanced?.loading) break;
          await pauseDiscovery();
        }
        if(advanced?.refresh===true){
          if(++pageRefreshes>2)throw Error('LinkedIn kept changing the results before paging. Check its search tab and try again.');
          previous='';pageIndex--;notify('LinkedIn updated these results. Reading the same company and filters again…');continue;
        }
        if (typeof advanced !== 'boolean') throw Error('LinkedIn did not finish loading the next HR page. Check the search tab and try again.');
        if (!advanced) break;
      }
      checkHR();
      const complete=!finalSnapshot.hasNext && !omitted;
      saving=true;
      const response = await api({action:'save_hr',id:row.id,revision:row.revision,search:{company:row.company,company_name:finalSnapshot.company_name || companyName,company_url:finalSnapshot.company_url || companyURL,company_id:finalSnapshot.company_id,
        country,keywords,source_url:finalSnapshot.source_url,complete,people:[...found.values()]}});
      const index = rows.findIndex(item=>item.id===row.id); if (index >= 0) rows[index]=response.record;
      if (editing?.id === row.id) editing={...editing,revision:response.record.revision,hr:response.record.hr};
      hrRow=''; render(); drawPreview();
      const message=`${found.size} HR matches saved · ${country || 'Any country'} · Last scan ${createdLabel(response.record.hr.scanned_at)}. ${complete ? 'No further results shown by LinkedIn.' : 'Page/result limit reached; more people may be available on LinkedIn.'}`+(expectedID?' The ad could not be reread; its previously saved company identity was reconfirmed.':'');
      outcome={state:'saved',matches:found.size,complete,message};notify(message);
    } catch(error) {
      if(error.companionCode==='HR_COMPANY_REDIRECT' && recovery===0 && jobURL && !found.size && !finalSnapshot && !saving && error.companyURL)retryCompanyURL=error.companyURL;
      const saveUnconfirmed=saving && error.code!=='JOB_LEADS_CONFLICT';
      const message=(hrStopped ? 'Scan stopped.' : error.message)+' '+(saveUnconfirmed ? 'The save could not be confirmed. Refresh saved ads before trying again. No ad details were edited.' : `${found.size ? found.size+' matches from this attempt have not been saved. ' : ''}Previous saved results and ad details were kept.`);
      outcome={state:hrStopped ? 'stopped' : 'failed',message,stopQueue:saveUnconfirmed || error.stopQueue || ['HR_ACCESS_REQUIRED','HR_PAGE_CHANGED'].includes(error.companionCode) || /companion|reconnect|sign.?in|restriction|verification check|browser action stopped/i.test(error.message)};
      notify(message);
      if (!found.size) showPeople(row.hr?.people);
    } finally {
      if (hrRun) { try { if (await rpc('end',{run_id:hrRun}) !== true) cleanupFailed=true; } catch { cleanupFailed=true; } }
      hrRun='';
    }
    if (cleanupFailed) {
      outcome.stopQueue=true;outcome.message+=' The companion did not confirm cleanup. Reconnect it before scanning again.';notify(outcome.message);
    }
    if(retryCompanyURL && !cleanupFailed && !hrStopped){notify('Rechecking the updated employer link before starting the search…');return scanHR(row,{country,keywords,pages,companyURL:'',expectedRedirectURL:retryCompanyURL},notify,showPeople,recovery+1);}
    return outcome;
  }
  function bulkHRControls() {
    for (const name of ['CountryMode','Country','Pages','Keywords']) el('BulkHR'+name).disabled=busy;
    el('BulkHRStart').disabled=busy || !rows.some(row=>picked.has(row.id) && !row.deleted);
    el('BulkHRStop').disabled=!bulkHR?.running || hrStopped;
  }
  function stopHR() {
    if (!hrRunning) return;
    hrStopped=true;el('HRMessage').textContent='Stopping after the current read…';
    if(hrCapture)rpc('jobReadCancel',{operation_id:hrCapture}).catch(()=>{});
    if (bulkHR?.running) el('BulkHRMessage').textContent='Stopping after the current read. Completed ads are already saved; remaining ads will not start.';
    discoveryControls();
  }
  function bulkHRSummary() {
    el('BulkHRBar').value=bulkHR.completed;
    el('BulkHRSummary').textContent=`${bulkHR.completed} of ${bulkHR.items.length} ads processed · ${bulkHR.saved} saved · ${bulkHR.failed} failed`+(bulkHR.cancelled ? ` · ${bulkHR.cancelled} stopped` : '');
  }
  async function startBulkHR() {
    const selection=rows.filter(row=>picked.has(row.id) && !row.deleted).map(row=>({...row}));
    if (busy || !selection.length) return;
    let settings;
    try {
      if (selection.length>40) throw Error('Select up to 40 ads for one HR scan. You can run the next group afterward.');
      settings=hrSettings('BulkHR');
    } catch(error) {
      el('BulkHRProgress').hidden=false;el('BulkHRBar').hidden=true;el('BulkHRSummary').textContent='';el('BulkHRResults').replaceChildren();el('BulkHRMessage').textContent=error.message;return;
    }
    rememberHRPreferences('BulkHR');
    const activity=beginScanActivity();
    hrStopped=false;hrRunning=true;bulkHR={running:true,completed:0,saved:0,failed:0,cancelled:0,items:[]};
    el('BulkHRResults').replaceChildren();el('BulkHRProgress').hidden=false;el('BulkHRBar').hidden=false;
    el('BulkHRBar').max=selection.length;
    for (const row of selection) {
      const title=row.company+' — '+row.role,item=node('li',title+' · Waiting');item.dataset.state='waiting';
      bulkHR.items.push({row,title,node:item});el('BulkHRResults').appendChild(item);
    }
    bulkHRSummary();lock(true);
    let stoppedReason='';
    try {
      for (let index=0;index<bulkHR.items.length;index++) {
        if (hrStopped) break;
        const item=bulkHR.items[index],row=item.row;
        item.node.dataset.state='running';item.node.textContent=item.title+' · Scanning…';
        const notify=message=>{
          el('BulkHRMessage').textContent=`Ad ${index+1} of ${selection.length} · ${item.title} · ${message}`;
          if (savedJob(previewUrl)?.id===row.id) el('HRMessage').textContent=message;
        };
        const showPeople=people=>{if (savedJob(previewUrl)?.id===row.id) hrPeople(people);};
        const outcome=await scanHR(row,{...settings,companyURL:row.hr?.company_url || ''},notify,showPeople);
        item.node.dataset.state=outcome.state;
        item.node.textContent=item.title+' · '+(outcome.state==='saved' ? `${outcome.matches} HR matches saved${outcome.complete ? '' : ' · Limited scan'}` : outcome.message);
        bulkHR.completed++;if (outcome.state==='saved') bulkHR.saved++;else if (outcome.state==='failed') bulkHR.failed++;else bulkHR.cancelled++;
        bulkHRSummary();
        if (outcome.stopQueue) { stoppedReason=outcome.message;break; }
      }
    } catch(error) {
      stoppedReason=error.message;
      const active=bulkHR.items.find(item=>item.node.dataset.state==='running');
      if (active) {active.node.dataset.state='failed';active.node.textContent=active.title+' · '+error.message;bulkHR.completed++;bulkHR.failed++;}
    }
    finally {
      bulkHR.running=false;hrRunning=false;
      const remaining=bulkHR.items.length-bulkHR.completed;
      for (const item of bulkHR.items) if (item.node.dataset.state==='waiting') item.node.textContent=item.title+' · Not started';
      el('BulkHRMessage').textContent=(hrStopped || stoppedReason ? 'Queue stopped. ' : 'Queue finished. ')+`${bulkHR.saved} ads saved, ${bulkHR.failed} failed${bulkHR.cancelled ? ', '+bulkHR.cancelled+' stopped' : ''}${remaining ? ', '+remaining+' not started' : ''}. `+(stoppedReason || 'Completed results are saved with each ad.');
      bulkHRSummary();lock(false);finishScanActivity(activity,bulkHR.failed>0 || !!stoppedReason);
    }
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
  const beginScanActivity = () => typeof markTabRunning === 'function' ? markTabRunning('jobleads') : null;
  function finishScanActivity(token, failed) {
    if (token === null) return;
    if (failed && typeof markTabFailed === 'function') markTabFailed('jobleads',token);
    else if (typeof markTabDone === 'function') markTabDone('jobleads',token);
  }
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
    const activity=beginScanActivity();let failed=false;
    lock(true); searchStatus('Checking the browser companion…');
    try {
      const companion = await rpc('jobStatus',{},1000).catch(() => null);
      checkDiscovery();
      if (!companion?.connected) throw Error('Open this CV Studio address in Chrome or Brave with the companion enabled. It connects automatically. Use Set up companion once if needed. LinkedIn job search cannot run inside the Codex preview.');
      if (companion.job_search !== true || !Number.isInteger(companion.job_search_revision) || companion.job_search_revision < 1) throw Error('Update and reload the latest companion, refresh CV Studio and LinkedIn, then reconnect this tab to enable the current job search. Updating CV Studio alone does not update the companion.');
      if (companion.busy) throw Error('Finish the current companion search or ad read before starting another search.');
      discoveryRun = hex(); discovered = []; discoveryPicked.clear(); discoveryPage = 0; previewUrl = ''; previewCapture = null;
      previewSource = 'search'; previewDismissed = false;
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
    } catch (error) { failed=!discoveryStopped;searchStatus(discoveryStopped ? `Stopped. ${discovered.length} ads found so far are kept for review.` : error.message + ' Ads already found are kept.'); }
    finally {
      if (discoveryRun) { try { await rpc('end',{run_id:discoveryRun}); } catch {} }
      discoveryRun = ''; discovering = false; lock(false); drawDiscovery();finishScanActivity(activity,failed);
    }
  }
  async function previewDiscovered(row, source = 'search') {
    if (busy) return;
    selectPreview(row.url, false, source);
    lock(true); searchStatus('Reading the selected ad in Chrome…');
    try {
      const data = await prepareSource(await rpc('jobFromLink',{url:row.url}));
      if (jobLink(data?.url || '') !== row.url || !data.company || !data.role) throw Error('This ad changed while it was being read.');
      if (!data.description?.trim()) throw Error('The full content was not available. Its search summary is kept.');
      // Reading a saved ad is a temporary preview; never overwrite its durable content or editing draft.
      previewCapture = {...row,company:data.company,role:data.role,location:data.location || '',date_posted:data.date_posted || '',
        description:data.description,description_rich:data.description_rich || [],description_truncated:data.description_truncated === true,full:true};
      const found = discovered.find(value => value.url === row.url); if (found) Object.assign(found,previewCapture);
      searchStatus(savedJob(row.url) ? 'Full ad captured for preview. To update the saved content, use Edit / view details → Refresh ad content, then save.' : 'Full ad captured for review. Select it and Add selected to list when ready.');
    } catch (error) { searchStatus(error.message + ' The previous content or search summary is still available.'); }
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
      const id = hex(), timer = setTimeout(() => { pending.delete(id); reject(Error('The companion did not respond. Refresh this CV Studio tab after reloading the companion. Use Chrome or Brave, and click the companion toolbar icon once if this installation has not been connected. Saved ads remain available below.')); }, waitMs ?? (action === 'jobFromLink' ? args.company_only ? 55000 : 35000 : 12000));
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
    if (data.error) { const error=Error(data.error);if(/^HR_[A-Z_]{1,50}$/.test(data.error_code || ''))error.companionCode=data.error_code;if(/^https:\/\/www\.linkedin\.com\/company\/[A-Za-z0-9_-]+\/$/.test(data.company_url || ''))error.companyURL=data.company_url;item.reject(error); } else item.resolve(data.result);
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
    if (!request || typeof request !== 'object' || Array.isArray(request)) return {error:'Choose a valid job-ad action.'};
    const action = request.action === undefined ? 'add' : request.action;
    if (!['add','remove','folders','create_folder'].includes(action) || request.folder !== undefined &&
        (typeof request.folder !== 'string' || request.folder.length > 80 || /[\x00-\x1f]/.test(request.folder))) return {error:'Choose a valid job-ad action and folder.'};
    if (!ready || busy && action !== 'folders') return {error:'Wait for the current CV Studio action to finish, then add this ad again.'};
    const url = typeof raw?.url === 'string' ? jobLink(raw.url) : '';
    if (!url || raw.url !== url || action !== 'folders' && (typeof raw.company !== 'string' || !raw.company.trim() || raw.company.length > 200 ||
        typeof raw.role !== 'string' || !raw.role.trim() || raw.role.length > 240)) return {error:'The job details could not be confirmed.'};
    if (action === 'folders') {
      // Read authoritative metadata without rendering/loading the panel: doing
      // that would clear selections or disturb a draft while LinkedIn preloads.
      try {
        const data = await api(), existing = data.records.find(row => row.url === url);
        return {ok:true,folders:data.folders || [],folder:existing && !existing.deleted ? existing.folder : el('SearchFolder').value,saved:!!existing && !existing.deleted};
      } catch (error) { return {error:error.message}; }
    }
    const folder = request.folder === undefined ? el('SearchFolder').value : request.folder;
    let changed = false;
    lock(true);
    try {
      await load();
      let existing = rows.find(row => row.url === url);
      if (action === 'create_folder') {
        const created = await api({action:'create_folder',folder});
        await load();
        return {ok:true,folders:[...folderNames],folder:created.folder,saved:!!existing && !existing.deleted};
      }
      if (editing && existing?.id === editing.id) throw Error('Finish editing this ad in CV Studio before changing it from LinkedIn. Your draft has been kept.');
      if (action === 'remove') {
        if (existing && !existing.deleted) await api({action:'trash',records:[{id:existing.id,revision:existing.revision}]});
        await load(); selectPreview(url); searchStatus('Removed from LinkedIn selection. The ad can be restored from Trash.');
        return {ok:true,saved:false,folder:existing?.folder || ''};
      }
      // Add is idempotent for an active record, even if another window saved it
      // after the companion's preflight. Only explicit moves or Trash restore
      // may refile an existing ad; a chosen Add destination is for new ads.
      if (existing && !existing.deleted) {
        selectPreview(url); searchStatus('This LinkedIn ad is already saved. Its existing folder and details were kept.');
        return {ok:true,duplicate:true,saved:true,folder:existing.folder || ''};
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
        selectPreview(url); searchStatus('This LinkedIn ad is saved in ' + (existing.folder || 'Unfiled') + '. Existing details were kept.');
        return {ok:true,duplicate:true,saved:true,folder:existing.folder || ''};
      }
      const data = await prepareSource({...raw});
      const record = {url,company:data.company,role:data.role,location:data.location || '',date_posted:data.date_posted || '',
        description:data.description || '',description_rich:data.description_rich || [],description_truncated:data.description_truncated === true,
        folder,status:'new',contact:'',notes:'',follow_up:''};
      const saved = await api({action:'save',record});
      await load(); selectPreview(url);
      searchStatus(saved.duplicate ? 'This LinkedIn ad was already saved. Existing details were kept.' : 'Added from LinkedIn to ' + (folder || 'Unfiled') + '.');
      return {ok:true,duplicate:!!saved.duplicate,saved:!saved.record?.deleted,folder:saved.record?.folder || ''};
    } catch (error) {
      if (changed) {
        try { await load(); selectPreview(url); const current = rows.find(row => row.url === url); return {ok:true,saved:!!current && !current.deleted,folder:current?.folder || '',warning:error.message}; }
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
    void window.cvStudioApollo?.init();
    if (ready) return;
    ready = true;
    el('HRStart').addEventListener('click',startHR);
    el('HRStop').addEventListener('click',stopHR);
    el('BulkHRStart').addEventListener('click',startBulkHR);el('BulkHRStop').addEventListener('click',stopHR);
    setHRPreferenceControls('BulkHR',preferredHR || {countryMode:'',country:'',pages:3});
    el('BulkHRKeywords').value=hrDefaultKeywords;el('BulkHRProgress').hidden=true;
    el('HRCountryMode').addEventListener('change',()=>{ el('HRCountry').hidden=el('HRCountryLabel').hidden=!el('HRCountryMode').value; rememberHRPreferences(); });
    el('HRCountry').addEventListener('input',()=>rememberHRPreferences());
    el('HRPages').addEventListener('change',()=>rememberHRPreferences());
    el('BulkHRCountryMode').addEventListener('change',()=>{el('BulkHRCountry').hidden=el('BulkHRCountryLabel').hidden=!el('BulkHRCountryMode').value;rememberHRPreferences('BulkHR');});
    el('BulkHRCountry').addEventListener('input',()=>rememberHRPreferences('BulkHR'));
    el('BulkHRPages').addEventListener('change',()=>rememberHRPreferences('BulkHR'));
    document.getElementById('viewJobLeads').dataset.companionChannel = channel;
    document.getElementById('viewJobLeads').dataset.companionActions = '1';
    document.getElementById('viewJobLeads').dataset.companionFolders = '2';
    el('PreviewRead').addEventListener('click',() => { const row = previewRow(); if (row) return previewDiscovered(row, previewSource); });
    el('PreviewSave').addEventListener('click',() => addDiscovered(previewUrl));
    el('PreviewPrevious').addEventListener('click',() => navigatePreview(-1));
    el('PreviewNext').addEventListener('click',() => navigatePreview(1));
    el('PreviewClose').addEventListener('click',closePreview);
    el('PreviewRemove').addEventListener('click',managePreview);
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
    el('SearchClear').addEventListener('click',() => { if (!busy) { discovered = []; discoveryPicked.clear(); discoveryPage = 0; closePreview(); searchStatus('Search results cleared. Your saved ads are kept.'); } });
    el('SearchPrevious').addEventListener('click',() => navigateResults(-1));
    el('SearchNext').addEventListener('click',() => navigateResults(1));
    el('SearchSelectPage').addEventListener('change',() => {
      if (busy) return;
      for (const row of discovered.slice(discoveryPage*20,(discoveryPage+1)*20).filter(row => !savedJob(row.url))) {
        if (el('SearchSelectPage').checked) discoveryPicked.add(row.url); else discoveryPicked.delete(row.url);
      }
      drawDiscovery();
    });
    window.addEventListener('pagehide',() => {
      discoveryStopped = true; hrStopped = true;
      if(hrCapture)rpc('jobReadCancel',{operation_id:hrCapture}).catch(()=>{});
      if (discoveryRun) rpc('end',{run_id:discoveryRun}).catch(() => {});
      if (hrRun) rpc('end',{run_id:hrRun}).catch(() => {});
    });
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
    for (const id of ['Search', 'Filter', 'FolderFilter']) el(id).addEventListener(id === 'Search' ? 'input' : 'change', applySavedFilters);
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
