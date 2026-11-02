"""Host-only regression; no physical qualification claims."""
import json
from dataclasses import replace
from unittest.mock import Mock
import pytest
from hardware.elegoo_mobile import ElegooMobileBase
from experiments.ppal.mobile_navigation import MotionLease
from learning.mobile_safety import validate_report, runtime_hash


def car_fixture():
    c=ElegooMobileBase();c.sock=Mock();c._running=True
    c._send=Mock(return_value={'ok':True});c.stop_verified=Mock(return_value={'sent':True,'physically_stopped':None})
    return c


def pulse(c,**kwargs):
    now=[1.]
    if c._send.side_effect is None:
        def completed(payload,**options):
            if options.get('preflight') and not options['preflight']():
                raise InterruptedError('fixture wire veto')
            now[0]+=payload['T']/1000.+.001
            options['wait_check']()
            return {'ok':True,'response':'{'+payload['H']+'_ok}'}
        c._send.side_effect=completed
    return c.pulse(kwargs.pop('direction','FORWARD'),pwm=kwargs.pop('pwm',30),seconds=kwargs.pop('seconds',.1),
        lease=kwargs.pop('lease',MotionLease('supervised_trial',2,'fixture','boot')),boot_id='boot',
        envelope={'max_pwm':35,'max_duration':.2},safety_check=kwargs.pop('safety_check',lambda:True),
        clock=lambda:now[0],wait=lambda dt:now.__setitem__(0,now[0]+dt),**kwargs)


@pytest.mark.parametrize('direction,d1',[('LEFT',1),('RIGHT',2),('FORWARD',3),('REVERSE',4)])
def test_bounded_directions_and_stop(direction,d1):
    c=car_fixture();result=pulse(c,direction=direction)
    payload=c._send.call_args.args[0]
    assert payload['N']==2 and payload['D1']==d1 and payload['T']==100 and c._send.call_args.kwargs['retry'] is False
    assert result['executed'] is None and result['physically_observed'] is None
    c.stop_verified.assert_called_once()


@pytest.mark.parametrize('change',[{'pwm':True},{'pwm':36},{'seconds':float('nan')},{'seconds':.201},{'direction':'OTHER'},
 {'lease':MotionLease('supervised_trial',1.05,'fixture','boot')},{'lease':MotionLease('supervised_trial',2,'fixture','old')}])
def test_invalid_pulses_do_not_start(change):
    c=car_fixture()
    with pytest.raises(ValueError):pulse(c,**change)
    c._send.assert_not_called()


def test_ambiguous_ack_and_cancellation_stop():
    c=car_fixture();c._send.side_effect=TimeoutError('lost ACK')
    with pytest.raises(TimeoutError):pulse(c)
    assert c._send.call_count==1;c.stop_verified.assert_called_once()
    c=car_fixture();checks=iter([True,False])
    with pytest.raises(InterruptedError):pulse(c,safety_check=lambda:next(checks))
    c.stop_verified.assert_called_once()


def test_nonretry_wire_failure_never_reconnects():
    c=ElegooMobileBase();c.sock=Mock();c._running=True
    c._send_raw=Mock(side_effect=OSError('ambiguous write'));c.connect=Mock()
    with pytest.raises(OSError):c._send({'N':3},retry=False)
    assert c._send_raw.call_count==1;c.connect.assert_not_called()


def test_stop_failure_surfaces_uncertainty_and_sensor_is_never_speculative():
    c=ElegooMobileBase();c._send=Mock(side_effect=ConnectionError())
    assert c.stop_verified()==dict(sent=None,acknowledged=False,physically_stopped=None,error='ConnectionError')
    c._send.reset_mock()
    with pytest.raises(ValueError):c.read_ultrasonic(protocol={})
    c._send.assert_not_called()


def test_no_report_or_unsupported_runtime_can_qualify():
    assert len(runtime_hash())==64
    with pytest.raises(ValueError):validate_report({})
    with pytest.raises(ValueError):validate_report(dict(schema='charlie.mobile.qualification.v1',authentic=False))


