"""Explicit synthetic contracts; no live animal, game, camera or motion claims."""
from dataclasses import replace
import sqlite3
import time
import pytest
from memory.evidence import EvidenceJournal
from memory.human_interaction import HumanInteractionGateway, InformationNeed, detect_need
from memory.learning_projects import LearningExecutive


def fixture_record(j, kind='pet'):
    if kind == 'pet':
        payload = dict(category='mobile_perception', observation=dict(frame=dict(source='synthetic', received_at=10)),
            tracking=dict(target=dict(id='fixture-session:1', at=10, observed=True, ambiguous=False,
                lifecycle='confirmed', confidence=.6, species_posterior=dict(cat=.55, dog=.45))))
    else:
        payload = dict(category='score_review_proposal', confidence=.4, proposed_score=100, synthetic=True)
    return j.append('observation', payload, episode='synthetic-'+kind, producer='deterministic-fixture', version='1',
                    provenance=dict(synthetic=True))


@pytest.fixture
def env(tmp_path):
    j = EvidenceJournal(tmp_path/'evidence.sqlite')
    g = HumanInteractionGateway(j)
    e = LearningExecutive(j, None)
    yield j,g,e
    j.close()


def ask(e,g,row,**kw):
    return e.consider_human_question(g,row.id,reason='Resolve an interpretation before later learning review',
        consequence=kw.get('consequence',1),priority=kw.get('priority',1),
        alternative_available=kw.get('alternative_available',False))


@pytest.mark.parametrize('kind,owner,value',[('pet','pet_observe','cat'),('robotron','robotron','readable score proposal')])
def test_restart_delayed_answer_and_consumer(env,kind,owner,value):
    j,g,e = env; row=fixture_record(j,kind)
    q=ask(e,g,row)['question_id']
    assert ask(e,g,row)['question_id']==q
    path=j.path
    # Separate connection models restart without rewriting the existing notebook.
    other=EvidenceJournal(path); resumed=HumanInteractionGateway(other)
    assert resumed.questions()[q]['status']=='pending'
    answer=resumed.answer(q,value=value,operator='fixture-human',request_id='fixture-answer-1')
    assert resumed.answer(q,value=value,operator='fixture-human',request_id='fixture-answer-1').id==answer.id
    assert answer.data['payload']['fallible'] and not answer.data['payload']['physical_authorization']
    assert answer.data['sources']==[q] and j.get(q).data['sources']==[row.id]
    assert not resumed.results('wrong-requester')
    assert resumed.results(owner)[0]['evidence_id']==answer.id
    with pytest.raises(ValueError): resumed.acknowledge('wrong-requester',answer.id)
    resumed.acknowledge(owner,answer.id)
    assert not g.results(owner)
    with pytest.raises(sqlite3.IntegrityError):
        other.conn.execute('DELETE FROM records WHERE id=?',(answer.id,))
    other.conn.rollback(); other.verify(); other.close()


@pytest.mark.parametrize('change',[dict(ambiguous=True),dict(observed=False),dict(lifecycle='reacquired'),
    dict(at=5),dict(species_posterior=dict(cat=.95,dog=.05)),dict(species_posterior=dict(cat=float('nan'),dog=.5))])
def test_pet_detection_boundaries(env,change):
    j,g,e=env; row=fixture_record(j); p=row.data['payload'];p['tracking']['target'].update(change)
    if 'nan' in str(change):
        with pytest.raises(ValueError):j.append('observation',p,episode='bad',producer='fixture',version='1')
        return
    row=j.append('observation',p,episode='bad',producer='fixture',version='1')
    assert not ask(e,g,row)['asked']


@pytest.mark.parametrize('kw',[dict(consequence=.1),dict(priority=0),dict(alternative_available=True)])
def test_value_and_priority(env,kw):
    j,g,e=env
    assert ask(e,g,fixture_record(j),**kw)['reason']=='observe_or_defer'


