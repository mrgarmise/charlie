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
