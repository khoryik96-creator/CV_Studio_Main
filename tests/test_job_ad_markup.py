from unittest import mock
import pytest
from test_job_leads import module
from cvstudio_job_leads import render_description_markup, format_description, rich_text, JobLeadsError

MARKUP = ('<strong>Example Company </strong>helps clients.<br><br>'
          '<strong>What you will do</strong><br><ul><li></li><ul>'
          '<li>Build systems.</li><li>Support &amp; improve services.</li>'
          '</ul></ul><p>Apply today.</p>')

def test_literal_html_becomes_bold_and_one_clean_bullet_list_without_text_loss():
    result = render_description_markup(MARKUP)
    assert '<strong>' not in result['description'] and '&amp;' not in result['description']
    assert 'Support & improve services.' in result['description']
    lists = [node for node in result['description_rich'] if node.get('tag') == 'ul']
    assert len(lists) == 1 and [item['tag'] for item in lists[0]['children']] == ['li','li']
    assert result['description_rich'][0]['tag'] == 'strong'
    assert ''.join(result['description'].split()) == ''.join(rich_text(result['description_rich']).split())
    assert format_description(result['description'], MARKUP) == result['description_rich']

def test_real_nested_items_and_numbered_lists_remain_nested():
    result = render_description_markup('<ol><li>Main<ol><li>Child</li></ol></li><li>Next</li></ol>')
    outer = result['description_rich'][0]
    assert outer['tag'] == 'ol' and outer['children'][0]['children'][1]['tag'] == 'ol'
    assert 'Main' in result['description'] and 'Child' in result['description']

def test_markup_never_returns_executable_tags_attributes_links_or_remote_images():
    result = render_description_markup('<p onclick="bad()">Visible <a href="https://example.invalid">words</a><img src="https://example.invalid/image"></p><script>secret()</script><iframe>hidden</iframe>')
    assert result['description'] == 'Visible words'
    assert result['description_rich'] == [{'tag':'p','children':[{'text':'Visible '},{'text':'words'}]}]
    with pytest.raises(JobLeadsError): render_description_markup('<p>'+'x'*20001+'</p>')
    with pytest.raises(JobLeadsError): render_description_markup('<div>'*5000+'<p>Text</p>')
    with pytest.raises(JobLeadsError): render_description_markup('Plain business text')

def test_render_route_is_read_only_and_uses_no_provider(module):
    client=module.app.test_client()
    with mock.patch.object(module._AI_PROVIDER_CLIENT,'request') as provider:
        response=client.post('/job-leads',json={'action':'format_content','render_markup':True,'description':MARKUP},headers={'X-CV-Studio-Request':'1'})
        assert response.status_code == 200
        assert {key:response.json[key] for key in ('description','description_rich')} == render_description_markup(MARKUP)
        assert not module._JOB_LEADS.path.exists()
        provider.assert_not_called()
