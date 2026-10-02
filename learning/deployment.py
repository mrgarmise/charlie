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
        evaluation=self.journal.get(p['evaluation_id'])
        measured=evaluation.data['payload']
        if evaluation.data['producer']!='ModelFoundry' or measured.get('category')!='offline_model_evaluation' or not measured.get('metrics',{}).get('improved') or not measured['metrics'].get('independence_groups'):
            raise ValueError('independent model evaluation required')
        candidate=measured['candidate']
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

    def observe(self, target, image):
        """Offline shadow inference returns interpretations, never identity facts."""
        from .cycle import gameplay_active
        from .foundry import build,checked_load
        if gameplay_active(): raise RuntimeError('offline shadow unavailable during gameplay')
        active=self.active(target)
        if not active or active.get('candidate') is None: return {'status':'unavailable'}
        candidate=active['candidate']
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
