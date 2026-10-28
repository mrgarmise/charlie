"""Perception extension of existing CapabilityDeployment, shadow target only."""
from memory.evidence import digest
TARGET='perception-shadow'


def approve(service,qualification_id,*,operator,reason,answer_id=None,reviewer=None):
    row=service.journal.get(qualification_id);payload=row.data['payload']
    if payload.get('category')!='model_qualification' or not payload['decision']['accepted'] or not operator or not reason:
        raise ValueError('qualified candidate and attributed human approval required')
    if not answer_id or not reviewer: raise ValueError('reviewed asynchronous human approval required')
    answer=service.journal.get(answer_id)
    data=answer.data['payload']
    if answer.data['producer']!='HumanInteractionGateway' or data.get('op')!='answer' or data.get('value')!='approve_shadow' or data.get('operator')!=operator:
        raise ValueError('explicit gateway approval required')
    if not any(r.data['payload']['question_id']==data.get('question_id') and r.data['payload']['kind']=='approval'
        and r.data['payload']['source_id']==qualification_id for r in service.data.events('model_gateway_link')):
        raise ValueError('qualification/answer linkage required')
    from .qualification import reasons
    evaluation=service.journal.get(payload['decision']['evaluation_id'])
    if reasons(evaluation.data['payload']['metrics'],payload['gates']): raise ValueError('independent qualification gates failed')
    candidate=payload['decision']['candidate_id'];service.candidate(candidate)
    return service.data.append('model_approval',dict(qualification_id=qualification_id,candidate_id=candidate,
        operator=operator,reason=reason,target=TARGET,answer_id=answer_id,reviewer=reviewer),sources=[qualification_id]+([answer_id] if answer_id else []),producer='operator-model-review')


def activate(deployment,service,approval_id):
    if deployment.journal is not service.journal: raise ValueError('same deployment notebook required')
    approval=deployment.journal.get(approval_id);p=approval.data['payload']
    if p.get('category')!='model_approval' or approval.data['producer']!='operator-model-review' or p['target']!=TARGET:
        raise ValueError('external approval record required')
    q=deployment.journal.get(p['qualification_id']).data['payload']
    if not q['decision']['accepted'] or q['decision']['candidate_id']!=p['candidate_id']: raise ValueError('qualification mismatch')
    evaluation=deployment.journal.get(q['decision']['evaluation_id']); measured=evaluation.data['payload']
    if evaluation.data['producer']!='independent-model-evaluator' or not measured['metrics']['authentic'] or not measured['metrics']['fresh_holdout']:
        raise ValueError('independent authentic qualification required')
    from .qualification import reasons
    if reasons(measured['metrics'],q['gates']): raise ValueError('independent qualification gates failed')
    candidate=service.candidate(p['candidate_id'])
    if measured['candidate_id']!=p['candidate_id']: raise ValueError('evaluation candidate mismatch')
    key=digest(dict(approval=approval_id,target=TARGET))
    with deployment.journal.batch():
        events=deployment.journal.category_records('event','capability_activation')
        if any(r.data['payload'].get('revoked_activation')==key for r in events): raise ValueError('revoked approval cannot reactivate')
        old=next((r for r in events if r.data['payload'].get('activation_key')==key),None)
        if old:return old
        current=deployment.active(TARGET)
        return service.data.append('capability_activation',dict(target=TARGET,candidate_id=p['candidate_id'],candidate=candidate,
            approval_id=approval_id,activation_key=key,previous_activation=current['activation_key'] if current else None,
            mode='shadow',physical_authorization=False),sources=[approval_id],producer='authorized-capability-deployment')


def rollback(deployment,service,*,operator,reason):
    if deployment.journal is not service.journal or not operator or not reason: raise ValueError('attributed rollback required')
    with deployment.journal.batch():
        current=deployment.active(TARGET)
        if not current: raise ValueError('no shadow activation')
        previous=None
        if current.get('previous_activation'):
            previous=next(r.data['payload'] for r in deployment.journal.category_records('event','capability_activation')
                if r.data['payload'].get('activation_key')==current['previous_activation'])
            service.candidate(previous['candidate_id'])
        return service.data.append('capability_activation',dict(target=TARGET,
            candidate_id=previous['candidate_id'] if previous else None,candidate=previous['candidate'] if previous else None,
            activation_key=digest(dict(rollback=current['activation_key'],operator=operator,reason=reason)),
            previous_activation=None,revoked_activation=current['activation_key'],operator=operator,reason=reason,
            mode='shadow',physical_authorization=False),producer='authorized-capability-deployment')
