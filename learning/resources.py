"""Cooperative budgets for Executive-owned offline work, never an agenda."""
from dataclasses import dataclass
import os
from pathlib import Path
import resource
import time


class ResourceUnavailable(InterruptedError):
    pass


@dataclass(frozen=True)
class DevelopmentResources:
    cpu_cores: int = 2
    memory_mb: int = 768
    temperature_c: float = 75.
    poll_seconds: float = .05

    def __post_init__(self):
        if not 1<=self.cpu_cores<=4 or not 128<=self.memory_mb<=4096:
            raise ValueError('bounded developmental CPU/memory budget required')
        if not 40<=self.temperature_c<=85 or not .01<=self.poll_seconds<=.1:
            raise ValueError('bounded thermal/ownership polling budget required')

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


def temperature():
    values=[]
    for path in Path('/sys/class/thermal').glob('thermal_zone*/temp'):
        try:values.append(float(path.read_text())/1000.)
        except (OSError,ValueError):continue
    return max(values,default=None)


class ResourceGuard:
    def __init__(self, policy=None, *, clock=None, owner=None):
        self.policy=policy or DevelopmentResources()
        self.clock=clock or time.monotonic
        self.owner=owner
        self.checked_at=None
        self.sample={}
        self.checks=0

    def check(self, *, force=False):
        now=self.clock()
        if not force and self.checked_at is not None and now-self.checked_at<self.policy.poll_seconds:
            return
        self.checked_at=now;self.checks+=1
        from .cycle import gameplay_active
        if (self.owner or gameplay_active)():
            raise InterruptedError('primary gameplay owns time-critical resources; checkpoint learning')
        rss=resident_bytes();temp=temperature()
        usage=resource.getrusage(resource.RUSAGE_SELF)
        self.sample=dict(cpu_cores=self.policy.cpu_cores,memory_budget_mb=self.policy.memory_mb,
            temperature_limit_c=self.policy.temperature_c,ownership_poll_seconds=self.policy.poll_seconds,
            resident_bytes=rss,peak_rss_bytes=usage.ru_maxrss*1024,
            cpu_seconds=usage.ru_utime+usage.ru_stime,temperature_c=temp,
            thermal_sensor_available=temp is not None,ownership_checks=self.checks)
        if rss>self.policy.memory_mb*1024**2:
            raise ResourceUnavailable('developmental resident-memory budget exceeded')
        if temp is not None and temp>=self.policy.temperature_c:
            raise ResourceUnavailable('developmental temperature budget reached')
