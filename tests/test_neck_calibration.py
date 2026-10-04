"""CAL-1 and persistent neck health: simulated hardware exclusively."""
import copy
import json
import sys
from types import SimpleNamespace
import pytest
from test_active_vision_firmware import board,PROFILE,load


def commissioning():
    p=copy.deepcopy(PROFILE)
    p.pop('validation_status');p.update(commissioning_reviewed=True,
        calibration_id='FAKE_COMMISSION',commissioning_margin=.1,max_rate=1,max_step=.5,
        clearance_polygon=[[88,90],[90,88],[92,90],[90,92]])
    return p


@pytest.fixture
def cal(board):
    profile=commissioning()
    a=board.module.ServoController(electrical_gate=True,calibration_profile=profile,
        calibration_input=lambda:board.pressed[0],clock=lambda:board.now[0],
        pwm_factory=lambda pin:factory_pwm(board,pin),pin_factory=lambda pin:pin)
    a.establish_session('session_1234')
    def tick(contact=False,count=5):
        board.pressed[0]=contact
        for _ in range(count):board.now[0]+=20;a.update()
    def request(op,**kw):
        data=dict(op=op,run_id='calibration_001');data.update(kw)
        return a.calibration.request(a._session,a._epoch,data)
    proof=dict(operator='operator_001',evidence='evidence_001',pose_verified=True,pulse_mapping_verified=True,
        clearance_verified=True,cutoff_verified=True,external_power_off=True,supervised=True,
        no_binding=True,settled=True)
    def ready():
        request('begin');tick();request('verify',pose=[90,90],**proof)
    def prepare(pose=[90.5,90],step='cal_step_001'):
        request('prepare',pose=pose,step_id=step,rate=1,**proof)
    def move():
        before=[a.a_pan.target,a.a_tilt.target]
        tick(True);assert [a.a_pan.target,a.a_tilt.target]==before
        tick(False)
        for _ in range(30):tick(False,1)
        assert a.calibration.state=='AWAIT_CONFIRMATION'
    return SimpleNamespace(a=a,b=board,request=request,tick=tick,ready=ready,prepare=prepare,
        move=move,proof=proof,profile=profile)


def factory_pwm(board,pin):
    class PWM:
        def __init__(self):self.pin=pin;self.values=[];self.disabled=False
        def freq(self,v):self.frequency=v
        def duty_u16(self,v):self.values.append(v)
        def deinit(self):self.disabled=True
    p=PWM();board.pwms.append(p);board.pins.append(pin);return p


def test_startup_touch_and_held_contact_never_activate(cal):
    cal.tick(True,100);cal.tick(False);assert not cal.b.pwms
    cal.ready();cal.prepare();cal.tick(True,100)
    assert not cal.b.pwms and cal.a.calibration.state=='PREPARED'
    cal.tick(False)
    assert [p.pin for p in cal.b.pwms]==[4,5]
    cal.tick(True,100)
    count=len(cal.b.pwms);target=cal.a.a_pan.target
    cal.tick(False);cal.tick(True,100)
    assert len(cal.b.pwms)==count and cal.a.a_pan.target==target


def test_contact_bounce_cannot_create_a_permit(cal):
    cal.ready();cal.prepare()
    for _ in range(20):cal.tick(True,1);cal.tick(False,1)
    assert not cal.b.pwms
    cal.move();assert len(cal.b.pwms)==2


def test_first_activation_uses_verified_pose_not_estimated_home(cal):
    cal.request('begin');cal.tick();cal.request('verify',pose=[89.5,90],**cal.proof)
    cal.prepare([89,90]);cal.tick(True);cal.tick(False)
    expected=int(cal.a.calibration.envelope.pulse(0,89.5)*65535/20000)
    assert cal.b.pwms[0].values[0]==expected
    assert cal.a.a_pan.target==89 and cal.a.status()['measured_position'] is None


@pytest.mark.parametrize('missing',['pose_verified','pulse_mapping_verified','clearance_verified','cutoff_verified','external_power_off'])
def test_each_initial_prerequisite_is_mandatory(cal,missing):
    cal.request('begin');proof=dict(cal.proof);proof[missing]=False
    with pytest.raises(RuntimeError):cal.request('verify',pose=[90,90],**proof)
    cal.tick(True);cal.tick(False);assert not cal.b.pwms


