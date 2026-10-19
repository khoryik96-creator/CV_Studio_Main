/* Job Leads: durable local records; the companion only fills a reviewable draft. */
(function () {
  'use strict';
  const el = id => document.getElementById('jobLeads' + id);
  const labels = {new:'New', to_contact:'To contact', contacted:'Contacted', follow_up:'Following up', won:'Won', closed:'Closed'};
  const fields = ['url', 'company', 'role', 'contact', 'location', 'date_posted', 'status', 'follow_up', 'notes', 'description'];
  const hex = () => crypto.randomUUID().replaceAll('-', '');
  const channel = hex(), pending = new Map();
  let rows = [], editing = null, busy = false, dirty = false, page = 0, ready = false, lastReadUrl = '', descriptionTruncated = false;
  const status = message => { el('Message').textContent = message; };
  function localDate() {
    const d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }
  const due = row => row.follow_up && row.follow_up <= localDate() && !['won', 'closed'].includes(row.status);
  function draft() { return {...Object.fromEntries(fields.map(key => [key, el(key).value])), description_truncated:descriptionTruncated}; }
  function descriptionHint() {
    el('DescriptionNote').textContent = descriptionTruncated || el('description').value.length >= 20000 ? 'Captured excerpt. Open the LinkedIn ad for the complete content.' : 'This captured text is saved with the lead and can be read here later.';
  }
  function fill(record) {
    fields.forEach(key => { el(key).value = record?.[key] || (key === 'status' ? 'new' : ''); });
    editing = record?.id ? record : null; dirty = false;
    lastReadUrl = record?.url || '';
    descriptionTruncated = record?.description_truncated === true; descriptionHint();
    el('Heading').textContent = editing ? 'Edit lead' : 'Save a job ad';
    el('Save').textContent = editing ? 'Save changes' : 'Save lead';
  }
  function discard() { return !dirty || window.confirm('Discard the unsaved changes in this lead?'); }
  function lock(value) {
    busy = value;
    for (const id of ['Save', 'New', 'Read', 'Tabs', 'Refresh', 'Restore', 'AutoFill', 'BrowserFill']) el(id).disabled = value;
    for (const name of fields) el(name).disabled = value;
    el('List').querySelectorAll('button').forEach(button => { button.disabled = value; });
  }
  async function api(body) {
    const response = await fetch('/job-leads', body ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body), ...(body.action === 'lookup' ? {timeout:30000} : {})} : {});
    const data = await response.json();
    if (!response.ok || data.error) throw Error(data.error || 'Job Leads could not finish this request.');
    return data;
  }
  async function load() { rows = (await api()).records; render(); }
  function filtered() {
    const term = el('Search').value.trim().toLocaleLowerCase(), filter = el('Filter').value;
    return rows.filter(row => (!filter || row.status === filter || filter === 'due' && due(row)) &&
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
  function render() {
    const selected = filtered(), list = el('List'); list.replaceChildren();
    el('Total').textContent = String(rows.length);
    el('Due').textContent = String(rows.filter(due).length);
    page = Math.min(page, Math.max(0, Math.ceil(selected.length / 40)-1));
    el('Count').textContent = selected.length ? `${page*40+1}–${Math.min((page+1)*40, selected.length)} of ${selected.length}` : '0 leads';
    el('Previous').disabled = page === 0; el('Next').disabled = (page+1)*40 >= selected.length;
    if (!selected.length) list.appendChild(node('p', rows.length ? 'No leads match these filters.' : 'Save your first LinkedIn job ad to start tracking opportunities.', 'job-leads-muted'));
    selected.slice(page*40, (page+1)*40).forEach(row => {
      const card = node('article', '', 'job-lead-card');
      card.append(node('h3', row.company), node('p', row.role, 'job-lead-role'));
      const meta = node('div', '', 'job-lead-meta');
      meta.append(node('span', labels[row.status], 'job-lead-status'));
      meta.append(node('span', 'Posted: ' + postedLabel(row.date_posted)));
      if (row.follow_up) meta.append(node('span', (due(row) ? 'Due · ' : 'Follow up · ') + row.follow_up, due(row) ? 'job-lead-due' : ''));
      card.appendChild(meta);
      if (row.contact) card.appendChild(node('p', 'Contact: ' + row.contact));
      if (row.location) card.appendChild(node('p', row.location, 'job-leads-muted'));
      if (row.notes) card.appendChild(node('p', row.notes.slice(0, 300) + (row.notes.length > 300 ? '…' : ''), 'job-lead-notes'));
      const actions = node('div', '', 'job-leads-actions');
      const link = node('a', 'Open LinkedIn ad'); link.href = row.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
      const edit = node('button', 'Edit / view details', 'sec'); edit.type = 'button'; edit.disabled = busy;
      edit.addEventListener('click', () => { if (!busy && discard()) { fill(row); status('Editing saved lead.'); el('Form').scrollIntoView({block:'start', behavior:'smooth'}); } });
      actions.append(link, edit); card.appendChild(actions); list.appendChild(card);
      const details = node('details', '', 'job-lead-ad');
      details.appendChild(node('summary', 'View more — job ad content'));
      if (row.description) {
        if (row.description_truncated || row.description.length >= 20000) details.appendChild(node('p', 'Captured excerpt. Open the LinkedIn ad for the complete content.', 'job-leads-muted'));
        details.appendChild(node('div', row.description, 'job-lead-ad-content'));
      } else details.appendChild(node('p', 'No job description was saved. Open the LinkedIn ad, or use Edit / view details and Fill from link, then save.', 'job-leads-muted'));
      card.appendChild(details);
    });
  }
  function rpc(action, args = {}) {
    return new Promise((resolve, reject) => {
      const id = hex(), timer = setTimeout(() => { pending.delete(id); reject(Error('Connect the latest companion in Chrome to fill from a job link. You can also enter the details manually.')); }, action === 'jobFromLink' ? 35000 : 12000);
      pending.set(id, {resolve, reject, timer});
      window.postMessage({type:'CVSTUDIO_LINKEDIN_REQUEST', id, channel, action, args}, location.origin);
    });
  }
  window.addEventListener('message', event => {
    const data = event.data;
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
      const id = view ? view[1] : /^\/jobs(?:\/search|\/collections\/[^/]+)?\/?$/.test(u.pathname) && ids.length === 1 ? ids[0] : '';
      return /^[0-9]{1,24}$/.test(id) ? 'https://www.linkedin.com/jobs/view/' + id : '';
    } catch { return ''; }
  }
  async function fillFromLink(useBrowser = false) {
    if (busy) return;
    const url = jobLink(el('url').value);
    if (!url) { status('Paste a LinkedIn job ad link to fill in its details.'); return; }
    if (editing && jobLink(editing.url) !== url) { status('Click New lead before filling a different job ad. Your current lead has been kept.'); return; }
    const before = draft(); lock(true); status(useBrowser ? 'Reading this job ad in Chrome…' : 'Reading public LinkedIn job details…');
    try {
      const data = useBrowser ? await rpc('jobFromLink', {url}) : (await api({action:'lookup', url})).record;
      if (jobLink(data?.url || '') !== url || !data.company || !data.role) throw Error('The job details could not be confirmed. Use Read job ad or enter them manually.');
      // Never fill contacts, notes, follow-up dates or BD status from ad text,
      // and preserve manual corrections already made to other populated fields.
      for (const key of ['company','role','location','date_posted','description']) {
        if (!before[key].trim() && typeof data[key] === 'string') {
          el(key).value = data[key];
          if (key === 'description') descriptionTruncated = data.description_truncated === true;
        }
      }
      descriptionHint();
      el('url').value = url; dirty = true; lastReadUrl = url;
      status('Job details filled in. Review them, optionally add a contact, then Save lead.' + (data.description_truncated ? ' The description is an excerpt.' : ''));
    } catch (error) { status(error.message + ' Your draft has been kept.'); }
    finally { lock(false); }
  }
  window.initJobLeads = async function () {
    if (ready) return;
    ready = true;
    fields.forEach(key => el(key).addEventListener('input', () => {
      dirty = true;
      if (key === 'description') { descriptionTruncated = false; descriptionHint(); }
    }));
    el('AutoFill').addEventListener('click', () => fillFromLink());
    el('BrowserFill').addEventListener('click', () => fillFromLink(true));
    el('url').addEventListener('paste', event => {
      const value = event.clipboardData?.getData('text/plain') || '';
      if (busy || !jobLink(value)) return;
      event.preventDefault(); el('url').value = value.trim(); dirty = true;
      return fillFromLink();
    });
    el('url').addEventListener('change', () => { const url = jobLink(el('url').value); if (url && url !== lastReadUrl) return fillFromLink(); });
    el('Form').addEventListener('submit', async event => {
      event.preventDefault(); if (busy) return;
      lock(true); status('Saving lead…');
      try {
        const value = await api({action:'save', record:{...draft(), ...(editing ? {id:editing.id, revision:editing.revision} : {})}});
        await load();
        if (value.duplicate) {
          status('This job is already saved. Your draft has been kept; use Edit / view details on the existing lead to change it.');
        } else { fill(value.record); status('Lead saved on this computer.'); }
      } catch (error) { status(error.message); }
      finally { lock(false); }
    });
    el('New').addEventListener('click', () => { if (!busy && discard()) { fill(null); status('Ready for another job ad.'); } });
    el('Refresh').addEventListener('click', async () => { if (busy) return; lock(true); try { await load(); status('Saved leads refreshed. Reopen a lead to load its latest changes.'); } catch (error) { status(error.message); } finally { lock(false); } });
    for (const id of ['Search', 'Filter']) el(id).addEventListener(id === 'Search' ? 'input' : 'change', () => { page = 0; render(); });
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
        const data = await rpc('jobRead', {tab_id:Number(option.value), expected_url:option.dataset.url});
        fill(data); dirty = true;
        status('Job ad filled in. Review the details, add a contact or notes, then Save lead.' + (data.description_truncated ? ' The captured description is an excerpt.' : ''));
      } catch (error) { status(error.message); } finally { lock(false); }
    });
    el('Export').addEventListener('click', () => {
      const safe = value => { const text = String(value ?? ''); return '"' + (/^[\s]*[=+@-]/.test(text) ? "'" : '') + text.replaceAll('"', '""') + '"'; };
      const keys = ['company','role','contact','date_posted','status','follow_up','url','location','notes','description'];
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
    try { await load(); status('Ready. Saved leads stay on this computer.'); }
    catch (error) { status(error.message); }
    finally { lock(false); }
  };
  function download(blob, name) {
    const url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  document.addEventListener('DOMContentLoaded', () => { if (new URLSearchParams(location.search).get('module') === 'jobleads') switchTab('jobleads'); });
})();
