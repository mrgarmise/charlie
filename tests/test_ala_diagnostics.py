import pytest
from learning.datasets import SCOPE
from learning.cycle import investigate
from learning.diagnostics import execute
from experiments.ppal.reflect_robotron import reflect_model_investigations
from learning.capabilities import default_registry
from test_ala_cycle import make


def failed(ds, history=None):
    return ds.journal.append('observation',dict(category='offline_model_evaluation',
        metrics={'improved':False,'candidate':.8,'baseline':.1},
        candidate={'dataset_digest':'frozen-dataset','spec':{'epochs':2},
                   'history':history if history is not None else [
                       {'epoch':1,'train_loss':.2,'validation_loss':.9},
                       {'epoch':2,'train_loss':.1,'validation_loss':.8}]}),
        episode=SCOPE,producer='ModelFoundry',version='controlled')


def test_competing_evidence_proposals_and_independent_chooser(tmp_path):
    ds,g=make(tmp_path); evidence=failed(ds)
    proposals=reflect_model_investigations(ds,g,default_registry())
    assert len(proposals)==2
    assert {p['proposal']['scope']['predicate'] for p in proposals}=={
        'validation_exceeds_training','improving_at_budget'}
    assert all(ds.journal.get(p['hypothesis_id']).data['sources']==[evidence.id] for p in proposals)
    report=investigate(ds,g,diagnostics_only=True)
    assert len(report['results'])==2
    for row in report['results']:
        plan=row['plan']; result=row['result']
        assert result['result']=='supported'
        assert len(plan['competing_explanations'])==2
        assert plan['alternatives'][0]['evaluator_priority'] is not None
        assert ds.journal.get(plan['prediction_id']).sequence < ds.journal.get(result['evaluation_id']).sequence
        assert report['projects'][row['project_id']]['progress']['independent_physical_episodes']==0
        assert report['projects'][row['project_id']]['status']=='paused'
    assert investigate(ds,g,diagnostics_only=True)['results']==[]
    ds.journal.verify()


@pytest.mark.parametrize('history,expected',[
    ([],{'unresolved'}),
    ([{'epoch':1,'train_loss':.9,'validation_loss':.5},
      {'epoch':2,'train_loss':.8,'validation_loss':.6}],{'contradicted'})])
def test_unknown_and_contradiction_do_not_create_remedies(tmp_path,history,expected):
    ds,g=make(tmp_path);failed(ds,history)
    report=investigate(ds,g,diagnostics_only=True)
    assert {r['result']['result'] for r in report['results']}==expected
    assert not any(r.data['payload'].get('category')=='model_deployment_proposal' for r in ds.journal.records('event'))


def test_retrieval_crash_recovery_does_not_reobserve(tmp_path,monkeypatch):
    ds,g=make(tmp_path);failed(ds)
    original=ds.journal.resolve
    monkeypatch.setattr(ds.journal,'resolve',lambda *a,**kw: (_ for _ in ()).throw(InterruptedError()))
    with pytest.raises(InterruptedError):investigate(ds,g,diagnostics_only=True,max_jobs=1)
    plan=next(r.data['payload']['plan'] for r in ds.journal.records('event') if r.data['payload'].get('category')=='offline_experiment_plan')
    monkeypatch.setattr(ds.journal,'resolve',original)
    monkeypatch.setattr('learning.diagnostics.measurements',lambda *a: (_ for _ in ()).throw(AssertionError('reobserved')))
    assert execute(plan,ds)['status']=='resolved'
    count=len(ds.journal.records())
    assert execute(plan,ds)['status']=='already_resolved'
    assert len(ds.journal.records())==count
    changed=dict(plan,predicate='improving_at_budget' if plan['predicate']!='improving_at_budget' else 'validation_exceeds_training')
    with pytest.raises(ValueError,match='exact committed'):execute(changed,ds)


def test_active_play_and_method_authorization_preserved(tmp_path,monkeypatch):
    ds,g=make(tmp_path);failed(ds)
    with pytest.raises(ValueError,match='authorization'):
        default_registry().invoke('model-diagnostics',resources={'model-evaluation'},authorized=set(),plan={},dataset=ds)
    monkeypatch.setattr('learning.cycle.gameplay_active',lambda:True)
    with pytest.raises(RuntimeError,match='active gameplay'):investigate(ds,g,diagnostics_only=True)


def test_historical_host_clock_not_compared_to_current_forecast(tmp_path):
    import time
    ds,g=make(tmp_path)
    old=ds.journal.append('observation',{'category':'historical'},episode=SCOPE,at=time.monotonic()+100000,
                          producer='recorded-host',version='test')
    failed(ds)
    assert len(investigate(ds,g,diagnostics_only=True)['results'])==2
    assert ds.journal.get(old.id).data['at']>time.monotonic()
    ds.journal.verify()


def test_host_reboot_keeps_unfinished_prediction_unresolved(tmp_path,monkeypatch):
    ds,g=make(tmp_path);failed(ds)
    original=ds.journal.resolve
    monkeypatch.setattr(ds.journal,'resolve',lambda *a,**kw: (_ for _ in ()).throw(InterruptedError()))
    with pytest.raises(InterruptedError):investigate(ds,g,diagnostics_only=True,max_jobs=1)
    plan=next(r.data['payload']['plan'] for r in ds.journal.records('event') if r.data['payload'].get('category')=='offline_experiment_plan')
    monkeypatch.setattr(ds.journal,'resolve',original)
    monkeypatch.setattr('learning.clock.domain',lambda:'different-host-boot')
    result=execute(plan,ds)
    assert result['result']=='unresolved' and result['metrics']['clock_continuity']=='UNKNOWN'


def test_generic_question_retrieval_and_correlated_contexts(tmp_path):
    ds,g=make(tmp_path)
    # An unspecified question category is accepted without an actuator/Robotron adapter.
    for source in ('one','one','two'):
        ds.journal.append('observation',dict(category='learning_context_reference',source_episode=source,
            context={'questions':[{'category':'previously-unspecified-gap','question':'What evidence is missing?'}]}),
            episode=SCOPE,producer='Reflection',version=source)
    r=investigate(ds,g,diagnostics_only=True,review_questions=True,max_jobs=8)
    selected=next(x for x in r['results'] if x['plan']['question_category']=='previously-unspecified-gap')
    assert selected['result']['result']=='supported'
    assert selected['result']['metrics']['distinct_source_episodes']==2
    assert len(selected['plan']['competing_explanations'])==2
    project=r['projects'][selected['project_id']]
    assert project['progress']['independent_physical_episodes']==0
    assert len([x for x in r['results'] if x['plan']['question_category']=='previously-unspecified-gap'])==1
    assert not investigate(ds,g,diagnostics_only=True,review_questions=True,max_jobs=8)['results']


def test_context_provenance_missing_is_unknown(tmp_path):
    ds,g=make(tmp_path)
    r=investigate(ds,g,diagnostics_only=True,review_questions=True)
    assert len(r['results'])==1 and r['results'][0]['result']['result']=='unresolved'
