"""Real loopback protocol/cancellation tests, independent of the provider fake."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
import multiprocessing
import pytest
from learning.consultation import OllamaConfig,OllamaProvider


@pytest.fixture
def server():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):self.reply(dict(version='fixture-1') if self.path=='/api/version' else dict(models=[dict(name='qwen3:1.7b',digest='test-model-digest')]))
        def do_POST(self):
            payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            self.server.received.append((self.path,payload))
            if self.path=='/api/show':return self.reply(dict(details=dict(quantization_level='fixture-Q4')))
            if self.server.mode=='slow':time.sleep(2)
            if self.server.mode=='bad':return self.reply('not json',raw=True)
            self.reply(dict(model='qwen3:1.7b',done=True,message=dict(content='Ambiguous; observe again.'),eval_count=9))
        def reply(self,value,raw=False):
            body=value.encode() if raw else json.dumps(value).encode()
            self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers()
            try:self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):pass
    try:s=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    except PermissionError:pytest.skip('native sandbox denies loopback socket creation; independent CI required')
    s.daemon_threads=True;s.received=[];s.mode='normal'
    worker=threading.Thread(target=s.serve_forever,daemon=True);worker.start()
    yield s
    s.shutdown();s.server_close();worker.join(timeout=3)


def provider(server,seconds=5):
    return OllamaProvider(OllamaConfig(endpoint='http://127.0.0.1:'+str(server.server_port),wall_seconds=seconds))


def test_actual_protocol_and_model_identity(server):
    result=provider(server).consult('What can be inferred?')
    assert result['origin']=='local' and result['metrics']['eval_count']==9
    assert result['identity']['model_digest']=='test-model-digest'
    assert result['identity']['details']['quantization_level']=='fixture-Q4'
    path,payload=server.received[-1]
    assert path=='/api/chat' and payload['think'] is False and payload['keep_alive']==0
    assert payload['options']['num_thread']==1


def test_bad_json_returns_recoverable_failure(server):
    server.mode='bad'
    with pytest.raises(ValueError):provider(server).consult('question')


def test_deadline_terminates_child_without_leaking_workers(server):
    server.mode='slow';before={p.pid for p in multiprocessing.active_children()};start=time.monotonic()
    with pytest.raises(TimeoutError):provider(server,.5).consult('question')
    assert time.monotonic()-start<2
    assert {p.pid for p in multiprocessing.active_children()}==before


def test_cancel_while_inference_inflight(server):
    server.mode='slow';start=time.monotonic()
    def check():
        if time.monotonic()-start>.5:raise InterruptedError('cancel')
    with pytest.raises(InterruptedError):provider(server).consult('question',check)
    assert time.monotonic()-start<2


def test_existing_dashboard_discoveries_requires_auth_and_is_read_only(server,tmp_path):
    from ui.dashboard import start_dashboard
    import urllib.request
    import urllib.error
    status=dict(mode='shadow',counts=dict(verified=0,pending=1),questions=[])
    path=tmp_path/'development-status.json';path.write_text(json.dumps(dict(consultations=status)))
    before=path.read_bytes();token='x'*40
    dashboard=start_dashboard(None,token,port=0,learning_state=tmp_path)
    base='http://127.0.0.1:'+str(dashboard.address[1])
    try:
        with pytest.raises(urllib.error.HTTPError) as error:urllib.request.urlopen(base+'/api/discoveries')
        assert error.value.code==401
        req=urllib.request.Request(base+'/api/discoveries',headers={'Authorization':'Bearer '+token})
        with urllib.request.urlopen(req) as response:assert json.load(response)==status
        req=urllib.request.Request(base+'/discoveries',headers={'Authorization':'Bearer '+token})
        with urllib.request.urlopen(req) as response:
            assert 'Questions &amp; Discoveries' in response.read().decode()
        req=urllib.request.Request(base+'/api/discoveries',data=b'{}',headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with pytest.raises(urllib.error.HTTPError) as error:urllib.request.urlopen(req)
        assert error.value.code==404 and path.read_bytes()==before
    finally:dashboard.close()
