import json
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter
from experiments.ppal.eyes.active_vision import (
    ActiveVision, Config, State, discover, DegradationGate, apply_validated_view)
from experiments.ppal.eyes.camera_lease import CameraLease


from experiments.ppal.eyes.simulate_active_vision import SimulatedHead as Controller, SimulatedCamera as Source


def make(tmp_path, **kwargs):
    c = Controller()
    s = Source(c)
    av = ActiveVision(lambda:s,c,tmp_path/'run',initial_pose=c.pose,
        simulated=True,wait=lambda _:None,config=Config(experiments=16),**kwargs)
    return av,c,s


def test_independent_experiments_lock_release_and_no_overhead(tmp_path):
    av,c,s = make(tmp_path)
    result = av.run()
    observed = [e['quality'] for e in av.events if e['decision']=='observe target']
    assert result['state']=='LOCKED'
    assert max(observed)>observed[0]+.02
    assert any(e['decision']=='retain measured improvement' for e in av.events)
    assert any(e['decision']=='reject experiment' for e in av.events)
    assert s.closed and av.source is None
    assert c.stops >= 3
    before = s.reads,len(c.moves)
    primary=Source(c)
    from experiments.ppal.eyes.calibration import Calibration
    geometry=result['calibration']
    calibration=Calibration(tuple(tuple(p) for p in geometry['corners']),tuple(geometry['output_size']))
    for tick in range(20):
        frame=primary.read()
        ImageDraw.Draw(frame).ellipse((130+tick,130,140+tick,140),fill='red')
        assert calibration.apply(frame).size==(640,480)
    assert primary.reads==20
    primary.close()
    assert before==(s.reads,len(c.moves))
    assert json.loads((tmp_path/'run/view.json').read_text())['simulated']
    assert list((tmp_path/'run').glob('raw_*.png'))
    assert list((tmp_path/'run').glob('corrected_*.png'))
    with pytest.raises(RuntimeError):av.run()


def test_authorization_before_open(tmp_path):
    av,c,s=make(tmp_path)
    av.simulated=False
    with pytest.raises(PermissionError):av.run()
    assert not (tmp_path/'run').exists() and not c.moves


def test_failure_release(tmp_path):
    av,c,s=make(tmp_path,detector=lambda _: (_ for _ in ()).throw(ValueError('no target')))
    av.cfg=Config(acquisition_moves=2)
    with pytest.raises(ValueError):av.run()
    assert av.state==State.FAILED and s.closed and c.stops>=2
    assert not (tmp_path/'run/view.json').exists()


def test_disconnection(tmp_path):
    av,c,s=make(tmp_path)
    original=s.read_fresh
    def disconnect():
        frame=original();c.connected=False;return frame
    s.read_fresh=disconnect
    with pytest.raises(ConnectionError):av.run()
    assert s.closed and av.state==State.FAILED


def test_interrupt(tmp_path):
    av,c,s=make(tmp_path)
    av.wait=lambda _:av.interrupt()
    with pytest.raises(InterruptedError):av.run()
    assert s.closed and av.state==State.STOPPED


def test_lease_released_for_primary(tmp_path):
    c=Controller();s=Source(c,tmp_path)
    av=ActiveVision(lambda:s,c,tmp_path/'evidence',initial_pose=c.pose,
        simulated=True,wait=lambda _:None)
    with pytest.raises(RuntimeError):CameraLease(directory=tmp_path)
    av.run()
    primary=CameraLease(directory=tmp_path)
    primary.close()


def test_geometry_not_scene_activity_and_permission_hysteresis():
    reference=np.array([[.2,.2],[.8,.2],[.8,.8],[.2,.8]])
    gate=DegradationGate(persistence=3,severe=5,cooldown=10)
    for t in range(50):
        assert gate.observe(reference,reference,now=t)=='continue'
    for t in range(2):assert gate.observe(reference,reference+.1,now=50+t)=='continue'
    assert gate.observe(reference,reference+.1,now=52)=='request_permission'
    assert gate.observe(reference,reference+.1,now=53,authorized=True)=='reacquire'
    assert gate.observe(reference,None,now=54,expected_transition=True)=='continue'
    for t in range(5):result=gate.observe(reference,None,now=70+t)
    assert result=='suspend_and_request'
    assert gate.observe(reference,None,now=75,authorized=True)=='reacquire'
    assert gate.observe(reference,reference+.1,now=76,authorized=True)=='continue'
    assert gate.observe(reference,reference+.1,now=77,requested=True,authorized=True)=='reacquire'


def test_second_finite_reacquisition(tmp_path):
    av,c,s=make(tmp_path);av.run()
    c.pose=(90,90)
    other=Source(c)
    reacquire=ActiveVision(lambda:other,c,tmp_path/'second',initial_pose=c.pose,
        simulated=True,wait=lambda _:None)
    assert reacquire.run()['state']=='LOCKED' and other.closed


def test_no_simulated_handoff(tmp_path):
    av,c,s=make(tmp_path)
    with pytest.raises(ValueError):apply_validated_view(s,av.run())


def test_rotated_discovery_and_clipping():
    frame=Image.new('RGB',(640,480),'black');d=ImageDraw.Draw(frame)
    d.polygon([(180,50),(570,220),(450,440),(60,270)],outline='white',width=5)
    assert abs(discover(frame).rotation)>15
    with pytest.raises(ValueError):discover(Image.new('RGB',(640,480),'black'))


