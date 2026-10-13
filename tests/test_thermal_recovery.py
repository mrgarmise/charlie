"""Deterministic engineering controls, never native temperature/learning evidence."""
import json
import signal
import sys
from functools import partial
from pathlib import Path
import pytest
from learning.resources import (DevelopmentResources,ResourceGuard,ThermalSuspended,
    MemoryUnavailable,ResourceUnavailable,DevelopmentInterrupted)
from learning.lifecycle import DevelopmentLifecycle,run
from test_normal_learning_lifecycle import experience,rows
from test_meditation_yield import fragments


class Clock:
    def __init__(self):self.now=0.
    def __call__(self):return self.now
    def sleep(self,seconds):self.now+=seconds


def guard(temp=60.,**kwargs):
    clock=Clock();reading=[temp]
    result=ResourceGuard(DevelopmentResources(stabilization_seconds=2.,require_thermal=True),
        clock=clock,owner=lambda:False,thermal_reader=lambda:reading[0],
        memory_reader=lambda:(40*1024**2,0),**kwargs)
    return result,clock,reading


def check(g):g.check(force=True)


def test_normal_and_exact_ceiling_and_cached_hot_check():
    g,c,t=guard();check(g);assert not g.suspended
    t[0]=75.
    with pytest.raises(ThermalSuspended):check(g)
    assert g.suspended and g.thermal_state=='thermal suspension'
    with pytest.raises(ThermalSuspended):g.check() # No cached clear while latched.


def test_hysteresis_stabilization_reheating_and_oscillation():
    g,c,t=guard(75.)
    with pytest.raises(ThermalSuspended):check(g)
    for when,value in ((1,70),(2,65),(3,64),(4,65),(5,64),(6,64)):
        c.now=when;t[0]=value
        with pytest.raises(ThermalSuspended):check(g)
    c.now=7;check(g)
    assert not g.suspended and g.resume_count==1 and g.thermal_state=='resumed work'
    t[0]=75.;c.now=7.1
    with pytest.raises(ThermalSuspended):check(g)
    assert g.suspended and g.resume_count==1
    for when,value in ((8,64),(9,66),(10,64),(11,70),(12,64)):
        c.now=when;t[0]=value
        with pytest.raises(ThermalSuspended):check(g)
    assert g.resume_count==1


@pytest.mark.parametrize('bad',[None,float('nan'),float('inf'),-1,151,True,'bad'])
def test_missing_or_invalid_telemetry_fail_closed(bad):
    g,c,t=guard(bad)
    with pytest.raises(ThermalSuspended,match='telemetry'):check(g)
    t[0]=60;c.now=1
    with pytest.raises(ThermalSuspended):check(g)
    c.now=3;check(g);assert not g.suspended


def test_sensor_exception_and_loss_during_cooling_resets_stability():
    g,c,t=guard(75.)
    with pytest.raises(ThermalSuspended):check(g)
    t[0]=60;c.now=1
    with pytest.raises(ThermalSuspended):check(g)
    def missing():raise OSError('sensor gone')
    g.thermal_reader=missing;c.now=2
    with pytest.raises(ThermalSuspended,match='telemetry'):check(g)
    g.thermal_reader=lambda:60.;c.now=3
    with pytest.raises(ThermalSuspended):check(g)
    c.now=5;check(g);assert g.resume_count==1


def test_arm_telemetry_mandatory_even_without_flag(monkeypatch):
    import learning.resources as resources
    monkeypatch.setattr(resources.platform,'machine',lambda:'aarch64')
    monkeypatch.setattr(resources.platform,'system',lambda:'Linux')
    g=ResourceGuard(thermal_reader=lambda:None,owner=lambda:False)
    with pytest.raises(ThermalSuspended):check(g)
    assert g.require_thermal


def test_desktop_without_sensors_is_explicitly_unqualified(monkeypatch):
    import learning.resources as resources
    monkeypatch.setattr(resources.platform,'machine',lambda:'x86_64')
    g=ResourceGuard(thermal_reader=lambda:None,owner=lambda:False,memory_reader=lambda:(0,0))
    check(g)
    assert not g.sample['thermal_sensor_available'] and not g.require_thermal


