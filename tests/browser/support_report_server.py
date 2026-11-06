"""Isolated real app + fictional Outlook. Run before support_report.py."""
from pathlib import Path
import os
import sys
import tempfile
import time
from unittest.mock import Mock, patch

package_root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(package_root))
with tempfile.TemporaryDirectory(prefix='cvstudio-support-check-') as folder:
    root=Path(folder)
    original_expanduser=os.path.expanduser
    def isolated_expanduser(path):
        value=os.fspath(path)
        if value=='~':return str(root)
        if value.startswith('~/'):return str(root/value[2:])
        return original_expanduser(path)
    os.environ.update(CVSTUDIO_STATE_DIR=str(root/'state'),CVSTUDIO_DB_PATH=str(root/'main.sqlite3'),CVSTUDIO_JOB_STATE_PATH=str(root/'jobs.json'),SALARY_COMPARISON_DATA_DIR=str(root/'salary'),LOCALAPPDATA=str(root/'local'),APPDATA=str(root/'appdata'),CVSTUDIO_SUPPORT_EMAIL='support@example.test')
    with patch('os.path.expanduser',side_effect=isolated_expanduser):
        from owner_build_tools.build_protected import write_test_receipt
        write_test_receipt(package_root,environment={'HOME':str(root)})
        os.environ.update(CVSTUDIO_OWNER_BUILD_SMOKE='1',CVSTUDIO_OWNER_BUILD_SMOKE_PORT='58484')
        import app
        service=app._OUTLOOK_SERVICE
        service._store=dict(access_token='fictional-token',expires_at=int(time.time())+3600,scope=service._SEND_SCOPE,account=dict(email='reporter@example.test'))
        messages=[];graph=Mock()
        def response(path,**kwargs):
            if path=='me/sendMail':messages.append(kwargs['body']);return {}
            if path=='me':return dict(mail='reporter@example.test')
            raise AssertionError('Unexpected fake Graph request')
        graph.request_json.side_effect=response
        service._graph_client=graph
        app._CVSTUDIO_SUPPORT.runtime=lambda:{'runtime_mode':'source','platform':{'system':'Fictional OS'},'connections':{'outlook':{'connected':True}}}
        @app.app.get('/__support_fixture__')
        def marker():return {'fictional_support_fixture':True,'sends':len(messages),'messages':messages}
        @app.app.post('/__support_fixture__/disconnect')
        def disconnect():service._store={};return {'ok':True}
        app.app.run(host='127.0.0.1',port=58484,debug=False,use_reloader=False)
