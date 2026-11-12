"""77.36 fps / 1280x720 / 64 MiB regression; synthetic pixels, real transport logic."""
import hashlib
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace

from PIL import Image
import pytest

from experiments.ppal.arcade_transport import ArcadeController
from experiments.ppal.models import Action
from experiments.ppal.observation_stream import ObservationStream
from experiments.ppal.progress_supervision import Progress, SupervisedController
from experiments.ppal.shot_capture import capture_window, CapturedFrames

FIXTURE=Path(__file__).parent/'fixtures/native-causal-overflow-20261024'
FPS=77.36277629689837
SIZE=(1280,720)


def report():return json.loads((FIXTURE/'report.json').read_text())


def test_authentic_report_and_capacity_reproduce_exact_655_frame_failure():
    provenance=json.loads((FIXTURE/'provenance.json').read_text())
    assert hashlib.sha256((FIXTURE/'report.json').read_bytes()).hexdigest()==provenance['files']['report.json']
    original=report();observed=original['performance']['stream']
    assert observed['error']=='critical capture window overflow; no frames silently discarded'
    assert observed['acquired']==655 and observed['producer_hz']==pytest.approx(FPS)
    assert original['ticks']==0 and original['sensory_preflight']['status']=='usable'
    assert provenance['example_original_frame']['size']==list(SIZE)
    stream=ObservationStream(None)
    image=Image.new('RGB',SIZE)
    def append(sequence):
        with stream.condition:
            stream._append(image,dict(first_pixel_exposure_at=sequence/FPS,sensor_timestamp_ns=int(sequence/FPS*1e9)))
    for sequence in range(1,638):append(sequence)
    stream.begin_window()
    for sequence in range(638,655):append(sequence)
    with pytest.raises(BufferError,match='critical capture window overflow'):append(655)
    replay=stream.stats()
    for key in ('acquired','ordinary_history_evictions','retained','retained_bytes','maximum_bytes','byte_capacity'):
        assert replay[key]==observed[key]
    assert 18/(FPS)<.060+.250
    assert [p.sequence for p in stream.end_window()]==list(range(637,655))


@pytest.fixture
def rig(tmp_path,monkeypatch):
    counter=[0];stream=None;next_at=[time.monotonic()+1/FPS]
    def acquire():
        # Real pacing with independent monotonic exposure identities, not a
        # scheduler-dependent burst into a tiny queue.
        if stream.stop_event.wait(max(0.,next_at[0]-time.monotonic())):raise OSError('fixture owner stopped')
        next_at[0]+=1/FPS
        counter[0]+=1;at=time.monotonic()
        image=Image.new('RGB',SIZE,(counter[0]%251,17,31))
        return image,dict(first_pixel_exposure_at=at,sensor_timestamp_ns=int(at*1e9),
                          synthetic_sequence=counter[0],frame_duration_us=1e6/FPS)
    stream=ObservationStream(acquire)
    stream.start()
    stream.latest(timeout=1)
    class Wire:
        commands=[]
        closed=False
        def write(self,wire):self.commands.append(wire.decode().strip())
        def readline(self,size):return b'OK\n'
        def close(self):self.closed=True
    wire=Wire()
    connection=SimpleNamespace(settimeout=lambda _:None,makefile=lambda *a,**kw:wire,
        close=lambda:setattr(wire,'closed',True),shutdown=lambda *a:None)
    monkeypatch.setattr('experiments.ppal.arcade_transport.socket.create_connection',lambda *a,**kw:connection)
    transport=ArcadeController('synthetic',require_lease=True)
    progress=Progress(tmp_path/'progress.json')
    controller=SupervisedController(transport,progress)
    source=SimpleNamespace(stream=stream,recorder=SimpleNamespace(output=tmp_path))
    yield SimpleNamespace(source=source,stream=stream,controller=controller,transport=transport,
                          wire=wire,output=tmp_path,progress=progress)
    controller.close();stream.close()
    assert not stream.thread.is_alive()
    assert not any(t.name=='charlie-causal-controller' and t.is_alive() for t in threading.enumerate())


def manifest(rig):
    paths=list(rig.output.glob('causal-windows/*/manifest.json'))
    assert len(paths)==1
    return json.loads(paths[0].read_text())


