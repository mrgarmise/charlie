"""Controlled resource limits; no physical operations or thermal claims."""
import json
from pathlib import Path
import pytest
from learning.resources import DevelopmentResources,ResourceGuard,ResourceUnavailable
from learning.lifecycle import DevelopmentLifecycle
from test_normal_learning_lifecycle import experience


def test_owner_probe_is_direct_and_conservative(tmp_path,monkeypatch):
    import learning.cycle as cycle
    real=Path
    monkeypatch.setattr(cycle,'Path',lambda p:tmp_path if p=='/proc' else real(p))
    process=tmp_path/'23';process.mkdir();(process/'cmdline').write_bytes(b'python\0unrelated\0')
    assert not cycle.gameplay_active()
    (process/'cmdline').write_bytes(b'python\0-m\0experiments.ppal.play_robotron\0')
    assert cycle.gameplay_active()
    (process/'cmdline').unlink()
    assert not cycle.gameplay_active() # process exited


def test_owner_preemption_is_bounded_and_has_no_cached_clear_after_deadline():
    clock=[0.];owner=[False];calls=[]
    def check():calls.append(clock[0]);return owner[0]
    guard=ResourceGuard(clock=lambda:clock[0],owner=check)
    guard.check();owner[0]=True;clock[0]=.049;guard.check()
    clock[0]=.05
    with pytest.raises(InterruptedError,match='primary gameplay'):guard.check()
    assert calls==[0.,.05]


@pytest.mark.parametrize('limitation',['memory','temperature'])
def test_resource_pressure_preserves_work_and_recovers(tmp_path,monkeypatch,limitation):
    import learning.resources as resources
    root=experience(tmp_path);life=DevelopmentLifecycle(tmp_path/'state',[root])
    hot=[True]
    monkeypatch.setattr(resources,'resident_bytes',lambda:900*1024**2 if hot[0] and limitation=='memory' else 40*1024**2)
    monkeypatch.setattr(resources,'temperature',lambda:76. if hot[0] and limitation=='temperature' else 60.)
    before=[r.id for r in life.journal.records()]
    for _ in range(4):life.turn()
    assert [r.id for r in life.journal.records()]==before
    assert life.phase=='waiting for resources'
    assert not life.executive.work_states()
    hot[0]=False;life.turn()
    assert life.executive.work_states()
    assert life.resources.sample['ownership_poll_seconds']==.05
    life.close()


def test_resource_preemption_inside_reconstruction_is_not_stall(tmp_path,monkeypatch):
    from experiments.ppal import meditate_robotron as meditation
    from test_meditation_yield import fragments
    root=experience(tmp_path);(root/'tracks.json').write_text(json.dumps({'tracks':fragments()}))
    state=tmp_path/'state';life=DevelopmentLifecycle(state,[root]);calls=[]
    def pressure():
        calls.append(1)
        if len(calls)>3:raise ResourceUnavailable('controlled memory pressure')
    monkeypatch.setattr(life,'yield_for_primary',pressure)
    life.turn()
    assert life.phase=='waiting for resources'
    work=next(iter(life.executive.work_states().values()))
    assert work['outcome']=='preempted' and work['nonprogress_turns']==0
    saved=json.loads(next((state/'meditations').glob('*/checkpoint.json')).read_text())
    assert saved['reconstruction']['neighbor']>0
    life.close();monkeypatch.undo()
    life=DevelopmentLifecycle(state,[root]);life.turn()
    assert next(iter(life.executive.work_states().values()))['status']=='completed'
    life.close()


@pytest.mark.parametrize('kwargs',[dict(cpu_cores=0),dict(cpu_cores=5),dict(memory_mb=64),dict(temperature_c=90),dict(poll_seconds=1)])
def test_unbounded_resources_rejected(kwargs):
    with pytest.raises(ValueError):DevelopmentResources(**kwargs)
