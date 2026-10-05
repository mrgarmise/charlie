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
        auth.get('execution') != 'offline' or not auth.get('source')):
        raise ValueError('explicit offline deployment authority required')
    if active['target'] == 'ppal-policy' and not set(domains) <= set(auth.get('allowed_domains', [])):
        raise ValueError('decision domain outside authorization')
    shadow = journal.get(active['shadow_id']).data
    expected = 'motion_operational_shadow' if spec['adapter'] == 'meditation-motion-v1' else 'decision_policy_shadow'
    expected_producer = 'controlled-motion-adapter' if expected == 'motion_operational_shadow' else 'controlled-policy-adapter'
    s = shadow['payload']
    if (shadow['producer'] != expected_producer or s.get('category') != expected or
        not s.get('passed') or s.get('proposal_id') != proposal_id or
        s.get('candidate_id') != candidate['identifier'] or
        s.get('checkpoint_sha256') != candidate['checkpoint_sha256']):
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
        uncertainty='Evaluation supports its measured domain; complete-game utility unverified')


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
