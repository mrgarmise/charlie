"""Controlled interface evidence; none of these fixtures is Robotron learning."""
from dataclasses import replace
import json
import pytest

from experiments.ppal.models import WorldState, Position, Object
from experiments.ppal.forebrain import Forebrain
from experiments.ppal.hindbrain import Hindbrain
from experiments.ppal.qualified_policy import load_policy, VERSION, DECISION_ADAPTER
from learning.deployment import CapabilityDeployment
from learning.datasets import sha
from learning.cycle import investigate
from learning.meditation import qualify_corpus, shadow
from memory.evidence import digest
from test_ala_cycle import make
from test_meditation_candidate import finding, corpus


def motion_policy(tmp_path):
    ds,g=make(tmp_path);finding(ds,tmp_path)
    source=corpus(ds,tmp_path);document=json.loads(source.read_text())
    document['provenance_kind']='simulated-controlled-trajectories'
    source.write_text(json.dumps(document));qualify_corpus(ds,source)
    row=investigate(ds,g,diagnostics_only=True,max_jobs=1)['results'][0]
    proposal=row['result']['deployment_proposal'];s=shadow(ds.journal,proposal)
    deployment=CapabilityDeployment(ds.journal)
    deployment.activate(proposal,target='offline-shadow',shadow_id=s.id,
        authorization=dict(target='offline-shadow',proposal_id=proposal,
                           source='controlled software acceptance',execution='offline'))
    path=tmp_path/'ppal-policy.json';deployment.export_policy('offline-shadow',path)
    return ds,g,deployment,path


def parameter_policy(tmp_path, parameters):
    """Explicit fabricated contract to isolate interface, NOT learner success.

    Reuse an independently exercised fixture investigation identity; never
    pretend these manually selected values were invented by Reflection.
    """
    ds,g,deployment,path=motion_policy(tmp_path)
    original=deployment.active('offline-shadow')
    p=ds.journal.get(original['proposal_id']).data['payload']
    previous=ds.journal.get(p['evaluation_id']).data['payload']['candidate']
    spec=dict(adapter=DECISION_ADAPTER,parameters=parameters)
    checkpoint=tmp_path/'parameters.json';checkpoint.write_text(json.dumps(spec))
    candidate=dict(previous,identifier=digest(spec),checkpoint=str(checkpoint),
                   checkpoint_sha256=sha(checkpoint),spec=spec)
    contract=dict(eligible=True,policy_version=VERSION,domains=sorted(parameters),spec_sha256=digest(spec))
    measured=ds.journal.append('observation',dict(category='offline_model_evaluation',candidate=candidate,
        metrics=dict(improved=True,fresh_final_evidence=True,independence_groups=['fixture-1','fixture-2','fixture-3'],
                     decision_contract=contract,provenance_kind='simulated-interface-fixture')),
        episode='perceptual-learning',producer='ModelFoundry',version='explicit-fixture')
    proposal=ds.journal.append('event',dict(category='model_deployment_proposal',eligible=True,target='ppal-policy',
        candidate_id=candidate['identifier'],evaluation_id=measured.id,prediction_id=p['prediction_id'],contract=contract),
        episode='perceptual-learning',producer='Reflection',version='explicit-fixture')
    s=ds.journal.append('observation',dict(category='decision_policy_shadow',passed=True,proposal_id=proposal.id,
        candidate_id=candidate['identifier'],checkpoint_sha256=candidate['checkpoint_sha256'],controller_writes=0,
        limitation='constructed acceptance contract; not scientific or score evidence'),episode='perceptual-learning',
        producer='controlled-policy-adapter',version='explicit-fixture')
    deployment.activate(proposal.id,target='ppal-policy',shadow_id=s.id,
        authorization=dict(target='ppal-policy',proposal_id=proposal.id,source='explicit interface fixture',
                           execution='offline',allowed_domains=sorted(parameters)))
    deployment.export_policy('ppal-policy',path)
    return ds,g,deployment,path


def decide(world, policy=None, shot_model=None, timestamp=0):
    f,h=Forebrain(policy=policy),Hindbrain(policy=policy,shot_model=shot_model)
    goal=f.update(world);intent,action=h.decide(world,goal,timestamp=timestamp)
    return goal,intent,action,dict(forebrain=f.last_reason,hindbrain=h.last_decision)


