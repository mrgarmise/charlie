"""Synthetic source cadence; original pixel retention is not game qualification."""
import json
import threading
import time
import pytest
from PIL import Image
from experiments.ppal.progress_evidence import CaptureEvidence
from memory.evidence import EvidenceJournal
from memory.episode_identity import recording_completion,verify_recording_completion,IdentityIntegrityError


def test_30hz_observations_5hz_images_exact_identity_and_clocks(tmp_path):
    r=CaptureEvidence(tmp_path,'simulated-cadence',{},visual_hz=5)
    base=time.monotonic();ids=[];frame=Image.new('RGB',(20,20),'red')
    for n in range(30):ids.append(r.capture(frame,dict(timestamp=base+n/30,sequence=n)))
    r.close();verify_recording_completion(tmp_path)
    j=EvidenceJournal(tmp_path/'session-evidence.sqlite3',read_only=True)
    obs=j.category_records('observation','camera_observation');captures=j.category_records('observation','camera_capture')
    assert len(obs)==30 and len(captures)==5 and len(set(ids))==30
    assert [x.data['payload']['sample'] for x in captures]==[1,7,13,19,25]
    assert [x.data['at'] for x in obs]==[base+n/30 for n in range(30)]
    assert sum(x.data['payload']['retention']['status']=='not_selected' for x in obs)==25
    assert all(x.data['payload']['observation_id'] in ids for x in captures)
    j.close()


def test_optional_payload_pressure_does_not_pause_critical_trace(tmp_path):
    r=CaptureEvidence(tmp_path,'simulation',{},visual_hz=10,capacity=2,record_capacity=32);r.ready()
    entered=threading.Event();release=threading.Event();original=r._capture
    def slow(*a):entered.set();assert release.wait(3);return original(*a)
    r._capture=slow
    t=time.monotonic();r.capture(Image.new('RGB',(20,20)),dict(timestamp=t));assert entered.wait(1)
    ids=[]
    for n in range(1,10):ids.append(r.capture(Image.new('RGB',(20,20)),dict(timestamp=t+n/10)))
    assert r.telemetry()['retention_counts']['unavailable']==9
    assert not r.telemetry()['paused']
    release.set();r.close();verify_recording_completion(tmp_path)
    assert len(list((tmp_path/'observations').glob('*.png')))==1


def test_multiframe_sources_stay_exact_even_without_saved_images(tmp_path):
    r=CaptureEvidence(tmp_path,'simulation',{},visual_hz=1)
    first=r.capture(Image.new('RGB',(20,20)),dict(timestamp=time.monotonic()))
    second=r.capture(Image.new('RGB',(20,20)),dict(timestamp=time.monotonic()))
    p=r.event('tactical_prediction',{'uncertainty':'provisional'},at=time.monotonic(),sources=[first,second])
    r.close();j=EvidenceJournal(tmp_path/'session-evidence.sqlite3',read_only=True)
    assert j.get(p).data['sources']==[second,first]
    assert j.get(second).data['payload']['retention']['status']=='not_selected'
    j.close()


def test_sampled_contract_cannot_excuse_missing_selected_pixel(tmp_path):
    r=CaptureEvidence(tmp_path,'simulation',{},visual_hz=5)
    r.capture(Image.new('RGB',(20,20)),dict(timestamp=time.monotonic()));r.close()
    next((tmp_path/'observations').glob('*.png')).unlink()
    with pytest.raises((IdentityIntegrityError,FileNotFoundError)):recording_completion(tmp_path)


def test_strict_default_still_requires_every_original(tmp_path):
    r=CaptureEvidence(tmp_path,'simulation',{})
    for n in range(3):r.capture(Image.new('RGB',(20,20)),dict(timestamp=time.monotonic()))
    r.close();assert len(list((tmp_path/'observations').glob('*.png')))==3
    assert r.telemetry()['visual_contract']=='strict-full-frame-v1'
    assert not r.visual_hz
