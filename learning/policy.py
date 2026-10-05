"""Qualification-time PPAL policy export through existing deployment records."""
import json
import subprocess
from pathlib import Path

from memory.evidence import digest
from .datasets import sha
from experiments.ppal.qualified_policy import VERSION, validate_spec, DECISION_ADAPTER


def policy_payload(journal, active):
    required=('policy_code_revision','policy_code_dirty','policy_runtime_sha256','policy_provenance_kind')
    if any(k not in active for k in required):
        raise ValueError('legacy activation lacks runtime qualification; retain baseline policy')
    candidate = active['candidate']; proposal_id = active['proposal_id']
    proposal = journal.get(proposal_id); p = proposal.data['payload']
    evaluation = journal.get(p['evaluation_id']); measured = evaluation.data['payload']
    if (proposal.data['producer'] != 'Reflection' or
        measured.get('category') != 'offline_model_evaluation' or
        evaluation.data['producer'] != 'ModelFoundry' or
        measured.get('candidate') != candidate or not measured['metrics'].get('improved') or
        not measured['metrics'].get('fresh_final_evidence') or
        not measured['metrics'].get('independence_groups')):
        raise ValueError('Charlie proposal and independent fresh evaluation required')
    if sha(candidate['checkpoint']) != candidate['checkpoint_sha256']:
        raise ValueError('candidate artifact changed')
    spec = json.loads(Path(candidate['checkpoint']).read_text())
    if spec != candidate['spec'] or candidate.get('originator') != 'Reflection':
        raise ValueError('Charlie-originated frozen candidate required')
    domains = validate_spec(spec)
    plan_rows = [r for r in journal.records('event')
        if r.data['payload'].get('category') == 'offline_experiment_plan'
        and r.data['payload']['plan']['prediction_id'] == p.get('prediction_id')]
    if len(plan_rows) != 1:
        raise ValueError('original committed investigation required')
    plan = plan_rows[0].data['payload']['plan']
    sources = candidate.get('source_evidence', [])
    if not sources or sources != plan['source_evidence']:
        raise ValueError('candidate investigation provenance mismatch')
    for ref in sources:
        journal.get(ref)
    resolution = journal.resolution_for(p['prediction_id'])
    if not resolution or resolution.data['payload']['result'] != 'supported':
        raise ValueError('supported independent investigation outcome required')
    if spec['adapter'] == DECISION_ADAPTER:
        contract = measured['metrics'].get('decision_contract', {})
        if (contract != p.get('contract') or not contract.get('eligible') or
            contract.get('policy_version') != VERSION or contract.get('domains') != list(domains) or
            contract.get('spec_sha256') != digest(spec)):
            raise ValueError('independently evaluated decision contract required')
    auth = active.get('authorization', {})
    if (auth.get('target') != active['target'] or auth.get('proposal_id') != proposal_id or
        auth.get('execution') not in ('offline','physical') or not auth.get('source')):
        raise ValueError('explicit bounded deployment authority required')
    if active['target'] == 'ppal-policy' and not set(domains) <= set(auth.get('allowed_domains', [])):
        raise ValueError('decision domain outside authorization')
    readiness=None
    if auth['execution']=='physical':
        readiness=physical_readiness(journal,active,measured)
    shadow = journal.get(active['shadow_id']).data
    expected = 'motion_operational_shadow' if spec['adapter'] == 'meditation-motion-v1' else 'decision_policy_shadow'
    expected_producer = 'controlled-motion-adapter' if expected == 'motion_operational_shadow' else 'controlled-policy-adapter'
    s = shadow['payload']
    if (shadow['producer'] != expected_producer or s.get('category') != expected or
        not s.get('passed') or s.get('proposal_id') != proposal_id or
        s.get('candidate_id') != candidate['identifier'] or
        s.get('checkpoint_sha256') != candidate['checkpoint_sha256'] or
        s.get('policy_runtime_sha256') != active['policy_runtime_sha256']):
        raise ValueError('candidate-specific operational shadow required')
    return dict(version=VERSION, qualification='independently_evaluated_offline',
        target=active['target'], journal=str(journal.path.resolve()),
        candidate_id=candidate['identifier'], investigation_id=plan_rows[0].id,
        prediction_id=p['prediction_id'], source_evidence=sources, evaluation_id=evaluation.id,
        activation_key=active['activation_key'], rollback_identity=active['activation_key'],
        previous_activation=active.get('previous_activation'), authorization=auth,
        code_revision=active['policy_code_revision'], provenance_kind=active['policy_provenance_kind'],
        code_dirty=active['policy_code_dirty'], runtime_sha256=active['policy_runtime_sha256'],
        permitted_domains=list(domains), spec=spec, checkpoint_sha256=candidate['checkpoint_sha256'],
        shadow_id=active['shadow_id'], score_improvement='UNKNOWN',
        physical_readiness_id=active.get('physical_readiness_id'),physical_readiness=readiness,
        uncertainty='Evaluation supports its measured domain; complete-game utility unverified')


