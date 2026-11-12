"""Finite issuer state machine. Production driver uses kernel/systemd facts.

No driver choice, command, approval fields or safe-idle assertions arrive from
an Executive request. All dependencies are selected by the protected daemon.
"""
import hashlib
import json
import math
import os
import sqlite3
import time
import threading
import uuid


class Scheduler:
    def __init__(self, driver, ledger, *, clock=time.time, monotonic=time.monotonic):
        self.writes=threading.RLock();self.notices=threading.RLock()
        self.driver=driver;self.clock=clock;self.mono=monotonic
        self.db=sqlite3.connect(ledger,check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS events (n INTEGER PRIMARY KEY, at REAL, slot TEXT, op TEXT, data TEXT)')
        self.db.execute("CREATE TRIGGER IF NOT EXISTS immutable_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'immutable'); END")
        self.db.execute("CREATE TRIGGER IF NOT EXISTS immutable_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'immutable'); END")
        self.db.commit();self.active=None
        rows=list(self.db.execute('SELECT slot,op FROM events ORDER BY n'))
        states={}
        for slot,op in rows:states[slot]=op
        self.notice_sequence=0
        for data, in self.db.execute("SELECT data FROM events WHERE op LIKE 'notice-%'"):
            self.notice_sequence=max(self.notice_sequence,json.loads(data).get('ack',{}).get('sequence',0))
        self.recovery_blocked=any(op not in ('available','refused') for op in states.values())

    def event(self, slot, op, **data):
        with self.writes:
            self.db.execute('INSERT INTO events(at,slot,op,data) VALUES (?,?,?,?)',
                            (self.clock(),slot,op,json.dumps(data,sort_keys=True,allow_nan=False)))
            self.db.commit()

    def policy(self):
        p=self.driver.policy()
        if (p.get('enabled') is not True or p.get('model')!='qwen3:1.7b'
                or p.get('model_digest')!='8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7'
                or type(p.get('max_seconds')) is not int or not 40<=p['max_seconds']<=90
                or type(p.get('daily_limit')) is not int or not 1<=p['daily_limit']<=4
                or not 3600<=p.get('cooldown',0)<=86400):raise PermissionError('standing policy unavailable')
        return p

    def reserve(self, commission, seconds, pid):
        p=self.policy()
        if self.recovery_blocked or self.active:raise PermissionError('prior completion or active reservation')
        if not isinstance(commission,str) or not commission or len(commission)>160 or type(seconds) is not int or not 40<=seconds<=p['max_seconds']:
            raise ValueError('bounded commission required')
        slot=uuid.uuid4().hex;requested=self.clock()+seconds
        end=self.driver.acquire(requested)  # actual deadline negotiation, kernel lock
        if not math.isfinite(end) or not 40<=end-self.clock()<=seconds+.01:
            self.driver.release();raise PermissionError('insufficient reserved time')
        self.active=dict(id=slot,commission=commission,pid=pid,ends_at=end,
            mono_end=self.mono()+end-self.clock(),policy_digest=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest(),
            initializing=True,sequence=0,last_notice=0,prepared=False,submitted=False,approval=None)
        try:
            self.event(slot,'reserved',commission=commission,ends_at=end,pid=pid)
            self.driver.watch_client(pid)
            self.check(notice=False)
            self.notice('PREPARING')
            self.active['initializing']=False
            return dict(id=slot,ends_at=end)
        except BaseException:
            self.finish('reservation refused');raise

    def notice(self, phase):
        with self.notices:
            a=self.active;self.notice_sequence+=1;a['sequence']=self.notice_sequence;a['last_notice']=self.mono()
            ack=self.driver.notice(a['id'],a['sequence'],phase)
            expected=phase!='CLEAR'
            if (not isinstance(ack,dict) or ack.get('sequence')!=a['sequence'] or ack.get('visible') is not expected
                    or (expected and (ack.get('slot')!=a['id'] or ack.get('phase')!=phase or not 0<ack.get('remaining_ms',0)<=2000))):
                raise PermissionError('display acknowledgement unavailable')
            a['last_notice']=self.mono();a['phase']=phase
            self.event(a['id'],'notice-'+phase.lower(),ack=ack,ends_at=a['ends_at'])
            return ack

    def check(self, notice=True):
        a=self.active
        if not a or a.get('closing'):raise PermissionError('no open active slot')
        p=self.policy()
        if hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()!=a['policy_digest']:
            raise PermissionError('policy revoked or changed')
        if self.mono()>=a['mono_end']-5 or self.clock()>=a['ends_at']-5 or not self.driver.client_alive():raise InterruptedError('client death or cutoff')
        snapshot=self.driver.inspect(a['ends_at'])
        for key in ('sensing','telemetry_deadline','watchdog_deadline','physical_task','gameplay','outstanding_lease','primary_pending','revoked','swap_used','throttled'):
            if snapshot.get(key) is not False:raise InterruptedError('unsafe or unknown '+key)
        if snapshot.get('independent_inventory_complete') is not True:raise PermissionError('unknown inventory')
        if any(type(snapshot.get(k)) not in (int,float) or not math.isfinite(snapshot[k])
               for k in ('temperature_c','available_gib','load','reserved_until')):
            raise PermissionError('unknown numeric resource state')
        if (snapshot.get('temperature_c',100)>=70 or snapshot.get('available_gib',0)<3
                or snapshot.get('load',100)>2 or snapshot.get('reserved_until',0)<a['ends_at']):
            raise InterruptedError('resource/deadline headroom')
        if notice:
            with self.notices:
                if not self.driver.notice_valid(a['id'],a['sequence']):raise InterruptedError('display lost or emergency')
        return snapshot

    def budget(self, commission, daily, cooldown):
        a=self.active;p=self.policy();self.check()
        if commission!=a['commission'] or daily!=p['daily_limit'] or cooldown!=p['cooldown']:
            raise PermissionError('caller cannot change standing budget')
        prior=list(self.db.execute("SELECT at,data FROM events WHERE op='budget'"))
        if (any(json.loads(data)['commission']==commission for _,data in prior)
                or sum(0<=self.clock()-at<86400 for at,_ in prior)>=daily
                or any(self.clock()-at<cooldown for at,_ in prior)):
            raise PermissionError('durable rate/replay budget')
        self.event(a['id'],'budget',commission=commission);a['budget']=True

    def prepare(self, model, digest, ends_at):
        a=self.active;self.check()
        if (not a.get('budget') or a['prepared'] or model!=self.policy()['model'] or digest!=self.policy()['model_digest']
                or ends_at>a['ends_at'] or a['ends_at']-self.clock()<40):raise PermissionError('preparation budget/identity')
        self.notice('THINKING');a['prepared']=True
        # Independent guardian already holds runtime.lock before any prewarm.
        approval=self.driver.prepare(a,model,digest)
        self.check();a['approval']=approval
        self.event(a['id'],'prepared',approval_digest=approval['digest'])
        return approval['path']

    def validate(self, digest):
        a=self.active;self.check()
        if not a['prepared'] or not a['approval'] or digest!=a['approval']['digest']:
            raise PermissionError('approval not independently issued')
        return dict(slot=a['id'],ends_at=a['ends_at'],identity=getattr(self.driver,'identity',{}))

    def mark_submission(self, digest):
        self.validate(digest)
        if self.active['submitted']:raise PermissionError('slot already submitted; no retry')
        self.event(self.active['id'],'submitted-unknown');self.active['submitted']=True
        self.driver.latch(self.active['id'])

    def retained(self, digest):
        self.validate(digest)
        if not self.active['submitted']:raise PermissionError('no submitted request')
        self.driver.unloaded(self.active['approval']['digest'])  # independent /api/ps proof; never trust client cleanup flag
        self.event(self.active['id'],'answer-retained');self.active['retained']=True

    def tick(self):
        if not self.active:return
        try:
            self.check()
            if self.mono()-self.active['last_notice']>=.75:self.notice(self.active['phase'])
        except Exception:self.finish('guard revoked')

    def finish(self, reason='completed'):
        a=self.active
        if not a:return
        a['closing']=True
        # Failure leaves durable recovery latch AND driver locks in place.
        try:
            self.driver.quiesce(a)
            try:self.notice('CLEAR')
            except Exception:
                self.driver.expire_notice(a)
                self.event(a['id'],'notice-clear-pending-ttl',verified_clear=False)
            unknown=a['submitted'] and not a.get('retained')
            if unknown:
                self.event(a['id'],'uncertain-completion',reason=reason);self.recovery_blocked=True
            else:
                self.driver.complete(a)
                self.event(a['id'],'available',reason=reason)
            self.driver.release();self.active=None
        except BaseException:
            self.event(a['id'],'cleanup-unknown',reason=reason);self.recovery_blocked=True
            raise
