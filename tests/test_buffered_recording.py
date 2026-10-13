"""Controlled software recording loads; no camera or physical transport opened."""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
import pytest
from PIL import Image
from experiments.ppal.progress_evidence import CaptureEvidence,DurableRows
from experiments.ppal.progress_supervision import ObservationFailure
from memory.evidence import EvidenceJournal
from memory.episode_identity import (finalize_capture,inspect_capture,IdentityIntegrityError,
                                    verify_recording_completion)


def hold_writer(recorder):
    entered=threading.Event();release=threading.Event();original=recorder._capture
    def slow(*args):
        entered.set();assert release.wait(3);return original(*args)
    recorder._capture=slow
    return entered,release


def test_predictions_and_logs_do_not_wait_for_encoding_and_freeze_inputs(tmp_path):
    r=CaptureEvidence(tmp_path,'software-session',{});r.ready()
    entered,release=hold_writer(r);frame=Image.new('RGB',(80,60),'red')
    metadata=dict(timestamp=time.monotonic(),capture={'exposure':42})
    observation=r.capture(frame,metadata);assert entered.wait(1)
    frame.paste('blue',(0,0,80,60));metadata['capture']['exposure']=99
    p=r.event('tactical_prediction',dict(question='does E move?',action={'move':'E'}),at=time.monotonic())
    rows=DurableRows(tmp_path/'steps.jsonl');rows.recorder=r;row={'prediction_id':p,'move':'E'}
    rows.append(row);row['move']='W'
    assert not (tmp_path/'steps.jsonl').exists() # writer still held; enqueue returned
    assert r.telemetry()['occupancy']==3
    release.set();r.close()
    j=EvidenceJournal(tmp_path/'session-evidence.sqlite3',read_only=True)
    assert j.get(p).data['sources']==[observation]
    assert j.get(observation).data['payload']['metadata']['capture']['exposure']==42
    assert j.get(p).data['payload']['mode']=='buffered_live_prospective'
    assert j.get(p).data['at']>=j.get(observation).data['at']
    assert Image.open(tmp_path/'observations/camera-000001.png').getpixel((0,0))==(255,0,0)
    assert json.loads((tmp_path/'steps.jsonl').read_text())['move']=='E'
    j.verify();j.close();verify_recording_completion(tmp_path)


def test_encoding_and_file_sync_execute_on_writer_thread(tmp_path,monkeypatch):
    r=CaptureEvidence(tmp_path,'simulation',{});r.ready();calls=[]
    original_save=Image.Image.save;original_sync=os.fsync
    def save(*args,**kwargs):
        calls.append(('encode',threading.current_thread().name));return original_save(*args,**kwargs)
    def sync(*args):
        calls.append(('sync',threading.current_thread().name));return original_sync(*args)
    monkeypatch.setattr(Image.Image,'save',save);monkeypatch.setattr(os,'fsync',sync)
    r.capture(Image.new('RGB',(80,60)),dict(timestamp=time.monotonic()))
    r.append_line(tmp_path/'agency.jsonl',{'observed':True});r.flush()
    assert calls and all(name=='camera-evidence' for _,name in calls)
    r.close()


def test_burst_full_queue_pauses_and_retains_emergency_frame(tmp_path):
    r=CaptureEvidence(tmp_path,'simulation',{},capacity=2,record_capacity=4);r.ready()
    entered,release=hold_writer(r)
    try:
        for n in range(2):r.capture(Image.new('RGB',(80,60),(n,0,0)),dict(timestamp=time.monotonic()))
        assert entered.wait(1)
        with pytest.raises(ObservationFailure,match='saturated'):
            r.capture(Image.new('RGB',(80,60),(2,0,0)),dict(timestamp=time.monotonic()))
        t=r.telemetry();assert t['occupancy']==2 and t['frame_occupancy']==2 and t['backpressure']==1 and t['paused']
        with pytest.raises(RuntimeError,match='paused'):r.event('execution',{},at=time.monotonic())
    finally:release.set();r.close()
    assert len(list((tmp_path/'observations').glob('*.png')))==3
    assert r.telemetry()['accepted']==r.telemetry()['written']==3
    verify_recording_completion(tmp_path)


def test_memory_and_record_budgets_are_independent(tmp_path):
    r=CaptureEvidence(tmp_path,'simulation',{},capacity=10,record_capacity=10,byte_capacity=12000);r.ready()
    entered,release=hold_writer(r)
    try:
        r.capture(Image.new('RGB',(40,40)),dict(timestamp=time.monotonic()));assert entered.wait(1)
        r.capture(Image.new('RGB',(40,40)),dict(timestamp=time.monotonic()))
        with pytest.raises(ObservationFailure):r.capture(Image.new('RGB',(40,40)),dict(timestamp=time.monotonic()))
        assert 9600<r.telemetry()['buffered_bytes']<=12000
    finally:release.set();r.close()


def test_writer_failure_blocks_sealing_and_retains_gap(tmp_path):
    r=CaptureEvidence(tmp_path,'simulation',{});r.ready()
    def broken(*args):raise OSError('simulated full storage')
    r._capture=broken;r.capture(Image.new('RGB',(40,40)),dict(timestamp=time.monotonic()))
    with pytest.raises(OSError,match='full storage'):r.close()
    state=json.loads((tmp_path/'recording-state.json').read_text())
    assert state['status']=='incomplete' and state['uncommitted_records']==1
    assert state['uncommitted_ids']
    (tmp_path/'report.json').write_text('{}')
    with pytest.raises(IdentityIntegrityError,match='incomplete'):finalize_capture(tmp_path)
    assert not (tmp_path/'capture-manifest.json').exists()


