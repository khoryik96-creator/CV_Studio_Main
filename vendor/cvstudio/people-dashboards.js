/* Saved professional observations only. Unlocks remain explicit per person. */
(() => {
  'use strict';
  const el=id=>document.getElementById('people'+id);
  const text=(tag,value,cls)=>{const n=document.createElement(tag);n.textContent=value;if(cls)n.className=cls;return n;};
  const link=(value,url)=>{const a=text('a',value);if(/^https:\/\/www\.linkedin\.com\/(?:in\/[A-Za-z0-9_%~-]+(?:\/details\/experience\/|\/?)|talent\/(?:hire\/)?profile\/[^/?#]+|jobs\/view\/\d+\/?|company\/[A-Za-z0-9_-]+\/)$/u.test(url || '')){a.href=url;a.target='_blank';a.rel='noopener noreferrer';}return a;};
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
  const SORTS=new Set(['saved_at','score','name','location','read']);
  // The same case-, accent- and number-aware key as cvstudio_people._sort_key,
  // so the table and its Excel export list candidates in the same order.
  const SPACE=/^[ \t\n\r\f\v\u00a0]+|[ \t\n\r\f\v\u00a0]+$/g;
  function sortKey(value){const text=String(value ?? '').normalize('NFKD').replace(SPACE,'').toLowerCase().replace(/\p{Mn}/gu,'');return text.split(/([0-9]+)/).map((part,index)=>index%2?BigInt(part):part);}
  function compareKeys(a,b){
    for(let i=0;i<Math.min(a.length,b.length);i++){
      const x=a[i],y=b[i];if(x===y)continue;
      if(typeof x==='bigint')return x<y?-1:1;
      const p=[...x],q=[...y];
      for(let j=0;j<Math.min(p.length,q.length);j++){const m=p[j].codePointAt(0),n=q[j].codePointAt(0);if(m!==n)return m<n?-1:1;}
      return p.length-q.length;
    }
    return a.length-b.length;
  }
  const score=row=>typeof row.score==='number' && Number.isFinite(row.score)?row.score:null;
  function candidateView() {
    const sort=el('CandidatesSort').value,order=el('CandidatesOrder').value;
    return {min_score:Number(el('CandidatesMinScore').value) || 0,read:el('CandidatesRead').value,sort:SORTS.has(sort)?sort:'saved_at',order:order==='asc'?'asc':'desc'};
  }
  function filtered(kind) {
    const query=el(kind+'Query').value.trim().toLowerCase(),value=selected(kind);
    const rows=boards[kind].rows.filter(row=>(!value || row[kind==='HR'?'company_id':'run_id']===value) && (!query || fields[kind].map(k=>Array.isArray(row[k])?row[k].join(' '):String(row[k]??'')).join(' ').toLowerCase().includes(query)));
    if(kind!=='Candidates')return rows;
    // Same rules as the Excel export: filters first, blank values last, and
    // equal values keep the newest-first archive order.
    const view=candidateView(),picked=rows.filter(row=>(score(row) ?? 0)>=view.min_score && (!view.read || row.read===view.read));
    const keys=new Map(picked.map(row=>[row,view.sort==='score'?score(row):sortKey(row[view.sort])]));
    const blank=row=>view.sort==='score'?keys.get(row)===null:keys.get(row).length===1 && keys.get(row)[0]==='';
    const compare=(a,b)=>view.sort==='score'?keys.get(a)-keys.get(b):compareKeys(keys.get(a),keys.get(b));
    const sign=view.order==='asc'?1:-1;
    return picked.filter(row=>!blank(row)).map((row,index)=>({row,index})).sort((a,b)=>sign*compare(a.row,b.row) || a.index-b.index).map(item=>item.row).concat(picked.filter(blank));
  }
  function markSort() {
    const view=candidateView();
    for(const th of document.querySelectorAll('#peopleCandidatesPanel th[data-sort]')){if(th.dataset.sort===view.sort)th.setAttribute('aria-sort',view.order==='asc'?'ascending':'descending');else th.removeAttribute('aria-sort');}
  }
  function controls(kind) {
    const b=boards[kind],rows=filtered(kind);
    el(kind+'Refresh').disabled=b.loading || dateBusy;
    el(kind+'Export').disabled=b.loading || b.exporting || !rows.length;
    el(kind+'Previous').disabled=b.loading || b.page===0;
    el(kind+'Next').disabled=b.loading || (b.page+1)*40>=rows.length;
    for(const button of document.querySelectorAll('[data-employment]'))button.disabled=appBusy || dateBusy;
    el('HRDateStop').hidden=!dateBusy;el('HRDateStop').disabled=dateStopped;
    el('HRDateAll').disabled=appBusy || dateBusy || boards.HR.loading || !filtered('HR').some(row=>!row.joined);
    for(const suffix of ['Query','Company'])el('HR'+suffix).disabled=dateBusy;
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
  function personSource(row,employment=false) {return {id:employment?(row.employment_id || row.id):row.id,revision:employment?(row.employment_revision || row.revision):row.revision,company:row.company,hr:{company_id:row.company_id,company_url:employment?(row.employment_company_url || row.company_url):row.company_url,people:[row]}};}
  function manualDates(target,row,person) {
    if(target.querySelector?.('[data-manual-dates]'))return;
    const form=document.createElement('details');form.dataset.manualDates='';
    const summary=text('summary','Set dates from LinkedIn'),start=document.createElement('input'),end=document.createElement('input'),present=document.createElement('input'),confirmed=document.createElement('input'),save=text('button','Save confirmed dates','sec'),note=text('small','');
    start.type=end.type='month';start.setAttribute('aria-label','Employment start month and year');end.setAttribute('aria-label','Employment end month and year');
    present.type=confirmed.type='checkbox';present.checked=true;end.disabled=true;save.type='button';
    const label=(words,control)=>{const n=text('label',words);n.append(control);return n;};
    present.addEventListener('change',()=>{end.disabled=present.checked;});
    form.append(summary,link('Open LinkedIn Experience',person.url.replace(/\/$/,'')+'/details/experience/'),label('From',start),label('Present',present),label('To',end),label('I confirmed these dates and the employer: '+row.company,confirmed),save,note);
    save.addEventListener('click',async()=>{
      if(appBusy || dateBusy || window.cvStudioJobLeads?.isBusy())return;
      if(!confirmed.checked || !/^(?:19|20)\d{2}-(?:0[1-9]|1[0-2])$/.test(start.value) || !present.checked && (!/^(?:19|20)\d{2}-(?:0[1-9]|1[0-2])$/.test(end.value) || end.value<start.value)){
        note.textContent='Enter the visible month/year range and confirm the employer.';return;
      }
      save.disabled=true;window.cvStudioJobLeads.lock(true);note.textContent='Saving your confirmation…';
      try{
        const data=await api('/job-leads',{action:'employment',id:row.id,revision:row.revision,url:person.url,user_confirmed:true,dates:{joined:start.value,left:present.checked?'':end.value,current:present.checked}});
        note.textContent='Dates saved · confirmed by you';await window.cvStudioJobLeads.refresh();await refresh('HR');
      }catch(error){note.textContent=error.message;}
      finally{save.disabled=false;window.cvStudioJobLeads.lock(false);}
    });
    target.append(form);
  }
  function decorateDate(target,row,person) {
    if(!row?.hr || !/^https:\/\/www\.linkedin\.com\/in\/[A-Za-z0-9_%~-]+\/?$/.test(person?.url || ''))return;
    const button=text('button','Check employment','sec');button.type='button';button.dataset.employment='';
    const stop=text('button','Stop checking','sec');stop.type='button';stop.hidden=true;stop.dataset.dateStop='';stop.addEventListener('click',stopDate);
    button.addEventListener('click',()=>{activeDateStop=stop;void checkEmployment(row,person,button);});target.append(button,stop);if(person.employment_confirmed_by_user)target.append(text('small','Dates confirmed by you'));
    button.disabled=appBusy || dateBusy;
  }
  async function readEmployment(row,person) {
    if(dateStopped)throw Error('Employment check stopped. Saved dates were kept.');
    dateOperation=crypto.randomUUID().replaceAll('-','');
    const result=await window.cvStudioJobLeads.rpc('hrDate',{operation_id:dateOperation,url:person.url.replace(/\/$/,''),company_url:row.hr.company_url,company_id:row.hr.company_id},90000);
    if(dateStopped)throw Error('Employment check stopped. Saved dates were kept.');
    if(result?.url!==person.url.replace(/\/$/,'') || !/^(?:19|20)\d{2}(?:-(?:0[1-9]|1[0-2]))?$/.test(result.joined || ''))throw Error('No employment range was confirmed for this company. Saved dates were kept.');
    const data=await api('/job-leads',{action:'employment',id:row.id,revision:row.revision,url:person.url,dates:{joined:result.joined,left:result.left,current:result.current}});
    return data.record.hr.people.find(p=>p.url.replace(/\/$/,'')===person.url.replace(/\/$/,''));
  }
  async function checkMissingEmployment() {
    if(appBusy || dateBusy || boards.HR.loading || window.cvStudioJobLeads?.isBusy())return;
    const pending=filtered('HR').filter(row=>!row.joined && /^https:\/\/www\.linkedin\.com\/in\/[A-Za-z0-9_%~-]+\/?$/.test(row.url));
    if(!pending.length)return;
    dateBusy=true;dateStopped=false;activeDateStop=null;
    const activity=window.cvStudioJobLeads.activityStart(),deadline=Date.now()+3600000;let checked=0,failed=0,limited=false;
    window.cvStudioJobLeads.lock(true);controls('HR');
    const note=el('HRDateProgress'),queue=pending.slice(0,500);
    try {
      const status=await window.cvStudioJobLeads.rpc('jobStatus');
      if(status?.hr_date_check_revision!==1 || status.hr_experience_page_revision!==1 || status.hr_employment_shapes_revision!==1)throw Error('Apply the latest companion update, then refresh CV Studio and LinkedIn.');
      for(const item of queue) {
        if(dateStopped)break;
        if(Date.now()>deadline){limited=true;break;}
        // Each save advances its ad revision. Read the refreshed observation
        // source before the next person, including people sharing one ad.
        const current=boards.HR.rows.find(row=>row.url===item.url && row.company_id===item.company_id);
        if(!current || current.joined)continue;
        note.textContent=`Checking ${checked+failed+1} of ${queue.length} · ${current.name}`;
        try{await readEmployment(personSource(current,true),current);checked++;}
        catch(error){if(dateStopped)break;failed++;note.textContent=error.message;}
        dateOperation='';
        if(!await refresh('HR'))throw Error('The saved people list could not be refreshed. Check again before continuing.');
      }
      note.textContent=`${dateStopped?'Stopped':limited?'Time limit reached':'Finished'} · ${checked} updated · ${failed} not confirmed`+(pending.length>queue.length?' · More missing dates remain; click Check missing dates again.':'');
      await window.cvStudioJobLeads.refresh();
    } catch(error){failed++;note.textContent=error.message;}
    finally{dateBusy=false;dateOperation='';activeDateStop=null;window.cvStudioJobLeads.lock(false);window.cvStudioJobLeads.activityEnd(activity,failed>0);controls('HR');}
  }
  async function checkEmployment(row,person,button) {
    if(appBusy || dateBusy || window.cvStudioJobLeads?.isBusy())return;
    dateBusy=true;dateStopped=false;dateOperation=crypto.randomUUID().replaceAll('-','');const activity=window.cvStudioJobLeads.activityStart();let failed=false;
    window.cvStudioJobLeads?.lock(true);button.textContent='Checking…';
    const note=el('HRMessage');note.textContent='Reading this person’s company employment in LinkedIn…';controls('HR');
    try {
      const status=await window.cvStudioJobLeads.rpc('jobStatus');
      if(status?.hr_date_check_revision!==1 || status.hr_experience_page_revision!==1 || status.hr_employment_shapes_revision!==1)throw Error('Apply the latest companion update, then refresh CV Studio and LinkedIn to check employment.');
      const updated=await readEmployment(row,person);
      button.textContent=window.cvStudioJobLeads.employment(updated);
      await window.cvStudioJobLeads.refresh();await refresh('HR');
      note.textContent='Employment updated: '+window.cvStudioJobLeads.employment(updated);
    } catch(error) {
      failed=!dateStopped;note.textContent=error.message;button.textContent='Retry employment';button.title=error.message;
      const local=text('small',error.message);local.setAttribute('role','status');button.parentElement.append(local);manualDates(button.parentElement,row,person);
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
        const dates=text('td',row.employment);decorateDate(dates,personSource(row,true),row);tr.append(dates);
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
    if(kind==='Candidates')markSort();
  }
  async function refresh(kind) {
    const b=boards[kind];if(b.loading){b.again=true;return;}b.loading=true;const generation=++b.generation;controls(kind);el(kind+'Message').textContent='Loading…';
    try {
      const data=await api(kind==='HR'?'/apollo':'/linkedin-sourcer',{action:kind==='HR'?'hr_people':'candidates'});
      if(generation!==b.generation)return;
      b.rows=data[kind==='HR'?'people':'candidates'] || [];choices(kind);draw(kind);
      el(kind+'Message').textContent=b.rows.length?'':kind==='HR'?'No saved HR people yet.':'Candidates from new searches are saved here automatically.';return true;
    } catch(error){el(kind+'Message').textContent=error.message;return false;}
    finally{b.loading=false;controls(kind);if(b.again){b.again=false;if(!el(kind+'Panel').hidden)void refresh(kind);}}
  }
  async function exportRows(kind) {
    const b=boards[kind];if(b.exporting || b.loading || !filtered(kind).length)return;b.exporting=true;controls(kind);
    try {
      const response=await fetch(kind==='HR'?'/apollo':'/linkedin-sourcer',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:kind==='HR'?'export_people':'export_candidates',query:el(kind+'Query').value,[kind==='HR'?'company':'search']:selected(kind),...(kind==='Candidates'?candidateView():{})})});
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
  async function stopDate(){if(!dateBusy)return;dateStopped=true;controls('HR');if(dateOperation)try{await window.cvStudioJobLeads.rpc('jobReadCancel',{operation_id:dateOperation});}catch{}}
  el('HRDateStop').addEventListener('click',stopDate);
  el('HRDateAll').addEventListener('click',checkMissingEmployment);
  window.addEventListener('pagehide',()=>{void stopDate();});
  window.addEventListener('beforeunload',event=>{if(noteDrafts.size){event.preventDefault();event.returnValue='';}});
  function candidates(show){el('CandidatesPanel').hidden=!show;el('SourcerSearchPanel').hidden=show;el('CandidatesTab').setAttribute('aria-pressed',String(show));el('SourcerSearchTab').setAttribute('aria-pressed',String(!show));if(show)void refresh('Candidates');}
  // Sort/order choices are a per-viewer convenience in browser storage.
  for(const name of ['Sort','Order']){
    try{const saved=localStorage.getItem('cvstudio_candidates_'+name.toLowerCase());if(saved && [...el('Candidates'+name).options].some(option=>option.value===saved))el('Candidates'+name).value=saved;}catch{}
  }
  for(const name of ['MinScore','Read','Sort','Order'])el('Candidates'+name).addEventListener('change',()=>{
    if(name==='Sort' || name==='Order')try{localStorage.setItem('cvstudio_candidates_'+name.toLowerCase(),el('Candidates'+name).value);}catch{}
    boards.Candidates.page=0;draw('Candidates');
  });
  el('CandidatesTab').addEventListener('click',()=>candidates(true));el('SourcerSearchTab').addEventListener('click',()=>candidates(false));initialized=true;
})();
