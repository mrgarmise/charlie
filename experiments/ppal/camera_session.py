"""One live camera and current-observation calibration per marathon.

Saved visual evidence is only a candidate; fresh confirmation remains mandatory. Episode borrowers cannot close the hardware.
The owner must be closed before offline learning or another marathon.
"""
from uuid import uuid4


class CameraSession:
    def __init__(self, factory):
        self.factory = factory
        self.id = 'camera-session:' + uuid4().hex
        self.source = None
        self.calibration = None
        self.report = None
        self.reference = None
        self.origin = None
        self.closed = False
        self.invalid = False

    def borrow(self):
        if self.closed or self.invalid:
            raise RuntimeError('camera session closed or invalid; new marathon preflight required')
        if self.source is None:
            self.source = self.factory()
        return _BorrowedCamera(self)

    def establish(self, source, output, preflight, *, seed_position=None):
        if self.closed or self.invalid:
            raise RuntimeError('invalid camera session')
        reused = self.calibration is not None
        if not reused:
            self.calibration, self.report = preflight(source, output, seed_position=seed_position)
            if self.calibration is None or self.report.get('status')!='usable':
                self.invalid=True
                raise ValueError('current camera preflight did not qualify a usable view')
            frame=getattr(source,'raw',None)
            if frame is not None:self.reference=self.calibration.apply(frame).copy()
            self.origin = str(output.resolve())
        elif self.report.get('visual_readiness') is not None:
            from .eyes.visual_readiness import confirm_view, record_view
            from learning.foundry import atomic_json
            handoff={}
            try:
                self.calibration, frame = confirm_view(source, self.report['visual_readiness'], report=handoff)
            except Exception:
                self.invalid=True
                raise
            self.reference=self.calibration.apply(frame).copy()
            record=record_view(self.calibration, handoff['focus'], frame, origin=output,
                               observations=handoff['observations'])
            self.report=dict(self.report, viewpoint_handoff=handoff, visual_readiness=record,
                             quality=handoff['quality'])
            output.mkdir(parents=True, exist_ok=True)
            atomic_json(output/'visual-readiness.json',record)
        return self.calibration, dict(self.report, camera_session=dict(
            id=self.id, reused=reused, qualification_origin=self.origin,
            scope='current uninterrupted live camera session; not a saved profile'))

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.source is not None:
            self.source.close()


class _BorrowedCamera:
    def __init__(self, owner):
        self.owner = owner

    def __getattr__(self, name):
        return getattr(self.owner.source, name)

    def close(self):
        # Episode recorder and controller are closed separately by the player.
        pass
