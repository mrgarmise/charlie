"""Scoped retrospective label retrieval through the existing Executive/Evaluator.

No model training, species correction, physical control or new scheduler.
"""
import time
from memory.evidence import digest
from memory.learning_projects import reflect_project_opportunities


def labeled_pairs(journal, model=None):
    pairs=[]
    for annotation in journal.category_records('observation','mobile_operator_annotation'):
        if len(annotation.data['sources'])!=1:continue
        raw=journal.get(annotation.data['sources'][0]);p=raw.data['payload'];a=annotation.data['payload']
        if p.get('category')!='mobile_native_prediction':continue
        if model and p['raw']['model_sha256']!=model:continue
        if not p.get('artifact') or a.get('artifact')!=p['artifact']:raise ValueError('operator label pixel binding differs')
        if a['annotation'].get('species') not in ('cat','dog') or not a['annotation'].get('source'):raise ValueError('independent operator species label required')
        pairs.append((raw,annotation))
    return pairs


def reflect_native(executive,journal):
    """Data availability is an opportunity; the existing portfolio chooses priority."""
    models=sorted({r.data['payload']['raw']['model_sha256'] for r,a in labeled_pairs(journal)})
    for model in models:
        pairs=labeled_pairs(journal,model)
        # All frames in one source log are correlated, not independent animals.
        for episode in sorted({r.data['episode'] for r,a in pairs}):
            group=[(r,a) for r,a in pairs if r.data['episode']==episode]
            h=dict(method='mobile-evidence-review',scope=dict(model_sha256=model,source_episode=episode),
                expected='retrieved species predictions agree with independently recorded operator labels',
                evidence_ids=[a.id for r,a in group],conditions=[dict(review='captured'),dict(review='new-independent-scene')],
                observed_conditions=[dict(review='captured')],requires=['native-labeled-mobile-evidence'])
            for item in reflect_project_opportunities(journal,episode,[h]):
                executive.propose(item['proposal'],journal,[item['evidence_id']])


def evaluate_labels(journal,source_ids):
    """Independent evaluation reads raw predictions and separate annotations.

    Deliberately not a detector/tracker output. No labels for missing captures.
    """
    pairs={a.id:(r,a) for r,a in labeled_pairs(journal)}
    if not source_ids or any(i not in pairs for i in source_ids):raise ValueError('verified original annotation records required')
    correct=wrong=0;units=set()
    for key in source_ids:
        r,a=pairs[key];units.add(r.data['episode'])
        expected=a.data['payload']['annotation']['species']
        for d in r.data['payload']['raw']['detections']:
            if d['label'] in ('cat','dog'):
                if d['label']==expected:correct+=1
                else:wrong+=1
    return dict(reviewed_frames=len(source_ids),correct_species=correct,wrong_species=wrong,
                independent_source_logs=len(units),recall=None,physical_authorization=False,
                verdict='contradicted' if wrong else 'supported' if correct else 'unresolved',
                interpretation='retrieval of historical classification discrepancies; no causal failure explanation or unseen accuracy claim')


def execute_review(executive,project,journal,gateway):
    from memory.evaluator import MemoryEvaluator
    pairs=[(r,a) for r,a in labeled_pairs(journal,project['scope']['model_sha256']) if r.data['episode']==project['scope']['source_episode']]
    ids=[a.id for r,a in pairs];basis=digest(ids);episode='mobile-review:'+basis
    prior=journal.category_records('event','mobile_review_plan')
    prior=next((r.data['payload']['plan'] for r in prior if r.data['payload']['plan']['dataset_id']==basis),None)
    if prior:plan=prior
    else:
        refs=[journal.append('observation',dict(category='mobile_review_reference',annotation_id=i),episode=episode,
                    producer='existing-evidence-consolidation',version='mobile-review-v1') for i in ids]
        at=time.monotonic()
        prediction=journal.predict(project['expected'],episode=episode,at=at,deadline=at+30,
            sources=[r.id for r in refs],producer='LearningExecutive',version='mobile-review-v1',mode='replay_prospective')
        plan=dict(reason='existing Executive selected an evidence-backed mobile label retrieval opportunity',project_id=project['id'],method=project['method'],prediction_id=prediction.id,
            source_evidence=[r.id for r in refs],annotation_ids=ids,dataset_id=basis,memory_id=None,
            expected=project['expected'],condition=dict(project['scope'],review='captured'),
            experiment_kind='offline',independence_unit=project['scope']['source_episode'],
            evidence_groups=[project['scope']['source_episode']])
        journal.append('event',dict(category='offline_experiment_plan',plan=plan),episode=episode,
                       sources=[prediction.id],producer='LearningExecutive',version='mobile-review-v1')
        journal.append('event',dict(category='mobile_review_plan',plan=plan),episode=episode,
                       sources=[prediction.id],producer='LearningExecutive',version='mobile-review-v1')
    commission=executive.commission(plan,journal)
    resolution=journal.resolution_for(plan['prediction_id'])
    if resolution is None:
        metrics=MemoryEvaluator.evaluate_mobile_labels(journal,plan['annotation_ids'])
        outcome=journal.append('observation',dict(category='mobile_independent_label_evaluation',ee_episode=episode,metrics=metrics),
            episode=episode,at=time.monotonic(),sources=[plan['prediction_id']],producer='independent-label-evaluator',version='mobile-review-v1')
        resolution=journal.resolve(plan['prediction_id'],sources=[outcome.id],result=metrics['verdict'],
            reason='Independent operator labels compared with preserved raw model species predictions; correlated capture batch')
    result=dict(status='resolved',result=resolution.data['payload']['result'],reason=resolution.data['payload']['reason'],resolution_id=resolution.id)
    executive.record_result(project['id'],plan,result,journal,episode=episode)
    executive.transition(project['id'],'paused','Historical review retained; await independent scene or new qualified evidence',journal,[resolution.id])
    return dict(project_id=project['id'],commission=commission,plan=plan,result=result)
