"""Offline tests only. No device, operator key, review receipt or real state is used."""
import hashlib
import json
import os
import subprocess

import pytest
from tools.runtime_adoption import stationary as s


@pytest.fixture
def host(tmp_path, monkeypatch):
    ctl = s.Stationary(tmp_path)
    ctl.fallback.parent.mkdir(parents=True)
    (ctl.ops / 'logs').mkdir()
    for p in (ctl.normal, ctl.fallback):
        p.write_bytes(b'#!/bin/sh\nexit 0\n')
    monkeypatch.setattr(s, 'ORIGINAL', s.sha(ctl.normal))
    state = ctl.ops / 'batch-a-state'
    state.mkdir()
    (state / 'existing').write_bytes(b'preserve me')
    return ctl


def test_add_remove_and_restore_preserve_history(host):
    original = host.normal.read_bytes()
    for before, after in [(set(), {s.A}), ({s.A}, {s.A, s.B}), ({s.A, s.B}, {s.A}), ({s.A}, set())]:
        with s.locked(host.ops):
            host.switch(before, after)
        assert s.selection(host.normal) == after
        assert (host.ops / 'batch-a-state/existing').read_bytes() == b'preserve me'
    assert host.normal.read_bytes() == original
    assert len(list((host.ops / 'logs').glob('*.json'))) == 4


def test_busy_lock_denies_second_process(host):
    with s.locked(host.ops):
        p = subprocess.run(['flock', '-n', str(host.ops / 'runtime.lock'), 'true'])
    assert p.returncode == 1
    assert s.selection(host.normal) == set()


def test_interrupted_transaction_retains_original(host, monkeypatch):
    def failed(*args):
        raise OSError('injected rename failure')
    monkeypatch.setattr(os, 'replace', failed)
    with pytest.raises(OSError):
        host.switch(set(), {s.A})
    assert s.selection(host.normal) == set()
    assert sorted(p.name for p in host.ops.glob('tmp*')) == []


def test_drift_refuses_overwrite(host):
    host.normal.write_text('unexpected bytes')
    with pytest.raises(ValueError):
        host.switch(set(), {s.A})
    assert host.normal.read_text() == 'unexpected bytes'


@pytest.mark.parametrize('selection', [set(), {s.B}, {s.A, 'pr-10'}, {'motion'}])
def test_no_other_profiles(selection):
    with pytest.raises(ValueError):
        s.template(selection)


@pytest.mark.parametrize('flags', [['--hardware'], ['--pet-follow'], ['--native-meditation'],
                                   ['--mobile-dashboard'], ['--llm-consultation'], ['pr-10']])
def test_generated_normal_launcher_rejects_arguments(host, flags):
    host.normal.write_bytes(s.template({s.A}))
    assert subprocess.run(['sh', str(host.normal), *flags]).returncode == 64


def test_candidate_or_review_absent_cannot_enable(host, monkeypatch):
    monkeypatch.setattr(s.Path, 'home', lambda: host.home)
    with pytest.raises(ValueError):
        s.main(['enable', s.A])
    assert s.selection(host.normal) == set()


@pytest.mark.parametrize('selected', [set(), {s.A}, {s.A, s.B}])
def test_native_qualification_requires_original_launcher(host, monkeypatch, selected):
    """The unsigned qualification path must never run after a cutover."""
    monkeypatch.setattr(host, 'preserved', lambda: None)
    monkeypatch.setattr(s.socket, 'gethostname', lambda: 'charlie')
    host.home = s.Path('/home/five')
    if selected:
        host.normal.write_bytes(s.template(selected))
    monkeypatch.setattr(s, 'idle_guard', lambda: None)
    monkeypatch.setattr(s, 'device_guard', lambda: None)
    monkeypatch.setattr(host, 'lineage', lambda: 'existing-history')
    host.models.parent.mkdir(exist_ok=True)
    host.models.write_text(json.dumps({'objects': {'path': 'test-model.hef', 'sha256': '0'*64}}))
    host.new.mkdir()
    (host.new / 'test-model.hef').write_bytes(b'offline test model')
    if selected:
        with pytest.raises(ValueError, match='unchanged original normal launcher'):
            s.qualification_preflight(host, selected)
    else:
        # Refuse a mismatched model before any hardware activity.
        monkeypatch.setattr(host, 'preserved', lambda: None)
        monkeypatch.setattr(s, 'sha', lambda path: s.ORIGINAL if path == host.normal else '1'*64)
        with pytest.raises(ValueError, match='reviewed Hailo model changed'):
            s.qualification_preflight(host, set())


