import sys,json,hashlib
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
import argparse
parser=argparse.ArgumentParser(description='Controlled no-device historical attention probe, never native following acceptance')
for key in ('native-journal','images','state','output'):parser.add_argument('--'+key,type=Path,required=True)
args=parser.parse_args()
from memory.evidence import EvidenceJournal
from learning.lifecycle import DevelopmentLifecycle
from learning.capabilities import default_registry
from learning.mobile_review import reflect_native,execute_review,labeled_pairs
from learning.mobile import MobileEvidenceAdapter
from vision.mobile_tracking import PetTracker
from experiments.ppal.mobile_navigation import MobileNavigator
from behaviors.mobile_observe import MobileObserveBehavior
from attention.manager import AttentionManager
from stimulus.bus import StimulusBus
import time,cv2
source=args.native_journal
source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
state=args.state;state.mkdir(exist_ok=True)
life=DevelopmentLifecycle(state,[],budget_seconds=1)
try:
 old=EvidenceJournal(source,read_only=True)
 try:life.journal.merge_from(old)
 finally:old.close()
 verified=0
 for raw,annotation in labeled_pairs(life.journal):
  a=raw.data['payload']['artifact'];path=args.images/a['name']
  assert hashlib.sha256(path.read_bytes()).hexdigest()==a['encoded_sha256']
  assert hashlib.sha256(cv2.imread(str(path)).tobytes()).hexdigest()==a['pixel_sha256'];verified+=1
 reflect_native(life.executive,life.journal)
 registry=default_registry();methods={p['id'] for p in registry.describe()}
 resources={'native-labeled-mobile-evidence','offline-slot','context-evidence','model-evaluation','meditation-evidence'}
 interest=life.executive.select(methods=methods,resources=resources,authorized_methods=methods)
 assert interest['project']['method']=='mobile-evidence-review'
 tracker=PetTracker(loss_seconds=2.);chosen=None
 originals=life.journal.category_records('observation','mobile_native_prediction')
 from datetime import datetime
 for row in originals:
  raw=row.data['payload']['raw'];at=datetime.fromisoformat(raw['time_utc']).timestamp()
  frame=dict(id=raw['frame_id'],received_at=at,geometry=[800,600],pan_deg=None,yaw_deg=None,authentic=True,
    source='elegoo-v4',source_age_known=False,clock_domain='historical UTC; not current Pi monotonic',sha256=raw.get('pixel_sha256'))
  tracking=tracker.update({'frame':frame,'objects':raw['detections']})
  if tracking['target'] and chosen is None:
   observation=dict(frame=frame,objects=raw['detections'],depth={'kind':'unavailable'},qualification='historical-unqualified',
     sensors={},model=[{'sha256':raw['model_sha256']}],historical_origin=row.id)
   chosen=(observation,tracking)
 assert chosen is not None
 o,t=chosen;now=time.monotonic();clock=lambda:now
 adapter=MobileEvidenceAdapter(life.journal,episode='historical-attention-control',revision='completion-probe',executive=life.executive)
 proposal=MobileNavigator(clock=clock).propose(o,t,{})
 row=adapter.record(o,t,proposal,{'dispatched':False,'executed':None,'rejected':['historical_only']})
 adapter.opportunities(row.id)
 bus=StimulusBus();attention=AttentionManager(bus,mobile_enabled=False)
 service=MobileObserveBehavior(None,SimpleNamespace(clock=clock),adapter,bus=bus)
 service.bind_attention(attention,life.executive,registry,base_factory=lambda:(_ for _ in ()).throw(AssertionError('no device')))
 service.executive_resources=resources
 result=dict(observation=o,tracking=t,proposal=proposal,execution={'dispatched':False},evidence_id=row.id)
 bus.emit('mobile_opportunity',result);attention.update(None)
 assert service.last_decision['intent']=='decline' and not result['execution']['dispatched']
 reviewed=execute_review(life.executive,interest['project'],life.journal,life.gateway)
 metrics=life.journal.category_records('observation','mobile_independent_label_evaluation')[-1].data['payload']['metrics']
 from learning.mobile_safety import runtime_hash
 report=dict(runtime_sha256=runtime_hash(),qualification='controlled host replay of authentic historical records; NOT live/native acceptance',
  source_journal_sha256=source_sha,raw_records=len(originals),verified_original_images=verified,
  initial_interest=interest['project']['method'],animal_opportunity_intent=service.last_decision['intent'],
  selected_project_method='mobile-evidence-review',same_executive=True,new_camera_frames=0,inference_calls=0,
  physical_connections=0,motor_commands=0,review_result=reviewed['result']['result'],metrics=metrics,
  learned_improvement=False,pet_follow_demonstrated=False)
 life.journal.verify()
 assert hashlib.sha256(source.read_bytes()).hexdigest()==source_sha
 args.output.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report))
finally:life.close()
