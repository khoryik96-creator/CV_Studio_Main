"""Real Chromium, real support route, fictional Graph; never sends live email."""
import io
import json
import zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright

ORIGIN='http://127.0.0.1:58484'
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1280,'height':1000},accept_downloads=True)
    context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(ORIGIN+'/') else route.abort())
    page=context.new_page()
    assert page.request.get(ORIGIN+'/__support_fixture__').json()['fictional_support_fixture']
    page.add_init_script('''
      window.captureStops=0;
      Object.defineProperty(navigator.mediaDevices,'getDisplayMedia',{value:async()=>{
        const canvas=document.createElement('canvas');canvas.width=640;canvas.height=360;
        const ctx=canvas.getContext('2d');ctx.fillStyle='navy';ctx.fillRect(0,0,640,360);
        ctx.fillStyle='white';ctx.font='24px sans-serif';ctx.fillText('Fictional CV Studio issue',20,60);
        const stream=canvas.captureStream(10);for(const track of stream.getTracks()){
          const stop=track.stop.bind(track);track.stop=()=>{window.captureStops++;stop();};
        }return stream;
      }});
    ''')
    page.goto(ORIGIN+'/')
    page.locator('#cvSupportBadge').wait_for()
    page.evaluate("console.warn('PRIVATE-CV-CONTENT-OMIT');cvStudioSupport.recordIssue({module:'Job Leads',code:'JOBADDER_CONTACT_UNCONFIRMED',http_status:201,result_reason:'missing_contact_id'})")
    page.locator('#cvSupportBadge').click()
    page.locator('#cvSupportDescription').fill('A fictional Create in JobAdder result could not be confirmed.')
    page.locator('#cvSupportSteps').fill('Review the fictional contact, then click Create.')
    page.locator('#cvSupportCapture').click()
    page.locator('#cvSupportScreenshot').wait_for(state='visible')
    assert page.evaluate('window.captureStops')==1
    page.locator('#cvSupportReview').click()
    page.locator('#cvSupportSend').wait_for(state='visible')
    assert page.locator('#cvSupportSender').inner_text()=='reporter@example.test'
    assert page.locator('#cvSupportRecipient').inner_text()=='support@example.test'
    assert 'JOBADDER_CONTACT_UNCONFIRMED' in page.locator('#cvSupportDoctor').text_content()
    assert 'PRIVATE-CV-CONTENT-OMIT' not in page.locator('#cvSupportDoctor').text_content()
    with page.expect_download() as download:
        page.locator('#cvSupportDownload').click()
    raw=Path(download.value.path()).read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert set(archive.namelist())=={'report.txt','doctor-report.txt','runtime.json','screenshot.jpg'}
        assert b'PRIVATE-CV-CONTENT-OMIT' not in archive.read('doctor-report.txt')
        assert b'fictional-token' not in archive.read('runtime.json')
    assert page.request.get(ORIGIN+'/__support_fixture__').json()['sends']==0
    def cancel(dialog):dialog.dismiss()
    page.on('dialog',cancel);page.locator('#cvSupportSend').click();page.remove_listener('dialog',cancel)
    assert page.request.get(ORIGIN+'/__support_fixture__').json()['sends']==0
    page.on('dialog',lambda dialog:dialog.accept())
    page.locator('#cvSupportSend').dblclick()
    page.wait_for_function("() => document.getElementById('cvSupportMessage').textContent.includes('Outlook accepted')")
    result=page.request.get(ORIGIN+'/__support_fixture__').json()
    assert result['sends']==1
    assert result['messages'][0]['message']['toRecipients']==[{'emailAddress':{'address':'support@example.test'}}]
    page.locator('#cvSupportNew').click();page.locator('#cvSupportReview').click()
    page.locator('#cvSupportSend').wait_for(state='visible')
    def lose_response(route):
        if route.request.method=='POST' and route.request.post_data_json.get('action')=='issue_send':
            route.fetch();route.abort()
        else:route.continue_()
    page.route('**/diagnostics/support_bundle',lose_response)
    page.locator('#cvSupportSend').click()
    page.locator('#cvSupportCheck').wait_for(state='visible')
    page.wait_for_function("() => !document.getElementById('cvSupportCheck').disabled")
    page.locator('#cvSupportCheck').click()
    page.wait_for_function("() => document.getElementById('cvSupportMessage').textContent.includes('Outlook accepted')")
    assert page.request.get(ORIGIN+'/__support_fixture__').json()['sends']==2
    page.unroute('**/diagnostics/support_bundle',lose_response)
    page.request.post(ORIGIN+'/__support_fixture__/disconnect',headers={'X-CV-Studio-Request':'1'})
    page.locator('#cvSupportNew').click();page.locator('#cvSupportReview').click()
    page.wait_for_function("() => document.getElementById('cvSupportMessage').textContent.includes('Connect Outlook')")
    assert page.locator('#cvSupportSend').is_disabled()
    assert page.locator('#cvSupportDownload').is_enabled()
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.getElementById("cvSupportDialog").scrollWidth <= document.getElementById("cvSupportDialog").clientWidth')
    page.locator('#cvSupportConnect').click()
    assert not page.locator('#cvSupportDialog').is_visible()
    assert page.locator('#settingsPanel').is_visible()
    page.evaluate("closeSettingsPanel();switchTab('jobleads');document.getElementById('jobLeadsJADialog').showModal()")
    page.locator('#jobLeadsJADialog [data-cv-support]').click()
    page.locator('#cvSupportDialog').wait_for(state='visible')
    page.evaluate("document.getElementById('jobLeadsJAClose').disabled=true")
    page.locator('#cvSupportConnect').click()
    assert 'Wait for the current contact request' in page.locator('#cvSupportMessage').inner_text()
    assert page.locator('#jobLeadsJADialog').is_visible()
    page.evaluate("document.getElementById('jobLeadsJAClose').disabled=false")
    page.locator('#cvSupportConnect').click()
    assert not page.locator('#jobLeadsJADialog').is_visible()
    assert page.locator('#settingsPanel').is_visible()
    browser.close()
print('PASS: capture/stop, redacted Doctor, ZIP, confirmation cancel, one send, lost-response recovery, disconnected Outlook, mobile, nested contact dialog, Settings')
