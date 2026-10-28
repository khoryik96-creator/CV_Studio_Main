"""Project additional-section layout; fictional source only, no provider calls."""
import copy
import time
import pytest
import cvstudio_cv_normalize as n
import cvstudio_blind_mask as blind


def example(shape=list):
    items = ['Project: Ledger Migration, Contoso Bank, 2023 - 2024',
             'Technical Lead. Team size: 5', 'Managed product proofs of concept',
             'o Parallel Processing - multi-threaded runs',
             'o Data Store - export to warehouse', 'Managed delivery',
             'Role: Northwind Bank, 2021 - 2022, Upgrade Project',
             'Technical Lead. Team size: 5', 'Delivered testing',
             'Fabrikam Bank, London', '2020, SENIOR CONSULTANT', 'Provided support']
    source = '\n'.join(['PROJECT EXPERIENCE', *items[:2],
        '\u2022 Managed product proofs of concept', items[3], items[4], '\u2022 Managed delivery',
        *items[6:8], '\u2022 Delivered testing', *items[9:11], '\u2022 Provided support',
        'EDUCATION', 'Another section'])
    return {'candidate':{'name':'Example Candidate','current_position':''},'skills':[{'category':'Project Experience',
                      'items': items if shape is list else '\n'.join(items)}]}, source


@pytest.mark.parametrize('shape',[list,str])
def test_project_names_roles_and_nested_points_keep_the_source_shape(shape):
    data,source=example(shape)
    before=copy.deepcopy(data)
    output=n._normalize_cv_data_for_output(data,source)
    assert output['skills'][0]['item_layout']==[
        'heading','heading','bullet','nested','nested','bullet',
        'heading','heading','bullet','heading','heading','bullet']
    assert output['skills'][0]['items']==before['skills'][0]['items']
    assert n._normalize_cv_data_for_output(copy.deepcopy(output),source)==output
    assert n._normalize_cv_data_for_output(copy.deepcopy(output))==output


@pytest.mark.parametrize('alteration',['marked','duplicate_source','duplicate_group',
                                     'outside','reordered','missing_role','wrong_category',
                                     'changed_role','duplicate_header'])
def test_uncertain_headers_are_not_invented(alteration):
    data,source=example()
    if alteration=='marked': source=source.replace('Project:','\u2022 Project:',1)
    if alteration=='duplicate_source': source+='\n'+source
    if alteration=='duplicate_group':data['skills'].append(copy.deepcopy(data['skills'][0]))
    if alteration=='outside':source='SUMMARY\n'+source.replace('PROJECT EXPERIENCE','PROJECT NOTES')
    if alteration=='reordered':data['skills'][0]['items'][1:3]=reversed(data['skills'][0]['items'][1:3])
    if alteration=='missing_role':data['skills'][0]['items'].pop(1)
    if alteration=='wrong_category':data['skills'][0]['category']='Technical Skills'
    if alteration=='changed_role':data['skills'][0]['items'][1]='Another Manager'
    if alteration=='duplicate_header':source=source.replace('EDUCATION', source.split('PROJECT EXPERIENCE\n')[1])
    result=n._normalize_cv_data_for_output(data,source)['skills'][0]
    assert result.get('item_layout',['bullet'])[0]!='heading'


def test_source_recheck_clears_stale_layout_and_boundaries_stop_it():
    data,source=example()
    out=n._normalize_cv_data_for_output(data,source)
    assert 'item_layout' in out['skills'][0]
    out=n._normalize_cv_data_for_output(out,source.replace('PROJECT EXPERIENCE','SUMMARY'))
    assert 'item_layout' not in out['skills'][0]
    data,source=example()
    source=source.replace('PROJECT EXPERIENCE','PROJECT EXPERIENCE\nEDUCATION')
    assert 'item_layout' not in n._normalize_cv_data_for_output(data,source)['skills'][0]


def test_limits_and_ordinary_o_words_stay_unchanged():
    for source in ['x'*1000001,'line\n'*12001]:
        data,_=example();started=time.perf_counter()
        assert 'item_layout' not in n._normalize_cv_data_for_output(data,source)['skills'][0]
        assert time.perf_counter()-started<1
    data,source=example();data['skills'][0]['items'][3]='O rings tested'
    output=n._normalize_cv_data_for_output(data,source)
    assert output['skills'][0]['item_layout'][3]=='bullet'


@pytest.mark.parametrize('marker', ['\u2022', '\uf0b7', '-', '*', '1.'])
def test_generated_wrapping_markers_and_repeated_role_labels(marker):
    for index in range(30):
        data, source = example()
        source = source.replace('\u2022', marker).replace(
            'Managed product proofs of concept', 'Managed product proofs\nof concept')
        data['skills'][0]['items'][0] += ' ' + str(index)
        source = source.replace('2023 - 2024', '2023 - 2024 ' + str(index), 1)
        result = n._normalize_cv_data_for_output(data, source)['skills'][0]
        assert result['item_layout'][:5] == ['heading','heading','bullet','nested','nested']


def test_wrapped_children_source_footer_and_changed_country_do_not_change_words():
    data, source = example()
    source = source.replace('o Parallel Processing - multi-threaded runs',
                            'o Parallel Processing -\nmulti-threaded runs')
    source = source.replace('Role: Northwind',
                            'Example Curriculum Vitae\nRole: Northwind')
    before = copy.deepcopy(data['skills'][0]['items'])
    result = n._normalize_cv_data_for_output(data, source)['skills'][0]
    assert result['items'] == before
    assert result['item_layout'][3:5] == ['nested','nested']


