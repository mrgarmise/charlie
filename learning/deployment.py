"""Externally authorized, versioned shadow activation; no production PPAL swap."""
from memory.evidence import digest
from .datasets import SCOPE, sha

class CapabilityDeployment:
    def __init__(self,journal): self.journal=journal
    def active(self,target):
        active=None
        for row in self.journal.records('event'):
            p=row.data['payload']
            if p.get('category')=='capability_activation' and p['target']==target: active=p
        return active
    def activate(self, proposal_id, *, target, authorization, adapters=('offline-shadow',)):
        p=self.journal.get(proposal_id).data['payload']
        if p.get('category')!='model_deployment_proposal' or not p['eligible'] or p['target']!=target:
            raise ValueError('supported independent deployment proposal required')
        if target not in adapters or target!='offline-shadow': raise ValueError('production integration is not authorized or implemented')
        if not authorization or authorization.get('target')!=target or authorization.get('proposal_id')!=proposal_id or not authorization.get('source'):
            raise ValueError('separate explicit execution authorization required')
        candidate=self.journal.get(p['evaluation_id']).data['payload']['candidate']
        if sha(candidate['checkpoint'])!=candidate['checkpoint_sha256']: raise ValueError('candidate weights changed')
        previous=self.active(target)
        return self.journal.append('event',dict(category='capability_activation',target=target,
            candidate_id=p['candidate_id'],candidate=candidate,proposal_id=proposal_id,authorization=authorization,
            previous_activation=previous['activation_key'] if previous else None,
            activation_key=digest(dict(proposal=proposal_id,authorization=authorization))),episode=SCOPE,
            sources=[proposal_id],producer='authorized-capability-deployment',version='ala-1')
    def rollback(self, target, *, reason, authorization):
        current=self.active(target)
        if not current or not reason or not authorization or authorization.get('target')!=target or not authorization.get('source'): raise ValueError('explicit rollback required')
        prior=None
        if current['previous_activation']:
            prior=next(r.data['payload'] for r in self.journal.records('event') if r.data['payload'].get('activation_key')==current['previous_activation'])
            if sha(prior['candidate']['checkpoint'])!=prior['candidate']['checkpoint_sha256']: raise ValueError('rollback weights changed')
        return self.journal.append('event',dict(category='capability_activation',target=target,
            candidate_id=prior['candidate_id'] if prior else None,candidate=prior['candidate'] if prior else None,
            authorization=authorization,reason=reason,previous_activation=None,
            activation_key=digest(dict(rollback=current['activation_key'],reason=reason,authorization=authorization))),
            episode=SCOPE,producer='authorized-capability-deployment',version='ala-1')