@pytest.mark.parametrize('pose',[[91,91],[90.5,90.5],[91,90],[float('nan'),90],[90,float('inf')]])
def test_joint_region_single_axis_step_and_finite_limits(cal,pose):
    cal.ready()
    with pytest.raises(RuntimeError):cal.prepare(pose)
    assert not cal.b.pwms


def test_missing_confirmation_and_repeated_step_block_next_move(cal):
    cal.ready();cal.prepare();cal.move()
    with pytest.raises(RuntimeError):cal.prepare([91,90],'cal_step_002')
    cal.request('confirm',step_id='cal_step_001',visual_displacement=[2,0],**cal.proof)
    with pytest.raises(RuntimeError,match='REPEATED'):cal.prepare([91,90])
    cal.prepare([91,90],'cal_step_002');assert len(cal.b.pwms)==2


@pytest.mark.parametrize('interrupt',['STOP','watchdog','reconnect','primary','input_failure','stage_timeout'])
def test_interruptions_revoke_pending_permit_disable_pwm_and_record(cal,interrupt):
    cal.ready();cal.prepare();cal.move()
    if interrupt=='STOP':cal.a.stop()
    elif interrupt=='watchdog':cal.b.now[0]+=10001;cal.a.update()
    elif interrupt=='reconnect':cal.a.establish_session('new_session_123')
    elif interrupt=='primary':cal.a.primary_acquire(cal.a._session,cal.a._epoch)
    elif interrupt=='input_failure':
        cal.a.calibration.input=lambda:(_ for _ in ()).throw(OSError('wire'))
        with pytest.raises(RuntimeError):cal.a.update()
    else:
        cal.b.now[0]+=30001;cal.a.contact();cal.a.update()
    assert not cal.a.status()['armed'] and all(p.disabled for p in cal.b.pwms)
    assert cal.a.calibration.state=='ABORTED'
    assert any(e['kind']=='interruption' for e in cal.a.calibration.events)


def test_reentry_requires_new_pose_verification_and_reboot_restores_no_grants(cal):
    cal.ready();cal.prepare();old=cal.a._epoch;cal.a.stop()
    with pytest.raises(RuntimeError):cal.a.calibration.request('session_1234',old,dict(op='prepare',run_id='calibration_001'))
    cal.request('begin',run_id='calibration_002');cal.tick(True);cal.tick(False)
    assert not cal.b.pwms
    new=cal.b.module.ServoController()
    assert not new.status()['armed'] and new.calibration.state=='DISABLED' and new._session is None


def test_private_calibration_hooks_do_not_bypass_jumper_permit(cal):
    cal.ready();cal.prepare()
    with pytest.raises(RuntimeError):cal.a._calibration_activate([90,90],cal.a.calibration.envelope)
    with pytest.raises(RuntimeError):cal.a._calibration_move([90.5,90],1)
    with pytest.raises(RuntimeError):cal.a._activate([90,90],cal.a.calibration.envelope)
    with pytest.raises(RuntimeError):cal.a._set_target([90.5,90],1,cal.a.calibration.envelope)
    with pytest.raises(RuntimeError):cal.a.look(90.5,90,session=cal.a._session,epoch=cal.a._epoch)
    assert not cal.b.pwms


def test_event_failure_stops_and_does_not_energize(cal):
    cal.ready()
    cal.a.calibration.sink=lambda _:(_ for _ in ()).throw(OSError('disk'))
    with pytest.raises(RuntimeError):cal.prepare()
    assert not cal.a.status()['armed'] and not cal.b.pwms


def test_invalid_commissioning_profiles_and_disconnected_b(board):
    for patch in (dict(clearance_polygon=[[90,90],[91,91],[90,91],[91,90]]),
                  dict(max_step=2),dict(max_rate=float('nan')),dict(commissioning_reviewed=False),dict(pins=[14,15])):
        p=commissioning();p.update(patch)
        with pytest.raises((RuntimeError,ValueError)):board.module.ServoController(calibration_profile=p)
    assert not board.pwms


