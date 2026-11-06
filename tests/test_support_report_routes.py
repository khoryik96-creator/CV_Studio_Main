"""The existing support ZIP route gains explicit, paired issue actions only."""
import io
import zipfile
from unittest import mock

from test_support_reports import setup
from cvstudio_support import SupportReports


def test_issue_actions_require_current_browser_pairing_and_preserve_legacy_download():
    import app
    service,messages,_,_,_=setup()
    browser=app.app.test_client();headers={'X-CV-Studio-Request':'1'}
    with mock.patch.object(app,'_CVSTUDIO_SUPPORT',service):
        assert browser.post('/diagnostics/support_bundle',json={'action':'issue_status'},headers=headers).status_code==403
        browser.get('/')
        assert browser.post('/diagnostics/support_bundle',json={'action':'issue_status'},headers={'Origin':'https://other.test'}).status_code==403
        status=browser.post('/diagnostics/support_bundle',json={'action':'issue_status'},headers=headers)
        assert status.status_code==200 and status.json['recipient']=='support@example.test'
        preview=browser.post('/diagnostics/support_bundle',json={'action':'issue_prepare','description':'A fictional button failed.','doctor':'Fictional Doctor'},headers=headers)
        assert preview.status_code==200 and not messages
        data=preview.json;proof={key:data[key] for key in ('report_id','preview_token')}
        assert browser.post('/diagnostics/support_bundle',json={'action':'issue_send',**proof},headers=headers).status_code==400
        download=browser.post('/diagnostics/support_bundle',json={'action':'issue_download',**proof},headers=headers)
        with zipfile.ZipFile(io.BytesIO(download.data)) as archive:assert 'doctor-report.txt' in archive.namelist()
        assert not messages
        sent=browser.post('/diagnostics/support_bundle',json={'action':'issue_send',**proof,'confirmed':True},headers=headers)
        assert sent.status_code==200 and sent.json['state']=='accepted' and len(messages)==1
        result=browser.post('/diagnostics/support_bundle',json={'action':'issue_result',**proof},headers=headers)
        assert result.status_code==200 and result.json['state']=='accepted'
        assert 'no-store' in result.headers['Cache-Control']
        assert browser.post('/diagnostics/support_bundle',json={'action':'issue_unknown'},headers=headers).status_code==400
    with mock.patch.object(app._CVSTUDIO_DIAGNOSTICS_SERVICE,'support_bundle',side_effect=lambda body:app.jsonify(legacy=True)) as legacy:
        response=browser.post('/diagnostics/support_bundle',json={'browser':{'active_tab':'format'}},headers=headers)
        assert response.json=={'legacy':True}
        assert legacy.call_args.args==({'browser':{'active_tab':'format'}},)


def test_oversized_support_body_is_rejected_without_parsing_or_delivery():
    import app
    browser=app.app.test_client();browser.get('/')
    with mock.patch.object(app._CVSTUDIO_SUPPORT,'send') as send:
        result=browser.post('/diagnostics/support_bundle',data=b' '* (SupportReports.MAX_INPUT_BYTES+1),content_type='application/json',headers={'X-CV-Studio-Request':'1'})
    assert result.status_code==413;send.assert_not_called()
