"""Isolated Sourcer folder/search fixture with a fictional paid provider."""
import os
from pathlib import Path
import runpy
from unittest import mock

import flask

root = Path(__file__).resolve().parents[2]
os.environ['CVSTUDIO_PEOPLE_FIXTURE_PORT'] = '5099'
with mock.patch.object(flask.Flask, 'run'):
    seed = runpy.run_path(str(root / 'tests/browser/people_dashboard_server.py'))
app = seed['app']
calls = []


def provider(model, brief, task, schema, observed):
    calls.append(task)
    if task == 'search_plan':
        tool, value = 'return_search_plan', {
            'query': '(Oracle OR "Oracle Database" OR DBA) AND (Ansible OR Chef OR Puppet OR automation)',
            'country': 'Malaysia', 'requirements': ['Oracle database', 'Automation with Ansible or equivalent', 'Located in Malaysia'],
        }
    else:
        profile = observed['profiles'][0]
        tool, value = 'return_profile_review', {'candidates': [{
            'id': profile['id'], 'score': 88,
            'evidence_refs': [profile['passages'][0]['id']], 'unknowns': ['Availability not shown'],
        }]}
    return {'content': [{'type': 'tool_use', 'name': tool, 'input': value}]}, {'usage': {'input_tokens': 10, 'output_tokens': 20}, 'cost': 0}


app._LINKEDIN_SOURCER.key_available = lambda: True
app._LINKEDIN_SOURCER.provider_call = provider


@app.app.route('/__sourcer_folders_fixture__')
def marker():
    return {'fictional_sourcer_folders_fixture': True, 'provider_calls': list(calls)}


app.app.run(host='127.0.0.1', port=5099, debug=False, use_reloader=False)
