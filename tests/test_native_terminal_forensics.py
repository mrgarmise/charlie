"""Original derived masks and labelled controllerless interface regressions."""
import base64,hashlib,json,zlib
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from PIL import Image
from experiments.ppal.robotron_screen_state import _game_over_evidence,CurrentScreenClassifier
from experiments.ppal.episode_end import EpisodeEndObserver
from experiments.ppal import marathon_robotron as marathon,play_robotron as play

FEATURES=json.loads((Path(__file__).parent/'fixtures/robotron-terminal-221727/features.json').read_text())['rows']

@pytest.mark.parametrize('row',FEATURES,ids=lambda row:str(row['sample']))
def test_native_gameover_words_temporal_holdouts_and_negatives(row):
    raw=zlib.decompress(base64.b64decode(row['zlib_base64']))
    assert hashlib.sha256(raw).hexdigest()==row['mask_sha256']
    result=_game_over_evidence(np.frombuffer(raw,dtype=np.uint8).reshape(row['shape']))
    assert result['matched']==(row['sample'] in (152,153,154))
    assert result['similarity']>.98 if result['matched'] else result['similarity']<.4


def native_observer():
    observer=EpisodeEndObserver(entry_evidence={'method':'acknowledged_START','capture_timestamp':15798.224,
        'transport':{'command':'START','ack_at':15798.224}})
    for at in (15799.858,15802.025,15818.812):
        observer.observe_phase(dict(state='gameplay',phase='gameplay',capture_timestamp=at))
    return observer


def test_three_fresh_native_gameover_frames_confirm_before_original_deadline_without_start():
    observer=native_observer()
    for row in FEATURES:
        if row['sample'] not in (152,153,154):continue
        raw=zlib.decompress(base64.b64decode(row['zlib_base64']))
        screen=dict(state='not_gameplay',phase='terminal',reason='recorded_game_over_message',
            terminal_reference=_game_over_evidence(np.frombuffer(raw,dtype=np.uint8).reshape(row['shape'])),capture_timestamp=row['at'])
        observer.observe_phase(screen)
    assert observer.confirmed and not observer.agency_allowed
    assert observer.last_capture==15840.790938 and observer.last_capture<15842.713142799
    evidence=observer.evidence(screen=screen,self_lost_frames=12)
    assert marathon._postgame_pages(evidence)
    assert not play._startable(screen)
    observer.observe_phase(dict(state='gameplay',phase='gameplay',capture_timestamp=15841.345452))
    assert observer.confirmed and not observer.agency_allowed


def test_duplicate_nonfinite_and_unsupported_frames_never_certify_terminal():
    observer=native_observer()
    screen=dict(state='not_gameplay',phase='terminal',reason='recorded_game_over_message',
        terminal_reference={'matched':True,'similarity':float('nan')},capture_timestamp=15840.)
    for _ in range(20):observer.observe_phase(screen)
    assert not observer.confirmed


def test_exact_observation_cache_is_mutation_safe_and_new_exposure_reclassified():
    key=[1];calls=[]
    classifier=CurrentScreenClassifier(lambda frame:calls.append(frame) or {'label_scores':{'heroes':.1}},lambda:key[0])
    first=classifier('frame');first['label_scores']['heroes']=1.
    assert classifier('same-frame')['label_scores']['heroes']==.1
    assert len(calls)==1
    key[0]=2;classifier('fresh');assert len(calls)==2


@pytest.mark.parametrize('count,status,cleanup,expected',[(0,'unverified_episode_boundary',False,False),
    (2,'bounded_attempts_complete',False,False),(3,'qualified_target_complete',False,True),
    (3,'interrupted',False,False),(3,'qualified_target_complete',True,False)])
def test_scheduled_learning_requires_qualified_three_game_block_and_camera_release(count,status,cleanup,expected):
    doc=dict(completion_counts={'completed':count},qualified_game_target=3,target_met=count>=3,status=status,camera_cleanup_error=cleanup)
    assert marathon.scheduled_learning(doc)['eligible'] is expected


def test_failed_block_never_calls_scheduled_reflection(tmp_path,monkeypatch):
    from test_marathon_deferred import args
    from test_experiment_return import gateway
    a=args(tmp_path);a.focus=None;played=[]
    monkeypatch.setattr(marathon,'reflect_marathon',lambda *a,**k:pytest.fail('incomplete scheduled meditation'))
    def driver(cmd,*args):
        game=Path(cmd[cmd.index('--output')+1]);game.mkdir();played.append(game)
        (game/'report.json').write_text(json.dumps({'result':'OBSERVATION UNCERTAIN','steps':[],
            'episode_end':{'confirmed':False}}));return 0
    doc=marathon.developmental_marathon(a,driver=driver,gateway=gateway(tmp_path))
    assert len(played)==1 and doc['scheduled_learning']['eligible'] is False


