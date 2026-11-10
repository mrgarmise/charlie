"""Host-only admission/fault tests. Every native approval here is a fixture."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
from types import SimpleNamespace
import time

import pytest
import learning.consultation_activation as activation
from learning.consultation import ConsultationService, OllamaConfig
from memory.evidence import EvidenceJournal
from test_consultation import source


def approval():
    now = time.time()
    return dict(schema=activation.SCHEMA, operator_consent=True, native_prerequisites_verified=True,
                safe_idle_no_sensing_deadlines=True, exclusive_service=True,
                model=activation.MODEL, boot_id='boot-fixture', code_revision='revision-fixture',
                issued_at=now, expires_at=now+90, model_digest='a'*64,
                qualification_sha256='b'*64, service_invocation_id='c'*32, server_version='fixture')


def validate(doc):
    return activation.validate_approval(doc, now=time.time(), boot_id='boot-fixture', revision='revision-fixture')


@pytest.mark.parametrize('key,value', [
    ('operator_consent', False), ('native_prerequisites_verified', False),
    ('safe_idle_no_sensing_deadlines', False), ('exclusive_service', False),
    ('model', 'qwen3:0.6b'), ('boot_id', 'other'), ('code_revision', 'old'),
    ('expires_at', float('nan')), ('expires_at', time.time()-1),
    ('issued_at', time.time()-500), ('model_digest', 'unknown'),
    ('qualification_sha256', ''), ('service_invocation_id', ''), ('server_version', None)])
def test_missing_native_gates_fail_closed(key, value):
    doc=approval(); doc[key]=value
    with pytest.raises(ValueError): validate(doc)


def test_private_approval_is_bounded_owner_only_not_symlink(tmp_path):
    path=tmp_path/'approval.json'; path.write_text('{}'); path.chmod(0o600)
    assert activation.private_read(path)==b'{}'
    link=tmp_path/'link'; link.symlink_to(path)
    with pytest.raises(OSError): activation.private_read(link)
    path.chmod(0o644)
    with pytest.raises(ValueError): activation.private_read(path)
    path.chmod(0o600);path.write_bytes(b'x'*16385)
    with pytest.raises(ValueError): activation.private_read(path)


def resident(doc):
    return dict(models=[dict(name=activation.MODEL, digest=doc['model_digest'], context_length=2048,
                expires_at=datetime.fromtimestamp(time.time()+90, timezone.utc).isoformat())])


@pytest.mark.parametrize('change', ['cold','other','digest','context','short','permanent','multiple'])
def test_readiness_cannot_load_switch_or_refresh(change):
    doc=approval(); raw=resident(doc)
    if change=='cold':raw['models']=[]
    elif change=='multiple':raw['models']*=2
    else:
        key,value={'other':('name','qwen3:0.6b'), 'digest':('digest','wrong'),
                   'context':('context_length',4096), 'short':('expires_at',datetime.now(timezone.utc).isoformat()),
                   'permanent':('expires_at','9999-01-01T00:00:00+00:00')}[change]
        raw['models'][0][key]=value
    with pytest.raises(ValueError): activation.ready_model(raw,doc,now=time.time())


@pytest.fixture
def native_fakes(tmp_path, monkeypatch):
    """Run real worker/pipe/deadline code; fake only native attestation + HTTP."""
    directory=tmp_path/'private'; directory.mkdir(mode=0o700)
    doc=approval(); calls=tmp_path/'calls.jsonl'; mode={'value':'ok'}
    class Admission:
        def __init__(self,path):
            if mode['value']=='unapproved':raise ValueError('missing native approval')
            self.doc=doc;self.raw=json.dumps(doc).encode();self.identity={'invocation_id':'fixture'}
        def check(self,**kwargs):
            if mode['value']=='revoked':raise ValueError('revoked')
    def http(config,payload,path='/api/chat'):
        with calls.open('a') as f: f.write(json.dumps(dict(path=path,payload=payload,pid=os.getpid()))+'\n')
        if path=='/api/version':return {'version':'fixture'}
        if path=='/api/ps':
            sent=calls.read_text().count('"path": "/api/chat"')
            return {'models':[]} if mode['value']=='cold' or (sent and mode['value']!='unload_failed') else resident(doc)
        if mode['value']=='slow':time.sleep(3)
        if mode['value']=='error':raise OSError('provider outage')
        return dict(model=activation.MODEL,done=True,message=dict(content='A hypothesis, not truth.'))
    monkeypatch.setattr(activation,'Admission',Admission)
    monkeypatch.setattr(activation,'runtime_directory',lambda:directory)
    monkeypatch.setattr(activation,'_http',http)
    # fork propagates deterministic test seams; production always uses spawn.
    context=multiprocessing.get_context('fork')
    monkeypatch.setattr(activation.multiprocessing,'get_context',lambda _:context)
    def rows():return [json.loads(x) for x in calls.read_text().splitlines()] if calls.exists() else []
    return SimpleNamespace(path=directory/'approval.json',mode=mode,rows=rows,
                           marker=directory/'completion-unknown.json')


def test_real_gate_default_remains_shadow(tmp_path, monkeypatch):
    with closing(EvidenceJournal(tmp_path/'j.sqlite3')) as journal:
        service=activation.make_service(journal)
        assert service.shadow and service.provider is None
        q=service.consider(source(journal).id)
        assert q and service.process_one() is None
        assert service.status()['mode']=='shadow'


def test_worker_retains_answer_before_clearing_latch(native_fakes,tmp_path):
    with closing(EvidenceJournal(tmp_path/'j.sqlite3')) as journal:
        service=activation.make_service(journal,native_fakes.path)
        q=service.consider(source(journal).id)
        answer=service.process_one()
        assert answer.data['payload']['trust']=='unverified_hypothesis'
        assert service.questions()[q.id]['status']=='answered'
        assert not native_fakes.marker.exists()
        rows=native_fakes.rows(); chat=[r for r in rows if r['path']=='/api/chat']
        assert len(chat)==1 and chat[0]['pid']!=os.getpid()
        assert chat[0]['payload']['keep_alive']==0 and chat[0]['payload']['think'] is False
        assert [r['path'] for r in rows]==['/api/version','/api/ps','/api/chat','/api/ps']
        assert service.status()['transport']['active_sensing_supported'] is False
        assert service.status()['counts']['verified']==0


@pytest.mark.parametrize('mode', ['cold','unapproved'])
def test_not_ready_never_sends_inference(native_fakes, tmp_path, mode):
    native_fakes.mode['value']=mode
    with closing(EvidenceJournal(tmp_path/'j.sqlite3')) as journal:
        service=activation.make_service(journal,native_fakes.path)
        q=service.consider(source(journal).id);service.process_one()
        assert service.questions()[q.id]['status']=='deferred'
        assert not any(r['path']=='/api/chat' for r in native_fakes.rows())
        assert not native_fakes.marker.exists()


@pytest.mark.parametrize('mode', ['slow','error','unload_failed'])
def test_unknown_completion_latches_across_provider_restart(native_fakes, mode):
    native_fakes.mode['value']=mode
    provider=activation.OperationalProvider(native_fakes.path)
    if mode=='slow':provider.config=OllamaConfig(wall_seconds=.5)
    before={p.pid for p in multiprocessing.active_children()}
    with pytest.raises((ValueError,TimeoutError)):provider.consult('general question')
    assert native_fakes.marker.exists()
    assert {p.pid for p in multiprocessing.active_children()}==before
    native_fakes.mode['value']='ok'
    with pytest.raises(ValueError):activation.OperationalProvider(native_fakes.path).consult('another question')
    assert len([r for r in native_fakes.rows() if r['path']=='/api/chat'])==1


def test_cancel_and_journal_failure_leave_unknown_marker(native_fakes,tmp_path,monkeypatch):
    native_fakes.mode['value']='slow';started=time.monotonic()
    def check():
        if time.monotonic()-started>.2:raise InterruptedError('STOP/resource cancel')
    with pytest.raises(InterruptedError):activation.OperationalProvider(native_fakes.path).consult('general',check)
    assert native_fakes.marker.exists()


def test_one_outstanding_request_across_notebooks(native_fakes):
    first=activation.OperationalProvider(native_fakes.path)
    first.consult('general')  # Deliberately not acknowledged into a journal yet.
    try:
        with pytest.raises(ValueError):activation.OperationalProvider(native_fakes.path).consult('other')
        assert len([r for r in native_fakes.rows() if r['path']=='/api/chat'])==1
    finally:first.close()
    assert native_fakes.marker.exists()


def test_cli_requires_both_optins_and_worker_isolation():
    from main import main, parser
    assert parser().parse_args([]).llm_consultation_approval is None
    with pytest.raises(ValueError,match='requires --llm-consultation'):
        main(['--llm-consultation-approval','/no/such/approval'])
    with pytest.raises(ValueError,match='separate normal Executive worker'):
        main(['--llm-consultation','--llm-consultation-approval','/no/such/approval','--mobile-observe'])


@pytest.fixture
def service_files(tmp_path, monkeypatch):
    """Kernel/service identity fixture; no actual systemd or device access."""
    root=tmp_path/'sys/fs/cgroup'; group=root/'test/service'; group.mkdir(parents=True)
    for name,value in {'memory.max':str(2500*1024**2),'memory.swap.max':'0',
                       'memory.swap.current':'0','cpu.max':'100000 100000'}.items():
        (group/name).write_text(value)
    proc=tmp_path/'proc'; (proc/'321/fd').mkdir(parents=True);(proc/'net').mkdir()
    (proc/'321/fd/3').symlink_to('socket:[999]')
    (proc/'321/stat').write_text('321 (ollama) '+' '.join(['0']*19+['100']))
    (proc/'net/tcp').write_text('header\n0: 0100007F:2CAA 00000000:0000 0A 0 0 0 0 0 999\n')
    props=dict(ActiveState='active',MainPID='321',InvocationID='c'*32,ControlGroup='/test/service',
               PrivateDevices='yes',NoNewPrivileges='yes',ProtectHome='tmpfs',RuntimeMaxUSec='1min 30s',
               TimeoutStopUSec='5s',Restart='no',KillMode='control-group',SendSIGKILL='yes')
    def path(*args):
        original=Path(*args)
        if str(original).startswith('/sys/fs/cgroup'):return tmp_path/str(original).lstrip('/')
        if str(original).startswith('/proc'):return tmp_path/str(original).lstrip('/')
        return original
    monkeypatch.setattr(activation,'Path',path)
    monkeypatch.setattr(activation.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout='\n'.join(f'{k}={v}' for k,v in props.items())))
    return props,group,proc


def test_service_identity_checks_kernel_limits_and_owned_listener(service_files):
    props,group,proc=service_files
    result=activation.service_identity()
    assert result['pid']==321 and result['invocation_id']=='c'*32
    assert result['memory_max']==2500*1024**2
    (group/'cpu.max').write_text('max 100000')
    with pytest.raises(ValueError):activation.service_identity()


@pytest.mark.parametrize('key,value', [('PrivateDevices','no'),('Restart','always'),
    ('RuntimeMaxUSec','infinity'),('RuntimeMaxUSec','3min'),('TimeoutStopUSec','30s'),
    ('KillMode','process'),('SendSIGKILL','no'),('ProtectHome','no'),('ActiveState','inactive')])
def test_unbounded_or_unsandboxed_service_refused(service_files,key,value):
    service_files[0][key]=value
    with pytest.raises(ValueError):activation.service_identity()


@pytest.mark.parametrize('file,value', [('memory.max','max'),('memory.max',str(3*1024**3)),
    ('memory.swap.max','1'),('memory.swap.current','1'),('cpu.max','200000 100000')])
def test_cgroup_pressure_and_missing_hard_limits_refused(service_files,file,value):
    (service_files[1]/file).write_text(value)
    with pytest.raises(ValueError):activation.service_identity()


def test_foreign_or_public_listener_refused(service_files):
    tcp=service_files[2]/'net/tcp'
    tcp.write_text(tcp.read_text().replace('0100007F','00000000'))
    with pytest.raises(ValueError):activation.service_identity()


def test_admission_checks_receipt_revocation_and_restart(tmp_path,monkeypatch):
    doc=approval();doc['boot_id']=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    receipt=tmp_path/'receipt';receipt.write_bytes(b'fixture independent receipt');receipt.chmod(0o600)
    doc.update(qualification_path=str(receipt),qualification_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest())
    path=tmp_path/'approval';path.write_text(json.dumps(doc));path.chmod(0o600)
    identity=dict(invocation_id='c'*32,cutoff_monotonic=time.monotonic()+60)
    monkeypatch.setattr(activation,'git_revision',lambda:'revision-fixture')
    monkeypatch.setattr(activation,'service_identity',lambda:dict(identity))
    monkeypatch.setattr(activation,'consultation_resources',lambda check:check())
    monkeypatch.setattr(activation,'temperature',lambda:50)
    monkeypatch.setattr(activation.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout='throttled=0x0'))
    admission=activation.Admission(path);admission.check(starting=True)
    identity['invocation_id']='d'*32;admission.next_sample=0
    with pytest.raises(ValueError,match='identity'):admission.check()
    identity['invocation_id']='c'*32
    path.write_text('{}')
    with pytest.raises(ValueError,match='revoked'):admission.check()


def test_admission_refuses_hot_missing_thermal_and_throttle(tmp_path,monkeypatch):
    # Exercise the monitoring gate independently from the factory fixture.
    doc=approval();path=tmp_path/'approval';raw=json.dumps(doc).encode();path.write_bytes(raw);path.chmod(0o600)
    admission=object.__new__(activation.Admission)
    admission.path=path;admission.raw=raw;admission.doc=doc
    admission.boot='boot-fixture';admission.revision='revision-fixture';admission.next_sample=0
    monkeypatch.setattr(activation,'consultation_resources',lambda check:check())
    for heat in (None,70,80):
        monkeypatch.setattr(activation,'temperature',lambda:heat)
        with pytest.raises(ValueError,match='temperature'):admission.check()
    monkeypatch.setattr(activation,'temperature',lambda:50)
    monkeypatch.setattr(activation.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout='throttled=0x1'))
    with pytest.raises(ValueError,match='throttling'):admission.check()


def test_journal_failure_never_acknowledges_result(native_fakes,tmp_path,monkeypatch):
    with closing(EvidenceJournal(tmp_path/'j.sqlite3')) as journal:
        service=activation.make_service(journal,native_fakes.path)
        service.consider(source(journal).id)
        append=service._event
        def fail(q,op,**extra):
            if op=='answered':raise OSError('simulated durable write failure')
            return append(q,op,**extra)
        monkeypatch.setattr(service,'_event',fail)
        service.process_one()
        assert native_fakes.marker.exists()
        assert not service.status()['counts']['answered']


def test_source_age_not_just_queue_age_blocks_stale_evidence(tmp_path):
    from learning.consultation import FakeProvider
    with closing(EvidenceJournal(tmp_path/'j.sqlite3')) as journal:
        row=source(journal);now=[datetime.fromisoformat(row.committed_at).timestamp()+299]
        provider=FakeProvider();service=ConsultationService(journal,provider,shadow=False,clock=lambda:now[0])
        q=service.consider(row.id);assert q
        now[0]+=2;service.process_one()
        assert service.questions()[q.id]['status']=='deferred' and not provider.calls


@pytest.mark.parametrize('extras', [[], ['--human-questions'], ['--model-learning'],
                                    ['--human-questions','--model-learning']])
def test_real_optin_forwarded_only_to_existing_normal_worker(monkeypatch,tmp_path,extras):
    from test_objective_a_normal_runtime import test_monitoring_keeps_normal_vision_attention_and_single_worker
    test_monitoring_keeps_normal_vision_attention_and_single_worker(monkeypatch,tmp_path,
        ['--llm-consultation','--llm-consultation-approval',str(tmp_path/'unissued-native-approval'),*extras])


def test_normal_worker_constructs_same_journal_real_service_without_native_calls(tmp_path,monkeypatch):
    from learning.lifecycle import run, DevelopmentLifecycle
    from learning.resources import DevelopmentResources, ResourceGuard
    monkeypatch.setattr(DevelopmentResources,'apply',lambda self:None)
    monkeypatch.setattr('os.nice',lambda n:None)
    policy=DevelopmentResources()
    guard=ResourceGuard(policy,thermal_reader=lambda:40,memory_reader=lambda:(1024,0))
    seen=[]
    def factory(*args,**kwargs):
        life=DevelopmentLifecycle(*args,**kwargs,resource_guard=guard)
        def turn():
            assert life.consultation.journal is life.journal
            assert isinstance(life.consultation.provider,activation.OperationalProvider)
            assert life.consultation.provider.child is None
            seen.append(life.consultation.status())
            return True
        life.turn=turn
        return life
    result=run(tmp_path/'state',[],resources=policy,lifecycle_factory=factory,turns=1,
               llm_consultation=True,llm_consultation_approval=tmp_path/'not-approved')
    assert result['termination_reason']=='attempt limit reached'
    assert seen[0]['mode']=='qualified-safe-idle'
    assert seen[0]['transport']['state']=='awaiting-native-safe-idle-admission'


@pytest.mark.parametrize('ready', [False,True])
def test_operational_protocol_over_real_loopback(native_fakes,monkeypatch,ready):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from learning.consultation import _http
    state={'loaded':ready,'requests':[]}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,value):
            raw=json.dumps(value).encode();self.send_response(200)
            self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            if self.path=='/api/version':return self.reply({'version':'fixture'})
            assert self.path=='/api/ps'
            self.reply(resident(approval()) if state['loaded'] else {'models':[]})
        def do_POST(self):
            assert self.path=='/api/chat'
            value=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            state['requests'].append(value);state['loaded']=False
            self.reply(dict(model=activation.MODEL,done=True,message=dict(content='Unverified loopback fixture.')))
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    monkeypatch.setattr(activation,'_http',_http)
    provider=activation.OperationalProvider(native_fakes.path)
    provider.config=OllamaConfig(endpoint='http://127.0.0.1:'+str(server.server_port))
    try:
        if ready:
            answer=provider.consult('General evidence question')
            assert answer['answer']=='Unverified loopback fixture.'
            assert answer['identity']['model_digest']=='a'*64
            assert native_fakes.marker.exists()  # awaiting durable result receipt
            provider.retained()
            assert not native_fakes.marker.exists()
            assert len(state['requests'])==1 and state['requests'][0]['keep_alive']==0
        else:
            with pytest.raises(ValueError):provider.consult('General evidence question')
            assert state['requests']==[] and not native_fakes.marker.exists()
    finally:
        provider.close();server.shutdown();server.server_close();thread.join(timeout=2)
