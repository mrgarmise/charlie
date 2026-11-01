"""Consume existing registered observations; predictions cannot dispatch actions."""
class ShadowSubscriber:
    def __init__(self,service,candidate_id):
        service.candidate(candidate_id)
        self.service=service;self.candidate_id=candidate_id

    def consume(self,observation_id):
        try:
            record=self.service.shadow(self.candidate_id,observation_id)
            return dict(status='shadow',evidence_id=record.id,prediction=record.data['payload']['prediction'])
        except (OSError,ValueError,StopIteration) as exc:
            return dict(status='abstained',reason=str(exc),prediction=dict(label='unknown',mode='shadow'))


class RegisteredShadowPerception:
    """PR #13 scalar subscription adapter for source-owner evidence bookmarks.

    The capture/evidence owner publishes a retained observation ID; this adapter
    does not acquire or retain camera pixels. Requires PR #13's bus contract.
    """
    def __init__(self,bus,service,candidate_id,*,bookmark_source,output_source,observation_type=None,clock=None):
        import time
        if observation_type is None:
            from stimulus.bus import Observation
            observation_type=Observation
        self.clock=clock or time.monotonic
        self.bus=bus;self.service=service;self.output_source=output_source
        self.observation_type=observation_type;self.sequence=0
        self.worker=ShadowSubscriber(service,candidate_id)
        self.subscription=bus.subscribe_observations(bookmark_source,max_age=.25,clock=self.clock)
        bus.claim_observations(output_source,self,metadata=dict(modality='perception',mode='shadow',authority='none',task=service.adapter.task))

    def poll(self):
        import uuid
        if not hasattr(self,'generation'): self.generation=uuid.uuid4().hex
        value=self.subscription.read()
        if value is None:return None
        identifier=value.values.get('observation_id')
        try:
            record=self.service.journal.get(identifier)
            provenance=record.data['payload']['provenance']
            if provenance.get('source')!=value.source or provenance.get('generation')!=value.generation:
                raise ValueError('bookmark source/generation mismatch')
            result=self.worker.consume(identifier)
        except (KeyError,ValueError,TypeError):
            result=dict(status='abstained',prediction=dict(label='unknown',mode='shadow'))
        self.sequence+=1
        output=self.observation_type(source=self.output_source,sequence=self.sequence,received_at=self.clock(),
            values=result,provenance=dict(input_source=value.source,input_generation=value.generation,
            input_sequence=value.sequence,observation_id=identifier,authority='none'),generation=self.generation)
        self.bus.publish_observation(self.output_source,self,output)
        return result

    def close(self):
        self.subscription.close()
        self.bus.release_observations(self.output_source,self)
