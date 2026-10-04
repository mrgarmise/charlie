import json
from pathlib import Path
import pytest
from learning.retrospective import discover, ingest, inventory, recover_notebook, run
from memory.evidence import EvidenceJournal
from learning.datasets import ExperienceDataset, sha


def episode(tmp_path, partial=False):
    root=tmp_path/'archive'/'game-01';root.mkdir(parents=True)
    if not partial:
        (root/'report.json').write_text(json.dumps({'score':1200,'result':'TIME LIMIT','steps':[]}))
    (root/'agency.jsonl').write_text(json.dumps({'self_track_id':None,'capture_timestamp':1.})+'\n{torn')
    return root


def test_partial_torn_logs_are_diagnostic_never_deaths_or_scores(tmp_path):
    root=episode(tmp_path,True)
    data=discover(root)
    assert data['partial'] and data['verified_deaths'] is None
    assert data['torn_lines']['agency.jsonl']==[2]
    assert data['complete_game_score'] is False
    out=tmp_path/'output'
    first=run([root],out)
    assert first['new_investigations']>0
    assert run([root],out)['new_investigations']==0
    j=EvidenceJournal(out/'learning-evidence.sqlite3',read_only=True)
    bookmarks=[r for r in j.records('event') if r.data['payload'].get('op')=='investigation_bookmark']
    dispatch=[r for r in j.records('event') if r.data['payload'].get('op')=='meditation_dispatch']
    assert bookmarks and len(bookmarks)==len(dispatch)
    assert all(r.data['producer']=='LearningExecutive' for r in bookmarks+dispatch)
    assert all(r.data['payload']['physical_authorization'] is False for r in bookmarks)
    j.close()


def test_copy_recovery_preserves_ids_and_rejects_other_output(tmp_path):
    root=episode(tmp_path);out=tmp_path/'first';run([root],out)
    before=inventory(out)
    recovered=tmp_path/'recovered'
    receipt=recover_notebook(out,recovered)
    assert inventory(out)==before
    copied=EvidenceJournal(recovered/'learning-evidence.sqlite3',read_only=True)
    assert [r.id for r in copied.records()]==receipt['journal_content_ids'];copied.close()
    assert recover_notebook(out,recovered)==receipt
    assert run([root],recovered)['new_investigations']==0
    with pytest.raises(ValueError):recover_notebook(out,tmp_path)


def test_modified_archive_and_overlapping_output_fail_closed(tmp_path):
    root=episode(tmp_path);out=tmp_path/'output';run([root],out)
    (root/'agency.jsonl').write_text('{}\n')
    with pytest.raises(ValueError,match='changed'):run([root],out)
    with pytest.raises(ValueError,match='separate'):run([root],root/'analysis')


def test_interrupted_import_resumes_exact_saved_meditation(tmp_path,monkeypatch):
    root=episode(tmp_path);saved=root.parent/'game-01-evidence';saved.mkdir()
    (saved/'meditation.json').write_text(json.dumps({'quality':{'adjacent':{'mean_error':1.},'gaps':{'mean_error':4.}}}))
    j=EvidenceJournal(tmp_path/'output'/'learning-evidence.sqlite3')
    ds=ExperienceDataset(j,tmp_path/'output'/'pixels')
    original=j.append
    def fail(kind,payload,**kw):
        if payload.get('category')=='retrospective_ingestion':raise InterruptedError()
        return original(kind,payload,**kw)
    monkeypatch.setattr(j,'append',fail)
    with pytest.raises(InterruptedError):ingest(root,ds)
    monkeypatch.setattr(j,'append',original)
    ingest(root,ds)
    for category in ('learning_context_reference','preserved_meditation','retrospective_ingestion'):
        assert sum(r.data['payload'].get('category')==category for r in j.records())==1
    j.verify();j.close()


def test_executive_dispatch_recovery_and_rejects_unselected_or_mutated(tmp_path):
    from test_ala_cycle import make
    from test_meditation_candidate import finding
    from learning.meditation import reflect
    from learning.capabilities import default_registry
    from memory.learning_projects import LearningExecutive
    from experiments.ppal.experiment_return import select_offline_experiment
    ds,g=make(tmp_path);finding(ds,tmp_path);e=LearningExecutive(ds.journal,g)
    item=reflect(ds,g,default_registry())[0]
    pid=e.propose(item['proposal'],ds.journal,[item['evidence_id']])
    e.select(methods={'meditation-motion'},resources={'offline-slot','meditation-evidence'},authorized_methods={'meditation-motion'})
    plan=select_offline_experiment(g,ds.journal,e.chooser_context(pid),budget_seconds=60)
    ids=e.commission(plan,ds.journal);count=len(ds.journal.records())
    assert LearningExecutive(ds.journal,g).commission(plan,ds.journal)==ids
    assert len(ds.journal.records())==count
    changed=dict(plan,method='evidence-review')
    with pytest.raises(ValueError):e.commission(changed,ds.journal)
    e.transition(pid,'paused','test pause',ds.journal,[item['evidence_id']])
    with pytest.raises(ValueError):e.commission(plan,ds.journal)


def test_active_gameplay_blocks_retrospective(tmp_path,monkeypatch):
    monkeypatch.setattr('learning.cycle.gameplay_active',lambda:True)
    with pytest.raises(RuntimeError,match='active gameplay'):run([],tmp_path/'output')
    assert not (tmp_path/'output').exists()


def test_legacy_observation_ingestion_marker_is_recovered(tmp_path):
    root=episode(tmp_path);out=tmp_path/'output'
    j=EvidenceJournal(out/'learning-evidence.sqlite3');ds=ExperienceDataset(j,out/'pixels')
    ref=j.append('observation',dict(category='learning_context_reference',
        source_episode='episode:'+sha(root/'report.json'),
        inventory=inventory(root),context=discover(root)),episode='autonomous-learning-v1',
        producer='existing-evidence-consolidation',version='legacy')
    marker=j.append('observation',dict(category='retrospective_ingestion',
        source_episode=ref.data['payload']['source_episode'],context_id=ref.id),
        episode='autonomous-learning-v1',sources=[ref.id],producer='existing-evidence-consolidation',version='legacy')
    count=len(j.records())
    assert ingest(root,ds)['record_id']==marker.id
    assert len(j.records())==count
    j.close()


def test_dispatch_interruption_resumes_without_duplicate_bookmark(tmp_path,monkeypatch):
    from test_ala_cycle import make
    from test_meditation_candidate import finding
    from learning.cycle import investigate
    from learning.capabilities import CapabilityRegistry
    ds,g=make(tmp_path);finding(ds,tmp_path)
    original=CapabilityRegistry.invoke
    monkeypatch.setattr(CapabilityRegistry,'invoke',lambda *a,**k: (_ for _ in ()).throw(InterruptedError()))
    with pytest.raises(InterruptedError):investigate(ds,g,diagnostics_only=True,max_jobs=1)
    monkeypatch.setattr(CapabilityRegistry,'invoke',original)
    result=investigate(ds,g,diagnostics_only=True,max_jobs=1)
    assert len(result['results'])==1
    events=ds.journal.records('event')
    assert sum(r.data['payload'].get('op')=='investigation_bookmark' for r in events)==1
    assert sum(r.data['payload'].get('op')=='meditation_dispatch' for r in events)==1
    assert result['results'][0]['result']['result']=='unresolved'
    assert investigate(ds,g,diagnostics_only=True,max_jobs=1)['results']==[]
