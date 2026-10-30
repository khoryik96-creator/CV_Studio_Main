"""New module contracts; all providers and browser actions are synthetic."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock
import zipfile

from cvstudio_linkedin_sourcer import LinkedInSourcerService, SourcerError, validate_plan, PLAN_SCHEMA

PROFILE = {"id": "p0", "name": "Sample Person", "url": "https://www.linkedin.com/in/sample-person", "text": "Finance Manager. SAP and manufacturing."}
ROW = {"id": "p0", "score": 80, "evidence": ["SAP and manufacturing"], "unknowns": ["Availability"]}


def provider(model, brief, task, schema, data):
    value = {"query": "Finance SAP", "country": "", "requirements": ["Manufacturing"]} if task == 'search_plan' else {"candidates": [ROW]}
    return {"content": [{"type": "tool_use", "name": "return_"+task, "input": value}]}, {"usage": {"input_tokens": 100, "output_tokens": 20, "api_calls": 1}, "cost": 0.001, "model": model, "provider": "deepseek"}


class DomainTests(unittest.TestCase):
    def test_country_is_a_native_filter_not_boolean_keywords(self):
        query = '("SAP FICO" OR "SAP FI/CO" OR "SAP Finance" OR "SAP Controlling")'
        plan = {"query": query, "requirements": ["SAP FICO", "Malaysia"], "country": "Malaysia"}
        self.assertEqual(validate_plan(plan), plan)
        self.assertEqual(validate_plan({"query": "SAP", "country": "", "requirements": ["SAP"]})["country"], "")
        with self.assertRaises(SourcerError): validate_plan({"query": "SAP", "requirements": ["SAP"]})
        for country in [None, [], "x\ny", "x" * 101]:
            with self.assertRaises(SourcerError): validate_plan({**plan, "country": country})
        with self.assertRaises(SourcerError):
            validate_plan({**plan, "query": query + ' AND (Malaysia OR "Kuala Lumpur" OR Selangor OR Penang OR Johor)'})
        self.assertIn("country", PLAN_SCHEMA["required"])
        self.assertIn("Exclude ALL geography", PLAN_SCHEMA["properties"]["query"]["description"])
    def setUp(self):
        self.transport = mock.Mock(side_effect=provider)
        self.service = LinkedInSourcerService(key_available=lambda: True, provider_call=self.transport)
    def start(self, **patch):
        return self.service.handle({"action": "start", "brief": "Finance managers with SAP", "mode": "standard", "max_pages": 15, "max_calls": 35, "confirm_paid": True, **patch})['run']['id']
    def test_three_modes_and_consent(self):
        for mode in ['standard','lite','recruiter']:
            run=self.start(mode=mode);self.service.handle({'action':'stop','run_id':run})
        with self.assertRaises(SourcerError):self.start(confirm_paid=False)
        self.transport.assert_not_called()
    def test_plan_review_budget_and_source_grounding(self):
        run=self.start(max_calls=2)
        self.assertEqual(self.service.handle({'action':'plan','run_id':run})['plan']['query'],'Finance SAP')
        reply=self.service.handle({'action':'review','run_id':run,'stage':'screen','page':1,'profiles':[PROFILE]})
        self.assertEqual(reply['candidates'][0]['url'],PROFILE['url'])
        self.assertEqual(reply['run']['tokens'],240)
        with self.assertRaises(SourcerError):self.service.handle({'action':'plan','run_id':run})
        self.assertEqual(self.transport.call_count,2)
    def test_invalid_page_or_links_do_not_call_provider(self):
        run=self.start()
        for patch in [{'page':16},{'stage':[]},{'profiles':[{**PROFILE,'url':'https://attacker.invalid/in/x'}]}]:
            with self.assertRaises(SourcerError):self.service.handle({'action':'review','run_id':run,'stage':'screen','page':1,'profiles':[PROFILE],**patch})
        self.transport.assert_not_called()
    def test_malformed_paid_output_keeps_accounting(self):
        run=self.start()
        raw,fields=provider('', '', 'search_plan', {}, {})
        raw['content'][0]['input']={'query':''}
        self.transport.side_effect=lambda *args:(raw,fields)
        with self.assertRaises(SourcerError) as failure:self.service.handle({'action':'plan','run_id':run})
        self.assertEqual(failure.exception.accounting['usage']['api_calls'],1)
        self.assertTrue(failure.exception.accounting['paid_ai_failure'])
    def test_stop_during_provider_wait_prevents_next_action(self):
        run=self.start(); entered=threading.Event();release=threading.Event();failures=[]
        def blocked(*args):entered.set();release.wait(3);return provider(*args)
        self.transport.side_effect=blocked
        def plan():
            try:self.service.handle({'action':'plan','run_id':run})
            except SourcerError as error:failures.append(error)
        thread=threading.Thread(target=plan);thread.start();self.assertTrue(entered.wait(2))
        self.service.handle({'action':'stop','run_id':run})
        with self.assertRaises(SourcerError):self.start()
        release.set();thread.join(3)
        self.assertEqual(len(failures),1);self.assertIn('usage',failures[0].accounting)
        with self.assertRaises(SourcerError):self.service.handle({'action':'plan','run_id':run})
        self.assertEqual(self.transport.call_count,1)


class RouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if 'app' not in sys.modules:
            cls.state=tempfile.TemporaryDirectory(prefix='cvstudio-linkedin-tests-')
            base=Path(cls.state.name)
            os.environ.update(LOCALAPPDATA=str(base),APPDATA=str(base),CVSTUDIO_STATE_DIR=str(base/'state'),CVSTUDIO_DB_PATH=str(base/'db.sqlite3'),CVSTUDIO_JOB_STATE_PATH=str(base/'jobs.json'),SALARY_COMPARISON_DATA_DIR=str(base/'salary'))
            from owner_build_tools.build_protected import write_test_receipt
            write_test_receipt(Path(__file__).resolve().parents[1],environment={'HOME':str(base),'LOCALAPPDATA':str(base)})
        import app
        cls.module=app
    def setUp(self):
        self.client=self.module.app.test_client();self.client.get('/')
        self.original=self.module._LINKEDIN_SOURCER
        self.module._LINKEDIN_SOURCER=LinkedInSourcerService(key_available=lambda:True,provider_call=self.module._linkedin_sourcer_provider_call)
        self.addCleanup(setattr,self.module,'_LINKEDIN_SOURCER',self.original)
    def post(self,**data):
        return self.client.post('/linkedin-sourcer',json=data,headers={'X-CV-Studio-Request':'1'})
    def test_existing_118_route_contract_and_guards_preserved(self):
        from cvstudio_architecture import _route_contract
        rows=tuple(row for row in _route_contract(self.module.app) if row['endpoint'] not in {'linkedin_sourcer', 'job_leads', 'email_verifier', 'apollo_connection', 'jobadder_contact_actions', 'jobadder_clients'})
        digest=hashlib.sha256(json.dumps(rows,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.assertEqual(digest,'42768445b8fe97e48688238c02bebf5abce0251befc3d212c2d2b029911f7862')
    def test_new_route_requires_paid_session_and_rejects_extension_origin(self):
        unpaired=self.module.app.test_client()
        self.assertEqual(unpaired.post('/linkedin-sourcer',json={'action':'start'},headers={'X-CV-Studio-Request':'1'}).status_code,403)
        response=self.client.post('/linkedin-sourcer',json={'action':'start'},headers={'Origin':'chrome-extension://'+'a'*32})
        self.assertEqual(response.status_code,403)
    def test_companion_download_contains_only_expected_static_files(self):
        response=self.client.get('/linkedin-sourcer?action=extension')
        self.assertEqual(response.status_code,200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            self.assertEqual({Path(name).name for name in archive.namelist()},{'manifest.json','worker.js','content.js','reader.js'})
            manifest=json.loads(archive.read('CV-Studio-LinkedIn-Companion/manifest.json'))
            self.assertNotIn('https://api.deepseek.com/*',manifest['host_permissions'])
    def test_companion_setup_uses_bundled_folder_and_current_version(self):
        response=self.client.get('/linkedin-sourcer?action=companion_setup')
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.cache_control.no_store)
        folder=Path(response.json['folder'])
        self.assertEqual(folder,Path(self.module.__file__).resolve().parent/'vendor'/'linkedin-companion')
        self.assertEqual(response.json['version'],(folder.parents[1]/'VERSION').read_text().strip())
        self.assertTrue((folder/'manifest.json').is_file())
    def test_companion_pairing_proof_requires_live_app_session_and_fresh_challenge(self):
        nonce='a'*64
        address='/linkedin-sourcer?action=companion_challenge&nonce='+nonce
        self.assertEqual(self.module.app.test_client().get(address).status_code,403)
        self.assertEqual(self.client.get(address.replace(nonce,'invalid')).status_code,400)
        secret='12'*32
        with mock.patch.object(self.module,'_LINKEDIN_COMPANION_KEY',''), mock.patch.object(self.module,'_cv_secure_load',return_value={'key':secret}), mock.patch.object(self.module,'_cv_secure_save') as save:
            response=self.client.get(address)
            paired=self.client.get(address.replace('companion_challenge','companion_pair'))
            changed=self.client.get(address.replace(nonce,'b'*64))
            save.assert_not_called()
        self.assertEqual(response.status_code,200,response.json)
        self.assertTrue(response.cache_control.no_store)
        self.assertNotIn('key',response.json)
        import hmac
        expected=hmac.new(bytes.fromhex(paired.json['key']),('CVStudio companion v1|http://localhost|'+nonce).encode(),hashlib.sha256).hexdigest()
        self.assertEqual(response.json['proof'],expected)
        self.assertNotEqual(changed.json['proof'],expected)
        self.assertNotEqual(paired.json['key'],secret,'identity is specific to the installation folder')
    def test_companion_key_creation_is_protected_and_failed_save_is_failure_visible(self):
        with mock.patch.object(self.module,'_LINKEDIN_COMPANION_KEY',''), mock.patch.object(self.module,'_cv_secure_load',return_value={}), mock.patch.object(self.module,'_cv_secure_save') as save:
            response=self.client.get('/linkedin-sourcer?action=companion_pair&nonce='+'a'*64)
            self.assertEqual(response.status_code,200)
            self.client.get('/linkedin-sourcer?action=companion_challenge&nonce='+'b'*64)
            save.assert_called_once()
            self.assertEqual(save.call_args.args[0],'companion')
            self.assertEqual(len(save.call_args.args[1]['key']),64)
        with mock.patch.object(self.module,'_LINKEDIN_COMPANION_KEY',''), mock.patch.object(self.module,'_cv_secure_load',return_value={}), mock.patch.object(self.module,'_cv_secure_save',side_effect=OSError('Synthetic private path')):
            response=self.client.get('/linkedin-sourcer?action=companion_pair&nonce='+'a'*64)
            self.assertEqual(response.status_code,503)
            self.assertNotIn('Synthetic private path',response.text)
    def test_paid_tools_use_central_guard_and_keep_usage(self):
        response=self.post(action='start',brief='Finance managers with SAP',mode='standard',max_pages=1,max_calls=3,confirm_paid=True)
        run=response.json['run']['id']
        raw={'content':[{'type':'tool_use','name':'return_search_plan','input':{'query':'Finance SAP','country':'','requirements':['Manufacturing']}}],'usage':{'input_tokens':100,'output_tokens':20}}
        with mock.patch.object(self.module,'_phase5b_enforce_request_guardrail') as gate, mock.patch.object(self.module._AI_PROVIDER_CLIENT,'request',return_value=raw) as call, mock.patch.dict(self.module._ai_secret_store,{'main_deepseek':'synthetic-private-key'}):
            result=self.post(action='plan',run_id=run)
        self.assertEqual(result.status_code,200,result.json)
        gate.assert_called_once();call.assert_called_once()
        self.assertEqual(call.call_args.args[0],'deepseek')
        self.assertEqual(call.call_args.args[2]['tool_choice']['type'],'tool')
        self.assertEqual(result.json['usage']['api_calls'],1)
        self.assertIn('cost_details',result.json)
        self.assertNotIn('synthetic-private-key',result.text)
    def test_spend_guard_failure_never_transports(self):
        response=self.post(action='start',brief='Finance managers with SAP',mode='standard',max_pages=1,max_calls=3,confirm_paid=True)
        with mock.patch.object(self.module,'_phase5b_enforce_request_guardrail',side_effect=ValueError('Synthetic limit')), mock.patch.object(self.module._AI_PROVIDER_CLIENT,'request') as call:
            result=self.post(action='plan',run_id=response.json['run']['id'])
        self.assertEqual(result.status_code,400);call.assert_not_called()


if __name__=='__main__':unittest.main()
