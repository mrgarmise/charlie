import hashlib
import json
import secrets
import pytest
from networking.transport import TLSProtocol, SecretStore, Enrollment, Endpoint
from networking.provisioning import NetworkCredentials
from networking.adapters import SavedAdapters


@pytest.fixture
def wire(tmp_path, monkeypatch):
    certificate = b'generated-test-certificate-bytes'
    store = SecretStore(tmp_path/'keys')
    enrollment = Enrollment('device-test', hashlib.sha256(certificate).hexdigest(), secrets.token_urlsafe(32))
    store.save(enrollment)
    class Response:
        status=200
        def read(self, bound): return json.dumps(Connection.reply).encode()[:bound]
    class Socket:
        def getpeercert(self, binary_form): return Connection.certificate
    class Connection:
        certificate=b'generated-test-certificate-bytes'
        requests=[]
        reply={'device_id':'device-test','joined':True,'transaction':'test'}
        def __init__(self,*args,**kwargs): self.sock=Socket()
        def connect(self): pass
        def close(self): pass
        def request(self,*args,**kwargs): self.requests.append((args,kwargs))
        def getresponse(self): return Response()
    monkeypatch.setattr('networking.transport.http.client.HTTPSConnection',Connection)
    return TLSProtocol(store), Connection, enrollment


def test_tls_pin_checked_before_secrets(wire):
    protocol,connection,enrollment=wire
    connection.certificate=b'wrong-certificate'
    with pytest.raises(OSError): protocol.status(Endpoint('10.0.0.8'),'device-test',protocol.clock()+5)
    assert not connection.requests


def test_tls_identity_and_response_filtering(wire):
    protocol,connection,enrollment=wire
    connection.reply['password']=secrets.token_urlsafe(20)
    reply=protocol.status(Endpoint('10.0.0.8'),'device-test',protocol.clock()+5)
    assert 'password' not in reply
    connection.reply['device_id']='impostor'
    with pytest.raises(ValueError): protocol.status(Endpoint('10.0.0.8'),'device-test',protocol.clock()+5)


@pytest.mark.parametrize('field,value',[('ssid','wrong'),('joined',False),('transaction','stale'),('device_id','impostor')])
def test_confirm_checks_target_before_commit(wire,field,value):
    protocol,connection,enrollment=wire
    connection.reply.update(ssid='fixture-network')
    connection.reply[field]=value
    with pytest.raises(ValueError):
        protocol.confirm(Endpoint('10.0.0.8'),'device-test','test','fixture-network',protocol.clock()+5)
    assert len(connection.requests)==1


def test_deadline_no_network(wire):
    protocol,connection,enrollment=wire
    with pytest.raises(TimeoutError): protocol.status(Endpoint('10.0.0.8'),'device-test',0)
    assert not connection.requests


class Backend:
    def __init__(self): self.calls=[]; self.saved_profile='original'; self.current='original'
    def device(self,name): return name
    def snapshot(self,device): return "fixture-ip-routes-dns"
    def saved(self,device): return self.saved_profile
    def checkpoint(self,device,seconds): self.calls.append(('checkpoint',device,seconds)); return 'checkpoint'
    def profile(self,uuid): return 'setup'
    def validate_setup(self,profile,adapter): pass
    def activate(self,profile,device): self.calls.append(('activate',device)); self.current=profile
    def rollback(self,path): self.calls.append(('rollback',path)); self.current=self.saved_profile; return True
    def restored(self,device,saved): return self.current==saved


def test_checkpoint_before_activation_and_saved_profile_restored():
    backend=Backend(); adapters=SavedAdapters(backend,{'wlan1':'fixture-uuid'},Endpoint('192.168.4.1'))
    checkpoint=adapters.checkpoint('wlan1',95)
    assert adapters.connect_setup('wlan1',adapters.clock()+1)==Endpoint('192.168.4.1')
    assert adapters.restore(checkpoint,adapters.clock()+1)
    assert backend.calls==[('checkpoint','wlan1',95),('activate','wlan1'),('rollback','checkpoint')]
    assert checkpoint.saved=='original'


def test_daemon_rollback_never_cancelled_on_failure():
    backend=Backend(); backend.rollback=lambda path:False
    adapters=SavedAdapters(backend,{'wlan1':'fixture-uuid'},Endpoint('192.168.4.1'))
    checkpoint=adapters.checkpoint('wlan1',95)
    assert not adapters.restore(checkpoint,adapters.clock()+1)
    assert backend.calls==[('checkpoint','wlan1',95)]


def test_restored_uuid_without_original_routes_is_failure():
    backend=Backend(); adapters=SavedAdapters(backend,{'wlan1':'fixture-uuid'},Endpoint('192.168.4.1'))
    checkpoint=adapters.checkpoint('wlan1',95)
    backend.snapshot=lambda device:'changed-default-route'
    assert not adapters.restore(checkpoint,adapters.clock())


@pytest.mark.parametrize('unsafe', ['default','dns','routes','adapter','dhcp-routes'])
def test_native_profile_validation_rejects_primary_interference(unsafe):
    from networking.adapters import DBusBackend
    import copy
    settings={'connection':{'type':'802-11-wireless','interface-name':'wlan1'},
              'ipv4':{'never-default':True,'ignore-auto-dns':True,'ignore-auto-routes':True},
              'ipv6':{'never-default':True,'ignore-auto-dns':True,'ignore-auto-routes':True}}
    backend=object.__new__(DBusBackend)
    backend.call=lambda *args:settings
    backend.validate_setup('/profile','wlan1')
    if unsafe=='default':settings['ipv4']['never-default']=False
    elif unsafe=='dns':settings['ipv6']['dns']=['fixture']
    elif unsafe=='routes':settings['ipv4']['route-data']=[{'dest':'0.0.0.0'}]
    elif unsafe=='adapter':settings['connection']['interface-name']='wlan0'
    elif unsafe=='dhcp-routes':settings['ipv4']['ignore-auto-routes']=False
    with pytest.raises(ValueError):backend.validate_setup('/profile','wlan1')


def test_deadline_cannot_automatically_reopen_unpinned_session(wire):
    protocol,connection,enrollment=wire
    original=connection.request
    def request(self,*args,**kwargs):
        assert self.auto_open==0
        return original(self,*args,**kwargs)
    connection.request=request
    protocol.status(Endpoint('10.0.0.8'),'device-test',protocol.clock()+5)
