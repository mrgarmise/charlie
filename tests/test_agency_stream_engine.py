"""Host-only deterministic camera/transport fixtures; no physical devices."""
import json
import math
import queue
import threading
import time
from types import SimpleNamespace
import pytest
from PIL import Image
from experiments.ppal.observation_stream import ObservationStream,Exposure
from experiments.ppal.observation_camera import ObservedCamera
from experiments.ppal.gameplay_engine import AgencyScreen,CycleMetrics
from experiments.ppal.shot_capture import capture_window
from experiments.ppal.robotron_agency import VisualAgency,VECTORS
from experiments.ppal.projectile_agency import ShotOrigins
from experiments.ppal.eyes.detectors import Detection
from experiments.ppal.models import Action


def packet(at,sequence=1):
    return Exposure(sequence,Image.new('RGB',(20,20)),dict(first_pixel_exposure_at=at,sensor_timestamp_ns=int(at*1e9)))


def append(stream,at):
    p=packet(at)
    with stream.condition:stream._append(p.image,p.capture)


@pytest.mark.parametrize('bad',[1.,.9,float('nan'),True,None])
def test_duplicate_stale_missing_or_nonmonotonic_metadata_rejected(bad):
    s=ObservationStream(None);append(s,1.)
    p=packet(2.);p.capture['first_pixel_exposure_at']=bad
    with pytest.raises(ValueError):
        with s.condition:s._append(p.image,p.capture)


def test_ordinary_eviction_explicit_critical_window_never_evicted():
    s=ObservationStream(None,capacity=3,byte_capacity=10000)
    for at in (1.,2.,3.,4.):append(s,at)
    assert s.evicted==1 and [p.at for p in s.frames]==[2.,3.,4.]
    assert s.begin_window().at==4.
    append(s,5.);append(s,6.)
    with pytest.raises(BufferError):append(s,7.)
    assert [p.at for p in s.end_window()]==[4.,5.,6.]
    assert s.bytes<=10000


def test_newest_frame_selection_and_no_duplicate_evidence_delivery():
    s=ObservationStream(None)
    for at in (1.,2.,3.):append(s,at)
    observed=ObservedCamera(SimpleNamespace(stream=s))
    observed.stream_sequence=0
    assert observed.read().size==(20,20) and observed.timestamp==3.
    assert observed.stream_skipped==2
    with pytest.raises(ValueError):observed.accept_exposure(s.frames[-1])
    with pytest.raises(TimeoutError):s.latest(after=3,timeout=.001)


def test_capture_includes_before_during_and_after_synchronous_execute():
    q=queue.Queue();thread_ids=set();stream=None
    def acquire():
        thread_ids.add(threading.get_ident())
        while not stream.stop_event.is_set():
            try:return q.get(timeout=.02)
            except queue.Empty:pass
        raise OSError('fixture stopped')
    stream=ObservationStream(acquire)
    def emit():
        at=time.monotonic();p=packet(at);q.put((p.image,p.capture))
        return stream.latest(after=stream.sequence,timeout=.5)
    stream.start()
    try:
        emit();source=SimpleNamespace(stream=stream)
        class Controller:
            closed=False
            def close(self):self.closed=True
            def execute(self,a,ms,**kwargs):
                self.last_execution=dict(move=a.move,fire=a.fire,started_at=time.monotonic(),controls_ready_at=time.monotonic())
                emit();emit()
                self.last_execution['pulse_finished_at']=time.monotonic()
                emit()
                self.last_execution['release_completed_at']=time.monotonic()
                # A later independent exposure closes the declared interval;
                # it is ordinary history rather than protected evidence.
                timer=threading.Timer(.03,emit);timer.daemon=True;timer.start()
        c=Controller()
        execution,frames,status=capture_window(source,c,Action('STAY','E'),60,post_seconds=.01)
        assert any(p.at<status['submitted_at'] for p in frames)
        assert sum(execution['controls_ready_at']<p.at<execution['pulse_finished_at'] for p in frames)==2
        assert any(p.at>execution['pulse_finished_at'] for p in frames)
        assert len(frames)==4 and not c.closed and len(thread_ids)==1
        assert thread_ids!={threading.get_ident()}
        frames.close(replayed=True)
    finally:stream.close()
    assert not stream.thread.is_alive()


