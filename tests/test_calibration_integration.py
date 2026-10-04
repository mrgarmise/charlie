"""Reusable CAL-1 integration, with fake UART, clocks, cameras and PWM only."""
import copy
import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_active_vision_firmware import board, load, PROFILE, transport
from test_neck_calibration import commissioning
from hardware.calibration_service import CalibrationService
from hardware.neck_calibration import ProfileRepository
from memory.evidence import EvidenceJournal
from memory.learning_projects import LearningExecutive


@pytest.fixture
def service(tmp_path):
    status = dict(pan=90, tilt=90, moving=False, armed=False, pwm_active=False,
                  owner=None, envelope=dict(calibration_id='SIMULATED_001'))
    calls = []
    host = SimpleNamespace(motion_status=lambda: status,
        stop=lambda: calls.append('STOP'), neck_uncertain=lambda: calls.append('NECK_UNCERTAIN'))
    journal = EvidenceJournal(tmp_path / 'requests.sqlite3')
    executive = LearningExecutive(journal, SimpleNamespace(remember=lambda _: None))
    repo = ProfileRepository(tmp_path / 'profiles')
    now = [0.0]
    adapter = CalibrationService(host, repo, journal, executive, clock=lambda: now[0])
    yield SimpleNamespace(s=adapter, repo=repo, j=journal, e=executive,
                          host=host, status=status, calls=calls, now=now, root=tmp_path)
    adapter.close()


def qualify_fake(f, name='SIMULATED_001', supersedes=()):
    profile = copy.deepcopy(PROFILE)
    profile.update(calibration_id=name, supersedes=list(supersedes))
    f.repo.save(profile)
    f.repo.activate(name)
    return profile


@pytest.mark.parametrize('reason', sorted(CalibrationService.REASONS))
def test_executive_requests_are_durable_discoverable_and_not_authority(service, reason):
    f = service
    rid = f.e.request_neck_calibration(f.s, reason, dict(diagnostic='fake preserved evidence'))
    assert rid in f.e.pending_neck_calibrations(f.s)
    assert f.s.request(reason, dict(diagnostic='more evidence')) == rid
    assert f.s.requests()[rid]['latest_evidence']['diagnostic'] == 'more evidence'
    assert not f.calls
    selected = f.e.select(methods=['supervised_neck_recalibration'], resources=[], authorized_methods=[])
    assert selected['project'] is None and selected['alternatives'][0]['blocked']
    second = EvidenceJournal(f.j.path)
    recovered = CalibrationService(f.host, f.repo, second)
    assert recovered.requests()[rid]['physical_authorization'] is False
    assert recovered.requests()[rid]['evidence']['diagnostic'] == 'fake preserved evidence'
    recovered.close()


def test_missing_invalid_quarantined_and_incompatible_profiles_request_without_activation(service):
    f = service
    assert f.s.refresh() is None
    assert next(iter(f.s.requests().values()))['reason'] == 'missing'
    qualify_fake(f)
    assert f.s.refresh()['calibration_id'] == 'SIMULATED_001'
    f.repo.quarantine('SIMULATED_001', 'fake fault', dict(observed=True))
    assert f.s.refresh() is None
    assert any(r['reason'] == 'quarantined' for r in f.s.requests().values())
    # Corrupt activation and quarantine are retained, never repaired or cleared.
    (f.repo.directory / 'activation.json').write_text('{')
    assert f.s.refresh() is None
    assert any(r['reason'] == 'invalid' for r in f.s.requests().values())
    assert (f.repo.directory / 'SIMULATED_001.quarantine.json').exists()
    assert not f.calls


def test_actual_incompatible_profile_is_identified_and_preserved(service):
    import hashlib
    f = service
    qualify_fake(f)
    path = f.repo.directory / 'SIMULATED_001.json'
    profile = json.loads(path.read_text())
    profile['hardware']['head_a'] = [14, 15]
    raw = json.dumps(profile).encode()
    path.write_bytes(raw)  # Inject corruption in test fixture, never production migration.
    pointer = json.loads((f.repo.directory / 'activation.json').read_text())
    pointer['sha256'] = hashlib.sha256(raw).hexdigest()
    (f.repo.directory / 'activation.json').write_text(json.dumps(pointer))
    assert f.s.refresh() is None
    assert any(r['reason'] == 'incompatible' for r in f.s.requests().values())
    assert path.read_bytes() == raw and not f.calls


