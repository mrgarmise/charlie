"""Exercise the real armed runner with a deterministic camera/controller world."""
import json
import sys
from PIL import Image
import pytest
from experiments.ppal.eyes.detectors import Detection
from experiments.ppal.robotron_agency import VECTORS


@pytest.mark.parametrize('fail_during_play,respawn,delayed_render,bootstrap',
                         [(False,False,False,False),(True,False,False,False),
                          (False,True,False,False),(False,False,True,False),(False,False,True,True)])
def test_armed_runner_uses_generic_agency_and_always_releases(monkeypatch,tmp_path,fail_during_play,respawn,delayed_render,bootstrap):
    from experiments.ppal import play_robotron as play
    clock=[0.]; points=[(20.,20.),(50.,50.)]; commands=[]; closed=[]; reads=[0]
    image=Image.new('RGB',(100,100))
    pending = [None]; response_reads = [0]
    class Source:
        def read(self):
            clock[0]+=.01; reads[0]+=1
            if pending[0] is not None:
                response_reads[0] += 1
                if response_reads[0] == 2:
                    u = pending[0]; p = points[0]
                    points[0] = (p[0]+u[0],p[1]+u[1])
                    pending[0] = None
            if respawn and reads[0] == 22: points[0]=(80.,80.)
            if fail_during_play and reads[0]>25: raise RuntimeError('camera disconnected')
            return image
        def close(self): closed.append('camera')
    class Recognizer:
        def detect(self,frame):
            # Only the wrong stationary center object looks like PLAYER.
            return [(Detection('unknown' if i==0 else 'player',p,(1,1,10,20),100),
                     {'class_scores':{'player':.01 if i==0 else .99}}) for i,p in enumerate(points)]
    class Controller:
        def __init__(self,*a,**k): pass
        def _command(self,command): commands.append(command)
        def execute(self,action,ms):
            commands.append(action)
            u=VECTORS[action.move]
            if delayed_render and action.move != "STAY":
                pending[0] = u; response_reads[0] = 0
            else:
                p=points[0]; points[0]=(p[0]+u[0],p[1]+u[1])
            clock[0]+=ms/1000
        def close(self): closed.append('controller')
    monkeypatch.setattr(play,'PiCameraSource',Source)
    monkeypatch.setattr(play.TaughtRecognizer,'load',lambda *a:Recognizer())
    monkeypatch.setattr(play.Calibration,'load',lambda *a:type('Calibration',(),{'apply':lambda self,f:f})())
    monkeypatch.setattr(play,'ArcadeController',Controller)
    monkeypatch.setattr(play.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(play.time,'sleep',lambda duration:None)
    monkeypatch.setattr(sys,'argv',['play','--arm','--seconds','1','--output',str(tmp_path/'run')]
                        + (['--bootstrap-body-fire'] if bootstrap else []))
    if fail_during_play:
        with pytest.raises(RuntimeError,match='camera disconnected'): play.main()
    else:
        play.main()
    report=json.loads((tmp_path/'run/report.json').read_text())
    assert report['acquisition']==('provisional_body_agency' if bootstrap else 'generic_visual_agency')
    actions=[r for r in report['steps'] if 'action' in r]
    assert actions
    if respawn:
        assert any(r.get('status')=='player_reacquired' for r in report['steps'])
        assert any(r['player'][0]>60 for r in actions)
    else:
        assert all(r['player'][0]<40 for r in actions)
    assert all(r['agency']['controlled_track_id'] is not None for r in actions)
    assert closed==['controller','camera']
    assert (tmp_path/'run/agency.jsonl').exists()
    telemetry=list(map(json.loads,(tmp_path/'run/agency.jsonl').read_text().splitlines()))
    assert telemetry[0]['command'] is None  # pre-command anchor is now recorded
    assert all(row['tracking']['clock']=='seconds' for row in telemetry)
    assert all(row['tracking']['detections'] for row in telemetry)
    assert (tmp_path/'run/tracks.json').exists()
    original=Image.open(tmp_path/'run'/report['raw_frames'][0]['path'])
    assert original.getextrema()==((0,0),(0,0),(0,0))
    assert all(r['self_track_id']==r['agency']['controlled_track_id'] for r in actions)
    if bootstrap:
        assert report['bootstrap_body_fire']
        assert any(getattr(c,'fire','NONE') != 'NONE' for c in commands)
        assert any(r['agency']['identity_status']=='provisional' for r in actions)
    assert report['result'].startswith('ERROR:') if fail_during_play else report['result']=='TIME LIMIT'
