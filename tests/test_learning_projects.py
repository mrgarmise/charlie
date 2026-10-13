"""Controlled architecture tests. Synthetic outcomes are not autonomous learning."""
import json
from pathlib import Path
import time
from types import SimpleNamespace

import pytest

from memory.evidence import EvidenceJournal
from memory.evaluator import MemoryEvaluator
from memory.former import Experience
from memory.gateway import MemoryGateway
from memory.learning_projects import LearningExecutive, CompletionCriteria, reflect_project_opportunities
from memory.store import JsonlStore
from experiments.ppal.experiment_return import select_experiment
from experiments.ppal.marathon_robotron import process_completed_episode, developmental_marathon


def gateway(root):
    return MemoryGateway(evaluator=MemoryEvaluator(root/'memory.sqlite3', exploration_rate=0),
                         store=JsonlStore(root/'selected.jsonl'))


def hypothesis(journal, *, method='opaque-test-method', scope=None, expected='measured-repeat',
               requires=(), conditions=None):
    scope = scope or {'instrument': 'previously-unspecified-transducer'}
    conditions = conditions or [{'setting': 'a'}, {'setting': 'b'}]
    record = journal.append('event', {'category': 'controlled_hypothesis', 'measured': expected},
        episode='controlled-source', producer='Reflection', version='controlled-test-v1')
    h = dict(method=method, scope=scope, expected=expected, requires=list(requires),
             conditions=conditions, observed_conditions=[conditions[0]], evidence_ids=[record.id])
    return reflect_project_opportunities(journal, 'controlled-source', [h])[0]


def result(executive, identifier, journal, *, condition, episode, verdict='supported'):
    project = executive.projects()[identifier]
    at = time.monotonic()
    scope = f'controlled-trial:{episode}:{len(journal.records())}'
    source = journal.append('observation', {'category': 'controlled_trial_origin'}, episode=scope,
                            at=at, producer='controlled-test', version='1')
    at = time.monotonic()
    prediction = journal.predict(project['expected'], episode=scope, at=at, deadline=at+60,
        sources=[source.id], producer='controlled-adapter', version='1', mode='live_prospective')
    outcome = journal.append('observation', {'category': 'experiment_outcome', 'ee_episode': episode},
        episode=scope, at=time.monotonic()+.001, producer='controlled-adapter', version='1')
    resolution = journal.resolve(prediction.id, sources=[outcome.id] if verdict!='unresolved' else [],
                                 result=verdict, reason='explicit synthetic outcome')
    plan = dict(project_id=identifier, prediction_id=prediction.id, memory_id='controlled-memory',
                condition=condition, expected=project['expected'])
    return executive.record_result(identifier, plan, dict(result=verdict, reason='synthetic outcome',
        resolution_id=resolution.id), journal, episode=episode)


def select(executive, *, resources=(), urgent=(), methods=('opaque-test-method',)):
    return executive.select(methods=set(methods), resources=set(resources),
                            authorized_methods=set(methods), urgent_projects=urgent)


def test_cumulative_completion_persists_and_conclusion_uses_existing_memory(tmp_path):
    g = gateway(tmp_path); source = EvidenceJournal(tmp_path/'source.sqlite3')
    notebook = EvidenceJournal(tmp_path/'projects.sqlite3'); e = LearningExecutive(notebook, g)
    p = hypothesis(source); identifier = e.propose(p['proposal'], source, [p['evidence_id']])
    assert select(e)['project']['id'] == identifier
    first = result(e, identifier, source, condition={'instrument':'previously-unspecified-transducer','setting':'a'}, episode='one')
    assert first['status'] == 'active' and first['progress']['resolved'] == 1
    notebook.close()
    notebook = EvidenceJournal(tmp_path/'projects.sqlite3'); e = LearningExecutive(notebook, gateway(tmp_path))
    assert e.projects()[identifier]['experiment_history'] == first['experiment_history']
    second = result(e, identifier, source, condition={'instrument':'previously-unspecified-transducer','setting':'b'}, episode='two')
    assert second['status'] == 'active'
    completed = result(e, identifier, source, condition={'instrument':'previously-unspecified-transducer','setting':'a'}, episode='three')
    assert completed['status'] == 'completed' and completed['disposition'] == 'achieved'
    assert completed['open_questions'] == first['open_questions']
    assert any(r['source']=='learning-project:assessment' for r in e.gateway.evaluator.recent(100))
    assert select(e)['project'] is None
    assert notebook.verify() is None
    notebook.close(); source.close()


