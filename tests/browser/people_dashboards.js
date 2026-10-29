/* Optional native regression. First run people_dashboard_server.py in a
 * separate terminal. CVSTUDIO_PLAYWRIGHT selects the installed Playwright module.
 * The marker check prevents running this against an owner/real account server.
 * Browser fixture messages and all records are fictional; no live unlocks.
 */
const assert=require('assert/strict'),path=require('path'),fs=require('fs');
const evidence=path.resolve(__dirname,'../../runtime/people521-native');fs.mkdirSync(evidence,{recursive:true});
const {chromium}=require(process.env.CVSTUDIO_PLAYWRIGHT || 'playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],calls=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST')calls.push({url:new URL(r.url()).pathname,data:r.postDataJSON()});});
 await page.addInitScript(()=>window.addEventListener('message',e=>{const d=e.data;if(d?.type==='CVSTUDIO_LINKEDIN_REQUEST'&&['hrDate','jobStatus'].includes(d.action))window.postMessage({type:'CVSTUDIO_LINKEDIN_RESPONSE',channel:d.channel,id:d.id,result:d.action==='jobStatus'?{connected:true,hr_date_check_revision:1,hr_experience_page_revision:1}:{url:d.args.url,joined:'2026-10',left:'',current:true}},location.origin);}));
 const marker=await page.request.get('http://127.0.0.1:5096/__people_dashboard_fixture__');const seed=await marker.json();assert.equal(seed.fictional_people_fixture,true,'Run only against the isolated fictional fixture');
 await page.goto('http://127.0.0.1:5096/?module=jobleads');await page.locator('#peopleHRTab').click();
 await page.locator('#peopleHRRows tr').first().waitFor();assert.equal(await page.locator('#peopleHRRows tr').count(),2);
 assert(!await page.locator('#jobLeadsApolloAdsPanel').isVisible());assert(!await page.locator('#jobLeadsApolloContactsPanel').isVisible());
 assert.equal(calls.filter(r=>r.data?.action==='reveal').length,0,'opening dashboard never unlocks');
 await page.locator('#peopleHRQuery').fill('Fictional Former');assert.equal(await page.locator('#peopleHRRows tr').count(),1);await page.locator('#peopleHRQuery').fill('');
 const first=page.locator('#peopleHRRows tr').first();assert(await first.locator('td').filter({hasText:'Jul 2022 to Present'}).isVisible(),'confirmed older-ad dates survive a newer blank observation');await first.getByRole('button',{name:'Check employment',exact:true}).click();
 await page.locator('#peopleHRMessage').filter({hasText:'Employment updated: Oct 2026 to Present'}).waitFor();assert.equal(calls.find(r=>r.data?.action==='employment')?.data.id,seed.employment_source,'date refresh uses its exact observation source');assert.notEqual(seed.employment_source,seed.latest_source);assert(await page.locator('#peopleHRRows').locator('td').filter({hasText:'Oct 2026 to Present'}).isVisible());
 await page.screenshot({path:path.join(evidence,'people521_hr.png'),fullPage:true});
 page.on('dialog',d=>d.accept());const unlock=page.locator('#peopleHRRows').getByRole('button',{name:'Unlock email',exact:true});assert.equal(await unlock.count(),1);await unlock.click();
 await page.waitForFunction(()=>!document.querySelector('#peopleHRRows [data-unlock]:not([hidden])'));assert.equal(calls.filter(r=>r.data?.action==='reveal').length,1);
 await page.locator('#jobLeadsApolloAdsTab').click();assert(!await page.locator('#peopleHRPanel').isVisible());
 await page.locator('#jobLeadsList button').filter({hasText:'HR people'}).first().click();await page.locator('#jobLeadsHRResults').getByText('Employment: Oct 2026 to Present',{exact:true}).waitFor();
 await page.locator('#tabLinkedinSourcer').click();await page.locator('#peopleCandidatesTab').click();await page.locator('#peopleCandidatesRows tr').first().waitFor();
 assert.equal(await page.locator('#peopleCandidatesRows tr').count(),40);assert.equal(await page.locator('#peopleCandidatesCount').textContent(),'45');
 await page.locator('#peopleCandidatesNext').click();assert.equal(await page.locator('#peopleCandidatesRows tr').count(),5);await page.locator('#peopleCandidatesPrevious').click();
 await page.locator('#peopleCandidatesRows tr').first().locator('td:last-child summary').click();
 const note=page.locator('#peopleCandidatesRows textarea').first();await note.fill('=literal note for follow-up');await page.locator('#peopleCandidatesQuery').fill('no such candidate');assert.equal(await page.locator('#peopleCandidatesRows tr').count(),0);await page.locator('#peopleCandidatesQuery').fill('');assert.equal(await page.locator('#peopleCandidatesRows textarea').first().inputValue(),'=literal note for follow-up');assert(await page.locator('#peopleCandidatesRows textarea').first().evaluate(n=>n.getBoundingClientRect().height<100),'notes stay compact');await page.locator('#peopleCandidatesRows tr').first().getByRole('button',{name:'Save note',exact:true}).click();await page.locator('#peopleCandidatesMessage').filter({hasText:'Note saved.'}).waitFor();
 await page.locator('#peopleCandidatesQuery').fill('=literal');assert.equal(await page.locator('#peopleCandidatesRows tr').count(),1);
 const download=page.waitForEvent('download');await page.locator('#peopleCandidatesExport').click();const file=await download;await file.saveAs(path.join(evidence,'people521_candidates.xlsx'));
 await page.locator('#peopleCandidatesQuery').fill('');await page.screenshot({path:path.join(evidence,'people521_candidates.png'),fullPage:true});
 await page.reload();await page.locator('#tabLinkedinSourcer').click();await page.locator('#peopleCandidatesTab').click();await page.locator('#peopleCandidatesQuery').fill('=literal');await page.waitForFunction(()=>document.querySelectorAll('#peopleCandidatesRows tr').length===1);assert.equal(await page.locator('#peopleCandidatesRows textarea').inputValue(),'=literal note for follow-up');
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(evidence,'people521_mobile.png'),fullPage:true});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'table scroll must not expand the page');assert.deepEqual(errors,[]);
 console.log('Native actual app: HR all-person table/search/tabs/date-only persistence/card refresh/one explicit Apollo unlock; candidate paging/notes/reload/filter/Excel; mobile width passed. Fictional transports and isolated encrypted storage only.');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
