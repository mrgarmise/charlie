#!/usr/bin/env python3
"""
Charlie system updater.

Performs:

    • git pull
    • synchronize RP2040
    • restart Charlie service

Future versions will detect whether the RP2040 changed,
perform dependency updates, and run diagnostics.
"""

from __future__ import annotations

import subprocess
import sys
import argparse
import getpass
import hashlib
import json
import re
from pathlib import Path

from tools.sync_rp2040 import Synchronizer


CHARLIE_SERVICE = "charlie"


class UpdateError(RuntimeError):
    pass


class CharlieUpdater:

    def run_command(self, *cmd: str) -> subprocess.CompletedProcess:

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise UpdateError(result.stderr.strip())

        return result

    def git_pull(self):

        print()
        print("Updating repository...")

        result = self.run_command(
            "git",
            "pull",
        )

        print(result.stdout.strip())

    def sync_rp2040(self):

        print()
        print("Synchronizing Raspberry Pi Pico...")

        Synchronizer().run()

    def restart_charlie(self):

        print()
        print("Restarting Charlie service...")

        self.run_command(
            "sudo",
            "systemctl",
            "restart",
            CHARLIE_SERVICE,
        )

        print("Charlie restarted.")

    def update(self):

        print("=" * 50)
        print("Charlie Updater")
        print("=" * 50)

        self.git_pull()

        self.sync_rp2040()

        self.restart_charlie()

        print()
        print("Update complete.")


