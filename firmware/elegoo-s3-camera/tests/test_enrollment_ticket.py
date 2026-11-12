import importlib.util
import json
import secrets
import subprocess
from pathlib import Path
import pytest
root=Path(__file__).resolve().parents[1]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
peer=load('ticket',root/'verify_ticket.py')
enrollment=load('enrollment',root/'tools'/'make_enrollment.py')
DEVICE='elegoo-010203040506'

def ticket(**changes):
    result=dict(version=1,device_id=DEVICE,transaction=secrets.token_hex(16),ssid='fixture-network',lease_seconds=2)
    result.update(changes);return result

@pytest.mark.parametrize('change',[{'version':True},{'device_id':'impostor'},{'transaction':'bad'},
    {'ssid':'x'*33},{'ssid':'bad\0name'},{'lease_seconds':91},{'lease_seconds':True},{'token':'untrusted'}])
def test_bad_tickets_rejected(change):
    with pytest.raises(ValueError):peer.parse_ticket(json.dumps(ticket(**change)),DEVICE)

def test_duplicate_and_large_ticket_rejected():
    with pytest.raises(ValueError):peer.parse_ticket('{"version":1,"version":1}',DEVICE)
    with pytest.raises(ValueError):peer.parse_ticket('x'*1025,DEVICE)

def test_explicit_authorization_required_before_importing_peer(tmp_path):
    result=subprocess.run(['python3',str(root/'verify_ticket.py'),'--ticket',str(tmp_path/'missing'),
        '--enrollments',str(tmp_path),'--lan-ip','127.0.0.1','--device-id',DEVICE],capture_output=True,text=True)
    assert result.returncode!=0 and '--authorize-confirm' in result.stderr

def test_private_physical_enrollment_and_name_constrained_ca(tmp_path,capsys):
    path=tmp_path/'private';metadata=enrollment.generate(path,DEVICE)
    record=json.loads((path/'identity-enrollment.json').read_text())
    assert path.stat().st_mode&0o777==0o700
    assert all(p.stat().st_mode&0o777==0o600 for p in path.iterdir())
    assert len(record['certificate'].encode())<2048 and len(record['private_key'].encode())<2048
    assert metadata['enrollment_bytes']<7168
    assert record['token'] not in json.dumps(metadata)+capsys.readouterr().out
    assert record['command_key'] != record['token']
    assert record['command_key'] not in (path/DEVICE).read_text()
    assert record['command_key'] not in json.dumps(metadata)
    assert json.loads((path/'qualified-control.json').read_text())['command_key']==record['command_key']
    assert record['private_key'] not in json.dumps(metadata)
    # A certificate for this device cannot authenticate another hostname.
    command=['openssl','verify','-CAfile',str(path/'operator-ca.crt'),'-verify_hostname','foreign.invalid',str(path/'device.crt')]
    assert subprocess.run(command,capture_output=True).returncode!=0
    with pytest.raises(FileExistsError):enrollment.generate(path,DEVICE)

class Clock:
    def __init__(self):self.now=0.
    def __call__(self):return self.now
    def sleep(self,value):self.now+=value

@pytest.mark.parametrize('failure',['auth','transaction','target','loss'])
def test_failure_never_claims_verified_and_never_switches(failure):
    clock=Clock();t=ticket()
    class Protocol:
        def status(self,*args):
            if failure in ('auth','loss'):raise OSError('untrusted private failure')
            return dict(device_id=DEVICE,joined=True,transaction=t['transaction'] if failure=='target' else 'stale')
        def confirm(self,*args):raise ValueError('wrong target')
    class Discovery:
        def candidates(self,*args):return ['lan']
    with pytest.raises(TimeoutError):peer.verify(t,Protocol(),Discovery(),clock=clock,sleep=clock.sleep)
    assert clock.now<=2


def test_private_material_cannot_be_generated_in_git(tmp_path):
    repository=tmp_path/'repository';git=repository/'.git';git.mkdir(parents=True)
    (git/'HEAD').write_text('ref: refs/heads/test\n')
    output=repository/'private-identity'
    with pytest.raises(ValueError):enrollment.generate(output,DEVICE)
    assert not output.exists()
