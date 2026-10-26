/* First-party email verification. Lists/results stay in this tab until exported. */
(function () {
  'use strict';
  const MAX = 200;
  const labels = {accepted:'Mailbox accepted', invalid:'Invalid', catch_all:'Catch-all', unknown:'Unknown', domain_ok:'Domain passed', not_checked:'Not checked'};
  const el = name => document.getElementById('emailVerifier' + name);
  let rows = [], running = false, importing = false, stopping = false, ready = false;

  function unique(values) {
    const seen = new Set(), emails = [];
    for (const raw of values) {
      const email = raw.trim();
      if (!email) continue;
      const at = email.lastIndexOf('@');
      const key = at < 0 ? email : email.slice(0, at) + email.slice(at).toLowerCase();
      if (!seen.has(key)) { seen.add(key); emails.push(email); }
    }
    if (emails.length > MAX) throw new Error('Check up to 200 unique emails at a time. Split this list into smaller batches.');
    if (emails.some(email => email.length > 320)) throw new Error('An entry is too long. Put one email address on each line.');
    return {emails, duplicates:values.filter(value => value.trim()).length - emails.length};
  }
  function parseText(text) {
    if (text.length > 1000000) throw new Error('This list is too large. Use a file smaller than 1 MB.');
    const values = []; let current = '', quoted = false, escaped = false;
    for (const char of text) {
      if (!escaped && char === '"') quoted = !quoted;
      if (!quoted && /[\r\n,;]/.test(char)) { values.push(current); current=''; }
      else current += char;
      escaped = !escaped && char === '\\';
    }
    values.push(current);
    return unique(values);
  }
  function parseCSV(text) {
    if (text.length > 1000000) throw new Error('Use a CSV file smaller than 1 MB.');
    text = text.replace(/^\uFEFF/, '');
    const records = [];
    let row = [], cell = '', quoted = false, closed = false;
    for (let i = 0; i <= text.length; i++) {
      const char = text[i];
      if (quoted) {
        if (char === '"' && text[i+1] === '"') { cell += '"'; i++; }
        else if (char === '"') { quoted = false; closed = true; }
        else if (char === undefined) throw new Error('The CSV has an unclosed quote. Check the file and try again.');
        else cell += char;
      } else if (char === ',' || char === '\n' || char === '\r' || char === undefined) {
        row.push(cell); cell = ''; closed = false;
        if (char !== ',') { if (row.some(value => value.trim())) records.push(row); row = []; if (char === '\r' && text[i+1] === '\n') i++; }
      } else if (char === '"' && !cell && !closed) quoted = true;
      else if (closed || char === '"') throw new Error('The CSV has an unexpected quote or extra text after a quote.');
      else cell += char;
    }
    if (!records.length) return {emails:[], duplicates:0};
    const columns = records[0].map(value => value.trim().toLowerCase().replace(/[\s_-]/g,''));
    const matches = columns.map((value,index) => ['email','emailaddress'].includes(value) ? index : -1).filter(index => index >= 0);
    if (matches.length > 1) throw new Error('Keep one Email column in this CSV.');
    const column = matches.length ? matches[0] : 0;
    if (!matches.length && records.some(record => record.length !== 1)) throw new Error('Include a column named Email in a CSV with multiple columns.');
    return unique(records.slice(matches.length ? 1 : 0).map(record => record[column] || ''));
  }
  // Escape formula prefixes as well as RFC CSV quotes; no input is executable.
  function csvCell(value) {
    let text = String(value ?? '');
    if (/^\s*[=+\-@]/.test(text)) text = "'" + text;
    return '"' + text.replaceAll('"', '""') + '"';
  }
  function makeCSV(results) {
    const header = ['Email','Result','Reason','Flags','Suggested correction','Mode','Checked at'];
    return [header, ...results.map(row => [row.email, labels[row.status] || 'Unknown', row.reason, (row.flags || []).join('; '), row.suggestion, row.mode, row.checked_at])]
      .map(row => row.map(csvCell).join(',')).join('\r\n');
  }
  function textNode(tag, value, className) {
    const node = document.createElement(tag); node.textContent = value;
    if (className) node.className = className;
    return node;
  }
  function shown() {
    const filter = el('Filter').value, search = el('Search').value.toLowerCase().trim();
    return rows.filter(row => (!filter || row.status === filter) && (!search || row.email.toLowerCase().includes(search)));
  }
  function render() {
    const complete = rows.filter(row => row.status !== 'not_checked').length;
    for (const [name, state] of [['Accepted','accepted'],['Invalid','invalid'],['CatchAll','catch_all'],['Unknown','unknown'],['Domain','domain_ok']]) {
      el(name).textContent = rows.filter(row => row.status === state).length;
    }
    el('Total').textContent = rows.length ? complete + ' of ' + rows.length + ' checked' : 'Your results will appear here';
    el('Progress').value = complete; el('Progress').max = rows.length || 1;
    el('Progress').hidden = !rows.length;
    const visible = shown();
    el('Results').replaceChildren();
    for (const row of visible) {
      const tr = document.createElement('tr'), email = document.createElement('td');
      email.appendChild(textNode('span',row.email,'ev-address'));
      if (row.suggestion) email.appendChild(textNode('small','Possible typo: ' + row.suggestion,'ev-suggestion'));
      const state = document.createElement('td');
      state.appendChild(textNode('span',labels[row.status] || 'Unknown','ev-badge ev-' + (Object.hasOwn(labels,row.status) ? row.status : 'unknown')));
      const detail = document.createElement('td');
      detail.appendChild(textNode('p',row.reason || (running ? 'Waiting for its turn.' : 'Not checked in this run.')));
      if (row.flags?.length) detail.appendChild(textNode('small',row.flags.join(' · '),'ev-flags'));
      tr.append(email,state,detail); el('Results').appendChild(tr);
    }
    el('Empty').hidden = visible.length > 0;
    el('Empty').textContent = rows.length ? 'No emails match this filter.' : 'Add an email or a list to start your first check.';
    el('Export').disabled = !visible.some(row => row.status !== 'not_checked');
    el('Clear').disabled = running || importing || !rows.length;
    el('Start').disabled = running || importing;
    el('Stop').disabled = !running || stopping;
    el('Input').disabled = running || importing; el('File').disabled = running || importing; el('Import').disabled = running || importing; el('Mode').disabled = running || importing;
  }
  async function start() {
    if (running || importing) return;
    let list;
    try { list = parseText(el('Input').value); if (!list.emails.length) throw new Error('Add at least one email address first.'); }
    catch (error) { el('Message').textContent = error.message; return; }
    const mode = el('Mode').value;
    rows = list.emails.map(email => ({email,status:'not_checked',reason:'',flags:[],mode}));
    running = true; stopping = false;
    const token = typeof markTabRunning === 'function' ? markTabRunning('emailverifier') : null;
    let failed = false;
    el('Message').textContent = list.duplicates ? list.duplicates + ' duplicate entries removed.' : 'Checking your list…';
    render();
    try {
      for (let index = 0; index < rows.length && !stopping; index++) {
        el('Message').textContent = 'Checking ' + (index + 1) + ' of ' + rows.length + '…';
        try {
          const response = await fetch('/email-verifier', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:rows[index].email,mode}),timeout:32000});
          const data = await response.json();
          if (!response.ok || !data.ok) throw new Error(data.error || 'The check could not be completed.');
          const result = data.result;
          if (!result || !Object.hasOwn(labels,result.status) || result.status === 'not_checked' || typeof result.reason !== 'string') throw new Error('The verifier returned an incomplete result.');
          // Keep the input identity; never accept a returned email as another row.
          rows[index] = {...rows[index],...result,email:rows[index].email};
        } catch (error) {
          failed = true;
          el('Message').textContent = 'Stopped: ' + error.message + ' Completed results have been kept.';
          break;
        }
        render();
      }
      if (!failed) el('Message').textContent = stopping ? 'Stopped. Completed results are kept; remaining emails have not been checked.' : 'Finished. ' + rows.length + ' emails checked' + (list.duplicates ? '; ' + list.duplicates + ' duplicates removed.' : '.');
    } finally {
      running = false; render();
      if (token !== null) { if (failed && typeof markTabFailed === 'function') markTabFailed('emailverifier',token); else if (typeof markTabDone === 'function') markTabDone('emailverifier',token); }
    }
  }
  function init() {
    if (ready) return;
    ready = true;
    el('Start').addEventListener('click',start);
    el('Stop').addEventListener('click',() => { stopping = true; el('Message').textContent = 'Stopping after the current email check…'; render(); });
    el('Clear').addEventListener('click',() => { if (running || importing) return; rows=[]; el('Input').value=''; el('Filter').value=''; el('Search').value=''; el('Message').textContent=''; render(); });
    el('Filter').addEventListener('change',render); el('Search').addEventListener('input',render);
    el('Import').addEventListener('click',() => el('File').click());
    el('File').addEventListener('change',async () => {
      const file = el('File').files?.[0];
      if (!file || running || importing) return;
      importing = true; render();
      try {
        if (file.size > 1000000) throw new Error('Use a CSV file smaller than 1 MB.');
        const list = parseCSV(await file.text());
        if (!list.emails.length) throw new Error('No emails were found in the file.');
        el('Input').value = list.emails.join('\n');
        el('Message').textContent = list.emails.length + ' emails imported' + (list.duplicates ? '; ' + list.duplicates + ' duplicates removed.' : '.');
      } catch (error) { el('Message').textContent=error.message; }
      finally { importing = false; el('File').value=''; render(); }
    });
    el('Export').addEventListener('click',() => {
      const complete = shown().filter(row => row.status !== 'not_checked');
      if (!complete.length) return;
      const url = URL.createObjectURL(new Blob(['\uFEFF' + makeCSV(complete)],{type:'text/csv;charset=utf-8'}));
      const link=document.createElement('a'); link.href=url; link.download='CV-Studio-Email-Verification.csv'; link.click(); setTimeout(() => URL.revokeObjectURL(url),1000);
    });
    render();
  }
  window.initEmailVerifier = init;
  // Pure parsing/export functions are shared by the no-network regression fixture.
  if (typeof module !== 'undefined' && module.exports) module.exports={parseText,parseCSV,makeCSV};
  document.addEventListener('DOMContentLoaded',() => { if (new URLSearchParams(location.search).get('module') === 'emailverifier') switchTab('emailverifier'); });
}());
