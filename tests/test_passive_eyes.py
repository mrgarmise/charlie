import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from urllib.request import urlopen

import numpy as np
from PIL import Image
import pytest

from experiments.ppal.eyes.passive import PassivePublisher, atomic_json, read_json
from experiments.ppal.eyes.camera_lease import CameraLease, camera_owner
from experiments.ppal.eyes.passive_viewer import Viewer, make_server
from experiments.ppal.observation_camera import ObservedCamera


def until(predicate, seconds=2):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if predicate():return
        time.sleep(.01)
    raise AssertionError('condition timed out')


def test_latest_only_raw_crop_and_provisional_evidence(tmp_path):
    publisher=PassivePublisher(tmp_path,fps=5,context={'project':{'id':'p','goal':'tentative question'}})
    atomic_json(tmp_path/'demand.json',{'at':time.monotonic()})
    raw=Image.new('RGB',(1280,720),'red');crop=Image.new('RGB',(640,480),'blue')
    for index in range(100):
        publisher.submit(raw,timestamp=index,playfield=crop,metadata={'agency':{
            'identity_status':'provisional','controlled_track_id':9,'self_track_id':None,
            'tracking':{'detections':[{'track_id':9,'box':[1,2,3,4]}]}}})
    until(lambda:publisher.published==1)
    packet=read_json(tmp_path/'latest.json')
    assert packet['capture_timestamp']==99
    assert packet['raw']['size']==[1280,720] and packet['playfield']['size']==[640,480]
    assert raw.size==(1280,720) and raw.getpixel((0,0))==(255,0,0)
    assert packet['evidence']['agency']['self_track_id'] is None
    assert packet['evidence']['agency']['identity_status']=='provisional'
    assert packet['evidence']['learning_project']['id']=='p'
    assert publisher.dropped>=99 and publisher.pending.maxsize==1
    publisher.close()


def test_detached_observer_has_no_encoding_and_failures_do_not_escape(tmp_path,monkeypatch):
    p=PassivePublisher(tmp_path,fps=5)
    p.submit(Image.new('RGB',(32,32)),timestamp=1)
    time.sleep(.25);assert p.published==0 and p.encode_seconds==0
    atomic_json(tmp_path/'demand.json',{'at':time.monotonic()})
    monkeypatch.setattr(p,'jpeg',lambda _:(_ for _ in ()).throw(OSError('failed codec')))
    p.submit(Image.new('RGB',(32,32)),timestamp=2)
    until(lambda:p.errors==1)
    assert p.thread.is_alive();p.close()


