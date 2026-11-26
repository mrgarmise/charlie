"""Offline checks for local owner approval; no native devices are opened."""
import stat

import pytest

from tools.runtime_adoption import stationary as s
from tools.runtime_adoption import supervised_release as release


@pytest.fixture
def owner(tmp_path, monkeypatch):
    ctl = s.Stationary(tmp_path)
    ctl.review.mkdir(parents=True)
    (ctl.ops / 'logs').mkdir()
    ctl.normal.write_text('original launcher')
    monkeypatch.setattr(release, 'foreground', lambda: None)
    binding = dict(scope=release.SCOPE, qualification_log=str(tmp_path / 'qualification.log'),
                   hardware={'pico': 'verified'}, boot='boot-a')
    monkeypatch.setattr(release, 'bindings', lambda ctl, log: dict(binding))
    return ctl, binding


def test_explicit_local_approval_and_per_session_isolation(owner, monkeypatch):
    ctl, binding = owner
    answer = iter(['no', 'APPROVE SUPERVISED BATCH A', 'no', 'MOTION POWER ISOLATED'])
    monkeypatch.setattr('builtins.input', lambda _: next(answer))
    approval = ctl.review / release.APPROVAL
    with pytest.raises(ValueError, match='declined'):
        release.approve(ctl, binding['qualification_log'])
    assert not approval.exists()
    release.approve(ctl, binding['qualification_log'])
    assert stat.S_IMODE(approval.stat().st_mode) == 0o600
    with pytest.raises(ValueError, match='already exists'):
        release.approve(ctl, binding['qualification_log'])
    with pytest.raises(ValueError, match='isolation not confirmed'):
        release.admit(ctl)
    assert release.admit(ctl) == s.sha(approval)
    assert ctl.normal.read_text() == 'original launcher'
    assert not (ctl.review / 'release.json').exists()


def test_changed_boot_and_failed_session_deny_restart(owner, monkeypatch):
    ctl, binding = owner
    monkeypatch.setattr('builtins.input', lambda _: 'APPROVE SUPERVISED BATCH A')
    release.approve(ctl, binding['qualification_log'])
    decision = s.sha(ctl.review / release.APPROVAL)
    binding['boot'] = 'boot-b'
    with pytest.raises(ValueError, match='binding changed'):
        release.admit(ctl)
    with pytest.raises(RuntimeError):
        with s.session_guard(ctl, {s.A}, owner_approval=decision):
            raise RuntimeError('interrupted')
    with pytest.raises(FileExistsError):
        with s.session_guard(ctl, {s.A}, owner_approval=decision):
            pytest.fail('interrupted approval may not retry')


def test_supervised_cli_requires_narrow_scope(owner, monkeypatch):
    ctl, _ = owner
    monkeypatch.setattr(s.Path, 'home', lambda: ctl.home)
    monkeypatch.setattr(s, 'ORIGINAL', s.sha(ctl.normal))
    with pytest.raises(ValueError, match='limited to Batch A'):
        s.main(['supervised-launch', s.B])
    with pytest.raises(ValueError, match='required only'):
        s.main(['supervised-approve'])
    with pytest.raises(FileNotFoundError):
        s.main(['supervised-launch'])
    assert ctl.normal.read_text() == 'original launcher'


def test_exact_qualification_requires_observational_stop(tmp_path, monkeypatch):
    import json
    import sqlite3

    ctl = s.Stationary(tmp_path)
    for name in ('state', 'batch-a-state'):
        state = ctl.ops / name
        state.mkdir(parents=True)
        with sqlite3.connect(state / 'learning-evidence.sqlite3') as db:
            db.execute('CREATE TABLE example (id INTEGER)')
    logs = ctl.ops / 'logs'
    logs.mkdir()
    log = logs / 'stationary-qualification-1.log'
    identity = dict(candidate=s.CANDIDATE, motion_authorized=False, controller_sha='head',
                    controller_tree='tree', original_launcher=s.ORIGINAL, boot='boot')
    header = 'BEGIN QUALIFICATION ' + json.dumps(identity) + '\n'
    monkeypatch.setattr(s, 'selection', lambda _: set())
    monkeypatch.setattr(s, 'qualification_preflight', lambda *_: None)
    monkeypatch.setattr(ctl, 'bindings', lambda: dict(
        controller_sha='head', controller_tree='tree', boot_id='boot', hef_sha256='model',
        logs={'guarded_session': {'clean_shutdown_logged': True}}))
    monkeypatch.setattr(s, 'evidence', lambda *_: dict(clean_shutdown_logged=True, sha256=s.sha(log)))
    monkeypatch.setattr(release, 'hardware_identity', lambda: {'board': 'fixture'})
    monkeypatch.setattr(release, 'artifacts', lambda _: {'n0': 'fixture'})

    log.write_text(header)
    with pytest.raises(ValueError, match='observational STOP missing'):
        release.bindings(ctl, log)
    log.write_text(header + 'STATIONARY STOP REQUESTED: recognition shutdown; motion not authorized\n')
    with pytest.raises(ValueError, match='regular evidence'):
        release.bindings(ctl, log)
    log.with_suffix('.cleanup.json').write_text(json.dumps(dict(
        log_sha256=s.sha(log), idle_and_device_guards_passed=True)))
    assert release.bindings(ctl, log)['qualification_sha256'] == s.sha(log)
    identity['boot'] = 'stale'
    log.write_text('BEGIN QUALIFICATION ' + json.dumps(identity) + '\n')
    with pytest.raises(ValueError, match='another build, boot or scope'):
        release.bindings(ctl, log)
