"""Software controls only; no physical interfaces are opened."""
from pathlib import Path
import pytest
from memory.evidence import EvidenceJournal
from learning import campaign as c
from learning.foundry import atomic_json


def prepare(tmp,blocks=1):
    j=EvidenceJournal(tmp/'notebook'/'learning-evidence.sqlite3');j.close()
    c.create(tmp/'campaign',tmp/'notebook',blocks=blocks)
    return tmp/'campaign'


def test_disarmed_default_and_interrupted_launch_never_replay(tmp_path):
    root=prepare(tmp_path)
    state=c.run(root,supervisor=lambda *a,**k:pytest.fail('unarmed'))
    assert state['phase']=='blocked' and not state['attempts']
    state.update(phase='playing',attempts=[{'progress':'original'}]);atomic_json(root/'campaign.json',state)
    state=c.run(root,armed=True,supervisor=lambda *a,**k:pytest.fail('duplicate START'))
    assert state['phase']=='blocked' and 'no automatic retry' in state['reason']
    assert all(v=='NOT YET DEMONSTRATED' for v in state['gates'].values())


def test_revocation_interrupts_existing_parent_supervisor(tmp_path):
    root=prepare(tmp_path);c.arm(root)
    def supervisor(cmd,progress,**kw):
        kw['on_poll']();(root/'authority.json').unlink();kw['on_poll']()
        pytest.fail('revocation ignored')
    state=c.run(root,armed=True,supervisor=supervisor)
    assert state['phase']=='blocked' and len(state['attempts'])==1 and 'disarmed' in state['reason']
    assert c.run(root,armed=True,supervisor=lambda *a,**k:pytest.fail('retry'))['phase']=='blocked'


def test_real_three_game_marathon_and_reflection_handoff(tmp_path):
    from experiments.ppal import marathon_robotron as m
    from test_marathon_deferred import args
    from test_experiment_return import gateway
    from test_learning_projects import synthetic_game
    from test_recording_handoff import seal_software_recording
    root=prepare(tmp_path);c.arm(root);g=gateway(tmp_path);played=[]
    def supervisor(cmd,progress,**kw):
        kw['on_poll']();assert '--baseline-only' in cmd and '--game-seconds' not in cmd
        a=args(tmp_path);a.focus=None;a.baseline_only=True;a.qualified_games=3
        a.supervised_marathon=True;a.marathon_progress=progress;a.root=root/'runs'
        a.learning_root=tmp_path/'notebook';a.project_evidence=a.learning_root/'learning-project-evidence.sqlite3'
        def driver(command,timeout):
            assert '--experiment-plan' not in command
            game=Path(command[command.index('--output')+1]);played.append(game)
            synthetic_game(game,{'prediction_id':'test-only','body':'NE','fire':'SE','expected':'signed_command_response'})
            seal_software_recording(game);return 0
        doc=m.developmental_marathon(a,driver=driver,gateway=g)
        assert doc['target_met'] and len(played)==3
        return 0
    def reflect(session,a):
        assert len(played)==3
        return m.reflect_marathon(session,a,gateway=g,processor=m.process_completed_episode,development=lambda *a,**kw:None)
    state=c.run(root,armed=True,supervisor=supervisor,reflector=reflect)
    assert state['phase']=='completed',state.get('reason')
    assert state['attempts'][0]['reflection']['phase']=='checkpointed'
    assert c.run(root,armed=True,supervisor=lambda *a,**kw:pytest.fail('repeat'))==state
    with pytest.raises(ValueError,match='native source'):
        c.qualify_session(state['attempts'][0]['session'])


def test_reflection_resumes_offline_before_any_more_games(tmp_path):
    root=prepare(tmp_path);state=c.read(root/'campaign.json')
    state.update(phase='reflecting',attempts=[{'session':str(tmp_path/'session')}]);atomic_json(root/'campaign.json',state)
    never=lambda *a,**k:pytest.fail('launch')
    assert c.run(root,reflector=lambda *a:dict(phase='yielded'),supervisor=never)['phase']=='reflecting'
    assert c.run(root,reflector=lambda *a:dict(phase='checkpointed'),supervisor=never)['phase']=='completed'


def test_expansion_requires_reviewed_native_evidence(tmp_path):
    root=prepare(tmp_path,2)
    with pytest.raises(ValueError,match='reviewed native'):c.arm(root)
    assert not (root/'authority.json').exists()


def test_expiration_and_source_freeze(tmp_path,monkeypatch):
    root=prepare(tmp_path);grant=c.arm(root)
    monkeypatch.setattr(c.time,'time',lambda:grant['expires_at']+1)
    with pytest.raises(InterruptedError,match='expired'):c.check_authority(root,c.read(root/'campaign.json'),grant)
    monkeypatch.setattr(c,'source_identity',lambda:dict(revision='different'))
    with pytest.raises(ValueError,match='source changed'):c.arm(root)