def test_flush_timeout_cannot_become_completion_when_writer_later_finishes(tmp_path):
    r=CaptureEvidence(tmp_path,'simulation',{},flush_timeout=.05);r.ready()
    entered,release=hold_writer(r);r.capture(Image.new('RGB',(40,40)),dict(timestamp=time.monotonic()))
    assert entered.wait(1)
    try:
        with pytest.raises(TimeoutError):r.close()
    finally:release.set();r.thread.join(timeout=1)
    assert json.loads((tmp_path/'recording-state.json').read_text())['status']=='incomplete'
    with pytest.raises(IdentityIntegrityError):verify_recording_completion(tmp_path)


def test_process_death_preserves_completed_records_and_reports_unknown_tail(tmp_path):
    script='''
import os,sys,time,threading
from pathlib import Path
from PIL import Image
from experiments.ppal.progress_evidence import CaptureEvidence
r=CaptureEvidence(Path(sys.argv[1]),'simulation',{})
r.capture(Image.new('RGB',(40,40)),dict(timestamp=time.monotonic()));r.ready()
r._capture=lambda *args:threading.Event().wait(100)
r.capture(Image.new('RGB',(40,40),'red'),dict(timestamp=time.monotonic()))
os._exit(23)
'''
    env=dict(os.environ);env['PYTHONPATH']=str(Path.cwd())+os.pathsep+env.get('PYTHONPATH','')
    run=subprocess.run([sys.executable,'-c',script,str(tmp_path)],env=env,timeout=5)
    assert run.returncode==23
    j=EvidenceJournal(tmp_path/'session-evidence.sqlite3',read_only=True);before=[r.id for r in j.records()];j.close()
    assert (tmp_path/'observations/camera-000001.png').exists()
    r=CaptureEvidence(tmp_path,'simulation',{});assert r.recovery['interrupted_flush'];r.close()
    state=json.loads((tmp_path/'recording-state.json').read_text())
    assert state['status']=='incomplete' and state['telemetry']['recovery']['uncommitted_tail']=='unknown after process death'
    j=EvidenceJournal(tmp_path/'session-evidence.sqlite3',read_only=True);assert [r.id for r in j.records()]==before;j.close()
    with pytest.raises(IdentityIntegrityError):verify_recording_completion(tmp_path)


def test_completion_restart_and_manifest_are_immutable_and_verified(tmp_path):
    r=CaptureEvidence(tmp_path,'simulation',{});r.capture(Image.new('RGB',(40,40)),dict(timestamp=time.monotonic()));r.close()
    (tmp_path/'report.json').write_text('{}');manifest=finalize_capture(tmp_path)
    original={p.name:p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    r=CaptureEvidence(tmp_path,'simulation',{});r.close()
    assert all((tmp_path/name).read_bytes()==data for name,data in original.items())
    assert inspect_capture(tmp_path)['manifest_id']==manifest['manifest_id']
    (tmp_path/'observations/camera-000001.png').write_bytes(b'corrupt')
    with pytest.raises(IdentityIntegrityError):inspect_capture(tmp_path)


def test_prediction_cannot_follow_future_observation_even_if_queued(tmp_path):
    j=EvidenceJournal(tmp_path/'notebook.sqlite3')
    from memory.evidence import PreparedEvidence
    a=j.prepare_observation({},episode='simulation',at=time.monotonic(),producer='test',version='1')
    j.commit_prepared(a)
    at=time.monotonic();p=j.prepare_buffered_prediction({},episode='simulation',at=at,deadline=at+2,sources=[a.id],producer='test',version='1')
    j.append('observation',{},episode='simulation',at=at+.01,producer='test',version='1')
    with pytest.raises(ValueError,match='later observation'):j.commit_prepared(p)
    j.close()


def test_missing_completion_marker_cannot_reclassify_new_capture_as_legacy(tmp_path):
    r=CaptureEvidence(tmp_path,'simulation',{});r.capture(Image.new('RGB',(40,40)),dict(timestamp=time.monotonic()));r.close()
    (tmp_path/'recording-state.json').unlink()
    (tmp_path/'report.json').write_text('{}')
    with pytest.raises(IdentityIntegrityError,match='marker missing'):finalize_capture(tmp_path)


def test_required_record_larger_than_budget_is_explicitly_incomplete(tmp_path):
    r=CaptureEvidence(tmp_path,'simulation',{},byte_capacity=100);r.ready()
    with pytest.raises(ValueError,match='memory budget'):r.capture(Image.new('RGB',(40,40)),dict(timestamp=time.monotonic()))
    r.close()
    assert json.loads((tmp_path/'recording-state.json').read_text())['status']=='incomplete'


def test_acknowledged_completion_releases_capacity_before_next_preflight_capture(tmp_path,monkeypatch):
    from concurrent.futures import Future
    r=CaptureEvidence(tmp_path,'simulation',{},capacity=1)
    acknowledged=threading.Event();release=threading.Event();blocked=[False];original=Future.set_result
    def delayed_ack(self,value):
        original(self,value)
        if threading.current_thread().name=='camera-evidence' and not blocked[0]:
            blocked[0]=True;acknowledged.set();assert release.wait(3)
    monkeypatch.setattr(Future,'set_result',delayed_ack)
    try:
        r.capture(Image.new('RGB',(40,40)),dict(timestamp=time.monotonic()))
        assert acknowledged.wait(1)
        # Completion is visible while the worker deliberately stays in the ack.
        # A capacity-one preflight must accept this next frame without spinning,
        # an IndexError, or falsely claiming required evidence was dropped.
        r.capture(Image.new('RGB',(40,40),'red'),dict(timestamp=time.monotonic()))
    finally:release.set();r.close()
    assert r.telemetry()['captures_written']==2 and r.telemetry()['backpressure']==0
