const assert=require('assert/strict');
const {fixture}=require('./test_job_search_frontend');
const preference='cvstudio_job_leads_hr_preferences';
function bulkFixture(options={}){
  const f=fixture(options),base=f.state.records[0];
  f.state.records=[1,2,3].map(n=>({...structuredClone(base),id:String(n).repeat(32),url:'https://www.linkedin.com/jobs/view/111111111'+n,company:'Example Company '+n,role:'Example role '+n,hr:{people:[],country:'Singapore',keywords:'HR',company_url:'',complete:true}}));
  Object.assign(f.state,{active:null,ends:[],starts:[]});
  f.state.onRPC=(message,reply)=>{
    const {action,args}=message,s=f.state;
    if(action==='jobStatus'){reply({connected:!s.disconnected,company_hr_revision:1,hr_company_identity_revision:1,hr_joined_revision:1,hr_joined_loading_revision:1,hr_keyword_revision:1,busy:false});return true;}
    if(action==='jobFromLink'){
      const row=s.records.find(r=>r.url===args.url);s.active=row;
      if(row.id===s.failId){reply(null,'The company link is unavailable.');return true;}
      reply({url:row.url,company:row.company,company_url:'https://www.linkedin.com/company/example-'+row.id[0]+'/'});return true;
    }
    if(action==='hrBegin'){s.starts.push({...args});reply({tab_id:30});return true;}
    if(action==='hrRead'){
      const row=s.active,person={url:'https://www.linkedin.com/in/example-'+row.id[0],name:'Example Person '+row.id[0],title:'HR Business Partner',location:'Malaysia',matched:'HR'};
      const value={company_id:row.id[0],source_url:'https://www.linkedin.com/search/results/people/?currentCompany=%5B%22'+row.id[0]+'%22%5D',people:[person],signature:'one',hasNext:false,empty:false};
      if(row.id===s.holdId){s.release=()=>reply(value);return true;}
      reply(value);return true;
    }
    if(action==='hrJoined'){reply({url:args.url,joined:'2020-06'});return true;}
    if(action==='hrJoinedClose'){reply(true);return true;}
    if(action==='end'){
      s.ends.push(args.run_id);if(s.active?.id===s.cleanupFailId)reply(null,'Companion cleanup failed.');else reply(true);return true;
    }
  };
  f.state.onRequest=async data=>{
    if(data.action!=='save_hr')return;
    const row=f.state.records.find(r=>r.id===data.id);assert.equal(data.search.company,row.company);assert.equal(data.revision,row.revision);
    if(row.id===f.state.staleId)return {ok:false,json:async()=>({error:'Ad changed during scan',code:'JOB_LEADS_CONFLICT'})};
    row.hr={...data.search,scanned_at:'2026-10-27T00:00:00Z'};row.revision++;
    if(row.id===f.state.disconnectAfter)f.state.disconnected=true;
    return {ok:true,json:async()=>({record:structuredClone(row)})};
  };
  f.select=()=>{f.el('SelectPage').checked=true;f.el('SelectPage').handlers.change();};
  f.start=()=>f.el('BulkHRStart').click();
  return f;
}
async function held(f){for(let i=0;i<40&&!f.state.release;i++)await new Promise(r=>setTimeout(r,0));assert(f.state.release,'a scan is in flight');}
(async()=>{
  const f=bulkFixture({preferences:new Map([[preference,JSON.stringify({countryMode:'specific',country:'Malaysia',pages:10})]])});await f.init();f.select();
  assert.equal(typeof f.el('BulkHRStart').handlers.click,'function','selected ads have a bulk HR action');
  assert.equal(f.el('BulkHRCountry').value,'Malaysia');assert.equal(f.el('BulkHRPages').value,'10');
  f.el('notes').value='Keep my draft';f.el('notes').handlers.input();await f.start();
  assert.equal(f.state.starts.length,3);assert(f.state.starts.every(a=>a.country==='Malaysia'&&a.max_pages===10));
  assert.equal(new Set(f.state.starts.map(a=>a.run_id)).size,3);assert.deepEqual(f.state.ends,f.state.starts.map(a=>a.run_id));
  assert.equal(f.el('BulkHRBar').value,3);assert.equal(f.el('BulkHRBar').max,3);assert.match(f.el('BulkHRMessage').textContent,/finished/i);
  assert.equal(f.el('notes').value,'Keep my draft');assert.equal(f.requests.filter(r=>r.action==='save_hr').length,3);
  assert.equal(f.el('HRResults').children[0].children[0].textContent,'Example Person 1','another company cannot replace the previewed company HR cards');
  assert(f.state.records.every(r=>r.hr.people.length===1&&r.hr.country==='Malaysia'&&r.notes==='Important saved notes'&&r.contact==='Manual Contact'));
  const stopped=bulkFixture();await stopped.init();stopped.select();stopped.state.holdId='2'.repeat(32);const running=stopped.start();await held(stopped);
  assert.equal(stopped.el('BulkHRBar').value,1);assert(stopped.el('BulkHRStart').disabled);assert(!stopped.el('BulkHRStop').disabled);
  assert.match(stopped.el('BulkHRMessage').textContent,/2 of 3.*Example Company 2/);stopped.el('BulkHRStop').click();stopped.state.release();await running;
  assert.equal(stopped.requests.filter(r=>r.action==='save_hr').length,1);assert.equal(stopped.state.starts.length,2);assert.equal(stopped.state.records[1].hr.country,'Singapore');assert.equal(stopped.state.records[2].hr.country,'Singapore');
  assert.match(stopped.el('BulkHRMessage').textContent,/stopped/i);assert(!stopped.el('BulkHRStart').disabled);
  const failed=bulkFixture();await failed.init();failed.select();failed.state.failId='2'.repeat(32);await failed.start();
  assert.equal(failed.requests.filter(r=>r.action==='save_hr').length,2);assert.equal(failed.el('BulkHRBar').value,3);assert.match(failed.el('BulkHRResults').children[1].textContent,/unavailable/);
  const stale=bulkFixture();await stale.init();stale.select();stale.state.staleId='2'.repeat(32);await stale.start();assert.equal(stale.state.records[1].hr.country,'Singapore');assert.equal(stale.state.records[2].hr.people.length,1);
  const storage=bulkFixture();await storage.init();storage.select();storage.state.onRequest=async data=>data.action==='save_hr'?{ok:false,json:async()=>({error:'Storage unavailable',code:'JOB_LEADS_STORAGE_ERROR'})}:undefined;
  await storage.start();assert.equal(storage.state.starts.length,1,'an unavailable or ambiguous save stops the queue without replay');assert.match(storage.el('BulkHRMessage').textContent,/save could not be confirmed/);assert(!storage.el('BulkHRMessage').textContent.includes('Previous saved results'));
  const disconnect=bulkFixture();await disconnect.init();disconnect.select();disconnect.state.disconnectAfter='1'.repeat(32);await disconnect.start();assert.equal(disconnect.state.starts.length,1,'a lost companion stops the remaining queue');
  const cleanup=bulkFixture();await cleanup.init();cleanup.select();cleanup.state.cleanupFailId='1'.repeat(32);await cleanup.start();assert.equal(cleanup.state.starts.length,1,'an unconfirmed End cannot start another run');
  const saving=bulkFixture();await saving.init();saving.select();const saveHandler=saving.state.onRequest;
  saving.state.onRequest=async data=>{if(data.action==='save_hr'&&data.id==='1'.repeat(32)){await new Promise(resolve=>saving.state.releaseSave=resolve);}return saveHandler(data);};
  const writing=saving.start();for(let i=0;i<40&&!saving.state.releaseSave;i++)await new Promise(r=>setTimeout(r,0));assert(saving.state.releaseSave);saving.el('BulkHRStop').click();saving.state.releaseSave();await writing;
  assert.equal(saving.state.records[0].hr.people.length,1,'an already sent save is accounted for');assert.equal(saving.state.starts.length,1,'Stop during save prevents another ad');assert.equal(saving.el('BulkHRBar').value,1);
  const unloaded=bulkFixture();await unloaded.init();unloaded.select();unloaded.state.holdId='1'.repeat(32);const leaving=unloaded.start();await held(unloaded);unloaded.pagehide();unloaded.state.release();await leaving;assert.equal(unloaded.state.starts.length,1);assert(!unloaded.requests.some(r=>r.action==='save_hr'));
  const invalid=bulkFixture();await invalid.init();invalid.select();invalid.el('BulkHRCountryMode').value='specific';invalid.el('BulkHRCountry').value='';await invalid.start();assert.equal(invalid.state.starts.length,0);assert.match(invalid.el('BulkHRMessage').textContent,/country/i);
  const trash=bulkFixture();trash.state.records[1].deleted=true;await trash.init();trash.select();await trash.start();assert.equal(trash.state.starts.length,2,'only selected live saved ads are scanned');
  const large=bulkFixture(),template=large.state.records[0];large.state.records=Array.from({length:41},(_,i)=>({...structuredClone(template),id:(i+1).toString(16).padStart(32,'0'),url:'https://www.linkedin.com/jobs/view/'+(1111111000+i)}));
  await large.init();large.select();await large.el('Next').click();large.select();await large.start();assert.equal(large.state.starts.length,0);assert.match(large.el('BulkHRMessage').textContent,/40 ads/,'bulk work has a bounded run size across page selections');
  console.log('Bulk HR: shared saved settings, serial ownership/cleanup, progress, independent saves, Stop, pagehide, per-ad errors, stale writes, disconnects and drafts passed');
})().catch(error=>{console.error(error);process.exitCode=1});
