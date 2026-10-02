import json,time
from pathlib import Path
import pytest
from PIL import Image
from memory.evidence import EvidenceJournal
from memory.evaluator import MemoryEvaluator
from memory.gateway import MemoryGateway
from memory.store import JsonlStore
from learning.datasets import ExperienceDataset,SCOPE
from learning.cycle import investigate,run_plan
from learning.deployment import CapabilityDeployment


def make(tmp_path,verified=False):
    ds=ExperienceDataset(EvidenceJournal(tmp_path/'e.sqlite3'),tmp_path/'pixels')
    g=MemoryGateway(store=JsonlStore(tmp_path/'memory.jsonl'),evaluator=MemoryEvaluator(tmp_path/'eval.sqlite3'))
    for group in range(3):
        for label in range(2):
            p=tmp_path/f'{group}-{label}.png'; Image.new('RGB',(16,16),(group,label*180,20)).save(p)
            row=ds.add(p,episode=str(group),source={'kind':'controlled'},metadata={'identity_status':'provisional'})
            if verified: ds.annotate(row.id,str(label),status='verified',source='independent_measurement',evidence='controlled-generator')
    ds.journal.append('observation',dict(category='learning_context_reference',context={'identity_samples':{'unknown':10},'questions':[{'category':'uncertainty'}]}),episode=SCOPE,producer='controlled-context',version='1')
    return ds,g


def driver(cmd,path,**kwargs):
    from learning.foundry import train,atomic_json
    c=json.loads(Path(cmd[-1]).read_text()); result=train(c['snapshot'],c['spec'],c['output'],budget_seconds=60.)
    return 75 if result['status']=='yielded' else 0


def test_evidence_originated_cycle_resolution_memory_and_restart(tmp_path):
    pytest.importorskip('torch')
    ds,g=make(tmp_path)
    report=investigate(ds,g,budget_seconds=8,max_jobs=2,driver=driver)
    assert len(report['results'])==1
    result=report['results'][0]; assert result['plan']['experiment_kind']=='offline'
    assert result['result']['status']=='resolved'
    prediction=ds.journal.get(result['plan']['prediction_id']); outcome=ds.journal.get(result['result']['evaluation_id'])
    assert prediction.sequence<outcome.sequence
    assert report['projects'][result['project_id']]['progress']['independent_physical_episodes']==0
    assert result['plan']['method_alternatives'][0]['eligible'] is False
    assert result['result']['metrics']['limitations']
    before=len(ds.journal.records()); repeat=run_plan(result['plan'],ds,tmp_path/'models',driver=driver)
    assert repeat['status']=='already_resolved' and len(ds.journal.records())==before
    assert g.evaluator.recent(10)
    report2=investigate(ds,g,budget_seconds=8,max_jobs=2,driver=driver)
    assert all(r['plan']['method']=='model-diagnostics' for r in report2['results'])
    refinement=investigate(ds,g,budget_seconds=8,max_jobs=2,driver=driver)
    assert all(r['plan']['evaluation_mode']=='validation-only' for r in refinement['results'])
    assert all(not r['result']['metrics']['test_consulted'] for r in refinement['results'])
    assert investigate(ds,g,budget_seconds=8,max_jobs=2,driver=driver)['results']==[]
    deploy=CapabilityDeployment(ds.journal)
    with pytest.raises(ValueError): deploy.activate(result['result']['deployment_proposal'],target='offline-shadow',authorization=None)
    ds.journal.verify()


def test_multiple_offline_projects_share_evidence_without_physical_credit(tmp_path):
    pytest.importorskip('torch')
    ds,g=make(tmp_path,True)
    report=investigate(ds,g,budget_seconds=8,max_jobs=2,driver=driver)
    assert len(report['opportunities'])==2 and len(report['results'])==2
    assert {p['method'] for p in report['projects'].values()}=={'cnn-classification','cnn-reconstruction'}
    assert all(p['progress']['independent_physical_episodes']==0 for p in report['projects'].values())


def test_no_gap_no_proposal_and_no_live_training(tmp_path,monkeypatch):
    ds,g=make(tmp_path)
    monkeypatch.setattr('learning.cycle.gameplay_active',lambda:True)
    with pytest.raises(RuntimeError,match='active gameplay'): investigate(ds,g)


def test_productive_worker_deferred_not_resolved(tmp_path):
    ds,g=make(tmp_path)
    report=investigate(ds,g,budget_seconds=8,driver=lambda *a,**kw:75)
    result=report['results'][0]
    assert result['result']['status']=='deferred'
    assert ds.journal.resolution_for(result['plan']['prediction_id']) is None