def test_autonomous_activation_needs_qualified_profile_and_fresh_verified_pose(board):
    a=board.module.ServoController(PROFILE,electrical_gate=True,autonomous_enabled=True,
        profile_quarantine=lambda reason:None,
        profile_operation=lambda active:None,
        clock=lambda:board.now[0],pwm_factory=lambda p:factory_pwm(board,p),pin_factory=lambda p:p)
    a.establish_session('session_1234')
    with pytest.raises(RuntimeError):a.activate_autonomous(a._session,a._epoch)
    proof=dict(operator='operator_001',evidence='evidence_001',pose_verified=True,
        pulse_mapping_verified=True,clearance_verified=True,cutoff_verified=True,external_power_off=True)
    a.confirm_start_pose(a._session,a._epoch,[89,90],proof)
    assert not board.pwms
    a.activate_autonomous(a._session,a._epoch)
    a.authorize('ACTIVE_VISION',a._session,a._epoch,'INITIAL')
    a.look(90,90,session=a._session,epoch=a._epoch)
    for _ in range(30):board.now[0]+=20;a.update()
    assert a.a_pan.position==pytest.approx(90) and a._input is None
    a.stop()
    with pytest.raises(RuntimeError):a.activate_autonomous(a._session,a._epoch)


def test_no_gp10_normal_arm_configuration():
    from pathlib import Path
    text=(Path(__file__).resolve().parents[1]/'rp2040/main.py').read_text()
    assert "if LOCAL_ARM_PIN == 10:" in text and 'GP10_CALIBRATION_ONLY_NOT_ARM' in text


def completed_grid(cal,tmp_path,*,simulated=True):
    from hardware.neck_calibration import CalibrationJournal
    journal=CalibrationJournal(tmp_path/'calibration.jsonl',simulated=simulated)
    cal.a.calibration.sink=journal.append
    cal.ready()
    path=[[90.5,90],[90.5,89.5],[90,89.5],[89.5,89.5],[89.5,90],
          [89.5,90.5],[90,90.5],[90.5,90.5]]
    previous=[90,90]
    for i,pose in enumerate(path):
        step=f'grid_step_{i:03d}'
        cal.prepare(pose,step);cal.move()
        cal.request('confirm',step_id=step,visual_displacement=[4*(b-a) for a,b in zip(previous,pose)],**cal.proof)
        previous=pose
    cal.request('finish');journal.close()
    return tmp_path/'calibration.jsonl'


def test_simulated_grid_derives_conservative_candidate_never_qualifies(cal,tmp_path):
    from hardware.neck_calibration import derive_candidate,independently_qualify,ProfileRepository
    evidence=completed_grid(cal,tmp_path)
    candidate=derive_candidate(evidence,cal.profile,name='candidate_001',margin=.1)
    assert candidate['pan']['min']==pytest.approx(89.6) and candidate['pan']['max']==pytest.approx(90.4)
    assert candidate['validation_status']=='CANDIDATE' and candidate['measured_position'] is None
    repo=ProfileRepository(tmp_path/'profiles');repo.save(candidate)
    with pytest.raises(ValueError):repo.activate('candidate_001')
    with pytest.raises(ValueError):independently_qualify(candidate,name='qualified_001',reviewer='reviewer_001',evidence='missing',physical_validation=True)
    with pytest.raises(FileExistsError):repo.save(candidate)


def review_report(candidate,tmp_path):
    from hardware.neck_calibration import encode
    import hashlib
    report=dict(schema='charlie-neck-qualification-v1',reviewer='reviewer_001',candidate_id=candidate['calibration_id'],
        candidate_sha256=hashlib.sha256(encode(candidate)).hexdigest(),evidence_sha256=candidate['evidence_sha256'],
        simulated=False,physical_validation=True,interval_clearance_verified=True,initial_pulse_verified=True,
        torque_release_verified=True,watchdog_and_cutoff_verified=True)
    path=tmp_path/'FAKE-review.json';path.write_text(json.dumps(report));return path


