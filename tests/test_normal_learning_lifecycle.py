"""Normal entry-point acceptance with explicit controlled software evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from memory.evidence import EvidenceJournal
from learning.datasets import sha
from learning.lifecycle import DevelopmentLifecycle
from test_meditation_candidate import corpus
from types import SimpleNamespace


def startup(state, roots, *, authorize=True, turns=8):
    cmd=[sys.executable,'main.py','--offline','--learning-state',str(state),
        '--learning-turns',str(turns),'--learning-interval','.05','--learning-budget','10']
    for root in roots:cmd+=['--episode-root',str(root)]
    if authorize:cmd+=['--allow-offline-improvements']
    return subprocess.run(cmd,capture_output=True,text=True,timeout=40)


def experience(tmp_path):
    root=tmp_path/'episodes'/'controlled-game';root.mkdir(parents=True)
    (root/'report.json').write_text(json.dumps(dict(score=None,steps=[],simulation=True)))
    # Adjacent steady motion plus a gap with a discontinuity makes the existing
    # algorithm originate competing hypotheses. Links stay unverified.
    paths=[dict(tick=i,center=[20+i,20]) for i in range(6)]
    paths+=[dict(tick=8,center=[40,20]),dict(tick=9,center=[41,20])]
    track=dict(track_id=1,first_tick=0,last_tick=9,observations=8,displacement=21,
        path=paths,candidate_kinds={'unknown':8})
    (root/'tracks.json').write_text(json.dumps(dict(tracks=[track])))
    return root


def delivered_corpus(tmp_path,state):
    state.mkdir(exist_ok=True)
    path=corpus(None,tmp_path)
    document=json.loads(path.read_text())
    document['provenance_kind']='simulated-controlled-trajectories'
    # Distinct target/player velocities cross an existing chooser deadband.
    # Future action changes are measured, not hand-chosen by runtime.
    for e in document['episodes']:
        for i,f in enumerate(e['frames']):
            f['targets'][0]['position']=[24-i,20]
    inbox=state/'acquisition-inbox';inbox.mkdir(exist_ok=True)
    (inbox/'motion.json').write_text(json.dumps(document))
    # Explicit test-harness admission; normal acquisition must reject these
    # generated reports/bin files as physical independent measurements.
    from learning.datasets import ExperienceDataset
    from learning.meditation import qualify_corpus
    journal=EvidenceJournal(state/'learning-evidence.sqlite3')
    try:qualify_corpus(ExperienceDataset(journal,state/'pixels'),inbox/'motion.json',allow_fixture=True)
    finally:journal.close()


def rows(state):
    j=EvidenceJournal(state/'learning-evidence.sqlite3',read_only=True)
    try:return j.records()
    finally:j.close()


def test_normal_startup_owns_full_cycle_and_restart(tmp_path):
    root=experience(tmp_path);state=tmp_path/'state';delivered_corpus(tmp_path,state)
    before=sha(root/'tracks.json')
    process=startup(state,[root])
    assert process.returncode==0,process.stderr
    records=rows(state)
    category=lambda c:[r for r in records if r.data['payload'].get('category')==c]
    assert category('retrospective_ingestion') and category('reflection_commission')
    assert category('normal_meditation_result') and category('perceptual_experiment_proposal')
    assert any(r.data['payload'].get('op')=='meditation_dispatch' for r in records)
    evaluations=category('meditation_candidate_evaluation')
    assert evaluations and evaluations[0].data['payload']['result']['result']=='supported'
    assert category('motion_operational_shadow') and category('capability_activation')
    outcomes=category('offline_operational_outcome')
    assert len(outcomes)==1 and outcomes[0].data['payload']['changed_decisions']>0
    assert outcomes[0].data['payload']['controller_writes']==0
    assert outcomes[0].data['payload']['evidence_use']=='reused validation diagnostic'
    feedback=[r for r in records if r.data['payload'].get('op')=='operational_feedback']
    assert len(feedback)==1
    assert sha(root/'tracks.json')==before
    count=len(records)
    assert startup(state,[root]).returncode==0
    assert len(rows(state))==count
    status=json.loads((state/'development-status.json').read_text())
    assert status['phase']=='stopped' and status['physical_authorization'] is False
    assert status['activation']['candidate_id']


def test_no_authority_keeps_candidate_pending(tmp_path):
    root=experience(tmp_path);state=tmp_path/'state';delivered_corpus(tmp_path,state)
    p=startup(state,[root],authorize=False)
    assert p.returncode==0,p.stderr
    records=rows(state)
    assert any(r.data['payload'].get('category')=='offline_authorization_request' for r in records)
    assert not any(r.data['payload'].get('category')=='capability_activation' for r in records)


def test_evidence_arrival_resumes_blocked_work_and_lock(tmp_path):
    root=experience(tmp_path);state=tmp_path/'state'
    p=startup(state,[root],turns=1);assert p.returncode==0,p.stderr
    assert not any(r.data['payload'].get('category')=='capability_activation' for r in rows(state))
    delivered_corpus(tmp_path,state)
    p=startup(state,[root]);assert p.returncode==0,p.stderr
    assert any(r.data['payload'].get('category')=='offline_operational_outcome' for r in rows(state))
    lifecycle=DevelopmentLifecycle(state,[root])
    try:
        with pytest.raises(BlockingIOError):DevelopmentLifecycle(state,[root])
    finally:lifecycle.close()


def test_gameplay_yields_without_acquiring_hardware(tmp_path,monkeypatch):
    root=experience(tmp_path);state=tmp_path/'state'
    lifecycle=DevelopmentLifecycle(state,[root])
    monkeypatch.setattr('learning.cycle.gameplay_active',lambda:True)
    try:
        lifecycle.turn()
        assert lifecycle.phase=='experiencing'
        assert not lifecycle.journal.records()
    finally:lifecycle.close()


def test_interruption_after_activation_reconciles_feedback_once(tmp_path,monkeypatch):
    root=experience(tmp_path);state=tmp_path/'state';delivered_corpus(tmp_path,state)
    authority=dict(source='explicit controlled offline authority',target='offline-shadow',execution='offline')
    life=DevelopmentLifecycle(state,[root],offline_authority=authority)
    from memory.learning_projects import LearningExecutive
    original=LearningExecutive.receive_operational_outcome
    def crash(*a,**kw):raise InterruptedError('after durable operational measurement')
    monkeypatch.setattr(LearningExecutive,'receive_operational_outcome',crash)
    try:
        with pytest.raises(InterruptedError):life.turn()
    finally:life.close()
    monkeypatch.setattr(LearningExecutive,'receive_operational_outcome',original)
    p=startup(state,[root]);assert p.returncode==0,p.stderr
    records=rows(state)
    for category in ('capability_activation','offline_operational_outcome','motion_final_consultation'):
        assert sum(r.data['payload'].get('category')==category for r in records)==1
    assert sum(r.data['payload'].get('op')=='operational_feedback' for r in records)==1


def test_meditation_checkpoint_retry_and_source_integrity(tmp_path,monkeypatch):
    root=experience(tmp_path);state=tmp_path/'state'
    import experiments.ppal.meditate_robotron as m
    original=m.quality
    def crash(*a,**kw):raise InterruptedError('bounded reflection interrupted')
    monkeypatch.setattr(m,'quality',crash)
    life=DevelopmentLifecycle(state,[root])
    try:
        with pytest.raises(InterruptedError):life.turn()
    finally:life.close()
    monkeypatch.setattr(m,'quality',original)
    p=startup(state,[root]);assert p.returncode==0,p.stderr
    records=rows(state)
    assert sum(r.data['payload'].get('category')=='reflection_commission' for r in records)==1
    assert sum(r.data['payload'].get('category')=='normal_meditation_result' for r in records)==1
    (root/'tracks.json').write_text('{}')
    p=startup(state,[root],turns=1)
    assert p.returncode==0,p.stderr
    conflicts=[r for r in rows(state) if r.data['payload'].get('category')=='episode_identity_quarantine']
    assert conflicts and 'changed' in conflicts[-1].data['payload']['reason']
    assert sum(r.data['payload'].get('category')=='normal_meditation_result' for r in rows(state))==1
    assert json.loads((state/'development-status.json').read_text())['identity_conflicts']


def test_surviving_legacy_context_preserved_without_inventing_tracks(tmp_path):
    state=tmp_path/'state';source=tmp_path/'legacy';source.mkdir()
    from learning.datasets import SCOPE
    j=EvidenceJournal(source/'learning-evidence.sqlite3')
    old=j.append('observation',dict(category='learning_context_reference',source_episode='legacy-game',
        context=dict(questions=[],identity_samples={})),episode=SCOPE,producer='existing-evidence-consolidation',version='ala-1')
    j.close()
    cmd=[sys.executable,'main.py','--offline','--learning-state',str(state),'--history-root',str(source),
        '--episode-root',str(tmp_path/'empty'),'--learning-turns','2','--learning-interval','.05']
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
    assert p.returncode==0,p.stderr
    records=rows(state);assert any(r.id==old.id for r in records)
    result=next(r for r in records if r.data['payload'].get('category')=='normal_meditation_result')
    assert result.data['payload']['status']=='unavailable'
    assert not any(r.data['payload'].get('category')=='preserved_meditation' for r in records)
    status=json.loads((state/'development-status.json').read_text())
    assert status['developmental_work'][old.id]['status']=='blocked'
    assert status['developmental_work'][old.id]['progress_occurred'] is False
    assert status['turn_outcome']['progress_occurred'] is False
    assert status['turn_outcome']['next_direction']=='Await qualified evidence or capability/dependency change'


def test_history_context_alias_is_not_another_meditation(tmp_path):
    root=experience(tmp_path);state=tmp_path/'state'
    p=startup(state,[root]);assert p.returncode==0,p.stderr
    from learning.datasets import SCOPE
    j=EvidenceJournal(state/'learning-evidence.sqlite3')
    episode='episode:'+sha(root/'report.json')
    j.append('observation',dict(category='learning_context_reference',source_episode=episode,
        context=dict(questions=[],identity_samples={}),source_journal='relocated original notebook'),
        episode=SCOPE,producer='existing-evidence-consolidation',version='ala-1')
    j.close()
    p=startup(state,[root]);assert p.returncode==0,p.stderr
    assert sum(r.data['payload'].get('category')=='normal_meditation_result' for r in rows(state))==1


def test_subsequent_diagnostic_failure_rolls_back_offline_only(tmp_path,monkeypatch):
    root=experience(tmp_path);state=tmp_path/'state';delivered_corpus(tmp_path,state)
    import learning.meditation as m
    original=m.motion_error;calls=0
    def degraded(spec,episodes):
        nonlocal calls
        calls+=1
        metric=original(spec,episodes)
        if calls==5:  # Three tuning comparisons, one sealed final, then subsequent use.
            metric['candidate']=metric['baseline']+1
        return metric
    monkeypatch.setattr(m,'motion_error',degraded)
    authority=dict(source='explicit controlled offline authority',target='offline-shadow',execution='offline')
    life=DevelopmentLifecycle(state,[root],offline_authority=authority)
    try:
        life.turn()
        from learning.deployment import CapabilityDeployment
        active=CapabilityDeployment(life.journal).active('offline-shadow')
        assert active['candidate'] is None and active['revoked_proposal']
        assert any(r.data['payload'].get('op')=='operational_feedback' for r in life.journal.records())
    finally:life.close()


def test_exported_normal_notebook_restores_results_by_hash(tmp_path):
    root=experience(tmp_path);state=tmp_path/'state'
    p=startup(state,[root]);assert p.returncode==0,p.stderr
    # Simulate relocation while retaining the original immutable record's path.
    moved=tmp_path/'moved';state.rename(moved)
    target=tmp_path/'target'
    cmd=[sys.executable,'main.py','--offline','--learning-state',str(target),'--history-root',str(moved),
        '--episode-root',str(root),'--learning-turns','2','--learning-interval','.05']
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
    assert p.returncode==0,p.stderr
    assert sum(r.data['payload'].get('category')=='normal_meditation_result' for r in rows(target))==1


def test_normal_attention_lifecycle_survives_worker_interruption(tmp_path,monkeypatch):
    """Simulated camera/motion/process APIs; no hardware objects initialized."""
    from types import ModuleType
    import main
    calls=[]
    class Worker:
        def __init__(self,**kwargs):calls.append('worker constructed');self.alive=False
        def start(self):calls.append('worker started')
        def is_alive(self):return self.alive
        def join(self,**kwargs):calls.append('worker joined')
    monkeypatch.setattr(main.multiprocessing,'get_context',lambda *a:SimpleNamespace(Process=Worker))
    class Attention:
        def __init__(self,*a):pass
        def update(self,*a):calls.append('attention update')
        def close(self):calls.append('attention closed')
    class Camera:
        def __init__(self):calls.append('simulated camera')
        def close(self):calls.append('camera closed')
    class Vision:
        def __init__(self,*a):self.steps=0
        def update(self):
            self.steps+=1
            if self.steps>2:raise KeyboardInterrupt()
    replacements={
        'motion.controller':dict(Deck=lambda:object()),
        'attention.manager':dict(AttentionManager=Attention),
        'stimulus.keyboard':dict(KeyboardStimulus=lambda bus:None),
        'vision.camera':dict(Camera=Camera),
        'vision.detector':dict(ColorDetector=lambda **kw:object()),
        'vision.stimulus':dict(VisionStimulus=Vision)}
    for name,contents in replacements.items():
        module=ModuleType(name);module.__dict__.update(contents);monkeypatch.setitem(sys.modules,name,module)
    with pytest.raises(KeyboardInterrupt):main.main(['--learning-state',str(tmp_path/'state')])
    assert calls.count('worker started')==2
    assert calls.count('attention update')==2
    assert 'attention closed' in calls and 'camera closed' in calls
