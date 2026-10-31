"""Real loopback authorization; runs in independent CI, not native motor testing."""
import http.client
import json
import socket
import pytest
from ui.dashboard import start_dashboard,DEFAULT_ORIGIN
from tests.test_mobile_console import fixture


@pytest.fixture
def endpoint():
    try:
        probe=socket.socket();probe.close()
    except PermissionError:pytest.skip('session denies loopback sockets; independent CI required')
    s=fixture();server=start_dashboard(None,'m'*40,drive_token='d'*40,mobile=s.c,port=0)
    yield s,server
    server.close()


def call(server,path='/api/mobile',method='GET',token='m'*40,body=None,**changes):
    c=http.client.HTTPConnection(*server.address,timeout=3)
    headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Origin':DEFAULT_ORIGIN}
    headers.update(changes)
    c.request(method,path,body=json.dumps(body) if body is not None else None,headers=headers)
    r=c.getresponse();data=r.read();code=r.status;c.close()
    return code,data


def test_monitor_cannot_acquire_or_drive_but_can_read_status_and_frame(endpoint):
    s,server=endpoint
    assert call(server)[0]==200
    assert call(server,'/api/mobile/frame')[1].startswith(b'\x89PNG')
    assert call(server,method='POST',body={'action':'acquire','boot':s.c.boot})[0]==401
    assert call(server,token='bad')[0]==401
    assert call(server,Origin='https://foreign.example')[0]==403
    assert call(server,Host='evil.example')[0]==403
    assert call(server,'/mobile')[0]==200


def test_drive_auth_boot_lease_and_nonreplay_sequence_are_all_required(endpoint):
    s,server=endpoint
    assert call(server,method='POST',token='d'*40,body={'action':'acquire','boot':'old'})[0]==400
    code,raw=call(server,method='POST',token='d'*40,body={'action':'acquire','boot':s.c.boot})
    assert code==200;lease=json.loads(raw)['lease'];s.now[0]+=.001
    b={'action':'drive','boot':s.c.boot,'lease':lease,'sequence':1,'direction':'FORWARD','pwm':20}
    assert call(server,method='POST',token='d'*40,body=b)[0]==200
    assert call(server,method='POST',token='d'*40,body=b)[0]==400
    assert call(server,method='POST',token='d'*40,body={'action':'emergency'})[0]==200
    assert s.e._safety_stopped


def test_missing_drive_credential_and_invalid_configuration_fail_closed():
    with pytest.raises(ValueError):start_dashboard(None,'m'*40,drive_token='m'*40,port=0)
    with pytest.raises(ValueError):start_dashboard(None,'m'*40,drive_token='short',port=0)


def test_bounded_bodies_and_methods_and_frame_metadata(endpoint):
    s,server=endpoint
    code,_=call(server,method='POST',token='d'*40,body={'padding':'x'*5000})
    assert code==400
    code,_=call(server,method='POST',token='d'*40,body=['array'])
    assert code==400
    c=http.client.HTTPConnection(*server.address,timeout=3)
    c.request('GET','/api/mobile/frame?overlays=1',headers={'Authorization':'Bearer '+'m'*40,'Origin':DEFAULT_ORIGIN})
    r=c.getresponse();metadata=json.loads(r.getheader('X-Charlie-Frame'));assert r.status==200
    assert metadata['frame_id']=='f1' and metadata['source']=='elegoo-v4';r.read();c.close()
