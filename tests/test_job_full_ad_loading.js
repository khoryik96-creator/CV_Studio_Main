const assert=require('assert/strict'),{fixture}=require('./test_linkedin_job_search');
const url='https://www.linkedin.com/jobs/view/1234567890';
function fullFixture(){
  const f=fixture();f.state.fastWait=true;f.state.fullReads=0;
  f.state.onScript=args=>{
    if(args.args?.[0]!==url)return;
    f.state.fullReads++;
    if(f.state.loading>0){f.state.loading--;return [{result:{loading:true}}];}
    if(f.state.access)return [{result:{jobError:'access',reason:'captcha'}}];
    return [{result:{url,company:'Example Finance',role:'Finance Manager',description:f.state.empty?'':'Complete full ad'}}];
  };return f;
}
(async()=>{
  const f=fullFixture();await f.arm();f.state.loading=24;
  assert.equal((await f.rpc('jobStatus')).result.full_ad_background_revision,1);
  const result=await f.rpc('jobFromLink',{url,operation_id:'a'.repeat(32)});
  assert.equal(result.result?.description,'Complete full ad','slow React details can settle beyond the old 16-poll cutoff');
  assert.equal(f.state.fullReads,25);assert(!f.tabs.has(11),'owned background tab is cleaned up');
  const description=fullFixture();await description.arm();description.state.empty=true;
  const original=description.state.onScript;description.state.onScript=args=>{if(description.state.fullReads===24)description.state.empty=false;return original(args);};
  assert((await description.rpc('jobFromLink',{url})).result?.description,'a loaded header waits for its description instead of returning empty after six polls');
  const empty=fullFixture();await empty.arm();empty.state.empty=true;
  assert.equal((await empty.rpc('jobFromLink',{url})).error_code,'HR_AD_TIMEOUT');assert.equal(empty.state.fullReads,48);
  const access=fullFixture();await access.arm();access.state.access=true;
  assert.equal((await access.rpc('jobFromLink',{url})).error_code,'HR_ACCESS_REQUIRED');assert.equal(access.state.fullReads,1);
  assert(!access.tabs.has(11));
  const partial=fullFixture();await partial.arm();const immediate=[];
  partial.state.onCreated=tab=>{tab.status='loading';};
  const base=partial.state.onScript;partial.state.onScript=args=>{if(args.files || args.args?.[0]===url)immediate.push(args.injectImmediately);return base(args);};
  assert.equal((await partial.rpc('jobFromLink',{url})).result?.description,'Complete full ad','a committed document with ready ad content need not wait for Chrome load completion');
  assert.equal(partial.state.fullReads,1);assert(immediate.length>=2 && immediate.every(value=>value===true));assert(!partial.tabs.has(11));
  for(const alias of [url+'/',url.replace('/1234567890','/fictional-role-at-company-1234567890/')]){
    const redirected=fullFixture();await redirected.arm();redirected.state.onCreated=tab=>{tab.url=alias;};
    assert((await redirected.rpc('jobFromLink',{url})).result?.description);assert(!redirected.tabs.has(11),'a path-only job redirect still closes after capture');
    const viewed=fullFixture();await viewed.arm();viewed.state.onCreated=tab=>{tab.url=alias;tab.active=true;};
    assert((await viewed.rpc('jobFromLink',{url})).result?.description);assert(viewed.tabs.has(11),'a viewed ad stays available');
  }
  const pending=fullFixture();await pending.arm();pending.state.onCreated=tab=>{tab.status='loading';tab.pendingUrl=url;};
  assert.equal((await pending.rpc('jobFromLink',{url})).error_code,'HR_AD_TIMEOUT','navigation timeout is an isolated ad failure, not a fatal companion error');assert.equal(pending.state.fullReads,0,'a pending navigation is not observed as a ready document');
  const metadata=fullFixture();await metadata.arm();metadata.state.onCreated=tab=>{tab.status='loading';};
  assert.equal((await metadata.rpc('jobFromLink',{url,company_only:true})).error_code,'HR_AD_TIMEOUT');assert.equal(metadata.state.fullReads,0,'HR employer capture retains complete-document readiness');
  for(const phase of ['files','read']){
    const transient=fullFixture();await transient.arm();let changed=false;const original=transient.state.onScript;
    transient.state.onScript=args=>{if(!changed && (phase==='files'?args.files:args.args?.[0]===url)){changed=true;throw Error('Execution context was destroyed');}return original(args);};
    assert.equal((await transient.rpc('jobFromLink',{url})).result?.description,'Complete full ad','a transient '+phase+' observation waits/reinjects on the same URL');assert.equal(transient.state.created.length,1);
  }
  console.log('Full-ad worker: delayed header/description readiness, bounded timeout, capability, access-stop and owned-tab cleanup passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
