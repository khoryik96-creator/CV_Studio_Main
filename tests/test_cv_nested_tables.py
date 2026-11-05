"""Nested layout-table CVs retain content before any provider call (fictional data)."""
import io
import json
from unittest import mock
from docx import Document
from docx.oxml import OxmlElement
import test_cv_label_table_reconciliation as fixture

app=fixture.app
HEADERS={'Origin':'http://127.0.0.1:5000','X-CV-Studio-Request':'1'}


def source():
    doc=Document();outer=doc.add_table(rows=1,cols=2);outer.cell(0,0).text=''
    body=outer.cell(0,1)
    header=body.add_table(rows=1,cols=1);header.cell(0,0).text='Example Candidate'
    body.add_paragraph('Hybrid Cloud Engineer with enterprise platform experience.')
    skills=body.add_table(rows=2,cols=1);skills.cell(0,0).text='SKILLS';skills.cell(1,0).text='Linux, VMware, AWS and automation'
    body.add_paragraph('WORK EXPERIENCE')
    job=body.add_table(rows=1,cols=2)
    date=job.cell(0,0).paragraphs[0]
    for _ in range(2):
        box=OxmlElement('w:txbxContent');p=OxmlElement('w:p');r=OxmlElement('w:r');t=OxmlElement('w:t');t.text='Sep 2024 to Present';r.append(t);p.append(r);box.append(p)
        run=OxmlElement('w:r');pict=OxmlElement('w:pict');pict.append(box);run.append(pict);date._p.append(run)
    details=job.cell(0,1).add_table(rows=1,cols=1);cell=details.cell(0,0);cell.text='Example Cloud Services'
    cell.add_paragraph('Hybrid Cloud Engineer');cell.add_paragraph('Maintain production Linux clusters.',style='List Bullet')
    cell.add_paragraph('Automate cloud provisioning.',style='List Bullet')
    body.add_paragraph('EDUCATION');body.add_table(rows=1,cols=1).cell(0,0).text='Example University | Engineering degree'
    payload=io.BytesIO();doc.save(payload);return payload.getvalue()


def assert_complete(value):
    expected=['Example Candidate','Hybrid Cloud Engineer with enterprise platform experience.','SKILLS','Linux, VMware, AWS and automation','WORK EXPERIENCE','Sep 2024 to Present','Example Cloud Services','Hybrid Cloud Engineer','Maintain production Linux clusters.','Automate cloud provisioning.','EDUCATION','Example University']
    positions=[value.index(text) for text in expected[:7]]
    assert positions==sorted(positions),'name, skills, work heading, local date and employer retain source order'
    for text in expected:assert text in value
    assert value.count('Sep 2024 to Present')==1,'drawing fallback copies do not duplicate dates'
    assert '• Maintain production Linux clusters.' in value


def test_shared_docx_reader_reaches_nested_tables_and_local_date_boxes():
    assert_complete(app._extract_docx_text_preserve_tables(source()))


def test_real_extract_route_retains_nested_cv_sections_before_ai_parsing():
    client=app.app.test_client()
    response=client.post('/extract-text',data={'file':(io.BytesIO(source()),'fictional-nested-cv.docx')},headers=HEADERS)
    assert response.status_code==200,response.get_json()
    assert_complete(response.get_json()['text'])


def test_nested_source_survives_parse_and_actual_word_generation():
    client=app.app.test_client()
    extracted=client.post('/extract-text',data={'file':(io.BytesIO(source()),'fictional-nested-cv.docx')},headers=HEADERS).get_json()['text']
    parsed={'candidate':{'name':'Example Candidate','current_position':'Hybrid Cloud Engineer','current_company':'Example Cloud Services'},
            'work_experiences':[{'company':'Example Cloud Services','date_range':'Sep 2024 to Present','roles':[{'title':'Hybrid Cloud Engineer','date_range':'Sep 2024 to Present','bullets':['Maintain production Linux clusters.','Automate cloud provisioning.']}]}],
            'education':[{'institution':'Example University','degree':'Engineering degree','date_range':''}],
            'skills':[{'category':'Skills','items':['Linux','VMware','AWS','automation']}],'certifications':[]}
    reply={'content':[{'type':'text','text':json.dumps(parsed)}],'usage':{}}
    with mock.patch.object(app,'call_llm',return_value=reply) as provider,mock.patch.object(app,'_ai_spend_session_allowed',return_value=True),mock.patch.object(app,'_resolve_request_api_key',return_value='fictional'):
        result=client.post('/parse',json={'cv_text':extracted},headers=HEADERS)
    assert result.status_code==200,result.get_json()
    assert 'Example Candidate' in provider.call_args.args[2]['messages'][0]['content']
    formatted=client.post('/generate-docx',json={'data':result.get_json()['data']},headers=HEADERS)
    assert formatted.status_code==200
    text=app._extract_docx_text_preserve_tables(formatted.data)
    for value in ['Example Candidate','Example Cloud Services','Hybrid Cloud Engineer','Maintain production Linux clusters.','Automate cloud provisioning.','Example University','Linux','VMware','AWS','automation']:
        assert value in text
