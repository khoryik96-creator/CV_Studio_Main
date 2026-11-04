"""Local browser fixture: fictional ads, no live search/AI calls or keys."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json

ORIGIN = 'http://127.0.0.1:5077'
AD = 'https://my.jobstreet.com/job/87401944'
SEARCH = 'https://www.google.com/search?q=%22Nov%202026%22%20%22Software%20Engineer%20%28with%20Salaries%29%22%20site%3Amy.jobstreet.com'
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];requests=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    def route(r):
        if r.request.url == ORIGIN+'/lead-finder/search':
            requests.append(r.request.post_data_json)
            r.fulfill(json={'ok':True,'companies':[
                {'company':'Nov 2026','matched_role':'Software Engineer (with Salaries)','job_url':'','source_url':SEARCH,'job_url_quality':'needs_verification'},
                {'company':'Fictional Systems','matched_role':'Software Engineer','country':'Malaysia','job_url':AD,'job_portal':'JobStreet','job_fit_percent':85}
            ],'people':[],'summary':{'candidate_title':'Software Engineer','search_provider_used':'tavily','job_source_counts':[{'source':'JobStreet','count':1},{'source':'LinkedIn Jobs','count':0}]},'usage':{},'cost':0})
        elif r.request.url.startswith(ORIGIN+'/'):r.continue_()
        else:r.abort()
    page.route('**/*',route)
    page.goto(ORIGIN+'/')
    page.evaluate("()=>{leadFinderSetUnlocked();switchTab('leadfinder');window._hSearchProvider='tavily';window._hSearchProviderKey='fictional';aiRoutePayload=()=>({provider:'deepseek',model:'deepseek-v4-flash',api_key:'fictional'});renderLeadFinder();}")
    assert page.locator('#leadSearchProvider').inner_text()=='Search: Tavily'
    assert not page.locator('.lead-options').evaluate('(n)=>n.open')
    page.locator('.lead-options > summary').click()
    assert page.locator('#leadContext').is_visible()
    page.locator('.lead-options > summary').click()
    page.locator('#leadCvText').fill('Fictional Software Engineer in Malaysia. Python backend development and SQL. '*3)
    page.locator('#btnLeadSearch').click()
    page.wait_for_function("()=>document.getElementById('leadSearchStatus').textContent.includes('1 job ad(s) found · Tavily')")
    assert requests[0]['search_provider']=={'provider':'tavily','api_key':'fictional'}
    assert page.locator('#leadKpiCompanies').inner_text()=='1'
    assert 'Ads by source:' in page.locator('#leadSummaryBox').inner_text()
    assert 'LinkedIn Jobs: 0' in page.locator('#leadSummaryBox').inner_text()
    page.locator('#leadSubCompanies').click()
    assert page.locator('#leadCompaniesBox .lead-company-card').count()==1
    assert page.locator('#leadCompaniesBox a').get_attribute('href')==AD
    assert 'Nov 2026' not in page.locator('#leadCompaniesBox').inner_text()
    page.locator('#viewLeadFinder').screenshot(path='/workspace/outputs/leadfinder-results.png')
    google='https://www.google.com/about/careers/applications/jobs/results/123456789-software-engineer/'
    page.evaluate("(url)=>{_leadCompanies=normalizeLeadData({companies:[{job_url:url,company:'Google',matched_role:'Software Engineer'}]}).companies;_leadSummary={candidate_title:'Software Engineer'};renderLeadFinder();switchLeadSubtab('companies');}",google)
    assert page.locator('#leadCompaniesBox .lead-company-card').count()==1
    assert page.locator('#leadCompaniesBox a').get_attribute('href')==google
    page.set_viewport_size({'width':390,'height':844})
    page.locator('.lead-options > summary').click()
    assert page.locator('#leadMustHave').is_visible()
    assert not errors,errors
    browser.close()
print('Chromium: simple form, More options, saved Tavily selection in search payload, direct-ad-only results/KPI, and narrow viewport checked. No live provider calls.')
