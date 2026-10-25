"""Deterministic host tests; none opens a camera, socket, or controller."""
import hashlib
import json
from pathlib import Path
import tarfile
import pytest
from experiments.ppal.projectile_agency import ShotOrigins, timing_summary, candidates
from experiments.ppal.robotron_agency import VisualAgency, VECTORS
from experiments.ppal.eyes.detectors import Detection


def shot(model, direction=(1,0), start=.1, bodies=None, offset=0):
    bodies=bodies or {7:(50,50)}
    assert model.begin(direction,dict(move='STAY',fire={v:k for k,v in VECTORS.items()}[direction],controls_ready_at=start,pulse_finished_at=start+.2),bodies,[])
    rows=[]
    for i in range(3):
        distance=2+i
        p=(50+direction[0]*distance,50+direction[1]*distance+offset)
        rows+=model.observe([p],start+.1+i*.05)
    return rows


def test_two_nonparallel_new_trajectories_confirm_common_origin():
    m=ShotOrigins()
    assert len(shot(m))==1 and m.confirmed is None
    assert len(shot(m,(0,-1),.5))==1 and m.confirmed==7
    assert m.votes[7][0]['observations'][0][0]==pytest.approx(.2)


@pytest.mark.parametrize('direction',[(1,0),(-1,0)])
def test_parallel_or_reversed_shots_do_not_confirm(direction):
    m=ShotOrigins();shot(m);shot(m,direction,.5)
    assert m.confirmed is None


def test_shared_origin_ambiguity_rejects_even_center_candidate():
    m=ShotOrigins()
    assert shot(m,bodies={7:(50,50),8:(50,51)})==[]
    assert m.votes=={} and m.confirmed is None


def test_off_axis_enemy_and_nonlinear_effect_rejected():
    m=ShotOrigins();assert shot(m,offset=5)==[]
    m.begin((1,0),dict(move='STAY',fire='E',controls_ready_at=.1,pulse_finished_at=.3),{7:(50,50)},[])
    for t,p in [(.2,(52,50)),(.25,(53,52)),(.3,(54,50))]:m.observe([p],t)
    assert m.votes=={}


def test_preexisting_projectile_and_duplicate_exposure_supply_no_evidence():
    m=ShotOrigins()
    m.begin((1,0),dict(move='STAY',fire='E',controls_ready_at=.1,pulse_finished_at=.3),{7:(50,50)},[(52,50)])
    m.observe([(52,50)],.2)
    assert m.paths==[]
    m.observe([(54,50)],.25);m.observe([(55,50)],.25)
    assert m.votes=={}


def test_ambiguous_association_and_mass_effect_rejected():
    m=ShotOrigins();m.begin((1,0),dict(move='STAY',fire='E',controls_ready_at=.1,pulse_finished_at=.3),{7:(50,50)},[])
    m.observe([(52,50)],.2);m.observe([(53,50),(53,51)],.25)
    assert not m.paths
    m.observe([(i,50) for i in range(65)],.3)
    assert m.window is None


@pytest.mark.parametrize('execution',[{},dict(started_at=1),dict(move='STAY',fire='E',controls_ready_at=2,pulse_finished_at=1),
                                     dict(move='STAY',fire='E',controls_ready_at=float('nan'),pulse_finished_at=3)])
def test_controller_acknowledgment_timing_is_required(execution):
    m=ShotOrigins();assert not m.begin((1,0),execution,{7:(50,50)},[])
    assert not m.observe([(52,50)],3)


def test_center_is_ordering_only_and_respawn_requires_independent_boundary():
    v=VisualAgency();order=[]
    pairs=[(Detection('unknown',p,(1,1,10,20),100),{}) for p in [(20,20),(50,50)]]
    class C:
        last_execution=None
        def execute(self,*a):pass
    v.discover(lambda:pairs,C(),center_spawn=True,record=lambda r:order.append(list(v.positions.values())))
    assert order[0][0]==(50,50) and v.agency.self_id is None
    assert not v.confirmed_respawn(death_confirmed=False,respawn_confirmed=True)
    assert not v.confirmed_respawn(death_confirmed=True,respawn_confirmed=True,game_over=True)
    v.shots.votes={1:[{}]}
    assert v.confirmed_respawn(death_confirmed=True,respawn_confirmed=True)
    assert v.spawn_prior and not v.shots.votes and not v.tracker.active
    v.reframe();assert not v.spawn_prior


