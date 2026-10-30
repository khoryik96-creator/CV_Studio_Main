const assert=require('assert/strict');
const {fixture}=require('./test_job_search_frontend');
const guided=(f,name)=>f.el(name)['data-guide']==='true';
(async()=>{
  const f=fixture();await f.init();
  f.el('SearchQuery').value='';f.el('SearchQuery').handlers.input();
  assert(guided(f,'SearchQuery'));assert.equal(f.el('SearchQuery')['aria-invalid'],'false');
  const before=f.calls.length;await f.el('SearchStart').click();
  assert.equal(f.calls.length,before,'invalid search must not start a browser action');
  assert.equal(f.el('SearchQuery')['aria-invalid'],'true');
  f.el('SearchQuery').value='Finance';f.el('SearchQuery').handlers.input();
  assert(!guided(f,'SearchQuery'));assert.equal(f.el('SearchQuery')['aria-invalid'],'false');
  f.el('SearchPages').value='0';await f.el('SearchStart').click();assert(guided(f,'SearchPages'));
  f.el('SearchPages').value='3';f.el('SearchPages').handlers.input();
  f.state.connected=false;await f.el('SearchStart').click();
  assert(guided(f,'SearchSetupGuide'));assert.equal(f.el('SearchSetupGuide')['aria-invalid'],'false');

  await f.el('New').click();assert(guided(f,'url'));
  await f.el('AutoFill').click();assert.equal(f.el('url')['aria-invalid'],'true');
  f.el('url').value='https://www.linkedin.com/jobs/view/1111111110';f.el('url').handlers.input();
  assert(guided(f,'company'));f.el('company').value='Fictional Company';f.el('company').handlers.input();
  assert(guided(f,'role'));f.el('role').value='Finance Manager';f.el('role').handlers.input();assert(guided(f,'Save'));

  f.el('HRCountryMode').value='specific';f.el('HRCountryMode').handlers.change();
  assert(guided(f,'HRCountry'));const requests=f.requests.length;await f.el('HRStart').click();
  assert.equal(f.el('HRCountry')['aria-invalid'],'true');assert.equal(f.requests.length,requests);
  f.el('HRCountry').value='Malaysia';f.el('HRCountry').handlers.input();assert(guided(f,'HRStart'));
  f.el('SelectPage').checked=true;f.el('SelectPage').handlers.change();assert(guided(f,'BulkHRStart'));
  f.el('BulkHRCountryMode').value='specific';f.el('BulkHRCountryMode').handlers.change();
  f.el('BulkHRCountry').value='';f.el('BulkHRCountry').handlers.input();
  await f.el('BulkHRStart').click();assert(guided(f,'BulkHRCountry'));assert.equal(f.el('BulkHRCountry')['aria-invalid'],'true');
  f.el('BulkHRCountry').value='Malaysia';f.el('BulkHRCountry').handlers.input();assert(guided(f,'BulkHRStart'));
  assert.equal(f.el('BulkHRCountry')['aria-invalid'],'false');

  const running=fixture();await running.init();running.state.hold=true;
  const search=running.el('SearchStart').click();
  while(!running.state.held)await new Promise(resolve=>setTimeout(resolve,0));
  for(const name of ['SearchStart','SearchQuery','PreviewSave','HRStart','BulkHRStart'])assert(!guided(running,name),'running scans have no next-step outline');
  await running.el('SearchStop').click();running.state.held();await search;
  assert(!running.el('SearchStart').disabled);assert(!running.calls.some(c=>c.action==='hrBegin'));
  console.log('Search guidance: invalid inputs do not start work, outline follows edits/connection/review/HR/bulk, and Stop keeps transport behavior');
})().catch(error=>{console.error(error);process.exitCode=1});
