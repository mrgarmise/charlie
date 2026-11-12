"""Real issuer state machine, fake kernel/serial/service boundaries. Never native consent."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
from learning.native_meditation.engine import Scheduler
from learning.native_meditation.daemon import Broker


class Driver:
    def __init__(self, clock):
        self.clock=clock;self.held=False;self.model=False;self.visible=False;self.alive=True
        self.pending=False;self.emergency_count=0;self.trace=[];self.invalid={};self.display=True;self.dirty=False
        self.p=dict(enabled=True,model='qwen3:1.7b',model_digest='8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7',
                    max_seconds=90,daily_limit=4,cooldown=3600,client_uid=os.getuid())
    def policy(self):return dict(self.p)
    def acquire(self,end):
        if self.held:raise BlockingIOError()
        self.held=True;self.trace.append('lock');return min(end,getattr(self,'duty',end))
    def watch_client(self,pid):self.pid=pid
    def client_alive(self):return self.alive
    def inspect(self,end):
        from learning.native_meditation.linux import FIELDS
        return dict(dict.fromkeys(FIELDS,False),**dict(independent_inventory_complete=True,temperature_c=40,available_gib=4,load=0,reserved_until=end,**self.invalid))
    def notice(self,slot,seq,phase):
        self.trace.append(phase)
        if not self.display:raise PermissionError('display unavailable')
        self.visible=phase!='CLEAR';self.seq=seq;self.slot=slot
        return dict(slot=slot,sequence=seq,phase=phase,visible=self.visible,remaining_ms=2000 if self.visible else 0)
    def notice_valid(self,slot,seq):return self.visible and not self.pending and self.slot==slot and self.seq==seq
    def prepare(self,slot,model,digest):
        assert self.held and self.visible
        self.trace.append('prewarm');self.model=True
        return dict(path='/fixture/root-approval.json',digest='a'*64)
    def latch(self,slot):self.dirty=True;self.trace.append('unknown-latched')
    def unloaded(self,digest):
        if self.model:raise PermissionError('still loaded')
        self.trace.append('retained')
    def quiesce(self,a):
        self.trace.append('quiesce')
        if self.invalid.get('cutoff_failed'):raise PermissionError('unknown cgroup')
        self.model=False
    def expire_notice(self,a):self.visible=False;self.trace.append('TTL')
    def complete(self,a):self.dirty=False
    def release(self):assert not self.model;self.held=False;self.trace.append('unlock')
    def emergency(self):self.pending=True;self.model=False;self.emergency_count+=1


def setup(tmp_path):
    clock=[1800000000.];d=Driver(clock)
    e=Scheduler(d,tmp_path/'root.sqlite3',clock=lambda:clock[0],monotonic=lambda:clock[0])
    return clock,d,e


def test_sequence_durable_budget_one_query_cleanup(tmp_path):
    clock,d,e=setup(tmp_path)
    slot=e.reserve('Executive-commission',90,123)
    assert d.trace==['lock','PREPARING']
    e.budget('Executive-commission',4,3600)
    path=e.prepare(d.p['model'],d.p['model_digest'],slot['ends_at']);assert path
    e.mark_submission('a'*64)
    with pytest.raises(PermissionError):e.mark_submission('a'*64)
    d.model=False;e.retained('a'*64);e.finish()
    assert not d.held and not d.visible and not e.recovery_blocked
    assert d.trace.index('quiesce')<d.trace.index('CLEAR')<d.trace.index('unlock')
    clock[0]+=3601;e.reserve('Executive-commission',90,123)
    with pytest.raises(PermissionError):e.budget('Executive-commission',4,3600)
    e.finish()


@pytest.mark.parametrize('veto', ['sensing','telemetry_deadline','watchdog_deadline','physical_task','gameplay','outstanding_lease','primary_pending','revoked','swap_used','throttled'])
def test_real_engine_refuses_active_or_unknown_owner(tmp_path,veto):
    clock,d,e=setup(tmp_path);d.invalid[veto]=None
    with pytest.raises(InterruptedError):e.reserve('commission',90,123)
    assert 'prewarm' not in d.trace and not d.held


@pytest.mark.parametrize('mode',['display','policy','death','deadline','numeric'])
def test_revocation_cutoff_and_client_death(tmp_path,mode):
    clock,d,e=setup(tmp_path);e.reserve('commission',90,123)
    if mode=='display':d.display=False;d.visible=False
    if mode=='policy':d.p['enabled']=False
    if mode=='death':d.alive=False
    if mode=='deadline':clock[0]+=86
    if mode=='numeric':d.invalid['load']=float('nan')
    e.tick();assert e.active is None and not d.held and not d.visible


def test_display_missing_and_shortened_duty_never_prewarm(tmp_path):
    clock,d,e=setup(tmp_path);d.display=False
    with pytest.raises(PermissionError):e.reserve('commission',90,123)
    assert 'prewarm' not in d.trace and 'TTL' in d.trace and not d.held
    d.display=True;d.duty=clock[0]+20
    with pytest.raises(PermissionError):e.reserve('next',90,123)
    assert not d.held


def test_unknown_completion_survives_restart_and_no_retry(tmp_path):
    clock,d,e=setup(tmp_path);s=e.reserve('commission',90,123);e.budget('commission',4,3600)
    e.prepare(d.p['model'],d.p['model_digest'],s['ends_at']);e.mark_submission('a'*64)
    e.finish('network timeout');assert e.recovery_blocked and d.dirty and not d.held
    other=Scheduler(d,tmp_path/'root.sqlite3',clock=lambda:clock[0],monotonic=lambda:clock[0])
    with pytest.raises(PermissionError):other.reserve('different question',90,123)


def test_failed_cgroup_cutoff_never_releases_runtime(tmp_path):
    clock,d,e=setup(tmp_path);e.reserve('commission',90,123);d.invalid['cutoff_failed']=True
    with pytest.raises(PermissionError):e.finish()
    assert d.held and e.recovery_blocked


def test_broker_rejects_wrong_uid_and_fake_approval(tmp_path):
    clock,d,e=setup(tmp_path);b=Broker(e)
    with pytest.raises(PermissionError):b.handle(os.getuid()+1,123,dict(op='reserve',commission='x',seconds=90))
    slot=b.handle(os.getuid(),123,dict(op='reserve',commission='x',seconds=90))
    with pytest.raises(PermissionError):b.handle(os.getuid(),123,dict(op='validate',slot=slot['id'],digest='forged'))
    with pytest.raises(ValueError):b.handle(os.getuid(),123,dict(op='phase',slot=slot['id'],phase='CLEAR'))
    b.handle(os.getuid(),123,dict(op='primary'))
    assert not d.held and d.emergency_count==1


def test_policy_cannot_increase_budget_or_extend_slot(tmp_path):
    clock,d,e=setup(tmp_path);s=e.reserve('c',90,123)
    with pytest.raises(PermissionError):e.budget('c',99,0)
    e.budget('c',4,3600)
    with pytest.raises(PermissionError):e.prepare(d.p['model'],d.p['model_digest'],s['ends_at']+1)
    e.finish()


def test_root_owned_policy_and_standing_approval_cannot_be_forged(tmp_path):
    from learning.native_meditation.security import root_read,standing_bytes
    fake=tmp_path/'approval.json';fake.write_text('{}')
    with pytest.raises(PermissionError):root_read(fake)
    with pytest.raises(PermissionError):standing_bytes(fake)


def test_client_does_not_implement_issuer_flags():
    from learning.native_meditation.client import NativeBackend
    calls=[]
    b=NativeBackend();b.call=lambda op,**kwargs:calls.append((op,kwargs)) or dict(id='a'*32,ends_at=1000)
    with b.exclusive('commission',90) as lease:lease.inspect()
    assert [op for op,_ in calls]==['reserve','inspect','finish']
    assert not any('safe_idle' in str(p) or 'operator_consent' in str(p) for _,p in calls)


def test_kernel_peer_identity_rejects_same_user_forged_root():
    import socket
    from learning.native_meditation.security import peer
    a=b=None
    try:
        a,b=socket.socketpair();credentials=peer(a)
        assert credentials[1]==os.getuid()
        if os.getuid()!=0:assert credentials[1]!=0
    except PermissionError:pytest.skip('sandbox denies Unix peer credentials; independently covered in CI')
    finally:
        if a:a.close()
        if b:b.close()


def test_real_display_bridge_only_uses_existing_owner(board,screen):
    from test_meditation_notice import connected,SLOT
    from learning.native_meditation.display_bridge import DisplayBridge
    host,a,h=connected(board,screen);bridge=DisplayBridge(host)
    with pytest.raises(PermissionError):bridge.dispatch(1001,dict(op='notice',slot=SLOT,sequence=1,phase='PREPARING'))
    assert bridge.dispatch(0,dict(op='notice',slot=SLOT,sequence=1,phase='PREPARING'))['visible']
    assert bridge.dispatch(0,dict(op='status'))['visible']
    host.stop();assert bridge.cancel.is_set()
    with pytest.raises(InterruptedError):bridge.dispatch(0,dict(op='notice',slot=SLOT,sequence=2,phase='THINKING'))
    assert not board.pwms


from test_meditation_notice import board,screen


def test_actual_executive_encloses_thinking_and_no_question(tmp_path):
    from learning.lifecycle import DevelopmentLifecycle
    from learning.native_meditation.coordinator import NativeMeditationCoordinator
    from test_normal_learning_lifecycle import experience
    from learning.question_selection import QuestionQueue
    from learning.meditation_consultation import MeditationConsultations
    from memory.evidence import EvidenceJournal
    trace=[]
    class Backend:
        @contextmanager
        def exclusive(self,c,s):
            trace.append('reserve-ack')
            lease=SimpleNamespace(id='a'*32,ends_at=1800000090.,phase=lambda p:trace.append(p),
                                  inspect=lambda:trace.append('thinking-check'),finished=False)
            try:yield lease
            finally:trace.append('clear-quiesce');lease.finished=True
    j=EvidenceJournal(tmp_path/'questions.sqlite3')
    consultation=MeditationConsultations(QuestionQueue(j),[],enabled=True)
    life=DevelopmentLifecycle(tmp_path/'state',[experience(tmp_path)])
    life.meditation_consultations=NativeMeditationCoordinator(consultation,Backend())
    try:
        life.turn()
        assert trace[0:2]==['reserve-ack','MEDITATING'] and trace[-1]=='clear-quiesce'
        assert 'thinking-check' in trace
        assert life.journal.category_records('observation','normal_meditation_result')
        phases=[r.data['payload']['phase'] for r in j.category_records('event','native_meditation')]
        assert phases==['requesting','reserved/preparing','meditating','available']
    finally:life.close();j.close()


@pytest.mark.parametrize('args',[['--hardware'],['--mobile-observe'],['--llm-consultation-approval','/fake']])
def test_native_cli_cannot_run_in_primary_or_manual_approval_paths(args):
    from main import main,parser
    assert parser().parse_args([]).native_meditation is False
    with pytest.raises(ValueError,match='native meditation'):main(['--native-meditation',*args])


def test_inherited_kernel_flock_survives_issuer_exit(tmp_path):
    import subprocess,sys,fcntl,signal,time
    lock=tmp_path/'runtime.lock';lock.touch()
    code="""import subprocess,sys
