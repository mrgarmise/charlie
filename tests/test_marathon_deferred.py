"""Controllerless simulated marathon; authentic proposal input is labeled separately."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from memory.evidence import EvidenceJournal
from memory.learning_projects import LearningExecutive
from experiments.ppal import marathon_robotron as m
from experiments.ppal.episode_evidence import import_episode
from test_experiment_return import gateway
from test_learning_projects import real_seed,synthetic_game
from test_recording_handoff import seal_software_recording


def args(tmp):
    return SimpleNamespace(root=tmp/'runs',seed_episode=None,max_games=3,game_seconds=None,
        focus=1.3,retry_wait=0,learning_projects=True,developmental=True,play_first=True,
        project_evidence=tmp/'projects.sqlite3',learning_root=tmp/'learning',
        reflection_turns=2,ala_budget=1.,processing_budget=20.)


def prepare(tmp,a,g):
    # Genuine October 1 BODY/FIRE extracts, not an invented winning strategy.
    source=real_seed(tmp/'authentic-seed')
    j=EvidenceJournal(a.project_evidence);c=EvidenceJournal(tmp/'seed-commitments.sqlite3')
    m.process_completed_episode(source,tmp/'seed-analysis',g,c,executive=LearningExecutive(j,g))
    j.close();c.close()


def test_three_games_before_any_offline_processing_and_executive_handoff(tmp_path,monkeypatch):
    a=args(tmp_path);g=gateway(tmp_path);prepare(tmp_path,a,g)
    played=[];processed=[]
    real_reflect=m.reflect_marathon
    def processor(game,*values,**options):
        from learning.cycle import gameplay_active
        assert not gameplay_active()
        assert len(played)==3 and options['defer_meditation'] is True
        processed.append(game)
        return m.process_completed_episode(game,*values,**options)
    monkeypatch.setattr(m,'reflect_marathon',lambda session,a,**kw:real_reflect(session,a,**kw,processor=processor))
    def no_direct_meditation(*args,**kw):raise AssertionError('meditation outside Executive')
    monkeypatch.setattr('experiments.ppal.meditate_robotron.meditate',no_direct_meditation)
    def driver(cmd,timeout):
        from learning.cycle import gameplay_active
        from learning.resources import ResourceGuard
        assert gameplay_active()  # Also covers the idle gap before a child exists.
        with pytest.raises(InterruptedError,match='primary gameplay'):
            ResourceGuard().check(force=True)
        assert '--diagnostic-seconds' not in cmd
        game=Path(cmd[cmd.index('--output')+1])
        plan=json.loads(Path(cmd[cmd.index('--experiment-plan')+1]).read_text())
        synthetic_game(game,plan);seal_software_recording(game)
        played.append(game)
        # No imported episode / resolution exists before all game children finish.
        c=EvidenceJournal(game.parent/'experiment-evidence.sqlite3',read_only=True)
        assert not c.records('resolution');c.close()
        assert not list(game.parent.glob('game-*-evidence'))
        return 0
    doc=m.developmental_marathon(a,driver=driver,gateway=g)
    assert doc['status']=='bounded_attempts_complete' and len(played)==len(processed)==3
    assert doc['reflection']['phase']=='checkpointed'
    assert all(x['between_game']['status']=='deferred' for x in doc['games'])
    session=played[0].parent;original=(session/'session.json').read_bytes()
    c=EvidenceJournal(session/'experiment-evidence.sqlite3',read_only=True)
    assert len(c.records('prediction'))==len(c.records('resolution'))==3
    ids=[r.id for r in c.records()];c.close()
    episodes=[]
    for game in played:
        j=EvidenceJournal(session/(game.name+'-evidence')/'evidence.sqlite3',read_only=True)
        episodes.append(j.records('episode')[0].data['episode']);j.close()
    assert len(set(episodes))==3
    assert (a.learning_root/'development-status.json').exists()
    assert json.loads((a.learning_root/'development-status.json').read_text())['physical_authorization'] is False
    # Completed import/resolve adapters are not run again; the Executive may continue.
    result=real_reflect(session,a,gateway=g,processor=lambda *v,**kw:pytest.fail('completed episode repeated'),development=lambda *v,**kw:None)
    assert result['phase']=='checkpointed' and (session/'session.json').read_bytes()==original
    c=EvidenceJournal(session/'experiment-evidence.sqlite3',read_only=True)
    assert [r.id for r in c.records()]==ids;c.close()


@pytest.mark.parametrize('result,rc',[('TIME LIMIT',0),('missing',1),('GAME OVER',124)])
def test_failed_start_uncertain_boundary_never_starts_second_game(tmp_path,monkeypatch,result,rc):
    a=args(tmp_path);g=gateway(tmp_path);played=[]
    monkeypatch.setattr(m,'reflect_marathon',lambda *v,**kw:dict(phase='checkpointed'))
    def driver(cmd,*v):
        game=Path(cmd[cmd.index('--output')+1]);game.mkdir();played.append(game)
        if result!='missing':(game/'report.json').write_text(json.dumps({'result':result,'steps':[],'episode_end':{'confirmed':False}}))
        return rc
    doc=m.developmental_marathon(a,driver=driver,gateway=g)
    assert len(played)==1 and doc['status'] in ('unverified_episode_boundary','child_timeout')


def test_interrupted_child_is_bookmarked_without_false_resolution(tmp_path,monkeypatch):
    a=args(tmp_path);g=gateway(tmp_path);prepare(tmp_path,a,g)
    monkeypatch.setattr(m,'reflect_marathon',lambda *v,**kw:pytest.fail('reflect on interrupt'))
    def driver(cmd,*v):
        Path(cmd[cmd.index('--output')+1]).mkdir()
        raise KeyboardInterrupt()
    doc=m.developmental_marathon(a,driver=driver,gateway=g)
    assert doc['status']=='interrupted' and len(doc['games'])==1
    assert doc['games'][0]['status']=='recording'
    session=Path(doc['games'][0]['path']).parent
    c=EvidenceJournal(session/'experiment-evidence.sqlite3',read_only=True)
    assert len(c.records('prediction'))==1 and not c.records('resolution');c.close()


def test_large_import_commits_cursor_resumes_without_reappending_prefix(tmp_path,monkeypatch):
    root=tmp_path/'source';root.mkdir()
    (root/'report.json').write_text(json.dumps({'result':'unknown','steps':[]}))
    (root/'agency.jsonl').write_text(''.join(json.dumps({'sample':i,'capture_timestamp':i+1.,
        'control_execution':{'move':'N','started_at':1.}})+'\n' for i in range(550)))
    path=tmp_path/'import.sqlite3';attempted=[]
    original=EvidenceJournal.append
    def counted(self,kind,payload,**kw):
        if payload.get('category')=='agency_tracking_observation':attempted.append(payload['artifact']['line'])
        return original(self,kind,payload,**kw)
    monkeypatch.setattr(EvidenceJournal,'append',counted)
    for end in (200,400,600):
        j=EvidenceJournal(path)
        def pulse():
            cursors=j.category_records('event','episode_import_checkpoint')
            if any(r.data['payload'].get('stage')=='agency.jsonl' and r.data['payload']['completed_units']>=end for r in cursors):
                raise m.ProcessingYield('fixture bounded interrupt after durable chunk')
        j.on_progress=pulse
        if end<600:
            with pytest.raises(m.ProcessingYield):import_episode(root,j)
            assert len(j.records('episode'))==1
        else:episode=import_episode(root,j)
        j.on_progress=None;j.verify();j.close()
    assert attempted==list(range(1,551))
    j=EvidenceJournal(path)
    assert len(j.records('episode'))==1
    assert len([r for r in j.records('observation') if r.data['payload'].get('category')=='action_transport_report'])==1
    ids=[r.id for r in j.records()];import_episode(root,j)
    assert [r.id for r in j.records()]==ids
    assert j.conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok';j.close()


def test_reflection_import_yields_then_resume_skips_completed_stage(tmp_path):
    a=args(tmp_path);g=gateway(tmp_path);session=tmp_path/'session';session.mkdir()
    games=[]
    for i in range(3):
        game=session/f'game-{i+1:02d}';game.mkdir()
        (game/'report.json').write_text(json.dumps({'result':'unknown','steps':[],'provenance':{'simulation':i}}))
        games.append({'path':str(game),'experiment':None})
    (session/'session.json').write_text(json.dumps({'games':games}))
    calls=[]
    def processor(game,output,*v,**kw):
        calls.append(game.name)
        if len(calls)==2:raise m.ProcessingYield('simulated partial import')
        return m.process_completed_episode(game,output,*v,**kw)
    assert m.reflect_marathon(session,a,gateway=g,processor=processor,development=lambda *v,**kw:pytest.fail('premature Executive'))['phase']=='yielded'
    assert calls==['game-01','game-02']
    result=m.reflect_marathon(session,a,gateway=g,processor=processor,development=lambda *v,**kw:None)
    assert result['phase']=='checkpointed' and calls==['game-01','game-02','game-02','game-03']
    assert all(x['boundary'].startswith('uncertain') for x in result['episodes'].values())
    with pytest.raises(ValueError,match='retain learning_root'):
        m.reflect_marathon(session,SimpleNamespace(learning_root=tmp_path/'replacement'),gateway=g)
    (session/'game-01-evidence'/'between-game.json').write_text('{}')
    with pytest.raises(ValueError,match='receipt changed'):
        m.reflect_marathon(session,a,gateway=g,development=lambda *v,**kw:None)


def test_failed_import_unit_rolls_back_cursor_and_data_together(tmp_path,monkeypatch):
    root=tmp_path/'source';root.mkdir()
    (root/'report.json').write_text('{"steps":[]}')
    (root/'agency.jsonl').write_text(''.join(json.dumps({'sample':i,'timestamp':i+1})+'\n' for i in range(250)))
    path=tmp_path/'import.sqlite3';j=EvidenceJournal(path)
    append=j.append
    def fail(kind,payload,**kw):
        if payload.get('category')=='agency_tracking_observation' and payload['artifact']['line']==150:
            raise InterruptedError('fixture failure inside second chunk')
        return append(kind,payload,**kw)
    monkeypatch.setattr(j,'append',fail)
    with pytest.raises(InterruptedError):import_episode(root,j)
    j.close()
    j=EvidenceJournal(path)
    assert len([r for r in j.records('observation') if r.data['payload'].get('category')=='agency_tracking_observation'])==100
    assert j.category_records('event','episode_import_checkpoint')[-1].data['payload']['completed_units']==100
    import_episode(root,j);j.verify()
    assert len([r for r in j.records('observation') if r.data['payload'].get('category')=='agency_tracking_observation'])==250
    j.close()


def test_gameplay_resource_claim_releases_on_interruption(tmp_path,monkeypatch):
    from learning import cycle
    monkeypatch.setattr(cycle,'_gameplay_lock',lambda:tmp_path/'primary.lock')
    with pytest.raises(InterruptedError):
        with cycle.gameplay_session():
            assert cycle.gameplay_active()
            raise InterruptedError('fixture stop')
    assert not cycle.gameplay_active()


def test_real_offline_cli_supervised_imports_and_normal_executive_without_arm(tmp_path,monkeypatch):
    import sys
    from memory.marm import MarmOutbox
    from memory.evaluator import MemoryEvaluator
    from memory.gateway import MemoryGateway
    session=tmp_path/'old-session';session.mkdir()
    entries=[]
    for index in range(3):
        game=session/f'game-{index+1:02d}';game.mkdir()
        (game/'report.json').write_text(json.dumps({'result':'TIME LIMIT','steps':[],
            'provenance':{'simulation':True,'game_index':index}}))
        entries.append({'path':str(game),'returncode':0,'experiment':None})
    (session/'session.json').write_text(json.dumps({'games':entries,'status':'processing_deferred'}))
    original=(session/'session.json').read_bytes()
    gateway=MemoryGateway(evaluator=MemoryEvaluator(tmp_path/'memory.sqlite3'),store=MarmOutbox(tmp_path/'outbox.sqlite3'))
    reflect=m.reflect_marathon
    monkeypatch.setattr(m,'reflect_marathon',lambda session,args:reflect(session,args,gateway=gateway))
    monkeypatch.setattr(m,'run_bounded',lambda *v,**kw:pytest.fail('controller/gameplay child forbidden'))
    monkeypatch.setattr(sys,'argv',['marathon_robotron','--reflect-session',str(session),
        '--learning-root',str(tmp_path/'normal-notebook'),'--project-evidence',str(tmp_path/'projects.sqlite3'),
        '--ala-budget','1','--reflection-turns','1','--processing-budget','20'])
    m.main()
    state=json.loads((session/'reflection-progress.json').read_text())
    assert state['phase']=='checkpointed' and len(state['episodes'])==3 and not state['physical_authorization']
    assert (session/'session.json').read_bytes()==original
    assert all((session/(Path(k).name+'-evidence')/'processing-config.json').exists() for k in state['episodes'])
    assert json.loads((tmp_path/'normal-notebook'/'development-status.json').read_text())['physical_authorization'] is False
    monkeypatch.setattr(sys,'argv',['marathon_robotron','--reflect-session',str(session),'--arm'])
    with pytest.raises(SystemExit) as exc:m.main()
    assert exc.value.code==2


def test_partial_reportless_experiment_retains_unresolved_outcome(tmp_path):
    from test_experiment_return import prepare as proposed
    g,j,c,plan=proposed(tmp_path)
    game=tmp_path/'next';game.mkdir()
    (game/'events.jsonl').write_text('{"at":1,"event":"interrupted"}\n')
    result=m.process_completed_episode(game,tmp_path/'partial',g,c,plan,defer_meditation=True)
    assert result['resolution']['result']=='unresolved' and result['resolution']['attempted'] is None
    ids=[r.id for r in c.records()]
    m.process_completed_episode(game,tmp_path/'partial',g,c,plan,defer_meditation=True)
    assert [r.id for r in c.records()]==ids
    j.close();c.close()


def test_import_checkpoint_refuses_wrong_source_binding(tmp_path):
    root=tmp_path/'source';root.mkdir()
    (root/'report.json').write_text('{"steps":[]}')
    (root/'agency.jsonl').write_text('{"sample":1}\n')
    j=EvidenceJournal(tmp_path/'import.sqlite3');episode=import_episode(root,j)
    # A separate partial import notebook with an internally valid but incorrect
    # declared cursor must not skip source units on the strength of its count.
    other=EvidenceJournal(tmp_path/'partial.sqlite3')
    for r in j.records():
        if r.data['payload'].get('category')=='episode_import_complete':continue
        other.append(r.data['kind'],r.data['payload'],episode=r.data['episode'],at=r.data['at'],
            sources=r.data['sources'],producer=r.data['producer'],version=r.data['version'],provenance=r.data['provenance'])
    start=other.records('episode')[0]
    other.append('event',dict(category='episode_import_checkpoint',stage='agency.jsonl',
        source_sha256='0'*64,completed_units=999,action_digests=[]),episode=episode,
        sources=[start.id],producer='fixture-invalid-cursor',version='1')
    with pytest.raises(ValueError,match='source changed'):import_episode(root,other)
    other.close();j.close()


def test_active_normal_executive_receives_handoff_without_second_owner(tmp_path):
    from learning.lifecycle import DevelopmentLifecycle
    a=args(tmp_path);g=gateway(tmp_path);session=tmp_path/'session';session.mkdir()
    game=session/'game-01';game.mkdir()
    (game/'report.json').write_text(json.dumps({'steps':[],'result':'unknown','provenance':{'simulation':True}}))
    (session/'session.json').write_text(json.dumps({'games':[{'path':str(game),'experiment':None}]}))
    # Normal app already owns the notebook. Its acquisition roots deliberately
    # do not include the session; the durable handoff supplies this location.
    live=DevelopmentLifecycle(a.learning_root,[],budget_seconds=1.)
    try:
        result=m.reflect_marathon(session,a,gateway=g,processor=m.process_completed_episode,
            development=lambda *v,**kw:pytest.fail('competing Executive started'))
        assert result['phase']=='executive_owned'
        live.turn()
        assert len(live.journal.category_records('event','marathon_history_acquired'))==1
        contexts=live.journal.category_records('observation','learning_context_reference')
        assert len(contexts)==1 and contexts[0].data['payload']['source_root']==str(game.resolve())
        live.turn()
        assert len(live.journal.category_records('event','marathon_history_acquired'))==1
    finally:live.close()


def test_resume_preserves_prior_processing_bytes_and_authentic_meditation(tmp_path):
    import hashlib
    game=tmp_path/'source';game.mkdir()
    (game/'report.json').write_text('{"steps":[],"result":"unknown"}')
    tracks=game/'tracks.json';tracks.write_text('{"tracks":[]}')
    output=tmp_path/'analysis';output.mkdir()
    saved={'source_sha256':hashlib.sha256(tracks.read_bytes()).hexdigest(),
        'version':'reconstruction-v1','history':[],'merges':[],'quality':{},'note':'fixture prior interpretation'}
    (output/'meditation.json').write_text(json.dumps(saved))
    (output/'between-game.json').write_text('{"prior_failure":"fixture interrupted"}')
    before={p.name:p.read_bytes() for p in output.glob('*.json')}
    c=EvidenceJournal(tmp_path/'commitments.sqlite3')
    result=m.process_completed_episode(game,output,gateway(tmp_path),c,defer_meditation=True)
    assert result['meditation']==str(output/'meditation.json')
    for name,data in before.items():
        retained=output/'processing-history'/(name+'-'+hashlib.sha256(data).hexdigest())
        assert retained.read_bytes()==data
    assert (output/'meditation.json').read_bytes()==before['meditation.json']
    c.close()