def test_cancelled_or_overbudget_shot_sends_nothing():
    class C:
        def execute(self,*a,**kw):raise AssertionError('no authority to send')
    with pytest.raises(InterruptedError):capture_window(None,C(),Action('STAY','E'),400,deadline=time.monotonic()+.1)
    with pytest.raises(InterruptedError):capture_window(None,C(),Action('STAY','E'),60,should_stop=lambda:True)
    with pytest.raises(ValueError):capture_window(None,C(),Action('STAY','E'),501)


def test_failure_cancels_and_closes_controller():
    s=ObservationStream(None);append(s,time.monotonic())
    class C:
        closed=False
        def execute(self,*a,**kw):raise OSError('transport fixture failed')
        def close(self):self.closed=True
    c=C()
    with pytest.raises(OSError):capture_window(SimpleNamespace(stream=s),c,Action('STAY','E'),60)
    assert c.closed and s.pin is None


def test_post_release_sample_extends_path_born_during_fire():
    m=ShotOrigins()
    m.begin((1,0),dict(move='STAY',fire='E',controls_ready_at=1.,pulse_finished_at=1.15),{7:(50,50)},[])
    assert m.observe([], .99)==[] # a genuine pre-command baseline does not kill the window
    assert m.observe([(51,50)],1.1)==[]
    assert m.observe([(52,50)],1.2)==[]
    votes=m.observe([(53,50)],1.3)
    assert len(votes)==1 and votes[0]['emission_at']==pytest.approx(1.)
    assert m.observe([(54,50)],1.3)==[] and m.window is None


def test_terminal_templates_absent_with_supported_self_but_investigate_loss_change():
    calls=[];supported=[True]
    def full(frame):calls.append(True);return dict(state='gameplay',phase='gameplay')
    screen=AgencyScreen(full,lambda:supported[0]);screen.active=True
    dark=Image.new('RGB',(100,100));bright=Image.new('RGB',(100,100),'white')
    screen(dark)
    for _ in range(10):assert screen(dark)['restart_permission'] is False
    assert len(calls)==1
    supported[0]=False;screen(dark);assert len(calls)==2
    supported[0]=True;screen(bright);assert len(calls)==3


def test_start_ack_alone_and_attract_cannot_seed_expected_self():
    v=VisualAgency();receipt=dict(command='START',accepted=True,ack_at=1.)
    assert not v.seed_new_game(receipt,[])
    assert not v.seed_new_game(receipt,[dict(phase='title',capture_timestamp=t) for t in (2.,3.,4.)])
    assert not v.seed_new_game(receipt,[dict(phase='gameplay',capture_timestamp=2.)]*3)
    assert v.expected_self is None and v.player is None
    assert v.seed_new_game(receipt,[dict(phase='gameplay',capture_timestamp=t) for t in (2.,3.,4.)])
    assert v.expected_self['status']=='expected' and v.agency.self_id is None
    pairs=[(Detection('unknown',p,(1,1,10,20),100),{}) for p in ((10,10),(50,50))]
    row=v.observe(pairs,observed_at=5.)
    assert row['expected_self']['status']=='provisional'
    assert v.positions[row['candidate_track_id']]==(50,50) and v.player is None


def test_brief_occlusion_retains_identity_without_predicted_position_control():
    v=VisualAgency();clock=[1.];p=[20.,20.]
    def read():clock[0]+=.01;return [(Detection('unknown',tuple(p),(1,1,10,20),100),{})]
    class C:
        last_execution=None
        def execute(self,a,ms):
            u=VECTORS[a.move];p[0]+=u[0];p[1]+=u[1]
    v.discover(read,C(),observation_time=lambda:clock[0],fire_first=False)
    key=v.agency.self_id;assert key is not None
    v.observe([],observed_at=clock[0]+.05)
    assert v.brief_occlusion(clock[0]+.05) and v.player is None
    assert not v.brief_occlusion(clock[0]+.5)
    row=v.observe(read(),observed_at=clock[0]+.1)
    assert row['self_track_id']==key
    assert not v.confirmed_respawn(death_confirmed=False,respawn_confirmed=True)