def test_provisional_identity_does_not_end_discovery():
    v=VisualAgency(bootstrap_body_fire=True);p=[20.,20.];commands=[]
    def read():return [(Detection('unknown',tuple(p),(1,1,10,20),100),{})]
    class C:
        last_execution=None
        def execute(self,a,ms):
            commands.append(a.move)
            u=VECTORS[a.move];p[0]+=u[0];p[1]+=u[1]
    v.discover(read,C())
    assert commands[:2]==['STAY','STAY']
    assert 'S' in commands and v.agency.self_id is not None


def test_fast_segmentation_has_no_class_admission():
    from PIL import Image,ImageDraw
    f=Image.new('RGB',(640,480));d=ImageDraw.Draw(f)
    d.rectangle((310,220,326,248),fill='white');d.rectangle((350,230,353,233),fill='white')
    bodies,points=candidates(f)
    assert len(bodies)==1 and len(points)==1
    assert bodies[0][0].kind=='unknown' and bodies[0][1]=={}


def test_timing_distinguishes_sensor_and_delivered_cadence():
    rows=[dict(capture_timestamp=t,capture=dict(frame_duration_us=66667,exposure_time_us=60000),
               acquisition_processing_seconds=.01,
               control_execution=dict(started_at=1,controls_ready_at=1.12)) for t in (0,.2,.4)]
    s=timing_summary(rows)
    assert s['independent_observation_hz']==5
    assert s['sensor_cadence_hz']==pytest.approx(15,rel=1e-4)
    assert s['controller_ready_seconds']==pytest.approx(.12)
    assert timing_summary([])['sensor_cadence_hz'] is None


def test_authentic_oct17_failure_is_preserved_and_remains_failed():
    root=Path(__file__).resolve().parents[1]/'docs/validation/fast-projectile-self/originals'
    archive=root/'charlie-first-game-diagnostics.tar.gz'
    manifest=json.loads((root/'sha256.json').read_text())
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==manifest[archive.name]
    with tarfile.open(archive) as t:
        prefix='development-20261017-182719/game-01/'
        report=json.load(t.extractfile(prefix+'report.json'))
        rows=[json.loads(x) for x in t.extractfile(prefix+'agency.jsonl')]
    assert report['provenance']['git_commit']=='d74d7a620c39104ce58fb2c9551381543a66b5f2'
    assert report['ticks']==0 and report['result']=='OBSERVATION UNCERTAIN'
    assert any(r['identity_status']=='provisional' for r in rows)
    assert not any(r['self_track_id'] is not None for r in rows)
    timing=timing_summary(rows)
    assert timing['exposure_us']>60000
    assert timing['independent_observation_hz']<10


@pytest.mark.parametrize('enabled',[False,True])
def test_fire_first_discovery_handoff_requires_explicit_confirmation_route(enabled):
    clock=[0.];fire=[None];endpoint=[0];commands=[];rows=[]
    def read():
        clock[0]+=.05
        if fire[0] is not None:
            endpoint[0]+=1;u=VECTORS[fire[0]];d=1+endpoint[0]
            read.projectiles=[(50+u[0]*d,50+u[1]*d)]
        else:read.projectiles=[]
        return [(Detection('unknown',(50,50),(1,1,10,20),100),{})]
    class Controller:
        last_execution=None
        def execute(self,a,ms):
            commands.append(a)
            fire[0]=a.fire if a.fire in ('E','N') else None;endpoint[0]=0
            self.last_execution=dict(move='STAY',fire=a.fire,controls_ready_at=clock[0],pulse_finished_at=clock[0]+.2)
            clock[0]+=.2
    v=VisualAgency(projectile_confirmation=enabled)
    v.discover(read,Controller(),observation_time=lambda:clock[0],record=rows.append)
    assert [a.fire for a in commands[:2]]==['E','N']
    if enabled:
        assert len(commands)==2 and v.player==(50,50)
        assert rows[-1]['confirmation_route']=='two_nonparallel_command_aligned_shot_origins'
        assert rows[-1]['identity_status']=='confirmed'
        # Loss clears the alternative route; no inherited confirmation on respawn.
        v.observe([],observed_at=clock[0]+.1)
        assert v.player is None  # brief occlusion retains identity, never a guessed control position
        v.observe([],observed_at=clock[0]+.5)
        assert v.agency.self_id is None
    else:
        assert len(commands)>2 and v.agency.self_id is None