def test_profile_pointer_cannot_alias_a_different_qualified_identity(service):
    import hashlib
    f = service
    qualify_fake(f)
    path = f.repo.directory / 'SIMULATED_001.json'
    profile = json.loads(path.read_text())
    profile['calibration_id'] = 'SIMULATED_002'
    raw = json.dumps(profile).encode()
    path.write_bytes(raw)
    pointer = json.loads((f.repo.directory / 'activation.json').read_text())
    pointer['sha256'] = hashlib.sha256(raw).hexdigest()
    (f.repo.directory / 'activation.json').write_text(json.dumps(pointer))
    with pytest.raises(ValueError, match='identifier mismatch'): f.repo.active()
    with pytest.raises(ValueError, match='identifier mismatch'): f.repo.activate('SIMULATED_001')
    assert f.s.refresh() is None and path.read_bytes() == raw


@pytest.mark.parametrize('document', [None, [], 'invalid'])
def test_nonobject_profile_documents_are_invalid_requests_and_never_authority(service, document):
    import hashlib
    f = service
    qualify_fake(f)
    raw = json.dumps(document).encode()
    (f.repo.directory / 'SIMULATED_001.json').write_bytes(raw)
    pointer = json.loads((f.repo.directory / 'activation.json').read_text())
    pointer['sha256'] = hashlib.sha256(raw).hexdigest()
    (f.repo.directory / 'activation.json').write_text(json.dumps(pointer))
    assert f.s.refresh() is None
    assert f.s.requests() and not f.calls


def test_request_listing_and_unauthorized_console_never_open_uart(service, monkeypatch, capsys):
    from tools.calibrate_neck import main
    import hardware.rp2040_controller
    f = service
    rid = f.s.request('missing', dict(reason='fake absent profile'))
    monkeypatch.setattr(hardware.rp2040_controller, 'RP2040Controller',
                        lambda *a, **kw: pytest.fail('UART must not open'))
    monkeypatch.setattr(sys, 'argv', ['calibrate_neck', '--state-directory', str(f.root), '--list-requests'])
    main()
    assert rid in json.loads(capsys.readouterr().out)
    monkeypatch.setattr(sys, 'argv', ['calibrate_neck', '--state-directory', str(f.root)])
    with pytest.raises(SystemExit) as error: main()
    assert error.value.code == 2
    assert not f.calls


def test_installed_console_uses_durable_requests_and_reenters_without_flash(board, tmp_path, monkeypatch):
    import io
    from tools.calibrate_neck import main
    import hardware.rp2040_controller
    host, authority, _ = transport(board)
    authority.calibration = sys.modules['calibration'].Calibration(authority, commissioning(),
        lambda: board.pressed[0], sink=lambda event: print('CAL_EVENT', json.dumps(event)))
    host.close = lambda: None  # Fake transport stays installed across console restarts.
    monkeypatch.setattr(hardware.rp2040_controller, 'RP2040Controller', lambda *a: host)
    def open_service(cls, controller, directory):
        return cls(controller, ProfileRepository(directory / 'profiles'),
                   EvidenceJournal(directory / 'requests.sqlite3'))
    monkeypatch.setattr(CalibrationService, 'open', classmethod(open_service))
    monkeypatch.setattr('tools.calibrate_neck.select.select', lambda *args: ([sys.stdin], [], []))
    initial = CalibrationService.open(None, tmp_path)
    rid = initial.request('missing', dict(reason='fake calibration absent'))
    initial.close()
    proof = dict(operator='operator_001', evidence='evidence_001', pose_verified=True,
        pulse_mapping_verified=True, clearance_verified=True, cutoff_verified=True, external_power_off=True)
    for n in range(2):
        run = f'console_run_{n:03d}'
        ops = [dict(op='begin', run_id=run), dict(op='verify', run_id=run, pose=[90, 90], **proof),
               dict(op='finish', run_id=run)]
        monkeypatch.setattr(sys, 'stdin', io.StringIO('\n'.join(json.dumps(op) for op in ops) + '\n'))
        monkeypatch.setattr(sys, 'argv', ['calibrate_neck', '--state-directory', str(tmp_path),
            '--request-id', rid, '--evidence', str(tmp_path / f'console-{n}.jsonl'),
            '--authorize-supervised-calibration'])
        main()  # Everything behind the console is simulated; no GPIO/UART device.
        assert authority.calibration.state == 'CLOSED' and not board.pwms
    recovered = CalibrationService.open(None, tmp_path)
    assert rid in recovered.requests()
    assert len(list(tmp_path.glob('console-*.jsonl'))) == 2
    recovered.close()


