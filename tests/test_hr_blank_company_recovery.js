const assert=require('assert/strict'),{hrFixture}=require('./test_linkedin_company_hr');
async function blankFixture(){
  const f=hrFixture(),read=f.state.onScript;f.state.blank=true;
  f.state.onScript=args=>args.args?.[0]==='readHRCompany' && f.state.blank?[{result:{loading:true,blank_document:true}}]:read(args);
  await f.arm();f.id=(await f.beginHR()).result.tab_id;return f;
}
(async()=>{
  const f=await blankFixture();
  for(let i=0;i<11;i++){assert((await f.readHR(f.id)).result.loading);f.boot();}
  assert.equal(f.state.reloaded?.length||0,0,'ordinary initial hydration receives passive waits first');
  assert((await f.readHR(f.id)).result.loading);assert.deepEqual(f.state.reloaded,[f.id]);
  for(let i=0;i<20;i++){f.boot();assert((await f.readHR(f.id)).result.loading);}
  assert.equal(f.state.reloaded.length,1,'a blank page reload is bounded across worker suspension');
  assert.equal(f.state.hrReads,0);assert.equal(f.state.hrClicks.length,0,'no profiles or native filters before company confirmation');
  f.state.blank=false;assert((await f.readHR(f.id)).result.loading);assert((await f.readHR(f.id)).result.people,'normal exact-company validation resumes after hydration');
  for(const reason of ['active','content','changed','persist','interrupted']){
    const g=await blankFixture();
    if(reason==='active')g.tabs.get(g.id).active=true;
    if(reason==='content'){const read=g.state.onScript;g.state.onScript=args=>args.args?.[0]==='readHRCompany'?[{result:{loading:true}}]:read(args);}
    if(reason==='changed')g.tabs.get(g.id).url='https://www.linkedin.com/login';
    if(reason==='persist')g.state.failWrite=true;
    if(reason==='interrupted'){g.state.onReload=()=>{throw Error('Interrupted reload')};}
    for(let i=0;i<15;i++){const r=await g.readHR(g.id);if(r.error)break;}
    if(reason==='interrupted'){g.boot();assert((await g.readHR(g.id)).result.loading);assert.equal(g.state.reloaded.length,1,'after an ambiguous read-only reload, passive confirmation can continue but the reload cannot repeat');}
    else assert.equal(g.state.reloaded?.length||0,0,reason+' cannot authorize a blank reload');
    assert.equal(g.state.hrReads,0);
  }
  console.log('Blank company recovery: bounded reload, suspension, hydration, takeover, content, access, storage failure and ambiguous actions passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
