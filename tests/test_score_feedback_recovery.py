"""Controlled feedback mechanism tests; not October 10 or native acceptance."""
import json
from pathlib import Path
import pytest
import numpy as np
from PIL import Image
from memory.evidence import EvidenceJournal,digest
from experiments.ppal.eyes.calibration import Calibration
from experiments.ppal.robotron_hud import RobotronHUDReader
from experiments.ppal.score_observer import ScoreObserver
from experiments.ppal.score_feedback import build_candidate,ScoreFeedbackReader,reviewed_labels
from test_robotron_hud import glyph,cv2_resize


def fixture_frame():
    raw=np.zeros((960,640,3),dtype=np.uint8)
    for i,d in enumerate('8400'):
        raw[55:77,132+i*12:141+i*12]=cv2_resize(glyph(d),9,22)[:,:,None]*255
    return Image.fromarray(raw)


def calibration():return Calibration(((0,.1),(1,.1),(1,.6),(0,.6)))


def reviewed(tmp_path,*,partition='training',channel=1):
    j=EvidenceJournal(tmp_path/'review.sqlite3');frame=fixture_frame();path=tmp_path/'original.png';frame.save(path)
    value=RobotronHUDReader(calibration()).read(frame).player1_score
    p=ScoreObserver.review_proposal(j,path,source_episode='controlled-game',timestamp=12.,clock='fixture',
        proposed=value,confidence=.9,partition=partition,synthetic=True,
        context={'score_channel':channel,'reader_revision':'frozen-fixture','source_session':'controlled-session'})
    # Deliberately distinct fixture label demonstrates causality only; this is
    # not a new authentic human correction or a claim about visible raw digits.
    a=ScoreObserver.annotate_review(j,p.id,annotator='fixture',verdict='correct',value=9400,
        reason='controlled label perturbation; not authentic review',independent=True)
    return j,p,a,frame


def test_retained_state_changes_predictions_without_code_or_input_change(tmp_path):
    j,p,a,frame=reviewed(tmp_path);baseline=RobotronHUDReader(calibration()).read(frame)
    assert baseline.player1_score==8400
    original=p.document;candidate,state=build_candidate(j,calibration(),tmp_path/'candidate.json',allow_fixture=True)
    assert state['training_proposal_ids']==[p.id] and a.id in state['annotation_ids']
    with pytest.raises(ValueError,match='fixture'):ScoreFeedbackReader.load(tmp_path/'candidate.json',calibration())
    learned=ScoreFeedbackReader.load(tmp_path/'candidate.json',calibration(),allow_fixture=True).read(frame)
    assert learned.player1_score==9400 and learned.player1_confidence<=.9
    assert learned.player2_score is None and baseline.player2_score is None
    assert j.get(p.id).document==original and not candidate.data['payload']['physical_authorization']
    j.close();j=EvidenceJournal(tmp_path/'review.sqlite3',read_only=True)
    assert j.get(candidate.id).id==candidate.id
    assert ScoreFeedbackReader.load(tmp_path/'candidate.json',calibration(),allow_fixture=True).read(frame)==learned
    assert RobotronHUDReader(calibration()).read(frame)==baseline # Retained-state ablation.
    j.close()


def test_conflicts_supersession_missing_sensor_identity_and_partition_guards(tmp_path):
    j,p,a,frame=reviewed(tmp_path)
    rows,excluded=reviewed_labels(j,allow_fixture=True);assert len(rows)==1
    assert not reviewed_labels(j)[0]
    ScoreObserver.annotate_review(j,p.id,annotator='other',verdict='confirm',reason='conflicting fixture',independent=True)
    assert not reviewed_labels(j,allow_fixture=True)[0]
    # Explicit final holdout access is now supported for the neural-score
    # review corpus; a training-partition fixture must not leak into it.
    assert reviewed_labels(j,partition='final') == ([], [])
    assert reviewed_labels(j,partition='validation') == ([], [])
    Image.new('RGB',frame.size,'blue').save(tmp_path/'original.png')
    assert not reviewed_labels(j,allow_fixture=True)[0]
    j.close()


