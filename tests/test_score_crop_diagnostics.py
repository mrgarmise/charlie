"""Controlled fixtures; authentic corpus-005/model-002 are operator dependencies."""
import json
from pathlib import Path
import numpy as np
import pytest
from PIL import Image,ImageDraw

from experiments.ppal.neural_score.contract import (PREPROCESS,PADDED_PREPROCESS,
    preprocess,decode,sha,OUTPUT)
from experiments.ppal.neural_score.corpus import freeze,from_reviews,verify
from experiments.ppal.neural_score.diagnose import channel_geometry,ctc_trace,run
from experiments.ppal.neural_score.train import ctc_targets,train
from experiments.ppal.neural_score.evaluate import metrics
from experiments.ppal.score_digits import valid_display_digits
from experiments.ppal.score_feedback import reviewed_labels
from experiments.ppal.score_observer import ScoreObserver
from experiments.ppal.eyes.calibration import Calibration
from memory.evidence import EvidenceJournal,digest


def sample(tmp_path,label='00',partition='training',synthetic=False):
    cal=Calibration(((0,.2),(1,.2),(1,1),(0,1)))
    path=tmp_path/'original.png';image=Image.new('RGB',(640,600))
    ImageDraw.Draw(image).rectangle((90,86,150,100),fill='white');image.save(path)
    j=EvidenceJournal(tmp_path/'reviews.sqlite3')
    proposal=ScoreObserver.review_proposal(j,path,source_episode='fixture-session',timestamp=10,
        clock='fixture',proposed=0,confidence=.9,partition=partition,synthetic=synthetic,
        context=dict(score_channel=1,source_session='fixture-session',
        calibration_geometry_digest=digest(dict(corners=cal.corners,output_size=cal.output_size))))
    annotation=ScoreObserver.annotate_review(j,proposal.id,annotator='fixture',verdict='correct',
        value=int(label),visible_digits=label,reason='controlled fixture',independent=True)
    return j,proposal,annotation,cal,path


@pytest.mark.parametrize('value',['0','00','100','800','1200'])
def test_exact_target_and_display_validity(value):
    assert valid_display_digits(value) and ctc_targets(value)==list(map(int,value))


@pytest.mark.parametrize('value',['0000','000','01','１２',None,0,'-1'])
def test_invalid_targets_cannot_be_normalized(value):
    assert not valid_display_digits(value)
    with pytest.raises(ValueError):ctc_targets(value)


def test_human_two_zeros_survive_entire_pipeline(tmp_path):
    j,p,a,cal,path=sample(tmp_path)
    original=sha(path)
    rows,_=reviewed_labels(j)
    assert rows[0]['display_digits']=='00' and rows[0]['label']==0
    corpus=from_reviews(j,cal,tmp_path/'corpus')
    label=corpus['rows'][0]['label']
    assert label=='00' and ctc_targets(label)==[0,0]
    result=metrics([dict(label=label,prediction=dict(proposed_digits='00',digits=None,score=None,confidence=.8,reason='ambiguous'),wall_seconds=.1)])
    assert result['raw_exact']==1 and result['accepted']==0 and result['per_score']['00']['samples']==1
    assert sha(path)==original and j.get(a.id).data['payload']['visible_digits']=='00'
    j.close()


def test_historical_invalid_label_superseded_without_rewriting(tmp_path):
    j,p,a,cal,path=sample(tmp_path)
    payload=dict(j.get(a.id).data['payload'],visible_digits='0000',supersedes=a.id)
    # Deliberately preserve a historically admitted bad annotation fixture.
    old=j.append('observation',payload,episode='fixture-session',producer='human-score-review',version='1')
    assert reviewed_labels(j)[0]==[]
    assert 'unsupported Robotron' in reviewed_labels(j)[1][0]['reason']
    before=old.data
    corrected=ScoreObserver.annotate_review(j,p.id,annotator='fixture',verdict='correct',value=0,
        visible_digits='00',reason='controlled human supersession',independent=True,supersedes=old.id)
    assert reviewed_labels(j)[0][0]['display_digits']=='00'
    assert j.get(old.id).data==before and corrected.data['payload']['supersedes']==old.id
    with pytest.raises(ValueError):ScoreObserver.annotate_review(j,p.id,annotator='fixture',verdict='correct',value=0,
        visible_digits='0000',reason='invalid',independent=True)
    j.close()


def test_geometry_is_actual_channel_not_whole_screen(tmp_path):
    j,p,a,cal,path=sample(tmp_path)
    with Image.open(path) as image:hud,crop,meta=channel_geometry(image,cal,1)
    assert hud.size==(640,96) and crop.size==(115,96)
    assert meta['crop_box_hud']==[64,0,179,96] and meta['camera_pixel_coverage']==1
    assert meta['bright_bbox'] and not meta['bright_touches_edge']
    with Image.open(path) as raw:
        assert crop.tobytes()==__import__('experiments.ppal.robotron_hud',fromlist=['RobotronHUDReader']).RobotronHUDReader(cal).rectify(raw).crop((64,0,179,96)).tobytes()
    j.close()