def qualified_fixture(cal,tmp_path):
    """Fabricated physical-shaped documents test schema only, no physical claim."""
    from hardware.neck_calibration import derive_candidate,independently_qualify
    evidence=completed_grid(cal,tmp_path,simulated=False)
    candidate=derive_candidate(evidence,cal.profile,name='candidate_001',margin=.1)
    review=review_report(candidate,tmp_path)
    qualified=independently_qualify(candidate,name='qualified_001',reviewer='reviewer_001',evidence=review,physical_validation=True)
    return candidate,qualified,review


def test_persistent_versions_reboot_selection_quarantine_and_history(cal,tmp_path):
    from hardware.neck_calibration import ProfileRepository
    candidate,qualified,_=qualified_fixture(cal,tmp_path)
    repo=ProfileRepository(tmp_path/'profiles');repo.save(candidate);repo.save(qualified)
    repo.activate('qualified_001')
    assert ProfileRepository(repo.directory).active()==qualified
    # Independent RP2040 loader validates exactly the same immutable bytes.
    store=load('profile_store_test','rp2040/profile_store.py')
    assert store.load(str(repo.directory))==qualified
    newer=copy.deepcopy(qualified);newer['calibration_id']='qualified_002';newer['supersedes']+=['qualified_001']
    repo.save(newer);repo.activate('qualified_002')
    assert repo.read('qualified_001')==qualified
    assert (repo.directory/'qualified_001.activation-history.json').exists()
    repo.quarantine('qualified_002','uncertain movement',dict(mechanical_fault_confirmed=False))
    with pytest.raises(ValueError):ProfileRepository(repo.directory).active()
    with pytest.raises(RuntimeError):store.load(str(repo.directory))
    with pytest.raises(ValueError):repo.activate('qualified_002')
    assert repo.read('qualified_001')==qualified


@pytest.mark.parametrize('fault',['missing','corrupt','digest','hardware','unverified','combination','qualification'])
def test_invalid_persistent_profiles_fail_closed(board,tmp_path,fault):
    from hardware.neck_calibration import ProfileRepository
    p=copy.deepcopy(PROFILE);p['calibration_id']='qualified_001'
    repo=ProfileRepository(tmp_path/'profiles')
    if fault=='hardware':p['hardware']['head_a']=[14,15]
    if fault=='unverified':p['validation_status']='CANDIDATE'
    if fault=='combination':p['clearance_polygon']=[[90,90],[91,91],[90,91],[91,90]]
    if fault=='qualification':p['independent_review']['reviewer']='fake_operator'
    if fault not in ('missing','hardware'):
        repo.save(p)
        if fault not in ('unverified','combination','qualification'):repo.activate('qualified_001')
    if fault=='corrupt':(repo.directory/'activation.json').write_text('{')
    if fault=='digest':(repo.directory/'qualified_001.json').write_text('{}')
    store=load('bad_profile_store','rp2040/profile_store.py')
    with pytest.raises(RuntimeError):store.load(str(repo.directory))
    assert not board.pwms


def test_qualification_rejects_operator_self_review_and_tampered_evidence(cal,tmp_path):
    from hardware.neck_calibration import independently_qualify
    c,q,review=qualified_fixture(cal,tmp_path)
    with pytest.raises(ValueError):independently_qualify(c,name='qualified_002',reviewer='operator_001',evidence=review,physical_validation=True)
    with open(c['evidence'],'a') as f:f.write('{}\n')
    with pytest.raises(ValueError):independently_qualify(c,name='qualified_002',reviewer='reviewer_001',evidence=review,physical_validation=True)


def test_derivation_rejects_missing_grid_clearance_and_unfinished_run(cal,tmp_path):
    from hardware.neck_calibration import CalibrationJournal,derive_candidate
    journal=CalibrationJournal(tmp_path/'incomplete.jsonl',simulated=True)
    cal.a.calibration.sink=journal.append;cal.ready();cal.prepare();cal.move()
    cal.request('confirm',step_id='cal_step_001',visual_displacement=[2,0],**cal.proof)
    with pytest.raises(ValueError):derive_candidate(journal.path,cal.profile,name='candidate_001',margin=.1)
    cal.request('finish');journal.close()
    with pytest.raises(ValueError,match='grid'):derive_candidate(journal.path,cal.profile,name='candidate_001',margin=.1)


