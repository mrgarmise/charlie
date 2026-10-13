"""Integrated Pi perception -> real UART/protocol -> RP2040, simulated IO only."""
import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import cv2
import numpy as np
import pytest
from test_active_vision_firmware import board, transport, PROFILE
from test_neck_calibration import commissioning
from hardware.calibration_service import CalibrationService
from hardware.neck_calibration import ProfileRepository
from hardware.scene_response import SceneResponse
from memory.evidence import EvidenceJournal


@pytest.fixture
def integrated(board, tmp_path):
    host, authority, behaviors = transport(board)
    p = commissioning()
    p['powered_start_review'] = dict(pose=[90, 90], powered_initialization_verified=True,
        reviewer='reviewer_001', evidence='FAKE_powered_start_review')
    authority.calibration = sys.modules['calibration'].Calibration(authority, p,
        lambda: board.pressed[0], sink=lambda event:
            host.serial.lines.append(('CAL_EVENT '+json.dumps(event)+'\n').encode()))
    journal = EvidenceJournal(tmp_path/'requests.sqlite3')
    repository = ProfileRepository(tmp_path/'profiles')
    repository.save(copy.deepcopy(PROFILE)); repository.activate(PROFILE['calibration_id'])
    service = CalibrationService(host, repository, journal, clock=lambda: board.now[0]/1000)
    brain = service.attach_brain(authorized=True, supervised=True, simulated=True, maximum_steps=8)
    rng = np.random.default_rng(40)
    texture = cv2.GaussianBlur(rng.integers(0, 255, (360, 480, 3), dtype=np.uint8), (3, 3), 0)
    def frame():
        pose = authority._positions
        transform = np.float32([[1, 0, 4*(pose[0]-90)], [0, 1, 4*(pose[1]-90)]])
        return cv2.warpAffine(texture, transform, (480, 360))
    def tick(contact=False):
        board.pressed[0] = contact
        for _ in range(5):
            board.now[0] += 20; authority.update()
        service.observe_frame(frame())
    fixture = SimpleNamespace(host=host, a=authority, b=board, s=service, brain=brain,
                              tick=tick, frame=frame, root=tmp_path, profile=p)
    yield fixture
    service.close()


def test_brain_continuous_calibration_without_json_or_camera_owner(integrated):
    f = integrated
    f.brain.request(); f.tick()
    assert f.brain.last_state == 'VERIFY_INITIAL' and not f.b.pwms
    f.brain.confirm_start(); f.tick(); f.tick()
    assert f.a.calibration.state == 'PREPARED'
    f.tick(True); f.tick(False)
    for _ in range(150):
        f.tick()
        if f.brain.session is None: break
    assert f.brain.session is None and not f.brain.blocked
    assert len(f.brain.responses) >= 4
    assert len(f.b.pwms) == 2 and f.a.status()['armed']
    assert all(p.pin in (4, 5) for p in f.b.pwms)
    assert any(e['kind'] == 'camera_confirmed' for e in f.a.calibration.events)
    assert any(e['kind'] == 'normal_resumed' for e in f.a.calibration.events)
    records = list((f.root/'observations').glob('*.json'))
    assert records and all(json.loads(p.read_text())['validation_status'] == 'PROVISIONAL' for p in records)
    assert not any(e['kind'] == 'confirmed' for e in f.a.calibration.events)
    # A target outside digital range causes a bounded physical correction.
    f.brain.update(f.frame(), dict(x=460, y=180, width=10, height=10))
    f.b.now[0] += 100
    f.brain.update(f.frame(), dict(x=460, y=180, width=10, height=10))
    assert f.brain.tracking_pending is not None
    for _ in range(20): f.tick()
    assert not f.brain.blocked and not f.s.health.quarantined
    assert any(r.data['payload'].get('op') == 'offscale_camera_correction' for r in f.s.journal.records('event'))


def test_missing_qualification_explores_only_on_gp10_and_retraces_supported_path(integrated):
    f = integrated
    f.a.envelope = None  # No independent safe region; no normal motion grant.
    f.brain.request(); f.tick(); f.brain.confirm_start(); f.tick(); f.tick()
    assert f.a.calibration.state == 'PREPARED' and not f.b.pwms
    f.tick(True); f.tick(False)
    for _ in range(20): f.tick()
    assert f.a.calibration.state == 'PREPARED' and f.a._positions[0] == pytest.approx(90)
    before = f.a._positions.copy()
    # Withheld permission is a provisional boundary, not a mechanical diagnosis.
    for _ in range(110):
        f.tick()
        if any(e['kind'] == 'permission_withheld' for e in f.a.calibration.events): break
    withheld = [e for e in f.a.calibration.events if e['kind'] == 'permission_withheld']
    assert withheld and withheld[-1]['mechanical_hard_stop'] is False
    assert min(e['commanded_pose'][0] for e in f.a.calibration.events) >= before[0]-1e-5
    for _ in range(20): f.tick()
    assert f.a._positions[0] == pytest.approx(90)
    assert any(e.get('source') == 'supervised_return_path' for e in f.a.calibration.events)
    assert f.brain.boundaries and not f.brain.blocked