from learning.native_meditation.runner import inherit_lock
fd=inherit_lock(sys.argv[1])
p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(3)'],pass_fds=(fd,),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
print(p.pid,flush=True)
"""
    parent=subprocess.run([sys.executable,'-c',code,str(lock)],capture_output=True,text=True,timeout=2)
    assert parent.returncode==0,parent.stderr
    child=int(parent.stdout.strip())
    try:
        with lock.open('a') as fd:
            with pytest.raises(BlockingIOError):fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    finally:os.kill(child,signal.SIGTERM)


def test_emergency_does_not_wait_for_engine_prewarm_lock(tmp_path):
    import threading,time
    clock,d,e=setup(tmp_path);b=Broker(e);s=e.reserve('commission',90,123);e.budget('commission',4,3600)
    started=threading.Event();killed=threading.Event();errors=[]
    def prepare(*args):
        d.model=True;started.set()
        if not killed.wait(2):raise AssertionError('emergency blocked behind prewarm lock')
        raise InterruptedError('model process killed')
    def emergency():d.pending=True;d.model=False;killed.set()
    d.prepare=prepare;d.emergency=emergency
    def worker():
        try:b.handle(os.getuid(),123,dict(op='prepare',slot=s['id'],model=d.p['model'],digest=d.p['model_digest'],ends_at=s['ends_at']))
        except InterruptedError:errors.append('cancelled')
    t=threading.Thread(target=worker);t.start();assert started.wait(1)
    start=time.monotonic();b.handle(os.getuid(),123,dict(op='cancel'));t.join(1)
    assert time.monotonic()-start<1 and errors==['cancelled'] and not d.held


def test_daily_budget_is_durable_and_not_reset_by_new_client(tmp_path):
    clock,d,e=setup(tmp_path)
    for i in range(4):
        e.reserve(str(i),90,123);e.budget(str(i),4,3600);e.finish();clock[0]+=3601
    e.reserve('fifth',90,456)
    with pytest.raises(PermissionError):e.budget('fifth',4,3600)
    e.finish()


def test_broker_coordinator_question_retention_and_human_deferral(tmp_path):
    from learning.native_meditation.client import NativeBackend
    from learning.native_meditation.coordinator import NativeMeditationCoordinator
    from learning.meditation_consultation import MeditationConsultations
    from learning.question_selection import QuestionQueue
    from memory.evidence import EvidenceJournal
    from test_question_selection import source
    import time
    path=source(tmp_path);clock,d,e=setup(tmp_path);b=Broker(e)
    backend=NativeBackend();backend.call=lambda op,**kw:b.handle(os.getuid(),os.getpid(),dict(op=op,**kw))
    j=EvidenceJournal(tmp_path/'answers.sqlite3')
    class Provider:
        def __init__(self,path):self.state='checking';self.model='qwen3:1.7b'
        def status(self):return dict(state=self.state)
        def consult(self,prompt,check):
            assert d.visible and d.held and d.model
            backend.call('submit',slot=e.active['id'],digest='a'*64)
            self.state='request-in-flight';check();d.trace.append('query')
            d.model=False
            return dict(answer='Unverified offline hypothesis',identity={'model_digest':d.p['model_digest'],'approval_digest':'a'*64})
        def retained(self):
            assert any(r.data['payload'].get('state')=='answer-durable' for r in j.records())
            backend.call('retained',slot=e.active['id'],digest='a'*64);self.state='completed-unload-confirmed'
        def close(self):pass
    c=MeditationConsultations(QuestionQueue(j,lambda:clock[0]),[path],enabled=True,
        provider_factory=Provider,clock=lambda:clock[0]);native=NativeMeditationCoordinator(c,backend);native.refresh()
    try:
        with native.window('Executive commission',lambda:None,client_deadline=time.monotonic()+60) as check:
            assert d.visible
            interaction=native.interaction('human-request')
            assert interaction['state']=='delayed'
            assert native.interaction('human-request') is interaction
            d.trace.append('meditation');check()
        assert interaction['state']=='ready' and e.active is None and not d.held and not d.model and not d.visible
        assert d.trace.index('PREPARING')<d.trace.index('meditation')<d.trace.index('prewarm')<d.trace.index('query')<d.trace.index('retained')<d.trace.index('CLEAR')<d.trace.index('unlock')
        assert any(s['state']=='awaiting-evaluation' for s in c.queue.states().values())
    finally:j.close()


def test_native_no_slot_yields_checkpoint_and_never_runs_thinking(tmp_path):
    from learning.native_meditation.coordinator import NativeMeditationCoordinator
    from learning.lifecycle import MeditationYield
    from learning.meditation_consultation import MeditationConsultations
    from learning.question_selection import QuestionQueue
    from memory.evidence import EvidenceJournal
    class Refused:
        @contextmanager
        def exclusive(self,*args):raise PermissionError('display occupied');yield
    j=EvidenceJournal(tmp_path/'answers.sqlite3')
    n=NativeMeditationCoordinator(MeditationConsultations(QuestionQueue(j),[],enabled=True),Refused())
    try:
        with pytest.raises(MeditationYield):
            with n.window('commission',lambda:None,client_deadline=0):raise AssertionError('thinking before acknowledgement')
    finally:j.close()


def test_standing_authority_respects_negotiated_end_after_ipc_delay():
    from learning.standing_consultation_policy import StandingSlotAuthority,StandingPolicy
    clock=[1000.]
    class Lease:
        id='slot';ends_at=1080.
        def inspect(self):
            from learning.native_meditation.linux import FIELDS
            return dict(dict.fromkeys(FIELDS,False),independent_inventory_complete=True,temperature_c=40,available_gib=4,load=0,reserved_until=1080.)
        def reserve_budget(self,*a):pass
        def prepare(self,**kw):assert kw['ends_at']==1080.;return 'fixture'
        def finish(self,**kw):pass
    class Backend:
        @contextmanager
        def exclusive(self,*args):clock[0]+=.1;yield Lease()
    a=StandingSlotAuthority(StandingPolicy(enabled=True),Backend(),clock=lambda:clock[0])
    with a.reserve(commission_id='c',seconds=90) as slot:assert slot.ends_at==1080.


def test_display_refresh_and_guard_continue_while_prewarm_holds_dispatch_lock(tmp_path):
    import threading
    clock,d,e=setup(tmp_path);b=Broker(e);s=e.reserve('c',90,123);e.budget('c',4,3600)
    entered=threading.Event();release=threading.Event();stop=threading.Event();done=[]
    def prepare(*args):
        entered.set();assert release.wait(2)
        return dict(path='fixture',digest='a'*64)
    d.prepare=prepare
    def worker():done.append(b.handle(os.getuid(),123,dict(op='prepare',slot=s['id'],model=d.p['model'],digest=d.p['model_digest'],ends_at=s['ends_at'])))
    t=threading.Thread(target=worker);t.start();assert entered.wait(1)
    sequence=e.active['sequence'];clock[0]+=1
    monitor=threading.Thread(target=b.monitor,args=(stop,));monitor.start()
    try:
        import time
        end=time.monotonic()+1
        while e.active['sequence']==sequence and time.monotonic()<end:time.sleep(.01)
        assert e.active['sequence']>sequence
    finally:release.set();t.join(2);stop.set();monitor.join(2)
    assert done==['fixture'];e.finish()


def test_private_model_proxy_refuses_admin_duplicate_and_wrong_envelope(tmp_path):
    from learning.consultation import OllamaConfig,request_payload
    clock,d,e=setup(tmp_path);b=Broker(e);s=e.reserve('c',90,123);e.budget('c',4,3600)
    e.prepare(d.p['model'],d.p['model_digest'],s['ends_at']);e.mark_submission('a'*64)
    d.question=lambda prompt:'original-canonical-question'
    d.http=lambda payload,path,timeout:dict(done=True)
    def call(path,payload):return b.handle(os.getuid(),123,dict(op='http',slot=s['id'],digest='a'*64,path=path,payload=payload))
    with pytest.raises(PermissionError):call('/api/pull',{'model':'other'})
    with pytest.raises(PermissionError):call('/api/chat',dict(messages=[{},dict(content='q')]))
    assert call('/api/chat',request_payload(OllamaConfig(),'q'))==dict(done=True)
    with pytest.raises(PermissionError):call('/api/chat',request_payload(OllamaConfig(),'q'))
    e.finish()


def test_owner_writable_file_cannot_claim_standing_issuer(tmp_path):
    from learning.consultation_activation import Admission
    path=tmp_path/'forged';path.write_text(json.dumps(dict(issuer='root-meditation-v1')));path.chmod(0o600)
    with pytest.raises(PermissionError,match='owner-writable'):Admission(path)


def test_mixed_cycles_keep_query_rate_and_exclusion(tmp_path):
    clock,d,e=setup(tmp_path);queries=0
    for i in range(300):
        clock[0]+=3601;d.invalid={} if i%3 else {'sensing':True}
        try:e.reserve('commission-'+str(i),90,123)
        except InterruptedError:
            assert not d.held;continue
        try:e.budget('commission-'+str(i),4,3600)
        except PermissionError:e.finish();continue
        s=e.active;e.prepare(d.p['model'],d.p['model_digest'],s['ends_at'])
        assert d.held and d.visible
        e.mark_submission('a'*64);queries+=1;d.model=False;e.retained('a'*64);e.finish()
        assert not d.held and not d.model and not d.visible
    rows=list(e.db.execute("SELECT at FROM events WHERE op='budget' ORDER BY at"))
    assert queries>4 and all(sum(0<=at[0]-other[0]<86400 for other in rows)<=4 for at in rows)


def test_root_launcher_checks_actual_kernel_bound_before_model_exec(tmp_path,monkeypatch):
    import learning.native_meditation.runner as runner
    import hashlib
    actual_os=os;trace=[]
    p=dict(enabled=True,ollama_binary='/reviewed/ollama',ollama_binary_sha256=hashlib.sha256(b'binary').hexdigest(),
           state_dir='/protected',runtime_lock='/runtime.lock',model_uid=1102,model_gid=1102)
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    lease=dict(boot_id=boot,mono_end=180.,runtime_seconds=60)
    monkeypatch.setattr(runner,'root_read',lambda path,limit=0:json.dumps(lease if str(path).endswith('service-lease.json') else p).encode() if str(path)!='/reviewed/ollama' else b'binary')
    monkeypatch.setattr(runner,'time',SimpleNamespace(monotonic=lambda:110.))
    monkeypatch.setattr(runner,'os',SimpleNamespace(geteuid=lambda:0,setgroups=lambda x:trace.append('groups'),
        setgid=lambda x:trace.append('gid'),setuid=lambda x:trace.append('uid'),execv=lambda *a:trace.append('exec')))
    def run(args,**kw):
        trace.append('kernel-bound')
        assert args[:3]==['systemctl','show','charlie-meditation-consultant.service']
        return SimpleNamespace(stdout='ActiveEnterTimestampMonotonic=100000000\nRuntimeMaxUSec=1min\nTimeoutStopUSec=5s\n')
    monkeypatch.setattr(runner,'subprocess',SimpleNamespace(run=run))
    runner.main();assert trace==['kernel-bound','groups','gid','uid','exec']
    trace.clear();lease['mono_end']=160.
    with pytest.raises(PermissionError):runner.main()
    assert 'exec' not in trace and 'uid' not in trace


def test_scm_rights_preserves_exact_flock_until_guardian_releases(tmp_path):
    import socket,array,fcntl
    from learning.native_meditation.runner import inherit_lock
    path=tmp_path/'runtime.lock';path.touch();fd=inherit_lock(path);received=None;a=b=None
    try:
        try:a,b=socket.socketpair()
        except PermissionError:pytest.skip('sandbox denies Unix FD transfer; independent CI covers it')
        a.sendmsg([b'lock'],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[fd]))])
        _,ancillary,_,_=b.recvmsg(16,socket.CMSG_SPACE(array.array('i').itemsize))
        values=array.array('i');values.frombytes(ancillary[0][2]);received=values[0]
        os.close(fd);fd=None
        with path.open('a') as other:
            with pytest.raises(BlockingIOError):fcntl.flock(other,fcntl.LOCK_EX|fcntl.LOCK_NB)
            os.close(received);received=None
            fcntl.flock(other,fcntl.LOCK_EX|fcntl.LOCK_NB)
    finally:
        if fd is not None:os.close(fd)
        if received is not None:os.close(received)
        if a:a.close()
        if b:b.close()


def test_restart_resumes_durable_human_requests_only_after_independent_cleanup(tmp_path):
    from memory.evidence import EvidenceJournal
    from learning.question_selection import QuestionQueue
    from learning.meditation_consultation import MeditationConsultations
    from learning.native_meditation.coordinator import NativeMeditationCoordinator
    j=EvidenceJournal(tmp_path/'answers.sqlite3')
    try:
        c=MeditationConsultations(QuestionQueue(j),[],enabled=True)
        backend=SimpleNamespace(status=lambda:dict(available=False))
        first=NativeMeditationCoordinator(c,backend);first.event('interaction-delayed',interaction_id='human-one')
        blocked=NativeMeditationCoordinator(c,backend);assert blocked.interactions[0]['id']=='human-one'
        backend.status=lambda:dict(available=True)
        resumed=NativeMeditationCoordinator(c,backend);assert not resumed.interactions
        row=j.category_records('event','native_meditation')[-1].data['payload']
        assert row['recovered'] is True and row['resumed']==['human-one']
    finally:j.close()


def test_notice_sequences_remain_monotonic_across_slots_and_issuer_restart(tmp_path):
    clock,d,e=setup(tmp_path)
    e.reserve('one',90,123);e.finish();previous=d.seq
    e.reserve('two',90,123);assert d.seq>previous;e.finish();previous=d.seq
    reloaded=Scheduler(d,tmp_path/'root.sqlite3',clock=lambda:clock[0],monotonic=lambda:clock[0])
    reloaded.reserve('three',90,123);assert d.seq>previous;reloaded.finish()


def test_client_identity_cannot_retain_supplementary_authority(monkeypatch):
    import learning.native_meditation.linux as linux
    text=['Uid:\t1101 1101 1101 1101\nGid:\t1101 1101 1101 1101\nGroups:\t1101 0\nCapEff:\t0\nCapPrm:\t0\nNoNewPrivs:\t1\n']
    calls=[];d=linux.LinuxDriver.__new__(linux.LinuxDriver);d.p=dict(client_uid=1101,client_gid=1101)
    monkeypatch.setattr(linux,'Path',lambda *a:SimpleNamespace(read_text=lambda:text[0]))
    monkeypatch.setattr(linux,'os',SimpleNamespace(pidfd_open=lambda pid:calls.append(pid) or 99))
    with pytest.raises(PermissionError):d.watch_client(123)
    assert not calls
    text[0]=text[0].replace('1101 0','1101')
    d.watch_client(123);assert calls==[123]


def test_original_source_must_be_outside_executive_write_domain(tmp_path):
    from learning.native_meditation.security import protected_source
    original=tmp_path/'fabricated.sqlite3';original.write_bytes(b'not original evidence')
    with pytest.raises(PermissionError):protected_source(original,os.getuid(),os.getgid())


def test_primary_completion_requires_fresh_independent_quiet_before_stop_reset(tmp_path,monkeypatch):
    import learning.native_meditation.linux as linux
    lock=tmp_path/'runtime.lock';lock.touch();trace=[]
    d=linux.LinuxDriver.__new__(linux.LinuxDriver)
    d.pending=True;d.p=dict(display_socket='/display',display_uid=1103)
    d._lock_path=lambda:lock;d.model_empty=lambda:True
    def inspect(end):
        assert d._clearing_primary is True
        trace.append('all-independent-probes')
        return dict(independent_inventory_complete=True)
    d.inspect=inspect
    def rpc(*a,**kw):trace.append('physical-stop-reset');return dict(clear=True)
    monkeypatch.setattr(linux,'rpc',rpc)
    assert d.primary_done()['independent_inventory_complete']
    assert trace==['all-independent-probes','physical-stop-reset'] and d.pending is False
    d.pending=True;trace.clear()
    def unsafe(end):raise InterruptedError('primary still holds resources')
    d.inspect=unsafe
    with pytest.raises(InterruptedError):d.primary_done()
    assert d.pending is True and not trace and d._clearing_primary is False


@pytest.mark.parametrize('bad', [dict(valid_until=float('nan'),scheduled_duties=[]),
    dict(valid_until=2000000000,scheduled_duties=[dict(at=float('nan'))]),
    dict(valid_until=2000000000,scheduled_duties=[dict(at='unknown')]),
    dict(valid_until=2000000000,scheduled_duties=None)])
def test_root_deadline_inventory_rejects_unknown_and_nonfinite(monkeypatch,bad):
    import learning.native_meditation.linux as linux
    d=linux.LinuxDriver.__new__(linux.LinuxDriver);d.p=dict(inventory_path='/protected')
    monkeypatch.setattr(linux,'root_read',lambda path:json.dumps(bad).encode())
    with pytest.raises(PermissionError):d.inventory()


def test_namespace_helper_binds_pid_and_drops_authority_before_http(monkeypatch):
    import io
    import learning.native_meditation.ns_http as helper
    trace=[];output=io.StringIO()
    monkeypatch.setattr(helper,'root_read',lambda path:json.dumps(dict(model_uid=1102,model_gid=1102)).encode())
    ticks=['12345']
    monkeypatch.setattr(helper,'Path',lambda *args:SimpleNamespace(read_text=lambda:'1 (model) '+'0 '*19+ticks[0]))
    monkeypatch.setattr(helper,'sys',SimpleNamespace(argv=['helper','123','12345','/api/ps'],
        stdin=SimpleNamespace(buffer=io.BytesIO(b'{"payload":null,"timeout":2}')),stdout=output))
    monkeypatch.setattr(helper,'os',SimpleNamespace(geteuid=lambda:0,O_RDONLY=0,CLONE_NEWNET=0x40000000,
        open=lambda *args:trace.append('open-model-netns') or 99,close=lambda fd:trace.append('close-netns'),
        setns=lambda *args:trace.append('setns'),setgroups=lambda groups:trace.append('groups-empty'),
        setgid=lambda gid:trace.append('model-gid'),setuid=lambda uid:trace.append('model-uid')))
    def http(*args):
        assert trace[-3:]==['groups-empty','model-gid','model-uid']
        trace.append('http');return dict(models=[])
    monkeypatch.setattr(helper,'_http',http)
    helper.main();assert json.loads(output.getvalue())==dict(models=[])
    assert trace==['open-model-netns','setns','close-netns','groups-empty','model-gid','model-uid','http']
    trace.clear();ticks[0]='54321'
    helper.sys.stdin.buffer=io.BytesIO(b'{"payload":null,"timeout":2}')
    with pytest.raises(PermissionError):helper.main()
    assert trace==['open-model-netns','close-netns']
