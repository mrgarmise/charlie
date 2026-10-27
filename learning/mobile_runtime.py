"""Unarmed mobile acquisition through main.py; Executive remains lifecycle-owned."""
from pathlib import Path
import json
import subprocess
import time
import threading
from uuid import uuid4
from memory.evidence import EvidenceJournal
from .mobile import MobileEvidenceAdapter
from .resources import ResourceGuard
from vision.mobile_perception import MobileFrame, MobileFrameSource, MobilePerception, FrameArtifactStore, RecordingFrameSource
from vision.mobile_models import FixtureModel, HailoObjects, HailoRelativeDepth, UnavailableDepth
from behaviors.mobile_observe import MobileObserveBehavior


class ReplaySource:
    """Explicit fixture replay; virtual receipt clock, no hardware path."""
    def __init__(self, records):
        if not 1<=len(records)<=10000:raise ValueError('bounded fixture sequence required')
        self.records=iter(records);self.now=0.;self.sequence=0
    def read(self):
        import numpy as np
        self.row=next(self.records);self.sequence+=1
        at=self.row['at']
        if type(at) not in (int,float) or at<=self.now:raise ValueError('increasing fixture clock required')
        self.now=at
        w,h=self.row.get('geometry',[320,240])
        if type(w) is not int or type(h) is not int or not 1<=w<=4096 or not 1<=h<=4096:raise ValueError('bounded geometry required')
        return MobileFrame(f'fixture:{self.sequence}',np.zeros((h,w,3),dtype=np.uint8),at,
                           source='offline-fixture',sequence=self.sequence)
    def close(self):pass


class ReplayModel(FixtureModel):
    def __init__(self,source,key):super().__init__(None);self.source,self.key=source,key
    def infer(self,frame):
        self.result=self.source.row[self.key]
        return super().infer(frame)