def test_executive_recovers_request_committed_before_reflection(service):
    f = service
    f.s.executive = None  # Simulate interruption before Executive publication.
    rid = f.s.request('missing', dict(error='profile absent'))
    assert not f.e.projects()
    recovered = CalibrationService(f.host, f.repo, f.j, f.e)
    assert any(p['scope']['request_id'] == rid for p in f.e.projects().values())
    again = CalibrationService(f.host, f.repo, f.j, f.e)
    assert len(f.e.projects()) == 1 and rid in again.requests()


def test_dismissal_is_explicit_persistent_and_does_not_clear_quarantine(service):
    f = service
    f.s.refresh()
    rid = next(iter(f.s.requests()))
    with pytest.raises(ValueError): f.s.dismiss(rid, actor='', reason='ignore', evidence='')
    f.s.dismiss(rid, actor='operator', reason='neck disconnected', evidence='inspection_record')
    assert not f.s.requests()
    f.s.refresh()
    assert not f.s.requests()  # Same diagnostic does not undo explicit dismissal.
    assert f.s.requests(pending_only=False)[rid]['status'] == 'dismissed'
    assert all(p['status'] == 'abandoned' for p in f.e.projects().values())
    assert not f.calls


def test_session_evidence_does_not_resolve_request_only_new_qualified_profile_can(service):
    f = service
    qualify_fake(f)
    rid = f.s.request('degraded', dict(observed='fake drift'), profile_id='SIMULATED_001')
    with pytest.raises(ValueError): f.s.resolve(rid, evidence='session_finished')
    f.repo.quarantine('SIMULATED_001', 'drift', dict(observed=True))
    qualify_fake(f, 'SIMULATED_002', ['SIMULATED_001'])
    f.s.resolve(rid, evidence='fake independent qualification and external activation')
    assert f.s.requests(pending_only=False)[rid]['status'] == 'resolved'
    assert all(p['status'] == 'superseded' for p in f.e.projects().values())
    assert (f.repo.directory / 'SIMULATED_001.quarantine.json').exists()
    rid2 = f.s.request('degraded', dict(observed='new drift'), profile_id='SIMULATED_002')
    assert rid2 != rid and rid2 in f.s.requests()
    assert not f.calls


@pytest.mark.parametrize('fault', ['moving', 'pose_change', 'nonfinite', 'owner', 'mismatch', 'invalid', 'disconnected'])
def test_primary_telemetry_uncertainty_revokes_and_persists_request(service, fault):
    f = service
    qualify_fake(f)
    corners = [[0, 0], [100, 0], [100, 100], [0, 100]]
    f.s.observe_primary(corners, telemetry=f.status)
    f.now[0] += 1
    if fault == 'moving': f.status['moving'] = True
    elif fault == 'pose_change': f.status['pan'] = 90.5
    elif fault == 'nonfinite': f.status['pan'] = float('nan')
    elif fault == 'owner': f.status['owner'] = 'ACTIVE_VISION'
    elif fault == 'mismatch': f.status['envelope']['calibration_id'] = 'OTHER_PROFILE'
    elif fault == 'invalid': f.status['profile_invalid'] = True
    else: f.host.motion_status = lambda: None
    f.s.observe_primary(corners)
    assert f.calls == ['NECK_UNCERTAIN', 'STOP']
    assert (f.repo.directory / 'SIMULATED_001.quarantine.json').exists()
    assert any(r['reason'] == 'degraded' for r in f.s.requests().values())
    evidence = [r.data['payload']['report'] for r in f.j.records('event')
                if r.data['payload'].get('op') == 'health_observation']
    assert all(r['mechanical_fault_confirmed'] is False for r in evidence)
    assert any(r.get('alternatives') for r in evidence)


