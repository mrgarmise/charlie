"""Software fixtures only; these do not demonstrate authentic learning."""
from learning.lifecycle import DevelopmentLifecycle
from learning.acquisition import retain_dependency_request, investigate_requests, satisfy_artifact_requests
from learning.datasets import SCOPE
from PIL import Image


def request(life, name, required):
    origin=life.journal.append('observation',dict(category='fixture_origin',name=name),
        episode=SCOPE,producer='explicit-software-fixture',version='1')
    return retain_dependency_request(life.journal,origin.id,work_id=name,
        required_evidence=required,reason='Fixture missing evidence')


def test_unavailable_search_is_durable_and_changed_source_reconsidered(tmp_path):
    state=tmp_path/'state';root=tmp_path/'missing'
    life=DevelopmentLifecycle(state,[root])
    original=request(life,'original-question',['Independent trajectories'])
    result=investigate_requests(life.dataset,[root],provenance=life.provenance)
    life.executive.receive_evidence_searches()
    p=life.journal.get(result[0]).data['payload']
    assert p['status']=='unsatisfied' and not p['searched_sources'][0]['available']
    assert p['request_id']==original.id and not p['physical_authorization']
    assert not investigate_requests(life.dataset,[root],provenance=life.provenance)
    count=len(life.journal.records());life.close()
    life=DevelopmentLifecycle(state,[root])
    assert not investigate_requests(life.dataset,[root],provenance=life.provenance)
    assert not life.executive.receive_evidence_searches()
    assert len(life.journal.records())==count
    root.mkdir()
    assert len(investigate_requests(life.dataset,[root],provenance=life.provenance))==1
    assert len(life.executive.receive_evidence_searches())==1
    assert len(life.journal.category_records('event','learning_evidence_request'))==1
    life.close()


def test_two_dependencies_deliver_original_bytes_without_independent_experience(tmp_path):
    life=DevelopmentLifecycle(tmp_path/'state',[])
    image=tmp_path/'fixture.png';Image.new('RGB',(16,16),(10,20,30)).save(image)
    example=life.dataset.add(image,episode='explicit-software-group',source={'kind':'simulation'},metadata={'simulation':True})
    p=example.data['payload']
    req=request(life,'visual-artifact:'+example.id,[dict(type='preserved_pixel_artifact',example_id=example.id,sha256=p['pixel_sha256'])])
    other=request(life,'other-question',['Independently measured physical observation'])
    assert satisfy_artifact_requests(life.dataset)
    results=investigate_requests(life.dataset,[],provenance=life.provenance)
    outcomes={life.journal.get(i).data['payload']['request_id']:life.journal.get(i).data['payload'] for i in results}
    assert outcomes[req.id]['status']=='delivered'
    assert outcomes[other.id]['status']=='unsatisfied'
    assert all(p['new_independent_experience'] is False for p in outcomes.values())
    assert len(life.executive.receive_evidence_searches())==2
    assert not life.executive.receive_evidence_searches()
    assert len(life.dataset.examples())==1
    life.close()


def test_existing_bookmark_commission_is_idempotent(tmp_path):
    life=DevelopmentLifecycle(tmp_path/'state',[])
    life.executive._event(dict(op='proposed',project=dict(id='retained-project',goal='Fixture question',
        status='paused',experiment_history=[],origins=[],hypothesis_evidence=[])),[])
    bookmark=life.executive._event(dict(op='evidence_continuation',project_id='retained-project',
        required_evidence=['Independent measurements'],physical_authorization=False),[])
    ids=life.executive.commission_evidence_searches()
    assert ids==life.executive.commission_evidence_searches()
    r=life.journal.get(ids[0]);p=r.data['payload']
    assert r.data['sources']==[bookmark.id] and p['work_id']=='retained-project'
    assert p['required_evidence']==bookmark.data['payload']['required_evidence']
    assert not p['physical_authorization']
    life.close()


def test_corrupt_inbox_deduplicated_and_changed_bytes_retried(tmp_path):
    life=DevelopmentLifecycle(tmp_path/'state',[])
    inbox=life.output/'acquisition-inbox';inbox.mkdir()
    source=inbox/'fixture.json';source.write_text('{broken')
    life.acquire();life.acquire()
    assert len(life.journal.category_records('event','acquisition_delivery_rejected'))==1
    source.write_text('[]');life.acquire()
    assert len(life.journal.category_records('event','acquisition_delivery_rejected'))==2
    assert not life.journal.category_records('observation','independent_motion_corpus')
    life.close()


def test_rejected_delivery_retries_when_external_artifact_changes(tmp_path):
    import json
    life=DevelopmentLifecycle(tmp_path/'state',[])
    inbox=life.output/'acquisition-inbox';inbox.mkdir()
    proof=tmp_path/'missing-proof.json'
    (inbox/'fixture.json').write_text(json.dumps(dict(source_kind='independent_measurement',
        qualification_artifact=dict(path=str(proof),sha256='not-a-valid-hash'),episodes=[])))
    life.acquire();life.acquire()
    assert len(life.journal.category_records('event','acquisition_delivery_rejected'))==1
    proof.write_text('Explicit software fixture; not qualification')
    life.acquire();life.acquire()
    assert len(life.journal.category_records('event','acquisition_delivery_rejected'))==2
    assert not life.journal.category_records('observation','independent_motion_corpus')
    life.close()


def test_restart_between_acquisition_and_executive_delivery(tmp_path):
    state=tmp_path/'state';life=DevelopmentLifecycle(state,[])
    original=request(life,'retained-question',['Original input'])
    searches=investigate_requests(life.dataset,[],provenance=life.provenance)
    life.close()
    life=DevelopmentLifecycle(state,[])
    assert not investigate_requests(life.dataset,[],provenance=life.provenance)
    assert len(life.executive.receive_evidence_searches())==1
    event=next(r for r in life.journal.records('event') if r.data['payload'].get('op')=='evidence_search_received')
    assert event.data['payload']['request_id']==original.id
    assert event.data['payload']['search_id']==searches[0]
    assert not life.executive.receive_evidence_searches()
    life.close()