def executive_case(tmp_path,method='pet_follow'):
    """Synthetic contracts exercise the real Executive; not native evidence."""
    from memory.evidence import EvidenceJournal
    from memory.learning_projects import LearningExecutive,reflect_project_opportunities
    j=EvidenceJournal(tmp_path/'executive.sqlite3');e=LearningExecutive(j,Mock())
    o=j.append('observation',dict(observation={'frame':{'authentic':True}}),episode='software-control',producer='test',version='1')
    def propose(method,weight=.5):
        h=dict(method=method,scope={'control':method},expected='synthetic control expectation',evidence_ids=[o.id],
               conditions=[{'v':1},{'v':2}],observed_conditions=[{'v':1}],requires=[])
        p=reflect_project_opportunities(j,'software-control',[h])[0]
        return e.propose(p['proposal'],j,[p['evidence_id']])
    project=propose(method)
    return j,e,o,project,propose


def test_existing_executive_selects_or_declines_without_movement_authority(tmp_path):
    j,e,o,p,propose=executive_case(tmp_path)
    selected=e.consider_mobile_attention(o.id,methods=['pet_follow'],resources=[],authorized_methods=['pet_follow'])
    assert selected['intent']=='follow' and selected['project_id']==p
    assert e.consider_mobile_attention(o.id,primary_priority=80,methods=['pet_follow'],authorized_methods=['pet_follow'])['intent']=='yield'
    assert e.consider_mobile_attention(o.id,methods=['pet_follow'],authorized_methods=[])['intent']=='decline'
    assert not j.category_records('event','capability_activation')
    j.close()


def test_same_portfolio_can_prefer_an_existing_other_interest(tmp_path):
    j,e,o,p,propose=executive_case(tmp_path,'evidence-review')
    # Sticky current interest remains in the ONE portfolio when animal appears.
    e.select(methods=['evidence-review'],resources=[],authorized_methods=['evidence-review'])
    propose('pet_follow')
    d=e.consider_mobile_attention(o.id,methods=['pet_follow','evidence-review'],authorized_methods=['pet_follow','evidence-review'])
    assert d['intent']=='decline' and d['project_id']==p and len(d['alternatives'])==2
    j.close()


def test_fixture_cannot_create_interest_and_reopening_cannot_restore_motion(tmp_path):
    from memory.learning_projects import LearningExecutive
    from memory.evidence import EvidenceJournal
    j,e,o,p,propose=executive_case(tmp_path)
    fake=j.append('observation',{'observation':{'frame':{'authentic':False}}},episode='fixture',producer='test',version='1')
    assert e.consider_mobile_attention(fake.id,methods=['pet_follow'],authorized_methods=['pet_follow'])['intent']=='decline'
    j.close();j=EvidenceJournal(tmp_path/'executive.sqlite3');e=LearningExecutive(j,Mock())
    assert p in e.projects() and not MotionLease().valid(1,'new-boot')
    j.close()


def test_catalog_lists_without_devices_and_readiness_is_dynamic(capsys,monkeypatch):
    from main import main
    from learning.capabilities import default_registry
    monkeypatch.setattr(ElegooMobileBase,'connect',Mock(side_effect=AssertionError('device')))
    main(['--list-capabilities'])
    rows=json.loads(capsys.readouterr().out)
    assert {r['id'] for r in rows}>={'pet_observe','pet_follow'}
    assert not next(r for r in rows if r['id']=='pet_follow')['readiness']['available']
    r=default_registry();state={'pet_observe':dict(available=True,qualified=False),'pet_follow':dict(available=False,qualified=False,reasons=['range'])}
    rows=r.describe(state)
    assert next(x for x in rows if x['id']=='pet_observe')['readiness']['available']
    ElegooMobileBase.connect.assert_not_called()


def test_attention_uses_executive_and_debounces_species_flip(monkeypatch):
    from attention.manager import AttentionManager
    from stimulus.bus import StimulusBus
    from learning.capabilities import default_registry
    monkeypatch.setattr('learning.cycle.gameplay_active',lambda:False)
    a=AttentionManager(StimulusBus(),mobile_enabled=True);s=Mock()
    s.readiness.return_value={'pet_observe':{'available':True},'pet_follow':{'available':False}}
    s.executive_resources=set();s.perception.clock.return_value=1.
    e=Mock();e.projects.return_value={'x':{'method':'mobile-observe'}}
    e.consider_mobile_attention.return_value={'intent':'observe','project_id':'x'}
    a.attach_pet_service(s,e,default_registry())
    result=dict(tracking={'target':{'id':'animal-1','label':'cat'}},evidence_id='event')
    a.handle_event('mobile_opportunity',result)
    result['tracking']['target']['label']='dog';a.handle_event('mobile_opportunity',result)
    assert e.consider_mobile_attention.call_count==1 and s.accept_attention.call_count==2
    assert a._ensure_mobile() is None
    a.handle_event('emergency_stop',None);s.yield_attention.assert_called_with('emergency_stop')
    a.handle_event('mobile_opportunity',{'tracking':{'target':None}})
    assert s.yield_attention.call_args.args[0]=='target_lost_or_ambiguous'


