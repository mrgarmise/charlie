"""Ephemeral HTTPS simulation only; never opens physical/network-manager devices."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import ssl
import sys
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import pytest
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('enrollment_fixture',root/'tools'/'make_enrollment.py')
enrollment=importlib.util.module_from_spec(spec);spec.loader.exec_module(enrollment)

@pytest.fixture
def simulated_device(tmp_path):
    try:
        probe=socket.socket();probe.close()
    except PermissionError:pytest.skip('loopback denied; independent CI required')
    device='elegoo-010203040506';directory=tmp_path/'private'
    enrollment.generate(directory,device)
    identity=json.loads((directory/'identity-enrollment.json').read_text())
    state={'device_id':device,'transaction':'','ssid':'','joined':True,'committed':False,'requests':[]}
    class Server(ThreadingHTTPServer):
        def handle_error(self,*args):pass # expected wrong-pin peer closure, no raw exception/body logging
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def handle_request(self):
            if self.path in ('/setup','/setup.js'):
                path=root/'web'/('setup.js' if self.path.endswith('.js') else 'setup.html')
                body=path.read_bytes();self.send_response(200);self.send_header('Content-Type','application/javascript' if path.suffix=='.js' else 'text/html')
                self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
            if self.headers.get('Authorization')!='Bearer '+identity['token']:
                self.send_response(401);self.end_headers();return
            state['requests'].append(self.path)
            count=int(self.headers.get('Content-Length','0'));request=json.loads(self.rfile.read(count)) if count else None
            if self.path=='/v1/network/prepare':
                state.update(transaction=request['transaction'],ssid=request['ssid'])
                reply={'accepted':True,'transaction':state['transaction']}
            elif self.path=='/v1/network/confirm':
                state['committed']=request['transaction']==state['transaction']
                reply={'verified':state['committed'],'transaction':state['transaction']}
            else:reply={key:state[key] for key in ['device_id','transaction','ssid','joined']}
            data=json.dumps(reply).encode();self.send_response(200);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        do_GET=handle_request
        do_POST=handle_request
    server=Server(('127.0.0.1',0),Handler)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(directory/'device.crt',directory/'device.key')
    server.socket=context.wrap_socket(server.socket,server_side=True)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:yield state,directory,identity,server
    finally:server.shutdown();server.server_close();worker.join(2)

@pytest.fixture
def peer_modules():
    path=os.environ.get('CHARLIE_PEER_ROOT')
    if not path:pytest.skip('reviewed PR28 checkout required; set CHARLIE_PEER_ROOT')
    sys.path.insert(0,path)
    try:
        from networking.transport import TLSProtocol,SecretStore
        yield TLSProtocol,SecretStore
    finally:sys.path.remove(path)
