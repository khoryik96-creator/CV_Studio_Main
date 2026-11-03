"""Optional Chromium workflow against job_leads_email_composer_server.py.

All companion/public replies are fictional; external browser requests are blocked.
Requires Playwright and Chromium. Run from the repository root.
"""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
source=Path(__file__).with_name('job_ads_background.py').read_text()
mock=source.split("MOCK=r'''",1)[1].split("'''",1)[0].replace('Array.from({length:25}','Array.from({length:3}')
mock=mock.replace("if(m.action==='jobFromLink'){window.jobFixture.reads.push(m.args);", "if(m.action==='jobFromLink'){if(window.jobFixture.reads.length!==1){window.jobFixture.reads.push(m.args);window.postMessage({type:'CVSTUDIO_LINKEDIN_RESPONSE',id:m.id,channel:m.channel,error:'Synthetic unknown browser layout',error_code:'HR_AD_LAYOUT'},origin);return;}window.jobFixture.reads.push(m.args);")
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path=os.environ.get('CVSTUDIO_CHROMIUM','/usr/bin/chromium'),args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1450,'height':1000})
    errors=[];public=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.context.route('**/*',lambda route:route.continue_() if route.request.url.startswith('http://127.0.0.1:5077/') else route.abort())
    def public_limit(route):
        data=route.request.post_data_json if route.request.method=='POST' else {}
        if data.get('action')!='lookup':return route.continue_()
        public.append(data['url'])
        route.fulfill(status=429,content_type='application/json',headers={'Retry-After':'120'},body=json.dumps({'error':'Synthetic public rate limit','code':'JOB_AD_RATE_LIMITED','retry_after_seconds':120}))
    page.route('**/job-leads',public_limit)
    assert page.request.get('http://127.0.0.1:5077/__job_leads_email_fixture__').json()['fictional_email_fixture']
    before=page.request.get('http://127.0.0.1:5077/job-leads').json()['records']
    page.add_init_script(mock);page.goto('http://127.0.0.1:5077/?module=jobleads')
    page.locator('#jobLeadsList tr').filter(has_text='Finance Manager 1').wait_for()
    page.locator('#jobLeadsSearchQuery').fill('database administrator');page.locator('#jobLeadsSearchPages').fill('1');page.locator('#jobLeadsSearchStart').click()
    page.wait_for_function('()=>window.jobFixture.reads.length===2')
    assert len(public)==1
    assert 'Public reads paused; Chrome companion only' in page.locator('#jobLeadsBackgroundStatus').inner_text()
    assert page.locator('#jobLeadsBackgroundStop').is_visible(),'public rate limit does not stop companion capture'
    second=page.locator('.job-leads-discovery-card').nth(1);second.locator('.job-ad-company').click()
    page.evaluate('()=>window.jobFixture.release()')
    page.wait_for_function('()=>document.getElementById("jobLeadsBackgroundStop").hidden')
    assert page.evaluate('()=>window.jobFixture.reads.length')==3 and len(public)==1
    status=page.locator('#jobLeadsBackgroundStatus').inner_text()
    assert '1 of 3 full ads ready' in status and '2 could not load' in status
    assert page.locator('#jobLeadsPreviewContent strong').count()>0,'healthy companion content is ready despite the public limit'
    first=page.locator('.job-leads-discovery-card').first;first.locator('.job-ad-company').click();page.locator('#jobLeadsPreviewRead').click()
    page.wait_for_function('()=>!document.getElementById("jobLeadsPreviewRead").disabled')
    assert len(public)==1,'manual retries also honor the public cooldown'
    assert page.request.get('http://127.0.0.1:5077/job-leads').json()['records']==before
    assert not errors,errors
    print('Chromium rate-limit workflow passed: one public 429, companion queue continues, rich cached content remains, failed summaries survive, manual retry does not repeat public traffic; no live provider action.')
    browser.close()