def test_stale_wrong_actuator_and_old_origin_votes_are_rejected():
    m=ShotOrigins();shot(m)
    assert not m.begin((0,-1),dict(move='STAY',fire='E',controls_ready_at=.5,pulse_finished_at=.7),{7:(50,50)},[])
    shot(m,(0,-1),10.)
    assert m.confirmed is None


def test_controller_records_actual_ack_and_pulse_intervals_without_socket(monkeypatch):
    from experiments.ppal import arcade_transport as transport
    from experiments.ppal.controller_sandbox import ControllerSandbox
    from experiments.ppal.models import Action
    clock=[10.]
    monkeypatch.setattr(transport.time,'monotonic',lambda:clock[0])
    c=object.__new__(transport.ArcadeController) # bypass all I/O construction
    c.protocol='positions';c.pulse=True;c.closed=False;c.positions=('LS_CENTER','RS_CENTER')
    c.require_lease=False  # explicit socket-free fixture; real lease behavior tested separately
    c.sandbox=ControllerSandbox();c.held=frozenset()
    def command(value):clock[0]+=.12
    def sleep(seconds):clock[0]+=seconds
    c._command=command;c.sleep=sleep
    c.execute(Action('STAY','E'),60)
    e=c.last_execution
    assert e['controls_ready_at']-e['started_at']==pytest.approx(.12)
    assert e['pulse_finished_at']-e['controls_ready_at']==pytest.approx(.06)
    assert e['returned_at']-e['pulse_finished_at']==pytest.approx(.24)
    assert e['commands'][0]['ack_at']-e['commands'][0]['sent_at']==pytest.approx(.12)


def test_center_prior_ranks_existing_ids_without_changing_evidence_thresholds():
    v=VisualAgency();v.spawn_prior=False
    pairs=[(Detection('unknown',p,(1,1,10,20),100),{}) for p in [(10,10),(50,50)]]
    first=v.observe(pairs,observed_at=1.)
    old=first['candidate_track_id']
    v.spawn_prior=True
    row=v.observe(pairs,observed_at=2.)
    assert row['candidate_track_id']!=old
    assert v.positions[row['candidate_track_id']]==(50,50)
    assert row['confidence']==0 and row['self_track_id'] is None
    assert all(b.hits==0 for b in v.agency.beliefs.values())


def test_camera_only_profiler_closes_before_writing(monkeypatch,tmp_path):
    from experiments.ppal import acquisition_profile as profile
    from experiments.ppal.eyes import sources
    from PIL import Image
    clock=[0.];closed=[];focus=[];out=tmp_path/'profile.json'
    class Camera:
        def manual_focus(self,p):focus.append(p)
        set_manual_focus=manual_focus
        def focus_limits(self):return (0.,10.)
        def read_fresh(self):
            assert not out.exists()
            clock[0]+=.5
            self.last_capture=dict(lens_position=2.,af_state=0,sensor_timestamp_ns=int(clock[0]*1e9),first_pixel_exposure_at=clock[0],
                frame_duration_us=66667,exposure_time_us=60000)
            return Image.new('RGB',(100,100))
        def close(self):closed.append(True)
    monkeypatch.setattr(sources,'PiCameraSource',Camera)
    monkeypatch.setattr(profile.time,'monotonic',lambda:clock[0])
    profile.main(['--native-camera','--seconds','1','--output',str(out)])
    assert closed==[True] and focus==[2.]
    assert json.loads(out.read_text())['controller_opened'] is False


def test_new_body_contradiction_invalidates_shot_identity():
    v=VisualAgency(projectile_confirmation=True)
    def pairs(x):return [(Detection('unknown',(x,50),(1,1,10,20),100),{})]
    v.observe(pairs(50),observed_at=1.)
    key=next(iter(v.positions));v.shots.confirmed=key
    assert v.observe(pairs(50),observed_at=2.)['identity_status']=='confirmed'
    assert v.observe(pairs(49),move='E',observed_at=3.)['identity_status']=='unknown'
    assert v.shots.confirmed is None