def run_mobile(args, resources, frame_bus=None):
    if not 1<=args.mobile_frames<=10000:raise ValueError('mobile frames must be 1..10000')
    state=args.learning_state.resolve();state.mkdir(parents=True,exist_ok=True)
    revision=subprocess.run(['git','rev-parse','HEAD'],cwd=Path(__file__).resolve().parents[1],
                            capture_output=True,text=True,check=True).stdout.strip()
    if args.mobile_replay:
        if args.mobile_replay.stat().st_size>8*1024*1024:raise ValueError('fixture file too large')
        doc=json.loads(args.mobile_replay.read_text())
        if doc.get('schema')!='charlie.mobile.fixture.v1':raise ValueError('explicit fixture schema required')
        source=ReplaySource(doc['frames']);clock=lambda:source.now
        detector,depth=ReplayModel(source,'objects'),ReplayModel(source,'depth')
    else:
        if not args.mobile_manifest:raise ValueError('--mobile-manifest required for live unarmed models')
        config=json.loads(args.mobile_manifest.read_text())
        if config.get('schema')!='charlie.mobile.models.v1':raise ValueError('model manifest required')
        objects=dict(config['objects'])
        if getattr(args,'object_label_display','off')!='off':objects['include_all']=True
        detector=HailoObjects(**objects);depth=HailoRelativeDepth(**config['depth']) if config.get('depth') else UnavailableDepth()
        # Only a camera transport is initialized, never MobileBase/Deck/face behavior.
        from vision.camera_source import CameraSubscription
        source=CameraSubscription(frame_bus)
        source.switch('elegoo')
        clock=time.monotonic
    # One normal lifecycle/Executive owns the existing durable learning agenda.
    from .lifecycle import DevelopmentLifecycle
    from learning.capabilities import default_registry
    from attention.manager import AttentionManager
    from stimulus.bus import StimulusBus
    lifecycle=DevelopmentLifecycle(state,args.episode_root or [Path(__file__).resolve().parents[1]/'robotron-runs'],
        budget_seconds=args.learning_budget,resources=resources,history_roots=args.history_root)
    from contextlib import ExitStack
    with ExitStack() as owners:
        owners.callback(lifecycle.close)
        owners.callback(source.close)
        owners.callback(detector.close) if hasattr(detector,'close') else None
        owners.callback(depth.close) if hasattr(depth,'close') else None
        lifecycle.acquire()
        journal=EvidenceJournal(state/'mobile-evidence.sqlite3')
        adapter=MobileEvidenceAdapter(journal,episode='mobile:'+uuid4().hex,revision=revision,executive=lifecycle.executive)
        guard=ResourceGuard(resources)
        perception=MobilePerception(detector,depth,resources=guard,revision=revision,clock=clock)
        from vision.mobile_tracking import PetTracker
        mode=getattr(args,'object_label_display','off')
        if args.mobile_replay and mode=='rp2040':raise ValueError('fixture replay cannot activate physical display')
        from attention.object_display_runtime import attach
        labels,display_owned=attach(mode,clock=clock,port=args.object_label_port)
        if display_owned is not None:owners.callback(display_owned.close)
        bus=StimulusBus();attention=AttentionManager(bus,mobile_enabled=False,object_labels=labels)
        behavior=MobileObserveBehavior(source,perception,adapter,tracker=PetTracker(loss_seconds=2.),bus=bus)
        context=None
        if getattr(args,'pet_follow',False):
            from learning.mobile_safety import MobileSafetyContext
            from learning.deployment import CapabilityDeployment
            # Boot ID is emitted, never restored. Prior process grants cannot revive motion.
            boot_id=uuid4().hex
            print(json.dumps(dict(mobile_boot_id=boot_id,motion_authorized=False)),flush=True)
            context=MobileSafetyContext(CapabilityDeployment(lifecycle.journal),boot_id=boot_id,
                hardware_id=args.mobile_hardware_id,zone=args.mobile_zone,feed=args.mobile_safety_feed,clock=clock)
        if context is not None:context.health_check=lambda:guard.check(force=True)
        from motion.mobile_base import MobileBase
        behavior.bind_attention(attention,lifecycle.executive,default_registry(),context=context,base_factory=MobileBase)
        behavior.before_attention=lambda:lifecycle.journal.merge_from(journal)
        behavior.executive_resources={'offline-slot','context-evidence','model-evaluation','meditation-evidence'}
        from .mobile_review import labeled_pairs
        if labeled_pairs(lifecycle.journal):behavior.executive_resources.add('native-labeled-mobile-evidence')
        # Existing face/body activity can preempt on this same bus; no legacy conversion.
        status_at=[None]
        def between_steps():
            if status_at[0] is None or clock()-status_at[0]>=2:
                from .foundry import atomic_json
                atomic_json(state/'pet-ability-status.json',dict(abilities=default_registry().describe(behavior.readiness()),
                    attention=behavior.last_decision,execution=behavior.last_execution,
                    boot_id=context.boot_id if context else None,hardware_id=context.hardware_id if context else None,
                    zone=context.zone if context else None,physical_demonstration=False))
                status_at[0]=clock()
            if not args.mobile_replay and behavior.intent in ('decline','yield'):
                lifecycle.turn()  # Existing lifecycle owns the work; never a second chooser.

        behavior.retention=EventRetention(FrameArtifactStore(state/'mobile-pixels'),mode=args.mobile_retain,limit=args.mobile_captures)
        owners.callback(journal.close)
        owners.callback(attention.close)
        owners.callback(behavior.close)
        import signal
        if threading.current_thread() is threading.main_thread():
            previous=signal.getsignal(signal.SIGTERM)
            def terminate(signum,frame):raise KeyboardInterrupt('application termination; STOP on exit')
            signal.signal(signal.SIGTERM,terminate)
            owners.callback(signal.signal,signal.SIGTERM,previous)
        try:
            return watch(behavior,frames=args.mobile_frames,seconds=args.mobile_seconds,max_faults=args.mobile_max_faults,
                         clock=clock,fixture=bool(args.mobile_replay),between_steps=between_steps)
        finally:
            lifecycle.journal.merge_from(journal)


class EventRetention:
    def __init__(self,store,*,mode='events',limit=100):
        if mode not in ('none','events','all') or type(limit) is not int or not 0<=limit<=10000:raise ValueError('invalid retention policy')
        self.store,self.mode,self.limit=store,mode,limit
        self.saved=0;self.last_at=None
    def __call__(self,frame,observation,tracking):
        if not frame.authentic or self.mode=='none' or self.saved>=self.limit:return None
        event=any(d['label'] in ('cat','dog') for d in observation['objects'])
        if self.mode=='events' and (not event or (self.last_at is not None and frame.received_at-self.last_at<1.)):return None
        retained=self.store.retain(frame)
        self.saved+=1;self.last_at=frame.received_at
        return retained.artifact