def test_prior_commencement_requires_one_new_fresh_frame_and_never_certifies_self(tmp_path,monkeypatch):
    clock=[1.];reads=[]
    class Source:
        timestamp=1.
        def read(self):clock[0]+=.1;self.timestamp=clock[0];reads.append(clock[0]);return Image.new('RGB',(640,480))
    monkeypatch.setattr(play.time,'monotonic',lambda:clock[0]);monkeypatch.setattr(play.time,'sleep',lambda s:None)
    prior=[dict(capture_timestamp=t,screen_state={'phase':'gameplay'}) for t in (.7,.8,.9)]
    out=play._wait_for_gameplay(Source(),SimpleNamespace(apply=lambda f:f),SimpleNamespace(detect=lambda f:[]),tmp_path,
        generic_ready=True,classifier=lambda f:{'phase':'gameplay'},verified_observations=prior)
    assert len(reads)==1 and out[0] is None and out[1]=='generic_visual_ready'
    assert out[3][0]['candidate_count'] is None


def test_center_prior_does_not_identify_stationary_object(monkeypatch):
    from experiments.ppal.robotron_agency import VisualAgency
    from experiments.ppal.eyes.detectors import Detection
    clock=[0.];monkeypatch.setattr('experiments.ppal.robotron_agency.time.monotonic',lambda:clock[0])
    def pairs():
        clock[0]+=.1
        return [(Detection('unknown',p,(1,1,10,20),100),{}) for p in ((20.,20.),(50.,50.))]
    visual=VisualAgency()
    result=visual.discover(pairs,SimpleNamespace(execute=lambda *args:None),center_spawn=True,observation_time=lambda:clock[0])
    assert result is None and visual.agency.self_id is None
    assert visual.last_discovery['spawn_prior']


def test_terminal_confirmation_inside_batch_wins_over_processing_deadline(tmp_path,monkeypatch):
    from test_marathon_camera_session import test_real_player_starts_two_simulated_playable_games_on_one_camera
    test_real_player_starts_two_simulated_playable_games_on_one_camera(tmp_path,monkeypatch,False,
        terminal_pages=True,terminal_delay=True)


def test_terminal_diagnostics_are_durable_and_bound_to_original_observation(tmp_path,monkeypatch):
    from test_marathon_camera_session import test_real_player_starts_two_simulated_playable_games_on_one_camera
    from memory.evidence import EvidenceJournal
    test_real_player_starts_two_simulated_playable_games_on_one_camera(tmp_path,monkeypatch,False,terminal_pages=True)
    for path in (tmp_path/'runs').glob('*/game-*/session-evidence.sqlite3'):
        journal=EvidenceJournal(path,read_only=True)
        records=[r for r in journal.records('observation') if r.data['payload'].get('category')=='terminal_observation']
        assert records
        for row in records:
            d=row.data;p=d['payload'];source=journal.get(p['camera_observation_id'])
            assert p['observation_id']==source.id and source.id in d['sources']
            assert p['capture_timestamp']==source.data['at']
        journal.close()


def test_legacy_successful_worker_return_cannot_schedule_incomplete_block(tmp_path,monkeypatch):
    import sys
    from experiments.ppal import progress_supervision
    session=tmp_path/'session';session.mkdir()
    (session/'session.json').write_text(json.dumps(dict(status='unverified_episode_boundary',
        completion_counts={'completed':0},qualified_game_target=3,target_met=False)))
    monkeypatch.setattr(progress_supervision,'supervise',lambda *a,**k:0)
    monkeypatch.setattr(marathon,'load_report',lambda path:dict(gameplay_finished=True,session=str(session))
        if 'watchdog' in str(path) else json.loads(Path(path).read_text()))
    monkeypatch.setattr(marathon,'reflect_marathon',lambda *a,**k:pytest.fail('incomplete parent meditation'))
    monkeypatch.setattr(sys,'argv',['marathon_robotron','--arm','--developmental','--learning-projects','--play-first','--root',str(tmp_path/'runs')])
    with pytest.raises(SystemExit) as stopped:marathon.main()
    assert stopped.value.code==2
