"""Loaded local PPAL parameters, never a planner, observer or authority owner.

Validation/journal reads happen once before an episode. Decisions only consult
compiled values and the existing bounded causal motion predictor.
"""
from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType

VERSION = 'ppal-policy-v1'
DECISION_ADAPTER = 'decision-parameters-v1'
DOMAINS = {'goal_preference', 'positioning_preference', 'firing_behavior',
           'action_effect_prediction'}


def validate_spec(spec):
    """Finite capability vocabulary, not a prescribed winning strategy."""
    if spec.get('adapter') == 'meditation-motion-v1':
        from learning.meditation import PlanningCandidate
        PlanningCandidate(spec)
        return ('action_effect_prediction',)
    if spec.get('adapter') != DECISION_ADAPTER or set(spec) != {'adapter', 'parameters'}:
        raise ValueError('unsupported policy version/adapter')
    parameters = spec['parameters']
    if not isinstance(parameters, dict) or not parameters or not set(parameters) <= DOMAINS-{'action_effect_prediction'}:
        raise ValueError('unsupported decision domains')
    fields = {'goal_preference': {'rescue', 'survive', 'target_threat_weight'},
              'positioning_preference': {'N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'},
              'firing_behavior': {'deadband'}}
    for domain, values in parameters.items():
        if not isinstance(values, dict) or not values or not set(values) <= fields[domain]:
            raise ValueError('unsupported policy parameters')
        for key, value in values.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError('finite policy parameters required')
            lo, hi = ((0, 3) if domain == 'firing_behavior' else
                      (0, 1) if key == 'target_threat_weight' else (-1, 1))
            if not lo <= value <= hi:
                raise ValueError('policy parameters outside capability bounds')
    return tuple(sorted(parameters))


@dataclass(frozen=True)
class QualifiedPolicy:
    identity: object
    parameters: object
    predictor: object = None

    @classmethod
    def from_payload(cls, payload):
        # Only the guarded loader calls this in normal operation.
        spec = payload['spec']; domains = validate_spec(spec)
        params = {d: MappingProxyType(dict(v)) for d, v in spec.get('parameters', {}).items()}
        predictor = None
        if spec['adapter'] == 'meditation-motion-v1':
            from .shadow_predictor import ShadowPredictor
            predictor = ShadowPredictor(velocity_alpha=spec['velocity_alpha'],
                horizon_seconds=spec['horizon_seconds'], max_speed=spec['max_speed'])
        identity = {k: payload[k] for k in ('candidate_id', 'investigation_id', 'evaluation_id',
                    'activation_key', 'rollback_identity', 'code_revision', 'provenance_kind')}
        identity.update(policy_version=VERSION, domains=domains)
        return cls(MappingProxyType(identity), MappingProxyType(params), predictor)

    def values(self, domain):
        return self.parameters.get(domain, {})

    def trace(self, applied=(), *, disposition='eligible'):
        return dict(self.identity, applied_domains=list(applied), disposition=disposition)

    def predicted_targets(self, world, timestamp):
        """Predictions never overwrite observed player, threats or identities."""
        if self.predictor is None or timestamp is None or not isfinite(timestamp):
            return None
        if self.predictor.observed_at is not None and timestamp <= self.predictor.observed_at:
            return None  # stale/repeated captures do not advance causal estimates
        self.predictor.observe(world, timestamp)
        return self.predictor.project(world).targets

    def reset_predictions(self):
        if self.predictor:
            self.predictor._objects.clear()
            self.predictor._player = None
            self.predictor.observed_at = None


def load_policy(path, *, physical=False):
    """Fail closed at episode load; no database/network work in decision methods."""
    import json
    from pathlib import Path
    from memory.evidence import digest, EvidenceJournal
    from learning.policy import policy_payload,runtime_hash
    from learning.deployment import CapabilityDeployment
    location = Path(path)
    if location.stat().st_size > 65536:
        raise ValueError('bounded policy artifact required')
    document = json.loads(location.read_text()); payload = document['payload']
    if document.get('sha256') != digest(payload) or payload.get('version') != VERSION:
        raise ValueError('policy integrity/version mismatch')
    if payload.get('runtime_sha256')!=runtime_hash():
        raise ValueError('policy runtime version mismatch; requalification required')
    journal = EvidenceJournal(payload['journal'], read_only=True)
    try:
        active = CapabilityDeployment(journal).active(payload['target'])
        if not active or not active.get('candidate') or policy_payload(journal, active) != payload:
            raise ValueError('policy is not current qualified activation; rollback/tampering detected')
        # An arm flag cannot upgrade an offline grant. The same qualification
        # boundary verifies exact independent readiness at load time.
        if physical and (payload['target']!='ppal-policy' or
                         payload['authorization'].get('execution')!='physical' or
                         not payload.get('physical_readiness')):
            raise ValueError('PPAL decision policy physical readiness/activation is not qualified')
        return QualifiedPolicy.from_payload(payload)
    finally:
        journal.close()
