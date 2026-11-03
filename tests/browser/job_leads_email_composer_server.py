"""Isolated email-composer preview with sample ads and fictional Graph calls.

Run from the repository root, then run job_leads_email_composer.py.
All receipt/data/token paths point to a temporary directory.
"""
from pathlib import Path
import os
import tempfile
from unittest.mock import patch
import sys
package_root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(package_root))
with tempfile.TemporaryDirectory(prefix='cvstudio-review-') as folder:
    root=Path(folder)
    original_expanduser=os.path.expanduser
    def isolated_expanduser(path):
        value=os.fspath(path)
        if value=='~':return str(root)
        if value.startswith('~/'):return str(root/value[2:])
        return original_expanduser(path)
    os.environ.update(CVSTUDIO_STATE_DIR=str(root/'state'),CVSTUDIO_DB_PATH=str(root/'main.sqlite3'),CVSTUDIO_JOB_STATE_PATH=str(root/'jobs.json'),SALARY_COMPARISON_DATA_DIR=str(root/'salary'),LOCALAPPDATA=str(root/'local'),APPDATA=str(root/'appdata'))
    with patch('os.path.expanduser',side_effect=isolated_expanduser):
        from owner_build_tools.build_protected import write_test_receipt
        write_test_receipt(package_root,environment={'HOME':str(root)})
        os.environ.update(CVSTUDIO_OWNER_BUILD_SMOKE='1',CVSTUDIO_OWNER_BUILD_SMOKE_PORT='5077')
        import app
        import time
        from unittest.mock import Mock
        for i in range(1,4):
            app._JOB_LEADS.save(dict(url='https://www.linkedin.com/jobs/view/'+str(90000+i),company='Example Client '+str(i),role='Finance Manager '+str(i),contact='Alex <alex@example.com>' if i==1 else '',favorite=i==1))
        app._OUTLOOK_SERVICE._store=dict(access_token='fictional-token',expires_at=int(time.time())+3600,scope=app._OUTLOOK_SERVICE._SEND_SCOPE,account=dict(email='owner@example.com'))
        graph=Mock()
        def graph_response(path,**kwargs):
            if path=='me/messages':return dict(id='fictional-draft',webLink='https://outlook.office.com/mail/draft/fictional')
            if path=='me/sendMail':return {}
            if path=='me':return dict(mail='owner@example.com')
            raise AssertionError('Unexpected fake Graph path: '+path)
        graph.request_json.side_effect=graph_response
        app._OUTLOOK_SERVICE._graph_client=graph
        @app.app.get('/__job_leads_email_fixture__')
        def email_fixture_marker():return {'fictional_email_fixture':True}
        app.app.run(host='127.0.0.1',port=5077,debug=False,use_reloader=False)
