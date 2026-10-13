"""Cooperative budgets for Executive-owned offline work, never an agenda."""
from dataclasses import dataclass
import os
import math
import platform
from pathlib import Path
import resource
import time


class ResourceUnavailable(InterruptedError):
    reason = "other_resource"


class ThermalSuspended(ResourceUnavailable):
    reason = "thermal"


class MemoryUnavailable(ResourceUnavailable):
    reason = "memory"


class DevelopmentInterrupted(InterruptedError):
    """Application shutdown/deadline, distinct from resource ownership."""


@dataclass(frozen=True)
class DevelopmentResources:
    cpu_cores: int = 2
    memory_mb: int = 768
    temperature_c: float = 75.
    poll_seconds: float = .05
    recovery_temperature_c: float = 65.
    stabilization_seconds: float = 5.
    cooldown_poll_seconds: float = 1.
    require_thermal: bool = False  # ARM Linux always requires it, irrespective of this flag.

    def __post_init__(self):
        if not 1<=self.cpu_cores<=4 or not 128<=self.memory_mb<=4096:
            raise ValueError('bounded developmental CPU/memory budget required')
        if not 40<=self.temperature_c<=75 or not .01<=self.poll_seconds<=.1:
            raise ValueError('bounded thermal/ownership polling budget required')
        values=(self.recovery_temperature_c,self.stabilization_seconds,self.cooldown_poll_seconds)
        if not all(math.isfinite(v) for v in values) or not (0<self.recovery_temperature_c<self.temperature_c):
            raise ValueError('finite recovery threshold below thermal ceiling required')
        if not .1<=self.stabilization_seconds<=300 or not .05<=self.cooldown_poll_seconds<=10:
            raise ValueError('bounded stabilization/cooldown polling required')

    def apply(self):
        """Only called in the existing development process before heavy imports."""
        if hasattr(os,'sched_getaffinity'):
            allowed=sorted(os.sched_getaffinity(0))
            os.sched_setaffinity(0,allowed[-min(len(allowed),self.cpu_cores):])
        for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
            os.environ[name]=str(self.cpu_cores)


def resident_bytes(pid=None):
    # /proc may expose a different PID namespace than os.getpid().
    status=Path('/proc')/('self' if pid is None else str(pid))/'status'
    for line in status.read_text().splitlines():
        if line.startswith('VmRSS:'):return int(line.split()[1])*1024
    return 0


def owned_resident_bytes(proc_root=None):
    """Sample only this development process and its existing worker children."""
    proc=Path('/proc') if proc_root is None else proc_root
    total=resident_bytes();pending=[None];seen=set();count=0
    while pending:
        pid=pending.pop()
        path=proc/'thread-self'/'children' if pid is None else proc/str(pid)/'task'/str(pid)/'children'
        try:children=[int(i) for i in path.read_text().split()]
        except FileNotFoundError:continue # completed worker
        for child in children:
            if child in seen:continue
            seen.add(child)
            try:total+=resident_bytes(child)
            except FileNotFoundError:continue
            count+=1;pending.append(child)
    return total,count


def temperature():
    """Fail closed if an advertised sensor is unreadable or invalid."""
    values=[]
    for path in Path('/sys/class/thermal').glob('thermal_zone*/temp'):
        value=float(path.read_text())/1000.
        if not math.isfinite(value) or not 0<=value<=150:
            raise ValueError('invalid thermal-zone reading')
        values.append(value)
    return max(values,default=None)