def test_native_qualification_refuses_existing_approval_or_arguments(host, monkeypatch):
    monkeypatch.setattr(s.Path, 'home', lambda: host.home)
    # The CLI cannot select any ability during unsigned native qualification.
    with pytest.raises(ValueError, match='qualification takes no ability selection'):
        s.main(['qualify-native', s.A])
    assert s.selection(host.normal) == set()


def test_prepare_review_creates_only_unsigned_pending_drafts(host, monkeypatch):
    from tools.runtime_adoption import stationary_packet_prepare as drafts
    monkeypatch.setattr(host, 'preserved', lambda: None)
    monkeypatch.setattr(drafts, 'ORIGINAL', s.sha(host.normal))
    monkeypatch.setattr(drafts, 'git', lambda *a: '' if 'status' in a else 'a' * 40)
    host.models.parent.mkdir(parents=True)
    host.models.write_text(json.dumps({'objects': {'sha256': 'f' * 64}}))
    approved = host.normal.read_bytes()
    result = drafts.prepare(host)
    assert result['status'] == 'UNSIGNED_DRAFT_ONLY'
    assert result['normal_runtime_changed'] is False
    assert result['approval_issued'] is False
    assert result['validated_native_sessions'] == 0
    assert host.normal.read_bytes() == approved
    assert not (host.review / 'inputs.json').exists()
    assert not (host.review / 'ci.json').exists()
    assert not (host.review / 'release.json').exists()
    parent = s.Path(result['directory'])
    assert all((parent / ('draft-' + name + '.json')).is_file() for name in s.SCOPES[s.A])
    assert all(json.loads((parent / ('draft-' + name + '.json')).read_text())['status'] == 'pending'
               for name in s.SCOPES[s.A])
    assert all(json.loads((parent / ('draft-' + name + '.json')).read_text())['independent_review'] is False
               for name in s.SCOPES[s.A])


def test_prepare_review_refuses_after_cutover_without_packet(host, monkeypatch):
    from tools.runtime_adoption import stationary_packet_prepare as drafts
    monkeypatch.setattr(host, 'preserved', lambda: None)
    host.normal.write_bytes(s.template({s.A}))
    with pytest.raises(ValueError, match='unchanged original normal launcher'):
        drafts.prepare(host)
    assert not (host.review / 'drafts').exists()


def test_prepare_review_cli_rejects_capability_arguments(host, monkeypatch):
    monkeypatch.setattr(s.Path, 'home', lambda: host.home)
    with pytest.raises(ValueError, match='review preparation takes no ability arguments'):
        s.main(['prepare-review', s.A])
    assert not (host.review / 'drafts').exists()


def test_stationary_x_emits_stop_and_reports_it(capsys):
    from tools.runtime_adoption.stationary_boundary import install_stationary_stop
    from stimulus.keyboard import KeyboardStimulus
    from stimulus.bus import StimulusBus
    original = KeyboardStimulus.emergency_stop
    restore = install_stationary_stop(KeyboardStimulus)
    try:
        bus = StimulusBus()
        keyboard = KeyboardStimulus.__new__(KeyboardStimulus)
        keyboard.object_mode = True
        keyboard.bus = bus
        keyboard.on_emergency = None
        keyboard.emergency_stop()
        assert [event for event, _ in bus.get_all()] == [
            'emergency_stop', 'object_recognition_stop']
        assert 'STATIONARY STOP REQUESTED' in capsys.readouterr().out
    finally:
        restore()
    assert KeyboardStimulus.emergency_stop is original


def test_stationary_stop_wrapper_does_not_change_other_keyboard_modes():
    from tools.runtime_adoption.stationary_boundary import install_stationary_stop
    from stimulus.keyboard import KeyboardStimulus
    from stimulus.bus import StimulusBus
    restore = install_stationary_stop(KeyboardStimulus)
    try:
        bus = StimulusBus()
        keyboard = KeyboardStimulus.__new__(KeyboardStimulus)
        keyboard.object_mode = False
        keyboard.bus = bus
        keyboard.on_emergency = None
        keyboard.emergency_stop()
        assert [event for event, _ in bus.get_all()] == ['emergency_stop']
    finally:
        restore()


