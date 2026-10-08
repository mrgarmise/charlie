"""Incident fixtures, not real collisions or independent gameplay."""
import time
from PIL import Image
from experiments.ppal.progress_evidence import CaptureEvidence
from memory.evidence import EvidenceJournal
from memory.episode_identity import verify_recording_completion


def test_past_future_overlap_preserves_original_identity_once(tmp_path):
    r=CaptureEvidence(tmp_path,'simulation',{},visual_hz=1,rolling_seconds=1,rolling_bytes=100000)
    base=time.monotonic();ids=[]
    for n in range(5):ids.append(r.capture(Image.new('RGB',(20,20),(n,0,0)),dict(timestamp=base+n/10)))
    request=r.request_incident('unexpected simulated response',preceding=.3,following=.2)
    overlap=r.request_incident('second simulated hypothesis',preceding=.2,following=0)
    for n in range(5,8):ids.append(r.capture(Image.new('RGB',(20,20),(n,0,0)),dict(timestamp=base+n/10)))
    r.close();verify_recording_completion(tmp_path)
    j=EvidenceJournal(tmp_path/'session-evidence.sqlite3',read_only=True)
    rows=j.category_records('observation','camera_capture')
    original=[x.data['payload']['observation_id'] for x in rows]
    assert len(original)==len(set(original)) and set(ids[2:6])<=set(original)
    resolutions=j.category_records('observation','incident_resolution')
    assert {x.data['payload']['request_id'] for x in resolutions}=={request,overlap}
    assert all(x.data['payload']['verification'].startswith('selected IDs') for x in resolutions)
    assert r.telemetry()['rolling']['bytes']==0
    j.close()


def test_eviction_byte_count_duration_and_shortfall_are_explicit(tmp_path):
    r=CaptureEvidence(tmp_path,'simulation',{},visual_hz=1,rolling_seconds=.2,rolling_frames=2,rolling_bytes=2400)
    base=time.monotonic()
    for n in range(5):r.capture(Image.new('RGB',(20,20)),dict(timestamp=base+n/10))
    t=r.telemetry()['rolling'];assert t['bytes']<=2400 and t['frames']<=2 and t['evictions']>=3
    request=r.request_incident('lost SELF fixture',preceding=1,following=1)
    r.close();verify_recording_completion(tmp_path)
    j=EvidenceJournal(tmp_path/'session-evidence.sqlite3',read_only=True)
    resolution=j.category_records('observation','incident_resolution')[0].data['payload']
    assert resolution['request_id']==request
    assert any(x['reason'].startswith('preceding originals') for x in resolution['shortfalls'])
    assert any(x['reason']=='following interval interrupted' for x in resolution['shortfalls'])
    j.close()


def test_incident_admission_capped_and_disabled_buffer_disclosed(tmp_path):
    r=CaptureEvidence(tmp_path,'simulation',{},visual_hz=5)
    r.capture(Image.new('RGB',(20,20)),dict(timestamp=time.monotonic()))
    for n in range(5):r.request_incident('fixture '+str(n),preceding=.1,following=1)
    assert len(r._incidents)==4
    r.close();j=EvidenceJournal(tmp_path/'session-evidence.sqlite3',read_only=True)
    requests=j.category_records('observation','incident_request')
    assert requests[-1].data['payload']['admission'].startswith('rejected')
    assert len(j.category_records('observation','incident_resolution'))==5
    j.close()