def test_unreviewed_powered_start_never_creates_pwm(integrated):
    f = integrated
    f.a.calibration.envelope.powered_start_review = None
    f.brain.request(); f.tick(); f.brain.confirm_start(); f.tick()
    assert not f.b.pwms and f.a.calibration.state == 'VERIFY_INITIAL'
    assert f.brain.last_message == 'START POSE UNVERIFIED'


def test_visual_failure_stops_without_retry_and_preserves_uncertainty(integrated):
    f = integrated
    f.brain.request(); f.tick(); f.brain.confirm_start(); f.tick(); f.tick()
    f.tick(True); f.tick(False)
    f.brain.estimator.compare = lambda *args: dict(reliable=False, displacement=[0, 0])
    for _ in range(20): f.tick()
    assert f.brain.blocked and not f.a.status()['pwm_active']
    count = len(f.b.pwms)
    for _ in range(10): f.tick()
    assert len(f.b.pwms) == count
    faults = [r.data['payload'] for r in f.s.journal.records('event') if r.data['payload'].get('op') == 'brain_fault']
    assert faults and faults[-1]['mechanical_fault_confirmed'] is False


def test_restart_preserves_observations_but_not_pending_permission(integrated):
    f = integrated
    f.brain.request(); f.tick(); f.brain.confirm_start(); f.tick(); f.tick()
    f.tick(True); f.tick(False)
    for _ in range(20): f.tick()
    files = {p: p.read_bytes() for p in (f.root/'observations').glob('*.json')}
    assert files
    f.s.close_session(); f.brain.session = None
    f.s.journal.close()
    recovered = CalibrationService(f.host, f.s.repository, EvidenceJournal(f.root/'requests.sqlite3'))
    new = recovered.attach_brain(authorized=True, supervised=True, simulated=True)
    assert not new.confirmed_start and not new.pending
    assert all(p.read_bytes() == raw for p, raw in files.items())
    assert recovered.requests()
    recovered.close()


def test_no_authorization_leaves_all_firmware_gates_untouched(integrated):
    f = integrated
    f.brain.authorized = False
    f.brain.request()
    for _ in range(10): f.tick(True)
    assert not f.b.pwms and f.a.calibration.run_id is None


def test_full_combined_grid_generates_candidate_without_qualification(integrated):
    f = integrated
    f.brain.maximum_steps = 24
    f.brain.request(); f.tick(); f.brain.confirm_start(); f.tick(); f.tick()
    f.tick(True); f.tick(False)
    for _ in range(300):
        f.tick()
        if f.brain.session is None: break
    assert f.brain.session is None and not f.brain.blocked
    candidates = list((f.root/'profiles').glob('*_candidate.json'))
    assert len(candidates) == 1
    candidate = json.loads(candidates[0].read_text())
    assert candidate['validation_status'] == 'CANDIDATE' and candidate['simulated'] is True
    with pytest.raises(ValueError): f.s.repository.activate(candidate['calibration_id'])
    assert f.s.repository.active()['calibration_id'] == PROFILE['calibration_id']
    assert any(e.get('source') == 'qualified_path' for e in f.a.calibration.events)
    # Reuse the installed capability: durable initial grid drives the next
    # developmental goal, rather than repeating a disposable demonstration.
    old_run = f.brain.run
    f.brain.request(); f.tick()
    assert f.brain.run != old_run and f.brain.phase == 'boundary'
    for _ in range(300):
        f.tick()
        if f.brain.session is None: break
    assert f.brain.session is None and not f.brain.blocked
    assert any(abs(r['commanded_pose'][0]-90) > .5 for r in f.brain.responses)
    assert any(r.data['payload'].get('op') == 'brain_resume_bookmark' for r in f.s.journal.records('event'))


def test_normal_powered_start_uses_review_and_live_confirmation_without_gp10(integrated):
    f = integrated
    profile = copy.deepcopy(PROFILE)
    profile['powered_start_review'] = f.profile['powered_start_review']
    profile['calibration_id'] = 'SIMULATED_002'; profile['supersedes'] = [PROFILE['calibration_id']]
    f.s.repository.save(profile); f.s.repository.activate(profile['calibration_id'])
    f.a.envelope = f.b.module.Envelope(profile)
    f.a._autonomous_enabled = True
    f.a._quarantine = lambda reason: None
    f.a._profile_operation = lambda active: None
    f.brain.supervised = False
    f.tick()
    assert not f.b.pwms and f.brain.startup_waiting
    f.brain.confirm_start(); f.tick()
    assert len(f.b.pwms) == 2 and f.a.status()['armed']
    assert not f.b.pressed[0] and f.a.calibration.run_id is None