def test_bounded_logger_normal_shutdown(tmp_path):
    log = tmp_path / 'session.log'
    with log.open('wb') as out:
        with s.bounded_log_tee(out) as tee:
            tee.stdin.write(b'hello qualifying log\\n')
            tee.stdin.flush()
            tee.stdin.close()
        assert tee.returncode == 0
    assert log.read_bytes() == b'hello qualifying log\\n'


def test_bounded_logger_kills_stuck_tee_without_indefinite_wait(tmp_path, monkeypatch):
    """An inherited writer must not permanently block qualification cleanup."""
    import subprocess as sp
    events = []
    class FakeInput:
        closed = False
        def close(self):
            self.closed = True
            events.append('close')
    class FakeTee:
        def __init__(self):
            self.stdin = FakeInput()
            self.returncode = None
        def wait(self, timeout):
            events.append(('wait', timeout))
            if self.returncode is None:
                raise sp.TimeoutExpired('tee', timeout)
            return self.returncode
        def terminate(self):
            events.append('terminate')
            self.returncode = -15
        def kill(self):
            raise AssertionError('terminate should suffice')
    fake = FakeTee()
    monkeypatch.setattr(s.subprocess, 'Popen', lambda *a, **k: fake)
    with (tmp_path / 'log').open('wb') as out:
        with s.bounded_log_tee(out):
            pass
    assert events == ['close', ('wait', 5), 'terminate', ('wait', 2)]


def test_complete_log_allows_bounded_tee_cleanup(tmp_path, monkeypatch, capsys):
    import signal
    from types import SimpleNamespace
    model = 'a' * 64
    log = tmp_path / 'complete.log'
    log.write_text('Development operational: clean shutdown | shutdown requested\\n'
                   'END stationary exit=0\\n')
    monkeypatch.setattr(s, 'evidence', lambda path, expected, digest: {
        'clean_shutdown_logged': True, 'observations': 32
    } if path == log and expected is None and digest == model else None)
    tee = SimpleNamespace(returncode=-signal.SIGTERM, charlie_forced_cleanup=True)
    assert s.verified_log_exit(tee, log, model)['observations'] == 32
    assert 'bounded termination' in capsys.readouterr().err


def test_incomplete_log_never_passes_even_after_forced_cleanup(tmp_path):
    import signal
    from types import SimpleNamespace
    log = tmp_path / 'incomplete.log'
    log.write_text('Development operational: clean shutdown\\n')
    tee = SimpleNamespace(returncode=-signal.SIGTERM, charlie_forced_cleanup=True)
    import pytest
    with pytest.raises(Exception):
        s.verified_log_exit(tee, log, 'a' * 64)


def test_unexpected_logger_failure_never_passes(tmp_path):
    from types import SimpleNamespace
    import pytest
    tee = SimpleNamespace(returncode=1, charlie_forced_cleanup=False)
    with pytest.raises(Exception):
        s.verified_log_exit(tee, tmp_path / 'absent.log', 'a' * 64)


def test_offline_status_reports_unknown_host_without_mutation(tmp_path):
    ctl = s.Stationary(tmp_path)
    result = ctl.inspect()
    assert result['selected'] is None and result['launch_verified'] is False
    assert all(v['status'] == 'PENDING' for v in result['checks'].values())
    assert list(tmp_path.iterdir()) == []


def row():
    return dict(observation=dict(schema='charlie.object-observation.v1', source='elegoo-v4', frame_id=1),
                provenance=dict(frame=dict(source='elegoo-v4', id=1), software_revision=s.CANDIDATE['sha'],
                                motion_authorized=False, model=[dict(sha256='a'*64, backend='hailort-hef')]),
                motion_authorized=False)


