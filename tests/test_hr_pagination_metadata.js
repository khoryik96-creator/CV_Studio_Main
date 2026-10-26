const assert=require('assert/strict');
const {hrFixture}=require('./test_linkedin_company_hr');
(async()=>{
  const f=hrFixture();await f.arm();const id=(await f.beginHR()).result.tab_id;
  await f.readHR(id);assert((await f.readHR(id)).result.people);
  const url=new URL(f.tabs.get(id).url);url.searchParams.set('page','2');
  url.searchParams.set('spellCorrectionEnabled','true');url.searchParams.set('prioritizeMessage','false');
  f.tabs.get(id).url=url.href;
  assert((await f.readHR(id)).result?.people,'native pagination flags must not invalidate unchanged company, country and keywords');
  for(const [key,value] of [['currentCompany','["999"]'],['keywords','Changed query'],['geoUrn','["999"]']]){
    const changed=new URL(url);changed.searchParams.set(key,value);f.tabs.get(id).url=changed.href;
    assert((await f.readHR(id)).error,'real search identity changes remain rejected: '+key);
  }
  const broken=hrFixture('Malaysia');await broken.arm();const source=(await broken.beginHR()).result.tab_id;
  await broken.readHR(source);
  broken.state.onScript=args=>args.files?undefined:[{result:{hrError:'layout'}}];
  const failed=await broken.readHR(source);
  assert.match(failed.error,/location filter/i,'country-control failures identify the failed step');
  assert(!failed.error.includes('Example Company'),'errors must not echo page or company text');
  console.log('HR pagination metadata, unchanged search filters and fixed step-specific error messages passed');
})().catch(error=>{console.error(error);process.exit(1)});
