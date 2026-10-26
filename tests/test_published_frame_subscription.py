"""Lossless subscriptions extend the existing passive publication; fake pixels only."""
from dataclasses import replace
import json
from pathlib import Path
import time
import pytest
from PIL import Image
from experiments.ppal.eyes.passive import PassivePublisher, PublishedFrameSubscription, atomic_json
from test_camera_sources import frame,wait_until


def test_cross_process_interface_preserves_pixels_timestamps_identity_and_freshness(tmp_path):
    at=time.monotonic()
    expected=frame(at=at)
    import hashlib
    # Explicit synthetic pixels; this exercises the real asynchronous publisher.
    subscription=PublishedFrameSubscription('pi-primary',directory=tmp_path,max_age=5)
    publisher=PassivePublisher(tmp_path,fps=5)
    try:
        assert subscription.read() is None
        metadata=expected.metadata()
        metadata['host_boot_id']=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        publisher.submit(Image.fromarray(expected.image[:,:,::-1]),timestamp=at,
                         metadata={'frame_subscription':metadata})
        wait_until(lambda:publisher.published>=1)
        actual=subscription.read()
        assert actual.id==expected.id and actual.source==expected.source
        assert actual.received_at==expected.received_at and actual.stream_generation==expected.stream_generation
        assert actual.camera_identity==expected.camera_identity
        assert actual.image.tobytes()==expected.image.tobytes()
        assert actual.authentic is False and not actual.image.flags.writeable
        assert subscription.read() is None
        second=PublishedFrameSubscription('pi-primary',directory=tmp_path,max_age=5)
        assert second.read().id==expected.id
        subscription.close()
        assert second.read() is None and publisher.thread.is_alive()
        document=json.loads((tmp_path/'latest.json').read_text())
        document['subscription_frame']['host_boot_id']='another-boot'
        atomic_json(tmp_path/'latest.json',document)
        with pytest.raises(ValueError,match='another boot'):second.read()
        second.close()
    finally:subscription.close();publisher.close()


def test_legacy_jpeg_cannot_be_promoted_to_a_source_frame(tmp_path):
    atomic_json(tmp_path/'latest.json',dict(raw={'image':'jpeg'},capture_timestamp=time.monotonic()))
    subscription=PublishedFrameSubscription('pi-primary',directory=tmp_path)
    assert subscription.read() is None
    subscription.close()


def test_independent_processes_subscribe_without_device_constructors(tmp_path):
    import subprocess,sys
    import hashlib
    script='''
import json,sys
from experiments.ppal.eyes.passive import PublishedFrameSubscription
from pathlib import Path
s=PublishedFrameSubscription('pi-primary',directory=Path(sys.argv[1]),max_age=5)
f=s.wait(timeout=3)
print(json.dumps(dict(source=f.source,id=f.id,pixels=f.image[0,0].tolist(),native_imported='picamera2' in sys.modules)))
s.close()
'''
    children=[subprocess.Popen([sys.executable,'-c',script,str(tmp_path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
              for _ in range(2)]
    publisher=PassivePublisher(tmp_path,fps=5)
    try:
        at=time.monotonic();snapshot=frame(at=at)
        metadata=dict(snapshot.metadata(),host_boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
        publisher.submit(Image.fromarray(snapshot.image[:,:,::-1]),timestamp=at,
                         metadata={'frame_subscription':metadata})
        records=[]
        for child in children:
            out,error=child.communicate(timeout=5)
            assert child.returncode==0,error
            records.append(json.loads(out))
        assert all(r==dict(source='pi-primary',id=snapshot.id,pixels=[30,20,10],native_imported=False) for r in records)
        assert publisher.thread.is_alive()
    finally:
        for child in children:
            if child.poll() is None:child.kill();child.wait()
        publisher.close()
