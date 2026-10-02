import json
import time
from pathlib import Path
from types import SimpleNamespace
import pytest
from PIL import Image
from memory.evidence import EvidenceJournal
from memory.gateway import MemoryGateway
from memory.evaluator import MemoryEvaluator
from memory.store import JsonlStore
from learning.datasets import ExperienceDataset,SCOPE
from learning.cycle import investigate
from learning.deployment import CapabilityDeployment
from learning.operational import load_manifest,OperationalClassifier
from experiments.ppal.semantic_observer import SemanticObserver
from experiments.ppal.eyes.detectors import Detection
from experiments.ppal.play_robotron import _objects
from experiments.ppal.models import Position,WorldState
from experiments.ppal.forebrain import Forebrain
from experiments.ppal.hindbrain import Hindbrain
from test_ala_cycle import driver


def lab(tmp_path,authority=None):
    ds=ExperienceDataset(EvidenceJournal(tmp_path/'e.sqlite3'),tmp_path/'pixels')
    g=MemoryGateway(store=JsonlStore(tmp_path/'memory.jsonl'),evaluator=MemoryEvaluator(tmp_path/'eval.sqlite3'))
    for group in range(3):
        for label in ('human','threat'):
            for n in range(3):
                im=Image.new('RGB',(24,24),(220,10+group*3+n,10) if label=='human' else (10,10+group*3+n,220))
                path=tmp_path/f'{group}-{label}-{n}.png';im.save(path)
                example=ds.add(path,episode=str(group),crop=(0,0,24,24),source={'kind':'controlled-lab-generator'},metadata={'domain':'controlled-lab'})
                ds.annotate(example.id,label,status='verified',source='independent_measurement',evidence='controlled-independent-generator')
    ds.journal.append('observation',dict(category='learning_context_reference',context={'identity_samples':{'unknown':12},'questions':[{'category':'perception-gap'}]}),episode=SCOPE,producer='controlled-context',version='1')
    r=investigate(ds,g,budget_seconds=30,max_jobs=1,driver=driver,deployment_authority=authority)
    return ds,g,r


def test_evidence_cycle_deployment_operational_decision_and_rollback(tmp_path):
    pytest.importorskip('torch')
    ds,g,report=lab(tmp_path);row=report['results'][0];result=row['result']
    assert row['selection']['project']['originator']=='Reflection'
    assert result['metrics']['improved'] and result['operational_proposal'] and result['shadow_id']
    assert result['metrics']['operational']['accepted_accuracy']==1.
    deploy=CapabilityDeployment(ds.journal);proposal=result['operational_proposal']
    auth={'source':'controlled-lab-method-authorization','target':'ppal-semantics','proposal_id':proposal}
    with pytest.raises(ValueError,match='authorization'):deploy.activate(proposal,target='ppal-semantics',authorization=None,shadow_id=result['shadow_id'])
    with pytest.raises(ValueError,match='shadow'):deploy.activate(proposal,target='ppal-semantics',authorization=auth)
    active=deploy.activate(proposal,target='ppal-semantics',authorization=auth,shadow_id=result['shadow_id'])
    manifest=tmp_path/'activation.json';deploy.export('ppal-semantics',manifest)
    activation,model=load_manifest(manifest)
    image=Image.new('RGB',(24,24),(220,11,10));prediction=model.infer(image)
    assert prediction['label']=='human' and prediction['status']=='tentative_semantic_prediction'
    observer=SemanticObserver(model,activation)
    detection=Detection('unknown',(35.,50.),(0,0,24,24),576)
    pairs=[(detection,{})];tracks={42:SimpleNamespace(identity_uncertain=False)}
    observer.latest={42:dict(prediction,timestamp=1.,activation=activation['activation_key'])}
    planned,evidence=observer.apply(pairs,{0:42},tracks,self_id=99,timestamp=1.1)
    baseline=WorldState(0,Position(50,50),targets=(),threats=(),unresolved=_objects(pairs,{'unknown'},'unresolved',{0:42}))
    candidate=WorldState(0,Position(50,50),targets=_objects(planned,{'human'},'human',{0:42}),threats=())
    old=Hindbrain().decide(baseline,Forebrain().update(baseline))
    new=Hindbrain().decide(candidate,Forebrain().update(candidate))
    assert new[0].kind=='approach' and old[0].kind!='approach'
    assert new[1]!=old[1] and candidate.targets[0].id==baseline.unresolved[0].id
    assert evidence[0]['identity_status'].startswith('unchanged')
    assert observer.apply(pairs,{0:42},tracks,self_id=42,timestamp=1.1)[0]==pairs
    assert observer.apply(pairs,{0:42},tracks,self_id=99,timestamp=2.)[0]==pairs
    tracks[42].identity_uncertain=True
    assert observer.apply(pairs,{0:42},tracks,self_id=99,timestamp=1.1)[0]==pairs
    with pytest.raises(ValueError,match='readiness'):load_manifest(manifest,physical=True)
    deploy.rollback('ppal-semantics',reason='controlled regression exercise',authorization=auth)
    with pytest.raises(ValueError,match='current authorized'):load_manifest(manifest)
    observer.close();ds.journal.verify()