@pytest.mark.parametrize('duration',[60,400])
def test_full_interval_exceeds_ring_capacity_but_all_originals_survive(rig,duration):
    execution,frames,status=capture_window(rig.source,rig.controller,Action('STAY','E'),duration)
    assert len(frames)>18
    sequences=[p.sequence for p in frames]
    assert sequences==list(range(sequences[0],sequences[-1]+1))
    times=[p.at for p in frames]
    assert all(b>a for a,b in zip(times,times[1:]))
    assert times[0]<execution['fire_on_submitted_at']
    assert any(execution['controls_ready_at']<at<execution['pulse_finished_at'] for at in times)
    assert sum(at>execution['fire_off_ack_at'] for at in times)>=3
    assert status['post_seconds']==.25 and times[-1]<=status['end_exposure_at']
    for packet in frames:
        image=packet.image
        assert image.size==SIZE and image.mode=='RGB'
        assert image.getpixel((0,0))==(packet.capture['synthetic_sequence']%251,17,31)
        image.close()
    stats=rig.stream.stats()
    assert stats['byte_capacity']==64*1024*1024 and stats['maximum_bytes']<=stats['byte_capacity']
    assert stats['retained']<=18 and not stats['failed'] and rig.stream.pin is None
    assert stats['protected_drained']==len(frames)
    assert rig.wire.commands[:2]==['NEUTRAL','LEASE'] and 'LEASE' in rig.wire.commands[2:]
    assert rig.transport.positions==('LS_CENTER','RS_CENTER') and not rig.transport.closed
    assert rig.stream.thread.is_alive() and not rig.progress.data.get('failure_kind')
    frames.close(replayed=True)
    saved=manifest(rig)
    assert saved['status']=='capture_complete' and saved['replay']=='consumed'
    assert len(saved['frames'])==len(frames) and saved['accounted_bytes']<=saved['max_bytes']


def test_slow_consumer_does_not_extend_protection_into_replay_or_future_history(rig,monkeypatch):
    original=CapturedFrames.append
    def slow(self,packet):
        time.sleep(.025)  # Below camera FPS; ring absorbs finite pulse backlog.
        return original(self,packet)
    monkeypatch.setattr(CapturedFrames,'append',slow)
    execution,frames,status=capture_window(rig.source,rig.controller,Action('STAY','E'),60)
    assert status['completed_at']>status['end_exposure_at']+.05
    assert frames[-1].at<=status['end_exposure_at']
    assert [p.sequence for p in frames]==list(range(frames[0].sequence,frames[-1].sequence+1))
    before=rig.stream.sequence
    time.sleep(.1)
    assert rig.stream.sequence>before and rig.stream.thread.is_alive() and rig.stream.pin is None
    # Slow causal analysis loads an unchanged disk original while ordinary
    # acquisition/eviction continues; no full-image replay list is retained.
    old=frames[0].image
    assert hashlib.sha256(old.tobytes()).hexdigest()==frames[0].rgb_sha256
    old.close();frames.close(replayed=True)
    assert rig.stream.stats()['maximum_bytes']<=64*1024*1024


def test_cancellation_neutralizes_unpins_and_preserves_received_originals(rig):
    cancel=threading.Event();timer=threading.Timer(.04,cancel.set);timer.start()
    try:
        with pytest.raises(InterruptedError):
            capture_window(rig.source,rig.controller,Action('STAY','E'),400,should_stop=cancel.is_set)
    finally:timer.join()
    saved=manifest(rig)
    assert saved['status']=='invalid' and saved['error_type']=='InterruptedError'
    assert saved['frames'] and not saved['worker_alive']
    assert rig.stream.pin is None and rig.transport.closed
    assert rig.wire.commands[-1]=='NEUTRAL' and rig.transport.positions==('LS_CENTER','RS_CENTER')
    assert rig.stream.thread.is_alive() and not rig.stream.failed.is_set()
    for row in saved['frames']:
        assert (next(rig.output.glob('causal-windows/*'))/row['path']).is_file()


def test_finite_archive_exhaustion_is_explicit_and_fails_closed(rig):
    with pytest.raises(BufferError,match='archive budget exhausted'):
        capture_window(rig.source,rig.controller,Action('STAY','E'),400,max_frames=3)
    saved=manifest(rig)
    assert saved['status']=='invalid' and len(saved['frames'])==3
    assert saved['recovery_error'] and saved['unarchived_sequences']
    assert rig.stream.pin is None and rig.transport.closed and rig.wire.commands[-1]=='NEUTRAL'
    assert saved['accounted_bytes']<=saved['max_bytes'] and not saved['worker_alive']


def test_stalled_handoff_preserves_original_buffer_overflow_and_stops_probe(rig,monkeypatch):
    original=CapturedFrames.append
    def stalled(self,packet):
        time.sleep(.35)  # More than the authentic ring's 18/77.36 seconds.
        return original(self,packet)
    monkeypatch.setattr(CapturedFrames,'append',stalled)
    with pytest.raises(RuntimeError,match='causal capture failed'):
        capture_window(rig.source,rig.controller,Action('STAY','E'),60)
    saved=manifest(rig)
    assert saved['stream']['error_type']=='BufferError'
    assert 'critical capture window overflow' in saved['stream']['error']
    assert 'BufferError' in saved['stream']['error_traceback']
    assert saved['stream']['last_capture']['sensor_timestamp_ns']>0
    assert rig.stream.pin is None and saved['frames'] and not saved['worker_alive']
    assert rig.transport.closed and rig.wire.commands[-1]=='NEUTRAL'


