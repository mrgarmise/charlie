"""Publish durable development lifecycle records on the existing stimulus bus."""

from time import monotonic
from uuid import uuid4

from stimulus.bus import Observation


class LifecyclePublication:
    def __init__(self, bus, factory, mission):
        self.bus, self.factory, self.mission = bus, factory, mission
        self.source = f"sandbox:{mission}"
        self.generation = uuid4().hex
        self.owner = object()
        self.cursor = 0

    def __enter__(self):
        self.bus.claim_observations(self.source, self.owner,
                                    metadata={"schema": 1, "mode": "development"})
        return self

    def flush(self):
        while page := self.factory.events(self.mission, after=self.cursor):
            for event in page:
                self.bus.publish_observation(
                    self.source, self.owner,
                    Observation(self.source, event["sequence"], monotonic(), event,
                                {"schema": 1, "durable": True}, self.generation))
                self.cursor = event["sequence"]

    def __exit__(self, *_):
        self.bus.release_observations(self.source, self.owner)
