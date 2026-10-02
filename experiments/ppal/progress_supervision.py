"""Out-of-process progress supervision; elapsed healthy gameplay is unbounded."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time


class Progress:
    def __init__(self, path, clock=time.monotonic):
        self.path = Path(path)
        self.clock = clock
        now = clock()
        self.data = dict(pid=os.getpid(), phase='startup', phase_started_at=now,
                         updated_at=now, fresh_at=now, sensor_at=None,
                         perception_at=now, cycle_at=now, cycles=0)
        self.cost_seconds = 0.
        self.enter('startup')

    def update(self, **fields):
        began = self.clock()
        self.data.update(fields, updated_at=began)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.data)+'\n')
        temporary.replace(self.path)
        self.cost_seconds += self.clock()-began

    def enter(self, phase):
        self.update(phase=phase, phase_started_at=self.clock())

    def fresh(self, sensor_at):
        # Repeated/stale exposures must not keep the watchdog alive.
        if sensor_at is not None and (self.data['sensor_at'] is None or sensor_at > self.data['sensor_at']):
            self.update(sensor_at=sensor_at, fresh_at=self.clock())
        self.enter('perception')

    def perception(self):
        self.update(perception_at=self.clock())

    def cycle(self):
        self.update(cycle_at=self.clock(), cycles=self.data['cycles']+1)


def stalled_reason(row, now, *, silence=30., camera=10., controller=10., processing=60.):
    """Only absence of progress or a stuck operation, never game age."""
    if not row:
        return 'subprocess_hang'
    phase = row.get('phase')
    age = now-row['phase_started_at']
    if phase == 'controller' and age > controller:
        return 'controller_failure'
    if phase == 'camera' and age > camera:
        return 'observation_failure'
    if phase in ('camera', 'perception') and now-row['fresh_at'] > camera:
        return 'observation_failure'
    if phase in ('perception', 'startup') and age > silence:
        return 'subprocess_hang'
    if phase == 'finalizing' and age > processing:
        return 'processing_stall'
    if now-row['updated_at'] > (processing if phase in ('processing', 'finalizing') else silence):
        return 'processing_stall' if phase in ('processing','finalizing') else 'subprocess_hang'
    if row.get('mode') in ('playing', 'reacquiring') and phase not in ('finalizing', 'controller'):
        if now-max(row['cycle_at'], row.get('mode_started_at', 0.)) > silence:
            return 'perception_cycle_stall'
    return None


class UncertaintyWindow:
    """Sustained loss of actionable observation, not game duration or death."""
    def __init__(self, seconds):
        self.seconds = seconds
        self.since = None

    def observe(self, available, now):
        if available:
            self.since = None
            return False
        if self.since is None:
            self.since = now
        return now-self.since >= self.seconds


def stop_process(child, *, grace=5.):
    """Interrupt for normal finally/neutralization, then kill/reap if stuck."""
    if child.poll() is not None:
        return True
    def send(sig):
        try:
            os.killpg(child.pid, sig)
        except ProcessLookupError:
            pass  # child can exit between poll and signal
    send(signal.SIGINT)
    try:
        child.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        send(signal.SIGTERM)
        try:
            child.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            send(signal.SIGKILL)
            try:
                child.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                # An uninterruptible kernel wait cannot be repaired in Python.
                # Do not hang the supervisor or authorize another camera/START.
                return False
    return True


def supervise(cmd, progress_path, *, silence=30., camera=10., controller=10.,
              processing=60., budget=None, poll=.2, grace=5., on_progress=None):
    """Parent watchdog works even if capture, transport or the child loop blocks.

    Optional budget is for offline processing only, never healthy gameplay.
    Durable supervisor.json preserves an unverified partial-episode boundary.
    """
    path = Path(progress_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    child = subprocess.Popen(cmd, start_new_session=True)
    began = time.monotonic()
    reason = None
    row = None
    reported_units = 0
    try:
        while child.poll() is None:
            try:
                candidate = json.loads(path.read_text())
                if candidate.get('pid') == child.pid:
                    row = candidate
                    units = row.get('processing_units', 0)
                    if on_progress is not None and units > reported_units:
                        reported_units = units
                        on_progress()
            except (OSError, ValueError):
                pass
            now = time.monotonic()
            reason = (stalled_reason(row, now, silence=silence, camera=camera,
                                    controller=controller, processing=processing)
                      if row else ('subprocess_hang' if now-began > silence else None))
            if budget is not None and now-began > budget:
                reason = 'processing_budget_exhausted'
            if reason:
                break
            time.sleep(poll)
    except KeyboardInterrupt:
        reason = 'interrupted'
    finally:
        reaped = stop_process(child, grace=grace)
        result = dict(reason=reason or 'child_exited', returncode=child.returncode,
                      last_progress=row, elapsed=time.monotonic()-began,
                      episode_boundary='unverified' if reason else 'consult report',
                      progress_path=path.name, reaped=reaped)
        path.with_name(path.stem+'-supervisor.json').write_text(json.dumps(result, indent=2)+'\n')
    return 124 if reason else child.returncode


class SupervisedController:
    def __init__(self, controller, progress):
        self.controller, self.progress = controller, progress

    def __getattr__(self, name):
        return getattr(self.controller, name)

    def _call(self, name, *args):
        previous = self.progress.data['phase']
        self.progress.enter('controller')
        try:
            return getattr(self.controller, name)(*args)
        except Exception:
            self.progress.update(failure_kind='controller_failure')
            raise
        finally:
            self.progress.enter(previous if previous == 'finalizing' else 'perception')

    def execute(self, *args):
        return self._call('execute', *args)

    def _command(self, *args):
        return self._call('_command', *args)

    def close(self):
        return self._call('close')


class ObservationFailure(RuntimeError):
    pass