def health_fixture(tmp_path):
    from hardware.neck_health import NeckHealth
    from hardware.neck_calibration import ProfileRepository
    stopped=[];invalidated=[];events=[]
    host=SimpleNamespace(stop=lambda:stopped.append(True),neck_uncertain=lambda:invalidated.append(True))
    repo=ProfileRepository(tmp_path/'profiles')
    health=NeckHealth(host,'qualified_001',events,repository=repo)
    corners=[[0,0],[100,0],[100,100],[0,100]]
    telemetry=dict(pan=90.5,tilt=90,moving=False,armed=True)
    return health,corners,telemetry,stopped,invalidated,events,repo


@pytest.mark.parametrize('bad',['no_displacement','missing_target','nonfinite_target','wrong_telemetry','moving'])
def test_health_discrepancy_stops_on_first_uncertain_move_no_obstruction_retry(tmp_path,bad):
    h,c,t,stops,invalid,events,repo=health_fixture(tmp_path)
    h.prepare([90,90],[90.5,90],c)
    if bad=='missing_target':c=None
    if bad=='nonfinite_target':c=[[float('nan'),0]]*4
    if bad=='wrong_telemetry':t['pan']=89
    if bad=='moving':t['moving']=True
    h.observe(c,telemetry=t)
    assert stops and invalid and h.quarantined
    assert any(e.get('alternatives') for e in events) and all(not e['mechanical_fault_confirmed'] for e in events)
    with pytest.raises(PermissionError):h.prepare([90,90],[90.5,90],c)
    assert (repo.directory/'qualified_001.quarantine.json').exists()
    assert h.executive_context()['physical_authorization'] is False
    assert h.executive_context()['resources']==['passive_observation','digital_correction']


def test_health_tracks_normal_moves_and_ordinary_scene_changes_without_fault(tmp_path):
    h,c,t,stops,invalid,events,_=health_fixture(tmp_path)
    h.prepare([90,90],[90.5,90],c)
    shifted=[[x+2,y] for x,y in c];h.observe(shifted,telemetry=t)
    for _ in range(5):h.observe([[x+100,y] for x,y in c],expected_transition=True)
    h.observe(None)
    assert not stops and not invalid and not h.quarantined


@pytest.mark.parametrize('axis', ['pan', 'tilt'])
@pytest.mark.parametrize('value', [float('nan'), float('inf'), float('-inf'), None, 'invalid', True])
def test_health_invalid_commanded_position_revokes_and_quarantines(tmp_path, axis, value):
    h,c,t,stops,invalid,events,repo=health_fixture(tmp_path)
    h.prepare([90,90],[90.5,90],c)
    t[axis]=value
    h.observe([[x+2,y] for x,y in c],telemetry=t)
    assert stops and invalid and h.quarantined
    assert (repo.directory/'qualified_001.quarantine.json').exists()
    assert all(not e['mechanical_fault_confirmed'] for e in events)
    assert any(e.get('alternatives') for e in events)
    with pytest.raises(PermissionError):h.prepare([90.5,90],[91,90],c)


def test_health_persistent_uncommanded_camera_change_requires_recalibration(tmp_path):
    h,c,t,stops,*_=health_fixture(tmp_path);h.observe(c)
    moved=[[x+40,y] for x,y in c]
    h.observe(moved);h.observe(moved);assert not stops
    h.observe(moved);assert stops and h.quarantined


def test_health_evidence_failure_still_stops(tmp_path):
    h,c,t,stops,*_=health_fixture(tmp_path)
    h.evidence=lambda _:(_ for _ in ()).throw(OSError('disk'))
    with pytest.raises(OSError):h.unsafe('uncertain')
    assert stops and h.quarantined


def test_executive_consumes_health_evidence_without_authorizing_physical_recalibration(tmp_path):
    from memory.evidence import EvidenceJournal
    from memory.learning_projects import LearningExecutive
    h,*_=health_fixture(tmp_path);h.quarantined=True
    journal=EvidenceJournal(tmp_path/'learning.sqlite')
    executive=LearningExecutive(journal,SimpleNamespace(remember=lambda _:None))
    projects=h.reflect_to_executive(executive,journal)
    assert len(projects)==1
    result=executive.select(methods=['supervised_neck_recalibration'],resources=[],authorized_methods=[])
    assert result['project'] is None and result['alternatives'][0]['blocked']
    assert executive.projects()[projects[0]]['originator']=='Reflection'
    journal.close()


