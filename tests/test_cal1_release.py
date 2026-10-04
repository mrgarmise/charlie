"""Cohesive deployment exercised against fake Pico storage/services only."""
import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace
import pytest
from tools.update_charlie import Cal1Release, UpdateError

ROOT = Path(__file__).resolve().parents[1]
SHA = 'f'*40


@pytest.fixture
def release(tmp_path, monkeypatch):
    checkout = tmp_path/'existing-pi-stage'
    (checkout/'.venv/bin').mkdir(parents=True)
    (checkout/'.venv/bin/python').write_text('fake interpreter')
    updater = Cal1Release(checkout, SHA)
    updater.root = tmp_path/'persistent'
    updater.release = updater.root/'releases'/SHA
    updater.backup = updater.root/'deployment-history'/SHA
    updater.dropin = tmp_path/'systemd/charlie.service.d/cal1-release.conf'
    files = {p.name: b'FAKE prior installed '+p.name.encode() for p in (ROOT/'rp2040').glob('*.py')}
    files.update({'profiles/activation.json': b'FAKE immutable physical metadata',
                  'cal1/charlie_cal1_004.jsonl': b'FAKE preserved commissioning failure',
                  'lib/Pico_ed.py': b'FAKE installed vendor display support'})
    original = files.copy()
    calls = []
    fail = [False]
    controls = dict(active=True, acknowledge=True, manifest_failure=False)
    class Pico:
        def require(self): calls.append(('mpremote', 'require'))
        def run(self, *args):
            calls.append(args)
            if args[0] == 'exec':
                assert 'machine' not in args[1]
                if controls['manifest_failure']:
                    raise OSError('injected snapshot failure')
                return SimpleNamespace(stdout=json.dumps({n: hashlib.sha256(raw).hexdigest() for n, raw in files.items()}))
            if args[:2] == ('fs', 'cp'):
                Path(args[3]).write_bytes(files[args[2][1:]])
                return SimpleNamespace(stdout='')
            raise AssertionError(args)
        def copy(self, source, destination):
            if fail[0] and source.name == 'servos.py':
                fail[0] = False
                raise OSError('injected partial upload failure')
            calls.append(('copy', source.name, destination))
            files[destination[1:]] = source.read_bytes()
        def reset(self): calls.append(('mpremote', 'reset'))
        def remove(self, path):
            calls.append(('remove', path))
            del files[path[1:]]
    pico = Pico()
    import tools.mpremote_helper
    monkeypatch.setattr(tools.mpremote_helper, 'MpRemote', lambda: pico)
    import hardware.rp2040_controller
    monkeypatch.setattr(hardware.rp2040_controller, 'RP2040Controller', lambda:
        SimpleNamespace(connected=True, _accepted=lambda command, name: calls.append(('UART', command)) or controls['acknowledge'],
                        close=lambda: calls.append(('UART', 'closed'))))
    def command(*args):
        calls.append(args)
        if args[:4] == ('sudo', 'systemctl', 'is-active', '--quiet'):
            assert updater.dropin.exists()
        if args[:2] == ('sudo', 'cp'):
            target = Path(args[3]); target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(args[2], args[3])
        if args[:3] == ('sudo', 'rm', '-f'):
            assert args[3] == str(updater.dropin)
            updater.dropin.unlink(missing_ok=True)
        return SimpleNamespace(stdout='', returncode=0)
    def git(*args):
        calls.append(('git', *args))
        if args[:2] == ('worktree', 'add'):
            updater.release.mkdir(parents=True)
            shutil.copytree(ROOT/'rp2040', updater.release/'rp2040')
            (updater.release/'main.py').write_text((ROOT/'main.py').read_text())
        return ''
    monkeypatch.setattr(updater, 'run_command', command)
    monkeypatch.setattr(updater, 'git', git)
    monkeypatch.setattr('tools.update_charlie.subprocess.run', lambda *args, **kwargs:
        SimpleNamespace(stdout='FAKE existing charlie normal service',
                        returncode=0 if 'cat' in args[0] or controls['active'] else 3))
    return SimpleNamespace(u=updater, pico=pico, calls=calls, files=files, original=original,
                           fail=fail, controls=controls)


def test_single_release_preserves_installed_configuration_evidence_and_support(release):
    f = release
    f.u.deploy()
    for name, raw in f.original.items():
        if name in f.u.PRESERVE or '/' in name:
            assert f.files[name] == raw
    copies = [c for c in f.calls if c[0] == 'copy']
    assert copies[-1][1] == 'main.py'
    assert not set(f.u.PRESERVE) & {c[1] for c in copies}
    assert ('UART', 'STOP') in f.calls
    assert all((f.u.backup/'pico'/name).read_bytes() == raw for name, raw in f.original.items())
    assert 'CHARLIE_NECK_MOTION_AUTHORIZED=0' in f.u.dropin.read_text()
    assert 'main.py' in f.u.dropin.read_text()


def test_partial_upload_rolls_back_automatically_without_erasing_evidence(release):
    f = release
    f.fail[0] = True
    with pytest.raises(OSError, match='partial upload'):
        f.u.deploy()
    assert all(f.files[name] == raw for name, raw in f.original.items())
    assert not f.u.dropin.exists()
    assert ('sudo', 'systemctl', 'start', 'charlie') in f.calls


def test_dry_run_never_touches_git_uart_files_or_services(release, capsys):
    f = release
    f.u.dry_run = True
    f.u.deploy()
    assert not f.calls and not f.u.release.exists() and not f.u.backup.exists()
    assert json.loads(capsys.readouterr().out)['physical_motion_authorized'] is False


def test_release_requires_exact_published_revision(tmp_path):
    for value in ('feature/active-vision', 'f5bc395', '../malicious', 'f'*40+'\n'):
        with pytest.raises(UpdateError): Cal1Release(tmp_path, value)


def test_rollback_removes_only_new_application_files_after_partial_upload(release):
    f = release
    del f.files['calibration.py']; del f.original['calibration.py']
    f.fail[0] = True
    with pytest.raises(OSError, match='partial upload'):
        f.u.deploy()
    assert f.files == f.original
    assert ('remove', ':calibration.py') in f.calls


@pytest.mark.parametrize('active', [True, False])
@pytest.mark.parametrize('failure', ['acknowledge', 'manifest_failure', 'missing_config', 'partial_upload'])
def test_failed_maintenance_restores_original_service_activity(release, active, failure):
    f = release
    f.controls['active'] = active
    if failure == 'acknowledge': f.controls['acknowledge'] = False
    if failure == 'manifest_failure': f.controls['manifest_failure'] = True
    if failure == 'missing_config':
        del f.files['config.py']; del f.original['config.py']
    if failure == 'partial_upload': f.fail[0] = True
    with pytest.raises((OSError, UpdateError)):
        f.u.deploy()
    assert (('sudo', 'systemctl', 'start', 'charlie') in f.calls) is active
    assert f.files == f.original


def test_service_authority_off_survives_inherited_environment_files(release):
    text = release.u.service_text()
    start = next(line for line in text.splitlines() if line.startswith('ExecStart=/'))
    assert start.startswith('ExecStart=/usr/bin/env CHARLIE_NECK_MOTION_AUTHORIZED=0 CHARLIE_NECK_SUPERVISED=0 ')