@pytest.mark.parametrize('fault', ['none', 'source', 'revision', 'motion', 'model', 'repeat', 'exit'])
def test_log_import_reads_observations(tmp_path, fault):
    r = row()
    if fault == 'source':
        r['observation']['source'] = 'pi-primary'
    if fault == 'revision':
        r['provenance']['software_revision'] = '0'*40
    if fault == 'motion':
        r['provenance']['motion_authorized'] = True
    if fault == 'model':
        r['provenance']['model'][0]['sha256'] = 'b'*64
    entries = [json.dumps(r)] * (2 if fault == 'repeat' else 1)
    entries += ['Development operational: clean shutdown', 'END stationary exit=' + ('1' if fault == 'exit' else '0')]
    path = tmp_path / 'log'
    path.write_text('\n'.join(entries))
    if fault == 'none':
        report = s.evidence(path, 1, 'a'*64)
        assert report['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert report['clean_shutdown_logged'] and report['pico_ack'] == 'unverified'
    else:
        with pytest.raises(ValueError):
            s.evidence(path, 1, 'a'*64)



@pytest.mark.parametrize('exit_bytes', [b'0', b'0\n'])
def test_historical_qualification_accepts_separate_zero_exit(tmp_path, monkeypatch, exit_bytes):
    """The old foreground launcher did not append END to session.log."""
    log = tmp_path / 'session.log'
    exit_file = tmp_path / 'exit-code.txt'
    exit_file.write_bytes(exit_bytes)
    # A historical session must contain the expected number of unique observations.
    entries = []
    for i in range(229):
        observation = row()
        observation['observation']['frame_id'] = i
        observation['provenance']['frame']['id'] = i
        entries.append(json.dumps(observation))
    entries.extend(['Development operational: clean shutdown | shutdown requested',
                    'Development: stopped | no project'])
    log.write_text('\n'.join(entries) + '\n')
    monkeypatch.setattr(s, 'FIRST', s.sha(log))
    result = s.evidence(log, 229, 'a'*64, historical_exit=exit_file)
    assert result['observations'] == 229
    assert result['clean_shutdown_logged'] is True
    assert result['exit_code_sha256'] == s.sha(exit_file)
    with pytest.raises(ValueError, match='missing successful session end'):
        s.evidence(log, 229, 'a'*64)


@pytest.mark.parametrize('fault', ['missing', 'nonzero', 'symlink', 'modified_log', 'no_shutdown'])
def test_historical_exit_rejects_invalid_evidence(tmp_path, monkeypatch, fault):
    entries = []
    for i in range(229):
        observation = row()
        observation['observation']['frame_id'] = i
        observation['provenance']['frame']['id'] = i
        entries.append(json.dumps(observation))
    if fault != 'no_shutdown':
        entries.append('Development operational: clean shutdown | shutdown requested')
    log = tmp_path / 'session.log'
    log.write_text('\n'.join(entries) + '\n')
    monkeypatch.setattr(s, 'FIRST', s.sha(log))
    exit_file = tmp_path / 'exit-code.txt'
    if fault == 'symlink':
        actual = tmp_path / 'real-exit.txt'
        actual.write_text('0\n')
        exit_file.symlink_to(actual)
    elif fault != 'missing':
        exit_file.write_text('1\n' if fault == 'nonzero' else '0\n')
    if fault == 'modified_log':
        log.write_text(log.read_text() + 'Modified\n')
    with pytest.raises((ValueError, FileNotFoundError)):
        s.evidence(log, 229, 'a'*64, historical_exit=exit_file)


def test_no_historical_exit_override_on_operational_log(tmp_path, monkeypatch):
    log = tmp_path / 'session.log'
    log.write_text(json.dumps(row()) + '\nDevelopment operational: clean shutdown\n')
    exit_file = tmp_path / 'exit-code.txt'
    exit_file.write_text('0\n')
    monkeypatch.setattr(s, 'FIRST', 'f'*64)
    with pytest.raises(ValueError, match='historical exit record is only valid'):
        s.evidence(log, 1, 'a'*64, historical_exit=exit_file)


@pytest.mark.parametrize('character,returncode,stderr', [(False, 1, b''), (True, 0, b''), (True, 1, b'permission denied')])
def test_device_conflict_and_failed_inspection_refuse(character, returncode, stderr, monkeypatch):
    monkeypatch.setattr(s.Path, 'is_char_device', lambda self: character)
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess([], returncode, b'', stderr))
    with pytest.raises(ValueError):
        s.device_guard()


def test_existing_manual_guard_sources_match_approved_receipt():
    from tools.runtime_adoption.inventory import manual_guards
    record = s.load(s.ROOT / 'docs/runtime-adoption/evidence/approved-baseline.json')
    assert manual_guards(s.ROOT) == record['manual_llm_guards']


