const assert=require('assert/strict');
const {fixture}=require('./test_linkedin_job_search');
const companyURL='https://www.linkedin.com/company/example/';
function hrFixture(country=''){
  const f=fixture();Object.assign(f.state,{hrClicks:[],hrMutations:[],hrReads:0,country});
  f.state.onUpdate=(id,args)=>{assert(id>=11,'only newly created HR source is navigated');f.state.hrMutations.push(args.url);Object.assign(f.tabs.get(id),args);return {...f.tabs.get(id)}};
  f.state.onScript=args=>{
    if(!args.args||args.files)return;
    const [method]=args.args;
    if(method==='readHRCompany')return [{result:f.state.badCompany?{hrError:'layout'}:{company_id:'123'}}];
    if(method==='readHRSearch'){
      f.state.hrReads++;
      return [{result:{people:[],signature:'one',hasNext:true,empty:false}}];
    }
    if(method.startsWith('hrCountry')||method==='nextHRSearch'){
      f.state.hrClicks.push(method);
      if(f.state.nullMutation)return [{result:null}];
      if(f.state.failPick&&method==='hrCountryPick')return [{result:false}];
      if(method==='hrCountryApply'){
        const tab=f.tabs.get(args.target.tabId),u=new URL(tab.url);u.searchParams.set('geoUrn','["106808692"]');tab.url=u.href;
      }
      if(f.state.suspendMutation)throw Error('Synthetic interrupted mutation');
      return [{result:true}];
    }
  };
  f.beginHR=patch=>f.rpc('hrBegin',{run_id:f.run,company_url:companyURL,company:'Example Company',country,keywords:'HR, TA, recruitment',max_pages:2,...patch});
  f.readHR=id=>f.rpc('hrRead',{run_id:f.run,tab_id:id});
  f.nextHR=id=>f.rpc('hrNext',{run_id:f.run,tab_id:id,signature:'one'});
  return f;
}
(async()=>{
  const f=hrFixture();assert((await f.beginHR()).error);await f.arm();const id=(await f.beginHR()).result.tab_id;
  assert.equal(f.tabs.get(id).url,companyURL+'people/');assert.equal(f.state.created.length,1);
  assert((await f.readHR(id)).result.loading);
  let query=new URL(f.tabs.get(id).url);assert.equal(query.searchParams.get('currentCompany'),'["123"]');assert.match(query.searchParams.get('keywords'),/"HR" OR "TA"/);
  f.boot();assert((await f.readHR(id)).result.people);assert.equal(f.state.hrClicks.length,0,'Any country never clicks location controls');
  assert((await f.rpc('read',{run_id:f.run,tab_id:id,method:'readProfile'})).error);
  assert((await f.rpc('create',{run_id:f.run,url:'https://www.linkedin.com/in/sample'})).error);
  assert((await f.readHR(2)).error);assert((await f.beginHR()).result);assert.equal(f.state.created.length,1);
  assert.equal((await f.nextHR(id)).result,true);f.boot();assert((await f.nextHR(id)).error,'page budget persists across worker restart/Begin');
  await f.end();assert(f.tabs.has(id));assert.equal(f.state.removed.length,0,'user-facing source remains open');
  const c=hrFixture('Malaysia');await c.arm();const ci=(await c.beginHR()).result.tab_id;
  for(let n=0;n<6;n++){const r=await c.readHR(ci);assert(!r.error,r.error);c.boot();}
  assert.deepEqual(c.state.hrClicks,['hrCountryOpen','hrCountryType','hrCountryPick','hrCountryApply']);
  assert.equal(c.state.hrReads,1);assert.equal(new URL((await c.readHR(ci)).result.source_url).searchParams.get('geoUrn'),'["106808692"]');
  c.tabs.get(ci).url+='&network=%5B%22F%22%5D';assert((await c.readHR(ci)).error,'changing any search filter invalidates HR read');
  const changed=hrFixture();await changed.arm();const ch=(await changed.beginHR()).result.tab_id;await changed.readHR(ch);
  changed.state.onInject=()=>{changed.tabs.get(ch).url=changed.tabs.get(ch).url.replace('123','999')};
  assert((await changed.readHR(ch)).error);assert.equal(changed.state.hrReads,0,'filter identity rechecked after injection');
  for(const problem of ['nullMutation','suspendMutation']){
    const broken=hrFixture('Malaysia');await broken.arm();const bi=(await broken.beginHR()).result.tab_id;await broken.readHR(bi);broken.state[problem]=true;
    assert((await broken.readHR(bi)).error);broken.boot();assert((await broken.readHR(bi)).error);assert.equal(broken.state.hrClicks.length,1,'ambiguous mutation never replays after suspension');
  }
  const bad=hrFixture();await bad.arm();for(const patch of [{company_url:'https://attacker.invalid/company/x/'},{country:'x\ny'},{max_pages:16},{keywords:''}])assert((await bad.beginHR(patch)).error);
  assert.equal(bad.state.created.length,0);
  const busy=hrFixture();await busy.arm();await busy.begin();assert((await busy.beginHR()).error,'Jobs and HR runs cannot overlap');
  const old=hrFixture();await old.arm();const oi=(await old.beginHR()).result.tab_id;old.tabs.get(oi).url='https://www.linkedin.com/login';assert((await old.readHR(oi)).error);
  console.log('Company HR worker: exact document/company/country/source, bounded pages, suspension, mutation non-replay, competing runs and retained source passed');
})().catch(error=>{console.error(error);process.exitCode=1});