def test_memory_never_misclassified_and_blocks_thermal_release():
    g,c,t=guard();g.memory_reader=lambda:(900*1024**2,0)
    with pytest.raises(MemoryUnavailable):check(g)
    assert not g.suspended and g.resume_count==0
    # Even the normal check cache must not return a false resource-clear.
    with pytest.raises(MemoryUnavailable):g.check()
    t[0]=75
    with pytest.raises(ThermalSuspended):check(g)
    t[0]=60;c.now=1
    with pytest.raises(ThermalSuspended):check(g)
    c.now=3
    with pytest.raises(MemoryUnavailable):check(g)
    assert g.suspended and g.thermal_state=='recovery eligible' and not g.resume_count
    with pytest.raises(MemoryUnavailable):g.check()
    g.memory_reader=lambda:(0,0);check(g)
    assert not g.suspended and g.resume_count==1


def test_gameplay_priority_blocks_recovery_and_restarts_stabilization():
    g,c,t=guard(75.)
    with pytest.raises(ThermalSuspended):check(g)
    t[0]=60;c.now=1
    with pytest.raises(ThermalSuspended):check(g)
    g.owner=lambda:True;c.now=3
    with pytest.raises(InterruptedError,match='primary gameplay'):check(g)
    assert g.suspended and not g.resume_count
    g.owner=lambda:False;c.now=4
    with pytest.raises(ThermalSuspended):check(g)
    c.now=6;check(g);assert g.resume_count==1


def test_restart_retains_same_investigation_checkpoint_and_no_duplicates(tmp_path,monkeypatch,record_property):
    from experiments.ppal import meditate_robotron as meditation
    root=experience(tmp_path);(root/'tracks.json').write_text(json.dumps({'tracks':fragments()}))
    original_bytes=(root/'tracks.json').read_bytes()
    state=tmp_path/'state';g,c,t=guard()
    life=DevelopmentLifecycle(state,[root],resource_guard=g)
    original=meditation.predicted_link;seen=[]
    def heat(left,right,*args):
        answer=original(left,right,*args);seen.append((left['track_id'],right['track_id']))
        if len(seen)==1:t[0]=75.;c.now+=.1
        return answer
    monkeypatch.setattr(meditation,'predicted_link',heat)
    life.turn()
    assert g.suspended and life.phase=='waiting for resources'
    work=life.executive.work_states();work_id=next(iter(work));commission=life.current_activity['meditation']['commission_id']
    checkpoint=next((state/'meditations').glob('*/checkpoint.json'))
    saved_bytes=checkpoint.read_bytes()
    saved=json.loads(saved_bytes);assert saved['reconstruction']['neighbor']==1
    before=[(r.id,r.document) for r in life.journal.records()]
    for _ in range(5):
        c.now+=1;life.turn()
    assert before==[(r.id,r.document) for r in life.journal.records()]
    assert checkpoint.read_bytes()==saved_bytes
    life.close()
    assert json.loads((state/'development-operational-status.json').read_text())['thermal']['suspended']
    monkeypatch.setattr(meditation,'predicted_link',original)
    # Between thresholds at restart cannot bypass the retained interruption.
    fresh,c2,t2=guard(70.)
    life=DevelopmentLifecycle(state,[root],resource_guard=fresh)
    life.turn();assert fresh.suspended
    assert before==[(r.id,r.document) for r in life.journal.records()]
    t2[0]=60;c2.now=1;life.turn();assert fresh.suspended
    c2.now=3;life.turn()
    resumed=life.executive.work_states()[work_id]
    assert json.loads(checkpoint.read_text())['commission_id']==commission
    assert resumed['status']=='completed'
    after=life.journal.records()
    assert all(any(a.id==i and a.document==doc for a in after) for i,doc in before)
    for category in ('reflection_commission','normal_meditation_result'):
        assert sum(r.data['payload'].get('category')==category for r in after)==1
    assert not any(r.data['payload'].get('category')=='capability_activation' for r in after)
    assert (root/'tracks.json').read_bytes()==original_bytes
    life.close()
    status=json.loads((state/'development-status.json').read_text())
    assert status['physical_authorization'] is False and status['activation'] is None
    op=json.loads((state/'development-operational-status.json').read_text())
    assert op['controller_writes']==0 and op['state']=='clean shutdown'
    record_property('retained_work_id',work_id)
    record_property('retained_commission_id',commission)
    record_property('original_records_preserved',len(before))
    record_property('held_poll_record_delta',0)
    record_property('checkpoint_neighbor_before',saved['reconstruction']['neighbor'])
    record_property('resumed_status',resumed['status'])
    record_property('physical_authorization',False)
    record_property('controller_writes',0)


