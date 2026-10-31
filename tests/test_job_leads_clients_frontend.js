/* Signed clients view in Job Leads. Fictional clients, accounts and ads; the
 * JobAdder, Job Leads and companion replies are all simulated in memory. */
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const walkSource=fs.readFileSync(path.join(__dirname,'../vendor/cvstudio/job-search-walk.js'),'utf8');
const source=fs.readFileSync(path.join(__dirname,'../vendor/cvstudio/job-leads-clients.js'),'utf8');
const ACCOUNT='a'.repeat(64),OTHER='b'.repeat(64);

class Element {
  constructor(tag='div'){Object.assign(this,{tagName:tag.toUpperCase(),children:[],handlers:{},dataset:{},attributes:{},textContent:'',value:'',checked:false,disabled:false,hidden:false,open:false,href:'',target:'',rel:''});}
  addEventListener(type,fn){(this.handlers[type] ||= []).push(fn);}
  dispatch(type,event={}){return Promise.all((this.handlers[type]||[]).map(fn=>fn({preventDefault(){},key:'',...event,target:this})));}
  append(...items){this.children.push(...items);} replaceChildren(...items){this.children=items;}
  setAttribute(name,value){this.attributes[name]=String(value);} getAttribute(name){return this.attributes[name] ?? null;} removeAttribute(name){delete this.attributes[name];}
  querySelectorAll(selector){const found=[],walk=item=>{for(const child of item.children){if(!(child instanceof Element))continue;if(selector==='[data-client-action]'?'clientAction' in child.dataset:child.tagName===selector.toUpperCase())found.push(child);walk(child);}};walk(this);return found;}
  click(){return this.dispatch('click');}
  get text(){return [this.textContent,...this.children.map(child=>child instanceof Element?child.text:'')].join(' ').replace(/\s+/g,' ').trim();}
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function settle(times=40){for(let n=0;n<times;n++)await tick();}
const job=(id,company='Example Client Sdn Bhd',patch={})=>({url:'https://www.linkedin.com/jobs/view/'+id,role:'Role '+id,company,location:'Kuala Lumpur',date_posted:'2026-10-20',description:'Summary '+id,...patch});
const client=(id,linkedin_id,name='Client '+id)=>({company_id:id,name,linkedin_url:'',linkedin_id,followed_at:'2026-10-30T00:00:00+00:00',pulled_at:'',jobadder_url:'https://app.jobadder.com/companies/'+id});
const bulk=(start,count,company)=>Array.from({length:count},(_,n)=>job(String(start+n),company));

function fixture(options={}){
  const ids=new Map(),calls=[],leadsCalls=[],rpcCalls=[],windowEvents={},storage=options.storage||new Map();
  const document={getElementById:id=>{if(!ids.has(id))ids.set(id,new Element(id.endsWith('Select')||id.endsWith('Pages')||id.endsWith('Folder')?'select':'div'));return ids.get(id);},createElement:tag=>new Element(tag)};
  const el=name=>document.getElementById('jobLeadsClients'+name);
  el('Pages').value='1';
  // As on the page, the tables sit inside the panel, so panel-wide control
  // updates reach every row.
  el('Panel').append(el('Statuses'),el('Followed'),el('Found'),el('Companies'));
  const state={account:ACCOUNT,signed:[],statuses:[{id:1,name:'Prospect',active:true},{id:2,name:'Signed Client',active:true}],followed:[],
    companies:[{company_id:11,name:'Example Client',status:'Signed Client',owner:'Sample Owner',followed:false,jobadder_url:'https://app.jobadder.com/companies/11'},
               {company_id:12,name:'Second Client',status:'Signed Client',owner:'',followed:false,jobadder_url:'javascript:alert(1)'}],
    details:{11:{linkedin_url:'https://www.linkedin.com/company/example-client/',linkedin_id:'4242'},12:{linkedin_url:'',linkedin_id:''}},
    records:[{id:'1'.repeat(32),url:'https://www.linkedin.com/jobs/view/900',company:'Example Client',role:'Saved role',deleted:false},
             {id:'2'.repeat(32),url:'https://www.linkedin.com/jobs/view/901',company:'PT Example Client Tbk',role:'Other saved',deleted:false,hr:{company_url:'https://www.linkedin.com/company/second-client/',company_id:'5151'}}],
    folders:['Clients'],busy:false,locks:[],refreshes:0,apiInfo:null,companion:{connected:true,concurrent_scans_revision:1,job_search:true,job_search_revision:1,job_search_company_revision:1,busy:false},
    pages:{'4242':[[job(1001),job(900),job(1002)],[job(1003)]],'5151':[[job(1002,'Second Client'),job(2001,'Second Client'),{url:'https://evil.test/jobs/view/1',company:'X',role:'Bad'}]]},hold:null,holdBegin:null,...options};
  const reply=data=>({ok:true,json:async()=>({ok:true,...data})});
  const fail=(status,error)=>({ok:false,status,json:async()=>({ok:false,error})});
  const fetch=async(url,init={})=>{
    if(url==='/jobadder/api_info')return {ok:true,json:async()=>state.apiInfo || {connected:true,account_cache_namespace:state.account}};
    if(url==='/job-leads'){
      if(!init.body)return reply({records:structuredClone(state.records),folders:[...state.folders]});
      const body=JSON.parse(init.body);leadsCalls.push(body);assert.equal(body.action,'save');
      const duplicate=state.records.find(row=>row.url===body.record.url);
      if(duplicate)return reply({record:duplicate,duplicate:true});
      const record={...body.record,id:String(state.records.length+1).padStart(32,'0'),deleted:false};state.records.push(record);return reply({record,duplicate:false});
    }
    assert.equal(url,'/jobadder/clients','no other route is used');assert.equal(init.method,'POST');
    const body=JSON.parse(init.body);calls.push(body);
    if(state.down)return fail(503,'JobAdder could not be reached to refresh the sign-in. Check the internet connection.');
    if(!['overview','statuses','companies'].includes(body.action) && body.account!==state.account)return fail(409,'The JobAdder account changed.');
    const followed=()=>structuredClone(state.followed);
    if(body.action==='overview')return reply({account:state.account,signed:[...state.signed],followed:followed()});
    if(body.action==='statuses')return reply({account:state.account,statuses:structuredClone(state.statuses),signed:[...state.signed]});
    if(body.action==='set_statuses'){state.signed=[...body.status_ids];return reply({account:state.account,signed:[...state.signed]});}
    if(body.action==='companies')return reply({account:state.account,companies:state.companies.map(row=>({...row,followed:state.followed.some(f=>f.company_id===row.company_id)})),offset:0,total:2,next_offset:null});
    if(body.action==='follow'){const company=state.companies.find(row=>row.company_id===body.company_id);state.followed.push({company_id:company.company_id,name:company.name,...state.details[company.company_id],followed_at:'2026-10-30T00:00:00+00:00',pulled_at:'',jobadder_url:company.jobadder_url});return reply({account:state.account,followed:followed()});}
    if(body.action==='unfollow'){state.followed=state.followed.filter(row=>row.company_id!==body.company_id);return reply({account:state.account,followed:followed()});}
    if(body.action==='set_linkedin'){const row=state.followed.find(f=>f.company_id===body.company_id);const id=/f_C=(\d+)/.exec(body.link)?.[1];const page=/\/company\/([\w-]+)\//.exec(body.link)?.[1];if(id)row.linkedin_id=id;if(page){row.linkedin_url='https://www.linkedin.com/company/'+page+'/';row.linkedin_id=/^\d+$/.test(page)?page:'';}return reply({account:state.account,followed:followed()});}
    if(body.action==='pulled'){state.followed.find(f=>f.company_id===body.company_id).pulled_at='2026-10-30T09:00:00+00:00';return reply({account:state.account,followed:followed()});}
    throw Error('unexpected action '+body.action);
  };
  const runs=new Map(),begun=[],ended=[];let tab=40;
  const app={
    lock:value=>{state.locks.push(value);state.busy=value;},isBusy:()=>state.busy,refresh:async()=>{state.refreshes++;},activityStart:()=>'activity',activityEnd:()=>{},
    rpc:async(action,args={})=>{
      rpcCalls.push({action,args:structuredClone(args)});
      if(action==='jobStatus')return state.companion;
      if(action==='jobSearchBegin'){
        assert.equal(args.use_open,false);assert.equal(args.query,'');begun.push(args.run_id);
        if(state.holdBegin)await new Promise(resolve=>{state.releaseBegin=resolve;});
        runs.set(args.run_id,{company:args.company_id,page:0,tab:++tab});return {tab_id:tab};
      }
      if(action==='end'){ended.push(args.run_id);if(!runs.has(args.run_id))throw Error('No run yet.');runs.delete(args.run_id);return true;}
      const run=runs.get(args.run_id);if(!run)throw Error('The companion run has ended.');
      if(args.method==='scrollJobSearch')return false;
      if(args.method==='nextJobSearch'){run.page++;return true;}
      if(state.hold || state.holdPage===run.page){state.holdPage=null;await new Promise(resolve=>{state.release=resolve;});}
      const jobs=(state.pages[run.company]||[])[run.page]||[];
      return {jobs,signature:run.page+':'+jobs.map(row=>row.url).join('|'),hasNext:run.page+1<(state.pages[run.company]||[]).length,atBottom:true,empty:!jobs.length};
    }};
  const window={cvStudioJobLeads:app,cvStudioPeople:{hideHR:()=>{state.hrHidden=true;}},_jaAccountCacheNamespace:'ja'+ACCOUNT,addEventListener:(name,fn)=>{windowEvents[name]=fn;}};
  window.applyJAPublicInfo=info=>{const next=info?.connected?'ja'+info.account_cache_namespace:'';const before=window._jaAccountCacheNamespace;window._jaAccountCacheNamespace=next;state.applied=(state.applied||0)+1;if(before && before!==next)window.clearJobLeadsClientsAccountState();};
  const localStorage={getItem:key=>storage.has(key)?storage.get(key):null,setItem:(key,value)=>storage.set(key,String(value))};
  let serial=0;
  const context=vm.createContext({window,document,fetch,console,structuredClone,Promise,Set,Map,Array,Number,String,Math,Error,JSON,localStorage,URL,
    crypto:{randomUUID:()=>'00000000-0000-4000-8000-'+String(++serial).padStart(12,'0')},setTimeout:(fn,ms)=>setTimeout(fn,ms===350?0:ms)});
  vm.runInContext(walkSource,context);vm.runInContext(source,context);
  return {el,state,calls,leadsCalls,rpcCalls,begun,ended,storage,window,document,api:window.cvStudioJobLeadsClients,clear:()=>window.clearJobLeadsClientsAccountState(),pagehide:()=>windowEvents.pagehide?.()};
}
const rows=f=>f.el('Followed').children;
const found=f=>f.el('Found').children;
const box=row=>row.querySelectorAll('input')[0];
const allEnded=f=>f.begun.every(run=>f.ended.includes(run));

let finished=false;
// A scenario that never settles must fail, not end silently with exit code 0.
process.on('exit',()=>{if(!finished && !process.exitCode){console.error('Signed clients test did not finish: a pending step never settled.');process.exitCode=1;}});
(async()=>{
  // Pure helpers.
  {const {api}=fixture();
   assert.deepEqual([...api.words('PT Example Client Indonesia Tbk')],['example','client','indonesia']);
   assert(api.sameCompany('Example Client','PT Example Client Tbk'));assert(api.sameCompany('Example Client Sdn. Bhd.','example client'));
   assert(api.sameCompany('Example','Other Example Client'),'every word of the shorter name inside the longer name matches');assert(!api.sameCompany('Example Client','Example Holdings'));assert(!api.sameCompany('PT Tbk','PT Tbk'),'legal words alone never match');
   assert.equal(api.linkedinId({linkedin_id:'77'},[]),'77');
   assert.equal(api.linkedinId({linkedin_url:'https://www.linkedin.com/company/second-client/',linkedin_id:''},[{hr:{company_url:'https://www.linkedin.com/company/second-client/',company_id:'5151'}}]),'5151');
   assert.equal(api.linkedinId({linkedin_url:'https://www.linkedin.com/company/unknown/',linkedin_id:''},[]),'');
   assert.equal(api.linkedinId({linkedin_url:'javascript:alert(1)',linkedin_id:'x'},[{hr:{company_url:'javascript:alert(1)',company_id:'1'}}]),'');
   const tagged=api.cleanJobs({jobs:[job(1),job(1),{url:'https://evil.test/jobs/view/2',company:'X',role:'Y'},job(3)]},{company_id:5,name:'Five'},[job(3)]);
   assert.deepEqual([...tagged.added.map(row=>row.url)],['https://www.linkedin.com/jobs/view/1'],'shared checks plus de-duplication');assert.equal(tagged.added[0].client_name,'Five');
   const full=api.cleanJobs({jobs:[job(7),job(8)]},{company_id:5,name:'Five'},Array.from({length:api.MAX_FOUND-1},(_,n)=>({url:'u'+n})));
   assert.equal(full.added.length,1);assert.equal(full.dropped,1,'an ad that does not fit is counted');}

  // The shared search loop checks for Stop before every read.
  {const {window:w}=fixture();let checks=0,reads=0;
   const walking=w.cvStudioJobSearch.walk({rpc:async(action,args)=>{if(args.method==='readJobSearch')reads++;return {loading:true};},run:'r',tab:1,pages:1,
     check:()=>{if(++checks===3)throw Error('Stopped.');},keep(){},full:()=>false});
   await assert.rejects(walking,/Stopped/);assert.equal(reads,1,'a Stop between reads prevents the next read');}

  // Opening the view: other panels hide, nothing is written, statuses are asked for.
  const f=fixture();
  const ads=f.document.getElementById('jobLeadsApolloAdsPanel'),contacts=f.document.getElementById('jobLeadsApolloContactsPanel');
  ads.hidden=false;
  await f.el('Tab').click();await settle();
  assert(!f.el('Panel').hidden);assert(ads.hidden && contacts.hidden && f.state.hrHidden,'the other Job Leads views hide');
  assert.equal(f.el('Tab').getAttribute('aria-pressed'),'true');
  assert.deepEqual(f.calls.map(c=>c.action),['overview','statuses']);
  assert(f.el('Setup').open,'status setup opens until signed statuses are chosen');
  assert.match(f.el('Message').textContent,/Start by choosing/);
  assert(f.el('Search').disabled && f.el('Pull').disabled);

  // Choose the signed status, then find and follow clients.
  const statusBoxes=f.el('Statuses').querySelectorAll('input');assert.equal(statusBoxes.length,2);
  statusBoxes[1].checked=true;await statusBoxes[1].dispatch('change');assert(!f.el('StatusesSave').disabled);
  await f.el('StatusesSave').click();await settle();
  assert.deepEqual(f.calls.at(-1),{action:'set_statuses',status_ids:[2],account:ACCOUNT});
  assert.match(f.el('SetupSummary').textContent,/Signed Client/);assert(f.el('Browse').open);
  f.el('Query').value=' Example ';await f.el('Search').click();await settle();
  assert.deepEqual(f.calls.at(-1),{action:'companies',query:'Example',offset:0});
  const companyRows=f.el('Companies').children;assert.equal(companyRows.length,2);
  assert.equal(companyRows[0].querySelectorAll('a')[0].href,'https://app.jobadder.com/companies/11');
  assert.equal(companyRows[1].querySelectorAll('a')[0].href,'','an unsafe JobAdder link never becomes a link');
  await companyRows[0].querySelectorAll('button')[0].click();await settle();
  assert.deepEqual(f.calls.at(-1),{action:'follow',company_id:11,account:ACCOUNT});
  await f.el('Companies').children[1].querySelectorAll('button')[0].click();await settle();
  assert.equal(rows(f).length,2);assert.equal(f.el('Count').textContent,'2');
  assert(box(rows(f)[0]).checked && !box(rows(f)[0]).disabled,'a client with a LinkedIn company id is ready to pull');
  assert(box(rows(f)[1]).disabled,'a client without a LinkedIn link cannot be pulled');
  assert.match(rows(f)[1].text,/Add its LinkedIn company page/);
  assert.match(rows(f)[0].text,/Ready to pull/);
  assert.equal(rows(f)[0].children[3].textContent,'2','saved ads are counted by company name, ignoring PT/Tbk');

  // A pasted named page links to an HR-scanned company id.
  const editor=rows(f)[1].querySelectorAll('input')[1];editor.value='https://www.linkedin.com/company/second-client/';
  await rows(f)[1].querySelectorAll('button')[0].click();await settle();
  assert.equal(f.calls.at(-1).action,'set_linkedin');assert.equal(f.calls.at(-1).account,ACCOUNT);
  assert(!box(rows(f)[1]).disabled && box(rows(f)[1]).checked,'the company id from a saved HR scan makes it pullable');
  assert.match(rows(f)[1].text,/saved HR scan/);
  assert.equal(f.el('Ticked').textContent,'2 of 15 ticked');

  // An outdated or missing companion is reported before any search opens.
  f.state.companion={...f.state.companion,job_search_company_revision:undefined};
  await f.el('Pull').click();await settle();
  assert.match(f.el('Progress').textContent,/latest companion update/);assert(!f.rpcCalls.some(c=>c.action==='jobSearchBegin'));
  assert.deepEqual(f.state.locks,[true,false],'Job Leads is unlocked after a refused pull');
  f.state.companion={...f.state.companion,job_search_company_revision:1,connected:false};
  await f.el('Pull').click();await settle();assert.match(f.el('Progress').textContent,/companion enabled/);
  f.state.companion={...f.state.companion,connected:true};

  // A busy Job Leads: the buttons stay usable and explain instead of doing nothing.
  f.state.busy=true;
  assert(!f.el('Pull').disabled,'Pull is not left disabled by Job Leads');
  const before=f.rpcCalls.length;await f.el('Pull').click();await settle();
  assert.equal(f.rpcCalls.length,before);assert.match(f.el('Progress').textContent,/Job Leads is busy/);
  await f.el('Refresh').click();await settle();assert.equal(f.calls.at(-1).action,'statuses','reading still works while Job Leads is busy');
  assert(!f.el('Pull').disabled,'after a redraw Pull is still not disabled by a busy Job Leads');
  f.state.busy=false;

  // Pull both clients: company-filtered searches, client tags, de-duplication.
  f.el('Pages').value='2';f.state.locks=[];
  await f.el('Pull').click();await settle(120);
  const begins=f.rpcCalls.filter(c=>c.action==='jobSearchBegin');
  assert.deepEqual(begins.map(c=>c.args.company_id),['4242','5151']);assert(begins.every(c=>c.args.max_pages===2 && c.args.location===''));
  assert(allEnded(f),'every companion run is ended');
  assert.deepEqual(f.state.locks,[true,false]);
  const urls=found(f).map(row=>row.querySelectorAll('a')[0].href);
  assert.deepEqual(urls,['https://www.linkedin.com/jobs/view/1001','https://www.linkedin.com/jobs/view/900','https://www.linkedin.com/jobs/view/1002','https://www.linkedin.com/jobs/view/1003','https://www.linkedin.com/jobs/view/2001'],'unsafe and duplicate ads are dropped');
  assert.match(found(f)[1].text,/Already in Job ads/);assert.equal(found(f)[1].querySelectorAll('input').length,0,'saved ads cannot be added twice');
  assert.equal(found(f)[4].children[2].textContent,'Second Client','each ad keeps the client it was pulled for');
  assert.deepEqual(f.calls.filter(c=>c.action==='pulled').map(c=>c.company_id),[11,12]);
  assert.match(f.el('Progress').textContent,/Finished\. 2 clients pulled, 5 ads found, 4 new to review/);
  assert(!f.el('Review').hidden);assert.equal(f.el('FoundCount').textContent,'5');

  // Review, then add the chosen ads to Job ads.
  assert(f.el('Add').disabled,'nothing is added until ads are chosen');
  f.el('SelectNew').checked=true;await f.el('SelectNew').dispatch('change');
  const firstNew=box(found(f)[0]);firstNew.checked=false;await firstNew.dispatch('change');
  f.el('Folder').value='Clients';
  await f.el('Add').click();await settle();
  assert.deepEqual(f.leadsCalls.map(c=>c.record.url),['https://www.linkedin.com/jobs/view/1002','https://www.linkedin.com/jobs/view/1003','https://www.linkedin.com/jobs/view/2001']);
  assert.deepEqual(Object.keys(f.leadsCalls[0].record).sort(),['company','contact','date_posted','description','description_rich','description_truncated','folder','follow_up','location','notes','role','status','url'].sort());
  assert.equal(f.leadsCalls[0].record.folder,'Clients');assert.equal(f.leadsCalls[0].record.status,'new');assert.equal(f.leadsCalls[0].record.notes,'');
  assert.equal(f.state.refreshes,1,'the main Job ads list reloads');
  assert.match(f.el('Message').textContent,/^Added 3 ads to Clients/);
  assert.match(found(f)[2].text,/Already in Job ads/);assert.equal(box(found(f)[0]).checked,false,'the unticked ad stays available');
  // Adding waits for a busy Job Leads, with a message.
  box(found(f)[0]).checked=true;await box(found(f)[0]).dispatch('change');f.state.busy=true;
  await f.el('Add').click();await settle();assert.match(f.el('Message').textContent,/Job Leads is busy/);assert.equal(f.leadsCalls.length,3);f.state.busy=false;

  // Selecting is per page, and Add saves up to 100 at a time.
  {const big=fixture({signed:[2],followed:[client(11,'4242','Example Client')],pages:{'4242':[bulk(3000,40),bulk(3040,40),bulk(3080,40),bulk(3120,30)]}});
   await big.el('Tab').click();await settle();big.el('Pages').value='5';await big.el('Pull').click();await settle(200);
   assert.equal(big.el('FoundCount').textContent,'150');
   big.el('SelectNew').checked=true;await big.el('SelectNew').dispatch('change');
   await big.el('FoundNext').click();assert.equal(found(big).filter(row=>box(row).checked).length,0,'selecting one page leaves the next page unticked');
   for(let page=1;page<3;page++){big.el('SelectNew').checked=true;await big.el('SelectNew').dispatch('change');assert.equal(found(big).filter(row=>box(row).checked).length,50,'one page at a time');if(page<2)await big.el('FoundNext').click();}
   await big.el('Add').click();await settle(200);
   assert.equal(big.leadsCalls.length,100);assert.match(big.el('Message').textContent,/50 selected ads are still waiting: click Add selected again/);
   await big.el('Add').click();await settle(200);
   assert.equal(big.leadsCalls.length,150);assert.doesNotMatch(big.el('Message').textContent,/still waiting/);}

  // The review list cap: no more searches once 600 ads wait, and no "pulled" mark.
  {// Five clients of 5 pages x 35 ads: the fourth fills the list part-way.
   const followed=[client(21,'21'),client(22,'22'),client(23,'23'),client(24,'24'),client(25,'25')];
   const pages=id=>Array.from({length:5},(_,p)=>bulk(id*10000+p*35,35));
   const cap=fixture({signed:[2],followed,pages:{'21':pages(21),'22':pages(22),'23':pages(23),'24':pages(24),'25':pages(25)}});
   await cap.el('Tab').click();await settle();cap.el('Pages').value='5';await cap.el('Pull').click();await settle(400);
   assert.equal(cap.el('FoundCount').textContent,'600');
   assert.deepEqual(cap.rpcCalls.filter(c=>c.action==='jobSearchBegin').map(c=>c.args.company_id),['21','22','23','24'],'no search opens once the list is full');
   assert.equal(cap.rpcCalls.filter(c=>c.args?.method==='nextJobSearch').length,14,'paging stops as soon as the list is full');
   assert.deepEqual(cap.calls.filter(c=>c.action==='pulled').map(c=>c.company_id),[21,22,23],'a client cut short is not marked as pulled');
   assert.match(cap.el('Progress').textContent,/review list is full \(600 ads\): 2 clients were not fully pulled/);
   assert(allEnded(cap));
   const searches=cap.rpcCalls.length;await cap.el('Pull').click();await settle();
   assert.equal(cap.rpcCalls.length,searches);assert.match(cap.el('Progress').textContent,/review list is full/);}

  // Ticks: at most 15, remembered, and Untick all.
  {const many=Array.from({length:16},(_,n)=>client(100+n,String(500+n)));
   const t=fixture({signed:[2],followed:many});
   await t.el('Tab').click();await settle();
   assert.equal(t.el('Ticked').textContent,'15 of 15 ticked','only 15 are ticked by default');
   const last=box(rows(t)[15]);assert(!last.checked);last.checked=true;await last.dispatch('change');
   assert(!last.checked);assert.match(t.el('Progress').textContent,/Tick up to 15/);
   const first=box(rows(t)[0]);first.checked=false;await first.dispatch('change');
   const again=fixture({signed:[2],followed:many,storage:t.storage});await again.el('Tab').click();await settle();
   assert.equal(again.el('Ticked').textContent,'14 of 15 ticked','ticks are remembered');assert(!box(rows(again)[0]).checked);
   await again.el('Untick').click();await settle();assert.equal(again.el('Ticked').textContent,'0 of 15 ticked');assert(again.el('Pull').disabled);}

  // A status JobAdder no longer lists can be dropped.
  {const s=fixture({signed:[2,9]});await s.el('Tab').click();await settle();
   assert(s.el('Setup').open);assert.match(s.el('Message').textContent,/no longer in JobAdder/);assert.match(s.el('SetupSummary').textContent,/1 no longer in JobAdder/);
   assert(!s.el('StatusesSave').disabled,'saving the remaining statuses is possible');
   await s.el('StatusesSave').click();await settle();assert.deepEqual(s.calls.at(-1),{action:'set_statuses',status_ids:[2],account:ACCOUNT});}

  // Stop during a pull: the run ends at once and the summary counts what was found.
  {const s=fixture({signed:[2],followed:[client(11,'4242','Example Client')],pages:{'4242':[[job(1001),job(1002)],[job(1003)]]}});
   await s.el('Tab').click();await settle();
   s.el('Pages').value='2';s.state.holdPage=1;const running=s.el('Pull').click();await settle();
   assert(s.state.release,'the second page read is in progress');assert(!s.el('Stop').disabled);
   await s.el('Stop').click();assert(s.ended.length>=1,'Stop ends the companion run straight away');
   s.state.release();await running;await settle();
   assert.match(s.el('Progress').textContent,/^Stopped\. 0 clients pulled, 2 ads found, 2 new to review/);assert.equal(found(s).length,2);
   assert.equal(s.calls.filter(c=>c.action==='pulled').length,0,'a stopped client is not marked as pulled');
   assert.deepEqual(s.state.locks,[true,false]);assert(allEnded(s));}

  // An account change while the search is opening still ends that run.
  {const a=fixture({signed:[2],followed:[client(11,'4242','Example Client')],holdBegin:true});
   await a.el('Tab').click();await settle();
   const pending=a.el('Pull').click();await settle();
   assert.equal(a.begun.length,1);
   a.window._jaAccountCacheNamespace='ja'+OTHER;a.clear();
   a.state.releaseBegin();await pending;await settle();
   assert(allEnded(a),'the run that was opening is ended once it starts');
   assert.equal(a.el('Count').textContent,'0');assert.equal(a.el('Found').children.length,0);
   assert.equal(a.state.locks.at(-1),false,'Job Leads is unlocked');assert.equal(a.calls.filter(c=>c.action==='pulled').length,0);}

  // A reply for another account refreshes this page's account and reloads once.
  {const r=fixture({signed:[2],followed:[client(11,'4242','Example Client')]});
   r.state.account=OTHER;r.state.apiInfo={connected:true,account_cache_namespace:OTHER};
   await r.el('Tab').click();await settle(80);
   assert.equal(r.state.applied,1,'the page account is re-read');assert.equal(r.window._jaAccountCacheNamespace,'ja'+OTHER);
   assert.equal(r.el('Count').textContent,'1','the current account loads');assert.doesNotMatch(r.el('Message').textContent,/account changed/);
   // If the account still does not match after re-reading, the owner is told to reconnect.
   const stuck=fixture({signed:[2]});stuck.state.account=OTHER;stuck.state.apiInfo={connected:true,account_cache_namespace:ACCOUNT};
   await stuck.el('Tab').click();await settle(80);
   assert.match(stuck.el('Message').textContent,/Reconnect JobAdder in Settings/);assert.equal(stuck.el('Count').textContent,'0');}

  // Saved-ad counts are worked out once per data change, not on every redraw.
  {const followed=Array.from({length:200},(_,n)=>client(1000+n,String(n+1),'Client Number '+n+' Holdings'));
   const records=Array.from({length:5000},(_,n)=>({id:String(n).padStart(32,'0'),url:'https://www.linkedin.com/jobs/view/'+(800000+n),company:'Company '+(n%300)+' Holdings',role:'R',deleted:false}));
   const p=fixture({signed:[2],followed,records});
   const started=Date.now();await p.el('Tab').click();await settle();
   for(let n=0;n<30;n++){p.el('FoundNext').disabled=false;await p.el('FoundPrevious').click();}
   assert(Date.now()-started<8000,'redraws stay fast at the documented limits ('+(Date.now()-started)+' ms)');}

  // Account change on screen, and a JobAdder outage.
  const down=fixture({down:true});await down.el('Tab').click();await settle();
  assert.match(down.el('Message').textContent,/could not be reached/);assert(down.el('Pull').disabled);
  finished=true;
  console.log('Signed clients view: status choice and stale statuses, follow, LinkedIn links, ticks, company-filtered pulls, review cap, per-page select and batched add, busy Job Leads, Stop, account changes and redraw cost passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
