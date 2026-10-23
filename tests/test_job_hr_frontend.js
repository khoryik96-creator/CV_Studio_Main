const assert=require('assert/strict');
const {fixture}=require('./test_job_search_frontend');
const profile={name:'Sample <Person>',title:'HR Business Partner',location:'Malaysia',url:'https://www.linkedin.com/in/sample',matched:'HR'};
const companyURL='https://www.linkedin.com/company/example/';
function hrFixture(){
  const f=fixture();Object.assign(f.state,{hrPage:0,hrSeen:0});
  f.state.onRPC=(message,reply)=>{
    const {action,args}=message;
    if(action==='jobStatus'){reply({connected:true,company_hr_revision:f.state.oldCompanion?0:1,hr_joined_revision:1,busy:!!f.state.hrBusy});return true;}
    if(action==='hrJoined'){
      const value=f.state.joinedLoading?{loading:true}:{url:args.url,joined:f.state.joined ?? '2020-06'};
      if(f.state.holdJoined)f.state.releaseJoined=()=>reply(value);else reply(value);
      return true;
    }
    if(action==='hrJoinedClose'){reply(true);return true;}
    if(action==='jobFromLink'){reply({...f.state.records[0],company_url:companyURL});return true;}
    if(action==='hrBegin'){f.state.hrArgs=args;reply({tab_id:30});return true;}
    if(action==='hrNext'){f.state.hrPage++;reply(true);return true;}
    if(action==='hrRead'){
      f.state.hrSeen++;
      if(f.state.loading&&f.state.hrSeen===1){reply({loading:true});return true;}
      const snapshot={company_id:'123',source_url:'https://www.linkedin.com/search/results/people/?currentCompany=%5B%22123%22%5D'+(f.state.hrArgs.country?'&geoUrn=%5B%22106808692%22%5D':''),people:[profile],signature:'page'+f.state.hrPage,hasNext:f.state.hrPage===0,empty:false};
      if(f.state.capCase){
        const count=f.state.capCase==='exact'&&f.state.hrPage===2?20:40;
        snapshot.people=Array.from({length:count},(_,i)=>({...profile,url:profile.url+'-'+(f.state.capCase==='duplicates'&&f.state.hrPage===2&&i>=20?i:f.state.hrPage*40+i)}));
        snapshot.hasNext=f.state.hrPage<2;
      }
      if(f.state.bad)snapshot.people=[{...profile,url:'javascript:bad'}];
      if(f.state.hold){f.state.release=()=>reply(snapshot);return true;}
      reply(snapshot);return true;
    }
    return false;
  };
  f.state.onRequest=async data=>{
    if(data.action!=='save_hr')return;
    if(f.state.conflict)return {ok:false,json:async()=>({error:'Ad changed during scan'})};
    const row=f.state.records[0];assert.equal(data.revision,row.revision);
    row.hr={...data.search,scanned_at:'2026-10-22T00:00:00Z'};row.revision++;
    return {ok:true,json:async()=>({record:structuredClone(row)})};
  };
  return f;
}
(async()=>{
  const f=hrFixture();await f.init();
  assert(!f.el('HR').hidden);assert.equal(f.el('HRCountryMode').value,'');
  await f.el('PreviewRead').click();assert(!f.el('HR').hidden,'temporary full-ad capture must retain the saved ad HR column');
  f.el('notes').value='Unsaved draft stays';
  f.state.loading=true;await f.el('HRStart').click();
  assert.equal(f.state.hrArgs.country,'');assert.match(f.state.hrArgs.keywords,/CHRO/);
  assert.equal(f.state.hrArgs.company,f.state.records[0].company);assert.equal(f.state.hrArgs.company_url,companyURL);
  assert.equal(f.state.hrSeen,3);assert.equal(f.requests.filter(x=>x.action==='save_hr').length,1);
  assert.equal(f.state.records[0].hr.people.length,1,'profiles deduplicate across pages');
  assert.equal(f.el('notes').value,'Unsaved draft stays');assert.match(f.el('HRMessage').textContent,/1 HR matches saved/);
  assert.equal(f.el('HRResults').children[0].children[0].textContent,'Sample <Person>','names remain text');
  assert.equal(f.el('HRResults').children[0].children[3].textContent,'Joined company: Jun 2020');
  assert.equal(f.state.records[0].hr.people[0].joined,'2020-06');
  assert.equal(f.calls.filter(x=>x.action==='hrJoined').length,1,'duplicate pages do not re-open profiles');
  assert(f.calls.some(x=>x.action==='end'));
  f.el('HRCountryMode').value='specific';f.el('HRCountryMode').handlers.change();assert(!f.el('HRCountry').hidden);
  f.el('HRCountry').value='Singapore';await f.el('HRStart').click();assert.equal(f.state.hrArgs.country,'Singapore');
  f.state.records[0].hr.people=[{...profile,name:'Changed in another window'}];f.state.records[0].revision++;
  await f.el('Refresh').click();assert.equal(f.el('HRResults').children[0].children[0].textContent,'Changed in another window','explicit Refresh loads newer saved HR evidence');
  f.state.records[0].hr.complete=false;f.state.records[0].revision++;await f.el('Refresh').click();assert.match(f.el('HRMessage').textContent,/Limited scan/);
  for(const kind of ['oldCompanion','hrBusy','bad','conflict']){
    const g=hrFixture();await g.init();g.state[kind]=true;await g.el('HRStart').click();
    assert(!g.state.records[0].hr,kind+' must not persist partial/unverified results');
    assert.match(g.el('HRMessage').textContent,/Previous saved results/);
    if(['oldCompanion','hrBusy'].includes(kind))assert(!g.calls.some(x=>x.action==='hrBegin'));
  }
  const stopped=hrFixture();await stopped.init();stopped.state.hold=true;
  const run=stopped.el('HRStart').click();for(let n=0;n<20&&!stopped.state.release;n++)await new Promise(resolve=>setTimeout(resolve,0));
  assert(stopped.state.release);
  for(const id of ['Search','Filter','FolderFilter'])assert(stopped.el(id).disabled,'HR scan keeps its visible saved-ad context fixed');
  stopped.el('HRStop').click();stopped.state.release();await run;
  for(const id of ['Search','Filter','FolderFilter'])assert(!stopped.el(id).disabled);
  assert(!stopped.requests.some(x=>x.action==='save_hr'));assert(stopped.calls.some(x=>x.action==='end'));
  assert.match(stopped.el('HRMessage').textContent,/Scan stopped/);
  const trash=hrFixture();trash.state.records[0].deleted=true;trash.el('FolderFilter').value='!trash';await trash.init();
  assert(trash.el('HR').hidden);assert(trash.el('HRStart').disabled);
  const year=hrFixture();await year.init();year.state.joined='2023';await year.el('HRStart').click();
  assert.equal(year.el('HRResults').children[0].children[3].textContent,'Joined company: 2023');
  delete year.state.records[0].hr.people[0].joined;year.state.records[0].revision++;await year.el('Refresh').click();
  assert.equal(year.el('HRResults').children[0].children[3].textContent,'Joined company: Not available','older records still render safely');
  const missing=hrFixture();await missing.init();missing.state.joinedLoading=true;await missing.el('HRStart').click();
  assert.equal(missing.state.records[0].hr.people[0].joined,'','optional missing Experience does not lose valid HR people');
  assert.equal(missing.calls.filter(x=>x.action==='hrJoined').length,20,'loading lookup has a bounded poll count');
  assert(missing.calls.some(x=>x.action==='hrJoinedClose'));
  const unloaded=hrFixture();await unloaded.init();unloaded.state.holdJoined=true;
  const unloading=unloaded.el('HRStart').click();for(let n=0;n<20&&!unloaded.state.releaseJoined;n++)await new Promise(resolve=>setTimeout(resolve,0));
  assert(unloaded.state.releaseJoined);unloaded.pagehide();
  assert(unloaded.calls.some(x=>x.action==='end'&&x.args.run_id===unloaded.state.hrArgs.run_id),'pagehide ends the exact active HR run without waiting for a profile read');
  unloaded.state.releaseJoined();await unloading;assert(!unloaded.requests.some(x=>x.action==='save_hr'),'an unloaded attempt cannot save later');
  for(const kind of ['overflow','exact','duplicates']){
    const cap=hrFixture();await cap.init();cap.state.capCase=kind;await cap.el('HRStart').click();
    assert.equal(cap.state.records[0].hr.people.length,100);
    assert.equal(cap.calls.filter(x=>x.action==='hrJoined').length,100,'result ceiling also bounds profile lookups');
    assert.equal(cap.state.records[0].hr.complete,kind!=='overflow','only omitted unique profiles make the final page incomplete');
    assert.match(cap.el('HRMessage').textContent,kind==='overflow'?/limit reached/:/No further results/);
    cap.el('PreviewClose').click();await cap.el('Refresh').click();
    cap.el('List').querySelectorAll('button').find(button=>button.textContent.startsWith('HR people')).click();
    assert.equal(cap.el('HRMessage').textContent.includes('Limited scan'),kind==='overflow','saved incomplete status survives reopening');
  }
  console.log('Company HR UI: company-scoped requests, countries, paging/dedup, saved evidence, XSS text, draft preservation, Stop, old/busy companion, invalid profiles and stale-write failures passed');
})().catch(error=>{console.error(error);process.exitCode=1});
