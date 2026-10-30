/* Signed clients view in Job Leads. Fictional clients, accounts and ads; the
 * JobAdder, Job Leads and companion replies are all simulated in memory. */
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
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

function fixture(options={}){
  const ids=new Map(),calls=[],leadsCalls=[],rpcCalls=[],windowEvents={};
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
    folders:['Clients'],busy:false,locks:[],refreshes:0,companion:{connected:true,concurrent_scans_revision:1,job_search:true,job_search_revision:1,job_search_company_revision:1,busy:false},
    pages:{'4242':[[job(1001),job(900),job(1002)],[job(1003)]],'5151':[[job(1002,'Second Client'),job(2001,'Second Client'),{url:'https://evil.test/jobs/view/1',company:'X',role:'Bad'}]]},hold:null,...options};
  const reply=data=>({ok:true,json:async()=>({ok:true,...data})});
  const fail=(status,error)=>({ok:false,status,json:async()=>({ok:false,error})});
  const fetch=async(url,init={})=>{
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
  const runs=new Map();let tab=40;
  const app={
    lock:value=>{state.locks.push(value);state.busy=value;},isBusy:()=>state.busy,refresh:async()=>{state.refreshes++;},activityStart:()=>'activity',activityEnd:()=>{},
    rpc:async(action,args={})=>{
      rpcCalls.push({action,args:structuredClone(args)});
      if(action==='jobStatus')return state.companion;
      if(action==='jobSearchBegin'){assert.equal(args.use_open,false);assert.equal(args.query,'');runs.set(args.run_id,{company:args.company_id,page:0,tab:++tab});return {tab_id:tab};}
      if(action==='end'){runs.delete(args.run_id);return true;}
      const run=runs.get(args.run_id);assert(run,'reads belong to a live run');
      if(args.method==='scrollJobSearch')return false;
      if(args.method==='nextJobSearch'){run.page++;return true;}
      if(state.hold){await new Promise(resolve=>{state.release=resolve;});}
      const jobs=(state.pages[run.company]||[])[run.page]||[];
      return {jobs,signature:run.page+':'+jobs.map(row=>row.url).join('|'),hasNext:run.page+1<(state.pages[run.company]||[]).length,atBottom:true,empty:!jobs.length};
    }};
  const window={cvStudioJobLeads:app,cvStudioPeople:{hideHR:()=>{state.hrHidden=true;}},_jaAccountCacheNamespace:'ja'+ACCOUNT,addEventListener:(name,fn)=>{windowEvents[name]=fn;}};
  let serial=0;
  const context=vm.createContext({window,document,fetch,console,structuredClone,Promise,Set,Map,Array,Number,String,Math,Error,JSON,
    crypto:{randomUUID:()=>'00000000-0000-4000-8000-'+String(++serial).padStart(12,'0')},setTimeout:(fn,ms)=>setTimeout(fn,ms===350?0:ms)});
  vm.runInContext(source,context);
  return {el,state,calls,leadsCalls,rpcCalls,window,document,api:window.cvStudioJobLeadsClients,clear:()=>window.clearJobLeadsClientsAccountState(),pagehide:()=>windowEvents.pagehide?.()};
}
const rows=f=>f.el('Followed').children;
const found=f=>f.el('Found').children;
const box=row=>row.querySelectorAll('input')[0];

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
   assert.equal(api.linkedinId({linkedin_url:'javascript:alert(1)',linkedin_id:'x'},[{hr:{company_url:'javascript:alert(1)',company_id:'1'}}]),'');}

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

  // A pasted named page links to an HR-scanned company id; a "See all jobs" link gives the id directly.
  const editor=rows(f)[1].querySelectorAll('input')[1];editor.value='https://www.linkedin.com/company/second-client/';
  await rows(f)[1].querySelectorAll('button')[0].click();await settle();
  assert.equal(f.calls.at(-1).action,'set_linkedin');assert.equal(f.calls.at(-1).account,ACCOUNT);
  assert(!box(rows(f)[1]).disabled && box(rows(f)[1]).checked,'the company id from a saved HR scan makes it pullable');
  assert.match(rows(f)[1].text,/saved HR scan/);

  // An outdated companion is reported before any search opens.
  f.state.companion={...f.state.companion,job_search_company_revision:undefined};
  await f.el('Pull').click();await settle();
  assert.match(f.el('Progress').textContent,/latest companion update/);assert(!f.rpcCalls.some(c=>c.action==='jobSearchBegin'));
  assert.deepEqual(f.state.locks,[true,false],'Job Leads is unlocked after a refused pull');
  f.state.companion={...f.state.companion,job_search_company_revision:1,connected:false};
  await f.el('Pull').click();await settle();assert.match(f.el('Progress').textContent,/companion enabled/);
  f.state.companion={...f.state.companion,connected:true};

  // Pull both clients: company-filtered searches, client tags, de-duplication.
  f.el('Pages').value='2';f.state.locks=[];
  await f.el('Pull').click();await settle(120);
  const begins=f.rpcCalls.filter(c=>c.action==='jobSearchBegin');
  assert.deepEqual(begins.map(c=>c.args.company_id),['4242','5151']);assert(begins.every(c=>c.args.max_pages===2 && c.args.location===''));
  assert.equal(f.rpcCalls.filter(c=>c.action==='end').length,2,'every companion run is ended');
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
  assert.match(f.el('Message').textContent,/Added 3 ads to Clients/);
  assert.match(found(f)[2].text,/Already in Job ads/);assert.equal(box(found(f)[0]).checked,false,'the unticked ad stays available');

  // Job Leads busy: the view still reads, but pulling and adding wait.
  f.state.busy=true;
  await f.el('Refresh').click();await settle();
  assert.equal(f.calls.at(-1).action,'statuses','refresh works while Job Leads is busy');
  assert(f.el('Pull').disabled);const pulls=f.rpcCalls.length;await f.el('Pull').click();await settle();assert.equal(f.rpcCalls.length,pulls);
  f.state.busy=false;

  // Stop during a pull keeps the ads found so far and ends the run.
  const s=fixture({signed:[2],followed:[{company_id:11,name:'Example Client',linkedin_url:'',linkedin_id:'4242',followed_at:'2026-10-30T00:00:00+00:00',pulled_at:'',jobadder_url:'https://app.jobadder.com/companies/11'}],hold:true});
  await s.el('Tab').click();await settle();
  s.el('Pages').value='2';const running=s.el('Pull').click();await settle();
  assert(s.state.release,'the first read is in progress');assert(!s.el('Stop').disabled);
  await s.el('Stop').click();s.state.hold=false;s.state.release();await running;await settle();
  assert.match(s.el('Progress').textContent,/^Stopped\./);assert.equal(s.rpcCalls.filter(c=>c.action==='end').length,1);
  assert.equal(s.calls.filter(c=>c.action==='pulled').length,0,'a stopped client is not marked as pulled');
  assert.deepEqual(s.state.locks,[true,false]);

  // A JobAdder account change discards everything and releases Job Leads.
  const a=fixture({signed:[2],followed:[{company_id:11,name:'Example Client',linkedin_url:'',linkedin_id:'4242',followed_at:'2026-10-30T00:00:00+00:00',pulled_at:'',jobadder_url:'https://app.jobadder.com/companies/11'}],hold:true});
  await a.el('Tab').click();await settle();
  const pending=a.el('Pull').click();await settle();
  a.window._jaAccountCacheNamespace='ja'+OTHER;a.clear();
  a.state.hold=false;a.state.release();await pending;await settle();
  assert.equal(a.el('Count').textContent,'0');assert.equal(a.el('Followed').children.length,0);assert.equal(a.el('Found').children.length,0);
  assert.equal(a.state.locks.at(-1),false,'Job Leads is unlocked');assert.equal(a.calls.filter(c=>c.action==='pulled').length,0);
  // A reply for the previous account is not shown.
  a.state.account=ACCOUNT;await a.el('Refresh').click();await settle();
  assert.equal(a.el('Followed').children.length,0);assert.match(a.el('Message').textContent,/account changed/);
  a.state.account=OTHER;a.state.followed=[];await a.el('Refresh').click();await settle();
  assert.equal(a.el('Message').textContent,'','the new account loads normally');

  // Too many clients at once, and a JobAdder outage.
  const many=fixture({signed:[2],followed:Array.from({length:16},(_,n)=>({company_id:100+n,name:'Client '+n,linkedin_url:'',linkedin_id:String(500+n),followed_at:'2026-10-30T00:00:00+00:00',pulled_at:'',jobadder_url:'https://app.jobadder.com/companies/'+(100+n)}))});
  await many.el('Tab').click();await settle();await many.el('Pull').click();await settle();
  assert.match(many.el('Progress').textContent,/up to 15 clients/);assert.equal(many.rpcCalls.length,0);
  const down=fixture({down:true});await down.el('Tab').click();await settle();
  assert.match(down.el('Message').textContent,/could not be reached/);assert(down.el('Pull').disabled);
  finished=true;
  console.log('Signed clients view: status choice, follow, LinkedIn links, company-filtered pulls, review/add, busy Job Leads, Stop, account change and limits passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