def test_existing_gate_binds_frame_sensors_authority_and_single_dispatch():
    from experiments.ppal.mobile_navigation import QualifiedMobileExecutor,MobileExecutionGate
    from memory.evidence import digest
    c=Mock();c.boot_id='boot';c.activation.return_value=({'activation_key':'grant'},{'envelope':{'max_pwm':35,'max_duration':.2},'direction_envelopes':{'FORWARD':{'max_pwm':35,'max_duration':.2}}})
    c.current={'observation':{'frame':{'id':'frame'},'sensors':{}},'tracking':{'target':{'id':'animal'}},'activation':{'activation_key':'grant'}}
    c.safe.return_value=True
    base=Mock();base.pulse.return_value={'acknowledged':True,'command':{'N':3},'stop':{'sent':True,'acknowledged':True}}
    backend=QualifiedMobileExecutor(base,c,clock=lambda:1)
    p=dict(id='proposal',frame_id='frame',at=1,action='advance',speed=.15,duration=.1,reasons=[],binding=backend.binding(c.current))
    gate=MobileExecutionGate(backend=backend,clock=lambda:1,boot_id='boot',safety_check=c.safe)
    gate.lease=MotionLease('supervised_trial',2,'grant','boot')
    result=gate.execute(p)
    assert result['dispatched'] and result['executed'] is None and result['stop']['sent']
    assert not gate.execute(p)['approved'] and base.pulse.call_count==1
    p['id']='next';c.current['observation']['frame']['id']='new-frame'
    assert not gate.execute(p)['approved'] and base.pulse.call_count==1


def test_absent_safety_feed_cannot_qualify_screen_or_model(monkeypatch,tmp_path):
    from learning.mobile_safety import MobileSafetyContext
    c=MobileSafetyContext(Mock(),boot_id='boot',hardware_id='car',zone='zone',clock=lambda:1)
    c.activation=Mock(return_value=({},{}))
    o={'frame':{'authentic':True,'id':'phone-photo'}}
    assert c.bind(o,{'target':{'id':'phone-photo'}})==o
    assert c.current is None and c.failure


def test_normal_main_replay_has_attention_evaluation_and_no_activation(tmp_path,monkeypatch):
    from main import main
    from memory.evidence import EvidenceJournal
    monkeypatch.setattr(ElegooMobileBase,'connect',Mock(side_effect=AssertionError('motor connection')))
    monkeypatch.setattr('learning.cycle.gameplay_active',lambda:False)
    main(['--mobile-replay','tests/fixtures/mobile/species-loss.json','--learning-state',str(tmp_path),'--mobile-frames','4'])
    j=EvidenceJournal(tmp_path/'mobile-evidence.sqlite3')
    decisions=j.category_records('event','mobile_attention_episode');assert decisions
    assert all(not r.data['payload']['execution']['dispatched'] for r in decisions)
    assert j.category_records('event','mobile_attention_evaluation')
    assert not j.category_records('event','capability_activation')
    assert not j.category_records('event','learning_project_proposal')
    j.verify();j.close();ElegooMobileBase.connect.assert_not_called()