def test_fixed_padding_and_ctc_axes_do_not_change_decoder_gates():
    image=Image.new('RGB',(115,96),'white')
    x,m=preprocess(image,profile=PADDED_PREPROCESS)
    assert m['padding']==[16,2] and x.shape==(1,3,32,256)
    assert np.all(x[:,:,:2,:]==0) and np.all(x[:,:,:,:16]==0)
    assert np.all(x[:,:,2:30,16:240]==1)
    assert m['scale_xy'][0]/m['scale_xy'][1]==pytest.approx((256/115)/(32/96))
    a=np.full(OUTPUT,-8.,np.float32);a[:,10,:,:]=8
    for index in (4,8):a[:,:,0,index]=-8;a[:,0,0,index]=8
    assert ctc_trace(a)['prediction']['digits']=='00'
    a[:,:,0,0]=-8;a[:,0,0,0]=8
    trace=ctc_trace(a)
    assert trace['first_token']==0 and trace['last_blank']
    assert trace['prediction']['score'] is None and trace['prediction']['reason']=='edge/truncated sequence'
    a=np.full(OUTPUT,-8.,np.float32);a[:,10,:,:]=8
    for index in (4,8,12,16):a[:,:,0,index]=-8;a[:,0,0,index]=8
    assert decode(a)['proposed_digits']=='0000' and decode(a)['score'] is None


def test_training_only_diagnostics_preserve_sources_and_final_ledger(tmp_path):
    j,p,a,cal,path=sample(tmp_path)
    corpus_path=tmp_path/'corpus'/'manifest.json';from_reviews(j,cal,corpus_path.parent)
    before=sha(corpus_path);image_before=sha(path)
    report=run(corpus_path,tmp_path/'diagnostic',calibration=cal,limit=1)
    assert report['training_images']==1 and report['geometry_status']=={'verified':1}
    assert report['final_test_consulted'] is False
    assert (tmp_path/'diagnostic'/'contact-sheet.png').is_file()
    assert sha(corpus_path)==before and sha(path)==image_before
    ledger=(corpus_path.parent/'score-corpus-ledger.jsonl').read_text()
    assert 'test-consulted' not in ledger
    with pytest.raises(FileExistsError):run(corpus_path,tmp_path/'diagnostic')
    j.close()


def test_actual_export_opset_and_profile_resume_guard(tmp_path):
    pytest.importorskip('torch');onnx=pytest.importorskip('onnx')
    j,p,a,cal,path=sample(tmp_path);manifest=tmp_path/'corpus'/'manifest.json'
    from_reviews(j,cal,manifest.parent);j.close()
    result=train(manifest,tmp_path/'model',steps=2,seconds=30,preprocessing=PADDED_PREPROCESS,boundary_blank_weight=.1)
    assert result['export']['opset_imports']=={'':11}
    assert result['preprocessing']==PADDED_PREPROCESS
    assert len(result['boundary_losses'])==2
    repeated=train(manifest,tmp_path/'reproduced',steps=2,seconds=30,preprocessing=PADDED_PREPROCESS,boundary_blank_weight=.1)
    from experiments.ppal.neural_score.model import load
    import torch
    one,_=load(tmp_path/'model'/'score.pt');two,_=load(tmp_path/'reproduced'/'score.pt')
    assert all(torch.equal(value,two.state_dict()[key]) for key,value in one.state_dict().items())
    from experiments.ppal.neural_score.model import reexport
    source_hash=sha(tmp_path/'model'/'score.onnx')
    converted=reexport(tmp_path/'model'/'score.pt',tmp_path/'model'/'training.json',tmp_path/'reexported')
    assert converted['source_onnx_sha256']==source_hash and converted['weights_retrained'] is False
    assert converted['export']['opset_imports']=={'':11}
    assert sha(tmp_path/'model'/'score.onnx')==source_hash
    from tools.bundle_score_crop_diagnostics import bundle
    calibration_path=tmp_path/'calibration.json';cal.save(calibration_path)
    # Original paths still resolve; the optional relocation map is unused.
    export=tmp_path/'portable';export.mkdir();(export/'image-locations.json').write_text('{}')
    packed=bundle(manifest,tmp_path/'model',calibration_path,export,tmp_path/'bundle')
    assert packed['training_images']==1 and packed['reserved_evaluation_included'] is False
    assert (tmp_path/'bundle'/'corpus'/'manifest.json').read_bytes()==manifest.read_bytes()
    assert sha(path)==packed['file_sha256']['originals/images/'+sha(path)+'.png']
    from experiments.ppal.neural_score.backends import CPU
    model_path=tmp_path/'model'/'score.onnx'
    with pytest.raises(ValueError,match='preprocessing mismatch'):CPU(model_path,sha(model_path))
    CPU(model_path,sha(model_path),preprocessing=PADDED_PREPROCESS)
    with pytest.raises(ValueError,match='resume preprocessing'):
        train(manifest,tmp_path/'invalid-resume',steps=1,seconds=30,resume=tmp_path/'model'/'score.pt')
    from experiments.ppal.neural_score.compile import validate_graph
    graph=onnx.load(tmp_path/'model'/'score.onnx');graph.opset_import[0].version=18
    wrong=tmp_path/'opset18.onnx';onnx.save(graph,wrong)
    with pytest.raises(ValueError,match='actual ONNX opset 11'):validate_graph(wrong)


def test_no_synthetic_leakage_or_guessed_legacy_zero(tmp_path):
    j,p,a,cal,path=sample(tmp_path,synthetic=True)
    assert not reviewed_labels(j)[0]
    j.close()


def test_prior_frozen_near_duplicate_cannot_enter_validation(tmp_path):
    first=tmp_path/'train.png';Image.new('RGB',(115,96),(80,80,80)).save(first)
    def row(path,role):return dict(image=str(path),sha256=sha(path),label='00',role=role,
        session=role,verified=True,reviewer='fixture',annotation_ids=[role])
    train_manifest=tmp_path/'training.json';freeze([row(first,'train')],train_manifest)
    later=tmp_path/'validation.png';Image.new('RGB',(115,96),(81,81,81)).save(later)
    with pytest.raises(ValueError,match='near-duplicate split leakage'):
        freeze([row(later,'val')],tmp_path/'validation.json',previous=[train_manifest])