def watch(behavior,*,frames,seconds,max_faults,clock=time.monotonic,cancel=None,fixture=False,publish=None,between_steps=None):
    import math
    if (type(frames) is not int or not 1<=frames<=10000 or not math.isfinite(seconds) or not 0<seconds<=3600
            or type(max_faults) is not int or not 1<=max_faults<=100):raise ValueError('bounded watcher required')
    cancel=cancel or threading.Event();started=clock();last_status=started;consecutive=0
    counts=dict(records=0,frames=0,polls=0,faults=0,motion_authorized=False,mode='fixture' if fixture else 'unarmed-perception',
                native_qualified=False,physical_qualified=False)
    latencies=[];inference=[]
    if publish is None:publish=lambda v:print(json.dumps(v,allow_nan=False),flush=True)
    try:
        for _ in range(frames):
            if cancel.is_set() or clock()-started>=seconds:break
            counts['polls']+=1
            try:result=behavior.step()
            except StopIteration:break
            except (TimeoutError,EOFError,OSError,InterruptedError) as exc:
                counts['faults']+=1;consecutive+=1
                for model in (behavior.perception.detector,behavior.perception.depth):
                    if hasattr(model,'close'):model.close()
                publish(dict(status='observation suspended',error=type(exc).__name__,**counts))
                if consecutive>=max_faults or cancel.is_set():break
                if not fixture:cancel.wait(min(2.,.1*2**min(consecutive,4)))
                continue
            consecutive=0
            if getattr(behavior,'frame_acquired',result is not None):counts['frames']+=1
            if result is None and not fixture:cancel.wait(.02)
            if result:
                counts['records']+=1
                execution=result['execution']
                counts['dispatch_attempts']=counts.get('dispatch_attempts',0)+(execution.get('dispatched') is not False)
                counts['acknowledged']=counts.get('acknowledged',0)+(execution.get('acknowledged') is True)
                counts['last_attention']=result.get('attention')
                counts['native_qualified']=result['observation'].get('qualification')=='native-qualified'
                counts['motion_authorized']=bool(getattr(behavior.gate,'lease',None) and
                    behavior.gate.lease.valid(clock(),behavior.gate.boot_id))
                latencies.append(result['observation']['receipt_to_decision_seconds'])
                inference.append(sum(result['observation']['inference_seconds'].values()))
                publish(dict(evidence_id=result['evidence_id'],target=result['tracking']['target'],
                             proposal=result['proposal'],execution=result['execution']))
            if between_steps is not None:between_steps()
            if clock()-last_status>=5:
                publish(dict(status='stationary observing',**counts));last_status=clock()
    except KeyboardInterrupt:
        behavior.acquisition_fault(InterruptedError('operator cancelled stationary watcher'))
        counts['cancelled']=True
    finally:behavior.close()
    import numpy as np
    for name,values in (('receipt_to_decision_seconds',latencies),('inference_seconds',inference)):
        if values:counts[name]={f'p{q}':float(np.percentile(values,q)) for q in (50,95,99)}
    counts.update(source_capture_age='unknown; receipt age is not exposure age',elapsed_seconds=max(0,clock()-started))
    publish(counts)
    return counts


def import_mobile_evidence(lifecycle):
    """Called by existing Executive acquisition turn; never another scheduler."""
    before=len(lifecycle.journal.records())
    paths=[lifecycle.output/'mobile-evidence.sqlite3']
    paths+=sorted((lifecycle.output/'mobile-native').glob('*/native-evidence.sqlite3'))
    for path in paths[:17]:
        if not path.exists():continue
        source=EvidenceJournal(path,read_only=True)
        try:
            if path.name=='native-evidence.sqlite3' and any(r.data['payload'].get('category') not in ('mobile_native_prediction','mobile_operator_annotation','mobile_native_reported_fault','mobile_reference_frame','mobile_reference_annotation') for r in source.records()):
                raise ValueError('native mobile intake contains non-mobile records')
            lifecycle.journal.merge_from(source)
        finally:source.close()
    from .mobile_review import reflect_native
    reflect_native(lifecycle.executive,lifecycle.journal)
    # Interpretation stays on the existing Executive's thread/journal, where
    # native qualification and fixture exclusions are independently rechecked.
    adapter=MobileEvidenceAdapter(lifecycle.journal,episode='mobile-opportunities',revision='mobile-v1',
                                  executive=lifecycle.executive,gateway=lifecycle.gateway)
    for row in lifecycle.journal.category_records('observation','mobile_perception'):
        # Reflection sources must stay in their original episode.
        adapter.episode=row.data['episode']
        adapter.opportunities(row.id)
    return len(lifecycle.journal.records())!=before
