"""Callable meditation sub-slot coordinator; no second Executive or native bypass.

Native guard intentionally denies until external scheduler isolation is qualified.
A test authority is an injected dependency, never an OS trust boundary.
"""
from dataclasses import dataclass
from contextlib import contextmanager, ExitStack
import fcntl
import math
import time
import uuid
from pathlib import Path
from .question_selection import discover, fingerprint, context_for
from .consultation_activation import OperationalProvider


class NativeSlotAuthority:
    """Explicit native integration stub. No Executive-supplied safe flags accepted.

    External dependency: independently owned runtime.lock scheduler, exhaustive
    camera/telemetry/watchdog/lease inventory, revocation channel, private receipt
    issuer and bounded service lifecycle driver. A JSON file from the Executive
    cannot replace this boundary. Existing per-window Admission remains required.
    """
    @contextmanager
    def reserve(self, *, commission_id, seconds):
        raise PermissionError('native trusted-slot guard not yet qualified')
        yield  # context manager protocol; never an admission


@dataclass(frozen=True)
class Slot:
    id: str
    approval_path: str
    ends_at: float
    check: object


class MeditationConsultations:
    def __init__(self, queue, paths, authority=None, *, enabled=False,
                 provider_factory=OperationalProvider, clock=time.time,
                 daily_limit=4, cooldown=3600, slot_seconds=90):
        if (type(enabled) is not bool or not 1<=daily_limit<=4 or not 60<=cooldown<=86400
                or not 40<=slot_seconds<=120):raise ValueError('finite standing policy required')
        self.queue=queue;self.paths=list(paths);self.authority=authority or NativeSlotAuthority()
        self.enabled=enabled;self.provider_factory=provider_factory;self.clock=clock
        self.daily_limit=daily_limit;self.cooldown=cooldown;self.slot_seconds=slot_seconds
        self.catalog=None

    def refresh(self, check=lambda:None):
        """Bounded offline preparation, outside time-critical meditation slice."""
        report=discover(self.paths,now=self.clock(),check=check)
        self.catalog=report
        if report['errors'] or report['truncated']:return report
        for item in report['candidates']:
            if item['eligible']:
                try:self.queue.queue(item)
                except ValueError:break  # full bounded queue
        return report

    def _attempts(self):
        return [r.data['payload'] for r in self.queue.journal.category_records('event','generalized_question')
                if r.data['payload']['state']=='admission-pending']

    def on_meditation(self, commission_id, check=lambda:None, *, selected_id=None):
        """Called only after an Executive commission, at a stable checkpoint.

        Selection is automatic unless a manual selected_id is supplied. No retry
        after admission starts, even if admission later refuses, without review.
        """
        if not self.enabled:return None
        check()
        if not self.catalog or self.catalog['errors'] or self.catalog['truncated']:return None
        states=self.queue.states()
        # A reset after a possible dispatch/durable receipt is globally latched.
        # No automatic retry or new question can hide an unresolved completion.
        if any(s['state'] in ('admission-pending','submitted/unknown','answer-durable',
                              'provider-cleanup-confirmed','uncertain-completion') for s in states.values()):
            return None
        eligible=[s for s in states.values() if s['state'] in ('queued','operator-selected','deferred-to-next-eligible-meditation')
                  and (selected_id is None or s['item']['id']==selected_id)]
        if not eligible:return None
        eligible.sort(key=lambda s:(-s['item']['score'],s['item']['committed_at'],s['item']['id']))
        item=eligible[0]['item']; now=self.clock()
        attempts=self._attempts()
        if (sum(0<=now-p['timestamp']<86400 for p in attempts)>=self.daily_limit
                or any(now-p['timestamp']<self.cooldown for p in attempts)
                or any(p.get('commission_id')==commission_id for p in attempts)):
            return self.queue.event(item,'deferred-to-next-eligible-meditation',reason='finite rate/cooling or commission replay budget')
        provider=None;attempt=uuid.uuid4().hex; started=False
        try:
            # Cross-process queue ownership; separate from independently held runtime.lock.
            with (self.queue.journal.path.parent/'question-execution.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                # Re-read under lock to prevent stale selections by another process.
                if self.queue.states()[item['id']]['state'] not in ('queued','operator-selected','deferred-to-next-eligible-meditation'):return None
                # Refuse changed source, status drift and newly retained answers.
                fresh=discover(self.paths,now=self.clock(),check=check)
                current=next((q for q in fresh['candidates'] if q['id']==item['id']),None)
                if fresh['errors'] or fresh['truncated'] or not current or not current['eligible']:
                    return self.queue.event(item,'rejected',reason='source eligibility changed')
                if current['locations']!=item['locations']:
                    return self.queue.event(item,'rejected',reason='source fingerprint changed; review required')
                with self.authority.reserve(commission_id=commission_id,seconds=self.slot_seconds) as slot, ExitStack() as cleanup:
                    def guard():
                        check();slot.check()
                        if not math.isfinite(slot.ends_at) or self.clock()>=slot.ends_at-5:
                            raise InterruptedError('safe slot cutoff headroom')
                    guard()
                    if slot.ends_at-self.clock()<35:raise InterruptedError('insufficient consultation headroom')
                    self.queue.event(item,'admission-pending',attempt_id=attempt,commission_id=commission_id,
                                     slot_id=slot.id,context=context_for(item))
                    started=True
                    provider=self.provider_factory(slot.approval_path)
                    cleanup.callback(provider.close)
                    admitted=False
                    def monitor():
                        nonlocal admitted
                        guard()
                        if provider.status()['state']=='request-in-flight' and not admitted:
                            self.queue.event(item,'submitted/unknown',attempt_id=attempt,slot_id=slot.id)
                            admitted=True
                    result=provider.consult(context_for(item)['text'],monitor)
                    guard()
                    if (not isinstance(result.get('answer'),str) or not result['answer'].strip()
                            or len(result['answer'].encode())>8192 or not result.get('identity',{}).get('model_digest')):
                        raise ValueError('bounded qualified result required')
                    self.queue.event(item,'answer-durable',attempt_id=attempt,result=result,
                        original_question_id=item['question_id'],prompt_digest=context_for(item)['digest'],
                        trust='unverified_hypothesis',physical_authorization=False,model_update=False)
                    provider.retained()
                    if provider.status()['state']!='completed-unload-confirmed':
                        return self.queue.event(item,'uncertain-completion',attempt_id=attempt,reason='cleanup unconfirmed')
                    self.queue.event(item,'provider-cleanup-confirmed',attempt_id=attempt)
                    return self.queue.event(item,'awaiting-evaluation',attempt_id=attempt,trust='unverified_hypothesis')
        except (Exception, KeyboardInterrupt) as exc:
            return self.queue.event(item,'uncertain-completion' if started else 'deferred-to-next-eligible-meditation',
                                    attempt_id=attempt,reason=type(exc).__name__+'; no retry after admission-pending')
        finally:
            if provider is not None:provider.close()


class ManualApprovalSlot:
    """Manual fallback only: consumes an independently issued one-off Admission.

    Never issues consent or safe flags. Native standing automation cannot select
    this adapter implicitly. Caller must already have an independently reserved
    entire service lifetime; this class does not manufacture a safe interval.
    """
    def __init__(self, approval, runtime_lock):
        self.approval=Path(approval);self.runtime_lock=Path(runtime_lock)

    @contextmanager
    def reserve(self, *, commission_id, seconds):
        from .consultation_activation import Admission
        from .runtime_exclusion import runtime_exclusion
        with runtime_exclusion(self.runtime_lock):
            admission=Admission(self.approval)
            admission.check(starting=True)
            yield Slot(commission_id,str(self.approval),admission.doc['expires_at'],admission.check)
