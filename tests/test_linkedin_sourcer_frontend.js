const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert/strict');
const root = path.resolve(__dirname, '..');

(async function(){
  const callbacks = {};
  let counter = 10;
  const tabs = new Map([
    [1, {id:1, url:'http://127.0.0.1:5000/', active:true}],
    [2, {id:2, url:'https://www.linkedin.com/search/results/people/', status:'complete',active:true}],
    [3, {id:3, url:'https://www.linkedin.com/in/unrelated', status:'complete'}]
  ]);
  const url = 'https://www.linkedin.com/in/sample-person';
  let searchResult, readerFailure='';
  const chrome = {
    storage:{session:{get:async()=>({}),set:async()=>{}}},
    action: {onClicked:{addListener:fn=>callbacks.click=fn},setBadgeText:async()=>{}},
    tabs: {onRemoved:{addListener:()=>{}},onUpdated:{addListener:()=>{}},onActivated:{addListener:()=>{}},
      query:async()=>[tabs.get(2)],get:async id=>{if(!tabs.has(id))throw Error('Missing');return tabs.get(id)},
      create:async({url})=>{const tab={id:++counter,url,active:false,status:'complete'};tabs.set(tab.id,tab);return tab},
      update:async(id,{url})=>{tabs.get(id).url=url},remove:async id=>tabs.delete(id)},
    scripting:{executeScript:async args=>{
      if(args.files)return [{}];
      if(!args.args)return [{result:true,documentId:'app-document'}];
      if(readerFailure)return [{result:vm.runInNewContext('('+args.func.toString()+')(...values)',{values:args.args,SourcerReader:{[args.args[0]]:()=>{throw Error(readerFailure)}}})}];
      return [{result:args.args[0]==='readSearch'?(searchResult === undefined ? {profiles:[{id:'p0',url}],signature:'one',hasNext:true} : searchResult):true}];
    }},runtime:{onMessage:{addListener:fn=>callbacks.message=fn}}
  };
  const context=vm.createContext({chrome,URL,console,Map,Set,Error,Number});
  vm.runInContext(fs.readFileSync(path.join(root,'vendor/linkedin-companion/worker.js'),'utf8'),context);
  const sender={tab:{id:1},documentId:'app-document',url:tabs.get(1).url};
  const rpc=(action,args={},who=sender)=>new Promise(resolve=>callbacks.message({kind:'sourcer',action,args},who,resolve));
  assert((await rpc('tabs')).error);
  await callbacks.click(tabs.get(1));
  assert.equal((await rpc('tabs')).result[0].id,2);
  const legacyTab=(await rpc('tabs')).result[0];assert.equal(legacyTab.active,true);assert.equal(legacyTab.lastAccessed,0,'older Chrome metadata has an active-tab fallback without requiring a newer minimum version');
  assert((await rpc('tabs',{}, {...sender,documentId:'different-document'})).error);
  const run_id='a'.repeat(32);
  const fresh=(await rpc('openPeopleSearch')).result;
  assert.equal(fresh.url,'https://www.linkedin.com/search/results/people/');
  assert.notEqual(fresh.id,2,'fresh searches never repurpose an existing tab');
  const begin={run_id,source_tab_id:2,max_pages:2,mode:'standard'};
  assert.equal((await rpc('begin',begin)).result,true);
  assert((await rpc('openPeopleSearch')).error,'an active run cannot open another source');
  assert((await rpc('create',{run_id,url})).error, 'unobserved profile must be blocked');
  assert((await rpc('read',{run_id,tab_id:3,method:'readProfile',values:[tabs.get(3).url]})).error);
  await rpc('read',{run_id,tab_id:2,method:'readSearch',values:['standard']});
  searchResult=null;
  assert.equal((await rpc('read',{run_id,tab_id:2,method:'readSearch',values:['standard']})).result.loading,true,'missing injection results are loading, never successful snapshots');
  searchResult={profiles:'invalid'};
  assert((await rpc('read',{run_id,tab_id:2,method:'readSearch',values:['standard']})).error,'malformed nonempty snapshots fail visibly');
  searchResult=undefined;
  readerFailure='LinkedIn needs you to sign in or complete a check. The agent will stop.';
  assert.match((await rpc('read',{run_id,tab_id:2,method:'readSearch',values:['standard']})).error,/sign-in|verification/,'page exceptions survive as useful, fixed guidance');
  readerFailure='Synthetic error with private page text';
  const readerError=(await rpc('read',{run_id,tab_id:2,method:'readSearch',values:['standard']})).error;
  assert.match(readerError,/latest companion/);assert(!readerError.includes('private page text'));
  readerFailure='';
  const profile=(await rpc('create',{run_id,url})).result;
  assert.equal(typeof profile,'number');
  assert((await rpc('navigate',{run_id,tab_id:profile,url:'https://attacker.invalid'})).error);
  assert.equal((await rpc('read',{run_id,tab_id:2,method:'next',values:['standard','one']})).result,true);
  await rpc('begin',begin);
  assert((await rpc('read',{run_id,tab_id:2,method:'next',values:['standard','one']})).error, 'repeat begin must not reset limits');
  await rpc('end',{run_id});
  assert(!tabs.has(profile));
  assert(tabs.has(fresh.id),'End never closes the new source search');
  assert((await rpc('read',{run_id,tab_id:2,method:'readSearch',values:['standard']})).error);
  assert(!fs.readFileSync(path.join(root,'vendor/linkedin-companion/worker.js'),'utf8').includes('api.deepseek.com'));

  const coreContext=vm.createContext({window:{},URL,Map,Set,setTimeout,clearTimeout,Error,console});
  vm.runInContext(fs.readFileSync(path.join(root,'vendor/cvstudio/linkedin-sourcer-core.js'),'utf8'),coreContext);
  const Core=coreContext.window.CVLinkedinCore;
  for(const invalid of [null,undefined,{},true,{empty:true},{profiles:'invalid',signature:'one'}]) {
    let reads=0;
    const invalidAgent=new Core.Agent({signal:new AbortController().signal,wait:async()=>{},update:()=>{},api:async()=>{},browser:{read:async()=>{reads++;return invalid}}});
    await assert.rejects(invalidAgent.waitSearch(2,'standard'),/LinkedIn.*read|LinkedIn.*reader/,'invalid snapshots have useful guidance instead of null/empty errors');
    assert.equal(reads,1,'malformed snapshots are not treated as zero results');
  }
  for (const mode of ['standard','lite','recruiter']) {
    let page=1,next=0,calls=0;
    const candidate=()=>({id:'p0',name:'Sample Person',url:`https://www.linkedin.com/in/sample-${page}`,text:'SAP manufacturing',score:80,evidence:['SAP'],unknowns:['Availability']});
    const run={id:'b'.repeat(32)};
    const agent=new Core.Agent({signal:new AbortController().signal,wait:async()=>{},update:()=>{},
      api:async(route,body)=>{
        if(route.endsWith('start')||route.endsWith('stop'))return {run};
        if(route.endsWith('plan'))return {run,plan:{query:'SAP'}};
        calls++;return {run,candidates:[candidate()]};
      },browser:{activeTab:async()=>({id:2,url:mode==='standard'?'https://www.linkedin.com/search/results/people/':'https://www.linkedin.com/talent/search'}),
        navigate:async()=>{},createTab:async()=>10,closeOwnedTab:async()=>{},read:async(id,method)=>{
          if(method==='search')return true;
          if(method==='next'){page++;next++;return true}
          if(method==='readProfile')return {text:'SAP manufacturing'};
          return {profiles:[candidate()],signature:String(page),hasNext:page<15,paginationKnown:true};
        }}});
    await agent.start({mode,max_pages:15,use_open_search:false});
    assert.equal(agent.results.length,15);assert.equal(next,14);assert.equal(calls,30);
  }
  assert(Core.csv([{name:'=FORMULA()',url,score:5,checked:true,evidence:[],unknowns:[]}]).includes("'=FORMULA()"));
  console.log('LinkedIn module: companion binding, observed links, owned tabs, Stop/page limits, all three 15-page modes and CSV safety passed');
})().catch(error=>{console.error(error);process.exitCode=1});