def test_existing_executive_selects_and_retains_calibration_project(integrated):
    from memory.learning_projects import LearningExecutive
    f = integrated
    f.s.executive = LearningExecutive(f.s.journal, SimpleNamespace(remember=lambda *args: None))
    f.brain.maximum_steps = 24
    f.brain.request(); f.tick(); f.brain.confirm_start(); f.tick(); f.tick()
    f.tick(True); f.tick(False)
    for _ in range(300):
        f.tick()
        if f.brain.session is None: break
    project = f.s.executive.projects()[f.brain.project_id]
    assert project['status'] == 'candidate'
    assert project['originator'] == 'Reflection' and f.brain.generated_candidate
    assert f.s.requests()  # A candidate is not a qualified capability.
    assert f.s.repository.active()['calibration_id'] == PROFILE['calibration_id']


def test_actual_normal_main_runs_calibration_and_resumes_tracking(integrated, monkeypatch):
    import runpy
    import hardware.rp2040_controller
    import motion.controller
    import vision.detector
    f = integrated
    camera = SimpleNamespace(read=f.frame, close=lambda: None)
    f.s.request('uncertain', dict(reason='simulated normal-brain calibration request'))
    monkeypatch.setitem(sys.modules, 'vision.camera', SimpleNamespace(Camera=lambda: camera))
    monkeypatch.setattr(hardware.rp2040_controller, 'RP2040Controller', lambda: f.host)
    monkeypatch.setattr(motion.controller, 'RP2040Controller', lambda: f.host)
    f.host.close = lambda: None
    monkeypatch.setattr(CalibrationService, 'open', classmethod(lambda cls, *args: f.s))
    attach = f.s.attach_brain
    monkeypatch.setattr(f.s, 'attach_brain', lambda **options: attach(**options, simulated=True, maximum_steps=8))
    bus_ref = []
    monkeypatch.setitem(sys.modules, 'stimulus.keyboard', SimpleNamespace(KeyboardStimulus=lambda bus: bus_ref.append(bus)))
    monkeypatch.setattr(vision.detector, 'ColorDetector', lambda **options:
        SimpleNamespace(detect=lambda frame: dict(x=460, y=180, width=10, height=10)
                        if f.s.brain.session is None and f.s.brain.responses else None))
    monkeypatch.setenv('CHARLIE_NECK_MOTION_AUTHORIZED', '1')
    monkeypatch.setenv('CHARLIE_NECK_SUPERVISED', '1')
    ticks = [0]
    class EndApplication(BaseException): pass
    def sleep(_):
        ticks[0] += 1
        brain = f.s.brain
        if brain.last_state == 'VERIFY_INITIAL': bus_ref[0].emit('confirm_neck_start')
        state = f.a.calibration.state
        # One supervised contact at the first prepared increment only.
        f.b.pressed[0] = state == 'PREPARED' and ticks[0] < 9
        for _ in range(5): f.b.now[0] += 20; f.a.update()
        if brain.tracking_pending is not None and brain.session is None:
            raise EndApplication()
        if ticks[0] > 150: pytest.fail('normal application failed to complete calibration')
    monkeypatch.setattr('time.sleep', sleep)
    with pytest.raises(EndApplication):
        runpy.run_path(str(Path(__file__).resolve().parents[1]/'main.py'), run_name='__main__')
    assert len(f.s.brain.responses) >= 4
    assert any(e['kind'] == 'normal_resumed' for e in f.a.calibration.events)
    assert not f.a.status()['armed']  # Normal application finally sends STOP.


def test_background_estimator_rejects_uniform_scene_and_local_target_motion():
    observer = SceneResponse()
    blank = np.zeros((360, 480, 3), dtype=np.uint8)
    assert not observer.compare(observer.snapshot(blank), observer.snapshot(blank))['reliable']
    rng = np.random.default_rng(1)
    texture = rng.integers(0, 255, blank.shape, dtype=np.uint8)
    shifted = cv2.warpAffine(texture, np.float32([[1, 0, 3], [0, 1, -2]]), (480, 360))
    result = observer.compare(observer.snapshot(texture), observer.snapshot(shifted))
    assert result['reliable'] and result['displacement'] == pytest.approx([3, -2], abs=.1)
    patch = blank.copy(); patch[20:80, 20:80] = texture[20:80, 20:80]
    moved = cv2.warpAffine(patch, np.float32([[1, 0, 3], [0, 1, -2]]), (480, 360))
    assert not observer.compare(observer.snapshot(patch), observer.snapshot(moved))['reliable']


