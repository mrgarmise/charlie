"""Publish existing interpretation results; never acquire pixels or run inference."""
from uuid import uuid4
from stimulus.bus import Observation


class DetectionPublication:
    def __init__(self, bus):
        self.bus=bus
        self.generation=uuid4().hex
        self.sequence=0
        self.sources=set()

    def publish(self, packet):
        source='object-detections:'+packet['source']
        if source not in self.sources:
            self.bus.claim_observations(source,self,metadata=dict(modality='object-hypotheses',
                body='ELEGOO' if packet['source']=='elegoo-v4' else 'Pi',clock='source receipt monotonic',
                acquisition='existing perception subscriber; not ground truth'))
            self.sources.add(source)
        self.sequence+=1
        self.bus.publish_observation(source,self,Observation(source,self.sequence,packet['at'],packet,
            {'interpretation_only':True},self.generation))

    def invalidate(self, reason):
        for source in self.sources:self.bus.observation_fault(source,self,reason)

    def close(self):
        for source in self.sources:self.bus.release_observations(source,self)
        self.sources.clear()
