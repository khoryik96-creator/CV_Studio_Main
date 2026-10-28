const assert=require('assert/strict'),fs=require('fs'),path=require('path'),vm=require('vm');
const {fixture}=require('./test_linkedin_companion_lifecycle');
const {hrFixture}=require('./test_linkedin_company_hr');
const first='https://www.linkedin.com/in/sample-person';
const second='https://www.linkedin.com/in/other-person';
async function profile(){const f=fixture();await f.arm();await f.begin();await f.observe();return {f,id:(await f.create()).result};}
const read=(f,id)=>f.rpc('read',{run_id:f.run,tab_id:id,method:'readProfile',values:[first]});
async function hr(){const f=hrFixture();await f.arm();const id=(await f.beginHR()).result.tab_id;await f.readHR(id);await f.readHR(id);const join=()=>f.rpc('hrJoined',{run_id:f.run,tab_id:id,url:'https://www.linkedin.com/in/sample'});await join();return {f,id,join,profileId:f.state.session.cvstudioLinkedinLeadsSessionV1.connection.hr.joining.tab_id};}
const cases=[
 ['unrelated tab activation leaves scans alone',async()=>{const {f,id}=await profile();await f.hooks().activated({tabId:999});assert.equal((await read(f,id)).result,true);await f.end();assert(!f.tabs.has(id));}],
 ['viewed profile reads continue and next navigation uses a new background tab',async()=>{
  const {f,id}=await profile();f.tabs.get(id).active=true;await f.hooks().activated({tabId:id});
  assert.equal((await read(f,id)).result,true);
  const moved=(await f.navigate(id)).result;assert(Number.isInteger(moved.tab_id));assert.notEqual(moved.tab_id,id);
  assert.equal(f.tabs.get(id).url,first);assert.equal(f.tabs.get(moved.tab_id).url,second);assert.equal(f.tabs.get(moved.tab_id).active,false);
  assert.equal(f.state.updates.length,0);f.tabs.get(id).active=false;await f.end();assert(f.tabs.has(id));assert(!f.tabs.has(moved.tab_id));
 }],
 ['view protection and read authority survive worker suspension',async()=>{
  const {f,id}=await profile();f.tabs.get(id).active=true;await f.hooks().activated({tabId:id});f.tabs.get(id).active=false;f.boot();
  assert.equal((await read(f,id)).result,true);const moved=(await f.navigate(id)).result;assert.notEqual(moved.tab_id,id);await f.end();assert(f.tabs.has(id));
 }],
 ['activation during injection permits only unchanged read and preserves tab',async()=>{
  const {f,id}=await profile();f.state.onInject=()=>{f.tabs.get(id).active=true};assert.equal((await read(f,id)).result,true);await f.end();assert(f.tabs.has(id));
 }],
 ['actual navigation during the profile read rejects the returned evidence',async()=>{
  const {f,id}=await profile();f.state.onRead=tabId=>{f.tabs.get(tabId).url=second};assert((await read(f,id)).error);await f.end();assert(f.tabs.has(id));
 }],
 ['activation while staging navigation creates a replacement without changing the viewed page',async()=>{
  const {f,id}=await profile();f.state.onWrite=value=>{if(value.cvstudioLinkedinSessionV1?.owned.some(row=>row[0]===id&&row[1]===second))f.tabs.get(id).active=true};
  const result=await f.navigate(id);assert(!result.error);assert.notEqual(result.result.tab_id,id);assert.equal(f.tabs.get(id).url,first);assert.equal(f.state.updates.length,0);await f.end();assert(f.tabs.has(id));
 }],
 ['viewed loading profiles keep polling and End releases all read references',async()=>{
  const f=fixture();await f.arm();await f.begin();await f.observe();f.state.loadingCreate=true;const id=(await f.create()).result;
  f.tabs.get(id).active=true;await f.hooks().activated({tabId:id});f.boot();assert((await read(f,id)).result.loading);
  Object.assign(f.tabs.get(id),{url:first,status:'complete'});delete f.tabs.get(id).pendingUrl;assert.equal((await read(f,id)).result,true);await f.end();
  assert(f.tabs.has(id));assert.deepEqual(f.state.session.cvstudioLinkedinSessionV1.viewed,[]);assert.deepEqual(f.state.session.cvstudioLinkedinSessionV1.owned,[]);
 }],
 ['real navigation still blocks evidence and cleanup',async()=>{
  const {f,id}=await profile();f.tabs.get(id).active=true;await f.hooks().activated({tabId:id});f.tabs.get(id).url='https://www.linkedin.com/feed/';await f.hooks().updated(id,{url:f.tabs.get(id).url});
  const before=f.state.scripts.length;assert((await read(f,id)).error);assert.equal(f.state.scripts.length,before);await f.end();assert(f.tabs.has(id));
 }],
 ['replacement failure never changes or closes the viewed page',async()=>{
  const {f,id}=await profile();f.tabs.get(id).active=true;await f.hooks().activated({tabId:id});f.state.onCreated=()=>{f.state.failWrite=true};assert((await f.navigate(id)).error);assert.equal(f.tabs.get(id).url,first);assert.equal(f.state.updates.length,0);assert(f.tabs.has(id));
 }],
 ['corrupt persisted view protection grants no authority',async()=>{
  for(const rows of [[[999,'']],[[999,first],[999,second]],[[11,first]],[[999,'https://attacker.invalid/in/person']],Array.from({length:76},(_,i)=>[100+i,first])]){
   const {f}=await profile();f.state.session.cvstudioLinkedinSessionV1.viewed=rows;f.boot();assert((await f.rpc('tabs')).error);assert.equal(f.state.updates.length,0);
  }
 }],
 ['older session snapshots remain readable and replacement tabs cannot reset budgets',async()=>{
  const {f,id}=await profile();delete f.state.session.cvstudioLinkedinSessionV1.viewed;f.boot();assert.equal((await read(f,id)).result,true);
  f.tabs.get(id).active=true;await f.hooks().activated({tabId:id});const moved=(await f.navigate(id)).result;
  for(let i=2;i<75;i++)assert((await f.navigate(moved.tab_id)).result);
  f.boot();assert((await f.navigate(moved.tab_id)).error);assert.equal(f.state.counter,12);await f.end();assert(f.tabs.has(id));
 }],
 ['HR joining reads a viewed exact profile and leaves it open',async()=>{
  const {f,join,profileId}=await hr();f.tabs.get(profileId).active=true;await f.hooks().activated({tabId:profileId});const result=await join();assert.equal(result.result.joined,'2020-06');assert(f.tabs.has(profileId));
 }],
 ['HR does not scroll a viewed profile whose Experience is still missing',async()=>{
  const {f,join,profileId}=await hr();f.tabs.get(profileId).active=true;await f.hooks().activated({tabId:profileId});f.state.joinedNull=true;const result=await join();assert.equal(result.result.joined,'');assert.equal(f.state.profileScrolls||0,0);assert(f.tabs.has(profileId));assert(!f.state.session.cvstudioLinkedinLeadsSessionV1.connection.hr.joining);
 }],
 ['controller follows only a valid companion replacement ID',async()=>{
  const context=vm.createContext({window:{},URL,Map,Set,setTimeout,clearTimeout,Error,console});vm.runInContext(fs.readFileSync(path.join(__dirname,'../vendor/cvstudio/linkedin-sourcer-core.js'),'utf8'),context);
  const rows=[{id:'p0',url:first,name:'First',text:'Observed skill',score:80,evidence:['Observed skill'],unknowns:[]},{id:'p1',url:second,name:'Second',text:'Observed skill',score:70,evidence:['Observed skill'],unknowns:[]}];
  const run={id:'a'.repeat(32)};
  for(const replacement of [{tab_id:20},{tab_id:-1},{tab_id:'20'},{},[]]){
  const profileReads=[];
  const agent=new context.window.CVLinkedinCore.Agent({signal:new AbortController().signal,wait:async()=>{},update:()=>{},
   api:async(route,body)=>route.endsWith('plan')?{run,plan:{query:'Skill'}}:route.endsWith('review')?{run,candidates:rows}:{run},
   browser:{activeTab:async()=>({id:2,url:'https://www.linkedin.com/search/results/people/'}),navigate:async(id)=>id===10?replacement:true,createTab:async()=>10,closeOwnedTab:async()=>{},read:async(id,method)=>{if(method==='readProfile'){profileReads.push(id);return {text:'Observed skill'}}return {profiles:rows,signature:'one',hasNext:false,paginationKnown:true}}}});
  const started=agent.start({mode:'standard',max_pages:1,use_open_search:true});
  if(replacement.tab_id===20){await started;assert.deepEqual(profileReads,[10,20]);assert.equal(agent.results.length,2)}
  else {await assert.rejects(started,/confirm the new background/);assert.deepEqual(profileReads,[10]);assert.equal(agent.results.length,2,'prior card results remain')}
  }
 }],
];
(async()=>{let failed=0;for(const [name,test] of cases){try{await test();console.log('PASS',name)}catch(e){failed++;console.error('FAIL',name,e.message)}}if(failed)process.exitCode=1;})().catch(e=>{console.error(e);process.exitCode=1});
