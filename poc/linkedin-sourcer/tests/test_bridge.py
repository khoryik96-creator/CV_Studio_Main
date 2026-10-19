import json
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge import create_app
from provider import (DeepSeek, SourcerError, clean_profiles, profile_url,
                      validate_reviews, PLAN_SCHEMA)

CODE = 'x' * 43
HEADERS = {'Authorization': 'Bearer ' + CODE, 'Origin': 'chrome-extension://' + 'a' * 32}
PROFILE = {'id': 'p0', 'name': 'Sample Person', 'url': 'https://www.linkedin.com/in/sample-person',
           'text': 'Finance Manager. Manufacturing and SAP. Regional reporting.'}
ROW = {'id': 'p0', 'score': 80, 'evidence': ['Manufacturing and SAP'], 'unknowns': ['Availability']}


class FakeProvider:
    def __init__(self):
        self.key_loader = lambda: 'synthetic-private-key'
        self.calls = []
        self.fail = False
        self.entered, self.release = threading.Event(), threading.Event()
        self.block = False

    def call(self, model, brief, task, schema, data):
        self.calls.append((model, brief, task, data))
        if self.block:
            self.entered.set()
            if not self.release.wait(3):
                raise SourcerError('Test timeout')
        if self.fail:
            raise SourcerError('Synthetic provider outage')
        return ({'query': 'Finance Manager SAP', 'requirements': ['Manufacturing']} if task == 'search_plan'
                else {'candidates': [ROW.copy()]}), 123


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.provider = FakeProvider()
        self.app = create_app(self.provider, CODE)
        self.client = self.app.test_client()

    def get(self, url, **kwargs):
        return self.client.get(url, base_url='http://127.0.0.1:5073', headers=HEADERS, **kwargs)

    def post(self, url, body):
        return self.client.post(url, base_url='http://127.0.0.1:5073', headers=HEADERS, json=body)

    def start(self, **overrides):
        data = {'brief': 'Finance managers with SAP', 'mode': 'standard', 'max_pages': 15,
                'max_calls': 35, 'confirm_paid': True, **overrides}
        response = self.post('/api/start', data)
        self.assertEqual(response.status_code, 200, response.json)
        return response.json['run']['id']

    def test_all_modes_and_explicit_consent(self):
        for mode in ['standard', 'lite', 'recruiter']:
            run = self.start(mode=mode)
            self.assertEqual(self.post('/api/stop', {'run_id': run}).status_code, 200)
        self.assertEqual(self.post('/api/start', {'confirm_paid': False}).status_code, 400)
        self.assertEqual(self.provider.calls, [])

    def test_plan_review_and_budget(self):
        run = self.start(max_calls=2)
        self.assertEqual(self.post('/api/plan', {'run_id': run}).json['plan']['query'], 'Finance Manager SAP')
        reply = self.post('/api/review', {'run_id': run, 'page': 1, 'stage': 'screen', 'profiles': [PROFILE]})
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json['candidates'][0]['url'], PROFILE['url'])
        self.assertEqual(reply.json['run']['tokens'], 246)
        self.assertEqual(self.post('/api/plan', {'run_id': run}).status_code, 400)
        self.assertEqual(len(self.provider.calls), 2)

    def test_no_keys_or_profile_content_in_status(self):
        response = self.get('/api/status')
        self.assertTrue(response.json['configured'])
        self.assertNotIn('synthetic-private-key', response.text)
        self.assertNotIn('app', sys.modules)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_host_origin_and_pairing_guards(self):
        self.assertEqual(self.client.get('/api/status', base_url='http://127.0.0.1:5073').status_code, 401)
        self.assertEqual(self.client.get('/', base_url='http://attacker.invalid').status_code, 403)
        self.assertEqual(self.client.get('/', base_url='http://127.0.0.1:5073', headers={'Origin': 'https://attacker.invalid'}).status_code, 403)
        for origin in ['null', 'chrome-extension://invalid', 'https://www.linkedin.com']:
            self.assertEqual(self.client.get('/api/status', base_url='http://127.0.0.1:5073', headers={**HEADERS, 'Origin': origin}).status_code, 403)
        self.assertNotIn('Access-Control-Allow-Origin', self.get('/api/status').headers)

    def test_invalid_inputs_never_make_paid_request(self):
        run = self.start()
        for patch in [{'page': 16}, {'page': True}, {'stage': 'send_message'}, {'profiles': []},
                      {'profiles': [{**PROFILE, 'url': 'https://attacker.invalid/in/test'}]}]:
            response = self.post('/api/review', {'run_id': run, 'page': 1, 'stage': 'screen', 'profiles': [PROFILE], **patch})
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.client.post('/api/review', base_url='http://127.0.0.1:5073', headers=HEADERS, data='{}').status_code, 415)
        self.assertEqual(self.client.post('/api/review', base_url='http://127.0.0.1:5073', headers=HEADERS, json={'large': 'x' * 660000}).status_code, 413)

    def test_failed_request_consumes_budget_and_does_not_retry(self):
        run = self.start(max_calls=1)
        self.provider.fail = True
        self.assertEqual(self.post('/api/plan', {'run_id': run}).status_code, 400)
        self.assertEqual(self.post('/api/plan', {'run_id': run}).status_code, 400)
        self.assertEqual(len(self.provider.calls), 1)
        self.assertFalse(self.get('/api/status').json['run']['usage_complete'])

    def test_malformed_json_field_types_fail_before_provider_transport(self):
        for mode in [[], {}, 1]:
            reply = self.post('/api/start', {'brief': 'Finance with SAP', 'mode': mode,
                                           'max_pages': 1, 'max_calls': 2, 'confirm_paid': True})
            self.assertEqual(reply.status_code, 400)
        run = self.start()
        for stage in [[], {}, 1]:
            reply = self.post('/api/review', {'run_id': run, 'page': 1,
                                            'stage': stage, 'profiles': [PROFILE]})
            self.assertEqual(reply.status_code, 400)
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.client.get('/api/status', base_url='http://127.0.0.1:5073',
            headers={'Authorization': 'Bearer é'}).status_code, 401)

    def test_stop_blocks_future_calls(self):
        run = self.start()
        self.post('/api/stop', {'run_id': run})
        self.assertEqual(self.post('/api/plan', {'run_id': run}).status_code, 400)
        self.assertEqual(self.provider.calls, [])

    def test_concurrent_calls_and_stop_during_inflight(self):
        run = self.start()
        self.provider.block = True
        answers = []
        def request_plan():
            with self.app.test_client() as client:
                answers.append(client.post('/api/plan', base_url='http://127.0.0.1:5073', headers=HEADERS, json={'run_id': run}))
        thread = threading.Thread(target=request_plan)
        thread.start()
        self.assertTrue(self.provider.entered.wait(2))
        self.assertEqual(self.post('/api/plan', {'run_id': run}).status_code, 400)
        self.assertEqual(self.post('/api/stop', {'run_id': run}).status_code, 200)
        self.assertEqual(self.post('/api/start', {'brief': 'Another profile', 'mode': 'standard', 'max_pages': 1, 'max_calls': 3, 'confirm_paid': True}).status_code, 400)
        self.provider.release.set()
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(answers[0].status_code, 400)
        self.assertEqual(len(self.provider.calls), 1)


