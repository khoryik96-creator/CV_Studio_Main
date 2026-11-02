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
    assert.match(dialogs[0],/Not in this file[\s\S]*JobAdder Client Secret[\s\S]*Main AI key/,'the import lists what the file leaves out');
    assert.match(await page.locator('#settingsSetupFileStatus').textContent(),/Filled in: Outlook, OneNote\. JobAdder: Client ID filled in\. Enter the Client Secret/);
    assert.equal(await page.inputValue('#settingsOutlookClientId'),GUID);assert.equal(await page.inputValue('#settingsJobAdderClientId'),'example-ja-client');
    assert.equal(await page.evaluate(()=>localStorage.getItem('onenote_ms_client_id')),GUID2,'OneNote is saved through its own Save');
    await page.locator('#settingsSetupFileCard summary').click();
    // Every column shows, with the saved IDs and tenants filled in.
    const heads=await page.locator('#settingsSetupFileCard .setup-file-head span').allTextContents();
    assert.deepEqual(heads,['App','Application (client) ID','Tenant','Client Secret','Used for','Provider','API key']);
    await page.waitForFunction(id=>document.getElementById('settingsSetupOutlookId').value===id,GUID);
    assert.deepEqual(await Promise.all(['#settingsSetupJobAdderId','#settingsSetupOutlookId','#settingsSetupOutlookTenant','#settingsSetupOneNoteId','#settingsSetupOneNoteTenant'].map(id=>page.inputValue(id))),
      ['example-ja-client',GUID,'common',GUID2,'common']);
    for(const id of ['#settingsSetupJobAdderSecret','#settingsSetupKeyAnthropic','#settingsSetupKeyOpenai','#settingsSetupKeyDeepseek','#settingsSetupLeadKey','#settingsSetupSearchKey','#settingsSetupEnrichmentKey'])
      assert(await page.locator(id).isVisible(),id+' is shown');
    await page.screenshot({path:path.join(process.env.CVSTUDIO_SCREENSHOTS||dir,'setup_file_columns.png'),clip:await page.locator('#settingsSetupFileCard').boundingBox()});
    await page.fill('#settingsSetupOneNoteTenant','contoso.onmicrosoft.com');
    const download=page.waitForEvent('download');await page.locator('#settingsSetupFileCreate').click();
    const created=JSON.parse(fs.readFileSync(await (await download).path(),'utf8'));
    assert.deepEqual([created.product,created.schema,created.jobadder,created.outlook,created.onenote],['CV Studio setup',2,{client_id:'example-ja-client'},{client_id:GUID,tenant:'common'},{client_id:GUID2,tenant:'contoso.onmicrosoft.com'}]);
    assert.equal(created.ai,undefined,'no secret is added unless typed');
    assert.match(await page.locator('#settingsSetupFileStatus').textContent(),/Not in the file: JobAdder Client Secret, Main AI key/);
    assert(await page.locator('#settingsSetupFileCard').isVisible(),'creating the file keeps Settings open');
    await page.setViewportSize({width:390,height:844});assert(await page.locator('#settingsSetupFileCreate').isVisible());
    // On a phone each box carries its own column name and nothing overflows.
    assert(await page.locator('#settingsSetupFileCard .setup-file-col').first().isVisible());assert(!await page.locator('#settingsSetupFileCard .setup-file-head').first().isVisible());
    assert(await page.locator('#settingsSetupFileCard').evaluate(card=>card.scrollWidth<=card.clientWidth+1),'no sideways scrolling');
    await page.locator('#settingsSetupFileCard').screenshot({path:path.join(process.env.CVSTUDIO_SCREENSHOTS||dir,'setup_file_phone.png')});
    assert.deepEqual(errors,[]);
    console.log('Native team setup file: import confirmation with missing items, per-section saves, every column shown and filled in, ID-only file creation, Settings stays open, phone layout passed.');
  } finally { await browser.close(); fs.rmSync(dir,{recursive:true,force:true}); }
})().catch(error=>{console.error(error);process.exit(1);});
