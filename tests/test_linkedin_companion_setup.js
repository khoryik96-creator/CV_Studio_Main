const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../vendor/linkedin-companion/worker.js'),'utf8');
function fixture(){
  const hooks={},session={},tabs=new Map([[1,{id:1,url:'http://127.0.0.1:5000/',status:'complete',active:true}],
    [2,{id:2,url:'https://www.linkedin.com/search/results/people/',status:'complete',active:true}]]);
  const state={document:'doc-1',valid:true,reloads:0,removed:[],created:[],disk:'24.6.481',loaded:'24.6.480',fetches:[]};
  const chrome={storage:{session:{get:async()=>session,set:async value=>{if(state.failWrite)throw Error('Synthetic storage failure');Object.assign(session,JSON.parse(JSON.stringify(value)))}}},
    action:{onClicked:{addListener:fn=>hooks.click=fn},setBadgeText:async()=>{}},
    tabs:{onRemoved:{addListener:fn=>hooks.removed=fn},onUpdated:{addListener:fn=>hooks.updated=fn},onActivated:{addListener:()=>{}},
      get:async id=>{if(!tabs.has(id))throw Error('Missing tab');return {...tabs.get(id)}},query:async()=>[...tabs.values()],
      create:async options=>{state.created.push(options);return {id:20,...options}},remove:async id=>state.removed.push(id)},
    scripting:{executeScript:async options=>{if(options.target.documentIds?.[0]!==undefined&&options.target.documentIds[0]!==state.document)throw Error('Stale document');return [{result:state.valid,documentId:state.document}]}},
    runtime:{id:'test-extension',getManifest:()=>({version:state.loaded}),getURL:file=>'chrome-extension://test-extension/'+file,
      reload:()=>state.reloads++,onMessage:{addListener:fn=>hooks.message=fn}}};
  const fetch=async(url,options)=>{state.fetches.push({url,options});if(state.beforeFetch)await state.beforeFetch();return {ok:true,json:async()=>({manifest_version:3,name:'CV Studio LinkedIn Companion',version:state.disk})}};
  vm.runInNewContext(source,{chrome,fetch,URL,console,setTimeout,clearTimeout});
  const sender=(id=1)=>({id:chrome.runtime.id,tab:tabs.get(id),frameId:0,documentId:state.document,url:tabs.get(id)?.url});
  const rpc=(action,args={},who=sender())=>new Promise(resolve=>hooks.message({kind:'sourcer',action,args},who,resolve));
  return {state,tabs,hooks,rpc,sender,session};
}
const tests=[
  ['connects a verified CV Studio document without a toolbar click',async()=>{
    const f=fixture();assert.equal((await f.rpc('connect')).result.connected,true);
    assert.equal((await f.rpc('jobStatus')).result.connected,true);assert.equal(f.state.created.length,0);
    assert.equal(f.session.cvstudioLinkedinSessionV1.connection.documentId,'doc-1');
  }],
  ['refresh binds the new document but never resumes the old run',async()=>{
    const f=fixture();await f.rpc('connect');assert((await f.rpc('begin',{run_id:'a'.repeat(32),source_tab_id:2,max_pages:2,mode:'standard'})).result);
    await f.hooks.updated(1,{status:'loading'});f.state.document='doc-2';
    assert((await f.rpc('connect')).result.connected);assert.equal(f.session.cvstudioLinkedinSessionV1.connection.run,undefined);
    assert((await f.rpc('read',{run_id:'a'.repeat(32),tab_id:2,method:'readSearch'})).error);
  }],
  ['duplicate and concurrent connections preserve an active run',async()=>{
    const f=fixture();await Promise.all([f.rpc('connect'),f.rpc('connect')]);
    assert((await f.rpc('begin',{run_id:'a'.repeat(32),source_tab_id:2,max_pages:2,mode:'standard'})).result);await f.rpc('connect');
    assert.equal(f.session.cvstudioLinkedinSessionV1.connection.run,'a'.repeat(32));
    f.tabs.set(3,{id:3,url:'http://127.0.0.1:5000/',status:'complete',active:true});
    assert((await f.rpc('connect',{},f.sender(3))).error);assert.equal(f.session.cvstudioLinkedinSessionV1.connection.tabId,1);
  }],
  ['rejects fake pages, subframes, foreign senders and stale documents',async()=>{
    for(const kind of ['fake','frame','foreign','stale','pending','nonlocal']){
      const f=fixture(),sender=f.sender();
      if(kind==='fake')f.state.valid=false;
      if(kind==='frame')sender.frameId=2;
      if(kind==='foreign')sender.id='another-extension';
      if(kind==='stale')sender.documentId='old-doc';
      if(kind==='pending')f.tabs.get(1).pendingUrl='http://127.0.0.1:5000/other';
      if(kind==='nonlocal')sender.url='https://example.invalid/';
      assert((await f.rpc('connect',{},sender)).error,kind);assert.equal(f.session.cvstudioLinkedinSessionV1?.connection??null,null,kind);
    }
  }],
  ['applies only locally installed matching update files',async()=>{
    const f=fixture();await f.rpc('connect');const result=await f.rpc('reloadCompanion',{version:f.state.disk});
    assert.equal(result.result.reloading,true);await new Promise(resolve=>setTimeout(resolve,150));
    assert.equal(f.state.reloads,1);assert.equal(f.state.fetches[0].url,'chrome-extension://test-extension/manifest.json');
    assert.equal(f.state.fetches[0].options.cache,'no-store');
  }],
  ['a search starting during update validation prevents reload',async()=>{
    const f=fixture();await f.rpc('connect');let resume;f.state.beforeFetch=()=>new Promise(resolve=>resume=resolve);
    const updating=f.rpc('reloadCompanion',{version:f.state.disk});await new Promise(resolve=>setImmediate(resolve));
    assert((await f.rpc('begin',{run_id:'a'.repeat(32),source_tab_id:2,max_pages:2,mode:'standard'})).result);resume();
    assert.match((await updating).error,/finish|stop/i);assert.equal(f.state.reloads,0);
  }],
  ['a background app cannot replace an idle binding and failed persistence grants no authority',async()=>{
    const f=fixture();await f.rpc('connect');f.tabs.set(3,{id:3,url:'http://127.0.0.1:5000/',status:'complete',active:false});
    assert((await f.rpc('connect',{},f.sender(3))).error);assert.equal(f.session.cvstudioLinkedinSessionV1.connection.tabId,1);
    const unavailable=fixture();unavailable.state.failWrite=true;assert((await unavailable.rpc('connect')).error);
    assert((await unavailable.rpc('jobStatus')).error);
  }],
  ['old downloaded copies and busy runs do not reload',async()=>{
    const f=fixture();await f.rpc('connect');f.state.disk=f.state.loaded;
    assert.match((await f.rpc('reloadCompanion',{version:'24.6.481'})).error,/folder/i);
    assert.equal((await f.rpc('reloadCompanion',{version:f.state.loaded})).result.current,true);
    assert((await f.rpc('begin',{run_id:'a'.repeat(32),source_tab_id:2,max_pages:2,mode:'standard'})).result);
    assert.match((await f.rpc('reloadCompanion',{version:f.state.loaded})).error,/finish|stop/i);assert.equal(f.state.reloads,0);
  }],
];
(async()=>{let failed=0;for(const [name,test]of tests){try{await test();console.log('PASS',name)}catch(error){failed++;console.error('FAIL',name,error.message)}}if(failed)process.exitCode=1;})();
