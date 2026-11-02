"""Fictional Signed clients UI fixture. No real JobAdder transport or data."""
import copy
import os
from pathlib import Path
import runpy
from unittest import mock

import flask

company_reads = {}
root = Path(__file__).resolve().parents[2]
os.environ['CVSTUDIO_PEOPLE_FIXTURE_PORT'] = '5098'
with mock.patch.object(flask.Flask, 'run'):
    seed = runpy.run_path(str(root / 'tests/browser/people_dashboard_server.py'))
app = seed['app']  # the seed isolates every receipt/database/vault before import
companies = [
    {'companyId': 41, 'name': 'Client 10', 'status': {'statusId': 2, 'name': 'Signed Client'}, 'owner': {'firstName': 'Beta', 'lastName': 'Owner'}, 'social': {'linkedin': 'https://www.linkedin.com/company/fictional-client/'}},
    {'companyId': 42, 'name': 'Client 2', 'status': {'statusId': 2, 'name': 'Signed Client'}, 'owner': {'firstName': 'Alpha', 'lastName': 'Owner'}},
    {'companyId': 43, 'name': 'Zeta', 'status': {'statusId': 3, 'name': 'Active Client'}},
    {'companyId': 44, 'name': 'alpha', 'status': {'statusId': 3, 'name': 'Active Client'}, 'owner': {'firstName': 'Alpha', 'lastName': 'Owner'}},
]


class FictionalReadClient:
    def request_json(self, path, **kwargs):
        assert kwargs.get('method', 'GET') == 'GET', 'No JobAdder writes in this fixture'
        if path == 'users/current':
            data = {'userId': 7, 'accountName': 'Fictional Recruitment'}
        elif path == 'companies/lists/status':
            data = {'items': [{'statusId': i, 'name': label, 'active': True} for i, label in [(1, 'Prospect'), (2, 'Signed Client'), (3, 'Active Client')]]}
        elif path == 'companies':
            params = kwargs.get('params') or {}
            rows = [row for row in companies if row['status']['statusId'] in params.get('StatusId', []) and str(params.get('Name', '')).lower() in row['name'].lower()]
            offset, limit = params.get('Offset', 0), params.get('Limit', 50)
            data = {'items': rows[offset:offset + limit], 'totalCount': len(rows)}
        elif path.startswith('companies/'):
            data = copy.deepcopy(next(row for row in companies if str(row['companyId']) == path.split('/')[-1]))
            company_reads[path] = company_reads.get(path, 0) + 1
            if path == 'companies/41' and company_reads[path] == 1:
                data.pop('social', None)  # Link added in fictional JobAdder after Follow.
        else:
            data = {'items': [], 'totalCount': 0}
        return 200, copy.deepcopy(data)

    def request_raw(self, *args, **kwargs):
        raise AssertionError('No external transport in fictional Signed clients fixture')


app._JOBADDER_CLIENT = FictionalReadClient()
app._ja_public_info = lambda: {'connected': True, 'account_cache_namespace': 'a' * 64, 'api_url': 'https://api.jobadder.com/v2'}
app._ja_refresh_access_token = lambda force=False: 'fictional-token'


@app.app.route('/__signed_clients_fixture__')
def marker():
    return {'fictional_signed_clients_fixture': True}


@app.app.after_request
def banner(response):
    if flask.request.path == '/' and response.mimetype == 'text/html':
        response.direct_passthrough = False
        response.set_data(response.get_data().replace(b'<div class="app">', b'<div style="padding:8px;text-align:center;background:#fff2cc">Fictional QA preview</div><div class="app">', 1))
    return response


app.app.run(host='127.0.0.1', port=5098, debug=False, use_reloader=False)