def test_http_reuses_frames_without_camera_or_tracking_pass(tmp_path):
    lease=CameraLease(directory=tmp_path)
    p=PassivePublisher(tmp_path,fps=5)
    viewer=Viewer(tmp_path,idle=True,camera_factory=lambda:pytest.fail('second camera opened'))
    server=make_server(viewer,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url=f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(url+'/frame') as response:assert json.load(response)['status']=='unavailable'
        p.submit(Image.new('RGB',(64,64)),timestamp=time.monotonic(),metadata={'phase':'tracking'})
        until(lambda:p.published==1)
        with urlopen(url+'/frame') as response:assert json.load(response)['status']=='passive'
        with urlopen(url+'/') as response:assert b'dashed amber' in response.read()
        time.sleep(.4)
        assert viewer.preview is None
    finally:server.shutdown();server.server_close();viewer.close();p.close();lease.close()


def test_idle_preview_releases_on_close_and_unknown(tmp_path):
    opened=[]
    class Camera:
        def __init__(self):self.lease=CameraLease('preview',tmp_path);self.closed=False;opened.append(self)
        def read(self):return np.zeros((48,64,3),dtype=np.uint8)
        def close(self):self.closed=True;self.lease.close()
    viewer=Viewer(tmp_path,idle=True,camera_factory=Camera)
    assert viewer.frame()['status']=='unavailable'
    until(lambda:viewer.preview is not None)
    until(lambda:(tmp_path/'latest.json').exists())
    frame=viewer.frame()
    assert frame['status']=='idle preview' and frame['evidence']['identity_status']=='unknown'
    viewer.close();assert opened[0].closed and camera_owner(tmp_path)=={}


def preview_child(directory,ready):
    lease=CameraLease('preview',Path(directory));stop=threading.Event()
    signal.signal(signal.SIGUSR1,lambda *_:stop.set());ready.set()
    stop.wait(3);lease.close()


def test_active_camera_preempts_preview_before_capture(tmp_path):
    context=multiprocessing.get_context('spawn');ready=context.Event()
    child=context.Process(target=preview_child,args=(str(tmp_path),ready));child.start()
    try:
        assert ready.wait(2)
        lease=CameraLease('active',tmp_path)
        assert lease.handoff_seconds<1
        assert camera_owner(tmp_path)['purpose']=='active'
        with pytest.raises(RuntimeError):CameraLease('preview',tmp_path)
        with pytest.raises(RuntimeError):CameraLease('active',tmp_path)
        lease.close()
    finally:child.join(timeout=3);assert not child.is_alive()


def test_stale_owner_is_not_live_and_stale_packet_not_displayed(tmp_path):
    atomic_json(tmp_path/'owner.json',{'pid':os.getpid(),'purpose':'active'})
    assert camera_owner(tmp_path)=={}
    lease=CameraLease(directory=tmp_path)
    atomic_json(tmp_path/'latest.json',dict(producer_pid=os.getpid(),published_at=time.monotonic()-4))
    viewer=Viewer(tmp_path)
    assert viewer.frame()['status']=='unavailable'
    viewer.close();lease.close()


def test_observed_camera_publishes_existing_read_once(tmp_path):
    class Source:
        calls=0
        def read(self):self.calls+=1;return Image.new('RGB',(32,32))
    source=Source();publisher=PassivePublisher(tmp_path)
    observed=ObservedCamera(source,publisher=publisher)
    frame=observed.read()
    assert observed.raw is frame and source.calls==1 and publisher.offers==1
    publisher.close()


def test_eof_shuts_down_remote_server_without_systemd(tmp_path):
    import socket
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    env=dict(os.environ,XDG_RUNTIME_DIR=str(tmp_path))
    proc=subprocess.Popen([sys.executable,'-m','experiments.ppal.eyes.passive_viewer',
        '--port',str(port),'--exit-on-stdin-close'],stdin=subprocess.PIPE,env=env)
    def available():
        try:
            with urlopen(f'http://127.0.0.1:{port}/frame',timeout=.1) as r:return r.status==200
        except OSError:return False
    try:
        until(available);proc.stdin.close();assert proc.wait(timeout=3)==0
    finally:
        if proc.poll() is None:proc.kill();proc.wait()


def test_mint_installer_and_remote_command_quote_paths(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('launcher','setup/charlie_eyes_launcher.py')
    launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
    assert '--exit-on-stdin-close' in launcher.remote_command('Projects/charlie','./.venv/bin/python')
    assert "'Projects/a b'" in launcher.remote_command('Projects/a b','./.venv/bin/python')
    env=dict(os.environ,HOME=str(tmp_path))
    subprocess.run([sys.executable,'setup/install_charlie_eyes_mint.py','--host','five@charlie'],env=env,check=True)
    desktop=(tmp_path/'.local/share/applications/charlie-eyes.desktop').read_text()
    assert 'Terminal=false' in desktop and 'five@charlie' in desktop and 'systemd' not in desktop
    assert (tmp_path/'.local/share/charlie-eyes/launcher.py').exists()


def test_camera_wrapper_releases_driver_and_lease_on_failure(tmp_path,monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setenv('XDG_RUNTIME_DIR',str(tmp_path))
    class Picamera:
        def __init__(self):self.closed=False
        def create_preview_configuration(self,**_):return {}
        def configure(self,_):pass
        def start(self):pass
        def stop(self):raise OSError('stop failure')
        def close(self):self.closed=True
    monkeypatch.setitem(sys.modules,'libcamera',SimpleNamespace(controls=SimpleNamespace()))
    monkeypatch.setitem(sys.modules,'picamera2',SimpleNamespace(Picamera2=Picamera))
    spec=importlib.util.spec_from_file_location('tested_camera','vision/camera.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    camera=module.Camera()
    with pytest.raises(RuntimeError):module.Camera()
    with pytest.raises(OSError):camera.close()
    assert camera.picam2.closed and camera.lease.closed
    camera.close()  # idempotent
    lease=CameraLease(directory=camera.lease.directory);lease.close()
    import experiments.ppal.eyes.camera_lease as leases
    monkeypatch.setattr(leases,'CameraLease',lambda *_:(_ for _ in ()).throw(OSError('observer storage unavailable')))
    fallback=module.Camera()
    assert fallback.lease is None and fallback.lease_error
    with pytest.raises(OSError):fallback.close()
    with pytest.raises(OSError):module.Camera(purpose='preview')


def test_launcher_window_exit_closes_ssh_input_and_remote_lifetime(monkeypatch):
    from io import BytesIO
    spec=importlib.util.spec_from_file_location('tested_launcher','setup/charlie_eyes_launcher.py')
    launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
    launched=[]
    class Process:
        def __init__(self,cmd,**kwargs):
            self.cmd=cmd;self.stdin=BytesIO() if cmd[0]=='ssh' else None;launched.append(self)
        def poll(self):return None if self.stdin else 0
        def wait(self,**kwargs):
            if self.stdin:assert self.stdin.closed
            return 0
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*_):pass
    monkeypatch.setattr(launcher,'browser_command',lambda *_:['owned-browser'])
    monkeypatch.setattr(launcher.subprocess,'Popen',Process)
    monkeypatch.setattr(launcher,'urlopen',lambda *_args,**_kwargs:Response())
    monkeypatch.setattr(launcher,'notify',lambda message:pytest.fail(message))
    monkeypatch.setattr(sys,'argv',['launcher','--host','five@charlie'])
    launcher.main()
    assert launched[0].stdin.closed and '--exit-on-stdin-close' in launched[0].cmd[-1]
    assert launched[1].cmd==['owned-browser']


def test_live_latency_comparison_preserves_unmeasured_data():
    from experiments.ppal.eyes.compare_passive_runs import summarize
    rows=[]
    for attached,offset in ((False,10),(True,20)):
        for n in range(2):
            at=offset+n*.4
            rows.append(dict(capture_timestamp=at,control_execution={'started_at':at+.1},
                viewer_state={'attached':attached,'checked_at':at-.2},identity_status='provisional'))
    result=summarize([{'steps':rows}])
    assert result['attached']['samples']==2
    assert result['detached']['capture_to_controller_start_ms_mean']==pytest.approx(100)
    assert result['attached']['ordinary_action_cadence_hz']==pytest.approx(2.5)
    unknown=summarize([{'steps':[{'capture_timestamp':1,'action_timestamp':1.1}]}])
    assert unknown['attached']['ordinary_action_cadence_hz'] is None
