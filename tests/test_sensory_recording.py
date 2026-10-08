from pathlib import Path
from types import SimpleNamespace
import hashlib
import pytest
from PIL import Image
from experiments.ppal.progress_evidence import CaptureEvidence
from memory.evidence import EvidenceJournal


def test_lossless_capture_before_prediction_and_ordered_outcome_restart(tmp_path):
    import time
    recorder=CaptureEvidence(tmp_path,'session:test',{'source':'simulation'})
    frame=Image.new('RGB',(80,60),'red')
    recorder.capture(frame,dict(timestamp=time.monotonic(),capture={'mode':'simulation'}));recorder.ready()
    p=recorder.event('exploratory_prediction',dict(question='does control change screen?',controls=['A']),at=time.monotonic())
    recorder.capture(frame,dict(timestamp=time.monotonic(),capture={'mode':'simulation'}))
    recorder.event('exploratory_outcome',dict(prediction_id=p,scene_changed=False,uncertainty='ambiguous effect'),at=time.monotonic())
    recorder.close()
    journal=EvidenceJournal(tmp_path/'session-evidence.sqlite3',read_only=True)
    original=[r.id for r in journal.records()]
    assert len(journal.records('prediction'))==len(journal.records('resolution'))==1
    assert journal.records('resolution')[0].data['payload']['result']=='unresolved'
    assert Image.open(tmp_path/'observations/camera-000001.png').tobytes()==frame.tobytes()
    journal.close()
    recorder=CaptureEvidence(tmp_path,'session:test',{'source':'simulation'})
    assert recorder.count==2
    recorder.close()
    journal=EvidenceJournal(tmp_path/'session-evidence.sqlite3',read_only=True)
    assert [r.id for r in journal.records()]==original
    journal.close()


def test_orphaned_capture_survives_without_fake_observation(tmp_path):
    (tmp_path/'observations').mkdir();Image.new('RGB',(32,32)).save(tmp_path/'observations/camera-000007.png')
    before=(tmp_path/'observations/camera-000007.png').read_bytes()
    r=CaptureEvidence(tmp_path,'session:test',{});assert r.count==7
    r.capture(Image.new('RGB',(32,32),'white'),dict(timestamp=1));r.close()
    assert (tmp_path/'observations/camera-000007.png').read_bytes()==before
    j=EvidenceJournal(tmp_path/'session-evidence.sqlite3',read_only=True)
    assert len(j.records())==1 and j.records()[0].data['payload']['sample']==8;j.close()


def test_actual_sensory_preflight_bounded_optics_and_quality(monkeypatch,tmp_path):
    from experiments.ppal import preflight as p
    from tests.test_robotron_preflight import _synthetic_robotron_border
    from PIL import ImageDraw
    image=_synthetic_robotron_border();ImageDraw.Draw(image).text((200,200),'OBSERVED DETAIL',fill='white')
    class Source:
        capture={}
        def read(self):return image
        def lens_position(self):return 1.3
        def set_manual_focus(self,n):self.focus=n
        def lock_white_balance(self,c):return False
    # Existing physical geometry/focus algorithms remain real; no controller,
    # camera hardware or motion interface is created.
    source=Source();c,report=p.sensory_preflight(source,tmp_path,timeout=60)
    assert report['status']=='usable' and report['geometry']['observations']>=6
    assert report['quality']['detail_pixels']>=50 and source.focus>=0
    assert report['physical_motion'] is False and 'unqualified' in report['color_fidelity']


def test_unreadable_preflight_preserves_failure_and_never_calls_controller(tmp_path):
    from experiments.ppal.preflight import sensory_preflight
    class Source:
        capture={}
        def read(self):return Image.new('RGB',(160,120))
        def lens_position(self):return 1.3
        def set_manual_focus(self,n):pass
    with pytest.raises(ValueError):sensory_preflight(Source(),tmp_path,timeout=.02)
    import json
    d=json.loads((tmp_path/'sensory-preflight.json').read_text())
    assert d['status']=='failed' and d['request'] and not d['physical_motion']


def test_live_prediction_history_enters_existing_acquisition_once(tmp_path):
    import json,time
    from experiments.ppal.episode_evidence import import_episode
    root=tmp_path/'run';root.mkdir()
    r=CaptureEvidence(root,'recording-not-qualified-game',{'source':'simulation'})
    r.capture(Image.new('RGB',(32,32)),dict(timestamp=time.monotonic()));r.ready()
    prediction=r.event('tactical_prediction',dict(question='test response',hypothesis={'move':'E'}),at=time.monotonic())
    r.capture(Image.new('RGB',(32,32),'white'),dict(timestamp=time.monotonic()))
    r.event('tactical_outcome',dict(prediction_id=prediction,eligible=True,resolved_result='contradicted'),at=time.monotonic());r.close()
    (root/'report.json').write_text(json.dumps({'result':'simulated recording','steps':[]}))
    original=EvidenceJournal(root/'session-evidence.sqlite3',read_only=True)
    original_rows={row.id:row.document for row in original.records()};original.close()
    j=EvidenceJournal(tmp_path/'learning.sqlite3');episode=import_episode(root,j)
    assert all(j.get(k).document==v for k,v in original_rows.items())
    before=[row.id for row in j.records()]
    assert import_episode(root,j)==episode and [row.id for row in j.records()]==before
    assert len(j.records('episode'))==1
    assert j.get(prediction).data['payload']['mode']=='live_prospective'
    assert j.records('resolution')[0].data['payload']['result']=='contradicted'
    j.verify();j.close()


def test_recording_congestion_retains_last_frame_and_fails_closed(tmp_path):
    import threading,time
    from experiments.ppal.progress_supervision import ObservationFailure
    r=CaptureEvidence(tmp_path,'simulation',{},capacity=1);r.ready()
    release=threading.Event();started=threading.Event();original=r._capture
    def slow(*args):
        started.set();assert release.wait(2);return original(*args)
    r._capture=slow
    r.capture(Image.new('RGB',(32,32),'red'),dict(timestamp=time.monotonic()))
    assert started.wait(1)
    try:
        with pytest.raises(ObservationFailure,match='saturated'):
            r.capture(Image.new('RGB',(32,32),'blue'),dict(timestamp=time.monotonic()))
    finally:release.set();r.close()
    assert Image.open(tmp_path/'observations/camera-000002.png').getpixel((0,0))==(0,0,255)
