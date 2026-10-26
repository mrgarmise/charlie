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
        self.retention=None
        self.display_attention=None
        if hasattr(source,'on_fault'):source.on_fault=self.acquisition_fault
        if self.gate.backend is not None:raise ValueError('observation behavior has no physical execution backend')

    def acquisition_fault(self, error, metrics=None):
        self.tracker.invalidate(type(error).__name__)
        self.gate.close()
        for model in (self.perception.detector,self.perception.depth):
            if hasattr(model,'close'):model.close()
        self.evidence.fault(error,metrics)
        if self.bus is not None:
            self.bus.emit('mobile_observation',dict(target=None,target_lost=True,reason='acquisition_fault'))
            self.bus.emit('object_observation_fault',None)
            if self.display_attention is not None:self.display_attention.update(None)

    def step(self):
        self.frame_acquired=False
        try:
            frame=self.source.read()
            if frame is None:return None
            self.frame_acquired=True
            observation=self.perception.observe(frame)
            if observation is None:return None
            tracking=self.tracker.update(observation)
            proposal=self.navigator.propose(observation,tracking,observation['sensors'])
            execution=self.gate.execute(proposal)
            if self.retention is not None:
                artifact=self.retention(frame,observation,tracking)
                if artifact is not None:observation['frame']['artifact']=artifact
            row=self.evidence.record(observation,tracking,proposal,execution)
            self.evidence.opportunities(row.id)
            if self.bus is not None:
                emit_attention(self.bus,tracking,observation['frame'])
                from vision.object_observation import object_observation
                self.bus.emit('object_observation',object_observation(observation,tracking))
                if self.display_attention is not None:self.display_attention.update(None)
            return dict(observation=observation,tracking=tracking,proposal=proposal,execution=execution,evidence_id=row.id)
        except StopIteration:
            self.gate.close()
            raise
        except BaseException as exc:
            self.acquisition_fault(exc)
            raise

    def close(self):
        try:
            self.gate.close()
            if self.display_attention is not None:self.display_attention.close()
        finally:
            try:self.source.close()
            finally:
                for model in (self.perception.detector,self.perception.depth):
                    if hasattr(model,'close'):model.close()
