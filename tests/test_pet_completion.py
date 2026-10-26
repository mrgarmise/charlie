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
    return c.pulse(kwargs.pop('direction','FORWARD'),pwm=kwargs.pop('pwm',30),seconds=kwargs.pop('seconds',.1),
        lease=kwargs.pop('lease',MotionLease('supervised_trial',2,'fixture','boot')),boot_id='boot',
        envelope={'max_pwm':35,'max_duration':.2},safety_check=kwargs.pop('safety_check',lambda:True),
        clock=lambda:now[0],wait=lambda dt:now.__setitem__(0,now[0]+dt),**kwargs)


@pytest.mark.parametrize('direction,d1',[('LEFT',1),('RIGHT',2),('FORWARD',3),('REVERSE',4)])
def test_bounded_directions_and_stop(direction,d1):
    c=car_fixture();result=pulse(c,direction=direction)
    payload=c._send.call_args.args[0]
    assert payload['D1']==d1 and payload['T']==100 and c._send.call_args.kwargs['retry'] is False
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
    assert c.stop_verified()==dict(sent=False,acknowledged=False,physically_stopped=None,error='ConnectionError')
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
    c=Mock();c.boot_id='boot';c.activation.return_value=({'activation_key':'grant'},{'envelope':{'max_pwm':35,'max_duration':.2}})
    c.current={'observation':{'frame':{'id':'frame'},'sensors':{}},'tracking':{'target':{'id':'animal'}},'activation':{'activation_key':'grant'}}
    c.safe.return_value=True
    base=Mock();base.pulse.return_value={'acknowledged':True,'command':{'N':3},'stop':{'sent':True}}
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