def test_restore_rehearsal_preserves_both_notebooks_and_catches_divergence(host, monkeypatch):
    from memory.evidence import EvidenceJournal
    from tools.runtime_adoption.stationary_restore import rehearse
    monkeypatch.setattr(host, 'preserved', lambda: None)
    for name in ('state', 'batch-a-state'):
        journal = EvidenceJournal(host.ops / name / 'learning-evidence.sqlite3')
        journal.append('observation', {'value': 1}, episode='test', producer='test', version='v1')
        journal.close()
    assert host.lineage()
    host.models.parent.mkdir()
    host.models.write_text('{}')
    for name in ('approved.sha', 'QUALIFICATION.md', 'run-historical-consultation.py',
                 'batch-a-operator-pin.sha', 'start-stationary-batch-a.sh'):
        (host.ops / name).write_text('test only')
    result = rehearse(host, host.ops / 'rehearsal')
    assert result['isolated_restore_verified'] and result['independent_review'] is False
    assert len(result['backup_manifests']) == 3
    journal = EvidenceJournal(host.ops / 'state/learning-evidence.sqlite3')
    journal.append('observation', {'value': 2}, episode='test', producer='test', version='v1')
    journal.close()
    with pytest.raises(ValueError, match='omits approved history'):
        host.lineage()


@pytest.mark.parametrize('raw,allowed', [(b'STOP\n', True), (b'PING\n', True), (b'DISPLAY_CAPS\n', True),
    (b'OBJECT_LABEL 4500 100 CAT\n', True), (b'OBJECT_LABEL 4500 100 CAT\nHOME\n', False),
    (b'OBJECT_LABEL 99999 100 CAT\n', False), (b'HOME\n', False), (b'SCAN\n', False),
    (b'MEDITATION_NOTICE x\n', False), (b'VIEWPOINT\n', False)])
def test_display_wire_allowlist(raw, allowed):
    from tools.runtime_adoption.stationary_boundary import display_write
    assert display_write(raw) == allowed


def test_no_control_endpoint_redirect_listener_or_worker_network():
    import socket
    from types import SimpleNamespace
    from tools.runtime_adoption.stationary_boundary import transport_policy
    url = 'http://127.0.0.1:81/stream'
    guard = transport_policy(url)
    sock = SimpleNamespace(family=socket.AF_INET, type=socket.SOCK_STREAM)
    guard('urllib.Request', (url, None, {}, 'GET'))
    guard('socket.connect', (sock, ('127.0.0.1', 81)))
    for event, args in [('urllib.Request', (url, b'move', {}, 'POST')),
                        ('urllib.Request', (url + '?cmd=control', None, {}, 'GET')),
                        ('socket.connect', (sock, ('127.0.0.1', 11434))),
                        ('socket.bind', (sock, ('127.0.0.1', 80)))]:
        with pytest.raises(PermissionError):
            guard(event, args)
    with pytest.raises(PermissionError):
        transport_policy(None)('socket.connect', (sock, ('127.0.0.1', 81)))


def test_interrupted_native_session_requires_review_and_keeps_rollback_available(host):
    host.review.mkdir()
    grant = host.review / (s.A + '.json')
    grant.write_text('offline fixture')
    host.switch(set(), {s.A})
    with pytest.raises(InterruptedError):
        with s.session_guard(host, {s.A}):
            raise InterruptedError('injected interruption')
    with pytest.raises(FileExistsError):
        with s.session_guard(host, {s.A}):
            pytest.fail('same decision admitted a second session')
    host.switch({s.A}, set())
    assert s.selection(host.normal) == set()


def test_completed_health_check_releases_session_hold(host):
    host.review.mkdir()
    (host.review / (s.A + '.json')).write_text('offline fixture')
    for _ in range(2):
        with s.session_guard(host, {s.A}):
            assert len(list((host.ops / 'logs').glob('stationary-incomplete-*'))) == 1
    assert not list((host.ops / 'logs').glob('stationary-incomplete-*'))


