"""Interface simulations, never independent physical games or learned efficacy."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from experiments.ppal.robotron_agency import VisualAgency


def test_terminal_observation_stops_probe_batch_before_another_command():
    agency=VisualAgency()
    count=[0]
    def read():
        count[0]+=1
        return []
    controller=Mock()
    assert agency.discover(read,controller,response_frames=3,should_stop=lambda:count[0]>=2) is None
    assert controller.execute.call_count==1
    assert agency.agency.self_id is None


def test_camera_or_controller_error_propagates_instead_of_retrying_commands():
    controller=Mock()
    with pytest.raises(OSError,match='camera failed'):
        VisualAgency().discover(Mock(side_effect=OSError('camera failed')),controller)
    controller.execute.assert_not_called()
    controller.execute.side_effect=ConnectionError('transport failed')
    with pytest.raises(ConnectionError):VisualAgency().discover(lambda:[],controller)
    assert controller.execute.call_count==1


def test_explicit_stop_or_deadline_prevents_even_fire_exploration():
    controller=Mock()
    agency=VisualAgency(bootstrap_body_fire=True)
    assert agency.discover(lambda:[],controller,should_stop=lambda:True) is None
    controller.execute.assert_not_called()


def test_positive_gameplay_can_begin_agency_without_recognized_regions(tmp_path,monkeypatch):
    from experiments.ppal import play_robotron as play
    clock=[0.]
    def read():
        clock[0]+=.1
        return Image.new('RGB',(100,100))
    source=SimpleNamespace(read=read)
    monkeypatch.setattr(play.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(play.time,'sleep',lambda duration:None)
    result=play._wait_for_gameplay(source,SimpleNamespace(apply=lambda frame:frame),
        SimpleNamespace(detect=lambda frame:[]),tmp_path,generic_ready=True,
        classifier=lambda frame:dict(state='gameplay',phase='gameplay'))
    assert result[0] is None and result[1]=='generic_visual_ready'
    assert len(result[3])==3


def test_unsupported_response_window_is_rejected_without_commands():
    controller=Mock()
    with pytest.raises(ValueError):VisualAgency().discover(lambda:[],controller,response_frames=100)
    controller.execute.assert_not_called()
