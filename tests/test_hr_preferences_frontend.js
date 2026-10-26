const assert=require('assert/strict');
const {fixture}=require('./test_job_search_frontend');
const key='cvstudio_job_leads_hr_preferences';
function choose(f,country='Malaysia',pages='10'){
  f.el('HRCountryMode').value='specific';f.el('HRCountryMode').handlers.change();
  f.el('HRCountry').value=country;f.el('HRCountry').handlers.input?.();
  f.el('HRPages').value=pages;f.el('HRPages').handlers.change?.();
}
function another(f){f.state.records.push({...f.state.records[0],id:'f'.repeat(32),url:'https://www.linkedin.com/jobs/view/4444444444',revision:1,hr:{country:'Singapore',keywords:'HR',people:[],scanned_at:'2026-10-01T00:00:00Z',company_url:'',complete:true}})}
(async()=>{
  const preferences=new Map(),f=fixture({preferences});another(f);await f.init();
  choose(f);assert(preferences.has(key),'explicit country/pages are stored');assert.deepEqual(JSON.parse(preferences.get(key)),{countryMode:'specific',country:'Malaysia',pages:10});
  f.el('PreviewNext').click();assert.equal(f.el('HRCountry').value,'Malaysia');assert.equal(f.el('HRPages').value,'10');
  await f.el('Refresh').click();assert.equal(f.el('HRPages').value,'10');
  const reload=fixture({preferences});await reload.init();assert.equal(reload.el('HRCountryMode').value,'specific');assert.equal(reload.el('HRCountry').value,'Malaysia');assert.equal(reload.el('HRPages').value,'10');
  reload.el('HRCountryMode').value='';reload.el('HRCountryMode').handlers.change();
  const worldwide=fixture({preferences});await worldwide.init();assert.equal(worldwide.el('HRCountryMode').value,'');assert(worldwide.el('HRCountry').hidden);assert.equal(worldwide.el('HRPages').value,'10');
  assert(!f.requests.some(r=>r.action==='save_hr'),'remembering controls does not alter saved HR evidence');
  for(const raw of ['invalid','[]','null',JSON.stringify({countryMode:'specific',country:'x\ny',pages:10}),JSON.stringify({countryMode:'specific',country:'x'.repeat(101),pages:10}),JSON.stringify({countryMode:'specific',country:'Malaysia',pages:999}),JSON.stringify({countryMode:'specific',country:'Malaysia',pages:'10'})]){
    const bad=fixture({preferences:new Map([[key,raw]])});await bad.init();assert.equal(bad.el('HRPages').value,'3');assert.equal(bad.el('HRCountryMode').value,'');
  }
  const denied={getItem(){throw Error('Storage blocked')},setItem(){throw Error('Storage full')},removeItem(){throw Error('Storage blocked')}};
  const memory=fixture({storage:denied});another(memory);await memory.init();choose(memory);memory.el('PreviewNext').click();
  assert.equal(memory.el('HRCountry').value,'Malaysia');assert.equal(memory.el('HRPages').value,'10','unavailable browser storage still keeps current-tab choices');
  console.log('HR preferences: explicit country/page choices survive ads, refresh/reload, Any country, invalid data and unavailable storage without saving HR records');
})().catch(error=>{console.error(error);process.exit(1)});
