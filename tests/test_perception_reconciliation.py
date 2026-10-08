"""Controlled independent-witness interface fixtures, never game qualification."""
import time
import hashlib
import pytest
from PIL import Image
from experiments.ppal.progress_evidence import CaptureEvidence
from memory.evidence import EvidenceJournal,digest
from memory.evaluator import MemoryEvaluator


def source(tmp_path,*,saved=True):
    r=CaptureEvidence(tmp_path,'synthetic-witness',{},visual_hz=1)
    r.capture(Image.new('RGB',(20,20)),dict(timestamp=time.monotonic()))
    if not saved:r.capture(Image.new('RGB',(20,20)),dict(timestamp=time.monotonic()))
    obs=r.latest_observation.id
    trace=r.event('detector_trace',dict(geometry={'normalized':[100,100]},
        detections=[dict(center=[50.,50.],kind='unknown')]),at=time.monotonic())
    r.close();j=EvidenceJournal(tmp_path/'session-evidence.sqlite3')
    return j,obs,trace


def test_unretained_trace_is_plausible_not_independent_truth_and_deduplicates(tmp_path):
    j,obs,trace=source(tmp_path,saved=False)
    result=MemoryEvaluator.reconcile_perception(j,tmp_path)
    assert result[0].data['payload']['judgments'][0]['status']=='plausible_but_not_independently_observed'
    assert MemoryEvaluator.reconcile_perception(j,tmp_path)[0].id==result[0].id
    assert len(j.category_records('observation','perception_reconciliation'))==1
    j.close()


@pytest.mark.parametrize('point,clock_shift,association,expected',[
    ([50.3,50.],0,'independently_qualified','corroborated'),
    ([70.,50.],0,'independently_qualified','disputed'),
    ([50.3,50.],.01,'independently_qualified','unresolved'),
    ([50.3,50.],0,'occluded','unresolved')])
def test_exact_measurement_uncertainty_and_no_nearest_substitution(tmp_path,point,clock_shift,association,expected):
    j,obs,trace=source(tmp_path)
    capture=j.category_records('observation','camera_capture')[0]
    proof=tmp_path/'qualification.json';proof.write_text('{"simulation":true}')
    method=j.append('event',dict(category='visual_measurement_method_qualification',status='verified',
        qualification_artifact=dict(path=str(proof),sha256=hashlib.sha256(proof.read_bytes()).hexdigest())),
        episode='synthetic-witness',sources=[obs],producer='independent-visual-measurement',version='fixture')
    witness=j.append('observation' ,dict(category='independent_visual_measurement',
        observation_id=obs,artifact_sha256=capture.data['payload']['artifact']['sha256'],
        timestamp=j.get(obs).data['at']+clock_shift,geometry_sha256=digest({'normalized':[100,100]}),
        center=point,position_uncertainty=.5,internal_position_uncertainty=.5,
        detection_index=0,identity_association=association,method_reference=method.id),
        episode='synthetic-witness',at=time.monotonic(),sources=[obs],producer='independent-visual-measurement',version='fixture')
    result=MemoryEvaluator.reconcile_perception(j,tmp_path)[0]
    assert result.data['payload']['judgments'][0]['status']==expected
    assert j.get(trace).data['payload']['detections'][0]['center']==[50.,50.]
    j.verify();j.close()


def test_normal_acquisition_context_carries_reconciliation_without_rewriting_sources(tmp_path):
    import json
    from memory.episode_identity import finalize_capture
    from learning.retrospective import ingest,inventory
    from learning.datasets import ExperienceDataset
    root=tmp_path/'captured';root.mkdir()
    j,obs,trace=source(root);j.close()
    (root/'report.json').write_text(json.dumps({'result':'SIMULATED DIAGNOSTIC','steps':[]}))
    finalize_capture(root);before=inventory(root)
    notebook=EvidenceJournal(tmp_path/'learning-evidence.sqlite3')
    dataset=ExperienceDataset(notebook,tmp_path/'pixels')
    first=ingest(root,dataset)
    contexts=notebook.category_records('observation','learning_context_reference')
    context=contexts[0].data['payload']['context']
    assert context['perception_reconciliation']['counts']['unresolved']==1
    assert any(q['category']=='perception_reconciliation' for q in context['questions'])
    assert inventory(root)==before
    assert ingest(root,dataset)['record_id']==first['record_id']
    assert len(notebook.category_records('observation','learning_context_reference'))==1
    notebook.verify();notebook.close()
