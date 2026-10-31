"""Legacy face motion is unavailable until independently qualified migration."""
from unittest.mock import Mock
import pytest
from motion.mobile_base import LegacyMotionUnavailable, MobileBase


@pytest.mark.parametrize('name,args', [
    ('pan', (90,)), ('pivot', ('LEFT',)),
    ('begin_attention_align', (120,)), ('update_attention_align', (True,)),
])
def test_legacy_motion_cannot_open_transport_or_issue_command(name, args):
    base = MobileBase()
    base.car = Mock()
    with pytest.raises(LegacyMotionUnavailable, match='qualified actuator executor'):
        getattr(base, name)(*args)
    base.car.assert_not_called()
    assert base.car.mock_calls == []


def test_stop_and_qualified_pulse_facade_are_not_removed():
    base = MobileBase(); base.car = Mock()
    base.stop()
    base.car.stop.assert_called_once_with()
    base.pulse('LEFT', lease='passed-to-existing-qualified-boundary')
    base.car.pulse.assert_called_once_with('LEFT', lease='passed-to-existing-qualified-boundary')