def test_candidate_preserves_powered_review_and_reference_pixel_units(integrated):
    f = integrated
    f.a.calibration.envelope.observation_size = [960, 720]
    f.brain.maximum_steps = 24
    f.brain.request(); f.tick(); f.brain.confirm_start(); f.tick(); f.tick()
    f.tick(True); f.tick(False)
    for _ in range(300):
        f.tick()
        if f.brain.session is None: break
    assert not f.brain.blocked and f.brain.generated_candidate
    candidate = json.loads(next((f.root/'profiles').glob('*_candidate.json')).read_text())
    assert candidate['powered_start_review'] == f.profile['powered_start_review']
    assert candidate['observation_size'] == [960, 720]
    assert candidate['visual_response']['pan'] == pytest.approx([8, 0], abs=.3)
    assert candidate['visual_response']['tilt'] == pytest.approx([0, 8], abs=.3)
    evidence = f.brain.responses[0]['evidence']
    assert evidence['reference_size'] == [960, 720]
    assert evidence['raw_displacement'] != evidence['displacement']


def test_retained_closure_evidence_failure_stops_and_restores_sink(integrated, monkeypatch):
    f = integrated
    sink = object()
    closed = []
    fake = SimpleNamespace(poll=lambda: dict(state='CLOSED', run_id='fake_closed'),
        close=lambda: pytest.fail('qualified closure should not request another CAL operation'),
        previous_sink=sink, evidence=SimpleNamespace(path=f.root/'fake.jsonl', close=lambda: closed.append(True)))
    f.s.session = fake
    monkeypatch.setattr(f.host, 'motion_status', lambda: dict(armed=True, profile_invalid=False,
        envelope=dict(independently_qualified=True), owner=None, moving=False))
    stops = []
    monkeypatch.setattr(f.host, 'stop', lambda: stops.append(True))
    monkeypatch.setattr(f.s, 'event', lambda *args, **kwargs: (_ for _ in ()).throw(OSError('disk full')))
    with pytest.raises(OSError, match='disk full'):
        f.s.close_session(retain_qualified=True)
    assert stops and closed and f.host.calibration_sink is sink


@pytest.mark.parametrize('loss', ['camera', 'telemetry'])
def test_normal_observation_loss_revokes_without_retry(integrated, monkeypatch, loss):
    f = integrated
    stops = []
    monkeypatch.setattr(f.host, 'stop', lambda: stops.append(True))
    if loss == 'camera':
        f.brain.update(None)
    else:
        monkeypatch.setattr(f.host, 'motion_status', lambda: None)
        f.brain.update(f.frame())
    assert f.brain.blocked and stops and not f.b.pwms
    for _ in range(5): f.brain.update(f.frame())
    assert len(stops) == 1


@pytest.mark.parametrize('failure', ['camera', 'detector'])
def test_normal_application_startup_failure_releases_transport_and_camera(integrated, monkeypatch, failure):
    import runpy
    import hardware.rp2040_controller
    import motion.controller
    import vision.detector
    f = integrated
    calls = []
    def unavailable(*args, **kwargs): raise RuntimeError('injected startup failure')
    camera = SimpleNamespace(read=f.frame, close=lambda: calls.append('camera closed'))
    monkeypatch.setitem(sys.modules, 'vision.camera', SimpleNamespace(
        Camera=unavailable if failure == 'camera' else lambda: camera))
    monkeypatch.setattr(hardware.rp2040_controller, 'RP2040Controller', lambda: f.host)
    monkeypatch.setattr(motion.controller, 'RP2040Controller', lambda: f.host)
    monkeypatch.setattr(f.host, 'close', lambda: calls.append('transport closed'))
    monkeypatch.setattr(f.host, 'stop', lambda: calls.append('STOP'))
    monkeypatch.setattr(CalibrationService, 'open', classmethod(lambda cls, *args: f.s))
    monkeypatch.setitem(sys.modules, 'stimulus.keyboard', SimpleNamespace(KeyboardStimulus=lambda bus: None))
    monkeypatch.setenv('CHARLIE_VISION_TARGET', 'face')
    monkeypatch.setattr(vision.detector, 'FaceDetector', unavailable)
    with pytest.raises(RuntimeError, match='startup failure'):
        runpy.run_path(str(Path(__file__).resolve().parents[1]/'main.py'), run_name='__main__')
    assert calls[-2:] == ['STOP', 'transport closed']
    assert ('camera closed' in calls) is (failure == 'detector')