def physical_readiness(journal, active, measured):
    """Future separate authority/readiness gate. Never establishes hardware truth."""
    auth=active['authorization'];candidate=active['candidate']
    contract=measured['metrics'].get('decision_contract',{})
    if (active['target']!='ppal-policy' or auth.get('execution')!='physical' or
        auth.get('operating_domain')!='robotron-camera' or
        contract.get('operating_domain')!='robotron-camera' or
        measured['metrics'].get('provenance_kind')!='independently-qualified-robotron'):
        raise ValueError('physical policy requires separate Robotron-domain authority and independent evidence')
    record=journal.get(active.get('physical_readiness_id'));r=record.data;p=r['payload']
    required={'processing_recovery','controller_release','terminal_boundaries','camera_ownership',
              'operational_cadence','current_world_arbitration','uncertainty','rollback','resource_contention'}
    if (r['producer']!='independent-physical-measurement' or
        p.get('category')!='physical_readiness_validation' or p.get('passed') is not True or
        p.get('candidate_id')!=candidate['identifier'] or
        p.get('checkpoint_sha256')!=candidate['checkpoint_sha256'] or
        p.get('policy_runtime_sha256')!=active['policy_runtime_sha256'] or
        not p.get('source_evidence') or any(p.get('checks',{}).get(k) is not True for k in required)):
        raise ValueError('candidate/runtime-specific independent physical readiness required')
    for ref in p['source_evidence']:journal.get(ref)
    proof=p.get('qualification_artifact',{})
    if not proof.get('path') or sha(proof['path'])!=proof.get('sha256'):
        raise ValueError('unchanged independent readiness proof required')
    return p


def revision():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'],
        cwd=Path(__file__).resolve().parents[1], text=True).strip()


def runtime_hash():
    root=Path(__file__).resolve().parents[1]
    files=('experiments/ppal/qualified_policy.py','experiments/ppal/forebrain.py',
           'experiments/ppal/hindbrain.py','experiments/ppal/models.py','experiments/ppal/shadow_predictor.py')
    return digest({name:sha(root/name) for name in files})


def dirty():
    return bool(subprocess.check_output(['git','status','--porcelain'],
        cwd=Path(__file__).resolve().parents[1],text=True).strip())


def export_policy(deployment, target, path):
    from .foundry import atomic_json
    active = deployment.active(target)
    if not active or not active.get('candidate'):
        raise ValueError('active qualified policy required')
    payload = policy_payload(deployment.journal, active)
    atomic_json(path, dict(payload=payload, sha256=digest(payload)))
    return payload


def shadow_policy(journal, proposal_id):
    """Existing chooser compatibility on frozen validation only; never utility."""
    from .cycle import gameplay_active
    from .meditation import world_from_frame
    from experiments.ppal.qualified_policy import QualifiedPolicy
    from experiments.ppal.forebrain import Forebrain
    from experiments.ppal.hindbrain import Hindbrain
    if gameplay_active():raise RuntimeError('offline shadow unavailable during gameplay')
    proposal=journal.get(proposal_id);p=proposal.data['payload']
    if not p.get('eligible') or p.get('target')!='ppal-policy':
        raise ValueError('eligible decision proposal required')
    candidate=journal.get(p['evaluation_id']).data['payload']['candidate']
    if sha(candidate['checkpoint'])!=candidate['checkpoint_sha256']:
        raise ValueError('candidate artifact changed')
    corpus=journal.get(candidate['dataset_digest']).data['payload']['corpus']
    runtime=runtime_hash();steps=0
    for episode in corpus['episodes']:
        if episode['partition']!='validation':continue
        policy=QualifiedPolicy.from_payload(dict(spec=candidate['spec'],candidate_id=candidate['identifier'],
            investigation_id=p['prediction_id'],evaluation_id=p['evaluation_id'],activation_key='unactivated-shadow',
            rollback_identity='unactivated-shadow',code_revision=revision(),provenance_kind='unactivated-shadow'))
        f,h=Forebrain(policy),Hindbrain(policy=policy)
        for frame in episode['frames']:
            if sha(frame['artifact']['path'])!=frame['artifact']['sha256']:
                raise ValueError('shadow input artifact changed')
            world=world_from_frame(frame);intent,action=h.decide(world,f.update(world),timestamp=frame['timestamp'])
            if not action.move or not action.fire or not intent.kind:
                raise ValueError('invalid chooser output')
            steps+=1
    if not steps:raise ValueError('no validation shadow observations')
    return journal.append('observation',dict(category='decision_policy_shadow',passed=True,
        proposal_id=proposal_id,candidate_id=candidate['identifier'],checkpoint_sha256=candidate['checkpoint_sha256'],
        policy_runtime_sha256=runtime,steps=steps,controller_writes=0,
        limitation='fixed validation compatibility, not independent score utility'),episode=proposal.data['episode'],
        sources=[proposal_id],producer='controlled-policy-adapter',version=VERSION)


def comparison_versions(manifest):
    """Freeze version identities for the existing score protocol, never run it."""
    from experiments.ppal.qualified_policy import load_policy
    load_policy(manifest)  # require current qualified offline version
    value=json.loads(Path(manifest).read_text());p=value['payload']
    baseline=dict(policy_version=VERSION,runtime_sha256=runtime_hash(),policy=None,
                  behavior='existing Forebrain/Hindbrain defaults; no learned decision policy')
    return dict(baseline_version=digest(baseline),baseline=baseline,
        candidate_version=digest(value),candidate_id=p['candidate_id'],activation_key=p['activation_key'],
        investigation_id=p['investigation_id'],evaluation_id=p['evaluation_id'],
        source_evidence=p['source_evidence'],permitted_domains=p['permitted_domains'],
        readiness='pending; offline version identities do not grant physical authorization',
        score_objective='official_game_score',physical_authorization=False)
