"""Optional Chromium checks for loading documents and cached full-ad queues.

Run job_leads_email_composer_server.py first. All browser/companion/public replies
are fictional; external requests are intercepted. Run from the repository root.
"""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
url='https://www.linkedin.com/jobs/view/1234567890'
html='''<main><section class="job-view-layout"><h1 class="job-details-jobs-unified-top-card__job-title"><a href="https://www.linkedin.com/jobs/view/1234567890">Database Administrator</a></h1><div class="job-details-jobs-unified-top-card__company-name"><a href="https://www.linkedin.com/company/fictional/">Fictional Employer</a></div><div id="job-details"><p><strong>Ready ad description</strong></p><p>Manage database operations.</p></div></section><img src="https://www.linkedin.com/held-resource.png"></main>'''
source=Path(__file__).with_name('job_ads_background.py').read_text()
mock=source.split("MOCK=r'''",1)[1].split("'''",1)[0].replace('Array.from({length:25}','Array.from({length:3}').replace('(4444444400+i)','(i===0?90001:4444444400+i)')
mock=mock.replace("if(m.action==='jobFromLink'){window.jobFixture.reads.push(m.args);", "if(m.action==='jobFromLink'){if(!window.jobFixture.reads.length){window.jobFixture.reads.push(m.args);window.postMessage({type:'CVSTUDIO_LINKEDIN_RESPONSE',id:m.id,channel:m.channel,error:'The LinkedIn ad did not finish loading. Open it in your browser, wait for the page to load, then try again.'},origin);return;}window.jobFixture.reads.push(m.args);")
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CVSTUDIO_CHROMIUM','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
    context=browser.new_context();page=context.new_page();pending=[]
    def document_page(route):
        if route.request.url==url:return route.fulfill(status=200,content_type='text/html',body=html)
        if route.request.url.endswith('/held-resource.png'):pending.append(route);return
        route.abort()
    context.route('**/*',document_page)
    page.goto(url,wait_until='domcontentloaded')
    page.add_script_tag(content=Path('vendor/linkedin-companion/reader.js').read_text())
    result=page.evaluate('(url)=>SourcerReader.readJob(url)',url)
    assert result['url']==url and 'Ready ad description' in result['description'] and 'strong' in result['description_html']
    assert page.evaluate('document.readyState')!='complete','the browser load event is deliberately still pending'
    for route in pending:route.fulfill(status=204,body='')
    context.close()

    context=browser.new_context();page=context.new_page();errors=[];reads=[];writes=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    context.route('**/*',lambda route:route.continue_() if route.request.url.startswith('http://127.0.0.1:5077/') else route.abort())
    def data(route):
        if route.request.method=='GET':
            response=route.fetch();body=response.json()
            for row in body.get('records',[]):
                if row['url']=='https://www.linkedin.com/jobs/view/90001':
                    row.update(description='Saved complete ad body',description_truncated=False,description_rich=[{'tag':'p','children':[{'tag':'strong','children':[{'text':'Saved complete ad body'}]}]}])
            return route.fulfill(status=200,content_type='application/json',body=json.dumps(body))
        body=route.request.post_data_json
        if body.get('action')=='lookup':
            reads.append(body['url']);return route.fulfill(status=422,content_type='application/json',body=json.dumps({'error':'Synthetic unavailable public ad','code':'JOB_AD_UNAVAILABLE'}))
        if body.get('action')!='format_content':writes.append(body)
        route.continue_()
    page.route('**/job-leads',data)
    assert page.request.get('http://127.0.0.1:5077/__job_leads_email_fixture__').json()['fictional_email_fixture']
    page.add_init_script(mock);page.goto('http://127.0.0.1:5077/?module=jobleads')
    page.locator('#jobLeadsList tr').filter(has_text='Finance Manager 1').wait_for()
    page.locator('#jobLeadsSearchQuery').fill('SAP fico');page.locator('#jobLeadsSearchPages').fill('1');page.locator('#jobLeadsSearchStart').click()
    page.wait_for_function('()=>window.jobFixture.reads.length===2')
    assert page.locator('.job-leads-discovery-card').first.get_by_text('Saved full ad',exact=True).count()==1
    assert '1 of 3 full ads ready' in page.locator('#jobLeadsBackgroundStatus').inner_text()
    assert page.locator('#jobLeadsBackgroundStop').is_visible(),'the next ad is still being captured after a loading timeout'
    assert page.evaluate('()=>window.jobFixture.reads.every(read=>read.url!=="https://www.linkedin.com/jobs/view/90001")')
    assert page.locator('#jobLeadsPreviewContent strong').inner_text()=='Saved complete ad body'
    page.locator('#jobLeadsPreviewRead').click();assert page.evaluate('()=>window.jobFixture.reads.length')==2
    page.evaluate('()=>window.jobFixture.release()');page.wait_for_function('()=>document.getElementById("jobLeadsBackgroundStop").hidden')
    assert '2 of 3 full ads ready' in page.locator('#jobLeadsBackgroundStatus').inner_text()
    assert '1 could not load' in page.locator('#jobLeadsBackgroundStatus').inner_text()
    assert len(reads)==1 and not writes and not errors,(reads,writes,errors)
    print('Chromium recovery passed: content read before browser load completes; saved full content reused without opening it, an old loading timeout falls back without stopping the next ad, and cache/readiness remain correct. No live provider actions.')
    browser.close()