def test_semantic_worker_drop_old_nonblocking_and_errors(tmp_path):
    import threading
    gate=threading.Event()
    class Slow:
        def infer(self,image):gate.wait(2);raise RuntimeError('unreadable')
    observer=SemanticObserver(Slow(),{'activation_key':'controlled','candidate_id':'controlled'},fps=5)
    pairs=[(Detection('unknown',(50,50),(0,0,8,8),64),{})];tracks={1:SimpleNamespace(identity_uncertain=False)}
    frame=Image.new('RGB',(8,8));start=time.perf_counter()
    for n in range(20):observer.submit(frame,pairs,{0:1},tracks,self_id=None,timestamp=n)
    assert time.perf_counter()-start<.25 and observer.queue.qsize()<=1 and observer.dropped>0
    assert observer.apply(pairs,{0:1},tracks,self_id=None,timestamp=20)[0]==pairs
    gate.set();observer.close()


def test_reconstruction_and_self_labels_cannot_be_operational():
    with pytest.raises(ValueError,match='SELF'):OperationalClassifier({},dict(target='ppal-semantics',input='RGB-candidate-crop',classes=['player','threat'],eligible=True))


def test_autonomous_candidate_return_under_preexisting_bounded_authority(tmp_path):
    pytest.importorskip('torch')
    authority={'source':'controlled-lab-external-authorization','target':'ppal-semantics','allowed_domains':['controlled-lab']}
    ds,g,report=lab(tmp_path,authority)
    result=report['results'][0]['result'];deployment=result['deployment']
    assert deployment['status']=='activated'
    active,model=load_manifest(deployment['manifest'])
    assert model.infer(Image.new('RGB',(24,24),(10,11,220)))['label']=='threat'
    assert active['authorization']['policy']==authority
    with pytest.raises(ValueError,match='readiness'):load_manifest(deployment['manifest'],physical=True)
    # An identical recovery does not create a second activation.
    deploy=CapabilityDeployment(ds.journal);count=len(ds.journal.records())
    deploy.apply_authority(result,authority,Path(deployment['manifest']))
    assert len(ds.journal.records())==count
    assert not deploy.apply_authority(result,dict(authority,allowed_domains=['other-domain']),tmp_path/'bad.json')['manifest']
    deploy.rollback('ppal-semantics',reason='explicit rejection must survive retries',authorization={'source':'lab','target':'ppal-semantics'})
    assert deploy.apply_authority(result,authority,Path(deployment['manifest']))['status']=='blocked'


def test_recovery_after_resolution_before_shadow_does_not_retest(tmp_path,monkeypatch):
    pytest.importorskip('torch')
    import learning.operational as operational
    from learning.cycle import run_plan
    original=operational.shadow
    monkeypatch.setattr(operational,'shadow',lambda *a:(_ for _ in ()).throw(InterruptedError('crash before adapter handoff')))
    with pytest.raises(InterruptedError):lab(tmp_path)
    journal=EvidenceJournal(tmp_path/'e.sqlite3');ds=ExperienceDataset(journal,tmp_path/'pixels')
    plans=[r.data['payload']['plan'] for r in journal.records('event') if r.data['payload'].get('category')=='offline_experiment_plan']
    assert journal.resolution_for(plans[0]['prediction_id'])
    monkeypatch.setattr(operational,'shadow',original)
    monkeypatch.setattr('learning.foundry.evaluate',lambda *a:(_ for _ in ()).throw(AssertionError('test rerun')))
    result=run_plan(plans[0],ds,tmp_path/'models',driver=driver)
    assert result['status']=='already_resolved' and result['shadow_id']
    deploy=CapabilityDeployment(journal)
    grant={'source':'preexisting-lab-grant','target':'ppal-semantics','allowed_domains':['controlled-lab']}
    assert deploy.apply_authority(result,grant,tmp_path/'activation.json')['status']=='activated'
    before=len(journal.records());run_plan(plans[0],ds,tmp_path/'models',driver=driver)
    assert len(journal.records())==before
    journal.verify();journal.close()
