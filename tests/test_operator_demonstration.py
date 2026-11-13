"""Real attention/perception/serializer and loopback requests; no device access."""
import hashlib
import http.client
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import pytest
from attention.manager import AttentionManager
from learning.demonstration import Demonstration, ABILITY
from stimulus.bus import StimulusBus
from tests.test_object_recognition import setup_session, packet


def request(service, **changes):
    status=service.status()
    row=dict(id=str(uuid4()),ability=ABILITY,camera='pi-primary',duration=15,
             boot=status['boot'],nonce=status['nonce'],action='start')
    row.update(changes)
    return row


def fixture(tmp_path):
    s=setup_session(tmp_path)
    # Use exactly the fixture's existing attention, pipeline, model and serial owner.
    s.service=Demonstration(s.session.attention,lambda execution:s.session,tmp_path,clock=lambda:s.now[0])
    s.session.output_allowed=lambda:s.service.running and not s.service.cancel_requested and s.now[0]-s.service.started<15
    return s


def start(s):
    row=s.service.submit(request(s.service))
    assert row['state']=='requested'
    s.session.attention.update(None)
    assert s.service.running
    return row


def feed(s,at,seq):
    s.now[0]=at
    s.frames.publish_frame('pi-primary',s.pi,packet(at,sequence=seq))
    s.service.tick()


def close(s):
    s.service.close();s.session.close();s.transport.close();s.journal.close()


def test_real_pipeline_stabilizes_journals_and_ends_without_motion(tmp_path):
    s=fixture(tmp_path)
    other=s.frames.subscribe_frames('pi-primary',clock=lambda:s.now[0])
    try:
        row=start(s)
        for i,at in enumerate((1.,1.11,1.22)):feed(s,at,i)
        assert other.read().id=='pi-primary2'
        assert s.labels.current==('pi-primary','CHAIR')
        s.now[0]=16.;s.service.tick()
        status=s.service.status()['session']
        assert status['state']=='completed' and status['elapsed_seconds']==15
        assert status['display_acknowledgments']==1
        assert status['physical_display']=='unobserved' and not status['motion_authorized']
        assert s.frames.frame_owners=={'pi-primary':s.pi,'elegoo-v4':s.elegoo}
        assert s.session.sources.closed and s.labels.current is None
        records=s.service.db.execute('SELECT body,sha256 FROM events').fetchall()
        assert all(hashlib.sha256(b.encode()).hexdigest()==h for b,h in records)
        observation=[json.loads(b)['event']['result'] for b,h in records if '"result"' in b][0]
        assert observation['provenance']['model'][0]['backend']=='offline-fixture'
        assert observation['provenance']['frame']['source']=='pi-primary'
        assert observation['evidence_id']
    finally:other.close();close(s)


@pytest.mark.parametrize('changes',[{'duration':14},{'duration':True},{'camera':'elegoo-v4'},
    {'ability':'pet_follow'},{'action':'move'},{'id':'bad'},{'motion':True},{'nonce':[]},{'duration':float('nan')}])
def test_request_arguments_are_strict(tmp_path,changes):
    s=fixture(tmp_path)
    try:
        with pytest.raises((ValueError,TypeError)):s.service.submit(request(s.service,**changes))
        assert s.service.active is None
    finally:close(s)


def test_replay_concurrent_and_cancel_before_dispatch(tmp_path):
    s=fixture(tmp_path)
    try:
        req=request(s.service);s.service.submit(req)
        with pytest.raises(ValueError,match='replay'):s.service.submit(req)
        with pytest.raises(ValueError,match='another'):s.service.submit(request(s.service))
        with pytest.raises(ValueError,match='duplicate'):s.service.submit(request(s.service,id=req['id']))
        s.service.submit(request(s.service,id=req['id'],action='cancel'))
        s.session.attention.update(None)
        assert s.service.status()['session']['state']=='cancelled'
        assert s.service.pipeline is None
    finally:close(s)


def test_expired_and_foreign_boot_requests(tmp_path):
    s=fixture(tmp_path)
    try:
        req=request(s.service);s.now[0]+=31
        with pytest.raises(ValueError,match='stale'):s.service.submit(req)
        with pytest.raises(ValueError,match='foreign'):s.service.submit(request(s.service,boot='old'))
    finally:close(s)


