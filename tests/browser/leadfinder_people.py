"""Actual UI with fictional companion/API responses; no live provider actions."""
from playwright.sync_api import sync_playwright
ORIGIN='http://127.0.0.1:5077'
MOCK=r'''(()=>{window.peopleFixture={opened:0,closed:0,held:false};window.addEventListener('message',event=>{const m=event.data;if(event.source!==window||m?.type!=='CVSTUDIO_LINKEDIN_REQUEST'||m.scope!=='leads')return;let result;if(m.action==='jobStatus')result={lead_people_revision:1};else if(m.action==='leadPeopleBegin'){window.peopleFixture.opened++;result={tab_id:11};}else if(m.action==='leadPeopleRead')result=window.peopleFixture.held?{loading:true}:{url:'https://www.linkedin.com/search/results/people/?keywords=Elitez',profiles:[{name:'Fictional HR',title:'HR Manager at Elitez',url:'https://www.linkedin.com/in/fictional-hr',text:'Fictional HR HR Manager at Elitez Malaysia'}],signature:'one',empty:false};else if(m.action==='end'){window.peopleFixture.closed++;result=true;}else return;window.postMessage({type:'CVSTUDIO_LINKEDIN_RESPONSE',id:m.id,channel:m.channel,result},location.origin);});})();'''
company={'id':'one','company':'Elitez','matched_role':'Software Engineer','job_url':'https://sg.jobstreet.com/job/95258471','job_portal':'JobStreet'}
person={'id':'pe1','name':'Fictional HR','title':'HR Manager at Elitez','company':'Elitez','profile_url':'https://www.linkedin.com/in/fictional-hr','source_url':'https://www.linkedin.com/in/fictional-hr'}
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    for mode in ['deepseek','anthropic','stop']:
        ctx=browser.new_context(viewport={'width':1440,'height':1000});page=ctx.new_page();calls=[];errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        def route(r):
            if r.request.url==ORIGIN+'/lead-finder/find-people':
                body=r.request.post_data_json;calls.append(body)
                data={'ok':True,'people':[person],'provider':body['provider'],'model':body['model'],'usage':{},'cost':0}
                if body.get('action')=='companion_plan':data={'ok':True,'companies':[company],'plan':[{'company':'Elitez','query':'Elitez HR'}]}
                r.fulfill(json=data)
            elif r.request.url.startswith(ORIGIN+'/'):r.continue_()
            else:r.abort()
        page.route('**/*',route);page.add_init_script(MOCK);page.goto(ORIGIN+'/')
        provider='deepseek' if mode=='stop' else mode
        page.evaluate("(args)=>{leadFinderSetUnlocked();switchTab('leadfinder');_leadCompanies=normalizeLeadData({companies:[args.company]}).companies;aiRoutePayload=()=>({provider:args.provider,model:args.provider==='deepseek'?'deepseek-v4-flash':'claude-sonnet-4-6',api_key:'fictional'});renderLeadFinder();}",{'company':company,'provider':provider})
        if mode=='stop':page.evaluate('()=>peopleFixture.held=true')
        page.locator('#leadSubCompanies').click();page.locator('#btnLeadPeopleSearchShown').click()
        if mode=='stop':
            page.wait_for_function('()=>peopleFixture.opened===1');page.locator('#leadPeopleStop').click()
            page.wait_for_function('()=>peopleFixture.closed===1 && !_leadPeopleAbort')
            assert len(calls)==1 and calls[0]['action']=='companion_plan'
        else:
            page.wait_for_function('()=>_leadPeople.length===1 && !_leadPeopleAbort')
            assert page.locator('#leadPeopleBox').inner_text().find('Fictional HR')>=0
            if mode=='deepseek':
                assert [c['action'] for c in calls]==['companion_plan','companion_review']
                assert calls[1]['observed_people'][0]['company']=='Elitez'
                assert page.evaluate('()=>peopleFixture.closed')==1
            else:
                assert len(calls)==1 and 'action' not in calls[0]
                assert page.evaluate('()=>peopleFixture.opened')==0
        assert not errors,errors
        ctx.close()
    browser.close()
print('Chromium: DeepSeek observes/reviews real-card-shaped input, Claude retains legacy request, Stop cleans up and prevents AI review. Fictional responses only.')
