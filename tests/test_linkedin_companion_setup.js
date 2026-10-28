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
      create:async options=>{state.created.push(options);return {id:20,...options}},remove:async id=>state.removed.push(id),
      sendMessage:async(id,message,options)=>{(state.readyMessages??=[]).push({id,message,options});return state.onReady?.()}},
    scripting:{executeScript:async options=>{if(options.target.documentIds?.[0]!==undefined&&options.target.documentIds[0]!==state.document)throw Error('Stale document');return [{result:state.valid,documentId:state.document}]}},
    runtime:{id:'test-extension',getManifest:()=>({version:state.loaded}),getURL:file=>'chrome-extension://test-extension/'+file,
      reload:()=>state.reloads++,onMessage:{addListener:fn=>hooks.message=fn}}};
  const fetch=async(url,options)=>{state.fetches.push({url,options});if(state.beforeFetch)await state.beforeFetch();return {ok:true,json:async()=>({manifest_version:3,name:'CV Studio LinkedIn Companion',version:state.disk})}};
  const identity=require('./linkedin_companion_identity_fixture')(chrome);
  const boot=()=>vm.runInNewContext(source,{chrome,fetch,URL,console,setTimeout,clearTimeout,crypto:identity.crypto,TextEncoder});boot();
  const sender=(id=1)=>({id:chrome.runtime.id,tab:tabs.get(id),frameId:0,documentId:state.document,url:tabs.get(id)?.url});
  const rpc=(action,args={},who=sender(),scope)=>new Promise(resolve=>hooks.message({kind:'sourcer',scope,action,args},who,resolve));
  return {state,tabs,hooks,rpc,sender,session,identity:identity.state,boot};
}
const tests=[
  ['unpaired local imitations cannot auto-connect or steal an idle binding',async()=>{
    const f=fixture();f.identity.trusted={};assert((await f.rpc('connect')).error);
    assert((await f.rpc('tabs')).error);assert.equal(f.session.cvstudioLinkedinSessionV1?.connection??null,null);
    f.identity.trusted={'http://127.0.0.1:5000':f.identity.key};assert((await f.rpc('connect')).result.connected);
    f.tabs.set(3,{id:3,url:'http://127.0.0.1:5999/',status:'complete',active:true});
    assert((await f.rpc('connect',{},f.sender(3))).error);assert.equal(f.session.cvstudioLinkedinSessionV1.connection.tabId,1);
  }],
  ['paired origins must answer a fresh backend proof, not just copy DOM markers',async()=>{
    const f=fixture();f.identity.key='34'.repeat(32);assert((await f.rpc('connect')).error);
    f.identity.key='12'.repeat(32);assert((await f.rpc('connect')).result.connected);
    const proof=f.identity.proofs[0].nonce;assert.notEqual(proof,f.identity.proofs[1].nonce);
    await f.hooks.updated(1,{status:'loading'});f.state.document='doc-2';f.identity.proof='00'.repeat(32);
    assert((await f.rpc('connect')).error);
  }],
  ['toolbar pairing is explicit, persists trust and fails closed on storage errors',async()=>{
    const f=fixture();f.identity.trusted={};await f.hooks.click(f.tabs.get(1));
    assert.equal(f.identity.trusted['http://127.0.0.1:5000'],f.identity.key);
    assert((await f.rpc('connect')).result.connected);
    assert(!JSON.stringify(f.session).includes(f.identity.key),'pairing keys never enter session snapshots');
    assert.equal(f.identity.access[0].accessLevel,'TRUSTED_CONTEXTS');
    const broken=fixture();broken.identity.trusted={};broken.identity.failWrite=true;await broken.hooks.click(broken.tabs.get(1));
    assert((await broken.rpc('tabs')).error);
  }],
  ['fresh workers verify persistent trust and cannot inherit an old unpaired session',async()=>{
    const f=fixture();f.identity.trusted={};await f.hooks.click(f.tabs.get(1));
    f.boot();assert((await f.rpc('tabs')).result);
    f.identity.trusted={};f.boot();assert((await f.rpc('tabs')).error);
    assert.equal(f.session.cvstudioLinkedinSessionV1.connection,null);
  }],
  ['old proofs cannot be replayed and navigation during pairing grants no authority',async()=>{
    const f=fixture();assert((await f.rpc('connect')).result);
    const {createHmac}=require('crypto'),first=f.identity.proofs[0];
    f.identity.proof=createHmac('sha256',Buffer.from(f.identity.key,'hex')).update('CVStudio companion v1|'+first.actual+'|'+first.nonce).digest('hex');
    await f.hooks.updated(1,{status:'loading'});f.state.document='doc-2';assert((await f.rpc('connect')).error);
    const moved=fixture();moved.identity.trusted={};moved.identity.beforeWrite=async()=>{moved.state.document='doc-2'};
    await moved.hooks.click(moved.tabs.get(1));assert((await moved.rpc('tabs')).error);
  }],
  ['loading-time rejection reconnects on tab completion without another app action',async()=>{
    const f=fixture();f.tabs.get(1).status='loading';const loading=await f.rpc('connect');assert(loading.error);assert.equal(loading.loading,true);
    f.state.onReady=()=>f.rpc('connect');f.tabs.get(1).status='complete';await f.hooks.updated(1,{status:'complete'});
    assert((await f.rpc('jobStatus')).result?.connected,'completion must initiate a fresh verified handshake');
    assert.equal(f.state.readyMessages[0].options.frameId,0);
  }],
  ['only the same loading app URL receives a retry hint',async()=>{
    const f=fixture();f.tabs.get(1).status='loading';f.tabs.get(1).pendingUrl=f.tabs.get(1).url;assert.equal((await f.rpc('connect')).loading,true);
    f.tabs.get(1).pendingUrl='https://example.invalid/';assert.equal((await f.rpc('connect')).loading,undefined);
    f.tabs.get(1).pendingUrl='';assert.equal((await f.rpc('connect',{}, {...f.sender(),frameId:1})).loading,undefined);
  }],
  ['completion does not notify other hosts, paths or pending navigations',async()=>{
    for(const url of ['https://example.invalid/','http://127.0.0.1:5000/other']){
      const f=fixture();f.tabs.get(1).url=url;await f.hooks.updated(1,{status:'complete'});assert.equal(f.state.readyMessages?.length||0,0);
    }
    const f=fixture();f.tabs.get(1).pendingUrl='https://example.invalid/';await f.hooks.updated(1,{status:'complete'});assert.equal(f.state.readyMessages?.length||0,0);
  }],
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
  ['update validation reserves both sessions before any new scan can start',async()=>{
    const f=fixture();await f.rpc('connect');let resume;f.state.beforeFetch=()=>new Promise(resolve=>resume=resolve);
    const updating=f.rpc('reloadCompanion',{version:f.state.disk});await new Promise(resolve=>setImmediate(resolve));
    assert((await f.rpc('begin',{run_id:'a'.repeat(32),source_tab_id:2,max_pages:2,mode:'standard'})).error);
    assert((await f.rpc('hrBegin',{},f.sender(),'leads')).error);resume();
    assert((await updating).result.reloading);await new Promise(resolve=>setTimeout(resolve,150));assert.equal(f.state.reloads,1);
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
