"""One unarmed sensing step in Charlie's existing behavior namespace."""
from experiments.ppal.mobile_navigation import MobileNavigator, MobileExecutionGate
from vision.mobile_tracking import PetTracker, emit_attention


class MobileObserveBehavior:
    def __init__(self, source, perception, evidence, *, tracker=None, navigator=None, gate=None, bus=None):
        self.source,self.perception,self.evidence=source,perception,evidence
        self.tracker=tracker or PetTracker()
        self.navigator=navigator or MobileNavigator(clock=perception.clock)
        self.gate=gate or MobileExecutionGate(clock=perception.clock)
        self.bus=bus
        if self.gate.backend is not None:raise ValueError('observation behavior has no physical execution backend')

    def step(self):
        try:
            frame=self.source.read()
            observation=self.perception.observe(frame)
            if observation is None:return None
            tracking=self.tracker.update(observation)
            proposal=self.navigator.propose(observation,tracking,observation['sensors'])
            execution=self.gate.execute(proposal)
            row=self.evidence.record(observation,tracking,proposal,execution)
            self.evidence.opportunities(row.id)
            if self.bus is not None:emit_attention(self.bus,tracking,observation['frame'])
            return dict(observation=observation,tracking=tracking,proposal=proposal,execution=execution,evidence_id=row.id)
        except StopIteration:
            self.gate.close()
            raise
        except BaseException as exc:
            self.gate.close()
            self.evidence.fault(exc)
            raise

    def close(self):
        try:self.gate.close()
        finally:self.source.close()
