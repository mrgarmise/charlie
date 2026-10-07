"""Controlled software stalls and dependencies; no physical activation."""
import json
import pytest
from pathlib import Path
from learning.lifecycle import DevelopmentLifecycle, MeditationYield
from memory.evidence import digest
from test_normal_learning_lifecycle import experience,startup,rows,delivered_corpus
from experiments.ppal import meditate_robotron as meditation


def test_no_progress_meditation_yields_then_waits_and_restarts(tmp_path,monkeypatch):
    root=experience(tmp_path);state=tmp_path/'state';life=DevelopmentLifecycle(state,[root])
    calls=[]
    def stuck(*args,**kw):
        calls.append(1);raise MeditationYield('controlled unavailable processing slice')
    monkeypatch.setattr(meditation,'meditate',stuck)
    for _ in range(6):life.turn()
    # Initial checkpoint creation plus three unchanged attempts, then no busy work.
    assert len(calls)==4
    work=next(iter(life.executive.work_states().values()))
    assert work['status']=='blocked' and work['nonprogress_turns']==3
    assert life.phase=='waiting for evidence'
    before=[r.id for r in life.journal.records()];life.close()
    life=DevelopmentLifecycle(state,[root])
    for _ in range(5):life.turn()
    assert len(calls)==4 and [r.id for r in life.journal.records()]==before
    # Reviewed budget is an explicit changed resource dependency, not a timeout removal.
    life.close();monkeypatch.undo()
    life=DevelopmentLifecycle(state,[root],budget_seconds=11)
    life.turn();life.close()
    after=rows(state)
    assert sum(r.data['payload'].get('category')=='reflection_commission' for r in after)==1
    assert sum(r.data['payload'].get('category')=='normal_meditation_result' for r in after)==1


