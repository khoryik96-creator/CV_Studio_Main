const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../vendor/linkedin-companion/worker.js'),'utf8');
const first='https://www.linkedin.com/in/sample-person',second='https://www.linkedin.com/in/other-person';
const clone=value=>JSON.parse(JSON.stringify(value));
function fixture(){
  const state={session:{},document:'bound-document',updates:[],removed:[],scripts:[],counter:10,failWrite:false};
  const tabs=new Map([[1,{id:1,url:'http://127.0.0.1:5000/',status:'complete',active:true}],
    [2,{id:2,url:'https://www.linkedin.com/search/results/people/',status:'complete',active:true}]]);
  let hooks;
  const chrome={
    storage:{session:{get:async key=>({[key]:clone(state.session[key]??null)}),set:async value=>{if(state.failWrite)throw Error('Synthetic session failure');Object.assign(state.session,clone(value));}}},
    action:{onClicked:{addListener:fn=>hooks.arm=fn},setBadgeText:async()=>{}},
    tabs:{onRemoved:{addListener:fn=>hooks.removed=fn},onUpdated:{addListener:fn=>hooks.updated=fn},onActivated:{addListener:fn=>hooks.activated=fn},
      query:async()=>[...tabs.values()],get:async id=>{if(!tabs.has(id))throw Error('Missing synthetic tab');return {...tabs.get(id)}},
      create:async({url,active})=>{const tab={id:++state.counter,url:state.loadingCreate?'about:blank':url,active,status:state.loadingCreate?'loading':'complete'};if(state.loadingCreate)tab.pendingUrl=url;tabs.set(tab.id,tab);return {...tab}},
      update:async(id,{url})=>{state.updates.push({id,url});const tab=tabs.get(id);if(state.loadingNavigation){tab.pendingUrl=url;tab.status='loading'}else tab.url=url;return {...tab}},
      remove:async id=>{state.removed.push(id);tabs.delete(id)}},
    scripting:{executeScript:async args=>{
      state.scripts.push(args);
      if(args.target.documentIds && args.target.documentIds[0]!==state.document)throw Error('Original document is gone');
      if(args.files){if(state.onInject)await state.onInject(args.target.tabId);return [{}]}
      if(!args.args)return [{result:true,documentId:state.document}];
      return [{result:args.args[0]==='readSearch'?{profiles:[{url:first},{url:second}]}:true}];
    }},runtime:{onMessage:{addListener:fn=>hooks.message=fn}}};
  function boot(){hooks={};vm.runInContext(source,vm.createContext({chrome,URL,console,Map,Set,Error,Number,JSON,Promise,Array,Object,String,Date,setTimeout,clearTimeout}));}
  boot();
  const sender=()=>({tab:{id:1},documentId:state.document,url:tabs.get(1).url});
  const rpc=(action,args={},who=sender())=>new Promise(resolve=>hooks.message({kind:'sourcer',action,args},who,resolve));
  const run='a'.repeat(32);
  return {state,tabs,boot,rpc,run,hooks:()=>hooks,arm:()=>hooks.arm(tabs.get(1)),
    begin:()=>rpc('begin',{run_id:run,source_tab_id:2,max_pages:2,mode:'standard'}),
    observe:()=>rpc('read',{run_id:run,tab_id:2,method:'readSearch',values:['standard']}),
    create:()=>rpc('create',{run_id:run,url:first}),
    navigate:id=>rpc('navigate',{run_id:run,tab_id:id,url:second}),end:()=>rpc('end',{run_id:run})};
}
const cases=[
  ['binding and limits survive a fresh worker',async()=>{
    const f=fixture();await f.arm();f.boot();assert((await f.rpc('tabs')).result,'idle worker restart preserves the same app binding');
    await f.begin();await f.observe();const id=(await f.create()).result;
    await f.rpc('read',{run_id:f.run,tab_id:2,method:'next',values:['standard','one']});f.boot();
    assert((await f.rpc('create',{run_id:f.run,url:'https://www.linkedin.com/in/unobserved'})).error);
    assert((await f.rpc('read',{run_id:f.run,tab_id:2,method:'next',values:['standard','one']})).error,'restart cannot reset the page budget');
    assert((await f.navigate(id)).result,'owned tabs and observed links survive restart');
    await f.end();assert(!f.tabs.has(id),'End cleans up only retained owned tabs');f.boot();assert((await f.navigate(id)).error,'ended run stays ended');
  }],
  ['user activation relinquishes a profile tab',async()=>{
    const f=fixture();await f.arm();await f.begin();await f.observe();const id=(await f.create()).result;
    f.tabs.get(id).active=true;assert((await f.navigate(id)).error,'active user-owned tab must not be navigated');
    assert.equal(f.state.updates.length,0);f.tabs.get(id).active=false;await f.end();assert(f.tabs.has(id),'a relinquished tab is never cleaned up');
  }],
  ['user navigation relinquishes a profile tab',async()=>{
    const f=fixture();await f.arm();await f.begin();await f.observe();const id=(await f.create()).result;
    f.tabs.get(id).url='https://www.linkedin.com/feed/';assert((await f.navigate(id)).error);assert.equal(f.state.updates.length,0);
    await f.end();assert(f.tabs.has(id));
  }],
  ['activation events persist relinquishment across restart',async()=>{
    const f=fixture();await f.arm();await f.begin();await f.observe();const id=(await f.create()).result;
    f.tabs.get(id).active=true;await f.hooks().activated({tabId:id});f.tabs.get(id).active=false;f.boot();await f.end();assert(f.tabs.has(id));
  }],
  ['changed or loading documents cannot inherit authority',async()=>{
    const f=fixture();await f.arm();await f.begin();f.state.document='replacement-document';f.boot();
    assert((await f.rpc('tabs')).error);await f.arm();assert((await f.rpc('tabs')).result);
    await f.hooks().updated(1,{status:'loading'});f.boot();assert((await f.rpc('tabs')).error);
  }],
  ['storage failure blocks new browser actions',async()=>{
    const f=fixture();f.state.failWrite=true;await f.arm();assert((await f.rpc('tabs')).error);
    assert.equal(f.state.updates.length,0);assert.equal(f.state.counter,10);
  }],
  ['ownership is checked again after script injection',async()=>{
    const f=fixture();await f.arm();await f.begin();await f.observe();const id=(await f.create()).result;
    f.state.onInject=tabId=>{if(tabId===id)f.tabs.get(id).active=true};
    const before=f.state.scripts.length;assert((await f.rpc('read',{run_id:f.run,tab_id:id,method:'readProfile',values:[first]})).error);
    assert.equal(f.state.scripts.slice(before).filter(item=>item.args?.[0]==='readProfile').length,0);
  }],
  ['profile limits and toolbar rearming cannot reset a running budget',async()=>{
    const f=fixture();await f.arm();await f.begin();await f.observe();const id=(await f.create()).result;
    for(let attempt=1;attempt<75;attempt++)assert((await f.navigate(id)).result);
    await f.arm();assert((await f.navigate(id)).error,'same-document toolbar click preserves limits');
    f.boot();assert((await f.navigate(id)).error,'worker restart preserves profile limits');
    assert.equal(f.state.updates.length,74);await f.end();f.boot();assert((await f.rpc('tabs')).result);
  }],
  ['failed writes stop actions before navigation',async()=>{
    const f=fixture();await f.arm();await f.begin();await f.observe();const id=(await f.create()).result;
    f.state.failWrite=true;assert((await f.navigate(id)).error);assert.equal(f.state.updates.length,0);
    assert((await f.rpc('tabs')).error);f.state.failWrite=false;await f.arm();assert((await f.rpc('tabs')).result);
  }],
  ['corrupt or missing document state never creates authority',async()=>{
    const f=fixture();await f.arm();await f.begin();
    const key=Object.keys(f.state.session)[0];f.state.session[key].owned=[[11,'']];f.boot();
    assert((await f.rpc('tabs')).error);assert.equal(f.state.updates.length,0);await f.arm();assert((await f.rpc('tabs')).result);
    f.tabs.delete(1);f.boot();assert((await f.rpc('tabs',{}, {tab:{id:1},documentId:'bound-document',url:'http://127.0.0.1:5000/'})).error);
  }],
  ['commanded profile navigation preserves loading polling across restart',async()=>{
    const f=fixture();await f.arm();await f.begin();await f.observe();const id=(await f.create()).result;
    f.state.loadingNavigation=true;assert((await f.navigate(id)).result);
    const read=()=>f.rpc('read',{run_id:f.run,tab_id:id,method:'readProfile',values:[second]});
    assert((await read()).result?.loading,'old committed URL plus expected pending target must keep loading');
    f.boot();assert((await read()).result?.loading,'suspension during a commanded navigation keeps ownership');
    Object.assign(f.tabs.get(id),{url:second,status:'complete'});delete f.tabs.get(id).pendingUrl;
    assert.equal((await read()).result,true);await f.end();assert(!f.tabs.has(id));
  }],
  ['new profile tabs can start with an uncommitted URL',async()=>{
    const f=fixture();await f.arm();await f.begin();await f.observe();f.state.loadingCreate=true;const id=(await f.create()).result;
    assert((await f.rpc('read',{run_id:f.run,tab_id:id,method:'readProfile',values:[first]})).result?.loading);
    Object.assign(f.tabs.get(id),{url:first,status:'complete'});delete f.tabs.get(id).pendingUrl;
    assert.equal((await f.rpc('read',{run_id:f.run,tab_id:id,method:'readProfile',values:[first]})).result,true);
  }],
];
(async()=>{let failures=0;for(const [name,test] of cases){try{await test();console.log('PASS',name)}catch(error){failures++;console.error('FAIL',name,error.message)}}if(failures)process.exitCode=1;})().catch(error=>{console.error(error);process.exitCode=1});
