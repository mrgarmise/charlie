from pathlib import Path
import pytest
from PIL import Image
from memory.evidence import EvidenceJournal
from learning.datasets import ExperienceDataset
pytest.importorskip('torch')
from learning.foundry import train,evaluate,validate_spec,checked_load


def data(tmp_path,classification=False):
    ds=ExperienceDataset(EvidenceJournal(tmp_path/'e.sqlite3'),tmp_path/'pixels')
    for group in range(3):
        for label in range(2):
            p=tmp_path/f'{group}-{label}.png'; Image.new('RGB',(24,24),(label*180+group,10,20)).save(p)
            r=ds.add(p,episode=str(group),source={'kind':'controlled-test'})
            if classification and not next(x for x in ds.examples() if x['id']==r.id)['annotation']:
                ds.annotate(r.id,str(label),status='verified',source='independent_measurement',evidence='synthetic-generator:'+str(label))
    result=ds.snapshot(objective='classification' if classification else 'reconstruction').data['payload']; ds.journal.close(); return result


def spec(objective='reconstruction'):
    return dict(family='small-cnn',objective=objective,channels=[4],kernel=3,activation='relu',size=16,epochs=4,lr=.01,seed=0,patience=5)


def test_resume_reproducible_and_independent_test(tmp_path):
    snapshot=data(tmp_path)
    with pytest.raises(InterruptedError): train(snapshot,spec(),tmp_path/'resume',interrupt_after=2)
    resumed=train(snapshot,spec(),tmp_path/'resume'); fresh=train(snapshot,spec(),tmp_path/'fresh')
    assert resumed['history']==fresh['history'] and resumed['checkpoint_sha256']==fresh['checkpoint_sha256']
    assert not resumed['test_consulted'] and evaluate(snapshot,resumed)==evaluate(snapshot,fresh)
    assert (tmp_path/'resume/last.pointer.json').exists()
    modified=spec(); modified['lr']=.02
    with pytest.raises(ValueError,match='changed'): train(snapshot,modified,tmp_path/'resume')


def test_classification_and_guardrails(tmp_path):
    snapshot=data(tmp_path,True); result=train(snapshot,spec('classification'),tmp_path/'model')
    assert evaluate(snapshot,result)['metric']=='balanced_accuracy'
    invalid=spec(); invalid['python']='print(42)'
    with pytest.raises(ValueError): validate_spec(invalid)
    Path(result['checkpoint']).write_bytes(b'modified')
    with pytest.raises(ValueError): checked_load(result['checkpoint'])


def test_training_does_not_open_test_pixels(tmp_path):
    snapshot=data(tmp_path)
    for row in snapshot['examples']:
        if row['partition']=='test': Path(row['pixel_path']).unlink()
    result=train(snapshot,spec(),tmp_path/'model')
    with pytest.raises(FileNotFoundError): evaluate(snapshot,result)
