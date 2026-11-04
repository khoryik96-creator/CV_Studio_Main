"""Optional Chromium activity-state check against the isolated local fixture.

Run job_leads_email_composer_server.py first, from the repository root.
Companion replies are fictional and external browser requests are blocked.
"""
from pathlib import Path
import os
from playwright.sync_api import sync_playwright
source=Path('tests/browser/job_ads_background.py').read_text();mock=source.split("MOCK=r'''",1)[1].split("'''",1)[0]
mock=mock.replace('window.jobFixture={reads:[],cancel:[]};','window.jobFixture={reads:[],cancel:[],searchPage:0};')
original=next(line for line in mock.splitlines() if line.startswith("if(m.action==='read')"))
replacement=r'''if(m.action==='read'){
 if(m.args.method==='nextJobSearch'){window.jobFixture.searchPage++;return reply(true);}
 const p=window.jobFixture.searchPage;
 const snapshot={jobs:Array.from({length:25},(_,i)=>({url:'https://www.linkedin.com/jobs/view/'+(4444444400+p*25+i),role:'SAP FICO Consultant '+(p*25+i+1),company:'Example Company '+(i+1),location:'Kuala Lumpur',description:'Keyword-matched search summary'})),signature:'page-'+p,hasNext:p<2,atBottom:true};
 if(p===2){window.jobFixture.releaseSearch=()=>reply(window.jobFixture.failSearch?null:snapshot,window.jobFixture.failSearch?'Synthetic search failure':undefined);return;}
 return reply(snapshot);
}'''
mock=mock.replace(original,replacement)
out=Path('/tmp/cvstudio555');out.mkdir(exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=os.environ.get('CVSTUDIO_CHROMIUM','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
 for mode in ['complete','stop','failure']:
  page=b.new_page(viewport={'width':1450,'height':1080});errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
  page.context.route('**/*',lambda route:route.continue_() if route.request.url.startswith('http://127.0.0.1:5077/') else route.abort())
  assert page.request.get('http://127.0.0.1:5077/__job_leads_email_fixture__').json()['fictional_email_fixture']
  page.add_init_script(mock);page.goto('http://127.0.0.1:5077/?module=jobleads');page.locator('#jobLeadsList tr').filter(has_text='Finance Manager 1').wait_for()
  page.locator('#jobLeadsSearchQuery').fill('SAP fico');page.locator('#jobLeadsSearchPages').fill('3');page.locator('#jobLeadsSearchStart').click()
  page.wait_for_function('()=>window.jobFixture.releaseSearch')
  status=page.locator('#jobLeadsSearchStatus');results=page.locator('#jobLeadsSearchResults');stop=page.locator('#jobLeadsSearchStop')
  assert status.inner_text()=='Reviewed 2 of 3 pages. 50 unique ads found.'
  assert results.get_attribute('aria-busy')=='true'
  assert status.evaluate('(el)=>getComputedStyle(el).animationName')=='job-search-activity'
  assert float(results.evaluate('(el)=>getComputedStyle(el).opacity'))<.8
  assert results.evaluate('(el)=>getComputedStyle(el).filter')=='grayscale(1)'
  assert stop.is_visible() and stop.is_enabled() and stop.evaluate('(el)=>getComputedStyle(el).opacity')=='1'
  if mode=='complete':
   page.locator('#jobLeadsSearchPanel').screenshot(path=str(out/'search-running.png'))
   page.emulate_media(reduced_motion='reduce')
   assert status.evaluate('(el)=>getComputedStyle(el).animationName')=='none'
   assert status.evaluate('(el)=>getComputedStyle(el).borderTopStyle')=='solid'
   page.set_viewport_size({'width':390,'height':844})
   assert status.evaluate('(el)=>el.scrollWidth<=el.clientWidth+1')
   assert results.evaluate('(el)=>el.scrollWidth<=el.clientWidth+1')
   page.set_viewport_size({'width':1450,'height':1080});page.emulate_media(reduced_motion='no-preference')
  if mode=='stop':
   stop.click();assert status.evaluate('(el)=>el.classList.contains("is-running")'),'stopping stays visible until the current read settles'
  if mode=='failure':page.evaluate('()=>window.jobFixture.failSearch=true')
  page.evaluate('()=>window.jobFixture.releaseSearch()')
  page.wait_for_function('()=>document.getElementById("jobLeadsSearchResults").getAttribute("aria-busy")==="false"')
  page.wait_for_function('()=>getComputedStyle(document.getElementById("jobLeadsSearchResults")).opacity==="1"')
  assert not status.evaluate('(el)=>el.classList.contains("is-running")')
  if mode=='complete':
   page.wait_for_function('()=>window.jobFixture.release')
   background=page.locator('#jobLeadsBackgroundStatus')
   assert background.evaluate('(el)=>getComputedStyle(el).animationName')=='job-search-activity'
   assert page.locator('#jobLeadsSearchSelectPage').is_enabled()
   page.locator('#jobLeadsSearchPanel').screenshot(path=str(out/'background-running.png'))
   page.locator('#jobLeadsBackgroundStop').click();page.wait_for_function('()=>document.getElementById("jobLeadsBackgroundStop").hidden')
   assert not background.evaluate('(el)=>el.classList.contains("is-running")')
  else:assert not page.locator('#jobLeadsBackgroundStatus').evaluate('(el)=>el.classList.contains("is-running")')
  assert not errors,errors
  page.close()
 print('Chromium activity visuals passed: 50 streamed results dimmed, orange animated progress, enabled Stop, completion/Stop/error cleanup, usable background queue, reduced motion and narrow-screen wrapping. Screenshots: '+str(out))
 b.close()