def test_candidate_integrity_calibration_and_no_overwrite(tmp_path):
    j,p,a,frame=reviewed(tmp_path);path=tmp_path/'candidate.json';record,state=build_candidate(j,calibration(),path,allow_fixture=True)
    with pytest.raises(FileExistsError):build_candidate(j,calibration(),path,allow_fixture=True)
    with pytest.raises(ValueError,match='calibration'):ScoreFeedbackReader.load(path,Calibration(((0,.2),(1,.2),(1,.8),(0,.8))),allow_fixture=True)
    state['prototypes'][0]['digit']='5';path.write_text(json.dumps(state))
    with pytest.raises(ValueError,match='integrity'):ScoreFeedbackReader.load(path,calibration(),allow_fixture=True)
    j.close()


def test_no_digit_alignment_guess_no_channel_guess_and_unreadable(tmp_path):
    j,p,a,frame=reviewed(tmp_path,channel=None)
    record,state=build_candidate(j,calibration(),tmp_path/'empty.json',allow_fixture=True)
    assert not state['prototypes'] and not state['training_proposal_ids']
    assert 'channel' in state['excluded'][0]['reason']
    # Correctly binds an independent new proposal instead of changing old IDs.
    j.close()


def test_candidate_does_not_cross_game_or_source_evaluation_partitions(tmp_path):
    from memory.evaluator import MemoryEvaluator
    j,p,a,frame=reviewed(tmp_path);record,state=build_candidate(j,calibration(),tmp_path/'model.json',allow_fixture=True)
    with pytest.raises(ValueError,match='sealed'):
        MemoryEvaluator.evaluate_score_reader(j,record.id,lambda image:(9400,.9),partition='final')
    assert not j.category_records('event','capability_activation')
    assert not j.category_records('event','learning_project_proposal')
    j.close()


def test_existing_game_review_restores_finality_without_certifying(tmp_path):
    from test_score_review_queue import game
    from experiments.ppal.inspect_robotron_score import review_game,queue_rows
    j=EvidenceJournal(tmp_path/'review.sqlite3');r=ScoreObserver.queue_game(j,game(tmp_path/'game'),session='fixture',number=1,synthetic=True)
    original=j.get(r.data['payload']['proposal_id']).document
    review_game(j,r.id,annotator='fixture',verdict='correct',value=1300,reason='fixture correction',independent=True,not_final_score=True,finality_unknown=True)
    row=queue_rows(j)[0];assert row['annotations'][0]['value']==1300
    assert row['review']['not_final_score'] and row['review']['finality_unknown']
    assert row['review']['independent_score_certificate'] is False
    assert j.get(r.data['payload']['proposal_id']).document==original
    with pytest.raises(ValueError,match='boolean'):review_game(j,r.id,annotator='fixture',verdict='confirm',not_final_score='yes')
    j.close()


def test_metrics_include_digit_errors_abstention_and_unreadable_false_positives():
    from memory.evaluator import MemoryEvaluator
    rows=[dict(label=1300,baseline=1200,candidate=1300,baseline_confidence=.99,confidence=.9),
        dict(label=None,baseline=100,candidate=None,baseline_confidence=1.,confidence=0),
        dict(label=1200,baseline=1200,candidate=1200,baseline_confidence=.99,confidence=.9)]
    before=MemoryEvaluator.score_recognition_metrics(rows,'baseline');after=MemoryEvaluator.score_recognition_metrics(rows,'candidate')
    assert before['exact_match_per_readable']==.5 and after['exact_match_per_readable']==1
    assert before['digit_accuracy']==.875 and after['digit_accuracy']==1
    assert before['false_positive_unreadable']==1 and after['false_positive_unreadable']==0
    assert before['false_high_confidence']==2 and after['false_high_confidence']==0


def test_original_export_preserves_ids_timestamps_and_reloads_relocated_image(tmp_path):
    from tools.recover_score_reviews import recover
    j,p,a,frame=reviewed(tmp_path);original=[(r.id,r.document,r.committed_at) for r in j.records()];j.close()
    result=recover(tmp_path/'review.sqlite3',tmp_path/'bundle')
    assert result['annotation_records']==1 and result['distinct_reviewed_images']==1
    assert result['corrected'][0]['id']==a.id and result['imported_to_development'] is None
    (tmp_path/'original.png').unlink() # Local controlled relocation, not a native deletion.
    copied=EvidenceJournal(tmp_path/'bundle'/'learning-evidence.sqlite3',read_only=True)
    assert original==[(r.id,r.document,r.committed_at) for r in copied.records()]
    assert ScoreObserver.review_artifact(copied,p.data['payload']).read_bytes()==(tmp_path/'bundle'/result['images'][0]['recovered_path']).read_bytes()
    copied.close()
    with pytest.raises(FileExistsError):recover(tmp_path/'review.sqlite3',tmp_path/'bundle')


