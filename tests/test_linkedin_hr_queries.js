const assert=require('assert/strict');
const {hrFixture}=require('./test_linkedin_company_hr');
const keywords='HR, human resources, CHRO, chief people officer, talent acquisition, TA, recruitment, hiring, recruiter, HRBP, end to end recruitment';
const words=value=>value.split(' OR ');
async function setup(country='',max_pages=15){
  const f=hrFixture(country);await f.arm();const id=(await f.beginHR({keywords,max_pages})).result.tab_id;
  f.state.hrSnapshot=()=>({people:[],signature:'',empty:true,hasNext:false});
  await f.readHR(id);
  for(let n=0;n<(country?5:1);n++){const response=await f.readHR(id);assert(!response.error,response.error);}
  f.id=id;f.next=snapshot=>f.rpc('hrNext',{run_id:f.run,tab_id:id,signature:snapshot.signature});
  return f;
}
(async()=>{
  const f=await setup('Malaysia');
  const first=new URL(f.tabs.get(f.id).url);
  assert.equal(words(first.searchParams.get('keywords')).length,5,'default HR list must not generate one oversized Boolean query');
  assert.equal(first.searchParams.get('currentCompany'),'["123"]');assert.equal(first.searchParams.get('geoUrn'),'["106808692"]');
  const visited=[];
  for(let index=0;index<3;index++){
    f.boot();const snapshot=(await f.readHR(f.id)).result;
    assert.equal(snapshot.query_index,index);assert.equal(snapshot.query_count,3);
    visited.push(...words(new URL(snapshot.source_url).searchParams.get('keywords')));
    assert.equal(snapshot.hasNext,index<2,'an empty chunk is not the end of unsearched keywords');
    assert.equal(snapshot.empty,index===2,'only the final empty chunk is terminal');
    if(index<2){
      const old=f.tabs.get(f.id).url;
      f.state.onUpdate=(id,args)=>{f.state.hrMutations.push(args.url);f.state.requested=args.url;return {...f.tabs.get(id)}};
      assert.equal((await f.next(snapshot)).result,true);
      f.boot();assert((await f.readHR(f.id)).result.loading,'wait for a new chunk without reading the old complete query');
      assert.equal(f.tabs.get(f.id).url,old);
      Object.assign(f.tabs.get(f.id),{url:f.state.requested,status:'complete'});
      assert((await f.next(snapshot)).error,'a stale prior-query signature cannot advance the next query');
    }else assert.equal((await f.next(snapshot)).result,false);
  }
  assert.deepEqual(visited,keywords.split(',').map(term=>'"'+term.trim()+'"'),'no requested terms are dropped');
  assert.equal(f.state.hrClicks.filter(x=>x.startsWith('hrCountry')).length,4,'country is chosen once, then its exact geo filter is carried between queries');
  for(const target of f.state.hrMutations){const u=new URL(target);assert.equal(u.searchParams.get('currentCompany'),'["123"]');if(u.searchParams.has('geoUrn'))assert.equal(u.searchParams.get('geoUrn'),'["106808692"]');}
  const limited=await setup('',1);const partial=(await limited.readHR(limited.id)).result;
  assert(partial.hasNext);assert(!partial.empty);assert((await limited.next(partial)).error,'query splitting shares the original total page limit');
  assert.equal(limited.state.hrMutations.length,1);
  const found=await setup();found.state.hrSnapshot=()=>({people:[{url:'https://www.linkedin.com/in/sample'}],signature:'same-person',empty:false,hasNext:false});
  const a=(await found.readHR(found.id)).result;assert.equal((await found.next(a)).result,true);
  const b=(await found.readHR(found.id)).result;assert.notEqual(a.signature,b.signature,'identical people in different keyword groups do not look like a stuck page');
  assert.equal(b.people[0].url,a.people[0].url);
  const balanced=await setup('',3);balanced.state.hrSnapshot=()=>({people:[{url:'https://www.linkedin.com/in/sample'}],signature:'same-person',empty:false,hasNext:true});
  for(let index=0;index<3;index++){
    const snapshot=(await balanced.readHR(balanced.id)).result;assert.equal(snapshot.query_index,index,'reserve a first results page for each remaining keyword group when the selected budget permits');
    if(index<2)assert.equal((await balanced.next(snapshot)).result,true);
  }
  assert(!balanced.state.hrClicks.includes('nextHRSearch'),'one busy group cannot consume the pages reserved for all other requested keywords');
  balanced.boot();balanced.state.hrSnapshot=()=>({people:[],signature:'',empty:true,hasNext:false});
  const omitted=(await balanced.readHR(balanced.id)).result;assert(omitted.hasNext);assert(!omitted.empty);assert.equal((await balanced.next(omitted)).result,false,'skipped native pages keep the scan limited after the final keyword group ends');
  const interrupted=await setup();const before=(await interrupted.readHR(interrupted.id)).result;
  interrupted.state.onUpdate=()=>{throw Error('Synthetic ambiguous navigation')};assert((await interrupted.next(before)).error);
  interrupted.boot();assert((await interrupted.readHR(interrupted.id)).error,'an ambiguous query navigation never replays after suspension');
  const changed=await setup();const prior=(await changed.readHR(changed.id)).result;changed.tabs.get(changed.id).url+='&network=F';
  assert((await changed.next(prior)).error);assert.equal(changed.state.hrMutations.length,1,'changed filters cannot authorize another query');
  const budget=await setup();budget.state.session.cvstudioLinkedinLeadsSessionV1.connection.hr.joined_count=7;budget.boot();
  const bs=(await budget.readHR(budget.id)).result;assert.equal((await budget.next(bs)).result,true);budget.boot();
  assert.equal(budget.state.session.cvstudioLinkedinLeadsSessionV1.connection.hr.joined_count,7,'switching keywords never resets the existing profile budget');
  budget.state.session.cvstudioLinkedinLeadsSessionV1.connection.hr.started=Date.now()-600001;budget.boot();
  assert((await budget.readHR(budget.id)).error,'the original ten-minute ceiling spans all keyword groups');
  const corrupt=await setup();corrupt.state.session.cvstudioLinkedinLeadsSessionV1.connection.hr.query_index=99;corrupt.boot();assert((await corrupt.readHR(corrupt.id)).error,'a restored query must be derived from the original terms');
  const takeover=await setup();const ts=(await takeover.readHR(takeover.id)).result;
  takeover.state.onPersist=data=>{if(data.cvstudioLinkedinLeadsSessionV1?.connection?.hr?.query_index===1)takeover.tabs.get(takeover.id).url='https://www.linkedin.com/in/unrelated';};
  assert((await takeover.next(ts)).error,'query authority is rechecked after its persistent checkpoint');assert.equal(takeover.state.hrMutations.length,1,'a tab taken over while saving state is never repurposed');
  const lateLoad=await setup('',3);lateLoad.state.hrSnapshot=()=>({people:[],signature:'before-load',empty:false,hasNext:true});const ls=(await lateLoad.readHR(lateLoad.id)).result;
  lateLoad.state.onPersist=data=>{if(data.cvstudioLinkedinLeadsSessionV1?.connection?.hr?.query_index===1&&!lateLoad.state.delayed){lateLoad.state.delayed=true;lateLoad.tabs.get(lateLoad.id).status='loading';}};
  assert((await lateLoad.next(ls)).result.loading);const restored=lateLoad.state.session.cvstudioLinkedinLeadsSessionV1.connection.hr;
  assert.equal(restored.query_index,0);assert.equal(restored.omitted_pages,undefined);assert.equal(lateLoad.state.hrMutations.length,1);
  lateLoad.tabs.get(lateLoad.id).status='complete';lateLoad.boot();assert.equal((await lateLoad.next(ls)).result,true,'a proven unexecuted query change restores its state and budget before retrying');
  const sanitized=hrFixture();await sanitized.arm();const sid=(await sanitized.beginHR({keywords:'HR, hr,  , "HR", recruiter, "Talent Acquisition"'})).result.tab_id;
  await sanitized.readHR(sid);assert.equal(new URL(sanitized.tabs.get(sid).url).searchParams.get('keywords'),'"HR" OR "recruiter" OR "Talent Acquisition"','duplicate and blank terms cannot inflate Boolean length');
  console.log('HR keyword queries: short bounded groups, full keyword coverage, exact company/country, empty progression, duplicate signatures, total budgets, suspension and non-replay passed');
})().catch(error=>{console.error(error);process.exitCode=1});