def test_travel_and_rate_guard(tmp_path):
    with pytest.raises(ValueError):Config(rate=40)
    with pytest.raises(ValueError):Config(tilt_min=0)
    av,c,s=make(tmp_path)
    with pytest.raises(ValueError):av.move((120,90))
    assert not c.moves


def test_physical_gate_rejects_old_firmware_before_camera_open(tmp_path):
    av,c,s=make(tmp_path)
    av.simulated=False;av.authorized=True
    c.viewpoint_status=lambda:None
    with pytest.raises(ConnectionError):av.run()
    assert not c.moves and av.source is None


def test_publisher_released_on_lock(tmp_path):
    class Publisher:
        closed=False
        def submit(self,*args,**kw):pass
        def close(self):self.closed=True
    publisher=Publisher()
    av,c,s=make(tmp_path,publisher_factory=lambda:publisher)
    av.run()
    assert publisher.closed and av.publisher is None


def test_failed_validation_never_hands_off(tmp_path):
    av,c,s=make(tmp_path)
    av.cfg=Config(min_sharpness=1e9)
    with pytest.raises(ValueError,match='validation'):av.run()
    assert s.closed and not (tmp_path/'run/view.json').exists()


def test_unknown_and_duplicate_observations_are_not_camera_motion():
    ref=np.array([[.2,.2],[.8,.2],[.8,.8],[.2,.8]])
    gate=DegradationGate(persistence=3,severe=5)
    for _ in range(100):assert gate.observe(ref,ref+.1,now=1)=='continue'
    assert gate.bad==1
    for t in range(2,6):result=gate.observe(ref,np.full((4,2),np.nan),now=t)
    assert result=='continue' and gate.bad==0
    assert gate.observe(ref,None,now=6)=='suspend_and_request'


def test_camera_close_failure_invalidates_lock(tmp_path):
    av,c,s=make(tmp_path)
    def fail():raise OSError('camera closure failed')
    s.close=fail
    with pytest.raises(OSError):av.run()
    assert av.state==State.FAILED and not (tmp_path/'run/view.json').exists()


def test_existing_evidence_journal_adapter(tmp_path):
    from memory.evidence import EvidenceJournal
    journal=EvidenceJournal(tmp_path/'journal.sqlite3')
    av,c,s=make(tmp_path,journal=journal)
    av.cfg=Config(acquisition_moves=1)
    av.run()
    records=journal.records()
    assert records and all(r.data['producer']=='ActiveVision' for r in records)
    assert all(r.data['payload']['simulated'] for r in records)
    journal.verify();journal.close()


def test_existing_viewer_displays_viewpoint_without_opening_camera(tmp_path):
    import os,time
    from experiments.ppal.eyes.passive import atomic_json
    from experiments.ppal.eyes.passive_viewer import Viewer
    lease=CameraLease(directory=tmp_path)
    atomic_json(tmp_path/'active-vision.json',dict(producer_pid=os.getpid(),
        state='OPTIMIZE',confidence=.9,decision='retain measured improvement',at=time.monotonic()))
    viewer=Viewer(tmp_path,idle=False,camera_factory=lambda:pytest.fail('viewer opened camera'))
    try:
        packet=viewer.frame()
        assert packet['active_vision']['state']=='OPTIMIZE'
        assert packet['active_vision']['current'] and viewer.preview is None
    finally:viewer.close();lease.close()


@pytest.mark.parametrize('optimum', [(72,96),(102,84),(114,102)])
def test_adjustment_is_not_a_hardcoded_successful_pose(tmp_path,optimum):
    c=Controller();s=Source(c,optimum=optimum)
    av=ActiveVision(lambda:s,c,tmp_path/'different-world',initial_pose=c.pose,
        simulated=True,wait=lambda _:None)
    result=av.run()
    qualities=[e['quality'] for e in av.events if e['decision']=='observe target']
    assert qualities[-1]>qualities[0]+.01
    assert abs(result['pose'][0]-optimum[0])<=6


def test_physical_cli_refuses_before_serial_access(tmp_path):
    import subprocess,sys
    completed=subprocess.run([sys.executable,'-m','experiments.ppal.eyes.run_active_vision',
        '--output',str(tmp_path/'physical')],capture_output=True,text=True)
    assert completed.returncode==2 and 'authorization' in completed.stderr
    assert not (tmp_path/'physical').exists()


def test_physical_move_waits_for_delayed_settlement(tmp_path):
    """A moving servo must not fail merely because the nominal wait elapsed."""
    av, controller, source = make(tmp_path)
    av.simulated = False
    av.authorized = True
    av.output.mkdir()

    readings = iter([
        dict(pan=91, tilt=90, moving=True),
        dict(pan=93, tilt=90, moving=True),
        dict(pan=96, tilt=90, moving=False),
    ])
    controller.viewpoint_status = lambda timeout=1.0: next(readings)
    av.wait = lambda _: None

    av.move((96, 90))

    assert av.pose == (96, 90)
    assert av.events[-1]['decision'] == 'bounded physical experiment'


def test_physical_move_rejects_missing_viewpoint(tmp_path):
    """A missing firmware response must never count as settled movement."""
    av, controller, source = make(tmp_path)
    av.simulated = False
    av.authorized = True
    av.output.mkdir()

    controller.viewpoint_status = lambda timeout=1.0: None
    av.wait = lambda _: None

    with pytest.raises(ConnectionError, match='viewpoint response unavailable'):
        av.move((96, 90))