def test_restart_cancels_unfinished_session_and_old_requests(tmp_path):
    s=fixture(tmp_path)
    start(s);old=request(s.service)
    # Simulate lost process without orderly service.close().
    s.service.db.close()
    __import__('os').close(s.service.owner_fd)
    restored=Demonstration(s.session.attention,Mock(),tmp_path,clock=lambda:s.now[0])
    s.service=restored
    try:
        assert restored.status()['session']['reason'].startswith('application_restarted')
        with pytest.raises(ValueError,match='foreign'):restored.submit(old)
        restored.factory.assert_not_called()
    finally:close(s)


@pytest.mark.parametrize('kind',['priority','pending','face','pet','emergency','unknown_behavior','display'])
def test_busy_or_unready_attention_rejects_without_acquisition(tmp_path,kind):
    s=fixture(tmp_path);a=s.session.attention;s.service.factory=Mock()
    if kind=='priority':a.priority=80
    if kind=='pending':a.pending=(Mock(),50)
    if kind=='face':a.face_service=Mock()
    if kind=='pet':a.pet_service=Mock()
    if kind=='emergency':a.emergency_stopped=True
    if kind=='unknown_behavior':a.active=Mock()
    if kind=='display':a.object_labels=None
    try:
        req=s.service.submit(request(s.service));s.service.begin(req['id'])
        assert s.service.status()['session']['state']=='unavailable'
        s.service.factory.assert_not_called()
    finally:a.pending=None;close(s)


@pytest.mark.parametrize('interrupt',['cancel','emergency_stop','scan'])
def test_interrupt_releases_subscription_and_display(tmp_path,interrupt):
    s=fixture(tmp_path)
    try:
        row=start(s)
        for i,at in enumerate((1.,1.11,1.22)):feed(s,at,i)
        if interrupt=='cancel':s.service.submit(request(s.service,id=row['id'],action='cancel'));s.service.tick()
        else:s.session.attention.handle_event(interrupt,None)
        assert s.service.status()['session']['state']=='cancelled'
        assert s.session.sources.closed
        assert s.labels.current is None
        assert s.session.attention.emergency_stopped == (interrupt=='emergency_stop')
    finally:s.session.attention.pending=None;close(s)


def test_no_object_camera_loss_model_unavailable_and_serial_failure(tmp_path):
    s=fixture(tmp_path)
    try:
        s.detector.infer=lambda frame:[]
        start(s);feed(s,1.,1)
        s.now[0]=16.;s.service.tick()
        assert s.service.status()['session']['reason']=='no_recognizable_objects'
    finally:close(s)
    for mode in ('camera','model','serial','stall'):
        folder=tmp_path/mode;folder.mkdir();s=fixture(folder)
        try:
            if mode=='model':s.service.factory=Mock(side_effect=OSError('model unavailable'))
            row=s.service.submit(request(s.service));s.service.begin(row['id'])
            if mode=='model':assert s.service.status()['session']['state']=='unavailable';continue
            if mode=='camera':
                s.frames.frame_fault('pi-primary',s.pi,'lost');s.service.tick()
            if mode=='serial':s.transport.show_object_label=lambda *args:False
            if mode=='stall':s.now[0]=3.1;s.service.tick()
            else:
                for i,at in enumerate((1.,1.11,1.22)):feed(s,at,i)
            assert s.service.status()['session']['state']=='failed'
        finally:close(s)


def test_deadline_discards_late_display_and_idle_bookmark_is_retained(tmp_path):
    from behaviors.idle import IdleBehavior
    s=fixture(tmp_path);a=s.session.attention;deck=Mock()
    idle=IdleBehavior();idle.enter(deck);idle.last_move=123;idle.update=Mock()
    a.active=idle
    notebook=tmp_path/'development-bookmark.json';notebook.write_text('{"project":"original","hypothesis":"unchanged"}')
    original=notebook.read_bytes()
    try:
        start(s);a.update(deck);idle.update.assert_not_called()
        infer=s.detector.infer
        def late(frame):s.now[0]=16.1;return infer(frame)
        s.detector.infer=late
        feed(s,15.9,1)
        assert not any(x.startswith('OBJECT_LABEL') for x in s.transport.commands)
        s.service.tick()
        assert a.active is idle and idle.last_move==123
        assert notebook.read_bytes()==original
        a.update(deck);idle.update.assert_called_once()
    finally:a.active=None;close(s)


