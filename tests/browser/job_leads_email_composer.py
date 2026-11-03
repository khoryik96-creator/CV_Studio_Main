"""Optional Chromium workflow check against job_leads_email_composer_server.py.

Requires Playwright and /usr/bin/chromium; no real emails or Microsoft login.
"""
from playwright.sync_api import sync_playwright
from PIL import Image
from pathlib import Path
import io,uuid,os
out=Path('/tmp/cvstudio547');out.mkdir(exist_ok=True)
image=io.BytesIO();Image.new('RGB',(688,171),'#e6b54f').save(image,format='PNG')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path=os.environ.get('CVSTUDIO_CHROMIUM','/usr/bin/chromium'),args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1550,'height':1150})
    errors=[];email_posts=[];confirmations=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.route('**/*',lambda route:route.continue_() if route.request.url.startswith('http://127.0.0.1:5077/') or route.request.url.startswith('data:') else route.abort())
    assert page.request.get('http://127.0.0.1:5077/__job_leads_email_fixture__').json()['fictional_email_fixture']
    def record(request):
        if request.method=='POST' and request.url.endswith(('/job-leads','/ppc/outlook/create_draft')):
            data=request.post_data_json
            if data.get('action')=='outlook_send' or request.url.endswith('create_draft'):email_posts.append(data)
    page.on('request',record)
    page.goto('http://127.0.0.1:5077/?module=jobleads')
    row=page.locator('#jobLeadsList tr').filter(has_text='Finance Manager 1');row.wait_for()
    row.get_by_role('button',name='Email client',exact=True).click()
    page.locator('#jobLeadsEmailAccount').filter(has_text='owner@example.com').wait_for()
    page.wait_for_function("()=>!document.getElementById('jobLeadsEmailTemplateRefresh').disabled")
    assert page.locator('#jobLeadsEmailTo').input_value()=='alex@example.com'
    page.locator('#jobLeadsEmailTo').fill('alex@example.com; second@example.com')
    page.locator('#jobLeadsEmailCc').fill('cc@example.com')
    page.locator('#jobLeadsEmailBcc').fill('private@example.com')
    page.locator('#jobLeadsEmailSubject').fill('Your hiring plans')
    page.locator('#jobLeadsEmailEditor').fill('Hi Alex,\n\nLet us discuss your hiring plans.\n\nBest regards,\nGuok')
    # Mixed rich HTML/text + a file image must retain the entire signature.
    import base64
    page.evaluate("""encoded=>{
      const editor=document.getElementById('jobLeadsEmailEditor'),data=new DataTransfer();
      data.setData('text/html','<p>Best regards,</p><p><b>Full signature</b></p>');
      data.setData('text/plain','Best regards, Full signature');
      data.items.add(new File([Uint8Array.from(atob(encoded),c=>c.charCodeAt(0))],'clipboard.png',{type:'image/png'}));
      editor.focus();editor.dispatchEvent(new ClipboardEvent('paste',{clipboardData:data,bubbles:true,cancelable:true}));
    }""",base64.b64encode(image.getvalue()).decode())
    page.locator('#jobLeadsEmailEditor img').wait_for()
    assert 'Full signature' in page.locator('#jobLeadsEmailEditor').inner_text()
    assert page.locator('#jobLeadsEmailEditor b').filter(has_text='Full signature').count()==1
    page.locator('#jobLeadsEmailEditor').fill('Hi Alex, best regards Guok')
    page.evaluate("""()=>{const editor=document.getElementById('jobLeadsEmailEditor'),range=document.createRange();range.selectNodeContents(editor);const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);}""")
    page.get_by_role('button',name='Bold',exact=True).click()
    assert '<b>' in page.locator('#jobLeadsEmailEditor').inner_html() or '<strong>' in page.locator('#jobLeadsEmailEditor').inner_html()
    page.locator('#jobLeadsEmailFont').select_option('Georgia')
    page.locator('#jobLeadsEmailSize').select_option('4')
    assert 'Georgia' in page.locator('#jobLeadsEmailEditor').inner_html()
    page.evaluate("""()=>{const editor=document.getElementById('jobLeadsEmailEditor');editor.innerHTML='<p>Hi Alex,</p><p>Let us discuss your hiring plans.</p><p>Best regards,</p><p><b><i>Guok</i></b><br><a href="mailto:guok@example.com" style="color:#005bb4;font-size:10pt">guok@example.com</a></p>';editor.dispatchEvent(new Event('input',{bubbles:true}));}""")
    page.locator('#jobLeadsEmailImage').set_input_files({'name':'banner.png','mimeType':'image/png','buffer':image.getvalue()})
    page.locator('#jobLeadsEmailEditor img').wait_for()
    page.locator('#jobLeadsEmailMessage').filter(has_text='Banner embedded').wait_for()
    page.locator('#jobLeadsEmailFiles').set_input_files({'name':'brief.txt','mimeType':'text/plain','buffer':b'Hiring brief'})
    page.locator('#jobLeadsEmailAttachments').filter(has_text='brief.txt').wait_for()
    page.locator('#jobLeadsEmailTemplateName').fill('Client introduction '+uuid.uuid4().hex[:8])
    page.locator('#jobLeadsEmailTemplateCopy').click()
    page.locator('#jobLeadsEmailTemplateMessage').filter(has_text='Template saved').wait_for()
    template_id=page.locator('#jobLeadsEmailTemplate').input_value();assert template_id
    page.locator('#jobLeadsEmailSubject').fill('Updated introduction')
    page.locator('#jobLeadsEmailTemplateSave').click()
    page.wait_for_function("()=>!document.getElementById('jobLeadsEmailTemplateSave').disabled")
    page.locator('#jobLeadsEmailTemplateRefresh').click()
    page.wait_for_function("()=>!document.getElementById('jobLeadsEmailTemplateRefresh').disabled")
    saved=next(value for value in page.request.get('http://127.0.0.1:5077/job-leads?action=email_templates').json()['templates'] if value['id']==template_id)
    response=page.request.post('http://127.0.0.1:5077/job-leads',headers={'X-CV-Studio-Request':'1'},data={**saved,'action':'email_template_save','subject':'Changed in another window'})
    assert response.ok
    page.locator('#jobLeadsEmailTemplateRefresh').click()
    page.wait_for_function("()=>!document.getElementById('jobLeadsEmailTemplateRefresh').disabled")
    page.locator('#jobLeadsEmailTemplateSave').click()
    page.locator('#jobLeadsEmailTemplateMessage').filter(has_text='changed in another window').wait_for()
    assert page.locator('#jobLeadsEmailSubject').input_value()=='Updated introduction','refresh must not silently adopt a newer edit revision'
    page.once('dialog',lambda d:d.accept())
    page.locator('#jobLeadsEmailTemplateUse').click()
    assert page.locator('#jobLeadsEmailSubject').input_value()=='Changed in another window'
    page.locator('#jobLeadsEmailSubject').fill('Updated introduction')
    page.locator('#jobLeadsEmailTemplateSave').click()
    page.wait_for_function("()=>!document.getElementById('jobLeadsEmailTemplateSave').disabled")
    page.once('dialog',lambda d:(confirmations.append(d.message),d.dismiss()))
    page.locator('#jobLeadsEmailSend').click()
    page.wait_for_function("()=>!document.getElementById('jobLeadsEmailSend').disabled")
    assert not email_posts,'cancelling confirmation must not send'
    assert all(value in confirmations[-1] for value in ['alex@example.com','second@example.com','cc@example.com','private@example.com','brief.txt','Embedded images: 1'])
    page.locator('#jobLeadsEmailCard').screenshot(path=str(out/'signature-composer.png'))
    page.once('dialog',lambda d:d.accept())
    page.locator('#jobLeadsEmailDraft').click()
    page.locator('#jobLeadsEmailOpen').wait_for(state='visible')
    assert len(email_posts)==1 and len(email_posts[0]['attachments'])==1
    assert len(email_posts[0]['to'])==2 and email_posts[0]['bcc']==['private@example.com']
    assert 'data:image/png;base64,' in email_posts[0]['html']
    assert page.locator('#jobLeadsEmailEditor').get_attribute('contenteditable')=='false'
    page.locator('#jobLeadsEmailNew').click()
    page.wait_for_function("()=>!document.getElementById('jobLeadsEmailTemplate').disabled")
    page.locator('#jobLeadsEmailTemplate').select_option(template_id)
    assert page.locator('#jobLeadsEmailSubject').input_value()=='Updated introduction'
    assert page.locator('#jobLeadsEmailEditor img').count()==1
    assert page.locator('#jobLeadsEmailTo').input_value()=='' and page.locator('#jobLeadsEmailCc').input_value()==''
    assert page.locator('#jobLeadsEmailAttachments li').count()==0
    page.locator('#jobLeadsEmailTo').fill('alex@example.com')
    page.once('dialog',lambda d:(confirmations.append(d.message),d.accept()))
    page.locator('#jobLeadsEmailSend').click()
    page.locator('#jobLeadsEmailMessage').filter(has_text='Accepted by Outlook').wait_for()
    assert len(email_posts)==2 and email_posts[-1]['confirmed'] is True
    page.locator('#jobLeadsEmailSend').click(force=True,timeout=1000) if not page.locator('#jobLeadsEmailSend').is_disabled() else None
    assert len(email_posts)==2
    page.locator('#jobLeadsEmailNew').click()
    page.wait_for_function("()=>!document.getElementById('jobLeadsEmailTemplate').disabled")
    page.locator('#jobLeadsEmailTemplate').select_option(template_id)
    page.once('dialog',lambda d:d.accept())
    page.locator('#jobLeadsEmailTemplateDelete').click()
    page.locator('#jobLeadsEmailTemplateMessage').filter(has_text='Template deleted').wait_for()
    assert page.locator('#jobLeadsEmailEditor img').count()==1,'deleting a template preserves current message'
    assert page.locator('#jobLeadsEmailTemplate option[value="'+template_id+'"]').count()==0
    assert not errors,errors
    print('Browser passed: recipient autofill, multiple To/CC/BCC, rich signature and inline banner upload, attachment upload, template create/update/refresh/apply/delete, recipient and file separation, cancelled/confirmed send, draft creation, completed editor lock; fictional Outlook only.')
    browser.close()
