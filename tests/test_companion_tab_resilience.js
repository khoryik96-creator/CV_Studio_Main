// Companion behaviour while the user keeps working in other tabs. Synthetic
// tabs only: no LinkedIn, network, credentials or real browser are used.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const root=path.resolve(__dirname,'..');
const first='https://www.linkedin.com/jobs/view/1111111111',second='https://www.linkedin.com/jobs/view/2222222222';
const search=id=>'https://www.linkedin.com/jobs/search/?keywords=finance&currentJobId='+id;
function fixture(){
  const hooks={},state={created:[],removed:[],now:1000000};
  const tabs=new Map([[1,{id:1,url:'http://127.0.0.1:5000/',status:'complete',active:true}],
    [2,{id:2,url:search('1111111111'),status:'complete',active:false}],
    [5,{id:5,url:'http://127.0.0.1:5000/',status:'complete',active:false}]]);
  const chrome={action:{onClicked:{addListener:fn=>hooks.arm=fn},setBadgeText:async()=>{}},
    storage:{session:{get:async()=>({}),set:async()=>{}}},
    tabs:{onRemoved:{addListener:()=>{}},onUpdated:{addListener:()=>{}},onActivated:{addListener:()=>{}},
      query:async()=>{if(state.queryWait)await state.queryWait;return [...tabs.values()];},
      get:async id=>{const row=tabs.get(id);if(!row)throw Error('No tab with id');return {...row};},
      create:async args=>{state.created.push(args);const tab={id:10+state.created.length,url:args.url,active:false,status:'complete'};tabs.set(tab.id,tab);return tab;},
      remove:async id=>{state.removed.push(id);tabs.delete(id);},update:async()=>{throw Error('Must not navigate an existing tab');},
      sendMessage:async()=>({ok:true,saved:true,folder:''})},
    scripting:{executeScript:async args=>{
      if(args.files){if(state.onInject)await state.onInject(args.target.tabId);return [{}];}
      if(!args.args)return [{result:true,documentId:args.target.documentIds?.[0] || 'bound'}];
      return [{result:{url:args.args[0],company:'Sample Company',role:'Finance Manager',location:'Kuala Lumpur',description:'Full sample job description'}}];
    }},runtime:{id:'companion',getManifest:()=>({version:'0.0.1'}),onMessage:{addListener:fn=>hooks.message=fn}}};
  const identity=require('./linkedin_companion_identity_fixture')(chrome);
  class Clock extends Date{static now(){return state.now;}}
  const context=vm.createContext({chrome,URL,Map,Set,Error,Number,Date:Clock,setTimeout:fn=>fn(),crypto:identity.crypto,TextEncoder});
  vm.runInContext(fs.readFileSync(path.join(root,'vendor/linkedin-companion/worker.js'),'utf8'),context);
  const app={id:'companion',frameId:0,tab:{id:1},documentId:'bound',url:tabs.get(1).url};
  const other={id:'companion',frameId:0,tab:{id:5},documentId:'second',url:tabs.get(5).url};
  const send=(message,who)=>new Promise(resolve=>hooks.message(message,who,resolve));
  const rpc=(action,args={},who=app)=>send({kind:'sourcer',scope:'leads',action,args},who);
  return {hooks,state,tabs,rpc,send,app,other,arm:()=>hooks.arm(tabs.get(1))};
}
(async()=>{
  // A queued ad link opens its own background tab. It never reads from a Jobs
  // search the user is browsing, whose selected ad changes with every click.
  let f=fixture();await f.arm();
  let reply=await f.rpc('jobFromLink',{url:first,operation_id:'a'.repeat(32)});
  assert.equal(reply.result.url,first);
  assert.deepEqual(f.state.created.map(row=>[row.url,row.active]),[[first,false]],'the browsed search tab is not adopted');
  assert.deepEqual(f.state.removed,[11],'only the companion-owned tab is closed');
  assert.equal(f.tabs.get(2).url,search('1111111111'),'the user search tab is untouched');
  // A dedicated ad page that is already open is still reused, as before.
  f=fixture();await f.arm();f.tabs.set(3,{id:3,url:first,status:'complete',active:false});
  reply=await f.rpc('jobFromLink',{url:first,operation_id:'a'.repeat(32)});
  assert.equal(reply.result.url,first);assert.equal(f.state.created.length,0);assert.equal(f.state.removed.length,0);
  // If that page then moves to another ad, only this ad fails, with a code the
  // queue can skip. The message itself is unchanged.
  f=fixture();await f.arm();f.tabs.set(3,{id:3,url:first,status:'complete',active:false});
  f.state.onInject=id=>{if(id===3)f.tabs.get(3).url=second;};
  reply=await f.rpc('jobFromLink',{url:first,operation_id:'a'.repeat(32)});
  assert.deepEqual({...reply},{error:'The selected job changed. Open its LinkedIn tab and try again.',error_code:'HR_AD_CHANGED'});
  assert.equal(f.state.removed.length,0,'a tab the companion did not open is never closed');
  // A second read while one is running is reported as busy, not as a disconnect.
  f=fixture();await f.arm();
  let release;f.state.queryWait=new Promise(resolve=>{release=resolve;});
  const pending=f.rpc('jobFromLink',{url:second,operation_id:'b'.repeat(32)});await Promise.resolve();
  reply=await f.rpc('jobFromLink',{url:first,operation_id:'c'.repeat(32)});
  assert.deepEqual({...reply},{error:'Finish the current browser action before reading a job ad.',error_code:'HR_BUSY'});
  release();assert((await pending).result);f.state.queryWait=null;
  // Fixed companion messages are shown as written; they are not replaced by a
  // generic "reconnect" line. Unknown browser errors stay masked.
  reply=await f.rpc('jobSearchBegin',{run_id:'d'.repeat(32),max_pages:99,use_open:true,source_tab_id:2});
  assert.equal(reply.error,'Choose 1 to 15 job-search pages.');
  f.state.queryWait=Promise.reject(Error('Raw failure naming https://private.invalid/tab'));f.state.queryWait.catch(()=>{});
  reply=await f.rpc('jobFromLink',{url:first,operation_id:'e'.repeat(32)});f.state.queryWait=null;
  assert.equal(reply.error,'The browser action stopped. Reconnect the companion or check the LinkedIn page.','a raw browser error never leaves the companion');
  // Another CV Studio tab becoming visible cannot take the companion from a
  // tab that used it moments ago (between two ads of one queue).
  f=fixture();await f.arm();
  assert((await f.rpc('jobFromLink',{url:second,operation_id:'f'.repeat(32)})).result);
  f.tabs.get(1).active=false;f.tabs.get(5).active=true;
  reply=await f.send({kind:'sourcer',action:'connect'},f.other);
  assert.equal(reply.error,'Finish the companion action in the other CV Studio tab first.');
  assert.deepEqual({...(await f.send({kind:'sourcer',action:'connect'},f.app)).result},{connected:true,version:'0.0.1'},'the working tab keeps its connection');
  assert((await f.rpc('jobFromLink',{url:first,operation_id:'a'.repeat(32)})).result,'its next ad still loads');
  // A step that fails still counts as recent use.
  f.state.now+=29000;f.tabs.set(3,{id:3,url:first,status:'complete',active:false});f.state.onInject=id=>{if(id===3)f.tabs.get(3).url=second;};
  assert.equal((await f.rpc('jobFromLink',{url:first,operation_id:'b'.repeat(32)})).error_code,'HR_AD_CHANGED');
  f.state.now+=29000;
  assert((await f.send({kind:'sourcer',action:'connect'},f.other)).error,'still protected 29 seconds after a failed step');
  // Status checks alone do not hold the companion, and after 30 idle seconds
  // the visible tab connects automatically as before.
  await f.rpc('jobStatus');f.state.now+=30001;
  assert.equal((await f.send({kind:'sourcer',action:'connect'},f.other)).result?.connected,true);
  assert((await f.rpc('jobStatus',{},f.other)).result?.connected,'the second tab now holds the companion');
  // Add to CV Studio on LinkedIn waits for a background ad read, then saves.
  f=fixture();await f.arm();
  const linkedin={id:'companion',frameId:0,tab:{id:2},documentId:'li',url:f.tabs.get(2).url};
  f.state.queryWait=new Promise(resolve=>{release=resolve;});
  const reading=f.rpc('jobFromLink',{url:second,operation_id:'b'.repeat(32)});await Promise.resolve();
  let picked=f.send({kind:'sourcer_job_pick',url:first,operation:'add'},linkedin);
  reply=await picked;
  assert.equal(reply.error,'Wait for the current search or ad read to finish, then add this ad.','a read that never finishes still refuses, after a bounded wait');
  release();assert((await reading).result);f.state.queryWait=null;
  reply=await f.send({kind:'sourcer_job_pick',url:first,operation:'add'},linkedin);
  assert.equal(reply.result?.ok,true,'an idle companion saves at once');
  // A folder name is limited by characters (as the server counts), not by
  // UTF-16 units: 41 emoji are 82 units but only 41 characters.
  reply=await f.send({kind:'sourcer_job_pick',url:first,operation:'add',folder:'😀'.repeat(41)},linkedin);
  assert.equal(reply.result?.ok,true);
  reply=await f.send({kind:'sourcer_job_pick',url:first,operation:'add',folder:'😀'.repeat(81)},linkedin);
  assert.equal(reply.error,'Choose a valid folder or job-ad action.');
  console.log('companion tab resilience ok');
})().catch(error=>{console.error(error);process.exit(1);});
