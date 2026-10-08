"""Auditable human review interface fixtures; zero qualified physical games."""
import hashlib
import pytest
from PIL import Image
from memory.evidence import EvidenceJournal
from experiments.ppal.score_observer import ScoreObserver


def proposal(tmp_path,j,**kw):
    f=tmp_path/'original.png'
    if not f.exists():Image.new('RGB',(20,20),'red').save(f)
    return ScoreObserver.review_proposal(j,f,source_episode=kw.pop('episode','source-session'),timestamp=12.,clock='source monotonic',
        proposed=kw.pop('proposed',1200),confidence=kw.pop('confidence',.99),partition=kw.pop('partition','final'),**kw)


def test_correction_preserves_proposal_and_disagreement(tmp_path):
    j=EvidenceJournal(tmp_path/'review.sqlite3');p=proposal(tmp_path,j)
    ScoreObserver.annotate_review(j,p.id,annotator='independent fixture reviewer',verdict='correct',value=1300,reason='digits inspected fixture',independent=True)
    assert j.get(p.id).data['payload']['proposed_score']==1200
    metrics=ScoreObserver.review_metrics(j)
    assert metrics['exact_score_accuracy']==0 and metrics['false_confident_acceptances']==1
    ScoreObserver.annotate_review(j,p.id,annotator='second fixture reviewer',verdict='confirm',reason='contradictory fixture',independent=True)
    assert ScoreObserver.review_metrics(j)['disputed_proposals']==1
    assert ScoreObserver.review_metrics(j)['accepted']==0
    j.close()


def test_abstention_unreadable_and_source_partition_guard(tmp_path):
    j=EvidenceJournal(tmp_path/'review.sqlite3');p=proposal(tmp_path,j,proposed=None)
    ScoreObserver.annotate_review(j,p.id,annotator='fixture',verdict='correct',value=1300,reason='independent label fixture',independent=True)
    assert ScoreObserver.review_metrics(j)['abstention_rate']==1
    with pytest.raises(ValueError,match='partition'):proposal(tmp_path,j,partition='training')
    with pytest.raises(ValueError,match='partition'):proposal(tmp_path,j,episode='renamed-copy',partition='training')
    ScoreObserver.annotate_review(j,p.id,annotator='fixture2',verdict='unreadable',reason='ambiguous original',independent=True)
    assert ScoreObserver.review_metrics(j)['disputed_proposals']==1
    j.close()


def test_original_changed_rejects_review_and_synthetic_never_calibrates_reader(tmp_path):
    j=EvidenceJournal(tmp_path/'review.sqlite3');p=proposal(tmp_path,j,synthetic=True)
    ScoreObserver.annotate_review(j,p.id,annotator='fixture',verdict='confirm',reason='simulation only',independent=True)
    assert ScoreObserver.review_metrics(j)['eligible']==0
    Image.new('RGB',(20,20),'blue').save(tmp_path/'original.png')
    with pytest.raises(ValueError,match='changed'):ScoreObserver.annotate_review(j,p.id,annotator='fixture',verdict='confirm',reason='no rewrite')
    j.close()


def test_fifty_correct_does_not_certify_ninetynine_percent(tmp_path):
    j=EvidenceJournal(tmp_path/'review.sqlite3')
    for n in range(50):
        f=tmp_path/f'original-{n}.png';Image.new('RGB',(20,20),(n,0,0)).save(f)
        p=ScoreObserver.review_proposal(j,f,source_episode=f'controlled-source-{n}',timestamp=12.,clock='fixture',
            proposed=1200,confidence=1.,partition='final')
        ScoreObserver.annotate_review(j,p.id,annotator='fixture',verdict='confirm',reason='controlled fixture',independent=True)
    m=ScoreObserver.review_metrics(j)
    assert m['correct']==50 and m['wilson_95_interval'][0]<.99 and not m['target_99_supported']
    j.close()
