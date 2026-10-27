const assert=require('assert/strict'),{hrFixture}=require('./test_linkedin_company_hr');
function groupFixture(country='') {
  const f=hrFixture(country),original=f.state.onScript;
  f.state.onScript=args=>{
    const method=args.args?.[0];
    if(method==='readHRCompany')return [{result:{loading:true,company_ids:['123','456','789']}}];
    if(['hrCompanyOpen','hrCompanyOnly','hrCompanyApply'].includes(method)) {
      f.state.hrClicks.push(method);
      if(f.state.groupInterrupted)throw Error('Fictional interrupted filter');
      if(f.state.groupMissing)return [{result:{hrError:'layout'}}];
      if(method==='hrCompanyApply') {
        const tab=f.tabs.get(args.target.tabId),url=new URL(tab.url);url.searchParams.set('currentCompany',JSON.stringify([f.state.wrongGroup?'999':'456']));
        if(f.state.changedKeywords)url.searchParams.set('keywords','unrelated');
        tab.url=url.href;
        if(f.state.intermediate){f.state.finalURL=tab.url;tab.url='https://www.linkedin.com/search/results/people/?origin=FACETED_SEARCH';}
      }
      return [{result:true}];
    }
    return original(args);
  };
  return f;
}
(async()=>{
  for(const country of ['', 'Malaysia']) {
    const f=groupFixture(country);await f.arm();const source=(await f.beginHR()).result.tab_id;
    let result;for(let i=0;i<16;i++){f.boot();result=await f.readHR(source);assert(!result.error,result.error);if(!result.result.loading)break;}
    assert.equal(result.result.company_id,'456');assert.deepEqual(JSON.parse(new URL(result.result.source_url).searchParams.get('currentCompany')),['456']);
    assert(f.state.hrClicks.includes('hrCompanyOnly'));assert.equal(f.state.hrReads,1,'group results are never inspected before exact company confirmation');
    if(country)assert.equal(JSON.parse(new URL(result.result.source_url).searchParams.get('geoUrn'))[0],'106808692');
  }
  for(const failure of ['groupInterrupted','groupMissing','wrongGroup','changedKeywords']) {
    const f=groupFixture();f.state[failure]=true;await f.arm();const source=(await f.beginHR()).result.tab_id;
    let response;for(let i=0;i<9;i++){response=await f.readHR(source);if(response.error)break;}
    assert(response.error,failure+' must stop before reading people');assert.equal(f.state.hrReads,0);
    if(failure==='groupInterrupted'){f.boot();assert((await f.readHR(source)).error);assert.equal(f.state.hrClicks.length,1,'an ambiguous mutation never replays after suspension');}
  }
  const delayed=groupFixture();delayed.state.intermediate=true;await delayed.arm();const source=(await delayed.beginHR()).result.tab_id;
  for(let i=0;i<5;i++)assert(!(await delayed.readHR(source)).error);
  assert.equal(delayed.state.hrReads,0);delayed.tabs.get(source).url=delayed.state.finalURL;
  let snapshot;for(let i=0;i<4;i++){snapshot=await delayed.readHR(source);if(snapshot.result&&!snapshot.result.loading)break;}
  assert.equal(snapshot.result.company_id,'456');
  console.log('Company group worker: native-only selection, non-first exact ID, country gates, suspension, transient URLs and no premature profile reads passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