def test_tracking_loss_without_energized_neck_does_not_diagnose_fault(service):
    f = service
    qualify_fake(f)
    for _ in range(5):
        f.s.observe_primary(None, visual_tracking_available=False)
        f.now[0] += 1
    assert not f.calls and not f.s.requests()
    f.status['pwm_active'] = True
    for _ in range(3):
        f.s.observe_primary(None)
        f.now[0] += 1
    assert f.calls == ['NECK_UNCERTAIN', 'STOP']
    assert f.s.health.quarantined


def test_primary_fixed_reference_shift_uses_existing_monitor_and_expected_transitions(service):
    f = service
    qualify_fake(f)
    corners = [[0, 0], [100, 0], [100, 100], [0, 100]]
    shifted = [[x + 40, y] for x, y in corners]
    f.s.observe_primary(corners)
    f.now[0] += 1
    f.s.observe_primary(shifted, expected_transition=True)
    assert not f.calls
    shifted = [[x + 40, y] for x, y in shifted]
    for _ in range(3):
        f.now[0] += 1
        f.s.observe_primary(shifted)
    assert f.s.health.quarantined and f.calls == ['NECK_UNCERTAIN', 'STOP']


def test_shared_camera_and_detector_are_not_duplicated(service):
    from experiments.ppal.observation_camera import ObservedCamera
    from vision.stimulus import VisionStimulus
    from motion.controller import Deck
    f = service
    qualify_fake(f)
    reads, detects, events = [], [], []
    camera = SimpleNamespace(read=lambda: reads.append(1) or 'same_frame')
    wrapped = ObservedCamera(camera, neck_service=f.s)
    assert wrapped.read() == 'same_frame'
    assert len(reads) == 1
    deck = Deck(body=f.host, calibration=f.s)
    detector = SimpleNamespace(detect=lambda frame: detects.append(frame) or dict(x=2, y=3))
    bus = SimpleNamespace(emit=lambda *event: events.append(event))
    stimulus = VisionStimulus(camera, detector, bus, neck_observer=deck.observe_neck)
    stimulus.update()
    assert len(reads) == 2 and detects == ['same_frame']
    assert events == [('vision_target', (2, 3))]
    assert not f.calls


def test_normal_pi_main_keeps_idle_camera_and_request_lifecycle(service, monkeypatch):
    import motion.controller
    import vision.detector
    f = service
    calls = []
    f.host.display = lambda state: calls.append(('display', state))
    f.host.close = lambda: calls.append(('body', 'closed'))
    monkeypatch.setattr(motion.controller, 'RP2040Controller', lambda: f.host)
    monkeypatch.setattr(CalibrationService, 'open', classmethod(lambda cls, body, directory: f.s))
    monkeypatch.setattr(f.s, 'close', lambda: calls.append(('service', 'closed')))
    camera = SimpleNamespace(read=lambda: calls.append(('camera', 'read')) or 'frame',
                             close=lambda: calls.append(('camera', 'closed')))
    monkeypatch.setitem(sys.modules, 'vision.camera', SimpleNamespace(Camera=lambda: camera))
    monkeypatch.setitem(sys.modules, 'stimulus.keyboard', SimpleNamespace(KeyboardStimulus=lambda bus: None))
    monkeypatch.setattr(vision.detector, 'ColorDetector', lambda **kw: SimpleNamespace(detect=lambda frame: None))
    ticks = []
    class Finished(Exception): pass
    def sleep(seconds):
        ticks.append(seconds)
        if len(ticks) == 3: raise Finished()
    monkeypatch.setattr('time.sleep', sleep)
    with pytest.raises(Finished):
        runpy.run_path(str(Path(__file__).resolve().parents[1] / 'main.py'))
    assert calls.count(('camera', 'read')) == 3
    assert ('display', 'IDLE') in calls
    assert ('camera', 'closed') in calls and ('body', 'closed') in calls
    assert any(r['reason'] == 'missing' for r in f.s.requests().values())
    assert f.calls == ['STOP']  # Normal application shutdown remains fail closed.
    f.j.close()


