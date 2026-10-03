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
    def activate(self, proposal_id, *, target, authorization, adapters=('offline-shadow','ppal-semantics'),shadow_id=None,readiness_id=None):
        proposal_record=self.journal.get(proposal_id);p=proposal_record.data['payload'];scope=proposal_record.data['episode']
        if p.get('category')!='model_deployment_proposal' or not p['eligible'] or p['target']!=target:
            raise ValueError('supported independent deployment proposal required')
        if target not in adapters or target not in ('offline-shadow','ppal-semantics'): raise ValueError('production integration is not authorized or implemented')
        if not authorization or authorization.get('target')!=target or authorization.get('proposal_id')!=proposal_id or not authorization.get('source'):
            raise ValueError('separate explicit execution authorization required')
        evaluation=self.journal.get(p['evaluation_id'])
        measured=evaluation.data['payload']
        if evaluation.data['producer']!='ModelFoundry' or measured.get('category')!='offline_model_evaluation' or not measured.get('metrics',{}).get('improved') or not measured['metrics'].get('independence_groups'):
            raise ValueError('independent model evaluation required')
        if measured['metrics'].get('fresh_final_evidence') is False:
            raise ValueError('fresh independent final evidence required; repeated test groups cannot deploy')
        candidate=measured['candidate']
        if sha(candidate['checkpoint'])!=candidate['checkpoint_sha256']: raise ValueError('candidate weights changed')
        contract=None;readiness=None;sources=[proposal_id]
        if candidate.get('spec',{}).get('adapter')=='meditation-motion-v1':
            if target!='offline-shadow': raise ValueError('motion candidate has no physical activation authority')
            resolution=self.journal.resolution_for(p.get('prediction_id'))
            if not resolution or resolution.data['payload']['result']!='supported':
                raise ValueError('supported committed motion resolution required')
            if any(r.data['payload'].get('revoked_proposal')==proposal_id for r in self.journal.records('event')):
                raise ValueError('rollback revoked motion proposal; new evaluation required')
            if not shadow_id: raise ValueError('candidate-specific motion shadow required')
            s=self.journal.get(shadow_id)
            payload=s.data['payload']
            if (s.data['producer']!='controlled-motion-adapter' or payload.get('category')!='motion_operational_shadow'
                    or payload.get('proposal_id')!=proposal_id or not payload.get('passed')
                    or payload.get('candidate_id')!=candidate['identifier']
                    or payload.get('checkpoint_sha256')!=candidate['checkpoint_sha256']):
                raise ValueError('candidate-specific motion shadow required')
            sources.append(shadow_id)
        if target=='ppal-semantics':
            contract=measured['metrics'].get('operational')
            if not contract or not contract.get('eligible') or p.get('contract')!=contract:
                raise ValueError('independently evaluated semantic contract required')
            if p['candidate_id']!=candidate['identifier']:raise ValueError('candidate identity differs from evaluation')
            if not shadow_id:raise ValueError('passing operational shadow evidence required')
            s=self.journal.get(shadow_id)
            if s.data['producer']!='controlled-semantic-adapter' or s.data['payload'].get('category')!='operational_shadow_evaluation' or s.data['payload'].get('proposal_id')!=proposal_id or s.data['payload'].get('dataset_digest')!=candidate['dataset_digest'] or not s.data['payload'].get('passed'):
                raise ValueError('passing operational shadow evidence required')
            sources.append(shadow_id)
            if readiness_id:
                readiness=self.journal.get(readiness_id).data['payload']
                required={'processing_recovery','controller_release','terminal_boundaries','camera_ownership','operational_cadence'}
                if readiness.get('category')!='physical_readiness_validation' or not readiness.get('passed') or readiness.get('candidate_id')!=candidate['identifier'] or not readiness.get('source_evidence') or any(readiness.get('checks',{}).get(k) is not True for k in required):
                    raise ValueError('candidate-specific offline readiness evidence required')
                if self.journal.get(readiness_id).data['episode']!=scope:
                    readiness_id=self.journal.append('observation',dict(category='consolidated_evidence_reference',record_id=readiness_id,
                        source_episode=self.journal.get(readiness_id).data['episode'],journal=str(self.journal.path.resolve())),
                        episode=scope,producer='existing-evidence-consolidation',version='ala-2').id
                sources.append(readiness_id)
        previous=self.active(target)
        return self.journal.append('event',dict(category='capability_activation',target=target,
            candidate_id=p['candidate_id'],candidate=candidate,proposal_id=proposal_id,authorization=authorization,
            contract=contract,shadow_id=shadow_id,physical_readiness=readiness,evidence_scope=scope,
            previous_activation=previous['activation_key'] if previous else None,
            activation_key=digest(dict(proposal=proposal_id,authorization=authorization))),episode=scope,
            sources=sources,producer='authorized-capability-deployment',version='ala-2')
    def rollback(self, target, *, reason, authorization, to_baseline=False):
        current=self.active(target)
        if not current or not reason or not authorization or authorization.get('target')!=target or not authorization.get('source'): raise ValueError('explicit rollback required')
        prior=None
        if current['previous_activation'] and not to_baseline:
            prior=next(r.data['payload'] for r in self.journal.records('event') if r.data['payload'].get('activation_key')==current['previous_activation'])
            if sha(prior['candidate']['checkpoint'])!=prior['candidate']['checkpoint_sha256']: raise ValueError('rollback weights changed')
        return self.journal.append('event',dict(category='capability_activation',target=target,
            candidate_id=prior['candidate_id'] if prior else None,candidate=prior['candidate'] if prior else None,
            contract=prior.get('contract') if prior else None,shadow_id=prior.get('shadow_id') if prior else None,
            physical_readiness=prior.get('physical_readiness') if prior else None,
            revoked_proposal=current.get('proposal_id'),
            authorization=authorization,reason=reason,previous_activation=None,
            activation_key=digest(dict(rollback=current['activation_key'],reason=reason,authorization=authorization))),
            episode=SCOPE,producer='authorized-capability-deployment',version='ala-1')

    def export(self,target,path):
        """Freeze a separately authorized version for an episode; rollback applies next load."""
        from .foundry import atomic_json
        active=self.active(target)
        if not active or not active.get('candidate') or target!='ppal-semantics':raise ValueError('active semantic capability required')
        if sha(active['candidate']['checkpoint'])!=active['candidate']['checkpoint_sha256']:raise ValueError('candidate weights changed')
        payload=dict(active,journal=str(self.journal.path.resolve()))
        atomic_json(path,dict(payload=payload,sha256=digest(payload)))
        return payload

    def apply_authority(self,result,authority,path):
        """Execute a pre-existing, externally granted policy; never self-authorize."""
        proposal=result.get('operational_proposal')
        if not proposal or not authority:return {'status':'proposed_only','manifest':None}
        if any(r.data['payload'].get('revoked_proposal')==proposal for r in self.journal.records('event')):
            return {'status':'blocked','reason':'explicit rollback revoked this proposal; new evaluation/authorization required','manifest':None}
        if not authority.get('source') or authority.get('target')!='ppal-semantics' or not isinstance(authority.get('allowed_domains'),list):
            raise ValueError('external bounded deployment authority required')
        p=self.journal.get(proposal).data['payload'];domains=set(p['contract']['domains'])
        if not domains or not domains<=set(authority['allowed_domains']):
            return {'status':'blocked','reason':'model domains outside granted authority','manifest':None}
        previous=self.active('ppal-semantics')
        authorization=dict(source=authority['source'],target='ppal-semantics',proposal_id=proposal,
                           policy=authority,policy_digest=digest(authority))
        if not previous or previous.get('proposal_id')!=proposal:
            self.activate(proposal,target='ppal-semantics',authorization=authorization,
                shadow_id=result['shadow_id'],readiness_id=authority.get('readiness_id'))
        self.export('ppal-semantics',path)
        return dict(status='activated',manifest=str(path),proposal_id=proposal,
                    activation_key=self.active('ppal-semantics')['activation_key'],objective_evidence='diagnostic only; score UNKNOWN')

    def observe(self, target, image):
        """Offline shadow inference returns interpretations, never identity facts."""
        from .cycle import gameplay_active
        from .foundry import build,checked_load
        if gameplay_active(): raise RuntimeError('offline shadow unavailable during gameplay')
        active=self.active(target)
        if not active or active.get('candidate') is None: return {'status':'unavailable'}
        candidate=active['candidate']
        if candidate.get('spec',{}).get('adapter')=='meditation-motion-v1':
            raise ValueError('motion candidate requires the offline planning adapter')
        if sha(candidate['checkpoint'])!=candidate['checkpoint_sha256']: raise ValueError('candidate weights changed')
        import torch
        import numpy as np
        from PIL import Image
        torch.set_num_threads(1)
        spec=candidate['spec'];classes=candidate['classes'];model=build(spec,len(classes))
        model.load_state_dict(checked_load(candidate['checkpoint'])['weights']);model.eval()
        pixels=np.array(image.convert('RGB').resize((spec['size'],spec['size']),Image.Resampling.BILINEAR),dtype=np.float32)/255.
        x=torch.from_numpy(pixels.transpose(2,0,1)).unsqueeze(0)
        with torch.no_grad():
            value=model(x)
            if spec['objective']=='classification':
                probabilities=value.softmax(1)[0]; label=classes[int(probabilities.argmax())]
                return dict(status='unverified_model_prediction',label=label,confidence=float(probabilities.max()),
                    calibrated=False,candidate_id=candidate['identifier'],activation=active['activation_key'])
            error=float(torch.nn.functional.mse_loss(value,x))
            return dict(status='unverified_representation',reconstruction_mse=error,
                candidate_id=candidate['identifier'],activation=active['activation_key'],semantic_label=None)

    def planning_adapter(self):
        """Load an authorized offline motion version. Never install physical policy."""
        from .cycle import gameplay_active
        from .meditation import PlanningCandidate
        import json
        from pathlib import Path
        if gameplay_active(): raise RuntimeError('offline motion unavailable during gameplay')
        active=self.active('offline-shadow')
        if not active or not active.get('candidate'): return None
        candidate=active['candidate']
        if sha(candidate['checkpoint'])!=candidate['checkpoint_sha256']:
            raise ValueError('candidate artifact changed')
        spec=json.loads(Path(candidate['checkpoint']).read_text())
        if spec!=candidate['spec']: raise ValueError('candidate specification changed')
        return PlanningCandidate(spec)
