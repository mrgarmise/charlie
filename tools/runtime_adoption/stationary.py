"""Operator-controlled stationary worktree cutover. Importing this module does no I/O."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
import shutil
from pathlib import Path
import shlex
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time

from .inventory import collect, digest, git
from .promotion import load, require, validate

CANDIDATE = dict(sha='d7cabfc65b6c25d5d71af7ce5141ab5de828ba4f',
                 tree='53f0d945aed1eff2c147612d054917e83dcb1d4f')
BASELINE = dict(sha='d3dca9059233b5f054c4f6f9979085b1422f9674',
                tree='72cd9e4eba5939c181ae88d6ed03d5bbc50527c4')
A = 'stationary.object_recognition.elegoo_hailo_pico'
B = 'executive.read_only_status'
SCOPES = {A: ('N0', 'N1', 'N2', 'N5'), B: ('N0', 'N1', 'N5')}
NORMAL = 'start-stationary.sh'
ORIGINAL = '3305e83b84874162578d70f0de276c3dde5a80883261782bf0052db5420bd5e2'
PIN = '5022c8cf88b0928d9abea764510d53d10ace5cc570447e7650db406b2cb70e30'
CONSULT = '3a3956e899c20609a25ef6d63964aa80f9ef7894cd1c93955603c5db62c62a75'
FIRST = 'b0a0d4675acd6f83e36f4f5d85d54f3079d665eb92aea15a6b3e0eb09df85ec9'
ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return digest(path)['sha256']


def evidence(path, expected, model, *, historical_exit=None):
    """Read every JSON observation; refuse partial or mixed identity logs."""
    count = 0
    frames = set()
    last = ''
    stopped = False
    with path.open() as stream:
        for line in stream:
            line = line.strip()
            if len(line) > 2_000_000:
                raise ValueError('oversize log record')
            if line:
                last = line
            if 'Development operational: clean shutdown' in line:
                stopped = True
            if not line.startswith('{'):
                continue
            row = json.loads(line)
            if 'observation' not in row:
                require(row.get('motion_authorized', False) is False, 'unexpected authority')
                continue
            p, o = row['provenance'], row['observation']
            require(o['schema'] == 'charlie.object-observation.v1' and
                    p['software_revision'] == CANDIDATE['sha'] and
                    o['source'] == p['frame']['source'] == 'elegoo-v4' and
                    o['frame_id'] == p['frame']['id'] and
                    row['motion_authorized'] is False and p['motion_authorized'] is False and
                    p['model'][0]['sha256'] == model and
                    p['model'][0]['backend'] == 'hailort-hef', 'observation identity or authority')
            frames.add((o.get('stream_generation'), o['frame_id']))
            count += 1
    require(count == len(frames) and count > 0 and (expected is None or count == expected),
            'missing or repeated observations')
    if historical_exit is None:
        require(last.startswith('END ') and last.endswith(' exit=0'), 'missing successful session end')
    else:
        # Older qualification launchers recorded the exit status in a separate
        # file, not a session.log footer. Only the pinned original log may use
        # this format; newer operational sessions must keep their inline footer.
        require(expected == 229 and sha(path) == FIRST,
                'historical exit record is only valid for pinned qualification log')
        require(stopped, 'historical session did not record clean Executive shutdown')
        require(historical_exit.read_bytes() in (b'0', b'0\n'),
                'historical qualification exit code is not zero')
        exit_digest = sha(historical_exit)  # Refuses symlinks and missing files.
    result = dict(observations=count, sha256=sha(path), clean_shutdown_logged=stopped,
                  source='elegoo-v4', software_revision=CANDIDATE['sha'], hef_sha256=model,
                  residual_process_check='requires separate host evidence', pico_ack='unverified')
    if historical_exit is not None:
        result['exit_code_sha256'] = exit_digest
        result['exit_code_path'] = str(historical_exit)
    return result


def template(selected):
    require(A in selected and set(selected) <= SCOPES.keys(), 'unsupported stationary composition')
    call = ' '.join(shlex.quote(x) for x in sorted(selected))
    controller = shlex.quote(str(ROOT))
    pin = git(ROOT, 'rev-parse', 'HEAD')
    # Check the reviewed checkout outside Python, before importing any controller source.
    script = (
        'set -eu\n'
        f'cd {controller}\n'
        'revision=$(/usr/bin/git rev-parse HEAD)\n'
        f'[ "$revision" = {shlex.quote(pin)} ]\n'
        'dirty=$(/usr/bin/git -c core.fsmonitor=false status --porcelain --untracked-files=all)\n'
        '[ -z "$dirty" ]\n'
        'exec /home/five/Projects/charlie/.venv/bin/python -IB '
        + shlex.quote(str(ROOT / 'tools/stationary_ctl.py')) + ' launch ' + call
    )
    return ('#!/bin/sh\nset -eu\n[ "$#" -eq 0 ] || exit 64\n'
            'exec /usr/bin/env -i HOME=/home/five PATH=/usr/bin:/bin /bin/sh -c '
            + shlex.quote(script) + '\n').encode()



def selection(normal):
    current = sha(normal)
    if current == ORIGINAL:
        return set()
    for ids in ({A}, {A, B}):
        if current == hashlib.sha256(template(ids)).hexdigest():
            return ids
    raise ValueError('unrecognized canonical launcher; inspect or use independent rollback')


@contextmanager
def locked(ops):
    fd = os.open(ops / 'runtime.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


@contextmanager
def bounded_log_tee(out):
    """Log to file and foreground terminal; never wait indefinitely on inherited pipe FDs.

    A spawned worker may inherit a copy of stdout/stderr and keep the tee pipe
    open after the Executive completes. Such a leak must not hang the operator
    indefinitely or silently turn a failed cleanup into a qualification pass.
    """
    tee = subprocess.Popen(['/usr/bin/tee', '/proc/self/fd/' + str(out.fileno())],
                           stdin=subprocess.PIPE, pass_fds=(out.fileno(),))
    try:
        yield tee
    finally:
        if tee.stdin is not None and not tee.stdin.closed:
            tee.stdin.close()
        try:
            tee.wait(timeout=5)
        except subprocess.TimeoutExpired:
            tee.charlie_forced_cleanup = True
            tee.terminate()
            try:
                tee.wait(timeout=2)
            except subprocess.TimeoutExpired:
                tee.kill()
                tee.wait(timeout=2)



def verified_log_exit(tee, path, model):
    """Accept a forced tee shutdown ONLY with a complete, validated log.

    Children occasionally retain inherited output pipe FDs after the app
    exits. The bounded logger must still be stopped, and no incomplete log
    may be treated as a successful session.
    """
    orderly = tee.returncode == 0
    forced = (getattr(tee, 'charlie_forced_cleanup', False)
              and tee.returncode in (-signal.SIGTERM, -signal.SIGKILL))
    require(orderly or forced, 'evidence logger exited unexpectedly')
    result = evidence(path, None, model)
    require(result['clean_shutdown_logged'], 'missing clean Executive shutdown')
    if forced:
        print('WARNING: inherited logger pipe required bounded termination; '
              'complete session log independently validated', file=sys.stderr, flush=True)
    return result


def replace(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        temp = Path(f.name)
        try:
            f.write(data)
            f.flush()
            os.fchmod(f.fileno(), 0o700)
            os.fsync(f.fileno())
            os.replace(temp, path)
            directory = os.open(path.parent, os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temp.unlink(missing_ok=True)


class Stationary:
    def __init__(self, home):
        self.home = home
        self.ops = home / 'charlie-ops'
        self.old = home / 'charlie-runtime'
        self.new = home / 'charlie-runtime-adoption-v2'
        self.review = self.ops / 'stationary-review'
        self.normal = self.ops / NORMAL
        self.fallback = self.ops / 'promotion-backups/batch-a-20261119T220807Z' / NORMAL
        self.models = home / 'charlie-mobile-models/mobile-models.json'

    def logs(self):
        record = self.ops / 'promotion-evidence/batch-a-native-recognition.json'
        first_dir = self.home / 'charlie-candidate-acceptance/20261116T160554Z'
        first = first_dir / 'session.log'
        first_exit = first_dir / 'exit-code.txt'
        second = self.ops / 'logs/20261119T222200Z-batch-a-stationary.log'
        require(sha(first) == FIRST, 'original 229-observation log missing or changed')
        model = load(self.models)['objects']['sha256']
        qualification = load(record)
        native = qualification['native_recognition']
        require(qualification['candidate'] == CANDIDATE['sha'] and
                native['path'] == str(first_dir) and native['log_sha256'] == FIRST and
                native['observations'] == 229 and native['exit_code'] == 0 and
                native['motion_authorized'] is False,
                'qualification record does not bind original session and candidate')
        return {'qualification_record': sha(record),
                'qualification': evidence(first, 229, model, historical_exit=first_exit),
                'guarded_session': evidence(second, 354, model)}

    def health(self, selected):
        logs = list((self.ops / 'logs').glob('stationary-session-*.log'))
        require(bool(logs), 'no post-switch supervised session recorded')
        path = max(logs, key=lambda p: p.stat().st_mtime_ns)
        require(path.stat().st_mtime_ns >= self.normal.stat().st_mtime_ns, 'pre-switch session')
        with path.open() as f:
            require(f.readline().strip() == self.session_identity(selected), 'session identity mismatch')
        report = evidence(path, None, load(self.models)['objects']['sha256'])
        require(report['clean_shutdown_logged'], 'clean Executive shutdown missing')
        idle_guard()
        device_guard()
        return dict(session=str(path), evidence=report, canonical=self.normal.name,
                    enabled=sorted(selected), verified_at=time.time())

    def session_identity(self, selected):
        identity = dict(controller=git(ROOT, 'rev-parse', 'HEAD'), candidate=CANDIDATE,
                        boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                        launcher=sha(self.normal), selected=sorted(selected))
        return 'BEGIN ' + json.dumps(identity, sort_keys=True)

    def preserved(self):
        require(sha(self.fallback) == ORIGINAL and sha(self.ops / 'approved.sha') == PIN
                and sha(self.ops / 'run-historical-consultation.py') == CONSULT,
                'approved controls or fallback changed')
        require(self.new.resolve() == self.new and self.old.resolve() == self.old, 'redirected worktree')
        for path, identity in ((self.old, BASELINE), (self.new, CANDIDATE)):
            require(git(path, 'rev-parse', 'HEAD') == identity['sha'] and
                    git(path, 'rev-parse', 'HEAD^{tree}') == identity['tree'] and
                    not git(path, 'status', '--porcelain', '--untracked-files=all'), 'worktree mismatch')

    def validate(self, selected):
        self.preserved()
        trust, key = trusted_reviewer()
        require(not selected - SCOPES.keys() and A in selected, 'Batch A required')
        state = self.ops / 'batch-a-state'
        require(state.is_dir() and state.resolve() == state and any(state.iterdir()),
                'reviewed existing state required')
        require(socket.gethostname() == 'charlie' and self.home == Path('/home/five'),
                'unexpected operational host or home')
        release = load(self.review / 'manifest.json')
        bindings = self.bindings()
        require(bindings['logs']['guarded_session']['clean_shutdown_logged'] is True,
                'guarded session lacks clean Executive shutdown')
        receipts = load(self.review / 'ci.json')
        for stage, scope, name in [('release', [], 'release')] + [
                ('enablement', [sid], sid) for sid in sorted(selected)]:
            manifest = release if not scope else load(self.review / (name + '.manifest.json'))
            self.check_manifest(manifest, scope)
            require(manifest['stationary'] == bindings == release['stationary'], 'host or release drift')
            require(manifest['rollback'] == release['rollback'] and
                    manifest['required_ci'] == release['required_ci'], 'release contract changed')
            controller_ci = load(self.review / 'controller-ci.json')
            require(controller_ci['sha'] == bindings['controller_sha'] and controller_ci['conclusion'] == 'success'
                    and controller_ci['tree'] == bindings['controller_tree']
                    and sha(self.review / 'controller-ci.json') in manifest['protected'].values()
                    and str(controller_ci['url']).startswith('https://github.com/mrgarmise/charlie/actions/runs/')
                    and 0 <= time.time() - controller_ci['completed_at'] <= 7 * 86400, 'controller CI pending')
            backup = manifest['backup_qualification']
            require(any(load(path) == {k: v for k, v in backup.items() if k != 'evidence_sha256'}
                        for path, digest in manifest['protected'].items() if digest == backup['evidence_sha256']),
                    'restore receipt does not match protected original')
            for sid in scope:
                for gate, receipt in next(a for a in manifest['abilities'] if a['id'] == sid)['native_gates'].items():
                    matches = [p for p, h in manifest['protected'].items() if h == receipt['evidence_sha256']]
                    require(any(load(p) == {k: v for k, v in receipt.items() if k != 'evidence_sha256'}
                                for p in matches), 'native receipt differs from original file')
            observed = collect(self.old, self.new, self.ops, protected=manifest['protected'])
            approval = load(self.review / (name + '.json'))
            require(approval['record']['reviewer'] == trust['reviewer'], 'unknown reviewer')
            validate(manifest, observed, receipts, stage=stage, selected=scope, approval=approval,
                     key_path=key, key_sha256=trust['sha256'],
                     source_root=self.new)
            require(approval['record']['expires_at'] > time.time() + 180, 'review expires during session')

    def lineage(self):
        old = self.ops / 'state/learning-evidence.sqlite3'
        new = self.ops / 'batch-a-state/learning-evidence.sqlite3'
        require(old.is_file() and new.is_file() and not old.samefile(new), 'two original notebooks required')
        with sqlite3.connect(old.as_uri() + '?mode=ro', uri=True) as db:
            db.execute('ATTACH DATABASE ? AS candidate', (new.as_uri() + '?mode=ro',))
            head = db.execute('SELECT id FROM main.records ORDER BY sequence LIMIT 1').fetchone()
            require(head and not db.execute('SELECT id,document FROM main.records EXCEPT '
                                             'SELECT id,document FROM candidate.records LIMIT 1').fetchone(),
                    'candidate notebook omits approved history; reconciliation requires review')
        return head[0]

    def bindings(self):
        require(not git(ROOT, 'status', '--porcelain', '--untracked-files=all'), 'controller drift')
        model = load(self.models)['objects']
        require(sha(self.new / model['path']) == model['sha256'], 'model artifact changed')
        return dict(controller_sha=git(ROOT, 'rev-parse', 'HEAD'),
                    controller_tree=git(ROOT, 'rev-parse', 'HEAD^{tree}'),
                    models_sha256=sha(self.models), hef_sha256=model['sha256'],
                    boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                    machine_id=sha(Path('/etc/machine-id')), logs=self.logs(),
                    state_path=str(self.ops / 'batch-a-state'), notebook_anchor=self.lineage())

    @staticmethod
    def check_manifest(m, selected):
        require(m['candidate'] == CANDIDATE and m['baseline'] == BASELINE and
                m['rollback']['sha'] == BASELINE['sha'], 'wrong release identity')
        require(set(selected) <= SCOPES.keys(), 'unsupported ability')
        rows = {a['id']: a for a in m['abilities']}
        require(set(rows) == set(SCOPES), 'granular capability manifest required')
        protected = set(m['protected'].values())
        require(m['backup_qualification']['evidence_sha256'] in protected, 'restore evidence missing')
        require(m['default_authority'] == 'deny' and
                {'full', 'contracts', 'baseline-llm', 'browser', 'firmware-host', 'firmware-build',
                 'neural-cpu'} <= set(m['required_ci']), 'incomplete review contract')
        for sid, gates in SCOPES.items():
            a = rows[sid]
            require(a['enabled'] is False and a['source_present'] is True and a['dependencies'] == []
                    and set(a['required_native_gates']) == set(gates), 'invalid capability contract')
            if sid in selected:
                for gate in gates:
                    receipt = a['native_gates'][gate]
                    require(bool(receipt['artifacts']) and all(m['protected'].get(path) == digest
                            for path, digest in receipt['artifacts'].items()), 'native measurement files missing')
                    require(receipt['ability'] == sid and receipt['gate'] == gate and
                            receipt['controller_sha'] == m['stationary']['controller_sha'] and
                            receipt['evidence_sha256'] in protected, 'missing or mismatched gate artifact')

    def switch(self, before, after):
        if before == after:
            return
        require(selection(self.normal) == before, 'canonical selection changed')
        require(sha(self.fallback) == ORIGINAL, 'fallback changed')
        data = template(after) if after else self.fallback.read_bytes()
        audit = self.ops / 'logs' / ('stationary-change-%d.json' % time.time_ns())
        with audit.open('x') as f:
            json.dump(dict(before=sorted(before), requested=sorted(after),
                           intended_launcher_sha256=hashlib.sha256(data).hexdigest()), f)
            f.flush()
            os.fsync(f.fileno())
        replace(self.normal, data)

    def inspect(self):
        checks = {}
        for label, fn in [('controls_and_worktrees', self.preserved), ('observation_logs', self.logs),
                          ('review', lambda: self.validate({A}))]:
            try:
                value = fn()
                checks[label] = dict(status='PASS', evidence=value)
            except (ValueError, KeyError, TypeError, OSError, sqlite3.Error, subprocess.SubprocessError) as exc:
                checks[label] = dict(status='PENDING', reason=str(exc))
        try:
            active = sorted(selection(self.normal))
        except (OSError, ValueError) as exc:
            active = None
            checks['canonical'] = dict(status='PENDING', reason=str(exc))
        statuses = {}
        for sid in SCOPES:
            review_ok = checks['review']['status'] == 'PASS' if sid == A else False
            if sid == B and active and B in active:
                try:
                    self.validate({A, B})
                    review_ok = True
                except (ValueError, KeyError, OSError, TypeError, subprocess.SubprocessError):
                    pass
            statuses[sid] = dict(source_present=checks['controls_and_worktrees']['status'] == 'PASS',
                                 native_qualification='verified' if review_ok else 'pending verification',
                                 operator_reviewed=review_ok, selected=(sid in active if active is not None else None),
                                 post_switch_verified='run verify')
        checks['native_owners'] = dict(status='PENDING', reason='requires native owner reconciliation')
        checks['post_switch_session'] = dict(status='PENDING', reason='use verify after supervised launch')
        native = {}
        if socket.gethostname() == 'charlie' and self.home == Path('/home/five'):
            from .inventory import observed_processes, resources
            native = dict(resources=resources(), processes=observed_processes(), devices={})
            for dev in ('/dev/hailo0', '/dev/ttyACM0'):
                try:
                    f = subprocess.run(['/usr/bin/fuser', dev], capture_output=True, text=True, timeout=3)
                    native['devices'][dev] = dict(character_device=Path(dev).is_char_device(),
                        owner_pids=[int(word) for word in f.stdout.split() if word.isdecimal()],
                        probe_exit=f.returncode, diagnostic=bool(f.stderr.strip()))
                except (OSError, subprocess.SubprocessError) as exc:
                    native['devices'][dev] = dict(error=str(exc))
            for name in ('QUALIFICATION.md', 'start-stationary-batch-a.sh', 'batch-a-operator-pin.sha',
                         'run-historical-consultation.py', 'approved.sha'):
                path = self.ops / name
                native[name] = sha(path) if path.is_file() and not path.is_symlink() else None
            try:
                service = subprocess.run(['systemctl', 'show', 'charlie.service',
                    '--property=LoadState,ActiveState,SubState,MainPID'], capture_output=True, text=True, timeout=5)
                native['service'] = service.stdout.splitlines() if service.returncode == 0 else 'unknown'
            except (OSError, subprocess.SubprocessError):
                native['service'] = 'unknown'
        return dict(native_inventory=native, canonical=str(self.normal), selected=active, checks=checks, abilities=statuses,
                    candidate=CANDIDATE, baseline=BASELINE, state_migration=False,
                    launch_verified=False, other_capabilities='default denied')


@contextmanager
def session_guard(ctl, selected):
    # An interrupted controller cannot silently retry a failed physical profile.
    # A new independent signed ability decision gives a new attempt identity.
    grants = [sha(ctl.review / (sid + '.json')) for sid in sorted(selected)]
    key = hashlib.sha256((''.join(grants) + sha(ctl.normal)).encode()).hexdigest()
    hold = ctl.ops / 'logs' / ('stationary-incomplete-' + key)
    with hold.open('x') as f:
        f.write('Pending supervised health verification. Preserve on interruption.\n')
        f.flush()
        os.fsync(f.fileno())
    yield
    hold.unlink()


def idle_guard():
    from .inventory import observed_processes
    processes = observed_processes()
    require(not any(p['name'] != 'ollama' for p in processes['visible']), 'runtime still active')
    for process in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            if process.stat().st_uid == os.getuid():
                words = process.read_bytes().split(b'\0')
                require(not any(b'multiprocessing.spawn import spawn_main' in word for word in words),
                        'residual same-user spawn worker')
        except FileNotFoundError:
            continue


def trusted_reviewer():
    trust_file = Path('/etc/charlie/stationary-reviewer.json')
    for path in (trust_file.parent, trust_file, trust_file.with_suffix('.pem')):
        info = path.lstat()
        require(info.st_uid == 0 and not info.st_mode & 0o022 and not path.is_symlink(),
                'untrusted reviewer configuration')
    trust = load(trust_file)
    return trust, trust_file.with_suffix('.pem')


def qualification_preflight(ctl, before):
    """No signed grant is issued and the canonical launcher must remain original."""
    require(before == set() and sha(ctl.normal) == ORIGINAL,
            'qualification requires unchanged original normal launcher')
    ctl.preserved()
    require(socket.gethostname() == 'charlie' and ctl.home == Path('/home/five'),
            'native qualification must run on Charlie')
    require(not (ctl.ops / 'batch-a-state').is_symlink(),
            'qualification source state cannot be redirected')
    require(ctl.lineage(), 'approved historical state not preserved')
    model = load(ctl.models)['objects']
    require(sha(ctl.new / model['path']) == model['sha256'],
            'reviewed Hailo model changed')
    idle_guard()
    device_guard()


def device_guard():
    for device in ('/dev/hailo0', '/dev/ttyACM0'):
        require(Path(device).is_char_device(), 'required device unavailable: ' + device)
        probe = subprocess.run(['/usr/bin/fuser', device], capture_output=True, timeout=5)
        require(probe.returncode == 1 and not probe.stdout and not probe.stderr,
                'busy device or inconclusive owner probe: ' + device)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('action', choices=('restore-rehearsal', 'request', 'status', 'plan', 'dry-run', 'qualify-evidence', 'review',
                        'enable', 'disable', 'verify', 'rollback', 'launch', 'executive-status', 'qualify-native', 'prepare-review'))
    parser.add_argument('abilities', nargs='*', choices=None)
    args = parser.parse_args(argv)
    ctl = Stationary(Path.home())
    args_ids = set(args.abilities)
    require(len(args_ids) == len(args.abilities) and args_ids <= SCOPES.keys(), 'unsupported arguments')
    def run_foreground(state_override=None):
        """Enter only the fixed normal object branch, on the foreground terminal."""
        require(sys.stdin.isatty() and os.tcgetpgrp(0) == os.getpgrp(), 'foreground operator required')
        require(Path(sys.executable).samefile(ctl.home / 'Projects/charlie/.venv/bin/python') and
                Path(sys.prefix) == ctl.home / 'Projects/charlie/.venv', 'qualified Pi interpreter required')
        require(set(os.environ) <= {'HOME', 'PATH', 'LC_CTYPE'} and
                os.environ.get('HOME') == '/home/five' and os.environ.get('PATH') == '/usr/bin:/bin'
                and sys.flags.isolated, 'canonical sanitized interpreter required')
        from functools import partial
        sys.path.insert(0, str(ctl.new))
        os.chdir(ctl.new)
        from .stationary_boundary import install
        stream = load(ctl.models).get('stream_url') or 'http://192.168.4.1:81/stream'
        install(stream)
        import main as app
        require(Path(app.__file__).resolve() == ctl.new / 'main.py', 'wrong application')
        from stimulus.keyboard import KeyboardStimulus
        from .stationary_boundary import install_stationary_stop
        restore_stop = install_stationary_stop(KeyboardStimulus)
        app.application_camera_feeders = partial(app.application_camera_feeders, selected=('elegoo',))
        def deadline(signum, frame):
            raise SystemExit('stationary wall deadline exceeded')
        previous_handler = signal.signal(signal.SIGALRM, deadline)
        signal.alarm(150)
        try:
            app.main(['--hardware', '--object-recognition', '--camera-source', 'elegoo',
                  '--elegoo-stream-url', stream, '--object-label-display', 'rp2040', '--object-seconds', '90', '--learning-require-thermal',
                  '--learning-state', str(state_override or ctl.ops / 'batch-a-state')])
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous_handler)
            restore_stop()

    action = args.action
    if action == 'restore-rehearsal':
        require(not args_ids, 'restore rehearsal takes no ability flags')
        from .stationary_restore import rehearse
        with locked(ctl.ops):
            destination = ctl.ops / 'promotion-backups' / ('stationary-' + str(time.time_ns()))
            print(json.dumps(rehearse(ctl, destination), indent=2))
        return
    if action == 'prepare-review':
        require(not args_ids, 'review preparation takes no ability arguments')
        from .stationary_packet_prepare import prepare
        with locked(ctl.ops):
            print(json.dumps(prepare(ctl), indent=2, sort_keys=True))
        return
    if action == 'request':
        require(len(args_ids) <= 1, 'one ability per request')
        from .stationary_packet import proposal
        print(json.dumps(proposal(ctl, next(iter(args_ids), None)), indent=2, sort_keys=True))
        return
    if action in ('status', 'plan', 'dry-run', 'qualify-evidence'):
        require(not args_ids, 'inspection takes no abilities')
        result = ctl.logs() if action == 'qualify-evidence' else ctl.inspect()
        print(json.dumps(result, indent=2))
        return
    with locked(ctl.ops):
        before = selection(ctl.normal)
        if action == 'qualify-native':
            require(not args_ids, 'qualification takes no ability selection')
            qualification_preflight(ctl, before)
            require(sys.stdin.isatty() and os.tcgetpgrp(0) == os.getpgrp(),
                    'supervised foreground terminal required')
            # Copy under the same runtime lock. Never mutate either operational notebook.
            destination = Path(tempfile.mkdtemp(
                prefix='stationary-native-qualification-',
                dir=ctl.ops / 'promotion-backups'))
            isolated_state = destination / 'state'
            shutil.copytree(ctl.ops / 'batch-a-state', isolated_state, symlinks=False)
            require(not (isolated_state / 'learning-evidence.sqlite3').is_symlink(),
                    'redirected qualification notebook')
            log = ctl.ops / 'logs' / ('stationary-qualification-%d.log' % time.time_ns())
            with log.open('xb') as out:
                with bounded_log_tee(out) as tee:
                    saved = [os.dup(n) for n in (1, 2)]
                    try:
                        for fd in (1, 2):
                            os.dup2(tee.stdin.fileno(), fd)
                        print('BEGIN QUALIFICATION ' + json.dumps(dict(
                            candidate=CANDIDATE, controller_sha=git(ROOT, 'rev-parse', 'HEAD'),
                            controller_tree=git(ROOT, 'rev-parse', 'HEAD^{tree}'),
                            original_launcher=sha(ctl.normal), boot=Path(
                                '/proc/sys/kernel/random/boot_id').read_text().strip(),
                            isolated_state=str(isolated_state), motion_authorized=False
                        ), sort_keys=True), flush=True)
                        run_foreground(isolated_state)
                        print('END stationary exit=0', flush=True)
                    finally:
                        sys.stdout.flush()
                        sys.stderr.flush()
                        for fd, original in zip((1, 2), saved):
                            os.dup2(original, fd)
                            os.close(original)
                        tee.stdin.close()
            report = verified_log_exit(tee, log, load(ctl.models)['objects']['sha256'])
            idle_guard()
            device_guard()
            require(selection(ctl.normal) == set() and sha(ctl.normal) == ORIGINAL,
                    'normal launcher changed during qualification')
            print(json.dumps(dict(status='native-measurement-complete',
                                  approval_issued=False, normal_runtime_changed=False,
                                  log=str(log), isolated_state=str(isolated_state),
                                  controller=git(ROOT, 'rev-parse', 'HEAD'),
                                  evidence=report), indent=2))
            return
        if action in ('disable', 'rollback'):
            require((action == 'rollback' and not args_ids) or
                    (action == 'disable' and len(args_ids) == 1), 'select one ability')
            after = before - args_ids if action == 'disable' else set()
            require(not after or A in after, 'disable status first or roll back both')
            ctl.switch(before, after)
            return
        if action in ('enable', 'review'):
            require(len(args_ids) == 1, 'one ability per review')
            after = before | args_ids
            ctl.validate(after)
            if action == 'enable':
                idle_guard()
                device_guard()
                ctl.switch(before, after)
            return
        require(before and (args_ids == before if action == 'launch' else not args_ids),
                'canonical launcher does not select this scope')
        ctl.validate(before)
        if action == 'executive-status':
            require(B in before, 'status interface disabled')
            print(json.dumps(load(ctl.ops / 'batch-a-state/development-status.json')))
        elif action == 'launch':
            idle_guard()
            device_guard()
            with session_guard(ctl, before):
                log = ctl.ops / 'logs' / ('stationary-session-%d.log' % time.time_ns())
                with log.open('xb') as out:
                    # Preserve controlling terminal and stdin; duplicate output only.
                    with bounded_log_tee(out) as tee:
                        saved = [os.dup(n) for n in (1, 2)]
                        try:
                            for fd in (1, 2):
                                os.dup2(tee.stdin.fileno(), fd)
                            print(ctl.session_identity(before), flush=True)
                            run_foreground()
                            print('END stationary exit=0', flush=True)
                        finally:
                            sys.stdout.flush()
                            sys.stderr.flush()
                            for fd, original in zip((1, 2), saved):
                                os.dup2(original, fd)
                                os.close(original)
                            tee.stdin.close()
                verified_log_exit(tee, log, load(ctl.models)['objects']['sha256'])
                print(json.dumps(ctl.health(before), indent=2))
        else:
            print(json.dumps(ctl.health(before), indent=2))
