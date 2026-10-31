"""Synthetic exact-pixel decisions; capacity never authorizes or stops sensing."""
from unittest.mock import Mock

import pytest

from tests.test_object_recognition import setup_session, packet
from vision.mobile_perception import FrameArtifactStore, SelectiveFrameArtifacts


def test_full_store_preserves_pixels_and_keeps_real_pipeline_observing(tmp_path):
    s = setup_session(tmp_path)
    store = FrameArtifactStore(tmp_path/'pixels', max_bytes=1)
    s.session.artifact_store = SelectiveFrameArtifacts(store)
    try:
        s.session.select_camera('pi')
        for seq in range(10):
            s.now[0] = 1.+seq*.3
            s.frames.publish_frame('pi-primary', s.pi, packet(s.now[0], sequence=seq))
            row = s.session.step()
            receipt = row['provenance']['frame']['retention']
            assert receipt['status'] == 'not_retained'
            assert receipt['reason'] == 'cumulative_pixel_budget_exhausted'
            assert receipt['frame_id'] == row['provenance']['frame']['id']
            assert receipt['pixel_sha256'] == row['provenance']['frame']['sha256']
            assert row['provenance']['frame']['artifact'] is None
            assert not row['motion_authorized']
        assert s.session.perception.stats['processed'] == 10
        assert s.labels.current == ('pi-primary', 'CHAIR')
        assert not list(store.directory.glob('*.png'))
    finally:
        s.session.close(); s.transport.close(); s.journal.close()


def test_sampling_binds_exact_pixels_and_limits_encoding_across_restarts(tmp_path):
    store = FrameArtifactStore(tmp_path/'pixels')
    retain = store.retain = Mock(wraps=store.retain)
    policy = SelectiveFrameArtifacts(store, interval=5, max_samples=3)
    receipts=[]
    for seq in range(75):
        frame=packet(1.+seq*.2, sequence=seq)
        observation=dict(objects=[dict(label='chair')], frame=frame.metadata())
        receipts.append(policy.retain_observation(frame, observation))
    assert retain.call_count == 3
    assert sum(r['status']=='retained' for r in receipts) == 3
    assert any(r['status']=='not_selected' for r in receipts)
    before={p.name:p.read_bytes() for p in store.directory.glob('*.png')}
    # A new session gets its own selection context and the same cumulative cap.
    restarted=SelectiveFrameArtifacts(FrameArtifactStore(store.directory, max_bytes=1))
    frame=packet(20.,sequence=100)
    receipt=restarted.retain_observation(frame,dict(objects=[],frame=frame.metadata()))
    assert receipt['status'] in ('retained','not_retained')  # duplicate PNG needs no bytes
    assert {p.name:p.read_bytes() for p in store.directory.glob('*.png')} == before


def test_unexpected_storage_errors_remain_visible(tmp_path):
    store=FrameArtifactStore(tmp_path/'pixels')
    store.retain=Mock(side_effect=OSError('disk failure'))
    frame=packet(1.,sequence=1)
    with pytest.raises(OSError,match='disk failure'):
        SelectiveFrameArtifacts(store).retain_observation(frame,dict(objects=[],frame=frame.metadata()))
