const assert=require('assert/strict');
const {fixture}=require('./test_job_search_frontend');
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
const reply=data=>({ok:true,json:async()=>({ok:true,...data})});
(async()=>{
  const f=fixture({apollo:true,emailVerifier:true});let requests=[],hold=null;
  const rows=Array.from({length:41},(_,i)=>({name:i===0?'<img src=x onerror=bad>':'Person '+i,position:'HR',company:'Example '+i,company_id:String(i%2?102:101),country:i%2?'Singapore':'Malaysia',email:'person'+i+'@example.test',email_status:i%3?'verified':'catch_all',profile_url:'https://www.linkedin.com/in/person-'+i}));
  f.state.onApollo=async data=>{
    requests.push(data);
    if(!data)return reply({connected:false,available:true});
    if(data.action==='contacts'){
      if(hold)await new Promise(resolve=>{hold.release=resolve});
      if(f.state.contactsFail)return {ok:false,json:async()=>({error:'Fictional protected storage failure'})};
      return reply({contacts:rows,contact_warning:f.state.incomplete?'Some emails have not been archived.':''});
    }
    if(data.action==='export_contacts'){
      f.state.exportQuery=data.query;f.state.exportFilters=data.filters;
      if(f.state.exportFail)return {ok:false,json:async()=>({error:'Fictional export failure'})};
      return {ok:true,headers:{get:()=>f.state.incomplete?'1':null},blob:async()=>new Blob(['synthetic XLSX export'])};
    }
    throw Error('Unexpected paid or account action');
  };
  await f.init();await tick();
  assert(f.el('ApolloContactsPanel').hidden);
  assert(!requests.some(x=>x?.action==='contacts'),'opening Job Leads does not read history until requested');
  await f.el('ApolloContactsTab').click();await tick();
  assert(!f.el('ApolloContactsPanel').hidden && f.el('ApolloAdsPanel').hidden);
  assert.equal(f.el('ApolloContactsCount').textContent,'41');
  assert.equal(f.el('ApolloContactsRows').children.length,40);
  assert.equal(f.el('ApolloContactsRows').querySelectorAll('a')[0].textContent,rows[0].name,'source strings stay text, not markup');
  assert(!f.el('ApolloContactsNext').disabled);await f.el('ApolloContactsNext').click();
  assert.equal(f.el('ApolloContactsRows').children.length,1);
  await f.el('ApolloContactsPrevious').click();
  f.el('ApolloContactsSearch').value='Example 40';f.el('ApolloContactsSearch').handlers.input();
  assert.equal(f.el('ApolloContactsRows').children.length,1);assert.equal(f.el('ApolloContactsCount').textContent,'1');
  await f.el('ApolloContactsExport').click();assert.equal(f.state.exportQuery,'Example 40');
  f.el('ApolloContactsSearch').value='';f.el('ApolloContactsSearch').handlers.input();
  f.el('ApolloContactsCompany').value='101';f.el('ApolloContactsCompany').handlers.change();
  f.el('ApolloContactsCountry').value='Malaysia';f.el('ApolloContactsCountry').handlers.change();
  f.el('ApolloContactsStatus').value='catch_all';f.el('ApolloContactsStatus').handlers.change();
  assert.equal(Number(f.el('ApolloContactsCount').textContent),rows.filter(r=>r.company_id==='101' && r.country==='Malaysia' && r.email_status==='catch_all').length);
  await f.el('ApolloContactsExport').click();assert.equal(f.state.exportFilters.company,'101');assert.equal(f.state.exportFilters.country,'Malaysia');assert.equal(f.state.exportFilters.email_status,'catch_all');
  let probes=0;f.state.onVerify=async request=>{probes++;assert.equal(request.mode,'deep');return reply({result:{status:'catch_all',reason:'Synthetic catch-all result',assessment:{label:'Use caution'},attempts:2}});};
  assert.equal(probes,0,'loading and filtering contacts cannot probe mail servers');
  await f.el('ApolloContactsRows').querySelectorAll('button').find(b=>b.textContent==='Verify email').click();assert.equal(probes,1);
  for(const suffix of ['Company','Country','Status']){f.el('ApolloContacts'+suffix).value='';f.el('ApolloContacts'+suffix).handlers.change();}
  assert(f.el('ApolloContactsRows').querySelectorAll('strong').some(n=>n.textContent==='Use caution'),'verification survives filter/page rerenders in memory');
  assert.equal(probes,1,'redrawing a verified contact never probes again');

  assert.match(f.el('ApolloContactsMessage').textContent,/downloaded/);
  f.state.incomplete=true;await f.el('ApolloContactsRefresh').click();assert.match(f.el('ApolloContactsMessage').textContent,/not been archived/);
  await f.el('ApolloContactsExport').click();assert.match(f.el('ApolloContactsMessage').textContent,/not been archived/);
  f.state.incomplete=false;
  f.state.exportFail=true;await f.el('ApolloContactsExport').click();assert.match(f.el('ApolloContactsMessage').textContent,/export failure/);
  f.el('ApolloContactsSearch').value='unmatched';f.el('ApolloContactsSearch').handlers.input();
  assert(f.el('ApolloContactsExport').disabled);
  f.el('notes').value='Keep this draft';f.el('notes').handlers.input();
  await f.el('ApolloAdsTab').click();assert.equal(f.el('notes').value,'Keep this draft');
  assert(!f.el('ApolloAdsPanel').hidden && f.el('ApolloContactsPanel').hidden);
  f.state.contactsFail=true;await f.el('ApolloContactsTab').click();await tick();
  assert.match(f.el('ApolloContactsMessage').textContent,/storage failure/);
  assert.equal(f.requests.length,0,'dashboard never rewrites ads');
  assert(!requests.some(x=>['reveal','connect','disconnect','lookup-status'].includes(x?.action)),'dashboard has no paid/account side effects');
  f.state.contactsFail=false;hold={};const loading=f.el('ApolloContactsRefresh').click();await tick();
  assert(f.el('ApolloContactsRefresh').disabled && f.el('ApolloContactsExport').disabled);
  const release=hold.release;hold=null;release();await loading;
  f.pagehide();console.log('Contact dashboard: local history, search, paging, safe text/export, disconnected access, errors and draft/paid isolation passed.');
})().catch(error=>{console.error(error);process.exit(1)});
