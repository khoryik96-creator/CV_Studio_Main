/* Real worker + real DOM reader: no fake date response and no live network.
 * Optional Playwright regression, uses CVSTUDIO_PLAYWRIGHT when supplied.
 * CVSTUDIO_HR_WORKER/READER can select a historical implementation to prove
 * the regression fails there. Every profile/company fixture is fictional.
 */
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {chromium}=require(process.env.CVSTUDIO_PLAYWRIGHT || 'playwright');
const {hrFixture}=require('../test_linkedin_company_hr');
const reader=fs.readFileSync(process.env.CVSTUDIO_HR_READER || path.join(__dirname,'../../vendor/linkedin-companion/reader.js'),'utf8');
const workerSource=process.env.CVSTUDIO_HR_WORKER?fs.readFileSync(process.env.CVSTUDIO_HR_WORKER,'utf8'):undefined;
const profile='https://www.linkedin.com/in/sample';
const company='https://www.linkedin.com/company/example/';
const activity='<main><h2>About</h2><h2>Activity</h2><div componentkey="profileCardsExperienceOnlysample"></div></main>';
const details='<main><section componentkey="com.linkedin.sdui.profile.card.refFictionalExperienceDetailsSection"><div componentkey="profileExperienceDetails_top_anchor"></div><p>Experience</p><div componentkey="entity-collection-item-example"><a href="https://www.linkedin.com/company/123/">Logo</a><a href="https://www.linkedin.com/company/123/"><p>HR Partner</p><p>Example Company · Full-time</p><p>Jul 2022 - Present · 4 yrs</p></a></div></section><aside><a href="https://www.linkedin.com/company/123/"><p>Jan 1990 - Present</p></a></aside></main>';
(async()=>{
 const browser=await chromium.launch({headless:true});
 try {
  async function setup(){
   const f=hrFixture('',{workerSource}),pages=new Map(),original=f.state.onScript;f.state.fastWait=true;
   f.state.onCreated=async tab=>{
    if(!tab.url.includes('/in/'))return;
    const p=await browser.newPage();pages.set(tab.id,p);
    await p.route('**/*',route=>route.fulfill({contentType:'text/html; charset=utf-8',body:tab.url.endsWith('/details/experience/')?details:activity}));
    await p.goto(tab.url);return {...tab};
   };
   f.state.onScript=args=>{
    const p=pages.get(args.target.tabId);if(!p)return original(args);
    return (async()=>{
     if(args.files){await p.addScriptTag({content:reader});return [{}];}
     // Execute the production injection function against actual fixture DOM.
     const result=await p.evaluate(args.func,args.args?.[0]);
     return [{result}];
    })();
   };
   await f.arm();f.nativePages=pages;return f;
  }
  const f=await setup(),source=(await f.beginHR()).result.tab_id;
  await f.readHR(source);await f.readHR(source);
  const lookup=()=>f.rpc('hrJoined',{run_id:f.run,tab_id:source,url:profile});
  assert((await lookup()).result.loading);
  f.boot();const result=await lookup();assert(!result.error,result.error);
  assert.equal(result.result.joined,'2022-07','the actual Experience DOM must supply the date without a profile-scroll mock: '+JSON.stringify(result));
  assert.equal(result.result.current,true);assert.equal(f.state.created.at(-1).url,profile+'/details/experience/');
  assert(f.state.removed.includes(10+f.state.created.length));await f.end();
  const direct=await browser.newPage();await direct.route('**/*',route=>route.fulfill({contentType:'text/html; charset=utf-8',body:details}));
  await direct.goto(profile+'/details/experience/');await direct.addScriptTag({content:reader});
  const read=()=>direct.evaluate(([url,company])=>SourcerReader.readHRJoined(url,company,'123'),[profile,company]);
  assert.equal((await read()).joined,'2022-07');
  await direct.locator('section p').last().evaluate(n=>n.textContent='Mar 2021 - Aug 2025');
  assert.deepEqual(await read(),{joined:'2021-03',left:'2025-08',current:false});
  await direct.locator('section').evaluate(n=>n.remove());
  assert((await read()).loading,'an unrelated sidebar cannot supply an employment date');
  await direct.goto(profile+'/details/experience/?untrusted=1');await direct.addScriptTag({content:reader});
  await assert.rejects(read,/employment profile page changed/,'detail query redirects require review');
  await direct.close();
  const single=await setup();
  const value=await single.rpc('hrDate',{url:profile,company_url:company,company_id:'123',operation_id:'a'.repeat(32)});
  assert(!value.error,value.error);assert.equal(value.result.joined,'2022-07');assert.equal(value.result.current,true);
  assert.equal(single.state.hrMutations.length,0,'a date-only lookup never changes a user search');
  console.log('Native employment pipeline: real worker + real DOM reader, lazy profile vs direct Experience, suspension, exact-company scope, single/batch reads and owned cleanup passed. No live network or fabricated date reply.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