class Cal1Release(CharlieUpdater):
    """One pinned Pi/Pico upgrade, preserving installed hardware configuration.

    No firmware gate is granted. Rollback snapshots and integrity checks are
    automatic. The service starts Charlie's normal application with motion
    authorization false; this command is not commissioning.
    """
    PRESERVE = {'motion_profile.py', 'config.py', 'boot.py', 'test_rp2040.py'}

    def __init__(self, checkout, revision, *, dry_run=False):
        self.checkout = Path(checkout).resolve()
        if not re.fullmatch('[0-9a-f]{40}', revision):
            raise UpdateError('A full published 40-character commit SHA is required')
        self.revision, self.dry_run = revision, dry_run
        self.root = Path.home()/'.local/share/charlie'
        self.release = self.root/'releases'/revision
        self.backup = self.root/'deployment-history'/revision
        self.python = self.checkout/'.venv/bin/python'
        self.dropin = Path('/etc/systemd/system/charlie.service.d/cal1-release.conf')
        self.created_service = False

    def git(self, *arguments):
        return self.run_command('git', '-C', str(self.checkout), *arguments).stdout.strip()

    def plan(self):
        return dict(revision=self.revision, checkout=str(self.checkout),
            release=str(self.release), normal_application='main.py',
            preserved=sorted(self.PRESERVE), preserves_pico_profiles_and_libraries=True,
            physical_motion_authorized=False, service='charlie.service',
            automatic_snapshot=str(self.backup), dry_run=self.dry_run)

    def pico_manifest(self, mp):
        # File reads only, inside maintenance raw REPL. No machine imports.
        script = """import os, json
try:
    import uhashlib as hashlib
except ImportError:
    import hashlib
files = {}
def walk(directory):
    for name in os.listdir(directory):
        path = directory.rstrip('/') + '/' + name
        if os.stat(path)[0] & 0x4000:
            walk(path)
        else:
            with open(path, 'rb') as stream:
                files[path.lstrip('/')] = hashlib.sha256(stream.read()).digest().hex()
walk('/')
print(json.dumps(files))
"""
        result = mp.run('exec', script)
        manifest = json.loads(result.stdout.strip())
        if not isinstance(manifest, dict) or any(
            Path(name).is_absolute() or '..' in Path(name).parts or ':' in name
            or not re.fullmatch('[0-9a-f]{64}', digest) for name, digest in manifest.items()):
            raise UpdateError('Invalid Pico filesystem manifest')
        return manifest

    def snapshot_pico(self, mp):
        manifest = self.pico_manifest(mp)
        destination = self.backup/'pico'
        destination.mkdir(parents=True, exist_ok=False)
        for name, expected in manifest.items():
            local = destination/name; local.parent.mkdir(parents=True, exist_ok=True)
            mp.run('fs', 'cp', ':'+name, str(local))
            if hashlib.sha256(local.read_bytes()).hexdigest() != expected:
                raise UpdateError('Pico snapshot mismatch: '+name)
        (self.backup/'pico-manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2))
        return manifest

    def install_pico(self, mp):
        files = sorted((self.release/'rp2040').glob('*.py'), key=lambda p: (p.name == 'main.py', p.name))
        expected = {}
        for source in files:
            if source.name in self.PRESERVE:
                continue
            mp.copy(source, ':'+source.name)
            expected[source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
        actual = self.pico_manifest(mp)
        if any(actual.get(name) != digest for name, digest in expected.items()):
            raise UpdateError('Pico release integrity check failed')
        before = json.loads((self.backup/'pico-manifest.json').read_text())
        preserved = {name: digest for name, digest in before.items() if name not in expected}
        if any(actual.get(name) != digest for name, digest in preserved.items()):
            raise UpdateError('An unrelated Pico file or persistent profile changed')
        mp.reset()

    def service_text(self):
        for path in (self.release, self.python, self.root):
            if any(c in str(path) for c in ('\n', '\r', '"', '%', '\\')):
                raise UpdateError('Unsupported service path')
        return ('[Service]\nType=simple\n'
            'WorkingDirectory='+str(self.release)+'\nExecStart=\n'
            'ExecStart="'+str(self.python)+'" -u "'+str(self.release/'main.py')+'"\n'
            'Environment="CHARLIE_NECK_STATE='+str(self.root/'neck')+'"\n'
            'Environment="CHARLIE_NECK_MOTION_AUTHORIZED=0"\n'
            'Environment="CHARLIE_NECK_SUPERVISED=0"\n'
            'Environment="CHARLIE_VISION_TARGET=face"\n')

    def rollback(self, mp, manifest, had_dropin, *, existing_service=True):
        for name in sorted(manifest, key=lambda p: (p == 'main.py', p)):
            if '/' not in name and name.endswith('.py') and name not in self.PRESERVE:
                mp.copy(self.backup/'pico'/name, ':'+name)
        actual = self.pico_manifest(mp)
        if any(actual.get(name) != digest for name, digest in manifest.items()):
            raise UpdateError('Automatic rollback could not verify restored Pico files; service remains stopped')
        mp.reset()
        if had_dropin:
            self.run_command('sudo', 'cp', str(self.backup/'previous-service.conf'), str(self.dropin))
        else:
            self.run_command('sudo', 'rm', '-f', str(self.dropin))
        if self.created_service:
            self.run_command('sudo', 'rm', '-f', '/etc/systemd/system/charlie.service')
        self.run_command('sudo', 'systemctl', 'daemon-reload')
        if existing_service:
            self.run_command('sudo', 'systemctl', 'start', 'charlie')

    def deploy(self):
        if self.dry_run:
            print(json.dumps(self.plan(), indent=2))
            return  # No git mutation, hardware, sudo, or service access.
        if not self.python.exists():
            raise UpdateError('Existing Pi virtual environment is missing: '+str(self.python))
        self.git('fetch', 'origin', 'feature/active-vision')
        self.git('merge-base', '--is-ancestor', self.revision, 'origin/feature/active-vision')
        self.release.parent.mkdir(parents=True, exist_ok=True)
        if self.release.exists():
            raise UpdateError('Pinned release already exists; refusing to overwrite it')
        self.git('worktree', 'add', '--detach', str(self.release), self.revision)
        self.run_command(str(self.python), '-m', 'compileall', '-q', str(self.release))
        self.run_command(str(self.python), '-c',
            'import cv2, numpy, serial, picamera2; print("Pi application dependencies ready")')
        from tools.mpremote_helper import MpRemote
        mp = MpRemote(); mp.require()
        self.backup.mkdir(parents=True, exist_ok=False)
        existing = subprocess.run(['sudo', 'systemctl', 'cat', 'charlie'], capture_output=True, text=True)
        had_dropin = self.dropin.exists()
        if had_dropin:
            self.run_command('sudo', 'cp', str(self.dropin), str(self.backup/'previous-service.conf'))
        (self.backup/'service-before.txt').write_text(existing.stdout)
        if existing.returncode == 0:
            self.run_command('sudo', 'systemctl', 'stop', 'charlie')
        # Same Pi transport sends STOP before raw-REPL maintenance; no probing
        # movements or replacement calibration application is installed.
        from hardware.rp2040_controller import RP2040Controller
        body = RP2040Controller()
        try:
            if not body.connected or not body._accepted('STOP', 'STOP'):
                raise UpdateError('Pico did not acknowledge maintenance STOP')
        finally:
            body.close()
        try:
            manifest = self.snapshot_pico(mp)
        except Exception:
            mp.reset()
            if existing.returncode == 0:
                self.run_command('sudo', 'systemctl', 'start', 'charlie')
            raise
        if not {'motion_profile.py', 'config.py', 'main.py'} <= manifest.keys():
            raise UpdateError('Installed normal Pico configuration is missing; not reconstructing hardware assumptions')
        try:
            self.install_pico(mp)
            if existing.returncode != 0:
                unit = self.backup/'charlie.service'
                unit.write_text('[Unit]\nDescription=Charlie normal brain\nAfter=multi-user.target\n'
                    '[Service]\nUser='+getpass.getuser()+'\nRestart=on-failure\nRestartSec=3\n'
                    '[Install]\nWantedBy=multi-user.target\n')
                self.run_command('sudo', 'cp', str(unit), '/etc/systemd/system/charlie.service')
                self.created_service = True
            config = self.backup/'release-service.conf'; config.write_text(self.service_text())
            self.run_command('sudo', 'mkdir', '-p', str(self.dropin.parent))
            self.run_command('sudo', 'cp', str(config), str(self.dropin))
            self.run_command('sudo', 'systemctl', 'daemon-reload')
            self.run_command('sudo', 'systemctl', 'enable', '--now', 'charlie')
            self.run_command('sudo', 'systemctl', 'is-active', '--quiet', 'charlie')
        except Exception:
            self.run_command('sudo', 'systemctl', 'stop', 'charlie')
            self.rollback(mp, manifest, had_dropin, existing_service=existing.returncode == 0)
            raise
        (self.backup/'release.json').write_text(json.dumps(self.plan(), indent=2))
        print('Charlie normal brain started at '+self.revision+'. Motion authorization is off.')


def main():
    parser = argparse.ArgumentParser(description='Update Charlie normal Pi/Pico applications')
    parser.add_argument('--cal1-release')
    parser.add_argument('--checkout', default=str(Path.cwd()))
    parser.add_argument('--dry-run', action='store_true')
    options = parser.parse_args()

    try:

        if options.cal1_release:
            Cal1Release(options.checkout, options.cal1_release, dry_run=options.dry_run).deploy()
        else:
            if options.dry_run:
                parser.error('--dry-run requires --cal1-release')
            CharlieUpdater().update()

    except (UpdateError, RuntimeError) as exc:

        print()
        print(f"ERROR: {exc}")

        sys.exit(1)


if __name__ == "__main__":
    main()
