const assert=require('assert/strict');
const {fixture}=require('./test_linkedin_job_search');
const root='https://www.linkedin.com/company/fictional-client/',operation='c'.repeat(32);
const read=f=>f.rpc('jobCompanyID',{company_url:root,operation_id:operation},undefined,'leads');
const install=f=>{f.state.fastWait=true;f.state.onScript=args=>args.args?.[0]==='readCompanyJobsID'?[{result:{company_url:root,company_id:'4242'}}]:undefined;};
(async()=>{
 const f=fixture();install(f);assert((await read(f)).error);assert.equal(f.state.created.length,0);await f.arm();
 assert.equal((await f.rpc('jobStatus',{},undefined,'leads')).result.job_search_company_link_revision,1);
 assert.equal((await f.rpc('jobStatus',{},undefined,'leads')).result.company_jobs_action_revision,1);
 assert.equal((await read(f)).result.company_id,'4242');assert.equal(f.state.created[0].url,root+'jobs/');assert.equal(f.state.created[0].active,false);
 assert.deepEqual(f.state.removed,[11]);assert(f.tabs.has(2) && f.tabs.has(3),'unrelated user tabs remain');
 assert((await f.rpc('jobCompanyID',{company_url:root,operation_id:operation},undefined,'profiles')).error,'scope cannot cross modules');
 for(const args of [{company_url:'https://evil.invalid/company/x/',operation_id:operation},{company_url:root+'jobs/',operation_id:operation},{company_url:root,operation_id:'bad'}])assert((await f.rpc('jobCompanyID',args,undefined,'leads')).error);
 assert.equal(f.state.created.length,1,'bad input never opens tabs');
 const busy=fixture();install(busy);await busy.arm();await busy.begin();assert((await read(busy)).error);assert.equal(busy.state.created.length,1);await busy.end();
 const cancel=fixture();install(cancel);await cancel.arm();let release;cancel.state.onCreated=()=>new Promise(r=>release=r);
 const pending=read(cancel);for(let i=0;i<30&&!release;i++)await new Promise(r=>setImmediate(r));assert(release);
 assert.equal((await cancel.rpc('jobReadCancel',{operation_id:operation},undefined,'leads')).result,true);release();assert((await pending).error);assert.deepEqual(cancel.state.removed,[11]);
 const changed=fixture();install(changed);await changed.arm();changed.state.onInject=()=>{changed.tabs.get(11).pendingUrl='https://www.linkedin.com/company/other/jobs/';};
 assert((await read(changed)).error);assert(changed.tabs.has(11),'navigated tab is never closed');
 const access=fixture();install(access);await access.arm();access.state.onCreated=tab=>{access.tabs.get(tab.id).url='https://www.linkedin.com/login';};assert.match((await read(access)).error,/sign-in/);assert(access.tabs.has(11));
 const viewed=fixture();install(viewed);await viewed.arm();viewed.state.onCreated=tab=>{viewed.tabs.get(tab.id).active=true;};assert((await read(viewed)).result);assert(viewed.tabs.has(11),'user-activated tab remains open');
 const loading=fixture();install(loading);await loading.arm();loading.state.onScript=args=>args.args?.[0]==='readCompanyJobsID'?[{result:{loading:true}}]:undefined;
 assert.match((await read(loading)).error,/See all jobs/);assert.equal(loading.state.created.length,1,'bounded polling never repeats tab creation');assert.deepEqual(loading.state.removed,[11]);
 const late=fixture();install(late);await late.arm();late.state.onScript=args=>{if(args.args?.[0]==='readCompanyJobsID'){late.tabs.get(11).url='https://www.linkedin.com/company/wrong/jobs/';return [{result:{company_url:root,company_id:'4242'}}];}};assert((await read(late)).error,'post-read URL check rejects stale evidence');
 // LinkedIn's own first redirect of a company Jobs page (synthetic IDs).
 const toSearch=fixture();install(toSearch);await toSearch.arm();let reads=0;const base=toSearch.state.onScript;toSearch.state.onScript=args=>{if(args.args?.[0]==='readCompanyJobsID')reads++;return base(args);};
 toSearch.state.onCreated=tab=>{toSearch.tabs.get(tab.id).url='https://www.linkedin.com/jobs/search-results/?currentJobId=1234567890&keywords=jobs&f_C=13702795';};
 const searched=(await read(toSearch)).result;assert.deepEqual({...searched},{company_url:root,company_id:'13702795'},'a redirect to a one-company job search gives its number');
 assert.equal(reads,0,'no page read is needed');assert.deepEqual(toSearch.state.removed,[11],'the redirected tab is closed');
 const settling=fixture();install(settling);await settling.arm();let hops=0;
 settling.state.onCreated=tab=>{settling.tabs.get(tab.id).url=root+'jobs/';};
 const realGet=settling.tabs.get.bind(settling.tabs);settling.tabs.get=id=>{const tab=realGet(id);if(id===11 && tab && ++hops===2)tab.url='https://www.linkedin.com/jobs/search-results/?keywords=jobs&f_C=24242';return tab;};
 assert.equal((await read(settling)).result.company_id,'24242','an address rewritten just after load is followed before anything is read');
 const many=fixture();install(many);await many.arm();many.state.onCreated=tab=>{many.tabs.get(tab.id).url='https://www.linkedin.com/jobs/search-results/?f_C=1%2C2';};
 assert.match((await read(many)).error,/not for one company/);assert.deepEqual(many.state.removed,[11]);
 const renamed=fixture();await renamed.arm();renamed.state.fastWait=true;let readRoot='';
 renamed.state.onCreated=tab=>{renamed.tabs.get(tab.id).url='https://www.linkedin.com/company/fictional-client-group/jobs/?viewAsMember=true';};
 renamed.state.onScript=args=>{if(args.args?.[0]==='readCompanyJobsID'){readRoot=args.args[1];return [{result:{company_url:readRoot,company_id:'5151'}}];}};
 assert.deepEqual({...(await read(renamed)).result},{company_url:root,company_id:'5151'},'a canonical page name is read where LinkedIn landed');
 assert.equal(readRoot,'https://www.linkedin.com/company/fictional-client-group/');assert.deepEqual(renamed.state.removed,[11]);
 const none=fixture();install(none);await none.arm();none.state.onCreated=tab=>{none.tabs.get(tab.id).url='https://www.linkedin.com/company/fictional-client/';};
 const empty=await read(none);assert.equal(empty.error_code,'HR_COMPANY_NO_JOBS');assert.match(empty.error,/no open jobs/);assert.deepEqual(none.state.removed,[11]);
 const elsewhere=fixture();install(elsewhere);await elsewhere.arm();elsewhere.state.onCreated=tab=>{elsewhere.tabs.get(tab.id).url='https://www.linkedin.com/feed/';};
 assert.match((await read(elsewhere)).error,/different kind of page/);

 // A company page with a native CTA, and no exposed numeric link, is resolved
 // by one click in our inactive tab followed by a stable one-company search.
 const actionFixture=async(mode='success')=>{
  const a=fixture();a.state.fastWait=true;await a.arm();a.state.clicks=0;
  a.state.onScript=args=>{
   if(args.args?.[0]==='readCompanyJobsID')return [{result:{loading:true,jobs_action:true}}];
   if(args.args?.[0]===root){
    a.state.clicks++;
    if(mode==='hold')return new Promise(resolve=>{a.state.releaseAction=()=>{a.tabs.get(11).url='https://www.linkedin.com/jobs/search/?f_C=4242';resolve([{result:true}]);};});
    if(mode==='success')a.tabs.get(11).url='https://www.linkedin.com/jobs/search/?f_C=4242';
    if(mode==='many')a.tabs.get(11).url='https://www.linkedin.com/jobs/search/?f_C=1%2C2';
    if(mode==='access')a.tabs.get(11).url='https://www.linkedin.com/checkpoint/challenge/';
    if(mode==='pending'){
     const tab=a.tabs.get(11);tab.status='loading';tab.pendingUrl='https://www.linkedin.com/jobs/search/?f_C=4242';a.state.pendingTicks=5;
    }
    return [{result:mode!=='not-ready'}];
   }
  };
  if(mode==='pending'){
   const originalGet=a.tabs.get.bind(a.tabs);a.tabs.get=id=>{const tab=originalGet(id);
    if(id===11 && a.state.pendingTicks>0 && --a.state.pendingTicks===0){tab.url=tab.pendingUrl;delete tab.pendingUrl;tab.status='complete';}return tab;};
  }
  if(mode==='active')a.state.onCreated=tab=>{a.tabs.get(tab.id).active=true;};
  return a;
 };
 for(const mode of ['success','pending']){
  const a=await actionFixture(mode);const resolved=await read(a);assert.equal(resolved.result?.company_id,'4242',resolved.error);
  assert.equal(a.state.clicks,1);assert.deepEqual(a.state.removed,[11]);assert.equal(a.state.created.length,1,'native fallback never opens another automation tab');
 }
 for(const mode of ['many','access','no-navigation','not-ready','active']){
  const a=await actionFixture(mode),result=await read(a);assert(result.error,mode);
  assert.equal(a.state.clicks,mode==='active'?0:1,'one action at most, never replayed: '+mode);
  if(mode==='many')assert.match(result.error,/one company/);
  if(mode==='access')assert.equal(result.error_code,'HR_ACCESS_REQUIRED');
  if(mode==='active')assert(a.tabs.has(11),'a user-activated company tab is preserved');
  if(['no-navigation','not-ready'].includes(mode))assert.deepEqual(a.state.removed,[11]);
 }
 const stoppedAction=await actionFixture('hold'),pendingAction=read(stoppedAction);
 for(let i=0;i<100&&!stoppedAction.state.releaseAction;i++)await new Promise(resolve=>setTimeout(resolve,1));
 assert(stoppedAction.state.releaseAction);await stoppedAction.rpc('jobReadCancel',{operation_id:operation},undefined,'leads');
 stoppedAction.state.releaseAction();assert.equal((await pendingAction).error_code,'HR_STOPPED');assert.equal(stoppedAction.state.clicks,1);
 assert.deepEqual(stoppedAction.state.removed,[11],'cancellation closes our inactive action destination, even before it stabilizes');
 console.log('Company Jobs worker: scoped authority, validation, bounded loading, cancellation, post-read identity, first-load redirects (one-company search, canonical name, no-jobs page) and safe tab cleanup passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
