/* Optional native regression: node tests/browser/apollo_contacts_visibility.js
 * Requires Playwright/Chromium. CVSTUDIO_PLAYWRIGHT may name its installed module.
 * Uses actual panel markup, CSS and Apollo controller with synthetic fetch only.
 * No running CV Studio, account, provider, network or owner records are needed.
 */
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {chromium}=require(process.env.CVSTUDIO_PLAYWRIGHT || 'playwright');
const root=path.resolve(__dirname,'../..');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const css=fs.readFileSync(path.join(root,'vendor/cvstudio/app.css'),'utf8');
const controller=fs.readFileSync(path.join(root,'vendor/cvstudio/job-leads-apollo.js'),'utf8');
async function mount(context){
  const page=await context.newPage();
  await page.setContent('<!doctype html><html><head></head><body></body></html>');
  await page.addStyleTag({content:css});
  await page.evaluate(markup=>{
    const parsed=new DOMParser().parseFromString(markup,'text/html');
    document.body.append(document.importNode(parsed.getElementById('viewJobLeads'),true));
    document.getElementById('viewJobLeads').classList.add('active');
    window.contactTestCalls=[];
    window.fetch=async(url,options)=>{
      if(url!=='/apollo')throw Error('Unexpected route');
      const action=options?.body?JSON.parse(options.body).action:'status';
      window.contactTestCalls.push(action);
      if(!['status','contacts'].includes(action))throw Error('Unexpected paid/account action');
      const contacts=Array.from({length:44},(_,i)=>({name:'Fictional contact '+i,position:'HR',company:'Example',country:'Malaysia',email:'person'+i+'@example.test',email_status:'verified',profile_url:'https://www.linkedin.com/in/person-'+i}));
      return {ok:true,json:async()=>action==='status'?{ok:true,available:false,connected:false}:{ok:true,contacts}};
    };
  },html);
  await page.addScriptTag({content:controller});
  await page.evaluate(()=>window.cvStudioApollo.init());
  return page;
}
async function visibility(page,contactsVisible){
  assert.equal(await page.locator('#jobLeadsApolloContactsPanel').isVisible(),contactsVisible,'contacts must follow the selected view, including actual CSS');
  assert.equal(await page.locator('#jobLeadsApolloAdsPanel').isVisible(),!contactsVisible,'only one view must be rendered');
  assert.equal(await page.locator('#jobLeadsApolloContactsTab').getAttribute('aria-pressed'),String(contactsVisible));
  if(!contactsVisible)assert.equal(await page.locator('#jobLeadsApolloContactsPanel').evaluate(n=>getComputedStyle(n).display),'none');
}
(async()=>{
  const browser=await chromium.launch({headless:true});
  try{
    const context=await browser.newContext({viewport:{width:1360,height:960}});
    await context.route('**/*',route=>route.abort());
    for(const viewport of [{width:1360,height:960},{width:390,height:844}]){
      const page=await mount(context);await page.setViewportSize(viewport);
      await visibility(page,false);
      await page.locator('#jobLeadsnotes').fill('Keep this unsaved ad draft');
      await page.locator('#jobLeadsApolloContactsTab').click();
      await page.waitForFunction(()=>document.getElementById('jobLeadsApolloContactsCount').textContent==='44');
      await visibility(page,true);
      await page.locator('#jobLeadsApolloContactsSearch').fill('person42@example.test');
      assert.equal(await page.locator('#jobLeadsApolloContactsRows tr').count(),1);
      await page.locator('#jobLeadsApolloAdsTab').click();await visibility(page,false);
      assert.equal(await page.locator('#jobLeadsnotes').inputValue(),'Keep this unsaved ad draft');
      await page.locator('#jobLeadsApolloContactsTab').click();await visibility(page,true);
      assert.equal(await page.locator('#jobLeadsApolloContactsSearch').inputValue(),'person42@example.test');
      await page.locator('#jobLeadsApolloAdsTab').click();await visibility(page,false);
      assert((await page.evaluate(()=>window.contactTestCalls)).every(action=>['status','contacts'].includes(action)));
      await page.close();
      const reloaded=await mount(context);await reloaded.setViewportSize(viewport);
      await visibility(reloaded,false);await reloaded.close();
    }
    console.log('Native contact visibility: initial/selected/returned/fresh views at desktop/mobile, draft/search retention and zero paid actions passed.');
  }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
