"""One Executive: reserve + warn across thinking, optional existing consultation."""
from contextlib import contextmanager
import time
from learning.meditation_consultation import Slot
from .client import NativeBackend


class NativeMeditationCoordinator:
    def __init__(self, consultation, backend=None):
        self.consultation=consultation;self.backend=backend or NativeBackend();self.lease=None
        self.journal=consultation.queue.journal;self.interactions=[]
        pending={}
        for row in self.journal.category_records('event','native_meditation'):
            payload=row.data['payload']
            if payload['phase']=='interaction-delayed':pending[payload['interaction_id']]=dict(id=payload['interaction_id'],state='delayed')
            if payload['phase']=='available':
                for identifier in payload.get('resumed',[]):pending.pop(identifier,None)
        self.interactions=list(pending.values())
        if pending:
            try:
                if self.backend.status().get('available') is True:
                    self.event('available',resumed=list(pending),recovered=True)
                    self.interactions.clear()
            except Exception:pass  # keep durable deferred IDs; no fabricated availability

    def event(self, phase, **data):
        return self.journal.append('event',dict(category='native_meditation',phase=phase,
            at=time.time(),slot=self.lease.id if self.lease else None,**data),episode='native-meditation',
            producer='LearningExecutive:meditation',version='native-meditation-v1')

    def refresh(self, check=lambda:None):return self.consultation.refresh(check)

    @contextmanager
    def window(self, commission_id, check, *, client_deadline):
        if not self.consultation.enabled:
            yield check
            return
        self.event('requesting',commission=commission_id)
        lease=None;cleaned=False
        try:
            with self.backend.exclusive(commission_id,self.consultation.slot_seconds) as lease:
                self.lease=lease
                self.event('reserved/preparing',ends_at=lease.ends_at)
                lease.phase('MEDITATING')  # server has already positively acknowledged PREPARING
                self.event('meditating',ends_at=lease.ends_at)
                def guard():check();lease.inspect()
                guard()
                yield guard
                # One optional eligible question, same root reservation and notice.
                previous=self.consultation.authority
                coordinator=self
                class Borrowed:
                    @contextmanager
                    def reserve(self, *, commission_id, seconds):
                        lease.reserve_budget(commission_id,coordinator.consultation.daily_limit,coordinator.consultation.cooldown)
                        path=lease.prepare(model='qwen3:1.7b',digest='8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7',ends_at=lease.ends_at)
                        coordinator.event('consulting',ends_at=lease.ends_at)
                        yield Slot(lease.id,path,lease.ends_at,lease.inspect)
                self.consultation.authority=Borrowed()
                try:self.consultation.on_meditation(commission_id,guard,client_deadline=client_deadline)
                finally:self.consultation.authority=previous
            cleaned=True
        except BaseException as exc:
            self.event('cancelled/error',reason=type(exc).__name__)
            cleaned=lease is not None and getattr(lease,'finished',False)
            from learning.lifecycle import MeditationYield
            if isinstance(exc,Exception) and not isinstance(exc,MeditationYield):
                raise MeditationYield('native meditation deferred: '+type(exc).__name__) from exc
            raise
        finally:
            # Backend context completes model quiescence + acknowledged clear/TTL
            # before this transition. Failure is never advertised as available.
            self.lease=None
            if cleaned:
                self.event('available',resumed=[i['id'] for i in self.interactions])
                for interaction in self.interactions:interaction['state']='ready'
                self.interactions.clear()

    def on_meditation(self,*args,**kwargs):
        raise RuntimeError('native coordinator must enclose the actual meditation window')

    def interaction(self, identifier, *, urgent=False):
        if urgent:
            self.backend.emergency();self.event('emergency',interaction_id=identifier)
            return dict(id=identifier,state='urgent-released')
        if not self.lease:return dict(id=identifier,state='ready')
        if not isinstance(identifier,str) or not identifier or len(identifier)>128 or len(self.interactions)>=16:
            raise ValueError('bounded pending interaction queue')
        existing=next((i for i in self.interactions if i['id']==identifier),None)
        if existing is not None:return existing
        item=dict(id=identifier,state='delayed',message='Charlie is meditating; urgent requests still interrupt.')
        if not any(i['id']==identifier for i in self.interactions):self.interactions.append(item);self.event('interaction-delayed',interaction_id=identifier)
        return item