def world():
    return WorldState(0,Position(50,50),(Object('human',Position(70,70)),),())


def test_qualified_motion_restart_rollback_and_charlie_fixture_origin(tmp_path):
    ds,g,d,path=motion_policy(tmp_path)
    payload=json.loads(path.read_text())['payload']
    assert payload['investigation_id'] and payload['source_evidence'] and payload['evaluation_id']
    assert payload['provenance_kind']=='simulated-controlled-trajectories'
    assert payload['score_improvement']=='UNKNOWN'
    baseline=WorldState(1,Position(50,50),(Object('human',Position(53,70)),),())
    policy=load_policy(path);f,h=Forebrain(policy),Hindbrain(policy=policy)
    first=replace(baseline,tick=0,targets=(Object('human',Position(51,70)),))
    h.decide(first,f.update(first),timestamp=0)
    _,candidate=h.decide(baseline,f.update(baseline),timestamp=.15)
    assert decide(baseline)[2].move=='S' and candidate.move=='SE'
    assert h.last_decision['policy']['applied_domains']==['action_effect_prediction']
    assert load_policy(path).identity==policy.identity
    with pytest.raises(ValueError,match='physical'):load_policy(path,physical=True)
    d.rollback('offline-shadow',reason='controlled rollback',to_baseline=True,
               authorization=dict(target='offline-shadow',source='software acceptance'))
    with pytest.raises(ValueError,match='current qualified'):load_policy(path)
    assert decide(baseline)[2].move=='S'


def test_strategic_influence_and_immediate_override(tmp_path):
    ds,g,d,path=parameter_policy(tmp_path,{'goal_preference':{'rescue':-1,'survive':1}})
    policy=load_policy(path)
    assert decide(world())[0].kind=='rescue'
    goal,intent,action,trace=decide(world(),policy)
    assert goal.kind=='survive' and trace['forebrain']['policy']['applied_domains']==['goal_preference']
    threat=replace(world(),threats=(Object('enemy',Position(52,50)),))
    assert decide(threat)[1:3]==decide(threat,policy)[1:3]
    assert decide(threat,policy)[3]['hindbrain']['policy']['disposition']=='immediate override'
    unsafe=replace(world(),observation_safe=False)
    assert decide(unsafe,policy)[2].move=='STAY' and decide(unsafe,policy)[2].fire=='NONE'
    assert 'unsafe' in decide(unsafe,policy)[2].reason
    assert policy.identity['provenance_kind']=='simulated-interface-fixture'


def test_tactical_fire_shot_model_and_deterministic_reason(tmp_path):
    ds,g,d,path=parameter_policy(tmp_path,{'firing_behavior':{'deadband':0}})
    w=replace(world(),threats=(Object('enemy',Position(52,61)),))
    policy=load_policy(path)
    assert decide(w)[2].fire=='S' and decide(w,policy)[2].fire=='SE'
    class Miss:
        def likely_hit(self,*args):return False
    assert decide(w,policy,Miss())[2].move=='SE'
    assert decide(w,policy)[3]==decide(w,load_policy(path))[3]
    assert decide(w,policy)[3]['hindbrain']['policy']['evaluation_id']


def test_missing_corrupt_version_unqualified_and_domain_rejected(tmp_path):
    ds,g,d,path=motion_policy(tmp_path)
    with pytest.raises(OSError):load_policy(tmp_path/'absent')
    document=json.loads(path.read_text());path.write_text('{}')
    with pytest.raises(KeyError):load_policy(path)
    document['payload']['version']='unsupported';document['sha256']=digest(document['payload'])
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError,match='version'):load_policy(path)
    document['payload']['version']=VERSION;document['payload']['qualification']='unqualified'
    document['sha256']=digest(document['payload']);path.write_text(json.dumps(document))
    with pytest.raises(ValueError,match='current qualified'):load_policy(path)
    from experiments.ppal.qualified_policy import validate_spec
    with pytest.raises(ValueError):validate_spec(dict(adapter=DECISION_ADAPTER,parameters={'self_identity':{'confidence':1}}))