def test_advancing_bounded_reconstruction_is_not_a_stall(tmp_path,monkeypatch):
    root=experience(tmp_path);state=tmp_path/'state'
    from test_meditation_yield import fragments
    (root/'tracks.json').write_text(json.dumps(dict(tracks=fragments())))
    original=meditation.predicted_link
    clock=[0.]
    import learning.lifecycle as lifecycle
    from types import SimpleNamespace
    monkeypatch.setattr(lifecycle,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    def advance(*args):
        value=original(*args);clock[0]+=11;return value
    monkeypatch.setattr(meditation,'predicted_link',advance)
    life=DevelopmentLifecycle(state,[root])
    cursors=[]
    for _ in range(4):
        life.turn();work=next(iter(life.executive.work_states().values()))
        assert work['status']=='advancing' and work['nonprogress_turns']==0
        cursors.append(work['after'])
    assert len(set(cursors))==4
    life.close();monkeypatch.undo()
    p=startup(state,[root],authorize=False);assert p.returncode==0,p.stderr
    assert sum(r.data['payload'].get('category')=='reflection_commission' for r in rows(state))==1


def test_reflecting_status_identifies_commission_not_unrelated_retained_project(tmp_path,monkeypatch):
    from test_archive_qualification import archive
    from learning.archive_audit import audit,ingest
    from learning.cycle import investigate
    root=experience(tmp_path);state=tmp_path/'state';life=DevelopmentLifecycle(state,[root])
    q=ingest(life.journal,audit(archive(tmp_path)))
    report=investigate(life.dataset,life.gateway,executive=life.executive,
        diagnostics_only=True,review_questions=True,max_jobs=8)
    old=next(r for r in report['results'] if r['plan']['predicate']=='capture_horizon_supported')
    request=life.executive.retain_evidence_request(old['project_id'],life.journal,[q.id])
    captured=[]
    def yielded(*args,**kwargs):
        captured.append(json.loads((state/'development-status.json').read_text()))
        raise MeditationYield('controlled bounded slice')
    monkeypatch.setattr(meditation,'meditate',yielded)
    life.turn()
    status=captured[0]
    assert status['phase']=='reflecting'
    assert status['current_project'] is None
    assert status['current_question']!=life.executive.projects()[old['project_id']]['goal']
    activity=status['current_activity']
    assert activity['kind']=='meditation' and activity['commission_id']
    assert activity['context_id'] in status['activity_description']
    assert any(r['evidence_id']==request.id for r in status['evidence_requests'])
    assert life.executive.projects()[old['project_id']]['hold']
    life.close()


def test_waiting_investigation_resumes_on_qualified_delivery(tmp_path):
    root=experience(tmp_path);state=tmp_path/'state'
    p=startup(state,[root],authorize=False,turns=12);assert p.returncode==0,p.stderr
    status=json.loads((state/'development-status.json').read_text())
    assert status['phase']=='stopped' and status['last_activity']=='waiting for evidence'
    before=rows(state)
    p=startup(state,[root],authorize=False,turns=12);assert p.returncode==0,p.stderr
    assert [r.id for r in rows(state)]==[r.id for r in before]
    delivered_corpus(tmp_path,state)
    p=startup(state,[root],authorize=False,turns=12);assert p.returncode==0,p.stderr
    after=rows(state)
    assert any(r.data['payload'].get('category')=='meditation_candidate_evaluation' for r in after)
    assert not any(r.data['payload'].get('category')=='capability_activation' for r in after)
    p=startup(state,[root],authorize=False,turns=12);assert p.returncode==0,p.stderr
    assert [r.id for r in rows(state)]==[r.id for r in after]


def test_unrelated_context_proceeds_after_stalled_meditation(tmp_path,monkeypatch):
    first=experience(tmp_path);second=tmp_path/'episodes'/'second';second.mkdir()
    (second/'report.json').write_text(json.dumps(dict(score=None,steps=[],simulation=True,distinct=2)))
    tracks=json.loads((first/'tracks.json').read_text());tracks['tracks'][0]['track_id']=2
    (second/'tracks.json').write_text(json.dumps(tracks))
    original=meditation.meditate
    def stuck(tracks,*args,**kw):
        if tracks[0]['track_id']==1:raise MeditationYield('controlled stuck first context')
        return original(tracks,*args,**kw)
    monkeypatch.setattr(meditation,'meditate',stuck)
    life=DevelopmentLifecycle(tmp_path/'state',[first,second])
    for _ in range(9):life.turn()
    assert any(v['status']=='blocked' for v in life.executive.work_states().values())
    assert any(r.data['payload'].get('category')=='normal_meditation_result' and r.data['payload']['status']=='completed' for r in life.journal.records())
    assert life.phase=='waiting for evidence'
    life.close()


def test_deferred_experiment_is_bookmarked_without_freezing_other_work(tmp_path,monkeypatch):
    from learning.capabilities import default_registry
    import learning.cycle as cycle
    registry=default_registry();original=registry.invoke;stuck=[]
    def invoke(method,**kwargs):
        identifier=kwargs['plan']['project_id']
        if not stuck:stuck.append(identifier)
        if identifier==stuck[0]:return dict(status='deferred',returncode=75)
        return original(method,**kwargs)
    monkeypatch.setattr(registry,'invoke',invoke)
    monkeypatch.setattr(cycle,'default_registry',lambda:registry)
    root=experience(tmp_path);life=DevelopmentLifecycle(tmp_path/'state',[root])
    for _ in range(10):life.turn()
    work=life.executive.work_states()[stuck[0]]
    assert work['status']=='blocked' and work['nonprogress_turns']==3
    assert life.executive.projects()[stuck[0]]['status']=='blocked'
    assert any(r.data['kind']=='resolution' for r in life.journal.records())
    requests=[r for r in life.journal.records() if r.data['payload'].get('category')=='learning_evidence_request' and r.data['payload'].get('work_id')==stuck[0]]
    assert len(requests)==1
    before=[r.id for r in life.journal.records()];life.close()
    life=DevelopmentLifecycle(tmp_path/'state',[root])
    for _ in range(3):life.turn()
    assert [r.id for r in life.journal.records()]==before
    assert life.phase=='waiting for evidence'
    life.close()
    monkeypatch.undo()
    life=DevelopmentLifecycle(tmp_path/'state',[root],budget_seconds=11)
    life.turn()
    assert life.executive.work_states()[stuck[0]]['status']=='completed'
    plans=[r for r in life.journal.records() if r.data['payload'].get('category')=='offline_experiment_plan' and r.data['payload']['plan'].get('project_id')==stuck[0]]
    assert len(plans)==1
    life.close()


def test_heartbeat_changes_are_not_computed_progress(tmp_path):
    from memory.learning_projects import LearningExecutive
    from memory.evidence import EvidenceJournal
    j=EvidenceJournal(tmp_path/'journal');executive=LearningExecutive(j,None)
    path=tmp_path/'models'/'prediction'/'candidate';path.mkdir(parents=True)
    progress=path/'progress.json'
    progress.write_text(json.dumps(dict(pid=1,phase='processing',updated_at=1,phase_started_at=1,processing_units=3)))
    before=executive.experiment_progress(tmp_path/'models','prediction')
    progress.write_text(json.dumps(dict(pid=2,phase='processing',updated_at=10,phase_started_at=10,processing_units=3)))
    assert executive.experiment_progress(tmp_path/'models','prediction')==before
    progress.write_text(json.dumps(dict(processing_units=4)))
    assert executive.experiment_progress(tmp_path/'models','prediction')!=before
    j.close()


@pytest.mark.parametrize('change',['checkpoint','capability','implementation'])
def test_waiting_experiment_reconsiders_changed_checkpoint_without_new_evidence(tmp_path,monkeypatch,change):
    from learning.capabilities import default_registry
    import learning.cycle as cycle
    registry=default_registry();original=registry.invoke;stuck=[];released=[False]
    def invoke(method,**kwargs):
        identifier=kwargs['plan']['project_id']
        if not stuck:stuck.append(identifier)
        if identifier==stuck[0] and not released[0]:return dict(status='deferred',returncode=75)
        return original(method,**kwargs)
    monkeypatch.setattr(cycle,'default_registry',lambda:registry)
    monkeypatch.setattr(registry,'invoke',invoke)
    root=experience(tmp_path);state=tmp_path/'state';life=DevelopmentLifecycle(state,[root])
    life.turn()
    plan=next(r.data['payload']['plan'] for r in life.journal.records('event')
        if r.data['payload'].get('category')=='offline_experiment_plan'
        and r.data['payload']['plan']['project_id']==stuck[0])
    checkpoint=state/'models'/plan['prediction_id']/'candidate'/'progress.json'
    checkpoint.parent.mkdir(parents=True,exist_ok=True)
    checkpoint.write_text(json.dumps(dict(processing_units=1,pid=1,updated_at=1)))
    for _ in range(10):life.turn()
    assert life.executive.work_states()[stuck[0]]['status']=='blocked'
    assert life.phase=='waiting for evidence'
    before=[r.id for r in life.journal.records()]
    checkpoint.write_text(json.dumps(dict(processing_units=1,pid=2,updated_at=2)))
    life.turn()
    assert [r.id for r in life.journal.records()]==before # heartbeat is not a wakeup
    if change=='checkpoint':
        checkpoint.write_text(json.dumps(dict(processing_units=2)))
    elif change=='capability':
        from dataclasses import replace
        registry._items[plan['method']]=replace(registry.get(plan['method']),purpose='Reviewed execution capability')
    else:
        from memory.learning_projects import LearningExecutive
        original_implementation=LearningExecutive.execution_implementation
        monkeypatch.setattr(LearningExecutive,'execution_implementation',
            lambda self:dict(original_implementation(self),controlled_review='new-adapter-revision'))
    life.close();released[0]=True
    life=DevelopmentLifecycle(state,[root]);life.turn()
    assert life.executive.work_states()[stuck[0]]['status']=='completed'
    assert sum(r.data['payload'].get('category')=='offline_experiment_plan' and
        r.data['payload']['plan']['project_id']==stuck[0] for r in life.journal.records('event'))==1
    life.close()


def test_primary_preemption_is_not_meditation_stagnation(tmp_path,monkeypatch):
    root=experience(tmp_path);life=DevelopmentLifecycle(tmp_path/'state',[root])
    def primary():raise InterruptedError('primary owner preempted this slice')
    monkeypatch.setattr(life,'yield_for_primary',primary)
    for _ in range(6):
        life.turn()
        assert life.phase=='experiencing'
        work=next(iter(life.executive.work_states().values()))
        assert work['status']!='blocked' and work['nonprogress_turns']==0
    monkeypatch.undo()
    life.turn()
    assert next(iter(life.executive.work_states().values()))['status']=='completed'
    life.close()


def test_unavailable_candidate_cannot_claim_idle_productivity(tmp_path,monkeypatch):
    from test_learning_projects import hypothesis
    import importlib.util
    original=importlib.util.find_spec
    monkeypatch.setattr(importlib.util,'find_spec',lambda name:None if name=='torch' else original(name))
    life=DevelopmentLifecycle(tmp_path/'state',[])
    p=hypothesis(life.journal,method='cnn-reconstruction')
    identifier=life.executive.propose(p['proposal'],life.journal,[p['evidence_id']])
    life.turn()
    assert life.phase=='waiting for evidence'
    assert life.executive.projects()[identifier]['status']=='blocked'
    before=[r.id for r in life.journal.records()]
    for _ in range(4):life.turn()
    assert [r.id for r in life.journal.records()]==before
    life.close()


def test_quarantined_partial_meditation_does_not_keep_waiting_portfolio_busy(tmp_path,monkeypatch):
    root=experience(tmp_path);state=tmp_path/'state';life=DevelopmentLifecycle(state,[root])
    monkeypatch.setattr(meditation,'meditate',lambda *args,**kwargs:(_ for _ in ()).throw(MeditationYield('controlled interruption')))
    life.turn()
    assert life.executive.work_states()
    (root/'tracks.json').write_text(json.dumps(dict(tracks=[]))) # genuine preserved-source modification
    for _ in range(8):life.turn()
    assert life.phase=='waiting for evidence'
    assert not life.pending_work()
    assert json.loads((state/'development-status.json').read_text())['identity_conflicts']
    before=[r.id for r in life.journal.records()];life.close()
    life=DevelopmentLifecycle(state,[root])
    for _ in range(4):life.turn()
    assert [r.id for r in life.journal.records()]==before
    assert life.phase=='waiting for evidence'
    life.close()
