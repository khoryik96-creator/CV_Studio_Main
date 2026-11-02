const assert=require('assert/strict'),path=require('path'),fs=require('fs');
const {chromium}=require(process.env.CVSTUDIO_PLAYWRIGHT || 'playwright');
(async()=>{
 const origin='http://127.0.0.1:5098',output=path.resolve(__dirname,'../../runtime/loading531');fs.mkdirSync(output,{recursive:true});
 const browser=await chromium.launch({headless:true,...(process.env.CVSTUDIO_CHROMIUM?{executablePath:process.env.CVSTUDIO_CHROMIUM}:{})});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],held=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  assert.equal((await(await page.request.get(origin+'/__signed_clients_fixture__')).json()).fictional_signed_clients_fixture,true);
  await page.route('**/job-leads',route=>route.request().method()==='GET'?held.push(route):route.continue());
  await page.addInitScript(()=>{
   window.fixtureMode='current';window.fixtureCalls=[];
   window.addEventListener('message',event=>{const message=event.data;if(message?.type!=='CVSTUDIO_LINKEDIN_REQUEST')return;
    window.fixtureCalls.push(message.action);
    if(message.action==='jobStatus' && window.fixtureMode==='silent')return;
    const result=message.action==='tabs'?[]:message.action==='jobStatus'?{connected:true,companion_update_revision:1}:message.action==='reloadCompanion'?{current:true}:null;
    window.postMessage({type:'CVSTUDIO_LINKEDIN_RESPONSE',id:message.id,channel:message.channel,result},location.origin);
   });
  });
  await page.goto(origin+'/?module=jobleads');await page.locator('#jobLeadsClientsTab').click();
  await page.waitForFunction(()=>document.querySelectorAll('#jobLeadsClientsStatuses input').length===3);
  assert(await page.locator('#jobLeadsClientsRefresh').isDisabled(),'the independent saved-ad read is still pending');
  await page.waitForFunction(()=>!document.querySelector('#jobLeadsClientsRefresh').disabled,{},{timeout:20000});
  assert.match(await page.locator('#jobLeadsClientsMessage').textContent(),/Saved ads could not be refreshed/);
  assert(await page.locator('#jobLeadsClientsRefresh').isEnabled(),'Refresh is the one recovery action');
  await page.locator('#jobLeadsClientsPanel').screenshot({path:path.join(output,'clients-recovery.jpg')});
  for(const route of held)await route.abort().catch(()=>{});await page.unroute('**/job-leads');
  await page.locator('#tabLinkedinSourcer').click();await page.locator('#peopleSourcerSearchTab').click();await page.locator('#liSourcerSetupGuide').click();
  const update=page.locator('#liSourcerSetup button[onclick="reloadLinkedinCompanion(this)"]'),note=page.locator('#liSourcerSetup [data-companion-status]');
  const setupReads=[];await page.route('**/linkedin-sourcer?action=companion_setup',route=>setupReads.push(route));
  await update.click();await page.waitForFunction(()=>document.querySelector('#liSourcerSetup [data-companion-status]').textContent.includes('did not return'),{},{timeout:11000});assert(setupReads.length,'the setup read was deliberately held');
  assert(await update.isEnabled());assert.equal(await page.evaluate(()=>fixtureCalls.filter(action=>action==='reloadCompanion').length),0);
  for(const route of setupReads)await route.abort().catch(()=>{});await page.unroute('**/linkedin-sourcer?action=companion_setup');
  await page.evaluate(()=>{fixtureMode='silent'});await update.click();
  await page.waitForFunction(()=>document.querySelector('#liSourcerSetup [data-companion-status]').textContent.includes('companion did not reply'),{},{timeout:9000});
  assert(await update.isEnabled());assert.equal(await page.evaluate(()=>fixtureCalls.filter(action=>action==='reloadCompanion').length),0);
  await page.locator('#liSourcerSetup').screenshot({path:path.join(output,'companion-recovery.jpg')});
  await page.evaluate(()=>{fixtureMode='current'});await update.click();await page.waitForFunction(()=>document.querySelector('#liSourcerSetup [data-companion-status]').textContent.includes('up to date'));
  assert.equal(await page.evaluate(()=>fixtureCalls.filter(action=>action==='reloadCompanion').length),1,'only an explicit fresh click applies an update');
  assert.deepEqual(errors,[]);console.log('Native loading recovery: statuses independent of stalled ads, bounded local setup and silent companion, enabled recovery buttons, no automatic reload and explicit success passed.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
