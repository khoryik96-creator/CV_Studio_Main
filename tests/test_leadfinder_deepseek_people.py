"""DeepSeek only classifies actual supplied browser observations."""
import pytest
from cvstudio_lead_people import plan,observations,selected_people
COMPANIES=[{'id':'one','company':'Elitez','matched_role':'Software Engineer','job_url':'https://sg.jobstreet.com/job/95258471'}]
CARD={'url':'https://www.linkedin.com/in/fictional-hr','name':'Fictional HR','title':'HR Manager at Elitez','location':'Malaysia','company':'Elitez','text':'Fictional HR\nHR Manager at Elitez\nMalaysia'}

def test_plan_has_company_hr_and_functional_queries():
    queries=plan(COMPANIES,['Engineering Manager','Head of Engineering'])
    assert len(queries)==2
    assert all('Elitez' in q['query'] for q in queries)
    assert 'HR' in queries[0]['query'] and 'Engineering Manager' in queries[1]['query']

def test_only_observed_ids_names_titles_and_urls_can_be_returned():
    cards=observations([CARD],COMPANIES)
    people=selected_people({'matches':[{'id':'invented','title':'CEO'},{'id':'observed_1','name':'Invented Name','profile_url':'https://evil.invalid','contact_type':'HR','reason':'Observed role'}]},cards)
    assert len(people)==1
    assert people[0]['name']==CARD['name'] and people[0]['profile_url']==CARD['url']
    assert not people[0]['email']

def test_wrong_company_and_unobserved_title_cannot_gain_authority():
    cards=observations([{**CARD,'text':'Fictional HR\nHR Manager at Another Employer'}],COMPANIES)
    assert selected_people({'matches':[{'id':'observed_1'}]},cards)==[]
    cards=observations([{**CARD,'title':''}],COMPANIES)
    assert selected_people({'matches':[{'id':'observed_1','title':'CEO at Elitez'}]},cards)==[]

@pytest.mark.parametrize('patch',[{'url':'https://evil.invalid/in/person'},{'company':'Other Employer'},{'name':''},{'text':'tiny'}])
def test_invalid_observations_rejected_before_ai(patch):
    with pytest.raises(ValueError):observations([{**CARD,**patch}],COMPANIES)


def test_person_ids_are_stable_per_profile_and_distinct_across_runs():
    match={'matches':[{'id':'observed_1'}]}
    first=selected_people(match,observations([CARD],COMPANIES))[0]
    second=selected_people(match,observations([{**CARD,'url':CARD['url']+'-another'}],COMPANIES))[0]
    repeated=selected_people(match,observations([CARD],COMPANIES))[0]
    assert first['id']!=second['id'],'distinct people from separate runs must be independently selectable'
    assert first['id']==repeated['id']