def test_health_reversed_visual_response_quarantines_without_retry(tmp_path):
    h,c,t,stops,*_=health_fixture(tmp_path)
    h.response_model=dict(pan=[4,0],tilt=[0,4])
    h.prepare([90,90],[90.5,90],c)
    h.observe([[x-2,y] for x,y in c],telemetry=t)
    assert stops and h.quarantined


@pytest.mark.parametrize('line',['CAL session_1234 1 []','START_VERIFY session_1234 1 []',
    'CAL session_1234 1 {','CAL session_1234 1 '+('x'*2100),
    'AUTOSTART session_1234 1','NECK_UNCERTAIN session_1234 1 bad'])
def test_cal_protocol_malformed_stale_and_unauthorized_requests_fail_closed(board,line,capsys):
    a,b,h,_=board.create(calibrated=False,electrical=False,interlock=False)
    a.establish_session('session_1234');board.command(h,line)
    assert 'ERR' in capsys.readouterr().out and not board.pwms


def test_old_unqualified_profile_cannot_be_armed_by_contact(board):
    p=copy.deepcopy(PROFILE);p.pop('validation_status')
    a=board.module.ServoController(p,electrical_gate=True,arm_input=lambda:board.pressed[0],
        clock=lambda:board.now[0],pwm_factory=lambda p:factory_pwm(board,p),pin_factory=lambda p:p)
    a.establish_session('session_1234');board.press(a)
    assert not a.status()['armed'] and not board.pwms


def test_fresh_confirmation_expires_before_autonomous_activation(board):
    a=board.module.ServoController(PROFILE,electrical_gate=True,autonomous_enabled=True,
        profile_quarantine=lambda _:None,profile_operation=lambda _:None,clock=lambda:board.now[0],
        pwm_factory=lambda p:factory_pwm(board,p),pin_factory=lambda p:p)
    a.establish_session('session_1234')
    proof=dict(operator='operator_001',evidence='evidence_001',pose_verified=True,pulse_mapping_verified=True,
        clearance_verified=True,cutoff_verified=True,external_power_off=True)
    a.confirm_start_pose(a._session,a._epoch,[90,90],proof)
    board.now[0]+=30001;a.contact()
    with pytest.raises(RuntimeError):a.activate_autonomous(a._session,a._epoch)
    assert not board.pwms


def test_real_transport_calibration_events_are_fsynced_and_stop_on_close(board,tmp_path):
    from test_active_vision_firmware import transport
    from hardware.neck_calibration import SupervisedCalibration,CalibrationJournal
    host,a,b=transport(board)
    module=sys.modules['calibration']
    a.calibration=module.Calibration(a,commissioning(),lambda:board.pressed[0],
        sink=lambda record:print('CAL_EVENT',json.dumps(record)))
    journal=CalibrationJournal(tmp_path/'uart-cal.jsonl',simulated=True)
    supervisor=SupervisedCalibration(host,journal)
    status=supervisor.request(dict(op='begin',run_id='calibration_001'))
    assert status['state']=='VERIFY_INITIAL'
    records=[json.loads(s)['event'] for s in journal.path.read_text().splitlines()]
    assert any(e['kind']=='begin' and e['run_id']=='calibration_001' for e in records)
    supervisor.close();journal.close()
    assert a.calibration.state=='ABORTED' and not a.status()['pwm_active']


