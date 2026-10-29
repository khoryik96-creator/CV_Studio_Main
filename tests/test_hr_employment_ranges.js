const assert=require('assert/strict');
const {hrFixture:worker}=require('./test_linkedin_company_hr');
const {hrFixture:frontend}=require('./test_job_hr_frontend');
const profile='https://www.linkedin.com/in/sample';
async function read(dates){
  const f=worker();await f.arm();const id=(await f.beginHR()).result.tab_id;
  await f.readHR(id);await f.readHR(id);f.state.employment=dates;
  const lookup=()=>f.rpc('hrJoined',{run_id:f.run,tab_id:id,url:profile});
  await lookup();const response=await lookup();await f.end();return response;
}
(async()=>{
  for(const dates of [
    {joined:'2026-10',left:'',current:true},
    {joined:'2020-06',left:'2024-03',current:false},
    {joined:'2020',left:'2024',current:false},
    {joined:'',left:'',current:null},
  ]) {
    const response=await read(dates);assert(!response.error,response.error);
    assert.deepEqual({...response.result},{url:profile,...dates});
  }
  for(const dates of [
    {joined:'2024-01',left:'2023-12',current:false},
    {joined:'2024',left:'2025',current:true},
    {joined:'',left:'',current:true},
    {joined:'2024',left:'',current:false},
    {joined:'2024',left:'',current:'true'},
    {joined:'2024',current:true},
    {joined:'2024',left:''},
  ]) {
    assert((await read(dates)).error,'worker rejects inconsistent employment');
    const f=frontend();await f.init();f.state.joined=dates.joined;f.state.employment=dates;await f.el('HRStart').click();
    assert(!f.requests.some(r=>r.action==='save_hr'),'invalid RPC evidence cannot save');
  }
  for(const [dates,label] of [
    [{joined:'2026-10',left:'',current:true},'Oct 2026 to Present'],
    [{joined:'2020-06',left:'2024-03',current:false},'Jun 2020 to Mar 2024'],
    [{joined:'2020',left:'2024',current:false},'2020 to 2024'],
  ]) {
    const f=frontend();await f.init();f.state.joined=dates.joined;f.state.employment=dates;await f.el('HRStart').click();
    assert.equal(f.el('HRResults').children[0].children[3].textContent,'Employment: '+label);
    const saved=f.state.records[0].hr.people[0];for(const key of ['joined','left','current'])assert.equal(saved[key],dates[key]);
    await f.el('Refresh').click();assert.equal(f.el('HRResults').children[0].children[3].textContent,'Employment: '+label);
  }
  console.log('HR employment: guarded current/former ranges, month/year precision, legacy compatibility, invalid evidence and saved refresh passed');
})().catch(error=>{console.error(error);process.exitCode=1});
