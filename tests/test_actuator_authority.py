"""Synthetic evidence exercises denial and journal wiring; not qualification."""
import hashlib
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from learning.actuator_safety import STAGES, ActuatorSafetyAuthority, evaluate_actuator, validate_actuator_report
from learning.mobile_safety import runtime_hash
from learning.deployment import CapabilityDeployment
from memory.evidence import EvidenceJournal
from motion.elegoo_executor import ActuatorRequest


def write(path, value):
    raw=json.dumps(value,sort_keys=True).encode();path.write_bytes(raw)
    return {'path':str(path),'sha256':hashlib.sha256(raw).hexdigest()}


def fixture_report(tmp_path, group):
    firmware='a'*64; bridge='b'*64
    protocol=dict(firmware_sha256=firmware,bridge_sha256=bridge,installed_match=True,
        timed_motion=dict(N=2,T_unit='milliseconds',completion_ack='tagged_ok_after_local_stop',zero_duration='forbidden'),
        local_expiry_verified=True,motion={'LEFT':1,'RIGHT':2,'FORWARD':3,'REVERSE':4},
        pan={'N':5,'D1':1},pan_stop_verified=True,ultrasonic_read_only=True,ultrasonic={'N':21,'D1':2},
        yaw_read_only=True,yaw={'N':24})
    envelope = dict(directions=['LEFT','RIGHT'],max_pwm=20,max_duration=.1,max_stop_seconds=.4,max_stop_m=.3,max_stop_degrees=3,
                    min_degrees=20,max_degrees=160,max_settle_seconds=.3,position_command_verified=True)
    report=dict(schema='charlie.actuator.qualification.v1',group=group,authentic=True,runtime_sha256=runtime_hash(),
        witness='synthetic',hardware_id='fixture',zone='fixture',measured_utc='fixture',
        firmware_sha256=firmware,bridge_sha256=bridge,sensor_producer_sha256='c'*64,
        protocol_artifact=write(tmp_path/'protocol.json',protocol),envelope=envelope,trials={})
    for stage in STAGES[group]:
        refs=[]
        directions=['LEFT']*3+['RIGHT']*3 if group=='chassis' and stage in ('wheels_up','floor_braking') else ['LEFT']*3
        for i,direction in enumerate(directions):
            name=f'{stage}-{i}';raw=tmp_path/(name+'.raw');raw.write_text('synthetic '+name)
            measurement=dict(stop_seconds=.1,uncertainty_seconds=.01,post_stop_m=.1,uncertainty_m=.01,post_stop_degrees=1,uncertainty_degrees=.1,command_pwm=20,requested_seconds=.1,
                             min_degrees=20,max_degrees=160,settle_seconds=.1)
            trial=dict(stage=stage,group=group,authentic=True,passed=True,hardware_id='fixture',zone='fixture',
                firmware_sha256=firmware,witness='synthetic',utc='fixture',trial_id=name,direction=direction,
                measurements=measurement,raw_artifacts=[{'path':str(raw),'sha256':hashlib.sha256(raw.read_bytes()).hexdigest()}])
            refs.append(write(tmp_path/(name+'.json'),trial))
        report['trials'][stage]=refs
    return report


@pytest.mark.parametrize('group',['chassis','camera-pan','telemetry'])
def test_group_qualification_requires_independent_complete_records(tmp_path,group):
    report=fixture_report(tmp_path,group)
    assert validate_actuator_report(report)==report
    broken=deepcopy(report);broken['trials'][STAGES[group][0]]=broken['trials'][STAGES[group][0]][:2]
    with pytest.raises(ValueError):validate_actuator_report(broken)
    changed=deepcopy(report);changed['runtime_sha256']='bad'
    with pytest.raises(ValueError):validate_actuator_report(changed)
    path=report['trials'][STAGES[group][0]][0]['path'];open(path,'a').write('changed')
    with pytest.raises(ValueError):validate_actuator_report(report)


