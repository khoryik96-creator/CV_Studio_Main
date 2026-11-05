"""Numbered pages in Chromium, using isolated state and fictional companion data."""
from pathlib import Path
from playwright.sync_api import sync_playwright
ORIGIN='http://127.0.0.1:5077'
source=Path('tests/browser/job_ads_background.py').read_text()
mock=source.split("MOCK=r'''",1)[1].split("'''",1)[0]
mock=mock.replace('window.jobFixture={reads:[],cancel:[]};','window.jobFixture={reads:[],cancel:[],page:0};')
old=next(line for line in mock.splitlines() if line.startswith("if(m.action==='read')"))
mock=mock.replace(old,"""if(m.action==='read'){
 if(m.args.method==='nextJobSearch'){window.jobFixture.page++;return reply(true);}
 const p=window.jobFixture.page;
 return reply({jobs:Array.from({length:25},(_,i)=>({url:'https://www.linkedin.com/jobs/view/'+(4444444400+p*25+i),role:'SAP FICO Consultant '+(p*25+i+1),company:'Example Company '+(p*25+i+1),location:'Kuala Lumpur',description:'Search summary'})),signature:'page-'+p,hasNext:p<2,atBottom:true,paginationKnown:true});
}""")
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1450,'height':1080});errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.route('**/*',lambda route:route.continue_() if route.request.url.startswith(ORIGIN+'/') else route.abort())
    assert page.request.get(ORIGIN+'/__job_leads_email_fixture__').json()['fictional_email_fixture']
    page.add_init_script(mock);page.goto(ORIGIN+'/?module=jobleads')
    page.locator('#jobLeadsList tr').first.wait_for()
    page.locator('#jobLeadsSearchQuery').fill('SAP fico');page.locator('#jobLeadsSearchPages').fill('3');page.locator('#jobLeadsSearchStart').click()
    page.wait_for_function('()=>window.jobFixture.release && document.getElementById("jobLeadsSearchResults").getAttribute("aria-busy")==="false"')
    nav=page.get_by_role('navigation',name='Job search result pages')
    assert nav.get_by_role('button',name='Page 4',exact=True).is_visible()
    assert page.locator('#jobLeadsSearchColumn').locator('#jobLeadsSearchPagination').count()==1
    page.locator('#jobLeadsSearchResults article').first.get_by_role('checkbox').check()
    nav.get_by_role('button',name='Page 4',exact=True).click()
    assert page.locator('#jobLeadsSearchPageRange').inner_text()=='61–75 of 75'
    assert page.locator('#jobLeadsSearchResults article').count()==15
    assert '61 of 75' in page.locator('#jobLeadsPreviewPosition').inner_text()
    assert nav.get_by_role('button',name='Page 4',exact=True).get_attribute('aria-current')=='page'
    assert page.evaluate('()=>document.activeElement.textContent')=='4','keyboard focus follows the chosen page'
    nav.get_by_role('button',name='Page 1',exact=True).click()
    assert page.locator('#jobLeadsSearchResults article').first.get_by_role('checkbox').is_checked()
    assert page.evaluate('()=>window.jobFixture.reads.length')==1,'pagination does not trigger another ad read'
    page.locator('#jobLeadsBackgroundStop').click()
    page.wait_for_function('()=>document.getElementById("jobLeadsBackgroundStop").hidden')
    for width in [1450,390]:
        page.set_viewport_size({'width':width,'height':1080 if width>400 else 844})
        assert nav.evaluate('(el)=>el.scrollWidth<=el.clientWidth+1'),'page controls fit the column'
        assert page.locator('#jobLeadsSearchColumn').evaluate('(el)=>el.scrollWidth<=el.clientWidth+1')
    page.set_viewport_size({'width':1450,'height':1080})
    nav.screenshot(path='/tmp/cv-studio-job-pages.png')
    assert not errors,errors
    browser.close()
print('Chromium numbered pages: direct jump, accessible current page/focus, retained selection, no repeated read and desktop/mobile layout passed.')