def test_unicode_names_and_duplicate_source_parents_are_not_collapsed():
    data, source = example()
    data['skills'][0]['items'][0] = data['skills'][0]['items'][0].replace('Contoso', '東京')
    source = source.replace('Contoso', '北京')
    result = n._normalize_cv_data_for_output(data, source)['skills'][0]
    assert result['item_layout'][0] == 'bullet'
    data, source = example()
    source = source.replace('EDUCATION', '\u2022 Managed product proofs of concept\no Extra child\nEDUCATION')
    result = n._normalize_cv_data_for_output(data, source)['skills'][0]
    assert result['item_layout'][3:5] == ['bullet','bullet']


def test_explicit_legacy_date_title_can_have_a_source_marker():
    data, source = example()
    source = source.replace('2020, SENIOR CONSULTANT', '\uf0b7 2020, SENIOR CONSULTANT')
    result = n._normalize_cv_data_for_output(data, source)['skills'][0]
    assert result['item_layout'][9:12] == ['heading','heading','bullet']
    data, source = example()
    source = source.replace('Technical Lead. Team size: 5', '\u2022 Technical Lead. Team size: 5')
    result = n._normalize_cv_data_for_output(data, source)['skills'][0]
    assert result['item_layout'][:2] == ['bullet','bullet']


def test_real_word_pipeline_uses_headings_and_nested_numbering(tmp_path):
    import subprocess
    import json
    import zipfile
    from pathlib import Path
    from lxml import etree
    data, source = example()
    normalized = n._normalize_cv_data_for_output(data, source)
    payload = tmp_path/'cv.json'
    output = tmp_path/'cv.docx'
    payload.write_text(json.dumps(normalized), encoding='utf-8')
    root = Path(__file__).resolve().parents[1]
    subprocess.run(['node', str(root/'generate.js'), str(payload), str(output)],
                   cwd=root, check=True, capture_output=True)
    with zipfile.ZipFile(output) as archive:
        tree = etree.fromstring(archive.read('word/document.xml'))
    ns = {'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    ps = tree.xpath('//w:p', namespaces=ns)
    for item, style in zip(normalized['skills'][0]['items'], normalized['skills'][0]['item_layout']):
        visible = item[2:] if style == 'nested' else item
        matches = [p for p in ps if ''.join(p.xpath('.//w:t/text()', namespaces=ns)) == visible]
        assert matches
        for p in matches:
            levels = p.xpath('./w:pPr/w:numPr/w:ilvl/@w:val', namespaces=ns)
            if style == 'heading':
                assert not levels
                assert p.xpath('./w:pPr/w:keepNext', namespaces=ns)
                assert p.xpath('.//w:rPr/w:b', namespaces=ns)
            elif style == 'nested': assert levels == ['1']
            else: assert levels == ['0']


def test_blind_layout_has_no_source_text_and_requires_exact_unchanged_points():
    data,source=example();original=n._normalize_cv_data_for_output(data,source)
    reply=copy.deepcopy(original)
    reply['skills'][0]['items'][0]='Project: Ledger Migration, Leading Bank, 2023 - 2024'
    out=blind._blind_restore_cv_bullet_structure(reply,original)
    assert out['skills'][0]['item_layout']==original['skills'][0]['item_layout']
    assert 'Contoso' not in str(out)
    reply['skills'][0]['items'][2]='Changed duty'
    assert 'item_layout' not in blind._blind_restore_cv_bullet_structure(reply,original)['skills'][0]
    reply['skills'][0]['item_layout']=['SOURCE NAME']
    assert 'item_layout' not in blind._blind_restore_cv_bullet_structure(reply,{})['skills'][0]


@pytest.mark.parametrize('change', ['count','category','dates','reorder'])
def test_blind_layout_does_not_survive_ambiguous_correspondence(change):
    data, source = example()
    original = n._normalize_cv_data_for_output(data, source)
    reply = copy.deepcopy(original)
    group = reply['skills'][0]
    if change == 'count': group['items'].pop()
    if change == 'category': group['category'] = 'Training'
    if change == 'dates': group['items'][0] = group['items'][0].replace('2024','2025')
    if change == 'reorder': group['items'][2:4] = reversed(group['items'][2:4])
    assert 'item_layout' not in blind._blind_restore_cv_bullet_structure(reply, original)['skills'][0]


def test_malformed_original_layout_does_not_break_blinding():
    data, source = example()
    original=n._normalize_cv_data_for_output(data,source)
    original['skills'][0]['item_layout'][0]={'kind':'heading'}
    reply=copy.deepcopy(original)
    assert 'item_layout' not in blind._blind_restore_cv_bullet_structure(reply,original)['skills'][0]


def test_hostile_large_sections_and_malformed_skills_stay_bounded():
    for data, source in [
        ({'skills':[None, 42, 'text']}, 'PROJECT EXPERIENCE'),
        ({'skills':[{'category':'Project Experience','items':['x']*513}]}, 'PROJECT EXPERIENCE\nx'),
        (example()[0], 'PROJECT EXPERIENCE\n' + ('• ' + 'x'*200 + '\n')*4097),
    ]:
        started=time.perf_counter()
        out=n._normalize_cv_data_for_output(data, source)
        assert all('item_layout' not in s for s in out['skills'])
        assert time.perf_counter()-started<1