def test_corrupt_external_identity_cannot_substitute_candidate_and_no_hardware_imports(tmp_path):
    import sys
    prohibited=('motion.controller','vision.camera','experiments.ppal.controller','experiments.ppal.play_robotron')
    before={name:sys.modules.get(name) for name in prohibited}
    j,p,a,frame=reviewed(tmp_path);record,state=build_candidate(j,calibration(),tmp_path/'model.json',allow_fixture=True)
    with pytest.raises(ValueError,match='identity'):ScoreFeedbackReader.load(tmp_path/'model.json',calibration(),allow_fixture=True,expected_state_digest='incorrect')
    with pytest.raises(ValueError,match='artifact'):ScoreFeedbackReader.load(tmp_path/'model.json',calibration(),allow_fixture=True,expected_artifact_sha256='incorrect')
    assert all(sys.modules.get(name) is before[name] for name in prohibited)
    assert not j.category_records('event','capability_activation')
    j.close()


def test_frozen_candidate_evaluation_measures_pixel_predictions_on_disjoint_fixture(tmp_path):
    from memory.evaluator import MemoryEvaluator
    j,p,a,frame=reviewed(tmp_path);record,state=build_candidate(j,calibration(),tmp_path/'model.json',allow_fixture=True)
    image=frame.copy();image.putpixel((500,800),(1,2,3));path=tmp_path/'validation.png';image.save(path)
    validation=ScoreObserver.review_proposal(j,path,source_episode='controlled-validation-game',timestamp=13.,clock='fixture',
        proposed=8400,confidence=1.,partition='validation',synthetic=True,
        context={'source_session':'controlled-validation-session','reader_revision':'frozen-fixture','score_channel':1})
    ScoreObserver.annotate_review(j,validation.id,annotator='fixture',verdict='correct',value=9400,
        reason='same controlled label perturbation; correlated generated glyphs, not independent physical evidence',independent=True)
    reader=ScoreFeedbackReader.load(tmp_path/'model.json',calibration(),allow_fixture=True)
    measured=MemoryEvaluator.evaluate_score_reader(j,record.id,lambda raw:
        (lambda obs:(obs.player1_score,obs.player1_confidence))(reader.read(raw)),allow_fixture=True)
    result=measured.data['payload']['report']
    assert result['baseline']['exact_accuracy']==0 and result['candidate']['exact_accuracy']==1
    assert result['baseline']['digit_accuracy']==.75 and result['candidate']['digit_accuracy']==1
    assert result['fixture_only'] and not result['physical_authorization']
    assert result['outcomes'][0]['proposal_id']==validation.id
    j.close()


def test_separate_review_source_is_acquired_once_then_consumed_after_relocation(tmp_path):
    from tools.recover_score_reviews import recover
    from experiments.ppal.inspect_robotron_score import import_reviews
    source=tmp_path/'source';source.mkdir();j,p,a,frame=reviewed(source);original=[(r.id,r.document,r.committed_at) for r in j.records()];j.close()
    recover(source/'review.sqlite3',tmp_path/'recovered');(source/'original.png').unlink()
    work=EvidenceJournal(tmp_path/'working'/'learning-evidence.sqlite3')
    first=import_reviews(work,tmp_path/'recovered'/'learning-evidence.sqlite3')
    assert first['images']==1 and first['added_records']==2
    before=[r.id for r in work.records()];second=import_reviews(work,tmp_path/'recovered'/'learning-evidence.sqlite3')
    assert second['added_records']==0 and first['receipt_id']==second['receipt_id']
    assert [r.id for r in work.records()]==before
    assert all((work.get(i).document,work.get(i).committed_at)==(d,t) for i,d,t in original)
    candidate,state=build_candidate(work,calibration(),tmp_path/'imported-model.json',allow_fixture=True)
    assert state['training_proposal_ids']==[p.id] and a.id in state['annotation_ids']
    assert ScoreFeedbackReader.load(tmp_path/'imported-model.json',calibration(),allow_fixture=True).read(frame).player1_score==9400
    work.close()