def qualification_control(tmp_path):
    """Fictional files test proof validation ONLY. Not car/native measurements."""
    import hashlib
    from learning.mobile_safety import REQUIRED,runtime_hash
    def write(name,value):
        p=tmp_path/name;p.write_text(json.dumps(value,sort_keys=True))
        return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    protocol=write('protocol.json',dict(firmware_sha256='a'*64,bridge_sha256='b'*64,installed_match=True,
        motion={'LEFT':1,'RIGHT':2,'FORWARD':3,'REVERSE':4},local_expiry_verified=True,
        timed_motion=dict(N=2,T_unit='milliseconds',completion_ack='tagged_ok_after_local_stop',zero_duration='forbidden')))
    report=dict(schema='charlie.mobile.qualification.v1',authentic=True,runtime_sha256=runtime_hash(),
        witness='SOFTWARE CONTROL ONLY',zone='fixture-bench',hardware_id='fictional-car',measured_utc='fixture-not-native',
        firmware_sha256='a'*64,bridge_sha256='b'*64,model_sha256='c'*64,sensor_producer_sha256='d'*64,
        protocol_artifact=protocol,envelope=dict(max_pwm=35,max_duration=.1,max_stop_seconds=.3,max_stop_m=.1,
                                               stand_off_m=1.,margin_m=.2),trials={})
    report['direction_envelopes']={d:{'max_pwm':35,'max_duration':.1} for d in ('LEFT','RIGHT','FORWARD','REVERSE')}
    for stage in REQUIRED+('proxy_follow','live_pet_follow','voluntary_decline','restart_revoke'):
        refs=[]
        for n in range(12 if stage in ('wheels_up','floor_braking') else 3):
            raw=write(f'{stage}-{n}-raw.json',{'software_control_only':True,'stage':stage,'sample':n})
            refs.append(write(f'{stage}-{n}.json',dict(stage=stage,authentic=True,passed=True,
                hardware_id='fictional-car',zone='fixture-bench',firmware_sha256='a'*64,witness='SOFTWARE CONTROL ONLY',
                direction=('LEFT','RIGHT','FORWARD','REVERSE')[n%4],utc='fixture',surface='fixture-flat',battery_v=7.5,trial_id=f'{stage}-{n}',measurements={'command_pwm':35,'requested_seconds':.1,'stop_seconds':.1,'post_stop_m':.01,'stop_uncertainty_seconds':.01,'distance_uncertainty_m':.005},raw_artifacts=[raw])))
        report['trials'][stage]=refs
    return report,write


def test_independent_measurement_validation_activation_revocation_and_restart(tmp_path):
    from learning.mobile_safety import evaluate,active_mobile
    from learning.deployment import CapabilityDeployment
    from memory.evidence import EvidenceJournal
    report,write=qualification_control(tmp_path)
    ref=write('report.json',report);j=EvidenceJournal(tmp_path/'q.sqlite3');d=CapabilityDeployment(j)
    q=evaluate(j,ref,autonomous=True)
    auth=dict(target='mobile-pet-follow',qualification_id=q.id,execution='physical',source='software control only',
        boot_id='boot',mode='qualified_autonomous',purpose='operation',hardware_id='fictional-car',zone='fixture-bench',issued_at=.5,expires_at=2.)
    d.activate_mobile(q.id,authorization=auth)
    assert active_mobile(d,now=1,boot_id='boot',hardware_id='fictional-car',zone='fixture-bench')[1]==report
    for changes in ({'now':3},{'boot_id':'restart'},{'zone':'stairs'},{'hardware_id':'other'}):
        kw=dict(now=1,boot_id='boot',hardware_id='fictional-car',zone='fixture-bench');kw.update(changes)
        with pytest.raises(ValueError):active_mobile(d,**kw)
    d.revoke_mobile(reason='test revocation',authorization={'source':'software control'})
    with pytest.raises(ValueError):active_mobile(d,now=1,boot_id='boot',hardware_id='fictional-car',zone='fixture-bench')
    with pytest.raises(ValueError):d.activate_mobile(q.id,authorization=auth)
    j.close()


@pytest.mark.parametrize('change',['stopping','raw','repeated','firmware','runtime','autonomous'])
def test_incomplete_or_changed_measurements_never_admit(change,tmp_path):
    from learning.mobile_safety import validate_report
    from pathlib import Path
    report,write=qualification_control(tmp_path)
    if change=='stopping':report['envelope']['max_stop_seconds']=.01
    if change=='raw':Path(json.loads(Path(report['trials']['pi_loss'][0]['path']).read_text())['raw_artifacts'][0]['path']).write_text('changed')
    if change=='repeated':report['trials']['explicit_stop'][2]=report['trials']['explicit_stop'][0]
    if change=='firmware':report['firmware_sha256']='e'*64
    if change=='runtime':report['runtime_sha256']='0'*64
    if change=='autonomous':report['trials'].pop('live_pet_follow')
    with pytest.raises(ValueError):validate_report(report,autonomous=True)


