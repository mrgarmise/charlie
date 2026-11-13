"""Offline campaign contract tests. Injected workers never open devices."""
import json
from pathlib import Path
import pytest
from learning import campaign as c
from learning.foundry import atomic_json
from memory.evidence import EvidenceJournal


def prepare(tmp_path):
    notebook=tmp_path/'notebook'
    j=EvidenceJournal(notebook/'learning-evidence.sqlite3');j.close()
    root=tmp_path/'campaign';c.create(root,notebook,marathon=True,conditions={k:{"context":"software fixture"} for k in ("camera","game","system","measurement")})
    return root


def worker(root, completed=3):
    def run(cmd, progress, **kwargs):
        kwargs['on_poll']()
        assert '--frozen-policy' in cmd and '--baseline-only' in cmd
        assert '--observation-block' not in cmd and '--game-seconds' not in cmd
        assert cmd[cmd.index('--max-games')+1]=='3'
        state=c.read(root/'campaign.json');index=len(state['attempts'])
        session=root/f'session-{index}';session.mkdir()
        atomic_json(session/'session.json',dict(target_met=completed==3,games=[{}]*completed,
            completion_counts={'completed':completed}))
        atomic_json(progress,dict(gameplay_finished=True,session=str(session)))
        return 0
    return run


def qualification(session):
    return dict(session=str(session),source_revision=c.source_identity()['revision'],
        captures=[str(session)+f'/game-{i}' for i in range(3)],policies=[dict(kind='baseline',knowledge_sha256='frozen')]*3)


def test_original_six_game_order_offline_checkpoint_and_separate_review(tmp_path,monkeypatch):
    root=prepare(tmp_path);state=c.read(root/'campaign.json')
    assert state['games']==6 and state['blocks']==2
    grant=c.arm(root);assert grant['authorized_blocks']==1
    reflections=[]
    def reflect(session,args):
        assert len(c.read(root/'campaign.json')['attempts'])==1
        reflections.append(session);return dict(phase='checkpointed')
    state=c.run(root,armed=True,supervisor=worker(root),reflector=reflect,qualifier=qualification)
    assert state['phase']=='awaiting_second_block' and len(reflections)==1
    assert state['attempts'][0]['after_meditation']['learning_demonstrated'] is False
    # Re-running cannot spend a first-block grant on three more games.
    assert c.run(root,armed=True,supervisor=lambda *a,**kw:pytest.fail('unreviewed second block'))==state
    with pytest.raises(ValueError,match='reviewed native'):
        c.arm(root)
    monkeypatch.setattr(c,'qualify_session',lambda p:dict(qualification(p),source_revision=c.source_identity()['revision']))
    c.arm(root,reliability_session=state['attempts'][0]['session'],observed_native=True)
    state=c.run(root,armed=True,supervisor=worker(root),reflector=lambda *a:pytest.fail('extra meditation'),qualifier=qualification)
    assert state['phase']=='awaiting_comparison' and len(state['attempts'])==2
    assert state['adaptation']['activated'] is False
    assert all(v=='NOT YET DEMONSTRATED' for v in state['gates'].values())


def test_partial_block_never_meditates_or_counts_as_three(tmp_path):
    root=prepare(tmp_path);c.arm(root)
    state=c.run(root,armed=True,supervisor=worker(root,2),
        reflector=lambda *a:pytest.fail('premature meditation'),qualifier=qualification)
    assert state['phase']=='blocked' and len(state['attempts'])==1
    assert (root/'session-1/session.json').exists()
    with pytest.raises(ValueError):c.reconcile(root)


def test_completed_interrupted_handoff_resumes_without_start(tmp_path,monkeypatch):
    root=prepare(tmp_path);state=c.read(root/'campaign.json')
    progress=root/'block-progress.json';session=root/'retained-session';session.mkdir()
    atomic_json(progress,dict(gameplay_finished=True,session=str(session)))
    state.update(phase='playing',attempts=[dict(progress=str(progress))]);atomic_json(root/'campaign.json',state)
    monkeypatch.setattr(c,'qualify_session',qualification)
    recovered=c.reconcile(root)
    assert recovered['phase']=='reflecting'
    state=c.run(root,reflector=lambda *a:dict(phase='checkpointed'),supervisor=lambda *a,**kw:pytest.fail('duplicate START'))
    assert state['phase']=='awaiting_second_block'


def test_mode_and_second_policy_bound_to_authority(tmp_path):
    root=prepare(tmp_path);grant=c.arm(root);state=c.read(root/'campaign.json')
    state['second_policy']='unreviewed'
    with pytest.raises(InterruptedError):c.check_authority(root,state,grant)


def test_existing_marathon_and_reflection_execute_both_blocks(tmp_path,monkeypatch):
    """Real orchestration/import adapters, synthetic captures, no physical qualification."""
    from experiments.ppal import marathon_robotron as m
    from test_marathon_deferred import args
    from test_experiment_return import gateway
    from test_learning_projects import synthetic_game
    from test_recording_handoff import seal_software_recording
    root=prepare(tmp_path);g=gateway(tmp_path);played=[];reflected=[]
    stamps=iter(('block-one','block-two'));monkeypatch.setattr(m,'stamp',lambda:next(stamps))
    def supervisor(cmd,progress,**kw):
        kw['on_poll']()
        a=args(tmp_path);a.focus=None;a.baseline_only=True;a.qualified_games=3;a.frozen_policy=True
        a.supervised_marathon=True;a.marathon_progress=progress;a.root=root/'runs'
        a.learning_root=tmp_path/'notebook';a.project_evidence=a.learning_root/'learning-project-evidence.sqlite3'
        def driver(command,timeout):
            assert '--frozen-policy' in command and '--experiment-plan' not in command
            if len(played)%3==0:assert '--require-new-game' in command
            game=Path(command[command.index('--output')+1]);played.append(game)
            synthetic_game(game,{'prediction_id':'controlled-fixture','body':'NE','fire':'SE','expected':'signed_command_response'})
            seal_software_recording(game);return 0
        doc=m.developmental_marathon(a,driver=driver,gateway=g)
        assert doc['target_met'] and doc['completion_counts']['completed']==3
        return 0
    def reflector(session,a):
        assert len(played)==3
        reflected.append(session)
        return m.reflect_marathon(session,a,gateway=g,processor=m.process_completed_episode,
            development=lambda *a,**kw:None)
    c.arm(root)
    state=c.run(root,armed=True,supervisor=supervisor,reflector=reflector,qualifier=qualification)
    assert state['phase']=='awaiting_second_block' and len(reflected)==1
    # Actual production qualifier continues to reject these simulation recordings.
    with pytest.raises(ValueError):c.qualify_session(state['attempts'][0]['session'])
    monkeypatch.setattr(c,'qualify_session',qualification)
    c.arm(root,reliability_session=state['attempts'][0]['session'],observed_native=True)
    state=c.run(root,armed=True,supervisor=supervisor,reflector=reflector,qualifier=qualification)
    assert state['phase']=='awaiting_comparison' and len(played)==6 and len(reflected)==1
    assert all((p/'capture-manifest.json').exists() for p in played)
