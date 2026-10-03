"""Reusable CAL-1 evidence, immutable profile history and conservative derivation.

No imports open hardware. Profiles remain candidates until independent physical
review; qualification is never inferred from simulated evidence.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import threading
from datetime import datetime, timezone

HARDWARE = dict(controller='rp2040',head_a=[4,5],head_b_disabled=[14,15],
                calibration_input=10,calibration_input_only=True)


def timestamp(): return datetime.now(timezone.utc).isoformat()
def encode(value): return json.dumps(value,sort_keys=True,allow_nan=False,separators=(',',':')).encode()
def identifier(value):
    if not isinstance(value,str) or not 8<=len(value)<=64 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in value):
        raise ValueError('invalid identifier')
    return value


def durable_write(path, raw, *, exclusive=True):
    path=Path(path)
    with path.open('xb' if exclusive else 'wb') as f:
        f.write(raw);f.flush();os.fsync(f.fileno())
    descriptor=os.open(path.parent,os.O_RDONLY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


class CalibrationJournal:
    def __init__(self, path, *, simulated, journal=None):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.file=self.path.open('x');self.lock=threading.Lock();self.journal=journal
        self.simulated=simulated
        self.append(dict(kind='provenance',hardware=HARDWARE,simulated=simulated))

    def append(self, event):
        record=dict(at=timestamp(),simulated=self.simulated,event=event)
        with self.lock:
            self.file.write(encode(record).decode()+'\n');self.file.flush();os.fsync(self.file.fileno())
            if self.journal:
                self.journal.append('event',dict(category='neck_calibration',**record),
                    episode=str(self.path.resolve()),producer='CAL-1',version='1')
        return record

    def close(self): self.file.close()


class ProfileRepository:
    def __init__(self,directory):
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)

    def save(self,document):
        name=identifier(document['calibration_id'])
        if document.get('hardware')!=HARDWARE: raise ValueError('incompatible hardware')
        durable_write(self.directory/(name+'.json'),encode(document))
        return name

    def read(self,name):
        return json.loads((self.directory/(identifier(name)+'.json')).read_bytes())

    def active(self):
        pointer=json.loads((self.directory/'activation.json').read_bytes())
        name=identifier(pointer['calibration_id'])
        if (self.directory/(name+'.quarantine.json')).exists() or (self.directory/(name+'.running')).exists(): raise ValueError('profile quarantined or unclean operation')
        raw=(self.directory/(name+'.json')).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pointer['sha256']: raise ValueError('profile digest mismatch')
        result=json.loads(raw)
        from rp2040.neck_profile_schema import validate
        validate(result)
        if result.get('validation_status')!='QUALIFIED' or result.get('simulated') is not False or result.get('hardware')!=HARDWARE:
            raise ValueError('unverified profile')
        return result

    def activate(self,name):
        document=self.read(name)
        from rp2040.neck_profile_schema import validate
        validate(document)
        if (document.get('validation_status')!='QUALIFIED' or document.get('simulated') is not False
                or document.get('hardware')!=HARDWARE or (self.directory/(name+'.quarantine.json')).exists()
                or (self.directory/(name+'.running')).exists()):
            raise ValueError('qualified non-quarantined physical profile required')
        old=None
        if (self.directory/'activation.json').exists():
            old=json.loads((self.directory/'activation.json').read_bytes())['calibration_id']
        if old and old not in document.get('supersedes',[]): raise ValueError('superseded history required')
        raw=(self.directory/(name+'.json')).read_bytes()
        record=dict(calibration_id=name,sha256=hashlib.sha256(raw).hexdigest(),at=timestamp(),supersedes=old)
        durable_write(self.directory/(name+'.activation-history.json'),encode(record))
        tmp=self.directory/'activation.pending'
        durable_write(tmp,encode(record),exclusive=False)
        os.replace(tmp,self.directory/'activation.json')
        fd=os.open(self.directory,os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
        return record

    def quarantine(self,name,reason,evidence):
        path=self.directory/(identifier(name)+'.quarantine.json')
        if not path.exists(): durable_write(path,encode(dict(at=timestamp(),reason=reason,
            evidence=evidence,status='QUARANTINED',scope='entire_profile')))


def derive_candidate(evidence_path, commissioning, *, name, margin, supersedes=()):
    """Shrink a fully observed 3x3 Cartesian grid; never extrapolate endpoints.

    This is a candidate, not proof that interpolated mechanical clearance is
    safe. Independent physical path/clearance review remains mandatory.
    """
    raw=Path(evidence_path).read_bytes()
    records=[json.loads(line) for line in raw.splitlines()]
    events=[r['event'] for r in records]
    firmware=[e for e in events if 'seq' in e]
    if not firmware or len({e['seq'] for e in firmware})!=len(firmware) or any(b['seq']!=a['seq']+1 for a,b in zip(firmware,firmware[1:])):
        raise ValueError('complete ordered firmware evidence required')
    if len({e.get('run_id') for e in firmware})!=1 or len({e.get('session') for e in firmware})!=1:
        raise ValueError('one calibration run and session required')
    if not records or any(r.get('simulated')!=records[0].get('simulated') for r in records):
        raise ValueError('provenance mismatch')
    if any(e.get('kind')=='interruption' for e in events) or not any(e.get('kind')=='finished' for e in events):
        raise ValueError('completed uninterrupted calibration required')
    starts=[e for e in events if e.get('kind')=='initial_verified']
    if len(starts)!=1: raise ValueError('exactly one verified start required')
    completed=[e for e in events if e.get('kind')=='movement_completed']
    confirmed=[e for e in events if e.get('kind')=='confirmed']
    if not completed or {e['step_id'] for e in completed}!={e['step_id'] for e in confirmed}:
        raise ValueError('every completed movement must be confirmed')
    points={tuple(starts[0]['verified_pose'])}
    responses={'pan':[],'tilt':[]}
    previous=starts[0]['verified_pose']
    for event in confirmed:
        proof=event.get('operator_confirmation',{})
        if not all(proof.get(k) is True for k in ('clearance_verified','no_binding','settled','supervised')):
            raise ValueError('clearance evidence required')
        if any(not math.isfinite(float(v)) for v in event['visual_displacement']): raise ValueError('invalid vision evidence')
        if sum(float(v)**2 for v in event['visual_displacement'])<=0:
            raise ValueError('unsuccessful movement requires diagnosis, not qualification')
        if any(abs(a-b)>1e-5 for a,b in zip(event['commanded_pose'],event['requested_pose'])): raise ValueError('unsettled commanded estimate')
        points.add(tuple(round(v,8) for v in event['commanded_pose']))
        delta=[b-a for a,b in zip(previous,event['requested_pose'])]
        axis=0 if abs(delta[0])>1e-8 else 1
        if abs(delta[axis])<=1e-8 or abs(delta[1-axis])>1e-8 or abs(delta[axis])>commissioning['max_step']+1e-6:
            raise ValueError('one bounded axis per evidence step required')
        responses[('pan','tilt')[axis]].append([float(v)/delta[axis] for v in event['visual_displacement']])
        previous=event['requested_pose']
    pans=sorted({p[0] for p in points});tilts=sorted({p[1] for p in points})
    if len(pans)<3 or len(tilts)<3 or any((p,t) not in points for p in pans for t in tilts):
        raise ValueError('fully observed combined-axis grid required')
    if not math.isfinite(margin) or not 0<margin<=2: raise ValueError('positive conservative margin required')
    lo=[pans[0]+margin,tilts[0]+margin];hi=[pans[-1]-margin,tilts[-1]-margin]
    if any(a>=b for a,b in zip(lo,hi)): raise ValueError('margin consumes region')
    start=starts[0]['verified_pose']
    if any(not lo[i]<=start[i]<=hi[i] for i in range(2)): raise ValueError('start outside conservative region')
    vertices=[[lo[0],lo[1]],[hi[0],lo[1]],[hi[0],hi[1]],[lo[0],hi[1]]]
    # Replay the same convex constraints used by RP2040 (pure math, no hardware).
    from rp2040.motion_geometry import polygon,contains
    region=polygon(commissioning['clearance_polygon'])
    if any(not contains(region,p,commissioning['commissioning_margin']) for p in points):
        raise ValueError('evidence outside commissioning constraints')
    profile=dict(schema='charlie-neck-profile-v1',hardware=HARDWARE,calibration_id=identifier(name),
        assembled_head_verified=True,validation_status='CANDIDATE',created_at=timestamp(),qualified_at=None,
        supersedes=list(supersedes),simulated=records[0]['simulated'],pins=[4,5],
        pose_source='operator_confirmed_estimate',measured_position=None,confirmed_arm_pose=start,home_pose=start,
        clearance_polygon=vertices,clearance_margin=margin,
        max_rate=min(commissioning['max_rate'],2),max_step=min(commissioning['max_step'],1),
        evidence_sha256=hashlib.sha256(raw).hexdigest(),evidence=str(Path(evidence_path).resolve()),
        commissioning_id=commissioning['calibration_id'])
    profile['observation_size']=commissioning['observation_size']
    import statistics
    model={}
    for axis,samples in responses.items():
        if len(samples)<2: raise ValueError('repeated visual response evidence required')
        vector=[statistics.median(s[i] for s in samples) for i in (0,1)]
        magnitude=math.sqrt(sum(v*v for v in vector))
        if magnitude<.05 or any(math.sqrt(sum((s[i]-vector[i])**2 for i in (0,1)))>magnitude*.5 for s in samples):
            raise ValueError('inconsistent visual response; supervised diagnosis required')
        model[axis]=vector
    profile['visual_response']=model
    for i,axis in enumerate(('pan','tilt')):
        a=commissioning[axis]
        def pulse(angle): return a['min_us']+(angle-a['min'])*(a['max_us']-a['min_us'])/(a['max']-a['min'])
        profile[axis]=dict(min=lo[i],max=hi[i],min_us=pulse(lo[i]),max_us=pulse(hi[i]))
    return profile


def independently_qualify(candidate, *, name, reviewer, evidence, physical_validation=False):
    if candidate.get('validation_status')!='CANDIDATE' or candidate.get('simulated') is not False or not physical_validation:
        raise ValueError('independent physical qualification required')
    raw=Path(candidate['evidence']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=candidate['evidence_sha256']: raise ValueError('evidence changed')
    events=[json.loads(line)['event'] for line in raw.splitlines()]
    operators={e['operator_confirmation']['operator'] for e in events if 'operator_confirmation' in e}
    if reviewer in operators or not operators: raise ValueError('independent reviewer required')
    review_raw=Path(evidence).read_bytes()
    review=json.loads(review_raw)
    if (review.get('schema')!='charlie-neck-qualification-v1' or review.get('reviewer')!=reviewer
            or review.get('candidate_id')!=candidate['calibration_id']
            or review.get('candidate_sha256')!=hashlib.sha256(encode(candidate)).hexdigest()
            or review.get('evidence_sha256')!=candidate['evidence_sha256']
            or review.get('simulated') is not False
            or any(review.get(k) is not True for k in ('physical_validation','interval_clearance_verified',
                 'initial_pulse_verified','torque_release_verified','watchdog_and_cutoff_verified'))):
        raise ValueError('independent physical qualification report required')
    result=json.loads(encode(candidate))
    result.update(calibration_id=identifier(name),validation_status='QUALIFIED',qualified_at=timestamp(),
        independent_review=dict(operator=sorted(operators)[0],reviewer=identifier(reviewer),
                                evidence=str(Path(evidence).resolve()),report_sha256=hashlib.sha256(review_raw).hexdigest(),physical_validation=True))
    result['supersedes']=list(dict.fromkeys(candidate['supersedes']+[candidate['calibration_id']]))
    from rp2040.neck_profile_schema import validate
    validate(result)
    return result


class SupervisedCalibration:
    """Existing UART transport + durable log; never owns PWM or camera."""
    def __init__(self, controller, evidence):
        self.controller,self.evidence=controller,evidence
        self.previous_sink=getattr(controller,'calibration_sink',None)
        controller.calibration_sink=evidence.append

    def request(self,data):
        status=self.controller.motion_status()
        if not status or status.get('session')!=self.controller.link_session: raise ConnectionError('live session required')
        self.evidence.append(dict(kind='operator_request',request=data,epoch=status['epoch']))
        command='CAL '+self.controller.link_session+' '+str(status['epoch'])+' '+encode(data).decode()
        if not self.controller._accepted(command,'CAL'): raise PermissionError('RP2040 rejected calibration request')
        return self.poll()

    def poll(self):
        answer=self.controller._exchange('CAL_STATUS','CAL_STATUS ')
        if not answer: raise ConnectionError('calibration disconnected')
        return json.loads(answer.split(' ',1)[1])

    def close(self):
        try:
            self.evidence.append(dict(kind='interruption_requested',reason='supervisor_closed'))
            self.controller.stop()
            self.poll()
        finally: self.controller.calibration_sink=self.previous_sink
