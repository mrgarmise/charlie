from types import SimpleNamespace
from unittest.mock import Mock
import json
import pytest
from main import parser, main
from learning.capabilities import default_registry
from learning.mobile import MobileEvidenceAdapter
from learning.mobile_runtime import run_mobile, import_mobile_evidence
from learning.resources import DevelopmentResources
from memory.evidence import EvidenceJournal
from memory.learning_projects import LearningExecutive, reflect_project_opportunities


@pytest.fixture(autouse=True)
def isolated_fixture_resource_owner(monkeypatch):
    # Other concurrently running suites may own the global gameplay lease.
    # These integration inputs are explicitly offline fixtures. Resource vetoes
    # are exercised independently in test_mobile_perception.py.
    monkeypatch.setattr('learning.cycle.gameplay_active',lambda:False)


def fixture(path):
    frames=[dict(at=1+i*.25,objects=[dict(label='cat',box=[10,10,30,30],confidence=.9)],
                 depth=dict(kind='relative',clearance_certified=False),geometry=[40,40]) for i in range(4)]
    path.write_text(json.dumps(dict(schema='charlie.mobile.fixture.v1',frames=frames)))
    return path


def test_main_unarmed_end_to_end_and_persistence(tmp_path,monkeypatch):
    import hardware.elegoo_mobile
    import hardware.elegoo_camera
    monkeypatch.setattr(hardware.elegoo_mobile.ElegooMobileBase,'connect',Mock(side_effect=AssertionError('physical connect')))
    monkeypatch.setattr(hardware.elegoo_camera.ElegooCamera,'open',Mock(side_effect=AssertionError('camera connect')))
    path=fixture(tmp_path/'fixture.json')
    main(['--mobile-replay',str(path),'--learning-state',str(tmp_path/'state')])
    j=EvidenceJournal(tmp_path/'state/mobile-evidence.sqlite3',read_only=True)
    rows=j.category_records('observation','mobile_perception');assert len(rows)==4
    assert all(not r.data['payload']['execution']['dispatched'] for r in rows)
    assert all(r.data['provenance']['authentic'] is False for r in rows)
    assert rows[-1].data['payload']['tracking']['target']['label']=='cat'
    assert not j.category_records('event','learning_project_proposal')
    j.verify();j.close()
    hardware.elegoo_mobile.ElegooMobileBase.connect.assert_not_called()
    hardware.elegoo_camera.ElegooCamera.open.assert_not_called()


def test_lifecycle_imports_once_without_second_executive(tmp_path):
    path=fixture(tmp_path/'fixture.json');state=tmp_path/'state'
    args=parser().parse_args(['--mobile-replay',str(path),'--learning-state',str(state)])
    run_mobile(args,DevelopmentResources())
    j=EvidenceJournal(state/'learning-evidence.sqlite3');gateway=Mock()
    e=LearningExecutive(j,gateway)
    lifecycle=SimpleNamespace(output=state,journal=j,executive=e,gateway=gateway)
    assert import_mobile_evidence(lifecycle)
    assert not import_mobile_evidence(lifecycle)
    assert len(j.category_records('observation','mobile_perception'))==4
    assert e.projects()=={}
    j.close()


def test_registry_discovery_and_authority():
    r=default_registry()
    assert {c['id'] for c in r.describe()} >= {'mobile-observe','mobile-navigation-proposal','mobile-mobility'}
    with pytest.raises(ValueError):r.invoke('mobile-observe',resources=[],authorized=[],service=Mock())
    with pytest.raises(ValueError):r.invoke('mobile-mobility',resources=['qualified-car-local-controller','motion-lease'],authorized=['mobile-mobility'])


def test_existing_executive_bookmarks_survive_disconnection_and_restart(tmp_path):
    # Explicit synthetic Reflection source tests continuity, NOT authentic learning.
    j=EvidenceJournal(tmp_path/'journal.sqlite3');gateway=Mock()
    observation=j.append('observation',dict(fixture=True),episode='fixture',producer='fixture',version='1')
    proposals=reflect_project_opportunities(j,'fixture',[dict(method='mobile-observe',scope=dict(body='fixture'),
        expected='fixture property',evidence_ids=[observation.id],conditions=[dict(v=1),dict(v=2)],
        observed_conditions=[dict(v=1)],requires=['mobile-camera','mobile-models'])])
    e=LearningExecutive(j,gateway);p=proposals[0]
    identifier=e.propose(p['proposal'],j,[p['evidence_id']])
    adapter=MobileEvidenceAdapter(j,episode='fixture',revision='1',executive=e)
    request=adapter.request(identifier,reason='fixture observation opportunity')
    assert e.select(methods=['mobile-observe'],resources=[],authorized_methods=[])['project'] is None
    j.close()
    j=EvidenceJournal(tmp_path/'journal.sqlite3');e=LearningExecutive(j,gateway)
    adapter=MobileEvidenceAdapter(j,episode='fixture',revision='1',executive=e)
    assert adapter.pending()[0].id==request.id
    selected=e.select(methods=['mobile-observe'],resources=['mobile-camera','mobile-models'],authorized_methods=['mobile-observe'])
    assert selected['project']['id']==identifier
    assert selected['project']['expected']=='fixture property'
    j.verify();j.close()


def test_no_hardware_combination_with_mobile(tmp_path):
    with pytest.raises(ValueError):main(['--hardware','--mobile-replay',str(tmp_path/'unused')])


def test_capability_request_completion_across_session_boundary(tmp_path):
    j=EvidenceJournal(tmp_path/'journal.sqlite3');e=Mock();e.projects.return_value={'project':{}}
    adapter=MobileEvidenceAdapter(j,episode='request-session',revision='1',executive=e)
    request=adapter.request('project',reason='fixture')
    obs=j.append('observation',dict(category='mobile_perception'),episode='later-session',producer='fixture',version='1')
    adapter.episode='later-session'
    adapter.complete(request.id,obs.id)
    assert adapter.pending()==[]
    j.verify();j.close()


def test_independent_replay_evaluator_detects_misses_false_positives_switches():
    from vision.mobile_evaluation import evaluate_frames
    labels=[dict(frame_id=str(i),objects=[dict(label='cat',box=[1,1,10,10],identity='pet-a')]) for i in range(3)]
    predictions=[dict(frame_id=str(i),tracks=[dict(label='cat',box=[1,1,10,10],id=str(i),observed=True,ambiguous=False)]) for i in range(2)]
    predictions.append(dict(frame_id='2',tracks=[dict(label='dog',box=[20,1,30,10],id='dog',observed=True,ambiguous=False)]))
    result=evaluate_frames(predictions,labels,label_provenance='handwritten offline control, NOT authentic pet evidence')
    assert result['by_class']['cat']['recall']==2/3
    assert result['by_class']['dog']['false_positives']==1
    assert result['track_switches']==1