def test_persistent_unclean_operation_and_failed_quarantine_stay_blocked(board,tmp_path):
    from hardware.neck_calibration import ProfileRepository
    p=copy.deepcopy(PROFILE);p['calibration_id']='qualified_001'
    repo=ProfileRepository(tmp_path/'profiles');repo.save(p);repo.activate('qualified_001')
    store=load('operating_profile_store','rp2040/profile_store.py')
    store.operation(str(repo.directory),p['calibration_id'],True)
    with pytest.raises(RuntimeError,match='UNCLEAN'):store.load(str(repo.directory))
    store.operation(str(repo.directory),p['calibration_id'],False)
    assert store.load(str(repo.directory))==p
    # Operation marker is durable before PWM; quarantine failure cannot clear it.
    a=board.module.ServoController(p,electrical_gate=True,autonomous_enabled=True,
        profile_quarantine=lambda _:(_ for _ in ()).throw(OSError('flash')),
        profile_operation=lambda active:store.operation(str(repo.directory),p['calibration_id'],active),
        clock=lambda:board.now[0],pwm_factory=lambda pin:factory_pwm(board,pin),pin_factory=lambda pin:pin)
    a.establish_session('session_1234')
    proof=dict(operator='operator_001',evidence='evidence_001',pose_verified=True,pulse_mapping_verified=True,
        clearance_verified=True,cutoff_verified=True,external_power_off=True)
    a.confirm_start_pose(a._session,a._epoch,[90,90],proof);a.activate_autonomous(a._session,a._epoch)
    with pytest.raises(OSError):a.invalidate_profile('uncertain')
    a.stop()
    assert not a.status()['armed'] and all(p.disabled for p in board.pwms)
    with pytest.raises(RuntimeError):store.load(str(repo.directory))


@pytest.mark.parametrize('rate',[.5,5])
def test_qualified_autonomous_optimizer_with_health_uses_no_gp10(board,tmp_path,rate):
    from test_active_vision_firmware import transport
    from experiments.ppal.eyes.active_vision import ActiveVision
    from experiments.ppal.eyes.simulate_active_vision import SimulatedCamera
    from experiments.ppal.eyes.camera_lease import CameraLease
    from PIL import ImageChops
    from hardware.calibration_service import CalibrationService
    from hardware.neck_calibration import ProfileRepository
    from memory.evidence import EvidenceJournal
    host,a,_=transport(board)
    repo=ProfileRepository(tmp_path/'profiles')
    p=copy.deepcopy(PROFILE);p['visual_response']=dict(pan=[10,0],tilt=[0,2])
    repo.save(p);repo.activate(p['calibration_id'])
    service=CalibrationService(host,repo,EvidenceJournal(tmp_path/'neck.sqlite3'))
    a._input=None
    a.envelope.rate=rate
    a._autonomous_enabled=True;a._profile_operation=lambda _:None;a._quarantine=lambda _:None
    a.envelope.visual_response=dict(pan=[10,0],tilt=[0,2])
    proof=dict(operator='operator_001',evidence='evidence_001',pose_verified=True,pulse_mapping_verified=True,
        clearance_verified=True,cutoff_verified=True,external_power_off=True)
    a.confirm_start_pose(a._session,a._epoch,[90,90],proof);a.activate_autonomous(a._session,a._epoch)
    class Pose:
        @property
        def pose(self):return (a.a_pan.position,a.a_tilt.position)
    class Camera(SimulatedCamera):
        def read(self):
            image=super().read()
            return ImageChops.offset(image,round((self.controller.pose[0]-90)*10),0)
        read_fresh=read
    def factory():
        source=Camera(Pose(),optimum=(94,90));lease=CameraLease(directory=tmp_path,role='active_vision')
        source.camera=SimpleNamespace(lease=lease);original=source.close
        source.close=lambda:(original(),lease.close());return source
    def wait(seconds):board.now[0]+=int(seconds*1000);a.update()
    optimizer=ActiveVision(factory,host,tmp_path/'autonomous',initial_pose=(90,90),authorized=True,
                           wait=wait,calibration_service=service)
    result=optimizer.run()
    assert result['state']=='LOCKED' and optimizer.neck_health is not None
    assert not optimizer.neck_health.quarantined and a._input is None
    # No button polling is needed: its fake state stays released throughout.
    assert board.pressed[0] is False and result['resources_released'] and not a.status()['pwm_active']
    assert optimizer.neck_health is service.health and not service.requests()
    service.close()