def test_interruption_restart_completion_and_resumption_preserve_original_history(tmp_path):
    source = EvidenceJournal(tmp_path/'source.sqlite3'); notebook = EvidenceJournal(tmp_path/'projects.sqlite3')
    e = LearningExecutive(notebook, gateway(tmp_path))
    p = hypothesis(source, requires=('usable-perception',))
    original = e.propose(p['proposal'], source, [p['evidence_id']]); select(e, resources=('usable-perception',))
    before = result(e, original, source, condition=dict(p['proposal']['scope'], setting='a'), episode='one')
    repair = hypothesis(source, scope={'instrument':'unexpected-perception-fault'}, requires=('diagnostic-resource',))
    repair_id = e.propose(repair['proposal'], source, [repair['evidence_id']])
    # Recorded opportunity can preempt, but missing method/resource remains binding.
    chosen = select(e, resources=('diagnostic-resource',), urgent=(repair_id,))
    assert chosen['project']['id'] == repair_id
    assert e.projects()[original]['status'] == 'blocked'
    assert e.projects()[original]['interrupted_by'] == repair_id
    notebook.close(); notebook = EvidenceJournal(tmp_path/'projects.sqlite3'); e = LearningExecutive(notebook, gateway(tmp_path))
    for n, setting in enumerate(('a','b','a')):
        result(e, repair_id, source, condition=dict(repair['proposal']['scope'],setting=setting), episode=f'repair-{n}')
    resumed = select(e, resources=('usable-perception','diagnostic-resource'))
    assert resumed['reason'] == 'resume interrupted project'
    assert resumed['project']['id'] == original
    assert resumed['project']['experiment_history'] == before['experiment_history']
    assert resumed['project']['hypothesis_evidence'] == before['hypothesis_evidence']
    notebook.close(); source.close()


def test_sticky_project_dependencies_and_execution_authority_are_separate(tmp_path):
    source=EvidenceJournal(tmp_path/'s.sqlite3'); notebook=EvidenceJournal(tmp_path/'p.sqlite3')
    e=LearningExecutive(notebook,gateway(tmp_path))
    p=hypothesis(source); a=e.propose(p['proposal'],source,[p['evidence_id']]); select(e)
    other=hypothesis(source,scope={'instrument':'other'},conditions=[{'setting':str(i)} for i in range(10)])
    b=e.propose(other['proposal'],source,[other['evidence_id']])
    assert select(e)['project']['id']==a  # immediate attractive alternative does not steal goal
    code=hypothesis(source,method='code-modification',scope={'instrument':'code'})
    c=e.propose(code['proposal'],source,[code['evidence_id']])
    choice=e.select(methods={'opaque-test-method','code-modification'},resources=set(),
                    authorized_methods={'opaque-test-method'},urgent_projects=(c,))
    blocked=next(r for r in choice['alternatives'] if r['project_id']==c)
    assert blocked['blocked'] and not blocked['authorized'] and choice['project']['id']==a
    assert select(e,urgent=(b,))['project']['id']==b
    assert e.projects()[a]['status']=='paused'
    e.transition(b,'blocked','await independent resource evidence',source,[other['evidence_id']])
    assert select(e)['project']['id']==a
    e.transition(b,'candidate','new resource evidence supplied',source,[other['evidence_id']])
    assert select(e,urgent=(b,))['project']['id']==b
    notebook.close();source.close()


