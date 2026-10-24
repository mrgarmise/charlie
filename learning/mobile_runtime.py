"""Unarmed mobile acquisition through main.py; Executive remains lifecycle-owned."""
from pathlib import Path
import json
import subprocess
import time
from uuid import uuid4
from memory.evidence import EvidenceJournal
from .mobile import MobileEvidenceAdapter
from .resources import ResourceGuard
from vision.mobile_perception import MobileFrame, MobileFrameSource, MobilePerception, FrameArtifactStore, RecordingFrameSource
from vision.mobile_models import FixtureModel, HailoObjects, HailoRelativeDepth
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


def run_mobile(args, resources):
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
        detector=HailoObjects(**config['objects']);depth=HailoRelativeDepth(**config['depth'])
        # Only a camera transport is initialized, never MobileBase/Deck/face behavior.
        from hardware.elegoo_camera import ElegooCamera
        source=MobileFrameSource(ElegooCamera(stream_url=config.get('stream_url','http://192.168.4.1:81/stream'),timeout=2))
        clock=time.monotonic
    if not args.mobile_replay:
        source=RecordingFrameSource(source,FrameArtifactStore(state/'mobile-pixels'))
    journal=EvidenceJournal(state/'mobile-evidence.sqlite3')
    adapter=MobileEvidenceAdapter(journal,episode='mobile:'+uuid4().hex,revision=revision)
    guard=ResourceGuard(resources)
    perception=MobilePerception(detector,depth,resources=guard,revision=revision,clock=clock)
    behavior=MobileObserveBehavior(source,perception,adapter)
    counts=dict(records=0,frames=0,motion_authorized=False,mode='fixture' if args.mobile_replay else 'unarmed-perception',
                native_qualified=False,physical_qualified=False)
    latencies=[]
    try:
        for _ in range(args.mobile_frames):
            try:result=behavior.step()
            except StopIteration:break
            counts['frames']+=1
            if result:
                counts['records']+=1
                latencies.append(result['observation']['receipt_to_decision_seconds'])
                print(json.dumps(dict(evidence_id=result['evidence_id'],target=result['tracking']['target'],
                    proposal=result['proposal'],execution=result['execution']),allow_nan=False),flush=True)
    finally:
        behavior.close();journal.close()
    if latencies:
        import numpy as np
        counts['receipt_to_decision_seconds']={f'p{q}':float(np.percentile(latencies,q)) for q in (50,95,99)}
    counts['source_capture_age']='unknown; receipt age is not exposure age'
    print(json.dumps(counts),flush=True)
    return counts


def import_mobile_evidence(lifecycle):
    """Called by existing Executive acquisition turn; never another scheduler."""
    path=lifecycle.output/'mobile-evidence.sqlite3'
    if not path.exists():return False
    source=EvidenceJournal(path,read_only=True)
    try:
        before=len(lifecycle.journal.records())
        lifecycle.journal.merge_from(source)
    finally:source.close()
    # Interpretation stays on the existing Executive's thread/journal, where
    # native qualification and fixture exclusions are independently rechecked.
    adapter=MobileEvidenceAdapter(lifecycle.journal,episode='mobile-opportunities',revision='mobile-v1',
                                  executive=lifecycle.executive,gateway=lifecycle.gateway)
    for row in lifecycle.journal.category_records('observation','mobile_perception'):
        # Reflection sources must stay in their original episode.
        adapter.episode=row.data['episode']
        adapter.opportunities(row.id)
    return len(lifecycle.journal.records())!=before
