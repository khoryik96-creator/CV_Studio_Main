/* Reviewed company-contact creation from protected unlocked-contact history. */
(function(){
  'use strict';
  const el=name=>document.getElementById('jobLeadsJA'+name);
  let ready=false,current=null,account='',review='',working=false,generation=0;
  const msg=value=>{el('Message').textContent=value;};
  async function api(body){
    const response=await fetch('/jobadder/contact_actions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data=await response.json();if(!response.ok || !data.ok)throw Error(data.error || 'JobAdder could not complete this action.');return data;
  }
  function lock(value){working=value;for(const name of ['Close','Search','CompanyQuery','Company','First','Last','Position','Review','Create','Check'])el(name).disabled=value;}
  function invalidate(){review='';el('Create').hidden=true;el('Check').hidden=true;}
  function body(action){return {action,contact_key:current.contact_key,account,company_id:Number(el('Company').value),first_name:el('First').value,last_name:el('Last').value,position:el('Position').value,review_token:review,confirmed:action==='create'};}
  async function search(){
    if(working)return;const token=generation;lock(true);invalidate();account='';el('Company').replaceChildren(new Option('Choose company',''));msg('Searching JobAdder companies…');
    try{
      const data=await api({action:'companies',query:el('CompanyQuery').value});if(token!==generation)return;account=data.account;
      for(const company of data.companies)el('Company').append(new Option(company.name+(company.location?' · '+company.location:'')+' · #'+company.id,String(company.id)));
      msg(data.companies.length?(data.more?'Refine the company name if needed; showing the first 50 matches.':'Choose the company, then review the contact.'):'No companies found. Search another name or add the company in JobAdder first.');
    }catch(error){if(token===generation)msg(error.message);}finally{if(token===generation)lock(false);}
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
  }
  function open(row){
    if(working)return;init();current=row;++generation;account='';invalidate();
    const names=row.name.trim().split(/\s+/);el('First').value=names.shift() || '';el('Last').value=names.join(' ');el('Position').value=row.position || '';el('Email').value=row.email;el('CompanyQuery').value=row.company || '';
    el('Company').replaceChildren(new Option('Choose company',''));msg('Choose the existing JobAdder company and check the name before creating.');lock(false);el('Dialog').showModal();
  }
  window.cvStudioJAContacts={decorate(parent,row){if(!row.contact_key)return;const button=document.createElement('button');button.type='button';button.className='sec';button.textContent='Create in JobAdder';button.addEventListener('click',()=>open(row));parent.append(button);}};
})();
