/* Actual local app and protected archive; fictional provider and companion only. */
const assert=require('assert/strict'),path=require('path'),fs=require('fs');
const {chromium}=require(process.env.CVSTUDIO_PLAYWRIGHT || 'playwright');
(async()=>{
 const origin='http://127.0.0.1:5099',out=path.resolve(__dirname,'../../runtime/sourcer532');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,...(process.env.CVSTUDIO_CHROMIUM?{executablePath:process.env.CVSTUDIO_CHROMIUM}:{})});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  const status=()=>page.request.get(origin+'/__sourcer_folders_fixture__').then(r=>r.json());assert.equal((await status()).fictional_sourcer_folders_fixture,true);
  await page.addInitScript(()=>{
   const source={id:3,url:'https://www.linkedin.com/search/results/people/',title:'Fictional People search'};
   const profile={id:'p0',name:'Fictional Oracle Candidate',url:'https://www.linkedin.com/in/fictional-oracle-candidate',text:'Oracle Database and Ansible automation\nMalaysia'};
   window.fixtureCalls=[];
   window.addEventListener('message',event=>{
    const d=event.data;if(d?.type!=='CVSTUDIO_LINKEDIN_REQUEST')return;fixtureCalls.push({action:d.action,args:d.args});let result;
    if(d.action==='tabs')result=[source];else if(d.action==='openPeopleSearch')result=source;
    else if(d.action==='jobStatus')result={connected:true,profile_browsing_revision:1,concurrent_scans_revision:1,people_results_revision:1,people_country_revision:1,people_country_ready_revision:1};
    else if(['begin','navigate','end'].includes(d.action))result=true;else if(d.action==='create')result=10;
    else if(d.action==='read')result=d.args.method==='setCountry'?true:d.args.method==='readProfile'?profile:{profiles:[profile],signature:'one',hasNext:false,paginationKnown:true};else return;
    window.postMessage({type:'CVSTUDIO_LINKEDIN_RESPONSE',id:d.id,channel:d.channel,result},location.origin);
   });
  });
  await page.goto(origin+'/?module=linkedinsourcer');await page.waitForFunction(()=>!document.querySelector('#liSourcerFolderNew').disabled);
  await page.locator('#liSourcerFolderNew').click();await page.locator('#liSourcerFolderName').fill('Manual review');await page.locator('#liSourcerFolderCreate').click();await page.waitForFunction(()=>document.querySelector('#liSourcerFolder').value==='Manual review' && !document.querySelector('#liSourcerFolderNew').disabled);
  const samples=[
   {query:'',prompt:'Oracle database and automation in Malaysia',mode:'auto',country:'Malaysia',plan:1},
   {query:'Oracle AND (Ansible OR Terraform)',prompt:'',mode:'specific',country:'Malaysia',plan:0},
   {query:'Oracle AND automation',prompt:'Review Oracle and automation profiles in Malaysia',mode:'auto',country:'Malaysia',plan:1},
   {query:'',prompt:'Oracle database profiles in Malaysia',mode:'any',country:'',plan:1},
   {query:'"Oracle Database" AND Ansible',prompt:'Check current location and explicit work eligibility using evidence; mark unknowns.',mode:'specific',country:'Malaysia',plan:0}
  ];
  for(const sample of samples){
   await page.locator('#liSourcerBoolean').fill(sample.query);await page.locator('#liSourcerBrief').fill(sample.prompt);await page.locator('#liSourcerCountryMode').selectOption(sample.mode);
   if(sample.mode==='specific')await page.locator('#liSourcerCountryName').fill(sample.country);
   const before=(await status()).provider_calls.length;await page.evaluate(()=>{fixtureCalls=[]});
   await page.locator('#liSourcerConsent').check();await page.locator('#liSourcerStart').click();await page.waitForFunction(()=>document.querySelector('#liSourcerStart').disabled);
   assert(await page.locator('#liSourcerBoolean').isDisabled());assert(await page.locator('#liSourcerCountryMode').isDisabled());
   await page.waitForFunction(()=>!document.querySelector('#liSourcerStart').disabled,{},{timeout:20000});
   assert.equal(await page.locator('#liSourcerCount').textContent(),'1');
   const calls=await page.evaluate(()=>fixtureCalls),query=new URL(calls.find(call=>call.action==='navigate').args.url).searchParams.get('keywords');
   if(sample.query)assert.equal(query,sample.query,'the exact user Boolean controls navigation');
   const locations=calls.filter(call=>call.action==='read' && call.args.method==='setCountry');assert.equal(locations.length,sample.country?1:0);if(sample.country)assert.equal(locations[0].args.values[0],sample.country);
   assert.deepEqual((await status()).provider_calls.slice(before),[...(sample.plan?['search_plan']:[]),'profile_review','profile_review']);
  }
  assert((await page.locator('#liSourcerBoolean').boundingBox()).height<=110,'the Boolean box stays compact');
  await page.locator('#peopleSourcerSearchPanel').screenshot({path:path.join(out,'search-controls-desktop.jpg')});
  await page.reload();await page.waitForFunction(()=>document.querySelector('#liSourcerCountryMode').value==='specific');assert.equal(await page.locator('#liSourcerCountryName').inputValue(),'Malaysia','country preference survives this tab reload');
  await page.locator('#peopleCandidatesTab').click();await page.waitForFunction(()=>document.querySelector('#peopleCandidatesFolder option[value="Manual review"]'));await page.locator('#peopleCandidatesFolder').selectOption('Manual review');
  await page.waitForFunction(()=>document.querySelector('#peopleCandidatesCount').textContent==='5');
  const row=page.locator('#peopleCandidatesRows tr').first();assert.equal(await row.locator('td.people-pick button').count(),0);assert.equal(await row.locator('td.people-pick input').count(),1);
  const star=row.locator('.people-shortlist');assert.equal(await star.count(),1);await star.click();await page.waitForFunction(()=>document.querySelector('#peopleCandidatesRows .people-shortlist')?.getAttribute('aria-pressed')==='true');
  const anchor=await row.locator('td.people-candidate-name a').boundingBox(),button=await row.locator('.people-shortlist').boundingBox();assert(Math.abs((anchor.y+anchor.height/2)-(button.y+button.height/2))<8,'star is on the name line');
  await row.locator('td.people-candidate-name').screenshot({path:path.join(out,'shortlist-name.jpg')});
  await page.locator('#peopleCandidatesPanel').screenshot({path:path.join(out,'shortlist-desktop.jpg')});
  await page.setViewportSize({width:390,height:844});await page.locator('#peopleSourcerSearchTab').click();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert(await page.locator('#liSourcerCountryName').isVisible());
  await page.locator('#peopleSourcerSearchPanel').screenshot({path:path.join(out,'search-controls-mobile.jpg')});assert.deepEqual(errors,[]);
  console.log('Native manual search: prompt-only, Boolean-only, both, inferred/specific/Any country, exact queries, provider-call counts, folder archive, remembered country, inline shortlist and mobile passed.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