def test_shared_attention_pipeline_does_not_close_manager_or_open_cameras(tmp_path):
    from vision.object_recognition import ObjectRecognition
    s=setup_session(tmp_path)
    attention=AttentionManager(StimulusBus(),mobile_enabled=False,object_labels=s.labels)
    attention.close=Mock()
    pipeline=ObjectRecognition(s.frames,s.session.perception,s.session.evidence,StimulusBus(),attention=attention)
    try:
        pipeline.select_camera('pi');pipeline.close()
        attention.close.assert_not_called()
        assert s.frames.frame_owners['pi-primary'] is s.pi
    finally:s.session.close();s.transport.close();s.journal.close()


def test_repeated_sessions_with_lazy_factory_and_retained_development(tmp_path):
    a=AttentionManager(StimulusBus(),mobile_enabled=False,object_labels=Mock())
    clock=[0.];created=[]
    def factory(execution):
        p=Mock();p.step.return_value=None;created.append(p);return p
    service=Demonstration(a,factory,tmp_path,clock=lambda:clock[0])
    try:
        for i in range(2):
            row=service.submit(request(service));a.update(None);clock[0]+=15;service.tick()
            assert service.status()['session']['id']==row['id']
            assert service.status()['session']['state']=='failed'
            assert service.status()['session']['reason']=='no_fresh_observations'
        assert len(created)==2 and all(p.close.call_count==1 for p in created)
    finally:service.close()


def test_http_auth_origin_host_nonce_and_actual_attention_dispatch(tmp_path):
    from ui.dashboard import start_dashboard, DEFAULT_ORIGIN
    s=fixture(tmp_path);token='t'*40;server=start_dashboard(s.service,token,port=0)
    def call(method,path='/api/abilities',body=None,**headers):
        c=http.client.HTTPConnection(*server.address,timeout=3)
        try:
            c.request(method,path,json.dumps(body) if body else None,headers)
            r=c.getresponse();raw=r.read();return r.status,raw,r.getheaders()
        finally:c.close()
    try:
        assert call('GET')[0]==401
        auth={'Authorization':'Bearer '+token,'Origin':DEFAULT_ORIGIN}
        assert call('GET',**{**auth,'Origin':'https://evil.example'})[0]==403
        assert call('GET',**{**auth,'Host':'evil.example'})[0]==403
        code,raw,headers=call('GET',**auth);assert code==200
        st=json.loads(raw);assert ('Access-Control-Allow-Origin',DEFAULT_ORIGIN) in headers
        req=dict(id=str(uuid4()),ability=ABILITY,camera='pi-primary',duration=15,boot=st['boot'],nonce=st['nonce'],action='start')
        assert call('POST',body=req,**{**auth,'Content-Type':'application/json'})[0]==202
        assert not s.service.running
        s.session.attention.update(None);assert s.service.running
        assert call('POST',body=req,**{**auth,'Content-Type':'application/json'})[0]==400
        assert call('GET','/')[0]==200 and call('GET','/abilities.js')[0]==200
    finally:server.close();close(s)


def test_main_refuses_dashboard_before_hardware_when_invalid(monkeypatch):
    import main
    monkeypatch.delenv('CHARLIE_OPERATOR_TOKEN',raising=False)
    for args in (['--abilities-dashboard'],['--hardware','--abilities-dashboard'],
                 ['--hardware','--abilities-dashboard','--object-label-display','rp2040']):
        with pytest.raises(ValueError):main.main(args)


def test_competing_application_cannot_cancel_existing_session(tmp_path):
    s=fixture(tmp_path)
    try:
        start(s)
        with pytest.raises(RuntimeError,match='another application'):
            Demonstration(s.session.attention,Mock(),tmp_path)
        assert s.service.running
    finally:close(s)


