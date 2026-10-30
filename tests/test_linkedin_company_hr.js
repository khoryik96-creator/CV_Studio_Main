const assert=require('assert/strict');
const {fixture}=require('./test_linkedin_job_search');
const companyURL='https://www.linkedin.com/company/example/';
function hrFixture(country='',options={}){
  const f=fixture(options);Object.assign(f.state,{hrClicks:[],hrMutations:[],hrReads:0,country});
  f.state.onUpdate=(id,args)=>{assert(id>=11,'only newly created HR source is navigated');f.state.hrMutations.push(args.url);Object.assign(f.tabs.get(id),args);return {...f.tabs.get(id)}};
  f.state.onScript=args=>{
    if(!args.args||args.files)return;
    const [method]=args.args;
    if(method==='readHRCompany')return [{result:f.state.badCompany?{hrError:'layout'}:{company_id:'123'}}];
    if(method==='readHRSearch'){
      f.state.hrReads++;
      if(f.state.hrSnapshot)return [{result:f.state.hrSnapshot()}];
      return [{result:{people:[{url:'https://www.linkedin.com/in/sample'}],signature:'one',hasNext:true,empty:false}}];
    }
    if(Array.isArray(method)) {
      f.state.joinedReads=(f.state.joinedReads||0)+1;
      if(f.state.joinedNull)return [{result:null}];
      return [{result:f.state.employment || {joined:f.state.joinedBad?'2024-13':'2020-06'}}];
    }
    if(method==='https://www.linkedin.com/in/sample'){f.state.profileScrolls=(f.state.profileScrolls||0)+1;return [{result:true}];}
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
module.exports={hrFixture};
if(require.main===module)(async()=>{
  const delayed=hrFixture();await delayed.arm();const delayId=(await delayed.beginHR()).result.tab_id;
  delayed.state.onUpdate=(id,args)=>{delayed.state.hrMutations.push(args.url);delayed.state.requested=args.url;return {...delayed.tabs.get(id),pendingUrl:args.url}};
  assert((await delayed.readHR(delayId)).result.loading);
  delayed.boot();
  assert.equal((await delayed.readHR(delayId)).result?.loading,true,'tabs.update can return while the previous company page is still complete');
  delayed.tabs.get(delayId).pendingUrl=delayed.state.requested;
  assert.equal((await delayed.readHR(delayId)).result?.loading,true,'the exact requested pending People search is awaited');
  assert.equal(delayed.state.hrReads,0);assert.equal(delayed.state.hrMutations.length,1,'waiting never repeats navigation');
  Object.assign(delayed.tabs.get(delayId),{url:delayed.state.requested,pendingUrl:undefined,status:'complete'});
  delayed.boot();assert((await delayed.readHR(delayId)).result?.people,'reading resumes only after the requested company and keyword search commits');
  delayed.tabs.get(delayId).url=companyURL+'people/';
  assert((await delayed.readHR(delayId)).error,'returning to the old company page after the search is ready is not a loading transition');
  const loading=hrFixture('Malaysia');await loading.arm();const loadingId=(await loading.beginHR()).result.tab_id;await loading.readHR(loadingId);
  loading.state.onInject=()=>{loading.tabs.get(loadingId).status='loading'};
  assert.equal((await loading.readHR(loadingId)).result?.loading,true,'same-search loading during injection waits before any filter click');
  assert.equal(loading.state.hrClicks.length,0);loading.boot();loading.state.onInject=null;loading.tabs.get(loadingId).status='complete';
  assert((await loading.readHR(loadingId)).result?.loading);assert.deepEqual(loading.state.hrClicks,['hrCountryOpen'],'a deferred, unexecuted action runs once');
  const pageWait=hrFixture();await pageWait.arm();const pageId=(await pageWait.beginHR()).result.tab_id;await pageWait.readHR(pageId);await pageWait.readHR(pageId);
  pageWait.state.onInject=()=>{pageWait.tabs.get(pageId).status='loading'};
  assert.equal((await pageWait.nextHR(pageId)).result?.loading,true);assert.equal(pageWait.state.hrClicks.length,0);
  pageWait.boot();pageWait.state.onInject=null;pageWait.tabs.get(pageId).status='complete';
  assert.equal((await pageWait.nextHR(pageId)).result,true,'an unexecuted loading wait does not consume the page budget');
  assert.deepEqual(pageWait.state.hrClicks,['nextHRSearch']);
  assert((await pageWait.nextHR(pageId)).error,'a completed next-page click still consumes its persisted budget');
  for(const target of ['https://www.linkedin.com/search/results/people/?currentCompany=%5B%22999%22%5D','https://www.linkedin.com/login']){
    const wrongPending=hrFixture();await wrongPending.arm();const source=(await wrongPending.beginHR()).result.tab_id;
    wrongPending.state.onUpdate=(id,args)=>{wrongPending.state.requested=args.url;return {...wrongPending.tabs.get(id)}};
    await wrongPending.readHR(source);wrongPending.tabs.get(source).pendingUrl=target;
    assert((await wrongPending.readHR(source)).error,'an unrelated pending navigation must not be accepted as the requested transition');
    assert.equal(wrongPending.state.hrReads,0);
  }
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
  const dates=hrFixture();await dates.arm();const di=(await dates.beginHR()).result.tab_id;await dates.readHR(di);await dates.readHR(di);
  const dateRead=(url='https://www.linkedin.com/in/sample')=>dates.rpc('hrJoined',{run_id:dates.run,tab_id:di,url});
  assert((await dateRead('https://www.linkedin.com/in/unobserved')).error);assert.equal(dates.state.created.length,1);
  assert((await dateRead()).result.loading);assert.equal(dates.state.created.length,2);const pi=dates.state.created.length+10;
  dates.boot();assert((await dates.nextHR(di)).error,'cannot page while an HR profile read is pending');
  assert.equal((await dateRead()).result.joined,'2020-06');assert(dates.state.removed.includes(pi));
  assert(!dates.state.session.cvstudioLinkedinLeadsSessionV1.connection.hr.joining);
  assert.equal(dates.state.session.cvstudioLinkedinLeadsSessionV1.connection.hr.joined_count,1);
  assert(!JSON.stringify(dates.state.session).includes('2020-06'),'dates and captured profile content do not enter worker session state');
  assert.equal((await dates.rpc('hrJoinedClose',{run_id:dates.run,tab_id:di})).result,true);
  const takeover=hrFixture();await takeover.arm();const ti=(await takeover.beginHR()).result.tab_id;await takeover.readHR(ti);await takeover.readHR(ti);
  const tr=()=>takeover.rpc('hrJoined',{run_id:takeover.run,tab_id:ti,url:'https://www.linkedin.com/in/sample'});
  await tr();takeover.tabs.get(12).active=true;assert.equal((await tr()).result.joined,'2020-06');await takeover.end();assert(takeover.tabs.has(12),'viewing permits exact-profile reads but never cleanup');
  const interrupted=hrFixture();await interrupted.arm();const ii=(await interrupted.beginHR()).result.tab_id;await interrupted.readHR(ii);await interrupted.readHR(ii);
  interrupted.state.session.cvstudioLinkedinLeadsSessionV1.connection.hr.joining={url:'https://www.linkedin.com/in/sample',tab_id:null};interrupted.boot();
  assert((await interrupted.rpc('hrJoined',{run_id:interrupted.run,tab_id:ii,url:'https://www.linkedin.com/in/sample'})).error);assert.equal(interrupted.state.created.length,1,'ambiguous creation cannot reopen a profile');
  const limit=hrFixture();await limit.arm();const li=(await limit.beginHR()).result.tab_id;await limit.readHR(li);await limit.readHR(li);
  limit.state.session.cvstudioLinkedinLeadsSessionV1.connection.hr.joined_count=100;limit.boot();
  assert((await limit.rpc('hrJoined',{run_id:limit.run,tab_id:li,url:'https://www.linkedin.com/in/sample'})).error);assert.equal(limit.state.created.length,1);
  const drift=hrFixture();await drift.arm();const si=(await drift.beginHR()).result.tab_id;await drift.readHR(si);await drift.readHR(si);
  const sr=()=>drift.rpc('hrJoined',{run_id:drift.run,tab_id:si,url:'https://www.linkedin.com/in/sample'});await sr();
  drift.state.onInject=()=>{drift.tabs.get(12).url='https://www.linkedin.com/in/another'};
  assert((await sr()).error);assert.equal(drift.state.joinedReads||0,0,'owned profile identity is checked after reader injection');
  await drift.end();assert(drift.tabs.has(12),'an unrelated redirect is retained');
  const stale=hrFixture();await stale.arm();const sti=(await stale.beginHR()).result.tab_id;await stale.readHR(sti);await stale.readHR(sti);
  stale.tabs.get(sti).url+='&network=%5B%22F%22%5D';
  assert((await stale.rpc('hrJoined',{run_id:stale.run,tab_id:sti,url:'https://www.linkedin.com/in/sample'})).error);assert.equal(stale.state.created.length,1);
  const unreadable=hrFixture();await unreadable.arm();const ui=(await unreadable.beginHR()).result.tab_id;await unreadable.readHR(ui);await unreadable.readHR(ui);
  const ur=()=>unreadable.rpc('hrJoined',{run_id:unreadable.run,tab_id:ui,url:'https://www.linkedin.com/in/sample'});await ur();unreadable.state.joinedNull=true;unreadable.boot();assert((await ur()).result.loading);
  for(let n=0;n<7;n++){unreadable.boot();assert((await ur()).result.loading);}
  assert.equal(unreadable.state.profileScrolls,4,'lazy Experience scroll budget persists across suspension');
  assert.equal(unreadable.state.created.length,2,'null/loading reads poll the same owned profile');
  await unreadable.rpc('hrJoinedClose',{run_id:unreadable.run,tab_id:ui});assert(unreadable.state.removed.includes(12));
  for(const reason of ['navigate','remove','restore_missing','restore_changed'])for(const ownership of ['owned','pending','taken_over','redirected','other_pending']){
    const cleanup=hrFixture();await cleanup.arm();const source=(await cleanup.beginHR()).result.tab_id;await cleanup.readHR(source);await cleanup.readHR(source);
    await cleanup.rpc('hrJoined',{run_id:cleanup.run,tab_id:source,url:'https://www.linkedin.com/in/sample'});
    const profile=cleanup.tabs.get(12);
    if(ownership==='pending')Object.assign(profile,{url:'about:blank',pendingUrl:'https://www.linkedin.com/in/sample/details/experience/',status:'loading'});
    if(ownership==='taken_over'){profile.active=true;await cleanup.hooks().activated({tabId:12});profile.active=false;}
    if(ownership==='redirected'){profile.url='https://www.linkedin.com/in/other';await cleanup.hooks().updated(12,{url:profile.url});}
    if(ownership==='other_pending')profile.pendingUrl='https://www.linkedin.com/in/other';
    if(reason==='navigate'){cleanup.tabs.get(1).status='loading';await cleanup.hooks().updated(1,{status:'loading'});}
    if(reason==='remove'){cleanup.tabs.delete(1);await cleanup.hooks().removed(1);}
    if(reason==='restore_missing'){cleanup.tabs.delete(1);cleanup.boot();}
    if(reason==='restore_changed'){cleanup.state.document='replacement';cleanup.boot();}
    const sender={tab:{id:1},documentId:'bound',url:'http://127.0.0.1:5000/'};
    assert((await cleanup.rpc('jobStatus',{},sender)).error);
    const shouldClose=['owned','pending'].includes(ownership);
    assert.equal(cleanup.state.removed.includes(12),shouldClose,reason+'/'+ownership+' closes only inactive, unchanged HR-owned tabs');
    assert(cleanup.tabs.has(source),'the company search remains open');
    assert.equal(cleanup.state.session.cvstudioLinkedinLeadsSessionV1.connection,null);
    assert.equal(cleanup.state.session.cvstudioLinkedinLeadsSessionV1.owned.length,0);
  }
  const opening=hrFixture();await opening.arm();const os=(await opening.beginHR()).result.tab_id;await opening.readHR(os);await opening.readHR(os);
  opening.state.onCreated=tab=>new Promise(resolve=>{
    Object.assign(tab,{url:'about:blank',pendingUrl:'https://www.linkedin.com/in/sample/details/experience/',status:'loading'});
    opening.state.finishCreate=resolve;
  });
  const pending=opening.rpc('hrJoined',{run_id:opening.run,tab_id:os,url:'https://www.linkedin.com/in/sample'});
  for(let n=0;n<20&&!opening.state.finishCreate;n++)await new Promise(resolve=>setTimeout(resolve,0));
  assert(opening.state.finishCreate);await opening.hooks().updated(1,{status:'loading'});opening.state.finishCreate();
  assert((await pending).error);assert(opening.state.removed.includes(12),'a late-created pending tab is cleaned after its HR app document disappears');
  console.log('Company HR worker: exact document/company/country/source, bounded pages, suspension, mutation non-replay, competing runs and retained source passed');
})().catch(error=>{console.error(error);process.exitCode=1});
