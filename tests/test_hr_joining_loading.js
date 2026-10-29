const assert=require('assert/strict');
const {hrFixture}=require('./test_linkedin_company_hr');
const profile='https://www.linkedin.com/in/sample';
async function ready(){const f=hrFixture();await f.arm();const id=(await f.beginHR()).result.tab_id;await f.readHR(id);await f.readHR(id);return {f,id,read:()=>f.rpc('hrJoined',{run_id:f.run,tab_id:id,url:profile})};}
function loadOnSecondRead(f,id){
  const original=f.tabs.get.bind(f.tabs);let reads=0;
  f.tabs.get=key=>{const tab=original(key);return key===id&&++reads===2?{...tab,status:'loading',pendingUrl:tab.url}:tab};
  return ()=>{f.tabs.get=original};
}
(async()=>{
  const first=await ready();let restore=loadOnSecondRead(first.f,first.id);
  assert.equal((await first.read()).result?.loading,true,'same-source loading between initial metadata and joining verification waits');
  assert.equal(first.f.state.created.length,1,'no profile opens while source readiness is unknown');
  assert.equal(first.f.state.session.cvstudioLinkedinLeadsSessionV1.connection.hr.joined_count||0,0);
  restore();first.f.boot();assert.equal((await first.read()).result.wait_stage,'profile_navigation');
  assert.equal((await first.read()).result.joined,'2020-06');assert.equal(first.f.state.created.length,2);

  const injection=await ready();await injection.read();
  injection.f.state.onInject=()=>{injection.f.tabs.get(injection.id).status='loading'};
  assert((await injection.read()).result?.loading,'same-source loading after reader injection waits');
  assert.equal(injection.f.state.joinedReads||0,0,'no date is read before source readiness returns');
  injection.f.state.onInject=null;injection.f.tabs.get(injection.id).status='complete';injection.f.boot();
  assert.equal((await injection.read()).result.joined,'2020-06');assert.equal(injection.f.state.created.length,2,'resuming reuses the same owned profile');

  const after=await ready();await after.read();const script=after.f.state.onScript;
  after.f.state.onScript=args=>{const result=script(args);if(Array.isArray(args.args?.[0]))after.f.tabs.get(after.id).status='loading';return result};
  assert((await after.read()).result?.loading,'a result is not returned while source readiness changed after reading');
  assert(after.f.tabs.has(12),'the owned lookup remains available for bounded read-only polling');
  after.f.state.onScript=script;after.f.tabs.get(after.id).status='complete';
  assert.equal((await after.read()).result.joined,'2020-06');assert.equal(after.f.state.created.length,2);

  const cleanup=await ready();await cleanup.read();cleanup.f.tabs.get(cleanup.id).status='loading';
  assert.equal((await cleanup.f.rpc('hrJoinedClose',{run_id:cleanup.f.run,tab_id:cleanup.id})).result,true,'optional lookup cleanup is safe during an unchanged source load');
  assert(!cleanup.f.tabs.has(12));assert(!cleanup.f.state.session.cvstudioLinkedinLeadsSessionV1.connection.hr.joining);
  cleanup.f.tabs.get(cleanup.id).status='complete';assert((await cleanup.read()).result.loading,'cleanup does not leave the next profile falsely interrupted');

  for(const key of ['currentCompany','geoUrn','keywords']){
    const changed=await ready();const tab=changed.f.tabs.get(changed.id),url=new URL(tab.url);
    url.searchParams.set(key,key==='keywords'?'Changed words':'["999"]');tab.status='loading';tab.pendingUrl=url.href;
    assert((await changed.read()).error,'real pending filter changes still stop date checks: '+key);
    assert.equal(changed.f.state.created.length,1);
  }
  console.log('HR joining dates: same-source readiness races wait, profile/budget survive suspension, cleanup completes, real filter changes remain blocked');
})().catch(error=>{console.error(error);process.exit(1)});
