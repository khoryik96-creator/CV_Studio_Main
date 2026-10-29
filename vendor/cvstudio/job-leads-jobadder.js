/* Reviewed company-contact creation from protected unlocked-contact history. */
(function(){
  'use strict';
  const el=name=>document.getElementById('jobLeadsJA'+name);
  let ready=false,current=null,account='',review='',working=false,generation=0;
  let users=[],recruiters=null,assignmentAccount='',assignmentsReady=false;
  const msg=value=>{el('Message').textContent=value;el('Open').hidden=true;el('Open').href='';};
  function contactLink(data){
    if(!['created','exists'].includes(data.state) || !Number.isSafeInteger(data.contact_id) || data.contact_id<=0 ||
        typeof data.contact_url!=='string' || !/^https:\/\/[a-z0-9]+\.jobadder\.com\/contacts\/[1-9]\d*$/.test(data.contact_url) ||
        data.contact_url.split('/').pop()!==String(data.contact_id))return;
    el('Open').href=data.contact_url;el('Open').hidden=false;
  }
  async function api(body){
    const response=await fetch('/jobadder/contact_actions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data=await response.json();if(!response.ok || !data.ok)throw Error(data.error || 'JobAdder could not complete this action.');return data;
  }
  function lock(value){working=value;for(const name of ['Close','Search','CompanyQuery','Company','First','Last','Position','Review','Create','Check'])el(name).disabled=value;
    for(const name of ['Owner','RecruiterFilter','SelectAll','ClearRecruiters','Remember'])el(name).disabled=value || !assignmentsReady;
    for(const checkbox of el('RecruiterList').querySelectorAll('input'))checkbox.disabled=value || !assignmentsReady;
  }
  function invalidate(){review='';el('Create').hidden=true;el('Check').hidden=true;el('Open').hidden=true;el('Open').href='';}
  function body(action){return {action,contact_key:current.contact_key,account,company_id:Number(el('Company').value),first_name:el('First').value,last_name:el('Last').value,position:el('Position').value,review_token:review,confirmed:action==='create',
    owner_user_id:assignmentsReady && el('Owner').value?Number(el('Owner').value):null,recruiter_user_ids:assignmentsReady?recruiters:null,remember_assignments:assignmentsReady && el('Remember').checked};}
  function assignmentSummary(){el('RecruiterSummary').textContent='Recruiters · '+(recruiters===null?'JobAdder default':recruiters.length+' selected');}
  function renderRecruiters(){
    const filter=el('RecruiterFilter').value.trim().toLocaleLowerCase();el('RecruiterList').replaceChildren();
    for(const user of users.filter(user=>user.name.toLocaleLowerCase().includes(filter))){
      const label=document.createElement('label'),box=document.createElement('input');box.type='checkbox';box.checked=!!recruiters?.includes(user.id);box.disabled=working || !assignmentsReady;
      box.addEventListener('change',()=>{const selected=new Set(recruiters || []);if(box.checked)selected.add(user.id);else selected.delete(user.id);recruiters=[...selected].sort((a,b)=>a-b);invalidate();assignmentSummary();});
      label.append(box,document.createTextNode(user.name));el('RecruiterList').append(label);
    }
    assignmentSummary();
  }
  function resetAssignments(){users=[];recruiters=null;assignmentAccount='';assignmentsReady=false;el('Owner').replaceChildren(new Option('JobAdder default',''));el('Owner').value='';el('RecruiterFilter').value='';renderRecruiters();}
  function applyAssignments(data){
    const choices=data.assignments;
    if(!choices?.available || !Array.isArray(choices.users)){resetAssignments();return choices?.message || '';}
    const validId=value=>Number.isInteger(value) && value>0 && value<=2147483647;
    if(choices.users.length>1000 || choices.users.some(user=>!validId(user?.id) || typeof user.name!=='string') || new Set(choices.users.map(user=>user.id)).size!==choices.users.length){resetAssignments();throw Error('JobAdder user choices could not be confirmed.');}
    const same=assignmentsReady && assignmentAccount===data.account;
    const owner=same?(el('Owner').value?Number(el('Owner').value):null):choices.defaults?.owner_user_id ?? null;
    const selected=same?recruiters:choices.defaults?.recruiter_user_ids ?? null;
    users=choices.users;const ids=new Set(users.map(user=>user.id));
    if(owner!==null && !ids.has(owner) || selected!==null && (!Array.isArray(selected) || selected.length>1000 || selected.some(id=>!ids.has(id)) || new Set(selected).size!==selected.length)) {resetAssignments();throw Error('Saved owner or recruiter choices are unavailable. Search again and choose them.');}
    assignmentAccount=data.account;assignmentsReady=true;recruiters=selected===null?null:[...selected];
    el('Owner').replaceChildren(new Option('JobAdder default',''));for(const user of users)el('Owner').append(new Option(user.name,String(user.id)));el('Owner').value=owner===null?'':String(owner);renderRecruiters();
    return choices.stale?'Saved owner/recruiter choices are no longer available. Choose them again.':'';
  }
  async function search(){
    if(working)return;const token=generation;lock(true);invalidate();account='';el('Company').replaceChildren(new Option('Choose company',''));msg('Searching JobAdder companies…');
    try{
      const data=await api({action:'companies',query:el('CompanyQuery').value,include_assignments:true});if(token!==generation)return;account=data.account;
      for(const company of data.companies)el('Company').append(new Option(company.name+(company.location?' · '+company.location:'')+' · #'+company.id,String(company.id)));
      const notice=applyAssignments(data);
      msg((data.companies.length?(data.more?'Refine the company name if needed; showing the first 50 matches.':'Choose the company, then review the contact.'):'No companies found. Search another name or add the company in JobAdder first.')+(notice?' '+notice:''));
    }catch(error){if(token===generation){resetAssignments();msg(error.message);}}finally{if(token===generation)lock(false);}
  }
  async function act(action){
    if(working || !current)return;
    if(!el('Company').value || !account){msg('Search for and choose a JobAdder company first.');return;}
    if(action==='create' && !review)return;
    const token=generation,request=body(action);lock(true);msg(action==='create'?'Creating contact in JobAdder…':action==='check'?'Checking the previous request…':'Checking details and existing contacts…');
    try{
      const data=await api(request);if(token!==generation)return;
      review=data.review_token || '';el('Create').hidden=data.state!=='review';el('Check').hidden=data.state!=='unconfirmed';
      msg(data.message+(data.state==='review'?' Company: '+data.company:'')+(data.contact_id?' Contact #'+data.contact_id:'')+(data.matches?.length?' Company: '+data.matches.map(row=>row.company || 'Existing company').join(', '):''));
      contactLink(data);
    }catch(error){if(token===generation){review='';el('Create').hidden=true;el('Check').hidden=action==='review';msg(error.message+(action==='create'?' Check the previous result before starting another request.':''));}}
    finally{if(token===generation)lock(false);}
  }
  function init(){
    if(ready)return;ready=true;
    el('Search').addEventListener('click',search);el('Review').addEventListener('click',()=>act('review'));el('Create').addEventListener('click',()=>act('create'));el('Check').addEventListener('click',()=>act('check'));
    el('Close').addEventListener('click',()=>{if(!working){++generation;el('Dialog').close();}});
    el('Dialog').addEventListener('cancel',event=>{if(working)event.preventDefault();else ++generation;});
    for(const name of ['First','Last','Position'])el(name).addEventListener('input',invalidate);
    el('Company').addEventListener('change',invalidate);el('CompanyQuery').addEventListener('input',()=>{account='';invalidate();});
    el('Owner').addEventListener('change',invalidate);el('RecruiterFilter').addEventListener('input',renderRecruiters);
    el('SelectAll').addEventListener('click',()=>{if(working || !assignmentsReady)return;recruiters=users.map(user=>user.id);invalidate();renderRecruiters();});
    el('ClearRecruiters').addEventListener('click',()=>{if(working || !assignmentsReady)return;recruiters=[];invalidate();renderRecruiters();});
  }
  function open(row){
    if(working)return;init();current=row;++generation;account='';invalidate();resetAssignments();el('Remember').checked=true;el('Recruiters').open=false;
    const names=row.name.trim().split(/\s+/);el('First').value=names.shift() || '';el('Last').value=names.join(' ');el('Position').value=row.position || '';el('Email').value=row.email;el('CompanyQuery').value=row.company || '';
    el('Company').replaceChildren(new Option('Choose company',''));msg('Choose the existing JobAdder company and check the name before creating.');lock(false);el('Dialog').showModal();
  }
  window.cvStudioJAContacts={decorate(parent,row){if(!row.contact_key)return;const button=document.createElement('button');button.type='button';button.className='sec';button.textContent='Create in JobAdder';button.addEventListener('click',()=>open(row));parent.append(button);}};
})();