def test_disk_writer_failure_preserves_type_and_stops_the_probe(rig,monkeypatch):
    original=CapturedFrames._write;calls=[0]
    def failing(self,data):
        calls[0]+=1
        if calls[0]==2:
            original(self,data[:8])
            raise OSError('injected protected evidence disk failure')
        return original(self,data)
    monkeypatch.setattr(CapturedFrames,'_write',failing)
    with pytest.raises(OSError,match='protected evidence disk failure'):
        capture_window(rig.source,rig.controller,Action('STAY','E'),400)
    saved=manifest(rig)
    assert saved['status']=='invalid' and saved['error_type']=='OSError'
    assert not saved['worker_alive'] and rig.stream.pin is None
    assert rig.transport.closed and rig.wire.commands[-1]=='NEUTRAL'


def test_archive_pixel_integrity_checked_before_causal_replay(rig):
    _,frames,_=capture_window(rig.source,rig.controller,Action('STAY','E'),60)
    # Corrupt only a synthetic test artifact; authentic fixtures are read-only.
    with frames[-1].path.open('r+b') as target:
        target.seek(frames[-1].offset);target.write(b'bad')
    with pytest.raises(ValueError,match='pixels changed'):frames[-1].image
    frames.close()


@pytest.mark.parametrize('fault',['capture_timeout','stale_metadata'])
def test_originating_camera_fault_and_last_capture_survive_cleanup(rig,fault):
    original=rig.stream.acquire;calls=[0]
    def acquire():
        calls[0]+=1
        if calls[0]==5:
            if fault=='capture_timeout':raise OSError('injected native capture timeout')
            image,capture=original();capture['sensor_timestamp_ns']=1
            return image,capture
        return original()
    rig.stream.acquire=acquire
    with pytest.raises((RuntimeError,InterruptedError)):
        capture_window(rig.source,rig.controller,Action('STAY','E'),400)
    saved=manifest(rig)
    assert saved['status']=='invalid' and saved['frames']
    expected='OSError' if fault=='capture_timeout' else 'ValueError'
    assert saved['stream']['error_type']==expected
    assert expected in saved['stream']['error_traceback']
    assert saved['stream']['last_capture']['sensor_timestamp_ns']>1
    assert not saved['worker_alive'] and rig.stream.pin is None
    assert rig.transport.closed and rig.wire.commands[-1]=='NEUTRAL'


def test_insufficient_archive_admission_never_submits_action(rig):
    with pytest.raises(BufferError,match='baseline exceeds'):
        capture_window(rig.source,rig.controller,Action('STAY','E'),60,max_bytes=1024)
    assert rig.wire.commands==['NEUTRAL','LEASE','NEUTRAL']
    assert rig.stream.pin is None and manifest(rig)['status']=='invalid'


@pytest.mark.parametrize('replay_failure',[False,True])
def test_actual_self_discovery_replays_lazy_originals_and_closes_archive(rig,replay_failure):
    from experiments.ppal.robotron_agency import VisualAgency
    from experiments.ppal.observation_camera import ObservedCamera
    observed=ObservedCamera(SimpleNamespace(stream=rig.stream))
    captured=[];delivered=[];rows=[];v=VisualAgency();initial=[0]
    def read():
        observed.read();initial[0]=observed.stream_sequence
        return []
    def accept(packet):
        if packet.sequence<=observed.stream_sequence:return None
        delivered.append(packet.sequence)
        image=observed.accept_exposure(packet)
        assert hashlib.sha256(image.tobytes()).hexdigest()==packet.rgb_sha256
        image.close()
        if replay_failure:raise ValueError('injected causal analysis failure')
        return []
    read.accept_exposure=accept
    def capture(controller,action,duration,deadline,stop):
        result=capture_window(rig.source,controller,action,duration,deadline,stop)
        captured.append(result);return result
    def discover():
        return v.discover(read,rig.controller,capture_shots=capture,record=rows.append,
                          deadline=time.monotonic()+5,should_stop=lambda:bool(captured),
                          observation_time=lambda:observed.timestamp)
    if replay_failure:
        with pytest.raises(ValueError,match='causal analysis failure'):discover()
    else:
        discover()
        assert delivered==[p.sequence for p in captured[0][1] if p.sequence>initial[0]]
        assert len([r for r in rows if r.get('phase')=='shot_origin_experiment'])==len(delivered)
        assert v.agency.self_id is None  # Collection is not fabricated SELF acceptance.
    assert captured[0][1].closed and captured[0][1].file.closed
    assert manifest(rig)['replay']==('incomplete_or_not_requested' if replay_failure else 'consumed')
    assert rig.stream.pin is None and rig.transport.positions==('LS_CENTER','RS_CENTER')
