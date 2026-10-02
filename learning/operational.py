"""Controlled semantic inference adapter, never a detector or SELF authority."""
import time
from pathlib import Path
from .datasets import sha


class OperationalClassifier:
    def __init__(self,candidate,contract):
        if contract.get('target')!='ppal-semantics' or contract.get('input')!='RGB-candidate-crop' or set(contract.get('classes',[]))!={'human','threat'} or not contract.get('eligible'):
            raise ValueError('validated semantic contract required; SELF labels are prohibited')
        if candidate['spec']['objective']!='classification' or candidate['classes']!=contract['classes']:
            raise ValueError('model vocabulary escaped the contract')
        if sha(candidate['checkpoint'])!=candidate['checkpoint_sha256']:raise ValueError('model weights changed')
        from .foundry import build,checked_load
        import torch
        torch.set_num_threads(1)
        self.torch=torch;self.candidate=candidate;self.contract=contract
        self.model=build(candidate['spec'],len(candidate['classes']))
        self.model.load_state_dict(checked_load(candidate['checkpoint'])['weights']);self.model.eval()

    def infer(self,image):
        import numpy as np
        from PIL import Image
        began=time.perf_counter()
        x=np.array(image.convert('RGB').resize((self.candidate['spec']['size'],)*2,Image.Resampling.BILINEAR),dtype=np.float32)/255.
        tensor=self.torch.from_numpy(x.transpose(2,0,1)).unsqueeze(0)
        with self.torch.no_grad():probabilities=self.model(tensor).softmax(1)[0]
        confidence=float(probabilities.max());label=self.candidate['classes'][int(probabilities.argmax())]
        accepted=confidence>=self.contract['threshold']
        return dict(label=label if accepted else None,confidence=confidence,
            status='tentative_semantic_prediction' if accepted else 'UNKNOWN',
            physical_identity='unaffected',candidate_id=self.candidate['identifier'],
            seconds=time.perf_counter()-began)


def shadow(journal,proposal_id,snapshot):
    """Integration parity check on fixed held-out evidence, not another replication."""
    from .cycle import gameplay_active
    from memory.evidence import digest
    from .datasets import SCOPE
    from PIL import Image
    if gameplay_active():raise RuntimeError('offline shadow unavailable during gameplay')
    proposal=journal.get(proposal_id).data['payload']
    evaluation=journal.get(proposal['evaluation_id']).data['payload']
    candidate=evaluation['candidate'];contract=evaluation['metrics']['operational']
    if candidate['dataset_digest']!=digest(snapshot):raise ValueError('shadow dataset differs from evaluated candidate')
    prior=[r for r in journal.records('observation') if r.data['payload'].get('category')=='operational_shadow_evaluation' and r.data['payload'].get('proposal_id')==proposal_id]
    if prior:return prior[0]
    model=OperationalClassifier(candidate,contract);outputs=[];correct=0;accepted=0
    rows=[r for r in snapshot['examples'] if r['partition']=='test']
    for r in rows:
        if sha(r['pixel_path'])!=r['pixel_sha256']:raise ValueError('shadow pixels changed')
        with Image.open(r['pixel_path']) as im:value=model.infer(im)
        outputs.append(value)
        if value['label'] is not None:
            accepted+=1;correct+=int(value['label']==str(r['annotation']['value']))
    coverage=accepted/len(rows);accuracy=correct/accepted if accepted else None
    passed=coverage==contract['test_coverage'] and accuracy==contract['accepted_accuracy']
    return journal.append('observation',dict(category='operational_shadow_evaluation',proposal_id=proposal_id,
        passed=passed,coverage=coverage,accepted_accuracy=accuracy,outputs=outputs,
        dataset_digest=digest(snapshot),independence='same frozen held-out evidence; correlated integration check',
        physical_score_improvement='UNKNOWN'),episode=journal.get(proposal_id).data['episode'],sources=[proposal_id,proposal['evaluation_id']],
        producer='controlled-semantic-adapter',version='ala-2')


def load_manifest(path,*,physical=False):
    import json
    from memory.evidence import digest
    value=json.loads(Path(path).read_text());payload=value['payload']
    if value.get('sha256')!=digest(payload):raise ValueError('activation manifest changed')
    if payload.get('target')!='ppal-semantics' or not payload.get('activation_key') or not payload.get('authorization'):
        raise ValueError('authorized semantic activation required')
    from memory.evidence import EvidenceJournal
    from .deployment import CapabilityDeployment
    journal=EvidenceJournal(payload['journal'])
    try:active=CapabilityDeployment(journal).active('ppal-semantics')
    finally:journal.close()
    if active is None or dict(active,journal=payload['journal'])!=payload:
        raise ValueError('manifest is not the current authorized activation; rollback or tampering detected')
    if physical and (payload['contract']['domains']!=['robotron-camera'] or not payload.get('physical_readiness')):
        raise ValueError('Robotron-domain validation and explicit offline physical readiness required')
    return payload,OperationalClassifier(payload['candidate'],payload['contract'])
