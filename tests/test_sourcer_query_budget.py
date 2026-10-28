"""Normal People-query limits, using synthetic provider responses only."""
import copy
from unittest import mock

import pytest

from cvstudio_linkedin_sourcer import LinkedInSourcerService, SourcerError


ALIASES = ['SAP FICO', 'SAP FI/CO', 'SAP Finance', 'SAP Controlling',
           'SAP Financial Accounting', 'SAP FI', 'SAP CO']
LONG = '(' + ' OR '.join('"' + term + '"' for term in ALIASES) + ')'
SHORT = '(' + ' OR '.join('"' + term + '"' for term in ALIASES[:4]) + ')'


def plan(query=LONG, *, mode='standard', reuse=False):
    value = {'query': query, 'country': 'Malaysia',
             'requirements': ['SAP FICO', 'Malaysia', 'Implementation experience']}
    raw = {'content': [{'type': 'tool_use', 'name': 'return_search_plan', 'input': value}]}
    provider = mock.Mock(return_value=(raw, {'usage': {'input_tokens': 12, 'output_tokens': 8}, 'cost': .001}))
    service = LinkedInSourcerService(key_available=lambda: True, provider_call=provider)
    run = service.handle({'action': 'start', 'brief': 'SAP FICO in Malaysia', 'mode': mode,
                          'max_pages': 10, 'max_calls': 35, 'confirm_paid': True,
                          'use_open_search': reuse})['run']['id']
    return service, provider, value, run


def test_seven_alias_query_is_bounded_without_losing_criteria_or_country():
    service, provider, value, run = plan()
    original = copy.deepcopy(value)
    result = service.handle({'action': 'plan', 'run_id': run})
    assert result['plan']['query'] == SHORT
    assert result['plan']['country'] == 'Malaysia'
    assert result['plan']['requirements'] == original['requirements']
    assert value == original
    assert provider.call_count == 1
    assert result['run']['calls'] == 1
    assert result['run']['tokens'] == 20
    assert 'three' in provider.call_args.args[3]['properties']['query']['description'].lower()


@pytest.mark.parametrize('query', [SHORT, 'SAP FICO', 'SAP AND Finance NOT intern',
                                  '"Research OR development" OR Engineer'])
def test_already_short_query_is_unchanged(query):
    service, _, _, run = plan(query)
    assert service.handle({'action': 'plan', 'run_id': run})['plan']['query'] == query


@pytest.mark.parametrize(('mode', 'reuse'), [('lite', False), ('recruiter', False), ('standard', True)])
def test_recruiter_and_existing_filtered_search_are_unchanged(mode, reuse):
    service, _, _, run = plan(mode=mode, reuse=reuse)
    assert service.handle({'action': 'plan', 'run_id': run})['plan']['query'] == LONG


@pytest.mark.parametrize('query', [LONG + ' AND Architect', LONG + ' NOT intern',
                                  '(' + LONG + ' OR Other)',
                                  'A AND B AND C AND D AND E',
                                  '"A" OR "B" OR "C" OR "D" OR ""',
                                  'A OR B OR C OR D OR "broken'])
def test_unsafe_simplification_never_drops_required_clauses(query):
    service, provider, _, run = plan(query)
    with pytest.raises(SourcerError, match='normal LinkedIn|normal search'):
        service.handle({'action': 'plan', 'run_id': run})
    assert provider.call_count == 1
    assert service.run.calls == 1
    assert not service.run.busy.locked()


def test_country_keyword_guard_still_precedes_normalization():
    service, provider, _, run = plan(LONG + ' OR Malaysia')
    with pytest.raises(SourcerError, match='country into the keywords'):
        service.handle({'action': 'plan', 'run_id': run})
    assert provider.call_count == 1


@pytest.mark.parametrize(('query', 'expected'), [
    ('A OR B OR C OR D OR E', 'A OR B OR C OR D'),
    ('"Research OR development" OR A OR B OR C OR D', '"Research OR development" OR A OR B OR C'),
    ('(A OR a OR B OR C OR D OR E)', '(A OR B OR C OR D)'),
    ('"C++ (SAP)" OR A OR B OR C OR D', '"C++ (SAP)" OR A OR B OR C'),
])
def test_only_positive_aliases_are_shortened(query, expected):
    service, _, value, run = plan(query)
    result = service.handle({'action': 'plan', 'run_id': run})['plan']
    assert result['query'] == expected
    assert result['requirements'] == value['requirements']


def test_rejected_paid_plan_is_not_automatically_replayed():
    service, provider, _, run = plan('A AND B AND C AND D AND E')
    with pytest.raises(SourcerError):
        service.handle({'action': 'plan', 'run_id': run})
    assert provider.call_count == 1
    assert service.snapshot()['run']['calls'] == 1
    assert service.snapshot()['run']['tokens'] == 20
