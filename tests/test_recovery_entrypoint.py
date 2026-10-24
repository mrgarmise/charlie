"""Software-only CLI and resource admission tests; no hardware is opened."""
import sys
from types import SimpleNamespace
import pytest
from experiments.ppal import marathon_robotron as m


def command(tmp_path):
    return ['marathon','--arm','--developmental','--learning-projects',
        '--ala-learning','--recovery-trial','--max-games','2','--qualified-games','2',
        '--root',str(tmp_path)]


def test_recovery_cli_preserves_learning_and_requires_lease(tmp_path,monkeypatch):
    import os
    import experiments.ppal.progress_supervision as p
    monkeypatch.setattr(sys,'argv',command(tmp_path))
    callback=lambda:None
    monkeypatch.setattr(m,'recovery_resource_check',lambda root:callback)
    seen=[]
    def supervise(cmd,path,**kw):
        seen.append(cmd)
        assert kw['on_poll'] is callback
        assert os.environ['CHARLIE_CONTROLLER_LEASE']=='required'
        assert '--baseline-only' not in cmd and '--play-first' not in cmd
        return 2
    monkeypatch.setattr(p,'supervise',supervise)
    with pytest.raises(SystemExit) as exc:m.main()
    assert exc.value.code==2 and seen


@pytest.mark.parametrize('extra',[['--baseline-only'],['--play-first'],['--max-games','3']])
def test_recovery_rejects_incompatible_schedules(tmp_path,monkeypatch,extra):
    monkeypatch.setattr(sys,'argv',command(tmp_path)+extra)
    with pytest.raises(SystemExit) as exc:m.main()
    assert exc.value.code==2


def test_failed_recovery_is_nonzero(tmp_path,monkeypatch):
    monkeypatch.setattr(sys,'argv',command(tmp_path)+['--supervised-marathon'])
    monkeypatch.setattr(m,'developmental_marathon',lambda args:{'target_met':False})
    with pytest.raises(SystemExit) as exc:m.main()
    assert exc.value.code==2


def test_resource_refusal_stops_before_throttle_command(tmp_path,monkeypatch):
    import learning.resources as r
    def refuse(*a,**kw):raise r.ThermalSuspended('hot')
    monkeypatch.setattr(r.ResourceGuard,'check',refuse)
    with pytest.raises(r.ThermalSuspended):m.recovery_resource_check(tmp_path)()


def test_feature_report_does_not_claim_active_learning_artifacts():
    features=m.runtime_features(SimpleNamespace(developmental=True,learning_projects=True,ala_learning=True))
    assert features['offline_ala_investigation'] and features['executive_experiments']
    assert 'inactive' in features['neural_score_hailo']
    assert 'absent' in features['ppal_policy']


def test_recovery_releases_camera_before_between_game_processing(tmp_path,monkeypatch):
    from test_marathon_deferred import args
    from test_experiment_return import gateway
    from test_marathon_camera_session import completed
    import experiments.ppal.camera_session as cameras
    import experiments.ppal.play_robotron as player
    import experiments.ppal.experiment_return as experiments
    events=[]
    class Camera:
        def __init__(self,*a):events.append('open')
        def close(self):events.append('close')
    monkeypatch.setattr(cameras,'CameraSession',Camera)
    def play(argv,**kw):
        assert events[-1]=='open'
        completed(__import__('pathlib').Path(argv[argv.index('--output')+1]))
    monkeypatch.setattr(player,'main',play)
    monkeypatch.setattr(experiments,'select_experiment',lambda *a,**kw:None)
    def process(*a,**kw):
        assert events[-1]=='close'
        events.append('offline')
        return {}
    monkeypatch.setattr(m,'process_supervised',process)
    monkeypatch.setattr(m,'safe_to_restart',lambda *a,**kw:True)
    a=args(tmp_path);a.play_first=False;a.recovery_trial=True;a.max_games=2
    a.qualified_games=2;a.learning_projects=False;a.focus=2.
    doc=m.developmental_marathon(a,gateway=gateway(tmp_path))
    assert doc['target_met'] and events==['open','close','offline']*2


