"""Candidate-specific extension of the signed stationary release procedure."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import sqlite3
from contextlib import closing
import subprocess
import sys
import time

from . import stationary as s
from .promotion import require, load
from .supervised_release import foreground, confirm_isolation

SHARED = 'stationary.shared_recognition.elegoo'
CANDIDATE = dict(sha='77eb7b180688e6c2bb3aa850a0c685f305a973ae',
                 tree='e089a68b8be1896da8c6d3a5c10c0e84668e8b51')


class SharedRelease(s.Stationary):
    candidate = CANDIDATE
    primary = SHARED
    scopes = {SHARED: ('N0', 'N1', 'N2', 'N5')}

    def __init__(self, home):
        super().__init__(home)
        self.legacy = s.Stationary(home)
        self.new = home / 'charlie-shared-candidate'
        self.review = self.ops / 'shared-stationary-review'
        self.state = self.ops / 'shared-stationary-state'

    def preserved(self):
        self.legacy.preserved()
        require(self.new.resolve() == self.new and
                s.git(self.new, 'rev-parse', 'HEAD') == self.candidate['sha'] and
                s.git(self.new, 'rev-parse', 'HEAD^{tree}') == self.candidate['tree'] and
                not s.git(self.new, 'status', '--porcelain', '--untracked-files=all'),
                'shared candidate checkout changed')

    def launcher(self):
        revision = s.git(s.ROOT, 'rev-parse', 'HEAD')
        script = ('set -eu\ncd ' + shlex.quote(str(s.ROOT)) +
                  '\n[ "$(/usr/bin/git rev-parse HEAD)" = ' + shlex.quote(revision) +
                  ' ]\n[ -z "$(/usr/bin/git -c core.fsmonitor=false status --porcelain --untracked-files=all)" ]' +
                  '\nexec /home/five/Projects/charlie/.venv/bin/python -IB tools/shared_stationary_ctl.py launch')
        return ('#!/bin/sh\nset -eu\n[ "$#" -eq 0 ] || exit 64\n'
                'exec /usr/bin/env -i HOME=/home/five PATH=/usr/bin:/bin /bin/sh -c ' +
                shlex.quote(script) + '\n').encode()

    def display(self):
        value = load(self.review / 'inputs.json')['display']
        require(value in ('off', 'rp2040'), 'unsupported stationary display')
        return value

    def bindings(self):
        require(self.state.resolve() == self.state, 'redirected shared notebook')
        notebook = self.state / 'learning-evidence.sqlite3'
        require(notebook.resolve() == notebook, 'redirected shared notebook database')
        source = self.ops / 'batch-a-state/learning-evidence.sqlite3'
        with closing(sqlite3.connect(notebook.as_uri() + '?mode=ro', uri=True)) as db:
            db.execute('ATTACH DATABASE ? AS prior', (source.as_uri() + '?mode=ro',))
            require(not db.execute('SELECT id,document FROM prior.records EXCEPT '
                                   'SELECT id,document FROM main.records LIMIT 1').fetchone(),
                    'shared notebook omits prior history')
        identity = self.legacy.bindings()
        identity.update(state_path=str(self.state), state_origin=s.sha(self.state / 'backup-manifest.json'))
        identity.update(candidate=self.candidate, original_launcher=s.ORIGINAL,
                        intended_launcher=hashlib.sha256(self.launcher()).hexdigest(),
                        owner_profile='bounded-foreground-90s', display=self.display())
        return identity

    def transition(self, before, data):
        require(s.sha(self.normal) == before and s.sha(self.fallback) == s.ORIGINAL,
                'launcher drift or missing rollback')
        after = hashlib.sha256(data).hexdigest()
        with (self.ops / 'logs' / f'shared-switch-{time.time_ns()}.json').open('x') as f:
            json.dump(dict(before=before, after=after), f)
            f.flush()
            os.fsync(f.fileno())
        s.replace(self.normal, data)
        require(s.sha(self.normal) == after, 'atomic launcher verification failed')

    def rollback(self):
        before = s.sha(self.normal)
        if before != s.ORIGINAL:
            require(before == hashlib.sha256(self.launcher()).hexdigest(), 'unrecognized launcher')
            self.transition(before, self.fallback.read_bytes())


def verify_witness(path, display):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    peers = [r['value'] for r in rows if r['event'] == 'recognition-peer']
    require(len(peers) == 2 and len({p['pid'] for p in peers}) == 2, 'two independent witnesses required')
    ids = []
    for peer in peers:
        require(peer['exit'] == 0 and len(peer['results']) == 2, 'client did not receive two frames')
        ids.append({(v['source'], v['generation'], v['frame_id'], v['model_sha256']) for v in peer['results']})
    require(len(ids[0] & ids[1]) == 2, 'client observations were not shared')
    require(any(r['value'] for r in rows if r['event'] == 'passive-frames'), 'missing passive frames')
    labels = [r['value'] for r in rows if r['event'] == 'display']
    require(labels == ([dict(intent=t, acknowledged=True) for t in ('CHAIR', 'CAT', None)]
                       if display else []), 'display witness failed')
    require(any(r['value'] is True for r in rows if r['event'] == 'socket-released'), 'socket release missing')


def process_start(pid):
    # /proc stat field 22; the parenthesized command may contain spaces.
    return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('action', choices=['release-request', 'ability-request', 'restore-rehearsal',
                                          'prepare-state', 'review', 'enable', 'launch', 'rollback'])
    args = parser.parse_args()
    ctl = SharedRelease(Path.home())
    require(ctl.home == Path('/home/five') and s.socket.gethostname() == 'charlie', 'unexpected host')
    with s.locked(ctl.ops):
        if args.action == 'rollback':
            ctl.rollback()
            return
        ctl.preserved()
        if args.action == 'prepare-state':
            from charlie_ops.operator import backup
            require(s.sha(ctl.normal) == s.ORIGINAL, 'prepare while original launcher is selected')
            s.idle_guard()
            require(not ctl.state.exists() and not ctl.state.is_symlink(), 'existing shared state must be preserved')
            print(json.dumps(backup(ctl.ops / 'batch-a-state', ctl.state), indent=2))
            return
        if args.action == 'restore-rehearsal':
            from .stationary_restore import rehearse
            print(json.dumps(rehearse(ctl, ctl.ops / 'promotion-backups' / f'shared-{time.time_ns()}'), indent=2))
            return
        if args.action.endswith('-request'):
            from .stationary_packet import proposal
            scope = SHARED if args.action == 'ability-request' else None
            print(json.dumps(proposal(ctl, scope), indent=2, sort_keys=True))
            return
        active = hashlib.sha256(ctl.launcher()).hexdigest()
        pending = ctl.review / 'pending-smoke.json'
        if args.action == 'enable':
            require(s.sha(ctl.normal) == s.ORIGINAL and not pending.exists(),
                    'enable requires the original launcher and no interrupted smoke')
        if args.action == 'launch':
            require(s.sha(ctl.normal) == active, 'shared launcher not selected')
        try:
            if args.action == 'launch' and pending.exists():
                marker = load(pending)
                require(marker['pid'] == os.getppid() and
                        marker['parent_start'] == process_start(os.getppid()) and
                        marker['boot'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                        'interrupted or unrelated smoke launch')
            ctl.validate({SHARED})
            if args.action == 'review':
                return
            foreground()
            require(sys.flags.isolated and sys.dont_write_bytecode and
                    Path(sys.prefix) == Path('/home/five/Projects/charlie/.venv') and
                    set(os.environ) <= {'HOME', 'PATH', 'LC_CTYPE'} and
                    os.environ.get('PATH') == '/usr/bin:/bin', 'canonical sanitized interpreter required')
            confirm_isolation()
            s.idle_guard()
            s.device_guard()
            if args.action == 'enable':
                from charlie_ops.operator import verify_backup
                verify_backup(ctl.state)
                with pending.open('x') as record:
                    json.dump(dict(pid=os.getpid(), parent_start=process_start(os.getpid()),
                                   boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()), record)
                    record.flush()
                    os.fsync(record.fileno())
                ctl.transition(s.ORIGINAL, ctl.launcher())
            else:
                with s.session_guard(ctl, {SHARED}):
                    sys.path.insert(0, str(ctl.new))
                    os.chdir(ctl.legacy.new)
                    import main as app
                    require(Path(app.__file__).resolve() == ctl.new / 'main.py', 'wrong shared application')
                    from .shared_profile import run
                    stream = load(ctl.models).get('stream_url') or 'http://192.168.4.1:81/stream'
                    summary = ctl.ops / 'logs' / f'shared-owner-{time.time_ns()}.json' if pending.exists() else None
                    run(ctl.state, ctl.models, stream,
                        display=ctl.display() == 'rp2040', summary=summary)
                    if summary is not None:
                        owner = load(summary)
                        require(owner['hailort_completed'] > 0 and owner['delivered']['executive'] >= 1
                                and owner['delivered']['recognize'] >= 4, 'shared smoke lacks native deliveries')
                        with (ctl.review / 'smoke-owner.json').open('x') as out:
                            json.dump(dict(path=str(summary), sha256=s.sha(summary)), out)
                    s.idle_guard()
                    s.device_guard()
                return
        except BaseException:
            if args.action in ('enable', 'launch') and s.sha(ctl.normal) == active:
                ctl.rollback()
            raise

    # Exercise the exact installed entry point. Child takes the same admission lock.
    try:
        witness = ctl.ops / 'logs' / f'shared-witness-{time.time_ns()}.jsonl'
        command = [sys.executable, '-IB', str(s.ROOT / 'tools/shared_trial_probe.py'), '--receipt', str(witness)]
        display = ctl.display() == 'rp2040'
        if display:
            command.append('--display')
        observer = subprocess.Popen(command)
        try:
            subprocess.run([str(ctl.normal)], check=True, timeout=210)
            require(observer.wait(timeout=12) == 0, 'smoke witness failed')
        finally:
            if observer.poll() is None:
                observer.kill()
                observer.wait()
        verify_witness(witness, display)
        foreground()
        require(input('Verify shared Executive/client results, frame reader, quiet output, STOP and release. '
                      'Type SHARED SMOKE PASSED: ') == 'SHARED SMOKE PASSED', 'smoke unconfirmed')
        with s.locked(ctl.ops):
            require(s.sha(ctl.normal) == active, 'selection changed during smoke')
            receipt = load(ctl.review / 'smoke-owner.json')
            require(s.sha(Path(receipt['path'])) == receipt['sha256'], 'owner receipt changed')
            with (ctl.ops / 'logs' / f'shared-accepted-{time.time_ns()}.json').open('x') as out:
                json.dump(dict(before=s.ORIGINAL, after=active, candidate=ctl.candidate,
                               owner_receipt=receipt, witness_sha256=s.sha(witness), operator_smoke_confirmed=True), out)
            (ctl.review / 'smoke-owner.json').unlink()
            pending.unlink()
    except BaseException:
        with s.locked(ctl.ops):
            ctl.rollback()
        raise
