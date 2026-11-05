"""Company-name anchors use validated employer pages; external traffic is mocked."""
from playwright.sync_api import sync_playwright
ORIGIN='http://127.0.0.1:5077'
FIRST='https://www.linkedin.com/company/fictional-employer/'
SECOND='https://www.linkedin.com/company/fictional-hr-employer/'
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1450,'height':1000});errors=[];opened=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    def route(r):
        if r.request.url in [FIRST,SECOND]:
            opened.append(r.request.url);r.fulfill(body='<h1>Fictional LinkedIn employer page</h1>',content_type='text/html')
        elif r.request.url==ORIGIN+'/job-leads' and r.request.method=='GET':
            response=r.fetch();data=response.json();first,second=data['records'][:2]
            first['company_url']=FIRST
            second.pop('company_url',None)
            second['hr']={'company':second['company'],'company_url':SECOND,'company_id':'4242','people':[],'country':'Malaysia','keywords':'HR','pages':1,'scanned_at':'2026-11-05T00:00:00Z'}
            r.fulfill(response=response,json=data)
        elif r.request.url.startswith(ORIGIN+'/'):r.continue_()
        else:r.abort()
    page.context.route('**/*',route)
    assert page.request.get(ORIGIN+'/__job_leads_email_fixture__').json()['fictional_email_fixture']
    page.goto(ORIGIN+'/?module=jobleads');page.locator('#jobLeadsList tr').first.wait_for()
    links=page.locator('#jobLeadsList .job-lead-company-link')
    assert links.nth(0).get_attribute('href')==FIRST
    assert links.nth(1).get_attribute('href')==SECOND
    for index,url in [(0,FIRST),(1,SECOND)]:
        link=links.nth(index);assert link.get_attribute('target')=='_blank' and 'noopener' in link.get_attribute('rel')
        with page.expect_popup() as popup:link.click()
        popup.value.wait_for_url(url);assert popup.value.locator('h1').inner_text()=='Fictional LinkedIn employer page';popup.value.close()
    assert opened==[FIRST,SECOND]
    assert page.locator('#jobLeadsList tr').first.get_by_role('button',name='Edit',exact=True).is_visible()
    page.locator('#jobLeadsList tr').first.screenshot(path='/tmp/cv-studio-company-links.png')
    assert not errors,errors
    browser.close()
print('Chromium company links: captured and existing HR employer links open the correct new tab, with external pages mocked and editing controls intact.')
