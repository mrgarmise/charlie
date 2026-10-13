"""Controlled software resource interruptions, not physical acceptance."""
import json
import pytest
from learning.lifecycle import DevelopmentLifecycle
from test_normal_learning_lifecycle import experience, rows, startup
from experiments.ppal import meditate_robotron as meditation


def fragments():
    return [dict(track_id=i+1, first_tick=i*2,last_tick=i*2+1,
        path=[dict(tick=i*2,center=[i*2,0]),dict(tick=i*2+1,center=[i*2+1,0])],
        candidate_kinds={'unknown':2},displacement=1) for i in range(4)]


def test_reconstruction_cursor_survives_inner_pair_yield(tmp_path,monkeypatch):
    tracks=fragments();state={};calls=0
    evaluated=[];original=meditation.predicted_link
    def record(left,right,*args):
        pair=(left['track_id'],right['track_id'])
        assert pair not in evaluated, 'completed candidate comparison repeated'
        evaluated.append(pair)
        return original(left,right,*args)
    monkeypatch.setattr(meditation,'predicted_link',record)
    def interrupt():
        nonlocal calls
        calls+=1
        if calls==4: raise InterruptedError('primary task')
    with pytest.raises(InterruptedError):
        meditation.reconstruct_once(tracks,on_progress=interrupt,resume_state=state)
    # Serialize as the lifecycle does: JSON tuples must preserve ranking.
    restored=json.loads(json.dumps(state))
    assert restored['neighbor']>0 and restored.get('left',0)==0
    resumed=meditation.reconstruct_once(tracks,resume_state=restored)
    monkeypatch.setattr(meditation,'predicted_link',original)
    assert resumed==meditation.reconstruct_once(tracks)


@pytest.mark.parametrize('reason',['deadline','primary'])
def test_normal_yield_restart_retains_commission_and_progress(tmp_path,monkeypatch,reason):
    root=experience(tmp_path);state=tmp_path/'state'
    (root/'tracks.json').write_text(json.dumps(dict(tracks=fragments())))
    life=DevelopmentLifecycle(state,[root],budget_seconds=1)
    clock=[0.];seen=[];original=meditation.predicted_link
    import learning.lifecycle as lifecycle
    from types import SimpleNamespace
    monkeypatch.setattr(lifecycle,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    def prediction(left,right,*args):
        seen.append((left['track_id'],right['track_id']))
        answer=original(left,right,*args)
        if len(seen)==1:clock[0]=2.
        return answer
    monkeypatch.setattr(meditation,'predicted_link',prediction)
    if reason=='primary':
        def primary():
            if clock[0]>1:raise InterruptedError('primary gameplay owns resources')
        monkeypatch.setattr(life,'yield_for_primary',primary)
    try:
        life.turn()
        if reason=='primary':assert life.phase=='experiencing'
    finally:life.close()
    before=rows(state)
    events=lambda c:[r for r in before if r.data['payload'].get('category')==c]
    assert len(events('reflection_commission'))==1
    assert len(events('normal_meditation_yield'))==1
    assert not events('normal_meditation_result')
    saved=json.loads(next((state/'meditations').glob('*/checkpoint.json')).read_text())
    assert saved['reconstruction']['neighbor']==1
    assert not saved['history']
    monkeypatch.setattr(meditation,'predicted_link',original)
    monkeypatch.undo()
    process=startup(state,[root],authorize=False)
    assert process.returncode==0,process.stderr
    after=rows(state)
    assert len([r for r in after if r.data['payload'].get('category')=='reflection_commission'])==1
    assert len([r for r in after if r.data['payload'].get('category')=='normal_meditation_result'])==1
    assert all(any(a.id==b.id and a.document==b.document for a in after) for b in before)
    assert any(r.data['kind']=='resolution' for r in after)
    stable=[r.id for r in after]
    process=startup(state,[root],authorize=False)
    assert process.returncode==0,process.stderr
    assert [r.id for r in rows(state)]==stable


def test_legacy_stable_iteration_is_not_repeated(tmp_path,monkeypatch):
    root=experience(tmp_path);state=tmp_path/'state'
    life=DevelopmentLifecycle(state,[root]);life.acquire()
    context=next(r for r in life.journal.records() if r.data['payload'].get('category')=='learning_context_reference')
    commission=life.journal.append('event',dict(category='reflection_commission',context_id=context.id,
        physical_authorization=False,reason='New preserved experience warrants bounded retrospective reflection'),
        episode=context.data['episode'],sources=[context.id],producer='LearningExecutive',version='normal-lifecycle-v1')
    from learning.datasets import sha
    path=state/'meditations'/context.id/'checkpoint.json';path.parent.mkdir(parents=True)
    tracks=json.loads((root/'tracks.json').read_text())['tracks']
    path.write_text(json.dumps(dict(source_sha256=sha(root/'tracks.json'),tracks=tracks,
        history=[dict(iteration=1,merges=0)],merges=[])))
    def repeat(*args,**kwargs):raise AssertionError('completed reconstruction repeated')
    monkeypatch.setattr(meditation,'reconstruct_once',repeat)
    try:
        result=life.reflect_experience(context.id,commission.id)
        assert result.data['payload']['status']=='completed'
    finally:life.close()


def test_checkpoint_integrity_failure_cannot_publish_finding(tmp_path,monkeypatch):
    root=experience(tmp_path);state=tmp_path/'state';life=DevelopmentLifecycle(state,[root])
    life.acquire()
    context=next(r for r in life.journal.records() if r.data['payload'].get('category')=='learning_context_reference')
    commission=life.journal.append('event',dict(category='reflection_commission',context_id=context.id),
        episode=context.data['episode'],sources=[context.id],producer='LearningExecutive',version='test')
    path=state/'meditations'/context.id/'checkpoint.json';path.parent.mkdir(parents=True)
    path.write_text(json.dumps(dict(state_digest='corrupt',tracks=[])))
    try:
        with pytest.raises(ValueError,match='integrity'):
            life.reflect_experience(context.id,commission.id)
        assert not any(r.data['payload'].get('category')=='normal_meditation_result' for r in life.journal.records())
    finally:life.close()