def harness(tmp_path,monkeypatch,reading):
    g,c,t=guard(reading)
    monkeypatch.setattr(DevelopmentResources,'apply',lambda self:None)
    monkeypatch.setattr('os.nice',lambda n:None)
    lives=[]
    def factory(*args,**kwargs):
        life=DevelopmentLifecycle(*args,**kwargs,resource_guard=g);lives.append(life)
        return life
    def execute(**kwargs):
        return run(tmp_path/'state',[],clock=c,sleep=c.sleep,lifecycle_factory=factory,
            resources=g.policy,interval=.05,**kwargs)
    return g,c,t,lives,execute


def test_thermal_polling_does_not_consume_attempt_slots_and_resumes_same_owner(tmp_path,monkeypatch):
    g,c,t,lives,execute=harness(tmp_path,monkeypatch,75.)
    def cool(seconds):
        c.sleep(seconds)
        if c.now>=1:t[0]=60.
    result=run(tmp_path/'state',[],clock=c,sleep=cool,lifecycle_factory=lambda *a,**kw:
        DevelopmentLifecycle(*a,**kw,resource_guard=g),resources=g.policy,turns=2,interval=.05)
    assert result['nonthermal_attempt_slots']==2 and result['developmental_attempts']==2
    assert result['thermal_wait_polls']>=3 and result['productive_turns']==0
    assert result['termination_reason']=='attempt limit reached' and g.resume_count==1
    retained=rows(tmp_path/'state')
    assert not any(r.data['payload'].get('category') in ('reflection_commission','thermal','thermal_suspension') for r in retained)
    assert not any(r.data['kind']=='observation' for r in retained)


def test_bounded_cooldown_and_wall_deadlines_and_signal_restoration(tmp_path,monkeypatch):
    g,c,t,lives,execute=harness(tmp_path,monkeypatch,75.)
    handlers={s:signal.getsignal(s) for s in (signal.SIGTERM,signal.SIGINT)}
    result=execute(turns=4,cooldown_seconds=2,wall_seconds=10)
    assert result['termination_reason']=='cooldown deadline reached'
    assert c.now==pytest.approx(2) and result['nonthermal_attempt_slots']==0
    assert result['developmental_attempts']==0 and len(lives)==1
    assert handlers=={s:signal.getsignal(s) for s in handlers}
    assert json.loads((tmp_path/'state'/'development-operational-status.json').read_text())['state']=='clean shutdown'
    c.now=0
    result=execute(turns=4,cooldown_seconds=10,wall_seconds=1)
    assert result['termination_reason']=='wall-clock deadline reached' and c.now==pytest.approx(1)


def test_shutdown_during_unbounded_suspension_and_no_controller_imports(tmp_path,monkeypatch):
    g,c,t,lives,execute=harness(tmp_path,monkeypatch,75.)
    forbidden=('motion.controller','vision.camera','experiments.ppal.play_robotron')
    before={name:sys.modules.get(name) for name in forbidden}
    original=c.sleep
    def shutdown(seconds):
        original(seconds)
        if c.now>=.2:signal.getsignal(signal.SIGTERM)(signal.SIGTERM,None)
    c.sleep=shutdown
    result=execute()
    assert result['termination_reason']=='shutdown requested' and c.now<.4
    assert result['developmental_attempts']==0 and g.suspended
    assert all(sys.modules.get(name) is before[name] for name in forbidden)
    assert not rows(tmp_path/'state')


def test_memory_blockage_consumes_bounded_slot_without_cooldown(tmp_path,monkeypatch):
    g,c,t,lives,execute=harness(tmp_path,monkeypatch,60.)
    g.memory_reader=lambda:(900*1024**2,0)
    result=execute(turns=2)
    assert result['nonthermal_attempt_slots']==2 and result['thermal_wait_polls']==0
    assert result['developmental_attempts']==0 and not g.suspended
    op=json.loads((tmp_path/'state'/'development-operational-status.json').read_text())
    assert any(e['state']=='other resource blockage' and 'memory' in e['reason'] for e in op['events'])


def test_shutdown_check_not_hidden_by_cache():
    g,c,t=guard();check(g)
    def cancelled():raise DevelopmentInterrupted('shutdown requested')
    g.interruption_check=cancelled
    with pytest.raises(DevelopmentInterrupted):g.check()


@pytest.mark.parametrize('kwargs',[{'temperature_c':76},{'recovery_temperature_c':75},
    {'stabilization_seconds':0},{'cooldown_poll_seconds':0},{'recovery_temperature_c':float('nan')}])
def test_unsafe_or_unbounded_policy_rejected(kwargs):
    with pytest.raises(ValueError):DevelopmentResources(**kwargs)


