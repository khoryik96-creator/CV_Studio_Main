const assert=require('assert/strict');
const {bulkFixture,held}=require('./test_bulk_hr_frontend');
const {hrFixture}=require('./test_job_hr_frontend');
const key='cvstudio_job_leads_hr_queue_v1';
const company=n=>'Example Company '+n;
async function stopped(options={}){
  const f=bulkFixture(options);await f.init();f.select();f.state.holdId='2'.repeat(32);
  const run=f.start();await held(f);f.el('BulkHRStop').click();f.state.release();await run;f.state.holdId='';return f;
}
(async()=>{
  const f=await stopped();assert.equal(f.state.starts.length,2);
  assert.equal(f.el('BulkHRStart').textContent,'Resume unfinished ads');
  await f.start();assert.deepEqual(f.state.starts.slice(2).map(x=>x.company),[company(2),company(3)]);
  assert.equal(f.requests.filter(r=>r.action==='save_hr').length,3);assert.equal(f.el('BulkHRBar').value,3);
  assert.equal(f.el('BulkHRStart').textContent,'Scan selected ads');
  await f.start();assert.equal(f.state.starts.length,7,'a completed batch can be deliberately scanned afresh');

  const failure=bulkFixture();await failure.init();failure.select();failure.state.failId='2'.repeat(32);await failure.start();
  failure.state.failId='';await failure.start();assert.deepEqual(failure.state.starts.map(x=>x.company),[company(1),company(3),company(2)],'only the failed ad is retried after other ads saved');
  assert.equal(failure.el('BulkHRBar').value,3);

  const prefs=new Map(),before=await stopped({preferences:prefs});
  const checkpoint=JSON.parse(prefs.get(key));assert.equal(checkpoint.items[0].state,'saved');
  assert(!prefs.get(key).includes('Example Company'));assert(!prefs.get(key).includes('linkedin.com'));assert(!prefs.get(key).includes('email'));
  const reloaded=bulkFixture({preferences:prefs});reloaded.state.records=structuredClone(before.state.records);await reloaded.init();reloaded.select();
  await reloaded.start();assert.deepEqual(reloaded.state.starts.map(x=>x.company),[company(2),company(3)],'an explicit resumed scan after reload skips confirmed saves');

  const changed=await stopped();changed.el('BulkHRPages').value='10';changed.el('BulkHRPages').handlers.change();assert.equal(changed.el('BulkHRStart').textContent,'Scan selected ads');await changed.start();
  assert.deepEqual(changed.state.starts.slice(2).map(x=>x.company),[company(1),company(2),company(3)],'different scan settings request a fresh batch');
  const revised=await stopped();revised.state.records[0].revision++;await revised.el('Refresh').click();revised.select();await revised.start();
  assert.deepEqual(revised.state.starts.slice(2).map(x=>x.company),[company(2),company(3),company(1)],'changed saved ads need rescan, after unfinished ads');
  for(const raw of ['{bad',JSON.stringify({version:1,items:[{id:'bad',state:'saved'}]})]){
    const safe=bulkFixture({preferences:new Map([[key,raw]])});await safe.init();safe.select();await safe.start();assert.equal(safe.state.starts.length,3,'corrupt checkpoint cannot silently skip ads');
  }
  const unavailable=await stopped({storage:{getItem:()=>null,setItem:()=>{throw Error('Storage unavailable')},removeItem:()=>{}}});
  await unavailable.start();assert.deepEqual(unavailable.state.starts.slice(2).map(x=>x.company),[company(2),company(3)],'same-page resume survives unavailable browser storage');

  const dates=hrFixture();await dates.init();Object.assign(dates.state,{twoPeople:true,holdJoined:true,holdJoinedSecond:true,joined:'2026-10',employment:{left:'',current:true}});
  const run=dates.el('HRStart').click();for(let i=0;i<40&&!dates.state.releaseJoined;i++)await new Promise(r=>setTimeout(r,0));assert(dates.state.releaseJoined);
  assert.equal(dates.el('HRResults').children[0].children[3].textContent,'Employment: Oct 2026 to Present','first date appears before the second profile/page finishes');
  assert.equal(dates.el('HRResults').children[1].children[3].textContent,'Employment: Checking…');
  dates.el('HRStop').click();dates.state.releaseJoined();await run;
  assert.equal(dates.el('HRResults').children[0].children[3].textContent,'Employment: Oct 2026 to Present');
  assert.equal(dates.el('HRResults').children[1].children[3].textContent,'Employment: Not checked');
  assert(!dates.requests.some(r=>r.action==='save_hr'),'stopped partial evidence is not presented as saved');
  const immediate=hrFixture();await immediate.init();Object.assign(immediate.state,{holdDateCleanup:true,joined:'2026-10',employment:{left:'',current:true}});
  const reading=immediate.el('HRStart').click();for(let i=0;i<40&&!immediate.state.releaseDateCleanup;i++)await new Promise(r=>setTimeout(r,0));assert(immediate.state.releaseDateCleanup);
  assert.equal(immediate.el('HRResults').children[0].children[3].textContent,'Employment: Oct 2026 to Present','the date appears before cleanup/another person/page');
  immediate.el('HRStop').click();immediate.state.releaseDateCleanup();await reading;assert(!immediate.requests.some(r=>r.action==='save_hr'));
  const slow=hrFixture();await slow.init();slow.state.joinedNavigationWaits=25;await slow.el('HRStart').click();
  assert.equal(slow.state.records[0].hr.people[0].joined,'2020-06','profile navigation does not consume the Experience metadata budget');
  const hung=hrFixture();await hung.init();hung.state.joinedNavigationWaits=1000;await hung.el('HRStart').click();
  assert.equal(hung.calls.filter(x=>x.action==='hrJoined').length,60,'slow navigation stays bounded and optional');
  const alternating=hrFixture();await alternating.init();const rpc=alternating.state.onRPC;let waits=0;
  alternating.state.onRPC=(message,reply)=>message.action==='hrJoined'?(reply({loading:true,wait_stage:++waits%4?'profile_navigation':'profile_experience'}),true):rpc(message,reply);
  await alternating.el('HRStart').click();assert.equal(waits,79,'alternating stages cannot reset the separate or total budgets');
  console.log('HR retry: saved ads skipped, failed/stopped/changed ads ordered, explicit restart/settings/reload/corruption/storage guards, immediate dates and bounded navigation passed');
})().catch(error=>{console.error(error);process.exitCode=1});
