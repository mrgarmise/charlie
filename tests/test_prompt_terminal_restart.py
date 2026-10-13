"""Native pixel fixtures + simulated sequence/controls; not native game acceptance."""
import hashlib,json
from pathlib import Path
from types import SimpleNamespace
import pytest
from PIL import Image
from experiments.ppal.episode_end import EpisodeEndObserver
from experiments.ppal.marathon_robotron import safe_to_restart,qualified_game_over
from experiments.ppal.play_robotron import _verified_restart,_restart_permission
from experiments.ppal.robotron_screen_state import classify_screen_state
from test_robotron_recorded_screen_states import view,ROWS


def page(phase,at):
    row=dict(phase=phase,state='gameplay' if phase=='gameplay' else 'not_gameplay',capture_timestamp=float(at))
    if phase=='terminal':row.update(reason='recorded_heroes_headings',label_scores={'heroes':.9,'all-time':.91})
    if phase=='title':row.update(title_reference={'matched':True,'sha256':'a'*64})
    return row


def established():
    end=EpisodeEndObserver()
    for at in (1,2,3):end.observe_phase(page('gameplay',at))
    end.entry_evidence=dict(method='acknowledged_START',capture_timestamp=.5,transport={'command':'START','ack_at':.5})
    return end


def report(end,screen):
    return dict(result='GAME OVER',episode_end=dict(state='game_over',confirmed=end.confirmed,
        evidence=end.evidence(screen=screen,self_lost_frames=3)))


def test_actual_observed_sequence_latches_before_demo_or_false_reacquisition():
    end=established();end.observe_agency(False)
    for at in (4,5):
        end.observe_phase(page('terminal',at));assert not end.confirmed
    end.observe_phase(page('title',6))
    assert end.confirmed and end.last_gameplay_at==3.
    proof=report(end,page('title',6))
    assert qualified_game_over(proof) and not safe_to_restart(proof)
    end.self_reacquired() # attempted false acquisition must never clear the boundary
    for at in (7,8,9):end.observe_phase(page('gameplay',at))
    assert end.confirmed and not end.agency_allowed and end.last_gameplay_at==3.
    permission=[page('title',at) for at in (10,11,12)]
    proof['episode_end']['evidence']['restart_permission']={'verified':True,'observations':permission}
    assert safe_to_restart(proof)


@pytest.mark.parametrize('phase',['terminal','title'])
def test_prompt_three_fresh_strong_pages_do_not_wait_eight_frames_or_deadline(phase):
    end=established()
    for at in (3.1,3.2,3.3):end.observe_phase(page(phase,at))
    assert end.confirmed and qualified_game_over(report(end,page(phase,3.3)))


def test_pregame_and_one_unsupported_or_duplicate_page_never_end_game():
    end=EpisodeEndObserver()
    for at in range(1,10):end.observe_phase(page('terminal',at))
    assert not end.confirmed
    end=established()
    end.observe_phase(page('terminal',4))
    for _ in range(30):end.observe_phase(page('terminal',4))
    assert not end.confirmed
    for at in (5,6,7):end.observe_phase(dict(page('terminal',at),label_scores={'heroes':.6,'all-time':.6}))
    assert not end.confirmed
    assert not qualified_game_over(report(end,page('terminal',7)))


def test_native_recorded_high_scores_and_complete_logo_are_recognized():
    assert classify_screen_state(view(ROWS[2]))['phase']=='terminal'
    source=Path('tests/fixtures/robotron-calibration-20261011/exposure-ev-3.png')
    declaration=json.loads(Path('config/robotron/screen-labels/title-anchor.json').read_text())
    assert hashlib.sha256(source.read_bytes()).hexdigest()==declaration['source_sha256']
    title=classify_screen_state(Image.open(source))
    assert title['phase']=='title' and title['title_reference']['matched']
    # This is the anchor source, not held-out evidence of native generalization.
    assert classify_screen_state(Image.new('RGB',(640,480)))['phase']=='unknown'


