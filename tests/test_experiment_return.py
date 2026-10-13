import json
from pathlib import Path
import time
from types import SimpleNamespace

import pytest

from memory.evidence import EvidenceJournal
from memory.evaluator import MemoryEvaluator
from memory.gateway import MemoryGateway
from memory.store import JsonlStore
from experiments.ppal.episode_evidence import import_episode
from experiments.ppal.reflect_robotron import reflect_actuator_evidence
from experiments.ppal.experiment_return import select_experiment, experimental_action, resolve_experiment
from experiments.ppal.models import Action, Intent, Position, WorldState


def gateway(tmp):
    return MemoryGateway(evaluator=MemoryEvaluator(tmp/'eval.sqlite3',exploration_rate=0),
                         store=JsonlStore(tmp/'selected.jsonl'))


def seed(root):
    root.mkdir(parents=True)
    (root/'report.json').write_text(json.dumps({'result':'GAME OVER','steps':[]}))
    rows=[]
    for index,fire in enumerate(('NW','SE'),1):
        rows.append(dict(sample=index,capture_timestamp=float(index),identity_status='provisional',
            self_track_id=None,controlled_track_id=146,confidence=.5,command=[1,-1],
            control_execution={'started_at':index-.1,'move':'NE','fire':fire},
            response_window={'endpoint':2},evidence=[dict(track_id=146,reason='signed_command_response')],
            tracking=dict(events=[],detections=[{'track_id':146,'center':[20+index,20-index]}])))
    (root/'agency.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    return root


def prepare(tmp):
    g=gateway(tmp);root=seed(tmp/'seed');j=EvidenceJournal(tmp/'seed.sqlite3')
    episode=import_episode(root,j)
    assert reflect_actuator_evidence(root,j,episode,g)
    c=EvidenceJournal(tmp/'commitments.sqlite3')
    plan=select_experiment(g,c,tmp/'next',horizon_seconds=60)
    assert plan and plan['body']=='NE' and plan['fire'] not in ('NW','SE')
    return g,j,c,plan


@pytest.mark.parametrize('verdict,expected',[('signed_command_response','supported'),
                                           ('wrong_way','contradicted'),(None,'unresolved')])
def test_prediction_precedes_actual_different_action_and_resolves(tmp_path,verdict,expected):
    g,j,c,plan=prepare(tmp_path)
    world=WorldState(1,Position(30,30),(),(),True)
    baseline=Action('W','N','baseline')
    action,reason=experimental_action(plan,world,Intent('explore'),baseline,
                                    {'identity_status':'provisional'},now=time.monotonic())
    assert (action.move,action.fire)!= (baseline.move,baseline.fire)
    root=tmp_path/'next';root.mkdir()
    origin=time.monotonic();ended=origin+.05
    context={'prediction_id':plan['prediction_id'],'track_id':9,'origin_at':origin,
             'identity_status':'provisional','baseline_action':{'move':'W','fire':'N'}}
    (root/'report.json').write_text(json.dumps({'result':'TIME LIMIT','steps':[{'experiment':context,'action':{'move':action.move,'fire':action.fire}}]}))
    row=dict(sample=1,capture_timestamp=ended,identity_status='provisional',self_track_id=None,
        response_window={'endpoint':2,'origin_at':origin,'move':'NE'},global_motion=False,
        control_execution={'started_at':origin+.01,'move':action.move,'fire':action.fire},
        evidence=[{'track_id':9,'reason':verdict}] if verdict else [],tracking={'events':[],'detections':[]})
    (root/'agency.jsonl').write_text(json.dumps(row)+'\n')
    e=EvidenceJournal(tmp_path/'next.sqlite3');episode=import_episode(root,e)
    result=resolve_experiment(root,e,episode,c,plan,g)
    assert result['result']==expected and result['score_attribution'] is None
    assert plan['prediction_at']<origin<ended
    assert c.get(plan['prediction_id']).sequence<c.records('resolution')[0].sequence
    assert 'prediction' in {r.data['kind'] for r in c.records()}
    if expected=='unresolved':assert 'no usefulness credit' in result['belief_change']
    if expected=='contradicted':
        next_plan=select_experiment(g,c,tmp_path/'later',horizon_seconds=60)
        assert next_plan['memory_id']!=plan['memory_id']
        assert next_plan['fire']!=plan['fire']
    for item in (j,c,e):item.close()


def test_unknown_no_slot_and_superseded_memory(tmp_path):
    g,j,c,plan=prepare(tmp_path)
    world=WorldState(1,Position(30,30),(),(),True)
    assert experimental_action(plan,world,Intent('explore'),Action('W','N'),{'identity_status':'unknown'},now=time.monotonic())[0] is None
    assert experimental_action(plan,world,Intent('evade'),Action('W','N'),{'identity_status':'provisional'},now=time.monotonic())[0] is None
    g.evaluator.correct(plan['memory_id'],'not applicable','independent correction')
    revised=select_experiment(g,c,tmp_path/'later',horizon_seconds=60)
    assert revised and revised['memory_id']!=plan['memory_id']
    for row in g.evaluator.recent(100):
        g.evaluator.correct(row['id'],'not applicable','independent correction')
    assert select_experiment(g,c,tmp_path/'none',horizon_seconds=60) is None
    j.close();c.close()


def test_direction_fire_and_expected_result_are_generated_from_data(tmp_path):
    root=seed(tmp_path/'different')
    rows=[json.loads(x) for x in (root/'agency.jsonl').read_text().splitlines()]
    for row in rows:
        row['control_execution']['move']='SE'
        row['evidence'][0]['reason']='wrong_way'
    # Different familiarity evidence must choose a different FIRE setting.
    for n in range(5):
        rows.append(dict(sample=10+n,capture_timestamp=10.+n,identity_status='unknown',
            control_execution={'started_at':10.+n,'move':'STAY','fire':'N'},tracking={'events':[],'detections':[]}))
    (root/'agency.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    g=gateway(tmp_path);j=EvidenceJournal(tmp_path/'changed.sqlite3');ep=import_episode(root,j)
    reflect_actuator_evidence(root,j,ep,g)
    c=EvidenceJournal(tmp_path/'commit.sqlite3');plan=select_experiment(g,c,tmp_path/'next',horizon_seconds=60)
    assert (plan['body'],plan['fire'],plan['expected'])==('SE','N','wrong_way')
    assert len(plan['alternatives'])==9
    j.close();c.close()


def test_actual_body_fire_evidence_selects_experiment_without_supplied_strategy(tmp_path):
    source=Path(__file__).parent/'fixtures/robotron-body-fire-020552'
    root=tmp_path/'real';root.mkdir()
    (root/'report.json').write_bytes((source/'report.json').read_bytes())
    (root/'agency.jsonl').write_bytes((source/'agency-response-extract.jsonl').read_bytes())
    g=gateway(tmp_path);j=EvidenceJournal(tmp_path/'real.sqlite3');episode=import_episode(root,j)
    proposals=reflect_actuator_evidence(root,j,episode,g)
    assert len(proposals)==9
    assert all(p['proposal']['body']=='NE' for p in proposals)
    assert proposals[0]['proposal']['source_fire_settings']==['NW','SE']
    assert proposals[0]['proposal']['score_claim'] is None
    c=EvidenceJournal(tmp_path/'commit.sqlite3')
    plan=select_experiment(g,c,tmp_path/'next',horizon_seconds=60)
    assert plan['body']=='NE' and plan['fire']=='NONE' and plan['source_episode']==episode
    j.close();c.close()


def test_three_unattended_attempts_have_behavioral_return_path(tmp_path,monkeypatch):
    from experiments.ppal import marathon_robotron as marathon
    g=gateway(tmp_path);root=seed(tmp_path/'seed')
    args=SimpleNamespace(root=tmp_path/'runs',seed_episode=root,max_games=3,game_seconds=1.,focus=1.3,retry_wait=0)
    delivered=[]
    def driver(cmd,timeout):
        game=Path(cmd[cmd.index('--output')+1]);game.mkdir()
        plan=json.loads(Path(cmd[cmd.index('--experiment-plan')+1]).read_text())
        now=time.monotonic();action=Action(plan['body'],plan['fire'])
        # Synthetic transport episode; real live hook covered separately.
        delivered.append((action.move,action.fire))
        report={'armed':True,'acquisition':'provisional_body_agency','result':'GAME OVER','score':None,
                'episode_end':{'state':'game_over','confirmed':True,'evidence':{'synthetic_terminal':True,'rule':'persistent_not_gameplay_plus_no_controlled_self',
                    'not_gameplay_streak':8,'agency_failures':1,'screen':{'state':'not_gameplay','phase':'terminal'}}},
                'steps':[{'tick':0,'identity_status':'provisional','action':{'move':action.move,'fire':action.fire},
                          'experiment':{'prediction_id':plan['prediction_id'],'track_id':9,'origin_at':now}}]}
        (game/'report.json').write_text(json.dumps(report))
        row=dict(sample=1,capture_timestamp=now+.02,identity_status='provisional',controlled_track_id=9,
                 self_track_id=None,confidence=.5,global_motion=False,
                 control_execution={'started_at':now+.01,'move':action.move,'fire':action.fire},
                 response_window={'endpoint':2,'origin_at':now,'move':action.move},
                 evidence=[{'track_id':9,'reason':'signed_command_response'}],tracking={'events':[],'detections':[]})
        (game/'agency.jsonl').write_text(json.dumps(row)+'\n')
        from test_recording_handoff import seal_software_recording
        seal_software_recording(game)
        return 0
    result=marathon.developmental_marathon(args,driver=driver,gateway=g)
    assert result['status']=='bounded_attempts_complete' and len(result['games'])==3
    assert len(set(delivered))==1 and delivered[0][0]=='NE'
    assert all(r['between_game']['resolution']['result']=='supported' for r in result['games'])
    assert all(r['experiment']['memory_id'] for r in result['games'])


def test_unverified_boundary_stops_without_second_start(tmp_path):
    from experiments.ppal import marathon_robotron as marathon
    g=gateway(tmp_path)
    args=SimpleNamespace(root=tmp_path/'runs',seed_episode=None,max_games=3,game_seconds=1.,focus=1.3,retry_wait=0)
    calls=[]
    def driver(cmd,timeout):
        assert '--experiment-plan' not in cmd
        calls.append(cmd);game=Path(cmd[cmd.index('--output')+1]);game.mkdir()
        (game/'report.json').write_text(json.dumps({'result':'TIME LIMIT','steps':[],'episode_end':{'confirmed':False}}))
        return 0
    result=marathon.developmental_marathon(args,driver=driver,gateway=g)
    assert len(calls)==1 and result['status']=='unverified_episode_boundary'
    assert result['games'][0]['experiment'] is None


def test_single_observation_admits_exploration_without_improvement_claim(tmp_path):
    g=gateway(tmp_path);root=seed(tmp_path/'single')
    path=root/'agency.jsonl';path.write_text(path.read_text().splitlines()[0]+'\n')
    j=EvidenceJournal(tmp_path/'source.sqlite3');episode=import_episode(root,j)
    proposals=reflect_actuator_evidence(root,j,episode,g)
    assert proposals and all(p['proposal']['evidence_windows']==1 for p in proposals)
    c=EvidenceJournal(tmp_path/'commitments.sqlite3')
    plan=select_experiment(g,c,tmp_path/'next',horizon_seconds=60)
    assert plan and plan['max_actions']==1 and plan['body']=='NE'
    assert all(p['proposal']['score_claim'] is None for p in proposals)
    assert not c.category_records('event','capability_activation')
    j.close();c.close()
