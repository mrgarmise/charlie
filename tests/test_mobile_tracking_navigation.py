from dataclasses import replace
from unittest.mock import Mock
import pytest
from vision.mobile_tracking import PetTracker, emit_attention
from stimulus.bus import StimulusBus
from experiments.ppal.mobile_navigation import MobileNavigator, MobileExecutionGate, MotionLease


def packet(at=1, boxes=([1,1,10,15],),label='cat'):
    return dict(frame=dict(id=str(at),received_at=at,geometry=[40,30],source_age_known=False,
                           authentic=False,pan_deg=None),objects=[dict(label=label,box=b,confidence=.9) for b in boxes],
                depth=dict(kind='relative'),qualification='unqualified')


def test_tracking_confirmation_occlusion_reacquire_no_switch():
    t=PetTracker()
    assert t.update(packet())['target'] is None
    first=t.update(packet(1.2))['target']; assert first
    assert t.update(packet(1.4,[]))['target'] is None
    assert t.update(packet(1.5,[[25,1,39,15]]))['target'] is None
    assert t.update(packet(1.6))['target']['id']==first['id']
    assert t.update(packet(3,[]))['tracks']==[]
    assert t.update(packet(3.2))['target'] is None
    assert t.update(packet(3.4))['target']['id']!=first['id']


def test_crossing_ambiguity_abstains():
    t=PetTracker(confirmations=1)
    t.update(packet(1,[[1,1,15,15],[20,1,34,15]]))
    r=t.update(packet(1.1,[[10,1,25,15]]))
    assert r['target'] is None and any(x['ambiguous'] for x in r['tracks'])


def test_low_score_species_and_reorder():
    t=PetTracker(confirmations=1)
    p=packet();p['objects'][0]['confidence']=.1
    assert t.update(p)['target'] is None
    assert t.update(packet(1.1,label='person'))['target'] is None
    with pytest.raises(ValueError):t.update(packet(1))


def test_unarmed_attention_never_emits_legacy_actuator_events():
    b=StimulusBus();emit_attention(b,dict(target_lost=True),packet()['frame'])
    assert [x[0] for x in b.get_all()]==['mobile_observation']


def qualified():
    p=packet();p['frame'].update(source_age_known=True,authentic=True,pan_deg=90)
    p.update(qualification='native-qualified',depth=dict(kind='relative',valid=True,anomaly=False))
    target=dict(id='fixture-target',box=[15,1,25,15],observed=True,ambiguous=False)
    sensors={k:dict(valid=True,source='car-qualified',at=1,clear=True,meters=2) for k in
             ('ultrasonic','target_range','yaw','heartbeat','floor_clearance','hazard_map','blind_spot')}
    sensors['target_range']['track_id']='fixture-target'
    sensors['yaw']['degrees']=0
    sensors['pet_distress']=False
    return p,dict(target=target),sensors


def test_unknown_real_world_conditions_veto_motion():
    n=MobileNavigator(clock=lambda:1)
    p=packet();r=n.propose(p,dict(target=None),{})
    assert r['action']=='stop' and 'unknown_capture_age' in r['reasons']
    gate=MobileExecutionGate(clock=lambda:1)
    assert gate.execute(r)['dispatched'] is False


@pytest.mark.parametrize('sensor',['target_range','ultrasonic','yaw','heartbeat','floor_clearance','hazard_map','blind_spot'])
def test_missing_and_stale_sensor_each_veto(sensor):
    p,t,s=qualified();s[sensor]['at']=0
    r=MobileNavigator(clock=lambda:1).propose(p,t,s)
    assert r['action']=='stop' and f'{sensor}_unverified' in r['reasons']


@pytest.mark.parametrize('mutation',['pan','range','pet','depth','stale','fixture','blind','loss'])
def test_hazard_injection(mutation):
    p,t,s=qualified()
    if mutation=='pan':p['frame']['pan_deg']=40
    if mutation=='range':s['ultrasonic']['meters']=.5
    if mutation=='pet':s['pet_distress']=True
    if mutation=='depth':p['depth']['anomaly']=True
    if mutation=='stale':p['frame']['received_at']=0
    if mutation=='fixture':p['frame']['authentic']=False
    if mutation=='blind':s['blind_spot']['clear']=False
    if mutation=='loss':t['target']=None
    assert MobileNavigator(clock=lambda:1).propose(p,t,s)['action']=='stop'


def test_proposal_not_authority_and_ack_not_consequence():
    p,t,s=qualified();r=MobileNavigator(clock=lambda:1).propose(p,t,s)
    assert r['action']=='advance'
    backend=Mock(car_local_qualified=True);backend.execute_bounded.return_value=dict(acknowledged=True)
    gate=MobileExecutionGate(backend=backend,clock=lambda:1,boot_id='boot',safety_check=lambda p:True)
    assert not gate.execute(r)['approved'];backend.execute_bounded.assert_not_called()
    gate.lease=MotionLease('supervised_trial',2,'test-fixture-only','boot')
    result=gate.execute(r)
    assert result['acknowledged'] and result['executed'] is None and result['observed_consequence'] is None
    gate.lease=replace(gate.lease,expires_at=.9)
    assert not gate.execute(r)['approved'];backend.stop.assert_called_once()
    # Restart loses the authority even if someone supplies an old lease.
    gate2=MobileExecutionGate(backend=backend,clock=lambda:1,boot_id='new')
    gate2.lease=MotionLease('supervised_trial',2,'test-fixture-only','boot')
    assert not gate2.execute(r)['approved']


def test_controller_error_stops_and_unbounded_proposal_rejected():
    p,t,s=qualified();r=MobileNavigator(clock=lambda:1).propose(p,t,s)
    backend=Mock(car_local_qualified=True);backend.execute_bounded.side_effect=RuntimeError()
    gate=MobileExecutionGate(backend=backend,clock=lambda:1,boot_id='boot',safety_check=lambda p:True)
    gate.lease=MotionLease('supervised_trial',2,'fixture','boot')
    assert gate.execute(r)['rejected']==['controller_error'];backend.stop.assert_called_once()
    r['duration']=10
    assert 'duration_limit' in gate.execute(r)['rejected']


@pytest.mark.parametrize('bad',[None,'bad',float('nan'),float('inf')])
def test_invalid_telemetry_timestamps_fail_closed(bad):
    p,t,s=qualified();s['ultrasonic']['at']=bad
    assert MobileNavigator(clock=lambda:1).propose(p,t,s)['action']=='stop'


def test_target_range_must_refer_to_selected_pet():
    p,t,s=qualified();s['target_range']['track_id']='another-pet'
    assert MobileNavigator(clock=lambda:1).propose(p,t,s)['action']=='stop'
