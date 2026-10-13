from dataclasses import replace
import pytest
from memory.evidence import EvidenceJournal
from experiments.comparison.runner import Plan,Metric
from experiments.comparison.robotron import commit,evaluate


def setup(tmp_path,pairs=2):
    j=EvidenceJournal(tmp_path/'e.sqlite3');episode='comparison'
    learning=j.append('event',{'category':'controlled-learning-finding'},episode=episode,producer='test',version='1')
    plan=Plan('Evidence-originated candidate changes official score','fixed physical conditions','test',
              'baseline-version','candidate-version',Metric('official_game_score',0,10000),pairs=pairs)
    conditions=dict(camera={'focus':1.3},game={'configuration':'same'},system={'revision':'frozen'},measurement={'version':'qualified-method'})
    # Simulate a preserved v1 record. New commit() calls cannot disable gates.
    fresh=commit(j,plan,conditions=conditions,sources=[learning.id],episode=episode)
    payload=fresh.data['payload'];payload.pop('require_certificates')
    protocol=j.append('event',payload,episode=episode,sources=[learning.id],
        producer='recorded-v1-fixture',version='robotron-score-comparison-v1')
    return j,plan,protocol


def records(j,protocol,**changes):
    rows=[]
    for s in protocol.data['payload']['schedule']:
        p=dict(category='robotron_evaluation_episode',source_episode='game-'+str(s['slot']),slot=s['slot'],
               policy=s['policy'],conditions=protocol.data['payload']['conditions'],confirmed_terminal=True,
               score_observations=[dict(value=1000 if s['arm']=='baseline' else 2000,phase='final',
                  qualification='independently_validated',validation_evidence='controlled-test-reference',
                  artifact_sha256='controlled-test-artifact',timestamp=1.)])
        p.update(changes)
        rows.append(j.append('observation',p,episode=protocol.data['episode'],producer='test-fixture',version='1').id)
    return rows


def test_schedule_is_frozen_and_small_score_difference_inconclusive(tmp_path):
    j,plan,p=setup(tmp_path)
    assert [s['slot'] for s in p.data['payload']['schedule']]==list(range(4))
    report=evaluate(j,p.id,plan,records(j,p)).data['payload']['report']
    assert report['status']=='inconclusive' # repeated trials required; no one-game win
    assert report['metrics']['official_game_score']['improvement']==1000
    j.verify()


@pytest.mark.parametrize('changes',[
    {'confirmed_terminal':False},
    {'score_observations':[]},
    {'score_observations':[{'value':3300,'qualification':'tracker-reported'}]},
    {'conditions':{'camera':'changed'}},
])
def test_uncertainty_never_becomes_score_improvement(tmp_path,changes):
    j,plan,p=setup(tmp_path)
    r=evaluate(j,p.id,plan,records(j,p,**changes)).data['payload']['report']
    assert r['status']=='inconclusive' and r['failures']


def test_conflicting_measurements_and_duplicate_episode(tmp_path):
    j,plan,p=setup(tmp_path);rs=records(j,p)
    first=j.get(rs[0]).data['payload'];first['score_observations'].append(dict(first['score_observations'][0],value=3300))
    amended=j.append('observation',first,episode='comparison',producer='additional-source',version='1')
    rs[0]=amended.id
    assert evaluate(j,p.id,plan,rs).data['payload']['report']['status']=='inconclusive'
    with pytest.raises(ValueError,match='independent'):evaluate(j,p.id,plan,[rs[0],rs[0]])
    with pytest.raises(ValueError,match='exact committed'):evaluate(j,p.id,replace(plan,candidate='other'),rs)


def test_preregistration_requires_learning_provenance(tmp_path):
    j,plan,p=setup(tmp_path)
    with pytest.raises(ValueError):commit(j,replace(plan,synthetic=True),conditions=p.data['payload']['conditions'],sources=[],episode='comparison')
