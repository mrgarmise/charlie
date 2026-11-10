from contextlib import contextmanager, closing
from types import SimpleNamespace
import pytest
from memory.evidence import EvidenceJournal
from learning.question_selection import QuestionQueue, discover
from learning.meditation_consultation import MeditationConsultations, NativeSlotAuthority, Slot
from test_question_selection import source


class Authority:
    """Simulation dependency only; no approval files or native claims."""
    def __init__(self, clock):
        self.clock=clock;self.active=False;self.safe=False;self.revoked=False;self.used=set();self.resources=True
    @contextmanager
    def reserve(self, *, commission_id, seconds):
        if not self.safe or not self.resources or self.active or commission_id in self.used:
            raise PermissionError('simulation primary deadline/resource/overlap')
        self.active=True;self.used.add(commission_id)
        def check():
            if self.revoked or not self.safe or not self.resources:raise InterruptedError('simulation revocation')
        try:yield Slot(commission_id,'simulation-only',self.clock()+seconds,check)
        finally:self.active=False


class Provider:
    def __init__(self, path):self.state='checking-native-admission';self.calls=[];self.retained_called=False;self.closed=False
    def status(self):return {'state':self.state}
    def consult(self, prompt, check):
        check();self.state='request-in-flight';check();self.calls.append(prompt)
        return dict(answer='Offline hypothesis',identity={'model_digest':'a'*64},latency_seconds=0)
    def retained(self):self.retained_called=True;self.state='completed-unload-confirmed'
    def close(self):self.closed=True


def setup(tmp_path, factory=Provider, enabled=True):
    path=source(tmp_path);clock=[1800000000.]
    j=EvidenceJournal(tmp_path/'queue.sqlite3');q=QuestionQueue(j,lambda:clock[0]);authority=Authority(lambda:clock[0]);providers=[]
    def make(path):
        p=factory(path);providers.append(p);return p
    c=MeditationConsultations(q,[path],authority,enabled=enabled,provider_factory=make,clock=lambda:clock[0],cooldown=60)
    c.refresh()
    return SimpleNamespace(c=c,q=q,j=j,authority=authority,providers=providers,clock=clock,path=path)


def test_hundreds_of_mixed_activity_cycles(tmp_path):
    x=setup(tmp_path)
    try:
        for cycle in range(500):
            x.clock[0]+=61
            x.authority.safe=cycle%7==3
            x.authority.resources=cycle%11!=0
            before=len(x.providers)
            x.c.on_meditation(str(cycle))
            if len(x.providers)>before:
                assert x.authority.safe and x.authority.resources
                assert x.providers[-1].closed and x.providers[-1].retained_called
            assert not x.authority.active
        assert len(x.providers)==3
        assert len(set(p.calls[0] for p in x.providers))==3
        assert all(s['state']=='awaiting-evaluation' for s in x.q.states().values())
        rows=[r.data['payload'] for r in x.j.records()]
        assert sum(p['state']=='answer-durable' for p in rows)==3
        assert all(p['trust']=='unverified_hypothesis' for p in rows if p['state']=='answer-durable')
        # New coordinator on the same durable queue cannot replay answered work.
        x.c.refresh();x.c.on_meditation('restart');assert len(x.providers)==3
    finally:x.j.close()


@pytest.mark.parametrize('mode',['disabled','native-stub','unsafe','resource'])
def test_no_provider_before_independent_gate(tmp_path,mode):
    x=setup(tmp_path,enabled=mode!='disabled');x.authority.safe=True
    if mode=='native-stub':x.c.authority=NativeSlotAuthority()
    if mode=='unsafe':x.authority.safe=False
    if mode=='resource':x.authority.resources=False
    try:
        x.c.on_meditation('commission');assert not x.providers
    finally:x.j.close()


