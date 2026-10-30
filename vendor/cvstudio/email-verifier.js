/* First-party email verification. Lists/results stay in this tab until exported. */
(function () {
  'use strict';
  const MAX = 200;
  const labels = {accepted:'Mailbox accepted', invalid:'Invalid', catch_all:'Catch-all', unknown:'Unconfirmed', domain_ok:'Domain passed', not_checked:'Not checked'};
  const el = name => document.getElementById('emailVerifier' + name);
  let rows = [], running = false, importing = false, stopping = false, ready = false;
  let leaving = false;
  const cards = new WeakMap();
  const now=()=>typeof performance!=='undefined'?performance.now():Date.now();

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
    const header = ['Email','Result','Reason','Flags','Suggested correction','Mode','Checked at','Assessment','Mailbox evidence','Catch-all policy','Mail provider','SMTP sessions','Previous result'];
    return [header, ...results.map(row => [row.email, labels[row.status] || 'Unknown', row.reason, (row.flags || []).join('; '), row.suggestion, row.mode, row.checked_at,row.assessment?.label,row.mailbox_evidence,row.catch_all,row.provider,row.attempts,row.previous_result])]
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
  function evidence(row) {
    const parts=[];
    const syntax={ok:'Passed',invalid:'Invalid',unsupported:'Not supported'}[row.syntax];
    if(syntax) parts.push('Format: '+syntax);
    const domain={mx:'Found',no_domain:'Domain missing',no_mail:'Domain does not receive mail',no_server:'No usable server',not_checked:'Not checked'}[row.domain];
    if(domain) parts.push('Mail records: '+domain);
    if(row.domain==='implicit') parts.push(row.status==='domain_ok'||row.mailbox&&row.mailbox!=='not_checked'?'Fallback mail server: Found':'MX record: Not found');
    const mailbox={accepted:'Accepted',invalid:'Does not exist',catch_all:'Catch-all',unknown:'Unconfirmed',not_checked:'Not checked'}[row.mailbox];
    if(mailbox) parts.push('Mailbox: '+mailbox);
    return parts.join(' · ');
  }
  function details(row) {
    const parts=[];
    if(row.mailbox_evidence) parts.push('Address response: '+({accepted:'Accepted by server',rejected:'Rejected',unconfirmed:'Unconfirmed',conflicting:'Conflicting answers',not_checked:'Not checked'}[row.mailbox_evidence] || 'Unconfirmed'));
    if(row.catch_all) parts.push('Catch-all policy: '+({detected:'Detected',not_detected:'Not detected',inconclusive:'Unconfirmed',not_checked:'Not checked'}[row.catch_all] || 'Unconfirmed'));
    if(row.provider && row.provider!=='Not checked') parts.push(row.provider);
    if(Number.isInteger(row.attempts)) parts.push(row.attempts+' mail-server sessions');
    if(row.checked_at) {
      const checked=new Date(row.checked_at);
      if(!Number.isNaN(checked.getTime())) parts.push('Checked '+checked.toLocaleString());
    }
    return parts.join(' · ');
  }
  async function checkEmail(email,mode,recheckToken) {
    const response=await fetch('/email-verifier',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,mode,...(typeof recheckToken==='string' && recheckToken?{recheck_token:recheckToken}:{})}),timeout:32000});
    const data=await response.json();
    if(!response.ok || !data.ok) throw Error(data.error || 'The check could not be completed.');
    const result=data.result;
    if(!result || !Object.hasOwn(labels,result.status) || result.status==='not_checked' || typeof result.reason!=='string') throw Error('The verifier returned an incomplete result.');
    return {...result,email};
  }
  function canRecheck(row) {return ['unknown','catch_all'].includes(row.status) && !row._rechecked;}
  async function waitForRecheck(row) {
    // Space attempts using our own receipt time, independent of server clock skew.
    const until=Math.min(row._lastCheck ?? now(),now())+120000;
    while(!stopping && !leaving && now()<until) {
      el('Message').textContent='Waiting '+Math.ceil((until-now())/1000)+' seconds before a deeper recheck. Previous results are kept. You can Stop.';
      await new Promise(resolve=>setTimeout(resolve,Math.min(1000,Math.max(1,until-now()))));
    }
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
      if(row.assessment?.label) detail.appendChild(textNode('strong',row.assessment.label));
      detail.appendChild(textNode('p',row.reason || (running ? 'Waiting for its turn.' : 'Not checked in this run.')));
      const checks=evidence(row);
      if(checks && !row.mailbox_evidence) detail.appendChild(textNode('small',checks,'ev-flags'));
      if(details(row)) detail.appendChild(textNode('small',details(row),'ev-flags'));
      if(row.previous_result) detail.appendChild(textNode('small','Previous check: '+row.previous_result,'ev-flags'));
      if (row.flags?.length) detail.appendChild(textNode('small',row.flags.join(' · '),'ev-flags'));
      tr.append(email,state,detail); el('Results').appendChild(tr);
    }
    el('Empty').hidden = visible.length > 0;
    el('Empty').textContent = rows.length ? 'No emails match this filter.' : 'Add an email or a list to start your first check.';
    el('Export').disabled = !visible.some(row => row.status !== 'not_checked');
    el('Clear').disabled = running || importing || !rows.length;
    el('Start').disabled = running || importing;
    el('Recheck').disabled = running || importing || !rows.some(canRecheck);
    el('Stop').disabled = !running || stopping;
    el('Input').disabled = running || importing; el('File').disabled = running || importing; el('Import').disabled = running || importing; el('Mode').disabled = running || importing;
  }
  async function start(recheckOnly=false) {
    if (running || importing) return;
    let list;
    try { list = recheckOnly ? {emails:rows.map(row=>row.email),duplicates:0} : parseText(el('Input').value); if (!list.emails.length) throw new Error('Add at least one email address first.'); }
    catch (error) { el('Message').textContent = error.message; return; }
    const mode = recheckOnly?'deep':el('Mode').value;
    if(!recheckOnly) rows = list.emails.map(email => ({email,status:'not_checked',reason:'',flags:[],mode}));
    const indexes=rows.map((row,index)=>index).filter(index=>!recheckOnly || canRecheck(rows[index]));
    if(!indexes.length) return;
    running = true; stopping = false;
    const token = typeof markTabRunning === 'function' ? markTabRunning('emailverifier') : null;
    let failed = false;
    el('Message').textContent = list.duplicates ? list.duplicates + ' duplicate entries removed.' : 'Checking your list…';
    render();
    try {
      const rounds=recheckOnly?1:mode==='deep'?2:1;
      for(let round=0;round<rounds && !failed && !stopping && !leaving;round++) {
        const rechecking=recheckOnly || round===1;
        const queue=indexes.filter(index=>!rechecking || canRecheck(rows[index]) && (recheckOnly || rows[index].retryable===true));
        for (const [position,index] of queue.entries()) {
          if(stopping || leaving) break;
          try {
            if(rechecking) await waitForRecheck(rows[index]);
            if(stopping || leaving) break;
            el('Message').textContent=(rechecking?'Rechecking ':'Checking ')+(position+1)+' of '+queue.length+'…';
            const previous=rows[index];
            if(rechecking) previous._rechecked=true;
            const result=await checkEmail(previous.email,mode,rechecking?previous.recheck_token:undefined);
            rows[index]={...previous,...result,_rechecked:rechecking,_lastCheck:now(),previous_result:rechecking?labels[previous.status]+': '+previous.reason:''};
          } catch (error) {
            failed = true;
            el('Message').textContent = 'Stopped: ' + error.message + ' Completed results have been kept.';
            break;
          }
          render();
        }
      }
      if (!failed) el('Message').textContent = stopping || leaving ? 'Stopped. Completed results are kept; remaining checks have not run.' : recheckOnly?'Deeper rechecks finished. Previous results remain in each explanation.':'Finished. ' + rows.length + ' emails checked' + (list.duplicates ? '; ' + list.duplicates + ' duplicates removed.' : '.');
    } finally {
      running = false; render();
      if (token !== null) { if (failed && typeof markTabFailed === 'function') markTabFailed('emailverifier',token); else if (typeof markTabDone === 'function') markTabDone('emailverifier',token); }
    }
  }
  function init() {
    if (ready) return;
    ready = true;
    el('Start').addEventListener('click',()=>start());
    el('Recheck').addEventListener('click',()=>start(true));
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
  window.addEventListener?.('pagehide',()=>{leaving=true;stopping=true;});
  window.addEventListener?.('pageshow',()=>{leaving=false;});
  window.cvStudioEmailVerifier={
    forCard:card=>cards.get(card),
    decorate(card,person,options={}) {
      const wrap=textNode('div','','job-leads-email-check'), label=textNode('label','Email to verify'), input=document.createElement('input');
      input.type='email';input.autocomplete='off';input.setAttribute?.('aria-label','Email to verify for '+person.name);
      label.appendChild(input);
      const button=textNode('button','Verify email','sec'), result=textNode('div','','job-leads-email-result');
      button.type='button';result.setAttribute?.('role','status');result.setAttribute?.('aria-live','polite');
      let pending=false, generation=0, proposed='', recheckToken='';
      input.addEventListener('input',()=>{++generation;recheckToken='';result.replaceChildren();});
      button.addEventListener('click',async()=>{
        if(pending || !input.value.trim()) {if(!pending) result.replaceChildren(textNode('small','Enter an email address first.'));return;}
        const email=input.value.trim(), current=++generation;
        pending=true;button.disabled=true;button.textContent='Checking…';
        result.replaceChildren(textNode('small','Checking mail servers without sending an email…'));
        try {
          const answer=await checkEmail(email,'deep',recheckToken);
          if(current!==generation || leaving) return;
          recheckToken=answer.recheck_token || '';
          result.replaceChildren(textNode('strong',answer.assessment?.label || labels[answer.status]),textNode('p',answer.reason),textNode('small',details(answer)));
        } catch(error) {if(current===generation && !leaving) result.replaceChildren(textNode('small',error.message));}
        finally {pending=false;button.disabled=false;button.textContent='Verify email';}
      });
      const controller={suggest(email) {
        email=typeof email==='string'?email:'';
        if(email===proposed) return;
        if(!input.value || input.value===proposed) {input.value=email;++generation;recheckToken='';result.replaceChildren();}
        proposed=email;
      }};
      if(options.readOnly)input.readOnly=true;
      if(options.compact){label.hidden=true;wrap.className+=' job-leads-email-compact';}
      cards.set(card,controller);wrap.append(label,button,result);card.appendChild(wrap);
      if(options.email)controller.suggest(options.email);
      return controller;
    }
  };
  // Pure parsing/export functions are shared by the no-network regression fixture.
  if (typeof module !== 'undefined' && module.exports) module.exports={parseText,parseCSV,makeCSV,details};
  document.addEventListener('DOMContentLoaded',() => { if (new URLSearchParams(location.search).get('module') === 'emailverifier') switchTab('emailverifier'); });
}());
