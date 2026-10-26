"""Synthetic RAM history regression; no native devices or evidence claims."""
from dataclasses import replace
import pytest
from stimulus.bus import StimulusBus
from test_camera_sources import frame


def test_late_subscribers_history_and_provenance_do_not_control_capture():
    bus = StimulusBus(history_frames=2, history_bytes=1000)
    owner = object()
    bus.claim_frames('pi-primary', owner)
    slow = bus.subscribe_frames('pi-primary', clock=lambda: 1.)
    original = frame()
    bus.publish_frame('pi-primary', owner, original)
    original.camera_identity['device'] = 'producer mutation'
    for seq in (2, 3):
        bus.publish_frame('pi-primary', owner, frame(sequence=seq))
    late = bus.subscribe_frames('pi-primary', clock=lambda: 1.)
    assert late.read().sequence == slow.read().sequence == 3
    assert slow.dropped == 2
    history = bus.recent_frames('pi-primary', clock=lambda: 1.)
    assert [f.sequence for f in history] == [2, 3]
    history[-1].camera_identity['device'] = 'consumer mutation'
    assert bus.latest_frame('pi-primary', clock=lambda: 1.).camera_identity == {'device': 'fixture'}
    assert bus.frame_evictions['pi-primary'] == 1
    late.close()
    assert bus.frame_owners['pi-primary'] is owner and not slow.closed


def test_history_byte_budget_expiry_fault_and_recovery_are_explicit():
    bus = StimulusBus(history_frames=10, history_bytes=144)
    owner = object()
    bus.claim_frames('pi-primary', owner)
    for seq in (1, 2, 3):
        bus.publish_frame('pi-primary', owner, frame(sequence=seq))
    assert len(bus.recent_frames('pi-primary', clock=lambda: 1.)) == 2
    assert bus.latest_frame('pi-primary', clock=lambda: 9.) is None
    assert bus.latest_frame('pi-primary', clock=lambda: 0.) is None
    with pytest.raises(PermissionError):
        bus.frame_fault('pi-primary', object(), 'unauthorized')
    assert bus.latest_frame('pi-primary', clock=lambda: 1.).sequence == 3
    bus.frame_fault('pi-primary', owner, 'thermal suspension')
    with pytest.raises(OSError, match='thermal suspension'):
        bus.recent_frames('pi-primary', clock=lambda: 1.)
    late = bus.subscribe_frames('pi-primary', clock=lambda: 1.)
    with pytest.raises(OSError, match='thermal suspension'):
        late.read()
    bus.publish_frame('pi-primary', owner, replace(frame(), stream_generation='recovered'))
    assert late.read().stream_generation == 'recovered'
    bus.release_frames('pi-primary', owner)
    with pytest.raises(OSError, match='stopped'):
        bus.latest_frame('pi-primary', clock=lambda: 1.)


def test_ordering_generation_and_oversize_retention():
    bus = StimulusBus(history_bytes=1000)
    owner = object()
    bus.claim_frames('pi-primary', owner)
    bus.publish_frame('pi-primary', owner, frame(sequence=3))
    for value in (frame(sequence=3), frame(sequence=2), frame(sequence=4, at=.9)):
        with pytest.raises(ValueError, match='out-of-order'):
            bus.publish_frame('pi-primary', owner, value)
    bus.publish_frame('pi-primary', owner, replace(frame(), stream_generation='new'))
    assert len(bus.recent_frames('pi-primary', clock=lambda: 1.)) == 1
    tiny = StimulusBus(history_bytes=1)
    tiny.claim_frames('pi-primary', owner)
    consumer = tiny.subscribe_frames('pi-primary', clock=lambda: 1.)
    tiny.publish_frame('pi-primary', owner, frame())
    assert consumer.read().id == '1'  # live delivery survives history budget
    assert tiny.latest_frame('pi-primary', clock=lambda: 1.) is None
    assert tiny.frame_evictions['pi-primary'] == 1
    with pytest.raises(ValueError):
        StimulusBus(history_frames=0)