def test_revocation_mid_request_latches_no_retry(tmp_path):
    x=None
    class Revoked(Provider):
        def consult(self,prompt,check):
            self.state='request-in-flight';check();x.authority.revoked=True;check()
    x=setup(tmp_path,Revoked);x.authority.safe=True
    try:
        x.c.on_meditation('commission')
        assert len(x.providers)==1 and x.providers[0].closed
        assert any(s['state']=='uncertain-completion' for s in x.q.states().values())
        x.authority.revoked=False;x.clock[0]+=100
        # Same commission must never select a second question after uncertainty.
        x.c.on_meditation('commission');assert len(x.providers)==1
    finally:x.j.close()


def test_journal_failure_never_acknowledges_provider(tmp_path,monkeypatch):
    x=setup(tmp_path);x.authority.safe=True;event=x.q.event
    def fail(item,state,**kw):
        if state=='answer-durable':raise OSError('disk failure')
        return event(item,state,**kw)
    monkeypatch.setattr(x.q,'event',fail)
    try:
        x.c.on_meditation('commission')
        assert not x.providers[0].retained_called and x.providers[0].closed
        assert any(s['state']=='uncertain-completion' for s in x.q.states().values())
    finally:x.j.close()


def test_changed_source_rejected_before_provider(tmp_path):
    x=setup(tmp_path);x.authority.safe=True
    with closing(EvidenceJournal(x.path)) as j:
        j.append('event',{'category':'later'},episode='history',producer='Reflection',version='2')
    try:
        x.c.on_meditation('commission');assert not x.providers
        assert any(s['state']=='rejected' for s in x.q.states().values())
    finally:x.j.close()


def test_cleanup_uncertain_and_daily_budget(tmp_path):
    class Cleanup(Provider):
        def retained(self):self.retained_called=True;self.state='cleanup-unconfirmed'
    x=setup(tmp_path,Cleanup);x.authority.safe=True;x.c.daily_limit=1
    try:
        x.c.on_meditation('one');x.clock[0]+=100;x.c.on_meditation('two')
        assert len(x.providers)==1
        assert any(s['state']=='uncertain-completion' for s in x.q.states().values())
    finally:x.j.close()


def test_nested_runtime_lock_and_subprocess_exclusion(tmp_path):
    from learning.runtime_exclusion import runtime_exclusion
    import subprocess,sys
    path=tmp_path/'runtime.lock'
    with runtime_exclusion(path):
        with runtime_exclusion(path):
            child=subprocess.run([sys.executable,'-c',
                'from learning.runtime_exclusion import runtime_exclusion; import sys\nwith runtime_exclusion(sys.argv[1]): pass',str(path)],capture_output=True,text=True)
            assert child.returncode!=0 and 'BlockingIOError' in child.stderr
    with runtime_exclusion(path):pass


@pytest.mark.parametrize('field,value', [('sensing',True),('watchdog_deadline',True),('outstanding_lease',True),
    ('primary_pending',True),('revoked',True),('temperature_c',70),('available_gib',2.9),('load',3),
    ('reserved_until',0),('independent_inventory_complete',False),('telemetry_deadline',None)])
def test_standing_enforcer_checks_external_inventory(field,value):
    from learning.standing_consultation_policy import StandingPolicy,StandingSlotAuthority
    snapshot=dict(independent_inventory_complete=True,temperature_c=40,available_gib=4,load=0,reserved_until=1090)
    for k in ('sensing','telemetry_deadline','watchdog_deadline','physical_task','gameplay','outstanding_lease','primary_pending','revoked','swap_used','throttled'):snapshot[k]=False
    snapshot[field]=value
    lease=SimpleNamespace(inspect=lambda:snapshot)
    authority=StandingSlotAuthority(StandingPolicy(enabled=True),None,clock=lambda:1000)
    with pytest.raises((InterruptedError,PermissionError)):authority._check(lease,1090)