def test_supervisor_temporarily_owns_monitor_without_adding_camera_owner(service):
    f = service
    f.s.session = object()  # An explicit supervisor is active.
    assert f.s.observe_primary() is None and not f.calls and not f.s.requests()
    f.s.session = None


def test_primary_evidence_failure_revokes_even_without_a_durable_diagnostic(service, monkeypatch):
    f = service
    monkeypatch.setattr(f.j, 'append', lambda *args, **kw: (_ for _ in ()).throw(OSError('disk full')))
    with pytest.raises(OSError, match='disk full'): f.s.observe_primary()
    assert f.calls == ['NECK_UNCERTAIN', 'STOP']


def test_repeated_supervised_sessions_use_same_installed_controller_and_preserve_logs(board, tmp_path):
    host, authority, behavior = transport(board)
    authority.calibration = sys.modules['calibration'].Calibration(authority, commissioning(),
        lambda: board.pressed[0], sink=lambda event: print('CAL_EVENT', json.dumps(event)))
    journal = EvidenceJournal(tmp_path / 'requests.sqlite3')
    service = CalibrationService(host, ProfileRepository(tmp_path / 'profiles'), journal)
    rid = service.request('missing', dict(reason='fake commissioning'))
    proof = dict(operator='operator_001', evidence='evidence_001', pose_verified=True,
                 pulse_mapping_verified=True, clearance_verified=True, cutoff_verified=True,
                 external_power_off=True, supervised=True, no_binding=True, settled=True)
    def tick(contact=False, count=5):
        board.pressed[0] = contact
        for _ in range(count): board.now[0] += 20; authority.update()
    for n in range(25):
        path = tmp_path / f'run-{n:02d}.jsonl'
        supervisor = service.supervised_session(rid, path, simulated=True)
        run = f'calibration_{n:03d}'
        def request(op, **kw):
            return supervisor.request(dict(op=op, run_id=run, **kw))
        assert request('begin')['state'] == 'VERIFY_INITIAL'
        tick()
        request('verify', pose=[90, 90], **proof)
        request('prepare', pose=[90.5, 90], step_id='cal_step_001', rate=1, **proof)
        tick(True); tick(False); tick(False, 30)
        assert supervisor.poll()['state'] == 'AWAIT_CONFIRMATION'
        request('confirm', step_id='cal_step_001', visual_displacement=[2, 0], **proof)
        assert request('finish')['state'] == 'CLOSED'
        service.close_session()
        assert not authority.status()['pwm_active']
        records = [json.loads(line) for line in path.read_text().splitlines()]
        firmware = [r['event'] for r in records if 'seq' in r['event']]
        assert firmware[0]['seq'] == 1 and any(e['kind'] == 'finished' for e in firmware)
        assert all(e['run_id'] == run for e in firmware)
        assert authority.calibration.status()['event_count'] < 20
    assert rid in service.requests()  # Completion is not independent qualification.
    assert all(p.pin in (4, 5) and p.disabled for p in board.pwms)
    assert len(list(tmp_path.glob('run-*.jsonl'))) == 25
    service.close()


@pytest.mark.parametrize('failure', ['status', 'evidence'])
def test_supervisor_close_failure_still_stops_and_restores_sink(tmp_path, failure):
    from hardware.neck_calibration import SupervisedCalibration, CalibrationJournal
    calls = []
    host = SimpleNamespace(calibration_sink='old', stop=lambda: calls.append('STOP'),
        _exchange=lambda *args: None if failure == 'status' else
        'CAL_STATUS {"state":"ABORTED","run_id":null}')
    evidence = CalibrationJournal(tmp_path / 'failure.jsonl', simulated=True)
    session = SupervisedCalibration(host, evidence)
    if failure == 'evidence':
        evidence.append = lambda _: (_ for _ in ()).throw(OSError('disk full'))
    with pytest.raises(ConnectionError if failure == 'status' else OSError): session.close()
    assert calls == ['STOP'] and host.calibration_sink == 'old'
    evidence.close()


