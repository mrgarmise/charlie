"""Default-off local transport admission, owned only by the Executive worker.

Stock Ollama has no atomic resident-only inference operation. An independently
approved safe-idle window is consequently mandatory even after /api/ps passes.
This module cannot create that approval, prewarm, restart a service or actuate.
"""
from datetime import datetime
import fcntl
import hashlib
import json
import math
import multiprocessing
import os
from pathlib import Path
import re
import stat
import subprocess
import time

from .consultation import OllamaConfig, _http, parse_response, request_payload, consultation_resources
from .resources import temperature

MODEL = 'qwen3:1.7b'
SERVICE = 'charlie-consultant.service'
SCHEMA = 'charlie-consultation-idle-approval-v1'


def private_read(path, limit=16384):
    """Do not follow symlinks or admit a writable/shared approval."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('private owner-only regular approval required')
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('approval exceeds bound')
    return raw


def git_revision():
    repo = Path(__file__).resolve().parents[1]
    def git(*args):
        return subprocess.run(['git', *args], cwd=repo, check=True, capture_output=True,
                              text=True, timeout=2).stdout.strip()
    if git('status', '--porcelain', '--untracked-files=no'):
        raise ValueError('clean reviewed source required')
    return git('rev-parse', 'HEAD')


def validate_approval(doc, *, now, boot_id, revision):
    if (doc.get('schema') != SCHEMA or doc.get('operator_consent') is not True
            or doc.get('native_prerequisites_verified') is not True
            or doc.get('safe_idle_no_sensing_deadlines') is not True
            or doc.get('exclusive_service') is not True
            or doc.get('model') != MODEL or doc.get('boot_id') != boot_id
            or doc.get('code_revision') != revision):
        raise ValueError('native approval, consent, safe idle and source identity required')
    issued, expires = doc.get('issued_at'), doc.get('expires_at')
    if (any(type(x) not in (int, float) or not math.isfinite(x) for x in (issued, expires))
            or not issued <= now < expires or not 35 <= expires - issued <= 120):
        raise ValueError('expired or invalid bounded safe-idle window')
    for field in ('model_digest', 'qualification_sha256'):
        if not re.fullmatch('[a-f0-9]{64}', doc.get(field, '')):
            raise ValueError('exact content digest required')
    if not re.fullmatch('[a-f0-9]{32}', doc.get('service_invocation_id', '')):
        raise ValueError('service invocation identity required')
    if not isinstance(doc.get('server_version'), str) or not doc['server_version']:
        raise ValueError('server version required')
    return doc


def service_identity():
    """Read the existing dedicated unit and effective kernel limits; never edit it."""
    props = ('ActiveState', 'MainPID', 'InvocationID', 'ControlGroup',
             'PrivateDevices', 'NoNewPrivileges', 'ProtectHome', 'RuntimeMaxUSec',
             'TimeoutStopUSec', 'Restart', 'KillMode', 'SendSIGKILL')
    result = subprocess.run(['systemctl', '--user', 'show', SERVICE,
                             '--property=' + ','.join(props)], check=True,
                            capture_output=True, text=True, timeout=2)
    values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    if (values.get('ActiveState') != 'active' or values.get('PrivateDevices') != 'yes'
            or values.get('NoNewPrivileges') != 'yes' or values.get('ProtectHome') != 'tmpfs'):
        raise ValueError('dedicated sandbox unavailable')
    def seconds(value):
        # systemctl renders these durations as e.g. '1min 30s', '5s', '500ms'.
        units = {'min': 60, 's': 1, 'ms': .001, 'us': .000001}
        parts = re.findall(r'([0-9]+(?:\.[0-9]+)?)(min|ms|us|s)', value)
        if not parts or ''.join(a+b for a,b in parts) != value.replace(' ', ''):
            raise ValueError('finite service lifetime required')
        return sum(float(a)*units[b] for a,b in parts)
    runtime = seconds(values.get('RuntimeMaxUSec', ''))
    stop = seconds(values.get('TimeoutStopUSec', ''))
    if (not 0 < runtime <= 120 or not 0 < stop <= 5 or values.get('Restart') != 'no'
            or values.get('KillMode') != 'control-group' or values.get('SendSIGKILL') != 'yes'):
        raise ValueError('finite non-restarting service cutoff required for safe-idle containment')
    pid = int(values.get('MainPID', '0'))
    if pid <= 0:
        raise ValueError('service process unavailable')
    group = values.get('ControlGroup', '')
    root = Path('/sys/fs/cgroup').resolve()
    path = (root / group.lstrip('/')).resolve()
    if not group or path == root or root not in path.parents:
        raise ValueError('dedicated cgroup required')
    memory = int((path / 'memory.max').read_text())
    swap = int((path / 'memory.swap.max').read_text())
    quota, period = map(int, (path / 'cpu.max').read_text().split())
    if not 0 < memory <= 2500 * 1024**2 or swap != 0 or not 0 < quota <= period:
        raise ValueError('server hard resource bounds unavailable')
    if int((path / 'memory.swap.current').read_text()) != 0:
        raise ValueError('server swap in use')
    # Bind the HTTP listener to the inspected service PID, not just an API banner.
    inodes = set()
    for fd in Path('/proc', str(pid), 'fd').iterdir():
        try:
            target = os.readlink(fd)
            if target.startswith('socket:['):
                inodes.add(target[8:-1])
        except FileNotFoundError:
            continue
    listeners = [line.split() for line in Path('/proc/net/tcp').read_text().splitlines()[1:]]
    if any(row[3] == '0A' and row[9] in inodes and row[1] != '0100007F:2CAA' for row in listeners):
        raise ValueError('additional service listener refused')
    if not any(row[1] == '0100007F:2CAA' and row[3] == '0A' and row[9] in inodes for row in listeners):
        raise ValueError('loopback listener is not owned by dedicated service')
    ticks = Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19]
    return dict(invocation_id=values['InvocationID'], pid=pid, start_ticks=ticks,
                cgroup=group, memory_max=memory, cpu_max=[quota, period],
                cutoff_monotonic=int(ticks)/os.sysconf('SC_CLK_TCK') + runtime + stop)


class Admission:
    """Expiring operator attestation, never self-issued or refreshed by Charlie."""
    def __init__(self, path):
        self.path = Path(path)
        self.raw = private_read(self.path)
        self.doc = json.loads(self.raw)
        self.revision = git_revision()
        self.boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        validate_approval(self.doc, now=time.time(), boot_id=self.boot, revision=self.revision)
        receipt = private_read(self.doc['qualification_path'], 1024 * 1024)
        if hashlib.sha256(receipt).hexdigest() != self.doc['qualification_sha256']:
            raise ValueError('qualification receipt changed')
        self.identity = service_identity()
        if self.identity['invocation_id'] != self.doc['service_invocation_id']:
            raise ValueError('service restarted since approval')
        if self.identity['cutoff_monotonic'] - time.monotonic() > self.doc['expires_at'] - time.time():
            raise ValueError('safe-idle window must cover the kernel-supervised service cutoff')
        self.next_sample = 0.

    def check(self, *, starting=False):
        if private_read(self.path) != self.raw:
            raise ValueError('approval revoked or changed')
        validate_approval(self.doc, now=time.time(), boot_id=self.boot, revision=self.revision)
        if starting and self.doc['expires_at'] - time.time() < 35:
            raise ValueError('insufficient safe-idle time remaining')
        if time.monotonic() >= self.next_sample:
            consultation_resources(lambda: None)
            heat = temperature()
            if heat is None or heat >= 70:
                raise ValueError('native temperature unavailable or unsafe')
            throttled = subprocess.run(['vcgencmd', 'get_throttled'], check=True,
                                       capture_output=True, text=True, timeout=1).stdout.strip()
            if throttled != 'throttled=0x0':
                raise ValueError('throttling or undervoltage reported')
            if service_identity() != self.identity:
                raise ValueError('service identity or limits changed')
            self.next_sample = time.monotonic() + .5


def ready_model(raw, approval, *, now):
    models = raw.get('models')
    if not isinstance(models, list) or len(models) != 1 or not isinstance(models[0], dict):
        raise ValueError('exactly one resident model required')
    model = models[0]
    if (model.get('name') != MODEL or model.get('digest') != approval['model_digest']
            or model.get('context_length') != 2048):
        raise ValueError('resident model identity/context mismatch')
    expires = datetime.fromisoformat(model['expires_at'].replace('Z', '+00:00')).timestamp()
    if not 35 <= expires - now <= 120:
        raise ValueError('resident lease absent, too short or unbounded')
    return model


def runtime_directory():
    return Path('/run/user') / str(os.getuid()) / 'charlie-consultation'


def _operational_worker(config, prompt, approval_path, pipe):
    """All system/HTTP work stays in the existing provider's cancellable child."""
    lock = None
    try:
        admission = Admission(approval_path)
        admission.check(starting=True)
        # A common owner-only approval directory is required across notebooks.
        parent = runtime_directory()
        info = parent.stat()
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('private approval directory required')
        lock = os.open(parent / 'consultation.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        marker = parent / 'completion-unknown.json'
        if marker.exists():
            raise ValueError('unknown prior completion requires independent clearance')
        # Any ambiguous exit after this point leaves a durable, no-retry latch.
        version = _http(config, None, '/api/version')
        if version.get('version') != admission.doc['server_version']:
            raise ValueError('server version mismatch')
        resident = ready_model(_http(config, None, '/api/ps'), admission.doc, now=time.time())
        admission.check(starting=True)
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(dict(service=admission.identity, submitted_at=time.time(),
                           approval_digest=hashlib.sha256(admission.raw).hexdigest()), stream)
            stream.flush(); os.fsync(stream.fileno())
        directory = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
        pipe.send(('admitted', dict(approval=admission.doc, identity=admission.identity)))
        result = parse_response(_http(config, request_payload(config, prompt)), config)
        admission.check()
        # keep_alive=0 requests unload; verify rather than assert cleanup happened.
        if _http(config, None, '/api/ps').get('models') != []:
            raise ValueError('unload not confirmed; operator clearance required')
        result['identity'] = dict(server_version=version['version'], model_digest=resident['digest'],
                                  service=admission.identity,
                                  approval_digest=hashlib.sha256(admission.raw).hexdigest(),
                                  qualification_sha256=admission.doc['qualification_sha256'])
        # Parent must durably retain the answer before acknowledging completion.
        pipe.send(('ok', result))
        if pipe.poll(2) and pipe.recv() == 'retained':
            marker.unlink()
            directory = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(directory)
            finally: os.close(directory)
            pipe.send(('cleared', None))
    except Exception as exc:
        pipe.send(('error', type(exc).__name__))
    finally:
        if lock is not None: os.close(lock)
        pipe.close()


class OperationalProvider:
    origin = 'local'
    model = MODEL
    def __init__(self, approval_path):
        self.path = str(approval_path)
        self.config = OllamaConfig(keep_alive=0)
        self.state = 'awaiting-native-safe-idle-admission'
        self.child = None
        self.pipe = None

    def status(self):
        return dict(state=self.state, mode='qualified-safe-idle-only',
                    active_sensing_supported=False, prewarming=False, remote_fallback=False)

    def consult(self, prompt, check=lambda: None):
        request_payload(self.config, prompt)
        if self.child is not None:
            raise ValueError('one outstanding consultation required')
        ctx = multiprocessing.get_context('spawn')
        receive, send = ctx.Pipe()
        child = ctx.Process(target=_operational_worker,
                            args=(self.config, prompt, self.path, send), daemon=True)
        started = time.monotonic()
        self.child, self.pipe = child, receive
        self.state = 'checking-native-admission'
        try:
            check(); child.start(); send.close()
            admission = None
            while True:
                check()
                if admission is not None: admission.check()
                if time.monotonic() - started >= self.config.wall_seconds:
                    raise TimeoutError('operational consultation deadline')
                if receive.poll(.05):
                    state, result = receive.recv()
                    if state == 'admitted':
                        admission = Admission(self.path)
                        if admission.identity != result['identity'] or admission.doc != result['approval']:
                            raise ValueError('admission changed during dispatch')
                        self.state = 'request-in-flight'
                        continue
                    if state != 'ok': raise ValueError('operational admission/provider refused: ' + result)
                    self.state = 'answer-awaiting-journal'
                    result.update(origin=self.origin, latency_seconds=time.monotonic() - started)
                    return result
                if not child.is_alive(): raise ValueError('provider exited without receipt')
        except BaseException:
            self.state = 'deferred-check-native-clearance'
            self.close()
            raise
        finally:
            send.close()

    def retained(self):
        """Only called after the existing immutable journal stores the result."""
        self.state = 'answer-retained-cleanup-unconfirmed'
        try:
            if self.pipe is not None:
                self.pipe.send('retained')
                if self.pipe.poll(2) and self.pipe.recv()[0] == 'cleared':
                    self.state = 'completed-unload-confirmed'
        except (OSError, EOFError):
            pass  # Keep the durable answer; a missing cleanup receipt is not success.
        finally:
            self.close()

    def close(self):
        if self.child is not None and self.child.pid is not None:
            if self.child.is_alive(): self.child.terminate()
            self.child.join(timeout=1)
            if self.child.is_alive(): self.child.kill(); self.child.join(timeout=1)
        if self.pipe is not None: self.pipe.close()
        self.child = self.pipe = None


def make_service(journal, approval_path=None):
    from .consultation import ConsultationService
    if approval_path is None:
        return ConsultationService(journal)
    return ConsultationService(journal, OperationalProvider(approval_path), shadow=False)
