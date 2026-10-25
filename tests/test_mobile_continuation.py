import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from vision.mobile_tracking import PetTracker


def packet(at,label='cat',score=.4,box=(1,1,10,15),pan=None):
    return dict(frame=dict(id=str(at),received_at=at,pan_deg=pan,yaw_deg=None,geometry=[40,30]),
                objects=[dict(label=label,box=box,confidence=score)])


def test_species_flip_keeps_animal_id_and_separate_species_evidence():
    t=PetTracker()
    a=t.update(packet(1,'dog'))['tracks'][0]
    b=t.update(packet(1.2,'cat'))['target']
    assert b['id']==a['id'] and b['kind']=='animal'
    assert set(b['species_posterior'])=={'cat','dog'}
    assert 'ground truth' in b['species_calibration']
    assert b['lifecycle']=='confirmed'
    t.update(dict(frame=dict(received_at=1.3,pan_deg=None,yaw_deg=None),objects=[]))
    c=t.update(packet(1.4,'cat'))['target']
    assert c['id']==a['id'] and c['lifecycle']=='reacquired'
    assert t.invalidate()['target_lost']


def test_pose_change_does_not_assume_same_animal_geometry():
    t=PetTracker(confirmations=1)
    a=t.update(packet(1,pan=90))['target']
    b=t.update(packet(1.2,pan=120))
    assert b['target'] is None
    assert len(b['tracks'])==2


def test_native_import_integrity_idempotence_and_separate_labels(tmp_path):
    import cv2
    from learning.mobile_evidence import recover
    from memory.evidence import EvidenceJournal
    image=np.zeros((20,30,3),np.uint8);cv2.imwrite(str(tmp_path/'pet.png'),image)
    event=dict(time_utc='2026-10-24T23:48:27+00:00',frame_id='native:1',sequence=1,
        pixel_sha256=hashlib.sha256(image.tobytes()).hexdigest(),model_sha256='model',
        detections=[dict(label='dog',box=[1,1,10,15],confidence=.4)],saved_image='pet.png',motion_authorized=False)
    path=tmp_path/'events.jsonl';path.write_text(json.dumps(event)+'\n')
    labels={'pet.png':dict(species='cat',subject='Monty',source='test-only operator label')}
    result=recover(path,tmp_path,labels,output=tmp_path/'out')
    assert result['classification']['wrong_species']==1 and result['unlabeled_events']==0
    recover(path,tmp_path,labels,output=tmp_path/'out')
    j=EvidenceJournal(tmp_path/'out/native-evidence.sqlite3',read_only=True)
    assert len(j.records())==3
    raw=j.category_records('observation','mobile_native_prediction')[0]
    assert raw.data['payload']['raw']['detections'][0]['label']=='dog'
    assert j.category_records('observation','mobile_operator_annotation')[0].data['payload']['annotation']['species']=='cat'
    j.close()
    with pytest.raises(ValueError):recover(path,tmp_path,labels,output=tmp_path/'other',expected_sha='wrong')
    image[:]=255;cv2.imwrite(str(tmp_path/'pet.png'),image)
    with pytest.raises(ValueError,match='pixel integrity'):recover(path,tmp_path,labels,output=tmp_path/'bad')
