"""Optional Chromium recovery + title/favicon tests; start the isolated composer server first.
All LinkedIn, companion, verifier and AI replies are fictional; no provider calls.
"""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
ORIGIN='http://127.0.0.1:5077'
URL='https://www.linkedin.com/jobs/view/4456899159/'
posting={'@type':'JobPosting','identifier':{'value':'4456899159'},'url':URL,'datePosted':'2026-11-01T23:30:00-04:00','title':'Fictional Systems Engineer','hiringOrganization':{'name':'Fictional Employer'},'description':'<img src="https://fictional-resource.invalid/pixel"><iframe src="https://fictional-resource.invalid/frame"></iframe><p><strong>Complete fictional duties.</strong></p><ul><li>Maintain systems.</li></ul>'}
html='<main><h1>Fictional job view</h1></main><script type="application/ld+json">'+json.dumps(posting).replace('<','\\u003c')+'</script>'
source=Path('tests/browser/job_ads_background.py').read_text()
job_mock=source.split("MOCK=r'''",1)[1].split("'''",1)[0].replace('Array.from({length:25}','Array.from({length:3}')
sourcer_mock=r'''(()=>{const source={id:3,url:'https://www.linkedin.com/search/results/people/',title:'Fictional People search'};window.addEventListener('message',event=>{const m=event.data;if(event.source!==window||m?.type!=='CVSTUDIO_LINKEDIN_REQUEST'||m.scope!=='profiles')return;let result;if(m.action==='tabs')result=[source];else if(m.action==='openPeopleSearch')result=source;else if(m.action==='jobStatus')result={connected:true,profile_browsing_revision:1,concurrent_scans_revision:1,people_results_revision:1,people_country_revision:1,people_country_ready_revision:1};else if(['begin','end','navigate'].includes(m.action))result=true;else if(m.action==='read')result={profiles:[],signature:'empty',empty:true,hasNext:false,paginationKnown:true};else return;window.postMessage({type:'CVSTUDIO_LINKEDIN_RESPONSE',id:m.id,channel:m.channel,result},location.origin);});})();'''
def badge(page,feature,failed=False):
    # The current feature remains active and focused: notifications must still appear.
    assert page.evaluate('()=>!document.hidden && document.hasFocus()')
    if failed:
        assert page.evaluate('(feature)=>!!BROWSER_ACTIVITY_FAIL_BY_TAB[feature]',feature)
        page.wait_for_function('()=>document.title.includes("🔴")')
    else:
        assert page.evaluate('(feature)=>BROWSER_ACTIVITY_DONE_BY_TAB[feature]',feature)==1
        assert '(1)' in page.title()
    assert page.locator('link[rel~="icon"]').first.get_attribute('href').startswith('data:image/')
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CVSTUDIO_CHROMIUM','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
    ctx=browser.new_context();page=ctx.new_page();ctx.route('**/*',lambda route:route.fulfill(status=200,content_type='text/html',body=html) if route.request.url==URL else route.abort())
    page.goto(URL);page.add_script_tag(content=Path('vendor/linkedin-companion/reader.js').read_text())
    record=page.evaluate('(url)=>SourcerReader.readJob(url)',URL.rstrip('/'))
    assert record['role']==posting['title'] and record['company']=='Fictional Employer' and '<strong>' in record['description_html']
    assert 'Maintain systems.' in record['description'] and record['date_posted']=='2026-11-01'
    page.locator('h1').evaluate('(node)=>node.textContent="Sign in to LinkedIn"')
    assert page.evaluate('(url)=>{try{SourcerReader.readJob(url);return false;}catch(e){return true;}}',URL.rstrip('/'))
    page.locator('h1').evaluate('(node)=>node.textContent="Fictional job view"')
    assert page.evaluate('(url)=>{try{SourcerReader.readJob(url,true);return false;}catch(e){return !!e.cvstudioJobLoading;}}',URL.rstrip('/')),'HR company-only reads retain their DOM employer checks'
    for patch in [{'identifier':{'value':'999'}},{'url':'https://www.linkedin.com/jobs/view/999/'},{'description':''}]:
        page.locator('script[type="application/ld+json"]').evaluate('(node,value)=>node.textContent=JSON.stringify(value)',{**posting,**patch})
        assert page.evaluate('(url)=>{try{SourcerReader.readJob(url);return false;}catch(e){return !!e.cvstudioJobLoading;}}',URL.rstrip('/'))
    page.locator('script[type="application/ld+json"]').evaluate('(node,value)=>node.textContent=JSON.stringify(value)',{'@graph':[posting,{**posting,'title':'Conflicting role'}]})
    assert page.evaluate('(url)=>{try{SourcerReader.readJob(url);return false;}catch(e){return !!e.cvstudioJobLoading;}}',URL.rstrip('/'))
    page.locator('script[type="application/ld+json"]').evaluate('(node,value)=>node.textContent=JSON.stringify(value)',posting)
    page.locator('main').evaluate('(node,markup)=>node.innerHTML=markup','<div id="captcha-internal" style="width:200px;height:100px">Verification check</div>')
    assert page.evaluate('(url)=>{try{SourcerReader.readJob(url);return false;}catch(e){return /verification/.test(e.message);}}',URL.rstrip('/'))
    ctx.close()
    for feature in ['jobleads','linkedinsourcer','emailverifier']:
      for failed in [False,True]:
        ctx=browser.new_context();page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        ctx.route('**/*',lambda route:route.continue_() if route.request.url.startswith(ORIGIN+'/') else route.abort())
        assert page.request.get(ORIGIN+'/__job_leads_email_fixture__').json()['fictional_email_fixture']
        if feature=='jobleads':
          mock=job_mock
          if failed:
            mock=mock.replace('result,error},origin)',"result,error,...(error?{error_code:'HR_AD_TIMEOUT'}:{})},origin)")
            mock=mock.replace("reply({url:m.args.url", "if(window.jobFixture.reads.length===1){reply(null,'Fictional layout failure');return;}reply({url:m.args.url")
          page.add_init_script(mock)
          def leads(route):
            if route.request.method=='POST' and route.request.post_data_json.get('action')=='lookup':return route.fulfill(status=422,content_type='application/json',body=json.dumps({'error':'Fictional unavailable public page','code':'JOB_AD_UNAVAILABLE'}))
            route.continue_()
          page.route('**/job-leads',leads)
        elif feature=='linkedinsourcer':
          page.on('dialog',lambda d:d.accept('1212') if d.type=='prompt' else d.dismiss());page.add_init_script(sourcer_mock)
          run={'id':'a'*32,'calls':0,'max_calls':35,'tokens':0,'usage_complete':True,'stopped':False}
          def sourcer(route):
            data=route.request.post_data_json if route.request.method=='POST' else {};action=data.get('action')
            if action=='candidate_folders':value={'folders':[]}
            elif not action:value={'configured':True,'run':None}
            elif action=='plan' and failed:return route.fulfill(status=502,content_type='application/json',body=json.dumps({'error':'Fictional planning failure'}))
            elif action=='plan':value={'run':run,'plan':{'query':'Fictional','country':''}}
            else:value={'run':{**run,'stopped':action=='stop'}}
            route.fulfill(status=200,content_type='application/json',body=json.dumps(value))
          page.route('**/linkedin-sourcer',sourcer)
        else:
          page.route('**/email-verifier',lambda route:route.fulfill(status=500 if failed else 200,content_type='application/json',body=json.dumps({'ok':False,'error':'Fictional verification failure'} if failed else {'ok':True,'result':{'email':'person@example.com','status':'accepted','reason':'Fictional result','flags':[],'mode':'full','checked_at':'2026-11-04T00:00:00Z'}})))
        page.goto(ORIGIN+'/?module='+feature)
        if feature=='jobleads':
          page.locator('#jobLeadsList tr').first.wait_for();page.locator('#jobLeadsSearchQuery').fill('Fictional');page.locator('#jobLeadsSearchStart').click()
          for index in [1,2,3]:
            page.wait_for_function('(index)=>window.jobFixture.reads.length===index',arg=index)
            assert page.evaluate('()=>!BROWSER_ACTIVITY_DONE_BY_TAB.jobleads && !BROWSER_ACTIVITY_FAIL_BY_TAB.jobleads'),'search discovery must not notify before full-ad loading finishes'
            page.evaluate('()=>window.jobFixture.release()')
          page.wait_for_function('()=>document.getElementById("jobLeadsBackgroundStop").hidden')
        elif feature=='linkedinsourcer':
          page.wait_for_function('()=>!document.getElementById("liSourcerFolderNew").disabled');page.locator('#liSourcerBrief').fill('Fictional systems engineer');page.locator('#liSourcerConsent').check();page.locator('#liSourcerStart').click()
          page.wait_for_function('()=>!document.getElementById("liSourcerStart").disabled')
        else:
          page.locator('#emailVerifierInput').fill('person@example.com');page.locator('#emailVerifierStart').click();page.wait_for_function('()=>!document.getElementById("emailVerifierStart").disabled')
        badge(page,feature,failed)
        if failed:
          failed=False
          page.evaluate("()=>{const token=markTabRunning('format');markTabDone('format',token);}")
          if feature=='jobleads':
            page.locator('#jobLeadsSearchStart').click()
            for index in [4,5,6]:
              page.wait_for_function('(index)=>window.jobFixture.reads.length===index',arg=index);page.evaluate('()=>window.jobFixture.release()')
            page.wait_for_function('()=>document.getElementById("jobLeadsBackgroundStop").hidden')
          else:
            start='#liSourcerStart' if feature=='linkedinsourcer' else '#emailVerifierStart'
            page.locator(start).click();page.wait_for_function('(selector)=>!document.querySelector(selector).disabled',arg=start)
          assert page.evaluate('()=>BROWSER_ACTIVITY_DONE_BY_TAB.format')==1,'a retry must retain another module completion'
          page.evaluate("()=>ackBrowserActivityForTab('format')")
          assert not page.evaluate('(feature)=>!!BROWSER_ACTIVITY_FAIL_BY_TAB[feature]',feature),'a successful retry clears its previous failure'
          badge(page,feature)
        if not failed:
          page.evaluate('(feature)=>switchTab(feature)',feature);assert page.evaluate('()=>BROWSER_ACTIVITY_DONE_COUNT')==0
        assert not errors,errors
        ctx.close()
    browser.close()
print('Chromium: verified embedded full-ad recovery and strict identity/ambiguity/HR/captcha guards; all three modules show focused browser title/favicon Done or Failed; Job Leads waits for background completion; acknowledgement clears Done. No live provider calls.')
