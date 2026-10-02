import json
from pathlib import Path
import sqlite3

import pytest

from memory.evidence import EvidenceJournal, read_artifact
from memory.evaluator import MemoryEvaluator
from memory.gateway import MemoryGateway
from memory.store import JsonlStore
from experiments.ppal.episode_evidence import import_episode, derive_episode
from experiments.ppal.reflect_robotron import reflect_evidence


def test_immutable_unknown_provenance_reload(tmp_path):
    path=tmp_path/'e.sqlite3'
    j=EvidenceJournal(path)
    original={'self':None,'status':'provisional','nested':{'confidence':.3}}
    r=j.append('observation',original,episode='e',at=1,producer='camera',version='v1',provenance={'git':'abc'})
    original['nested']['confidence']=1
    r.data['payload']['nested']['confidence']=1
    assert j.get(r.id).data['payload']['nested']['confidence']==.3
    with pytest.raises(sqlite3.IntegrityError):
        j.conn.execute('UPDATE records SET document=? WHERE id=?',('{}',r.id))
    j.close()
    j=EvidenceJournal(path)
    assert j.get(r.id).data['payload']['self'] is None
    assert j.get(r.id).data['provenance']=={'git':'abc'}
    j.close()


@pytest.mark.parametrize('result',['supported','contradicted','unresolved'])
def test_prospective_resolution_and_hindsight(tmp_path,result):
    j=EvidenceJournal(tmp_path/'e.sqlite3')
    before=j.append('observation',{'x':0},episode='e',at=1,producer='sensor',version='1')
    p=j.predict({'x':1},episode='e',at=1,deadline=3,sources=(before.id,),producer='model',version='1')
    later=j.append('observation',{'x':1},episode='e',at=2,producer='sensor',version='1')
    with pytest.raises(ValueError,match='hindsight'):
        j.predict({'x':1},episode='e',at=1,deadline=3,sources=(before.id,),producer='model',version='2')
    with pytest.raises(ValueError,match='follow'):
        j.resolve(p.id,sources=(before.id,),result=result,reason='bad')
    r=j.resolve(p.id,sources=(later.id,),result=result,reason='explicit measurement')
    assert before.sequence<p.sequence<later.sequence<r.sequence
    assert r.data['payload']['result']==result
    with pytest.raises(ValueError,match='already resolved'):
        j.resolve(p.id,sources=(later.id,),result=result,reason='duplicate')
    j.close()


