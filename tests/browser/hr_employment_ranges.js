/* Optional native regression. Requires Playwright/Chromium; CVSTUDIO_PLAYWRIGHT
 * can point to its module. All LinkedIn pages are fulfilled locally with fictional
 * Experience markup. No real profile, browser, account or network is used.
 */
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {chromium}=require(process.env.CVSTUDIO_PLAYWRIGHT || 'playwright');
const reader=fs.readFileSync(path.join(__dirname,'../../vendor/linkedin-companion/reader.js'),'utf8');
const profile='https://www.linkedin.com/in/sample';
const company='https://www.linkedin.com/company/example/';
const role=(lines,id='123')=>'<a href="https://www.linkedin.com/company/'+id+'/"><p>'+lines.join('</p><p>')+'</p></a>';
const card=content=>'<div componentkey="entity-collection-item-fictional">'+content+'</div>';
(async()=>{
  const browser=await chromium.launch({headless:true});
  try {
    const context=await browser.newContext();
    await context.route('**/*',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><main><section><div><h2 componentkey="ProfileNullStateCardAnchor_Experience">Experience</h2></div><div id="roles"></div></section></main>'}));
    const page=await context.newPage();await page.goto(profile);await page.addScriptTag({content:reader});
    const read=()=>page.evaluate(([url,company])=>SourcerReader.readHRJoined(url,company,'123'),[profile,company]);
    const show=html=>page.locator('#roles').evaluate((node,html)=>node.innerHTML=html,html);
    await show(card('<a href="https://www.linkedin.com/company/123/">Company logo</a>'+role(['HR Partner','Example · Full-time'])));
    assert((await read()).loading,'company entry exists before date hydration');
    await show(card(role(['HR Partner','Example · Full-time','Oct 2026 - Present · 1 mo','Malaysia · Hybrid'])));
    assert.deepEqual(await read(),{joined:'2026-10',left:'',current:true});
    await show(card('<a href="https://www.linkedin.com/company/123/"><p>HR Partner</p><span aria-hidden="true">Oct 2026 - Present · 1 mo</span></a>'));
    assert.deepEqual(await read(),{joined:'2026-10',left:'',current:true},'date spans remain inside the exact employer link');
    await show(card(role(['HR Partner','Example · Full-time','Mar 2025 - Jul 2026 · 1 yr 5 mos'])));
    assert.deepEqual(await read(),{joined:'2025-03',left:'2026-07',current:false});
    await show(card(role(['Example · Full-time'])+'<ul><li>'+role(['HR Director','Jan 2024 - Present'])+'</li><li>'+role(['HR Partner','Jun 2020 - Dec 2023'])+'</li></ul>'));
    assert.deepEqual(await read(),{joined:'2020-06',left:'',current:true});
    await show(card(role(['Other company','Oct 2000 - Present'],'999'))+'<div>About: Oct 1990 - Present</div>');
    assert((await read()).loading,'other employer cards may hydrate before the requested company');
    await show(card(role(['HR Partner','Example','Oct 2026 - Present'])+'<button>Show all 5 experiences</button>'));
    assert.equal((await read()).joined,'','collapsed groups remain unknown');
    await page.close();await context.close();
    console.log('Native HR employment: delayed modern metadata, current/former month-year ranges, grouped promotions, exact company and collapsed evidence passed');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1});
