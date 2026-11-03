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
  console.log('Full-ad worker: delayed header/description readiness, bounded timeout, capability, access-stop and owned-tab cleanup passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
