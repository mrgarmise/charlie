"""Adapter to PR #14's asynchronous gateway; no speech or new web server."""
class ModelHumanGateway:
    def __init__(self,service,gateway,*,need_type=None):
        if gateway.journal is not service.journal: raise ValueError('single consolidated notebook required')
        if need_type is None:
            from memory.human_interaction import InformationNeed
            need_type=InformationNeed
        self.service=service;self.gateway=gateway;self.need_type=need_type

    def dispatch(self):
        from .questions import review_requests
        requests=review_requests(self.service)
        items=[(r['request_id'],'label',r['observation_id'],tuple(r['candidates']),
                'Review the historical perception frame from session '+r['session']) for r in requests]
        for record in self.service.data.events('model_qualification'):
            decision=record.data['payload']['decision']
            if decision['accepted']:
                items.append((record.id,'approval',decision['candidate_id'],('approve_shadow','reject','defer'),
                    'Independent diagnostic gates passed. Approve only a shadow perception pointer, reject or defer; no gameplay/motion activation.'))
        result=[]
        for source,kind,subject,candidates,proposition in items[:8]:
            # Existing queue policy enforces evidence freshness, dedup, priority,
            # interruption budget and expiry. Old reviews are never freshened.
            need=self.need_type(owner='model_learning',kind='interpret_result',subject=kind+':'+subject,
                proposition=proposition,candidates=candidates,sources=(source,),reason='Bounded model-learning evidence review',
                observed_at=self.gateway.clock(),consequence=.5,uncertainty=1.,priority=1)
            answer=self.gateway.consider(need);result.append(answer)
            question_id=answer.get('question_id')
            if question_id and not any(r.data['payload']['question_id']==question_id for r in self.service.data.events('model_gateway_link')):
                self.service.data.append('model_gateway_link',dict(question_id=question_id,kind=kind,subject=subject,source_id=source),sources=[question_id,source])
        return result

    def receive(self):
        # Gateway creates durable pending-review observations atomically. Nothing
        # here treats a reply as a label, qualification, deployment or motor grant.
        return self.gateway.receive('model_learning')

    def review_approval(self,answer_id,*,reviewer,reason):
        """Explicit review of an asynchronous human grant, still shadow-only."""
        from .deployment import approve
        if not reviewer or not reason: raise ValueError('independent review attribution required')
        record=self.service.journal.get(answer_id);answer=record.data['payload']
        if record.data['producer']!='HumanInteractionGateway' or answer.get('op')!='answer' or answer.get('value')!='approve_shadow':
            raise ValueError('explicit asynchronous human approval required')
        link=next((r.data['payload'] for r in self.service.data.events('model_gateway_link')
            if r.data['payload']['question_id']==answer['question_id'] and r.data['payload']['kind']=='approval'),None)
        if not link:raise ValueError('qualified model question linkage required')
        question=self.gateway.questions()[answer['question_id']]
        if question['need']['owner']!='model_learning':raise ValueError('requester mismatch')
        prior=next((r for r in self.service.data.events('model_approval') if r.data['payload'].get('answer_id')==answer_id),None)
        if prior:return prior
        with self.service.journal.batch():
            grant=approve(self.service,link['source_id'],operator=answer['operator'],reason=reason,
                answer_id=answer_id,reviewer=reviewer)
            return grant