def test_activation_is_group_specific_and_revocation_is_sticky(tmp_path):
    report=fixture_report(tmp_path,'camera-pan');ref=write(tmp_path/'report.json',report)
    journal=EvidenceJournal(tmp_path/'journal.db');qualification=evaluate_actuator(journal,ref)
    deployment=CapabilityDeployment(journal)
    auth=dict(target='elegoo-camera-pan',qualification_id=qualification.id,source='fixture-operator',
        boot_id='boot',hardware_id='fixture',zone='fixture',mode='supervised_trial',execution='physical',issued_at=1.,expires_at=20.)
    bad=dict(auth,target='elegoo-chassis')
    with pytest.raises(ValueError):deployment.activate_actuator(qualification.id,authorization=bad)
    deployment.activate_actuator(qualification.id,authorization=auth)
    authority=ActuatorSafetyAuthority(deployment,hardware_id='fixture',zone='fixture',clock=lambda:10.)
    assert authority.active('camera-pan','boot')[1]==report
    with pytest.raises(PermissionError):authority.active('chassis','boot')
    with pytest.raises(PermissionError):authority.active('camera-pan','other-boot')
    deployment.revoke_actuator('elegoo-camera-pan',reason='fixture',authorization={'source':'fixture'})
    with pytest.raises(PermissionError):authority.active('camera-pan','boot')
    with pytest.raises(ValueError):deployment.activate_actuator(qualification.id,authorization=auth)
    journal.close()


def test_frame_and_independent_feed_are_rechecked_for_each_request(tmp_path):
    report=fixture_report(tmp_path,'camera-pan');ref=write(tmp_path/'report.json',report)
    journal=EvidenceJournal(tmp_path/'journal.db');row=evaluate_actuator(journal,ref);deployment=CapabilityDeployment(journal)
    deployment.activate_actuator(row.id,authorization=dict(target='elegoo-camera-pan',qualification_id=row.id,
        source='fixture',boot_id='boot',hardware_id='fixture',zone='fixture',mode='supervised_trial',
        execution='physical',issued_at=1.,expires_at=20.))
    feed=dict(schema='charlie.actuator.safety.v1',boot_id='boot',hardware_id='fixture',zone='fixture',
        source='elegoo-v4',observation_id='f',firmware_sha256='a'*64,producer_sha256='c'*64,at=10.,
        capture_timing_verified=True,capture_age_seconds=.1,frame_sha256='pixels',power_ok=True,human_clear=True,
        animal_clear=True,stop_available=True,zone_inspected=True,pan_clear=True,pan_pose_known=True,pan_degrees=90.)
    path=tmp_path/'feed.json';write(path,feed)
    authority=ActuatorSafetyAuthority(deployment,hardware_id='fixture',zone='fixture',feed=path,clock=lambda:10.)
    request=ActuatorRequest('r','face','camera-pan','pan',10.,'elegoo-v4','f',{'degrees':100,'expected_pan_degrees':90})
    frame=SimpleNamespace(authentic=True,metadata=lambda:{'sha256':'pixels'})
    grant=authority.admit(request,frame,boot_id='boot');assert authority.safe(request,grant)
    feed['human_clear']=False;write(path,feed)
    assert not authority.safe(request,grant)
    with pytest.raises(PermissionError):authority.admit(request,frame,boot_id='boot')
    journal.close()


def test_feed_capture_age_includes_time_since_feed_was_written(tmp_path):
    report=fixture_report(tmp_path,'camera-pan');ref=write(tmp_path/'report.json',report)
    journal=EvidenceJournal(tmp_path/'journal.db');row=evaluate_actuator(journal,ref);deployment=CapabilityDeployment(journal)
    deployment.activate_actuator(row.id,authorization=dict(target='elegoo-camera-pan',qualification_id=row.id,
        source='fixture',boot_id='boot',hardware_id='fixture',zone='fixture',mode='supervised_trial',
        execution='physical',issued_at=1.,expires_at=20.))
    feed=dict(schema='charlie.actuator.safety.v1',boot_id='boot',hardware_id='fixture',zone='fixture',
        source='elegoo-v4',observation_id='f',firmware_sha256='a'*64,producer_sha256='c'*64,at=9.85,
        capture_timing_verified=True,capture_age_seconds=.2,frame_sha256='pixels',power_ok=True,human_clear=True,
        animal_clear=True,stop_available=True,zone_inspected=True,pan_clear=True,pan_pose_known=True,pan_degrees=90.)
    path=tmp_path/'feed.json';write(path,feed)
    authority=ActuatorSafetyAuthority(deployment,hardware_id='fixture',zone='fixture',feed=path,clock=lambda:10.)
    request=ActuatorRequest('r','face','camera-pan','pan',10.,'elegoo-v4','f',{'degrees':100,'expected_pan_degrees':90})
    with pytest.raises(PermissionError):authority.admit(request,SimpleNamespace(authentic=True,metadata=lambda:{'sha256':'pixels'}),boot_id='boot')
    journal.close()
