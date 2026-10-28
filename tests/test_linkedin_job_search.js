const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const worker=fs.readFileSync(path.join(__dirname,'../vendor/linkedin-companion/worker.js'),'utf8');
const search='https://www.linkedin.com/jobs/search/?keywords=finance&location=Malaysia';
const row={url:'https://www.linkedin.com/jobs/view/1234567890',company:'Example Finance',role:'Finance Manager',location:'Penang',description:'Visible search summary'};
const copy=value=>JSON.parse(JSON.stringify(value));
function fixture(){
  let hooks;
  const state={session:{},created:[],removed:[],document:'bound',next:0,scroll:0,failWrite:false,reads:0,location:'Malaysia',failInjection:false,failReader:false};
  const tabs=new Map([[1,{id:1,url:'http://127.0.0.1:5000/',status:'complete'}],[2,{id:2,url:search,status:'complete'}],[3,{id:3,url:'https://www.linkedin.com/search/results/people/',status:'complete'}]]);
  const chrome={storage:{session:{get:async key=>({[key]:copy(state.session[key]||null)}),set:async data=>{if(state.failWrite)throw Error('Synthetic storage failure');Object.assign(state.session,copy(data));if(state.onPersist)await state.onPersist(data);}}},
    action:{onClicked:{addListener:fn=>hooks.arm=fn},setBadgeText:async()=>{}},
    tabs:{onRemoved:{addListener:fn=>hooks.removed=fn},onUpdated:{addListener:fn=>hooks.updated=fn},onActivated:{addListener:fn=>hooks.activated=fn},
      query:async()=>[...tabs.values()],get:async id=>{if(!tabs.has(id))throw Error('Missing tab');return {...tabs.get(id)}},
      create:async args=>{state.created.push(args);const tab={...args,id:10+state.created.length,status:'complete'};tabs.set(tab.id,tab);if(state.onCreated)await state.onCreated(tab);return {...tab}},
      remove:async id=>{state.removed.push(id);tabs.delete(id)},reload:async id=>{(state.reloaded ||= []).push(id);if(state.onReload)await state.onReload(id);},update:async(id,args)=>{if(state.onUpdate)return state.onUpdate(id,args);throw Error('Do not navigate existing tabs')}},
    scripting:{executeScript:async args=>{
      if(state.onScript){const response=state.onScript(args);if(response!==undefined)return response;}
      if(args.target.documentIds?.[0] && args.target.documentIds[0]!==state.document)throw Error('Stale document');
      if(args.files){if(state.failInjection)throw Error('PRIVATE synthetic path and detail');if(state.onInject)state.onInject();return [{}]}
      if(!args.args)return [{result:true,documentId:state.document}];
      const method=args.args[0];
      if(state.failReader)throw Error('PRIVATE synthetic document and detail');
      if(method==='jobSearchContext')return [{result:{location:state.location}}];
      if(method==='nextJobSearch'){state.next++;return [{result:true}]}
      if(method==='scrollJobSearch'){state.scroll++;return [{result:true}]}
      state.reads++;return [{result:{url:tabs.get(args.target.tabId).url,jobs:[row],signature:row.url,hasNext:true,paginationKnown:true,atBottom:true}}];
    }},runtime:{getManifest:()=>({version:'24.6.461'}),onMessage:{addListener:fn=>hooks.message=fn}}};
  const identity=require('./linkedin_companion_identity_fixture')(chrome);
  const boot=()=>{hooks={};vm.runInContext(worker,vm.createContext({chrome,URL,Map,Set,Date,console,setTimeout:(fn,ms,...args)=>setTimeout(fn,state.fastWait&&[350,500].includes(ms)?0:ms,...args),clearTimeout,crypto:identity.crypto,TextEncoder}));};boot();
  const sender=()=>({tab:{id:1},documentId:state.document,url:tabs.get(1).url});
  const rpc=(action,args={},who=sender(),scope)=>new Promise(resolve=>hooks.message({kind:'sourcer',scope,action,args},who,resolve));
  const run='b'.repeat(32);
  return {state,tabs,boot,rpc,run,hooks:()=>hooks,arm:()=>hooks.arm(tabs.get(1)),begin:(patch={})=>rpc('jobSearchBegin',{run_id:run,query:'finance',location:'Malaysia',max_pages:2,...patch}),
    read:(id,method='readJobSearch')=>rpc('read',{run_id:run,tab_id:id,method,values:method==='readJobSearch'?[]:[row.url]}),end:()=>rpc('end',{run_id:run})};
}
module.exports={fixture};
if(require.main===module)(async()=>{
  const f=fixture();assert((await f.begin()).error);assert.equal(f.state.created.length,0);await f.arm();
  const started=await f.begin();assert(started.result?.tab_id,'bound job search begins');const id=started.result.tab_id;
  const status=(await f.rpc('jobStatus')).result;assert.equal(status.version,'24.6.461');assert.equal(status.job_search_revision,1,'readiness identifies the current reader/search contract');
  assert.equal(f.state.created.length,1);assert.equal(new URL(f.state.created[0].url).searchParams.get('keywords'),'finance');
  assert.equal(new URL(f.state.created[0].url).searchParams.get('location'),'Malaysia');
  assert.equal(f.tabs.get(2).url,search,'existing tabs are never repurposed');
  assert.equal((await f.read(id)).result.jobs[0].company,'Example Finance');
  assert((await f.rpc('jobFromLink',{url:row.url})).error,'single-ad capture waits for crawl');
  assert((await f.rpc('read',{run_id:f.run,tab_id:id,method:'readProfile',values:[row.url]})).error,'job run cannot read profiles');
  assert((await f.rpc('create',{run_id:f.run,url:'https://www.linkedin.com/in/person'})).error);
  assert((await f.rpc('navigate',{run_id:f.run,tab_id:id,url:'https://www.linkedin.com/search/results/people/?keywords=x'})).error);
  assert((await f.rpc('read',{run_id:f.run,tab_id:2,method:'readJobSearch',values:[]})).error,'unselected tabs remain isolated');
  assert((await f.read(id,'nextJobSearch')).result);f.boot();assert((await f.read(id)).result);
  assert((await f.begin()).result);assert.equal(f.state.created.length,1,'repeat Begin preserves source and budget');
  assert((await f.read(id,'nextJobSearch')).error);assert.equal(f.state.next,1,'suspension/rebegin cannot reset page ceiling');
  await f.end();assert(f.tabs.has(id),'search output is retained for user review');assert.equal(f.state.removed.length,0);
  const g=fixture();await g.arm();const open=await g.begin({use_open:true,source_tab_id:2});assert.equal(open.result.tab_id,2);assert.equal(g.state.created.length,0);
  g.tabs.get(2).url=search.replace('/jobs/search/','/jobs/search-results/')+'&eBP=job-card-tracking&currentJobId=1234567890';
  assert.equal((await g.read(2)).result.jobs[0].url,row.url,'new layout aliases and selected-card tracking retain filter identity');
  g.boot();assert((await g.read(2)).result,'the alias works after worker suspension');
  g.tabs.get(2).url=search+'&keywords=other';assert((await g.read(2)).error,'changed filters revoke reads');await g.end();
  const h=fixture();await h.arm();const hi=(await h.begin({max_pages:1})).result.tab_id;
  for(let n=0;n<8;n++)assert((await h.read(hi,'scrollJobSearch')).result);
  h.boot();assert((await h.read(hi,'scrollJobSearch')).error);assert.equal(h.state.scroll,8,'scroll limit persists');await h.end();
  const j=fixture();await j.arm();const ji=(await j.begin()).result.tab_id;
  j.state.onInject=()=>{j.tabs.get(ji).url='https://www.linkedin.com/login'};
  assert((await j.read(ji)).error);assert.equal(j.state.reads,0,'redirect checked after injection');
  const k=fixture();await k.arm();k.state.failWrite=true;assert((await k.begin()).error);assert((await k.read(11)).error);
  const bad=fixture();await bad.arm();
  for(const patch of [{max_pages:16},{max_pages:0},{query:''},{query:'x'.repeat(241)},{query:'line\nbreak'},{use_open:true,source_tab_id:3}])assert((await bad.begin(patch)).error);
  assert.equal(bad.state.created.length,0);
  const normalized=fixture();await normalized.arm();const ni=(await normalized.begin()).result.tab_id;
  normalized.tabs.get(ni).url='https://www.linkedin.com/jobs/search-results/?keywords=finance&currentJobId=1234567890';
  normalized.state.location='';assert.equal((await normalized.read(ni)).result.loading,true,'wait for the displayed location');
  normalized.boot();normalized.state.location='Malaysia';assert.equal((await normalized.read(ni)).result.jobs.length,1,'initial URL normalization retains a confirmed rendered location');
  normalized.tabs.get(ni).url+='&geoId=changed';assert((await normalized.read(ni)).error,'resolved filters are pinned after initial confirmation');
  const wrong=fixture();await wrong.arm();const wi=(await wrong.begin()).result.tab_id;wrong.state.location='Singapore';
  assert.match((await wrong.read(wi)).error,/different location/);assert.equal(wrong.state.reads,0);
  const changed=fixture();await changed.arm();const ci=(await changed.begin()).result.tab_id;
  changed.tabs.get(ci).url='https://www.linkedin.com/jobs/search-results/?keywords=other';assert((await changed.read(ci)).error,'initial normalization cannot change keywords');
  assert.equal(changed.state.reads,0);
  for(const initial of [true,false])for(const kind of ['failInjection','failReader']){
    const broken=fixture();await broken.arm();const bi=(await broken.begin(initial?{}:{use_open:true,source_tab_id:2})).result.tab_id;broken.state[kind]=true;
    const error=(await broken.read(bi)).error;
    assert.match(error,/LinkedIn|reader/,'the failed browser step is actionable');assert(!error.includes('PRIVATE'),'raw injection errors never leave the worker');
    assert.match(error,kind==='failInjection'?/reader could not start/:/could not be read/);
  }
  console.log('Job search companion: authority, source/run isolation, validated queries, suspension-safe page/scroll bounds, filter redirects and retained search tabs passed');
})().catch(error=>{console.error(error);process.exitCode=1});
