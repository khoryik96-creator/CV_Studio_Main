"""Reviewable issue reports; no app import, provider call or background sending.

Prepared attachments stay in bounded process memory. Email delivery delegates to
Outlook's durable non-replay ledger, with the exact reviewed sender and content.
"""
from __future__ import annotations

import base64
import hashlib
import html
import io
import json
import re
import secrets
import threading
import time
import zipfile


class SupportReportError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class SupportReports:
    TTL = 900
    MAX_REPORTS = 8
    MAX_SCREENSHOT_BYTES = 1500000
    MAX_INPUT_BYTES = 3200000

    def __init__(self, *, recipient, version, runtime, redact, outlook_info, send_email, clock=time.time):
        self.recipient, self.version, self.runtime = recipient, version, runtime
        self.redact_text, self.outlook_info, self.send_email, self.clock = redact, outlook_info, send_email, clock
        self.lock = threading.RLock()
        self.reports = {}

    def _redact(self, value):
        text = self.redact_text(str(value or ''))
        text = re.sub(r'\bsk-(?:ant-api\d+-|proj-)?[A-Za-z0-9_-]{10,}', '[key redacted]', text)
        text = re.sub(r'(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*', 'Bearer [redacted]', text)
        text = re.sub(r'\b[A-Za-z0-9_-]{48,}\b', '[token redacted]', text)
        text = re.sub(r'(?i)(/(?:contacts|companies)/)\d+', r'\1[id redacted]', text)
        return text

    def _text(self, value, label, limit, required=False):
        if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
            raise SupportReportError('Check the '+label+'.')
        return self._redact(value.strip())

    def _destination(self):
        value = str(self.recipient() or '').strip()
        return value if len(value)<=254 and re.fullmatch(r'[A-Z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,63}',value,re.I) else ''

    def status(self):
        try:
            info = self.outlook_info() or {}
        except Exception:
            info = {}
        account = info.get('account') if isinstance(info.get('account'),dict) else {}
        return {'recipient':self._destination(),'connected':bool(info.get('connected')),
                'can_send':bool(info.get('connected') and info.get('can_send') and account.get('email') and self._destination()),
                'sender':str(account.get('email') or '')[:254]}

    def _runtime(self):
        try:
            raw = self.runtime()
        except Exception as exc:
            return {'version':str(self.version()),'diagnostics_available':False,'error_type':type(exc).__name__}
        if not isinstance(raw,dict):
            return {'version':str(self.version()),'diagnostics_available':False}
        result = {'version':str(self.version()),'runtime_mode':self._redact(str(raw.get('runtime_mode') or ''))[:40]}
        platform = raw.get('platform') if isinstance(raw.get('platform'),dict) else {}
        result['platform']={key:self._redact(str(platform.get(key) or ''))[:120] for key in ('system','release','machine','python')}
        memory = raw.get('memory') if isinstance(raw.get('memory'),dict) else {}
        result['memory']={key:value for key in ('total_bytes','available_bytes','used_percent')
                          if type(value:=memory.get(key)) in (int,float) and 0<=value<10**16}
        dependencies = raw.get('dependencies') if isinstance(raw.get('dependencies'),dict) else {}
        result['dependencies']={}
        for key,value in dependencies.items():
            if not re.fullmatch(r'[a-z_]{1,60}',str(key)):continue
            if type(value) is bool:result['dependencies'][key]=value
            elif isinstance(value,dict):
                result['dependencies'][key]={field:item for field in ('available','trusted','functional','test_only')
                                               if type(item:=value.get(field)) is bool}
        connections = raw.get('connections') if isinstance(raw.get('connections'),dict) else {}
        result['connections']={}
        for key,value in connections.items():
            if re.fullmatch(r'[a-z_]{1,40}',str(key)) and isinstance(value,dict):
                result['connections'][key]={field:item for field in ('connected','configured','available','can_send')
                                            if type(item:=value.get(field)) is bool}
        receipt = raw.get('install_receipt') if isinstance(raw.get('install_receipt'),dict) else {}
        result['install_receipt']={'valid':receipt.get('valid') is True,'status':self._redact(str(receipt.get('status') or ''))[:240]}
        return result

    def _screenshot(self, value):
        if value in (None,''):return None
        if not isinstance(value,str) or len(value)>2800000:
            raise SupportReportError('Use a smaller PNG or JPEG screenshot.')
        match=re.fullmatch(r'data:image/(png|jpeg);base64,([A-Za-z0-9+/=\r\n]+)',value)
        if not match:raise SupportReportError('Attach a PNG or JPEG screenshot.')
        try:
            raw=base64.b64decode(match[2],validate=True)
            if len(raw)>2100000:raise ValueError()
            from PIL import Image, ImageOps
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in {'PNG','JPEG'} or image.width*image.height>12000000:
                    raise ValueError()
                image.load()
                image=ImageOps.exif_transpose(image)
                if image.mode in ('RGBA','LA'):
                    background=Image.new('RGB',image.size,'white');background.paste(image,mask=image.getchannel('A'));image=background
                else:image=image.convert('RGB')
                image.thumbnail((1600,1600))
                output=io.BytesIO();image.save(output,format='JPEG',quality=85,optimize=True)
                normalized=output.getvalue()
                if len(normalized)>self.MAX_SCREENSHOT_BYTES:raise ValueError()
                return normalized
        except Exception:
            raise SupportReportError('This screenshot could not be read safely. Attach a smaller PNG or JPEG.') from None

    def _prune(self):
        now=self.clock()
        for identity in [key for key,record in self.reports.items() if record['expires']<=now]:
            del self.reports[identity]

    def _get(self, body):
        identity,token=body.get('report_id'),body.get('preview_token')
        if (not isinstance(identity,str) or not re.fullmatch(r'[a-f0-9]{32}',identity)
                or not isinstance(token,str) or not re.fullmatch(r'[a-f0-9]{64}',token)):
            raise SupportReportError('Prepare and review the report first.',409)
        self._prune();record=self.reports.get(identity)
        if not record or not secrets.compare_digest(record['proof'],hashlib.sha256(token.encode()).hexdigest()):
            raise SupportReportError('This report expired or the app restarted. Check Sent Items if sending was already attempted; nothing was resent.',409)
        return record

    def prepare(self, body):
        description=self._text(body.get('description',''),'issue description',4000,True)
        steps=self._text(body.get('steps',''),'steps',4000)
        module=self._text(body.get('module','General'),'module',80)
        title=self._text(body.get('title','Issue report'),'title',160,True)
        title=re.sub(r'[\x00-\x1f\x7f]',' ',title)
        doctor=self._text(body.get('doctor','Doctor recorder unavailable.'),'Doctor report',180000)
        screenshot=self._screenshot(body.get('screenshot'))
        runtime=self._runtime();delivery=self.status()
        browser=body.get('browser') if isinstance(body.get('browser'),dict) else {}
        runtime['browser']={key:self._redact(str(browser.get(key) or ''))[:400] for key in ('user_agent','timezone','active_view')}
        recent=[]
        for item in (body.get('recent_issues') if isinstance(body.get('recent_issues'),list) else [])[-20:]:
            if not isinstance(item,dict):continue
            recent.append({key:self._redact(str(item.get(key) or ''))[:160]
                           for key in ('at','module','operation','code','request_id','http_status','result_reason')})
        identity=secrets.token_hex(16);nonce=secrets.token_hex(32)
        stamp=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(self.clock()))
        text=('CV Studio issue report\nReport ID: '+identity+'\nVersion: '+str(self.version())+
              '\nModule: '+module+'\nCreated: '+stamp+'\n\nWhat happened\n'+description+
              ('\n\nSteps to reproduce\n'+steps if steps else '')+
              '\n\nDoctor and runtime diagnostics are attached.'+
              (' A screenshot is attached.' if screenshot else ''))
        doctor_text=('Report ID: '+identity+'\n\n'+doctor+'\n\nRecent application outcomes (no contact details)\n'+json.dumps(recent,indent=2))
        runtime.update(report_id=identity,created_at=stamp)
        files=[{'name':'doctor-report.txt','content':doctor_text.encode('utf-8'),'content_type':'text/plain'},
               {'name':'runtime.json','content':json.dumps(runtime,indent=2,ensure_ascii=False).encode('utf-8'),'content_type':'application/json'}]
        if screenshot:files.append({'name':'screenshot.jpg','content':screenshot,'content_type':'image/jpeg'})
        payload={'request_id':'job-email:'+identity,'sender':delivery['sender'],'to':[delivery['recipient']],
                 'subject':'[CV Studio '+str(self.version())+'] '+module+': '+title,
                 'html':'<p>'+html.escape(text).replace('\n','<br>')+'</p>',
                 'attachments':[{'name':item['name'],'contentBytes':base64.b64encode(item['content']).decode('ascii')} for item in files]}
        record={'id':identity,'proof':hashlib.sha256(nonce.encode()).hexdigest(),'expires':self.clock()+self.TTL,
                'state':'prepared','payload':payload,'files':files,'text':text,'result':None,
                'recipient':delivery['recipient'],'sender':delivery['sender']}
        with self.lock:
            self._prune()
            if len(self.reports)>=self.MAX_REPORTS:
                raise SupportReportError('Close an older prepared report or wait a few minutes before preparing another.',429)
            self.reports[identity]=record
        return {'report_id':identity,'preview_token':nonce,'state':'prepared','delivery':delivery,'text':text,
                'doctor':doctor_text,'runtime':runtime,
                'attachments':[{'name':item['name'],'bytes':len(item['content'])} for item in files],
                'screenshot':'data:image/jpeg;base64,'+base64.b64encode(screenshot).decode('ascii') if screenshot else ''}

    def download(self, body):
        with self.lock:
            record=self._get(body)
            files=list(record['files']);text=record['text'];identity=record['id']
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('report.txt',text)
            for item in files:archive.writestr(item['name'],item['content'])
        return output.getvalue(),'cv-studio-issue-'+identity[:12]+'.zip'

    def report_status(self, body):
        with self.lock:
            record=self._get(body)
            return {'report_id':record['id'],'state':record['state'],**(record['result'] or {})}

    def discard(self, body):
        with self.lock:
            record=self._get(body)
            if record['state']=='sending':raise SupportReportError('Wait for the current send result.',409)
            del self.reports[record['id']]
        return {'state':'discarded'}

    def send(self, body):
        with self.lock:
            record=self._get(body)
            if body.get('confirmed') is not True:
                raise SupportReportError('Review the report and confirm before sending.')
            if record['state']=='accepted':return {'ok':True,'state':'accepted','reused':True},200
            if record['state']!='prepared':
                return {'state':record['state'],'error':'Sending was already attempted. Check the report status or Outlook Sent Items; nothing was resent.'},409
            delivery=self.status()
            if not delivery['can_send']:
                return {'retry_safe':True,'error':'Connect Outlook and enable sending in Settings, then prepare the report again.'},403
            if delivery['sender'].lower()!=record['sender'].lower() or delivery['recipient']!=record['recipient']:
                return {'retry_safe':True,'error':'The sender or support inbox changed. Prepare and review the report again.'},409
            record['state']='sending';record['expires']=self.clock()+self.TTL
            payload={**record['payload'],'confirmed':True}
        try:
            result,status=self.send_email(payload)
            if not isinstance(result,dict) or type(status) is not int:raise ValueError()
        except Exception:
            result,status={'state':'unconfirmed','error':'The send result could not be confirmed. Check Outlook Sent Items; do not resend.'},502
        with self.lock:
            record['state']=('prepared' if result.get('retry_safe') is True else
                             'accepted' if result.get('ok') and result.get('state')=='accepted' else
                             'rejected' if result.get('state')=='rejected' else 'unconfirmed')
            safe={key:result[key] for key in ('ok','state','retry_safe','needs_reconnect','needs_send_permission','reused') if key in result}
            if result.get('error'):safe['error']=self._redact(str(result['error']))[:600]
            record['result']=safe
        return {**safe,'report_id':record['id']},status