def test_standing_lifecycle_finishes_after_early_wakeup():
    from learning.standing_consultation_policy import StandingPolicy,StandingSlotAuthority
    snapshot=dict(independent_inventory_complete=True,temperature_c=40,available_gib=4,load=0,reserved_until=1090)
    for k in ('sensing','telemetry_deadline','watchdog_deadline','physical_task','gameplay','outstanding_lease','primary_pending','revoked','swap_used','throttled'):snapshot[k]=False
    events=[]
    class Lease:
        id='simulated'
        def inspect(self):return snapshot
        def reserve_budget(self,*args):events.append('budget')
        def prepare(self,**kw):events.append('prepare');return 'simulation-only'
        def finish(self,**kw):events.append('observed-empty')
    class Backend:
        @contextmanager
        def exclusive(self,*args):
            events.append('locked')
            try:yield Lease()
            finally:events.append('unlock')
    authority=StandingSlotAuthority(StandingPolicy(enabled=True),Backend(),clock=lambda:1000)
    with pytest.raises(InterruptedError):
        with authority.reserve(commission_id='commission',seconds=90) as slot:
            snapshot['primary_pending']=True;slot.check()
    assert events==['locked','budget','prepare','observed-empty','unlock']
    with pytest.raises(PermissionError):
        with StandingSlotAuthority(StandingPolicy(),Backend()).reserve(commission_id='x',seconds=90):pass


def test_reset_after_dispatch_blocks_entire_queue(tmp_path):
    x=setup(tmp_path);x.authority.safe=True
    try:
        item=next(iter(x.q.states().values()))['item']
        x.q.event(item,'admission-pending',attempt_id='lost-child',commission_id='old')
        x.c.refresh();x.c.on_meditation('new')
        assert not x.providers
    finally:x.j.close()



def test_actual_executive_meditation_hook_keeps_checkpoint(tmp_path):
    from learning.lifecycle import DevelopmentLifecycle
    from test_normal_learning_lifecycle import experience
    from learning.datasets import sha
    root=experience(tmp_path);before=sha(root/'tracks.json');seen=[]
    life=DevelopmentLifecycle(tmp_path/'state',[root])
    class Coordinator:
        def refresh(self,check):check();seen.append('refresh')
        def on_meditation(self,commission_id,check,*,client_deadline):
            assert client_deadline>0
            row=life.journal.get(commission_id)
            assert row.data['payload']['category']=='reflection_commission'
            checkpoints=list((life.output/'meditations').glob('**/checkpoint.json'))
            assert checkpoints
            check();seen.append('meditation')
    life.meditation_consultations=Coordinator()
    try:
        life.turn()
        assert seen==['refresh','meditation']
        assert life.journal.category_records('observation','normal_meditation_result')
        assert sha(root/'tracks.json')==before
    finally:life.close()


from test_consultation_activation import native_fakes


def test_actual_operational_provider_admission_refusal_is_not_submission(tmp_path,native_fakes):
    from learning.consultation_activation import OperationalProvider
    native_fakes.mode['value']='unapproved'
    x=setup(tmp_path,lambda _:OperationalProvider(native_fakes.path));x.authority.safe=True
    try:
        x.c.on_meditation('commission')
        assert not native_fakes.rows()
        states=[r.data['payload']['state'] for r in x.j.records()]
        assert 'admission-pending' in states and 'submitted/unknown' not in states
        assert states[-1]=='uncertain-completion'  # conservative no retry
    finally:x.j.close()


def test_actual_operational_provider_retention_order(tmp_path,native_fakes):
    from learning.consultation_activation import OperationalProvider
    x=setup(tmp_path,lambda _:OperationalProvider(native_fakes.path));x.authority.safe=True
    try:
        x.c.on_meditation('commission')
        states=[r.data['payload']['state'] for r in x.j.records()]
        assert states[-5:]==['admission-pending','submitted/unknown','answer-durable','provider-cleanup-confirmed','awaiting-evaluation']
        assert not native_fakes.marker.exists()
        assert len([r for r in native_fakes.rows() if r['path']=='/api/chat'])==1
    finally:x.j.close()


