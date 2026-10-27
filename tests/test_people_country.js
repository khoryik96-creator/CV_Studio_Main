const assert=require('assert/strict'),fs=require('fs'),vm=require('vm');
const {fixture}=require('./test_linkedin_job_search');
const query='("SAP FICO" OR "SAP FI/CO" OR "SAP Finance" OR "SAP Controlling")';
function countryFixture(country='Malaysia'){
  const f=fixture();f.state.clicks=[];
  f.state.onUpdate=(id,args)=>Object.assign(f.tabs.get(id),args);
  f.state.onScript=args=>{
    if(args.files || !args.args)return;
    const [method]=args.args;
    if(method.startsWith('hrCountry')){
      f.state.clicks.push(method);
      if(f.state.interrupt)throw Error('Interrupted browser mutation');
      if(f.state.missing)return [{result:null}];
      if(f.state.notReady)return [{result:false}];
      if(method==='hrCountryApply'){const tab=f.tabs.get(3),url=new URL(tab.url);url.searchParams.set('geoUrn','["12345"]');tab.url=url.href;}
      return [{result:true}];
    }
    if(method==='peopleCountrySelected' || method===country)return [{result:!f.state.unchecked}];
    if(method==='readSearch')return [{result:{profiles:[{url:'https://www.linkedin.com/in/sample'}],signature:'one'}}];
    if(method==='next'){f.state.next++;if(f.state.nextLoading)f.tabs.get(3).status='loading';return [{result:true}];}
  };
  f.start=async()=>{await f.arm();assert((await f.rpc('begin',{run_id:f.run,source_tab_id:3,mode:'standard',max_pages:10})).result);assert((await f.rpc('navigate',{run_id:f.run,tab_id:3,url:'https://www.linkedin.com/search/results/people/?keywords='+encodeURIComponent(query)})).result);};
  f.country=()=>f.rpc('read',{run_id:f.run,tab_id:3,method:'setCountry',values:[country]});
  f.profiles=()=>f.rpc('read',{run_id:f.run,tab_id:3,method:'readSearch',values:['standard']});
  return f;
}
(async()=>{
  for(const country of ['Malaysia','Singapore','Portugal']){
    const f=countryFixture(country);await f.start();
    f.tabs.get(3).status='loading';assert.equal((await f.country()).result?.loading,true);assert.equal(f.state.clicks.length,0);f.tabs.get(3).status='complete';
    f.state.notReady=true;assert.equal((await f.country()).result?.loading,true);f.state.notReady=false;
    for(let i=0;i<4;i++){assert.equal((await f.country()).result?.loading,true);f.boot();}
    assert.equal((await f.country()).result,true);
    assert.deepEqual(f.state.clicks,['hrCountryOpen','hrCountryOpen','hrCountryType','hrCountryPick','hrCountryApply']);
    assert.equal(new URL(f.tabs.get(3).url).searchParams.get('keywords'),query);assert.equal(new URL(f.tabs.get(3).url).searchParams.get('geoUrn'),'["12345"]');
    assert((await f.profiles()).result.profiles);
    f.state.unchecked=true;assert.equal((await f.profiles()).result?.loading,true,'selected visible filter must remain confirmed');f.state.unchecked=false;
    f.tabs.get(3).pendingUrl=f.tabs.get(3).url.replace('12345','999');assert((await f.profiles()).error,'pending country change blocks evidence');delete f.tabs.get(3).pendingUrl;
    f.tabs.get(3).url+='&network=F';assert((await f.profiles()).error,'other filters cannot silently change');
  }
  for(const problem of ['interrupt','missing']){
    const f=countryFixture();await f.start();f.state[problem]=true;assert((await f.country()).error);f.boot();f.state[problem]=false;assert((await f.country()).error);assert.equal(f.state.clicks.length,1,'ambiguous clicks never replay after worker suspension');
  }
  const unready=countryFixture();await unready.start();assert((await unready.profiles()).result,'a no-country search remains compatible');
  const changed=countryFixture();await changed.start();await changed.country();assert((await changed.profiles()).error,'unconfirmed location never reaches scoring');
  const paging=countryFixture();await paging.start();for(let i=0;i<5;i++)await paging.country();
  const next=()=>paging.rpc('read',{run_id:paging.run,tab_id:3,method:'next',values:['standard','one']});
  paging.state.onInject=()=>{paging.tabs.get(3).status='loading';};assert.equal((await next()).result?.loading,true);assert.equal(paging.state.next,0);
  paging.state.onInject=null;paging.tabs.get(3).status='complete';paging.state.nextLoading=true;
  assert.equal((await next()).result,true,'a confirmed pagination click is not replayed when navigation begins');assert.equal(paging.state.next,1);
  const scope={window:{},URL,Map,Set,setTimeout,clearTimeout,Error};vm.runInNewContext(fs.readFileSync(require.resolve('../vendor/cvstudio/linkedin-sourcer-core.js'),'utf8'),scope);
  for(const reuse of [false,true]){
    const events=[],run={id:'a'.repeat(32)},controller=new AbortController();
    const agent=new scope.window.CVLinkedinCore.Agent({signal:controller.signal,wait:async()=>{},update:()=>{},api:async route=>{events.push(route);return {run,plan:{query,country:'Malaysia'}}},browser:{activeTab:async()=>({id:3,url:'https://www.linkedin.com/search/results/people/'}),navigate:async(id,url)=>{events.push('navigate');assert.equal(new URL(url).searchParams.get('keywords'),query);},read:async(id,method,args)=>{events.push(method);if(method==='setCountry'){assert.equal(args[0],'Malaysia');return true;}return {empty:true,profiles:[],signature:'empty'};}}});
    await agent.start({mode:'standard',use_open_search:reuse,max_pages:1});
    assert.equal(events.includes('setCountry'),!reuse);if(!reuse)assert(events.indexOf('setCountry')<events.indexOf('readSearch'));
  }
  console.log('People country: exact native selection, arbitrary country labels, loading, suspension, no replay, filter identity and controller ordering passed');
})().catch(error=>{console.error(error);process.exitCode=1});
