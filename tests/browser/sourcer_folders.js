/* Real isolated routes/archive; simulated companion/provider, no live credits. */
const assert=require('assert/strict'),path=require('path'),fs=require('fs');
const {chromium}=require(process.env.CVSTUDIO_PLAYWRIGHT || 'playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CVSTUDIO_CHROMIUM?{executablePath:process.env.CVSTUDIO_CHROMIUM}:{})});
 try {
  const origin='http://127.0.0.1:5099',out=path.resolve(__dirname,'../../runtime/sourcer530');fs.mkdirSync(out,{recursive:true});
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  const status=()=>page.request.get(origin+'/__sourcer_folders_fixture__').then(r=>r.json());assert.equal((await status()).fictional_sourcer_folders_fixture,true);
  await page.addInitScript(()=>{
   const source={id:3,url:'https://www.linkedin.com/search/results/people/',title:'Fictional People search'};
   const profile={id:'p0',name:'Fictional Oracle Candidate',url:'https://www.linkedin.com/in/fictional-oracle-candidate',text:'Oracle Database and Ansible automation\nMalaysia'};
   window.addEventListener('message',e=>{
    const d=e.data;if(d?.type!=='CVSTUDIO_LINKEDIN_REQUEST')return;let result;
    if(d.action==='tabs')result=[source];else if(d.action==='openPeopleSearch')result=source;
    else if(d.action==='jobStatus')result={connected:true,profile_browsing_revision:1,concurrent_scans_revision:1,people_results_revision:1,people_country_revision:1,people_country_ready_revision:1};
    else if(['begin','navigate','end'].includes(d.action))result=true;else if(d.action==='create')result=10;
    else if(d.action==='read')result=d.args.method==='setCountry'?true:d.args.method==='readProfile'?profile:{profiles:[profile],signature:'one',hasNext:false,paginationKnown:true};else return;
    window.postMessage({type:'CVSTUDIO_LINKEDIN_RESPONSE',id:d.id,channel:d.channel,result},location.origin);
   });
  });
  await page.goto(origin+'/?module=linkedinsourcer');await page.waitForFunction(()=>!document.querySelector('#liSourcerFolderNew').disabled);
  await page.locator('#liSourcerFolderNew').click();await page.locator('#liSourcerFolderName').fill('Oracle search');await page.locator('#liSourcerFolderCreate').click();await page.waitForFunction(()=>document.querySelector('#liSourcerFolder').value==='Oracle search' && !document.querySelector('#liSourcerFolderNew').disabled);
  assert.equal((await status()).provider_calls.length,0,'folder setup never calls the provider');assert(!await page.locator('#liSourcerConsent').isChecked());
  await page.reload();await page.waitForFunction(()=>document.querySelector('#liSourcerFolder').value==='Oracle search');
  await page.locator('#liSourcerBrief').fill('Oracle database AND Ansible or alternative automation in Malaysia');await page.locator('#liSourcerConsent').check();await page.locator('#liSourcerStart').click();await page.waitForFunction(()=>document.querySelector('#liSourcerStart').disabled);
  assert(await page.locator('#liSourcerFolder').isDisabled());await page.waitForFunction(()=>!document.querySelector('#liSourcerStart').disabled);
  assert.equal(await page.locator('#liSourcerCount').textContent(),'1');assert.match(await page.locator('#liSourcerQuery').textContent(),/\(Oracle OR "Oracle Database"\) AND \(Ansible OR Chef\)/);
  assert.deepEqual((await status()).provider_calls,['search_plan','profile_review','profile_review'],'one plan, screen and detail only; no paid retry');
  await page.locator('#peopleCandidatesTab').click();await page.waitForFunction(()=>document.querySelector('#peopleCandidatesFolder option[value="Oracle search"]'));
  await page.locator('#peopleCandidatesFolder').selectOption('Oracle search');await page.waitForFunction(()=>document.querySelector('#peopleCandidatesCount').textContent==='1');assert.equal(await page.getByRole('link',{name:'Fictional Oracle Candidate',exact:true}).count(),1);
  await page.locator('#peopleSourcerSearchTab').click();await page.waitForFunction(()=>!document.querySelector('#liSourcerFolder').disabled);assert.equal(await page.locator('#liSourcerFolder').inputValue(),'Oracle search');
  await page.locator('#peopleSourcerSearchPanel').screenshot({path:path.join(out,'search-folder-desktop.jpg')});
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);
  console.log('Native Sourcer: create/remember folder without consent or AI, one compact Oracle+automation plan, real archive in selected folder, busy controls and mobile passed.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