def test_checkpointed_resolution_recovery_does_not_retest(tmp_path,monkeypatch):
    pytest.importorskip('torch')
    ds,g=make(tmp_path)
    original=ds.journal.resolve
    def stop(*a,**kw): raise InterruptedError('crash after test observation')
    monkeypatch.setattr(ds.journal,'resolve',stop)
    with pytest.raises(InterruptedError): investigate(ds,g,budget_seconds=8,driver=driver)
    plans=[r.data['payload']['plan'] for r in ds.journal.records('event') if r.data['payload'].get('category')=='offline_experiment_plan']
    monkeypatch.setattr(ds.journal,'resolve',original)
    monkeypatch.setattr('learning.foundry.evaluate',lambda *a:(_ for _ in ()).throw(AssertionError('test repeated')))
    result=run_plan(plans[0],ds,tmp_path/'models',driver=driver)
    assert result['status']=='resolved'
    assert len([r for r in ds.journal.records('observation') if r.data['payload'].get('category')=='offline_model_evaluation'])==1


def test_shadow_activation_requires_independent_support_and_rollback(tmp_path):
    ds,g=make(tmp_path)
    from learning.datasets import sha
    weights=tmp_path/'weights.bin';weights.write_bytes(b'controlled-test-candidate')
    evaluation=ds.journal.append('observation',dict(category='offline_model_evaluation',metrics={'improved':True,'independence_groups':['controlled-held-out']},candidate={'checkpoint':str(weights),'checkpoint_sha256':sha(weights)}),episode=SCOPE,producer='ModelFoundry',version='1')
    proposal=ds.journal.append('event',dict(category='model_deployment_proposal',candidate_id='controlled',evaluation_id=evaluation.id,eligible=True,target='offline-shadow'),episode=SCOPE,sources=[evaluation.id],producer='Reflection',version='1')
    deploy=CapabilityDeployment(ds.journal)
    with pytest.raises(ValueError): deploy.activate(proposal.id,target='live-PPAL',authorization={'source':'test'})
    auth={'source':'explicit-controlled-authorization','target':'offline-shadow','proposal_id':proposal.id}
    deploy.activate(proposal.id,target='offline-shadow',authorization=auth)
    assert deploy.active('offline-shadow')['candidate_id']=='controlled'
    deploy.rollback('offline-shadow',reason='controlled regression',authorization=auth)
    assert deploy.active('offline-shadow')['candidate_id'] is None


def test_new_evidence_releases_wait_without_independent_confirmation(tmp_path):
    pytest.importorskip('torch')
    ds,g=make(tmp_path)
    first=investigate(ds,g,budget_seconds=8,driver=driver)
    p=tmp_path/'new.png';Image.new('RGB',(16,16),(9,11,77)).save(p)
    # Additional frame within the same held-out episode is NOT independent replication.
    ds.add(p,episode='2',source={'kind':'controlled-additional-observation'})
    second=investigate(ds,g,budget_seconds=8,max_jobs=3,driver=driver)
    assert sum('candidates' in r['plan'] for r in second['results'])==1
    project=next(p for p in second['projects'].values() if p['method']=='cnn-reconstruction')
    assert project['progress']['offline_trials']==2 and project['progress']['independent_offline_evidence_units']==1
    assert project['status']!='completed'


def test_mutated_chooser_plan_cannot_execute(tmp_path):
    ds,g=make(tmp_path)
    report=investigate(ds,g,budget_seconds=8,driver=lambda *a,**kw:75)
    plan=report['results'][0]['plan']; plan['candidates'][0]['lr']=.02
    with pytest.raises(ValueError,match='exact committed'): run_plan(plan,ds,tmp_path/'models',driver=driver)


def test_optional_hook_reuses_existing_context_and_no_camera(tmp_path,monkeypatch):
    from learning.cycle import postgame_learning
    from memory.learning_projects import LearningExecutive
    ds,g=make(tmp_path)
    root=tmp_path/'episode';root.mkdir(); Image.new('RGB',(16,16),'cyan').save(root/'review-000.jpg')
    context={'identity_samples':{'unknown':1},'questions':[]}
    source=ds.journal.append('event',dict(category='postgame_learning_context',**context),episode='episode-one',producer='Reflection',version='test')
    context['evidence_id']=source.id
    executive=LearningExecutive(ds.journal,g)
    report=postgame_learning(root,ds.journal,'episode-one',context,g,executive,tmp_path/'shared',budget_seconds=1)
    assert report['results']==[]
    copied=EvidenceJournal(tmp_path/'shared/learning-evidence.sqlite3')
    assert len(ExperienceDataset(copied,tmp_path/'shared/pixels').examples())==1
    copied.verify();copied.close()