@pytest.mark.parametrize('condition',['released','held','gp10_as_arm','missing_persistent'])
def test_real_main_unexpected_startup_conditions_never_create_pwm(board,monkeypatch,tmp_path,condition):
    from pathlib import Path
    pins=[]
    class Pin:
        IN=0;PULL_UP=1
        def __init__(self,n,*_):pins.append(n)
        def value(self):return 0 if condition=='held' else 1
    monkeypatch.setitem(sys.modules,'machine',SimpleNamespace(Pin=Pin,PWM=lambda _:pytest.fail('startup PWM')))
    board.profile.CALIBRATION_INPUT_ENABLED=True
    if condition=='gp10_as_arm':board.profile.LOCAL_ARM_PIN=10
    if condition=='missing_persistent':
        board.profile.PERSISTENT_PROFILE_DIRECTORY=str(tmp_path)
        board.profile.AUTONOMOUS_MOTION_ENABLED=True
        board.profile.ELECTRICAL_GATE_CLEARED=True
        board.profile.CALIBRATION_PROFILE=commissioning()
        monkeypatch.setitem(sys.modules,'profile_store',load('boot_store','rp2040/profile_store.py'))
    for name in ('scanner','behaviors','commands','heartbeat'):
        monkeypatch.setitem(sys.modules,name,load('boot_'+name,'rp2040/'+name+'.py'))
    display=SimpleNamespace(NO_BRAIN='NO_BRAIN',status=lambda _:None,update=lambda:None)
    monkeypatch.setitem(sys.modules,'display',SimpleNamespace(Display=lambda:display))
    monkeypatch.setattr('select.poll',lambda:SimpleNamespace(register=lambda *_:None,poll=lambda _:[]))
    class EndBoot(BaseException):pass
    counter=[0]
    def tick(_):
        counter[0]+=1;board.now[0]+=20
        if counter[0]==10:raise EndBoot()
    monkeypatch.setattr('time.sleep_ms',tick,raising=False)
    root=Path(__file__).resolve().parents[1];namespace={}
    expected=RuntimeError if condition=='gp10_as_arm' else EndBoot
    with pytest.raises(expected):exec(compile((root/'rp2040/main.py').read_text(),'<real boot>','exec'),namespace)
    assert all(p==10 for p in pins) and not board.pwms
    if condition!='gp10_as_arm':
        a=namespace['servos'];assert not a.status()['armed']
        if condition=='missing_persistent':
            assert a.envelope is None and a.calibration.state=='READY'
            assert a._autonomous_enabled is False


def test_normal_watchdog_cannot_be_cleared_by_reconnect_stop(board,tmp_path):
    from hardware.neck_calibration import ProfileRepository
    p=copy.deepcopy(PROFILE);p['calibration_id']='qualified_001'
    repo=ProfileRepository(tmp_path/'profiles');repo.save(p);repo.activate(p['calibration_id'])
    store=load('watchdog_store','rp2040/profile_store.py')
    a=board.module.ServoController(p,electrical_gate=True,autonomous_enabled=True,
        profile_quarantine=lambda reason:store.quarantine(str(repo.directory),p['calibration_id'],reason),
        profile_operation=lambda active:store.operation(str(repo.directory),p['calibration_id'],active),
        clock=lambda:board.now[0],pwm_factory=lambda pin:factory_pwm(board,pin),pin_factory=lambda pin:pin)
    a.establish_session('session_1234')
    proof=dict(operator='operator_001',evidence='evidence_001',pose_verified=True,pulse_mapping_verified=True,
        clearance_verified=True,cutoff_verified=True,external_power_off=True)
    a.confirm_start_pose(a._session,a._epoch,[90,90],proof);a.activate_autonomous(a._session,a._epoch)
    board.now[0]+=10001;a.update();a.stop();a.establish_session('session_5678')
    assert not a.status()['armed'] and a.status()['profile_invalid']
    with pytest.raises(RuntimeError):store.load(str(repo.directory))
    with pytest.raises(ValueError):repo.active()


def test_contact_already_low_between_scheduler_samples_cannot_prepare(cal):
    cal.ready()
    assert cal.a.calibration.jumper.released()
    cal.b.pressed[0]=True  # Physical contact changed before the next 20ms tick.
    with pytest.raises(RuntimeError):cal.prepare()
    cal.tick(True);cal.tick(False)
    assert not cal.b.pwms
