"""Exercise preserved legacy behavior using fake motion, never real transport."""
from unittest.mock import Mock
import pytest
import behaviors.mobile_face_track as faces
from hardware.elegoo_mobile import ElegooMobileBase
from attention.manager import AttentionManager
from stimulus.bus import StimulusBus


def test_legacy_look_attend_and_loss_cancel(monkeypatch):
    mobile=Mock();mobile.begin_attention_align.return_value=True
    monkeypatch.setattr(faces,'MobileBase',lambda:mobile)
    monkeypatch.setattr(faces.time,'sleep',lambda _:None)
    behavior=faces.MobileFaceTrackBehavior()
    assert behavior.update_face(dict(normalized_x=.5))['state']=='CENTERED'
    mobile.pan.assert_not_called()
    assert behavior.update_face(dict(normalized_x=.1))['state']=='LOOK'
    mobile.pan.assert_called_once_with(120)
    assert behavior.update_face(dict(normalized_x=.1))['state']=='ATTEND_START'
    mobile.begin_attention_align.assert_called_once_with(120,max_rotation=15)
    behavior.face_history.clear()  # Isolate hold/cancellation from preserved predictive LOOK.
    assert behavior.update_face(None)['state']=='LOST_HOLD'
    mobile.cancel_attention_align.assert_called_once_with('face_lost')


def test_yaw_error_wrong_way_and_loss_stop_without_sockets(monkeypatch):
    for scenario in ('lost','yaw-error','wrong-way'):
        car=ElegooMobileBase();car.yaw=Mock(return_value=0)
        car.start_pivot=Mock();car.stop=Mock()
        assert car.begin_attention_align(120)
        if scenario=='yaw-error':car.yaw.side_effect=ValueError('bad telemetry')
        elif scenario=='wrong-way':car.yaw.return_value=20
        result=car.update_attention_align(face_visible=scenario!='lost')
        assert result['done'];car.stop.assert_called_once()


def test_rich_mobile_event_does_not_initialize_either_body():
    attention=AttentionManager(StimulusBus(),mobile_enabled=True)
    attention.handle_event('mobile_observation',dict(target=dict(label='cat')))
    assert attention.mobile is None and attention.pending is None


def test_stock_stop_fallback_is_preserved_with_mock_transport():
    car=ElegooMobileBase();car.sock=object();car._send=Mock(side_effect=[TimeoutError(),{}])
    car.stop()
    assert car._send.call_args_list[0].args[0]['N']==1
    assert car._send.call_args_list[1].args[0]['N']==102
