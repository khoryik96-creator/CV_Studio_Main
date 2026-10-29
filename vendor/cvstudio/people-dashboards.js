/* Saved professional observations only. Unlocks remain explicit per person. */
(() => {
  'use strict';
  const el=id=>document.getElementById('people'+id);
  const text=(tag,value,cls)=>{const n=document.createElement(tag);n.textContent=value;if(cls)n.className=cls;return n;};
  const link=(value,url)=>{const a=text('a',value);if(/^https:\/\/www\.linkedin\.com\/(?:in\/[A-Za-z0-9_%~-]+\/?|talent\/(?:hire\/)?profile\/[^/?#]+|jobs\/view\/\d+\/?|company\/[A-Za-z0-9_-]+\/)$/u.test(url || '')){a.href=url;a.target='_blank';a.rel='noopener noreferrer';}return a;};
  let appBusy=false, dateBusy=false, initialized=false,dateOperation='',dateStopped=false,activeDateStop=null;
  const noteDrafts=new Map();
  const boards={HR:{rows:[],page:0,loading:false,exporting:false,generation:0},Candidates:{rows:[],page:0,loading:false,exporting:false,generation:0}};
  async function api(path,body) {
    const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),cache:'no-store'});
    const data=await response.json();
    if(!response.ok || data.error)throw Error(data.error || 'The dashboard could not be loaded.');
    return data;
  }
  function selected(kind) {return el(kind+(kind==='HR'?'Company':'Search')).value;}
  const fields={HR:['name','title','company','location','country','employment','url','matched','job_url','scanned_at'],Candidates:['name','title','location','url','score','read','evidence','unknowns','notes','brief','saved_at']};
  function filtered(kind) {
    const query=el(kind+'Query').value.trim().toLowerCase(),value=selected(kind);
    return boards[kind].rows.filter(row=>(!value || row[kind==='HR'?'company_id':'run_id']===value) && (!query || fields[kind].map(k=>Array.isArray(row[k])?row[k].join(' '):String(row[k]??'')).join(' ').toLowerCase().includes(query)));
  }
  function controls(kind) {
    const b=boards[kind],rows=filtered(kind);
    el(kind+'Refresh').disabled=b.loading || dateBusy;
    el(kind+'Export').disabled=b.loading || b.exporting || !rows.length;
    el(kind+'Previous').disabled=b.loading || b.page===0;
    el(kind+'Next').disabled=b.loading || (b.page+1)*40>=rows.length;
    for(const button of document.querySelectorAll('[data-employment]'))button.disabled=appBusy || dateBusy;
    el('HRDateStop').hidden=!dateBusy;el('HRDateStop').disabled=dateStopped;
    for(const button of document.querySelectorAll('[data-date-stop]')){button.hidden=!dateBusy || button!==activeDateStop;button.disabled=dateStopped;}
    if(kind==='HR') {
      for(const button of el('HRRows').querySelectorAll('[data-unlock]'))button.disabled=appBusy || dateBusy || !window.cvStudioApollo?.connected();
      el('HRConnect').hidden=!!window.cvStudioApollo?.connected();el('HRConnect').disabled=appBusy || dateBusy || !window.cvStudioApollo?.available();
    }
  }
  function choices(kind) {
    const select=el(kind+(kind==='HR'?'Company':'Search')),old=select.value,seen=new Map();
    for(const row of boards[kind].rows)seen.set(row[kind==='HR'?'company_id':'run_id'],kind==='HR'?row.company:row.brief.slice(0,100)+(row.brief.length>100?'…':'')+' · '+row.saved_at.slice(0,10));
    select.replaceChildren();const any=text('option',kind==='HR'?'All companies':'All searches');any.value='';select.append(any);
    for(const [value,label] of [...seen].sort((a,b)=>kind==='HR'?a[1].localeCompare(b[1]):0)){const option=text('option',label);option.value=value;select.append(option);}
    select.value=seen.has(old)?old:'';
  }
  function expandCell(items) {
    const td=document.createElement('td'),details=document.createElement('details');
    details.append(text('summary',items.length?items[0]:'—'));
    if(items.length){const list=document.createElement('ul');for(const item of items)list.append(text('li',item));details.append(list);}
    td.append(details);return td;
  }
  function personSource(row) {return {id:row.id,revision:row.revision,company:row.company,hr:{company_id:row.company_id,company_url:row.company_url,people:[row]}};}
  function decorateDate(target,row,person) {
    if(!row?.hr || !/^https:\/\/www\.linkedin\.com\/in\/[A-Za-z0-9_%~-]+\/?$/.test(person?.url || ''))return;
    const button=text('button','Check employment','sec');button.type='button';button.dataset.employment='';
    const stop=text('button','Stop checking','sec');stop.type='button';stop.hidden=true;stop.dataset.dateStop='';stop.addEventListener('click',stopDate);
    button.addEventListener('click',()=>{activeDateStop=stop;void checkEmployment(row,person,button);});target.append(button,stop);
    button.disabled=appBusy || dateBusy;
  }
  async function checkEmployment(row,person,button) {
    if(appBusy || dateBusy || window.cvStudioJobLeads?.isBusy())return;
    dateBusy=true;dateStopped=false;dateOperation=crypto.randomUUID().replaceAll('-','');const activity=window.cvStudioJobLeads.activityStart();let failed=false;
    window.cvStudioJobLeads?.lock(true);button.textContent='Checking…';
    const note=el('HRMessage');note.textContent='Reading this person’s company employment in LinkedIn…';controls('HR');
    try {
      const status=await window.cvStudioJobLeads.rpc('jobStatus');
      if(status?.hr_date_check_revision!==1)throw Error('Apply the latest companion update, then refresh CV Studio and LinkedIn to check employment.');
      if(dateStopped)throw Error('Employment check stopped. Saved dates were kept.');
      const result=await window.cvStudioJobLeads.rpc('hrDate',{operation_id:dateOperation,url:person.url.replace(/\/$/,''),company_url:row.hr.company_url,company_id:row.hr.company_id},90000);
      if(dateStopped)throw Error('Employment check stopped. Saved dates were kept.');
      if(result?.url!==person.url.replace(/\/$/,'') || !/^(?:19|20)\d{2}(?:-(?:0[1-9]|1[0-2]))?$/.test(result.joined || ''))throw Error('No employment range was confirmed for this company. Saved dates were kept.');
      const data=await api('/job-leads',{action:'employment',id:row.id,revision:row.revision,url:person.url,dates:{joined:result.joined,left:result.left,current:result.current}});
      const updated=data.record.hr.people.find(p=>p.url.replace(/\/$/,'')===person.url.replace(/\/$/,''));
      button.textContent=window.cvStudioJobLeads.employment(updated);
      await window.cvStudioJobLeads.refresh();await refresh('HR');
      note.textContent='Employment updated: '+window.cvStudioJobLeads.employment(updated);
    } catch(error) {
      failed=!dateStopped;note.textContent=error.message;button.textContent='Retry employment';button.title=error.message;
      const local=text('small',error.message);local.setAttribute('role','status');button.parentElement.append(local);
    }
    finally {dateBusy=false;dateOperation='';activeDateStop=null;window.cvStudioJobLeads?.lock(false);window.cvStudioJobLeads.activityEnd(activity,failed);controls('HR');}
  }
  function draw(kind) {
    const b=boards[kind],all=filtered(kind),target=el(kind+'Rows');b.page=Math.min(b.page,Math.max(0,Math.ceil(all.length/40)-1));target.replaceChildren();
    el(kind+'Count').textContent=String(all.length);
    for(const row of all.slice(b.page*40,(b.page+1)*40)) {
      const tr=document.createElement('tr'),name=document.createElement('td');name.append(link(row.name,row.url));tr.append(name);
      if(kind==='HR') {
        tr.append(text('td',row.title || '—'),text('td',row.company),text('td',row.location || '—'));
        const dates=text('td',row.employment);decorateDate(dates,personSource(row),row);tr.append(dates);
        const email=document.createElement('td'),result=row.email_result;
        if(result?.state==='found')email.append(text('span',result.email,'people-email'));
        else {
          if(result?.message)email.append(text('small',result.message));
          const button=text('button',result?'Check lookup':'Unlock email','sec');button.type='button';button.dataset.unlock='';
          button.hidden=!!result && !['pending','unconfirmed'].includes(result.state);
          button.addEventListener('click',async()=>{
            const note=message=>{el('HRMessage').textContent=message;};
            const source=personSource(row);source.id=row.email_id || row.id;source.revision=row.email_revision || row.revision;
            const success=await window.cvStudioApollo?.unlockSaved(source,row,row.email_result || null,note,value=>{row.email_result=value;});
            if(success===false && !row.email_result)row.email_result={state:'unconfirmed',message:'Check the previous lookup before trying again.'};
            const message=el('HRMessage').textContent;await refresh('HR');el('HRMessage').textContent=message;
          });email.append(button);
        }
        tr.append(email);const source=document.createElement('td');source.append(link(row.ads+' ad'+(row.ads===1?'':'s'),row.job_url));tr.append(source);
      } else {
        tr.append(text('td',row.title || '—'),text('td',row.location || '—'),text('td',row.score+' / 100'),text('td',row.read),expandCell(row.evidence),expandCell(row.unknowns));
        const notes=document.createElement('td'),editor=document.createElement('details'),input=document.createElement('textarea'),save=text('button','Save note','sec');
        editor.append(text('summary',row.notes || 'Add note'));editor.open=noteDrafts.has(row.key);
        input.value=noteDrafts.get(row.key)?.value ?? row.notes;input.maxLength=2000;input.rows=2;input.setAttribute('aria-label','Notes for '+row.name);save.type='button';save.disabled=input.value===row.notes;
        input.addEventListener('input',()=>{save.disabled=input.value===row.notes;if(save.disabled)noteDrafts.delete(row.key);else noteDrafts.set(row.key,{value:input.value,revision:noteDrafts.get(row.key)?.revision ?? row.revision});});
        save.addEventListener('click',async()=>{
          save.disabled=true;input.disabled=true;
          try {
            const data=await api('/linkedin-sourcer',{action:'candidate_note',key:row.key,revision:noteDrafts.get(row.key)?.revision ?? row.revision,notes:input.value});
            ++boards.Candidates.generation;Object.assign(boards.Candidates.rows.find(value=>value.key===row.key) || row,data.candidate);
            noteDrafts.delete(row.key);draw('Candidates');el('CandidatesMessage').textContent='Note saved.';
          }
          catch(error){el('CandidatesMessage').textContent=error.message;save.disabled=false;}
          finally{input.disabled=false;}
        });editor.append(input,save);notes.append(editor);tr.append(notes);
      }
      target.append(tr);
    }
    el(kind+'Page').textContent=all.length?`${b.page*40+1}–${Math.min((b.page+1)*40,all.length)} of ${all.length}`:'';controls(kind);
  }
  async function refresh(kind) {
    const b=boards[kind];if(b.loading){b.again=true;return;}b.loading=true;const generation=++b.generation;controls(kind);el(kind+'Message').textContent='Loading…';
    try {
      const data=await api(kind==='HR'?'/apollo':'/linkedin-sourcer',{action:kind==='HR'?'hr_people':'candidates'});
      if(generation!==b.generation)return;
      b.rows=data[kind==='HR'?'people':'candidates'] || [];choices(kind);draw(kind);
      el(kind+'Message').textContent=b.rows.length?'':kind==='HR'?'No saved HR people yet.':'Candidates from new searches are saved here automatically.';
    } catch(error){el(kind+'Message').textContent=error.message;}
    finally{b.loading=false;controls(kind);if(b.again){b.again=false;if(!el(kind+'Panel').hidden)void refresh(kind);}}
  }
  async function exportRows(kind) {
    const b=boards[kind];if(b.exporting || b.loading || !filtered(kind).length)return;b.exporting=true;controls(kind);
    try {
      const response=await fetch(kind==='HR'?'/apollo':'/linkedin-sourcer',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:kind==='HR'?'export_people':'export_candidates',query:el(kind+'Query').value,[kind==='HR'?'company':'search']:selected(kind)})});
      if(!response.ok){const data=await response.json();throw Error(data.error || 'Export failed.');}
      const url=URL.createObjectURL(await response.blob()),a=document.createElement('a');a.href=url;a.download='CV-Studio-'+(kind==='HR'?'HR-People':'Candidates')+'.xlsx';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    } catch(error){el(kind+'Message').textContent=error.message;}
    finally{b.exporting=false;controls(kind);}
  }
  window.cvStudioPeople={
    decorateDate,
    appBusy(value){appBusy=value;if(initialized)controls('HR');},
    hideHR(){el('HRPanel').hidden=true;el('HRTab').setAttribute('aria-pressed','false');},
    sourcerChanged(){if(!el('CandidatesPanel').hidden)void refresh('Candidates');}
  };
  for(const kind of ['HR','Candidates']) {
    el(kind+'Refresh').addEventListener('click',()=>refresh(kind));el(kind+'Export').addEventListener('click',()=>exportRows(kind));
    el(kind+'Query').addEventListener('input',()=>{boards[kind].page=0;draw(kind);});
    el(kind+(kind==='HR'?'Company':'Search')).addEventListener('change',()=>{boards[kind].page=0;draw(kind);});
    for(const [suffix,delta] of [['Previous',-1],['Next',1]])el(kind+suffix).addEventListener('click',()=>{boards[kind].page+=delta;draw(kind);});
    draw(kind);
  }
  el('HRTab').addEventListener('click',()=>{
    el('HRPanel').hidden=false;el('HRTab').setAttribute('aria-pressed','true');
    for(const kind of ['Ads','Contacts']){document.getElementById('jobLeadsApollo'+kind+'Panel').hidden=true;document.getElementById('jobLeadsApollo'+kind+'Tab').setAttribute('aria-pressed','false');}
    void refresh('HR');
  });
  el('HRConnect').addEventListener('click',()=>window.cvStudioApollo?.connect());
  async function stopDate(){if(!dateBusy || !dateOperation)return;dateStopped=true;controls('HR');try{await window.cvStudioJobLeads.rpc('jobReadCancel',{operation_id:dateOperation});}catch{}}
  el('HRDateStop').addEventListener('click',stopDate);
  window.addEventListener('pagehide',()=>{void stopDate();});
  window.addEventListener('beforeunload',event=>{if(noteDrafts.size){event.preventDefault();event.returnValue='';}});
  function candidates(show){el('CandidatesPanel').hidden=!show;el('SourcerSearchPanel').hidden=show;el('CandidatesTab').setAttribute('aria-pressed',String(show));el('SourcerSearchTab').setAttribute('aria-pressed',String(!show));if(show)void refresh('Candidates');}
  el('CandidatesTab').addEventListener('click',()=>candidates(true));el('SourcerSearchTab').addEventListener('click',()=>candidates(false));initialized=true;
})();