def test_baseline_then_existing_chooser_and_bounded_proposal_command(tmp_path):
    root=prepare(tmp_path);state=c.read(root/'campaign.json');state['attempts']=[{}]
    assert '--baseline-only' in c.command(root,state,root/'progress')
    state['attempts'].append({});state['games']=6
    assert '--baseline-only' not in c.command(root,state,root/'progress')
    state.update(proposal_id='original-charlie-proposal',attempts=[{}],games=1)
    cmd=c.command(root,state,root/'progress')
    assert cmd[cmd.index('--max-games')+1]=='1' and '--observation-block' in cmd and '--baseline-only' in cmd


def test_one_game_contract_cannot_expand_into_three_attempts(monkeypatch):
    from experiments.ppal import marathon_robotron as m
    argv=['marathon','--arm','--supervised-marathon','--developmental','--learning-projects','--play-first',
        '--baseline-only','--single-observation','--max-games','1','--qualified-games','1']
    monkeypatch.setattr('sys.argv',argv);seen=[]
    monkeypatch.setattr(m,'developmental_marathon',lambda a:seen.append(a.max_games) or {})
    m.main();assert seen==[1]
    argv.remove('--baseline-only')
    with pytest.raises(SystemExit):m.main()


def test_offline_policy_grant_cannot_be_upgraded(tmp_path,monkeypatch):
    root=prepare(tmp_path);state=c.read(root/'campaign.json');state['policy']=str(tmp_path/'offline.json')
    atomic_json(root/'campaign.json',state);calls=[]
    def reject(path,physical=False):
        calls.append(physical);raise ValueError('offline policy lacks physical authority')
    monkeypatch.setattr('experiments.ppal.qualified_policy.load_policy',reject)
    with pytest.raises(ValueError,match='lacks physical'):c.arm(root)
    assert calls==[True] and not (root/'authority.json').exists()


def test_ten_game_campaign_keeps_exact_final_one_game_bound(tmp_path):
    j=EvidenceJournal(tmp_path/'notebook'/'learning-evidence.sqlite3');j.close()
    state=c.create(tmp_path/'campaign',tmp_path/'notebook',games=10)
    assert state['blocks']==4
    state['attempts']=[{}]*4
    cmd=c.command(tmp_path/'campaign',state,tmp_path/'progress')
    assert cmd[cmd.index('--max-games')+1]=='1' and '--baseline-only' in cmd
    assert '--observation-block' in cmd


def test_staged_experiment_delivery_retains_original_question_idempotently(tmp_path):
    from test_exploratory_proposals import prepare as project
    life,identifier=project(tmp_path);p=life.executive.stage_evidence_experiment();life.close()
    root=tmp_path/'campaign'
    state=c.create(root,tmp_path/'state',proposal_id=p.data['payload']['proposal_id'])
    session=tmp_path/'session';session.mkdir()
    atomic_json(session/'session.json',dict(games=[dict(durable_game_evidence={'record_id':'fixture-completion'})]))
    entry=dict(session=str(session))
    first=c.deliver_observation(state,entry)
    assert c.deliver_observation(state,entry)==first
    j=EvidenceJournal(tmp_path/'state'/'learning-evidence.sqlite3',read_only=True)
    row=j.get(first)
    assert row.data['sources']==[p.id] and row.data['payload']['project_id']==identifier
    assert not row.data['payload']['hypothesis_resolved'] and not row.data['payload']['candidate_activated']
    assert row.data['payload']['source_question']==p.data['payload']['original_question']
    j.close()


def test_original_notebook_owner_blocks_gameplay_launch(tmp_path):
    import fcntl
    root=prepare(tmp_path);c.arm(root)
    with (tmp_path/'notebook'/'offline.lock').open('a') as owner:
        fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
        result=c.run(root,armed=True,supervisor=lambda *a,**kw:pytest.fail('second writer'))
    assert result['phase']=='blocked'


def test_existing_executive_history_reaches_next_marathon_projection_unchanged(tmp_path):
    root=prepare(tmp_path);notebook=tmp_path/'notebook'
    j=EvidenceJournal(notebook/'learning-evidence.sqlite3')
    row=j.append('observation',{'category':'retained-investigation','result':'unresolved'},
        episode='authenticity-not-claimed',producer='test-fixture',version='1');j.close()
    from learning.datasets import sha
    frozen=sha(notebook/'learning-evidence.sqlite3')
    transfer=c.synchronize_projects(notebook)
    assert transfer['added_records']==1 and not transfer['independent_new_experience']
    j=EvidenceJournal(notebook/'learning-project-evidence.sqlite3',read_only=True)
    assert j.get(row.id).document==row.document;j.close()
    assert c.synchronize_projects(notebook)['added_records']==0
    assert sha(notebook/'learning-evidence.sqlite3')==frozen


def test_native_reliability_from_another_revision_cannot_expand_campaign(tmp_path,monkeypatch):
    root=prepare(tmp_path,2)
    monkeypatch.setattr(c,'qualify_session',lambda p:dict(source_revision='old-unqualified-source'))
    with pytest.raises(ValueError,match='frozen campaign revision'):
        c.arm(root,reliability_session=tmp_path/'old-native',observed_native=True)
    assert not (root/'authority.json').exists()