def test_slot_replay_cannot_consult_second_question(tmp_path):
    x=setup(tmp_path);x.authority.safe=True
    original=x.authority.reserve
    @contextmanager
    def same_slot(**kwargs):
        with original(**kwargs) as slot:yield Slot('same-external-slot',slot.approval_path,slot.ends_at,slot.check)
    x.authority.reserve=same_slot
    try:
        x.c.on_meditation('one');x.clock[0]+=100;x.c.on_meditation('two')
        assert len(x.providers)==1
    finally:x.j.close()


def test_decision_notebook_cannot_alias_source(tmp_path):
    import os
    path=source(tmp_path)
    alias=tmp_path/'alias.sqlite3';os.link(path,alias)
    with closing(EvidenceJournal(path)) as j:
        with pytest.raises(ValueError,match='separate'):
            MeditationConsultations(QuestionQueue(j),[alias])


def test_manual_existing_admission_holds_lock_through_cutoff(tmp_path,monkeypatch):
    import time
    from learning.meditation_consultation import ManualApprovalSlot
    cutoff=time.monotonic()+.02
    class Admission:
        raw=b'externally issued one-off admission'
        doc={'expires_at':time.time()+40}
        identity={'cutoff_monotonic':cutoff}
        def __init__(self,path):pass
        def check(self,**kwargs):pass
    monkeypatch.setattr('learning.consultation_activation.Admission',Admission)
    with ManualApprovalSlot(tmp_path/'external-approval',tmp_path/'runtime.lock').reserve(commission_id='manual',seconds=40):pass
    assert time.monotonic()>=cutoff


def test_slot_deadline_expiry_retains_unknown_without_answer(tmp_path):
    x=None
    class Late(Provider):
        def consult(self,prompt,check):
            self.state='request-in-flight';check();x.clock[0]+=90;check()
    x=setup(tmp_path,Late);x.authority.safe=True
    try:
        x.c.on_meditation('finite')
        states=[r.data['payload']['state'] for r in x.j.records()]
        assert states[-1]=='uncertain-completion' and 'answer-durable' not in states
        x.clock[0]+=100;x.c.on_meditation('next');assert len(x.providers)==1
    finally:x.j.close()


@pytest.mark.parametrize('budget,admitted',[(10,False),(60,True)])
def test_existing_meditation_budget_admits_only_sufficient_client_headroom(tmp_path,budget,admitted):
    from learning.lifecycle import DevelopmentLifecycle
    from test_normal_learning_lifecycle import experience
    questions=tmp_path/'questions';questions.mkdir()
    x=setup(questions);x.authority.safe=True
    life=DevelopmentLifecycle(tmp_path/'state',[experience(tmp_path)],budget_seconds=budget)
    life.meditation_consultations=x.c
    try:
        life.turn()
        assert len(x.providers)==int(admitted)
        expected='awaiting-evaluation' if admitted else 'deferred-to-next-eligible-meditation'
        assert any(s['state']==expected for s in x.q.states().values())
    finally:life.close();x.j.close()


def test_service_preparation_cannot_consume_required_client_headroom(tmp_path,monkeypatch):
    import time
    import learning.meditation_consultation as module
    x=setup(tmp_path);x.authority.safe=True;base=time.monotonic()
    original=x.authority.reserve
    @contextmanager
    def preparation(**kwargs):
        with original(**kwargs) as slot:
            monkeypatch.setattr(module,'time',SimpleNamespace(monotonic=lambda:base+30))
            yield slot
    x.authority.reserve=preparation
    try:
        x.c.on_meditation('commission',client_deadline=base+60)
        assert not x.providers
        assert not x.authority.active
        assert any('preparation consumed' in s['reason'] for s in x.q.states().values())
    finally:x.j.close()
