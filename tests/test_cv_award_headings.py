"""Awards layout checks with synthetic CVs; never call a provider."""
import copy
import io
import json
import os
from pathlib import Path
import sys
import time
from unittest import mock
import zipfile

from lxml import etree
import pytest

import cvstudio_cv_normalize as normal
import cvstudio_blind_mask as blind


def example(company='Northwind Services (M) Sdn Bhd',shape=list):
    values=[company,'2024','Recognition Award - Ten years of support.',
            '2023','Silver Award - Excellent monitoring support.']
    data={'candidate':{'name':'Example Candidate'},'work_experiences':[],
          'skills':[{'category':'Awards & Achievements','items':values if shape is list else '\n'.join(values)}]}
    source='\n'.join(['AWARDS/ ACHIEVEMENTS',*values,'TRAINING HIGHLIGHTS','Monitoring and systems.'])
    return data,source


def test_generated_legal_labels_round_trip_without_changing_items():
    for index in range(100):
        for shape in [list,str]:
            company=('Élan' if index%2 else 'Northwind')+' Services '+chr(65+index%26)+' Sdn Bhd'
            parsed,source=example(company,shape)
            before=copy.deepcopy(parsed)
            result=normal._normalize_cv_data_for_output(parsed,source)
            assert result['skills'][0]['item_headings']==[company,'2024','2023']
            assert result['skills'][0]['items']==before['skills'][0]['items']
            assert normal._normalize_cv_data_for_output(copy.deepcopy(result),source)==result
            assert normal._normalize_cv_data_for_output(copy.deepcopy(result))==result


@pytest.mark.parametrize('company',['Received A Support Award From Northwind Sdn Bhd',
                                    'Recognized For Work At Northwind Ltd',
                                    'Worked with Northwind Sdn Bhd',
                                    'Unverified Group'])
def test_uncertain_prose_does_not_become_an_organization_heading(company):
    parsed,source=example(company)
    assert 'item_headings' not in normal._normalize_cv_data_for_output(parsed,source)['skills'][0]


def test_optional_awards_scan_is_bounded():
    for text in ['x'*1000001, 'line\n'*12001]:
        parsed,_=example();started=time.perf_counter()
        assert normal._restore_cv_award_headings(parsed,text)==example()[0]
        assert time.perf_counter()-started<1
    parsed,source=example();parsed['skills'][0]['items']=['x']*513
    assert 'item_headings' not in normal._restore_cv_award_headings(parsed,source)['skills'][0]


def test_blind_awards_rebuild_only_already_visible_labels():
    parsed,source=example();original=normal._normalize_cv_data_for_output(parsed,source)
    reply=copy.deepcopy(original);reply['skills'][0]['items'][0]='Leading Technology Company'
    output=blind._blind_restore_cv_bullet_structure(reply,original)
    assert output['skills'][0]['item_headings']==['Leading Technology Company','2024','2023']
    assert 'Northwind' not in json.dumps(output)
    assert reply['skills'][0]['item_headings'][0].startswith('Northwind')


@pytest.fixture
def module(tmp_path):
    if 'app' not in sys.modules:
        os.environ.update(LOCALAPPDATA=str(tmp_path),APPDATA=str(tmp_path),CVSTUDIO_STATE_DIR=str(tmp_path/'state'),CVSTUDIO_DB_PATH=str(tmp_path/'main.sqlite3'),CVSTUDIO_JOB_STATE_PATH=str(tmp_path/'jobs.json'),SALARY_COMPARISON_DATA_DIR=str(tmp_path/'salary'))
        from owner_build_tools.build_protected import write_test_receipt
        write_test_receipt(Path(__file__).resolve().parents[1],environment={'HOME':str(tmp_path),'LOCALAPPDATA':str(tmp_path)})
    import app
    return app


def test_real_word_export_keeps_only_award_descriptions_bulleted(module):
    parsed,source=example();normalized=normal._normalize_cv_data_for_output(parsed,source)
    client=module.app.test_client();client.set_cookie(module._AI_SPEND_SESSION_COOKIE,module._AI_SPEND_SESSION_TOKEN)
    with mock.patch.object(module._AI_PROVIDER_CLIENT,'request') as paid:
        response=client.post('/generate-docx',json={'data':normalized},headers={'X-CV-Studio-Request':'1'})
        assert response.status_code==200
        paid.assert_not_called()
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        tree=etree.fromstring(archive.read('word/document.xml'))
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    paragraphs=tree.xpath('//w:p',namespaces=ns)
    items=normalized['skills'][0]['items']
    for item in items:
        found=[p for p in paragraphs if ''.join(p.xpath('.//w:t/text()',namespaces=ns))==item]
        assert len(found)==1
        listed=found[0].xpath('./w:pPr/w:numPr/w:numId/@w:val',namespaces=ns)
        if item in normalized['skills'][0]['item_headings']:
            assert not listed and found[0].xpath('.//w:rPr/w:b',namespaces=ns)
            assert found[0].xpath('./w:pPr/w:keepNext',namespaces=ns)
        else: assert listed and listed!=['0']
