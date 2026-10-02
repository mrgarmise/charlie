import json
from pathlib import Path
import sys
import time

import pytest

from experiments.ppal.progress_supervision import Progress, stalled_reason, supervise
from experiments.ppal.episode_end import EpisodeEndObserver
from experiments.ppal.marathon_robotron import safe_to_restart


def test_healthy_game_age_never_terminates(tmp_path):
    clock = [1.]
    progress = Progress(tmp_path/'progress.json', clock=lambda:clock[0])
    for at in (2., 60., 3600., 100000.):
        clock[0] = at
        progress.enter('camera')
        progress.fresh(at)
        progress.perception()
        progress.cycle()
        progress.update(mode='playing', mode_started_at=2.)
        assert stalled_reason(progress.data, at+.1) is None
    progress.enter('camera')
    assert stalled_reason(progress.data, clock[0]+11.) == 'observation_failure'


def test_stale_exposures_and_fake_progress_do_not_hide_failure(tmp_path):
    clock = [1.]
    progress = Progress(tmp_path/'progress.json', clock=lambda:clock[0])
    progress.fresh(10.)
    clock[0] = 12.
    progress.fresh(10.)
    assert stalled_reason(progress.data, 12.) == 'observation_failure'
    progress.fresh(11.)
    progress.update(mode='playing', mode_started_at=1., cycle_at=1.)
    clock[0] = 35.
    progress.fresh(12.)
    assert stalled_reason(progress.data, 35.) == 'perception_cycle_stall'


def test_controller_and_process_stalls_are_distinct(tmp_path):
    p = Progress(tmp_path/'progress.json', clock=lambda:1.)
    p.enter('controller')
    assert stalled_reason(p.data, 12.) == 'controller_failure'
    assert stalled_reason(p.data, 32.) == 'controller_failure'
    p.enter('unclassified')
    assert stalled_reason(p.data, 32.) == 'subprocess_hang'


def child_command(path, body):
    return [sys.executable, '-c',
            'import time,signal\nfrom experiments.ppal.progress_supervision import Progress\n'
            f'p=Progress({str(path)!r})\n'+body]


def test_real_child_survives_multiple_watchdog_horizons(tmp_path):
    path = tmp_path/'progress.json'
    cmd = child_command(path, "for n in range(25):\n p.enter('camera');p.fresh(time.monotonic());p.cycle();time.sleep(.02)\n")
    assert supervise(cmd, path, silence=.15, camera=.15, poll=.01, grace=.2) == 0
    summary = json.loads(path.with_name('progress-supervisor.json').read_text())
    assert summary['reason'] == 'child_exited' and summary['last_progress']['cycles'] >= 20


@pytest.mark.parametrize('phase,expected', [('camera','observation_failure'), ('controller','controller_failure')])
def test_stalled_operation_is_interrupted_and_reaped(tmp_path, phase, expected):
    path = tmp_path/'progress.json'
    released = tmp_path/'neutral.txt'
    cmd = child_command(path, f"p.enter({phase!r})\ntry:time.sleep(20)\nfinally:open({str(released)!r},'w').write('neutral')\n")
    assert supervise(cmd, path, silence=2., camera=.15, controller=.15, poll=.01, grace=.2) == 124
    summary = json.loads(path.with_name('progress-supervisor.json').read_text())
    assert summary['reason'] == expected and summary['episode_boundary'] == 'unverified'
    assert released.read_text() == 'neutral'


def test_uncooperative_child_is_killed_and_partial_evidence_remains(tmp_path):
    path = tmp_path/'progress.json'
    evidence = tmp_path/'agency.jsonl'
    body = f"signal.signal(signal.SIGINT,signal.SIG_IGN)\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\nopen({str(evidence)!r},'w').write('{{}}\\n')\np.enter('controller')\ntime.sleep(20)\n"
    assert supervise(child_command(path,body),path,silence=2.,controller=.1,poll=.01,grace=.05) == 124
    assert evidence.read_text() == '{}\n'
    assert json.loads(path.with_name('progress-supervisor.json').read_text())['returncode'] < 0


def test_offline_work_budget_is_not_game_timeout(tmp_path):
    path = tmp_path/'processing.json'
    cmd = child_command(path,"p.enter('processing')\nwhile True:p.update(processing_units=1);time.sleep(.02)\n")
    assert supervise(cmd,path,budget=.3,silence=2.,poll=.01,grace=.2) == 124
    assert json.loads(path.with_name('processing-supervisor.json').read_text())['reason'] == 'processing_budget_exhausted'


def test_terminal_and_uncertain_boundary_never_conflate():
    observer = EpisodeEndObserver()
    for _ in range(10): observer.observe_screen('not_gameplay')
    # Matches physical run: visible instruction page but no eligible challenge.
    assert not observer.confirmed
    observer.observe_agency(False)
    end = dict(state='game_over',confirmed=observer.confirmed,
               evidence=observer.evidence(screen=dict(state='not_gameplay',phase='startable'),self_lost_frames=10))
    assert safe_to_restart(dict(result='GAME OVER',episode_end=end))
    assert not safe_to_restart(dict(result='OBSERVATION UNCERTAIN',episode_end=end))
    assert not safe_to_restart(dict(result='GAME OVER',episode_end=end),124)
    observer.observe_screen('unknown')
    assert not observer.confirmed


