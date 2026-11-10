"""Standing policy enforcement over an independently owned scheduler backend.

This module never constructs native approval documents. The backend must live
outside the Executive trust domain and retain runtime exclusion through forced
cutoff. No backend is installed by this source change; native default is denial.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import math
import time
from .meditation_consultation import Slot


@dataclass(frozen=True)
class StandingPolicy:
    enabled: bool = False
    model: str = 'qwen3:1.7b'
    model_digest: str = '8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7'
    max_slot_seconds: int = 90
    max_daily: int = 4
    cooldown_seconds: int = 3600

    def __post_init__(self):
        import re
        if (type(self.enabled) is not bool or self.model!='qwen3:1.7b'
                or not re.fullmatch('[a-f0-9]{64}',self.model_digest)
                or type(self.max_slot_seconds) is not int or not 40<=self.max_slot_seconds<=120
                or type(self.max_daily) is not int or not 1<=self.max_daily<=4
                or not 60<=self.cooldown_seconds<=86400):
            raise ValueError('bounded local standing policy required')


class StandingSlotAuthority:
    """Backend interface is a required external dependency, not a safe-idle flag.

    exclusive() acquires the *same* operational runtime lock, denies unqualified
    owner inventories and yields a trusted lease. lease.inspect() reads primary
    owner state and live kernel/thermal telemetry independently; lease.prepare()
    drives finite prewarm/service lifecycle and issues the existing boot/revision/
    receipt-bound Admission in its private domain. finish() must wait for observed
    cgroup empty or its qualified hard cutoff BEFORE releasing exclusion, including
    on STOP, exceptions, or lost request completion. No Executive callback may
    implement that backend on Pi. NativeSlotAuthority remains the default stub.
    """
    def __init__(self, policy, backend, clock=time.time):
        self.policy=policy;self.backend=backend;self.clock=clock

    def _check(self, lease, end):
        status=lease.inspect()
        if status.get('independent_inventory_complete') is not True:
            raise PermissionError('unknown owner/deadline inventory')
        for field in ('sensing','telemetry_deadline','watchdog_deadline','physical_task','gameplay','outstanding_lease','primary_pending','revoked','swap_used','throttled'):
            if status.get(field) is not False:raise InterruptedError('unsafe or unknown '+field)
        for field in ('temperature_c','available_gib','load','reserved_until'):
            if type(status.get(field)) not in (int,float) or not math.isfinite(status[field]):
                raise PermissionError('unknown resource headroom')
        if (status['temperature_c']>=70 or status['available_gib']<3 or status['load']>2
                or status['reserved_until']<end or self.clock()>=end-5):
            raise InterruptedError('insufficient exclusive slot headroom')

    @contextmanager
    def reserve(self, *, commission_id, seconds):
        p=self.policy
        if not p.enabled or not 40<=seconds<=p.max_slot_seconds:
            raise PermissionError('standing policy disabled or slot budget exceeded')
        # The backend verifies its independently accepted deployment/issuer identity.
        # This Python object is not, and cannot be, a process isolation boundary.
        with self.backend.exclusive(commission_id,seconds) as lease:
            end=self.clock()+seconds
            self._check(lease,end)
            # Rate ledger must be durable in the independent authority, not only
            # the Executive queue. reserve_budget is atomic and replay resistant.
            lease.reserve_budget(commission_id,p.max_daily,p.cooldown_seconds)
            try:
                approval_path=lease.prepare(model=p.model,digest=p.model_digest,ends_at=end)
                self._check(lease,end)
                yield Slot(lease.id,approval_path,end,lambda:self._check(lease,end))
            finally:
                # Backend owns forced cutoff even if the Executive dies entirely.
                lease.finish(ends_at=end)
