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
    folders:['Clients'],busy:false,locks:[],refreshes:0,apiInfo:null,companion:{connected:true,concurrent_scans_revision:1,job_search:true,job_search_revision:1,job_search_company_revision:1,job_search_company_link_revision:1,busy:false},
    pages:{'4242':[[job(1001),job(900),job(1002)],[job(1003)]],'5151':[[job(1002,'Second Client'),job(2001,'Second Client'),{url:'https://evil.test/jobs/view/1',company:'X',role:'Bad'}]]},hold:null,holdBegin:null,...options};
  const deadlines=new Map();let timerId=100000;
  const reply=data=>({ok:true,json:async()=>({ok:true,...data})});
  const fail=(status,error)=>({ok:false,status,json:async()=>({ok:false,error})});
  const fetch=async(url,init={})=>{
    if(url==='/jobadder/api_info')return {ok:true,json:async()=>state.apiInfo || {connected:true,account_cache_namespace:state.account}};
    if(url==='/job-leads'){
      if(!init.body)state.recordGets=(state.recordGets||0)+1;
      if(!init.body && state.holdRecords)return new Promise(resolve=>state.recordsReply=resolve);
      if(!init.body)return reply({records:structuredClone(state.records),folders:[...state.folders]});
      const body=JSON.parse(init.body);
      // An update of an existing saved ad (posted-date backfill) is kept apart from new saves.
      if(body.action==='save' && body.record.id){const record=state.records.find(row=>row.id===body.record.id);(state.updates ||= []).push(body.record);Object.assign(record,body.record);return reply({record,duplicate:false});}
      leadsCalls.push(body);
      // Folder and Trash actions on saved ads, as the Job Leads store applies them.
      const find=identity=>state.records.find(record=>record.id===identity.id);
      if(body.action==='move_folder'){for(const item of body.records)find(item).folder=body.folder;if(body.folder && !state.folders.includes(body.folder))state.folders.push(body.folder);return reply({});}
      if(body.action==='trash'){for(const item of body.records)find(item).deleted=true;return reply({});}
      if(body.action==='create_folder'){const name=String(body.folder||'').trim();if(!name)return fail(400,'Enter a folder name.');state.folders.push(name);return reply({folder:name});}
      if(body.action==='delete_folder'){for(const item of body.records)find(item).folder='';state.folders=state.folders.filter(name=>name!==body.folder);return reply({});}
      assert.equal(body.action,'save');
      if(state.holdSave)await new Promise(resolve=>{state.releaseSave=resolve;});
      const duplicate=state.records.find(row=>row.url===body.record.url);
      if(duplicate)return reply({record:duplicate,duplicate:true});
      const record={...body.record,id:String(state.records.length+1).padStart(32,'0'),deleted:false};state.records.push(record);return reply({record,duplicate:false});
    }
    assert.equal(url,'/jobadder/clients','no other route is used');assert.equal(init.method,'POST');
    const body=JSON.parse(init.body);calls.push(body);
    if(body.action==='overview' && state.holdOverview)return new Promise(resolve=>state.overviewReply=resolve);
    if(state.down)return fail(503,'JobAdder could not be reached to refresh the sign-in. Check the internet connection.');
    if(!['overview','statuses','companies'].includes(body.action) && body.account!==state.account)return fail(409,'The JobAdder account changed.');
    const followed=()=>structuredClone(state.followed);
    if(body.action==='overview')return reply({account:state.account,signed:[...state.signed],followed:followed()});
    if(body.action==='statuses'&&state.statusesDown)return fail(502,'JobAdder could not list companies (HTTP 500). Try again later.');
    if(body.action==='statuses')return reply({account:state.account,statuses:structuredClone(state.statuses),signed:[...state.signed]});
    if(body.action==='set_statuses'){state.signed=[...body.status_ids];return reply({account:state.account,signed:[...state.signed]});}
    if(body.action==='companies'&&state.companiesDown)return fail(502,state.companiesDown===true?'JobAdder could not list companies (HTTP 500). Try again later.':state.companiesDown);
    if(body.action==='companies'&&state.companyReply)return reply({account:state.account,...state.companyReply});
    if(body.action==='companies')return reply({account:state.account,companies:state.companies.map(row=>({...row,followed:state.followed.some(f=>f.company_id===row.company_id)})),offset:0,total:2,next_offset:null});
    if(body.action==='follow'){const company=state.companies.find(row=>row.company_id===body.company_id);state.followed.push({company_id:company.company_id,name:company.name,...state.details[company.company_id],followed_at:'2026-10-30T00:00:00+00:00',pulled_at:'',jobadder_url:company.jobadder_url});return reply({account:state.account,followed:followed()});}
    if(body.action==='unfollow'){state.followed=state.followed.filter(row=>row.company_id!==body.company_id);return reply({account:state.account,followed:followed()});}
    if(body.action==='refresh_linkedin'){
      if(state.holdRefresh)await new Promise(resolve=>state.releaseRefresh=resolve);
      if(state.failRefresh===body.company_id)return fail(502,'Fictional company read failed.');
      const row=state.followed.find(f=>f.company_id===body.company_id);if(!row)return fail(404,'Follow this client first.');
      assert.equal(body.expected_url,row.linkedin_url);assert.equal(body.expected_id,row.linkedin_id);
      const change=state.details[row.company_id];if(change?.linkedin_url || change?.linkedin_id)Object.assign(row,change);return reply({account:state.account,followed:followed()});
    }
    if(body.action==='set_linkedin'){const row=state.followed.find(f=>f.company_id===body.company_id);const id=/f_C=(\d+)/.exec(body.link)?.[1];const page=/\/company\/([\w-]+)\//.exec(body.link)?.[1];if(id)row.linkedin_id=id;if(page){row.linkedin_url='https://www.linkedin.com/company/'+page+'/';row.linkedin_id=/^\d+$/.test(page)?page:'';}return reply({account:state.account,followed:followed()});}
    if(body.action==='pulled'){state.followed.find(f=>f.company_id===body.company_id).pulled_at='2026-10-30T09:00:00+00:00';return reply({account:state.account,followed:followed()});}
    throw Error('unexpected action '+body.action);
  };
  const runs=new Map(),begun=[],ended=[];let tab=40;
  const app={
    statusLabels:{new:'New',to_contact:'To contact',contacted:'Contacted',follow_up:'Following up',won:'Won',closed:'Closed'},
    lock:value=>{state.locks.push(value);state.busy=value;},isBusy:()=>state.busy,
    showClientAds:id=>{state.shown=id===undefined?'!any':id;},redraw:()=>{state.redraws=(state.redraws||0)+1;},
    stopHR:()=>{state.stoppedHR=(state.stoppedHR||0)+1;},hrRunning:()=>false,refresh:async()=>{state.refreshes++;},activityStart:()=>'activity',activityEnd:()=>{},
    rpc:async(action,args={})=>{
      rpcCalls.push({action,args:structuredClone(args)});
      if(action==='jobStatus')return state.companion;
      if(action==='jobCompanyID'){
        if(state.holdCompany)await new Promise(resolve=>state.releaseCompany=resolve);
        if(state.failCompany)throw Error('Company could not be read.');
        const planned=state.companyErrors?.[args.company_url];
        if(planned){const error=Error(planned.message);if(planned.code)error.companionCode=planned.code;throw error;}
        return {company_url:args.company_url,company_id:state.companyIds?.[args.company_url] || '4242'};
      }
      if(action==='jobReadCancel')return true;
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
  const opened=[];
  const window={cvStudioJobLeads:app,cvStudioPeople:{hideHR:()=>{state.hrHidden=true;},showHR:async id=>{state.shownHR=id;}},confirm:()=>state.confirm!==false,_jaAccountCacheNamespace:'ja'+ACCOUNT,addEventListener:(name,fn)=>{windowEvents[name]=fn;},
    open:(url,name,features)=>{opened.push({url,name,features});return null;}};
  window.applyJAPublicInfo=info=>{const next=info?.connected?'ja'+info.account_cache_namespace:'';const before=window._jaAccountCacheNamespace;window._jaAccountCacheNamespace=next;state.applied=(state.applied||0)+1;if(before && before!==next)window.clearJobLeadsClientsAccountState();};
  const localStorage={getItem:key=>storage.has(key)?storage.get(key):null,setItem:(key,value)=>storage.set(key,String(value))};
  let serial=0;
  const context=vm.createContext({window,document,fetch,console,structuredClone,Promise,Set,Map,Array,Number,String,Math,Error,JSON,localStorage,URL,AbortController,
    crypto:{randomUUID:()=>'00000000-0000-4000-8000-'+String(++serial).padStart(12,'0')},setTimeout:(fn,ms)=>{if(state.manualDeadlines && ms>=10000){const id=++timerId;deadlines.set(id,{fn,ms});return id;}return setTimeout(fn,ms===350?0:ms)},clearTimeout:id=>{deadlines.delete(id);clearTimeout(id)}});
  vm.runInContext(walkSource,context);vm.runInContext(source,context);
  return {el,state,calls,deadlines,leadsCalls,rpcCalls,begun,ended,storage,window,document,opened,api:window.cvStudioJobLeadsClients,clear:()=>window.clearJobLeadsClientsAccountState(),pagehide:()=>windowEvents.pagehide?.(),focus:()=>windowEvents.focus?.()};
}
const rows=f=>f.el('Followed').children;
const found=f=>f.el('Found').children;
const box=row=>row.querySelectorAll('input')[0];
const allEnded=f=>f.begun.every(run=>f.ended.includes(run));

let finished=false;
// A scenario that never settles must fail, not end silently with exit code 0.
process.on('exit',()=>{if(!finished && !process.exitCode){console.error('Signed clients test did not finish: a pending step never settled.');process.exitCode=1;}});
(async()=>{
  // Saved-ad hydration must not hide a ready account/status reply.
  {const f=fixture({signed:[2],followed:[client(11,'4242')],holdRecords:true,manualDeadlines:true});
   const loading=f.el('Tab').click();await settle();
   assert(f.calls.some(call=>call.action==='statuses'),'company statuses load independently of saved ads');
   assert.equal(f.el('Statuses').querySelectorAll('input').length,2);
   assert.equal(f.el('Count').textContent,'1','followed clients display before saved-ad hydration finishes');
   const deadline=[...f.deadlines.values()].find(timer=>timer.ms===15000);assert(deadline);deadline.fn();await loading;await settle();
   assert(!f.el('Refresh').disabled);assert.match(f.el('Message').textContent,/saved ads.*could not|Saved ads.*could not/i);assert(f.el('Pull').disabled,'unknown saved ads must not authorize a pull');
   assert.equal(rows(f).length,1,'a failed ads read does not discard followed clients');
   f.state.recordsReply({ok:true,json:async()=>({records:[],folders:[]})});await settle();
   assert.equal(rows(f).length,1,'late completion does not re-enter the load workflow');}
  {const f=fixture({holdOverview:true,manualDeadlines:true});const loading=f.el('Tab').click();await settle();
   const deadline=[...f.deadlines.values()].find(timer=>timer.ms===60000);assert(deadline);deadline.fn();await loading;await settle();
   assert(!f.el('Refresh').disabled,'failed startup leaves an explicit recovery action');
   assert.match(f.el('Message').textContent,/did not finish|timed out/);const calls=f.calls.length;
   f.state.overviewReply({ok:true,json:async()=>({account:ACCOUNT,signed:[2],followed:[client(11,'4242')]})});await settle();
   assert.equal(f.calls.length,calls,'late response never starts statuses or another request');assert.equal(rows(f).length,0);
   f.state.holdOverview=false;await f.el('Refresh').click();await settle();
   assert.equal(f.el('Statuses').querySelectorAll('input').length,2,'Refresh recovers the initial account read');}
  // Refresh metadata independently of the local overview; named links can
  // be selected, while missing links remain disabled. No implicit follow.
  {const f=fixture({signed:[2],followed:[client(11,''),client(12,'5151')]});
   await f.el('Tab').click();await settle();assert(box(rows(f)[0]).disabled);
   const before=box(rows(f)[1]).checked;
   f.state.details[11]={linkedin_url:'https://www.linkedin.com/company/fictional-client/',linkedin_id:''};
   await f.el('FollowedRefresh').click();await settle();
   assert(!box(rows(f)[0]).disabled,'JobAdder-added named link makes Pull selectable');assert.equal(box(rows(f)[1]).checked,before,'existing ticks survive');
   assert.equal(f.calls.filter(c=>c.action==='refresh_linkedin').length,2);assert(!f.calls.some(c=>c.action==='follow'));
   assert.match(f.el('Progress').textContent,/2 of 2 clients refreshed/);
   box(rows(f)[0]).checked=true;await box(rows(f)[0]).dispatch('change');await f.el('Pull').click();await settle();
   const lookup=f.rpcCalls.findIndex(c=>c.action==='jobCompanyID'),begin=f.rpcCalls.findIndex(c=>c.action==='jobSearchBegin');
   assert(lookup>=0 && begin>lookup);assert.equal(f.rpcCalls[begin].args.company_id,'4242');assert.equal(f.state.locks.at(-1),false);}
  {const f=fixture({signed:[2],followed:[client(11,''),client(12,'5151')],holdRefresh:true});
   await f.el('Tab').click();await settle();const queue=f.el('FollowedRefresh').click();await settle();
   assert(f.state.releaseRefresh);assert(!f.el('Stop').disabled);await f.el('Stop').click();f.state.releaseRefresh();await queue;
   assert.equal(f.calls.filter(c=>c.action==='refresh_linkedin').length,1,'Stop prevents the next metadata request');assert.match(f.el('Progress').textContent,/Stopped/);}
  {const f=fixture({signed:[2],followed:[client(11,''),client(12,'5151')],failRefresh:11});
   await f.el('Tab').click();await settle();await f.el('FollowedRefresh').click();
   assert.match(f.el('Progress').textContent,/1 could not be refreshed/);assert.equal(rows(f).length,2);assert.equal(f.calls.filter(c=>c.action==='refresh_linkedin').length,2,'a failed refresh does not block the next client');}
  for(const mode of ['stop','account','failed','old']){
   const row={...client(11,''),linkedin_url:'https://www.linkedin.com/company/fictional-client/'};
   const f=fixture({signed:[2],followed:[row],holdCompany:mode==='stop'||mode==='account',failCompany:mode==='failed'});
   await f.el('Tab').click();await settle();if(mode==='old')delete f.state.companion.job_search_company_link_revision;
   const pulling=f.el('Pull').click();await settle();
   if(mode==='stop'){await f.el('Stop').click();assert(f.rpcCalls.some(c=>c.action==='jobReadCancel'));f.state.releaseCompany();}
   if(mode==='account'){f.clear();f.state.releaseCompany();}
   await pulling;assert(!f.rpcCalls.some(c=>c.action==='jobSearchBegin'),'no search after '+mode+' lookup');
   if(mode==='old')assert.match(f.el('Progress').textContent,/latest companion update/);
  }
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
  assert.match(f.el('Message').textContent,/^Choose the statuses that mean a signed client, then click Save statuses\.$/);
  assert(f.el('Search').disabled && f.el('Pull').disabled);

  // Choose the signed status, then find and follow clients.
  const statusBoxes=f.el('Statuses').querySelectorAll('input');assert.equal(statusBoxes.length,2);
  statusBoxes[1].checked=true;await statusBoxes[1].dispatch('change');assert(!f.el('StatusesSave').disabled);
  await f.el('StatusesSave').click();await settle();
  // Saving lists the signed clients at once; no extra Search click is needed.
  assert.deepEqual(f.calls.slice(-2),[{action:'set_statuses',status_ids:[2],account:ACCOUNT},{action:'companies',query:'',offset:0}]);
  assert.match(f.el('SetupSummary').textContent,/Signed Client/);assert(f.el('Browse').open);
  assert.equal(f.el('Companies').children.length,2);assert.match(f.el('Message').textContent,/2 signed clients found/);
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
  assert(rows(f)[1].querySelectorAll('input')[1].getAttribute('data-guide')==='true','Follow reveals the link needed to enable selection');
  assert.match(rows(f)[1].text,/Add its LinkedIn page/);
  assert.match(rows(f)[0].text,/Ready/);
  assert.equal(rows(f)[0].children[3].text,'2','saved ads are counted by company name, ignoring PT/Tbk');
  await rows(f)[0].children[3].children[0].click();assert.equal(f.state.shown,11,'the count opens Job ads filtered to that client');
  await f.el('AdsOpen').click();assert.equal(f.state.shown,'!any','View in Job ads shows every client ad');

  // A pasted named page links to an HR-scanned company id.
  const editor=rows(f)[1].querySelectorAll('input')[1];editor.value='https://www.linkedin.com/company/second-client/';
  await rows(f)[1].querySelectorAll('button')[0].click();await settle();
  assert.equal(f.calls.at(-1).action,'set_linkedin');assert.equal(f.calls.at(-1).account,ACCOUNT);
  assert(!box(rows(f)[1]).disabled && box(rows(f)[1]).checked,'the company id from a saved HR scan makes it pullable');
  assert.match(rows(f)[1].text,/Ready/);
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
  const reads=f.calls.length;await f.el('Refresh').click();await settle();
  assert.deepEqual(f.calls.slice(reads).map(c=>c.action),['overview','statuses','companies'],'one Refresh re-reads statuses and the listed clients, even while Job Leads is busy');
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
  assert.deepEqual(Object.keys(f.leadsCalls[0].record).sort(),['client','company','contact','date_posted','date_posted_estimate','description','description_rich','description_truncated','folder','follow_up','location','notes','role','status','url'].sort());
  // Each saved ad carries the client it was pulled for, so the dashboard never guesses from names.
  assert(f.leadsCalls.every(call=>Number.isSafeInteger(call.record.client.company_id) && typeof call.record.client.name==='string' && call.record.client.name));
  assert.notEqual(f.leadsCalls[0].record.client.company_id,f.leadsCalls[2].record.client.company_id,'ads from different clients keep their own client');
  assert.equal(f.leadsCalls[0].record.folder,'Clients');assert.equal(f.leadsCalls[0].record.status,'new');assert.equal(f.leadsCalls[0].record.notes,'');
  assert.equal(f.state.refreshes,1,'the main Job ads list reloads');
  // The already-saved ad that had no posted date took the date this pull read.
  assert.deepEqual(f.state.updates.map(row=>[row.url,row.date_posted,row.date_posted_estimate]),[['https://www.linkedin.com/jobs/view/900','2026-10-20','']]);
  assert.equal(f.state.updates[0].role,'Saved role','nothing else in the saved ad changes');
  assert.match(f.el('Message').textContent,/^Saved 3 ads to Clients/);
  assert.match(found(f)[2].text,/Already in Job ads/);assert.equal(box(found(f)[0]).checked,false,'the unticked ad stays available');
  // Adding waits for a busy Job Leads, with a message.
  box(found(f)[0]).checked=true;await box(found(f)[0]).dispatch('change');f.state.busy=true;
  await f.el('Add').click();await settle();assert.match(f.el('Message').textContent,/Job Leads is busy/);assert.equal(f.leadsCalls.length,3);f.state.busy=false;

  // Selecting is per page, and Save saves every selected ad.
  {const big=fixture({signed:[2],followed:[client(11,'4242','Example Client')],pages:{'4242':[bulk(3000,40),bulk(3040,40),bulk(3080,40),bulk(3120,30)]}});
   await big.el('Tab').click();await settle();big.el('Pages').value='5';await big.el('Pull').click();await settle(200);
   assert.equal(big.el('FoundCount').textContent,'150');
   big.el('SelectNew').checked=true;await big.el('SelectNew').dispatch('change');
   await big.el('FoundNext').click();assert.equal(found(big).filter(row=>box(row).checked).length,0,'selecting one page leaves the next page unticked');
   for(let page=1;page<3;page++){big.el('SelectNew').checked=true;await big.el('SelectNew').dispatch('change');assert.equal(found(big).filter(row=>box(row).checked).length,50,'one page at a time');if(page<2)await big.el('FoundNext').click();}
   await big.el('Add').click();await settle(400);
   assert.equal(big.leadsCalls.length,150,'Save saves every selected ad in one click');assert.doesNotMatch(big.el('Message').textContent,/still waiting/);}

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
   await s.el('StatusesSave').click();await settle();assert.deepEqual(s.calls.slice(-2).map(c=>c.action),['set_statuses','companies']);
   assert.deepEqual(s.calls.at(-2),{action:'set_statuses',status_ids:[2],account:ACCOUNT});}

  // Reload statuses keeps ticks that are not saved yet.
  {const r=fixture();await r.el('Tab').click();await settle();
   const boxes=r.el('Statuses').querySelectorAll('input');boxes[1].checked=true;await boxes[1].dispatch('change');
   await r.el('Refresh').click();await settle();
   assert(r.el('Statuses').querySelectorAll('input')[1].checked,'the unsaved tick survives a reload');
   assert.match(r.el('Message').textContent,/not saved yet/);assert(!r.el('StatusesSave').disabled);
   // Searching waits for Save: the list would still use the saved statuses.
   assert(r.el('Search').disabled || !r.state.signed.length,'no search before the first save');
   await r.el('StatusesSave').click();await settle();assert.deepEqual(r.calls.at(-2),{action:'set_statuses',status_ids:[2],account:ACCOUNT});}

  // Untouched boxes follow a choice saved in another window; Save stays off.
  {const u=fixture({signed:[2]});await u.el('Tab').click();await settle();
   u.state.signed=[1,2];await u.el('Refresh').click();await settle();
   assert.deepEqual(u.el('Statuses').querySelectorAll('input').map(box=>box.checked),[true,true],'the other window\'s choice is shown');
   assert(u.el('StatusesSave').disabled,'nothing to save');assert.match(u.el('Message').textContent,/signed clients? found/,'Refresh also re-reads the listed clients');}

  // Changed but unsaved ticks hold back Search and paging until Save statuses.
  {const t=fixture({signed:[1],followed:[client(11,'4242','Example Client')]});await t.el('Tab').click();await settle();
   assert(!t.el('Search').disabled);
   const boxes=t.el('Statuses').querySelectorAll('input');boxes[1].checked=true;await boxes[1].dispatch('change');
   assert(t.el('Search').disabled && t.el('Query').disabled,'Search waits for the new ticks to be saved');
   assert.match(t.el('Message').textContent,/Click Save statuses to list clients with your new ticks/);
   boxes[1].checked=false;await boxes[1].dispatch('change');assert(!t.el('Search').disabled,'back to the saved choice');}

  // A fresh page restores the browse list even when followed clients exist.
  {const o=fixture({signed:[2]});await o.el('Tab').click();await settle();
   assert.deepEqual(o.calls.map(c=>c.action),['overview','statuses','companies']);assert(o.el('Browse').open);assert.equal(o.el('Companies').children.length,2);
   const k=fixture({signed:[2],followed:[client(11,'4242','Example Client')]});await k.el('Tab').click();await settle();
   assert.deepEqual(k.calls.map(c=>c.action),['overview','statuses','companies']);assert.equal(k.el('Companies').children.length,2);
   // Refresh reads everything again, including the page of clients already listed.
   await o.el('Refresh').click();await settle();
   assert.deepEqual(o.calls.map(c=>c.action),['overview','statuses','companies','overview','statuses','companies']);
   // A first-open list that cannot be read says so, without claiming followed clients.
   const x=fixture({signed:[2],companiesDown:true});await x.el('Tab').click();await settle();
   assert.equal(x.el('Message').textContent,'Your signed clients could not be listed. JobAdder could not list companies (HTTP 500). Try again later.');
   // A status list that cannot be read mentions followed clients only when there are some.
   const y=fixture({signed:[2],statusesDown:true});await y.el('Tab').click();await settle();
   assert.equal(y.el('Message').textContent,'JobAdder could not list companies (HTTP 500). Try again later.');
   const z=fixture({signed:[2],statusesDown:true,followed:[client(11,'4242','Example Client')]});await z.el('Tab').click();await settle();
   assert.match(z.el('Message').textContent,/Followed clients are still listed\.$/);}

  // A list JobAdder did not filter by the chosen statuses is an error, not a
  // page to click through; an empty page that has a next page says so.
  {const d=fixture({companiesDown:'JobAdder returned companies without your signed statuses, so the list could not be trusted. Try again later; nothing was changed.'});
   await d.el('Tab').click();await settle();
   const boxes=d.el('Statuses').querySelectorAll('input');boxes[1].checked=true;await boxes[1].dispatch('change');
   await d.el('StatusesSave').click();await settle();
   assert.match(d.el('Message').textContent,/^Saved\. JobAdder returned companies without your signed statuses/);
   const m=fixture({signed:[2],followed:[client(11,'4242','Example Client')],companyReply:{companies:[],offset:50,total:120,checked:50,next_offset:100}});
   await m.el('Tab').click();await settle();await m.el('Search').click();await settle();
   assert.equal(m.el('Companies').children[0].children[0].textContent,'No signed clients on this page.');
   const e=fixture({companiesDown:true});await e.el('Tab').click();await settle();
   const more=e.el('Statuses').querySelectorAll('input');more[1].checked=true;await more[1].dispatch('change');
   await e.el('StatusesSave').click();await settle();
   assert.match(e.el('Message').textContent,/^Saved\. JobAdder could not list companies/);assert.match(e.el('SetupSummary').textContent,/Signed Client/);}

  // When every saved status is gone from JobAdder, or every one is unticked,
  // the empty choice still saves; an unchanged empty choice does not.
  {const s=fixture({signed:[9]});await s.el('Tab').click();await settle();
   assert(!s.el('StatusesSave').disabled,'the removed status can be dropped without choosing another');
   await s.el('StatusesSave').click();await settle();assert.deepEqual(s.calls.at(-1),{action:'set_statuses',status_ids:[],account:ACCOUNT});
   assert.match(s.el('Message').textContent,/No status is chosen/);assert(!s.el('Browse').open);
   assert(s.el('StatusesSave').disabled,'nothing is left to save');
   const u=fixture({signed:[2]});await u.el('Tab').click();await settle();
   const boxes=u.el('Statuses').querySelectorAll('input');assert(boxes[1].checked);assert(u.el('StatusesSave').disabled);
   boxes[1].checked=false;await boxes[1].dispatch('change');assert(!u.el('StatusesSave').disabled,'unticking every status can be saved');
   await u.el('StatusesSave').click();await settle();assert.deepEqual(u.calls.at(-1),{action:'set_statuses',status_ids:[],account:ACCOUNT});
   assert.match(u.el('SetupSummary').textContent,/not chosen yet/);assert(u.el('Search').disabled);}

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

  // Filters intersect over the loaded page, keep their choice across page
  // reads and never query JobAdder themselves. Sort has deterministic ties
  // and places unassigned owners last in either direction.
  {const companies=[
    {company_id:41,name:'Client 10',status:'Signed Client',owner:'Beta Owner'},
    {company_id:42,name:'Client 2',status:'Signed Client',owner:'Alpha Owner'},
    {company_id:43,name:'Zeta',status:'Active Client',owner:''},
    {company_id:44,name:'alpha',status:'Active Client',owner:'Alpha Owner'}];
   const c=fixture({signed:[2],followed:[client(41,'4242','Client 10')],companyReply:{companies,offset:0,total:4,checked:4,next_offset:null}});
   const names=()=>c.el('Companies').children.flatMap(row=>row.querySelectorAll('a').map(a=>a.textContent));
   const choose=async(name,value)=>{c.el(name).value=value;await c.el(name).dispatch('change');};
   await c.el('Tab').click();await settle();const reads=c.calls.length;
   assert.deepEqual(names(),['alpha','Client 2','Client 10','Zeta']);
   await choose('Sort','name_desc');assert.deepEqual(names(),['Zeta','Client 10','Client 2','alpha']);
   await choose('Sort','owner_desc');assert.deepEqual(names(),['Client 10','alpha','Client 2','Zeta']);
   await choose('StatusFilter',JSON.stringify('Signed Client'));assert.deepEqual(names(),['Client 10','Client 2']);
   await choose('OwnerFilter',JSON.stringify('Alpha Owner'));assert.deepEqual(names(),['Client 2']);
   await choose('FollowingFilter','followed');assert.equal(names().length,0);assert.match(c.el('Companies').text,/filters on this page/);
   await c.el('FiltersReset').click();await choose('FollowingFilter','followed');assert.deepEqual(names(),['Client 10']);
   assert.match(c.el('CompaniesPage').textContent,/1 of 4 on this page/);
   await choose('FollowingFilter','unfollowed');assert.deepEqual(names(),['alpha','Client 2','Zeta']);
   await choose('OwnerFilter',JSON.stringify(''));assert.deepEqual(names(),['Zeta']);
   assert.equal(c.calls.length,reads,'filter and sort changes stay local');
   await c.el('FiltersReset').click();await choose('OwnerFilter',JSON.stringify('Beta Owner'));
   c.state.companyReply={companies:[companies[1]],offset:50,total:51,checked:1,next_offset:null};
   await c.el('Search').click();await settle();assert.equal(c.el('OwnerFilter').value,JSON.stringify('Beta Owner'));
   assert.equal(names().length,0,'an absent owner filter stays active on another loaded page');
   await c.el('FiltersReset').click();assert.deepEqual(names(),['Client 2']);
   c.clear();assert.equal(c.el('OwnerFilter').value,'');assert(!c.el('OwnerFilter').text.includes('Beta Owner'),'account reset clears owner labels');}

  // Clearing all signed statuses keeps followed choices but cannot start a
  // pull, even if an event is invoked after the control became disabled.
  {const c=fixture({signed:[2],followed:[client(11,'4242')]});await c.el('Tab').click();await settle();
   const box=c.el('Statuses').querySelectorAll('input').find(value=>value.value==='2');box.checked=false;await box.dispatch('change');
   await c.el('StatusesSave').click();await settle();assert(c.el('Pull').disabled);await c.el('Pull').click();await settle();
   assert(!c.rpcCalls.some(call=>call.action==='jobSearchBegin'));assert.match(c.el('Progress').textContent,/Save statuses/);assert.equal(rows(c).length,1);}

  // Signed clients and Followed clients are separate views of one module.
  {const v=fixture({signed:[2],followed:[client(11,'4242','Example Client')]});
   await v.el('FollowedTab').click();await settle();
   assert(!v.el('FollowedPanel').hidden && v.el('Panel').hidden,'Followed clients shows alone');
   assert.equal(v.el('FollowedTab').getAttribute('aria-pressed'),'true');assert.equal(v.el('Tab').getAttribute('aria-pressed'),'false');
   assert.equal(rows(v).length,1,'followed clients load in their own tab');
   await v.el('Tab').click();await settle();assert(!v.el('Panel').hidden && v.el('FollowedPanel').hidden);
   await v.document.getElementById('jobLeadsApolloAdsTab').click();assert(v.el('Panel').hidden && v.el('FollowedPanel').hidden,'another Job Leads view hides both');
   v.state.signed=[];await v.el('FollowedTab').click();await settle();
   assert.equal(v.el('FollowedMessage').textContent,'','no repeated hint');assert.match(v.el('FollowedSetupText').textContent,/choose which JobAdder statuses/,'the followed view says where to start');
   assert(v.el('OpenLinkedIn').disabled,'no LinkedIn search before signed statuses are chosen');}

  // Open on LinkedIn: one search for every ticked client, opened from the click.
  {const o=fixture({signed:[2],followed:[client(11,'4242','Example Client'),client(12,'5151','Second Client')]});
   await o.el('FollowedTab').click();await settle();
   assert.equal(o.api.linkedinSearch(['4242','5151','4242','bad']),'https://www.linkedin.com/jobs/search/?f_C=4242%2C5151');
   assert.equal(o.api.linkedinSearch([]),'');
   await o.el('OpenLinkedIn').click();await settle();
   assert.equal(o.opened.length,1);assert.equal(o.opened[0].url,'https://www.linkedin.com/jobs/search/?f_C=4242%2C5151');
   assert.match(o.opened[0].features,/noopener/);
   assert.equal(o.el('LinkedInLink').href,o.opened[0].url,'the same search stays available as a link');assert(!o.el('LinkedInReady').hidden);
   assert.match(o.el('Progress').textContent,/^Opened LinkedIn for 2 clients\. Add ads there with Add to CV Studio\.$/);
   assert(!o.rpcCalls.some(call=>['jobCompanyID','jobSearchBegin'].includes(call.action)),'known companies need no companion read or background search');
   const tick=box(rows(o)[1]);tick.checked=false;await tick.dispatch('change');
   assert(o.el('LinkedInReady').hidden,'changing the ticks drops the prepared search');
   await o.el('OpenLinkedIn').click();await settle();assert.equal(o.opened.at(-1).url,'https://www.linkedin.com/jobs/search/?f_C=4242');}

  // A client known only by its company page: the companion reads its number
  // once, then the search is offered as a link (the click has passed).
  {const page={...client(11,'','Example Client'),linkedin_url:'https://www.linkedin.com/company/example-client/'};
   const n=fixture({signed:[2],followed:[page],records:[]});await n.el('FollowedTab').click();await settle();
   await n.el('OpenLinkedIn').click();await settle(80);
   assert.equal(n.rpcCalls.filter(call=>call.action==='jobCompanyID').length,1);assert.equal(n.opened.length,0,'no blocked pop-up after the companion read');
   assert.equal(n.el('LinkedInLink').href,'https://www.linkedin.com/jobs/search/?f_C=4242');assert.match(n.el('Progress').textContent,/^Ready for 1 client: click Open LinkedIn search\./);
   assert.deepEqual(n.state.locks,[true,false],'Job Leads is locked only while the company is read');
   assert.match(n.el('Followed').text,/Ready/);
   await n.el('OpenLinkedIn').click();await settle();
   assert.equal(n.opened.length,1,'the number read this session opens directly next time');assert.equal(n.rpcCalls.filter(call=>call.action==='jobCompanyID').length,1);
   await n.el('Pull').click();await settle(120);
   assert.equal(n.rpcCalls.filter(call=>call.action==='jobCompanyID').length,1,'a pull reuses the number too');
   assert.equal(n.rpcCalls.find(call=>call.action==='jobSearchBegin').args.company_id,'4242');
   const failing=fixture({signed:[2],followed:[page],records:[],failCompany:true});await failing.el('FollowedTab').click();await settle();
   await failing.el('OpenLinkedIn').click();await settle(80);
   assert.match(failing.el('Progress').textContent,/No ticked client has a confirmed LinkedIn company yet\. Example Client: Company could not be read/);
   assert(failing.el('LinkedInReady').hidden);assert(failing.rpcCalls.some(call=>call.action==='jobReadCancel'));
   // A changed company page is read again, never searched with the old number.
   n.state.companyIds={'https://www.linkedin.com/company/other-client/':'6363'};
   n.state.followed[0].linkedin_url='https://www.linkedin.com/company/other-client/';await n.el('Refresh').click();await settle(40);
   const reads=n.rpcCalls.filter(call=>call.action==='jobCompanyID').length;
   await n.el('OpenLinkedIn').click();await settle(80);
   assert.equal(n.rpcCalls.filter(call=>call.action==='jobCompanyID').length,reads+1,'the new page is read');
   assert.equal(n.rpcCalls.at(-1).args.company_url,'https://www.linkedin.com/company/other-client/');
   assert.equal(n.el('LinkedInLink').href,'https://www.linkedin.com/jobs/search/?f_C=6363','the old number is not reused for another page');
   n.clear();assert.equal(n.state.linkedinSearch,undefined);assert.equal(n.el('LinkedInReady').hidden,true,'an account change drops the prepared search');}

  // Select all new ads across every page, then save them in one click.
  {const all=fixture({signed:[2],followed:[client(11,'4242','Example Client')],pages:{'4242':[bulk(5000,40),bulk(5040,40),[...bulk(5080,25),job(900)]]}});
   await all.el('FollowedTab').click();await settle();all.el('Pages').value='5';await all.el('Pull').click();await settle(200);
   assert.equal(all.el('FoundCount').textContent,'106');assert.match(all.el('Picked').textContent,/^0 of 105 new ads selected/);
   await all.el('SelectAll').click();assert.match(all.el('Picked').textContent,/^105 of 105/,'already-saved ads are never selected');
   assert(all.el('SelectAll').disabled);await all.el('SelectNone').click();assert.match(all.el('Picked').textContent,/^0 of 105/);
   await all.el('SelectAll').click();await all.el('Add').click();await settle(400);
   assert.equal(all.leadsCalls.length,105);assert.match(all.el('FollowedMessage').textContent,/^Saved 105 ads to Unfiled\.$/);
   assert.equal(all.el('AdsCount').textContent,'107','saved ads join the dashboard straight away');}

  // Saved client ads dashboard: only live ads of followed clients, with filters.
  {const day=offset=>{const d=new Date();d.setDate(d.getDate()-offset);return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');};
   const saved=(id,company,patch)=>({id:id.repeat(32).slice(0,32),url:'https://www.linkedin.com/jobs/view/'+id.charCodeAt(0),company,role:'Role '+id,location:'Kuala Lumpur',status:'new',folder:'',date_posted:'',created_at:'2026-10-01T00:00:00Z',deleted:false,...patch});
   const records=[saved('a','Example Client Sdn Bhd',{role:'Payroll Lead',date_posted:day(2),status:'contacted',folder:'Clients',created_at:'2026-10-05T00:00:00Z'}),
     saved('b','PT Example Client Tbk',{role:'Data Analyst',date_posted:day(40),hr:{company_url:'https://www.linkedin.com/company/example-client/',company_id:'4242',scanned_at:'2026-10-20T08:00:00Z'}}),
     saved('c','Second Client',{role:'Accountant',location:'Penang',date_posted:day(10)}),
     saved('d','Example Client',{role:'Deleted role',deleted:true}),saved('e','Unrelated Company',{role:'Elsewhere'})];
   const d=fixture({signed:[2],followed:[client(11,'4242','Example Client'),client(12,'5151','Second Client')],records,folders:['Clients']});
   await d.el('FollowedTab').click();await settle();
   assert.deepEqual(Array.from(d.api.clientAds(records,d.state.followed),row=>[row.record.role,row.client.name]),[['Payroll Lead','Example Client'],['Data Analyst','Example Client'],['Accountant','Second Client']]);
   assert.equal(d.el('AdsCount').textContent,'3');
   // Job ads lists these ads: clientOf gives its Client column the same owner.
   const owner=record=>{const value=d.api.clientOf(record);return value?[value.company_id,value.name]:null;};
   assert.deepEqual([owner(records[0]),owner(records[1]),owner(records[2]),owner(records[3]),owner(records[4])],
     [[11,'Example Client'],[11,'Example Client'],[12,'Second Client'],[11,'Example Client'],null],'an ad in Trash keeps its client; an unrelated ad has none');
   assert.equal(d.el('AdsCount').textContent,'3','the count still leaves out Trash');
   assert.deepEqual(owner(saved('z','Second Client Sdn Bhd',{role:'Newer in Job ads'})),[12,'Second Client'],'an ad Job ads has but this view has not read yet is matched by name');
   assert((d.state.redraws||0)>0,'Job ads redraws once followed clients are known');
   // Ads added on LinkedIn are counted when the owner returns to this tab.
   d.state.records.push(saved('f','Second Client',{role:'Added on LinkedIn',date_posted:day(1)}));d.focus();await settle();
   assert.equal(d.el('AdsCount').textContent,'4');
   await d.el('Tab').click();await settle();d.state.records.push(saved('g','Second Client'));const before=d.el('AdsCount').textContent;d.focus();await settle();
   assert.equal(d.el('AdsCount').textContent,before,'no background read while Followed clients is hidden');
   const empty=fixture({signed:[2],followed:[client(11,'4242','Example Client')],records:[]});await empty.el('FollowedTab').click();await settle();
   assert.equal(empty.el('AdsCount').textContent,'0');
   const before0=fixture({signed:[2],followed:[client(11,'4242','Example Client')]});assert.equal(before0.api.clientOf(records[0]),undefined,'unknown (not "no client") before followed clients load');
   assert.equal(before0.el('AdsCount').textContent,'—','no count before saved ads are read');}

  // Review fixes: attribution by pulled client, then the most specific name.
  {const rec=(id,company,patch={})=>({id:id.padStart(32,'0'),url:'https://www.linkedin.com/jobs/view/'+id,company,role:'Role '+id,status:'new',folder:'',date_posted:'',created_at:'2026-10-01T00:00:00Z',deleted:false,...patch});
   const records=[rec('81','ABC Logistics Sdn Bhd'),rec('82','ABC'),rec('83','Johnson Matthey',{client:{company_id:12,name:'JM Catalysts'}}),rec('84','Unrelated')];
   const followed=[client(11,'4242','ABC'),client(12,'5151','JM Catalysts'),client(13,'6363','ABC Logistics')];
   const a=fixture({signed:[2],followed,records});await a.el('FollowedTab').click();await settle();
   assert.deepEqual(Array.from(a.api.clientAds(records,followed),row=>[row.record.company,row.client.name]),
     [['ABC Logistics Sdn Bhd','ABC Logistics'],['ABC','ABC'],['Johnson Matthey','JM Catalysts']],'the most specific name wins and a pulled ad keeps its client');
   assert.deepEqual(rows(a).map(row=>row.children[3].text),['1','1','1'],'Ads in Job ads counts each ad once, for its most specific client');
   assert.equal(a.el('AdsCount').textContent,'3');}

  // A return-to-tab read never overwrites a newer read, and one return reads once.
  {const r=fixture({signed:[2],followed:[client(11,'4242','Example Client')]});await r.el('FollowedTab').click();await settle();
   const stale=structuredClone(r.state.records),before=r.state.recordGets;r.state.holdRecords=true;
   r.focus();r.focus();await settle();assert.equal(r.state.recordGets,before+1,'focus and visibility on one return read once');
   const held=r.state.recordsReply;r.state.holdRecords=false;
   r.state.records.push({id:'7'.repeat(32),url:'https://www.linkedin.com/jobs/view/7777',company:'Example Client',role:'Newer ad',status:'new',folder:'',date_posted:'',deleted:false});
   await r.el('FollowedRefresh').click();await settle();assert.equal(r.el('AdsCount').textContent,'3');
   held({ok:true,json:async()=>({ok:true,records:stale,folders:['Clients']})});await settle();
   assert.equal(r.el('AdsCount').textContent,'3','the older reply is ignored');}

  // Stop ends a long save batch between ads.
  {const st=fixture({signed:[2],followed:[client(11,'4242','Example Client')],pages:{'4242':[bulk(6000,30)]}});
   await st.el('FollowedTab').click();await settle();await st.el('Pull').click();await settle(120);
   await st.el('SelectAll').click();st.state.holdSave=true;const saving=st.el('Add').click();await settle();
   assert(!st.el('Stop').disabled,'Stop is available while saving');await st.el('Stop').click();
   st.state.holdSave=false;st.state.releaseSave();await saving;await settle(60);
   assert.equal(st.leadsCalls.length,1,'no further ad is saved after Stop');
   assert.match(st.el('FollowedMessage').textContent,/^Stopped\. Saved 1 ad.*29 selected ads are still waiting/);}

  // Every client's outcome is reported; a company with no open jobs is not a failure.
  {const page=(id,name,slug)=>({...client(id,'',name),linkedin_url:'https://www.linkedin.com/company/'+slug+'/'});
   const followed=[client(11,'4242','Example Client'),page(14,'Fictional Fingers','fictional-fingers'),page(15,'Fictional Moved','fictional-moved'),page(16,'Fictional Other','fictional-other')];
   const companyErrors={'https://www.linkedin.com/company/fictional-fingers/':{message:'LinkedIn shows no Jobs page for this company, so it has no open jobs right now.',code:'HR_COMPANY_NO_JOBS'},
     'https://www.linkedin.com/company/fictional-moved/':{message:'The saved company page changed (LinkedIn opened a different kind of page).'},
     'https://www.linkedin.com/company/fictional-other/':{message:'LinkedIn did not show this company number.'}};
   const o=fixture({signed:[2],followed,companyErrors});await o.el('FollowedTab').click();await settle();
   await o.el('Pull').click();await settle(200);
   const text=o.el('Progress').textContent;
   assert.match(text,/^Finished\. 2 clients pulled/,'a no-jobs company counts as pulled');
   assert.match(text,/No open jobs on LinkedIn: Fictional Fingers\./);
   assert.match(text,/2 could not be pulled: Fictional Moved: The saved company page changed \(LinkedIn opened a different kind of page\)\. Fictional Other: LinkedIn did not show this company number\./,'every failure is listed, not only the last');
   assert(o.calls.some(call=>call.action==='pulled' && call.company_id===14),'the no-jobs client is marked as pulled');
   await o.el('OpenLinkedIn').click();await settle(120);
   assert.equal(o.el('LinkedInLink').href,'https://www.linkedin.com/jobs/search/?f_C=4242');
   assert.match(o.el('Progress').textContent,/No open jobs on LinkedIn: Fictional Fingers\. 2 could not be included\. Fictional Moved: .* Fictional Other: /);
   const only=fixture({signed:[2],followed:[page(14,'Fictional Fingers','fictional-fingers')],companyErrors,records:[]});await only.el('FollowedTab').click();await settle();
   await only.el('OpenLinkedIn').click();await settle(80);
   assert.match(only.el('Progress').textContent,/None of the ticked clients has open jobs on LinkedIn right now\. No open jobs on LinkedIn: Fictional Fingers\./);}

  // Before any status is chosen or client followed, each view shows one next step.
  {const none=fixture({signed:[],followed:[]});await none.el('FollowedTab').click();await settle();
   assert(!none.el('FollowedSetup').hidden && none.el('FollowedBody').hidden,'no empty tables before anything is followed');
   assert.match(none.el('FollowedSetupText').textContent,/choose which JobAdder statuses/);
   await none.el('GoSigned').click();await settle();assert(!none.el('Panel').hidden,'Go to Signed clients opens that view');
   assert(none.el('Browse').hidden,'the client search waits for statuses');assert(none.el('GoFollowed').hidden);
   const later=fixture({signed:[2],followed:[]});await later.el('FollowedTab').click();await settle();
   assert.match(later.el('FollowedSetupText').textContent,/Follow your clients in Signed clients/);
   const ready=fixture({signed:[2],followed:[client(11,'4242','Example Client')]});await ready.el('Tab').click();await settle();
   assert(!ready.el('Browse').hidden && !ready.el('GoFollowed').hidden,'a followed client offers the next view');
   assert.equal(ready.el('TabCount').textContent,'1','the Followed clients tab shows its count');
   await ready.el('GoFollowed').click();await settle();assert(!ready.el('FollowedPanel').hidden && !ready.el('FollowedBody').hidden && ready.el('FollowedSetup').hidden);}

  // Account change on screen, and a JobAdder outage.
  const down=fixture({down:true});await down.el('Tab').click();await settle();
  assert.match(down.el('Message').textContent,/could not be reached/);assert(down.el('Pull').disabled);
  finished=true;
  console.log('Signed and Followed clients views: separate tabs, Open on LinkedIn, select all and save, client ads in Job ads, setup states, status choice and stale statuses, follow, LinkedIn links, ticks, company-filtered pulls, review cap, per-page select and batched add, busy Job Leads, Stop, account changes and redraw cost passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
