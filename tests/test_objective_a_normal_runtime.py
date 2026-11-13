"""Normal startup ownership regression; all physical I/O is replaced explicitly."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
import main as app
from stimulus.bus import StimulusBus


@pytest.mark.parametrize('review', [[], ['--human-questions'], ['--model-learning'],
                                  ['--human-questions', '--model-learning'], ['--llm-consultation'],
                                  ['--human-questions','--llm-consultation'],
                                  ['--model-learning','--llm-consultation'],
                                  ['--human-questions','--model-learning','--llm-consultation']])
def test_monitoring_keeps_normal_vision_attention_and_single_worker(monkeypatch, tmp_path, review):
    workers = []
    class Worker:
        def __init__(self, **kwargs):
            self.kwargs = kwargs; self.alive = False; workers.append(self)
        def start(self): self.alive = True
        def is_alive(self): return self.alive
        def terminate(self): self.alive = False
        def join(self, **kwargs): pass
    monkeypatch.setattr(app.multiprocessing, 'get_context', lambda *a: SimpleNamespace(Process=Worker))
    monkeypatch.setenv('CHARLIE_MONITOR_TOKEN', 'fixture-monitor-only-credential-0123456789')
    monkeypatch.delenv('CHARLIE_DRIVE_TOKEN', raising=False)
    monkeypatch.delenv('CHARLIE_MOBILE_ENABLED', raising=False)
    frame_bus = StimulusBus(); owners = []; events = []; managers = []
    @contextmanager
    def feeders(args, **kwargs):
        owners.append('cameras')
        try: yield frame_bus
        finally: events.append('cameras closed')
    @contextmanager
    def actuators(bus, **kwargs):
        assert bus is frame_bus
        owners.append('executor')
        try: yield executor, telemetry
        finally: events.append('executor closed')
    executor = Mock(); telemetry = Mock(); deck = Mock(); neck = Mock(); gateway = Mock()
    monkeypatch.setattr(app, 'application_camera_feeders', feeders)
    monkeypatch.setattr(app, 'application_mobile_actuators', actuators)
    monkeypatch.setattr('motion.controller.Deck', lambda: deck)
    monkeypatch.setattr('hardware.calibration_service.CalibrationService.open', lambda *a: neck)
    monkeypatch.setattr('motion.rp2040_requests.RP2040Requests', lambda *a, **kw: gateway)
    monkeypatch.setattr('stimulus.keyboard.KeyboardStimulus', lambda *a, **kw: Mock())
    monkeypatch.setattr('vision.camera_source.CameraSubscription', lambda bus: subscription)
    subscription = Mock()
    monkeypatch.setattr('vision.detector.ColorDetector', lambda **kw: Mock())
    from attention.manager import AttentionManager
    def manager(*a, **kw):
        value = AttentionManager(*a, **kw); managers.append(value); return value
    monkeypatch.setattr('attention.manager.AttentionManager', manager)
    vision = Mock(); vision.update.side_effect = lambda: events.append('vision update')
    monkeypatch.setattr('vision.stimulus.VisionStimulus', lambda *a, **kw: vision)
    monkeypatch.setattr('ui.dashboard.attach_dashboard', lambda *a: None)
    servers = []
    def attach(args, bus, lifecycle, **kwargs):
        assert bus is frame_bus and kwargs['executor'] is executor
        servers.append(bus); lifecycle.callback(lambda: events.append('http closed'))
    monkeypatch.setattr('ui.dashboard.attach_mobile', attach)
    class EndRun(Exception): pass
    def finish(seconds): raise EndRun()
    monkeypatch.setattr(app.time, 'sleep', finish)
    with pytest.raises(EndRun):
        app.main(['--hardware', '--mobile-dashboard', '--learning-state', str(tmp_path), *review])
    assert owners == ['cameras', 'executor'] and servers == [frame_bus]
    assert len(managers) == 1 and not managers[0].mobile_enabled
    assert len(workers) == 1 and not workers[0].alive
    for flag in ('human_questions', 'model_learning', 'llm_consultation'):
        assert workers[0].kwargs['kwargs'].get(flag, False) == ('--' + flag.replace('_', '-') in review)
    assert 'vision update' in events
    telemetry.poll.assert_called_once(); gateway.poll.assert_called_once()
    subscription.switch.assert_called_once_with('pi')
    deck.stop.assert_called_once(); deck.body.close.assert_called_once()
    assert events.index('http closed') < events.index('executor closed') < events.index('cameras closed')