def test_integer_weight_repair_survives_durable_journal_commit(tmp_path):
    from experiments.ppal.progress_evidence import CaptureEvidence
    from memory.evidence import EvidenceJournal
    v=VisualAgency();row=v.observe([(Detection('unknown',(50,50),(1,1,10,20),100),{})],observed_at=1.)
    assert all(isinstance(k,str) for k in row['spawn_prior']['weights'])
    r=CaptureEvidence(tmp_path,'host-serialization-fixture',{})
    r.capture(Image.new('RGB',(20,20)),dict(timestamp=1.))
    r.event('perception_trace',row,at=1.);r.close()
    j=EvidenceJournal(tmp_path/'session-evidence.sqlite3',read_only=True)
    j.verify();records=j.category_records('observation','perception_trace')
    assert records and records[0].data['payload']['spawn_prior']['weights']
    j.close()


def test_meaningful_updates_require_fresh_supported_decisions(monkeypatch):
    clock=[10.];monkeypatch.setattr(time,'monotonic',lambda:clock[0]);m=CycleMetrics()
    assert not m.decision('a',9.,supported=False)
    assert m.decision('a',9.9,supported=True,track_id=1)
    assert not m.decision('a',9.9,supported=True,track_id=1)
    clock[0]=10.1;assert m.decision('b',10.,supported=True,track_id=1)
    r=m.report();assert r['meaningful_updates']==2 and r['sustained_hz']==pytest.approx(10.)
    assert r['controller_visual_feedback_seconds']['samples']==0


def test_batched_template_scores_preserve_existing_classifier():
    import numpy as np
    from experiments.ppal.eyes.taught_recognizer import TaughtRecognizer
    from experiments.ppal.eyes.sprites import regions
    from pathlib import Path
    from PIL import ImageDraw
    r=TaughtRecognizer.load(Path('config/robotron/sprite-knowledge.json'))
    f=Image.new('RGB',(640,480));d=ImageDraw.Draw(f)
    d.rectangle((50,50,65,75),fill='white');d.rectangle((100,80,112,103),fill='red')
    expected=[r.classify_patch(patch) for _,_,patch in regions(f)]
    actual=r.detect(f)
    assert len(actual)==len(expected)>0
    for (_,a),e in zip(actual,expected):
        assert a['identity']==e[0] and a['score']==pytest.approx(e[1],abs=1e-5)
        assert a['class_scores']==pytest.approx(e[3],abs=1e-5)


def test_two_direction_buffer_replay_completes_existing_shot_handoff():
    v=VisualAgency(projectile_confirmation=True);clock=[1.];rows=[];seq=[0];calls=[]
    def read():return [(Detection('unknown',(50,50),(1,1,10,20),100),{})]
    def accept(p):
        clock[0]=p.at
        accept.projectiles=p.capture['dots']
        return read()
    read.accept_exposure=accept
    def capture(c,a,duration,deadline,stop):
        calls.append(a.fire);start=1.1 if a.fire=='E' else 1.5;u=VECTORS[a.fire]
        frames=[]
        for at,dist in ((start-.05,None),(start+.05,1),(start+.1,2),(start+.15,3)):
            seq[0]+=1;p=packet(at,seq[0]);p.capture['dots']=[] if dist is None else [(50+u[0]*dist,50+u[1]*dist)]
            frames.append(p)
        return dict(move='STAY',fire=a.fire,controls_ready_at=start,pulse_finished_at=start+.1),frames,{'fixture':'synthetic buffer'}
    v.discover(read,object(),capture_shots=capture,observation_time=lambda:clock[0],record=rows.append)
    assert calls==['E','N'] and v.player==(50,50)
    assert rows[-1]['identity_status']=='confirmed' and len(rows[-1]['projectile_support'])==2
    # Established identity does not repeat exploratory firing.
    clock[0]+=.2
    v.discover(read,object(),capture_shots=lambda *a:pytest.fail('unnecessary repeated FIRE'),observation_time=lambda:clock[0])


