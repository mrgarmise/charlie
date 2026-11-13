"""Real HTTP process tests; no device imports or private camera fixtures."""
import base64
from html.parser import HTMLParser
import http.client
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import urlencode
import pytest
from memory.evidence import EvidenceJournal
from memory.human_interaction import HumanInteractionGateway
from memory.learning_projects import LearningExecutive
from test_human_interaction import fixture_record, ask

TOKEN='synthetic-test-secret-not-production-12345'


class Inputs(HTMLParser):
    def __init__(self):super().__init__();self.values={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='input':self.values[a['name']]=a['value']


@pytest.fixture
def server(tmp_path):
    journal=tmp_path/'evidence.sqlite';j=EvidenceJournal(journal);g=HumanInteractionGateway(j)
    q=ask(LearningExecutive(j,None),g,fixture_record(j))['question_id'];j.close()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    process=subprocess.Popen([sys.executable,'-m','ui.human_questions','--journal',str(journal),
        '--operator','fixture-human','--port',str(port)],env=dict(os.environ,CHARLIE_QUESTIONS_TOKEN=TOKEN),
        stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    for _ in range(100):
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=.1):break
        except OSError:time.sleep(.05)
    else:
        process.terminate();pytest.fail('service did not start')
    yield port,journal,q
    process.terminate();process.communicate(timeout=5)


def request(port,path='/',method='GET',body=None,headers=None,auth=True):
    h={}
    if auth:h['Authorization']='Basic '+base64.b64encode(('operator:'+TOKEN).encode()).decode()
    h.update(headers or {})
    c=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
    c.request(method,path,body,h);r=c.getresponse();data=r.read();status=r.status;rh=dict(r.getheaders());c.close()
    return status,data,rh


def form(port):
    status,body,_=request(port);assert status==200
    p=Inputs();p.feed(body.decode());return dict(p.values,value='cat',explanation='<script>alert(1)</script>')


def post(port,data,headers=None):
    return request(port,'/answer','POST',urlencode(data),dict({'Content-Type':'application/x-www-form-urlencoded'},**(headers or {})))


def test_delayed_form_answer_escaping_and_replay(server):
    port,path,q=server;data=form(port)
    status,body,headers=post(port,data);assert status==200
    assert b'&lt;script&gt;' in body and b'<script>' not in body
    assert headers['Cache-Control']=='no-store' and "frame-ancestors 'none'" in headers['Content-Security-Policy']
    assert post(port,data)[0]==200
    data['value']='dog';assert post(port,data)[0]==400
    j=EvidenceJournal(path);g=HumanInteractionGateway(j)
    assert len(g.results('pet_observe'))==1 and g.questions()[q]['status']=='answered';j.close()


@pytest.mark.parametrize('path',['/../evidence.sqlite','/camera','/api/submit','/answer?x=1'])
def test_no_file_or_submission_routes(server,path):
    assert request(server[0],path)[0]==404


def test_unauthorized_and_cross_site(server):
    port,_,_=server
    assert request(port,auth=False)[0]==401
    assert request(port,headers={'Host':'evil.example'})[0]==403
    data=form(port)
    assert post(port,data,{'Origin':'https://evil.example'})[0]==403
    assert post(port,data,{'Sec-Fetch-Site':'cross-site'})[0]==403
    data['csrf']='forged';assert post(port,data)[0]==403


def test_payload_limits_and_forged_sources(server):
    port,_,_=server;data=form(port)
    data['sources']='invented';assert post(port,data)[0]==400
    del data['sources'];data['question_id']='forged';assert post(port,data)[0]==400
    data=form(port);data['explanation']='x'*2049;assert post(port,data)[0]==400
    assert request(port,'/answer','POST','x'*16385,{'Content-Type':'application/x-www-form-urlencoded'})[0]==413
    assert request(port,'/answer','POST','{}',{'Content-Type':'application/json'})[0]==415