def test_runtime_has_no_learning_journal_or_controller_calls(tmp_path, monkeypatch):
    ds,g,d,path=parameter_policy(tmp_path,{'positioning_preference':{'E':1}})
    policy=load_policy(path)
    def forbidden(*args,**kwargs):raise AssertionError('forbidden in realtime decision')
    from memory.evidence import EvidenceJournal
    from memory.learning_projects import LearningExecutive
    from experiments.ppal import meditate_robotron
    from experiments.ppal.arcade_transport import ArcadeController
    monkeypatch.setattr(EvidenceJournal,'records',forbidden)
    monkeypatch.setattr(LearningExecutive,'develop',forbidden)
    monkeypatch.setattr(meditate_robotron,'reconstruct_once',forbidden)
    monkeypatch.setattr(ArcadeController,'execute',forbidden)
    empty=replace(world(),targets=())
    assert decide(empty,policy)[2].move=='E'
    assert decide(empty)[2].move!='E'


def test_latency_and_normal_entry_point_persistence(tmp_path):
    import subprocess,sys,os
    ds,g,d,path=parameter_policy(tmp_path,{'goal_preference':{'rescue':-1,'survive':1}})
    from experiments.ppal.benchmark_decisions import measure
    report=measure(load_policy(path),iterations=100)
    assert report['baseline']['samples']==100 and report['policy_enabled']['samples']==100
    assert report['controller_writes']==0 and report['median_delta_ns'] is not None
    for restart in range(2):
        log=tmp_path/f'normal-{restart}.jsonl'
        process=subprocess.run([sys.executable,'-m','experiments.ppal.run_closed_loop',
            '--mode','synthetic','--max-steps','3','--learned-policy',str(path),'--log',str(log)],
            capture_output=True,text=True,env=os.environ.copy())
        assert process.returncode==0,process.stderr
        records=[json.loads(line) for line in log.read_text().splitlines()]
        assert records and all(r['source']=='rendered_simulator' for r in records)
        assert all(r['goal']['kind']=='survive' for r in records)
        assert records[0]['decision_provenance']['forebrain']['policy']['activation_key']==load_policy(path).identity['activation_key']


def test_motion_policy_preserves_observed_immediate_threat_and_unresolved_space(tmp_path):
    ds,g,d,path=motion_policy(tmp_path);policy=load_policy(path)
    first=world();f,h=Forebrain(policy),Hindbrain(policy=policy)
    h.decide(first,f.update(first),timestamp=0)
    danger=replace(first,tick=1,threats=(Object('enemy',Position(52,50)),))
    intent,action=h.decide(danger,f.update(danger),timestamp=.15)
    assert intent.kind=='evade' and action.move=='W'
    assert h.last_decision['policy']['applied_domains']==[]
    occupied=replace(first,tick=2,unresolved=(Object('unknown',Position(55.66,55.66)),))
    assert h.decide(occupied,f.update(occupied),timestamp=.3)[1].move=='STAY'


def test_rejected_evaluation_and_unauthorized_domain_cannot_activate(tmp_path):
    ds,g,d,path=parameter_policy(tmp_path,{'goal_preference':{'survive':1}})
    active=d.active('ppal-policy')
    with pytest.raises(ValueError,match='domain outside authorization'):
        d.activate(active['proposal_id'],target='ppal-policy',shadow_id=active['shadow_id'],
            authorization=dict(target='ppal-policy',proposal_id=active['proposal_id'],source='fixture',
                               execution='offline',allowed_domains=[]))
    proposal=ds.journal.get(active['proposal_id']).data['payload']
    evaluation=ds.journal.get(proposal['evaluation_id']).data['payload']
    failed=ds.journal.append('observation',dict(evaluation,metrics=dict(evaluation['metrics'],improved=False)),
        episode='perceptual-learning',producer='ModelFoundry',version='explicit-rejection-fixture')
    rejected=ds.journal.append('event',dict(proposal,evaluation_id=failed.id,eligible=False),
        episode='perceptual-learning',producer='Reflection',version='explicit-rejection-fixture')
    with pytest.raises(ValueError,match='supported independent'):
        d.activate(rejected.id,target='ppal-policy',shadow_id=active['shadow_id'],
            authorization=dict(active['authorization'],proposal_id=rejected.id))