def test_real_rp2040_main_scheduler_keeps_normal_commands_and_never_constructs_pwm(board, monkeypatch, capsys):
    instances, display_calls = [], []
    base = board.module.ServoController
    class Controller(base):
        def __init__(self, **kw):
            super().__init__(clock=lambda: board.now[0], **kw)
            instances.append(self)
    board.module.ServoController = Controller
    for name in ('scanner', 'behaviors', 'commands'):
        monkeypatch.setitem(sys.modules, name, load('main_' + name, 'rp2040/' + name + '.py'))
    class Display:
        NO_BRAIN = 'NO_BRAIN'; THINK = 'THINK'
        def __getattr__(self, name):
            return lambda *args: display_calls.append((name, args))
    monkeypatch.setitem(sys.modules, 'display', SimpleNamespace(Display=Display))
    monkeypatch.setitem(sys.modules, 'heartbeat', SimpleNamespace(
        Heartbeat=lambda: SimpleNamespace(alive=lambda: True, beat=lambda: None)))
    lines = iter(['PING\n', 'THINK\n', 'PROGRESS 42\n', 'MESSAGE CAL1 ready\n',
                  'SESSION session_1234\n', 'CAL session_1234 1 {"op":"begin","run_id":"run_0001"}\n'])
    monkeypatch.setattr(sys, 'stdin', SimpleNamespace(readline=lambda: next(lines)))
    monkeypatch.setitem(sys.modules, 'select', SimpleNamespace(POLLIN=1,
        poll=lambda: SimpleNamespace(register=lambda *args: None, poll=lambda _: True)))
    sleeps = []
    class Finished(Exception): pass
    def sleep(ms):
        sleeps.append(ms)
        if len(sleeps) == 6: raise Finished()
    monkeypatch.setattr('time.sleep_ms', sleep, raising=False)
    with pytest.raises(Finished):
        runpy.run_path(str(Path(__file__).resolve().parents[1] / 'rp2040/main.py'))
    output = capsys.readouterr().out
    assert 'READY' in output and 'ALIVE' in output and 'OK THINK' in output
    assert 'OK PROGRESS' in output and 'OK MESSAGE' in output
    assert 'CALIBRATION_PREREQUISITES_REQUIRED' in output
    assert len(instances) == 1 and not board.pwms
    assert any(name == 'update' for name, _ in display_calls)
    assert instances[0].calibration.state == 'DISABLED'


def test_application_upgrade_is_additive_and_shipped_gates_stay_false(board):
    from tools.sync_rp2040 import Synchronizer, RP2040_DIR
    copies = []
    sync = Synchronizer.__new__(Synchronizer)
    sync.mp = SimpleNamespace(copy=lambda source, target: copies.append((source.name, target)))
    sync.synchronize_application()  # Fake destination only; no hardware calls.
    names = {name for name, _ in copies}
    assert {'main.py', 'commands.py', 'servos.py', 'calibration.py', 'behaviors.py',
            'display.py', 'heartbeat.py', 'protocol.py', 'profile_store.py'} <= names
    assert len(copies) == len(list(RP2040_DIR.glob('*.py')))
    assert copies[-1] == ('main.py', ':main.py')
    profile = board.profile
    assert profile.CALIBRATED_ENVELOPE is None and profile.CALIBRATION_PROFILE is None
    assert profile.LOCAL_ARM_PIN is None and profile.PERSISTENT_PROFILE_DIRECTORY is None
    assert not profile.ELECTRICAL_GATE_CLEARED and not profile.CALIBRATION_INPUT_ENABLED
    assert not profile.AUTONOMOUS_MOTION_ENABLED
