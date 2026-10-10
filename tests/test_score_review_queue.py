"""Deferred review software fixtures; no physical games or certified scores."""
import json
from pathlib import Path
from PIL import Image
from memory.evidence import EvidenceJournal
from experiments.ppal.score_observer import ScoreObserver


def game(root,n=1,*,photo=True):
    root.mkdir(parents=True)
    (root/'report.json').write_text(json.dumps(dict(simulation=True,result='GAME OVER',
        score=n*100,episode_end=dict(confirmed=True,evidence=dict(terminal_capture_timestamps=[float(n)])),
        planning_mode='fixture-policy',session_timing=dict(started_at=0.,stopped_at=float(n)+1))))
    if photo:
        Image.new('RGB',(20,20),(n%256,20,40)).save(root/'original.png')
        (root/'score.jsonl').write_text(json.dumps(dict(timestamp=float(n),observation_id='fixture-camera-'+str(n),
            raw_frame='original.png',p1=dict(observed_score=n*100,confidence=.9)))+'\n')
    return root


def test_thirty_attempts_are_queued_without_review_and_missing_image_survives(tmp_path):
    j=EvidenceJournal(tmp_path/'journal.sqlite3')
    for n in range(1,31):
        root=game(tmp_path/f'game-{n}',n,photo=n!=10)
        first=ScoreObserver.queue_game(j,root,session='fixture-session',number=n,synthetic=True)
        assert ScoreObserver.queue_game(j,root,session='fixture-session',number=n,synthetic=True).id==first.id
    records=j.category_records('observation','score_game_record')
    assert len(records)==30 and len(j.category_records('observation','score_review_proposal'))==29
    assert records[9].data['payload']['proposal_id'] is None
    assert all(r.data['payload']['physical_authorization'] is False for r in records)
    assert not j.category_records('observation','score_human_annotation')
    j.verify();j.close()


def test_interrupted_attempt_remains_and_original_score_not_rewritten(tmp_path):
    j=EvidenceJournal(tmp_path/'journal.sqlite3');root=tmp_path/'missing'
    first=ScoreObserver.queue_game(j,root,session='fixture',number=1,interrupted=True)
    assert first.data['payload']['result']=='interrupted'
    game(root)
    later=ScoreObserver.queue_game(j,root,session='fixture',number=1,synthetic=True)
    assert later.data['payload']['previous']==first.id
    proposal=j.get(later.data['payload']['proposal_id'])
    before=proposal.document
    annotation=ScoreObserver.annotate_review(j,proposal.id,annotator='fixture reviewer',verdict='correct',value=200,
        reason='fixture correction',independent=True)
    ScoreObserver.annotate_review(j,proposal.id,annotator='fixture reviewer',verdict='correct',value=300,
        reason='later fixture correction',independent=True,supersedes=annotation.id)
    assert j.get(proposal.id).document==before
    assert len(j.category_records('observation','score_human_annotation'))==2
    j.close()
