"""Software-only checks of the reconciled attention and source boundaries."""
from unittest.mock import Mock
from attention.manager import AttentionManager
from stimulus.bus import StimulusBus


def test_one_attention_manager_routes_pet_and_object_events():
    bus = StimulusBus()
    labels = Mock()
    manager = AttentionManager(bus, mobile_enabled=False, object_labels=labels)
    pet = Mock()
    pet.perception.clock.return_value = 1.0
    pet.readiness.return_value = {'pet_observe': {'available': True}, 'pet_follow': {'available': False}}
    pet.executive_resources = set()
    executive = Mock()
    executive.projects.return_value = {'p': {'method': 'pet_observe'}}
    executive.consider_mobile_attention.return_value = {'intent': 'observe'}
    registry = Mock()
    registry.describe.return_value = [{'id': 'pet_observe'}]
    manager.attach_pet_service(pet, executive, registry)
    result = {'tracking': {'target': {'id': 'cat'}}, 'evidence_id': 'fixture'}
    manager.handle_event('mobile_opportunity', result)
    pet.accept_attention.assert_called_once_with(result, {'intent': 'observe'})
    packet = {'schema': 'charlie.object-observation.v1', 'source': 'elegoo', 'frame_id': '1',
              'at': 1., 'clock_domain': 'pi-monotonic', 'objects': []}
    manager.handle_event('object_observation', packet)
    labels.observe.assert_called_once_with(packet, None)
    manager.handle_event('emergency_stop', None)
    pet.yield_attention.assert_called_once_with('emergency_stop')
    manager.close()


def test_compatibility_cameras_subscribe_without_opening_mjpeg(monkeypatch):
    from hardware.elegoo_camera import ElegooCamera
    from stimulus.bus import StimulusBus, install_application_frames, remove_application_frames
    bus = StimulusBus()
    monkeypatch.setattr('hardware.elegoo_camera.urllib.request.urlopen', Mock(side_effect=AssertionError('second capture')))
    install_application_frames(bus)
    a, b = ElegooCamera(), ElegooCamera()
    try:
        a.open(); b.open()
        assert a.subscription is not b.subscription
    finally:
        a.close(); b.close(); remove_application_frames(bus)


def test_mobile_fixture_uses_one_manager_for_pet_and_display(tmp_path, monkeypatch):
    import json
    import attention.manager
    from main import main
    original = attention.manager.AttentionManager
    created = []
    def create(*args, **kwargs):
        manager = original(*args, **kwargs)
        created.append(manager)
        return manager
    monkeypatch.setattr(attention.manager, 'AttentionManager', create)
    monkeypatch.setattr('learning.cycle.gameplay_active', lambda: False)
    path = tmp_path / 'fixture.json'
    path.write_text(json.dumps({'schema': 'charlie.mobile.fixture.v1', 'frames': [
        {'at': 1 + i * .25, 'objects': [{'label': 'cat', 'box': [10, 10, 30, 30], 'confidence': .9}],
         'depth': {'kind': 'relative', 'clearance_certified': False}, 'geometry': [40, 40]} for i in range(4)]}))
    main(['--mobile-replay', str(path), '--learning-state', str(tmp_path / 'state'),
          '--object-label-display', 'dry-run'])
    assert len(created) == 1
    assert created[0].object_labels is not None
    assert created[0].pet_service is not None