def test_request_and_two_stage_validation_bind_every_original_artifact(host, monkeypatch):
    """Exercise packet generation and validation together, substituting only host and trust services."""
    import time
    from tools.runtime_adoption import promotion, stationary_packet as packet
    from tools.runtime_adoption.inventory import digest, manual_guards
    host.review.mkdir()
    # All operational paths captured by the fixture remain in tmp_path.
    host.home = s.Path('/home/five')
    host.new = s.ROOT
    binding = dict(controller_sha='1'*40, controller_tree='2'*40,
                   logs={'guarded_session': {'clean_shutdown_logged': True}})
    monkeypatch.setattr(host, 'preserved', lambda: None)
    monkeypatch.setattr(host, 'bindings', lambda: binding)
    monkeypatch.setattr(s.socket, 'gethostname', lambda: 'charlie')
    monkeypatch.setattr(packet, 'git', lambda *args: binding['controller_sha'])
    guard = manual_guards(s.ROOT)

    def inventory(old, new, ops, protected):
        return dict(candidate={**s.CANDIDATE, 'dirty': False}, baseline={**s.BASELINE, 'dirty': False},
                    approvals={'approval_binding': True}, manual_llm_guards=dict(baseline=guard, candidate=guard),
                    protected=[digest(p) for p in protected])

    monkeypatch.setattr(packet, 'collect', inventory)
    monkeypatch.setattr(s, 'collect', inventory)
    monkeypatch.setattr(s, 'trusted_reviewer', lambda: ({'reviewer': 'fixture', 'sha256': '0'*64}, None))
    def inspect_review(approval, *, stage, abilities, candidate, **kwargs):
        record = approval['record']
        assert record['stage'] == stage and record['abilities'] == abilities
        assert candidate == s.CANDIDATE
        return record
    monkeypatch.setattr(promotion, 'verify_record', inspect_review)

    def save(path, data):
        path.write_text(json.dumps(data))
        return str(path)

    def output(name, data):
        return save(host.review / name, data)

    for name in ('approved.sha', 'QUALIFICATION.md', 'run-historical-consultation.py'):
        (host.ops / name).write_text('offline test')
    backup = s.Path(output('fixture-backup.json', {'files': []}))
    restore = output('restore.json', dict(status='passed', complete_scope_verified=True,
                     isolated_restore_verified=True, state_compatible=True, independent_review=True,
                     candidate=s.CANDIDATE, backup_manifests={str(backup): s.sha(backup)}, completed_at=time.time()))
    url = 'https://github.com/mrgarmise/charlie/actions/runs/1'
    output('controller-ci.json', dict(sha=binding['controller_sha'], tree=binding['controller_tree'],
           conclusion='success', url=url, completed_at=time.time()))
    suites = ['full', 'contracts', 'baseline-llm', 'browser', 'firmware-host', 'firmware-build', 'neural-cpu']
    output('ci.json', [dict(candidate=s.CANDIDATE, suite=suite, passed=1, failed=0, completed_at=time.time(),
           conclusion='success', artifact_sha256='1'*64, url=url) for suite in suites])
    measurement = s.Path(output('measurements.json', {'synthetic': True}))
    native = {}
    for gate in s.SCOPES[s.A]:
        native[gate] = output(gate + '.json', dict(ability=s.A, gate=gate, status='passed', candidate=s.CANDIDATE,
             controller_sha=binding['controller_sha'], independent_review=True, artifacts={str(measurement): s.sha(measurement)}))
    output('inputs.json', dict(restore_receipt=restore, backup_manifests=[str(backup)], gate_receipts={s.A: native}))
    for stage, sid in [('release', None), ('enablement', s.A)]:
        manifest = packet.proposal(host, sid)
        output(sid + '.manifest.json' if sid else 'manifest.json', manifest)
        output((sid or 'release') + '.json', dict(record=dict(stage=stage, abilities=[sid] if sid else [],
               reviewer='fixture', expires_at=time.time()+600,
               manifest_sha256=hashlib.sha256(promotion.canonical(manifest)).hexdigest())))
    host.validate({s.A})
    measurement.write_text('altered')
    with pytest.raises(ValueError, match='altered or missing protected evidence'):
        host.validate({s.A})
    assert s.selection(host.normal) == set()


def test_bootstrap_checks_pinned_controller_before_loading_python(tmp_path, monkeypatch):
    root = tmp_path / 'reviewed-controller'
    root.mkdir()
    def git(*args):
        subprocess.run(['git', '-C', str(root), '-c', 'user.name=Fixture',
                        '-c', 'user.email=fixture@example.invalid', *args], check=True, capture_output=True)
    git('init')
    file = root / 'source'
    file.write_text('reviewed')
    git('add', 'source')
    git('commit', '-m', 'fixture')
    monkeypatch.setattr(s, 'ROOT', root)
    launcher = tmp_path / 'start'
    launcher.write_bytes(s.template({s.A}))
    file.write_text('changed')
    failed = subprocess.run(['sh', str(launcher)], capture_output=True)
    assert failed.returncode == 1 and not failed.stderr
    git('commit', '-am', 'different controller')
    failed = subprocess.run(['sh', str(launcher)], capture_output=True)
    assert failed.returncode == 1 and not failed.stderr