@pytest.mark.parametrize('verdict', ['contradicted','unresolved'])
def test_failures_and_unknown_do_not_fake_completion(tmp_path,verdict):
    source=EvidenceJournal(tmp_path/'s.sqlite3'); notebook=EvidenceJournal(tmp_path/'p.sqlite3')
    e=LearningExecutive(notebook,gateway(tmp_path)); p=hypothesis(source)
    identifier=e.propose(p['proposal'],source,[p['evidence_id']],criteria=CompletionCriteria(max_attempts=3))
    select(e)
    for n in range(3):
        state=result(e,identifier,source,condition=dict(p['proposal']['scope'],setting='a'),episode=f'episode-{n}',verdict=verdict)
    assert state['status']=='paused' and state['disposition']=='budget_exhausted'
    assert not any(r['source']=='learning-project:assessment' for r in e.gateway.evaluator.recent(100))
    assert select(e)['project'] is None
    notebook.close();source.close()


def test_repeated_negative_evidence_can_be_sufficiently_explored_without_achievement(tmp_path):
    source=EvidenceJournal(tmp_path/'s.sqlite3'); notebook=EvidenceJournal(tmp_path/'p.sqlite3')
    e=LearningExecutive(notebook,gateway(tmp_path)); p=hypothesis(source)
    identifier=e.propose(p['proposal'],source,[p['evidence_id']]); select(e)
    for n,setting in enumerate(('a','b','a','b','a')):
        state=result(e,identifier,source,condition=dict(p['proposal']['scope'],setting=setting),episode=f'episode-{n}',verdict='contradicted')
    assert state['status']=='completed' and state['disposition']=='sufficiently_explored'
    assert state['progress']['results']=={'contradicted':5}
    notebook.close();source.close()


def test_same_episode_replication_contradiction_and_proposal_idempotence(tmp_path):
    source=EvidenceJournal(tmp_path/'s.sqlite3'); notebook=EvidenceJournal(tmp_path/'p.sqlite3')
    e=LearningExecutive(notebook,gateway(tmp_path)); p=hypothesis(source)
    identifier=e.propose(p['proposal'],source,[p['evidence_id']]); select(e)
    assert e.propose(p['proposal'],source,[p['evidence_id']])==identifier
    assert len(e.projects()[identifier]['origins'])==1
    for setting in ('a','b','a'):
        state=result(e,identifier,source,condition=dict(p['proposal']['scope'],setting=setting),episode='same')
    assert state['status']=='active' and state['progress']['episodes']==1
    state=result(e,identifier,source,condition=dict(p['proposal']['scope'],setting='b'),episode='next',verdict='contradicted')
    assert state['status']=='active' and state['progress']['support_fraction']==.75
    state=result(e,identifier,source,condition=dict(p['proposal']['scope'],setting='a'),episode='later')
    assert state['disposition']=='achieved'  # stated threshold .8, not perfection
    notebook.close();source.close()


def real_seed(root):
    root.mkdir()
    fixture=Path(__file__).parent/'fixtures/robotron-body-fire-020552'
    (root/'report.json').write_bytes((fixture/'report.json').read_bytes())
    (root/'agency.jsonl').write_bytes((fixture/'agency-response-extract.jsonl').read_bytes())
    return root


def synthetic_game(game,plan,*,verdict=None):
    game.mkdir(); now=time.monotonic(); verdict=verdict or plan['expected']
    report=dict(armed=True,result='GAME OVER',acquisition='provisional_body_agency',
        episode_end=dict(state='game_over',confirmed=True,evidence=dict(
            rule='persistent_not_gameplay_plus_no_controlled_self',not_gameplay_streak=8,
            agency_failures=1,screen=dict(state='not_gameplay',phase='terminal'),synthetic=True)),
        steps=[dict(tick=0,identity_status='provisional',action=dict(move=plan['body'],fire=plan['fire']),
            experiment=dict(prediction_id=plan['prediction_id'],track_id=9,origin_at=now))])
    (game/'report.json').write_text(json.dumps(report))
    row=dict(sample=1,capture_timestamp=now+.02,identity_status='provisional',controlled_track_id=9,
        self_track_id=None,confidence=.5,global_motion=False,
        control_execution=dict(started_at=now+.01,move=plan['body'],fire=plan['fire']),
        response_window=dict(endpoint=2,origin_at=now,move=plan['body']),
        evidence=[dict(track_id=9,reason=verdict)],tracking=dict(events=[],detections=[]))
    (game/'agency.jsonl').write_text(json.dumps(row)+'\n')


