/* Job Leads: durable local records; the companion only fills a reviewable draft. */
(function () {
  'use strict';
  const el = id => document.getElementById('jobLeads' + id);
  const labels = {new:'New', to_contact:'To contact', contacted:'Contacted', follow_up:'Following up', won:'Won', closed:'Closed'};
  const fields = ['url', 'company', 'role', 'contact', 'location', 'date_posted', 'folder', 'follow_up', 'notes', 'description'];
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
  let discovered = [], discoveryPage = 0, discoveryRenderedPage = -1, discovering = false, discoveryStopped = false, discoveryRun = '';
  let backgroundAds = null, publicJobPausedUntil = 0, discoveryFailed = false, backgroundFailed = false;
  const discoveryPicked = new Set();
  let previewUrl = '', previewCapture = null, previewSource = 'saved', previewDismissed = false;
  let hrRow = '', hrRun = '', hrCapture = '', hrStopped = false, hrRunning = false, hrFailedUrl = '';
  let bulkHR = null;
  // The HR queue resumes only its own unfinished run.
  const bulkCheckpointKeys={BulkHR:'cvstudio_job_leads_hr_queue_v1'};
  // The Followed clients queue was merged into Job ads (v24.6.543).
  try { localStorage.removeItem('cvstudio_job_leads_client_hr_queue_v1'); } catch {}
  const bulkCheckpoints={};
  for (const [prefix,key] of Object.entries(bulkCheckpointKeys)) {
    try {
      const raw=localStorage.getItem(key);
      if(raw && raw.length<=16000) {
        const value=JSON.parse(raw),settings=value.settings;
        if(value.version===1 && settings && typeof settings.country==='string' && settings.country.length<=100 &&
            typeof settings.keywords==='string' && settings.keywords.length<=600 && Number.isInteger(settings.pages) && settings.pages>=1 && settings.pages<=15 &&
            Array.isArray(value.items) && value.items.length>0 && value.items.length<=40 && new Set(value.items.map(item=>item?.id)).size===value.items.length &&
            value.items.every(item=>item && /^[a-f0-9]{32}$/.test(item.id) && Number.isInteger(item.revision) && item.revision>0 && ['waiting','running','saved','failed','stopped'].includes(item.state))) bulkCheckpoints[prefix]=value;
      }
    } catch {}
  }
  const receivedCaptures = new Map();
  let rows = [], editing = null, busy = false, dirty = false, page = 0, ready = false, lastReadUrl = '', descriptionTruncated = false, descriptionRich = [];
  let draftCompanyURL = '', draftCompanyName = '';
  const guideNames = [...fields,'AutoFill','Save','SearchQuery','SearchLocation','SearchPages','SearchSource','SearchRefresh','SearchStart','SearchSetupGuide','SearchAdd','PreviewSave','HRStart','HRCountryMode','HRCountry','HRKeywords','HRPages','HRCompanyURL','BulkHRStart','BulkHRCountryMode','BulkHRCountry','BulkHRKeywords','BulkHRPages','SelectPage'];
  let guideFlow = 'Search', guideTried = false, guideIssue = '';
  function guide(name = '', invalid = false, focus = false) {
    for (const key of guideNames) {
      el(key).setAttribute('data-guide',String(!busy && key === name));
      el(key).setAttribute('aria-invalid',String(!busy && invalid && key === name));
    }
    if (!busy && focus && name) {
      for (let parent = el(name).parentElement; parent; parent = parent.parentElement) if (parent.tagName === 'DETAILS') parent.open = true;
      el(name).focus();
    }
  }
  function hrGuide(prefix) {
    if (!['','specific'].includes(el(prefix+'CountryMode').value)) return prefix+'CountryMode';
    if (el(prefix+'CountryMode').value && (!el(prefix+'Country').value.trim() || el(prefix+'Country').value.trim().length > 100 || /[\x00-\x1f\x7f]/.test(el(prefix+'Country').value.trim()))) return prefix+'Country';
    if (!el(prefix+'Keywords').value.split(',').some(word=>word.trim()) || el(prefix+'Keywords').value.length > 600 || /[\x00-\x1f\x7f]/.test(el(prefix+'Keywords').value.trim())) return prefix+'Keywords';
    const pages=Number(el(prefix+'Pages').value);
    return !Number.isInteger(pages) || pages < 1 || pages > 15 ? prefix+'Pages' : prefix+'Start';
  }
  function nextGuide(focus = false) {
    let name=guideIssue;
    if (!name && guideFlow === 'Form') name=fields.find(key=>el(key).validity?.valid === false) || (!jobLink(el('url').value) ? 'url' : lastReadUrl && jobLink(el('url').value) !== lastReadUrl ? 'AutoFill' : !el('company').value.trim() ? 'company' : !el('role').value.trim() ? 'role' : 'Save');
    if (!name && guideFlow === 'HR') name=el('HR').hidden ? '' : hrGuide('HR');
    if (!name && guideFlow === 'BulkHR') name=picked.size ? hrGuide('BulkHR') : '';
    if (!name && guideFlow === 'Search') {
      const pages=Number(el('SearchPages').value), useOpen=el('SearchMode').value === 'open';
      name=!useOpen && !el('SearchQuery').value.trim() ? 'SearchQuery' :
        !Number.isInteger(pages) || pages < 1 || pages > 15 ? 'SearchPages' :
        useOpen && !el('SearchSource').value ? 'SearchRefresh' : !el('SearchAdd').disabled && !el('SearchAdd').hidden ? 'SearchAdd' :
        !el('PreviewSave').disabled && !el('PreviewSave').hidden ? 'PreviewSave' : 'SearchStart';
    }
    const invalid=guideTried && (fields.includes(name) || ['SearchQuery','SearchLocation','SearchPages','HRCountry','HRKeywords','HRPages','HRCompanyURL','BulkHRCountry','BulkHRKeywords','BulkHRPages'].includes(name));
    guide(name,invalid,focus);
  }
  function chooseGuide(flow) { guideFlow=flow;guideTried=false;guideIssue='';nextGuide(); }
  const status = message => { el('Message').textContent = message; };
  // Today's local date, or the date `daysBack` days earlier, as YYYY-MM-DD.
  function localDate(daysBack = 0) {
    const d = new Date(); d.setDate(d.getDate() - daysBack);
    return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }
  const due = row => row.follow_up && row.follow_up <= localDate() && !['won', 'closed'].includes(row.status);
  function draft() {
    const value = {...Object.fromEntries(fields.map(key => [key, el(key).value])), status:editing?.status || 'new', description_truncated:descriptionTruncated, description_rich:descriptionRich};
    if (companyPage(draftCompanyURL) && value.company.trim() === draftCompanyName && jobLink(value.url) === lastReadUrl) value.company_url = draftCompanyURL;
    return value;
  }
  const richTags = new Set(['p','h3','h4','ul','ol','li','strong','em','br','blockquote']);
  const markupViews=new Map(),contentViews=new WeakMap();
  function content(target, plain, rich, normalized=false) {
    const view={};contentViews.set(target,view);
    if(!normalized && typeof plain==='string' && /<(?:p|strong|b|em|i|ul|ol|li|h[1-6]|br|blockquote)(?:\s[^>]*|\s*\/?)>/i.test(plain)){
      if(!markupViews.has(plain)){
        if(markupViews.size>=32)markupViews.delete(markupViews.keys().next().value);
        const pending=api({action:'format_content',render_markup:true,description:plain}).catch(()=>{if(markupViews.get(plain)===pending)markupViews.delete(plain);return null;});
        markupViews.set(plain,pending);
      }
      markupViews.get(plain).then(value=>{
        if(contentViews.get(target)===view && typeof value?.description==='string' && Array.isArray(value.description_rich))content(target,value.description,value.description_rich,true);
      });
    }
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
          } else {
            const child = document.createElement(item.tag);
            let children=item.children;
            if(['ul','ol'].includes(item.tag)){
              const words=(items,n=0)=>n>16?'':(items || []).map(value=>typeof value.text==='string'?value.text:words(value.children,n+1)).join('');
              children=(children || []).flatMap(value=>value.tag===item.tag?value.children:[value]).filter(value=>value.tag!=='li'||words([value]).trim());
            }
            add(child, children, depth+1); parent.appendChild(child);
          }
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
    } else target.textContent = '';
    target.hidden = !plain && !(Array.isArray(rich) && rich.length);
    target.className = 'job-lead-ad-content job-lead-rich';
  }
  function descriptionHint() {
    const excerpt=descriptionTruncated || el('description').value.length >= 20000;
    el('DescriptionNote').textContent = excerpt ? 'Captured excerpt.' : '';
    el('DescriptionNote').hidden=!excerpt;
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
    draftCompanyURL = recordCompanyPage(record); draftCompanyName = (record?.company || '').trim();
    descriptionTruncated = record?.description_truncated === true; descriptionRich = record?.description_rich || []; descriptionHint();
    el('Created').textContent = record?.created_at ? 'Date created: ' + createdLabel(record.created_at) : '';
    el('Created').hidden=!record?.created_at;
    el('Heading').textContent = editing ? 'Edit lead' : 'Save a job ad';
    el('Save').textContent = editing ? 'Save changes' : 'Save lead';
    nextGuide();
  }
  function discard() { return !dirty || window.confirm('Discard the unsaved changes in this lead?'); }
  function lock(value) {
    busy = value;
    window.cvStudioApollo?.busy(value);
    el('Previous').disabled=value || page===0;el('Next').disabled=value || (page+1)*40>=filtered().length;
    el('PageNumbers').querySelectorAll('button').forEach(button => { button.disabled = value; });
    for (const name of ['Search','Filter','FolderFilter','ClientFilter','PostedFilter','Sort','FiltersReset']) el(name).disabled = value && hrRunning;
    for (const id of ['Save', 'New', 'FormClose', 'AddManual', 'Read', 'Tabs', 'Refresh', 'Restore', 'AutoFill', 'BrowserFill', 'RefreshContent', 'Clear', 'ClearAll', 'FolderNew', 'FolderCreate', 'FolderCancel', 'FolderName', 'FolderDelete', 'Move', 'MoveFolder', 'SelectPage', 'SelectAll', 'UnselectAll']) el(id).disabled = value;
    for (const name of fields) el(name).disabled = value;
    el('List').querySelectorAll('button').forEach(button => { button.disabled = value; });
    el('List').querySelectorAll('input').forEach(input => { input.disabled = value; });
    discoveryControls();
    if (!value) { updateClear(); updateSelection(); }
    nextGuide();
  }
  async function api(body, signal) {
    const response = await fetch('/job-leads', body ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body), ...(body.action === 'lookup' ? {timeout:30000} : {}), ...(signal ? {signal} : {})} : {});
    const data = await response.json();
    if (!response.ok || data.error) {
      const error = Error(data.error || 'Job Leads could not finish this request.');
      error.code = data.code; error.requestId = data.request_id;
      if(error.code === 'JOB_AD_RATE_LIMITED') {
        const seconds=Number.isInteger(data.retry_after_seconds) && data.retry_after_seconds>0 && data.retry_after_seconds<=2147483647 ? data.retry_after_seconds : 300;
        publicJobPausedUntil=Math.max(publicJobPausedUntil,Date.now()+seconds*1000);
      }
      throw error;
    }
    return data;
  }
  async function load() {
    const data = await api(); rows = data.records; folderNames = data.folders || [];
    previewCapture = null;
    picked.clear(); syncFolders(); syncClients(); render();
    drawDiscovery();
    return data;
  }
  // The followed client an ad belongs to: Followed clients' own matching once
  // it knows the followed clients, before that the client the ad was saved for.
  function clientOf(row) {
    const known = window.cvStudioJobLeadsClients?.clientOf?.(row);
    return known !== undefined ? known : row?.client?.name ? row.client : null;
  }
  const postedOf = row => row.date_posted || estimateOf(row);
  const SORTS = {saved_desc:['created_at',-1], saved_asc:['created_at',1], posted_desc:['posted',-1], posted_asc:['posted',1],
    role_asc:['role',1], company_asc:['company',1], client_asc:['client',1]};
  function filtered() {
    const term = el('Search').value.trim().toLocaleLowerCase(), filter = el('Filter').value, folder = el('FolderFilter').value;
    const client = el('ClientFilter').value, days = Number(el('PostedFilter').value), since = days ? localDate(days - 1) : ''; // today and the days before
    // Each ad's client is looked up once per call, not per comparison.
    const owners = new Map(), ownerOf = row => { if (!owners.has(row)) owners.set(row, clientOf(row)); return owners.get(row); };
    const list = rows.filter(row => (folder === '!trash' ? row.deleted : !row.deleted && (folder === '*' || (row.folder || '') === folder)) &&
      (!filter || filter === 'favorite' && row.favorite) &&
      (!client || (client === '!any' ? !!ownerOf(row) : String(ownerOf(row)?.company_id ?? '') === client)) &&
      (!since || postedOf(row) >= since) &&
      (!term || [row.company, row.role, row.contact, row.notes, row.location, ownerOf(row)?.name].some(value => String(value || '').toLocaleLowerCase().includes(term))));
    const [field, direction] = SORTS[el('Sort').value] || [];
    if (!field) return list; // Recently updated: the saved order
    const value = row => field === 'posted' ? postedOf(row) : field === 'client' ? ownerOf(row)?.name || '' : row[field] || '';
    // Blank values sort last in either direction.
    return list.sort((a, b) => { const x = value(a), y = value(b); return !x || !y ? (x ? -1 : y ? 1 : 0) : direction * String(x).localeCompare(String(y)); });
  }
  function syncClients() {
    const select = el('ClientFilter'), old = select.value, clients = new Map();
    for (const row of rows) { const client = clientOf(row); if (client && !row.deleted) clients.set(String(client.company_id), client.name); }
    select.replaceChildren(new Option('All ads', ''), new Option('Any client', '!any'), ...[...clients].sort((a, b) => a[1].localeCompare(b[1])).map(([id, name]) => new Option(name, id)));
    select.value = ['', '!any', ...clients.keys()].includes(old) ? old : '';
    return clients;
  }
  // The manual form opens beside the list only while it is in use.
  function showForm(open) {
    el('FormCard').hidden = !open; el('Layout').dataset.form = open ? 'open' : ''; el('AddManual').hidden = open;
  }
  function node(tag, text, className) {
    const value = document.createElement(tag); value.textContent = text;
    if (className) value.className = className;
    return value;
  }
  function drawPageNumbers(id, current, total, size, navigate) {
    const target = el(id), count = Math.ceil(total / size), key = `${current}:${count}`;
    target.hidden = count < 2;
    if (target.dataset.pages !== key) {
      const restoreFocus = target.contains?.(document.activeElement);
      target.replaceChildren(); target.dataset.pages = key;
      const pages = Array.from({length:count}, (_, index) => index).filter(index =>
        count <= 7 || index === 0 || index === count-1 || Math.abs(index-current) <= 2);
      let previous = -1;
      for (const index of pages) {
        if (index > previous+1) {
          const gap = node('span','…','job-leads-page-gap'); gap.setAttribute('aria-hidden','true'); target.append(gap);
        }
        const button = node('button',String(index+1),'sec job-leads-page-number' + (index === current ? ' is-current' : ''));
        button.type = 'button'; button.dataset.page = String(index);
        button.setAttribute('aria-label','Page ' + (index+1));
        if (index === current) button.setAttribute('aria-current','page');
        button.addEventListener('click', () => { if (!busy && index !== current) navigate(index); });
        target.append(button); previous = index;
      }
      if (restoreFocus) [...target.querySelectorAll('button')].find(button => Number(button.dataset.page) === current)?.focus({preventScroll:true});
    }
    target.querySelectorAll('button').forEach(button => { button.disabled = busy; });
  }
  const DAY = /^\d{4}-\d{2}-\d{2}$/;
  const HR_REUSE_DAYS = 30; // a company's HR scan is reused for this long
  const estimateOf = row => typeof row?.date_posted_estimate === 'string' && DAY.test(row.date_posted_estimate) ? row.date_posted_estimate : '';
  function postedLabel(value) {
    if (!DAY.test(value || '')) return 'Not available';
    const date = new Date(value + 'T00:00:00Z');
    return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat('en-GB', {day:'numeric', month:'short', year:'numeric', timeZone:'UTC'}).format(date) : 'Not available';
  }
  function savedLabel(value) {
    const date = new Date(value);
    return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat('en-GB', {day:'numeric', month:'short', year:'numeric'}).format(date) : '—';
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
    const matching = filtered(), selectable = matching.filter(row => !row.deleted);
    const visible = matching.slice(page*40, (page+1)*40).filter(row => !row.deleted);
    el('SelectAll').disabled = busy || !selectable.some(row => !picked.has(row.id));
    el('UnselectAll').disabled = busy || !picked.size;
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
    el('AdsTabCount').textContent = el('Total').textContent;
    // HR people: each person once per company, keyed as the HR people list is.
    const people = new Set(rows.filter(row => !row.deleted && row.hr).flatMap(row => (row.hr.people || []).map(person =>
      (row.hr.company_id || '') + '|' + String(person.url || '').replace(/\/+$/, '').toLowerCase())));
    const hrCount = document.getElementById('peopleHRTabCount'); if (hrCount) hrCount.textContent = String(people.size);
    el('Due').textContent = String(rows.filter(row => !row.deleted && row.favorite).length);
    updateClear();
    page = Math.min(page, Math.max(0, Math.ceil(selected.length / 40)-1));
    el('Count').textContent = selected.length ? `${page*40+1}–${Math.min((page+1)*40, selected.length)} of ${selected.length}` : '0 leads';
    el('Previous').disabled = busy || page === 0; el('Next').disabled = busy || (page+1)*40 >= selected.length;
    drawPageNumbers('PageNumbers',page,selected.length,40,next => { page = next; render(); });
    updateSelection();
    if (!selected.length) {
      const empty = node('tr'), cell = node('td', rows.length ? 'No matching ads. Change or reset the filters.' : 'No saved ads yet. Search LinkedIn above, pull ads in Followed clients, or add one manually.', 'job-leads-muted');
      cell.colSpan = 11; empty.appendChild(cell); list.appendChild(empty);
    }
    const button = (text, action, cls = 'sec') => { const value = node('button', text, cls); value.type = 'button'; value.disabled = busy; value.addEventListener('click', action); return value; };
    selected.slice(page*40, (page+1)*40).forEach(row => {
      const tr = node('tr'), pick = node('td');
      if (!row.deleted) {
        const checkbox = node('input');
        checkbox.type = 'checkbox'; checkbox.checked = picked.has(row.id); checkbox.disabled = busy;
        checkbox.setAttribute('aria-label', 'Select ' + row.company + ' — ' + row.role);
        checkbox.addEventListener('change', () => { if (busy) return; if (checkbox.checked) picked.add(row.id); else picked.delete(row.id); updateSelection(); chooseGuide('BulkHR'); });
        pick.appendChild(checkbox);
      }
      // An estimate from LinkedIn's "2 weeks ago" is marked with ≈.
      const posted = row.date_posted ? postedLabel(row.date_posted) : estimateOf(row) ? '≈ ' + postedLabel(estimateOf(row)) : '—';
      const title = node('td'), open = button(row.role, () => { if (!busy) selectPreview(row.url, true); }, 'job-lead-title');
      open.setAttribute('aria-label', 'Preview ' + row.role + ' at ' + row.company); title.appendChild(open);
      if (row.notes) title.appendChild(node('div', row.notes.slice(0, 120) + (row.notes.length > 120 ? '…' : ''), 'job-leads-muted'));
      const company = node('td'), employerPage = recordCompanyPage(row);
      if (employerPage) {
        const link = node('a',row.company,'job-lead-company-link'); link.href = employerPage; link.target = '_blank'; link.rel = 'noopener noreferrer';
        link.setAttribute('aria-label','Open ' + row.company + ' on LinkedIn'); company.appendChild(link);
      } else company.textContent = row.company;
      if (row.contact) company.appendChild(node('div', 'Contact: ' + row.contact, 'job-leads-muted'));
      const state = node('td');
      if (!row.deleted) {
        const favorite = button(row.favorite ? '★' : '☆', async () => {
          if (busy) return;
          lock(true);
          try {
            const saved=await api({action:'save',record:{...row,favorite:!row.favorite}});
            if (editing?.id===row.id && editing.revision===row.revision) {
              editing={...editing,revision:saved.record.revision,favorite:saved.record.favorite};
            }
            await load(); status(row.favorite ? 'Removed from favorites.' : 'Added to favorites.');
          } catch (error) { status(error.message); } finally { lock(false); }
        });
        favorite.setAttribute('aria-label', (row.favorite ? 'Unfavorite ' : 'Favorite ') + row.role + ' at ' + row.company);
        favorite.setAttribute('aria-pressed', String(!!row.favorite)); state.append(favorite);
      }
      const hr = node('td');
      if (!row.deleted) hr.appendChild(button(row.hr ? `HR people (${row.hr.people.length})` : 'Find HR', () => { if (!busy) { selectPreview(row.url); chooseGuide('HR'); el('HR').scrollIntoView({block:'nearest',behavior:'smooth'}); } }));
      // The HR people tab, filtered to this company, is where emails are unlocked.
      if (!row.deleted && row.hr?.people?.length && row.hr.company_id) {
        const view = button('View', () => { if (!busy) window.cvStudioPeople?.showHR?.(String(row.hr.company_id)); });
        view.setAttribute('aria-label', 'View HR people for ' + row.company); hr.append(view);
      }
      const actions = node('div', '', 'job-leads-actions');
      const link = node('a', 'Open ↗'); link.href = row.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
      actions.append(link, button(row.deleted ? 'Restore' : 'Edit', () => {
        if (row.deleted) return moveToTrash([row], false);
        if (!busy && discard()) { fill(row); showForm(true); chooseGuide('Form'); status('Editing saved lead.'); el('Form').scrollIntoView({block:'start', behavior:'smooth'}); }
      }));
      if (!row.deleted) actions.appendChild(button('Email client', () => composeEmail(row)));
      if (!row.deleted) actions.appendChild(button('Delete', () => moveToTrash([row], true), 'sec job-lead-delete'));
      const cells = node('td'); cells.appendChild(actions);
      tr.append(pick, node('td', posted), title, company, node('td', clientOf(row)?.name || '—'), node('td', row.location || '—'),
        state, node('td', row.folder || 'Unfiled'), node('td', savedLabel(row.created_at)), hr, cells);
      list.appendChild(tr);
    });
  }
  let emailBusy=false, emailDone=false, emailSentEditable=false, emailAccount=null, emailRequest='', emailGeneration=0, emailComposeGeneration=0;
  let emailFiles=[],emailTemplates=[],emailTemplate='',emailTemplateRevision=null,emailTemplateBusy=false;
  const emailLimit=2560*1024;
  const emailReadOnly=()=>emailDone && !emailSentEditable;
  function emailChanged() {
    if(!emailDone || !emailSentEditable)return;
    emailDone=false;emailSentEditable=false;emailRequest='job-email:'+hex();
    emailMessage('Edited message. Send email will create a new email after confirmation.');
    // Async paste/image insertion already locks controls. Relocking here from
    // its synchronous input event would disable the editor and discard focus.
    if(!emailBusy)emailLock(false);
  }
  const emailDirty=()=>!emailDone && (['To','Cc','Bcc','Subject','Body'].some(name=>el('Email'+name).value.trim()) || emailFiles.length>0 || !!el('EmailEditor').querySelector?.('img'));
  const emailMessage=value=>{el('EmailMessage').textContent=value;};
  function emailLock(value) {
    emailBusy=value;const locked=value || emailTemplateBusy;
    for (const name of ['To','Cc','Bcc','Subject','Body','Files','Image','ImageChoose','Font','Size','Color']) el('Email'+name).disabled=locked || emailReadOnly();
    for (const name of ['Connect','Finish','Close','New']) el('Email'+name).disabled=locked;
    el('EmailEditor').contentEditable=String(!locked && !emailReadOnly());
    for(const button of document.querySelectorAll?.('[data-email-format]') || [])button.disabled=locked || emailReadOnly();
    for(const button of el('EmailAttachments').querySelectorAll('button'))button.disabled=locked || emailReadOnly();
    for(const name of ['Template','TemplateName','TemplateUse','TemplateSave','TemplateCopy','TemplateRefresh'])el('Email'+name).disabled=locked || emailReadOnly() || emailTemplateBusy;
    el('EmailTemplateDelete').disabled=locked || emailReadOnly() || emailTemplateBusy || !emailTemplate;
    el('EmailDraft').disabled=locked || emailDone || !emailAccount?.connected;
    el('EmailSend').disabled=locked || emailDone || !emailAccount?.can_send;
  }
  async function emailInfo() {
    const generation=++emailGeneration;
    try {
      const response=await fetch('/ppc/outlook/api_info',{cache:'no-store'}), data=await response.json();
      if (!response.ok) throw Error(data.error || 'Could not read Outlook account.');
      if (generation!==emailGeneration) return;
      emailAccount=data;
      el('EmailConnect').hidden=!!data.can_send;el('EmailFinish').hidden=!!data.can_send;
      el('EmailAccount').textContent=data.connected ? 'From: '+(data.account?.email || 'Unknown account')+(data.can_send ? '' : ' · Drafts only. Enable Outlook sending to send here.') : 'Connect Outlook in Settings → Integrations & Data, or enable sending below.';
    } catch (error) { if (generation===emailGeneration) {emailAccount=null;el('EmailAccount').textContent=error.message;} }
    emailLock(emailBusy);
  }
  function composeEmail(contact={}) {
    if (emailBusy || emailTemplateBusy) return;
    if (emailDirty() &&
        !window.confirm('Replace the email currently in the composer?')) return;
    const generation=++emailComposeGeneration;
    emailFiles=[];emailTemplate='';emailTemplateRevision=null;el('EmailAttachments').replaceChildren();el('EmailTemplate').value='';el('EmailTemplateName').value='';
    emailSelection=null;emailDone=false;emailSentEditable=false; emailRequest='job-email:'+hex(); emailAccount=null;
    el('EmailTo').value=contact.email || contact.email_result?.email || emailAddressesFromContact(contact.contact).join('; ');
    el('EmailCc').value='';el('EmailBcc').value='';el('EmailRecipients').replaceChildren();
    el('EmailSubject').value=contact.role ? 'Hiring for '+contact.role+(contact.company ? ' at '+contact.company : '') : '';
    el('EmailBody').value='';el('EmailEditor').innerHTML=''; el('EmailOpen').hidden=true;el('EmailOpen').removeAttribute?.('href');el('EmailNew').hidden=true;
    emailMessage('Review the recipient and message. Choose a draft to send in Outlook, or send here.');
    el('EmailCard').hidden=false;emailLock(false);emailInfo();emailLoadTemplates();emailSuggestRecipients(contact,generation);el('EmailCard').scrollIntoView({block:'start',behavior:'smooth'});
  }
  let emailSelection=null;
  function emailFormat(command,value=null) {
    if(emailBusy || emailReadOnly() || emailTemplateBusy)return;
    const editor=el('EmailEditor'),selection=window.getSelection();editor.focus();
    if(emailSelection && editor.contains(emailSelection.commonAncestorContainer)){selection.removeAllRanges();selection.addRange(emailSelection);}
    if(!selection?.rangeCount || !editor.contains(selection.anchorNode) || !editor.contains(selection.focusNode))return;
    document.execCommand(command,false,value);el('EmailBody').value=editor.innerText || editor.textContent;emailChanged();
  }
  const emailEscape=value=>String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  function emailAddresses(value,required=false) {
    const list=[...new Set(String(value || '').split(/[,;\n]+/).map(value=>value.trim()).filter(Boolean))];
    if(list.length>100 || required && !list.length)throw Error('Add 1 to 100 To recipients. Separate addresses with commas or semicolons.');
    for(const address of list)if(address.length>254 || !/^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}$/.test(address))throw Error('Invalid email address: '+address);
    return list;
  }
  function emailAddressesFromContact(value) {
    const matches=String(value || '').match(/[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}/g) || [];
    return [...new Set(matches)];
  }
  function emailSanitizeHTML(source) {
    if(source.length>3500000)throw Error('The formatted message is too large.');
    const template=document.createElement('template');template.innerHTML=source;
    const allowed=new Set(['P','DIV','BR','STRONG','B','EM','I','U','S','STRIKE','UL','OL','LI','BLOCKQUOTE','A','SPAN','H1','H2','H3','H4','TABLE','TBODY','TR','TD','TH','IMG','FONT']);
    const blocked=new Set(['SCRIPT','STYLE','IFRAME','OBJECT','TEMPLATE','SVG','MATH']);let count=0;
    const visit=(node,depth=0)=>{
      if(++count>10000 || depth>100)throw Error('The formatted message is too complex.');
      if(node.nodeType===3)return emailEscape(node.nodeValue);
      if(node.nodeType!==1 || blocked.has(node.tagName))return '';
      const inner=Array.from(node.childNodes).map(child=>visit(child,depth+1)).join('');
      if(!allowed.has(node.tagName))return inner;
      const tag=node.tagName==='FONT'?'span':node.tagName.toLowerCase();let attrs='';
      if(tag==='img') {
        const source=node.getAttribute('src') || '';
        if(!/^data:image\/(png|jpeg|gif);base64,[A-Za-z0-9+/=]+$/.test(source))return '';
        let dimensions='';
        for(const name of ['width','height']){const value=node.getAttribute(name) || '';if(/^[1-9][0-9]{0,3}$/.test(value) && Number(value)<=2000)dimensions+=' '+name+'="'+value+'"';}
        return '<img src="'+emailEscape(source)+'" alt="'+emailEscape(node.getAttribute('alt') || 'Signature banner')+'"'+dimensions+' style="max-width:100%;height:auto">';
      }
      if(tag==='a') {const href=node.getAttribute('href') || '';if(/^(https?:\/\/|mailto:)/i.test(href) && !/[\x00-\x1f]/.test(href))attrs+=' href="'+emailEscape(href)+'"';}
      const align=node.style.textAlign;
      const styles=[];
      if(['left','center','right','justify'].includes(align))styles.push('text-align:'+align);
      if(['bold','normal','400','700'].includes(node.style.fontWeight))styles.push('font-weight:'+node.style.fontWeight);
      if(['italic','normal'].includes(node.style.fontStyle))styles.push('font-style:'+node.style.fontStyle);
      if(['underline','line-through','none'].includes(node.style.textDecoration))styles.push('text-decoration:'+node.style.textDecoration);
      const color=node.style.color || node.getAttribute('color') || '';
      if(/^(#[a-f0-9]{3}([a-f0-9]{3})?|black|red|blue|green|gray|rgb\([0-9 ,]+\))$/i.test(color))styles.push('color:'+color);
      const fontSize=node.style.fontSize || ({1:'8pt',2:'10pt',3:'12pt',4:'14pt',5:'18pt',6:'24pt',7:'36pt'})[node.getAttribute('size')];
      if(fontSize && /^(?:[8-9]|[12][0-9]|3[0-6])(?:px|pt)$/.test(fontSize))styles.push('font-size:'+fontSize);
      const family=node.style.fontFamily || node.getAttribute('face') || '';
      if(family && /^[a-z ,"'-]{1,100}$/i.test(family))styles.push('font-family:'+family.replace(/"/g,"'"));
      if(styles.length)attrs+=' style="'+emailEscape(styles.join(';'))+'"';
      return '<'+tag+attrs+'>'+inner+(tag==='br'?'':'</'+tag+'>');
    };
    return Array.from(template.content.childNodes).map(node=>visit(node)).join('');
  }
  function emailBodyHTML() {
    if(el('EmailEditor').innerHTML) return emailSanitizeHTML(el('EmailEditor').innerHTML);
    return '<div>'+emailEscape(el('EmailBody').value).replace(/\n/g,'<br>')+'</div>';
  }
  async function emailSuggestRecipients(contact,generation) {
    const company=contact.hr?.company_id;
    if(!company || el('EmailTo').value)return;
    try {
      const response=await fetch('/apollo',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'contacts',filters:{company:String(company)}})});
      const data=await response.json();if(!response.ok || !data.ok)throw Error(data.error || 'Could not read saved contacts.');
      if(generation!==emailComposeGeneration || emailDone || emailBusy)return;
      const contacts=(data.contacts || []).filter(row=>String(row.company_id)===String(company) && emailAddressesFromContact(row.email).length);
      const named=contacts.filter(row=>row.name?.toLowerCase()===String(contact.contact || '').trim().toLowerCase());
      const single=named.length===1?named[0]:contacts.length===1?contacts[0]:null;
      if(single && !el('EmailTo').value)el('EmailTo').value=single.email;
      for(const row of contacts) {
        const button=node('button','Add '+row.name+' · '+row.email,'sec');button.type='button';
        button.addEventListener('click',()=>{if(emailBusy || emailReadOnly())return;try{el('EmailTo').value=[...new Set([...emailAddresses(el('EmailTo').value),row.email])].join('; ');emailChanged();}catch(error){emailMessage(error.message);}});
        el('EmailRecipients').append(button);
      }
    }catch(error){if(generation===emailComposeGeneration)emailMessage(error.message+' Enter the recipient manually.');}
  }
  async function emailPaste(event) {
    if(emailBusy || emailReadOnly() || emailTemplateBusy)return;
    event.preventDefault();
    const clipboard=event.clipboardData;
    const html=clipboard.getData('text/html'),plain=clipboard.getData('text/plain');
    const images=Array.from(clipboard.files || []).filter(file=>file.type.startsWith('image/'));
    const editor=el('EmailEditor'),selection=window.getSelection();
    const range=selection?.rangeCount && editor.contains(selection.anchorNode) && editor.contains(selection.focusNode)?selection.getRangeAt(0).cloneRange():null;
    emailLock(true);
    try {
      let clean=html?emailSanitizeHTML(html):emailEscape(plain).replace(/\n/g,'<br>');
      // Outlook can supply rich text and a file image in the same clipboard.
      // Keep the text, and include file images not already embedded in the HTML.
      if(images.length>10 || images.reduce((sum,file)=>sum+file.size,0)>emailLimit)throw Error('Use at most 10 clipboard images, totaling 2.5 MB or less.');
      for(const file of images) {
        if(!['image/png','image/jpeg','image/gif'].includes(file.type) || file.size>emailLimit)throw Error('Use PNG, JPEG or GIF clipboard images of up to 2.5 MB.');
        const source=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=()=>reject(Error('Could not read the pasted image.'));reader.readAsDataURL(file);});
        if(!clean.includes(source))clean+=emailSanitizeHTML('<img src="'+emailEscape(source)+'" alt="Signature banner">');
      }
      const stats=emailImageStats((editor.innerHTML || '')+clean);
      if(stats.count+emailFiles.length>10 || stats.size+emailFiles.reduce((sum,file)=>sum+file.size,0)>emailLimit)throw Error('Use at most 10 files/images, totaling 2.5 MB or less.');
      editor.contentEditable='true';editor.focus();
      if(range && editor.contains(range.commonAncestorContainer)){selection.removeAllRanges();selection.addRange(range);}
      else {const end=document.createRange();end.selectNodeContents(editor);end.collapse(false);selection.removeAllRanges();selection.addRange(end);}
      document.execCommand('insertHTML',false,clean);
      el('EmailBody').value=editor.innerText || editor.textContent;emailChanged();
    }catch(error){emailMessage(error.message);}finally{emailLock(false);}
  }
  function emailImageStats(html) {
    const images=[...new Set(html.match(/data:image\/(?:png|jpeg|gif);base64,[A-Za-z0-9+/=]+/g) || [])];
    return {count:images.length,size:images.reduce((sum,source)=>{const bytes=source.split(',')[1];return sum+bytes.length*3/4-(bytes.endsWith('==')?2:bytes.endsWith('=')?1:0);},0)};
  }
  async function emailInsertImage(file) {
    if(!file || emailBusy || emailReadOnly() || emailTemplateBusy)return;
    const images=emailImageStats(el('EmailEditor').innerHTML || '');
    if(images.count+emailFiles.length>=10 || images.size+emailFiles.reduce((sum,value)=>sum+value.size,0)+file.size>emailLimit){emailMessage('Use at most 10 files/images, totaling 2.5 MB or less.');return;}
    if(!['image/png','image/jpeg','image/gif'].includes(file.type) || file.size>emailLimit){emailMessage('Choose a PNG, JPEG or GIF of up to 2.5 MB.');return;}
    const generation=emailComposeGeneration;
    const insertion=emailSelection?.cloneRange();
    emailLock(true);
    try {
      const source=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=()=>reject(Error('Could not read the image.'));reader.readAsDataURL(file);});
      if(generation!==emailComposeGeneration)return;
      const clean=emailSanitizeHTML('<img src="'+emailEscape(source)+'" alt="Signature banner">');
      const editor=el('EmailEditor'),selection=window.getSelection();
      editor.contentEditable='true';editor.focus();
      if(insertion && editor.contains(insertion.commonAncestorContainer)){
        selection.removeAllRanges();selection.addRange(insertion);
      }else{
        const end=document.createRange();end.selectNodeContents(editor);end.collapse(false);selection.removeAllRanges();selection.addRange(end);
      }
      // Separate editable lines let Enter move the banner down, including in an
      // empty editor. Keep the range captured before the file picker/async lock.
      const marker=hex();
      document.execCommand('insertHTML',false,'<div data-email-banner="'+marker+'"><div><br></div><div>'+clean+'</div><div><br></div></div>');
      const wrapper=editor.querySelector('[data-email-banner="'+marker+'"]');
      if(!wrapper)throw Error('Could not insert the banner. Click in the message and try again.');
      wrapper.removeAttribute('data-email-banner');
      const after=document.createRange();after.setStart(wrapper.lastElementChild,0);after.collapse(true);
      selection.removeAllRanges();selection.addRange(after);emailSelection=after.cloneRange();
      el('EmailBody').value=editor.innerText || editor.textContent;emailChanged();
      emailMessage('Banner embedded. Save the template to keep it with your signature.');
    }catch(error){emailMessage(error.message);}finally{emailLock(false);}
  }
  function emailRenderFiles() {
    el('EmailAttachments').replaceChildren();
    emailFiles.forEach((file,index)=>{const item=node('li',file.name+' · '+Math.ceil(file.size/1024)+' KB '),remove=node('button','Remove','sec');remove.type='button';remove.disabled=emailBusy || emailReadOnly();remove.addEventListener('click',()=>{if(emailBusy || emailReadOnly())return;emailFiles.splice(index,1);emailChanged();emailRenderFiles();});item.append(remove);el('EmailAttachments').append(item);});
  }
  async function emailAttach() {
    if(emailBusy || emailReadOnly())return;
    const files=Array.from(el('EmailFiles').files || []);el('EmailFiles').value='';
    const images=emailImageStats(el('EmailEditor').innerHTML || '');
    if(images.count+emailFiles.length+files.length>10 || images.size+[...emailFiles,...files].reduce((sum,file)=>sum+file.size,0)>emailLimit){emailMessage('Attach at most 10 files, totaling 2.5 MB or less.');return;}
    emailLock(true);
    try {
      const added=[];
      for(const file of files) {
        if(file.name.length>200 || /[\x00-\x1f\x7f/\\]/.test(file.name))throw Error('The attachment filename is invalid.');
        const contentBytes=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1] || '');reader.onerror=()=>reject(Error('Could not read '+file.name));reader.readAsDataURL(file);});
        added.push({name:file.name,size:file.size,contentBytes});
      }
      emailFiles.push(...added);emailChanged();emailRenderFiles();emailMessage('Attachments added. Review them before sending.');
    }catch(error){emailMessage(error.message);}finally{emailLock(false);}
  }
  function emailTemplateChoices(selected=emailTemplate) {
    el('EmailTemplate').replaceChildren(new Option('No template',''),...emailTemplates.map(value=>new Option(value.name,value.id)));
    emailTemplate=emailTemplates.some(value=>value.id===selected)?selected:'';if(!emailTemplate)emailTemplateRevision=null;el('EmailTemplate').value=emailTemplate;emailLock(emailBusy);
  }
  async function emailLoadTemplates() {
    if(emailTemplateBusy)return;
    emailTemplateBusy=true;emailLock(emailBusy);
    try {const response=await fetch('/job-leads?action=email_templates',{cache:'no-store'}),data=await response.json();if(!response.ok || !data.ok)throw Error(data.error || 'Could not read templates.');emailTemplates=data.templates;emailTemplateChoices();el('EmailTemplateMessage').textContent='Templates save the subject, formatted message, signature and embedded banner.';}
    catch(error){el('EmailTemplateMessage').textContent=error.message;}
    finally{emailTemplateBusy=false;emailLock(emailBusy);}
  }
  function emailApplyTemplate() {
    if(emailBusy || emailReadOnly() || emailTemplateBusy)return;
    const selected=el('EmailTemplate').value,template=emailTemplates.find(value=>value.id===selected);
    if(!template){emailTemplate='';emailTemplateRevision=null;el('EmailTemplateName').value='';emailLock(false);return;}
    if((el('EmailSubject').value || el('EmailBody').value || el('EmailEditor').querySelector('img')) && !window.confirm('Replace this subject and message with the selected template?')){el('EmailTemplate').value=emailTemplate;return;}
    try {
      const html=emailSanitizeHTML(template.html);
      emailSelection=null;el('EmailEditor').innerHTML=html;el('EmailBody').value=el('EmailEditor').innerText || el('EmailEditor').textContent;
      el('EmailSubject').value=template.subject;el('EmailTemplateName').value=template.name;emailTemplate=selected;emailTemplateRevision=template.revision;emailChanged();emailLock(false);
    }catch(error){emailMessage(error.message);el('EmailTemplate').value=emailTemplate;}
  }
  async function emailSaveTemplate(copy=false,remove=false) {
    if(emailBusy || emailReadOnly() || emailTemplateBusy)return;
    const template=emailTemplates.find(value=>value.id===emailTemplate);
    if(remove && (!template || !window.confirm('Delete template "'+template.name+'"?')))return;
    let payload;
    try {payload=remove?{action:'email_template_delete',id:template.id,revision:emailTemplateRevision}:{action:'email_template_save',name:el('EmailTemplateName').value.trim(),subject:el('EmailSubject').value,html:emailBodyHTML(),...(!copy && template?{id:template.id,revision:emailTemplateRevision}:{})};if(!remove && !payload.name)throw Error('Enter a template name first.');}
    catch(error){el('EmailTemplateMessage').textContent=error.message;return;}
    emailTemplateBusy=true;emailLock(emailBusy);
    try {const response=await fetch('/job-leads',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),data=await response.json();if(!response.ok || !data.ok)throw Error(data.error || 'Could not update the template.');emailTemplates=data.templates;emailTemplateChoices(remove?'':data.id);emailTemplateRevision=emailTemplates.find(value=>value.id===emailTemplate)?.revision ?? null;if(remove)el('EmailTemplateName').value='';el('EmailTemplateMessage').textContent=remove?'Template deleted. Your message has been kept.':'Template saved.';}
    catch(error){el('EmailTemplateMessage').textContent=error.message;}
    finally{emailTemplateBusy=false;emailLock(emailBusy);}
  }
  async function emailSubmit(send) {
    if (emailBusy || emailDone || emailTemplateBusy) return;
    let to,cc,bcc,html;
    const subject=el('EmailSubject').value.trim();
    try {
      to=emailAddresses(el('EmailTo').value,true);cc=emailAddresses(el('EmailCc').value);bcc=emailAddresses(el('EmailBcc').value);
      if(to.length+cc.length+bcc.length>100)throw Error('Use at most 100 recipients in total.');
      html=emailBodyHTML();
      const images=emailImageStats(html);
      if(images.count+emailFiles.length>10 || images.size+emailFiles.reduce((sum,file)=>sum+file.size,0)>emailLimit)throw Error('Use at most 10 files/images, totaling 2.5 MB or less.');
      if(!subject || !el('EmailBody').value.trim() && !/<img\b/.test(html))throw Error('Enter a subject and message.');
    }catch(error){emailMessage(error.message);return;}
    emailLock(true);
    let attempted=false;
    try {
      // Re-read the connection before showing the sender in the confirmation.
      const previousSender=emailAccount?.account?.email;
      await emailInfo();
      if (!emailAccount?.connected || !emailAccount.account?.email) throw Error('Connect Outlook before creating or sending this email.');
      if (previousSender && previousSender!==emailAccount.account.email) throw Error('The Outlook account changed. Review the sender and try again.');
      if (send && !emailAccount.can_send) throw Error('Enable Outlook sending and approve Mail.Send first.');
      if (!window.confirm((send?'Send this email now?':'Create this draft in Outlook?')+'\n\nFrom: '+emailAccount.account.email+'\nTo: '+to.join('; ')+'\nCC: '+(cc.join('; ') || 'None')+'\nBCC: '+(bcc.join('; ') || 'None')+'\nSubject: '+subject+'\nAttachments: '+(emailFiles.map(file=>file.name).join(', ') || 'None')+'\nEmbedded images: '+(html.match(/<img\b/g) || []).length)) return;
      attempted=true;emailDone=true;emailSentEditable=false;
      const payload={composer_version:2,to,cc,bcc,subject,html,attachments:emailFiles.map(({name,contentBytes})=>({name,contentBytes})),request_id:emailRequest,sender:emailAccount.account.email};
      if (send) Object.assign(payload,{action:'outlook_send',confirmed:true});
      const response=await fetch(send?'/job-leads':'/ppc/outlook/create_draft',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const result=await response.json();
      if (!response.ok || !result.ok) {
        if (result.retry_safe===true || result.state==='rejected') {
          emailDone=false;emailRequest='job-email:'+hex();attempted=false;
        }
        throw Error(result.error || 'The Outlook result could not be confirmed. Check Outlook before composing again.');
      }
      if (send) {emailSentEditable=true;emailMessage('Accepted by Outlook for sending. You can edit this message here and send another email after confirmation.');}
      else {
        const url=new URL(result.webLink);
        if (url.protocol!=='https:' || !/^(outlook\.office\.com|outlook\.office365\.com|outlook\.live\.com)$/.test(url.hostname)) throw Error('Draft created. Open Outlook Drafts to review and send it.');
        el('EmailOpen').href=url.href;el('EmailOpen').hidden=false;emailMessage('Draft created. Open it in Outlook to review and send.');
      }
    } catch (error) { emailMessage(attempted ? error.message+' Check Outlook before composing another email.' : error.message); }
    finally {el('EmailNew').hidden=!emailDone;emailLock(false);}
  }
  const searchStatus = value => { el('SearchStatus').textContent = value; };
  const savedJob = url => rows.find(row => jobLink(row.url) === url);
  function recordCompanyPage(row) {
    return companyPage(row?.company_url) || (row?.hr && row.hr.company === row.company ? companyPage(row.hr.company_url) : '');
  }
  const previewRow = () => previewCapture?.url === previewUrl ? previewCapture : savedJob(previewUrl) || discovered.find(row => row.url === previewUrl);
  const previewSequence = () => previewSource === 'search' ? discovered : filtered();
  function applySavedFilters() {
    if (hrRunning) return;
    picked.clear(); page = 0; render();
    if (previewSource === 'saved' && !previewSequence().some(row => row.url === previewUrl)) { previewUrl = ''; previewCapture = null; }
    drawDiscovery();
  }
  function selectPreview(url, scroll = false, source = 'saved') {
    if (previewUrl !== url) hrFailedUrl='';
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
    el('SearchResults').setAttribute('aria-busy',String(discovering));
    el('SearchStatus').classList.toggle('is-running',discovering);
    el('BackgroundStatus').classList.toggle('is-running',!!backgroundAds);
    const adsFailed = discovered.some(row => !row.full && (backgroundFailed || row.fullError));
    el('SearchPanel').classList.toggle('has-error',!discovering && !backgroundAds && (discoveryFailed || adsFailed));
    el('BackgroundStatus').classList.toggle('has-error',!discovering && !backgroundAds && adsFailed);
    for (const name of ['SearchStart','SearchRefresh','SearchMode','SearchQuery','SearchLocation','SearchPages','SearchSource','SearchFolder','SearchClear']) el(name).disabled = busy;
    el('SearchStop').disabled = !discovering || discoveryStopped;
    el('SearchStop').hidden = !discovering;
    el('SearchClear').hidden = !discovered.length && !discovering;
    el('SearchAdd').hidden = !discovered.length;
    el('SearchSelection').hidden = !discovered.length;
    el('SearchOpen').hidden = el('SearchMode').value !== 'open';
    const visible = discovered.slice(discoveryPage*20, (discoveryPage+1)*20).filter(row => !savedJob(row.url));
    el('SearchSelectPage').disabled = busy || !visible.length;
    el('SearchSelectPage').checked = !!visible.length && visible.every(row => discoveryPicked.has(row.url));
    el('SearchSelectPage').indeterminate = !el('SearchSelectPage').checked && visible.some(row => discoveryPicked.has(row.url));
    el('SearchAdd').disabled = busy || !discovered.some(row => discoveryPicked.has(row.url) && !savedJob(row.url));
    el('SearchPrevious').disabled = busy || discoveryPage === 0;
    el('SearchNext').disabled = busy || (discoveryPage+1)*20 >= discovered.length;
    el('SearchPageRange').textContent = discovered.length ? `${discoveryPage*20+1}–${Math.min((discoveryPage+1)*20,discovered.length)} of ${discovered.length}` : '';
    drawPageNumbers('SearchPageNumbers',discoveryPage,discovered.length,20,next => navigateResults(next-discoveryPage));
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
    el('HR').classList.toggle('is-running',hrRunning && !bulkHR?.running);
    el('HR').classList.toggle('has-error',!hrRunning && !!hrFailedUrl && previewUrl === hrFailedUrl);
    bulkHRControls();
    el('BackgroundStart').hidden = !discovered.some(row => !row.full);
    el('BackgroundStart').disabled = busy || discovering || !!backgroundAds;
    el('BackgroundStop').hidden = !backgroundAds;
    el('BackgroundStop').disabled = !backgroundAds || backgroundAds.stopped;
    el('SearchPagination').hidden = !discovered.length;
    nextGuide();
  }
  function drawPreview() {
    const row = previewRow(), saved = row && row === savedJob(row.url);
    const sequence = previewSequence(), index = sequence.findIndex(item => item.url === previewUrl);
    el('PreviewPosition').textContent = row ? (previewSource === 'search' ? 'Search results' : 'Saved ads') +
      (index >= 0 ? ` · ${index+1} of ${sequence.length}` : ' · Outside current filters') : '';
    el('Preview').hidden=!row;
    el('PreviewTitle').textContent = row?.role || '';
    el('PreviewCompany').textContent = row?.company || '';
    el('PreviewMeta').textContent = row ? [row.location,saved || row.fullOrigin==='saved' ? 'Saved ad content' : row.full ? 'Captured ad content' : 'Search summary · Read full ad for the description',row.description_truncated ? 'Excerpt' : ''].filter(Boolean).join(' · ') : '';
    content(el('PreviewContent'),row?.description || '',row?.description_rich);
    drawHR(row ? savedJob(row.url) : null);
  }
  function drawDiscovery() {
    const target = el('SearchResults'), scroll = discoveryRenderedPage === discoveryPage ? target.scrollTop || 0 : 0;
    const expanded = new Set(), focus = {};
    for (const card of target.children) {
      if ([...card.querySelectorAll('details')].some(item => item.open)) expanded.add(card.dataset.url);
      const controls = [...card.querySelectorAll('button, input, a[href], summary')];
      const index = controls.indexOf(document.activeElement);
      if (index >= 0) { focus.url = card.dataset.url; focus.index = index; }
    }
    target.replaceChildren();
    discoveryPage = Math.min(discoveryPage, Math.max(0,Math.ceil(discovered.length/20)-1));
    if (!previewRow() && !previewDismissed) previewUrl = previewSequence()[0]?.url || '';
    el('Curation').hidden=!discovered.length && !previewRow();
    el('SearchResults').hidden = !discovered.length;
    el('SearchColumn').hidden = !discovered.length;
    el('Curation').className = 'job-leads-curation' + (!discovered.length ? ' no-search-results' : '') + (!previewRow() ? ' no-preview' : '');
    if (savedJob(previewUrl) && !savedJob(previewUrl).deleted) el('Curation').className += ' has-hr';
    el('SearchCount').textContent = `${discovered.length} found · ${discoveryPicked.size} selected`;
    for (const row of discovered.slice(discoveryPage*20, (discoveryPage+1)*20)) {
      const card = node('article','','job-leads-discovery-card' + (row.url === previewUrl ? ' is-previewing' : '') + (discoveryPicked.has(row.url) && !savedJob(row.url) ? ' is-selected' : ''));
      card.dataset.url = row.url;
      const openPreview=()=>{if(!busy)selectPreview(row.url,true,'search');};
      card.addEventListener('click',event=>{
        if(busy || event?.defaultPrevented)return;
        const control=event?.target?.closest?.('a, button, input, label, select, textarea, details, [role="button"]');
        if(control && card.contains(control))return;
        const selection=window.getSelection?.();
        if(selection?.toString() && (card.contains(selection.anchorNode) || card.contains(selection.focusNode)))return;
        openPreview();
      });
      const heading = node('div','','job-ad-card-heading'), identity = node('div','','job-ad-card-identity');
      const initials = String(row.company || '').trim().split(/\s+/).slice(0,2).map(word => Array.from(word)[0] || '').join('').toLocaleUpperCase() || 'AD';
      const mark = node('span',initials,'job-ad-company-mark'); mark.setAttribute('aria-hidden','true');
      const titleHeading=node('h3',''),title=node('button',row.role,'job-ad-card-title');
      title.type='button';title.setAttribute('aria-label','Preview '+row.role+' at '+row.company);
      title.addEventListener('click',openPreview);titleHeading.append(title);
      identity.append(titleHeading,node('p',row.company,'job-ad-company'));
      heading.append(mark,identity);
      const saved = savedJob(row.url), actions = node('div','','job-leads-actions job-ad-card-actions');
      if (saved) { discoveryPicked.delete(row.url); heading.append(node('span',saved.deleted ? 'Already in Trash' : 'Already saved','job-ad-saved')); }
      else {
        const pick = node('label','','job-leads-pick'), input = node('input');
        input.type = 'checkbox'; input.value = row.url; input.checked = discoveryPicked.has(row.url);
        input.setAttribute('aria-label','Select found ad ' + row.company + ' — ' + row.role);
        input.addEventListener('change', () => { if (busy) return; if (input.checked) discoveryPicked.add(row.url); else discoveryPicked.delete(row.url); drawDiscovery(); });
        pick.append(input,document.createTextNode('Select')); heading.append(pick);
      }
      card.append(heading);
      const meta = node('div','','job-ad-card-meta');
      if (row.location) meta.append(node('p',row.location,'job-ad-location'));
      const state = row.full ? 'ready' : row.fullState === 'reading' ? 'loading' : row.fullError ? 'error' : 'summary';
      meta.append(node('span',row.full ? row.fullOrigin==='saved' ? 'Saved full ad' : 'Full ad captured' : state === 'loading' ? 'Loading full ad…' : state === 'error' ? 'Could not load full ad' : 'Search summary only','job-ad-state is-' + state));
      card.append(meta);
      if (row.fullError && !row.full) card.append(node('p',row.fullError,'job-ad-card-error'));
      const link = node('a','Open on LinkedIn'); link.href = row.url; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.className = 'job-ad-source';
      const read = node('button',row.full ? 'View full ad' : row.fullError ? 'Retry full ad' : 'Read full ad','sec'); read.type = 'button'; read.addEventListener('click', () => previewDiscovered(row)); actions.append(read);
      actions.append(link); card.append(actions);
      const details = node('details'), summary = node('summary',row.full ? 'View job ad content' : 'View search summary');
      details.open = expanded.has(row.url);
      details.append(summary); const body = node('div'); content(body,row.description,row.description_rich); details.append(body); card.append(details);
      target.append(card);
      if (focus.url === row.url) [...card.querySelectorAll('button, input, a[href], summary')][focus.index]?.focus({preventScroll:true});
    }
    el('SearchCount').textContent = `${discovered.length} found · ${discoveryPicked.size} selected`;
    drawPreview(); discoveryControls();
    target.scrollTop = discoveryRenderedPage === discoveryPage ? scroll : 0;
    discoveryRenderedPage = discoveryPage;
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
    for (const other of ['HR','BulkHR']) if (other!==prefix) setHRPreferenceControls(other,value);
    try { localStorage.setItem(hrPreferenceKey,JSON.stringify(value)); } catch {}
    bulkHRControls();
  }
  function hrJoinedLabel(value) {
    if (typeof value !== 'string' || !/^(?:19|20)\d{2}(?:-(?:0[1-9]|1[0-2]))?$/.test(value)) return 'Not available';
    return value.length === 4 ? value : ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][Number(value.slice(5))-1]+' '+value.slice(0,4);
  }
  function hrEmployment(value) {
    const {joined,left,current}=value;
    if (!('left' in value) && !('current' in value)) return {};
    if (typeof left !== 'string' || !/^(?:(?:19|20)\d{2}(?:-(?:0[1-9]|1[0-2]))?)?$/.test(left) || ![true,false,null].includes(current) ||
        current===true && (!joined || left) || current===false && (!joined || !left) || current===null && (joined || left) ||
        left && (joined.length===4?joined+'-01':joined)>(left.length===4?left+'-12':left)) throw Error('The HR employment dates could not be confirmed.');
    return {left,current};
  }
  function hrEmploymentLabel(person) {
    const start=hrJoinedLabel(person.joined);
    if (start==='Not available') return person._employment==='checking'?'Checking…':person.employment_status==='not_shown' || person._employment==='observed'?'Not confirmed':'Not checked';
    try { hrEmployment(person); } catch { return 'Not available'; }
    return start+(person.current===true?' to Present':person.current===false?' to '+hrJoinedLabel(person.left):'');
  }
  function hrPeople(people) {
    const target = el('HRResults'); target.replaceChildren();
    window.cvStudioApollo?.begin(savedJob(previewUrl));
    for (const person of people || []) {
      if (!/^https:\/\/www\.linkedin\.com\/in\/[A-Za-z0-9_%~-]+\/?$/.test(person?.url || '')) continue;
      const card = node('article','','job-leads-hr-person'), link = node('a',person.name);
      link.href=person.url; link.target='_blank'; link.rel='noopener noreferrer';
      card.append(link,node('p',person.title),node('p',person.location || 'Location not shown','job-leads-muted'),node('p','Employment: '+hrEmploymentLabel(person),'job-leads-muted'),node('p','Matched: '+person.matched,'job-leads-muted'));
      window.cvStudioPeople?.decorateDate(card,savedJob(previewUrl),person);
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
    el('HRMessage').textContent = search ? `${search.people.length} saved matches · ${search.people.filter(p=>p.joined).length}/${search.people.length} employment dates confirmed · ${search.country || 'Any country'} · Last scan ${createdLabel(search.scanned_at)}. ${search.complete ? '' : 'Limited scan; more matches may be available. '}LinkedIn company association; titles are keyword matches.` : 'Use the connected Chrome companion to scan this company. Results will be saved with this ad. No AI charge.';
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
    chooseGuide('HR');guideTried=true;
    let settings;try { settings=hrSettings('HR'); } catch(error) { el('HRMessage').textContent=error.message;nextGuide(true);return; }
    rememberHRPreferences();
    const activity=beginScanActivity();let outcome;
    hrFailedUrl=''; hrStopped=false; hrRunning=true; hrRun=''; lock(true);
    try { outcome=await scanHR(row,{...settings,companyURL:el('HRCompanyURL').value.trim()},value=>{el('HRMessage').textContent=value;},hrPeople); }
    finally {
      const failed=!outcome || outcome.state==='failed' || outcome.stopQueue;
      hrFailedUrl=failed ? row.url : ''; hrRunning=false;lock(false);finishScanActivity(activity,failed);
    }
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
  // One LinkedIn company page URL per company, or '' when it is not one.
  function companyPage(url) {
    const match=String(url || '').match(/^https:\/\/www\.linkedin\.com\/company\/([A-Za-z0-9_-]+)(?:\/(?:people|about|life))?\/?$/);
    return match ? 'https://www.linkedin.com/company/'+match[1]+'/' : '';
  }
  // The employer link on this exact ad, or '' when the ad cannot be read.
  async function adCompanyPage(row) {
    hrCapture=hex();
    try {
      const captured=await rpc('jobFromLink',{url:row.url,company_only:true,operation_id:hrCapture});
      return captured?.url===row.url ? companyPage(captured.company_url) : '';
    } catch { return ''; }
    finally { hrCapture=''; }
  }
  async function scanHR(row, {country,keywords,pages,companyURL,expectedRedirectURL}, notify, showPeople, recovery=0) {
    const found = new Map();let finalSnapshot=null,omitted=false,outcome,cleanupFailed=false,saving=false,retryCompanyURL='';
    let companyName=row.hr?.company_name || row.company, jobURL='',expectedID='';
    hrRun='';
    try {
      notify('Checking the companion…');
      const companion = await rpc('jobStatus',{},1500); checkHR();
      if (companion?.profile_browsing_revision !== 1) throw Error('Apply the latest companion update, then refresh CV Studio and LinkedIn to keep browsing safely during scans.');
      if (companion?.concurrent_scans_revision !== 1) throw Error('Apply the latest companion update, then refresh CV Studio and LinkedIn to run Job Leads and Sourcer together.');
      if (companion?.hr_apply_transition_revision !== 1) throw Error('Apply the latest companion update, then refresh CV Studio and LinkedIn to use the corrected company-selection check.');
      if (!companion?.connected || companion.company_hr_revision !== 1 || companion.hr_company_identity_revision !== 1 || companion.hr_company_filter_revision !== 1 || companion.hr_company_source_revision !== 1 || companion.hr_resilience_revision !== 1 || companion.hr_layout_revision !== 1 || companion.hr_joined_revision !== 1 || companion.hr_joined_loading_revision !== 1 || companion.hr_employment_revision !== 1 || companion.hr_experience_page_revision !== 1 || companion.hr_employment_shapes_revision !== 1 || companion.hr_keyword_revision !== 1) throw Error('Apply the latest companion update, then refresh CV Studio and LinkedIn to use the corrected HR search and joining-date checks.');
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
      companyURL=companyPage(companyURL);
      if (!companyURL) throw Error('The company link is unavailable. Enter its LinkedIn company page under Search options.');
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
            const entry={...person,url:profileURL,joined:'',_employment:'checking'};
            found.set(profileURL,entry); showPeople([...found.values()]);
            // Read only this observed profile, one background tab at a time.
            // A missing/slow Experience section is optional evidence, never a
            // fabricated date or reason to erase otherwise valid HR matches.
            let navigationWaits=0,dateWaits=0;
            try {
              for (let attempt=0;attempt<80;attempt++) {
                checkHR(); notify(`Checking when ${person.name} joined ${row.company}…`);
                const value=await rpc('hrJoined',{run_id:hrRun,tab_id:source.tab_id,url:profileURL}); checkHR();
                if (value && !value.loading) {
                  if (value.url !== profileURL || typeof value.joined !== 'string' || !/^(?:(?:19|20)\d{2}(?:-(?:0[1-9]|1[0-2]))?)?$/.test(value.joined)) throw Error('An HR joining date could not be confirmed.');
                  Object.assign(entry,{joined:value.joined},hrEmployment(value));entry._employment=value.employment_status==='not_checked'?'not_checked':'observed';break;
                }
                // A slow profile navigation must not use up the separate,
                // bounded Experience hydration budget before the reader runs.
                if(value?.wait_stage==='profile_navigation' ? ++navigationWaits>=60 : ++dateWaits>=20) break;
                await pauseDiscovery();
              }
            } finally {
              if(entry._employment==='checking') entry._employment='not_checked';
              showPeople([...found.values()]);
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
      const search={company:row.company,company_name:finalSnapshot.company_name || companyName,company_url:finalSnapshot.company_url || companyURL,company_id:finalSnapshot.company_id,
        country,keywords,source_url:finalSnapshot.source_url,complete,people:[...found.values()].map(({_employment,...person})=>({...person,employment_status:person.joined?'observed':_employment==='observed'?'not_shown':'not_checked'}))};
      const response = await api({action:'save_hr',id:row.id,revision:row.revision,search});
      const index = rows.findIndex(item=>item.id===row.id); if (index >= 0) rows[index]=response.record;
      if (editing?.id === row.id) editing={...editing,revision:response.record.revision,hr:response.record.hr};
      hrRow=''; render(); drawPreview();
      const employmentConfirmed=[...found.values()].filter(person=>person.joined).length;
      const message=`${found.size} HR matches saved · ${employmentConfirmed}/${found.size} employment dates confirmed · ${country || 'Any country'} · Last scan ${createdLabel(response.record.hr.scanned_at)}. ${complete ? 'No further results shown by LinkedIn.' : 'Page/result limit reached; more people may be available on LinkedIn.'}`+(expectedID?' The ad could not be reread; its previously saved company identity was reconfirmed.':'');
      outcome={state:'saved',matches:found.size,employmentConfirmed,complete,message,search};notify(message);
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
    if (outcome.state==='saved' && !outcome.stopQueue && hrFailedUrl===row.url) hrFailedUrl='';
    return outcome;
  }
  function bulkHRControls() {
    for (const name of ['CountryMode','Country','Pages','Keywords']) el('BulkHR'+name).disabled=busy;
    el('BulkHRStart').disabled=busy || !rows.some(row=>picked.has(row.id) && !row.deleted);
    el('BulkHRStop').disabled=!bulkHR?.running || bulkHR.ui!==jobAdsHRUI || hrStopped;
    el('BulkHRProgress').classList.toggle('has-error',!!bulkHR && bulkHR.ui===jobAdsHRUI && !bulkHR.running && !!bulkHR.hasError);
    let resume=false;
    try { resume=bulkHRPlan(rows.filter(row=>picked.has(row.id) && !row.deleted),hrSettings('BulkHR')).resume; } catch {}
    el('BulkHRStart').textContent=resume?'Resume unfinished ads':'Scan selected ads';
  }
  function bulkHRPlan(selection,settings,prefix='BulkHR') {
    const previous=bulkCheckpoints[prefix],ids=selection.map(row=>row.id).sort();
    const same=previous && previous.items.length===ids.length && previous.items.map(item=>item.id).sort().every((id,index)=>id===ids[index]) &&
      ['country','keywords','pages'].every(key=>previous.settings[key]===settings[key]);
    const items=selection.map(row=>{
      const old=same && previous.items.find(item=>item.id===row.id);
      return {row,saved:!!old && old.state==='saved' && old.revision===row.revision,priority:!old || old.state==='saved'?2:old.state==='waiting'?1:0};
    });
    const resume=!!same && items.some(item=>!item.saved);
    if(!resume)for(const item of items){item.saved=false;item.priority=1;}
    return {resume,items};
  }
  function rememberBulkHR() {
    const checkpoint={version:1,settings:bulkHR.settings,items:bulkHR.items.map(item=>({id:item.row.id,
      revision:item.node.dataset.state==='saved' ? (rows.find(row=>row.id===item.row.id)?.revision || item.row.revision) : item.row.revision,state:item.node.dataset.state}))};
    // Only opaque ad IDs, revisions, outcomes and selected settings are kept.
    // No people, emails, URLs, partial results or automatic browser work.
    bulkCheckpoints[bulkHR.ui.prefix]=checkpoint;
    try { localStorage.setItem(bulkCheckpointKeys[bulkHR.ui.prefix],JSON.stringify(checkpoint)); } catch {}
  }
  function stopHR() {
    if (!hrRunning) return;
    hrStopped=true;el('HRMessage').textContent='Stopping after the current read…';
    if(hrCapture)rpc('jobReadCancel',{operation_id:hrCapture}).catch(()=>{});
    if (bulkHR?.running) bulkHR.ui.part('Message').textContent='Stopping after the current read. Completed ads are already saved; remaining ads will not start.';
    discoveryControls();
  }
  function bulkHRSummary() {
    bulkHR.ui.part('Bar').value=bulkHR.completed;
    bulkHR.ui.part('Summary').textContent=`${bulkHR.completed} of ${bulkHR.items.length} ads processed · ${bulkHR.saved} saved · ${bulkHR.failed} failed`+(bulkHR.cancelled ? ` · ${bulkHR.cancelled} stopped` : '');
  }
  // The Job ads queue UI parts.
  const jobAdsHRUI={prefix:'BulkHR',part:name=>el('BulkHR'+name),guide:true};
  async function startBulkHR(ids=null,ui=jobAdsHRUI) {
    const chosen=ids ? new Set(ids) : picked;
    const selection=rows.filter(row=>chosen.has(row.id) && !row.deleted).map(row=>({...row}));
    if (busy || !selection.length) return false;
    if (ui.guide) { chooseGuide('BulkHR');guideTried=true; }
    let settings;
    try {
      if (selection.length>40) { if (ui.guide) guideIssue='SelectPage'; throw Error('Select up to 40 ads for one HR scan. You can run the next group afterward.'); }
      settings=hrSettings(ui.prefix);
    } catch(error) {
      ui.part('Progress').hidden=false;ui.part('Bar').hidden=true;ui.part('Summary').textContent='';ui.part('Results').replaceChildren();ui.part('Message').textContent=error.message;if (ui.guide) nextGuide(true);return false;
    }
    rememberHRPreferences(ui.prefix);
    const plan=bulkHRPlan(selection,settings,ui.prefix);
    const activity=beginScanActivity();
    if (ui.guide) el('BulkHRNextStep').hidden=true;
    hrStopped=false;hrRunning=true;bulkHR={running:true,ui,settings,completed:0,saved:0,failed:0,cancelled:0,items:[]};
    ui.part('Results').replaceChildren();ui.part('Progress').hidden=false;ui.part('Bar').hidden=false;
    ui.part('Bar').max=selection.length;
    for (const entry of plan.items) {
      const {row,saved,priority}=entry,title=row.company+' — '+row.role,item=node('li',title+(saved?' · Previously saved':' · Waiting'));item.dataset.state=saved?'saved':'waiting';
      if(saved){bulkHR.completed++;bulkHR.saved++;}
      bulkHR.items.push({row,title,node:item,priority});ui.part('Results').appendChild(item);
    }
    bulkHRSummary();rememberBulkHR();lock(true);
    let stoppedReason='';
    // HR people belong to the company, not the ad: each LinkedIn company is
    // scanned once in a run. Another selected ad with the same employer name
    // has its own employer link read first, and only an exact match of the
    // scanned company page gets the saved result copied without a scan.
    const companyKey=row=>String(row.company || '').trim().toLocaleLowerCase();
    const scannedCompanies=new Map(), scannedNames=new Set();
    // Other saved ads scanned in the last 30 days with the same country and
    // keywords count too: such a company is not scanned again. The server
    // copies that scan with its original date, so a reused result never looks
    // newer than it is. The selected ads themselves are never sources, so
    // selecting an ad always scans it (or its company) afresh.
    const recentSince=Date.now()-HR_REUSE_DAYS*86400000, selectedIds=new Set(selection.map(row=>row.id));
    const recent=other=>!other.deleted && !selectedIds.has(other.id) && !!other.hr && other.hr.country===settings.country && other.hr.keywords===settings.keywords &&
      Date.parse(other.hr.scanned_at)>=recentSince && !!companyPage(other.hr.company_url);
    for (const other of rows) if (recent(other)) {
      const page=companyPage(other.hr.company_url), known=scannedCompanies.get(page);
      if (!known || known.scannedAt<other.hr.scanned_at) scannedCompanies.set(page,{source:other.id,matches:other.hr.people.length,title:other.company+' — '+other.role,scannedAt:other.hr.scanned_at});
      scannedNames.add(companyKey(other));
    }
    try {
      for (const item of bulkHR.items.filter(item=>item.node.dataset.state!=='saved').sort((a,b)=>a.priority-b.priority)) {
        if (hrStopped) break;
        const row=item.row;let shared=null,page='';
        if (scannedNames.has(companyKey(row))) {
          ui.part('Message').textContent=`Ad ${bulkHR.completed+1} of ${selection.length} · ${item.title} · Checking the company on this ad…`;
          page=await adCompanyPage(row);
          if (hrStopped) break;
          shared=scannedCompanies.get(page) || null;
        }
        if (shared) {
          item.node.dataset.state='running';item.node.textContent=item.title+' · Copying from the same company…';
          ui.part('Message').textContent=`Ad ${bulkHR.completed+1} of ${selection.length} · ${item.title} · Copying HR people from ${shared.title}…`;
          let unconfirmed='';
          try {
            const response=await api(shared.source ? {action:'save_hr',id:row.id,revision:row.revision,reuse_from:shared.source,company_url:page}
              : {action:'save_hr',id:row.id,revision:row.revision,search:{...shared.search,company:row.company}});
            const index=rows.findIndex(value=>value.id===row.id);if(index>=0)rows[index]=response.record;
            // Same bookkeeping as a scanned save: the open form keeps the new revision.
            if (editing?.id === row.id) editing={...editing,revision:response.record.revision,hr:response.record.hr};
            item.node.dataset.state='saved';item.node.textContent=item.title+` · ${shared.matches} HR matches copied from ${shared.title} (same company${shared.scannedAt ? ', scanned ' + savedLabel(shared.scannedAt) : ''}, no extra scan)`;
            if (savedJob(previewUrl)?.id===row.id) drawPreview(); // the new revision redraws its saved HR
            if (hrFailedUrl===row.url) hrFailedUrl='';
            bulkHR.saved++;
          } catch(error) {
            // Like a scanned save: a conflict keeps the ad; any other failure
            // may have saved, so the queue stops until saved ads are refreshed.
            if (error.code!=='JOB_LEADS_CONFLICT') unconfirmed=error.message+' The save could not be confirmed. Refresh saved ads before trying again. No ad details were edited.';
            item.node.dataset.state='failed';item.node.textContent=item.title+' · '+(unconfirmed || error.message+' Previous saved results and ad details were kept.');bulkHR.failed++;
          }
          bulkHR.completed++;bulkHRSummary();rememberBulkHR();render();
          if (unconfirmed) { stoppedReason=unconfirmed;break; }
          continue;
        }
        item.node.dataset.state='running';item.node.textContent=item.title+' · Scanning…';
        rememberBulkHR();
        const notify=message=>{
          ui.part('Message').textContent=`Ad ${bulkHR.completed+1} of ${selection.length} · ${item.title} · ${message}`;
          if (savedJob(previewUrl)?.id===row.id) el('HRMessage').textContent=message;
        };
        const showPeople=people=>{if (savedJob(previewUrl)?.id===row.id) hrPeople(people);};
        const outcome=await scanHR(row,{...settings,companyURL:row.hr?.company_url || ''},notify,showPeople);
        if (outcome.state==='saved' && companyPage(outcome.search?.company_url)) {
          scannedCompanies.set(companyPage(outcome.search.company_url),{search:outcome.search,matches:outcome.matches,title:item.title});scannedNames.add(companyKey(row));
        }
        item.node.dataset.state=outcome.state;
        item.node.textContent=item.title+' · '+(outcome.state==='saved' ? `${outcome.matches} HR matches saved${outcome.complete ? '' : ' · Limited scan'} · ${outcome.employmentConfirmed}/${outcome.matches} employment dates confirmed` : outcome.message);
        bulkHR.completed++;if (outcome.state==='saved') bulkHR.saved++;else if (outcome.state==='failed') bulkHR.failed++;else bulkHR.cancelled++;
        bulkHRSummary();rememberBulkHR();
        if (outcome.stopQueue) { stoppedReason=outcome.message;break; }
      }
    } catch(error) {
      stoppedReason=error.message;
      const active=bulkHR.items.find(item=>item.node.dataset.state==='running');
      if (active) {active.node.dataset.state='failed';active.node.textContent=active.title+' · '+error.message;bulkHR.completed++;bulkHR.failed++;}
    }
    finally {
      bulkHR.hasError=bulkHR.failed>0 || !!stoppedReason;
      bulkHR.running=false;hrRunning=false;
      const remaining=bulkHR.items.length-bulkHR.completed;
      for (const item of bulkHR.items) if (item.node.dataset.state==='waiting') item.node.textContent=item.title+' · Not started';
      rememberBulkHR();
      ui.part('Message').textContent=(hrStopped || stoppedReason ? 'Queue stopped. ' : 'Queue finished. ')+`${bulkHR.saved} ads saved, ${bulkHR.failed} failed${bulkHR.cancelled ? ', '+bulkHR.cancelled+' stopped' : ''}${remaining ? ', '+remaining+' not started' : ''}. `+(stoppedReason || 'Completed results are saved with each ad.');
      if (ui.guide) el('BulkHRNextStep').hidden=!bulkHR.saved; // next step: the saved HR people
      bulkHRSummary();lock(false);finishScanActivity(activity,bulkHR.failed>0 || !!stoppedReason);
    }
    return true;
  }
  function savedFullContent(row) {
    const saved=savedJob(row.url);
    if(!saved || saved.deleted || saved.description_truncated!==false || !saved.description?.trim())return null;
    return {...row,company_url:companyPage(row.company_url) || (row.company===saved.company ? recordCompanyPage(saved) : ''),description:saved.description,description_rich:saved.description_rich || [],
      description_truncated:false,full:true,fullOrigin:'saved',fullState:'ready',fullError:''};
  }
  function rememberJobs(snapshot) {
    for (const row of window.cvStudioJobSearch.rows(snapshot)) {
      if (discovered.some(item => item.url === row.url) || discovered.length >= 600) continue;
      discovered.push(savedFullContent(row) || {...row,description_truncated:true,description_rich:[],full:false});
    }
    drawDiscovery();backgroundAdStatus('');
  }
  function checkDiscovery() { if (discoveryStopped) throw Error('Stopped.'); }
  const pauseDiscovery = () => new Promise(resolve => setTimeout(resolve,350));
  const beginScanActivity = () => typeof markTabRunning === 'function' ? markTabRunning('jobleads',{acknowledgePrevious:true}) : null;
  function finishScanActivity(token, failed) {
    if (token === null) return;
    if (failed && typeof markTabFailed === 'function') markTabFailed('jobleads',token,{forceBrowser:true});
    else if (typeof markTabDone === 'function') markTabDone('jobleads',token,{forceBrowser:true});
  }
  async function startDiscovery() {
    if (busy) return;
    chooseGuide('Search');guideTried=true;
    const pages = Number(el('SearchPages').value), useOpen = el('SearchMode').value === 'open';
    const query = el('SearchQuery').value.trim(), where = el('SearchLocation').value.trim();
    if (!Number.isInteger(pages) || pages < 1 || pages > 15) { searchStatus('Choose 1 to 15 pages.'); guide('SearchPages',true,true); return; }
    if (!useOpen && (!query || query.length > 240 || where.length > 160 || /[\x00-\x1f]/.test(query + where))) { searchStatus('Enter job keywords and an optional location.'); guide(!query || query.length > 240 || /[\x00-\x1f]/.test(query) ? 'SearchQuery' : 'SearchLocation',true,true); return; }
    if (useOpen && !el('SearchSource').value) { searchStatus('Refresh search tabs and choose an open LinkedIn job search.'); guide('SearchRefresh',false,true); return; }
    discoveryFailed=false; backgroundFailed=false;
    discovering = true; discoveryStopped = false; discoveryRun = '';
    const activity=beginScanActivity();let failed=false, prefetch=false;
    lock(true); searchStatus('Checking the browser companion…');
    try {
      await stopBackgroundAds('Paused for a new search.');
      const companion = await rpc('jobStatus',{},1000).catch(() => null);
      checkDiscovery();
      if (!companion?.connected || companion.concurrent_scans_revision !== 1 || companion.job_search !== true || !Number.isInteger(companion.job_search_revision) || companion.job_search_revision < 1) { guideIssue='SearchSetupGuide';el('SearchPanel').open=true; }
      if (!companion?.connected) throw Error('Open this CV Studio address in Chrome or Brave with the companion enabled. It connects automatically. Use Set up companion once if needed. LinkedIn job search cannot run inside the Codex preview.');
      if (companion.concurrent_scans_revision !== 1) throw Error('Apply the latest companion update, then refresh CV Studio and LinkedIn to run Job Leads and Sourcer together.');
      if (companion.job_search !== true || !Number.isInteger(companion.job_search_revision) || companion.job_search_revision < 1) throw Error('Update and reload the latest companion, refresh CV Studio and LinkedIn, then reconnect this tab to enable the current job search. Updating CV Studio alone does not update the companion.');
      if (companion.busy) throw Error('Finish the current companion search or ad read before starting another search.');
      prefetch = companion.full_ad_background_revision === 1;
      discoveryRun = hex(); discovered = []; discoveryPicked.clear(); discoveryPage = 0; previewUrl = ''; previewCapture = null;
      previewSource = 'search'; previewDismissed = false;
      drawDiscovery(); backgroundAdStatus(''); searchStatus('Opening the LinkedIn job search in Chrome…');
      const source = await rpc('jobSearchBegin',{run_id:discoveryRun,query,location:where,max_pages:pages,use_open:useOpen,source_tab_id:Number(el('SearchSource').value)});
      checkDiscovery();
      await window.cvStudioJobSearch.walk({rpc,run:discoveryRun,tab:source.tab_id,pages,check:checkDiscovery,keep:rememberJobs,
        page:index => searchStatus(`Reviewed ${index+1} of ${pages} pages. ${discovered.length} unique ads found.`),full:() => discovered.length >= 600});
      checkDiscovery(); searchStatus(`Found ${discovered.length} ads.`);
    } catch (error) { failed=!discoveryStopped;searchStatus(discoveryStopped ? `Stopped. ${discovered.length} ads found so far are kept for review.` : error.message + ' Ads already found are kept.'); }
    finally {
      if (discoveryRun) { try { await rpc('end',{run_id:discoveryRun}); } catch { prefetch=false; } }
      discoveryFailed=failed; discoveryRun = ''; discovering = false; lock(false); drawDiscovery();
      if (prefetch && !failed && !discoveryStopped) startBackgroundAds();
      finishScanActivity(activity,failed);
    }
  }
  function fullAd(row, data) {
    if (jobLink(data?.url || '') !== row.url || !data.company || !data.role) throw Error('This ad changed while it was being read.');
    if (!data.description?.trim()) {
      const error = Error('The full content was not available. Its search summary is kept.');
      error.companionCode = 'HR_AD_EMPTY'; throw error;
    }
    return {...row,company:data.company,company_url:companyPage(data.company_url) || (row.company===data.company ? companyPage(row.company_url) : ''),role:data.role,location:data.location || '',date_posted:data.date_posted || '',
      date_posted_estimate:data.date_posted ? '' : estimateOf(data) || estimateOf(row),
      description:data.description,description_rich:data.description_rich || [],description_truncated:data.description_truncated === true,
      full:true,fullOrigin:'captured',fullState:'ready',fullError:''};
  }
  async function readFullContent(row, operation, read = rpc, queue = null) {
    const check = () => {
      if (queue?.stopped) { const error=Error('Full-ad loading was stopped.'); error.companionCode='HR_STOPPED'; throw error; }
    };
    try {
      const data=await prepareSource(await read('jobFromLink',{url:row.url,operation_id:operation}));
      check(); fullAd(row,data); return data;
    } catch (browserError) {
      check();
      // Older companions omitted the code on this exact, fixed loading error.
      // Treat that known ad timeout consistently without guessing at other errors.
      if(!browserError.companionCode && browserError.message==='The LinkedIn ad did not finish loading. Open it in your browser, wait for the page to load, then try again.')browserError.companionCode='HR_AD_TIMEOUT';
      // A second, independent parser can read public ads even when LinkedIn's
      // signed-in layout is unknown. Never fall back around an access check or
      // a disconnected/busy companion, and never replay either read.
      if (!['HR_AD_TIMEOUT','HR_AD_LAYOUT','HR_AD_EMPTY'].includes(browserError.companionCode)) throw browserError;
      if(Date.now()<publicJobPausedUntil) {
        browserError.message+=' Public reads are paused; this ad’s summary is kept.';
        throw browserError;
      }
      const controller=typeof AbortController==='function'?new AbortController():null;
      if(queue)queue.publicController=controller;
      try {
        const data=(await api({action:'lookup',url:row.url},controller?.signal)).record;
        check(); fullAd(row,data); return data;
      } catch (publicError) {
        check();
        if(publicError.code==='JOB_AD_RATE_LIMITED') {
          browserError.message+=' Public reads are temporarily paused; this ad’s summary is kept.';
          throw browserError;
        }
        if(publicError.code!=='JOB_AD_UNAVAILABLE')throw publicError;
        browserError.message+=' The public job page could not be read either; the previous content is kept.';
        throw browserError;
      } finally { if(queue)queue.publicController=null; }
    }
  }
  function backgroundAdStatus(message) {
    const ready = discovered.filter(row => row.full).length, failed = discovered.filter(row => row.fullError && !row.full).length;
    el('BackgroundStatus').textContent = discovered.length ? `${ready} of ${discovered.length} full ads ready` +
      (failed ? ` · ${failed} could not load` : '') + (Date.now()<publicJobPausedUntil ? ' · Public reads paused; Chrome companion only' : '') + (message ? ' · ' + message : '') : '';
  }
  async function stopBackgroundAds(message = 'Stopped. Resume loading whenever you are ready.') {
    const queue = backgroundAds;
    if (!queue) return;
    queue.stopped = true; queue.message = message; queue.publicController?.abort(); backgroundAdStatus('Stopping full-ad loading…'); discoveryControls();
    if (queue.operation) await rpc('jobReadCancel',{operation_id:queue.operation}).catch(() => {});
    await queue.done;
  }
  function startBackgroundAds() {
    if (busy || discovering || backgroundAds) return;
    backgroundFailed=false;
    for(const row of discovered){if(!row.full){const saved=savedFullContent(row);if(saved)Object.assign(row,saved);}}
    drawDiscovery();backgroundAdStatus('');
    if(!discovered.some(row=>!row.full))return;
    const queue = {stopped:false,operation:'',message:'',failed:false,activity:beginScanActivity()}; backgroundAds = queue;
    backgroundAdStatus('Checking the browser companion…');
    queue.done = Promise.resolve().then(async () => {
      try {
        const status = await sendRPC('jobStatus',{},1500);
        if (queue.stopped) return;
        if (!status?.connected || status.full_ad_background_revision !== 1) throw Error('Apply the companion update to load full ads in the background.');
        if (status.busy) throw Error('The companion is busy. Resume full ads after its current action finishes.');
        for (const row of [...discovered]) {
          while (busy && !queue.stopped) await pauseDiscovery();
          if (queue.stopped || !discovered.includes(row)) break;
          if (row.full) continue;
          const saved=savedFullContent(row);
          if(saved){Object.assign(row,saved);backgroundAdStatus('Loading descriptions in the background…');drawDiscovery();continue;}
          queue.operation = hex(); row.fullState = 'reading'; row.fullError = '';
          backgroundAdStatus('Loading descriptions in the background…'); drawDiscovery();
          try {
            const data = await readFullContent(row,queue.operation,sendRPC,queue);
            if (!queue.stopped && discovered.includes(row)) {
              Object.assign(row,fullAd(row,data));
              if (previewCapture?.url === row.url) previewCapture = {...row};
            }
          } catch (error) {
            if (!queue.stopped && discovered.includes(row)) {
              row.fullError = error.message.slice(0,500);
              if (!['HR_AD_TIMEOUT','HR_AD_LAYOUT','HR_AD_UNAVAILABLE','HR_AD_EMPTY'].includes(error.companionCode)) {
                queue.stopped = true; queue.message = error.message;
              }
            }
          } finally {
            queue.operation = ''; if (row.fullState === 'reading') row.fullState = '';
            drawDiscovery();
          }
          // Pace sequential reads; never open a pool of LinkedIn tabs.
          if (!queue.stopped) await pauseDiscovery();
        }
      } catch (error) { queue.message = error.message; queue.failed=!queue.stopped; }
      finally {
        if (backgroundAds === queue) { backgroundAds = null; backgroundFailed=queue.failed; }
        backgroundAdStatus(queue.message || 'Finished. You can retry ads that could not load.'); discoveryControls();
        finishScanActivity(queue.activity,queue.failed || discovered.some(row=>row.fullError && !row.full));
      }
    });
    discoveryControls(); return queue.done;
  }
  async function previewDiscovered(row, source = 'search') {
    if (busy) return;
    selectPreview(row.url, false, source);
    const cached = discovered.find(value => value.url === row.url && value.full);
    if (row.full || cached) {
      previewCapture = {...(cached || row)}; drawDiscovery(); return;
    }
    const activity=beginScanActivity();let failed=false;
    lock(true); searchStatus('Reading the selected ad in Chrome…');
    try {
      const data = await readFullContent(row,hex());
      // Reading a saved ad is a temporary preview; never overwrite its durable content or editing draft.
      previewCapture = fullAd(row,data);
      const found = discovered.find(value => value.url === row.url); if (found) Object.assign(found,previewCapture);
      backgroundAdStatus('');
      searchStatus(savedJob(row.url) ? 'Full ad captured for preview. To update the saved content, use Edit → Refresh content, then save.' : 'Full ad captured for review. Select it and Add selected to list when ready.');
    } catch (error) { failed=true;searchStatus(error.message + ' The previous content or search summary is still available.'); }
    finally { lock(false); drawDiscovery();finishScanActivity(activity,failed); }
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
        const record = {url:row.url,company:row.company,...(companyPage(row.company_url)?{company_url:row.company_url}:{}),role:row.role,location:row.location,date_posted:row.date_posted,
          date_posted_estimate:row.date_posted ? '' : estimateOf(row),
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
  async function rpc(action, args = {}, waitMs) {
    if (backgroundAds && action !== 'jobReadCancel') {
      await stopBackgroundAds('Paused for your browser action. Resume loading when ready.');
    }
    return sendRPC(action,args,waitMs);
  }
  function sendRPC(action,args = {},waitMs) {
    return new Promise((resolve, reject) => {
      const id = hex(), timer = setTimeout(() => { pending.delete(id); reject(Error('The companion did not respond. Refresh this CV Studio tab after reloading the companion. Use Chrome or Brave, and click the companion toolbar icon once if this installation has not been connected. Saved ads remain available below.')); }, waitMs ?? (action === 'jobFromLink' ? 55000 : 12000));
      pending.set(id, {resolve, reject, timer});
      window.postMessage({type:'CVSTUDIO_LINKEDIN_REQUEST', id, channel, scope:'leads', action, args}, location.origin);
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
  function jobLink(value) { return window.cvStudioJobSearch.jobLink(value); }
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
      const record = {url,company:data.company,...(companyPage(data.company_url)?{company_url:data.company_url}:{}),role:data.role,location:data.location || '',date_posted:data.date_posted || '',
        date_posted_estimate:data.date_posted ? '' : estimateOf(data),
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
    chooseGuide('Form');guideTried=true;
    const url = jobLink(el('url').value);
    if (!url) { status('Paste a LinkedIn job ad link to fill in its details.'); guide('url',true,true); return; }
    if (editing && jobLink(editing.url) !== url) { status('Click New lead before filling a different job ad. Your current lead has been kept.'); return; }
    const previousSource = lastReadUrl, changedSource = previousSource && previousSource !== url;
    if (changedSource && !window.confirm('Use this different job ad? Its details will replace this draft, including contact, notes and dates. The folder will be kept.')) {
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
      if (typeof data.company === 'string' && el('company').value.trim() === data.company.trim()) {
        draftCompanyURL = companyPage(data.company_url) || (!changedSource && before.company === data.company ? companyPage(before.company_url) : '');
        draftCompanyName = data.company.trim();
      } else { draftCompanyURL = ''; draftCompanyName = ''; }
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
    el('BulkHRStart').addEventListener('click',()=>startBulkHR());el('BulkHRStop').addEventListener('click',stopHR);
    el('BulkHRNext').addEventListener('click',()=>{if(!busy)window.cvStudioPeople?.showHR?.('');});
    setHRPreferenceControls('BulkHR',preferredHR || {countryMode:'',country:'',pages:3});
    el('BulkHRKeywords').value=hrDefaultKeywords;el('BulkHRProgress').hidden=true;
    el('HRCountryMode').addEventListener('change',()=>{ el('HRCountry').hidden=el('HRCountryLabel').hidden=!el('HRCountryMode').value; rememberHRPreferences(); chooseGuide('HR'); });
    el('HRCountry').addEventListener('input',()=>{rememberHRPreferences();chooseGuide('HR');});
    el('HRPages').addEventListener('change',()=>{rememberHRPreferences();chooseGuide('HR');});
    for (const name of ['HRKeywords','HRCompanyURL']) el(name).addEventListener('input',()=>chooseGuide('HR'));
    el('BulkHRCountryMode').addEventListener('change',()=>{el('BulkHRCountry').hidden=el('BulkHRCountryLabel').hidden=!el('BulkHRCountryMode').value;rememberHRPreferences('BulkHR');chooseGuide('BulkHR');});
    el('BulkHRCountry').addEventListener('input',()=>{rememberHRPreferences('BulkHR');chooseGuide('BulkHR');});
    el('BulkHRPages').addEventListener('change',()=>{rememberHRPreferences('BulkHR');chooseGuide('BulkHR');});
    el('BulkHRKeywords').addEventListener('input',()=>{bulkHRControls();chooseGuide('BulkHR');});
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
    el('BackgroundStart').addEventListener('click',startBackgroundAds);
    el('BackgroundStop').addEventListener('click',() => stopBackgroundAds());
    el('SearchStop').addEventListener('click',async () => {
      if (!discovering) return;
      discoveryStopped = true; discoveryControls(); searchStatus('Stopping after the current browser read. Found ads will be kept.');
      if (discoveryRun) { try { await rpc('end',{run_id:discoveryRun}); } catch {} }
    });
    el('SearchMode').addEventListener('change',()=>{discoveryControls();chooseGuide('Search');});
    for (const name of ['SearchQuery','SearchLocation','SearchPages','SearchSource']) el(name).addEventListener(name === 'SearchSource' ? 'change' : 'input',()=>chooseGuide('Search'));
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
    el('SearchClear').addEventListener('click',async () => {
      if (busy) return;
      lock(true);
      try {
        await stopBackgroundAds(); discoveryFailed=false; backgroundFailed=false; hrFailedUrl=''; discovered = []; discoveryPicked.clear(); discoveryPage = 0;
        previewUrl = ''; previewCapture = null; previewDismissed = true;
        backgroundAdStatus(''); searchStatus('Search results cleared. Your saved ads are kept.');
        if(typeof clearTabActivityNotifications==='function')clearTabActivityNotifications('jobleads');
      } finally { lock(false); drawDiscovery(); }
    });
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
      stopBackgroundAds().catch(() => {});
      if(hrCapture)rpc('jobReadCancel',{operation_id:hrCapture}).catch(()=>{});
      if (discoveryRun) rpc('end',{run_id:discoveryRun}).catch(() => {});
      if (hrRun) rpc('end',{run_id:hrRun}).catch(() => {});
    });
    fields.forEach(key => el(key).addEventListener('input', () => {
      dirty = true;
      if (key === 'folder') rememberFolder(el(key).value.trim());
      if (key !== 'url' && !lastReadUrl) lastReadUrl = jobLink(el('url').value);
      if (key === 'description') { descriptionTruncated = false; descriptionRich = []; descriptionHint(); }
      chooseGuide('Form');
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
    el('Save').addEventListener('click',()=>{chooseGuide('Form');guideTried=true;nextGuide(true);});
    el('Form').addEventListener('invalid',()=>{guideFlow='Form';guideTried=true;guideIssue='';nextGuide(true);},true);
    el('Form').addEventListener('submit', async event => {
      event.preventDefault(); if (busy) return;
      chooseGuide('Form');guideTried=true;
      if (lastReadUrl && jobLink(el('url').value) !== lastReadUrl) { status('This is a different job ad. Use Fill from link to replace the draft, or New lead to enter it manually. Your current details have been kept.'); guide('AutoFill',false,true); return; }
      lock(true); status('Saving lead…');
      try {
        const value = await api({action:'save', record:{...draft(), ...(editing ? {id:editing.id, revision:editing.revision} : {})}});
        await load();
        if (value.duplicate) {
          status(value.record.deleted ? 'This job is already saved in Trash. Your draft has been kept; restore the existing lead from Trash.' : 'This job is already saved. Your draft has been kept; use Edit on the existing lead to change it.');
        } else { fill(value.record); status('Lead saved on this computer.'); }
      } catch (error) { status(error.message); }
      finally { lock(false); }
    });
    el('New').addEventListener('click', () => { if (!busy && discard()) { fill(null); chooseGuide('Form'); status('Ready for another job ad.'); } });
    el('Refresh').addEventListener('click', async () => { if (busy) return; lock(true); try { await load(); status('Saved leads refreshed. Reopen a lead to load its latest changes.'); } catch (error) { status(error.message); } finally { lock(false); } });
    for (const id of ['Search', 'Filter', 'FolderFilter', 'ClientFilter', 'PostedFilter', 'Sort']) el(id).addEventListener(id === 'Search' ? 'input' : 'change', applySavedFilters);
    el('FiltersReset').addEventListener('click', () => {
      if (busy && hrRunning) return;
      el('Search').value = ''; el('Sort').value = '';
      for (const id of ['Filter', 'ClientFilter', 'PostedFilter']) el(id).value = '';
      el('FolderFilter').value = '*'; applySavedFilters();
    });
    for(const name of ['To','Cc','Bcc','Subject'])el('Email'+name).addEventListener('input',emailChanged);
    el('EmailEditor').addEventListener('input',()=>{el('EmailBody').value=el('EmailEditor').innerText || el('EmailEditor').textContent;emailChanged();});
    el('EmailEditor').addEventListener('paste',emailPaste);
    el('EmailEditor').addEventListener('drop',event=>event.preventDefault());
    for(const button of document.querySelectorAll?.('[data-email-format]') || []) {
      button.addEventListener('mousedown',event=>event.preventDefault());
      button.addEventListener('click',()=>{const command=button.dataset.emailFormat;let value=null;if(command==='createLink'){value=window.prompt('Enter an https:// link or mailto: email link');if(!value || !/^(https?:\/\/|mailto:)/i.test(value))return;}emailFormat(command,value);});
    }
    document.addEventListener('selectionchange',()=>{const selection=window.getSelection?.();if(document.activeElement===el('EmailEditor') && selection?.rangeCount && el('EmailEditor').contains(selection.anchorNode) && el('EmailEditor').contains(selection.focusNode))emailSelection=selection.getRangeAt(0).cloneRange();});
    el('EmailFont').addEventListener('change',()=>emailFormat('fontName',el('EmailFont').value));
    el('EmailSize').addEventListener('change',()=>emailFormat('fontSize',el('EmailSize').value));
    el('EmailColor').addEventListener('change',()=>emailFormat('foreColor',el('EmailColor').value));
    el('EmailImageChoose').addEventListener('mousedown',event=>{event.preventDefault();const selection=window.getSelection();if(document.activeElement===el('EmailEditor') && selection?.rangeCount && el('EmailEditor').contains(selection.anchorNode) && el('EmailEditor').contains(selection.focusNode))emailSelection=selection.getRangeAt(0).cloneRange();});
    el('EmailImageChoose').addEventListener('click',()=>{if(!emailBusy && !emailReadOnly() && !emailTemplateBusy)el('EmailImage').click();});
    el('EmailImage').addEventListener('change',()=>{const file=el('EmailImage').files?.[0];el('EmailImage').value='';emailInsertImage(file);});
    el('EmailFiles').addEventListener('change',emailAttach);
    el('EmailTemplate').addEventListener('change',emailApplyTemplate);
    el('EmailTemplateUse').addEventListener('click',emailApplyTemplate);
    el('EmailTemplateRefresh').addEventListener('click',emailLoadTemplates);
    el('EmailTemplateSave').addEventListener('click',()=>emailSaveTemplate());
    el('EmailTemplateCopy').addEventListener('click',()=>emailSaveTemplate(true));
    el('EmailTemplateDelete').addEventListener('click',()=>emailSaveTemplate(false,true));
    el('EmailCompose').addEventListener('click',()=>composeEmail());
    el('EmailClose').addEventListener('click',()=>{if(!emailBusy)el('EmailCard').hidden=true;});
    el('EmailDraft').addEventListener('click',()=>emailSubmit(false));
    el('EmailSend').addEventListener('click',()=>emailSubmit(true));
    el('EmailNew').addEventListener('click',()=>composeEmail());
    el('EmailConnect').addEventListener('click',async()=>{if(emailBusy)return;emailLock(true);try{await window.ppcStartOutlookLogin?.(true);}catch(error){emailMessage(error.message);}finally{await emailInfo();emailLock(false);}});
    el('EmailFinish').addEventListener('click',async()=>{if(emailBusy)return;emailLock(true);try{await window.ppcFinishOutlookLogin?.();}catch(error){emailMessage(error.message);}finally{await emailInfo();emailLock(false);}});
    el('AddManual').addEventListener('click', () => { if (!busy && discard()) { fill(null); showForm(true); chooseGuide('Form'); el('url').focus(); } });
    el('FormClose').addEventListener('click', () => { if (!busy && discard()) { fill(null); showForm(false); chooseGuide('Search'); } });
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
      render(); chooseGuide('BulkHR');
    });
    el('SelectAll').addEventListener('click', () => {
      if (busy) return;
      for (const row of filtered()) if (!row.deleted) picked.add(row.id);
      render(); chooseGuide('BulkHR');
    });
    el('UnselectAll').addEventListener('click', () => {
      if (busy) return;
      picked.clear(); render(); chooseGuide('BulkHR');
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
      const keys = ['company','role','folder','created_at','date_posted','contact','favorite','follow_up','url','location','notes','description'];
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
    window.addEventListener('beforeunload', event => { if (dirty || busy || emailBusy || emailTemplateBusy || emailDirty()) { event.preventDefault(); event.returnValue = ''; } });
    fill(null); lock(true);
    try {
      await load();
      if (preferredFolder && !folderNames.includes(preferredFolder)) { rememberFolder(null); el('folder').value = ''; }
      status('');
    }
    catch (error) { status(error.message); }
    finally { lock(false); }
  };
  function download(blob, name) {
    const url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  // Followed clients opens its saved ads here, filtered to one client (or any).
  // Ads saved from Followed clients are read again first, so none is missing.
  async function showClientAds(companyId = '!any') {
    document.getElementById('jobLeadsApolloAdsTab')?.click();
    // Filters stay as they are while an HR scan runs (its selection is in use).
    if (hrRunning) { status('Client ads can be listed when the HR scan finishes or is stopped.'); return; }
    if (!busy) { lock(true); try { await load(); } catch (error) { status(error.message); } finally { lock(false); } }
    if (hrRunning) return;
    // Only the client filter applies, so every saved ad of the client shows.
    el('Search').value = ''; el('Filter').value = ''; el('PostedFilter').value = ''; el('FolderFilter').value = '*';
    el('ClientFilter').value = syncClients().has(String(companyId)) ? String(companyId) : '!any';
    applySavedFilters(); el('List').scrollIntoView?.({block:'start', behavior:'smooth'});
  }
  // Update my clients: show today's folder and find HR people for its new
  // ads (up to 40 per run; recently scanned companies are reused).
  async function scanSavedAds(ids, folder) {
    document.getElementById('jobLeadsApolloAdsTab')?.click();
    if (busy || hrRunning) { status('Job Leads is busy. Select the new ads in ' + folder + ' and click Scan selected ads when it finishes.'); return false; }
    lock(true); try { await load(); } catch (error) { status(error.message); return false; } finally { lock(false); }
    el('Search').value = ''; el('Filter').value = ''; el('PostedFilter').value = ''; el('ClientFilter').value = '';
    el('FolderFilter').value = folderNames.includes(folder) ? folder : '*'; applySavedFilters();
    const live = ids.filter(id => rows.some(row => row.id === id && !row.deleted)), chosen = live.slice(0, 40);
    if (live.length > chosen.length) status(`${live.length - chosen.length} more new ads can be scanned afterwards: select them in ${folder} and click Scan selected ads.`);
    return chosen.length ? startBulkHR(chosen) : false;
  }
  window.cvStudioJobLeads={composeEmail,refresh:load,redraw:()=>{if(ready){syncClients();render();}},showClientAds,scanSavedAds,lock:value=>lock(value),isBusy:()=>busy,stopHR,hrRunning:()=>hrRunning,employment:hrEmploymentLabel,statusLabels:Object.freeze({...labels}),rpc,activityStart:beginScanActivity,activityEnd:finishScanActivity};
  document.addEventListener('DOMContentLoaded', () => { if (new URLSearchParams(location.search).get('module') === 'jobleads') switchTab('jobleads'); });
})();