def test_worker_poll_interrupts_even_without_progress_and_reaps_child(tmp_path,monkeypatch):
    import experiments.ppal.progress_supervision as supervision
    stopped=[]
    class Child:
        pid=123;returncode=None
        def poll(self):return None
    child=Child()
    monkeypatch.setattr(supervision.subprocess,'Popen',lambda *a,**kw:child)
    def reap(child,**kw):stopped.append(child);child.returncode=-2;return True
    monkeypatch.setattr(supervision,'stop_process',reap)
    g,c,t=guard();calls=[]
    def probe():
        calls.append(1)
        if len(calls)==2:t[0]=75.;c.now=.1
        g.check(force=True)
    with pytest.raises(ThermalSuspended):
        supervision.supervise(['offline-worker'],tmp_path/'progress.json',on_poll=probe)
    assert len(calls)==2 and stopped==[child]
    report=json.loads((tmp_path/'progress-supervisor.json').read_text())
    assert report['reason']=='resource_preemption' and report['reaped']
    assert report['last_progress'] is None and report['episode_boundary']=='unverified'


def test_mid_turn_thermal_preemption_not_charged_and_same_lifecycle_resumes(tmp_path,monkeypatch):
    root=experience(tmp_path);(root/'tracks.json').write_text(json.dumps({'tracks':fragments()}))
    g,c,t,lives,execute=harness(tmp_path,monkeypatch,60.)
    from experiments.ppal import meditate_robotron as meditation
    original=meditation.predicted_link;heated=[]
    def heat(*args,**kwargs):
        answer=original(*args,**kwargs)
        if not heated:t[0]=75.;c.now+=.1;heated.append(True)
        return answer
    monkeypatch.setattr(meditation,'predicted_link',heat)
    def cool(seconds):
        c.sleep(seconds)
        if c.now>=1:t[0]=60.
    def factory(*a,**kw):
        life=DevelopmentLifecycle(*a,**kw,resource_guard=g);lives.append(life);return life
    result=run(tmp_path/'state',[root],turns=1,resources=g.policy,interval=.05,
        clock=c,sleep=cool,lifecycle_factory=factory)
    assert len(lives)==1 and result['developmental_attempts']==2
    assert result['nonthermal_attempt_slots']==1 and result['productive_turns']>=1
    assert result['thermal_wait_polls']>=3
    retained=rows(tmp_path/'state')
    assert sum(r.data['payload'].get('category')=='reflection_commission' for r in retained)==1
    assert sum(r.data['payload'].get('category')=='normal_meditation_result' for r in retained)==1
    assert not any(r.data['payload'].get('category')=='capability_activation' for r in retained)


def test_poll_telemetry_deduplicates_and_corrupt_retained_latch_fails_closed(tmp_path):
    g,c,t=guard(75.)
    life=DevelopmentLifecycle(tmp_path/'state',[],resource_guard=g)
    life.turn();count=len(life.operational['events'])
    for i in range(1,20):c.now=i;life.turn()
    assert len(life.operational['events'])==count # Repeated hot polls create no redundant events.
    assert not life.journal.records()
    life.close()
    (tmp_path/'state'/'development-operational-status.json').write_text('{invalid')
    fresh,c,t=guard(70.)
    life=DevelopmentLifecycle(tmp_path/'state',[],resource_guard=fresh)
    life.turn();assert fresh.suspended and not life.journal.records()
    life.close()


def test_observer_is_bounded_read_only_and_refuses_overwrite(tmp_path):
    import subprocess
    state=tmp_path/'state';state.mkdir()
    status=state/'development-operational-status.json'
    status.write_text(json.dumps({'state':'thermal suspension'}));original=status.read_bytes()
    output=tmp_path/'native-observations.jsonl'
    command=[sys.executable,'tools/observe_development_thermal.py','--state',str(state),
        '--output',str(output),'--seconds','.11','--interval','.1']
    result=subprocess.run(command,capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stderr
    observed=[json.loads(line) for line in output.read_text().splitlines()]
    assert 1<=len(observed)<=2 and all(r['physical_authorization'] is False for r in observed)
    assert status.read_bytes()==original
    retained=output.read_bytes()
    assert subprocess.run(command,capture_output=True,timeout=5).returncode!=0
    assert output.read_bytes()==retained


def test_unrelated_worker_failure_is_not_thermal_recovery(tmp_path,monkeypatch):
    g,c,t=guard()
    life=DevelopmentLifecycle(tmp_path/'state',[],resource_guard=g)
    def failure(adapter):raise InterruptedError('unrelated worker failure')
    monkeypatch.setattr(life.executive,'develop',failure)
    with pytest.raises(InterruptedError,match='unrelated worker'):life.turn()
    assert not g.suspended and g.resume_count==0
    life.close()