def test_stale_budget_expiry_and_cooldown(env):
    j,g,e=env; row=fixture_record(j); now=time.time()
    g.clock=lambda:now+301
    assert ask(e,g,row)['reason']=='stale_or_future_evidence'
    g.clock=time.time; g.max_pending=1
    q=ask(e,g,row)['question_id']
    assert ask(e,g,fixture_record(j,'robotron'))['reason']=='interruption_budget'
    g.clock=lambda:now+90000
    assert g.questions()[q]['status']=='expired'
    with pytest.raises(ValueError):g.answer(q,value='cat',operator='a',request_id='expired-answer')


def test_lifecycle_conflicts_and_replay(env):
    j,g,e=env;q=ask(e,g,fixture_record(j))['question_id']
    g.transition(q,'failed','retryable consumer outage');g.transition(q,'pending','retry')
    with pytest.raises(ValueError):g.transition(q,'expired','early')
    a=g.answer(q,value=None,explanation='unknown',operator='human',request_id='unknown-answer')
    assert g.questions()[q]['status']=='unknown'
    with pytest.raises(ValueError):g.answer(q,value='dog',operator='human',request_id='unknown-answer')
    with pytest.raises(ValueError):g.answer(q,value='dog',operator='human',request_id='different-answer')
    assert g.results('pet_observe')[0]['evidence_id']==a.id


@pytest.mark.parametrize('status',['dismissed','superseded'])
def test_terminal_states(env,status):
    j,g,e=env;q=ask(e,g,fixture_record(j))['question_id'];g.transition(q,status,'operator lifecycle')
    with pytest.raises(ValueError):g.answer(q,value='cat',operator='human',request_id='closed-answer')
    assert ask(e,g,fixture_record(j))['reason']=='duplicate_or_cooldown'


def test_schema_forgery_and_churn(env):
    j,g,e=env;r=fixture_record(j)
    need=detect_need(j,r.id,now=time.time(),reason='test',consequence=1,priority=1)
    with pytest.raises(KeyError):g.consider(replace(need,sources=('forged',)))
    with pytest.raises(ValueError):g.consider(replace(need,kind='move'))
    with pytest.raises(ValueError):g.consider(replace(need,consequence=float('nan')))
    q=g.consider(need)['question_id']
    with pytest.raises(ValueError):g.answer(q,value='drive',operator='a',request_id='bad-answer')
    # New session track never inherits a human label; no identity aliasing.
    changed=replace(need,subject='different-session:1')
    assert g.consider(changed)['question_id']!=q


def test_pr13_real_tracker_adapter_contract(env):
    tracking = pytest.importorskip('vision.mobile_tracking', reason='PR #13 contract not merged into master')
    mobile = pytest.importorskip('learning.mobile')
    j,g,e=env;tracker=tracking.PetTracker()
    adapter=mobile.MobileEvidenceAdapter(j,episode='synthetic-adapter',revision='fixture-v1')
    for at,label in [(10.,'cat'),(10.1,'dog')]:
        observation=dict(frame=dict(source='synthetic',received_at=at,pan_deg=None,yaw_deg=None,authentic=False),
            qualification='synthetic',objects=[dict(label=label,confidence=.6,box=(0,0,100,100))])
        tracked=tracker.update(observation)
        record=adapter.record(observation,tracked,{},dict(dispatched=False))
    q=ask(e,g,record)['question_id']
    answer=g.answer(q,value='cat',operator='fixture-human',request_id='tracker-answer')
    assert g.results('pet_observe')[0]['evidence_id']==answer.id
    assert j.get(q).data['sources']==[record.id]
    assert not j.get(record.id).data['payload']['execution']['dispatched']


@pytest.mark.parametrize('kind,owner,value',[('pet','pet_observe','dog'),('robotron','robotron',None)])
def test_executive_review_intake_is_atomic_and_idempotent(env,kind,owner,value):
    j,g,e=env;q=ask(e,g,fixture_record(j,kind))['question_id']
    a=g.answer(q,value=value,operator='fixture',request_id='review-intake-answer')
    reviews=e.receive_human_answers(g,owner)
    assert len(reviews)==1 and reviews[0].data['sources']==[a.id]
    assert reviews[0].data['payload']['status']=='pending_independent_review'
    assert not reviews[0].data['payload']['model_update']
    assert e.receive_human_answers(g,owner)==[]
    assert g.results(owner)==[]