def test_pre_ack_and_post_release_transport_bounds_do_not_claim_display_onset():
    m=ShotOrigins()
    execution=dict(move='STAY',fire='E',fire_on_submitted_at=1.,controls_ready_at=1.1,
                   pulse_finished_at=1.16,fire_off_ack_at=1.3)
    assert m.begin((1,0),execution,{7:(50,50)},[])
    assert m.window['start']==1. and m.window['end']==1.3
    for at,p in [(1.05,(51,50)),(1.1,(52,50)),(1.15,(53,50))]:votes=m.observe([p],at)
    assert votes and votes[0]['emission_at']==pytest.approx(1.)


def test_one_producer_is_reused_across_three_episode_borrowers():
    from experiments.ppal.camera_session import CameraSession
    owners=[];closed=[]
    class Camera:
        def __init__(self):self.stream=None;owners.append(self)
        def start_stream(self):
            if self.stream is None:
                def acquire():
                    self.stream.stop_event.wait(.005)
                    p=packet(time.monotonic());return p.image,p.capture
                self.stream=ObservationStream(acquire)
                self.stream.start()
            return self.stream
        def close(self):self.stream.close();closed.append(True)
    session=CameraSession(Camera);sequences=[]
    try:
        for _ in range(3):
            observed=ObservedCamera(session.borrow());observed.start_stream();observed.read()
            sequences.append(observed.stream_sequence);observed.close()
            assert not closed
    finally:session.close()
    assert len(owners)==1 and closed==[True] and all(b>a for a,b in zip(sequences,sequences[1:]))
    assert not owners[0].stream.thread.is_alive()


def test_camera_failure_signals_active_transport_cancellation_and_joins():
    s=ObservationStream(lambda:(_ for _ in ()).throw(OSError('fixture disconnected'))).start()
    assert s.failed.wait(.5)
    with pytest.raises(RuntimeError):s.latest(timeout=.01)
    s.close();assert not s.thread.is_alive()


def test_transport_cancellation_keeps_existing_lease_and_neutralizes_without_socket():
    from experiments.ppal.arcade_transport import ArcadeController
    from experiments.ppal.controller_sandbox import ControllerSandbox
    c=object.__new__(ArcadeController);c.closed=False;c.protocol='positions';c.pulse=True
    c.positions=('LS_CENTER','RS_CENTER');c.sandbox=ControllerSandbox();calls=[]
    c._command=lambda command:calls.append(command)
    c.close=lambda:calls.append('NEUTRAL')
    event=threading.Event();event.set()
    with pytest.raises(InterruptedError):c.execute(Action('STAY','E'),60,cancel_event=event)
    assert calls==['NEUTRAL']


def test_ordinary_preparation_overlaps_transport_on_main_thread():
    from experiments.ppal.controller_overlap import execute_with_lookahead
    ready=threading.Event();prepared=threading.Event();threads=[]
    p=packet(time.monotonic())
    class C:
        def execute(self,*a,**kw):
            threads.append(threading.get_ident());ready.set()
            assert prepared.wait(.5)
        def close(self):pass
    class Stream:
        failed=threading.Event()
        def latest(self,**kw):
            assert ready.wait(.5)
            return p
    def prepare(packet):
        threads.append(threading.get_ident());prepared.set();return packet
    assert execute_with_lookahead(C(),Action('E','N'),80,Stream(),0,prepare)==p
    assert threads[0]!=threads[1] and threads[1]==threading.get_ident()
    assert not any(t.name=='charlie-bounded-controller' and t.is_alive() for t in threading.enumerate())
