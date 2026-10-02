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
    assert report2['results']==[] # unchanged evidence is not another experiment
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