def test_real_origin_existing_chooser_three_game_campaign_completion_and_next_project(tmp_path):
    g=gateway(tmp_path); c=EvidenceJournal(tmp_path/'commitments.sqlite3'); n=EvidenceJournal(tmp_path/'projects.sqlite3')
    e=LearningExecutive(n,g); root=real_seed(tmp_path/'real')
    seed=process_completed_episode(root,tmp_path/'seed-evidence',g,c,executive=e)
    assert len(seed['proposals'])==9 and len(seed['learning_projects']['proposed'])==1
    chosen=select(e,resources=('camera-evidence','actuator-experiment-slot'),methods=('actuator-response',))
    identifier=chosen['project']['id']; project=chosen['project']
    assert project['scope']=={'body':'NE'} and project['expected']=='signed_command_response'
    # Real origin generated NE; a competing objective is generated from altered
    # synthetic measurements, not embedded in the production Executive.
    changed=real_seed(tmp_path/'changed')
    rows=[json.loads(x) for x in (changed/'agency.jsonl').read_text().splitlines()]
    for row in rows:
        control=row.get('control_execution') or {}; control['move']='SE'
        for evidence in row.get('evidence',[]): evidence['reason']='unexpected_motion'
    (changed/'agency.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    other=process_completed_episode(changed,tmp_path/'other-evidence',g,c,executive=e)
    other_id=other['learning_projects']['proposed'][0]
    fires=[]
    for index in range(3):
        selected=select(e,resources=('camera-evidence','actuator-experiment-slot'),methods=('actuator-response',))
        assert selected['project']['id']==identifier
        game=tmp_path/f'game-{index}'
        plan=select_experiment(g,c,game,horizon_seconds=60,project_context=e.chooser_context(identifier))
        assert plan['body']=='NE' and plan['project_id']==identifier
        fires.append(plan['fire']); synthetic_game(game,plan)
        completed=process_completed_episode(game,tmp_path/f'analysis-{index}',g,c,plan,e)
        assert completed['resolution']['result']=='supported'
    assert fires[0]!=fires[1]  # coverage chosen tactically, no manually selected setting
    assert e.projects()[identifier]['disposition']=='achieved'
    next_selection=select(e,resources=('camera-evidence','actuator-experiment-slot'),methods=('actuator-response',))
    assert next_selection['project']['id']==other_id
    next_plan=select_experiment(g,c,tmp_path/'next',horizon_seconds=60,project_context=e.chooser_context(other_id))
    assert next_plan['body']=='SE' and next_plan['expected']=='unexpected_motion'
    c.close();n.close()


def test_persistent_project_recall_survives_memory_recent_window(tmp_path):
    g=gateway(tmp_path); c=EvidenceJournal(tmp_path/'c.sqlite3'); n=EvidenceJournal(tmp_path/'p.sqlite3')
    e=LearningExecutive(n,g)
    process_completed_episode(real_seed(tmp_path/'real'),tmp_path/'analysis',g,c,executive=e)
    chosen=select(e,resources=('camera-evidence','actuator-experiment-slot'),methods=('actuator-response',))
    for i in range(110):
        g.remember(Experience(kind='observation',summary=f'unrelated {i}',source='controlled:unrelated',significant=True,evidence=str(i)))
    assert not any(r['source']=='ppal:actuator-response-reflection' for r in g.evaluator.recent(100))
    plan=select_experiment(g,c,tmp_path/'next',horizon_seconds=60,project_context=e.chooser_context(chosen['project']['id']))
    assert plan is not None and len(plan['alternatives'])==9
    c.close();n.close()


def test_opt_in_runner_manages_campaign_and_unchanged_terminal_guard(tmp_path):
    g=gateway(tmp_path)
    args=SimpleNamespace(root=tmp_path/'runs',seed_episode=real_seed(tmp_path/'real'),max_games=3,
        game_seconds=1.,focus=1.3,retry_wait=0,learning_projects=True,project_evidence=tmp_path/'projects.sqlite3')
    def driver(cmd,timeout):
        plan=json.loads(Path(cmd[cmd.index('--experiment-plan')+1]).read_text())
        game=Path(cmd[cmd.index('--output')+1]);synthetic_game(game,plan)
        from test_recording_handoff import seal_software_recording
        seal_software_recording(game)
        return 0
    doc=developmental_marathon(args,driver=driver,gateway=g)
    assert doc['status']=='bounded_attempts_complete' and len(doc['games'])==3
    assert len({r['experiment']['project_id'] for r in doc['games']})==1
    assert next(iter(doc['learning_projects'].values()))['disposition']=='achieved'
    assert all(r['between_game']['resolution']['result']=='supported' for r in doc['games'])
    args.root=tmp_path/'second-runs';args.seed_episode=None
    calls=[]
    def uncertain(cmd,timeout):
        calls.append(cmd); game=Path(cmd[cmd.index('--output')+1]);game.mkdir()
        assert '--experiment-plan' not in cmd  # completed campaign is not restarted
        (game/'report.json').write_text(json.dumps({'result':'TIME LIMIT','steps':[]}))
        return 0
    stopped=developmental_marathon(args,driver=uncertain,gateway=g)
    assert stopped['status']=='unverified_episode_boundary' and len(calls)==1


def test_invalid_criteria_and_non_reflection_origins_rejected(tmp_path):
    with pytest.raises(ValueError): CompletionCriteria(min_episodes=1)
    source=EvidenceJournal(tmp_path/'s.sqlite3'); notebook=EvidenceJournal(tmp_path/'p.sqlite3')
    e=LearningExecutive(notebook,gateway(tmp_path)); p=hypothesis(source)
    fake=source.append('event',{},episode='fake',producer='remote-prose',version='1')
    with pytest.raises(ValueError):e.propose(p['proposal'],source,[fake.id])
    p['proposal']['uncertainty']=float('nan')
    with pytest.raises(ValueError):e.propose(p['proposal'],source,[p['evidence_id']])
    notebook.close();source.close()


def test_dependency_requires_achievement_and_abandoned_project_is_remembered(tmp_path):
    source=EvidenceJournal(tmp_path/'s.sqlite3'); notebook=EvidenceJournal(tmp_path/'p.sqlite3')
    e=LearningExecutive(notebook,gateway(tmp_path)); p=hypothesis(source)
    prerequisite=e.propose(p['proposal'],source,[p['evidence_id']])
    record=source.append('event',{},episode='dependency',producer='Reflection',version='controlled-v1')
    proposed=reflect_project_opportunities(source,'dependency',[dict(method='opaque-test-method',
        scope={'instrument':'dependent-task'},expected='derived-expectation',conditions=[{'setting':'a'},{'setting':'b'}],
        observed_conditions=[{'setting':'a'}],evidence_ids=[record.id],dependencies=[prerequisite])])[0]
    dependent=e.propose(proposed['proposal'],source,[proposed['evidence_id']])
    choice=select(e,urgent=(dependent,))
    assert choice['project']['id']==prerequisite
    assert next(a for a in choice['alternatives'] if a['project_id']==dependent)['unmet_dependencies']==[prerequisite]
    for n,setting in enumerate(('a','b','a')):
        result(e,prerequisite,source,condition=dict(p['proposal']['scope'],setting=setting),episode=f'episode-{n}')
    assert select(e)['project']['id']==dependent
    e.transition(dependent,'abandoned','new evidence removes the objective value',source,[record.id])
    assert any(r['source']=='learning-project:lifecycle' for r in e.gateway.evaluator.recent(100))
    notebook.close();source.close()


def test_restart_recovers_assessment_and_existing_memory_handoff(tmp_path,monkeypatch):
    source=EvidenceJournal(tmp_path/'s.sqlite3'); notebook=EvidenceJournal(tmp_path/'p.sqlite3')
    g=gateway(tmp_path); e=LearningExecutive(notebook,g); p=hypothesis(source)
    identifier=e.propose(p['proposal'],source,[p['evidence_id']]);select(e)
    def fail(_):raise RuntimeError('synthetic crash after durable result')
    monkeypatch.setattr(e,'assess',fail)
    with pytest.raises(RuntimeError):
        result(e,identifier,source,condition=dict(p['proposal']['scope'],setting='a'),episode='one')
    notebook.close();notebook=EvidenceJournal(tmp_path/'p.sqlite3');e=LearningExecutive(notebook,g)
    assert e.projects()[identifier]['progress']['attempts']==1
    result(e,identifier,source,condition=dict(p['proposal']['scope'],setting='b'),episode='two')
    remember=g.remember
    def fail_handoff(experience):
        if experience.source=='learning-project:assessment':raise RuntimeError('synthetic crash before memory handoff')
        return remember(experience)
    monkeypatch.setattr(g,'remember',fail_handoff)
    with pytest.raises(RuntimeError):
        result(e,identifier,source,condition=dict(p['proposal']['scope'],setting='a'),episode='three')
    assert e.projects()[identifier]['status']=='completed'
    notebook.close();notebook=EvidenceJournal(tmp_path/'p.sqlite3');g=gateway(tmp_path);e=LearningExecutive(notebook,g)
    assert sum(r['source']=='learning-project:assessment' for r in g.evaluator.recent(100))==1
    e.consolidate()
    assert sum(r['source']=='learning-project:assessment' for r in g.evaluator.recent(100))==1
    notebook.close();source.close()


def test_four_game_runner_discovers_competing_project_and_switches_after_completion(tmp_path):
    """New simulated measurements supply another goal; no manual between-game calls."""
    from experiments.ppal.hands import AXES
    g=gateway(tmp_path)
    args=SimpleNamespace(root=tmp_path/'runs',seed_episode=real_seed(tmp_path/'real'),max_games=4,
        game_seconds=1.,focus=1.3,retry_wait=0,learning_projects=True,project_evidence=tmp_path/'projects.sqlite3')
    plans=[]
    def driver(cmd,timeout):
        plan=json.loads(Path(cmd[cmd.index('--experiment-plan')+1]).read_text());plans.append(plan)
        game=Path(cmd[cmd.index('--output')+1]);synthetic_game(game,plan)
        if len(plans)==1:
            # Controlled transport also observes an unrelated provisional
            # candidate responding differently under other recorded actions.
            body=next(d for d in sorted(AXES) if d not in ('NONE','STAY',plan['body']))
            rows=[json.loads(x) for x in (game/'agency.jsonl').read_text().splitlines()]
            for n,fire in enumerate(list(sorted(set(AXES)-{'STAY'}))[:2]):
                now=time.monotonic()+.03+n*.01
                rows.append(dict(sample=2+n,capture_timestamp=now,identity_status='provisional',
                    controlled_track_id=17,self_track_id=None,global_motion=False,
                    control_execution=dict(started_at=now-.001,move=body,fire=fire),
                    response_window=dict(endpoint=2),evidence=[dict(track_id=17,reason='different_measured_response')],
                    tracking=dict(events=[],detections=[])))
            (game/'agency.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        from test_recording_handoff import seal_software_recording
        seal_software_recording(game)
        return 0
    doc=developmental_marathon(args,driver=driver,gateway=g)
    assert len(plans)==4 and doc['status']=='bounded_attempts_complete'
    assert len({p['project_id'] for p in plans[:3]})==1
    assert plans[3]['project_id']!=plans[0]['project_id']
    assert plans[3]['expected']=='different_measured_response'
    assert doc['learning_projects'][plans[0]['project_id']]['disposition']=='achieved'
    assert all(game['between_game']['resolution']['result']=='supported' for game in doc['games'])