@pytest.mark.parametrize('seconds,expected_sessions,expected_state',[(34,2,'completed'),(2,1,'cancelled')])
def test_normal_object_application_repeats_demo_with_same_inference_owner(tmp_path,monkeypatch,seconds,expected_sessions,expected_state):
    import time
    from main import parser
    from learning.object_runtime import run_objects
    from vision.mobile_models import FixtureModel
    import learning.demonstration as demo_module
    import ui.dashboard as dashboard
    now=[1.];services=[];models=[]
    original=demo_module.Demonstration
    def create_service(*args,**kwargs):
        service=original(*args,**kwargs,clock=lambda:now[0]);services.append(service);return service
    monkeypatch.setattr(demo_module,'Demonstration',create_service)
    monkeypatch.setattr('time.monotonic',lambda:now[0])
    monkeypatch.setattr('time.sleep',lambda seconds:None)
    monkeypatch.setattr('stimulus.keyboard.KeyboardStimulus',lambda *a,**kw:SimpleNamespace(close=lambda:None))
    monkeypatch.setattr('learning.resources.ResourceGuard',lambda *a:SimpleNamespace(check=lambda **kw:None))
    monkeypatch.setenv('CHARLIE_OPERATOR_TOKEN','fixture-test-token-not-real-secret-123456789')
    monkeypatch.setattr(dashboard,'start_dashboard',lambda *a,**kw:SimpleNamespace(address=('127.0.0.1',8768),close=lambda:None))
    def detector(**kwargs):
        model=FixtureModel([dict(label='chair',confidence=.95,box=[1,1,15,15])])
        model.metadata['classes']=['chair'];model.close=Mock();models.append(model);return model
    monkeypatch.setattr('vision.mobile_models.HailoObjects',detector)
    manifest=tmp_path/'models.json';manifest.write_text(json.dumps({'schema':'charlie.mobile.models.v1','objects':{}}))
    args=parser().parse_args(['--hardware','--object-recognition','--abilities-dashboard',
        '--object-label-display','dry-run','--object-model-manifest',str(manifest),'--object-seconds',str(seconds),
        '--learning-state',str(tmp_path/'state')])
    frames=StimulusBus();owner=object();frames.claim_frames('pi-primary',owner)
    requests=[];sequence=[0]
    def supervise():
        now[0]+=.2;sequence[0]+=1
        frames.publish_frame('pi-primary',owner,packet(now[0],sequence=sequence[0]))
        if services and len(requests)<2 and services[0].active is None:
            requests.append(services[0].submit(request(services[0]))['id'])
    run_objects(args,None,frames,supervise=supervise)
    import sqlite3
    with sqlite3.connect(tmp_path/'state/operator-demonstrations.sqlite3') as db:
        rows=[json.loads(x[0]) for x in db.execute('SELECT body FROM sessions')]
    assert len(models)==1 and len(rows)==expected_sessions
    assert all(r['state']==expected_state for r in rows)
    if expected_state=='completed':assert all(15<=r['elapsed_seconds']<15.3 for r in rows)
    else:assert all(r['elapsed_seconds']<2.3 for r in rows)
    assert all(r['display_acknowledgments']>0 for r in rows)
    assert frames.frame_owners=={'pi-primary':owner}
    assert list((tmp_path/'state/operator-demo-frames').glob('*.png'))


def test_cleanup_still_runs_if_evidence_storage_fails(tmp_path):
    s=fixture(tmp_path)
    try:
        start(s)
        s.service._save=Mock(side_effect=OSError('disk full'))
        s.service.finish('cancelled','operator_cancelled')
        assert s.session.sources.closed and s.service.pipeline is None
        assert s.service.status()['session']['state']=='failed'
        with pytest.raises(ValueError,match='persistence'):s.service.submit(request(s.service))
    finally:close(s)


def test_attention_update_cannot_refresh_label_after_deadline(tmp_path):
    s=fixture(tmp_path)
    try:
        start(s)
        for i,at in enumerate((1.,1.11,1.22)):feed(s,at,i)
        shown=sum(x.startswith('OBJECT_LABEL') for x in s.transport.commands)
        s.now[0]=16.
        s.session.attention.update(None)
        assert s.service.status()['session']['state']=='completed'
        assert sum(x.startswith('OBJECT_LABEL') for x in s.transport.commands)==shown
        assert s.transport.commands[-1]=='OBJECT_CLEAR'
    finally:close(s)
