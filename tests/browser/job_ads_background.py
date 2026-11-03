"""Optional Chromium check for the list-first background ad workflow.

Run job_leads_email_composer_server.py first. Uses fictional companion replies,
blocks external browser requests, and requires Playwright plus Chromium.
"""
import os
from playwright.sync_api import sync_playwright
from pathlib import Path
MOCK=r'''(()=>{
const origin=location.origin;window.jobFixture={reads:[],cancel:[]};
window.addEventListener('message',event=>{
const m=event.data;if(event.source!==window||m?.type!=='CVSTUDIO_LINKEDIN_REQUEST'||m.scope!=='leads')return;
const reply=(result,error)=>window.postMessage({type:'CVSTUDIO_LINKEDIN_RESPONSE',id:m.id,channel:m.channel,result,error},origin);
if(m.action==='jobStatus')return reply({connected:true,concurrent_scans_revision:1,job_search:true,job_search_revision:1,full_ad_background_revision:1,busy:false});
if(m.action==='jobSearchBegin')return reply({tab_id:20});
if(m.action==='end')return reply(true);
if(m.action==='read')return reply({jobs:Array.from({length:25},(_,i)=>({url:'https://www.linkedin.com/jobs/view/'+(4444444400+i),role:'SAP FICO Consultant '+(i+1),company:'Example Company '+(i+1),location:'Kuala Lumpur',description:'Keyword-matched search summary '+(i+1)})),signature:'sample-list',hasNext:false,atBottom:true,paginationKnown:true});
if(m.action==='jobFromLink'){window.jobFixture.reads.push(m.args);window.jobFixture.release=()=>{window.jobFixture.release=null;reply({url:m.args.url,role:'SAP FICO Consultant '+m.args.url.slice(-2),company:'Example Company',location:'Kuala Lumpur',description:'Full description loaded in the background. SAP FICO experience required.',description_html:'<p><b>Full description loaded in the background.</b> SAP FICO experience required.</p>'});};return;}
if(m.action==='jobReadCancel'){window.jobFixture.cancel.push(m.args);reply(true);window.jobFixture.release?.();return;}
console.error('Unexpected fixture RPC',m.action);
});})();'''
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path=os.environ.get('CVSTUDIO_CHROMIUM','/usr/bin/chromium'),args=['--no-sandbox'])
 page=b.new_page(viewport={'width':1450,'height':1000});errors=[]
 page.on('pageerror',lambda error:errors.append(str(error)))
 page.context.route('**/*',lambda route:route.continue_() if route.request.url.startswith('http://127.0.0.1:5077/') else route.abort())
 assert page.request.get('http://127.0.0.1:5077/__job_leads_email_fixture__').json()['fictional_email_fixture']
 page.add_init_script(MOCK)
 page.goto('http://127.0.0.1:5077/?module=jobleads')
 page.locator('#jobLeadsList tr').filter(has_text='Finance Manager 1').wait_for()
 page.locator('#jobLeadsSearchQuery').fill('SAP fico');page.locator('#jobLeadsSearchPages').fill('1')
 page.locator('#jobLeadsSearchStart').click()
 page.wait_for_function('()=>window.jobFixture.release && document.querySelectorAll(".job-leads-discovery-card").length===20')
 assert page.locator('#jobLeadsSearchCount').inner_text().startswith('25 found')
 assert page.locator('#jobLeadsSearchAdd').is_disabled()
 assert page.locator('#jobLeadsSearchNext').is_enabled()
 region=page.locator('#jobLeadsSearchResults');first=region.locator('article').first
 second=region.locator('article').nth(1)
 assert first.get_by_role('button',name='Preview',exact=True).count()==0,'the separate Preview button is removed'
 second.locator('.job-ad-company').click()
 assert '2 of 25' in page.locator('#jobLeadsPreviewPosition').inner_text(),'card content opens its preview'
 first.get_by_role('checkbox').check();first.locator('summary').click()
 assert '2 of 25' in page.locator('#jobLeadsPreviewPosition').inner_text(),'selection and expandable summaries do not activate the card'
 with page.expect_popup() as popup:first.get_by_role('link',name='Open on LinkedIn').click()
 popup.value.close()
 assert '2 of 25' in page.locator('#jobLeadsPreviewPosition').inner_text(),'LinkedIn links keep their own action'
 first.locator('.job-ad-card-title').focus();page.keyboard.press('Enter')
 assert '1 of 25' in page.locator('#jobLeadsPreviewPosition').inner_text(),'the title is a native keyboard preview button'
 second.locator('.job-ad-card-title').focus();page.keyboard.press('Space')
 assert '2 of 25' in page.locator('#jobLeadsPreviewPosition').inner_text()
 first.locator('.job-ad-company-mark').click()
 assert '1 of 25' in page.locator('#jobLeadsPreviewPosition').inner_text(),'card whitespace/initials open the preview too'
 page.evaluate('''()=>{const company=document.querySelectorAll('.job-ad-company')[1],range=document.createRange();range.selectNodeContents(company);const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);company.dispatchEvent(new MouseEvent('click',{bubbles:true}));}''')
 assert '1 of 25' in page.locator('#jobLeadsPreviewPosition').inner_text(),'selecting card text does not switch previews'
 page.evaluate('()=>window.getSelection().removeAllRanges()')
 assert page.evaluate('()=>window.jobFixture.reads.length')==1,'preview clicks do not trigger more companion reads'
 first.locator('.job-ad-card-title').focus()
 page.evaluate('()=>document.getElementById("jobLeadsSearchResults").scrollTop=220')
 assert page.locator('#jobLeadsSearchAdd').is_enabled()
 page.evaluate('()=>window.jobFixture.release()')
 page.wait_for_function('()=>window.jobFixture.reads.length===2')
 assert first.locator('details').evaluate('(el)=>el.open')
 assert page.evaluate('()=>document.activeElement.classList.contains("job-ad-card-title")')
 assert region.evaluate('(el)=>el.scrollTop')==220
 assert first.inner_text().find('Full ad captured')>=0
 assert page.locator('#jobLeadsPreviewContent strong').count()>0
 # Background redraws must also preserve keyboard focus on links/summaries.
 for selector in ['a[href]','summary']:
  first.locator(selector).first.focus()
  previous=page.evaluate('()=>window.jobFixture.reads.length')
  page.evaluate('()=>window.jobFixture.release()')
  page.wait_for_function('(previous)=>window.jobFixture.reads.length===previous+1',arg=previous)
  assert first.locator(selector).first.evaluate('(el)=>el===document.activeElement'),selector+' lost focus during background update'
 Path('/tmp/cvstudio550').mkdir(exist_ok=True)
 region.scroll_into_view_if_needed();page.screenshot(path='/tmp/cvstudio550/background-job-ads.png')
 page.locator('#jobLeadsBackgroundStop').click()
 page.wait_for_function('()=>document.getElementById("jobLeadsBackgroundStop").hidden')
 assert page.evaluate('()=>window.jobFixture.cancel.length')==1
 assert page.evaluate('()=>window.jobFixture.reads.length')==4
 assert page.locator('#jobLeadsBackgroundStatus').inner_text().startswith('3 of 25')
 page.set_viewport_size({'width':390,'height':844})
 second.locator('.job-ad-company').click()
 assert '2 of 25' in page.locator('#jobLeadsPreviewPosition').inner_text(),'mobile card taps open the selected preview'
 page.wait_for_function('()=>{const r=document.getElementById("jobLeadsPreview").getBoundingClientRect();return r.top<innerHeight && r.bottom>0;}')
 assert page.locator('#jobLeadsCuration').evaluate('(el)=>el.scrollWidth<=el.clientWidth+1')
 assert page.evaluate('()=>window.jobFixture.reads.length')==4
 page.locator('#jobLeadsSearchClear').click();page.wait_for_function('()=>document.getElementById("jobLeadsSearchResults").children.length===0')
 assert not errors,errors
 print('Chromium passed: 25 summaries first, sequential capture, rich preview, desktop/mobile card click and keyboard preview, independent controls/text selection, stable scroll/button/link/summary focus/expanded content, Stop and Clear; no page errors or external requests.')
 b.close()
