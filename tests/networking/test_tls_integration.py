"""Real ephemeral HTTPS endpoint, no hardware/D-Bus or persistent test secrets."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import socket
import ssl
import subprocess
import threading
from types import SimpleNamespace

import pytest
from networking.provisioning import Authorization, NetworkCredentials, NetworkManager, ProvisioningError
from networking.transport import Enrollment, SecretStore, TLSProtocol
from stimulus.bus import StimulusBus


@pytest.fixture
def device(tmp_path):
    try:
        probe=socket.socket();probe.close()
    except PermissionError:pytest.skip('loopback denied; independent CI required')
    key=tmp_path/'ephemeral.key';certificate=tmp_path/'ephemeral.crt'
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes',
                    '-keyout',str(key),'-out',str(certificate),'-days','1','-subj','/CN=localhost'],
                   check=True,capture_output=True,timeout=10)
    fingerprint=hashlib.sha256(ssl.PEM_cert_to_DER_cert(certificate.read_text())).hexdigest()
    token=secrets.token_urlsafe(32)
    state={'transaction':None,'ssid':None,'confirmed':False,'requests':0}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def handle_request(self):
            state['requests']+=1
            if self.headers.get('Authorization')!='Bearer '+token:
                self.send_response(403);self.end_headers();return
            size=int(self.headers.get('Content-Length','0'))
            body=json.loads(self.rfile.read(size)) if size else None
            if self.path=='/v1/network/prepare':
                state.update(transaction=body['transaction'],ssid=body['ssid'])
                reply={'accepted':True,'transaction':state['transaction']}
            elif self.path=='/v1/network/confirm':
                state['confirmed']=body['transaction']==state['transaction']
                reply={'verified':state['confirmed'],'transaction':state['transaction']}
            else:
                reply={'device_id':'device-test','joined':True,
                       'transaction':state['transaction'],'ssid':state['ssid']}
            raw=json.dumps(reply).encode();self.send_response(200)
            self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        do_GET=handle_request
        do_POST=handle_request
    class Server(ThreadingHTTPServer):
        def handle_error(self,*args):pass  # Expected TLS-pin rejection closes before HTTP.
    server=Server(('127.0.0.1',0),Handler)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(certificate,key)
    server.socket=context.wrap_socket(server.socket,server_side=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    store=SecretStore(tmp_path/'private');store.save(Enrollment('device-test',fingerprint,token))
    endpoint=SimpleNamespace(address='127.0.0.1',port=server.server_port,source_ip='127.0.0.1')
    try:yield state,store,endpoint,token
    finally:server.shutdown();server.server_close();thread.join(2)


def manager_for(store,endpoint):
    class Discovery:
        def candidates(self,*args):return [endpoint]
    class NoAdapter:
        def __getattr__(self,name):raise AssertionError('reachable LAN must not touch adapters')
    return NetworkManager(StimulusBus(),Discovery(),TLSProtocol(store),NoAdapter())


def test_real_tls_complete_prepare_rediscover_authenticate_confirm(device,capsys,caplog):
    state,store,endpoint,token=device
    manager=manager_for(store,endpoint)
    credentials=NetworkCredentials('fixture-network',secrets.token_urlsafe(20))
    result=manager.provision(credentials,Authorization('device-test',manager.clock()+20))
    assert result['verified'] and state['confirmed']
    assert state['requests']==5
    assert credentials.password not in str(result)+capsys.readouterr().out+caplog.text
    assert token not in str(result)+caplog.text


def test_real_tls_wrong_certificate_sends_no_authorization(device):
    state,store,endpoint,token=device
    store.save(Enrollment('device-test','0'*64,token))
    manager=manager_for(store,endpoint)
    with pytest.raises(ProvisioningError):
        manager.provision(NetworkCredentials('fixture-network',secrets.token_urlsafe(20)),
                          Authorization('device-test',manager.clock()+20))
    assert state['requests']==0 and not manager.status()['verified']
