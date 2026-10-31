"""Normal observational object mode: one source and one inference per fresh frame."""
from attention.manager import AttentionManager
from vision.camera_source import CameraSubscription
from vision.mobile_tracking import PetTracker
from vision.object_observation import object_observation


class ObjectRecognition:
    def __init__(self, frame_bus, perception, evidence, bus, labels=None, *, attention=None):
        self.perception, self.evidence, self.bus = perception, evidence, bus
        from stimulus.bus import StimulusBus
        self.owns_attention = attention is None
        self.attention_bus = StimulusBus() if attention is None else attention.bus
        self.attention = attention or AttentionManager(self.attention_bus, mobile_enabled=False, object_labels=labels)
        self.tracker = PetTracker()
        self.sources = CameraSubscription(frame_bus, on_change=self._source_changed, clock=perception.clock)
        self.stopped = self.closed = False
        self.generation = None

    def invalidate(self, reason):
        self.attention.object_attention = None
        self.attention.visual_target = None
        self.attention.handle_event('object_observation_fault', None)
        if self.attention.object_labels is not None:self.attention.object_labels.tick()
        # Tracking associations never survive camera/stream changes.
        self.tracker = PetTracker()
        self.perception.last_at = self.perception.last_id = None
        self.perception.detector.close()

    def _source_changed(self, old, new):
        self.invalidate('camera source switch')
        self.generation = None

    def select_camera(self, name):
        self.sources.switch(name)

    def acquisition_fault(self, error, metrics=None):
        self.invalidate(type(error).__name__)
        self.evidence.fault(error, metrics)

    def controls(self):
        # Recognition accepts only observational events. Legacy scan/track/calibration
        # events are never forwarded to AttentionManager in this mode.
        for event, data in self.bus.get_all():
            if event == 'camera_source':
                self.select_camera(data)
            elif event == 'object_recognition_stop':
                self.stopped = True
            elif event in ('object_attention','emergency_stop'):
                self.attention.handle_event(event, data)
        if self.owns_attention:self.attention.update(None)

    def step(self):
        if self.closed:
            raise InterruptedError('object recognition closed')
        try:
            self.controls()
            if self.stopped:
                return None
            frame = self.sources.read()
            if frame is None:
                return None
            generation = (frame.source, getattr(frame, 'stream_generation', None))
            if self.generation is not None and generation != self.generation:
                self.invalidate('camera stream changed')
            self.generation = generation
            store = getattr(self, 'artifact_store', None)
            selective = store is not None and hasattr(store, 'retain_observation')
            if store is not None and not selective:
                frame = self.artifact_store.retain(frame)
            observation = self.perception.observe(frame)
            if observation is None:
                return None
            if selective:
                receipt = store.retain_observation(frame, observation)
                observation['frame']['retention'] = receipt
                observation['frame']['artifact'] = receipt.get('artifact')
            tracking = self.tracker.update(observation)
            # Preserve original learning intake without a navigation planner/executor.
            proposal = dict(action='STOP', reason='object recognition is observational')
            execution = dict(dispatched=False, motion_authorized=False, reason='no execution backend')
            row = self.evidence.record(observation, tracking, proposal, execution)
            self.evidence.opportunities(row.id)
            packet = object_observation(observation)
            if getattr(self, 'output_allowed', lambda: True)():
                self.attention.handle_event('object_observation', packet)
                if self.attention.object_labels is not None:self.attention.object_labels.tick()
            return dict(observation=packet, evidence_id=row.id, provenance=observation, motion_authorized=False)
        except BaseException as exc:
            self.acquisition_fault(exc)
            raise

    def close(self):
        if self.closed:
            return
        self.stopped = True
        try:
            if self.owns_attention:self.attention.close()
            elif self.attention.object_labels is not None:
                self.attention.object_labels.invalidate()
                self.attention.object_labels.tick()
        finally:
            try:
                self.sources.close()
            finally:
                self.perception.detector.close()
                self.perception.depth.close()
        self.closed = True
