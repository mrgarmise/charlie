"""Mobile capability/evidence adapter to Charlie's ONE existing Executive.

No scheduler, learning algorithm, actuator, synthetic conclusion or pet identity.
"""
from memory.evidence import canonical
from memory.former import Experience
from memory.learning_projects import reflect_project_opportunities


class MobileEvidenceAdapter:
    def __init__(self, journal, *, episode, revision, gateway=None, executive=None):
        if not episode or not revision:raise ValueError('episode/revision required')
        self.journal,self.episode,self.revision=journal,episode,revision
        self.gateway,self.executive=gateway,executive
        self.opportunity_keys=set()

    def record(self, observation, tracking, proposal, execution):
        payload=dict(category='mobile_perception',observation=observation,tracking=tracking,
                     proposal=proposal,execution=execution)
        if len(canonical(payload).encode())>256*1024:raise ValueError('bounded mobile evidence required')
        row=self.journal.append('observation',payload,episode=self.episode,
            at=observation['frame']['received_at'],producer='mobile-perception',version=self.revision,
            provenance=dict(authentic=observation['frame']['authentic'],
                            qualification=observation['qualification']))
        # Gateway's existing Evaluator decides promotion. No inference of reward,
        # successful physical execution, learned utility or individual identity.
        if self.gateway is not None and observation['frame']['authentic'] and tracking['target']:
            self.gateway.remember(Experience(kind='observation',
                summary=f"Detector maintains an animal candidate; species hypothesis {tracking['target']['label']} is unverified; individual identity unverified",
                source='mobile:perception',subject=tracking['target']['label'],
                confidence=tracking['target']['confidence'],evidence=row.id,tags=('mobile','species-only')))
        return row

    def fault(self, error, metrics=None):
        return self.journal.append('event',dict(category='mobile_acquisition_fault',
            error=type(error).__name__,message=str(error)[:512],metrics=metrics or {},physical_authorization=False,
            learning_outcome='inconclusive; acquisition interrupted'),episode=self.episode,
            producer='mobile-perception',version=self.revision)

    def opportunities(self, observation_id):
        """Generic existing Reflection reproducibility policy; no forced agenda.

        Fixture data never creates live projects or semantic memories.
        """
        if self.executive is None:return []
        row=self.journal.get(observation_id); p=row.data['payload']; o=p['observation']
        if not o['frame']['authentic']:return []
        target=p['tracking']['target']
        if target is None:return []
        key=(o['frame']['source'],target['id'],o['frame'].get('pan_deg'),o.get('grounded_animal',False))
        if key in self.opportunity_keys or len(self.opportunity_keys)>=256:return []
        self.opportunity_keys.add(key)
        hypotheses=[dict(method='mobile-observe',scope=dict(body=o['frame']['source'],category=target.get('kind',target['label'])),
            expected='detector animal candidates and species uncertainty persist across independent observation conditions',
            evidence_ids=[row.id],conditions=[dict(view='centered'),dict(view='off-axis'),dict(view='pose-unknown')],
            observed_conditions=[dict(view='centered' if o['frame'].get('pan_deg')==90 else 'pose-unknown' if o['frame'].get('pan_deg') is None else 'off-axis')],
            requires=['mobile-camera','mobile-models'])]
        if o.get('grounded_animal') is True:
            hypotheses.append(dict(method='pet_follow',scope=dict(body=o['frame']['source'],kind='animal'),
                expected='bounded changes of viewpoint improve continued animal observation without reducing safe separation',
                evidence_ids=[row.id],conditions=[dict(view='far'),dict(view='stand-off'),dict(view='yield')],
                observed_conditions=[dict(view='far')],requires=['mobile-camera','mobile-models','qualified-car-local-controller','motion-lease']))
        proposals=reflect_project_opportunities(self.journal,self.episode,hypotheses)
        return [self.executive.propose(x['proposal'],self.journal,[x['evidence_id']]) for x in proposals]

    def request(self, project_id, *, reason):
        """Durable request/bookmark; existing portfolio retains goal through vetoes."""
        if self.executive is None or project_id not in self.executive.projects() or not reason:
            raise ValueError('existing Executive project and reason required')
        return self.journal.append('event',dict(category='mobile_observation_request',
            project_id=project_id,reason=reason,physical_authorization=False),
            episode=self.episode,producer='LearningExecutive',version=self.revision)

    def pending(self):
        completed={r.data['payload'].get('request_id') for r in self.journal.category_records('event','mobile_request_completed')}
        return [r for r in self.journal.category_records('event','mobile_observation_request') if r.id not in completed]

    def complete(self, request_id, observation_id):
        request=self.journal.get(request_id)
        if request.data['payload'].get('category')!='mobile_observation_request':raise ValueError('invalid request')
        row=self.journal.get(observation_id)
        if row.data['payload'].get('category')!='mobile_perception':raise ValueError('invalid observation')
        return self.journal.append('event',dict(category='mobile_request_completed',request_id=request_id,
            observation_id=observation_id,outcome='observation acquired; learning not demonstrated'),
            episode=request.data['episode'],sources=[request_id],producer='mobile-acquisition',version=self.revision,
            provenance=dict(observation_episode=row.data['episode'],cross_episode_link='verified immutable observation ID'))

    def attention_outcome(self, result, decision, execution, *, phase):
        payload=dict(category='mobile_attention_episode',observation_id=result['evidence_id'],
            frame=result['observation']['frame'],model=result['observation'].get('model'),
            software_revision=self.revision,tracking=result['tracking'],proposal=result['proposal'],
            sensors=result['observation'].get('sensors',{}),resources=result['observation'].get('resources',{}),
            decision=decision,execution=execution,phase=phase,
            consequence='unobserved; requires independent displacement and animal-reaction measurements',
            learning='no learned improvement or individual identity established')
        event=self.journal.append('event',payload,episode=self.episode,producer='AttentionManager',
            version=self.revision,provenance=dict(authentic=result['observation']['frame']['authentic']))
        from memory.evaluator import MemoryEvaluator
        MemoryEvaluator.evaluate_mobile_attention(self.journal,event.id)
        return event


def observe_capability(*, service, request_id=None):
    """Existing capability dispatch; perception only even if selected by Executive."""
    result=service.step()
    if result is not None and request_id is not None:
        service.evidence.complete(request_id,result['evidence_id'])
    return result
