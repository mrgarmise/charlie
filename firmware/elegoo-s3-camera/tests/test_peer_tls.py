import importlib.util
import json
from pathlib import Path
import secrets
from types import SimpleNamespace
import pytest
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('handoff_peer',root/'verify_ticket.py')
handoff=importlib.util.module_from_spec(spec);spec.loader.exec_module(handoff)

def test_real_pinned_tls_browser_ticket_commits_only_after_peer_confirmation(simulated_device,peer_modules):
    TLSProtocol,SecretStore=peer_modules
    state,directory,identity,server=simulated_device
    protocol=TLSProtocol(SecretStore(directory))
    endpoint=SimpleNamespace(address='127.0.0.1',port=server.server_port,source_ip='127.0.0.1')
    transaction=secrets.token_hex(16)
    credentials=SimpleNamespace(ssid='fixture-network',password=secrets.token_urlsafe(20))
    assert protocol.prepare(endpoint,state['device_id'],credentials,transaction,protocol.clock()+5)['accepted']
    assert not state['committed']
    ticket=handoff.parse_ticket(json.dumps(dict(version=1,device_id=state['device_id'],transaction=transaction,
        ssid=credentials.ssid,lease_seconds=5)),state['device_id'])
    class Discovery:
        def candidates(self,*args):return [endpoint]
    result=handoff.verify(ticket,protocol,Discovery())
    assert result['verified'] and state['committed']
    assert credentials.password not in json.dumps(result) and identity['token'] not in json.dumps(result)

def test_wrong_certificate_pin_sends_no_http_authentication(simulated_device,peer_modules):
    TLSProtocol,SecretStore=peer_modules
    state,directory,identity,server=simulated_device
    path=directory/state['device_id'];record=json.loads(path.read_text());record['fingerprint']='0'*64;path.write_text(json.dumps(record))
    protocol=TLSProtocol(SecretStore(directory))
    endpoint=SimpleNamespace(address='127.0.0.1',port=server.server_port,source_ip='127.0.0.1')
    with pytest.raises(OSError):protocol.status(endpoint,state['device_id'],protocol.clock()+5)
    assert state['requests']==[]