@pytest.mark.parametrize('stage',['explicit_stop','tcp_loss','pi_loss','local_expiry','floor_braking'])
@pytest.mark.parametrize('field,value',[('stop_seconds',-.005),('post_stop_m',-.001)])
def test_negative_measurements_cannot_be_hidden_by_uncertainty(tmp_path,stage,field,value):
    from pathlib import Path
    report,write=qualification_control(tmp_path)
    ref=report['trials'][stage][0]
    row=json.loads(Path(ref['path']).read_text())
    row['measurements'][field]=value
    report['trials'][stage][0]=write(Path(ref['path']).name,row)
    with pytest.raises(ValueError,match='stopping measurements exceed envelope'):
        validate_report(report)


def test_evaluator_wont_infer_pet_following_from_ack(tmp_path):
    from memory.evidence import EvidenceJournal
    from memory.evaluator import MemoryEvaluator
    j=EvidenceJournal(tmp_path/'e.sqlite3')
    event=j.append('event',dict(category='mobile_attention_episode',frame={'id':'fixture'},execution={'dispatched':True,'acknowledged':True}),
        episode='fixture',producer='AttentionManager',version='test',provenance={'authentic':False})
    row=MemoryEvaluator.evaluate_mobile_attention(j,event.id)
    assert row.data['payload']['outcome']=='unobserved' and row.data['payload']['learned_improvement'] is False
    assert MemoryEvaluator.evaluate_mobile_attention(j,event.id).id==row.id
    j.close()


def test_offline_cannot_enable_physical_pet_ability():
    from main import main
    with pytest.raises(ValueError,match='--offline never actuates'):main(['--offline','--pet-follow'])


def safety_control(tmp_path):
    from learning.mobile_safety import evaluate,MobileSafetyContext
    from learning.deployment import CapabilityDeployment
    from memory.evidence import EvidenceJournal
    from test_mobile_tracking_navigation import qualified
    report,write=qualification_control(tmp_path);j=EvidenceJournal(tmp_path/'feed.sqlite3');d=CapabilityDeployment(j)
    q=evaluate(j,write('report.json',report))
    d.activate_mobile(q.id,authorization=dict(target='mobile-pet-follow',qualification_id=q.id,execution='physical',source='software control only',
        boot_id='boot',mode='supervised_trial',purpose='live_pet',hardware_id='fictional-car',zone='fixture-bench',issued_at=.5,expires_at=2.))
    o,t,s=qualified();o['frame']['sha256']='e'*64;o['frame']['source_age_known']=False;o['model']=[{'sha256':'c'*64}]
    o['qualification']='unqualified'
    s.update(pet_willing=True,human_clear=True,zone_inspected=True,power_ok=True)
    feed=dict(schema='charlie.mobile.safety-snapshot.v1',boot_id='boot',hardware_id='fictional-car',zone='fixture-bench',
        frame_id=o['frame']['id'],frame_sha256='e'*64,track_id=t['target']['id'],firmware_sha256='a'*64,
        producer_sha256='d'*64,scene='live-animal-grounded',capture_timing_verified=True,capture_age_seconds=.1,
        at=1.,pan_deg=90,yaw_deg=0,sensors=s)
    path=tmp_path/'feed.json';path.write_text(json.dumps(feed))
    c=MobileSafetyContext(d,boot_id='boot',hardware_id='fictional-car',zone='fixture-bench',feed=path,clock=lambda:1.)
    return j,c,o,t,feed,path


def test_bound_feed_rechecks_changes_during_continuing_pulse(tmp_path):
    from experiments.ppal.mobile_navigation import MobileNavigator
    j,c,o,t,feed,path=safety_control(tmp_path)
    out=c.bind(o,t)
    assert out['qualification']=='native-qualified' and not o['frame']['source_age_known']
    p=MobileNavigator(clock=lambda:1).propose(out,t,out['sensors']);assert p['action']=='advance'
    assert c.safe(p)
    feed['sensors']['human_clear']=False;path.write_text(json.dumps(feed))
    assert not c.safe(p)
    j.close()


@pytest.mark.parametrize('change',['screen','frame','pose','stale','welfare','producer','model'])
def test_unqualified_scene_pose_or_feed_never_admits(change,tmp_path):
    j,c,o,t,feed,path=safety_control(tmp_path)
    if change=='screen':feed['scene']='phone-photo'
    if change=='frame':feed['frame_sha256']='f'*64
    if change=='pose':feed['yaw_deg']=40
    if change=='stale':feed['at']=0
    if change=='welfare':feed['sensors'].pop('pet_willing')
    if change=='producer':feed['producer_sha256']='0'*64
    if change=='model':o['model']=[{'sha256':'0'*64}]
    path.write_text(json.dumps(feed))
    assert c.bind(o,t)['qualification']=='unqualified' and c.current is None
    j.close()


