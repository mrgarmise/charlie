"""Durable asynchronous review outbox; PR #14 needs a new typed adapter.

No voice requests and no automatic approval. Human answers become attributed
label reviews through DatasetStore.label, never unconditional ground truth.
"""
def review_requests(service,*,limit=8):
    if type(limit) is not int or not 1<=limit<=8:raise ValueError('bounded review queue required')
    prior={r.data['payload']['observation_id']:r for r in service.data.events('model_review_request')}
    pending=[]
    for row in service.data.rows():
        if row['label'] is not None:continue # unresolved labels only, not split administration
        record=prior.get(row['observation_id'])
        if record is None:
            record=service.data.append('model_review_request',dict(observation_id=row['observation_id'],
                task=row['task'],session=row['session'],kind='perception_label',
                candidates=list(service.data.labels),
                reason='Existing perception cannot resolve the task label; a reviewed label may enable an offline comparison',
                status='pending-adapter',deferrable=True,approval_authority=False),sources=[row['observation_id']],producer='LearningExecutive')
        pending.append(dict(request_id=record.id,**record.data['payload']))
        if len(pending)>=limit:break
    return pending
