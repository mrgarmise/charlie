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


def test_camera_recovery_bounded_faults_and_cancel():
    from unittest.mock import Mock
    import threading
    from vision.mobile_perception import MobileFrameSource
    im=np.zeros((20,30,3),np.uint8)
    camera=Mock();camera.read.side_effect=[TimeoutError('stall'),(im,dict(sequence=5,received_at=1))]
    faults=[]
    s=MobileFrameSource(camera,clock=lambda:1,reconnect_attempts=2,backoff=0,on_fault=lambda e,m:faults.append(m))
    assert s.read().sequence==5 and len(faults)==1 and s.stats['faults']==1
    s.close()
    with pytest.raises(InterruptedError):s.read()
    camera=Mock();camera.read.side_effect=EOFError('offline')
    s=MobileFrameSource(camera,clock=lambda:1,reconnect_attempts=2,backoff=0)
    with pytest.raises(EOFError):s.read()
    assert camera.read.call_count==3


def test_old_camera_generation_cannot_publish_after_reopen():
    from hardware.elegoo_camera import ElegooCamera
    from unittest.mock import Mock
    camera=ElegooCamera();camera._running=True;camera._generation=2
    old=Mock();old.read.side_effect=AssertionError('old stream must not read')
    camera._reader_loop(old,1)
    old.read.assert_not_called()
    assert camera._running


def fake_hailo(monkeypatch,fail=False):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from unittest.mock import Mock
    import sys
    counts=dict(configure=0,infer=0,closed=0)
    @contextmanager
    def ctx(value):
        try:yield value
        finally:counts['closed']+=1
    group=SimpleNamespace(create_params=lambda:None,activate=lambda p:ctx(None))
    def configure(*a):counts['configure']+=1;return [group]
    device=SimpleNamespace(configure=configure)
    def infer(values):
        counts['infer']+=1
        if fail:raise TimeoutError('SDK timeout')
        return dict(out=np.arange(12).reshape(1,3,4,1))
    hef=SimpleNamespace(get_input_vstream_infos=lambda:[SimpleNamespace(name='input',shape=(2,2,3))],
                        get_output_vstream_infos=lambda:[SimpleNamespace(name='out',shape=(3,4,1))])
    params=SimpleNamespace(make_from_network_group=lambda *a,**k:{})
    module=SimpleNamespace(HEF=lambda p:hef,VDevice=lambda:ctx(device),
        ConfigureParams=SimpleNamespace(create_from_hef=lambda *a,**k:{}),HailoStreamInterface=SimpleNamespace(PCIe=1),
        InputVStreamParams=params,OutputVStreamParams=params,FormatType=SimpleNamespace(FLOAT32=1),
        InferVStreams=lambda *a:ctx(SimpleNamespace(infer=infer)))
    monkeypatch.setitem(sys.modules,'hailo_platform',module)
    return counts


def test_persistent_session_configures_once_and_releases_on_close(tmp_path,monkeypatch):
    from hardware.hailo_session import HailoSession,accelerator_lease
    counts=fake_hailo(monkeypatch);path=tmp_path/'model.hef';path.write_bytes(b'fixture')
    session=HailoSession(path,sha256=hashlib.sha256(b'fixture').hexdigest(),input_shape=(2,2,3),lock=tmp_path/'lock')
    session.infer(np.zeros((1,2,2,3)));session.infer(np.zeros((1,2,2,3)))
    assert counts['configure']==1 and counts['infer']==2
    with pytest.raises(BlockingIOError):
        with accelerator_lease(tmp_path/'lock'):pass
    session.close();assert counts['closed']==3
    with accelerator_lease(tmp_path/'lock'):pass


def test_session_timeout_and_bad_hash_release_everything(tmp_path,monkeypatch):
    from hardware.hailo_session import HailoSession,accelerator_lease
    counts=fake_hailo(monkeypatch,fail=True);path=tmp_path/'model.hef';path.write_bytes(b'fixture')
    session=HailoSession(path,sha256=hashlib.sha256(b'fixture').hexdigest(),input_shape=(2,2,3),lock=tmp_path/'lock')
    with pytest.raises(TimeoutError):session.infer(np.zeros((1,2,2,3)))
    assert session.stack is None and counts['closed']==3
    with accelerator_lease(tmp_path/'lock'):pass
    session=HailoSession(path,sha256='wrong',input_shape=(2,2,3),lock=tmp_path/'lock')
    with pytest.raises(ValueError):session.open()
    with accelerator_lease(tmp_path/'lock'):pass
