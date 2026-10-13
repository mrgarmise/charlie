from pathlib import Path
import pytest
from learning.cycle import investigate,run_plan
from learning.capabilities import default_registry
from learning.deployment import CapabilityDeployment
from experiments.ppal.reflect_robotron import reflect_training_extensions
from experiments.ppal.experiment_return import select_offline_experiment
from memory.learning_projects import LearningExecutive
from test_ala_cycle import make,driver


def test_retrieved_failure_generates_intervention_without_reopening_test(tmp_path,monkeypatch):
    pytest.importorskip('torch')
    ds,g=make(tmp_path)
    original=investigate(ds,g,budget_seconds=8,max_jobs=1,driver=driver)
    assert original['results'][0]['result']['result']=='contradicted'
    diagnostics=investigate(ds,g,budget_seconds=8,max_jobs=2,driver=driver,diagnostics_only=True)
    assert len(diagnostics['results'])==2
    opportunities=reflect_training_extensions(ds,g,default_registry())
    assert len(opportunities)==1
    item=opportunities[0];executive=LearningExecutive(ds.journal,g)
    project=executive.propose(item['proposal'],ds.journal,[item['evidence_id']])
    selection=executive.select(methods={'cnn-validation-extension'},resources={'offline-slot','RGB-examples','torch','model-evaluation'},authorized_methods={'cnn-validation-extension'})
    assert selection['project']['id']==project
    plan=select_offline_experiment(g,ds.journal,executive.chooser_context(project),budget_seconds=8)
    assert plan['candidates'][1]['epochs']==2*plan['candidates'][0]['epochs']
    assert len(plan['method_alternatives'])==3 and plan['source_evidence']
    snapshot=ds.journal.get(plan['dataset_id']).data['payload']
    for r in snapshot['examples']:
        if r['partition']=='test':Path(r['pixel_path']).unlink()
    monkeypatch.setattr('learning.foundry.evaluate',lambda *a:(_ for _ in ()).throw(AssertionError('test opened')))
    monkeypatch.setattr('learning.foundry.discover_groups',lambda *a:(_ for _ in ()).throw(AssertionError('test embeddings opened')))
    result=run_plan(plan,ds,tmp_path/'models',driver=driver)
    assert not result['metrics']['test_consulted'] and result['operational_proposal'] is None
    assert result['metrics']['independence_groups']==[]
    assert not ds.journal.get(result['deployment_proposal']).data['payload']['eligible']
    with pytest.raises(ValueError,match='proposal'):CapabilityDeployment(ds.journal).activate(result['deployment_proposal'],target='offline-shadow',authorization={})
    before=len(ds.journal.records());assert run_plan(plan,ds,tmp_path/'models',driver=driver)['status']=='already_resolved'
    assert len(ds.journal.records())==before
    ds.journal.verify()


def test_cnn_unknown_clock_preserves_checkpoint_without_false_resolution(tmp_path,monkeypatch):
    pytest.importorskip('torch')
    ds,g=make(tmp_path)
    report=investigate(ds,g,budget_seconds=8,max_jobs=1,driver=lambda *a,**kw:75)
    plan=report['results'][0]['plan']
    monkeypatch.setattr('learning.clock.domain',lambda:'another-boot')
    result=run_plan(plan,ds,tmp_path/'models',driver=lambda *a,**kw:(_ for _ in ()).throw(AssertionError('should not train')))
    assert result['result']=='unresolved' and result['metrics']['clock_continuity']=='UNKNOWN'
    assert run_plan(plan,ds,tmp_path/'models')['status']=='already_resolved'
    assert not any(r.data['payload'].get('category')=='offline_model_evaluation' for r in ds.journal.records())


def test_cnn_forecast_isolated_from_old_host_timestamps(tmp_path):
    pytest.importorskip('torch')
    ds,g=make(tmp_path)
    from learning.datasets import SCOPE
    ds.journal.append('observation',{'category':'historical-clock'},episode=SCOPE,at=1e12,producer='archived-host',version='1')
    report=investigate(ds,g,budget_seconds=8,max_jobs=1,driver=driver)
    result=report['results'][0]
    assert result['plan']['clock_domain'] and result['plan']['episode']!=SCOPE
    assert result['result']['result']!='unresolved'
