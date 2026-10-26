"""Controlled archive/review fixtures; never native or authentic score accuracy."""
import hashlib
import io
import json
import tarfile

import pytest
from PIL import Image

from memory.evidence import EvidenceJournal
from experiments.ppal.score_observer import ScoreObserver
from tools.recover_score_review_evidence import recover


def add(archive,name,data):
    member=tarfile.TarInfo(name);member.size=len(data)
    archive.addfile(member,io.BytesIO(data))


@pytest.mark.parametrize('include_image',[True,False])
def test_recovery_preserves_original_reviews_and_partitions(tmp_path,include_image):
    source=tmp_path/'original.png';Image.new('RGB',(640,600),'white').save(source)
    pixels=source.read_bytes();image_hash=hashlib.sha256(pixels).hexdigest()
    db=tmp_path/'source.sqlite3';j=EvidenceJournal(db)
    proposal=ScoreObserver.review_proposal(j,source,source_episode='fixture-session',
        timestamp=10,clock='controlled fixture',proposed=100,confidence=.9,
        synthetic=False,partition='diagnostic',context={'source_session':'fixture-session'})
    ScoreObserver.annotate_review(j,proposal.id,annotator='fixture-human',
        verdict='correct',value=2200,reason='controlled test only',independent=True)
    j.close();original=db.read_bytes();db_hash=hashlib.sha256(original).hexdigest()
    audit=tmp_path/'audit.tar.gz'
    with tarfile.open(audit,'w:gz') as archive:
        add(archive,'audit/score-review-audit.json',json.dumps({'sha256':db_hash}).encode())
        add(archive,'audit/sqlite/'+db_hash+'.sqlite3',original)
    images=tmp_path/'images.tar.gz'
    with tarfile.open(images,'w:gz') as archive:
        if include_image:add(archive,'../../never-extract.png',pixels)
    source.rename(tmp_path/'source-no-longer-present.png')
    out=tmp_path/'recovered'
    report=recover(audit,[images],out)
    assert db.read_bytes()==(out/'learning-evidence.sqlite3').read_bytes()==original
    assert report['partitions']['training']['eligible']==0
    assert report['partitions']['diagnostic']['eligible']==int(include_image)
    assert report['recovered_annotation_photos']==int(include_image)
    assert report['missing_annotation_photos']==([] if include_image else [image_hash])
    assert not (tmp_path/'never-extract.png').exists()
    assert not report['model_trained'] and not report['hef_generated']
    with pytest.raises(FileExistsError):recover(audit,[images],out)


def test_recovery_rejects_corrupt_snapshot(tmp_path):
    path=tmp_path/'audit.tar.gz'
    with tarfile.open(path,'w:gz') as archive:
        add(archive,'audit/score-review-audit.json',json.dumps({'sha256':'0'*64}).encode())
        add(archive,'audit/sqlite/'+'0'*64+'.sqlite3',b'not the claimed database')
    with pytest.raises(ValueError,match='integrity'):recover(path,[],tmp_path/'out')
