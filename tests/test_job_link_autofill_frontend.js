const fs=require('fs'), path=require('path'), vm=require('vm'), assert=require('assert/strict');
const root=path.resolve(__dirname,'..');
const url='https://www.linkedin.com/jobs/view/1234567890', other='https://www.linkedin.com/jobs/view/7777777777';
function fixture() {
  const hooks={}, state={created:[],removed:[],scripts:[],counter:10};
  const tabs=new Map([[1,{id:1,url:'http://127.0.0.1:5000/',status:'complete',active:true}],
    [2,{id:2,url,status:'complete',active:false}],[3,{id:3,url:'https://www.linkedin.com/search/results/people/',status:'complete'}]]);
  const chrome={action:{onClicked:{addListener:fn=>hooks.arm=fn},setBadgeText:async()=>{}},
    storage:{session:{get:async()=>({}),set:async()=>{}}},
    tabs:{onRemoved:{addListener:()=>{}},onUpdated:{addListener:fn=>hooks.updated=fn},onActivated:{addListener:()=>{}},
      query:async()=>{if(state.queryWait)await state.queryWait;return [...tabs.values()]},
      get:async id=>{const row=tabs.get(id);if(!row)throw Error('Missing synthetic tab');if(state.metadataGap&&id>10&&!state.gapSeen){state.gapSeen=true;return {...row,url:'about:blank',status:'loading',pendingUrl:state.changedPending?'https://attacker.invalid/':undefined}}return row},
      create:async args=>{state.created.push(args);const tab={id:++state.counter,url:args.url,active:args.active,status:state.loading?'loading':'complete'};tabs.set(tab.id,tab);return tab},
      remove:async id=>{state.removed.push(id);tabs.delete(id)},
      update:async()=>{throw Error('Must not navigate an existing tab')}},
    scripting:{executeScript:async args=>{
      state.scripts.push(args);
      if(args.files){if(state.inject)await state.inject(args.target.tabId);return [{}]}
      if(!args.args)return [{result:true,documentId:'bound'}];
      state.readCount=(state.readCount||0)+1;
      if(state.delayedReads){state.delayedReads--;return [{result:{loading:true}}]}
      if(state.readFails)throw Error('Synthetic unrecognized job layout');
      return [{result:state.readerError?{jobError:state.readerError}:{url:args.args[0],company:'Sample Company',role:'Finance Manager',location:'Kuala Lumpur'}}];
    }},runtime:{getManifest:()=>({version:'24.6.461'}),onMessage:{addListener:fn=>hooks.message=fn}}};
  const identity=require('./linkedin_companion_identity_fixture')(chrome);
  const context=vm.createContext({chrome,URL,Map,Set,Error,Number,setTimeout:fn=>fn(),crypto:identity.crypto,TextEncoder});
  vm.runInContext(fs.readFileSync(path.join(root,'vendor/linkedin-companion/worker.js'),'utf8'),context);
  const sender={tab:{id:1},documentId:'bound',url:tabs.get(1).url};
  const rpc=(action,args={},who=sender)=>new Promise(resolve=>hooks.message({kind:'sourcer',action,args},who,resolve));
  return {hooks,state,tabs,rpc,arm:()=>hooks.arm(tabs.get(1))};
}
(async()=>{
  const cold=fixture();await cold.arm();cold.state.metadataGap=true;
  assert.equal((await cold.rpc('jobFromLink',{url:other})).result?.company,'Sample Company','new owned tab may initially lack committed and pending URL metadata');
  const changed=fixture();await changed.arm();changed.state.metadataGap=true;changed.state.changedPending=true;
  assert((await changed.rpc('jobFromLink',{url:other})).error);assert.equal(changed.state.readCount||0,0,'a different pending target is never read');
  const access=fixture();await access.arm();access.state.readerError='access';
  assert.match((await access.rpc('jobRead',{tab_id:2,expected_url:url})).error,/sign-in|verification|restriction/i,'LinkedIn access failure is not reported as a disconnected extension');
  const f=fixture();
  assert((await f.rpc('jobStatus')).error,'status cannot bypass the app binding');
  assert((await f.rpc('jobFromLink',{url})).error);assert.equal(f.state.created.length,0);
  await f.arm();
  assert.deepEqual({...((await f.rpc('jobStatus')).result)},{connected:true,job_read:true,job_search:true,job_search_revision:1,company_hr_revision:1,hr_company_identity_revision:1,hr_company_filter_revision:1,hr_company_source_revision:1,hr_resilience_revision:1,hr_layout_revision:1,concurrent_scans_revision:1,profile_browsing_revision:1,hr_joined_revision:1,hr_joined_loading_revision:1,hr_keyword_revision:1,people_country_revision:1,people_results_revision:1,companion_update_revision:1,version:'24.6.461',busy:false,other_busy:false});
  assert.equal((await f.rpc('jobFromLink',{url})).result.location,'Kuala Lumpur');
  assert.equal(f.state.created.length,0);assert.equal(f.state.removed.length,0,'existing tabs remain open');
  f.state.delayedReads=3;let reads=f.state.readCount;
  assert.equal((await f.rpc('jobRead',{tab_id:2,expected_url:url})).result.company,'Sample Company');
  assert.equal(f.state.readCount-reads,6,'waits on delayed DOM fields and description without navigating');
  f.state.delayedReads=100;reads=f.state.readCount;
  assert((await f.rpc('jobRead',{tab_id:2,expected_url:url})).error);
  assert.equal(f.state.readCount-reads,16,'readiness wait has a fixed bound');f.state.delayedReads=0;
  assert.equal(f.state.created.length,0,'readiness never retries by creating another tab');
  for(const invalid of ['javascript:alert(1)','https://attacker.invalid/jobs/view/123','https://www.linkedin.com/in/person','https://user@www.linkedin.com/jobs/view/123',url+'?trk=x','https://www.linkedin.com/jobs/search/?currentJobId=1234567890']) {
    assert((await f.rpc('jobFromLink',{url:invalid})).error,invalid);
  }
  assert.equal(f.state.created.length,0);
  const result=await f.rpc('jobFromLink',{url:other});assert.equal(result.result.url,other);
  assert.equal(f.state.created.length,1);assert.equal(f.state.created[0].url,other);assert.equal(f.state.created[0].active,false);assert.deepEqual(f.state.removed,[11]);assert(f.tabs.has(2));
  f.state.inject=id=>{f.tabs.get(id).active=true};
  assert((await f.rpc('jobFromLink',{url:other})).result);assert(f.tabs.has(12),'a user-activated temporary tab must remain open');
  f.tabs.delete(12);
  f.state.inject=id=>{f.tabs.get(id).url='https://www.linkedin.com/checkpoint/challenge'};
  assert((await f.rpc('jobFromLink',{url:other})).error);assert(f.tabs.has(13),'a navigated tab must remain open');
  f.tabs.delete(13);f.state.inject=null;f.state.readFails=true;
  assert((await f.rpc('jobFromLink',{url:other})).error);assert(f.state.removed.includes(14),'failure closes only the unchanged inactive owned tab');
  f.state.readFails=false;f.state.loading=true;
  assert((await f.rpc('jobFromLink',{url:other})).error);assert(f.state.removed.includes(15),'bounded load timeout cleans up its own tab');
  f.state.loading=false;
  let release;f.state.queryWait=new Promise(resolve=>{release=resolve});
  const pending=f.rpc('jobFromLink',{url:other});await Promise.resolve();
  assert.equal((await f.rpc('jobStatus')).result.busy,true,'a pending capture is reported busy without disturbing it');
  assert((await f.rpc('jobFromLink',{url})).error,'concurrent capture blocked');
  assert((await f.rpc('jobRead',{tab_id:2,expected_url:url})).error,'manual read cannot overlap capture');
  assert((await f.rpc('begin',{run_id:'a'.repeat(32),source_tab_id:3,max_pages:1,mode:'standard'})).error,'Sourcer cannot start midway through capture');
  release();assert((await pending).result);f.state.queryWait=null;
  assert.equal((await f.rpc('begin',{run_id:'a'.repeat(32),source_tab_id:3,max_pages:1,mode:'standard'})).result,true);
  assert.equal((await f.rpc('jobStatus')).result.busy,true,'profile sourcing cannot be interrupted by fallback');
  assert((await f.rpc('jobFromLink',{url})).error,'capture cannot interrupt Sourcer');await f.rpc('end',{run_id:'a'.repeat(32)});
  f.state.inject=()=>f.hooks.updated(1,{status:'loading'});
  assert((await f.rpc('jobFromLink',{url:other})).error,'reloading the app revokes capture');
  assert(f.tabs.has(1) && f.tabs.has(2) && f.tabs.has(3));
  console.log('Job-link capture: bound sender, canonical jobs only, existing-tab reuse, temporary-tab ownership, timeout, challenges, concurrent capture, reload and Sourcer isolation passed');
})().catch(error=>{console.error(error);process.exitCode=1});