def test_recoverable_read_failure_and_exhaustion(tmp_path):
    from experiments.ppal.observation_camera import ObservedCamera
    from experiments.ppal.progress_supervision import ObservationFailure
    class Camera:
        calls = 0
        def read(self):
            self.calls += 1
            if self.calls < 3: raise OSError('temporary')
            return 'frame'
    camera = ObservedCamera(Camera())
    assert camera.read() == 'frame' and camera.read_failures == 2
    class Broken:
        def read(self): raise OSError('no frame')
    with pytest.raises(ObservationFailure): ObservedCamera(Broken()).read()


def test_partial_episode_import_preserves_bytes_and_unknown(tmp_path):
    from memory.evidence import EvidenceJournal
    from experiments.ppal.episode_evidence import import_episode
    from experiments.ppal.progress_evidence import DurableRows
    root = tmp_path/'partial';root.mkdir()
    steps = DurableRows(root/'steps.jsonl')
    steps.append(dict(action={'move':'STAY','fire':'NONE'},capture_timestamp=1.,identity_status='provisional'))
    (root/'agency.jsonl').write_text('{"sample":1,"capture_timestamp":1.0,"identity_status":"unknown"}\n{torn')
    journal = EvidenceJournal(tmp_path/'evidence.sqlite3')
    episode = import_episode(root,journal)
    assert episode.startswith('partial-episode:')
    record = journal.records('episode')[0].data['payload']
    assert record['outcome'] is None and record['completeness'].startswith('partial')
    assert len(journal.records('observation')) == 3
    assert sum(r.data['payload']['category']=='unreadable_artifact_line' for r in journal.records('observation')) == 1
    journal.close()


def test_phase_local_artifact_cache_keeps_hash_guards(tmp_path):
    import hashlib
    from memory.evidence import ArtifactReader
    path = tmp_path/'rows.jsonl';path.write_text('{"v":1}\n{"v":2}\n')
    ref = dict(path=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),line=1)
    read = ArtifactReader(tmp_path)
    assert read(ref) == {'v':1}
    assert read(dict(ref,line=2)) == {'v':2}
    path.write_text('{"v":3}\n{"v":2}\n')
    with pytest.raises(ValueError,match='changed'): read(ref)


def test_uncertainty_stops_without_calling_it_terminal():
    from experiments.ppal.progress_supervision import UncertaintyWindow
    window = UncertaintyWindow(60.)
    assert not window.observe(False, 100.)
    assert not window.observe(False, 159.)
    assert window.observe(False, 160.)
    assert not window.observe(True, 100000.)
    assert window.since is None
    # Ordinary reacquisition within the failure window is recoverable.
    assert not window.observe(False, 100001.)
    assert not window.observe(True, 100020.)


def test_isolated_processing_updates_existing_memory_and_project_store(tmp_path):
    from memory.evidence import EvidenceJournal
    from memory.gateway import MemoryGateway
    from memory.evaluator import MemoryEvaluator
    from memory.marm import MarmOutbox
    from memory.learning_projects import LearningExecutive
    from experiments.ppal.marathon_robotron import process_supervised
    source = Path(__file__).parent/'fixtures/robotron-body-fire-020552'
    game = tmp_path/'game';game.mkdir()
    (game/'report.json').write_bytes((source/'report.json').read_bytes())
    (game/'agency.jsonl').write_bytes((source/'agency-response-extract.jsonl').read_bytes())
    gateway = MemoryGateway(evaluator=MemoryEvaluator(tmp_path/'memory.sqlite3'),
                            store=MarmOutbox(tmp_path/'outbox.sqlite3'))
    commitments = EvidenceJournal(tmp_path/'commitments.sqlite3')
    projects = EvidenceJournal(tmp_path/'projects.sqlite3')
    executive = LearningExecutive(projects,gateway)
    result = process_supervised(game,tmp_path/'between',gateway,commitments,executive=executive,budget=20.)
    assert len(result['proposals']) == 9
    assert result['learning_projects']['proposed']
    # Parent observes worker's durable updates without a parallel memory store.
    assert executive.projects()
    assert gateway.evaluator.recent(100)
    assert result['processing_timing']['complete'] > result['processing_timing']['import']
    commitments.close();projects.close()


def test_partial_episode_runs_existing_between_game_path_without_report(tmp_path):
    from memory.evidence import EvidenceJournal
    from memory.gateway import MemoryGateway
    from memory.evaluator import MemoryEvaluator
    from memory.marm import MarmOutbox
    from experiments.ppal.marathon_robotron import process_supervised
    game=tmp_path/'game';game.mkdir()
    (game/'agency.jsonl').write_text('{"sample":1,"capture_timestamp":1,"identity_status":"unknown"}\n{torn')
    gateway=MemoryGateway(evaluator=MemoryEvaluator(tmp_path/'memory.sqlite3'),store=MarmOutbox(tmp_path/'outbox.sqlite3'))
    commitments=EvidenceJournal(tmp_path/'commitments.sqlite3')
    result=process_supervised(game,tmp_path/'between',gateway,commitments,budget=20.)
    assert result['episode'].startswith('partial-episode:')
    assert result['proposals']==[] and result['resolution'] is None
    assert json.loads((tmp_path/'between/shadow-evaluation.json').read_text())['boundary']=='unknown'
    commitments.close()