def test_existing_motor_owner_excludes_second_client_and_releases(monkeypatch):
    from uuid import uuid4
    sock=Mock();sock.recv.return_value=b''
    monkeypatch.setattr('hardware.elegoo_mobile.socket.create_connection',Mock(return_value=sock))
    key=uuid4().hex;a=ElegooMobileBase(host=key);b=ElegooMobileBase(host=key)
    a.connect()
    with pytest.raises(BlockingIOError):b.connect()
    a.close();b.connect();b.close()


def test_existing_camera_lease_excludes_second_and_cleans_failed_open(monkeypatch):
    from hardware.elegoo_camera import _ElegooCameraDevice as ElegooCamera
    from uuid import uuid4
    response=Mock();response.read.return_value=b''
    monkeypatch.setattr('hardware.elegoo_camera.urllib.request.urlopen',Mock(return_value=response))
    key='http://fixture-'+uuid4().hex+'/stream';a=ElegooCamera(key);b=ElegooCamera(key)
    a.open()
    with pytest.raises(BlockingIOError):b.open()
    a.close();b.open();b.close()
    monkeypatch.setattr('hardware.elegoo_camera.urllib.request.urlopen',Mock(side_effect=OSError('fixture')))
    for _ in range(2):
        with pytest.raises(OSError,match='fixture'):a.open()
    a.close()


def test_supervised_calibration_dry_run_has_no_device_and_cannot_skip_staging(tmp_path):
    from learning.mobile_safety import calibration_trial,runtime_hash
    from memory.evidence import EvidenceJournal
    report,write=qualification_control(tmp_path)
    protocol=json.loads(__import__('pathlib').Path(report['protocol_artifact']['path']).read_text())
    protocol['local_expiry_source_verified']=True
    trial=dict(schema='charlie.mobile.calibration-trial.v1',runtime_sha256=runtime_hash(),stage='wheels_up',
        witness='software control only',hardware_id='fictional-car',zone='fixture-bench',supervised=True,
        power_cutoff_accessible=True,no_animals=True,no_people_in_path=True,isolated_flat_test_area=True,wheels_clear=True,
        firmware_sha256='a'*64,bridge_sha256='b'*64,protocol_artifact=write('cal-protocol.json',protocol),direction='FORWARD',pwm=25,seconds=.1)
    j=EvidenceJournal(tmp_path/'cal.sqlite3');base=Mock(side_effect=AssertionError('no hardware'))
    result=calibration_trial(j,write('trial.json',trial),base_factory=base)
    assert result['executed'] is None and 'no device' in result['disposition'];base.assert_not_called()
    trial['stage']='empty_floor'
    with pytest.raises((KeyError,ValueError)):calibration_trial(j,write('floor.json',trial),execute=True,base_factory=base)
    base.assert_not_called();j.close()


def test_uncertain_stop_latches_executor_and_prevents_next_start():
    from experiments.ppal.mobile_navigation import QualifiedMobileExecutor,MobileExecutionGate
    c=Mock();c.boot_id='boot'
    c.activation.return_value=({'activation_key':'grant'},{'direction_envelopes':{'FORWARD':{'max_pwm':35,'max_duration':.1}}})
    c.current={'observation':{'frame':{'id':'frame'},'sensors':{}},'tracking':{'target':{'id':'animal'}},'activation':{'activation_key':'grant'}}
    c.safe.return_value=True
    base=Mock();base.pulse.return_value={'acknowledged':True,'command':{'N':3},'stop':{'sent':None,'acknowledged':False}}
    backend=QualifiedMobileExecutor(base,c,clock=lambda:1)
    gate=MobileExecutionGate(backend=backend,clock=lambda:1,boot_id='boot',safety_check=c.safe)
    gate.lease=MotionLease('supervised_trial',2,'grant','boot')
    p=dict(id='one',frame_id='frame',at=1,action='advance',speed=.15,duration=.1,reasons=[],binding=backend.binding(c.current))
    first=gate.execute(p)
    assert first['dispatched'] and first['physical_uncertainty'] and 'stop_unconfirmed' in first['rejected']
    p['id']='two';assert not gate.execute(p)['approved']
    assert base.pulse.call_count==1