class GroundingTests(unittest.TestCase):
    def test_urls(self):
        self.assertEqual(profile_url(PROFILE['url'] + '/?tracking=1'), PROFILE['url'])
        self.assertTrue(profile_url('https://www.linkedin.com/talent/profile/sample-ref'))
        for value in ['javascript:alert(1)', 'http://www.linkedin.com/in/test', 'https://www.linkedin.com.evil.invalid/in/test',
                      'https://user:pass@www.linkedin.com/in/test', 'https://www.linkedin.com/in/a%0atest',
                      'https://www.linkedin.com/messaging/thread/test', 'https://www.linkedin.com:444/in/test']:
            self.assertEqual(profile_url(value), '')

    def test_invented_ids_or_quotes_fail_closed(self):
        for row in [{**ROW, 'id': 'p9'}, {**ROW, 'evidence': ['Has ten years of SAP experience']},
                    {**ROW, 'id': []},
                    {**ROW, 'score': True}, {**ROW, 'score': 101}, {**ROW, 'unknowns': 'none'}]:
            with self.assertRaises(SourcerError):
                validate_reviews({'candidates': [row]}, [PROFILE], 5)
        result = validate_reviews({'candidates': [{**ROW, 'url': 'https://invented.invalid', 'name': 'Invented'}]}, [PROFILE], 5)
        self.assertEqual(result[0]['name'], PROFILE['name'])
        self.assertEqual(result[0]['url'], PROFILE['url'])

    def test_duplicate_ids_and_large_profiles(self):
        with self.assertRaises(SourcerError):
            clean_profiles([PROFILE, PROFILE])
        self.assertEqual(len(clean_profiles([{**PROFILE, 'text': 'x' * 30000}])[0]['text']), 14000)


class Response:
    def __init__(self, body=None, status=200, raw=None):
        self.status_code = status
        self.raw = raw if raw is not None else json.dumps(body).encode()
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def iter_content(self, size):
        for i in range(0, len(self.raw), size): yield self.raw[i:i + size]


class TransportTests(unittest.TestCase):
    def make(self, response):
        class Transport:
            def __init__(self): self.calls = []
            def post(self, *args, **kwargs): self.calls.append((args, kwargs)); return response
        transport = Transport()
        return DeepSeek(lambda: 'synthetic-private-key', transport), transport

    def body(self, **patch):
        return {'choices': [{'message': {'tool_calls': [{'function': {'name': 'return_search_plan',
            'arguments': json.dumps({'query': 'Finance SAP', 'requirements': ['Manufacturing']})}}]}}],
            'usage': {'total_tokens': 100}, **patch}

    def test_native_tool_call_and_no_secrets_in_prompt(self):
        provider, transport = self.make(Response(self.body()))
        value, tokens = provider.call('deepseek-flash', 'Find finance people', 'search_plan', PLAN_SCHEMA, {})
        self.assertEqual(tokens, 100)
        request = transport.calls[0][1]
        self.assertEqual(request['json']['tool_choice']['function']['name'], 'return_search_plan')
        self.assertFalse(request['allow_redirects'])
        self.assertNotIn('synthetic-private-key', json.dumps(request['json']))
        self.assertEqual(request['headers']['Authorization'], 'Bearer synthetic-private-key')

    def test_ambiguous_failure_malformed_or_redirect_never_retried(self):
        for response in [Response({}, 503), Response({}, 302), Response(raw=b'not json'),
                         Response(self.body(choices=[])), Response(raw=b'x' * 270000)]:
            provider, transport = self.make(response)
            with self.assertRaises(SourcerError):
                provider.call('deepseek-flash', 'brief', 'search_plan', PLAN_SCHEMA, {})
            self.assertEqual(len(transport.calls), 1)

    def test_missing_usage_stays_unknown(self):
        provider, _ = self.make(Response(self.body(usage={})))
        self.assertIsNone(provider.call('deepseek-flash', 'brief', 'search_plan', PLAN_SCHEMA, {})[1])


if __name__ == '__main__': unittest.main()