class ResourceGuard:
    def __init__(self, policy=None, *, clock=None, owner=None, thermal_reader=None,
                 memory_reader=None, interruption_check=None, on_transition=None):
        self.policy=policy or DevelopmentResources()
        self.clock=clock or time.monotonic
        self.owner=owner
        self.thermal_reader=thermal_reader
        self.memory_reader=memory_reader
        self.interruption_check=interruption_check
        self.on_transition=on_transition
        machine=platform.machine().lower()
        self.require_thermal=self.policy.require_thermal or (platform.system()=='Linux' and
            (machine.startswith('arm') or machine.startswith('aarch64')))
        self.checked_at=None
        self.sample=dict(cpu_cores=self.policy.cpu_cores,memory_budget_mb=self.policy.memory_mb,
            temperature_limit_c=self.policy.temperature_c,ownership_poll_seconds=self.policy.poll_seconds)
        self.checks=0
        self.peak_owned_resident_bytes=0
        self.suspended=False
        self.cool_since=None
        self.thermal_state='running'
        self.thermal_reason=None
        self.resume_count=0
        self.blockage=None

    def thermal_snapshot(self):
        return dict(suspended=self.suspended,state=self.thermal_state,reason=self.thermal_reason,
            temperature_c=self.sample.get('temperature_c'),required=self.require_thermal,
            ceiling_c=self.policy.temperature_c,recovery_below_c=self.policy.recovery_temperature_c,
            stabilization_seconds=self.policy.stabilization_seconds,resume_count=self.resume_count,
            stable_for_seconds=(max(0,self.clock()-self.cool_since) if self.cool_since is not None else 0))

    def restore_suspension(self, snapshot):
        # Monotonic clocks cannot survive a restart; require a fresh stable interval.
        if snapshot.get('suspended'):
            self.suspended=True
            self._transition('thermal suspension','retained thermal interruption; fresh cooling verification required')

    def _transition(self,state,reason):
        changed=(state,reason)!=(self.thermal_state,self.thermal_reason)
        self.thermal_state,self.thermal_reason=state,reason
        if changed and self.on_transition:self.on_transition(self.thermal_snapshot())

    def _thermal(self,temp,now,error=None):
        if error or (temp is None and (self.require_thermal or self.suspended)):
            self.suspended=True;self.cool_since=None
            self._transition('thermal suspension','thermal telemetry unavailable or invalid; fail closed')
        elif temp is not None and temp>=self.policy.temperature_c:
            self.suspended=True;self.cool_since=None
            self._transition('thermal suspension','developmental temperature budget reached')
        elif self.suspended:
            if temp>=self.policy.recovery_temperature_c:
                self.cool_since=None
                self._transition('thermal suspension','waiting for temperature below recovery threshold')
            else:
                if self.cool_since is None:self.cool_since=now
                if now-self.cool_since>=self.policy.stabilization_seconds:
                    self._transition('recovery eligible','stable cooling verified; recheck all resources')
                    # Actual release occurs only after memory and ownership checks.
                else:self._transition('cooling','temperature below recovery threshold; stabilizing')
        if self.suspended and self.thermal_state!='recovery eligible':
            raise ThermalSuspended(self.thermal_reason)

    def check(self, *, force=False):
        # Cancellation must never be hidden by the normal sampling cache.
        if self.interruption_check:self.interruption_check()
        now=self.clock()
        if not force and self.checked_at is not None and now-self.checked_at<self.policy.poll_seconds:
            if self.blockage:raise self.blockage
            if self.suspended:raise ThermalSuspended(self.thermal_reason)
            return
        self.checked_at=now;self.checks+=1
        self.blockage=None
        from .cycle import gameplay_active
        if (self.owner or gameplay_active)():
            self.blockage=InterruptedError('primary gameplay owns time-critical resources; checkpoint learning')
            # Ownership interrupts continuous cooling verification too.
            self.cool_since=None
            raise self.blockage
        error=None
        try:
            temp=(self.thermal_reader or temperature)()
            if temp is not None and (isinstance(temp,bool) or not math.isfinite(temp) or not 0<=temp<=150):
                raise ValueError('invalid temperature')
        except (OSError,ValueError,TypeError,OverflowError):temp=None;error=True
        self.sample.update(temperature_c=temp,thermal_sensor_available=temp is not None,
            thermal_telemetry_required=self.require_thermal,ownership_checks=self.checks)
        try:
            self._thermal(temp,now,error)
        except ThermalSuspended as exc:
            self.blockage=exc
            raise
        try:rss,children=(self.memory_reader or owned_resident_bytes)()
        except OSError as exc:
            self.blockage=MemoryUnavailable('Development worker memory telemetry unavailable')
            raise self.blockage from exc
        self.peak_owned_resident_bytes=max(self.peak_owned_resident_bytes,rss)
        usage=resource.getrusage(resource.RUSAGE_SELF)
        self.sample.update(cpu_cores=self.policy.cpu_cores,memory_budget_mb=self.policy.memory_mb,
            temperature_limit_c=self.policy.temperature_c,ownership_poll_seconds=self.policy.poll_seconds,
            resident_bytes=rss,owned_worker_count=children,peak_rss_bytes=usage.ru_maxrss*1024,
            peak_owned_resident_bytes=self.peak_owned_resident_bytes,
            cpu_seconds=usage.ru_utime+usage.ru_stime)
        if rss>self.policy.memory_mb*1024**2:
            self.blockage=MemoryUnavailable('developmental resident-memory budget exceeded')
            raise self.blockage
        if self.suspended:
            self.suspended=False;self.cool_since=None;self.resume_count+=1
            self._transition('resumed work','thermal recovery; all resource preflight checks passed')