def make_episode(root):
    root.mkdir()
    report={'result':'TIME LIMIT','provenance':{'git_commit':'test'},'steps':[
        {'observed_at':1.,'action_timestamp':1.1,'action':{'move':'E','fire':'N'},'identity_status':'provisional'}]}
    (root/'report.json').write_text(json.dumps(report))
    rows=[]
    for sample,x in enumerate((0,1,3,3),1):
        rows.append(dict(sample=sample,capture_timestamp=float(sample),self_track_id=None,
                         controlled_track_id=42,identity_status='provisional',confidence=.4,
                         tracking=dict(events=[{'kind':'created','track_id':42}] if sample==1 else [],
                                       detections=[{'track_id':42,'center':[x,0],'kind':'unknown'}])))
    (root/'agency.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    return root


def test_reinterpretation_memory_and_source_tamper(tmp_path):
    root=make_episode(tmp_path/'run')
    j=EvidenceJournal(tmp_path/'evidence.sqlite3')
    episode=import_episode(root,j)
    originals=[(r.id,r.document) for r in j.records('observation')]
    first=derive_episode(root,j,episode,window=2,tolerance=.1)
    second=derive_episode(root,j,episode,window=3,tolerance=10)
    assert {r.data['payload'].get('result') for r in first} >= {'contradicted','unresolved'}
    assert 'supported' in {r.data['payload'].get('result') for r in second}
    assert [(r.id,r.document) for r in j.records('observation')]==originals
    assert derive_episode(root,j,episode,window=2,tolerance=.1)
    evaluator=MemoryEvaluator(tmp_path/'eval.sqlite3',exploration_rate=0)
    gateway=MemoryGateway(store=JsonlStore(tmp_path/'memories.jsonl'),evaluator=evaluator)
    result=reflect_evidence(j,episode,gateway)
    assert len(result['findings'])==2 and not result['policy_updated']
    assert evaluator.recent()
    ref=j.records('observation')[1].data['payload']['artifact']
    assert read_artifact(root,ref)['identity_status']=='provisional'
    (root/'agency.jsonl').write_text('{}\n')
    with pytest.raises(ValueError,match='changed'):
        read_artifact(root,ref)
    j.close()


def test_failed_episode_no_identity_invention(tmp_path):
    root=tmp_path/'failed';root.mkdir()
    (root/'report.json').write_text(json.dumps({'result':'ERROR: calibration failed','score':None}))
    j=EvidenceJournal(tmp_path/'e.sqlite3');episode=import_episode(root,j)
    assert j.records('episode')[0].data['payload']['outcome']=='ERROR: calibration failed'
    assert derive_episode(root,j,episode)==[]
    j.close()


def test_real_tracking_fixture_no_second_association(tmp_path,monkeypatch):
    root=tmp_path/'real';root.mkdir()
    fixture=Path(__file__).parent/'fixtures/robotron-exposure-010300/tracking-inputs.jsonl'
    # Exact real camera inputs, including UNKNOWN SELF and tracker allocations.
    (root/'agency.jsonl').write_bytes(fixture.read_bytes())
    (root/'report.json').write_text(json.dumps({'result':'ERROR: self unknown','steps':[]}))
    from experiments.ppal.eyes.tracking import SpriteTracker
    monkeypatch.setattr(SpriteTracker,'update',lambda *a,**kw:pytest.fail('E/E introduced association'))
    j=EvidenceJournal(tmp_path/'real.sqlite3');episode=import_episode(root,j)
    assert derive_episode(root,j,episode)
    assert j.records('resolution_reference')
    j.close()


def test_offline_failure_preserves_sources_and_live_has_no_dependency(tmp_path,monkeypatch):
    root=make_episode(tmp_path/'run')
    original={p.name:p.read_bytes() for p in root.iterdir()}
    j=EvidenceJournal(tmp_path/'e.sqlite3')
    monkeypatch.setattr(j,'append',lambda *a,**kw: (_ for _ in ()).throw(OSError('disk full')))
    with pytest.raises(OSError,match='disk full'):
        import_episode(root,j)
    assert {p.name:p.read_bytes() for p in root.iterdir()}==original
    import ast
    runner=Path(__file__).parents[1]/'experiments/ppal/play_robotron.py'
    tree=ast.parse(runner.read_text())
    modules=[n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
    assert not any('episode_evidence' in m or 'memory.evidence' in m for m in modules)
    j.close()


def test_existing_session_diary_retains_absolute_phase_time(tmp_path):
    root=make_episode(tmp_path/'run')
    (root/'events.jsonl').write_text(json.dumps({'kind':'start_requested','at':1234.5,'t':2.})+'\n')
    journal=EvidenceJournal(tmp_path/'events.sqlite3');ep=import_episode(root,journal)
    rows=[r for r in journal.records('observation') if r.data['payload']['category']=='session_event_observation']
    assert len(rows)==1 and rows[0].data['at']==1234.5
    journal.close()


def test_interrupted_replay_resumes_exact_forecasts(tmp_path):
    root=make_episode(tmp_path/'run');journal=EvidenceJournal(tmp_path/'e.sqlite3')
    episode=import_episode(root,journal);calls=[0]
    def checkpoint():
        if list(tmp_path.glob('*.replay.sqlite3')):
            calls[0]+=1
            if calls[0]==4:raise InterruptedError('checkpoint')
    journal.on_progress=checkpoint
    with pytest.raises(InterruptedError):derive_episode(root,journal,episode)
    journal.on_progress=None
    derive_episode(root,journal,episode);ids=[r.id for r in journal.records()]
    derive_episode(root,journal,episode);assert [r.id for r in journal.records()]==ids
    replay=EvidenceJournal(next(tmp_path.glob('*.replay.sqlite3')));replay.verify()
    assert len(replay.records('prediction'))==len(replay.records('resolution'))
    assert len(journal.records('derivation_complete'))==1
    replay.close();journal.close()


def test_failed_atomic_unit_rolls_back(tmp_path):
    journal=EvidenceJournal(tmp_path/'e.sqlite3')
    with pytest.raises(InterruptedError):
        with journal.batch():
            journal.append('observation',{},episode='e',at=1,producer='sensor',version='1')
            raise InterruptedError()
    assert journal.records()==[];journal.close()


def test_productive_budget_yields_then_retries(tmp_path):
    from experiments.ppal.marathon_robotron import process_completed_episode,ProcessingYield
    root=make_episode(tmp_path/'run');output=tmp_path/'between'
    gateway=MemoryGateway(store=JsonlStore(tmp_path/'memory.jsonl'),evaluator=MemoryEvaluator(tmp_path/'eval.sqlite3'))
    commitments=EvidenceJournal(tmp_path/'commit.sqlite3')
    with pytest.raises(ProcessingYield):process_completed_episode(root,output,gateway,commitments,work_budget=0)
    assert not (output/'between-game.json').exists()
    first=process_completed_episode(root,output,gateway,commitments)
    second=process_completed_episode(root,output,gateway,commitments)
    assert first['evidence']['records']==second['evidence']['records']
    commitments.close()
