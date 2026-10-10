"""Protocol-validation fixtures only. No authentic identity or motion labels."""
import json
import pytest
from learning.datasets import sha
from learning.meditation import qualify_corpus
from learning.acquisition import satisfy_motion_requests,retain_dependency_request
from memory.evaluator import MemoryEvaluator
from learning.lifecycle import DevelopmentLifecycle
from test_ala_cycle import make
from test_meditation_candidate import corpus


def protocol_fixture(tmp_path):
    path=corpus(None,tmp_path);data=json.loads(path.read_text())
    proof=dict(schema='charlie-motion-measurement-protocol-v1',
        method=dict(id='explicit-software-fixture-not-a-real-measurement-method',revision='test-1',observer='fixture-observer',observed_at='2026-10-10T00:00:00Z'),
        independence=dict(candidate_predictions_used=False,tracker_identities_used_as_truth=False,training_overlap=False,
            unresolved_correlations=[],shared_inputs='synthetic fixture frames',shared_assumptions='controlled fixture only',
            failure_modes='not a real motion protocol',identity_verification='fixture identity assertions',geometry_verification='synthetic coordinates'),measurements=[])
    for e in data['episodes']:
        for f in e['frames']:
            proof['measurements'].append(dict(source_episode=e['source_episode'],artifact_sha256=f['artifact']['sha256'],timestamp=f['timestamp'],
                player=f['player'],targets=f['targets'],threats=f['threats'],uncertainty_board_units=.2,identity_status='independently_verified'))
    reference=tmp_path/'protocol.json';reference.write_text(json.dumps(proof))
    data['qualification_artifact']=dict(path=str(reference),sha256=sha(reference))
    return data,reference,proof


def test_protocol_binding_is_not_physical_admission(tmp_path):
    data,path,proof=protocol_fixture(tmp_path)
    assessment=MemoryEvaluator.assess_motion_measurement_provenance(data)
    assert assessment['method']['id'].startswith('explicit-software-fixture')
    ds,g=make(tmp_path);source=tmp_path/'corpus.json';source.write_text(json.dumps(data))
    # Passing protocol syntax cannot promote unqualified reports/bin files to originals.
    with pytest.raises(ValueError,match='qualified original occurrence'):qualify_corpus(ds,source)
    record=qualify_corpus(ds,source,allow_fixture=True);assert record.data['payload']['fixture_only']


@pytest.mark.parametrize('mutation',['candidate-output','tracker-truth','training-overlap','unresolved-correlation','changed-trajectory','nonfinite-uncertainty','missing-observer','opaque-proof'])
def test_correlated_fabricated_and_incomplete_measurement_protocol_rejected(tmp_path,mutation):
    data,path,proof=protocol_fixture(tmp_path)
    if mutation=='candidate-output':proof['independence']['candidate_predictions_used']=True
    if mutation=='tracker-truth':proof['independence']['tracker_identities_used_as_truth']=True
    if mutation=='training-overlap':proof['independence']['training_overlap']=True
    if mutation=='unresolved-correlation':proof['independence']['unresolved_correlations']=['same-model-identity-assumption']
    if mutation=='changed-trajectory':proof['measurements'][0]['player']=[90,90]
    if mutation=='nonfinite-uncertainty':proof['measurements'][0]['uncertainty_board_units']=float('nan')
    if mutation=='missing-observer':proof['method'].pop('observer')
    path.write_text('Opaque unsupported qualification assertion' if mutation=='opaque-proof' else json.dumps(proof))
    data['qualification_artifact']['sha256']=sha(path)
    with pytest.raises(ValueError):MemoryEvaluator.assess_motion_measurement_provenance(data)


def test_fixture_corpus_cannot_satisfy_normal_executive_dependency(tmp_path):
    life=DevelopmentLifecycle(tmp_path/'state',[])
    life.executive._event(dict(op='proposed',project=dict(id='fixture-project',goal='Fixture temporal dependency',
        status='paused',experiment_history=[],origins=[],hypothesis_evidence=[])),[])
    bookmark=life.executive._event(dict(op='evidence_continuation',project_id='fixture-project',required_evidence=['Independent trajectories'],
        acceptance_criteria={'interface':'existing independent_motion_corpus acquisition inbox'}),[])
    request=retain_dependency_request(life.journal,bookmark.id,work_id='fixture-project',required_evidence=['Independent trajectories'],reason='Fixture dependency')
    source=corpus(None,tmp_path);record=qualify_corpus(life.dataset,source,allow_fixture=True)
    assert satisfy_motion_requests(life.dataset)==[]
    assert not life.journal.category_records('event','acquisition_dependency_satisfied')
    life.close()
