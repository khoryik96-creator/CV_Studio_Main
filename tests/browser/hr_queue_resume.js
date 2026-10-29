/* Optional native UI regression. Requires Playwright/Chromium; uses actual
 * markup/CSS/controller with fictional records and companion replies only.
 * All network is blocked. No real browser, account or stored record is used.
 */
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {chromium}=require(process.env.CVSTUDIO_PLAYWRIGHT || 'playwright');
const root=path.resolve(__dirname,'../..');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const css=fs.readFileSync(path.join(root,'vendor/cvstudio/app.css'),'utf8');
const controller=fs.readFileSync(path.join(root,'vendor/cvstudio/job-leads.js'),'utf8');
(async()=>{
  const browser=await chromium.launch({headless:true});
  try {
    const context=await browser.newContext({viewport:{width:1360,height:960}});
    await context.route('**/*',route=>route.request().url()==='http://127.0.0.1:5519/'?route.fulfill({contentType:'text/html',body:'<!doctype html><body></body>'}):route.abort());
    const page=await context.newPage();await page.goto('http://127.0.0.1:5519/');await page.addStyleTag({content:css});
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.evaluate(markup=>{
      const parsed=new DOMParser().parseFromString(markup,'text/html');document.body.append(document.importNode(parsed.getElementById('viewJobLeads'),true));document.querySelector('#viewJobLeads').classList.add('active');
      window.hrNative={hold:true,starts:[],saved:[],active:null,records:[1,2,3].map(n=>({id:String(n).repeat(32),revision:1,url:'https://www.linkedin.com/jobs/view/111111111'+n,company:'Fictional Company '+n,role:'Example role',folder:'',status:'new',description:'',description_rich:[],description_truncated:false,contact:'',location:'',date_posted:'',notes:'Keep these notes',follow_up:'',deleted:false,created_at:'2026-10-01T00:00:00Z'}))};
      window.fetch=async(url,options)=>{
        if(url!=='/job-leads')throw Error('Unexpected or paid route');const s=hrNative,data=options?.body?JSON.parse(options.body):null;
        if(!data)return {ok:true,json:async()=>({records:structuredClone(s.records),folders:[]})};
        if(data.action!=='save_hr')throw Error('Unexpected write');const row=s.records.find(row=>row.id===data.id);
        if(row.revision!==data.revision)throw Error('Stale save');row.hr={...data.search,scanned_at:'2026-10-29T00:00:00Z'};row.revision++;s.saved.push(row.id);
        return {ok:true,json:async()=>({record:structuredClone(row)})};
      };
      window.postMessage=message=>{
        if(message.type!=='CVSTUDIO_LINKEDIN_REQUEST')return;
        const s=hrNative,{action,args}=message,reply=result=>window.dispatchEvent(new MessageEvent('message',{source:window,origin:location.origin,data:{type:'CVSTUDIO_LINKEDIN_RESPONSE',channel:message.channel,id:message.id,result}}));
        if(action==='jobStatus')return reply({connected:true,company_hr_revision:1,hr_company_identity_revision:1,hr_company_filter_revision:1,hr_company_source_revision:1,hr_resilience_revision:1,hr_layout_revision:1,hr_apply_transition_revision:1,hr_joined_revision:1,hr_joined_loading_revision:1,hr_employment_revision:1,hr_keyword_revision:1,profile_browsing_revision:1,concurrent_scans_revision:1,busy:false});
        if(action==='jobSearchTabs')return reply([]);
        if(action==='jobFromLink'){s.active=s.records.find(row=>row.url===args.url);return reply({url:s.active.url,company:s.active.company,company_url:'https://www.linkedin.com/company/example-'+s.active.id[0]+'/'});}
        if(action==='hrBegin'){s.starts.push(s.active.id);return reply({tab_id:30});}
        if(action==='hrRead')return reply({company_id:s.active.id[0],source_url:'https://www.linkedin.com/search/results/people/?currentCompany=%5B%22'+s.active.id[0]+'%22%5D',signature:'one',hasNext:false,empty:false,people:[{name:'Fictional Person '+s.active.id[0],title:'HR Partner',location:'Malaysia',matched:'HR',url:'https://www.linkedin.com/in/example-'+s.active.id[0]}]});
        if(action==='hrJoined')return reply({url:args.url,joined:'2026-10',left:'',current:true});
        if(action==='hrJoinedClose' && s.hold && s.active.id[0]==='2'){s.release=()=>reply(true);return;}
        if(['hrJoinedClose','end'].includes(action))return reply(true);
        throw Error('Unexpected companion action '+action);
      };
    },html);
    await page.addScriptTag({content:controller});await page.evaluate(()=>initJobLeads());
    await page.locator('#jobLeadsList button').filter({hasText:'HR people'}).first().click();
    await page.locator('#jobLeadsSelectPage').check();await page.locator('#jobLeadsBulkHRStart').click();
    await page.waitForFunction(()=>typeof hrNative.release==='function');
    assert.equal(await page.locator('#jobLeadsHRResults').getByText('Employment: Oct 2026 to Present',{exact:true}).count(),1);
    await page.locator('#jobLeadsBulkHRStop').click();await page.evaluate(()=>hrNative.release());
    await page.getByRole('button',{name:'Resume unfinished ads',exact:true}).waitFor();
    await page.evaluate(()=>{hrNative.hold=false;});await page.getByRole('button',{name:'Resume unfinished ads',exact:true}).click();
    await page.waitForFunction(()=>hrNative.saved.length===3 && !document.querySelector('#jobLeadsBulkHRStart').disabled);
    assert.deepEqual(await page.evaluate(()=>hrNative.starts.map(id=>id[0])),['1','2','2','3']);
    assert.equal(await page.locator('#jobLeadsBulkHRBar').getAttribute('max'),'3');
    assert.equal(await page.locator('#jobLeadsBulkHRBar').evaluate(n=>n.value),3);
    assert.equal(await page.locator('#jobLeadsBulkHRStart').textContent(),'Scan selected ads');
    assert((await page.locator('#jobLeadsBulkHRResults').innerText()).includes('Previously saved'));
    if(process.env.CVSTUDIO_TEST_SCREENSHOT_DIR){fs.mkdirSync(process.env.CVSTUDIO_TEST_SCREENSHOT_DIR,{recursive:true});await page.locator('#jobLeadsBulkHRProgress').screenshot({path:path.join(process.env.CVSTUDIO_TEST_SCREENSHOT_DIR,'hr519_resume.png')});}
    assert.deepEqual(errors,[]);await context.close();
    console.log('Native HR UI: immediate date, Stop, resume button, confirmed-save skipping, unfinished order and honest cumulative progress passed');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
