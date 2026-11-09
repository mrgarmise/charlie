import secrets
from concurrent.futures import ThreadPoolExecutor
import pytest

from networking.provisioning import Authorization, NetworkCredentials, NetworkManager, ProvisioningError
from networking.transport import Enrollment, Endpoint, SecretStore, Discovery
from networking.service import NetworkService
from stimulus.bus import StimulusBus


class Clock:
    def __init__(self): self.now = 10.
    def __call__(self): return self.now
    def sleep(self, seconds): self.now += seconds


class DiscoveryFake:
    def __init__(self): self.online = True
    def candidates(self, device, deadline): return ['stale', 'lan'] if self.online else []


class Protocol:
    def __init__(self, discovery):
        self.discovery = discovery
        self.transaction = None
        self.fail = None
        self.calls = []
    def status(self, endpoint, device, deadline):
        self.calls.append(('status', endpoint))
        if endpoint == 'stale' or self.fail == 'auth': raise OSError('untrusted')
        return dict(device_id=device, joined=True, transaction=self.transaction)
    def prepare(self, endpoint, device, credentials, transaction, deadline):
        self.calls.append(('prepare', endpoint))
        if self.fail == 'credentials': raise OSError('association failed')
        self.transaction = transaction
        self.discovery.online = self.fail != 'loss'
        return dict(accepted=True, transaction=transaction)
    def confirm(self, endpoint, device, transaction, ssid, deadline):
        self.calls.append(('confirm', endpoint))
        assert endpoint == 'lan'
        if self.fail == 'confirm': raise OSError('mismatch')


class Adapters:
    def __init__(self): self.calls = []; self.bad_secondary = False; self.bad_restore = False; self.absent = False
    def secondary(self): return ['wlan1']
    def primary(self): return 'wlan0'
    def checkpoint(self, adapter, seconds):
        self.calls.append(('checkpoint', adapter))
        if self.absent and adapter == 'wlan1': raise OSError('absent')
        return adapter
    def connect_setup(self, adapter, deadline):
        self.calls.append(('setup', adapter))
        if adapter == 'wlan1' and self.bad_secondary: raise OSError('unreachable')
        return 'setup'
    def restore(self, checkpoint, deadline):
        self.calls.append(('restore', checkpoint))
        return not self.bad_restore


@pytest.fixture
def rig():
    clock = Clock(); discovery = DiscoveryFake(); protocol = Protocol(discovery); adapters = Adapters()
    manager = NetworkManager(StimulusBus(), discovery, protocol, adapters, clock=clock, sleep=clock.sleep)
    return manager, discovery, protocol, adapters, clock


def credentials(): return NetworkCredentials('fixture-network', secrets.token_urlsafe(20))
def auth(clock, **kwargs): return Authorization('device-test', clock()+80, **kwargs)


def test_lan_priority_and_registry(rig):
    m,d,p,a,c = rig
    assert m.provision(credentials(), auth(c))['verified']
    assert not a.calls
    assert m.bus.latest_observation(m.source,max_age=1,clock=c).values['state'] == 'verified'
    assert not hasattr(m, 'executor')


def test_secondary_and_restore_before_lan_confirmation(rig):
    m,d,p,a,c = rig; d.online = False
    state = m.provision(credentials(), auth(c, allow_setup=True))
    assert state['restoration'] == 'verified'
    assert a.calls == [('checkpoint','wlan1'),('setup','wlan1'),('restore','wlan1')]
    assert ('confirm','lan') in p.calls


@pytest.mark.parametrize('absent', [True, False])
def test_explicit_primary_fallback(rig, absent):
    m,d,p,a,c = rig; d.online = False; a.absent=absent; a.bad_secondary=True
    assert m.provision(credentials(), auth(c,allow_setup=True,allow_primary=True,
                         acknowledged_disconnect=True))['verified']
    assert ('setup','wlan0') in a.calls


@pytest.mark.parametrize('options', [{},{'allow_setup':True},{'allow_setup':True,'allow_primary':True}])
def test_primary_never_implicit(rig, options):
    m,d,p,a,c = rig; d.online=False; a.bad_secondary=True
    with pytest.raises(ProvisioningError): m.provision(credentials(),auth(c,**options))
    assert ('setup','wlan0') not in a.calls


