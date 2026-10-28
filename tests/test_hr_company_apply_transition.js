const assert=require('assert/strict'),{groupFixture}=require('./test_hr_company_group_worker');
async function fixture(mode,country='',patch={}){
 const f=groupFixture(country),original=f.state.onScript;
 f.state.onScript=args=>{
  const result=original(args);
  if(args.args?.[0]==='hrCompanyApply'){
   const tab=f.tabs.get(args.target.tabId);f.state.final=tab.url;
   const bare=new URL(tab.url);bare.searchParams.delete('currentCompany');bare.searchParams.set('origin','FACETED_SEARCH');
   f.state.intermediate=bare.href;
   if(mode==='committed')tab.url=bare.href;
   if(mode==='pending')tab.pendingUrl=bare.href;
   if(mode==='group-pending'){const old=new URL(tab.url);old.searchParams.set('currentCompany','["123","456","789"]');tab.url=old.href;tab.pendingUrl=bare.href;}
  }
  return result;
 };
 await f.arm();const id=(await f.beginHR(patch)).result.tab_id;
 for(let i=0;i<4;i++){const response=await f.readHR(id);assert(!response.error,response.error)}
 assert.equal(f.state.session.cvstudioLinkedinLeadsSessionV1.connection.hr.stage,'company_wait');
 return {f,id};
}
(async()=>{
 for(const country of ['', 'Malaysia'])for(const mode of ['committed','pending','group-pending']){
  const {f,id}=await fixture(mode,country);const clicks=f.state.hrClicks.length;
  for(let n=0;n<8;n++){
   f.boot();const response=await f.readHR(id);assert(!response.error,mode+': '+response.error);assert(response.result.loading);assert.equal(f.state.hrReads,0);assert.equal(f.state.hrClicks.length,clicks,'passive waiting never repeats Apply');
  }
  f.tabs.get(id).url=f.state.final;delete f.tabs.get(id).pendingUrl;let result;
  for(let n=0;n<16;n++){result=await f.readHR(id);assert(!result.error,result.error);if(!result.result.loading)break}
  assert.equal(result.result.company_id,'456');assert.equal(f.state.hrReads,1);assert.deepEqual(JSON.parse(new URL(result.result.source_url).searchParams.get('currentCompany')),['456']);
  if(country)assert(new URL(result.result.source_url).searchParams.has('geoUrn'));
 }
 for(const change of ['keywords','extra-country','empty-company','foreign-company','duplicate-company','wrong-path']){
  const {f,id}=await fixture('committed');const u=new URL(f.tabs.get(id).url);
  if(change==='keywords')u.searchParams.set('keywords','Different requirement');
  if(change==='extra-country')u.searchParams.set('geoUrn','["999"]');
  if(change==='empty-company')u.searchParams.set('currentCompany','');
  if(change==='foreign-company')u.searchParams.set('currentCompany','["999"]');
  if(change==='duplicate-company'){u.searchParams.set('currentCompany','["456"]');u.searchParams.append('currentCompany','["123"]')}
  if(change==='wrong-path')u.pathname='/jobs/search/';
  f.tabs.get(id).url=u.href;assert((await f.readHR(id)).error,change+' must stop');assert.equal(f.state.hrReads,0);
 }
 const expired=await fixture('committed');expired.f.state.session.cvstudioLinkedinLeadsSessionV1.connection.hr.started=Date.now()-600001;expired.f.boot();assert((await expired.f.readHR(expired.id)).error);assert.equal(expired.f.state.hrReads,0);
 const pinned=await fixture('committed','',{expected_company_id:'789'});pinned.f.tabs.get(pinned.id).url=pinned.f.state.final;assert((await pinned.f.readHR(pinned.id)).error,'the saved company ID is still authoritative');assert.equal(pinned.f.state.hrReads,0);
 const stopped=await fixture('committed');assert((await stopped.f.end()).result);assert((await stopped.f.readHR(stopped.id)).error);assert.equal(stopped.f.state.hrReads,0);
 console.log('Company Apply transition: same-keyword filterless committed/pending/group URLs wait across restart; exact singleton/country required; foreign/changed filters, deadline, pinned ID and Stop remain guarded.');
})().catch(error=>{console.error(error);process.exitCode=1});
