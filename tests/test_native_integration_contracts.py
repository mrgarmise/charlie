"""Device-free combined-branch contracts; no native gameplay qualification."""
from PIL import Image
import pytest

from experiments.ppal.eyes.calibration import Calibration
from experiments.ppal.score_observer import ScoreObserver


def test_score_metrics_remain_bounded_while_totals_span_whole_game(tmp_path):
    observer = ScoreObserver(Calibration(((0,.2),(1,.2),(1,1),(0,1))), tmp_path/'score.jsonl')
    from experiments.ppal.robotron_hud import RobotronHUDObservation
    observer.system.reader.read = lambda image: RobotronHUDObservation(None,None,0.,0.)
    image=Image.new('RGB',(4,4))
    for sample in range(1,2051):
        observer.submit(image,timestamp=float(sample),sample=sample,preceding_action=None)
        observer.queue.join()
    observer.close()
    report=observer.report()
    assert report['samples']==2050
    assert len(observer.costs)<=2048
    assert report['processing_seconds_total']>=sum(observer.costs)
    assert len(observer.gameplay_observations)<=256
    assert report['final_observation']['sample']==2050


def test_closed_score_observer_rejects_geometry_without_dead_queue(tmp_path):
    calibration=Calibration(((0,.2),(1,.2),(1,1),(0,1)))
    observer=ScoreObserver(calibration,tmp_path/'score.jsonl');observer.close()
    with pytest.raises(RuntimeError,match='closed'):
        observer.reframe(calibration)


def test_shared_hailo_admission_excludes_scores_and_perception_and_releases():
    from experiments.ppal.neural_score.backends import Admission, Busy
    gate=Admission()
    with gate.perception():
        with pytest.raises(Busy):
            with gate.score():pytest.fail('score entered concurrent device owner')
        with pytest.raises(Busy):
            with gate.perception():pytest.fail('second detector entered device owner')
    with gate.score():
        with pytest.raises(Busy):
            with gate.perception():pytest.fail('detector entered in-flight score')
    with pytest.raises(ValueError):
        with gate.perception():raise ValueError('inference failure')
    with gate.score():pass
    gate.suspend('thermal')
    with pytest.raises(Busy):
        with gate.perception():pytest.fail('suspended device owner admitted')
    gate.resume()
    with gate.perception():pass


def test_detector_admission_denial_cannot_shift_contention_to_cpu():
    from experiments.ppal.neural_score.backends import Busy
    from experiments.ppal.detector_bridge import DetectorBridge, Frame
    from types import SimpleNamespace
    def denied(frame):raise Busy('score owner in flight')
    backend=SimpleNamespace(name='controlled',infer=denied)
    fallback=SimpleNamespace(infer=lambda frame:pytest.fail('resource denial used CPU fallback'))
    bridge=DetectorBridge(lambda:backend,model={},fallback=fallback,mode='fallback',clock=lambda:10.)
    frame=Frame('fixture',Image.new('RGB',(4,4)),10.,'fixture',{})
    with pytest.raises(Busy):bridge.observe(frame)
    assert bridge.events[-1]['error']=='Busy'