@pytest.mark.parametrize('flags',['throttled=0x1','unknown'])
def test_native_throttling_fails_closed(tmp_path,monkeypatch,flags):
    import learning.resources as r
    monkeypatch.setattr(r.ResourceGuard,'check',lambda *a,**kw:None)
    monkeypatch.setattr(m.subprocess,'check_output',lambda *a,**kw:flags)
    with pytest.raises(InterruptedError):m.recovery_resource_check(tmp_path)()


def test_thermal_refusal_retains_failed_sample_before_propagating(tmp_path,monkeypatch):
    import json
    import learning.resources as r
    def refuse(guard,**kw):
        guard.sample.update(temperature_c=75.1)
        raise r.ThermalSuspended('hot')
    monkeypatch.setattr(r.ResourceGuard,'check',refuse)
    with pytest.raises(r.ThermalSuspended):m.recovery_resource_check(tmp_path)()
    row=json.loads((tmp_path/'recovery-resources.jsonl').read_text())
    assert row['status']=='stopped' and row['temperature_c']==75.1
    assert row['throttling'] is None and row['free_disk_bytes'] is None
    assert row['stop_reason']=='ThermalSuspended: hot'


@pytest.mark.parametrize('flags',['throttled=0x1','unknown'])
def test_throttle_refusal_is_durable(tmp_path,monkeypatch,flags):
    import json
    import learning.resources as r
    monkeypatch.setattr(r.ResourceGuard,'check',lambda *a,**kw:None)
    monkeypatch.setattr(m.subprocess,'check_output',lambda *a,**kw:flags)
    with pytest.raises(InterruptedError):m.recovery_resource_check(tmp_path)()
    row=json.loads((tmp_path/'recovery-resources.jsonl').read_text())
    assert row['status']=='stopped' and row['throttling']==flags
    assert 'throttling' in row['stop_reason']


def test_disk_refusal_retains_measured_free_bytes(tmp_path,monkeypatch):
    import json,shutil
    import learning.resources as r
    monkeypatch.setattr(r.ResourceGuard,'check',lambda *a,**kw:None)
    monkeypatch.setattr(m.subprocess,'check_output',lambda *a,**kw:'throttled=0x0')
    monkeypatch.setattr(shutil,'disk_usage',lambda *a:SimpleNamespace(free=123))
    with pytest.raises(InterruptedError):m.recovery_resource_check(tmp_path)()
    row=json.loads((tmp_path/'recovery-resources.jsonl').read_text())
    assert row['status']=='stopped' and row['free_disk_bytes']==123
    assert 'disk below' in row['stop_reason']


def test_failed_stop_trace_preserves_original_resource_exception(tmp_path,monkeypatch):
    import learning.resources as r
    def refuse(*a,**kw):raise r.ThermalSuspended('hot')
    monkeypatch.setattr(r.ResourceGuard,'check',refuse)
    with pytest.raises(r.ThermalSuspended) as caught:
        m.recovery_resource_check(tmp_path/'missing-output')()
    assert 'Resource stop trace unavailable' in caught.value.__notes__[0]


def test_admission_writer_failure_cannot_continue_trial(tmp_path,monkeypatch):
    import os,shutil
    import learning.resources as r
    monkeypatch.setattr(r.ResourceGuard,'check',lambda *a,**kw:None)
    monkeypatch.setattr(m.subprocess,'check_output',lambda *a,**kw:'throttled=0x0')
    monkeypatch.setattr(shutil,'disk_usage',lambda *a:SimpleNamespace(free=3*1024**3))
    def full(*a):raise OSError('evidence fsync failed')
    monkeypatch.setattr(os,'fsync',full)
    with pytest.raises(OSError,match='fsync failed'):m.recovery_resource_check(tmp_path)()