def test_proxy_authority_cannot_admit_a_live_pet(tmp_path):
    j,c,o,t,feed,path=safety_control(tmp_path)
    from learning.deployment import CapabilityDeployment
    d=CapabilityDeployment(j);a=d.active('mobile-pet-follow')['authorization'];a=dict(a,purpose='proxy')
    d.activate_mobile(a['qualification_id'],authorization=a)
    assert c.bind(o,t)['qualification']=='unqualified'
    feed['scene']='proxy-grounded';path.write_text(json.dumps(feed))
    out=c.bind(o,t)
    assert out['grounded_proxy'] and not out['grounded_animal']
    j.close()


def test_uncertain_stop_is_not_cleared_by_later_acknowledgement():
    from experiments.ppal.mobile_navigation import QualifiedMobileExecutor, MobileExecutionGate
    c=Mock(); c.boot_id='boot'; c.safe.return_value=True
    c.activation.return_value=({'activation_key':'grant'},{'direction_envelopes':{'FORWARD':{'max_pwm':35,'max_duration':.1}}})
    c.current={'observation':{'frame':{'id':'frame'},'sensors':{}},'tracking':{'target':{'id':'animal'}},'activation':{'activation_key':'grant'}}
    base=Mock()
    base.pulse.return_value={'acknowledged':True,'stop':{'sent':None,'acknowledged':False}}
    base.stop_verified.return_value={'sent':True,'acknowledged':True,'physically_stopped':None}
    executor=QualifiedMobileExecutor(base,c,clock=lambda:1)
    gate=MobileExecutionGate(backend=executor,clock=lambda:1,boot_id='boot',safety_check=c.safe)
    gate.lease=MotionLease('supervised_trial',2,'grant','boot')
    proposal=dict(id='one',frame_id='frame',at=1,action='advance',speed=.15,duration=.1,reasons=[],binding=executor.binding(c.current))
    assert gate.execute(proposal)['physical_uncertainty']
    executor.stop()  # An ACK is not physical proof and does not clear the fault.
    proposal['id']='two'
    assert not gate.execute(proposal)['approved']
    assert base.pulse.call_count==1


def test_ambiguous_start_exception_latches_even_if_later_stop_acks():
    from experiments.ppal.mobile_navigation import QualifiedMobileExecutor, MobileExecutionGate
    c=Mock(); c.boot_id='boot'; c.safe.return_value=True
    c.activation.return_value=({'activation_key':'grant'},{'direction_envelopes':{'FORWARD':{'max_pwm':35,'max_duration':.1}}})
    c.current={'observation':{'frame':{'id':'frame'},'sensors':{}},'tracking':{'target':{'id':'animal'}},'activation':{'activation_key':'grant'}}
    base=Mock(); base.pulse.side_effect=TimeoutError('ambiguous wire delivery')
    base.stop_verified.return_value={'sent':True,'acknowledged':True,'physically_stopped':None}
    executor=QualifiedMobileExecutor(base,c,clock=lambda:1)
    gate=MobileExecutionGate(backend=executor,clock=lambda:1,boot_id='boot',safety_check=c.safe)
    gate.lease=MotionLease('supervised_trial',2,'grant','boot')
    proposal=dict(id='one',frame_id='frame',at=1,action='advance',speed=.15,duration=.1,reasons=[],binding=executor.binding(c.current))
    assert gate.execute(proposal)['physical_uncertainty']
    proposal['id']='two'
    assert not gate.execute(proposal)['approved']
    assert base.pulse.call_count==1


def test_pet_feed_capture_age_includes_time_since_snapshot(tmp_path):
    j,c,o,t,feed,path=safety_control(tmp_path)
    feed['at']=.8;feed['capture_age_seconds']=.4
    path.write_text(json.dumps(feed))
    assert c.bind(o,t)['qualification']=='unqualified' and c.current is None
    j.close()


def test_continuing_pet_pulse_rechecks_total_capture_age(tmp_path):
    from experiments.ppal.mobile_navigation import MobileNavigator
    j,c,o,t,feed,path=safety_control(tmp_path)
    feed['capture_age_seconds']=.4;path.write_text(json.dumps(feed))
    now=[1.];c.clock=lambda:now[0]
    out=c.bind(o,t)
    proposal=MobileNavigator(clock=lambda:now[0]).propose(out,t,out['sensors'])
    assert proposal['action']=='advance' and c.safe(proposal)
    now[0]=1.11
    assert not c.safe(proposal)
    j.close()
