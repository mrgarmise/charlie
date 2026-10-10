"""Synthetic lifecycle fixtures; not authentic experience or physical authority."""
import pytest
from learning.lifecycle import DevelopmentLifecycle
from learning.cycle import investigate
from learning.acquisition import investigate_requests
from test_meditation_candidate import finding


def prepare(tmp_path):
    life=DevelopmentLifecycle(tmp_path/'state',[])
    finding(life.dataset,tmp_path)
    report=investigate(life.dataset,life.gateway,executive=life.executive,diagnostics_only=True,max_jobs=1)
    project_id=report['results'][0]['project_id']
    life.executive.retain_developmental_request(project_id)
    life.executive.commission_evidence_searches()
    investigate_requests(life.dataset,[],provenance=life.provenance)
    life.executive.receive_evidence_searches()
    return life,project_id


def test_unresolved_question_stages_without_qualification_or_authority(tmp_path):
    life,identifier=prepare(tmp_path)
    before=life.executive.projects()[identifier]
    proposal=life.executive.stage_evidence_experiment();assert proposal
    p=proposal.data['payload']
    assert p['project_id']==identifier and p['original_question']==before['goal']
    assert p['trial_scope']['maximum_games']==1 and p['trial_scope']['maximum_candidate_shadows']==3
    assert all(not value for value in p['authorization'].values())
    assert not p['candidate_qualified'] and not p['physical_authorization']
    assert len(life.journal.records('prediction'))==1 # staging adds no prospective deadline
    assert life.executive.projects()[identifier]['status']==before['status']
    assert life.executive.stage_evidence_experiment().id==proposal.id
    life._status()
    import json
    status=json.loads((life.output/'development-status.json').read_text())
    assert any(r['proposal_id']==p['proposal_id'] for r in status['authorization_requests'])
    count=len(life.journal.records());life.close()
    life=DevelopmentLifecycle(tmp_path/'state',[])
    assert life.executive.stage_evidence_experiment().id==proposal.id
    assert len(life.journal.records())==count
    assert not life.journal.category_records('event','capability_activation')
    life.close()


def test_speculative_inspection_cannot_commission_or_clear_hold(tmp_path):
    life,identifier=prepare(tmp_path)
    with pytest.raises(ValueError,match='read-only'):
        life.executive.select(methods={'meditation-motion'},resources={'offline-slot','meditation-evidence'},
            authorized_methods={'meditation-motion'},exploratory_projects={identifier})
    normal=life.executive.select(methods={'meditation-motion'},resources={'offline-slot','meditation-evidence'},
        authorized_methods={'meditation-motion'},inspect=True)
    assert normal['project'] is None
    life.close()


def test_corrupt_candidate_spec_cannot_be_staged(tmp_path):
    life,identifier=prepare(tmp_path)
    # Altered source-spec fixture is appended as a newer evaluation; originals survive.
    old=life.journal.category_records('observation','meditation_candidate_evaluation')[-1]
    import copy
    payload=copy.deepcopy(old.data['payload']);payload['result']['candidates'][0]['checkpoint_sha256']='false'
    life.journal.append('observation',payload,episode=old.data['episode'],producer='ModelFoundry',version='fixture')
    assert life.executive.stage_evidence_experiment() is None
    life.close()


def test_staged_request_cannot_be_used_as_deployment_authority(tmp_path):
    from learning.deployment import CapabilityDeployment
    life,identifier=prepare(tmp_path)
    proposal=life.executive.stage_evidence_experiment()
    for target in ('offline-shadow','ppal-policy','ppal-semantics','gameplay'):
        with pytest.raises(ValueError,match='independent deployment proposal'):
            CapabilityDeployment(life.journal).activate(proposal.id,target=target,
                authorization={'proposal_id':proposal.id,'target':target,'source':'fixture approval'})
    assert not life.journal.category_records('event','capability_activation')
    life.close()


def test_independent_restart_validator_checks_staged_scope_and_permissions(tmp_path):
    from tools.inspect_developmental_progress import inspect
    from learning.continuity import compare_restart, ContinuityError
    from memory.evidence import canonical,digest
    import json,copy
    life,identifier=prepare(tmp_path);life._status();before=inspect(life.output)
    proposal=life.executive.stage_evidence_experiment();life._status();after=inspect(life.output)
    assert compare_restart(before,after)['continuity_passed']
    for change in ('authority','scope','question','alternatives'):
        bad=copy.deepcopy(after);row=bad['original_records'][-1];data=json.loads(row['document'])
        assert data['payload']['category']=='gameplay_experiment_proposal'
        if change=='authority':data['payload']['authorization']['gameplay']=True
        if change=='scope':data['payload']['trial_scope']['maximum_games']=2
        if change=='question':data['payload']['original_question']='human-substituted question'
        if change=='alternatives':data['payload']['alternatives']=[]
        row.update(id=digest(data),document=canonical(data))
        with pytest.raises(ContinuityError):compare_restart(before,bad)
    life.close()
