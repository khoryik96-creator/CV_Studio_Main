/* Optional native regression. First run signed_clients_server.py (port 5098)
 * in a separate terminal. CVSTUDIO_PLAYWRIGHT selects the installed Playwright
 * module. Fictional IDs only; nothing is connected and no secret is used.
 */
const assert=require('assert/strict'),fs=require('fs'),os=require('os'),path=require('path');
const {chromium}=require(process.env.CVSTUDIO_PLAYWRIGHT || 'playwright');
const origin='http://127.0.0.1:5098',GUID='11111111-2222-3333-4444-555555555555',GUID2='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
(async()=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'cvstudio-setup-file-')),input=path.join(dir,'setup.json');
  fs.writeFileSync(input,JSON.stringify({product:'CV Studio setup',schema:1,jobadder:{client_id:'example-ja-client'},outlook:{client_id:GUID,tenant:'common'},onenote:{client_id:GUID2}}));
  const browser=await chromium.launch({headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],dialogs=[];
    page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>{dialogs.push(d.message());void d.accept();});
    await page.goto(origin+'/');await page.evaluate(()=>{toggleSettings();showSettingsTab('integrations');});
    const chooser=page.waitForEvent('filechooser');await page.locator('#settingsSetupFileImport').click();await (await chooser).setFiles(input);
    await page.waitForFunction(()=>/Filled in/.test(document.getElementById('settingsSetupFileStatus').textContent));
    assert.match(dialogs[0],/JobAdder Client ID[\s\S]*Outlook app[\s\S]*OneNote app/,'the import lists what it will replace');
    assert.match(await page.locator('#settingsSetupFileStatus').textContent(),/Filled in: Outlook, OneNote\. JobAdder: Client ID filled in\. Enter the Client Secret/);
    assert.equal(await page.inputValue('#settingsOutlookClientId'),GUID);assert.equal(await page.inputValue('#settingsJobAdderClientId'),'example-ja-client');
    assert.equal(await page.evaluate(()=>localStorage.getItem('onenote_ms_client_id')),GUID2,'OneNote is saved through its own Save');
    await page.locator('#settingsSetupFileCard summary').click();
    const download=page.waitForEvent('download');await page.locator('#settingsSetupFileCreate').click();
    const created=JSON.parse(fs.readFileSync(await (await download).path(),'utf8'));
    assert.deepEqual([created.product,created.outlook,created.onenote],['CV Studio setup',{client_id:GUID,tenant:'common'},{client_id:GUID2,tenant:'common'}]);
    assert.equal(created.ai,undefined,'no secret is added unless typed');
    assert(await page.locator('#settingsSetupFileCard').isVisible(),'creating the file keeps Settings open');
    await page.setViewportSize({width:390,height:844});assert(await page.locator('#settingsSetupFileCreate').isVisible());
    assert.deepEqual(errors,[]);
    console.log('Native team setup file: import confirmation and per-section saves, ID-only file creation, Settings stays open, mobile width passed.');
  } finally { await browser.close(); fs.rmSync(dir,{recursive:true,force:true}); }
})().catch(error=>{console.error(error);process.exit(1);});
