"""Offline interfaces only; fixture predictions and reviews are not game scores."""
import pytest
from PIL import Image
from memory.evidence import EvidenceJournal
from memory.evaluator import MemoryEvaluator
from experiments.ppal.score_observer import ScoreObserver


def reviewed(j,root,*,episode='validation-game',partition='validation',session='validation-session',synthetic=True):
    root.mkdir(exist_ok=True);f=root/'original.png';Image.new('RGB',(20,20),'green').save(f)
    p=ScoreObserver.review_proposal(j,f,source_episode=episode,timestamp=1.,clock='fixture',
        proposed=100,confidence=.99,partition=partition,synthetic=synthetic,
        context={'source_session':session,'reader_revision':'frozen-fixture-reader'})
    ScoreObserver.annotate_review(j,p.id,annotator='fixture',verdict='correct',value=200,
        reason='fixture only',independent=True)
    return p


def candidate(j,training):
    return j.append('observation',dict(category='score_reader_candidate',training_proposal_ids=training,
        reader_revision='fixture-candidate'),episode='fixture-investigation',producer='Reflection',version='fixture')


def test_existing_evaluator_compares_frozen_original_predictions(tmp_path):
    j=EvidenceJournal(tmp_path/'e.sqlite3');p=reviewed(j,tmp_path/'image');c=candidate(j,[])
    result=MemoryEvaluator.evaluate_score_reader(j,c.id,lambda image:(200,.8),allow_fixture=True)
    r=result.data['payload']['report']
    assert r['baseline']['exact_accuracy']==0 and r['candidate']['exact_accuracy']==1
    assert r['fixture_only'] and not r['physical_authorization']
    assert j.get(p.id).data['payload']['proposed_score']==100
    assert MemoryEvaluator.evaluate_score_reader(j,c.id,lambda image:(200,.8)).data['payload']['report']['status']=='unresolved'
    with pytest.raises(ValueError,match='sealed'):MemoryEvaluator.evaluate_score_reader(j,c.id,lambda image:(200,.8),partition='final')
    with pytest.raises(ValueError,match='confidence'):MemoryEvaluator.evaluate_score_reader(j,c.id,lambda image:(200,float('nan')),allow_fixture=True)
    with pytest.raises(ValueError,match='score'):MemoryEvaluator.evaluate_score_reader(j,c.id,lambda image:(True,.8),allow_fixture=True)
    j.verify();j.close()


def test_training_consultation_and_original_integrity_gate(tmp_path):
    j=EvidenceJournal(tmp_path/'e.sqlite3');p=reviewed(j,tmp_path/'image');c=candidate(j,[p.id])
    with pytest.raises(ValueError,match='overlaps'):MemoryEvaluator.evaluate_score_reader(j,c.id,lambda image:(200,.8),allow_fixture=True)
    c=candidate(j,[]);Image.new('RGB',(20,20),'red').save(tmp_path/'image'/'original.png')
    with pytest.raises(ValueError,match='changed'):MemoryEvaluator.evaluate_score_reader(j,c.id,lambda image:(200,.8),allow_fixture=True)
    j.close()


def test_normal_acquisition_preserves_review_ids_and_idempotent_restart(tmp_path):
    from learning.lifecycle import DevelopmentLifecycle
    root=tmp_path/'authorized';root.mkdir();source=EvidenceJournal(root/'session-evidence.sqlite3')
    p=reviewed(source,root/'image',partition='diagnostic');ids=[r.id for r in source.records()];source.close()
    output=tmp_path/'normal'
    life=DevelopmentLifecycle(output,[root])
    try:
        life.acquire();assert all(life.journal.get(i).id==i for i in ids)
        assert life.journal.category_records('observation','score_reader_review_reconciliation')
        before=[r.id for r in life.journal.records()]
    finally:life.close()
    life=DevelopmentLifecycle(output,[root])
    try:
        life.acquire();assert [r.id for r in life.journal.records()]==before
        assert life.executive.projects()=={} # observations do not impose an agenda
    finally:life.close()


def test_reflection_exposes_diagnostic_feedback_without_opening_final_labels(tmp_path):
    from experiments.ppal.reflect_robotron import expose_score_review_contexts
    from learning.datasets import ExperienceDataset
    j=EvidenceJournal(tmp_path/'e.sqlite3');dataset=ExperienceDataset(j,tmp_path/'pixels')
    reviewed(j,tmp_path/'diagnostic',partition='diagnostic',synthetic=False)
    rows=expose_score_review_contexts(dataset);assert len(rows)==1
    assert rows[0].data['payload']['context']['questions'][0]['category']=='score_reader_review_uncertainty'
    assert expose_score_review_contexts(dataset)[0].id==rows[0].id
    # A final source uses different pixels/session; it must remain absent here.
    root=tmp_path/'final';root.mkdir();f=root/'original.png';Image.new('RGB',(20,20),'blue').save(f)
    p=ScoreObserver.review_proposal(j,f,source_episode='final-game',timestamp=1.,clock='fixture',proposed=10,
        confidence=.9,partition='final',context={'source_session':'final-session','reader_revision':'fixture'})
    ScoreObserver.annotate_review(j,p.id,annotator='fixture',verdict='confirm',reason='controlled interface fixture',independent=True)
    assert len(expose_score_review_contexts(dataset))==1
    assert not j.category_records('event','learning_project_proposal') # Reflection/Executive later own commissioning
    j.close()
