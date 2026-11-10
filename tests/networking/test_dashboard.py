import socket
import pytest
from tests.test_mobile_http import call
from ui.dashboard import start_dashboard


class Service:
    def __init__(self): self.requests=[]
    def status(self): return {'state':'offline','verified':False}
    def execute(self, request):
        if request != {'operation':'locally-armed'}: raise PermissionError('private failure')
        self.requests.append(request)
        return {'accepted':True}


def test_network_credential_must_be_separate():
    for credential in [None,'short','m'*40,'d'*40]:
        with pytest.raises(ValueError):
            start_dashboard(None,'m'*40,drive_token='d'*40,network=Service(),network_token=credential,port=0)


def test_dashboard_existing_auth_and_bounded_one_shot():
    try:
        probe=socket.socket(); probe.close()
    except PermissionError: pytest.skip('loopback denied; independent CI required')
    network=Service()
    server=start_dashboard(None,'m'*40,drive_token='d'*40,network=network,network_token='n'*40,port=0)
    try:
        assert call(server,'/api/network')[0]==200
        for token in ['m'*40,'d'*40,'wrong']:
            assert call(server,'/api/network',method='POST',token=token,body={'operation':'locally-armed'})[0]==401
        assert call(server,'/api/network',method='POST',token='n'*40,body={'operation':'locally-armed'})[0]==202
        assert len(network.requests)==1
        code,raw=call(server,'/api/network',method='POST',token='n'*40,body={'password':'x'*300})
        assert code==403 and b'private' not in raw
        assert call(server,'/api/network',method='POST',token='n'*40,body={},Origin='https://foreign.example')[0]==403
    finally: server.close()
