import json
import pytest
from ui import missions


def test_checkpoint_projection_retains_independent_states_and_refreshes(tmp_path, monkeypatch):
    path=tmp_path/'register.json';monkeypatch.setattr(missions,'REGISTER',path)
    register=dict(schema='charlie.master-campaign.v1',capabilities=[dict(id='fixture',
        status=dict(published_to_master='pending',installed='UNKNOWN',physically_qualified='pending'))])
    path.write_text(json.dumps(register))
    assert missions.mission_status()['register']==register
    assert missions.mission_status()['physical_authorization'] is False
    register['capabilities'][0]['status']['published_to_master']='fixture-merge'
    path.write_text(json.dumps(register))
    assert missions.mission_status()['register']==register
    path.write_text('{}')
    with pytest.raises(ValueError):missions.mission_status()


def test_monitoring_missions_endpoint_is_authenticated_and_read_only():
    import socket
    from tests.test_mobile_http import call
    from ui.dashboard import start_dashboard
    try:
        probe=socket.socket();probe.close()
    except PermissionError:pytest.skip('sandbox denies loopback; independent CI required')
    server=start_dashboard(None,'m'*40,port=0)
    try:
        assert call(server,'/api/missions',token='bad')[0]==401
        code,raw=call(server,'/api/missions')
        assert code==200 and json.loads(raw)['physical_authorization'] is False
        assert call(server,'/api/missions',method='POST',body={})[0]==404
        assert call(server,'/missions')[0]==200
    finally:server.close()
