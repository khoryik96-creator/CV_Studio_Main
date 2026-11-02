/* Actual DOM + real isolated service/store; run signed_clients_server.py first. */
const assert=require('assert/strict'),path=require('path'),fs=require('fs');
const {chromium}=require(process.env.CVSTUDIO_PLAYWRIGHT || 'playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CVSTUDIO_CHROMIUM?{executablePath:process.env.CVSTUDIO_CHROMIUM}:{})});
 try {
  const origin='http://127.0.0.1:5098',output=path.resolve(__dirname,'../../runtime/signed-clients536');fs.mkdirSync(output,{recursive:true});
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  assert.equal((await(await page.request.get(origin+'/__signed_clients_fixture__')).json()).fictional_signed_clients_fixture,true);
  await page.addInitScript(()=>{window.fixtureSearches=0;window.addEventListener('message',e=>{const d=e.data;if(d?.type==='CVSTUDIO_LINKEDIN_REQUEST' && d.action==='jobSearchBegin')window.fixtureSearches++;});});
  const choose=async(id,label)=>page.locator('#jobLeadsClients'+id).selectOption({label});
  const names=()=>page.locator('#jobLeadsClientsCompanies tr td:first-child a').allTextContents();
  const waitNames=async expected=>page.waitForFunction(value=>JSON.stringify([...document.querySelectorAll('#jobLeadsClientsCompanies tr td:first-child a')].map(n=>n.textContent))===JSON.stringify(value),expected);
  const status=label=>page.locator('#jobLeadsClientsStatuses').getByRole('checkbox',{name:label,exact:true});
  await page.goto(origin+'/?module=jobleads');await page.locator('#jobLeadsClientsTab').click();await status('Signed Client').waitFor();
  await status('Signed Client').check();await status('Active Client').check();await page.locator('#jobLeadsClientsStatusesSave').click();await waitNames(['alpha','Client 2','Client 10','Zeta']);
  const company=name=>page.locator('#jobLeadsClientsCompanies tr').filter({has:page.getByRole('link',{name,exact:true})});
  await company('Client 10').getByRole('button',{name:'Follow',exact:true}).click();await page.waitForFunction(()=>document.querySelectorAll('#jobLeadsClientsFollowed tr').length===1);
  assert(await page.locator('#jobLeadsClientsFollowed').isHidden(),'followed clients live in their own tab');
  await page.locator('#jobLeadsClientsFollowedTab').click();await page.locator('#jobLeadsClientsFollowed tr').waitFor();
  assert(await page.locator('#jobLeadsClientsPanel').isHidden() && await page.locator('#jobLeadsClientsBrowse').isHidden(),'Signed clients setup stays in its tab');
  let followed=page.locator('#jobLeadsClientsFollowed tr');assert(await followed.getByRole('checkbox').isDisabled());
  const link=followed.getByRole('textbox',{name:'LinkedIn link for Client 10'});assert(await link.isVisible());assert.equal(await link.getAttribute('data-guide'),'true');
  await page.getByRole('button',{name:'Refresh from JobAdder',exact:true}).click();
  await page.waitForFunction(()=>!document.querySelector('#jobLeadsClientsFollowed input[type="checkbox"]').disabled);
  assert.equal(await followed.getByRole('link',{name:'LinkedIn page'}).getAttribute('href'),'https://www.linkedin.com/company/fictional-client/');
  assert.match(await page.locator('#jobLeadsClientsProgress').textContent(),/1 of 1 clients refreshed/);
  await followed.getByRole('checkbox').check();assert(await followed.getByRole('checkbox').isChecked(),'named link may be selected without manually finding its number');
  await followed.locator('summary').click();
  await link.fill('https://www.linkedin.com/jobs/search/?f_C=4242');await followed.getByRole('button',{name:'Save link'}).click();await page.waitForFunction(()=>!document.querySelector('#jobLeadsClientsFollowed input[type="checkbox"]').disabled);
  assert(await page.locator('#jobLeadsClientsFollowed input[type="checkbox"]').isChecked());
  // Open on LinkedIn opens one company-filtered search straight from the click.
  await page.context().route('https://www.linkedin.com/**',route=>route.fulfill({status:200,contentType:'text/html',body:'<title>Fictional LinkedIn</title>'}));
  const [popup]=await Promise.all([page.waitForEvent('popup'),page.locator('#jobLeadsClientsOpenLinkedIn').click()]);
  assert.equal(popup.url(),'https://www.linkedin.com/jobs/search/?f_C=4242');await popup.close();
  assert.equal(await page.locator('#jobLeadsClientsLinkedInLink').getAttribute('href'),'https://www.linkedin.com/jobs/search/?f_C=4242');
  // Saved ads of a followed client fill the dashboard (fictional records).
  for (const [id,role,posted] of [['7001','Fictional Payroll Lead','2026-10-28'],['7002','Fictional Data Analyst','2026-10-12']])
    assert.equal(await page.evaluate(async([id,role,posted])=>(await fetch('/job-leads',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'save',record:{url:'https://www.linkedin.com/jobs/view/'+id,company:'Client 10 Sdn Bhd',role,location:'Kuala Lumpur',date_posted:posted,description:'',description_rich:[],description_truncated:true,folder:'',status:'new',contact:'',notes:'',follow_up:''}})})).status,[id,role,posted]),200);
  await page.locator('#jobLeadsClientsFollowedRefresh').click();await page.waitForFunction(()=>document.querySelector('#jobLeadsClientsAdsCount').textContent==='2');
  assert.deepEqual(await page.locator('#jobLeadsClientsAdsRows tr td:nth-child(2)').allTextContents(),['Fictional Payroll Lead','Fictional Data Analyst']);
  assert.equal(await page.locator('#jobLeadsClientsFollowed tr td:nth-child(4)').textContent(),'2','the Ads in Job ads count matches the dashboard');
  await page.locator('#jobLeadsClientsFollowedPanel').screenshot({path:path.join(output,'followed-clients-desktop.jpg')});
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'no page-wide horizontal scroll on a phone');
  await page.locator('#jobLeadsClientsFollowedPanel').screenshot({path:path.join(output,'followed-clients-mobile.jpg')});await page.setViewportSize({width:1440,height:1000});
  await page.reload();await page.locator('#jobLeadsClientsTab').click();await waitNames(['alpha','Client 2','Client 10','Zeta']);
  assert.equal(await page.locator('#jobLeadsClientsFollowed tr').count(),1,'followed choices restore from the protected store');
  await choose('StatusFilter','Signed Client');await waitNames(['Client 2','Client 10']);await choose('OwnerFilter','Alpha Owner');await waitNames(['Client 2']);
  await choose('FollowingFilter','Followed');await waitNames([]);assert.match(await page.locator('#jobLeadsClientsCompanies').textContent(),/filters on this page/);
  await page.locator('#jobLeadsClientsFiltersReset').click();await choose('Sort','Owner Z–A');await waitNames(['Client 10','alpha','Client 2','Zeta']);
  await choose('FollowingFilter','Followed');await waitNames(['Client 10']);await page.locator('#jobLeadsClientsFiltersReset').click();
  await page.locator('#jobLeadsClientsPanel').screenshot({path:path.join(output,'signed-desktop.jpg')});
  await page.locator('#jobLeadsClientsBrowse').screenshot({path:path.join(output,'results-desktop.jpg')});
  await page.setViewportSize({width:390,height:844});await page.locator('#jobLeadsClientsBrowse').scrollIntoViewIfNeeded();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.locator('#jobLeadsClientsPanel').screenshot({path:path.join(output,'signed-mobile.jpg')});await page.locator('#jobLeadsClientsBrowse').screenshot({path:path.join(output,'results-mobile.jpg')});
  await page.locator('#jobLeadsClientsSetup').evaluate(n=>n.open=true);await status('Signed Client').uncheck();await status('Active Client').uncheck();await page.locator('#jobLeadsClientsStatusesSave').click();await page.waitForFunction(()=>document.querySelector('#jobLeadsClientsPull').disabled);
  await page.waitForFunction(()=>document.querySelector('#jobLeadsClientsMessage').textContent.includes('No status is chosen'));
  assert.equal(await page.locator('#jobLeadsClientsFollowed tr').count(),1);await page.locator('#jobLeadsClientsPull').dispatchEvent('click');
  assert.match(await page.locator('#jobLeadsClientsProgress').textContent(),/Save statuses/);assert.equal(await page.evaluate(()=>window.fixtureSearches),0);
  await page.locator('#jobLeadsClientsFollowedTab').click();await page.waitForFunction(()=>!document.querySelector('#jobLeadsClientsFollowedRefresh').disabled);
  assert(await page.locator('#jobLeadsClientsOpenLinkedIn').isDisabled(),'no LinkedIn search without signed statuses');
  assert.deepEqual(errors,[]);console.log('Native Signed and Followed clients: separate tabs, Open on LinkedIn pop-up, saved client ads dashboard, saved Follow/link, reload restores browse/results, intersecting filters/sort, empty statuses block Pull, mobile and no page errors passed.');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
