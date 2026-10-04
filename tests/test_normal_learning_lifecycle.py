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
    # Distinct target/player velocities cross an existing chooser deadband.
    # Future action changes are measured, not hand-chosen by runtime.
    for e in document['episodes']:
        for i,f in enumerate(e['frames']):
            f['targets'][0]['position']=[24-i,20]
    inbox=state/'acquisition-inbox';inbox.mkdir(exist_ok=True)
    (inbox/'motion.json').write_text(json.dumps(document))


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
