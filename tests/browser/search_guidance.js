/* Actual DOM/focus/CSS checks against the isolated fictional 525 server. */
const assert=require('assert/strict'),path=require('path'),fs=require('fs');
const {chromium}=require(process.env.CVSTUDIO_PLAYWRIGHT || 'playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CVSTUDIO_CHROMIUM?{executablePath:process.env.CVSTUDIO_CHROMIUM}:{})});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],posts=[];
  const origin='http://127.0.0.1:5097',output=path.resolve(__dirname,'../../runtime/search-guidance526');fs.mkdirSync(output,{recursive:true});
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const request=route.request(),url=new URL(request.url());if(url.origin!==origin)return route.abort();
   if(request.method()==='POST')posts.push({path:url.pathname,body:request.postDataJSON()});
   if(url.pathname==='/linkedin-sourcer' && !url.search)return route.fulfill({json:{configured:true,run:null}});
   if(url.pathname==='/job-leads' && request.method()==='POST' && request.postDataJSON().action==='lookup')return route.fulfill({json:{record:{url:request.postDataJSON().url}}});
   return route.continue();
  });
  assert.equal((await (await page.request.get(origin+'/__job_leads525_fixture__')).json()).fictional_job_leads_fixture,true);
  await page.addInitScript(()=>{
   window.fixtureConnected=true;window.fixtureHoldTabs=false;window.fixtureTabs=null;window.fixtureRPC=[];
   window.fixtureReply=d=>window.postMessage({type:'CVSTUDIO_LINKEDIN_RESPONSE',id:d.id,channel:d.channel,...(!window.fixtureConnected?{error:'Fictional companion disconnected.'}:{result:d.action==='tabs'?[]:{connected:true,job_search:true,job_search_revision:1,concurrent_scans_revision:1}})},location.origin);
   window.addEventListener('message',e=>{const d=e.data;if(d?.type!=='CVSTUDIO_LINKEDIN_REQUEST')return;window.fixtureRPC.push(d.action);if(d.action==='tabs'&&window.fixtureHoldTabs)window.fixtureTabs=d;else if(['tabs','jobStatus','end'].includes(d.action))window.fixtureReply(d);});
  });
  const guided=async id=>assert.equal(await page.locator('#'+id).getAttribute('data-guide'),'true',id+' should guide the next step');
  const invalid=async id=>{await guided(id);assert.equal(await page.locator('#'+id).getAttribute('aria-invalid'),'true');assert.equal(await page.evaluate(()=>document.activeElement.id),id);assert.equal(await page.locator('#'+id).evaluate(n=>getComputedStyle(n).outlineStyle),'solid');};
  await page.goto(origin+'/?module=jobleads');await page.locator('#jobLeadsList article').first().waitFor();
  await page.locator('#jobLeadsSearchPanel').evaluate(n=>n.open=true);await page.locator('#jobLeadsSearchQuery').fill('');await page.locator('#jobLeadsSearchStart').click();await invalid('jobLeadsSearchQuery');
  await page.locator('#jobLeadsSearchQuery').fill('Finance');await guided('jobLeadsSearchStart');
  await page.locator('#jobLeadsSearchPages').fill('0');await page.locator('#jobLeadsSearchStart').click();await invalid('jobLeadsSearchPages');
  await page.locator('#jobLeadsSearchPages').fill('3');await page.locator('#jobLeadsSearchMode').selectOption('open');await page.locator('#jobLeadsSearchStart').click();await guided('jobLeadsSearchRefresh');
  await page.locator('#jobLeadsSearchMode').selectOption('new');await page.evaluate(()=>window.fixtureConnected=false);await page.locator('#jobLeadsSearchStart').click();await page.waitForFunction(()=>document.querySelector('#jobLeadsSearchSetupGuide').getAttribute('data-guide')==='true');
  assert.equal(await page.locator('#jobLeadsSearchSetupGuide').getAttribute('aria-invalid'),'false');await page.evaluate(()=>window.fixtureConnected=true);
  await page.locator('#jobLeadsNew').click();await page.locator('#jobLeadsSave').click();await invalid('jobLeadsurl');
  await page.locator('#jobLeadsurl').fill('https://www.linkedin.com/jobs/view/1234567890');await page.locator('#jobLeadsurl').press('Tab');await page.waitForFunction(()=>document.querySelector('#jobLeadsMessage').textContent.includes('draft has been kept'));
  await page.locator('#jobLeadsSave').click();await invalid('jobLeadscompany');
  await page.locator('#jobLeadscompany').fill('Fictional Company');await guided('jobLeadsrole');await page.locator('#jobLeadsrole').fill('Finance Manager');await guided('jobLeadsSave');
  await page.locator('#jobLeadsForm').screenshot({path:path.join(output,'save-guidance.jpg')});
  await page.locator('#jobLeadsList article').first().getByRole('button',{name:/^HR people/}).click();await page.locator('#jobLeadsHRCountryMode').selectOption('specific');await page.locator('#jobLeadsHRCountry').fill('');await page.locator('#jobLeadsHRStart').click();await invalid('jobLeadsHRCountry');
  await page.locator('#jobLeadsHRCountry').fill('Malaysia');await page.locator('#jobLeadsHRKeywords').evaluate(n=>{n.value='';n.dispatchEvent(new Event('input',{bubbles:true}));});await page.locator('#jobLeadsHRStart').click();await invalid('jobLeadsHRKeywords');
  assert(await page.locator('#jobLeadsHRKeywords').evaluate(n=>n.closest('details').open));await page.locator('#jobLeadsHRKeywords').fill('HR');await guided('jobLeadsHRStart');
  await page.locator('#jobLeadsSelectPage').check();await page.locator('#jobLeadsBulkHRCountryMode').selectOption('specific');await page.locator('#jobLeadsBulkHRCountry').fill('');await page.locator('#jobLeadsBulkHRStart').click();await invalid('jobLeadsBulkHRCountry');
  await page.locator('#jobLeadsBulkHRCountry').fill('Malaysia');await guided('jobLeadsBulkHRStart');await page.locator('#jobLeadsBulkHR').screenshot({path:path.join(output,'bulk-guidance.jpg')});
  assert(!(await page.evaluate(()=>window.fixtureRPC)).includes('hrBegin'),'invalid HR settings never begin a scan');
  await page.goto(origin+'/?module=linkedinsourcer');await page.waitForFunction(()=>document.querySelector('#liSourcerConnection').textContent.startsWith('Connected'));
  await guided('liSourcerBrief');await page.locator('#liSourcerBrief').fill('Finance managers in Malaysia');await page.locator('#liSourcerStart').click();await invalid('liSourcerConsent');
  await page.locator('#liSourcerConsent').check();await guided('liSourcerStart');await page.locator('#liSourcerOptions summary').click();await page.locator('#liSourcerPages').fill('0');await page.locator('#liSourcerStart').click();await invalid('liSourcerPages');
  await page.locator('#liSourcerPages').fill('10');await page.locator('#liSourcerOptions summary').click();await page.locator('#peopleSourcerSearchPanel').screenshot({path:path.join(output,'sourcer-guidance.jpg')});
  await page.evaluate(()=>window.fixtureHoldTabs=true);await page.locator('#liSourcerStart').click();await page.waitForFunction(()=>window.fixtureTabs);
  assert.equal(await page.locator('#viewLinkedinSourcer [data-guide="true"]').count(),0);await page.locator('#liSourcerStop').click();await page.evaluate(()=>{window.fixtureHoldTabs=false;window.fixtureReply(window.fixtureTabs);});await page.waitForFunction(()=>!document.querySelector('#liSourcerStart').disabled);await guided('liSourcerStart');
  assert(!posts.some(r=>r.path==='/linkedin-sourcer'),'validation and Stop-before-start do not send AI requests');
  assert(!posts.some(r=>r.path==='/job-leads' && ['save','save_hr'].includes(r.body.action)),'guidance never saves user records');
  await page.setViewportSize({width:390,height:844});await page.locator('#liSourcerStart').scrollIntoViewIfNeeded();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.deepEqual(errors,[]);console.log('Native search guidance: visible red outlines, invalid focus, collapsed fields, connection help, edits, bulk, Stop and mobile passed; no paid requests or record saves.');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