def source_for(monkeypatch,sequence):
    from experiments.ppal import play_robotron as play
    clock=[0.];index=[0]
    class Source:
        timestamp=0.
        def read(self):
            clock[0]+=.1;self.timestamp=clock[0]
            row=sequence[min(index[0],len(sequence)-1)];index[0]+=1
            return row
    monkeypatch.setattr(play.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(play.time,'sleep',lambda d:None)
    return Source(),SimpleNamespace(apply=lambda x:x)


def test_demo_never_attaches_or_sends_start_then_one_fresh_authorized_start(monkeypatch):
    sequence=[page('gameplay',0)]*4+[page('terminal',0)]*3+[page('title',0)]*3+[page('gameplay',0)]*3
    source,cal=source_for(monkeypatch,sequence);commands=[]
    decision=_verified_restart(source,cal,SimpleNamespace(_command=commands.append),classifier=lambda x:x,timeout=4.)
    assert decision['gameplay_verified'] and commands==['NEUTRAL','START']
    assert decision['observations'][8]['phase']=='title'


def test_unrecognized_demo_or_stale_permission_never_starts(monkeypatch):
    from experiments.ppal.progress_supervision import ObservationFailure
    source,cal=source_for(monkeypatch,[page('gameplay',0)])
    commands=[]
    with pytest.raises(RuntimeError):
        _verified_restart(source,cal,SimpleNamespace(_command=commands.append),classifier=lambda x:x,timeout=1.)
    assert commands==['NEUTRAL']
    end=established()
    for at in (4,5,6):end.observe_phase(page('terminal',at))
    r=report(end,page('terminal',6))
    r['episode_end']['evidence']['restart_permission']={'verified':True,'observations':[page('title',1)]*3}
    assert not safe_to_restart(r)


def test_start_acknowledgement_without_gameplay_is_not_success_or_retried(monkeypatch):
    from experiments.ppal.progress_supervision import ObservationFailure
    source,cal=source_for(monkeypatch,[page('startable',0)]);commands=[]
    with pytest.raises(RuntimeError):
        _verified_restart(source,cal,SimpleNamespace(_command=commands.append),classifier=lambda x:x,timeout=1.)
    assert commands==['NEUTRAL','START']


def test_gameplay_score_freezes_1100_and_keeps_1300_attract_separate(tmp_path):
    from experiments.ppal.score_observer import ScoreObserver
    from experiments.ppal.score_tracker import ScoreObservation,ScoreChannels
    from experiments.ppal.eyes.calibration import Calibration
    observer=ScoreObserver(Calibration(((0,.2),(1,.2),(1,1),(0,1))),tmp_path/'score.jsonl')
    def system(value):
        obs=ScoreObservation(1,value,value,0,.9,True,'changed')
        return ScoreChannels(obs,obs,1)
    observer.system.observe=lambda frame,t:system(1100)
    observer.system.report=lambda:dict(self_score=1100,p1_score=1100,p2_score=None,self_channel=1,status='measured')
    observer.non_gameplay_system.observe=lambda frame,t:system(1300)
    image=Image.new('RGB',(20,20))
    observer.late_change_frames=16 # force final gameplay-image retention beyond regular sampling
    observer.submit(image,timestamp=3.,sample=32,preceding_action=None,screen=page('gameplay',3.))
    observer.queue.join();observer.freeze(3.)
    observer.submit(image,timestamp=6.,sample=33,preceding_action=None,screen=page('terminal',6.))
    observer.queue.join()
    observer.submit(image,timestamp=9.,sample=34,preceding_action=None,screen=dict(page('gameplay',9.),episode_retired=True))
    observer.queue.join();observer.close()
    summary=observer.report()
    assert summary['self_score']==1100 and summary['final_observation']['timestamp']==3.
    rows=[json.loads(r) for r in (tmp_path/'score.jsonl').read_text().splitlines()]
    assert [r['score_partition'] for r in rows]==['gameplay','non_gameplay','non_gameplay']
    assert any(name=='score-raw-0032.png' for name,_ in observer.frames)
    assert rows[-1]['self_score']==1300 # preserved diagnostic, not a game-score correction


def test_two_real_player_episodes_reject_intervening_demo_with_shared_camera(tmp_path,monkeypatch):
    from test_marathon_camera_session import test_real_player_starts_two_simulated_playable_games_on_one_camera
    test_real_player_starts_two_simulated_playable_games_on_one_camera(tmp_path,monkeypatch,False,terminal_pages=True)


def test_demo_visual_transition_without_actual_entry_never_qualifies_completion():
    end=EpisodeEndObserver()
    for at in (1,2,3):end.observe_phase(page('gameplay',at))
    for at in (4,5,6):end.observe_phase(page('terminal',at))
    assert not end.confirmed and not qualified_game_over(report(end,page('terminal',6)))


def test_completed_evidence_is_durable_even_when_restart_permission_missing(tmp_path):
    from memory.evidence import EvidenceJournal
    from experiments.ppal.game_evidence import preserve_game
    from test_recording_handoff import seal_software_recording
    end=established()
    for at in (4,5,6):end.observe_phase(page('terminal',at))
    root=tmp_path/'game';root.mkdir()
    doc=dict(report(end,page('terminal',6)),armed=True,acquisition='simulated_causal_identity',
        steps=[{'action':{'move':'E'}}],simulation=True,score_summary={'self_score':None})
    (root/'report.json').write_text(json.dumps(doc));seal_software_recording(root)
    doc=json.loads((root/'report.json').read_text())
    j=EvidenceJournal(tmp_path/'completed.sqlite3')
    saved=preserve_game(j,root,marathon=tmp_path,returncode=0,report=doc)
    assert saved['classification']=='completed' and not safe_to_restart(doc,capture_root=root)
    j.close();j=EvidenceJournal(tmp_path/'completed.sqlite3')
    assert preserve_game(j,root,marathon=tmp_path,returncode=0,report=doc)['record_id']==saved['record_id']
    assert len(j.records('game_completion'))==1;j.close()