def test_surprise_loss_only_backoff(rig):
    m,d,p,a,c = rig
    assert m.poll('device-test')['valid']
    d.online=False; c.now += 3
    assert not m.poll('device-test')['valid']
    calls=len(p.calls)
    m.poll('device-test')
    assert len(p.calls)==calls and not a.calls
    assert m.next_retry > c()


@pytest.mark.parametrize('failure', ['auth','credentials','loss','confirm'])
def test_failure_never_verified_or_moves(rig, failure):
    m,d,p,a,c=rig; p.fail=failure
    with pytest.raises(ProvisioningError): m.provision(credentials(),auth(c))
    assert not m.status()['verified']
    assert not a.calls


def test_failed_restoration_blocks_success(rig):
    m,d,p,a,c=rig; d.online=False; a.bad_restore=True
    with pytest.raises(ProvisioningError): m.provision(credentials(),auth(c,allow_setup=True))
    assert m.status()['restoration']=='failed'
    assert not m.status()['verified']
    assert not any(call[0]=='confirm' for call in p.calls)


def test_one_use_authorization_and_deadlines(rig):
    m,d,p,a,c=rig; authorization=auth(c)
    m.provision(credentials(),authorization)
    with pytest.raises(ProvisioningError): m.provision(credentials(),authorization)
    for expiry in [c()-1, float('nan'), c()+121]:
        with pytest.raises(ProvisioningError): m.provision(credentials(),Authorization('device-test',expiry))


def test_concurrency_rejected_without_touching_adapter(rig):
    m,d,p,a,c=rig
    m.lock.acquire()
    try:
        with pytest.raises(ProvisioningError): m.provision(credentials(),auth(c))
        assert m.poll('device-test')['state']=='offline'
        assert not a.calls
    finally: m.lock.release()


def test_secret_store_permissions_and_no_repr_or_logging(rig,tmp_path,capsys,caplog):
    m,d,p,a,c=rig; secret=credentials(); store=SecretStore(tmp_path/'private')
    enrollment=Enrollment('device-test','a'*64,secrets.token_urlsafe(32))
    store.save(enrollment)
    assert store.load('device-test')==enrollment
    assert (tmp_path/'private'/'device-test').stat().st_mode & 0o777 == 0o600
    assert secret.password not in repr(secret) and enrollment.token not in repr(enrollment)
    m.provision(secret,auth(c))
    assert secret.password not in str(m.status())+capsys.readouterr().out+caplog.text
    (tmp_path/'private'/'device-test').chmod(0o644)
    with pytest.raises(PermissionError): store.load('device-test')
    with pytest.raises(ValueError): store.load('../escape')


def test_secret_store_symlink_rejected(tmp_path):
    directory=tmp_path/'private'; store=SecretStore(directory)
    (directory/'device-test').symlink_to(tmp_path/'elsewhere')
    with pytest.raises(OSError): store.load('device-test')


def test_local_intent_service_one_shot(rig):
    m,d,p,a,c=rig; service=NetworkService(m)
    handle=service.arm(credentials(),auth(c))
    assert handle not in str(service.status())
    with pytest.raises(PermissionError): service.execute({'operation':'invalid'})
    assert service.execute({'operation':handle})=={'accepted':True}
    service.worker.join(2)
    assert service.status()['verified']
    with pytest.raises(PermissionError): service.execute({'operation':handle})


def test_discovery_excludes_setup_stale_address_and_binds_lan():
    class Info:
        port=443
        def parsed_addresses(self): return ['192.168.4.1','10.0.0.8','127.0.0.1']
    class Z:
        def get_service_info(self,*args,**kwargs): return Info()
    discovery=Discovery(Z(),'10.0.0.2',hints=[Endpoint('10.0.0.8')])
    assert discovery.candidates('device-test',discovery.clock()+1)==[Endpoint('10.0.0.8',443,'10.0.0.2')]
